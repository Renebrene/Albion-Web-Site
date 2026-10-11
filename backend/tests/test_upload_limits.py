"""Ограничение размера загружаемых файлов (защита от memory-DoS)."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile

from backend.services.upload_limits import (
    UploadTooLargeError,
    read_upload_limited,
)


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="test.bin")


def test_read_limited_returns_content_within_limit():
    data = b"a" * 10

    assert read_upload_limited(_upload(data), 100) == data


def test_read_limited_rejects_oversized_file():
    data = b"a" * (2 * 1024 * 1024)  # 2 МБ

    with pytest.raises(UploadTooLargeError):
        read_upload_limited(_upload(data), 1024 * 1024)  # лимит 1 МБ


def test_read_limited_accepts_exact_limit():
    data = b"a" * 1024

    assert read_upload_limited(_upload(data), 1024) == data
