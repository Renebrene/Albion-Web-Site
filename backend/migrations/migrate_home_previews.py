"""Временный код для живого предпросмотра баннера в админке.

Таблица хранит несохранённый код редактора, чтобы предпросмотр видели все
воркеры uvicorn. В БД слайда код попадает только по кнопке «Сохранить».
"""
from __future__ import annotations

import logging

from backend.services.data_service import get_connection

logger = logging.getLogger(__name__)


def ensure_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS home_slide_previews (
                slide_id BIGINT PRIMARY KEY,
                code TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


if __name__ == "__main__":
    ensure_table()
    logger.info("Таблица home_slide_previews готова")
