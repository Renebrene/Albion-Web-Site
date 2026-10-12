"""Проверки данных нового импорта: адреса, координаты, цены.

Проверки «мягкие»: ничего не блокируют и всегда завершаются кодом 0.
Результат печатается маркерами этапов (STEP 6/7/8) и строками ``CHECK:``,
которые монитор обновления раскладывает по этапам — админка подсвечивает
этап розовым и показывает подробный список под ним.

Запускается из пайплайна импорта после записи в PostgreSQL; читает
``tmp/import/<key>/staging.sqlite``.
"""

from __future__ import annotations

import math
import os
import sqlite3
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
IMPORT_DIR = PROJECT_DIR / "tmp" / "import"

STEP_ADDRESS = 6
STEP_COORDS = 7
STEP_PRICE = 8

# Точка считается аномальной, если она дальше этого расстояния от центра
# остальных координат выгрузки (как в Excel-импортёре).
COORD_ANOMALY_KM = 300.0


def _import_key() -> str | None:
    key = (os.getenv("ALBION_IMPORT_KEY") or "").strip()

    if key:
        return key

    files = sorted(
        IMPORT_DIR.glob("*/staging.sqlite"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    return files[0].parent.name if files else None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2

    if len(ordered) % 2:
        return ordered[middle]

    return (ordered[middle - 1] + ordered[middle]) / 2


def _surface_rows(conn: sqlite3.Connection) -> list[tuple]:
    """Все поверхности с адресом/стороной и полями для проверок."""
    return conn.execute(
        """
        SELECT
            s.id,
            c.address,
            s.side,
            s.latitude,
            s.longitude,
            s.price,
            (
                SELECT COUNT(*)
                FROM surface_availability a
                WHERE a.surface_id = s.id
                  AND a.price IS NOT NULL
                  AND TRIM(a.price) <> ''
            ) AS month_prices
        FROM surfaces s
        JOIN constructions c ON c.id = s.construction_id
        WHERE s.is_active = 1
        ORDER BY c.address, s.side
        """
    ).fetchall()


def _where(address: str | None, side: str | None, surface_id: int) -> str:
    if address and address.strip():
        return address.strip() + (f" сторона={side}" if side else "")

    return f"поверхность id={surface_id}"


# ------------------------------------------------------------------ адреса


def check_addresses(conn: sqlite3.Connection) -> list[str]:
    """Пустой/слишком короткий адрес и адрес без названия (одни цифры).

    Пересечения улиц без номера дома (напр. «Вавилова ул. - Дачная ул.») —
    норма, поэтому «нет номера» НЕ считаем ошибкой.
    """
    messages: list[str] = []

    for surface_id, address, side, *_ in _surface_rows(conn):
        text = (address or "").strip()
        place = _where(address, side, surface_id)

        if not text:
            messages.append(f"[адрес пустой] {place}")
            continue

        if len(text) < 5:
            messages.append(f"[адрес слишком короткий] {text}")
            continue

        if not any(char.isalpha() for char in text):
            messages.append(f"[адрес без названия] {text}")

    return messages


# -------------------------------------------------------------- координаты


def check_coordinates(conn: sqlite3.Connection) -> list[str]:
    """Нет координат, вне диапазона, далеко от центра выгрузки."""
    rows = _surface_rows(conn)

    messages: list[str] = []
    points: list[tuple[float, float]] = []

    for surface_id, address, side, lat, lon, *_ in rows:
        if lat is None or lon is None:
            messages.append(f"[нет координат] {_where(address, side, surface_id)}")
            continue

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            messages.append(
                f"[координаты вне диапазона] {_where(address, side, surface_id)} "
                f"({lat}, {lon})"
            )
            continue

        points.append((lat, lon))

    if len(points) >= 3:
        center_lat = _median([lat for lat, _ in points])
        center_lon = _median([lon for _, lon in points])

        anomalies = []
        for surface_id, address, side, lat, lon, *_ in rows:
            if lat is None or lon is None:
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue

            distance = _haversine_km(center_lat, center_lon, lat, lon)

            if distance > COORD_ANOMALY_KM:
                anomalies.append(
                    f"[координаты далеко от центра] "
                    f"{_where(address, side, surface_id)} "
                    f"({distance:.0f} км)"
                )

        messages.extend(anomalies)

    return messages


# ------------------------------------------------------------------- цены


def check_prices(conn: sqlite3.Connection) -> list[str]:
    """Нет цены ни в поверхности, ни в месячной доступности."""
    messages: list[str] = []

    for surface_id, address, side, _lat, _lon, price, month_prices in _surface_rows(conn):
        if (price is None or not str(price).strip()) and not month_prices:
            messages.append(f"[нет цены] {_where(address, side, surface_id)}")

    return messages


# ------------------------------------------------------------------- вывод


def _emit(step: int, name: str, messages: list[str]) -> None:
    print(f"===== STEP {step}: {name} =====")
    print(f"Errors: {len(messages)}")

    for message in messages:
        print(f"CHECK: {message}")

    print()


def run() -> int:
    key = _import_key()
    staging_db = IMPORT_DIR / key / "staging.sqlite" if key else None

    if not staging_db or not staging_db.exists():
        print("Проверки: staging.sqlite не найден — шаг пропущен.")
        return 0

    conn = sqlite3.connect(staging_db)

    try:
        _emit(
            STEP_ADDRESS,
            "Проверка адресов",
            check_addresses(conn),
        )
        _emit(
            STEP_COORDS,
            "Проверка координат",
            check_coordinates(conn),
        )
        _emit(
            STEP_PRICE,
            "Проверка цен",
            check_prices(conn),
        )
    finally:
        conn.close()

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
