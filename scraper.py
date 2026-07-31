import os
import json
import gspread
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib3

# Отключаем предупреждения о старых SSL-сертификатах (частая проблема госсайтов)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🚀 Запуск мультисорсного парсера Костромы для 'Этажей'...")

# ============================================================
# 1. Настройка Google Sheets
# ============================================================
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

# ============================================================
# 2. RSS-источники
#    reliable=True  -> проверенные, стабильно отдающие RSS 2.0
#    reliable=False -> гос. сайты, формат может меняться/падать; парсер
#                       не остановится, но подробно залогирует причину сбоя
# ============================================================
rss_sources = [
    # --- Проверенные, широкий охват СМИ ---
    {"url": "https://kostroma.bezformata.com/rss", "name": "БезФормата — все новости Костромской области", "reliable": True},
    {"url": "https://kostroma.bezformata.com/rsstop", "name": "БезФормата — главные новости", "reliable": True},
    {"url": "https://k1news.ru/news/rss/", "name": "K1NEWS — главный портал Костромы", "reliable": True},
    {"url": "https://kostroma.today/feed/", "name": "Кострома.Today (Городские события)", "reliable": True},
    {"url": "https://smi44.ru/rss", "name": "СМИ44 (Официальные пресс-релизы)", "reliable": True},

    # --- Государственные источники (нестабильны, оставлены с диагностикой) ---
    {"url": "https://adm44.ru/rss/", "name": "Правительство Костромской области", "reliable": False},
    {"url": "https://grad.kostroma.gov.ru/rss", "name": "Администрация г. Костромы", "reliable": False},
    {"url": "https://gkh.kostroma.gov.ru/rss", "name": "Департамент строительства, ЖКХ и ТЭК", "reliable": False},
    {"url": "https://dkko.kostroma.gov.ru/rss", "name": "Департамент культуры Костромской области", "reliable": False},
    {"url": "https://don.kostroma.gov.ru/rss", "name": "Департамент образования и науки", "reliable": False},
    {"url": "https://socdep.kostroma.gov.ru/rss", "name": "Департамент по труду и соцзащите", "reliable": False},
    {"url": "https://44.mchs.gov.ru/deyatelnost/press-centr/novosti/rss", "name": "МЧС Костромской области (ярмарки, безопасность)", "reliable": False},
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*"
}

# ============================================================
# 3. Ключевые слова
#    Разбиты на смысловые группы, чтобы точнее подбирать промо-идею
#    под интересы агентства недвижимости "Этажи"
# ============================================================
keywords_events = [
    'конкурс', 'фестиваль', 'праздник', 'ярмарка', 'день города', 'забег',
    'турнир', 'мероприятие', 'выставка', 'форум', 'квест', 'гуляния',
    'акция', 'марафон'
]
keywords_family_social = [
    'грант', 'субсидия', 'поддержка', 'молодежь', 'молодая семья', 'семья',
    'многодетн', 'материнский капитал', 'льготная ипотека'
]
keywords_realty = [
    'строительство', 'благоустройство', 'жкх', 'новостройка', 'ижс',
    'квартира', 'жилье', 'жильё', 'ипотека', 'застройщик', 'двор',
    'реновация', 'снос', 'переселение', 'аварийное жилье'
]
keywords_eco_civic = [
    'волонтер', 'экология', 'городская среда', 'субботник', 'озеленение'
]

keywords = keywords_events + keywords_family_social + keywords_realty + keywords_eco_civic

total_added = 0
total_skipped_errors = 0
today_str = datetime.now().strftime("%d.%m.%Y %H:%M")


def classify_promo(text_to_check: str) -> str:
    """Подбирает идею промо-акции для 'Этажей' по совпавшим ключевым словам."""
    if any(k in text_to_check for k in ['новостройка', 'ижс', 'застройщик', 'ипотека', 'квартира']):
        return "VR-тур по новостройкам + консультация по ипотеке"
    if any(k in text_to_check for k in ['строительство', 'жкх', 'благоустройство', 'двор', 'реновация', 'снос', 'переселение', 'аварийное жилье']):
        return "Экспертный комментарий от 'Этажей' + спонсорство двора"
    if any(k in text_to_check for k in ['молодежь', 'студент', 'вуз', 'школь', 'молодая семья']):
        return "Лекторий 'Первый старт' + грант на переезд"
    if any(k in text_to_check for k in ['семья', 'ребенок', 'дет', 'многодетн']):
        return "Акция 'Здоровая семья' + розыгрыш сертификата на ипотеку"
    if any(k in text_to_check for k in ['грант', 'субсидия', 'поддержка', 'материнский капитал', 'льготная ипотека']):
        return "Консультация по использованию мат. капитала и субсидий"
    if any(k in text_to_check for k in ['фестиваль', 'ярмарка', 'день города', 'марафон']):
        return "VR-тур по новостройкам + раздача мерча на шатре"
    if any(k in text_to_check for k in ['волонтер', 'экология', 'субботник', 'озеленение']):
        return "Эко-акция с брендированным инвентарём от 'Этажей'"
    return "Стандартный квиз / Брендирование зоны"


# ============================================================
# 4. Проход по всем источникам с защитой от сбоев и диагностикой
# ============================================================
for source in rss_sources:
    print(f"\n📡 Сканируем: {source['name']}")
    try:
        response = requests.get(source['url'], headers=headers, timeout=15, verify=False, allow_redirects=True)

        if response.status_code != 200:
            print(f"   ⚠️ HTTP {response.status_code} — источник недоступен или сменил адрес")
            total_skipped_errors += 1
            continue

        snippet = response.text[:300].lower()
        if '<rss' not in snippet and '<feed' not in snippet:
            preview = response.text[:120].replace('\n', ' ')
            print(f"   ⚠️ Пропущено: ответ не RSS/Atom. Похоже на: {response.headers.get('Content-Type', '?')}")
            print(f"      Начало ответа: {preview}...")
            total_skipped_errors += 1
            continue

        root = ET.fromstring(response.content)
        # Поддержка и RSS 2.0 (<item>), и Atom (<entry>)
        items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
        print(f"   Найдено новостей: {len(items)}")

        for item in items:
            title_el = item.find('title')
            link_el = item.find('link')
            pubdate_el = item.find('pubDate') or item.find('{http://www.w3.org/2005/Atom}updated')

            title = title_el.text.strip() if title_el is not None and title_el.text else "Без названия"

            # Atom-лента хранит ссылку в атрибуте href, а не в тексте тега
            if link_el is not None:
                link = link_el.text.strip() if link_el.text else link_el.attrib.get('href', '')
            else:
                link = ""

            pub_date = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else "Дата не указана"

            description = item.find('description')
            if description is None:
                description = item.find('{http://www.w3.org/2005/Atom}summary')
            desc_text = description.text.lower() if description is not None and description.text else ""

            text_to_check = (title.lower() + " " + desc_text)
            matched_keywords = [kw for kw in keywords if kw in text_to_check]

            if matched_keywords:
                print(f"   ➕ Совпадение: '{title[:50]}...' ({', '.join(matched_keywords[:3])})")

                promo_idea = classify_promo(text_to_check)

                row = [today_str, title, pub_date, "Кострома", link, promo_idea, source['name']]

                try:
                    worksheet.append_row(row)
                    total_added += 1
                except Exception as e:
                    print(f"   ⚠️ Ошибка записи в таблицу: {e}")

    except requests.exceptions.Timeout:
        print(f"   ⚠️ Таймаут: сайт отвечает слишком долго, пропускаем")
        total_skipped_errors += 1
    except requests.exceptions.SSLError as e:
        print(f"   ⚠️ SSL-ошибка: {e}")
        total_skipped_errors += 1
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Ошибка сети: {e}")
        total_skipped_errors += 1
    except ET.ParseError as e:
        print(f"   ⚠️ Ошибка парсинга XML: сайт вернул некорректный формат ({e})")
        total_skipped_errors += 1

print(f"\n🎉 ПАРСИНГ ЗАВЕРШЕН! Добавлено строк: {total_added} | Источников с ошибками: {total_skipped_errors}")
