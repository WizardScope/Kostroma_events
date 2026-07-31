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

# 2. Парсинг RSS-ленты (намного надежнее, чем HTML-парсинг)
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

# Ключевые слова для фильтрации событий
keywords = ['конкурс', 'фестиваль', 'праздник', 'ярмарка', 'день города', 'забег', 'турнир', 'акция', 'мероприятие', 'выставка']
added_count = 0
today_str = datetime.now().strftime("%d.%m.%Y %H:%M")

for item in items:
    title = item.find('title').text if item.find('title') is not None else "Без названия"
    link = item.find('link').text if item.find('link') is not None else ""
    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "Дата не указана"
    
    # Проверяем наличие ключевых слов (в нижнем регистре)
    title_lower = title.lower()
    matched_keywords = [kw for kw in keywords if kw in title_lower]
    
    if matched_keywords:
        print(f"  ➕ Найдено совпадение: '{title}' (ключевые слова: {', '.join(matched_keywords)})")
        
        # Генерируем идею для акции на основе контекста
        promo_idea = "Стандартный квиз / VR-тур / Консультация"
        if 'город' in title_lower or 'день' in title_lower:
            promo_idea = "Акция 'Город для жизни' + VR-тур по новостройкам"
        elif 'спорт' in title_lower or 'забег' in title_lower:
            promo_idea = "Акция 'Здоровая семья' + спонсорство зоны отдыха"
        elif 'студент' in title_lower or 'вуз' in title_lower or 'школь' in title_lower:
            promo_idea = "Лекторий 'Первый старт' + скидка на услуги"
        elif 'бизнес' in title_lower or 'предприниматель' in title_lower:
            promo_idea = "Спецпредложение для ИП и самозанятых"
            
        row = [today_str, title, pub_date, "Кострома", link, promo_idea]
        try:
            worksheet.append_row(row)
            added_count += 1
        except Exception as e:
            print(f"  ⚠️ Ошибка записи строки: {e}")

print(f"\n🎉 Парсинг завершен. Добавлено новых строк в таблицу: {added_count}")
