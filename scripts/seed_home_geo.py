"""Первичное наполнение geo-слайда: по одной достопримечательности на город.

Фото берутся с Wikimedia Commons (свободные лицензии), сохраняются в локальное
медиа-хранилище, а источник/лицензия записываются для атрибуции в карточке.

Запуск:  .venv/bin/python -m scripts.seed_home_geo
Идемпотентно: уже созданные карточки повторно не добавляются.
"""
import json
import urllib.parse
import urllib.request

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file
from backend.services.media_service import save_image


load_env_file(PROJECT_DIR / ".env")

UA = "AlbionHomeGeo/1.0 (https://albion.cloudpub.ru/; contact: admin@albion.su)"

# label в home_geo_locations (city) -> карточка
ITEMS = [
    {
        "city": "Ростов-на-Дону",
        "title": "Собор Рождества Пресвятой Богородицы",
        "description": (
            "Главный православный храм Ростова-на-Дону и один из самых "
            "крупных соборов юга России. Расположен на Соборной площади, "
            "рядом с центральным рынком города."
        ),
        "file": "File:Cathedral of the Nativity of the Blessed Virgin Mary, Rostov-on-Don.jpg",
    },
    {
        "city": "ТАГАНРОГ",
        "title": "Таганрогский театр имени А. П. Чехова",
        "description": (
            "Один из старейших драматических театров юга России, носящий имя "
            "писателя Антона Павловича Чехова. Историческое здание на "
            "Красной площади — узнаваемый символ Таганрога."
        ),
        "file": "File:Здание Таганрогского ордена «Знак Почета» театра имени А.П. Чехова, г. Таганрог (2019г).jpg",
    },
    {
        "city": "НОВОЧЕРКАССК",
        "title": "Вознесенский войсковой собор",
        "description": (
            "Главный храм донского казачества на площади Ермака в "
            "Новочеркасске. Один из крупнейших соборов России, видимый "
            "далеко за пределами городского центра."
        ),
        "file": "File:Вознесенский собор. Новочеркасск.JPG",
    },
    {
        "city": "ШАХТЫ",
        "title": "Покровский кафедральный собор",
        "description": (
            "Кафедральный собор в центре Шахт, освящённый в честь Покрова "
            "Пресвятой Богородицы. Один из главных храмов города."
        ),
        "file": "File:Шахты. Кафедральный собор Покрова Пресвятой Богородицы.jpg",
    },
    {
        "city": "БАТАЙСК",
        "title": "Железнодорожная станция Батайск",
        "description": (
            "Старейший железнодорожный узел на подъездах к Ростову-на-Дону. "
            "Через Батайск проходят главные направления юга России."
        ),
        "file": "File:BatayskStation.JPG",
    },
    {
        "city": "БЕЛАЯ КАЛИТВА",
        "title": "Стела на въезде",
        "description": (
            "Стела на въезде в Белую Калитву — узнаваемый символ города. "
            "Белая Калитва стоит на реке Северский Донец."
        ),
        "file": "File:Belaya Kalitva-Stela.jpg",
    },
    {
        "city": "ВОЛГОДОНСК",
        "title": "Дон в окрестностях Волгодонска",
        "description": (
            "Волгодонск вырос у Цимлянского водохранилища на Дону. Река "
            "определяет облик города и его промышленную историю."
        ),
        "file": "File:Don River near Volgodonsk, Russia 01.jpg",
    },
    {
        "city": "ГУКОВО",
        "title": "Храм Казанской иконы Божией Матери",
        "description": (
            "Православный храм в шахтёрском городе Гуково, центр духовной "
            "жизни местных жителей."
        ),
        "file": "File:Храм иконы Казанской Божией Матери. Ростовкая обл., г. Гуково..jpg",
    },
    {
        "city": "МИЛЛЕРОВО",
        "title": "Железнодорожный вокзал",
        "description": (
            "Вокзал станции Миллерово — крупный транспортный узел севера "
            "Ростовской области, связывающий регион с центральной Россией."
        ),
        "file": "File:Вокзал ст. Миллерово.jpg",
    },
    {
        "city": "НОВОШАХТИНСК",
        "title": "Городской мемориал",
        "description": (
            "Мемориал в Новошахтинске в память о шахтёрах и защитниках "
            "города. Новошахтинск — один из центров донецкого угольного "
            "бассейна."
        ),
        "file": "File:Novoshakhtinsk memorial.jpg",
    },
    {
        "city": "САЛЬСК",
        "title": "Железнодорожный вокзал",
        "description": (
            "Вокзал узловой станции Сальск, связывающей центр области с её "
            "юго-восточными районами."
        ),
        "file": "File:Железнодорожный вокзал станции Сальск.jpg",
    },
]


def _commons(title: str, width: int = 1400) -> dict:
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": str(width),
        "format": "json",
        "origin": "*",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    pages = data.get("query", {}).get("pages", {})

    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]

        if info.get("thumburl") or info.get("url"):
            return info

    raise RuntimeError(f"Файл не найден: {title}")


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})

    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _location_id(conn, label: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM home_geo_locations "
        "WHERE kind = 'city' AND lower(label) = lower(%s) LIMIT 1",
        (label,),
    ).fetchone()

    return row[0] if row else None


def _attraction_exists(conn, location_id: int, title: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM home_geo_attractions "
        "WHERE location_id = %s AND title = %s LIMIT 1",
        (location_id, title),
    ).fetchone()

    return bool(row)


def run() -> None:
    print("ALBION · Наполнение geo-слайда (Wikimedia Commons)")

    with get_connection() as conn:
        with conn.cursor() as cur:
            pass

        for index, item in enumerate(ITEMS):
            location_id = _location_id(conn, item["city"])

            if not location_id:
                print(f"  · пропуск «{item['city']}» — нет локации")
                continue

            if _attraction_exists(conn, location_id, item["title"]):
                print(f"  · уже есть «{item['title']}»")
                continue

            info = _commons(item["file"])
            meta = info.get("extmetadata") or {}

            image_url = info.get("thumburl") or info.get("url")
            description_url = info.get("descriptionurl") or ""
            license_name = (meta.get("LicenseShortName") or {}).get("value") or ""

            image_bytes = _download(image_url)
            filename = item["file"].replace("File:", "")

            media = save_image(
                image_bytes,
                filename,
                alt=item["title"],
                title=item["title"],
            )

            with conn.transaction():
                attraction_id = conn.execute(
                    """
                    INSERT INTO home_geo_attractions
                        (location_id, title, description, sort_order, is_active)
                    VALUES (%s, %s, %s, %s, TRUE)
                    RETURNING id
                    """,
                    (location_id, item["title"], item["description"], index),
                ).fetchone()[0]

                conn.execute(
                    """
                    INSERT INTO home_geo_attraction_photos
                        (attraction_id, media_id, image_path, alt_text,
                         source_name, source_url, license, sort_order, is_cover)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 0, TRUE)
                    """,
                    (
                        attraction_id,
                        media.get("id"),
                        media.get("storage_path"),
                        item["title"],
                        "Wikimedia Commons",
                        description_url,
                        license_name,
                    ),
                )

            print(f"  ✓ {item['city']}: {item['title']} ({license_name})")

    print("COMMIT: geo-наполнение завершено.")


if __name__ == "__main__":
    run()
