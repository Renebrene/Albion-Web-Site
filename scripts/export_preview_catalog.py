"""Выгрузка крупных превью конструкций в читаемый каталог.

Для каждой активной поверхности создаётся папка «Город-Адрес-Сторона»,
внутрь копируются крупные (large) превью:

    Город+Адрес+Сторона.<ext>        — фото конструкции
    Город+Адрес+Сторона_карта.<ext>  — карта-схема

Папка создаётся всегда, файл — только если он реально есть.
Значения берутся те же, что показывает сайт (с учётом переопределений).

Запуск:
    .venv/bin/python scripts/export_preview_catalog.py [--dest ПУТЬ]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_DIR))

from backend.services.data_service import get_data  # noqa: E402


DEFAULT_DEST = Path.home() / "albion-previews"

# Символы, недопустимые в именах файлов (Windows-набор + управляющие).
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Имя каталога/файла ограничено 255 БАЙТАМИ (кириллица — 2 байта на символ),
# поэтому длину считаем в байтах, а не в символах.
_MAX_NAME_BYTES = 180
_MAX_CITY_BYTES = 60
_MAX_SIDE_BYTES = 24


def _truncate_bytes(text: str, limit: int) -> str:
    """Обрезает строку до limit байт, не разрывая символ."""
    encoded = text.encode("utf-8")

    if len(encoded) <= limit:
        return text

    cut = encoded[:limit]

    while cut:
        try:
            return cut.decode("utf-8").rstrip(" -+_")
        except UnicodeDecodeError:
            cut = cut[:-1]

    return ""


def safe_part(value: str, fallback: str = "без-названия") -> str:
    """Приводит часть имени к безопасному для файловой системы виду."""
    text = _UNSAFE.sub("-", str(value or ""))
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[-]{2,}", "-", text)
    text = text.strip(" .-")

    return text or fallback


def name_parts(item: dict) -> tuple[str, str, str]:
    """(город, адрес, сторона) — город и сторона целиком, адрес подрезаем."""
    city = _truncate_bytes(safe_part(item.get("city"), "город"), _MAX_CITY_BYTES)
    side = _truncate_bytes(safe_part(item.get("side"), "сторона"), _MAX_SIDE_BYTES)
    address = safe_part(item.get("address"), "адрес")

    rest = _MAX_NAME_BYTES - len(f"{city}-{side}".encode("utf-8"))
    address = _truncate_bytes(address, max(30, rest))

    return city, address, side


def folder_name(item: dict) -> str:
    return "-".join(name_parts(item))


def file_stem(item: dict) -> str:
    return "+".join(name_parts(item))


def source_path(web_path: str | None) -> Path | None:
    """«/storage/...» → путь на диске."""
    if not web_path:
        return None

    relative = str(web_path).lstrip("/")

    return PROJECT_DIR / relative


def unique_dir(parent: Path, name: str, used: set[str]) -> Path:
    """Папка с уникальным именем (на случай совпадения город+адрес+сторона)."""
    candidate = name
    index = 2

    while candidate.lower() in used:
        candidate = f"{name}_{index}"
        index += 1

    used.add(candidate.lower())

    return parent / candidate


def export(dest: Path) -> dict:
    items = get_data()

    if dest.exists():
        shutil.rmtree(dest)

    dest.mkdir(parents=True, exist_ok=True)

    used: set[str] = set()
    stats = {
        "surfaces": len(items),
        "folders": 0,
        "photos": 0,
        "maps": 0,
        "missing_photo": 0,
        "missing_map": 0,
        "errors": [],
    }

    for item in items:
        target_dir = unique_dir(dest, folder_name(item), used)
        target_dir.mkdir(parents=True, exist_ok=True)
        stats["folders"] += 1

        stem = file_stem(item)

        for key, suffix, counter, missing in (
            ("photo_large", "", "photos", "missing_photo"),
            ("map_large", "_карта", "maps", "missing_map"),
        ):
            source = source_path(item.get(key))

            if source is None or not source.is_file():
                stats[missing] += 1
                continue

            target = target_dir / f"{stem}{suffix}{source.suffix}"

            try:
                shutil.copy2(source, target)
            except OSError as exc:
                stats["errors"].append(f"{target}: {exc}")
                continue

            stats[counter] += 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Выгрузить крупные превью конструкций в каталог "
            "«Город-Адрес-Сторона»"
        )
    )
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help=f"куда складывать (по умолчанию {DEFAULT_DEST})",
    )

    args = parser.parse_args()
    dest = Path(args.dest).expanduser().resolve()

    print(f"Каталог:  {dest}")
    stats = export(dest)

    print(f"Поверхностей: {stats['surfaces']}  папок: {stats['folders']}")
    print(f"Фото:         {stats['photos']}  (нет файла: {stats['missing_photo']})")
    print(f"Карт:         {stats['maps']}  (нет файла: {stats['missing_map']})")

    if stats["errors"]:
        print(f"Ошибок копирования: {len(stats['errors'])}")
        for line in stats["errors"][:10]:
            print("  ", line)


if __name__ == "__main__":
    main()
