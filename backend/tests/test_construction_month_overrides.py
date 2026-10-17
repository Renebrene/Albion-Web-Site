from __future__ import annotations

import pytest

from backend.search.catalog_loader import _apply_month_overrides
from backend.services.construction_overrides import _clean_month_overrides
from engine.storage.models import AvailabilityRecord, SurfaceRecord


def test_clean_month_overrides_validates_year_status_and_price():
    assert _clean_month_overrides({
        "Ноябрь": {"year": 2026, "price": "18 500", "status": "busy"}
    }) == [(2026, 11, {"price": "18500", "status": "busy"})]

    with pytest.raises(ValueError):
        _clean_month_overrides({"Ноябрь": {"year": 2026, "status": "hacked"}})
    with pytest.raises(ValueError):
        _clean_month_overrides({"Ноябрь": {"year": 1999, "price": 5000}})
    with pytest.raises(ValueError):
        _clean_month_overrides({"Ноябрь": {"year": 2026, "price": -1}})


def test_month_overrides_apply_to_catalog_records_only_for_matching_year_month():
    surface = SurfaceRecord(
        id=17,
        city="Ростов-на-Дону",
        title="Щит",
        address="Ленина 1",
        side="A",
        media_type="Щит",
        size="6 X 3 Метр",
        metadata={"surface_hash": "hash-17"},
    )
    records = {
        17: {
            2026: {
                11: AvailabilityRecord(
                    surface_id=17, year=2026, month=11, status="FREE", price=10000
                )
            },
            2027: {
                11: AvailabilityRecord(
                    surface_id=17, year=2027, month=11, status="FREE", price=11000
                )
            },
        }
    }

    _apply_month_overrides(
        [surface], records, {("hash-17", 2026, 11): {"status": "busy", "price": "18500"}}
    )

    assert records[17][2026][11].status == "SOLD"
    assert records[17][2026][11].price == 18500
    assert records[17][2027][11].status == "FREE"
    assert records[17][2027][11].price == 11000
