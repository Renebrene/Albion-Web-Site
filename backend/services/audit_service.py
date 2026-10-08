"""Сервис журнала действий администраторов.

Пишет записи в таблицу admin_audit_log и отдаёт их для админ-раздела
«Журнал действий».

Логирование не должно ломать основной сценарий: ошибки записи
проглатываются (метод log_admin_action никогда не бросает исключение).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.data_service import get_connection


logger = logging.getLogger(__name__)


def _serialize_details(details: Any) -> str | None:
    """details в БД — TEXT: dict/list сериализуем в JSON."""
    if details is None:
        return None

    if isinstance(details, str):
        return details

    try:
        return json.dumps(details, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(details)


def log_admin_action(
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: Any = None,
    ip_address: str | None = None,
) -> None:
    """Пишет одну запись в admin_audit_log.

    Никогда не падает: при любой ошибке логирования просто фиксирует
    предупреждение в лог приложения.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admin_audit_log (
                    user_id,
                    action,
                    entity_type,
                    entity_id,
                    details,
                    ip_address
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    action,
                    entity_type,
                    entity_id,
                    _serialize_details(details),
                    ip_address,
                ),
            )
    except Exception:
        logger.warning(
            "Не удалось записать действие в admin_audit_log "
            "(action=%s, user_id=%s)",
            action,
            user_id,
            exc_info=True,
        )


def _row_payload(row) -> dict:
    (
        log_id,
        user_id,
        login,
        name,
        action,
        entity_type,
        entity_id,
        details,
        ip_address,
        created_at,
    ) = row

    parsed_details = details
    if isinstance(details, str) and details:
        try:
            parsed_details = json.loads(details)
        except (TypeError, ValueError):
            parsed_details = details

    return {
        "id": log_id,
        "user_id": user_id,
        "login": login,
        "user_name": name,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": parsed_details,
        "ip_address": str(ip_address) if ip_address is not None else None,
        "created_at": created_at.isoformat() if created_at else None,
    }


def list_audit(
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    user_id: int | None = None,
) -> tuple[list[dict], int]:
    """Возвращает (items, total) с join на admin_users ради логина."""
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    where = []
    params: list[Any] = []

    if action:
        where.append("l.action = %s")
        params.append(action)

    if user_id is not None:
        where.append("l.user_id = %s")
        params.append(user_id)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM admin_audit_log l {where_sql}",
            tuple(params),
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT
                l.id,
                l.user_id,
                u.login,
                u.name,
                l.action,
                l.entity_type,
                l.entity_id,
                l.details,
                l.ip_address,
                l.created_at
            FROM admin_audit_log l
            LEFT JOIN admin_users u
              ON u.id = l.user_id
            {where_sql}
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params) + (limit, offset),
        ).fetchall()

    return [_row_payload(row) for row in rows], int(total)
