import requests
import json
import time

# ——— Константы ————————————————————————————————————————————————
API_SEARCH_URL = 'https://middle-api.magnit.ru/v2/goods/search'
API_DETAIL_URL = 'https://middle-api.magnit.ru/api/v2/goods/{id}/stores/{store}'
STORE_CODE     = '770344'    # для первого запроса всегда фиксированный
CATEGORY_ID    = 4459        # ваша категория
CITY_ID        = '1'
LIMIT          = 20          # сколько товаров за раз
PAUSE          = 0.2         # секунда паузы между запросами

# ——— Заголовки ————————————————————————————————————————————————
BASE_HEADERS = {
    'x-app-version':    '8.57.0',
    'x-device-id':      'b4ffad2b-c7cd-3bf4-942f-ee21b4236584',
    'x-device-platform':'Android',
    'x-platform-version':'28',
    'x-device-tag':     '41BDE13C-E42E-4619-87E8-BD91D5340640_9D318296-014D-4675-9322-9BCDE9CC8FFE',
    'sentry-trace':     'a015ca4609c04622b479fbc6bd5886d9-af8e458832f54712',
    'baggage':          'sentry-environment=production,sentry-public_key=6d4cfb7c8887ad7d38f6d3182a75acda,'
                        'sentry-release=ru.tander.magnit%408.57.0%2B1149075,sentry-trace_id=a015ca4609c04622b479fbc6bd5886d9',
    'Content-Type':     'application/json; charset=UTF-8',
    'Connection':       'Keep-Alive',
    'User-Agent':       'okhttp/4.12.0',
}

DETAIL_HEADERS = {
    **BASE_HEADERS,
    'If-Modified-Since': 'Mon, 16 Jun 2025 15:30:33 GMT',
}

DETAIL_PARAMS = {
    'catalog-type': '2',
    'store-type':   'express',
}


# ——— Функция для запроса страницы поиска ——————————————————————————————————
def fetch_search_page(offset: int) -> dict:
    """Выполняет POST-запрос к API поиска товаров, возвращает JSON-словарь."""
    payload = {
        'catalogType': '2',
        'pagination':  {'limit': LIMIT, 'offset': offset},
        'sort':        {'order': 'desc', 'type': 'popularity'},
        'storeCode':   STORE_CODE,
        'storeType':   'express',
        'categories':  [CATEGORY_ID],
        'cityId':      CITY_ID,
        'filters':     [],
        'token':       '',
    }
    try:
        response = requests.post(API_SEARCH_URL, headers=BASE_HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при запросе страницы search offset={offset}: {e}")
        return { 'pagination': {'totalCount': 0}, 'items': [] }


# ——— Утилита для конвертации цены ————————————————————————————————————
def parse_price(cents):
    """Конвертирует цену из копеек в рубли и округляет до 2 знаков."""
    try:
        return round(cents / 100, 2) if cents is not None else None
    except (TypeError, ValueError):
        return None


# ——— Функция для запроса деталей товара —————————————————————————————————
def fetch_brand(product_id: str, store_code: str) -> str | None:
    """
    Выполняет GET-запрос к API деталей товара, возвращает название бренда.
    Если что-то идёт не так — возвращает None.
    """
    url = API_DETAIL_URL.format(id=product_id, store=store_code)
    try:
        resp = requests.get(url, headers=DETAIL_HEADERS, params=DETAIL_PARAMS, timeout=10)
        resp.raise_for_status()
        detail = resp.json()
        # Сначала пытаемся взять brand.name
        brand = detail.get('brand', {}).get('name')
        if brand:
            return brand
        # Ищем в секциях details
        for section in detail.get('details', []):
            if section.get('type') == 'tableType':
                for p in section.get('parameters', []):
                    if p.get('name') == 'Бренд':
                        return p.get('value')
    except requests.RequestException as e:
        print(f"Ошибка при запросе details для {product_id} (store {store_code}): {e}")
    except ValueError as e:
        print(f"Ошибка разбора JSON details для {product_id}: {e}")
    return None


# ——— Основная функция ————————————————————————————————————————————————
def main():
    # 1) Первый запрос, узнаём общее количество товаров
    first = fetch_search_page(0)
    total = first.get('pagination', {}).get('totalCount', 0)
    print(f'Всего товаров (totalCount): {total}')

    results = []
    # 2) По страницам загружаем товары
    for offset in range(0, total, LIMIT):
        print(f'Загружаю товары offset={offset}…')
        page = fetch_search_page(offset)
        items = page.get('items', [])
        if not items:
            print("  — Нет товаров на этой странице, пропускаем.")
            continue

        # 3) Для каждого товара собираем данные и сразу запрашиваем бренд
        for item in items:
            pid   = item.get('id')
            store = item.get('storeCode') or STORE_CODE  # fallback к базовому магазину
            product = {
                'id':       pid,
                'name':     item.get('name'),
                'price':    parse_price(item.get('price')),
                'oldPrice': parse_price(item.get('promotion', {}).get('oldPrice')),
                'brand':    None,  # проставим ниже
            }
            print(f"  → Получаем бренд для id={pid} (store={store})…")
            product['brand'] = fetch_brand(pid, store)
            results.append(product)
            time.sleep(PAUSE)

    # 4) Сохраняем результат в JSON-файл
    try:
        with open('output.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nГотово! Сохранено {len(results)} товаров в output.json")
    except IOError as e:
        print(f"Ошибка записи файла output.json: {e}")


if __name__ == '__main__':
    main()


