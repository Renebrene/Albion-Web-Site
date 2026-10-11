"""Ограничение размера загружаемых файлов при чтении.

Читаем UploadFile порциями и не превышаем лимит: иначе весь файл попадает
в память процесса до проверки размера (потенциальный memory-DoS).
"""
from __future__ import annotations

from fastapi import UploadFile


_CHUNK_SIZE = 1024 * 1024  # 1 МБ

# Абсолютный предел тела запроса (выше лимита видео 100 МБ — на multipart-обвязку).
MAX_REQUEST_BYTES = 120 * 1024 * 1024


class UploadTooLargeError(ValueError):
    """Файл превышает допустимый размер."""


def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Прочитать файл в память, но не больше max_bytes.

    Бросает UploadTooLargeError, если размер превышен (файл не читается дальше).
    """
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = file.file.read(_CHUNK_SIZE)

        if not chunk:
            break

        total += len(chunk)

        if total > max_bytes:
            raise UploadTooLargeError(
                f"Файл слишком большой (максимум {max_bytes // (1024 * 1024)} МБ)"
            )

        chunks.append(chunk)

    return b"".join(chunks)
