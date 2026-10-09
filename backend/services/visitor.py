"""Разбор посетителя: IP, User-Agent, необратимый хеш для уникальности.

IP-адрес НЕ сохраняется в БД — он используется только здесь, чтобы:
  • определить страну (см. geoip.lookup_country);
  • посчитать visitor_hash (уникальный посетитель без хранения адреса).

Хеш = sha256(salt | IP | User-Agent). Соль лежит в site_settings
(ключ visit_salt) и генерируется миграцией migrate_page_visits.
Ротация соли сбрасывает подсчёт уникальных посетителей.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets

from backend.services.data_service import get_connection


logger = logging.getLogger(__name__)

SALT_KEY = "visit_salt"

# ------------------------------- User-Agent разбор (без зависимостей)

_BOT_RE = re.compile(
    r"bot|crawler|spider|crawl|slurp|bingpreview|yandexbot|googlebot|"
    r"ahrefs|semrush|facebookexternalhit|telegrambot|whatsapp|preview|"
    r"headlesschrome|python-requests|curl/|wget/|httpx|go-http-client",
    re.IGNORECASE,
)

_TABLET_RE = re.compile(r"ipad|tablet|kindle|playbook|silk", re.IGNORECASE)
_MOBILE_RE = re.compile(
    r"mobi|iphone|android|ipod|blackberry|opera mini|windows phone",
    re.IGNORECASE,
)

# Порядок важен: Edge/Opera/Chrome содержат чужие подстроки.
_BROWSERS = (
    ("yandex", re.compile(r"yabrowser", re.IGNORECASE)),
    ("edge", re.compile(r"edg/|edgios|edga", re.IGNORECASE)),
    ("opera", re.compile(r"opr/|opera", re.IGNORECASE)),
    ("chrome", re.compile(r"chrome|crios", re.IGNORECASE)),
    ("firefox", re.compile(r"firefox|fxios", re.IGNORECASE)),
    ("safari", re.compile(r"safari", re.IGNORECASE)),
)


def parse_user_agent(ua: str | None) -> dict:
    """Возвращает {device, browser, is_bot} по строке User-Agent."""
    text = ua or ""

    is_bot = bool(_BOT_RE.search(text)) or not text

    if is_bot:
        device = "bot"
        browser = "bot"
    else:
        if _TABLET_RE.search(text):
            device = "tablet"
        elif _MOBILE_RE.search(text):
            device = "mobile"
        else:
            device = "desktop"

        browser = "other"

        for name, pattern in _BROWSERS:
            if pattern.search(text):
                browser = name
                break

    return {"device": device, "browser": browser, "is_bot": is_bot}


def client_ip(request) -> str | None:
    """IP посетителя.

    За прокси реальный адрес — в X-Forwarded-For (первый хоп). Доверять
    ему можно только если фронт действительно за прокси, поэтому читаем
    его ЛИШЬ при ALBION_TRUST_PROXY=1 — иначе клиент мог бы подделать
    заголовок. По умолчанию берём непосредственного peer (как admin_login).
    """
    if request is None:
        return None

    if os.getenv("ALBION_TRUST_PROXY") == "1":
        forwarded = request.headers.get("x-forwarded-for")

        if forwarded:
            first = forwarded.split(",")[0].strip()

            if first:
                return first

    return request.client.host if request.client else None


# ------------------------------- соль и хеш посетителя

_salt_cache: str | None = None


def _load_salt() -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM site_settings WHERE key = %s",
            (SALT_KEY,),
        ).fetchone()

    if row and row[0]:
        return str(row[0])

    # Соли нет — создаём (миграция обычно делает это заранее).
    salt = secrets.token_hex(32)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO site_settings (key, value, value_type, description)
            VALUES (%s, %s, 'text', 'Соль хеширования посетителей')
            ON CONFLICT (key) DO NOTHING
            """,
            (SALT_KEY, salt),
        )

        row = conn.execute(
            "SELECT value FROM site_settings WHERE key = %s",
            (SALT_KEY,),
        ).fetchone()

    return str(row[0]) if row and row[0] else salt


def get_visit_salt() -> str:
    """Соль из site_settings (кэшируется на процесс)."""
    global _salt_cache

    if _salt_cache is None:
        try:
            _salt_cache = _load_salt()
        except Exception:
            logger.warning("Не удалось получить соль визитов", exc_info=True)
            _salt_cache = "albion-fallback-salt"

    return _salt_cache


def visitor_hash(ip: str | None, ua: str | None) -> str:
    """Необратимый идентификатор посетителя (первые 32 hex-символа)."""
    raw = f"{get_visit_salt()}|{ip or ''}|{ua or ''}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
