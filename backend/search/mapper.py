from __future__ import annotations

import re
from typing import Any

from engine.address.parser_v2 import AddressParserV2
from engine.storage.models import SurfaceRecord


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_text(value: Any) -> str | None:
    value = _text(value)
    return value or None


def _price(value: Any) -> int | None:
    """Convert site TEXT price such as '15 400' to integer 15400."""
    if value is None:
        return None

    text = _text(value)
    if not text:
        return None

    digits = re.sub(r"\D", "", text)
    if not digits:
        return None

    return int(digits)


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number


def _media_path(value: Any) -> str | None:
    """Return a browser-safe URL for an imported media variant."""
    value = _optional_text(value)

    if not value:
        return None

    if value.startswith(("/", "http://", "https://")):
        return value

    return f"/{value.lstrip('/')}"


class SiteSurfaceMapper:
    """Map site PostgreSQL rows to albion-search SurfaceRecord objects."""

    @staticmethod
    def map(row: Any) -> SurfaceRecord:
        from backend.services.construction_overrides import (
            get_fields_map,
            get_overrides_map,
        )

        data = dict(row)

        surface_hash = _optional_text(data.get("surface_hash"))

        # Временное переопределение основных полей (раздел «Конструкции»)
        # применяем до разбора адреса, чтобы поиск/чат видели новые значения.
        if surface_hash:
            field_override = get_fields_map().get(surface_hash)

            if field_override:
                for key, value in field_override.items():
                    if key == "type":
                        data["type"] = value
                        data["media_type"] = value
                    else:
                        data[key] = value

        address = _text(data.get("address"))
        parsed = AddressParserV2.parse(address)

        photo_url = (
            _media_path(data.get("photo_large"))
            or _media_path(data.get("photo_url"))
        )
        map_url = (
            _media_path(data.get("map_large"))
            or _media_path(data.get("map_url"))
        )

        metadata = {
            "name": _optional_text(data.get("title")),
            "type": _optional_text(data.get("type"))
            or _optional_text(data.get("media_type")),
            "photo": (
                _media_path(data.get("photo_card"))
                or _media_path(data.get("photo_url"))
            ),
            "photo_thumb": _media_path(data.get("photo_thumb")),
            "photo_card": _media_path(data.get("photo_card")),
            "photo_large": _media_path(data.get("photo_large")),
            "map": (
                _media_path(data.get("map_card"))
                or _media_path(data.get("map_url"))
            ),
            "map_thumb": _media_path(data.get("map_thumb")),
            "map_card": _media_path(data.get("map_card")),
            "map_large": _media_path(data.get("map_large")),
            "surface_hash": surface_hash,
        }

        # Переопределение фото/карты из медиатеки конструкций (активный импорт).
        if surface_hash:
            overrides = get_overrides_map()

            photo_override = overrides.get((surface_hash, "photo"))

            if photo_override:
                metadata["photo"] = (
                    photo_override.get("card") or metadata["photo"]
                )
                metadata["photo_card"] = (
                    photo_override.get("card") or metadata["photo_card"]
                )
                metadata["photo_thumb"] = (
                    photo_override.get("thumb") or metadata["photo_thumb"]
                )
                metadata["photo_large"] = (
                    photo_override.get("large") or metadata["photo_large"]
                )
                photo_url = (
                    photo_override.get("large")
                    or photo_override.get("card")
                    or photo_url
                )

            map_override = overrides.get((surface_hash, "map"))

            if map_override:
                metadata["map"] = map_override.get("card") or metadata["map"]
                metadata["map_card"] = (
                    map_override.get("card") or metadata["map_card"]
                )
                metadata["map_thumb"] = (
                    map_override.get("thumb") or metadata["map_thumb"]
                )
                metadata["map_large"] = (
                    map_override.get("large") or metadata["map_large"]
                )
                map_url = (
                    map_override.get("large")
                    or map_override.get("card")
                    or map_url
                )

        return SurfaceRecord(
            id=int(data["id"]) if data.get("id") is not None else None,
            uuid=(
                str(data["uuid"])
                if data.get("uuid") is not None
                else None
            ),

            city=_text(data.get("city")),
            title=_text(data.get("title")),
            address=address,
            side=_text(data.get("side")),
            media_type=_text(data.get("media_type")),
            size=_text(data.get("size")),

            address_words=[],
            address_roots=parsed.all_street_roots,
            address_numbers=parsed.house_numbers,

            street_root=(parsed.street_roots[0] if parsed.street_roots else None),
            house_number=parsed.house_number,
            address_key=_optional_text(data.get("address_key")),

            street_names=parsed.streets,
            street_roots=parsed.all_street_roots,
            house_numbers=parsed.house_numbers,

            price=_price(data.get("price")),

            latitude=_float(data.get("latitude")),
            longitude=_float(data.get("longitude")),

            light=_optional_text(data.get("light")),
            material=_optional_text(data.get("material")),

            external_id=_optional_text(data.get("external_id")),
            photo_url=photo_url,
            map_url=map_url,

            district=_optional_text(data.get("district")),
            lot_number=None,
            owner=None,
            passport_number=None,
            support=None,

            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            is_active=bool(data.get("is_active", True)),
            metadata=metadata,
        )
