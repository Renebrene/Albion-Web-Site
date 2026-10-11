"""Сервис пунктов меню сайта: верхнее меню (main) и подвал (footer)."""
from __future__ import annotations

from typing import Any

from backend.services.data_service import get_connection
from backend.services.cms_url import clean_cms_url


SECTIONS = ("main", "footer")


def _row_payload(row) -> dict:
    return {
        "key": row[0],
        "label": row[1],
        "url": row[2],
        "sort_order": row[3],
        "is_active": row[4],
    }


def _load_section(conn, section: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT key, label, url, sort_order, is_active
        FROM site_menu_items
        WHERE section = %s
        ORDER BY sort_order, id
        """,
        (section,),
    ).fetchall()

    return [_row_payload(row) for row in rows]


def get_public_menu() -> dict:
    """Публичное меню: только активные пункты."""
    with get_connection() as conn:
        return {
            "main": [
                item
                for item in _load_section(conn, "main")
                if item["is_active"]
            ],
            "footer": [
                item
                for item in _load_section(conn, "footer")
                if item["is_active"]
            ],
        }


def get_admin_menu() -> dict:
    """Полное меню для редактора админки (включая неактивные)."""
    with get_connection() as conn:
        return {
            "main": _load_section(conn, "main"),
            "footer": _load_section(conn, "footer"),
        }


def _clean(value: Any) -> str:
    return (value or "").strip()


def update_menu_items(
    main: list[dict] | None = None,
    footer: list[dict] | None = None,
) -> dict:
    """Заменяет пункты разделов целиком (main/footer по мере передачи)."""
    payload = {
        "main": main,
        "footer": footer,
    }

    with get_connection() as conn:
        with conn.transaction():
            for section, items in payload.items():
                if items is None:
                    continue

                conn.execute(
                    "DELETE FROM site_menu_items WHERE section = %s",
                    (section,),
                )

                for index, item in enumerate(items):
                    label = _clean(item.get("label"))
                    try:
                        url = clean_cms_url(item.get("url"))
                    except ValueError as exc:
                        raise ValueError(
                            f"Пункт меню «{section}»: {exc}"
                        ) from exc

                    if not label:
                        raise ValueError(
                            f"Пункт меню «{section}» без названия"
                        )

                    key = _clean(item.get("key")) or (
                        f"item-{section}-{index + 1}"
                    )

                    conn.execute(
                        """
                        INSERT INTO site_menu_items (
                            section, key, label, url,
                            sort_order, is_active
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            section,
                            key,
                            label,
                            url,
                            int(item.get("sort_order") or (index + 1) * 10),
                            bool(item.get("is_active", True)),
                        ),
                    )

    return get_admin_menu()