"""Normalization helpers shared by search v2.

The site stores values as human-written TEXT (``1,2 X 1,8 Метр``, type
``Скроллер``), while user queries may use another separator/order or a
synonym. These helpers compare values semantically instead of by string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from engine.dictionary.synonym_dictionary import SynonymDictionary


_SIZE_RE = re.compile(
    r"(?<!\d)(\d+(?:[.,]\d+)?)\s*[xXхХ×*]\s*(\d+(?:[.,]\d+)?)(?!\d)"
)

TYPE_FALLBACKS = {
    # The synonym dictionary maps «скроллер» to «Сити-борд», while the site
    # data stores these surfaces as «Скроллер». Prefer the actual data value,
    # then the related city-format type.
    "сити-борд": ("скроллер", "сити-формат"),
    "ситиборд": ("скроллер", "сити-формат"),
    "скроллер": ("сити-борд",),
}

AREA_MARKERS = ("район", "округ", "р-н", "р-н.")


def normalize_text(value: object) -> str:
    return " ".join(
        str(value or "")
        .casefold()
        .replace("ё", "е")
        .split()
    )


def is_area_name(value: object) -> bool:
    text = normalize_text(value)
    return any(marker in text for marker in AREA_MARKERS)


@dataclass(frozen=True)
class SizeDimensions:
    major: float
    minor: float


def parse_dimensions(value: object) -> SizeDimensions | None:
    """Parse ``1,2 X 1,8`` / ``1.8x1.2`` into sorted dimensions."""
    match = _SIZE_RE.search(str(value or ""))

    if not match:
        return None

    try:
        first = float(match.group(1).replace(",", "."))
        second = float(match.group(2).replace(",", "."))
    except ValueError:
        return None

    major, minor = sorted((first, second), reverse=True)
    return SizeDimensions(major=major, minor=minor)


def same_size(
    left: object,
    right: object,
    *,
    abs_tol: float = 0.01,
) -> bool:
    first = (
        left if isinstance(left, SizeDimensions) else parse_dimensions(left)
    )
    second = (
        right if isinstance(right, SizeDimensions) else parse_dimensions(right)
    )

    if first is None or second is None:
        return False

    return (
        abs(first.major - second.major) <= abs_tol
        and abs(first.minor - second.minor) <= abs_tol
    )


class TypeResolver:
    """Resolve user type words against the types that really exist."""

    def __init__(
        self,
        types: Iterable[str],
        dictionary: SynonymDictionary | None = None,
    ) -> None:
        self.dictionary = dictionary
        self.by_norm: dict[str, str] = {}

        for value in types:
            text = str(value or "").strip()
            if text:
                self.by_norm.setdefault(normalize_text(text), text)

    def resolve(self, value: object) -> tuple[str | None, str | None]:
        text = str(value or "").strip()

        if not text:
            return None, None

        candidates: list[str] = [text]

        if self.dictionary is not None:
            canonical = (
                self.dictionary.find_type(text)
                or self.dictionary.find_keyword(text)
            )
            if canonical and normalize_text(canonical) != normalize_text(text):
                candidates.append(canonical)

        for candidate in candidates:
            key = normalize_text(candidate)
            if key in self.by_norm:
                return self.by_norm[key], None

        for candidate in candidates:
            key = normalize_text(candidate)

            for fallback in TYPE_FALLBACKS.get(key, ()):
                if fallback in self.by_norm:
                    return (
                        self.by_norm[fallback],
                        f"Тип «{text}» заменён на «{self.by_norm[fallback]}»: в базе нет первого варианта",
                    )

        available = ", ".join(sorted(self.by_norm.values()))
        return (
            None,
            f"Тип «{text}» отсутствует в базе. Доступны: {available}",
        )


def _common_prefix_length(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0

    while index < limit and left[index] == right[index]:
        index += 1

    return index


class LocationResolver:
    """Resolve city and area words against actual catalog values."""

    def __init__(self, cities: Iterable[str], areas: Iterable[str]) -> None:
        self.cities = {
            normalize_text(value): str(value).strip()
            for value in cities
            if str(value or "").strip()
        }
        self.areas = {
            normalize_text(value): str(value).strip()
            for value in areas
            if str(value or "").strip()
        }

    def resolve_city(self, value: object) -> str | None:
        text = normalize_text(value)
        if not text:
            return None

        if text in self.cities:
            return self.cities[text]

        matches = [
            (key, actual)
            for key, actual in self.cities.items()
            if text in key
        ]

        if matches:
            return max(matches, key=lambda item: len(item[0]))[1]

        return None

    def resolve_area(self, value: object) -> str | None:
        text = normalize_text(value)
        if not text:
            return None

        if text in self.areas:
            return self.areas[text]

        matches = [
            (key, actual)
            for key, actual in self.areas.items()
            if text in key
        ]

        if matches:
            return max(matches, key=lambda item: len(item[0]))[1]

        # Inflected forms: «Октябрьском» vs «ОКТЯБРЬСКИЙ РАЙОН».
        prefix_matches = [
            (_common_prefix_length(text, key), actual)
            for key, actual in self.areas.items()
            if _common_prefix_length(text, key) >= 4
        ]

        if prefix_matches:
            return max(prefix_matches, key=lambda item: item[0])[1]

        return None
