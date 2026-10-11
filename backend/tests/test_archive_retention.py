"""Ретенция архивов конструкций: не больше KEEP, по времени, включая ручные."""

from __future__ import annotations

import os

from backend.importer import import_pipeline as ip


def _mk(root, name: str, mtime: float) -> None:
    directory = root / name
    directory.mkdir()
    os.utime(directory, (mtime, mtime))


def test_cleanup_sorts_by_time_not_name(tmp_path):
    # Ручной архив СТАРШЕ всех, но по имени ("manual…") встал бы первым.
    # Правильная ретенция удаляет именно самый старый по времени.
    _mk(tmp_path, "manual-20260101-000000", 500)
    _mk(tmp_path, "20260102-000000", 1000)
    _mk(tmp_path, "20260103-000000", 2000)
    _mk(tmp_path, "20260104-000000", 3000)
    _mk(tmp_path, "20260105-000000", 4000)
    _mk(tmp_path, "20260106-000000", 5000)
    _mk(tmp_path, "_previous", 9999)  # служебный — не считается

    removed = ip.cleanup_old_archives(tmp_path, keep=5)

    assert removed == ["manual-20260101-000000"]
    assert (tmp_path / "_previous").exists()
    assert (tmp_path / "20260106-000000").exists()


def test_cleanup_keeps_recent_manual_archive(tmp_path):
    _mk(tmp_path, "20260101-000000", 1000)
    _mk(tmp_path, "20260102-000000", 2000)
    _mk(tmp_path, "20260103-000000", 3000)
    _mk(tmp_path, "20260104-000000", 4000)
    _mk(tmp_path, "20260105-000000", 5000)
    _mk(tmp_path, "manual-20260106-000000", 6000)  # самый свежий

    removed = ip.cleanup_old_archives(tmp_path, keep=5)

    assert removed == ["20260101-000000"]
    assert (tmp_path / "manual-20260106-000000").exists()


def test_cleanup_noop_when_within_limit(tmp_path):
    _mk(tmp_path, "20260101-000000", 1000)
    _mk(tmp_path, "20260102-000000", 2000)

    assert ip.cleanup_old_archives(tmp_path, keep=5) == []


def test_cleanup_handles_missing_root(tmp_path):
    assert ip.cleanup_old_archives(tmp_path / "nope", keep=5) == []
