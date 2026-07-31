import os
import json
import gspread
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

print("🚀 Запуск парсера событий Костромы для 'Этажей'...")

# 1. Настройка Google Sheets
sa_key_json = os.environ.get('GCP_SA_KEY')
if not sa_key_json:
    print("❌ ОШИБКА: Секрет GCP_SA_KEY не найден в настройках GitHub!")
    exit(1)

try:
    sa_creds = json.loads(sa_key_json)
    gc = gspread.service_account_from_dict(sa_creds)
    
    sheet_id = os.environ.get('SHEET_ID', '')
    if sheet_id:
        sh = gc.open_by_key(sheet_id)
        print(f"✅ Успешно подключились к таблице по ID: {sh.title}")
    else:
        sh = gc.open("Кострома_События_Этажи")
        print(f"✅ Успешно подключились к таблице по имени: {sh.title}")
        
    worksheet = sh.sheet1
except Exception as e:
    print(f"❌ Ошибка подключения к Google Таблице: {e}")
    print("💡 Проверьте, что вы дали права 'Редактор' email-адресу из вашего JSON-ключа.")
    exit(1)

# 2. Парсинг RSS-ленты
url = "https://kostroma.today/feed/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    print(f"✅ Успешно загрузили RSS-ленту: {url}")
except Exception as e:
    print(f"❌ Ошибка загрузки ленты: {e}")
    exit(1)

# Парсим XML
try:
    root = ET.fromstring(response.content)
except ET.ParseError as e:
    print(f"❌ Ошибка парсинга XML: {e}")
    exit(1)

items = root.findall('.//item')
print(f"🔍 Найдено всего новостей в ленте: {len(items)}")

# Ключевые слова для фильтрации событий (расширенный список)
keywords = [
    'конкурс', 'фестиваль', 'праздник', 'ярмарка', 'день города', 'забег', 
    'турнир', 'акция', 'мероприятие', 'выставка', 'форум', 'квест', 'гуляния'
]

added_count = 0
today_str = datetime.now().strftime("%d.%m.%Y %H:%M")

for item in items:
    title = item.find('title').text if item.find('title') is not None else "Без названия"
    link = item.find('link').text if item.find('link') is not None else ""
    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "Дата не указана"
    
    # Получаем описание новости (там часто бывают ключевые слова)
    description = item.find('description')
    desc_text = description.text.lower() if description is not None and description.text else ""
    
    # Проверяем наличие ключевых слов в заголовке ИЛИ в описании
    text_to_check = (title.lower() + " " + desc_text)
    matched_keywords = [kw for kw in keywords if kw in text_to_check]
    
    if matched_keywords:
        print(f"  ➕ Найдено совпадение: '{title[:50]}...' (ключевые слова: {', '.join(matched_keywords)})")
        
        # Генерируем идею для акции на основе контекста
        promo_idea = "Стандартный квиз / VR-тур / Консультация"
        if 'город' in text_to_check or 'день' in text_to_check:
            promo_idea = "Акция 'Город для жизни' + VR-тур по новостройкам"
        elif 'спорт' in text_to_check or 'забег' in text_to_check:
            promo_idea = "Акция 'Здоровая семья' + спонсорство зоны отдыха"
        elif 'студент' in text_to_check or 'вуз' in text_to_check or 'школь' in text_to_check:
            promo_idea = "Лекторий 'Первый старт' + скидка на услуги"
        elif 'бизнес' in text_to_check or 'предприниматель' in text_to_check:
            promo_idea = "Спецпредложение для ИП и самозанятых"
        elif 'конкурс' in text_to_check or 'выставка' in text_to_check:
            promo_idea = "Спонсорство призового фонда + брендирование зоны"
            
        row = [today_str, title.strip(), pub_date.strip(), "Кострома", link, promo_idea]
        try:
            worksheet.append_row(row)
            added_count += 1
        except Exception as e:
            print(f"  ⚠️ Ошибка записи строки: {e}")

print(f"\n🎉 Парсинг завершен. Добавлено новых строк в таблицу: {added_count}")
