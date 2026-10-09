"""Запись и чтение статистики визитов (таблица page_visits).

Запись (record_visit) вызывается из публичного /api/track в горячем пути
и никогда не должна ломать ответ посетителю — все ошибки глотаются.

Чтение (summary/daily/countries/pages/list_visits) — для админ-раздела.
Боты исключаются из агрегатов (в сводке показывается их доля), но
остаются в журнале визитов с пометкой.
"""
from __future__ import annotations

import logging

from backend.services.data_service import get_connection
from backend.services.geoip import lookup_country
from backend.services.visitor import parse_user_agent, visitor_hash


logger = logging.getLogger(__name__)

MAX_PATH_LENGTH = 512
MAX_REFERRER_LENGTH = 512


def _iso(value):
    return value.isoformat() if value is not None else None


# ---------------------------------------------------------------- запись


def record_visit(
    path: str,
    referrer: str | None,
    ip: str | None,
    user_agent: str | None,
) -> None:
    """Сохраняет визит. Ошибки глушатся — трекинг не влияет на ответ."""
    path = (path or "").strip()[:MAX_PATH_LENGTH]

    if not path:
        return

    referrer = (referrer or "").strip()[:MAX_REFERRER_LENGTH] or None

    ua = (user_agent or "")[:MAX_REFERRER_LENGTH]

    parsed = parse_user_agent(ua)
    country_code, country_name = lookup_country(ip)
    digest = visitor_hash(ip, ua)

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO page_visits
                    (path, referrer, country_code, country_name,
                     is_bot, device, browser, visitor_hash)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    path,
                    referrer,
                    country_code,
                    country_name,
                    parsed["is_bot"],
                    parsed["device"],
                    parsed["browser"],
                    digest,
                ),
            )
    except Exception:
        logger.warning("Не удалось записать визит", exc_info=True)


# ---------------------------------------------------------------- чтение


def _range_clause(date_from, date_to, column="created_at"):
    """Части WHERE по диапазону дат (включительно). Пусто — без фильтра."""
    clauses = []
    params = []

    if date_from:
        clauses.append(f"{column} >= %s::date")
        params.append(date_from)

    if date_to:
        clauses.append(f"{column} < (%s::date + INTERVAL '1 day')")
        params.append(date_to)

    return clauses, params


def _window_count(conn, days: int) -> dict:
    """Визиты и уникальные за последние `days` суток (боты исключены)."""
    row = conn.execute(
        f"""
        SELECT COUNT(*), COUNT(DISTINCT visitor_hash)
        FROM page_visits
        WHERE NOT is_bot
          AND created_at >= NOW() - INTERVAL '{int(days)} days'
        """
    ).fetchone()

    return {"visits": row[0], "unique": row[1]}


def summary(date_from=None, date_to=None) -> dict:
    """КПЭ: окна 1/7/30 дней + показатели за выбранный период."""
    clauses, params = _range_clause(date_from, date_to)
    base = " AND ".join(clauses) if clauses else "TRUE"

    with get_connection() as conn:
        today = _window_count(conn, 1)
        week = _window_count(conn, 7)
        month = _window_count(conn, 30)

        row = conn.execute(
            f"""
            SELECT
                COUNT(*) FILTER (WHERE NOT is_bot)              AS visits,
                COUNT(DISTINCT visitor_hash)
                    FILTER (WHERE NOT is_bot)                   AS unique_visitors,
                COUNT(DISTINCT country_code)
                    FILTER (WHERE NOT is_bot)                   AS countries,
                COUNT(*) FILTER (WHERE is_bot)                  AS bots,
                COUNT(*)                                        AS total
            FROM page_visits
            WHERE {base}
            """,
            params,
        ).fetchone()

    visits, unique_visitors, countries_count, bots, total = row
    bot_share = round(bots / total, 4) if total else 0.0

    return {
        "today": today,
        "week": week,
        "month": month,
        "period": {
            "visits": visits,
            "unique": unique_visitors,
            "countries": countries_count,
            "bots": bots,
            "bot_share": bot_share,
        },
    }


def daily(date_from=None, date_to=None) -> list[dict]:
    """Визиты и уникальные по дням (боты исключены)."""
    clauses, params = _range_clause(date_from, date_to)
    where = ("WHERE NOT is_bot AND " + " AND ".join(clauses)) if clauses \
        else "WHERE NOT is_bot"

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                to_char(created_at::date, 'YYYY-MM-DD') AS day,
                COUNT(*),
                COUNT(DISTINCT visitor_hash)
            FROM page_visits
            {where}
            GROUP BY created_at::date
            ORDER BY created_at::date
            """,
            params,
        ).fetchall()

    return [
        {"date": row[0], "visits": row[1], "unique": row[2]}
        for row in rows
    ]


def countries(date_from=None, date_to=None, limit: int = 50) -> list[dict]:
    """Разрез по странам с долей от визитов (боты исключены)."""
    clauses, params = _range_clause(date_from, date_to)
    where = ("WHERE NOT is_bot AND " + " AND ".join(clauses)) if clauses \
        else "WHERE NOT is_bot"

    limit = max(1, min(int(limit), 200))

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                country_code,
                MAX(country_name) AS country_name,
                COUNT(*) AS visits,
                COUNT(DISTINCT visitor_hash) AS unique_visitors
            FROM page_visits
            {where}
            GROUP BY country_code
            ORDER BY visits DESC
            LIMIT %s
            """,
            (*params, limit),
        ).fetchall()

    total = sum(row[2] for row in rows) or 0

    return [
        {
            "code": row[0],
            "name": row[1],
            "visits": row[2],
            "unique": row[3],
            "share": round(row[2] / total, 4) if total else 0.0,
        }
        for row in rows
    ]


def pages(date_from=None, date_to=None, limit: int = 50) -> list[dict]:
    """Топ страниц (боты исключены)."""
    clauses, params = _range_clause(date_from, date_to)
    where = ("WHERE NOT is_bot AND " + " AND ".join(clauses)) if clauses \
        else "WHERE NOT is_bot"

    limit = max(1, min(int(limit), 200))

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                path,
                COUNT(*) AS visits,
                COUNT(DISTINCT visitor_hash) AS unique_visitors
            FROM page_visits
            {where}
            GROUP BY path
            ORDER BY visits DESC
            LIMIT %s
            """,
            (*params, limit),
        ).fetchall()

    return [
        {"path": row[0], "visits": row[1], "unique": row[2]}
        for row in rows
    ]


def list_visits(date_from=None, date_to=None, limit: int = 50, offset: int = 0):
    """Журнал визитов (включая ботов) с пагинацией -> (items, total)."""
    clauses, params = _range_clause(date_from, date_to)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM page_visits {where}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT
                created_at, path, referrer, country_code, country_name,
                is_bot, device, browser, visitor_hash
            FROM page_visits
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        ).fetchall()

    items = [
        {
            "created_at": _iso(row[0]),
            "path": row[1],
            "referrer": row[2],
            "country_code": row[3],
            "country_name": row[4],
            "is_bot": row[5],
            "device": row[6],
            "browser": row[7],
            # Показываем только короткий префикс хеша — IP не хранится.
            "visitor": (row[8] or "")[:10],
        }
        for row in rows
    ]

    return items, total
