"""Перевод карточных вариантов (card/thumb) в WebP.

Зачем: замер на 100 реальных фото показал, что WebP q78–82 даёт
~27–29% меньше байт, чем JPEG q82, при SSIM не хуже. Large оставляем
JPEG — он нужен для печати/экспорта и совместимости.

Что делает:
- для ``construction_media`` конвертирует ``card_path`` и ``thumb_path``;
- для ``media_variants`` конвертирует варианты ``card`` и ``thumb``;
- рядом с исходным JPEG создаёт ``.webp`` и обновляет путь/MIME/размер в БД;
- старые JPEG не удаляет (ссылки из старых портфелей продолжают работать).

По умолчанию — dry-run. Запись в БД и файлы только с ``--apply``.

Примеры:

    .venv/bin/python -m backend.migrations.convert_card_variants_to_webp
    .venv/bin/python -m backend.migrations.convert_card_variants_to_webp --apply
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.services.data_service import PROJECT_DIR, get_connection
from backend.services.media_paths import fetch_active_import_key, resolve_import_url
from backend.services.media_service import STORAGE_ROOT

WEBP_QUALITY_PHOTO = 80
WEBP_QUALITY_MAP = 82


def absolute_path(value: str | None) -> Path | None:
    text = str(value or "").strip()

    if not text:
        return None

    if text.startswith("/storage/"):
        return PROJECT_DIR / text.lstrip("/")

    if text.startswith("/"):
        return Path(text)

    if text.startswith("storage/"):
        return PROJECT_DIR / text

    return STORAGE_ROOT / text


def webp_path_for(value: str) -> str:
    return str(Path(value).with_suffix(".webp"))


def resolve_construction_path(value: str, active_key: str | None) -> str:
    """Путь из БД может быть и `storage/...`, и `/storage/...`."""
    text = str(value or "").strip()

    if text.startswith("storage/"):
        text = f"/{text}"

    return resolve_import_url(text, active_key)


def convert_file(
    source: Path,
    quality: int,
    *,
    apply: bool,
) -> tuple[int, int] | None:
    """Возвращает (было_байт, стало_байт) или None, если пропущено."""
    if source.suffix.lower() not in {".jpg", ".jpeg"} or not source.exists():
        return None

    target = source.with_suffix(".webp")

    if target.exists():
        return source.stat().st_size, target.stat().st_size

    try:
        with Image.open(source) as image:
            if image.mode not in ("RGB", "L"):
                return None

            data = BytesIO()
            image.save(
                data,
                format="WEBP",
                quality=quality,
                method=6,
            )
            payload = data.getvalue()
    except Exception:
        return None

    if apply:
        tmp = target.with_suffix(".webp.tmp")
        tmp.write_bytes(payload)
        tmp.replace(target)

    return source.stat().st_size, len(payload)


def convert_construction_media(*, apply: bool, limit: int | None) -> dict:
    stats = {
        "rows": 0,
        "unique_files": 0,
        "converted": 0,
        "missing": 0,
        "before": 0,
        "after": 0,
    }

    # Читаем только активный импорт: старые папки удалены, их строки
    # в БД всё равно не отдаются сайтом.
    with get_connection() as conn:
        active_key = fetch_active_import_key(conn)
        pattern = f"%{active_key}%" if active_key else "%"

        rows = conn.execute(
            """
            SELECT id, media_type, card_path, thumb_path
            FROM construction_media
            WHERE (card_path LIKE %s OR thumb_path LIKE %s)
              AND (card_path IS NOT NULL OR thumb_path IS NOT NULL)
            ORDER BY id
            """,
            (pattern, pattern),
        ).fetchall()

    pending: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    converted_paths: dict[str, str] = {}
    converted_files: set[str] = set()

    for index, (row_id, media_type, card_path, thumb_path) in enumerate(rows):
        if limit is not None and index >= limit:
            break

        stats["rows"] += 1
        quality = WEBP_QUALITY_MAP if str(media_type) == "map" else WEBP_QUALITY_PHOTO
        updates: dict[str, str] = {}

        for column, value in (("card_path", card_path), ("thumb_path", thumb_path)):
            if not value:
                continue

            key = str(value)

            if key in converted_paths:
                updates[column] = converted_paths[key]
                continue

            if key in seen:
                continue

            seen.add(key)
            stats["unique_files"] += 1

            # Старые импорты удалены с диска: путь из БД может
            # указывать на несуществующую папку. Активный ключ
            # подставляет текущую папку с тем же именем файла.
            resolved = resolve_construction_path(key, active_key)
            source = absolute_path(resolved)

            if source is None or not source.exists():
                stats["missing"] += 1
                continue

            source_key = str(source)

            if source_key in converted_files:
                converted_paths[key] = webp_path_for(key)
                updates[column] = converted_paths[key]
                continue

            result = convert_file(source, quality, apply=apply)

            if result is None:
                continue

            converted_files.add(source_key)
            before, after = result
            stats["before"] += before
            stats["after"] += after
            stats["converted"] += 1
            converted_paths[key] = webp_path_for(key)
            updates[column] = converted_paths[key]

        if updates:
            pending.append((row_id, updates))

    if apply and pending:
        with get_connection() as conn:
            for row_id, updates in pending:
                sets = ", ".join(f"{column} = %s" for column in updates)
                conn.execute(
                    f"UPDATE construction_media SET {sets} WHERE id = %s",
                    (*updates.values(), row_id),
                )

    return stats


def convert_media_variants(*, apply: bool, limit: int | None) -> dict:
    stats = {
        "rows": 0,
        "converted": 0,
        "missing": 0,
        "before": 0,
        "after": 0,
    }

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, variant, storage_path, mime_type
            FROM media_variants
            WHERE variant IN ('card', 'thumb')
              AND storage_path IS NOT NULL
            ORDER BY id
            """
        ).fetchall()

        for index, (row_id, variant, storage_path, mime_type) in enumerate(rows):
            if limit is not None and index >= limit:
                break

            stats["rows"] += 1

            if str(mime_type or "").startswith("image/png"):
                continue

            source = absolute_path(storage_path)

            if source is None or not source.exists():
                stats["missing"] += 1
                continue

            result = convert_file(source, WEBP_QUALITY_PHOTO, apply=apply)

            if result is None:
                continue

            before, after = result
            stats["before"] += before
            stats["after"] += after
            stats["converted"] += 1

            if apply:
                target = source.with_suffix(".webp")
                width = height = None

                try:
                    with Image.open(target) as image:
                        width, height = image.size
                except Exception:
                    pass

                conn.execute(
                    """
                    UPDATE media_variants
                    SET storage_path = %s,
                        mime_type = 'image/webp',
                        file_size = %s,
                        width = %s,
                        height = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        webp_path_for(str(storage_path)),
                        after,
                        width,
                        height,
                        row_id,
                    ),
                )

    return stats


def report(name: str, stats: dict) -> None:
    before = stats.get("before", 0)
    after = stats.get("after", 0)
    saved = before - after
    percent = (saved / before * 100) if before else 0

    print(
        f"{name}: строк {stats['rows']}, файлов {stats.get('unique_files', stats.get('converted', 0))}, "
        f"сконвертировано {stats['converted']}, нет файла {stats['missing']}"
    )
    print(
        f"  байты: {before / 1024 / 1024:.1f} MB → {after / 1024 / 1024:.1f} MB "
        f"(экономия {saved / 1024 / 1024:.1f} MB, {percent:.1f}%)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="записать WebP-файлы и обновить БД (без флага — только расчёт)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="ограничить число строк (для проверки)",
    )
    args = parser.parse_args()

    print(f"Режим: {'APPLY' if args.apply else 'DRY-RUN'}")

    report(
        "construction_media",
        convert_construction_media(apply=args.apply, limit=args.limit),
    )
    report(
        "media_variants",
        convert_media_variants(apply=args.apply, limit=args.limit),
    )


if __name__ == "__main__":
    main()
