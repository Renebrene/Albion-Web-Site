"""Администрирование заявок: статусы, удаление, экспорт, уведомления.

Заявки приходят с сайта (``POST /api/requests``, ``account_id = NULL``) и из
личного кабинета, складываются в ``client_requests``.

Уведомления на почту — «основа»: **адрес получателя задаётся в админке**
(``site_settings['request_notify']``), а параметры SMTP берутся из
окружения (``ALBION_SMTP_*``), чтобы пароли не лежали в базе. Если SMTP не
настроен, заявка просто сохраняется — отправка сообщает причину.
"""

from __future__ import annotations

import csv
import io
import json
import os
import smtplib
from email.message import EmailMessage
from typing import Any

from backend.services.data_service import get_connection


SETTINGS_KEY = "request_notify"

STATUSES: list[dict[str, str]] = [
    {"value": "new", "label": "Новая"},
    {"value": "in_progress", "label": "В работе"},
    {"value": "done", "label": "Закрыта"},
    {"value": "canceled", "label": "Отменена"},
]

STATUS_VALUES = {item["value"] for item in STATUSES}
STATUS_LABELS = {item["value"]: item["label"] for item in STATUSES}

EXPORT_FORMATS = {"csv", "xlsx"}

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
}

# Колонки выгрузки: (заголовок, извлечение из заявки).
_COLUMNS: list[tuple[str, Any]] = [
    ("ID", lambda row: row.get("id")),
    ("Дата", lambda row: row.get("created_at") or ""),
    (
        "Откуда",
        lambda row: (
            f"Кабинет: {row['account_login']}"
            if row.get("account_login")
            else "Сайт"
        ),
    ),
    ("Имя", lambda row: (row.get("payload") or {}).get("name", "")),
    ("Телефон", lambda row: (row.get("payload") or {}).get("phone", "")),
    ("E-mail", lambda row: (row.get("payload") or {}).get("email", "")),
    ("Комментарий", lambda row: (row.get("payload") or {}).get("comment", "")),
    ("Что", lambda row: row.get("title", "")),
    (
        "Конструкции",
        lambda row: "; ".join(
            str(item.get("title") or item.get("id") or "")
            for item in ((row.get("payload") or {}).get("items") or [])
        ),
    ),
    (
        "Статус",
        lambda row: STATUS_LABELS.get(
            str(row.get("status") or ""),
            str(row.get("status") or ""),
        ),
    ),
]


# ------------------------------------------------------------- настройки


def _default_settings() -> dict:
    return {"enabled": False, "email": ""}


def get_notify_settings() -> dict:
    """Куда и нужно ли слать уведомления о заявках."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM site_settings WHERE key = %s",
            (SETTINGS_KEY,),
        ).fetchone()

    stored: dict = {}

    if row and row[0]:
        try:
            parsed = json.loads(row[0])

            if isinstance(parsed, dict):
                stored = parsed
        except (json.JSONDecodeError, TypeError):
            stored = {}

    settings = _default_settings()

    if stored.get("email") is not None:
        settings["email"] = str(stored["email"])[:400].strip()

    if stored.get("enabled") is not None:
        settings["enabled"] = bool(stored["enabled"])

    settings["smtp_configured"] = smtp_configured()

    return settings


def save_notify_settings(payload: dict) -> dict:
    """Сохраняет адрес(а) и переключатель уведомлений."""
    if not isinstance(payload, dict):
        raise ValueError("Ожидается объект настроек")

    settings = get_notify_settings()

    if "email" in payload:
        email = str(payload.get("email") or "")

        # Может быть несколько получателей через запятую.
        parts = [part.strip() for part in email.replace(";", ",").split(",")]
        parts = [part for part in parts if part]

        for part in parts:
            if "@" not in part or len(part) > 200:
                raise ValueError(f"Некорректный адрес: {part}")

        settings["email"] = ", ".join(parts)

    if "enabled" in payload:
        settings["enabled"] = bool(payload.get("enabled"))

    if settings["enabled"] and not settings.get("email"):
        raise ValueError("Укажите почту для уведомлений")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO site_settings (key, value, value_type, description)
            VALUES (%s, %s, 'json', 'Заявки: уведомления на почту')
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (
                SETTINGS_KEY,
                json.dumps(
                    {
                        "email": settings.get("email", ""),
                        "enabled": settings.get("enabled", False),
                    },
                    ensure_ascii=False,
                ),
            ),
        )

    return get_notify_settings()


# ------------------------------------------------------------- изменение


def set_status(request_id: int, status: str) -> dict:
    """Меняет статус заявки."""
    value = str(status or "").strip()

    if value not in STATUS_VALUES:
        raise ValueError(
            "Недопустимый статус. Доступны: "
            + ", ".join(sorted(STATUS_VALUES))
        )

    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE client_requests
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, status
            """,
            (value, int(request_id)),
        ).fetchone()

    if not row:
        raise ValueError("Заявка не найдена")

    return {"id": row[0], "status": row[1]}


def delete_request(request_id: int) -> dict:
    """Удаляет заявку (необратимо)."""
    with get_connection() as conn:
        row = conn.execute(
            "DELETE FROM client_requests WHERE id = %s RETURNING id",
            (int(request_id),),
        ).fetchone()

    if not row:
        raise ValueError("Заявка не найдена")

    return {"id": row[0], "deleted": True}


# ------------------------------------------------------------- экспорт


def export_requests(fmt: str = "csv") -> tuple[bytes, str, str]:
    """Выгрузка заявок: (содержимое, имя файла, content-type)."""
    from backend.services.account_service import list_all_requests

    if fmt not in EXPORT_FORMATS:
        raise ValueError("Поддерживаются форматы: csv, xlsx")

    rows = list_all_requests(limit=1000)

    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        writer.writerow([title for title, _ in _COLUMNS])

        for row in rows:
            writer.writerow([str(getter(row)) for _, getter in _COLUMNS])

        # BOM — чтобы Excel открыл UTF-8 без «кракозябр».
        content = buffer.getvalue().encode("utf-8-sig")

        return content, "zayavki.csv", CONTENT_TYPES["csv"]

    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    book = Workbook()
    sheet = book.active
    sheet.title = "Заявки"

    sheet.append([title for title, _ in _COLUMNS])

    for row in rows:
        sheet.append([str(getter(row)) for _, getter in _COLUMNS])

    widths = [6, 20, 18, 18, 18, 40, 40, 40, 12]

    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    buffer_bytes = io.BytesIO()
    book.save(buffer_bytes)

    return buffer_bytes.getvalue(), "zayavki.xlsx", CONTENT_TYPES["xlsx"]


# ------------------------------------------------------------- уведомления


def smtp_configured() -> bool:
    """Заданы ли параметры SMTP в окружении."""
    return bool(os.getenv("ALBION_SMTP_HOST") and _smtp_from())


def _smtp_from() -> str:
    return str(
        os.getenv("ALBION_SMTP_FROM")
        or os.getenv("ALBION_SMTP_USER")
        or ""
    ).strip()


def _format_body(request: dict) -> str:
    payload = request.get("payload") or {}
    items = payload.get("items") or []

    lines = [
        f"Заявка №{request.get('id')} с сайта",
        "",
        f"Имя:      {payload.get('name', '—')}",
        f"Телефон:  {payload.get('phone') or '—'}",
        f"E-mail:   {payload.get('email') or '—'}",
        f"Комментарий: {payload.get('comment') or '—'}",
        "",
        f"Что: {request.get('title', '')}",
    ]

    if items:
        lines.append("")
        lines.append("Выбранные конструкции:")

        for index, item in enumerate(items, start=1):
            lines.append(
                f"  {index}. {item.get('title') or ''}"
                + (f" (id {item.get('id')})" if item.get("id") else "")
            )

    lines += ["", f"Получена: {request.get('created_at') or ''}"]

    return "\n".join(lines)


def _send_notification(subject: str, body: str) -> dict:
    """Общая отправка на адрес(а) из настроек админки.

    Никогда не бросает исключение — сохранение заявки важнее уведомления.
    """
    try:
        settings = get_notify_settings()
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "reason": f"настройки недоступны: {exc}"}

    if not settings.get("enabled"):
        return {"sent": False, "reason": "уведомления выключены"}

    recipients = [
        part.strip()
        for part in str(settings.get("email") or "").split(",")
        if part.strip()
    ]

    if not recipients:
        return {"sent": False, "reason": "не указан адрес"}

    if not smtp_configured():
        return {
            "sent": False,
            "reason": "SMTP не настроен (ALBION_SMTP_HOST/USER/PASSWORD)",
        }

    host = os.getenv("ALBION_SMTP_HOST", "")
    port = int(os.getenv("ALBION_SMTP_PORT", "587"))
    user = os.getenv("ALBION_SMTP_USER", "")
    password = os.getenv("ALBION_SMTP_PASSWORD", "")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _smtp_from()
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if os.getenv("ALBION_SMTP_TLS", "1") != "0":
                smtp.starttls()

            if user and password:
                smtp.login(user, password)

            smtp.send_message(message)
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "reason": str(exc)}

    return {"sent": True, "to": recipients}


def _format_feedback(feedback: dict) -> str:
    return "\n".join(
        [
            "Новое сообщение с формы обратной связи",
            "",
            f"Имя:      {feedback.get('name') or '—'}",
            f"Телефон:  {feedback.get('phone') or '—'}",
            f"Сообщение: {feedback.get('message') or '—'}",
            "",
            f"Получено: {feedback.get('created_at') or ''}",
        ]
    )


def notify_new_request(request: dict) -> dict:
    """Отправляет уведомление о новой заявке."""
    return _send_notification(
        f"Заявка с сайта: {request.get('title') or 'новая'}",
        _format_body(request),
    )


def notify_new_feedback(feedback: dict) -> dict:
    """Отправляет сообщение формы обратной связи на почту из админки."""
    return _send_notification(
        "Сообщение с формы обратной связи",
        _format_feedback(feedback),
    )
