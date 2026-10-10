"""Импорт новостей с сайта albion.su в CMS проекта.

Что делает:
  1. Парсит список новостей из раздела https://www.albion.su/news/
     (заголовок, дата, ссылка, миниатюра).
  2. Для каждой новости открывает страницу и достаёт полный текст,
     обложку и встроенные в текст изображения.
  3. Скачивает изображения в медиатеку проекта — через
     media_service.save_image: файлы ложатся в storage/media,
     в БД создаются записи media + media_variants (large/card/thumb),
     файлы попадают в медиакатегорию «Новости».
  4. Текст сохраняет в таблицу news, связи «новость ↔ медиа» —
     в news_media (обложка помечается is_cover = TRUE).

Запуск (из корня проекта):
    .venv/bin/python -m backend.importer.news_import --replace
    .venv/bin/python -m backend.importer.news_import --dry-run

Без --replace повторный запуск пропускает уже импортированные новости
(проверка по slug), поэтому импорт идемпотентен.
--replace перед импортом удаляет все существующие новости (демо-запись
из админки тоже), чтобы раздел содержал только реальные новости сайта.
"""
from __future__ import annotations

import argparse
import html as html_module
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from backend.services.data_service import get_connection
from backend.services.media_service import (
    MediaValidationError,
    save_image,
)


BASE_URL = "https://www.albion.su"
NEWS_URL = f"{BASE_URL}/news/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)

# Медиатека: категория «Новости».
MEDIA_CATEGORY_NEWS = 2

# Пауза между HTTP-запросами — не долбим чужой сервер.
REQUEST_DELAY = 0.3
REQUEST_TIMEOUT = 30

# Максимум страниц листинга, которые просматриваем (защита от бесконечного цикла).
MAX_LISTING_PAGES = 20

# Рубрика для каждой новости (id из news_categories):
#   1 Компания, 6 Проекты, 7 Реклама, 8 Производство, 9 События.
CATEGORY_BY_SLUG = {
    "s-prazdnikom-velikoy-pobedy": 9,
    "rasshirenie-seti-konstrukciy-didzhital-formata-v-rostove-na-donu": 6,
    "s-dnem-kosmonavtiki": 9,
    "reklamnaya-kampaniya-po-protivodeystviyu-upotrebleniya-narkotikov-i-ih-nezakonnogo-oborota": 7,
    "novye-reklamnye-konstrukcii-v-oblasti": 6,
    "s-8-marta": 9,
    "video-ekran-v-centre-batayska": 6,
    "videoekrany-v-taganroge": 6,
    "super-predlozhenie": 7,
    "informacionnye-materialy-izbiratelnoy-komissii-rostovskoy-oblasti": 7,
    "predvybornaya-kampaniya-kandidata-v-gubernatory-rostovskoy-oblasti": 7,
    "albionu--30-let": 1,
}
DEFAULT_CATEGORY = 1  # Компания

# Новости, которые показываем на главной («На главной» в админке).
FEATURED_SLUGS = {
    "rasshirenie-seti-konstrukciy-didzhital-formata-v-rostove-na-donu",
    "super-predlozhenie",
    "albionu--30-let",
}

# Регулярки разбора HTML сайта (вёрстка стабильная, XHTML).
LISTING_ITEM_RE = re.compile(
    r'<div class="event_item"><a href="([^"]+)" class="event_slider_item">\s*'
    r'<img src="([^"]+)"\s*/></a>\s*'
    r'<div class="title">\s*<span>(\d{2}\.\d{2}\.\d{4})</span>\s*(.*?)</div>',
    re.S,
)
ARTICLE_TITLE_RE = re.compile(r"<h1>(.*?)</h1>", re.S)
ARTICLE_COVER_RE = re.compile(
    r'event-image-container"><img src="([^"]+)"',
    re.S,
)
# Текст новости: от <div class="event_content"> до формы обратного звонка.
ARTICLE_BODY_RE = re.compile(
    r'<div class="event_content">(.*?)(?:'
    r'<div\s+class="widgetblock-mainform|<footer)',
    re.S,
)
INLINE_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
CACHE_PHOTO_RE = re.compile(r"cache/events_photos/\d+x\d+x\d+x")


# ------------------------------------------------------------------ HTTP


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = response.read()

    time.sleep(REQUEST_DELAY)
    return data


def _fetch_text(url: str) -> str:
    return _fetch(url).decode("utf-8", "replace")


# ------------------------------------------------------------------ parsing


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html_module.unescape(value)).strip()


def slug_from_url(url: str) -> str:
    """slug новости из адреса: .../news/<slug>.html -> <slug>."""
    name = Path(urlparse(url).path).name
    return re.sub(r"\.html?$", "", name)


def parse_listing(page_html: str) -> list[dict]:
    items = []

    for url, thumb, date, title in LISTING_ITEM_RE.findall(page_html):
        items.append(
            {
                "url": url,
                "slug": slug_from_url(url),
                "title": _clean_text(title),
                "date": date,
                "thumb_url": thumb,
            }
        )

    return items


def fetch_news_list() -> list[dict]:
    """Все новости раздела. Идём по страницам пагинации, пока появляются
    новые ссылки (на источнике пагинация отдаёт один и тот же список,
    поэтому цикл завершится после второй страницы)."""
    seen: dict[str, dict] = {}

    for page in range(1, MAX_LISTING_PAGES + 1):
        url = NEWS_URL if page == 1 else f"{NEWS_URL}{page}/"

        try:
            page_html = _fetch_text(url)
        except (HTTPError, URLError):
            break

        added = False

        for item in parse_listing(page_html):
            if item["slug"] not in seen:
                seen[item["slug"]] = item
                added = True

        if not added:
            break

    return list(seen.values())


def html_to_text(fragment: str) -> str:
    """HTML новости -> простой текст. Фронтенд разбивает content по
    переводам строк на отдельные абзацы, поэтому блоки переводим в \\n."""
    # Встроенные картинки попадают в медиатеку, в тексте они не нужны.
    fragment = INLINE_IMG_RE.sub(" ", fragment)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<li[^>]*>", "\n- ", fragment, flags=re.I)
    fragment = re.sub(
        r"</(?:p|div|li|ul|ol|h[1-6]|tr|section|blockquote)>",
        "\n",
        fragment,
        flags=re.I,
    )
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html_module.unescape(fragment).replace("\xa0", " ")

    lines = []

    for line in fragment.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def build_excerpt(text: str, limit: int = 200) -> str:
    first = next((line for line in text.split("\n") if line.strip()), "")
    first = first.strip()

    if len(first) <= limit:
        return first

    cut = first[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{cut}…"


def normalize_image_url(url: str) -> str:
    """cache/events_photos/600x450x0x<hash> -> upload/events_photos/<hash>.
    Так из превью получаем оригинал в полном размере."""
    if CACHE_PHOTO_RE.search(url):
        return CACHE_PHOTO_RE.sub("upload/events_photos/", url)
    return url


def parse_article(page_html: str) -> dict:
    title_match = ARTICLE_TITLE_RE.search(page_html)
    cover_match = ARTICLE_COVER_RE.search(page_html)
    body_match = ARTICLE_BODY_RE.search(page_html)

    body_html = body_match.group(1) if body_match else ""

    inline_images = []

    for src in INLINE_IMG_RE.findall(body_html):
        src = html_module.unescape(src).strip()
        if src.startswith(("http://", "https://")) and src not in inline_images:
            inline_images.append(src)

    return {
        "title": _clean_text(title_match.group(1)) if title_match else "",
        "cover_url": cover_match.group(1) if cover_match else None,
        "content_html": body_html,
        "inline_images": inline_images,
    }


# ------------------------------------------------------------------ media


def _original_name(url: str, fallback: str) -> str:
    name = unquote(Path(urlparse(url).path).name)
    return name or fallback


def download_and_save_image(url: str, *, alt: str, title: str) -> int | None:
    """Скачивает изображение и кладёт его в медиатеку. Возвращает media.id
    либо None, если файл не удалось получить/обработать."""
    candidates = [normalize_image_url(url)]
    if candidates[0] != url:
        candidates.append(url)

    file_bytes = None

    for candidate in candidates:
        try:
            file_bytes = _fetch(candidate)
            url = candidate
            break
        except (HTTPError, URLError):
            continue

    if not file_bytes:
        print(f"    ! не скачалось: {url}")
        return None

    try:
        media = save_image(
            file_bytes,
            _original_name(url, "news-image"),
            alt=alt or None,
            title=title or None,
            category_id=[MEDIA_CATEGORY_NEWS],
        )
    except MediaValidationError as exc:
        print(f"    ! пропущено ({exc}): {url}")
        return None

    return media["id"]


# ------------------------------------------------------------------ database


def delete_all_news() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM news")
            removed = cur.rowcount

    return removed


def insert_news(article: dict, media_ids: list[int]) -> int:
    """Пишет новость и её связи с медиа. Первый media_id — обложка."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO news (
                    slug, title, excerpt, content, category_id,
                    published_at, is_published, is_featured,
                    seo_title, seo_description
                )
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s)
                RETURNING id
                """,
                (
                    article["slug"],
                    article["title"],
                    article["excerpt"],
                    article["content"],
                    article["category_id"],
                    article["published_at"],
                    article["is_featured"],
                    article["title"],
                    article["excerpt"],
                ),
            )

            news_id = cur.fetchone()[0]

            for index, media_id in enumerate(media_ids):
                cur.execute(
                    """
                    INSERT INTO news_media (news_id, media_id, sort_order, is_cover)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (news_id, media_id, index, index == 0),
                )

    return news_id


def news_exists(slug: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM news WHERE slug = %s LIMIT 1", (slug,))
            return cur.fetchone() is not None


# ------------------------------------------------------------------ pipeline


def build_article(item: dict, page_html: str) -> dict:
    parsed = parse_article(page_html)
    content = html_to_text(parsed["content_html"])

    day, month, year = item["date"].split(".")
    published_at = datetime(
        int(year), int(month), int(day),
        tzinfo=timezone(timedelta(hours=3)),
    )

    title = parsed["title"] or item["title"]

    return {
        "slug": item["slug"],
        "title": title,
        "excerpt": build_excerpt(content),
        "content": content,
        "cover_url": parsed["cover_url"] or normalize_image_url(item["thumb_url"]),
        "inline_images": parsed["inline_images"],
        "category_id": CATEGORY_BY_SLUG.get(item["slug"], DEFAULT_CATEGORY),
        "is_featured": item["slug"] in FEATURED_SLUGS,
        "published_at": published_at,
    }


def import_one(item: dict, *, dry_run: bool = False) -> bool:
    if news_exists(item["slug"]):
        print(f"  = пропуск (уже есть): {item['slug']}")
        return False

    page_html = _fetch_text(item["url"])
    article = build_article(item, page_html)

    if not article["content"]:
        print(f"  ! пустой текст, пропуск: {article['slug']}")
        return False

    image_urls = [article["cover_url"]] + article["inline_images"]

    print(
        f"  + {article['title']}\n"
        f"      дата: {article['published_at']:%d.%m.%Y}, "
        f"рубрика: {article['category_id']}, "
        f"изображений: {len(image_urls)}, "
        f"текст: {len(article['content'])} символов"
    )

    if dry_run:
        return True

    media_ids = []

    for index, image_url in enumerate(image_urls):
        # Не дублируем уже сохранённую картинку внутри одной новости.
        media_id = download_and_save_image(
            image_url,
            alt=article["title"],
            title=article["title"],
        )
        if media_id is not None and media_id not in media_ids:
            media_ids.append(media_id)

    insert_news(article, media_ids)
    return True


def run(*, replace: bool = False, dry_run: bool = False) -> None:
    print("Читаю список новостей albion.su ...")
    items = fetch_news_list()
    print(f"Найдено новостей: {len(items)}\n")

    if replace and not dry_run:
        removed = delete_all_news()
        print(f"Удалено старых новостей: {removed}\n")

    imported = 0

    for item in items:
        try:
            if import_one(item, dry_run=dry_run):
                imported += 1
        except (HTTPError, URLError) as exc:
            print(f"  ! не удалось загрузить {item['url']}: {exc}")

    suffix = " (dry-run, без записи)" if dry_run else ""
    print(f"\nГотово. Импортировано новостей: {imported}{suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Импорт новостей с albion.su в CMS проекта.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="удалить существующие новости перед импортом",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только показать, что будет импортировано",
    )
    args = parser.parse_args()

    run(replace=args.replace, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
