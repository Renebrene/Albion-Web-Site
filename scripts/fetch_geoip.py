"""Загрузка бесплатной гео-базы DB-IP Lite (страны) для статистики.

Качает dbip-country-lite-YYYY-MM.mmdb.gz (~4 МБ), распаковывает и кладёт
в backend/data/dbip-country-lite.mmdb. Формат MaxMind (.mmdb) — его же
читает backend/services/geoip.py, поэтому при желании файл можно заменить
на GeoLite2-Country.mmdb от MaxMind.

Лицензия DB-IP Lite — CC BY 4.0: требуется указание авторства
(строка «IP Geolocation by DB-IP» есть на странице статистики).

Запуск:
    .venv/bin/python -m scripts.fetch_geoip                # текущий месяц
    .venv/bin/python -m scripts.fetch_geoip --month 2026-09  # конкретный
    .venv/bin/python -m scripts.fetch_geoip --out backend/data/custom.mmdb
"""
from __future__ import annotations

import argparse
import gzip
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_DIR / "backend" / "data" / "dbip-country-lite.mmdb"

URL_TEMPLATE = "https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz"

USER_AGENT = "albion-geoip-fetch/1.0"


def current_month() -> str:
    today = date.today()

    return f"{today.year:04d}-{today.month:02d}"


def month_before(month: str) -> str:
    year, mon = (int(part) for part in month.split("-"))

    mon -= 1

    if mon == 0:
        mon = 12
        year -= 1

    return f"{year:04d}-{mon:02d}"


def download(month: str) -> bytes:
    """Скачивает архив месяца; при 404 пробует предыдущий месяц."""
    tried = []

    for candidate in (month, month_before(month), month_before(month_before(month))):
        if candidate in tried:
            continue

        tried.append(candidate)
        url = URL_TEMPLATE.format(month=candidate)

        print(f"  → {url}")

        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            print(f"    HTTP {exc.code}; пробую другой месяц…")
        except urllib.error.URLError as exc:
            print(f"    сеть недоступна: {exc.reason}")
            raise

    raise SystemExit(f"Не удалось скачать базу (пробовал: {', '.join(tried)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузка гео-базы DB-IP Lite")
    parser.add_argument(
        "--month",
        default=current_month(),
        help="Месяц в формате YYYY-MM (по умолчанию текущий)",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Куда положить .mmdb",
    )

    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"ALBION · Гео-база DB-IP Lite ({args.month})")

    archive = download(args.month)

    print(f"  ↓ получено {len(archive)} байт; распаковываю…")

    try:
        data = gzip.decompress(archive)
    except OSError as exc:
        raise SystemExit(f"Не удалось распаковать архив: {exc}")

    out_path.write_bytes(data)

    # Настоящая проверка формата: маркер MaxMind лежит в КОНЦЕ файла
    # (в метаданных), поэтому проверяем через сам читатель.
    try:
        import maxminddb

        maxminddb.open_database(str(out_path)).close()
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        raise SystemExit(f"Файл не читается как база MaxMind (.mmdb): {exc}")

    size_mb = len(data) / (1024 * 1024)

    print(f"COMMIT: база сохранена — {out_path} ({size_mb:.1f} МБ)")
    print("  • гео-статистика по странам заработает после перезапуска backend")


if __name__ == "__main__":
    sys.exit(main())
