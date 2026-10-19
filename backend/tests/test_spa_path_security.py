from __future__ import annotations

from pathlib import Path

from backend.main import _safe_spa_candidate


def test_spa_candidate_stays_inside_root(tmp_path):
    root = tmp_path / "spa"
    root.mkdir()
    asset = root / "assets" / "app.js"
    asset.parent.mkdir()
    asset.write_text("ok", encoding="utf-8")

    assert _safe_spa_candidate(root, "assets/app.js") == asset.resolve()
    assert _safe_spa_candidate(root, "../secret.txt") is None
    assert _safe_spa_candidate(root, "../../.env") is None


def test_spa_candidate_rejects_symlink_escape(tmp_path):
    root = tmp_path / "spa"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (root / "link").symlink_to(outside, target_is_directory=True)

    assert _safe_spa_candidate(root, "link/secret.txt") is None
