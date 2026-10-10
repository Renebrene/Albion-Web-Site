"""Правки geo-контента: описание Аксайского района и трассы М-4 «Дон».

- Локация «Верхнетемерницкий (Аксайский район)» получает описание Аксайского
  района и фото-обложку (станица Старочеркасская, Wikimedia Commons).
- Локация «ТРАССА М4» получает расширенное описание с акцентом на важность
  магистрали для региона и для рекламы.

Запуск:  .venv/bin/python -m scripts.seed_geo_aksai_m4
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file
from backend.services.media_service import save_image
from scripts.seed_geo_content import _commons, _download, _plain

load_env_file(PROJECT_DIR / ".env")

AKSAI_DESCRIPTION = (
    "Аксайский район — один из центральных районов Ростовской области, который "
    "непосредственно примыкает к областному центру. Его административный центр — "
    "город Аксай, а территория занимает около 117 тысяч гектаров в долине Нижнего "
    "Дона, между реками Аксай, Тузлов, Темерник и Доном.\n\n"
    "Здешние земли обжиты издавна: первое письменное упоминание о поселении на месте "
    "нынешнего Аксая относится к 1570 году, а сам район как административная единица "
    "существует с 1924 года. Здесь расположена станица Старочеркасская — бывшая "
    "столица донского казачества, а близость к Ростову-на-Дону сделала район одной из "
    "самых динамично развивающихся территорий области: здесь развиваются логистика, "
    "производство, торговля и жилая застройка."
)

M4_DESCRIPTION = (
    "М-4 «Дон» — главная автомобильная магистраль юга России, связывающая Москву через "
    "Воронеж и Ростов-на-Дону с Краснодаром, Новороссийском и черноморскими курортами. "
    "Для Ростовской области это ключевая транспортная артерия: по ней идут транзит, "
    "грузоперевозки и основной поток туристов на юг, а на территории региона проходит "
    "один из самых загруженных её участков с развилкой в сторону Азовского и Чёрного "
    "морей и Кавказа.\n\n"
    "Значение трассы для рекламы трудно переоценить: это непрерывный поток аудитории со "
    "всей страны — транзитные автомобилисты, дальнобойщики, семьи, едущие на отдых. "
    "Вдоль М-4 сосредоточены АЗС, сервисы, придорожные комплексы и торговые объекты, "
    "поэтому конструкции на трассе дают максимально широкий охват и стабильный контакт "
    "с аудиторией круглый год."
)

ATTACHMENT = (
    "АКСАЙСКИЙ",  # подстрока в названии локации
    "Starocherkassk (2004-04-016).jpg",
    "Станица Старочеркасская",
    "Бывшая столица донского казачества на Дону, в Аксайском районе.",
)


def _find_location(conn, needle):
    row = conn.execute(
        "SELECT id FROM home_geo_locations WHERE lower(label) LIKE %s LIMIT 1",
        (f"%{needle.lower()}%",),
    ).fetchone()
    return row[0] if row else None


def run():
    print("ALBION · Правки geo: Аксайский район и трасса М-4")

    with get_connection() as conn:
        # 1. Описание Аксайского района + фото
        needle, file_name, atitle, adesc = ATTACHMENT
        location_id = _find_location(conn, needle)
        if not location_id:
            print(f"  ! локация «{needle}» не найдена")
        else:
            with conn.transaction():
                conn.execute(
                    "UPDATE home_geo_locations SET description = %s, updated_at = NOW() "
                    "WHERE id = %s",
                    (AKSAI_DESCRIPTION, location_id),
                )
            print("  ✓ описание Аксайского района обновлено")

            exists = conn.execute(
                "SELECT 1 FROM home_geo_attractions WHERE location_id = %s LIMIT 1",
                (location_id,),
            ).fetchone()
            if exists:
                print("  · достопримечательность уже есть")
            else:
                info = _commons(file_name)
                meta = info.get("extmetadata") or {}
                image_url = info.get("thumburl") or info.get("url")
                source_url = info.get("descriptionurl") or ""
                license_name = _plain((meta.get("LicenseShortName") or {}).get("value"))
                artist = _plain((meta.get("Artist") or {}).get("value"))
                media = save_image(_download(image_url), file_name, alt=atitle, title=atitle)
                cred = f"Wikimedia Commons · {artist}" if artist else "Wikimedia Commons"

                with conn.transaction():
                    attraction_id = conn.execute(
                        "INSERT INTO home_geo_attractions "
                        "(location_id, title, description, sort_order, is_active) "
                        "VALUES (%s, %s, %s, 0, TRUE) RETURNING id",
                        (location_id, atitle, adesc),
                    ).fetchone()[0]
                    conn.execute(
                        "INSERT INTO home_geo_attraction_photos "
                        "(attraction_id, media_id, image_path, alt_text, source_name, "
                        " source_url, license, sort_order, is_cover) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, 0, TRUE)",
                        (attraction_id, media.get("id"), media.get("storage_path"),
                         atitle, cred, source_url, license_name),
                    )
                    conn.execute(
                        "UPDATE home_geo_locations SET cover_attraction_id = %s "
                        "WHERE id = %s",
                        (attraction_id, location_id),
                    )
                print(f"  ✓ добавлено фото: {atitle} ({license_name})")

        # 2. Описание трассы М-4
        m4_id = _find_location(conn, "трасса")
        if not m4_id:
            print("  ! локация «ТРАССА М4» не найдена")
        else:
            with conn.transaction():
                conn.execute(
                    "UPDATE home_geo_locations SET description = %s, updated_at = NOW() "
                    "WHERE id = %s",
                    (M4_DESCRIPTION, m4_id),
                )
            print("  ✓ описание трассы М-4 обновлено")

    print("COMMIT: правки geo готовы.")


if __name__ == "__main__":
    run()
