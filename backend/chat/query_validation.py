"""Валидация сущностей, извлечённых LLM.

LLM — недоверенный источник: она может вернуть ``null`` вместо всех полей,
строки вместо чисел, месяц 13 или отрицательный лимит. Здесь всё приводится
к безопасным типам/диапазонам до построения ``SearchQuery``.
"""

from __future__ import annotations

from typing import Any

from engine.dictionary.synonym_dictionary import SynonymDictionary


ALLOWED_KEYS = {
    "city",
    "district",
    "address",
    "media_type",
    "size",
    "month",
    "months",
    "year",
    "availability",
    "min_price",
    "max_price",
    "min_load",
    "max_load",
    "sort_by",
    "limit",
}

TEXT_LIMITS = {
    "city": 100,
    "district": 100,
    "address": 300,
    "media_type": 100,
    "size": 50,
}

EMPTY_VALUES = (None, "", [], {})

# Поля, которые реально сужают выдачу. Год/лимит/сортировка сами по себе
# не считаются запросом: иначе «весь каталог за 2026 год» снова вернулся бы.
SUBSTANTIVE_KEYS = {
    "city",
    "district",
    "address",
    "media_type",
    "size",
    "month",
    "months",
    "availability",
    "min_price",
    "max_price",
    "min_load",
    "max_load",
}


def _is_meaningful(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())

    return value not in EMPTY_VALUES


def meaningful(values: dict[str, Any]) -> bool:
    """True, если есть хотя бы одно поле, реально сужающее выдачу."""
    return any(
        _is_meaningful(value)
        for key, value in (values or {}).items()
        if key in SUBSTANTIVE_KEYS
    )


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).split())
    return text[:limit] or None


def _int(
    value: Any,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "null", "none", "нет", "не указано"}:
            return None
    elif value == "":
        return None

    if isinstance(value, bool):
        raise ValueError("boolean не является числом")

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        import re

        # Accept «90%», «90 процентов», «до 90».
        match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
        if not match:
            raise ValueError(f"не число: {value!r}")
        number = float(match.group(0).replace(",", "."))

    result = int(round(number))

    if minimum is not None and result < minimum:
        raise ValueError(f"значение {result} меньше {minimum}")

    if maximum is not None and result > maximum:
        raise ValueError(f"значение {result} больше {maximum}")

    return result


def _canonical_city(
    dictionary: SynonymDictionary,
    value: Any,
) -> str | None:
    text = _text(value, TEXT_LIMITS["city"])
    if not text:
        return None

    canonical = dictionary.find_city(text)
    if canonical:
        return canonical

    # LLM often returns an inflected form («Таганроге», «Шахтах»), while the
    # dictionary stores the nominative alias. Match by a long common prefix.
    normalized = " ".join(
        text.casefold().replace("ё", "е").split()
    )
    best: tuple[int, str] | None = None

    for alias, city in dictionary.city_map.items():
        prefix = 0
        limit = min(len(alias), len(normalized))

        while prefix < limit and alias[prefix] == normalized[prefix]:
            prefix += 1

        if prefix >= 4 and (best is None or prefix > best[0]):
            best = (prefix, city)

    return best[1] if best else text


def _canonical_type(
    dictionary: SynonymDictionary,
    value: Any,
) -> str | None:
    text = _text(value, TEXT_LIMITS["media_type"])
    if not text:
        return None

    return (
        dictionary.find_type(text)
        or dictionary.find_keyword(text)
        or text
    )


def validate_llm_entities(
    values: dict[str, Any],
    dictionary: SynonymDictionary,
) -> tuple[dict[str, Any], list[str]]:
    """Нормализует поля LLM и возвращает (clean, warnings).

    Никогда не бросает исключение на «мусорных» полях: неподходящее
    значение отбрасывается с предупреждением, чтобы остальные ограничения
    запроса остались рабочими.
    """
    clean: dict[str, Any] = {}
    warnings: list[str] = []

    raw = {
        key: value
        for key, value in (values or {}).items()
        if key in ALLOWED_KEYS
    }

    for key, limit in TEXT_LIMITS.items():
        if key not in raw:
            continue

        try:
            if key == "city":
                value = _canonical_city(dictionary, raw[key])
            elif key == "media_type":
                value = _canonical_type(dictionary, raw[key])
            elif key == "size":
                from engine.size.normalizer import QuerySizeNormalizer

                value = QuerySizeNormalizer.normalize(
                    _text(raw[key], limit)
                )
            else:
                value = _text(raw[key], limit)
        except (TypeError, ValueError) as exc:
            warnings.append(f"Поле {key} отброшено: {exc}")
            continue

        if value:
            clean[key] = value

    months: list[int] = []

    if raw.get("month") is not None:
        try:
            months.append(_int(raw["month"], minimum=1, maximum=12))
        except (TypeError, ValueError) as exc:
            warnings.append(f"month отброшен: {exc}")

    if raw.get("months") is not None:
        value = raw["months"]

        if not isinstance(value, (list, tuple)):
            warnings.append("months должен быть списком")
        else:
            for item in value:
                try:
                    month = _int(item, minimum=1, maximum=12)
                except (TypeError, ValueError) as exc:
                    warnings.append(f"month отброшен: {exc}")
                    continue

                if month is not None:
                    months.append(month)

    months = list(dict.fromkeys(months))

    if len(months) == 1:
        clean["month"] = months[0]
    elif months:
        clean["months"] = months

    if raw.get("year") is not None:
        try:
            clean["year"] = _int(raw["year"], minimum=2000, maximum=2100)
        except (TypeError, ValueError) as exc:
            warnings.append(f"year отброшен: {exc}")

    availability = raw.get("availability")

    if availability is not None and str(availability).strip():
        value = str(availability).strip().upper()

        if value in {"FREE", "СВОБОДНО", "СВОБОДНЫЕ", "СВОБОДНЫЙ"}:
            clean["availability"] = "FREE"
        else:
            warnings.append(
                f"availability «{availability}» отброшен: поддерживается FREE"
            )

    for key, label, maximum in (
        ("min_price", "min_price", 100_000_000),
        ("max_price", "max_price", 100_000_000),
        ("min_load", "min_load", 100),
        ("max_load", "max_load", 100),
    ):
        if raw.get(key) is None:
            continue

        try:
            clean[key] = _int(
                raw[key],
                minimum=0,
                maximum=maximum,
            )
        except (TypeError, ValueError) as exc:
            warnings.append(f"{label} отброшен: {exc}")

    if (
        clean.get("min_price") is not None
        and clean.get("max_price") is not None
        and clean["min_price"] > clean["max_price"]
    ):
        warnings.append("min_price больше max_price — ценовой диапазон отброшен")
        clean.pop("min_price", None)
        clean.pop("max_price", None)

    if (
        clean.get("min_load") is not None
        and clean.get("max_load") is not None
        and clean["min_load"] > clean["max_load"]
    ):
        warnings.append("min_load больше max_load — диапазон загрузки отброшен")
        clean.pop("min_load", None)
        clean.pop("max_load", None)

    # «До 90%» models often return min_load=max_load=90. Treat equal bounds
    # as an upper limit, otherwise the search requires exactly 90%.
    if (
        clean.get("min_load") is not None
        and clean.get("max_load") is not None
        and clean["min_load"] == clean["max_load"]
    ):
        clean.pop("min_load", None)

    if raw.get("limit") is not None:
        try:
            clean["limit"] = _int(raw["limit"], minimum=1, maximum=1000)
        except (TypeError, ValueError) as exc:
            warnings.append(f"limit отброшен: {exc}")

    sort_by = raw.get("sort_by")

    if sort_by is not None:
        value = str(sort_by).strip().lower()
        aliases = {
            "price": "price_asc",
            "price_asc": "price_asc",
            "дешевле": "price_asc",
            "дешёвые": "price_asc",
            "дешевые": "price_asc",
            "load": "load_asc",
            "load_asc": "load_asc",
            "загрузка": "load_asc",
        }

        if value in aliases:
            clean["sort_by"] = aliases[value]
        elif value:
            warnings.append(f"sort_by «{sort_by}» отброшен")

    # Year/limit/sort alone do not narrow anything (they would return the
    # whole catalog); treat such a response as an unsuccessful extraction.
    if not meaningful(clean):
        return {}, warnings

    return clean, warnings
