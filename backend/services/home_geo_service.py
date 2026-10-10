"""Структурированный geo-контент слайда «Возможности»."""
from __future__ import annotations

from urllib.parse import quote

from backend.services.data_service import get_connection, get_geo_location_stats


def _safe_source(value: str) -> str:
    value = str(value or '').strip()
    if value.startswith(('https://', 'http://')):
        return value
    return ''


def _media_url(storage_path: str | None) -> str:
    if not storage_path:
        return ''
    value = str(storage_path).strip()
    if value.startswith('/'):
        return value
    return f'/storage/{value}'


def _map_href(kind: str, value: str, enabled: bool) -> str:
    if not enabled or not value:
        return ''
    key = 'city' if kind == 'city' else 'address'
    return f'/vozmozhnosti?{key}={quote(value, safe="")}'


WHEEL_MODES = ('off', 'v1', 'v2', 'v3')


def _settings(conn) -> dict:
    row = conn.execute(
        'SELECT is_active, map_links_enabled, deck_wheel_mode '
        'FROM home_geo_settings WHERE id = 1'
    ).fetchone()
    if not row:
        return {'is_active': True, 'map_links_enabled': True, 'deck_wheel_mode': 'off'}
    return {
        'is_active': bool(row[0]),
        'map_links_enabled': bool(row[1]),
        'deck_wheel_mode': row[2] if row[2] in WHEEL_MODES else 'off',
    }


def _photos(conn, attraction_ids: list[int], *, active_only: bool) -> dict[int, list[dict]]:
    if not attraction_ids:
        return {}
    rows = conn.execute(
        """
        SELECT p.id, p.attraction_id, p.media_id, p.image_path,
               p.alt_text, p.source_name, p.source_url, p.license,
               p.sort_order, p.is_cover, m.storage_path
        FROM home_geo_attraction_photos p
        LEFT JOIN media m ON m.id = p.media_id
        WHERE p.attraction_id = ANY(%s)
        ORDER BY p.sort_order, p.id
        """,
        (attraction_ids,),
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for row in rows:
        path = row[3] or _media_url(row[10])
        item = {
            'id': row[0],
            'media_id': row[2],
            'url': _media_url(path),
            'alt': row[4] or '',
            'source_name': row[5] or '',
            'source_url': _safe_source(row[6]),
            'license': row[7] or '',
            'sort_order': row[8],
            'is_cover': bool(row[9]),
        }
        result.setdefault(row[1], []).append(item)
    return result


def _cover(photos: list[dict], attraction: dict | None) -> dict | None:
    """Фото-обложка локации: cover-фото достопримечательности или первое."""
    if not attraction:
        return None
    items = photos or []
    photo = next((p for p in items if p.get('is_cover')), None) or (items[0] if items else None)
    if not photo:
        return None
    return {
        'attraction_id': attraction['id'],
        'attraction_title': attraction['title'],
        'url': photo.get('url') or '',
        'alt': photo.get('alt') or attraction['title'],
        'source_name': photo.get('source_name') or '',
        'source_url': photo.get('source_url') or '',
        'license': photo.get('license') or '',
    }


def get_public_geo() -> dict:
    with get_connection() as conn:
        settings = _settings(conn)
        location_rows = conn.execute(
            """
            SELECT id, kind, label, map_value, parent_city, sort_order,
                   description, cover_attraction_id
            FROM home_geo_locations
            WHERE is_active = TRUE
            ORDER BY sort_order, id
            """
        ).fetchall()
        attraction_rows = conn.execute(
            """
            SELECT id, location_id, title, description, sort_order
            FROM home_geo_attractions
            WHERE is_active = TRUE
            ORDER BY sort_order, id
            """
        ).fetchall()
        photos = _photos(conn, [row[0] for row in attraction_rows], active_only=True)

    by_location: dict[int, list[dict]] = {}
    attractions = []
    for row in attraction_rows:
        item = {
            'id': row[0], 'location_id': row[1], 'title': row[2],
            'description': row[3], 'sort_order': row[4],
            'photos': photos.get(row[0], []),
        }
        attractions.append(item)
        if row[1] is not None:
            by_location.setdefault(row[1], []).append(item)
    attraction_by_id = {a['id']: a for a in attractions}

    location_stats = get_geo_location_stats()
    empty_stats = {'constructions': 0, 'formats': []}

    locations = []
    for row in location_rows:
        candidates = by_location.get(row[0], [])
        chosen = attraction_by_id.get(row[7]) if row[7] else None
        if chosen is None and candidates:
            chosen = candidates[0]
        locations.append({
            'id': row[0], 'kind': row[1], 'label': row[2],
            'map_value': row[3], 'parent_city': row[4],
            'sort_order': row[5],
            'description': row[6] or '',
            'href': _map_href(row[1], row[3], settings['map_links_enabled']),
            'map_href': _map_href(row[1], row[3], True),
            'cover': _cover(chosen['photos'] if chosen else [], chosen),
            'stats': location_stats.get(str(row[3]).strip().lower(), empty_stats),
        })
    return {'settings': settings, 'locations': locations, 'attractions': attractions}


def get_admin_geo() -> dict:
    with get_connection() as conn:
        settings = _settings(conn)
        locations = conn.execute(
            """SELECT id, kind, label, map_value, parent_city, sort_order, is_active,
                      description, cover_attraction_id
               FROM home_geo_locations ORDER BY kind, sort_order, id"""
        ).fetchall()
        attractions = conn.execute(
            """SELECT id, location_id, title, description, sort_order, is_active
               FROM home_geo_attractions ORDER BY sort_order, id"""
        ).fetchall()
        photos = _photos(conn, [row[0] for row in attractions], active_only=False)
    return {
        'settings': settings,
        'locations': [
            {'id': r[0], 'kind': r[1], 'label': r[2], 'map_value': r[3],
             'parent_city': r[4], 'sort_order': r[5], 'is_active': r[6],
             'description': r[7] or '', 'cover_attraction_id': r[8]}
            for r in locations
        ],
        'attractions': [
            {'id': r[0], 'location_id': r[1], 'title': r[2],
             'description': r[3], 'sort_order': r[4], 'is_active': r[5],
             'photos': photos.get(r[0], [])}
            for r in attractions
        ],
    }


def update_settings(data: dict) -> dict:
    mode = data.get('deck_wheel_mode')
    if mode is not None and mode not in WHEEL_MODES:
        raise ValueError('deck_wheel_mode: off, v1, v2 или v3')
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """UPDATE home_geo_settings
                   SET is_active = COALESCE(%s, is_active),
                       map_links_enabled = COALESCE(%s, map_links_enabled),
                       deck_wheel_mode = COALESCE(%s, deck_wheel_mode),
                       updated_at = NOW() WHERE id = 1""",
                (data.get('is_active'), data.get('map_links_enabled'), mode),
            )
        return _settings(conn)


def create_location(data: dict) -> dict:
    kind = str(data.get('kind') or '').strip()
    if kind not in ('city', 'district'):
        raise ValueError('kind должен быть city или district')
    label = str(data.get('label') or '').strip()[:200]
    if not label:
        raise ValueError('Название локации обязательно')
    value = str(data.get('map_value') or label).strip()[:200]
    cover = data.get('cover_attraction_id')
    cover = int(cover) if cover else None
    with get_connection() as conn:
        with conn.transaction():
            row = conn.execute(
                """INSERT INTO home_geo_locations
                   (kind, label, map_value, parent_city, sort_order, is_active,
                    description, cover_attraction_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (kind, label, value, str(data.get('parent_city') or '').strip(),
                 int(data.get('sort_order') or 0), bool(data.get('is_active', True)),
                 str(data.get('description') or '').strip()[:8000], cover),
            ).fetchone()
    return {'id': row[0]}


def update_location(location_id: int, data: dict) -> None:
    allowed = ('kind', 'label', 'map_value', 'parent_city', 'sort_order',
               'is_active', 'description', 'cover_attraction_id')
    sets, params = [], []
    for key in allowed:
        if key in data:
            value = data[key]
            if key == 'kind' and value not in ('city', 'district'):
                raise ValueError('kind должен быть city или district')
            if key == 'description':
                value = str(value or '').strip()[:8000]
            elif key == 'cover_attraction_id':
                value = int(value) if value else None
            elif key in ('label', 'map_value', 'parent_city'):
                value = str(value or '').strip()[:200]
            sets.append(f'{key} = %s'); params.append(value)
    if not sets: return
    params.append(int(location_id))
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute(f"UPDATE home_geo_locations SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s", tuple(params))
            if cur.rowcount == 0: raise LookupError('Локация не найдена')


def delete_location(location_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute('DELETE FROM home_geo_locations WHERE id=%s', (int(location_id),))
            if cur.rowcount == 0: raise LookupError('Локация не найдена')


def create_attraction(data: dict) -> dict:
    title = str(data.get('title') or '').strip()[:240]
    if not title: raise ValueError('Название достопримечательности обязательно')
    with get_connection() as conn:
        with conn.transaction():
            row = conn.execute(
                """INSERT INTO home_geo_attractions
                   (location_id,title,description,sort_order,is_active)
                   VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (data.get('location_id'), title, str(data.get('description') or '').strip()[:6000],
                 int(data.get('sort_order') or 0), bool(data.get('is_active', True))),
            ).fetchone()
    return {'id': row[0]}


def update_attraction(attraction_id: int, data: dict) -> None:
    allowed = ('location_id', 'title', 'description', 'sort_order', 'is_active')
    sets, params = [], []
    for key in allowed:
        if key in data:
            value = data[key]
            if key == 'title': value = str(value or '').strip()[:240]
            if key == 'description': value = str(value or '').strip()[:6000]
            sets.append(f'{key} = %s'); params.append(value)
    if not sets: return
    params.append(int(attraction_id))
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute(f"UPDATE home_geo_attractions SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s", tuple(params))
            if cur.rowcount == 0: raise LookupError('Достопримечательность не найдена')


def delete_attraction(attraction_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute('DELETE FROM home_geo_attractions WHERE id=%s', (int(attraction_id),))
            if cur.rowcount == 0: raise LookupError('Достопримечательность не найдена')


def create_photo(attraction_id: int, data: dict) -> dict:
    source_url = _safe_source(data.get('source_url'))
    if not source_url: raise ValueError('Нужна http/https ссылка на источник')
    source_name = str(data.get('source_name') or '').strip()[:240]
    license_name = str(data.get('license') or '').strip()[:240]
    path = str(data.get('image_path') or '').strip()[:1000]
    if not source_name or not license_name or not path:
        raise ValueError('Фото требует путь, источник и лицензию')
    with get_connection() as conn:
        with conn.transaction():
            row = conn.execute(
                """INSERT INTO home_geo_attraction_photos
                   (attraction_id,media_id,image_path,alt_text,source_name,source_url,license,sort_order,is_cover)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (int(attraction_id), data.get('media_id'), path,
                 str(data.get('alt_text') or '').strip()[:240], source_name,
                 source_url, license_name, int(data.get('sort_order') or 0), bool(data.get('is_cover'))),
            ).fetchone()
    return {'id': row[0]}


def delete_photo(photo_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            cur = conn.execute('DELETE FROM home_geo_attraction_photos WHERE id=%s', (int(photo_id),))
            if cur.rowcount == 0: raise LookupError('Фото не найдено')
