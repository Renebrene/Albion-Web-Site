"""Public geocoding endpoints for the address/point search UI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, FiniteFloat, field_validator

from backend.services import geocoding_service as geo


router = APIRouter(prefix="/api/geo", tags=["geo"])


class AddressQuery(BaseModel):
    query: str = Field(min_length=3, max_length=320)

    @field_validator("query")
    @classmethod
    def normalize(cls, value: str) -> str:
        text = " ".join(value.split())
        if len(text) < 3 or any(ord(char) < 32 for char in text):
            raise ValueError("Введите не менее 3 символов")
        return text


class SuggestQuery(AddressQuery):
    limit: int = Field(default=8, ge=1, le=10)


class ReverseQuery(BaseModel):
    lat: FiniteFloat = Field(ge=-90, le=90)
    lon: FiniteFloat = Field(ge=-180, le=180)


def _http_error(exc: geo.GeocodingError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/status")
def status() -> dict:
    return {
        "geocoder_configured": bool(geo.geocoder_key()),
        "suggest_configured": bool(geo.suggest_key()),
        "region": "Ростовская область",
    }


@router.post("/geocode")
async def geocode(payload: AddressQuery) -> dict:
    try:
        return await geo.geocode_address(payload.query)
    except geo.GeocodingError as exc:
        raise _http_error(exc) from exc


@router.post("/reverse")
async def reverse(payload: ReverseQuery) -> dict:
    try:
        return await geo.reverse_geocode(payload.lat, payload.lon)
    except geo.GeocodingError as exc:
        raise _http_error(exc) from exc


@router.post("/suggest")
async def suggest(payload: SuggestQuery) -> dict:
    try:
        suggestions = await geo.suggest_address(payload.query, payload.limit)
    except geo.GeocodingError as exc:
        raise _http_error(exc) from exc

    return {
        "suggestions": suggestions,
        "source": "Yandex Geosuggest",
    }
