"""Перевод вариантов изображений в WebP и пересборка превью.

Зачем: замер на 100 реальных фото показал, что WebP q80 даёт ~25–29%
меньше байт, чем JPEG q82, при SSIM не хуже. Держим два превью:
card 640px (2× ширины карточки) и thumb 400px (узкие сетки/портфель);
large — 1600px, оригинал при необходимости скачивается отдельно.

Что делает:
- construction_media: ``large_path`` → 1600px WebP,
  ``card_path`` → 640px WebP, ``thumb_path`` → 400px WebP;
- media_variants: ``card``/``thumb`` → 640/400px WebP;
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
    target_size: int | None = None,
    output_path: Path | None = None,
    before_size: int | None = None,
) -> tuple[int, int] | None:
    """Возвращает (было_байт, стало_байт) или None, если пропущено.

    target_size — ограничение длинной стороны (превью = 2× ширины карточки).
    output_path — куда писать WebP (по умолчанию рядом с source).
    Старые thumb 400px не апскейлим: для них источником служит card/large.
    """
    if source.suffix.lower() not in {".jpg", ".jpeg"} or not source.exists():
        return None

    target = output_path or source.with_suffix(".webp")

    original_size = (
        before_size if before_size is not None else source.stat().st_size
    )

    if target.exists() and target_size is None:
        return original_size, target.stat().st_size

    try:
        with Image.open(source) as image:
            if image.mode not in ("RGB", "L"):
                return None

            width, height = image.size
            longest = max(width, height)

            if target_size is not None:
                if longest < target_size:
                    return None

                if longest > target_size:
                    scale = target_size / longest
                    image = image.resize(
                        (
                            max(1, round(width * scale)),
                            max(1, round(height * scale)),
                        ),
                        Image.Resampling.LANCZOS,
                    )

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

    return original_size, len(payload)


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
            SELECT id, media_type, card_path, thumb_path, large_path
            FROM construction_media
            WHERE (card_path LIKE %s OR thumb_path LIKE %s)
              AND (card_path IS NOT NULL OR thumb_path IS NOT NULL)
            ORDER BY id
            """,
            (pattern, pattern),
        ).fetchall()

    pending: list[tuple[int, dict[str, str]]] = []
    converted_files: set[tuple[str, int | None]] = set()

    def existing_source(value: str | None) -> tuple[str, Path] | None:
        if not value:
            return None

        resolved = resolve_construction_path(str(value), active_key)
        source = absolute_path(resolved)

        if source is None or not source.exists():
            return None

        return str(value), source

    for index, (row_id, media_type, card_path, thumb_path, large_path) in enumerate(
        rows
    ):
        if limit is not None and index >= limit:
            break

        stats["rows"] += 1
        quality = WEBP_QUALITY_MAP if str(media_type) == "map" else WEBP_QUALITY_PHOTO
        updates: dict[str, str] = {}

        card = existing_source(card_path)
        large = existing_source(large_path)
        thumb = existing_source(thumb_path)

        # card — 640px WebP (превью ×2); источник — large, иначе card.
        card_source = large or card

        if card and card_source:
            key, source = card_source
            marker = (str(source), 640)
            card_file = absolute_path(
                resolve_construction_path(str(card[0]), active_key)
            )
            output_path = card_file.with_suffix(".webp") if card_file else None

            if marker not in converted_files:
                result = convert_file(
                    source,
                    quality,
                    apply=apply,
                    target_size=640,
                    output_path=output_path,
                    before_size=(
                        card_file.stat().st_size
                        if card_file and card_file.exists()
                        else None
                    ),
                )

                if result is not None:
                    converted_files.add(marker)
                    before, after = result
                    stats["before"] += before
                    stats["after"] += after
                    stats["converted"] += 1

            if output_path and output_path.exists():
                updates["card_path"] = webp_path_for(str(card[0]))

        # large — 1600px WebP (orig 2400px JPEG больше не нужен).
        if large:
            key, source = large
            marker = (str(source), 1600)

            if marker not in converted_files:
                large_file = absolute_path(
                    resolve_construction_path(str(large[0]), active_key)
                )
                output_path = (
                    large_file.with_suffix(".webp") if large_file else None
                )
                result = convert_file(
                    source,
                    82,
                    apply=apply,
                    target_size=1600,
                    output_path=output_path,
                    before_size=(
                        large_file.stat().st_size
                        if large_file and large_file.exists()
                        else None
                    ),
                )

                if result is not None:
                    converted_files.add(marker)
                    before, after = result
                    stats["before"] += before
                    stats["after"] += after
                    stats["converted"] += 1
                    updates["large_path"] = webp_path_for(key)
            elif output_path and output_path.exists():
                updates["large_path"] = webp_path_for(key)

        # thumb — 400px (портфель/узкие сетки); источник — large, иначе card.
        thumb_source = large or card

        if thumb and thumb_source:
            key, source = thumb_source
            marker = (str(source), 400)

            if marker not in converted_files:
                thumb_file = absolute_path(
                    resolve_construction_path(str(thumb[0]), active_key)
                )
                output_path = (
                    thumb_file.with_suffix(".webp") if thumb_file else None
                )

                result = convert_file(
                    source,
                    quality,
                    apply=apply,
                    target_size=400,
                    output_path=output_path,
                    before_size=(
                        thumb_file.stat().st_size
                        if thumb_file and thumb_file.exists()
                        else None
                    ),
                )

                if result is not None:
                    converted_files.add(marker)
                    before, after = result
                    stats["before"] += before
                    stats["after"] += after
                    stats["converted"] += 1
                    updates["thumb_path"] = webp_path_for(str(thumb[0]))
            elif output_path and output_path.exists():
                updates["thumb_path"] = webp_path_for(str(thumb[0]))

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
            SELECT v.id, v.variant, v.storage_path, v.mime_type,
                   m.storage_path AS large_path
            FROM media_variants v
            JOIN media m ON m.id = v.media_id
            WHERE v.variant IN ('card', 'thumb')
              AND v.storage_path IS NOT NULL
            ORDER BY v.id
            """
        ).fetchall()

    pending: list[tuple[int, str, int, int | None, int | None]] = []

    for index, (row_id, variant, storage_path, mime_type, large_path) in enumerate(
        rows
    ):
        if limit is not None and index >= limit:
            break

        stats["rows"] += 1

        if str(mime_type or "").startswith("image/png"):
            continue

        # Крупный источник даёт лучшее качество при пересборке превью.
        source = absolute_path(large_path) or absolute_path(storage_path)

        if source is None or not source.exists():
            stats["missing"] += 1
            continue

        target_size = 400 if str(variant) == "thumb" else 640
        quality = WEBP_QUALITY_PHOTO
        variant_file = absolute_path(storage_path)
        output_path = (
            variant_file.with_suffix(".webp") if variant_file else None
        )
        result = convert_file(
            source,
            quality,
            apply=apply,
            target_size=target_size,
            output_path=output_path,
            before_size=(
                variant_file.stat().st_size
                if variant_file and variant_file.exists()
                else None
            ),
        )

        if result is None:
            continue

        before, after = result
        stats["before"] += before
        stats["after"] += after
        stats["converted"] += 1

        width = height = None

        if apply:
            target = output_path

            try:
                with Image.open(target) as image:
                    width, height = image.size
            except Exception:
                pass

        pending.append((row_id, str(storage_path), after, width, height))

    if apply and pending:
        with get_connection() as conn:
            for row_id, storage_path, file_size, width, height in pending:
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
                        webp_path_for(storage_path),
                        file_size,
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
        f"{name}: строк {stats['rows']}, файлов {stats['converted']}, "
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
