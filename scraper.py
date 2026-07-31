import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 1. Настройка Google Sheets
# В GitHub Secrets мы добавим содержимое JSON-ключа
sa_key_json = os.environ.get('GCP_SA_KEY')
sa_creds = json.loads(sa_key_json)
gc = gspread.service_account_from_dict(sa_creds)

# Открываем таблицу по имени или ID
sh = gc.open("Кострома_События_Этажи")
worksheet = sh.sheet1

# 2. Парсинг местного портала (Пример для абстрактного новостного сайта)
# ВАЖНО: Замените URL и CSS-селекторы на реальные с костромского портала
url = "https://kostroma.today/news" # Или RSS-лента, если есть
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# Ищем новости (примерные селекторы, нужно адаптировать под верстку сайта)
articles = soup.select('div.news-item') 

keywords = ['конкурс', 'фестиваль', 'праздник', 'ярмарка', 'день города', 'забег']

today_str = datetime.now().strftime("%d.%m.%Y %H:%M")

for article in articles:
    title_tag = article.select_one('h2 a')
    if not title_tag:
        continue
        
    title = title_tag.text.strip()
    link = title_tag['href']
    
    # Фильтруем только целевые события
    if any(kw in title.lower() for kw in keywords):
        # Пытаемся вытащить дату и место из превью (адаптировать под сайт)
        date_tag = article.select_one('span.date')
        event_date = date_tag.text.strip() if date_tag else "Уточнить"
        
        # Идея для акции генерируется на основе ключевых слов (заготовка)
        promo_idea = "Стандартный квиз / VR-тур / Консультация"
        if 'город' in title.lower(): promo_idea = "Акция 'Город для жизни' + VR"
        if 'спорт' in title.lower() or 'забег' in title.lower(): promo_idea = "Акция 'Здоровая семья'"
        if 'студент' in title.lower() or 'кгy' in title.lower(): promo_idea = "Лекторий 'Первый старт'"

        # Записываем в Google Таблицу
        row = [today_str, title, event_date, "Кострома", link, promo_idea]
        worksheet.append_row(row)
        print(f"Добавлено: {title}")

print("Парсинг завершен.")
