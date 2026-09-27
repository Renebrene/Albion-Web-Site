from __future__ import annotations

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from backend.importer.construction_media_downloader import (
    download_bytes,
    get_direct_link,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
STAGING_ROOT = PROJECT_DIR / "tmp" / "import"

DOWNLOAD_WORKERS = 12

LOG_LOCK = Lock()


def open_staging_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise RuntimeError(f"Staging DB не найден: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_staging_db() -> Path:
    databases = list(STAGING_ROOT.glob("*/staging.sqlite"))

    if not databases:
        raise RuntimeError("Staging DB не найден")

    return max(
        databases,
        key=lambda path: path.stat().st_mtime,
    )


def get_download_root(staging_path: Path) -> Path:
    return staging_path.parent / "downloads"


def get_log_path(staging_path: Path) -> Path:
    return staging_path.parent / "logs" / "media_download.jsonl"


def load_media_tasks(
    conn: sqlite3.Connection,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            s.id AS surface_id,
            s.surface_hash,
            c.address,
            s.side,
            s.photo_url,
            s.map_url
        FROM surfaces s
        JOIN constructions c
          ON c.id = s.construction_id
        WHERE s.is_active = 1
          AND s.surface_hash IS NOT NULL
        ORDER BY s.id
        """
    ).fetchall()

    tasks: list[dict] = []

    for row in rows:
        for media_type, url_column in (
            ("photo", "photo_url"),
            ("map", "map_url"),
        ):
            url = row[url_column]

            if not url or not str(url).strip():
                continue

            tasks.append(
                {
                    "surface_id": row["surface_id"],
                    "surface_hash": row["surface_hash"],
                    "address": row["address"],
                    "side": row["side"],
                    "media_type": media_type,
                    "url": str(url).strip(),
                }
            )

    return tasks


def safe_stem(value: str) -> str:
    value = str(value or "")
    value = value.replace("/", "_").replace("\\", "_")
    value = "_".join(value.split())
    return value or "construction"


def build_download_path(
    download_root: Path,
    task: dict,
) -> Path:
    address = safe_stem(task["address"])

    if task["media_type"] == "map":
        stem = f"{address}_карта"
    else:
        side = safe_stem(task["side"])
        stem = f"{address}_{side}" if side else address

    return (
        download_root
        / task["media_type"]
        / task["surface_hash"]
        / f"{stem}.source"
    )


def write_log(
    log_path: Path,
    result: dict,
) -> None:
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    line = json.dumps(
        result,
        ensure_ascii=False,
    )

    with LOG_LOCK:
        with log_path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(line + "\n")


def download_one(
    task: dict,
    download_root: Path,
    log_path: Path,
) -> dict:
    destination = build_download_path(
        download_root,
        task,
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        href = get_direct_link(task["url"])
        data = download_bytes(href)

        tmp_path = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        tmp_path.write_bytes(data)
        os.replace(tmp_path, destination)

        result = {
            **task,
            "status": "OK",
            "path": str(
                destination.relative_to(PROJECT_DIR)
            ),
            "file_size": len(data),
        }

    except Exception as exc:
        result = {
            **task,
            "status": "ERROR",
            "error": str(exc),
        }

    write_log(log_path, result)

    return result


def main() -> None:
    staging_path = get_latest_staging_db()
    download_root = get_download_root(staging_path)
    log_path = get_log_path(staging_path)

    print("=" * 70)
    print("CONSTRUCTION MEDIA DOWNLOAD")
    print("=" * 70)
    print(f"Staging DB:       {staging_path}")
    print(f"Download root:    {download_root}")
    print(f"Workers:          {DOWNLOAD_WORKERS}")

    conn = open_staging_db(staging_path)

    try:
        tasks = load_media_tasks(conn)
    finally:
        conn.close()

    print(f"Media tasks:      {len(tasks)}")

    download_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict] = []

    with ThreadPoolExecutor(
        max_workers=DOWNLOAD_WORKERS,
    ) as executor:
        futures = [
            executor.submit(
                download_one,
                task,
                download_root,
                log_path,
            )
            for task in tasks
        ]

        for future in as_completed(futures):
            results.append(future.result())

    ok = sum(
        1 for result in results
        if result["status"] == "OK"
    )
    errors = sum(
        1 for result in results
        if result["status"] == "ERROR"
    )

    print()
    print("DOWNLOAD RESULT")
    print("-" * 70)
    print(f"Tasks:            {len(results)}")
    print(f"OK:               {ok}")
    print(f"ERROR:            {errors}")
    print(f"Log:              {log_path}")
    print()
    print("PostgreSQL: НЕ ИЗМЕНЁН")
    print("Previews:   НЕ СОЗДАВАЛИСЬ")


if __name__ == "__main__":
    main()
