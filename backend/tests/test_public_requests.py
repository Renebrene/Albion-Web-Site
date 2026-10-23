"""Проверка контактов в публичной заявке (POST /api/requests).

Валидация выполняется до записи в БД, поэтому проверяем её напрямую:
нормализацию телефона, e-mail и обязательность хотя бы одного контакта.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException

from backend.api.public_requests import (
    PublicRequestPayload,
    create_public_request,
    normalize_email,
    normalize_phone,
)


def test_phone_accepts_any_input_format():
    expected = "+7 (900) 123-45-67"

    for raw in (
        "+7 900 123-45-67",
        "+79001234567",
        "8 900 123 45 67",
        "8(900)123-45-67",
        "9001234567",
        " 8 (900) 123-45-67 ",
    ):
        assert normalize_phone(raw) == expected


def test_phone_rejects_incomplete_and_foreign_numbers():
    for raw in ("", "123456", "+7 900", "+1 202 555 01 99", "abc"):
        assert normalize_phone(raw) == ""


def test_email_is_normalized_and_validated():
    assert normalize_email("  User@Example.RU ") == "user@example.ru"

    for raw in ("", "abc", "a@b", "a b@c.ru", "a@b.c"):
        assert normalize_email(raw) == ""


def _request(**kwargs):
    return create_public_request(PublicRequestPayload(**kwargs), BackgroundTasks())


def test_name_is_required():
    with pytest.raises(HTTPException) as exc:
        _request(name=" ", phone="+7 900 123-45-67")

    assert exc.value.status_code == 400
    assert "имя" in exc.value.detail.lower()


def test_contact_is_required():
    with pytest.raises(HTTPException) as exc:
        _request(name="Иван")

    assert exc.value.status_code == 400
    assert "телефон или e-mail" in exc.value.detail.lower()


def test_broken_phone_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _request(name="Иван", phone="12345")

    assert exc.value.status_code == 400
    assert "телефон" in exc.value.detail.lower()


def test_broken_email_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _request(name="Иван", email="ivan@")

    assert exc.value.status_code == 400
    assert "e-mail" in exc.value.detail.lower()
