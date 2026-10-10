"""Главная страница: вертикальные слайды и горизонтальные карточки.

Слайд = фото + заголовок + текст + (необязательная) кнопка.
У верхнего слайда (is_hero) дополнительно есть горизонтальные карточки
(home_slide_items), которые листаются каруселью.
"""
from __future__ import annotations

from typing import Optional

from backend.services.data_service import get_connection


_SLIDE_FIELDS = (
    "title",
    "text",
    "button_label",
    "button_url",
    "image_path",
)

_ITEM_FIELDS = (
    "title",
    "text",
    "eyebrow",
    "slogan",
    "button_label",
    "button_url",
    "button2_label",
    "button2_url",
    "image_path",
    "extra",
)


def _slide_dict(row) -> dict:
    (
        slide_id,
        sort_order,
        is_hero,
        kind,
        title,
        text,
        button_label,
        button_url,
        image_path,
        is_active,
    ) = row

    return {
        "id": slide_id,
        "sort_order": sort_order,
        "is_hero": is_hero,
        "kind": kind or ("hero" if is_hero else "text"),
        "title": title or "",
        "text": text or "",
        "button_label": button_label or "",
        "button_url": button_url or "",
        "image": image_path or "",
        "is_active": is_active,
        "items": [],
    }


def _item_dict(row) -> dict:
    (
        item_id,
        slide_id,
        sort_order,
        title,
        text,
        eyebrow,
        slogan,
        button_label,
        button_url,
        button2_label,
        button2_url,
        image_path,
        extra,
        is_active,
    ) = row

    return {
        "id": item_id,
        "slide_id": slide_id,
        "sort_order": sort_order,
        "title": title or "",
        "text": text or "",
        "eyebrow": eyebrow or "",
        "slogan": slogan or "",
        "button_label": button_label or "",
        "button_url": button_url or "",
        "button2_label": button2_label or "",
        "button2_url": button2_url or "",
        "image": image_path or "",
        "extra": extra or "",
        "is_active": is_active,
    }


def _fetch_slides(conn, *, only_active: bool) -> list[dict]:
    where = "WHERE is_active = TRUE" if only_active else ""

    rows = conn.execute(
        f"""
        SELECT id, sort_order, is_hero, kind, title, text,
               button_label, button_url, image_path, is_active
        FROM home_slides
        {where}
        ORDER BY sort_order, id
        """
    ).fetchall()

    slides = [_slide_dict(row) for row in rows]
    by_id = {slide["id"]: slide for slide in slides}

    if not by_id:
        return slides

    item_where = "AND is_active = TRUE" if only_active else ""

    items = conn.execute(
        f"""
        SELECT id, slide_id, sort_order, title, text,
               eyebrow, slogan, button_label, button_url,
               button2_label, button2_url, image_path, extra, is_active
        FROM home_slide_items
        WHERE slide_id = ANY(%s) {item_where}
        ORDER BY sort_order, id
        """,
        (list(by_id.keys()),),
    ).fetchall()

    for row in items:
        item = _item_dict(row)
        slide = by_id.get(item["slide_id"])

        if slide is not None:
            slide["items"].append(item)

    return slides


def get_home() -> dict:
    """Публичный контент главной: активные слайды с карточками."""
    with get_connection() as conn:
        slides = _fetch_slides(conn, only_active=True)

    if any(slide.get("kind") == "geo" for slide in slides):
        from backend.services.home_geo_service import get_public_geo

        geo = get_public_geo()
        for slide in slides:
            if slide.get("kind") == "geo":
                slide["geo"] = geo

    return {"slides": slides}


# ---------------------------------------------------------------- админка


def list_slides() -> list[dict]:
    with get_connection() as conn:
        return _fetch_slides(conn, only_active=False)


def _next_slide_order(conn) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM home_slides"
    ).fetchone()
    return int(row[0]) if row else 0


def _next_item_order(conn, slide_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM home_slide_items "
        "WHERE slide_id = %s",
        (slide_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def create_slide(data: dict) -> dict:
    values = {field: str(data.get(field) or "") for field in _SLIDE_FIELDS}
    is_hero = bool(data.get("is_hero"))
    kind = str(data.get("kind") or ("hero" if is_hero else "text"))

    with get_connection() as conn:
        with conn.transaction():
            order = _next_slide_order(conn)

            row = conn.execute(
                """
                INSERT INTO home_slides
                    (sort_order, is_hero, kind, title, text,
                     button_label, button_url, image_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    order,
                    is_hero,
                    kind,
                    values["title"],
                    values["text"],
                    values["button_label"],
                    values["button_url"],
                    values["image_path"],
                ),
            ).fetchone()

            new_id = row[0]

            if is_hero:
                # Верхний слайд только один.
                conn.execute(
                    "UPDATE home_slides SET is_hero = FALSE WHERE id <> %s",
                    (new_id,),
                )

    return get_slide(new_id)


def get_slide(slide_id: int) -> Optional[dict]:
    with get_connection() as conn:
        slides = _fetch_slides(conn, only_active=False)

    for slide in slides:
        if slide["id"] == int(slide_id):
            return slide

    return None


def update_slide(slide_id: int, data: dict) -> Optional[dict]:
    sets = []
    params: list = []

    for field in _SLIDE_FIELDS:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(str(data.get(field) or ""))

    with get_connection() as conn:
        with conn.transaction():
            if "kind" in data:
                sets.append("kind = %s")
                params.append(str(data.get("kind") or "text"))

            if "is_hero" in data:
                sets.append("is_hero = %s")
                params.append(bool(data.get("is_hero")))

            if "is_active" in data:
                sets.append("is_active = %s")
                params.append(bool(data.get("is_active")))

            if sets:
                sets.append("updated_at = NOW()")
                params.append(int(slide_id))
                conn.execute(
                    f"UPDATE home_slides SET {', '.join(sets)} WHERE id = %s",
                    tuple(params),
                )

            if data.get("is_hero"):
                conn.execute(
                    "UPDATE home_slides SET is_hero = FALSE WHERE id <> %s",
                    (int(slide_id),),
                )

    return get_slide(slide_id)


def delete_slide(slide_id: int) -> bool:
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute(
                "DELETE FROM home_slides WHERE id = %s", (int(slide_id),)
            )

    return cur.rowcount > 0


def create_item(slide_id: int, data: dict) -> Optional[dict]:
    values = {field: str(data.get(field) or "") for field in _ITEM_FIELDS}

    with get_connection() as conn:
        with conn.transaction():
            order = _next_item_order(conn, int(slide_id))

            row = conn.execute(
                """
                INSERT INTO home_slide_items
                    (slide_id, sort_order, title, text, eyebrow, slogan,
                     button_label, button_url, button2_label, button2_url,
                     image_path, extra)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    int(slide_id),
                    order,
                    values["title"],
                    values["text"],
                    values["eyebrow"],
                    values["slogan"],
                    values["button_label"],
                    values["button_url"],
                    values["button2_label"],
                    values["button2_url"],
                    values["image_path"],
                    values["extra"],
                ),
            ).fetchone()

    return get_item(row[0])


def get_item(item_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, slide_id, sort_order, title, text,
                   eyebrow, slogan, button_label, button_url,
                   button2_label, button2_url, image_path, extra, is_active
            FROM home_slide_items WHERE id = %s
            """,
            (int(item_id),),
        ).fetchone()

    return _item_dict(row) if row else None


def update_item(item_id: int, data: dict) -> Optional[dict]:
    sets = []
    params: list = []

    for field in _ITEM_FIELDS:
        if field in data:
            sets.append(f"{field} = %s")
            params.append(str(data.get(field) or ""))

    if "is_active" in data:
        sets.append("is_active = %s")
        params.append(bool(data.get("is_active")))

    if not sets:
        return get_item(item_id)

    params.append(int(item_id))

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                f"UPDATE home_slide_items SET {', '.join(sets)} WHERE id = %s",
                tuple(params),
            )

    return get_item(item_id)


def delete_item(item_id: int) -> bool:
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute(
                "DELETE FROM home_slide_items WHERE id = %s", (int(item_id),)
            )

    return cur.rowcount > 0


# ---------------------------------------------------------------- форма подписки


def create_feedback(data: dict) -> dict:
    name = str(data.get("name") or "").strip()[:200]
    phone = str(data.get("phone") or "").strip()[:80]
    message = str(data.get("message") or "").strip()[:4000]

    if not (name or phone or message):
        raise ValueError("Пустое сообщение")

    with get_connection() as conn:
        with conn.transaction():
            row = conn.execute(
                """
                INSERT INTO site_feedback (name, phone, message)
                VALUES (%s, %s, %s)
                RETURNING id, created_at
                """,
                (name, phone, message),
            ).fetchone()

    return {
        "id": row[0],
        "created_at": row[1].isoformat() if row[1] else None,
    }


def list_feedback() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, phone, message, created_at
            FROM site_feedback
            ORDER BY id DESC
            LIMIT 200
            """
        ).fetchall()

    return [
        {
            "id": r[0],
            "name": r[1] or "",
            "phone": r[2] or "",
            "message": r[3] or "",
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


def delete_feedback(feedback_id: int) -> bool:
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute(
                "DELETE FROM site_feedback WHERE id = %s", (int(feedback_id),)
            )

    return cur.rowcount > 0
