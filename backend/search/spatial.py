"""Пространственная выборка конструкций вокруг точки (read-only).

Вариант B: радиус задаётся в момент запроса, НИЧЕГО не сохраняется.
Используется `surfaces.location` (в `constructions.location` нет данных),
PostGIS + существующий GiST `idx_surfaces_location`. Привязки к трассам нет.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Optional

RADIUS_M_DEFAULT = 5_000  # 5 км
EARTH_R_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * EARTH_R_M * math.asin(min(1.0, math.sqrt(a)))


def radius_filter(
    items: Iterable[dict[str, Any]],
    lat: float,
    lng: float,
    radius_m: int = RADIUS_M_DEFAULT,
    *,
    lat_key: str = "latitude",
    lng_key: str = "longitude",
) -> list[dict[str, Any]]:
    """Запасной вариант без PostGIS: фильтр по haversine, сортировка по расстоянию."""
    out: list[dict[str, Any]] = []
    for item in items:
        try:
            la, lo = float(item[lat_key]), float(item[lng_key])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(la) and math.isfinite(lo)):
            continue
        if la == 0.0 and lo == 0.0:  # «нулевой остров» — мусорные координаты
            continue
        distance = haversine_m(lat, lng, la, lo)
        if distance <= radius_m:
            enriched = dict(item)
            enriched["distance_m"] = distance
            out.append(enriched)
    out.sort(key=lambda row: row["distance_m"])
    return out


def surface_ids_near_sql(radius_m: int = RADIUS_M_DEFAULT) -> str:
    """id поверхностей (surface.id) в радиусе — то, что возвращает чат.

    Одна конструкция имеет несколько поверхностей; каждая surface проверяется
    отдельно и сортируется по расстоянию до точки.
    """
    return f"""
SELECT s.id, ST_Distance(
    s.location::geography,
    ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography
) AS dist_m
FROM constructions c
JOIN surfaces s ON s.construction_id = c.id
WHERE c.is_active = TRUE
  AND s.is_active = TRUE
  AND s.location IS NOT NULL
  AND ST_DWithin(
      s.location::geography,
      ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography,
      %(radius_m)s
  )
ORDER BY dist_m
""".strip()


def find_surface_distances_near(
    conn: Any,
    lat: float,
    lng: float,
    radius_m: int = RADIUS_M_DEFAULT,
    limit: Optional[int] = None,
) -> dict[int, float]:
    """Только чтение: surface.id -> расстояние до точки в метрах."""
    sql = surface_ids_near_sql(radius_m)
    if limit is not None:
        sql += " LIMIT %(limit)s"
        params: dict[str, Any] = {
            "lng": lng, "lat": lat, "radius_m": radius_m, "limit": int(limit),
        }
    else:
        params = {"lng": lng, "lat": lat, "radius_m": radius_m}

    distances: dict[int, float] = {}
    for row in conn.execute(sql, params).fetchall():
        surface_id = int(row[0])
        distance = float(row[1])
        previous = distances.get(surface_id)
        if previous is None or distance < previous:
            distances[surface_id] = distance
    return distances


def find_surface_ids_near(
    conn: Any,
    lat: float,
    lng: float,
    radius_m: int = RADIUS_M_DEFAULT,
    limit: Optional[int] = None,
) -> list[int]:
    """Только чтение. Возвращает surface.id в радиусе, ближайшие первыми."""
    distances = find_surface_distances_near(conn, lat, lng, radius_m, limit)
    return sorted(distances, key=lambda surface_id: distances[surface_id])


def construction_ids_near_sql(radius_m: int = RADIUS_M_DEFAULT) -> str:
    """SQL с именованными параметрами psycopg3: %(lng)s, %(lat)s, %(radius_m)s.

    Одна конструкция может иметь несколько поверхностей — берём ближайшую.
    """
    return f"""
SELECT c.id, MIN(ST_Distance(
    s.location::geography,
    ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography
)) AS dist_m
FROM constructions c
JOIN surfaces s ON s.construction_id = c.id
WHERE c.is_active = TRUE
  AND s.is_active = TRUE
  AND s.location IS NOT NULL
  AND ST_DWithin(
      s.location::geography,
      ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography,
      %(radius_m)s
  )
GROUP BY c.id
ORDER BY dist_m
""".strip()


def find_construction_ids_near(
    conn: Any,
    lat: float,
    lng: float,
    radius_m: int = RADIUS_M_DEFAULT,
    limit: Optional[int] = None,
) -> list[int]:
    """Только чтение. Возвращает id конструкций в радиусе, ближайшие первыми."""
    sql = construction_ids_near_sql(radius_m)
    if limit is not None:
        sql += " LIMIT %(limit)s"
        params: dict[str, Any] = {
            "lng": lng, "lat": lat, "radius_m": radius_m, "limit": int(limit),
        }
    else:
        params = {"lng": lng, "lat": lat, "radius_m": radius_m}
    return [int(row[0]) for row in conn.execute(sql, params).fetchall()]
