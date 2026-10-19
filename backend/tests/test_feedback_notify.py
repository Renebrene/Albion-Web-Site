"""Обратная связь уходит на адрес из настроек админки."""

from __future__ import annotations

from backend.services import requests_service


class _FakeSMTP:
    sent = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def starttls(self) -> None:
        pass

    def login(self, user: str, password: str) -> None:
        pass

    def send_message(self, message) -> None:
        _FakeSMTP.sent.append(message)


def test_feedback_notification_uses_admin_recipient(monkeypatch):
    monkeypatch.setattr(
        requests_service,
        "get_notify_settings",
        lambda: {
            "enabled": True,
            "email": "manager@example.com",
        },
    )
    monkeypatch.setattr(requests_service, "smtp_configured", lambda: True)
    monkeypatch.setattr(requests_service.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.sent = []

    result = requests_service.notify_new_feedback(
        {
            "name": "Иван",
            "phone": "+7 999 000-00-00",
            "message": "Нужен щит",
            "created_at": "2026-10-20T12:00:00",
        }
    )

    assert result["sent"] is True
    assert result["to"] == ["manager@example.com"]
    assert len(_FakeSMTP.sent) == 1

    message = _FakeSMTP.sent[0]
    assert message["To"] == "manager@example.com"
    assert "Нужен щит" in message.get_content()
