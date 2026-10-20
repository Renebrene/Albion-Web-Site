"""Albion: конфигурация, сериализация URL, dual-write и проверка связи.

Тесты не ходят в сеть: HTTP-клиент и загрузка подменяются. Тест миграции
использует PostgreSQL, но выполняет DDL в транзакции и откатывает её.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from backend.migrations import migrate_media_external_storage as migration
from backend.services import albion_storage, media_service, storage_backend
from backend.tests.conftest import requires_db


# --------------------------------------------------------------------- helpers


def _png_bytes(size=(1200, 800)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format="PNG")
    return output.getvalue()


def _albion_config(**overrides) -> dict:
    config = {
        "mode": "albion",
        "url": "https://files.example.ru",
        "folder_id": "folder-1",
        "ttl_days": 90,
        "token": "secret-token",
    }
    config.update(overrides)
    return config


class _FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self, row=None):
        self.cursor_obj = _FakeCursor(row)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return self.cursor_obj


class _RecordingCursor:
    def __init__(self, updates):
        self.updates = updates

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.updates.append((sql, params))


class _RecordingConnection:
    def __init__(self):
        self.updates = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return _RecordingCursor(self.updates)


class _ScriptedCursor:
    """Отдаёт ответы в порядке, соответствующем delete_media."""

    def __init__(self):
        self.statements = []
        self._queue = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        normalized = " ".join(sql.split()).lower()

        if "from media where" in normalized:
            self._queue.append(
                (
                    "one",
                    (1, "media/file.jpg", "media/preview.webp", "albion", "ext-1"),
                )
            )
        elif "from media_variants" in normalized:
            self._queue.append(
                ("all", [("media/file-card.jpg", "albion", "ext-2")])
            )
        elif "from news_media" in normalized or "from page_block_media" in normalized:
            self._queue.append(("one", None))
        else:
            self._queue.append(("none", None))

    def _take(self, kind):
        while self._queue:
            item_kind, value = self._queue.pop(0)
            if item_kind == kind:
                return value
        return None

    def fetchone(self):
        return self._take("one")

    def fetchall(self):
        value = self._take("all")
        return value if value is not None else []


class _ScriptedConnection:
    def __init__(self):
        self.cur = _ScriptedCursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return self.cur


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        if self.error is not None:
            raise self.error
        return self.response


# ---------------------------------------------------------------- migration


def test_migration_sql_is_additive_and_idempotent():
    for table in ("media", "media_variants"):
        statement = migration.column_sql(table)

        assert "ADD COLUMN IF NOT EXISTS storage_backend" in statement
        assert "ADD COLUMN IF NOT EXISTS external_url" in statement
        assert "ADD COLUMN IF NOT EXISTS external_key" in statement

    assert migration.CHECK_CONSTRAINTS == {
        "media": "media_storage_backend_check",
        "media_variants": "media_variants_storage_backend_check",
    }


@requires_db
def test_migration_is_idempotent_in_database():
    """Два прогона подряд проходят; изменения откатываются."""
    from backend.services.data_service import get_raw_connection

    with get_raw_connection() as conn:
        try:
            migration.apply(conn)
            migration.apply(conn)
        finally:
            conn.rollback()


# ------------------------------------------------------------------- config


def test_resolve_config_uses_env_fallback(monkeypatch):
    monkeypatch.setattr(albion_storage, "_read_stored", lambda: {})
    monkeypatch.setenv("ALBION_FILES_MODE", "albion")
    monkeypatch.setenv("ALBION_FILES_URL", "https://files.example.ru/")
    monkeypatch.setenv("ALBION_FILES_TOKEN", "env-token")
    monkeypatch.setenv("ALBION_FILES_FOLDER_ID", "env-folder")
    monkeypatch.setenv("ALBION_FILES_TTL_DAYS", "30")

    config = albion_storage.resolve_config()

    assert config == {
        "mode": "albion",
        "url": "https://files.example.ru",
        "folder_id": "env-folder",
        "ttl_days": 30,
        "token": "env-token",
    }


def test_stored_config_overrides_env(monkeypatch):
    monkeypatch.setattr(
        albion_storage,
        "_read_stored",
        lambda: {"mode": "local", "url": "https://stored.example.ru"},
    )
    monkeypatch.setenv("ALBION_FILES_MODE", "albion")
    monkeypatch.setenv("ALBION_FILES_URL", "https://env.example.ru")

    config = albion_storage.resolve_config()

    assert config["mode"] == "local"
    assert config["url"] == "https://stored.example.ru"


def test_update_config_none_keeps_and_empty_clears(monkeypatch):
    state = {
        "mode": "albion",
        "url": "https://files.example.ru",
        "folder_id": "folder-1",
        "ttl_days": 90,
        "token": "secret-token",
    }

    monkeypatch.setattr(albion_storage, "_read_stored", lambda: dict(state))

    def fake_write(values):
        state.clear()
        state.update(values)

    monkeypatch.setattr(albion_storage, "_write_stored", fake_write)
    monkeypatch.delenv("ALBION_FILES_TOKEN", raising=False)

    albion_storage.update_config(
        mode=None,
        url=None,
        folder_id=None,
        ttl_days=None,
        token=None,
    )
    assert state["token"] == "secret-token"
    assert state["mode"] == "albion"

    public = albion_storage.update_config(token="")

    assert state["token"] == ""
    assert public["token_set"] is False
    assert public["token_hint"] == ""
    assert "secret-token" not in json.dumps(public)


def test_update_config_masks_token_and_validates(monkeypatch):
    state: dict = {}
    monkeypatch.setattr(albion_storage, "_read_stored", lambda: dict(state))

    def fake_write(values):
        state.clear()
        state.update(values)

    monkeypatch.setattr(albion_storage, "_write_stored", fake_write)

    public = albion_storage.update_config(
        mode="albion",
        url="https://files.example.ru/",
        folder_id="folder-1",
        ttl_days=45,
        token="abcdefgh",
    )

    assert public["mode"] == "albion"
    assert public["url"] == "https://files.example.ru"
    assert public["ttl_days"] == 45
    assert public["token_set"] is True
    assert public["token_hint"] == "****efgh"
    assert "abcdefgh" not in json.dumps(public)

    with pytest.raises(ValueError):
        albion_storage.update_config(mode="remote")

    with pytest.raises(ValueError):
        albion_storage.update_config(url="ftp://files.example.ru")

    with pytest.raises(ValueError):
        albion_storage.update_config(url="https://user:pass@files.example.ru")

    with pytest.raises(ValueError):
        albion_storage.update_config(ttl_days=0)


# ---------------------------------------------------------- URL serialization


def test_public_url_prefers_external_and_falls_back_to_local():
    assert (
        storage_backend.public_url({"storage_path": "media/a.jpg"})
        == "/storage/media/a.jpg"
    )
    assert (
        storage_backend.public_url(
            {
                "storage_path": "media/a.jpg",
                "external_url": "https://files.example.ru/a",
            }
        )
        == "https://files.example.ru/a"
    )
    assert (
        storage_backend.public_url(
            {
                "storage_path": "media/a.jpg",
                "external_url": "javascript:alert(1)",
            }
        )
        == "/storage/media/a.jpg"
    )
    assert storage_backend.public_url({}) == ""


def test_insert_media_serializes_url():
    now = datetime.now(timezone.utc)
    local_row = (
        1,
        str(uuid4()),
        "a.jpg",
        "media/a.jpg",
        "image/jpeg",
        10,
        100,
        100,
        None,
        None,
        [1],
        None,
        now,
        now,
        "local",
        None,
        None,
    )

    result = media_service._insert_media(
        _FakeConnection(local_row),
        media_uuid=uuid4(),
        original_name="a.jpg",
        storage_path=Path("media/a.jpg"),
        mime_type="image/jpeg",
        file_size=10,
        width=100,
        height=100,
        alt=None,
        title=None,
        category_id=[1],
    )
    assert result["url"] == "/storage/media/a.jpg"

    external_row = list(local_row)
    external_row[3] = "media/b.jpg"
    external_row[14] = "albion"
    external_row[15] = "https://files.example.ru/b"
    external_row[16] = "file-b"

    result = media_service._insert_media(
        _FakeConnection(tuple(external_row)),
        media_uuid=uuid4(),
        original_name="b.jpg",
        storage_path=Path("media/b.jpg"),
        mime_type="image/jpeg",
        file_size=10,
        width=100,
        height=100,
        alt=None,
        title=None,
        category_id=[1],
    )
    assert result["storage_backend"] == "albion"
    assert result["url"] == "https://files.example.ru/b"


def test_insert_variant_serializes_url():
    now_row = (7, "albion", "https://files.example.ru/card", "file-card")

    result = media_service._insert_variant(
        _FakeConnection(now_row),
        media_id=1,
        variant="card",
        storage_path=Path("media/a-card.jpg"),
        mime_type="image/jpeg",
        file_size=10,
        width=100,
        height=100,
    )

    assert result["storage_backend"] == "albion"
    assert result["url"] == "https://files.example.ru/card"


# --------------------------------------------------------------- dual write


def _patch_media_inserts(monkeypatch):
    connection = _RecordingConnection()
    monkeypatch.setattr(media_service, "get_connection", lambda: connection)
    monkeypatch.setattr(media_service, "_normalize_category_ids", lambda ids: [1])

    next_variant_id = {"value": 10}

    def fake_insert_media(conn, **kwargs):
        path = str(kwargs["storage_path"])
        return {
            "id": 1,
            "uuid": str(uuid4()),
            "original_name": kwargs["original_name"],
            "storage_path": path,
            "variants": [],
            "storage_backend": "local",
            "external_url": None,
            "external_key": None,
            "url": f"/storage/{path}",
        }

    def fake_insert_variant(conn, **kwargs):
        next_variant_id["value"] += 1
        path = str(kwargs["storage_path"])
        return {
            "id": next_variant_id["value"],
            "variant": kwargs["variant"],
            "storage_path": path,
            "storage_backend": "local",
            "external_url": None,
            "external_key": None,
            "url": f"/storage/{path}",
        }

    monkeypatch.setattr(media_service, "_insert_media", fake_insert_media)
    monkeypatch.setattr(media_service, "_insert_variant", fake_insert_variant)

    return connection


def test_save_image_uploads_all_objects_in_albion_mode(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(media_service, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        albion_storage,
        "resolve_config",
        lambda: _albion_config(),
    )

    uploaded = []

    def fake_upload(path, filename, *, subfolder=None):
        uploaded.append((Path(path).name, subfolder))
        return {
            "file_id": f"id-{filename}",
            "url": f"https://files.example.ru/{filename}",
            "object_key": f"site-media/{filename}",
        }

    monkeypatch.setattr(albion_storage, "upload_file", fake_upload)
    connection = _patch_media_inserts(monkeypatch)

    result = media_service.save_image(_png_bytes(), "photo.png")
    main_path = tmp_path / result["storage_path"]

    assert main_path.exists()
    assert result["storage_backend"] == "albion"
    assert result["url"] == (
        f"https://files.example.ru/{Path(result['storage_path']).name}"
    )
    assert len(uploaded) == 3
    assert {name for name, _ in uploaded} == {
        main_path.name,
        *(Path(v["storage_path"]).name for v in result["variants"]),
    }

    for variant in result["variants"]:
        assert variant["storage_backend"] == "albion"
        assert variant["url"].startswith("https://files.example.ru/")
        assert (tmp_path / variant["storage_path"]).exists()

    assert len(connection.updates) == 3
    sql = " ".join(statement for statement, _ in connection.updates)

    assert "UPDATE media" in sql
    assert "UPDATE media_variants" in sql


def test_save_image_keeps_local_copy_when_albion_fails(
    monkeypatch,
    tmp_path,
    caplog,
):
    monkeypatch.setattr(media_service, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        albion_storage,
        "resolve_config",
        lambda: _albion_config(),
    )

    def failing_upload(*args, **kwargs):
        raise RuntimeError("Albion недоступен")

    monkeypatch.setattr(albion_storage, "upload_file", failing_upload)
    connection = _patch_media_inserts(monkeypatch)
    caplog.set_level(logging.WARNING)

    result = media_service.save_image(_png_bytes(), "photo.png")

    assert result["storage_backend"] == "local"
    assert result["url"].startswith("/storage/")
    assert all(
        variant["storage_backend"] == "local"
        for variant in result["variants"]
    )
    assert (tmp_path / result["storage_path"]).exists()
    for variant in result["variants"]:
        assert (tmp_path / variant["storage_path"]).exists()

    assert connection.updates == []
    assert "не удалось загрузить" in caplog.text


# --------------------------------------------------------------- delete flow


def test_delete_media_removes_local_files_and_tolerates_album_failure(
    monkeypatch,
    tmp_path,
    caplog,
):
    monkeypatch.setattr(media_service, "STORAGE_ROOT", tmp_path)
    for relative in (
        "media/file.jpg",
        "media/preview.webp",
        "media/file-card.jpg",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    connection = _ScriptedConnection()
    monkeypatch.setattr(media_service, "get_connection", lambda: connection)

    deleted_keys = []

    def fake_delete(file_id):
        deleted_keys.append(file_id)
        return False

    monkeypatch.setattr(albion_storage, "delete_file", fake_delete)
    caplog.set_level(logging.WARNING)

    result = media_service.delete_media(1)

    assert result == {"id": 1, "deleted": True}
    assert deleted_keys == ["ext-1", "ext-2"]

    for relative in (
        "media/file.jpg",
        "media/preview.webp",
        "media/file-card.jpg",
    ):
        assert not (tmp_path / relative).exists()

    assert "остался в Albion" in caplog.text


# ------------------------------------------------------------------- verify


def _install_fake_client(monkeypatch, response=None, error=None):
    client = _FakeClient(response=response, error=error)

    def factory(**kwargs):
        client.kwargs = kwargs
        return client

    monkeypatch.setattr(albion_storage.httpx, "Client", factory)
    monkeypatch.setattr(
        albion_storage,
        "resolve_config",
        lambda: _albion_config(),
    )

    return client


def test_verify_success(monkeypatch):
    client = _install_fake_client(
        monkeypatch,
        response=_FakeResponse(
            200,
            {
                "ok": True,
                "name": "Демо-сайт",
                "scopes": ["upload", "delete"],
                "folder_id": "folder-1",
                "base_url": "https://files.example.ru",
                "limits": {"max_upload_gb": 50},
            },
        ),
    )

    result = albion_storage.verify()

    assert result["ok"] is True
    assert result["name"] == "Демо-сайт"
    assert result["scopes"] == ["upload", "delete"]
    assert client.calls[0][1]["X-API-Key"] == "secret-token"
    assert client.kwargs["follow_redirects"] is False


def test_verify_rejects_bad_token_without_leaking_it(monkeypatch):
    _install_fake_client(
        monkeypatch,
        response=_FakeResponse(401, {"error": "unauthorized"}),
    )

    with pytest.raises(albion_storage.AlbionError) as exc_info:
        albion_storage.verify()

    assert exc_info.value.status_code == 400
    assert "токен" in str(exc_info.value).lower()
    assert "secret-token" not in str(exc_info.value)


def test_verify_timeout_is_service_unavailable(monkeypatch):
    _install_fake_client(
        monkeypatch,
        error=httpx.TimeoutException("timeout"),
    )

    with pytest.raises(albion_storage.AlbionError) as exc_info:
        albion_storage.verify()

    assert exc_info.value.status_code == 503
    assert "время" in str(exc_info.value).lower()


def test_verify_server_error_is_service_unavailable(monkeypatch):
    _install_fake_client(
        monkeypatch,
        response=_FakeResponse(500, {"error": "boom"}),
    )

    with pytest.raises(albion_storage.AlbionError) as exc_info:
        albion_storage.verify()

    assert exc_info.value.status_code == 503


# ------------------------------------------------------------- admin API


def _admin_client():
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.services.auth_api import require_admin

    app.dependency_overrides[require_admin] = lambda: {
        "user": {"role": "admin"}
    }

    return TestClient(app)


def test_admin_integration_requires_admin():
    from fastapi.testclient import TestClient

    from backend.main import app

    response = TestClient(app).get("/api/admin/integration/albion")

    assert response.status_code == 401


def test_admin_integration_get_put_and_verify(monkeypatch):
    from backend.main import app
    from backend.services.auth_api import require_admin

    client = _admin_client()
    calls = []

    try:
        monkeypatch.setattr(
            albion_storage,
            "public_config",
            lambda: {
                "mode": "local",
                "url": "",
                "folder_id": "",
                "ttl_days": 90,
                "token_set": False,
                "token_hint": "",
            },
        )
        monkeypatch.setattr(
            albion_storage,
            "update_config",
            lambda **kwargs: (
                calls.append(kwargs)
                or {
                    "mode": "albion",
                    "url": "https://files.example.ru",
                    "folder_id": "folder-1",
                    "ttl_days": 30,
                    "token_set": True,
                    "token_hint": "****oken",
                }
            ),
        )
        monkeypatch.setattr(
            albion_storage,
            "verify",
            lambda: {"ok": True, "name": "Демо-сайт", "scopes": ["upload"]},
        )

        response = client.get("/api/admin/integration/albion")
        assert response.status_code == 200
        assert response.json()["mode"] == "local"

        response = client.put(
            "/api/admin/integration/albion",
            json={
                "mode": "albion",
                "url": "https://files.example.ru",
                "folder_id": "folder-1",
                "ttl_days": 30,
                "token": "secret-token",
            },
        )
        assert response.status_code == 200
        assert response.json()["mode"] == "albion"
        assert calls[0]["token"] == "secret-token"

        response = client.post("/api/admin/integration/albion/verify")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["name"] == "Демо-сайт"

        def failing_verify():
            raise albion_storage.AlbionError(
                "Истекло время ожидания ответа Albion",
                status_code=503,
            )

        monkeypatch.setattr(albion_storage, "verify", failing_verify)
        response = client.post("/api/admin/integration/albion/verify")
        assert response.status_code == 503
        assert response.json()["detail"] == "Истекло время ожидания ответа Albion"
    finally:
        app.dependency_overrides.pop(require_admin, None)
