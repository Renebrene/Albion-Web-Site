from __future__ import annotations

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from backend.importer.construction_media_downloader import (
    fetch_public_media,
)
from backend.services.data_service import get_connection


PROJECT_DIR = Path(__file__).resolve().parents[2]
STAGING_ROOT = PROJECT_DIR / "tmp" / "import"

# Публичный API Яндекса отвечает капчей/404 на всплеск параллельных
# запросов, поэтому качаем умеренно — с повторами (см. downloader).
DOWNLOAD_WORKERS = 6

LOG_LOCK = Lock()

MEDIA_TYPES = ("photo", "map")
VARIANT_NAMES = ("large", "card", "thumb")


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


def get_plan_path(staging_path: Path) -> Path:
    return staging_path.parent / "media_plan.json"


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


def load_old_active_media(pg_conn) -> tuple[str | None, dict]:
    """
    Возвращает (old_active_import_key, media) для ACTIVE импорта в PostgreSQL.

    Ключ карты: (surface_hash, media_type).
    Значение: прежний original_url, метаданные и пути preview-файлов.

    Если активного импорта нет или запрос падает —
    вызывающий код переходит в режим полной загрузки.
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, import_key
            FROM construction_imports
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        active = cur.fetchone()

        if not active:
            return None, {}

        active_id, active_key = active

        cur.execute(
            """
            SELECT
                surface_hash,
                media_type,
                original_url,
                original_name,
                mime_type,
                file_size,
                width,
                height,
                large_path,
                card_path,
                thumb_path
            FROM construction_media
            WHERE import_id = %s
              AND surface_hash IS NOT NULL
              AND media_type IN ('photo', 'map')
            """,
            (active_id,),
        )

        media: dict[tuple[str, str], dict] = {}

        for row in cur.fetchall():
            surface_hash = row[0]
            media_type = row[1]

            if not surface_hash or not media_type:
                continue

            media[(surface_hash, media_type)] = {
                "original_url": (
                    str(row[2]).strip()
                    if row[2] is not None
                    else None
                ),
                "original_name": row[3],
                "mime_type": row[4],
                "file_size": row[5],
                "width": row[6],
                "height": row[7],
                "large_path": row[8],
                "card_path": row[9],
                "thumb_path": row[10],
            }

    return active_key, media


def old_previews_exist(record: dict) -> bool:
    for variant in VARIANT_NAMES:
        path = record.get(f"{variant}_path")

        if not path:
            return False

        if not (PROJECT_DIR / path).is_file():
            return False

    return True


def plan_media_tasks(
    tasks: list[dict],
    old_media: dict[tuple[str, str], dict],
) -> tuple[list[dict], int, int]:
    entries: list[dict] = []
    reuse_count = 0
    download_count = 0

    for task in tasks:
        key = (
            task["surface_hash"],
            task["media_type"],
        )
        old = old_media.get(key)

        if (
            old
            and old.get("original_url")
            and old["original_url"] == task["url"]
            and old_previews_exist(old)
        ):
            entries.append(
                {
                    **task,
                    "decision": "reuse",
                    "status": "reuse",
                    "old_paths": {
                        variant: old[f"{variant}_path"]
                        for variant in VARIANT_NAMES
                    },
                    "old_original_url": old.get("original_url"),
                    "file_size": old.get("file_size"),
                    "mime_type": old.get("mime_type"),
                    "width": old.get("width"),
                    "height": old.get("height"),
                    "original_name": old.get(
                        "original_name"
                    ),
                    "source_path": None,
                    "error": None,
                }
            )
            reuse_count += 1
        else:
            entries.append(
                {
                    **task,
                    "decision": "download",
                    "status": "pending",
                    # Даже при решении download сохраняем старые пути:
                    # если загрузка/превью не удастся, preview-стадия
                    # скопирует старый файл в новый импорт (fallback).
                    "old_paths": (
                        {
                            variant: old[f"{variant}_path"]
                            for variant in VARIANT_NAMES
                        }
                        if old
                        else None
                    ),
                    "old_original_url": (
                        old.get("original_url") if old else None
                    ),
                    "file_size": old.get("file_size") if old else None,
                    "mime_type": old.get("mime_type") if old else None,
                    "width": old.get("width") if old else None,
                    "height": old.get("height") if old else None,
                    "original_name": (
                        old.get("original_name")
                        if old
                        else (
                            f'{task["address"]} '
                            f'{task["side"]} '
                            f'{task["media_type"]}'
                        ).strip()
                    ),
                    "source_path": None,
                    "error": None,
                }
            )
            download_count += 1

    return entries, reuse_count, download_count


def safe_stem(value: str) -> str:
    value = str(value or "")
    value = value.replace("/", "_").replace("\\", "_")
    value = "_".join(value.split())
    return value or "construction"


def build_download_path(
    download_root: Path,
    entry: dict,
) -> Path:
    address = safe_stem(entry["address"])

    if entry["media_type"] == "map":
        stem = f"{address}_карта"
    else:
        side = safe_stem(entry["side"])
        stem = f"{address}_{side}" if side else address

    return (
        download_root
        / entry["media_type"]
        / entry["surface_hash"]
        / f"{stem}.source"
    )


def write_log(
    log_path: Path,
    entry: dict,
) -> None:
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    line = json.dumps(
        entry,
        ensure_ascii=False,
    )

    with LOG_LOCK:
        with log_path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(line + "\n")


def download_one(
    entry: dict,
    download_root: Path,
    log_path: Path,
) -> dict:
    destination = build_download_path(
        download_root,
        entry,
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        data = fetch_public_media(entry["url"])

        tmp_path = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        tmp_path.write_bytes(data)
        os.replace(tmp_path, destination)

        entry["status"] = "ok"
        entry["source_path"] = str(
            destination.relative_to(PROJECT_DIR)
        )
        entry["file_size"] = len(data)
        entry["error"] = None

    except Exception as exc:
        entry["status"] = "error"
        entry["error"] = str(exc)

    write_log(log_path, entry)

    return entry


def read_plan(staging_path: Path) -> dict | None:
    plan_path = get_plan_path(staging_path)

    if not plan_path.exists():
        return None

    return json.loads(
        plan_path.read_text(encoding="utf-8"),
    )


def write_plan(staging_path: Path, plan: dict) -> None:
    get_plan_path(staging_path).write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    staging_path = get_latest_staging_db()
    import_key = staging_path.parent.name
    download_root = get_download_root(staging_path)
    log_path = get_log_path(staging_path)

    print("=" * 70)
    print("CONSTRUCTION MEDIA DOWNLOAD (INCREMENTAL)")
    print("=" * 70)
    print(f"Staging DB:       {staging_path}")
    print(f"Import key:       {import_key}")
    print(f"Download root:    {download_root}")
    print(f"Workers:          {DOWNLOAD_WORKERS}")

    conn = open_staging_db(staging_path)

    try:
        tasks = load_media_tasks(conn)
    finally:
        conn.close()

    print(f"Media tasks:      {len(tasks)}")

    # Сравнение со старой ACTIVE версией — опционально.
    # Если PostgreSQL недоступен или активного импорта нет,
    # работаем в режиме полной загрузки (скачиваем всё).
    old_active_import_key = None
    old_media: dict[tuple[str, str], dict] = {}

    try:
        with get_connection() as pg_conn:
            old_active_import_key, old_media = (
                load_old_active_media(pg_conn)
            )
    except Exception as exc:
        print(f"PostgreSQL недоступен: {exc}")
        print("Режим: полная загрузка (без REUSE)")

    if old_media:
        print(
            f"Старый ACTIVE import: {old_active_import_key}"
        )
        print(
            f"Записей construction_media: {len(old_media)}"
        )
    else:
        print("REUSE-источник отсутствует: скачиваем всё")

    entries, reuse_count, download_count = plan_media_tasks(
        tasks,
        old_media,
    )

    print()
    print("MEDIA PLAN")
    print("-" * 70)
    print(f"Решения REUSE:    {reuse_count}")
    print(f"Решения DOWNLOAD: {download_count}")

    if download_count:
        print()
        print("DOWNLOADING...")

        download_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        download_entries = [
            entry
            for entry in entries
            if entry["decision"] == "download"
        ]

        # Файлы, уже скачанные при прерванной попытке того же
        # import-ключа, не скачиваем повторно (запись атомарная).
        already = []

        for entry in download_entries:
            destination = build_download_path(
                download_root,
                entry,
            )

            if (
                destination.is_file()
                and destination.stat().st_size > 0
            ):
                entry["status"] = "ok"
                entry["source_path"] = str(
                    destination.relative_to(PROJECT_DIR)
                )
                entry["file_size"] = destination.stat().st_size
                entry["error"] = None
                already.append(entry)

        download_entries = [
            entry
            for entry in download_entries
            if entry["status"] != "ok"
        ]

        if already:
            print(
                f"Уже скачано ранее:  {len(already)}"
            )

        total_to_download = len(download_entries)
        progress_step = max(1, total_to_download // 20)
        done = 0
        ok_done = 0

        print(
            f"Скачиваем: {total_to_download} "
            f"(пропущено — уже есть: {reuse_count})"
        )

        with ThreadPoolExecutor(
            max_workers=DOWNLOAD_WORKERS,
        ) as executor:
            futures = {
                executor.submit(
                    download_one,
                    entry,
                    download_root,
                    log_path,
                ): entry
                for entry in download_entries
            }

            for future in as_completed(futures):
                entry = futures[future]
                future.result()
                done += 1

                # В прогресс идём только УСПЕШНЫЕ загрузки: иначе счётчик
                # «Скачано» показывал число попыток, а не скачанных файлов.
                if entry.get("status") == "ok":
                    ok_done += 1

                # Живой прогресс: строку «Downloaded: K» парсит админка,
                # поэтому счётчик «Скачано» обновляется по ходу.
                if done % progress_step == 0 or done == total_to_download:
                    print(f"Downloaded: {len(already) + ok_done}")

        ok = len(already) + sum(
            1
            for entry in download_entries
            if entry["status"] == "ok"
        )
        errors = sum(
            1
            for entry in download_entries
            if entry["status"] == "error"
        )

        print()
        print("DOWNLOAD RESULT")
        print("-" * 70)
        print(f"Downloaded:       {ok}")
        print(f"Errors:           {errors}")
        print(f"Log:              {log_path}")

    plan = {
        "import_key": import_key,
        "old_active_import_key": old_active_import_key,
        "mode": (
            "incremental"
            if old_media
            else "full"
        ),
        "entries": entries,
    }

    write_plan(staging_path, plan)
    print(f"Plan:             {get_plan_path(staging_path)}")

    print()
    print("PostgreSQL: НЕ ИЗМЕНЁН")
    print("Previews:   НЕ СОЗДАВАЛИСЬ")


if __name__ == "__main__":
    main()