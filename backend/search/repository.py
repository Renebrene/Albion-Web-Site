from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from backend.services.data_service import load_env_file
from backend.search.mapper import SiteSurfaceMapper, _price
from engine.house_number.matcher import HouseNumberMatcher
from engine.storage.models import AvailabilityRecord, SurfaceRecord


PROJECT_DIR = Path(__file__).resolve().parents[2]
load_env_file(PROJECT_DIR / ".env")


class SitePostgreSQLSearchRepository:
    """
    Read-only repository adapter for the existing site PostgreSQL schema.

    This class implements the repository contract expected by
    albion-search.SearchService without modifying either the site schema
    or the standalone search engine.
    """

    def __init__(self, engine=None):
        self.engine = engine or self._create_engine()

    @staticmethod
    def _create_engine():
        host = os.getenv("ALBION_DB_HOST", "127.0.0.1")
        port = os.getenv("ALBION_DB_PORT", "5432")
        dbname = os.getenv("ALBION_DB_NAME", "albion")
        user = os.getenv("ALBION_DB_USER", "albion_app")
        password = os.getenv("ALBION_DB_PASSWORD")

        url = (
            f"postgresql+psycopg://{user}:{password}"
            f"@{host}:{port}/{dbname}"
        )

        return create_engine(
            url,
            echo=False,
        )

    # ------------------------------------------------------------------
    # SQL / mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _surface_select() -> str:
        """
        Site schema -> standalone SurfaceRecord field aliases.

        Important:
        site surfaces.media_type is NULL, while surfaces.type contains
        the actual advertising media type.
        """
        return """
            SELECT
                s.id,
                s.uuid,
                ci.name AS city,
                s.name AS title,
                c.address,
                s.side,
                s.type AS media_type,
                s.size,
                s.price,
                s.external_number AS external_id,
                s.photo AS photo_url,
                s.map AS map_url,
                s.latitude,
                s.longitude,
                s.light,
                s.material,
                c.address_key,
                s.is_active,
                s.created_at,
                s.updated_at
            FROM surfaces s
            JOIN constructions c
              ON c.id = s.construction_id
            JOIN cities ci
              ON ci.id = c.city_id
        """

    def _load_surfaces(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        status: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        params: dict[str, Any] = {}
        conditions = ["s.is_active = TRUE"]

        join_availability = (
            year is not None
            or month is not None
            or status is not None
            or load_threshold is not None
            or max_load is not None
        )

        sql = self._surface_select()

        if join_availability:
            sql += """
                JOIN surface_availability sa
                  ON sa.surface_id = s.id
            """

        if year is not None:
            conditions.append("sa.year = :year")
            params["year"] = year

        if month is not None:
            conditions.append("sa.month = :month")
            params["month"] = month

        if status is not None:
            conditions.append("sa.status = :status")
            params["status"] = status

        if city:
            conditions.append(
                "LOWER(ci.name) LIKE LOWER(:city)"
            )
            params["city"] = f"%{city.strip()}%"

        if media_type:
            conditions.append(
                "LOWER(s.type) LIKE LOWER(:media_type)"
            )
            params["media_type"] = f"%{media_type.strip()}%"

        if size:
            conditions.append(
                "LOWER(s.size) LIKE LOWER(:size)"
            )
            params["size"] = f"%{size.strip()}%"

        # Site price is TEXT, therefore price limits are applied after
        # mapping to SurfaceRecord instead of comparing TEXT in SQL.
        sql += "\nWHERE " + "\n  AND ".join(conditions)

        sql += """
            ORDER BY
                ci.name,
                s.external_number,
                s.side,
                s.id
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                params,
            ).mappings().all()

        surfaces = [
            SiteSurfaceMapper.map(row)
            for row in rows
        ]

        if min_price is not None:
            surfaces = [
                surface
                for surface in surfaces
                if surface.price is not None
                and surface.price >= min_price
            ]

        if max_price is not None:
            surfaces = [
                surface
                for surface in surfaces
                if surface.price is not None
                and surface.price <= max_price
            ]

        if load_threshold is not None or max_load is not None:
            surface_ids = [
                surface.id
                for surface in surfaces
                if surface.id is not None
            ]

            availability = self.get_availabilities_for_surfaces(
                surface_ids=surface_ids,
                year=year if year is not None else 2026,
                months=[month] if month is not None else None,
            )

            filtered: list[SurfaceRecord] = []

            for surface in surfaces:
                records = availability.get(surface.id, [])

                matched = False

                for item in records:
                    if (
                        load_threshold is not None
                        and (
                            item.load_percent is None
                            or item.load_percent < load_threshold
                        )
                    ):
                        continue

                    if (
                        max_load is not None
                        and (
                            item.load_percent is None
                            or item.load_percent > max_load
                        )
                    ):
                        continue

                    matched = True
                    break

                if matched:
                    filtered.append(surface)

            surfaces = filtered

        return self._filter_surfaces_by_address(
            surfaces,
            address,
        )

    # ------------------------------------------------------------------
    # Address semantics
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_surfaces_by_address(
        surfaces: list[SurfaceRecord],
        address: str | None,
    ) -> list[SurfaceRecord]:

        if not address:
            return surfaces

        from engine.address.parser_v2 import AddressParserV2

        parsed = AddressParserV2.parse(address)

        if not parsed.objects:
            return []

        query_roots = {
            str(value).strip().lower()
            for value in parsed.all_street_roots
            if str(value).strip()
        }

        query_numbers = {
            str(value).strip().lower()
            for value in parsed.house_numbers
            if str(value).strip()
        }

        if not query_roots:
            return []

        result: list[SurfaceRecord] = []

        for surface in surfaces:
            surface_roots = {
                str(value).strip().lower()
                for value in surface.street_roots
                if str(value).strip()
            }

            surface_numbers = {
                str(value).strip().lower()
                for value in surface.house_numbers
                if str(value).strip()
            }

            if not query_roots.issubset(surface_roots):
                continue

            if query_numbers:
                matched = True

                for query_number in query_numbers:
                    best = HouseNumberMatcher.best_match(
                        query_number,
                        list(surface_numbers),
                    )

                    if best is None or best.score <= 0:
                        matched = False
                        break

                if not matched:
                    continue

            result.append(surface)

        return result

    # ------------------------------------------------------------------
    # Generic one-period search
    # ------------------------------------------------------------------

    def find_by_filters_with_availability(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        return self._load_surfaces(
            year=year,
            month=month,
            address=address,
            city=city,
            media_type=media_type,
            size=size,
            min_price=min_price,
            max_price=max_price,
            load_threshold=load_threshold,
            max_load=max_load,
        )

    # ------------------------------------------------------------------
    # Generic ANY
    # ------------------------------------------------------------------

    def find_by_filters_any(
        self,
        *,
        year: int,
        months: list[int],
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        unique_months = sorted(set(months))

        if not unique_months:
            return []

        return self._load_period_surfaces(
            year=year,
            months=unique_months,
            address=address,
            city=city,
            media_type=media_type,
            size=size,
            min_price=min_price,
            max_price=max_price,
            status=None,
            require_all=False,
            load_threshold=load_threshold,
            max_load=max_load,
        )

    # ------------------------------------------------------------------
    # Generic ALL
    # ------------------------------------------------------------------

    def find_by_filters_all(
        self,
        *,
        year: int,
        months: list[int],
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        unique_months = sorted(set(months))

        if not unique_months:
            return []

        return self._load_period_surfaces(
            year=year,
            months=unique_months,
            address=address,
            city=city,
            media_type=media_type,
            size=size,
            min_price=min_price,
            max_price=max_price,
            status=None,
            require_all=True,
            load_threshold=load_threshold,
            max_load=max_load,
        )

    # ------------------------------------------------------------------
    # FREE one period
    # ------------------------------------------------------------------

    def find_free(
        self,
        *,
        year: int,
        month: int,
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        return self._load_surfaces(
            year=year,
            month=month,
            address=address,
            city=city,
            media_type=media_type,
            size=size,
            status="FREE",
            min_price=min_price,
            max_price=max_price,
            load_threshold=load_threshold,
            max_load=max_load,
        )

    # ------------------------------------------------------------------
    # FREE ANY
    # ------------------------------------------------------------------

    def find_free_any(
        self,
        *,
        year: int,
        months: list[int],
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        unique_months = sorted(set(months))

        if not unique_months:
            return []

        return self._load_period_surfaces(
            year=year,
            months=unique_months,
            address=address,
            city=city,
            media_type=media_type,
            size=size,
            min_price=min_price,
            max_price=max_price,
            status="FREE",
            require_all=False,
            load_threshold=load_threshold,
            max_load=max_load,
        )

    # ------------------------------------------------------------------
    # FREE ALL
    # ------------------------------------------------------------------

    def find_free_all(
        self,
        *,
        year: int,
        months: list[int],
        address: str | None = None,
        city: str | None = None,
        media_type: str | None = None,
        size: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        load_threshold: int | None = None,
        max_load: int | None = None,
    ) -> list[SurfaceRecord]:

        unique_months = sorted(set(months))

        if not unique_months:
            return []

        return self._load_period_surfaces(
            year=year,
            months=unique_months,
            address=address,
            city=city,
            media_type=media_type,
            size=size,
            min_price=min_price,
            max_price=max_price,
            status="FREE",
            require_all=True,
            load_threshold=load_threshold,
            max_load=max_load,
        )

    # ------------------------------------------------------------------
    # Period helper
    # ------------------------------------------------------------------

    def _load_period_surfaces(
        self,
        *,
        year: int,
        months: list[int],
        address: str | None,
        city: str | None,
        media_type: str | None,
        size: str | None,
        min_price: int | None,
        max_price: int | None,
        status: str | None,
        require_all: bool,
        load_threshold: int | None,
        max_load: int | None,
    ) -> list[SurfaceRecord]:

        params: dict[str, Any] = {
            "year": year,
        }

        month_params = []

        for index, month in enumerate(months):
            name = f"month_{index}"
            month_params.append(f":{name}")
            params[name] = month

        conditions = [
            "s.is_active = TRUE",
            "sa.year = :year",
            f"sa.month IN ({', '.join(month_params)})",
        ]

        if status is not None:
            conditions.append("sa.status = :status")
            params["status"] = status

        if city:
            conditions.append(
                "LOWER(ci.name) LIKE LOWER(:city)"
            )
            params["city"] = f"%{city.strip()}%"

        if media_type:
            conditions.append(
                "LOWER(s.type) LIKE LOWER(:media_type)"
            )
            params["media_type"] = f"%{media_type.strip()}%"

        if size:
            conditions.append(
                "LOWER(s.size) = LOWER(:size)"
            )
            params["size"] = size.strip()

        sql = self._surface_select()
        sql += """
            JOIN surface_availability sa
              ON sa.surface_id = s.id
        """

        sql += "\nWHERE " + "\n  AND ".join(conditions)

        sql += """
            ORDER BY
                ci.name,
                s.external_number,
                s.side,
                s.id
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                params,
            ).mappings().all()

        # The same surface can occur once per requested month.
        mapped: dict[int, SurfaceRecord] = {}

        for row in rows:
            surface = SiteSurfaceMapper.map(row)

            if surface.id is not None:
                mapped[surface.id] = surface

        surfaces = list(mapped.values())

        if min_price is not None:
            surfaces = [
                surface
                for surface in surfaces
                if surface.price is not None
                and surface.price >= min_price
            ]

        if max_price is not None:
            surfaces = [
                surface
                for surface in surfaces
                if surface.price is not None
                and surface.price <= max_price
            ]

        # Re-evaluate the requested months against the actual availability
        # records. This keeps ALL semantics exact and makes load filtering
        # independent of the TEXT representation used by the site schema.
        availability = self.get_availabilities_for_surfaces(
            surface_ids=[
                surface.id
                for surface in surfaces
                if surface.id is not None
            ],
            year=year,
            months=months,
        )

        filtered: list[SurfaceRecord] = []

        for surface in surfaces:
            records = availability.get(surface.id, [])

            by_month = {
                item.month: item
                for item in records
            }

            valid_months = []

            for month in months:
                item = by_month.get(month)

                if item is None:
                    continue

                if status is not None and item.status != status:
                    continue

                if (
                    load_threshold is not None
                    and (
                        item.load_percent is None
                        or item.load_percent < load_threshold
                    )
                ):
                    continue

                if (
                    max_load is not None
                    and (
                        item.load_percent is None
                        or item.load_percent > max_load
                    )
                ):
                    continue

                valid_months.append(month)

            if require_all:
                if len(set(valid_months)) != len(set(months)):
                    continue
            elif not valid_months:
                continue

            filtered.append(surface)

        return self._filter_surfaces_by_address(
            filtered,
            address,
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @staticmethod
    def _availability(row) -> AvailabilityRecord:
        data = dict(row)

        return AvailabilityRecord(
            id=data.get("id"),
            uuid=(
                str(data["uuid"])
                if data.get("uuid")
                else None
            ),
            surface_id=int(data["surface_id"]),
            year=int(data["year"]),
            month=int(data["month"]),
            status=data["status"],
            price=_price(data.get("price")),
            load_percent=data.get("load_percent"),
            raw_value=data.get("raw_value"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            is_active=data.get("is_active", True),
        )

    def get_availabilities_for_surfaces(
        self,
        *,
        surface_ids: list[int],
        year: int,
        months: list[int] | None = None,
    ) -> dict[int, list[AvailabilityRecord]]:

        if not surface_ids:
            return {}

        params: dict[str, Any] = {
            "year": year,
            "surface_ids": list(surface_ids),
        }

        conditions = [
            "sa.surface_id = ANY(:surface_ids)",
            "sa.year = :year",
            "sa.is_active = TRUE",
        ]

        if months:
            params["months"] = list(sorted(set(months)))
            conditions.append(
                "sa.month = ANY(:months)"
            )

        sql = f"""
            SELECT
                sa.id,
                sa.uuid,
                sa.surface_id,
                sa.year,
                sa.month,
                sa.status,
                sa.price,
                sa.load_percent,
                sa.raw_value,
                sa.created_at,
                sa.updated_at,
                sa.is_active
            FROM surface_availability sa
            WHERE {' AND '.join(conditions)}
            ORDER BY
                sa.surface_id,
                sa.month
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                params,
            ).mappings().all()

        result: dict[int, list[AvailabilityRecord]] = {}

        for row in rows:
            item = self._availability(row)

            result.setdefault(
                item.surface_id,
                [],
            ).append(item)

        return result
