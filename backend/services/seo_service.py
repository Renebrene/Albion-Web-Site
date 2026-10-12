"""SEO: заголовки, описания и ключевые слова для публичных страниц.

Хранится в site_settings (ключ ``seo``, JSON), правится в админке
(раздел «SEO»). Значения по умолчанию подобраны под рекламную сеть
«Альбион»: наружная реклама, Ростов-на-Дону и область.

Публичный эндпоинт ``/api/seo`` отдаёт готовый набор, фронтенд применяет
его к <head> при смене маршрута; ``/robots.txt`` и ``/sitemap.xml``
генерируются из этих же настроек.
"""

from __future__ import annotations

import json
from typing import Any

from backend.services.data_service import get_connection


SEO_KEY = "seo"

# Публичные страницы: path — маршрут SPA, index — попадает ли в sitemap.
PAGES: list[dict[str, Any]] = [
    {"path": "/", "label": "Главная", "index": True},
    {"path": "/vozmozhnosti", "label": "Возможности (карта)", "index": True},
    {"path": "/napravleniya", "label": "Направления", "index": True},
    {"path": "/novosti", "label": "Новости", "index": True},
    {"path": "/o-kompanii", "label": "О компании", "index": True},
    {"path": "/kontakty", "label": "Контакты", "index": True},
    {"path": "/informaciya", "label": "Информация", "index": True},
    {"path": "/chat", "label": "Умный чат", "index": False},
    {"path": "/account", "label": "Личный кабинет", "index": False},
    {"path": "/portfolio", "label": "Портфель", "index": False},
]

DEFAULT_KEYWORDS = (
    "наружная реклама Ростов-на-Дону, аренда билбордов Ростов-на-Дону, "
    "рекламные конструкции Ростов, аренда рекламных щитов, "
    "размещение наружной рекламы, рекламные баннеры Ростов, "
    "видеоэкраны Ростов-на-Дону, призматроны, реклама на билбордах цена, "
    "рекламная сеть Альбион"
)

DEFAULT_SEO: dict[str, Any] = {
    "site_name": "Рекламная сеть «Альбион»",
    "site_url": "",
    "default_title": (
        "Наружная реклама в Ростове-на-Дону — рекламная сеть «Альбион»"
    ),
    "default_description": (
        "Более 1500 рекламных конструкций в Ростове-на-Дону и области: "
        "билборды, щиты, видеоэкраны, призматроны. Свободные поверхности "
        "на карте, цены по месяцам, подбор под задачу."
    ),
    "default_keywords": DEFAULT_KEYWORDS,
    "og_image": "",
    "pages": {
        "/": {
            "title": (
                "Наружная реклама в Ростове-на-Дону — "
                "рекламная сеть «Альбион»"
            ),
            "description": (
                "Аренда билбордов, щитов и видеоэкранов в Ростове-на-Дону. "
                "1500+ конструкций на интерактивной карте: свободные "
                "поверхности, цены по месяцам, расчёт размещения."
            ),
            "keywords": (
                "рекламная сеть Альбион, наружная реклама Ростов-на-Дону, "
                "аренда билбордов, рекламные конструкции Ростов, "
                "размещение наружной рекламы"
            ),
        },
        "/vozmozhnosti": {
            "title": (
                "Рекламные конструкции на карте — "
                "аренда билбордов в Ростове-на-Дону | Альбион"
            ),
            "description": (
                "Интерактивная карта рекламных конструкций: билборды, щиты, "
                "видеоэкраны и скроллеры. Свободные месяцы, цены и "
                "характеристики по каждой поверхности."
            ),
            "keywords": (
                "рекламные конструкции на карте, аренда билбордов "
                "Ростов-на-Дону, рекламные щиты и видеоэкраны, "
                "свободные поверхности, цены на наружную рекламу"
            ),
        },
        "/napravleniya": {
            "title": "Направления и форматы наружной рекламы | Альбион",
            "description": (
                "Форматы наружной рекламы: билборды, щиты, сити-форматы, "
                "пилоны, скроллеры, призматроны и видеоэкраны. "
                "Подбор под задачу и бюджет."
            ),
            "keywords": (
                "направления наружной рекламы, виды рекламных конструкций, "
                "билборды щиты пилоны скроллеры, аренда видеоэкранов"
            ),
        },
        "/novosti": {
            "title": "Новости рекламной сети «Альбион»",
            "description": (
                "Новости наружной рекламы в Ростове-на-Дону: обновления "
                "базы конструкций, новые поверхности и форматы, "
                "события рекламной сети."
            ),
            "keywords": (
                "новости наружной рекламы, новости рекламной сети Альбион, "
                "обновления базы конструкций"
            ),
        },
        "/o-kompanii": {
            "title": "О компании — рекламная сеть «Альбион», Ростов-на-Дону",
            "description": (
                "Рекламная сеть «Альбион»: более 1500 рекламных "
                "конструкций в Ростове-на-Дону и Ростовской области. "
                "Опыт размещения наружной рекламы."
            ),
            "keywords": (
                "рекламная сеть Альбион, о компании, наружная реклама "
                "Ростов-на-Дону, рекламные конструкции Ростовской области"
            ),
        },
        "/kontakty": {
            "title": "Контакты рекламной сети «Альбион»",
            "description": (
                "Как связаться с рекламной сетью «Альбион»: телефон, "
                "почта, адрес офиса в Ростове-на-Дону. Оставьте заявку на "
                "размещение наружной рекламы."
            ),
            "keywords": (
                "контакты Альбион, разместить наружную рекламу Ростов, "
                "телефон рекламной сети, заявка на размещение рекламы"
            ),
        },
        "/informaciya": {
            "title": "Информация для рекламодателей | Альбион",
            "description": (
                "Условия размещения наружной рекламы, документы и "
                "требования к макетам. Всё для старта рекламной кампании "
                "в Ростове-на-Дону."
            ),
            "keywords": (
                "информация для рекламодателей, условия размещения "
                "наружной рекламы, требования к макетам, документы"
            ),
        },
    },
}

# Ограничения длины — чтобы страница не выпадала из выдачи.
_LIMITS = {
    "title": 120,
    "description": 400,
    "keywords": 400,
    "site_name": 120,
    "site_url": 200,
    "og_image": 300,
}


def _default_pages() -> dict[str, dict[str, str]]:
    return {
        page["path"]: dict(DEFAULT_SEO["pages"].get(page["path"], {}))
        for page in PAGES
    }


def _clean(value: Any, limit: int = 400) -> str:
    text = " ".join(str(value or "").split())

    return text[:limit]


def _merge(stored: dict) -> dict:
    """Настройки по умолчанию + сохранённые значения."""
    result: dict[str, Any] = {
        key: DEFAULT_SEO[key] for key in DEFAULT_SEO if key != "pages"
    }
    result["pages"] = _default_pages()

    if not isinstance(stored, dict):
        return result

    for key in result:
        if key == "pages":
            continue

        if stored.get(key) is not None:
            result[key] = _clean(stored[key], _LIMITS.get(key, 400))

    stored_pages = stored.get("pages")

    if isinstance(stored_pages, dict):
        for path, values in stored_pages.items():
            if path not in result["pages"] or not isinstance(values, dict):
                continue

            for field in ("title", "description", "keywords"):
                if values.get(field) is not None:
                    result["pages"][path][field] = _clean(
                        values[field], _LIMITS[field]
                    )

    return result


def _read(conn) -> dict:
    row = conn.execute(
        "SELECT value FROM site_settings WHERE key = %s",
        (SEO_KEY,),
    ).fetchone()

    stored: dict = {}

    if row and row[0]:
        try:
            parsed = json.loads(row[0])
            if isinstance(parsed, dict):
                stored = parsed
        except (json.JSONDecodeError, TypeError):
            stored = {}

    return _merge(stored)


def get_seo() -> dict:
    """Текущие SEO-настройки + список страниц (для админки)."""
    with get_connection() as conn:
        current = _read(conn)

    return {"current": current, "pages": PAGES}


def get_public_seo() -> dict:
    """То же для публичного фронта (применяется к <head>)."""
    return get_seo()["current"]


def save_seo(payload: dict) -> dict:
    """Сохранить SEO-настройки (любое подмножество полей)."""
    if not isinstance(payload, dict):
        raise ValueError("Ожидается объект настроек")

    with get_connection() as conn:
        with conn.transaction():
            current = _read(conn)

            for key in (
                "site_name",
                "site_url",
                "default_title",
                "default_description",
                "default_keywords",
                "og_image",
            ):
                if key in payload:
                    current[key] = _clean(payload[key], _LIMITS[key])

            pages = payload.get("pages")

            if isinstance(pages, dict):
                for path, values in pages.items():
                    if path not in current["pages"]:
                        continue

                    if not isinstance(values, dict):
                        continue

                    for field in ("title", "description", "keywords"):
                        if field in values:
                            current["pages"][path][field] = _clean(
                                values[field], _LIMITS[field]
                            )

            conn.execute(
                """
                INSERT INTO site_settings (key, value, value_type, description)
                VALUES (%s, %s, 'json', 'SEO: заголовки, описания, ключевые слова')
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (SEO_KEY, json.dumps(current, ensure_ascii=False)),
            )

    return get_seo()


def reset_seo() -> dict:
    """Вернуть SEO-настройки к значениям по умолчанию."""
    with get_connection() as conn:
        conn.execute("DELETE FROM site_settings WHERE key = %s", (SEO_KEY,))

    return get_seo()


# ------------------------------------------------------------ robots / sitemap


def _site_url(seo: dict) -> str:
    url = str(seo.get("site_url") or "").strip().rstrip("/")

    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def robots_txt() -> str:
    seo = get_public_seo()
    base = _site_url(seo)

    lines = [
        "User-agent: *",
        "Allow: /",
        # Служебные разделы индексировать не нужно.
        "Disallow: /administration",
        "Disallow: /account",
        "Disallow: /portfolio",
        "Disallow: /api/",
    ]

    if base:
        lines += ["", f"Sitemap: {base}/sitemap.xml"]

    return "\n".join(lines) + "\n"


def sitemap_xml() -> str:
    seo = get_public_seo()
    base = _site_url(seo)

    entries = []

    for page in PAGES:
        if not page["index"]:
            continue

        loc = f"{base}{'' if page['path'] == '/' else page['path']}" if base else page["path"]
        entries.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            "    <changefreq>weekly</changefreq>\n"
            "  </url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
