"""Проверка ссылок медиа БЕЗ скачивания (для dry-run).

Строит тот же медиа-план, что и загрузчик (и сохраняет media_plan.json,
чтобы шаг 5 мог его прочитать), но вместо скачивания файлов проверяет
доступность каждой ссылки: резолв публичной ссылки Яндекс.Диска
(get_direct_link) и HEAD-запрос. Ничего не качает и не пишет в downloads/.

Результат по каждой ссылке: status = "ok" | "error" (+ размер и время).

Запуск: .venv/bin/python -m backend.importer.construction_media_check
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

from backend.services.data_service import get_connection
from backend.importer.construction_media_download import (
    get_latest_staging_db,
    get_log_path,
    load_media_tasks,
    load_old_active_media,
    open_staging_db,
    plan_media_tasks,
    write_plan,
)
from backend.importer.construction_media_downloader import get_direct_link


CHECK_WORKERS = 12
REQUEST_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def check_one(entry: dict) -> dict:
    started = time.time()

    try:
        href = get_direct_link(entry["url"])

        request = Request(
            href,
            method="HEAD",
            headers={"User-Agent": USER_AGENT},
        )

        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            length = response.headers.get("Content-Length")

        entry["status"] = "ok"
        entry["check_size"] = (
            int(length) if length and length.isdigit() else None
        )
        entry["error"] = None

    except Exception as exc:
        entry["status"] = "error"
        entry["check_size"] = None
        entry["error"] = str(exc)[:200]

    entry["check_seconds"] = round(time.time() - started, 2)

    return entry


def main() -> None:
    staging_path = get_latest_staging_db()
    import_key = staging_path.parent.name

    conn = open_staging_db(staging_path)

    try:
        tasks = load_media_tasks(conn)
    finally:
        conn.close()

    print("=" * 70)
    print("CONSTRUCTION MEDIA CHECK (DRY-RUN, без скачивания)")
    print("=" * 70)
    print(f"Import key:       {import_key}")
    print(f"Media tasks:      {len(tasks)}")

    old_active_import_key = None
    old_media: dict = {}

    try:
        with get_connection() as pg_conn:
            old_active_import_key, old_media = load_old_active_media(pg_conn)
    except Exception as exc:
        print(f"PostgreSQL недоступен: {exc}")

    entries, reuse_count, download_count = plan_media_tasks(tasks, old_media)

    # План сохраняем — его читает шаг 5 (staging_to_postgres).
    write_plan(
        staging_path,
        {
            "import_key": import_key,
            "old_active_import_key": old_active_import_key,
            "mode": "incremental" if old_media else "full",
            "entries": entries,
        },
    )

    print()
    print("MEDIA PLAN")
    print("-" * 70)
    print(f"Решения REUSE:    {reuse_count}")
    print(f"Решения DOWNLOAD: {download_count}")

    to_check = [
        entry for entry in entries if entry["decision"] == "download"
    ]

    ok = 0
    broken = 0
    started = time.time()

    if to_check:
        print()
        print(f"ПРОВЕРКА ССЫЛОК (workers={CHECK_WORKERS})...")

        done = 0

        with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as executor:
            futures = [executor.submit(check_one, entry) for entry in to_check]

            for future in as_completed(futures):
                entry = future.result()
                done += 1

                if entry["status"] == "ok":
                    ok += 1
                else:
                    broken += 1

                if done % 50 == 0 or done == len(to_check):
                    print(
                        f"  проверено {done}/{len(to_check)}  "
                        f"ok={ok} битых={broken}"
                    )

    elapsed = time.time() - started

    # Лог проверки — рядом с обычным логом загрузки.
    log_path = get_log_path(staging_path).with_name("media_check.jsonl")

    with log_path.open("w", encoding="utf-8") as log_file:
        for entry in entries:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print()
    print("CHECK RESULT")
    print("-" * 70)
    print(f"REUSE (уже есть локально): {reuse_count}")
    print(f"Проверено ссылок:          {len(to_check)}")
    print(f"  доступно:                {ok}")
    print(f"  битых/недоступно:        {broken}")
    print(f"Время проверки:            {elapsed:.1f}с")
    print(f"Log:                       {log_path}")

    print()
    print("PostgreSQL: НЕ ИЗМЕНЁН (dry-run)")
    print("Медиа:      НЕ СКАЧИВАЛОСЬ")


if __name__ == "__main__":
    main()
