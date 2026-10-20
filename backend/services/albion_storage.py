"""Клиент файлохранилища Albion для внутренних файлов сайта.

Секреты (токен) живут только в ``site_settings`` (ключ ``storage.albion``)
или в переменных окружения и никогда не возвращаются в API и не пишутся в
логи. Публичная схема настроек сайта (``settings_service``) не используется.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from backend.services.data_service import get_connection


logger = logging.getLogger(__name__)

SETTINGS_KEY = "storage.albion"
SETTINGS_DESCRIPTION = "Файлохранилище Albion (JSON, содержит токен)"

VALID_MODES = ("local", "albion")
DEFAULT_MODE = "local"
DEFAULT_TTL_DAYS = 90
MAX_TTL_DAYS = 3650

HTTP_TIMEOUT_SECONDS = 120.0


class AlbionError(Exception):
    """Безопасная ошибка клиента Albion.

    ``status_code`` — HTTP-код, который стоит вернуть админскому API:
    400 для ошибок конфигурации/прав, 503 для сети и ошибок сервера.
    """

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------- config


def _normalize_mode(value) -> str:
    mode = str(value or "").strip().lower() or DEFAULT_MODE

    if mode not in VALID_MODES:
        raise ValueError("Режим хранения должен быть local или albion")

    return mode


def _normalize_url(value) -> str:
    raw = str(value or "").strip()

    if not raw:
        return ""

    parsed = urlparse(raw)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL Albion должен начинаться с http:// или https://")

    if not parsed.netloc or not parsed.hostname:
        raise ValueError("Некорректный URL Albion")

    if parsed.username or parsed.password:
        raise ValueError("URL Albion не должен содержать логин и пароль")

    if parsed.query or parsed.fragment:
        raise ValueError("URL Albion не должен содержать параметры или якорь")

    return raw.rstrip("/")


def _normalize_ttl(value) -> int:
    try:
        ttl = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("TTL должен быть целым числом дней") from exc

    if ttl < 1 or ttl > MAX_TTL_DAYS:
        raise ValueError(f"TTL должен быть от 1 до {MAX_TTL_DAYS} дней")

    return ttl


def _normalize_text(value) -> str:
    return str(value or "").strip()


def _read_stored() -> dict:
    """Сырой JSON из site_settings; при недоступности БД — пустой словарь."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM site_settings WHERE key = %s",
                (SETTINGS_KEY,),
            ).fetchone()
    except Exception:  # noqa: BLE001 — настройки не должны ломать загрузку
        logger.warning("Albion storage: не удалось прочитать настройки")
        return {}

    if not row or not row[0]:
        return {}

    try:
        parsed = json.loads(row[0])
    except (TypeError, ValueError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _write_stored(values: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO site_settings (key, value, value_type, description)
            VALUES (%s, %s, 'json', %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (
                SETTINGS_KEY,
                json.dumps(values, ensure_ascii=False),
                SETTINGS_DESCRIPTION,
            ),
        )


def _pick(stored: dict, key: str, env_name: str, default, normalizer):
    """Значение из site_settings поверх env; некорректное значение игнорируем."""
    candidates = []

    if key in stored and stored.get(key) is not None:
        candidates.append(stored.get(key))

    candidates.append(os.getenv(env_name, default))

    for candidate in candidates:
        try:
            return normalizer(candidate)
        except (TypeError, ValueError):
            continue

    try:
        return normalizer(default)
    except (TypeError, ValueError):
        return normalizer("")


def resolve_config() -> dict:
    """Итоговая конфигурация: site_settings поверх переменных окружения."""
    stored = _read_stored()

    return {
        "mode": _pick(
            stored,
            "mode",
            "ALBION_FILES_MODE",
            DEFAULT_MODE,
            _normalize_mode,
        ),
        "url": _pick(stored, "url", "ALBION_FILES_URL", "", _normalize_url),
        "folder_id": _pick(
            stored,
            "folder_id",
            "ALBION_FILES_FOLDER_ID",
            "",
            _normalize_text,
        ),
        "ttl_days": _pick(
            stored,
            "ttl_days",
            "ALBION_FILES_TTL_DAYS",
            DEFAULT_TTL_DAYS,
            _normalize_ttl,
        ),
        "token": _pick(
            stored,
            "token",
            "ALBION_FILES_TOKEN",
            "",
            _normalize_text,
        ),
    }


def _mask_token(token: str) -> str:
    if not token:
        return ""

    if len(token) <= 4:
        return "****"

    return f"****{token[-4:]}"


def public_config() -> dict:
    """Настройки без секрета — для админского API."""
    config = resolve_config()

    return {
        "mode": config["mode"],
        "url": config["url"],
        "folder_id": config["folder_id"],
        "ttl_days": config["ttl_days"],
        "token_set": bool(config["token"]),
        "token_hint": _mask_token(config["token"]),
    }


def update_config(
    *,
    mode=None,
    url=None,
    folder_id=None,
    ttl_days=None,
    token=None,
) -> dict:
    """Обновляет настройки.

    ``None`` — не менять; ``""`` — очистить значение.
    """
    stored = _read_stored()

    if mode is not None:
        stored["mode"] = _normalize_mode(mode)

    if url is not None:
        stored["url"] = _normalize_url(url)

    if folder_id is not None:
        stored["folder_id"] = _normalize_text(folder_id)

    if ttl_days is not None:
        stored["ttl_days"] = _normalize_ttl(ttl_days)

    if token is not None:
        token_value = _normalize_text(token)

        if token_value:
            stored["token"] = token_value
        else:
            # Явная очистка: пустая строка должна перекрывать env-фолбэк.
            stored["token"] = ""

    _write_stored(stored)

    return public_config()


# ------------------------------------------------------------------ HTTP API


def _client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=False,
        timeout=HTTP_TIMEOUT_SECONDS,
    )


def _require_configured(config: dict) -> None:
    if not config.get("url"):
        raise AlbionError("URL хранилища Albion не задан")

    if not config.get("token"):
        raise AlbionError("Токен Albion не задан")


def _raise_for_status(status_code: int, *, action: str) -> None:
    if status_code in (401, 403):
        detail = (
            "Albion отклонил токен"
            if status_code == 401
            else "У токена нет нужных прав в Albion"
        )
        raise AlbionError(detail)

    if status_code == 413:
        raise AlbionError("Файл превышает лимит хранилища Albion")

    if status_code == 429:
        raise AlbionError("Слишком много запросов к Albion", status_code=503)

    if status_code >= 500:
        raise AlbionError(
            f"Albion вернул ошибку сервера ({status_code}) при {action}",
            status_code=503,
        )

    if status_code >= 400:
        raise AlbionError(f"Albion отклонил запрос ({status_code}) при {action}")


def _json_response(response: httpx.Response, *, action: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise AlbionError(
            "Albion вернул некорректный ответ",
            status_code=503,
        ) from exc

    if not isinstance(payload, dict):
        raise AlbionError(
            "Albion вернул некорректный ответ",
            status_code=503,
        )

    return payload


def _safe_public_url(value) -> str:
    raw = str(value or "").strip()

    if not raw:
        return ""

    parsed = urlparse(raw)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""

    if parsed.username or parsed.password:
        return ""

    return raw


def verify() -> dict:
    """GET /api/v1/integration/verify — проверка токена и прав."""
    config = resolve_config()
    _require_configured(config)

    try:
        with _client() as client:
            response = client.get(
                f"{config['url']}/api/v1/integration/verify",
                headers={"X-API-Key": config["token"]},
            )
    except httpx.TimeoutException as exc:
        raise AlbionError(
            "Истекло время ожидания ответа Albion",
            status_code=503,
        ) from exc
    except httpx.HTTPError as exc:
        raise AlbionError(
            "Не удалось связаться с Albion",
            status_code=503,
        ) from exc

    _raise_for_status(response.status_code, action="проверке")

    payload = _json_response(response, action="проверке")

    return {
        "ok": bool(payload.get("ok", True)),
        "name": str(payload.get("name") or ""),
        "scopes": payload.get("scopes")
            if isinstance(payload.get("scopes"), list)
            else [],
        "folder_id": str(payload.get("folder_id") or ""),
        "base_url": _safe_public_url(payload.get("base_url")),
        "limits": payload.get("limits")
            if isinstance(payload.get("limits"), dict)
            else {},
    }


def upload_file(
    path,
    filename: str,
    *,
    subfolder: str | None = None,
) -> dict:
    """POST /api/v1/integration/upload; возвращает ссылку и ключ объекта."""
    config = resolve_config()
    _require_configured(config)

    local_path = Path(path)

    try:
        file_handle = local_path.open("rb")
    except OSError as exc:
        raise AlbionError("Не удалось прочитать локальный файл") from exc

    data = {
        "display_name": filename,
        "ttl_days": str(config["ttl_days"]),
    }

    if config.get("folder_id"):
        data["folder_id"] = config["folder_id"]

    if subfolder:
        # v1 API привязывает папку к токену; поле передаём для совместимости
        # с серверами, которые поддерживают подпапки.
        data["subfolder"] = str(subfolder).strip("/")

    try:
        with file_handle:
            with _client() as client:
                response = client.post(
                    f"{config['url']}/api/v1/integration/upload",
                    headers={"X-API-Key": config["token"]},
                    data=data,
                    files={
                        "file": (
                            filename,
                            file_handle,
                            "application/octet-stream",
                        )
                    },
                )
    except httpx.TimeoutException as exc:
        raise AlbionError(
            "Истекло время ожидания ответа Albion",
            status_code=503,
        ) from exc
    except httpx.HTTPError as exc:
        raise AlbionError(
            "Не удалось связаться с Albion",
            status_code=503,
        ) from exc

    _raise_for_status(response.status_code, action="загрузке")

    payload = _json_response(response, action="загрузке")
    public_url = _safe_public_url(payload.get("url"))

    if not public_url:
        raise AlbionError(
            "Albion не вернул публичную ссылку",
            status_code=503,
        )

    return {
        "file_id": str(payload.get("file_id") or ""),
        "url": public_url,
        "short_url": _safe_public_url(payload.get("short_url")),
        "object_key": str(payload.get("object_key") or ""),
        "expires_at": payload.get("expires_at"),
    }


def delete_file(file_id: str) -> bool:
    """DELETE /api/v1/integration/files/{file_id}.

    ``False`` — удаление не выполнено (нет права delete, хранилище не
    настроено, файл уже удалён или сеть недоступна). Это не ошибка.
    """
    config = resolve_config()

    if not config.get("url") or not config.get("token") or not file_id:
        return False

    url = (
        f"{config['url']}/api/v1/integration/files/"
        f"{quote(str(file_id), safe='')}"
    )

    try:
        with _client() as client:
            response = client.delete(
                url,
                headers={"X-API-Key": config["token"]},
            )
    except httpx.HTTPError:
        logger.warning(
            "Albion storage: удаление не выполнено (сеть), объект остался"
        )
        return False

    if 200 <= response.status_code < 300:
        return True

    logger.warning(
        "Albion storage: удаление не выполнено (код %s), объект остался",
        response.status_code,
    )
    return False
