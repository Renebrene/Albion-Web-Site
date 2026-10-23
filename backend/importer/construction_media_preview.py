from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from zipfile import ZipFile

from backend.services.media_service import (
    MAX_PIXELS,
    _build_static_variants,
    _detect_format,
    _open_image,
    has_transparency,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
STAGING_ROOT = PROJECT_DIR / "tmp" / "import"
STORAGE_ROOT = PROJECT_DIR / "storage" / "constructions" / "imports"

VARIANT_NAMES = ("large", "card", "thumb")
WORKERS = max(1, (os.cpu_count() or 1) // 2)
COPY_WORKERS = 8


def get_latest_staging_db() -> Path:
    candidates = sorted(
        STAGING_ROOT.glob("*/staging.sqlite"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("staging.sqlite не найден")
    return candidates[0]


def get_plan_path(staging_path: Path) -> Path:
    return staging_path.parent / "media_plan.json"


def read_plan(staging_path: Path) -> dict:
    plan_path = get_plan_path(staging_path)

    if not plan_path.exists():
        raise RuntimeError(
            f"media_plan.json не найден: {plan_path}"
        )

    return json.loads(
        plan_path.read_text(encoding="utf-8"),
    )


def write_plan(staging_path: Path, plan: dict) -> None:
    get_plan_path(staging_path).write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


PREVIEW_MAX_INPUT_BYTES = 40 * 1024 * 1024
PREVIEW_MAX_ZIP_ENTRIES = 1000
PREVIEW_MAX_MEMBER_BYTES = 40 * 1024 * 1024
PREVIEW_MAX_COMPRESSION_RATIO = 100


def _read_bounded(stream, limit: int) -> bytes:
    chunks = []
    total = 0
    while total <= limit:
        chunk = stream.read(min(1024 * 1024, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise RuntimeError("Файл превышает допустимый размер preview")
    return b"".join(chunks)


def load_preview_bytes(source_path: Path) -> bytes:
    try:
        source_size = source_path.stat().st_size
    except OSError as exc:
        raise RuntimeError(f"Не удалось прочитать preview-файл: {exc}") from exc
    if source_size > PREVIEW_MAX_INPUT_BYTES:
        raise RuntimeError("Файл preview превышает лимит 40 МБ")

    with source_path.open("rb") as source:
        signature = source.read(4)
    if signature != b"PK\x03\x04":
        with source_path.open("rb") as source:
            return _read_bounded(source, PREVIEW_MAX_INPUT_BYTES)

    with ZipFile(source_path) as archive:
        infos = archive.infolist()
        if len(infos) > PREVIEW_MAX_ZIP_ENTRIES:
            raise RuntimeError("ZIP содержит слишком много записей")

        candidates = [
            info
            for info in infos
            if not info.is_dir()
            and "карта" in Path(info.filename).name.lower()
            and "фото+карта" not in Path(info.filename).name.lower()
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"ZIP: найдено карт-кандидатов: {len(candidates)}")

        candidate = candidates[0]
        if candidate.file_size > PREVIEW_MAX_MEMBER_BYTES:
            raise RuntimeError("ZIP preview member превышает лимит 40 МБ")
        if candidate.file_size and candidate.compress_size == 0:
            raise RuntimeError("Некорректный размер ZIP preview member")
        if candidate.compress_size and (
            candidate.file_size / candidate.compress_size > PREVIEW_MAX_COMPRESSION_RATIO
        ):
            raise RuntimeError("Слишком высокая степень сжатия ZIP preview member")

        with archive.open(candidate, "r") as member:
            data = _read_bounded(member, PREVIEW_MAX_MEMBER_BYTES)
        if len(data) != candidate.file_size:
            raise RuntimeError("Размер ZIP preview member не совпадает с заголовком")
        return data


def variant_paths(
    import_key: str,
    media_type: str,
    stem: str,
    extension: str,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}

    for variant in VARIANT_NAMES:
        directory = (
            STORAGE_ROOT
            / import_key
            / media_type
            / variant
        )
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        paths[variant] = (
            directory
            / f"{stem}{extension}"
        )

    return paths


def reuse_one(entry: dict, import_key: str) -> dict:
    """
    Копирует preview старой ACTIVE версии в новую import-директорию.
    Не скачивает и не пересоздаёт изображения.
    """
    media_type = entry["media_type"]
    stem = f'{entry["surface_hash"]}_{media_type}'

    entry["paths"] = {}
    entry["error"] = None

    for variant in VARIANT_NAMES:
        old_rel = entry["old_paths"][variant]

        if not old_rel:
            raise RuntimeError(
                f"REUSE: нет старого пути для {variant}"
            )

        old_path = PROJECT_DIR / old_rel

        if not old_path.is_file():
            raise RuntimeError(
                f"REUSE: старый файл не найден: {old_rel}"
            )

        extension = old_path.suffix

        paths = variant_paths(
            import_key,
            media_type,
            stem,
            extension,
        )

        destination = paths[variant]

        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        shutil.copy2(old_path, temporary)
        os.replace(temporary, destination)

        entry["paths"][variant] = str(
            destination.relative_to(PROJECT_DIR)
        )

    entry["status"] = "ok"

    return entry


def build_preview(entry: dict, import_key: str) -> dict:
    source_path = Path(entry["source_path"])

    if not source_path.is_absolute():
        source_path = PROJECT_DIR / source_path

    data = load_preview_bytes(source_path)

    image = _open_image(data)

    if image.width * image.height > MAX_PIXELS:
        raise RuntimeError(
            f"Слишком много пикселей: "
            f"{image.width}x{image.height}"
        )

    image_format = _detect_format(image)

    if image_format == "GIF" and getattr(image, "is_animated", False):
        raise RuntimeError(
            "Анимированный GIF не поддерживается для construction preview"
        )

    # PNG с реальной прозрачностью оставляем; непрозрачные карты — в WebP q90.
    preserve_png = image_format == "PNG" and has_transparency(image)

    variants = _build_static_variants(
        image,
        preserve_png=preserve_png,
    )

    media_type = entry["media_type"]
    stem = f'{entry["surface_hash"]}_{media_type}'
    extension = variants["large"][2]

    paths = variant_paths(
        import_key,
        media_type,
        stem,
        extension,
    )

    for variant in VARIANT_NAMES:
        data_bytes, _, _ = variants[variant]

        destination = paths[variant]

        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        temporary.write_bytes(data_bytes)
        os.replace(temporary, destination)

    entry["paths"] = {
        variant: str(
            paths[variant].relative_to(PROJECT_DIR)
        )
        for variant in VARIANT_NAMES
    }
    entry["status"] = "ok"
    entry["format"] = image_format
    entry["mime_type"] = variants["large"][1]
    entry["width"] = image.width
    entry["height"] = image.height
    entry["error"] = None

    return entry


def preview_task(
    position: int,
    entry: dict,
    import_key: str,
) -> tuple[int, dict]:
    """
    Модульный уровень обязателен: функция передаётся
    в ProcessPoolExecutor и должна быть pickle-совместимой.
    """
    try:
        return (
            position,
            build_preview(entry, import_key),
        )
    except Exception as exc:
        return (
            position,
            {
                **entry,
                "status": "error",
                "error": str(exc),
            },
        )


def main() -> None:
    staging_path = get_latest_staging_db()
    plan = read_plan(staging_path)
    import_key = plan["import_key"]

    entries = plan["entries"]

    download_entries = [
        entry
        for entry in entries
        if entry["decision"] == "download"
        and entry["status"] == "ok"
    ]
    reuse_entries = [
        entry
        for entry in entries
        if entry["decision"] == "reuse"
    ]
    failed_entries = [
        entry
        for entry in entries
        if entry["decision"] == "download"
        and entry["status"] == "error"
    ]
    # Ошибка скачивания не должна удалять рабочее фото/карту: если для
    # поверхности есть старая версия, копируем её превью в новый импорт.
    fallback_entries = [
        entry
        for entry in failed_entries
        if entry.get("old_paths")
    ]

    print("=" * 70)
    print("CONSTRUCTION MEDIA PREVIEW (INCREMENTAL)")
    print("=" * 70)
    print(f"Staging DB:     {staging_path}")
    print(f"Import key:     {import_key}")
    print(f"Plan entries:   {len(entries)}")
    print(f"Preview tasks:  {len(download_entries)}")
    print(f"REUSE copies:   {len(reuse_entries)}")
    print(f"Failed skip:    {len(failed_entries)}")
    print(f"Fallback copies:{len(fallback_entries)}")
    print(f"Workers:        {WORKERS}")
    print(f"Copy workers:   {COPY_WORKERS}")

    if download_entries:
        print()
        print("Preview generation started...")

        with ProcessPoolExecutor(
            max_workers=WORKERS,
        ) as executor:
            futures = [
                executor.submit(
                    preview_task,
                    position,
                    download_entries[position],
                    import_key,
                )
                for position in range(len(download_entries))
            ]

            for future in as_completed(futures):
                position, result = future.result()
                download_entries[position].update(result)

    if reuse_entries:
        print()
        print("REUSE copy started...")

        def copy_task(position: int) -> tuple[int, dict]:
            entry = reuse_entries[position]

            try:
                return (
                    position,
                    reuse_one(entry, import_key),
                )
            except Exception as exc:
                return (
                    position,
                    {
                        **entry,
                        "status": "error",
                        "error": str(exc),
                    },
                )

        with ThreadPoolExecutor(
            max_workers=COPY_WORKERS,
        ) as executor:
            futures = [
                executor.submit(copy_task, position)
                for position in range(len(reuse_entries))
            ]

            for future in as_completed(futures):
                position, result = future.result()
                reuse_entries[position].update(result)

    if fallback_entries:
        print()
        print("Fallback copy started (failed downloads)...")

        for entry in fallback_entries:
            reason = entry.get("error")

            try:
                result = reuse_one(entry, import_key)
                entry.update(result)
                entry["fallback"] = True
                entry["fallback_reason"] = reason
            except Exception as exc:
                entry["status"] = "error"
                entry["error"] = (
                    f"fallback: {exc}; original: {reason}"
                )

    write_plan(staging_path, plan)

    ok = sum(
        1
        for entry in entries
        if entry["status"] == "ok"
    )
    errors = sum(
        1
        for entry in entries
        if entry["status"] == "error"
    )

    print()
    print("PREVIEW RESULT")
    print("-" * 70)
    print(f"Tasks:     {len(entries)}")
    print(f"OK:        {ok}")
    print(f"ERROR:     {errors}")
    print(f"Plan:      {get_plan_path(staging_path)}")
    print()
    print("PostgreSQL: НЕ ИЗМЕНЁН")


if __name__ == "__main__":
    main()