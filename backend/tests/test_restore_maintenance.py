"""Maintenance-флаг restore создаётся и снимается."""

from __future__ import annotations

from backend.services import import_archive_service as archive


def test_maintenance_flag_roundtrip(tmp_path, monkeypatch):
    flag = tmp_path / "maintenance.json"

    monkeypatch.setattr(archive, "MAINTENANCE_FILE", flag)

    archive._set_maintenance(True, "20260101-000000")
    assert flag.is_file()

    archive._set_maintenance(False)
    assert not flag.exists()
