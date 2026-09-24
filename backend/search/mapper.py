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
    return float(value)


class SiteSurfaceMapper:
    """Map site PostgreSQL rows to albion-search SurfaceRecord objects."""

    @staticmethod
    def map(row: Any) -> SurfaceRecord:
        data = dict(row)

        address = _text(data.get("address"))
        parsed = AddressParserV2.parse(address)

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
            photo_url=_optional_text(data.get("photo_url")),
            map_url=_optional_text(data.get("map_url")),

            district=None,
            lot_number=None,
            owner=None,
            passport_number=None,
            support=None,

            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            is_active=bool(data.get("is_active", True)),
        )
