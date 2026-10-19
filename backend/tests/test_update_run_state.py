"""PID прогона импорта виден другим worker'ам."""

from __future__ import annotations

import os

from backend.services import update_service as update


def test_run_state_roundtrip_and_cleanup(tmp_path, monkeypatch):
    state_file = tmp_path / "update_run.json"
    stop_file = tmp_path / "update_stop_requested"

    monkeypatch.setattr(update, "RUN_STATE_FILE", state_file)
    monkeypatch.setattr(update, "STOP_FILE", stop_file)

    update._write_run_state(os.getpid(), dry_run=False)

    assert update._external_run_pid() == os.getpid()

    stop_file.write_text("stop", encoding="utf-8")
    assert stop_file.exists()

    update._clear_run_state()
    stop_file.unlink()

    assert not state_file.exists()
    assert update._external_run_pid() is None
