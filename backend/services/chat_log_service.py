"""Журнал умного чата: текстовые пары «вопрос–ответ» с датой-временем.

Сохраняется только текст — без медиа и персональных данных. Журнал нужен
для изучения типовых запросов пользователей.

Запись в журнал никогда не должна ломать сам чат: вызывающий код оборачивает
``log_turn`` в try/except.
"""
from __future__ import annotations

from typing import Any


def log_turn(
    *,
    session_id: Any = None,
    chat_key: str | None = None,
    question: str,
    answer: str | None,
) -> None:
    """Сохраняет один обмен «вопрос → ответ»."""
    from backend.services.data_service import get_connection

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO chat_turns (session_id, chat_key, question, answer)
            VALUES (%s, %s, %s, %s)
            """,
            (session_id, chat_key, question, answer),
        )


def _build_filters(
    *,
    date_from: str | None,
    date_to: str | None,
    query: str | None,
    selected_only: bool,
) -> tuple[str, list[Any]]:
    """Собирает WHERE-условие и параметры по фильтрам журнала."""
    conditions: list[str] = []
    params: list[Any] = []

    if date_from:
        conditions.append("created_at >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("created_at <= %s")
        params.append(date_to)

    if query:
        conditions.append("(question ILIKE %s OR answer ILIKE %s)")
        params.extend([f"%{query}%", f"%{query}%"])

    if selected_only:
        conditions.append("selected IS TRUE")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    return where, params


def _row_to_item(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "session_id": str(row[1]) if row[1] else None,
        "chat_key": row[2],
        "question": row[3],
        "answer": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
        "selected": bool(row[6]),
    }


def list_turns(
    *,
    limit: int = 50,
    offset: int = 0,
    date_from: str | None = None,
    date_to: str | None = None,
    query: str | None = None,
    selected_only: bool = False,
) -> dict[str, Any]:
    """Список записей журнала, новые сверху, с фильтрами и пагинацией."""
    from backend.services.data_service import get_connection

    where, params = _build_filters(
        date_from=date_from,
        date_to=date_to,
        query=query,
        selected_only=selected_only,
    )

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM chat_turns {where}",
            params,
        ).fetchone()[0]

        # Общее число отмеченных записей (без учёта фильтров) — для подсказки
        # и решения «выгружать только выбранное или всё».
        selected_total = conn.execute(
            "SELECT COUNT(*) FROM chat_turns WHERE selected IS TRUE"
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT id, session_id, chat_key, question, answer, created_at, selected
            FROM chat_turns
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [_row_to_item(row) for row in rows]

    return {
        "items": items,
        "total": int(total),
        "selected_total": int(selected_total),
    }


def set_selection(*, ids: list[int], selected: bool = True) -> int:
    """Ставит/снимает отметку «выбрано» у переданных записей.

    Возвращает число обновлённых строк.
    """
    if not ids:
        return 0

    from backend.services.data_service import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            """
            UPDATE chat_turns
            SET selected = %s
            WHERE id = ANY(%s)
            RETURNING id
            """,
            (bool(selected), list(ids)),
        ).fetchall()

    return len(rows)


def export_turns(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    query: str | None = None,
    selected_only: bool = False,
) -> list[dict[str, Any]]:
    """Записи для выгрузки в хронологическом порядке (старые сверху).

    Каждая запись — готовый пример «вопрос → ответ» в формате messages,
    пригодном и для анализа, и для последующего дообучения моделей.
    """
    from backend.services.data_service import get_connection

    where, params = _build_filters(
        date_from=date_from,
        date_to=date_to,
        query=query,
        selected_only=selected_only,
    )

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, session_id, chat_key, question, answer, created_at, selected
            FROM chat_turns
            {where}
            ORDER BY created_at ASC, id ASC
            """,
            params,
        ).fetchall()

    result: list[dict[str, Any]] = []

    for row in rows:
        item = _row_to_item(row)
        messages = [{"role": "user", "content": item["question"]}]

        if item["answer"]:
            messages.append({"role": "assistant", "content": item["answer"]})

        result.append(
            {
                "id": item["id"],
                "created_at": item["created_at"],
                "session_id": item["session_id"],
                "chat_key": item["chat_key"],
                "question": item["question"],
                "answer": item["answer"],
                "messages": messages,
            }
        )

    return result
