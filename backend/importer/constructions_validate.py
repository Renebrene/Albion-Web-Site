from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

PROJECT_DIR = Path(__file__).resolve().parents[2]
JSON_FILE = PROJECT_DIR / "tmp" / "constructions_import.json"

VALID_SIDES = {"A", "B", "C"}


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def classify_url(value: str) -> str:
    url = clean(value)

    if not url:
        return "empty"

    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host in {
        "disk.yandex.ru",
        "www.disk.yandex.ru",
        "yadi.sk",
        "www.yadi.sk",
    }:
        return "yandex_disk"

    if parsed.scheme in {"http", "https"}:
        return "direct_url"

    return "unknown"


def main() -> None:
    if not JSON_FILE.exists():
        raise RuntimeError(
            f"Файл не найден: {JSON_FILE}"
        )

    data = json.loads(
        JSON_FILE.read_text(encoding="utf-8")
    )

    rows = data.get("surfaces") or []

    if not rows:
        raise RuntimeError(
            "В constructions_import.json нет surfaces"
        )

    errors: list[str] = []
    warnings: list[str] = []

    photo_sources = {
        "yandex_disk": 0,
        "direct_url": 0,
        "empty": 0,
        "unknown": 0,
    }

    map_sources = {
        "yandex_disk": 0,
        "direct_url": 0,
        "empty": 0,
        "unknown": 0,
    }

    cities: set[str] = set()
    construction_keys: set[tuple[str, str]] = set()
    surface_keys: set[tuple[str, str, str]] = set()

    duplicate_constructions = 0
    duplicate_surfaces = 0
    coords_with = 0
    coords_without = 0

    required = (
        "city",
        "address",
        "name",
        "side",
        "type",
        "size",
    )

    for index, row in enumerate(rows, start=1):
        prefix = f"Строка {index}"

        for field in required:
            if not clean(row.get(field)):
                errors.append(
                    f"{prefix}: пустое поле {field}"
                )

        city = clean(row.get("city"))
        address = clean(row.get("address"))
        side = clean(row.get("side")).upper()

        if city:
            cities.add(city)

        construction_key = (
            city.lower(),
            address.lower(),
        )

        if construction_key in construction_keys:
            duplicate_constructions += 1
        else:
            construction_keys.add(construction_key)

        surface_key = (
            city.lower(),
            address.lower(),
            side,
        )

        if surface_key in surface_keys:
            duplicate_surfaces += 1
        else:
            surface_keys.add(surface_key)

        if side and side not in VALID_SIDES:
            warnings.append(
                f"{prefix}: неизвестная сторона '{side}'"
            )

        lat = row.get("latitude")
        lng = row.get("longitude")

        if lat is None or lng is None:
            coords_without += 1
        else:
            coords_with += 1

            if not (-90 <= float(lat) <= 90):
                errors.append(
                    f"{prefix}: latitude вне диапазона: {lat}"
                )

            if not (-180 <= float(lng) <= 180):
                errors.append(
                    f"{prefix}: longitude вне диапазона: {lng}"
                )

        photo_source = classify_url(
            row.get("photo_url", "")
        )
        map_source = classify_url(
            row.get("map_url", "")
        )

        photo_sources[photo_source] += 1
        map_sources[map_source] += 1

    print("=" * 70)
    print("CONSTRUCTIONS JSON VALIDATION")
    print("=" * 70)
    print(f"JSON:                  {JSON_FILE}")
    print(f"Поверхностей:          {len(rows)}")
    print(f"Городов:               {len(cities)}")
    print(f"Конструкций:           {len(construction_keys)}")
    print(f"Координаты:            {coords_with}")
    print(f"Без координат:         {coords_without}")
    print(f"Дубликаты конструкций: {duplicate_constructions}")
    print(f"Дубликаты поверхностей:{duplicate_surfaces}")

    print()
    print("ФОТО")
    print("-" * 70)
    for source, count in photo_sources.items():
        print(f"{source:20} {count}")

    print()
    print("КАРТА")
    print("-" * 70)
    for source, count in map_sources.items():
        print(f"{source:20} {count}")

    print()
    print("ПРОВЕРКА")
    print("-" * 70)
    print(f"Ошибок:                {len(errors)}")
    print(f"Предупреждений:        {len(warnings)}")

    if errors:
        print()
        print("ОШИБКИ:")
        for message in errors[:30]:
            print(f"  - {message}")

        if len(errors) > 30:
            print(
                f"  ... ещё {len(errors) - 30}"
            )

    if warnings:
        print()
        print("ПРЕДУПРЕЖДЕНИЯ:")
        for message in warnings[:30]:
            print(f"  - {message}")

        if len(warnings) > 30:
            print(
                f"  ... ещё {len(warnings) - 30}"
            )

    print()
    if errors:
        print("RESULT: FAILED")
        raise SystemExit(1)

    print("RESULT: OK")


if __name__ == "__main__":
    main()
