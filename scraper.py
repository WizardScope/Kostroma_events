import os
import json
import gspread
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib3

# Отключаем предупреждения о старых SSL-сертификатах (частая проблема госсайтов)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🚀 Запуск мультисорсного парсера департаментов Костромской области для 'Этажей'...")

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
    else:
        sh = gc.open("Кострома_События_Этажи")
        
    worksheet = sh.sheet1
    print(f"✅ Подключились к таблице: {sh.title}")
except Exception as e:
    print(f"❌ Ошибка подключения к Google Таблице: {e}")
    exit(1)

# 2. Проверенные и наиболее релевантные RSS-источники
rss_sources = [
    {"url": "https://smi44.ru/rss", "name": "СМИ44 (Официальные пресс-релизы)"},
    {"url": "https://kostroma.today/feed/", "name": "Кострома.Today (Городские события)"},
    {"url": "https://adm44.ru/rss.ashx", "name": "Правительство Костромской области"},
    {"url": "https://grad.kostroma.gov.ru/rss.ashx", "name": "Администрация г. Костромы"},
    {"url": "https://dsgh.kostroma.gov.ru/rss.ashx", "name": "Департамент строительства, ЖКХ и ТЭК"},
    {"url": "https://dkko.kostroma.gov.ru/rss.ashx", "name": "Департамент культуры Костромской области"},
    {"url": "https://don.kostroma.gov.ru/rss.ashx", "name": "Департамент образования и науки"},
    {"url": "https://socdep.kostroma.gov.ru/rss.ashx", "name": "Департамент по труду и соцзащите"},
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*"
}

# 3. Ключевые слова, релевантные для маркетинга и CSR "Этажей"
keywords = [
    'конкурс', 'фестиваль', 'праздник', 'ярмарка', 'день города', 'забег', 
    'турнир', 'мероприятие', 'выставка', 'форум', 'квест', 'гуляния',
    'грант', 'субсидия', 'поддержка', 'молодежь', 'семья', 'строительство', 
    'благоустройство', 'жкх', 'волонтер', 'экология', 'городская среда', 'двор'
]

total_added = 0
today_str = datetime.now().strftime("%d.%m.%Y %H:%M")

# 4. Проход по всем источникам с защитой от сбоев
for source in rss_sources:
    print(f"\n📡 Сканируем: {source['name']}")
    try:
        # Увеличен timeout до 15 сек и отключена строгая проверка SSL для госсайтов
        response = requests.get(source['url'], headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        
        # Быстрая проверка, что это действительно XML/RSS
        if '<rss' not in response.text[:300].lower() and '<feed' not in response.text[:300].lower():
            print(f"   ⚠️ Пропущено: ответ не является RSS-лентой")
            continue
            
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        print(f"   Найдено новостей: {len(items)}")
        
        for item in items:
            title = item.find('title').text.strip() if item.find('title') is not None else "Без названия"
            link = item.find('link').text.strip() if item.find('link') is not None else ""
            pub_date = item.find('pubDate').text.strip() if item.find('pubDate') is not None else "Дата не указана"
            
            description = item.find('description')
            desc_text = description.text.lower() if description is not None and description.text else ""
            
            # Проверяем заголовок И описание на наличие ключевых слов
            text_to_check = (title.lower() + " " + desc_text)
            matched_keywords = [kw for kw in keywords if kw in text_to_check]
            
            if matched_keywords:
                print(f"   ➕ Совпадение: '{title[:50]}...' ({', '.join(matched_keywords[:2])})")
                
                # Умная генерация идеи для акции
                promo_idea = "Стандартный квиз / Брендирование зоны"
                if any(k in text_to_check for k in ['строительство', 'жкх', 'благоустройство', 'двор']):
                    promo_idea = "Экспертный комментарий от 'Этажей' + спонсорство двора"
                elif any(k in text_to_check for k in ['молодежь', 'студент', 'вуз', 'школь']):
                    promo_idea = "Лекторий 'Первый старт' + грант на переезд"
                elif any(k in text_to_check for k in ['семья', 'ребенок', 'дет']):
                    promo_idea = "Акция 'Здоровая семья' + розыгрыш сертификата на ипотеку"
                elif any(k in text_to_check for k in ['грант', 'субсидия', 'поддержка']):
                    promo_idea = "Консультация по использованию мат. капитала и субсидий"
                elif any(k in text_to_check for k in ['фестиваль', 'ярмарка', 'день города']):
                    promo_idea = "VR-тур по новостройкам + раздача мерча на шатре"
                
                # Формируем строку: Дата парсинга | Заголовок | Дата события | Город | Ссылка | Идея акции | Источник
                row = [today_str, title, pub_date, "Кострома", link, promo_idea, source['name']]
                
                try:
                    worksheet.append_row(row)
                    total_added += 1
                except Exception as e:
                    print(f"   ⚠️ Ошибка записи в таблицу: {e}")
                    
    except requests.exceptions.Timeout:
        print(f"   ⚠️ Таймаут: сайт отвечает слишком долго, пропускаем")
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Ошибка сети: {e}")
    except ET.ParseError:
        print(f"   ⚠️ Ошибка парсинга XML: сайт вернул некорректный формат")

print(f"\n🎉 ПАРСИНГ ЗАВЕРШЕН! Всего добавлено новых строк: {total_added}")
