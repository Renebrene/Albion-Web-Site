"""Распознавание «населённый пункт из запроса» для умного чата.

Пока НЕ подключено к ChatService: отдельный слой, который можно тестировать.
Ничего не сохраняет. Ориентируется на запрос: «найди конструкции в районе
посёлка Красный Колос», «щиты рядом с селом …», «в посёлке …» и т.п.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from backend.search.spatial import RADIUS_M_DEFAULT

LEADING_VERBS = (
    "найди конструкции", "найдите конструкции", "покажи конструкции",
    "покажите конструкции", "подбери конструкции", "подберите конструкции",
    "найди", "найдите", "покажи", "покажите", "подбери", "подберите",
    "выбери", "выберите", "дай", "дайте",
    "конструкции", "конструкция", "баннеры", "щиты", "щит", "реклама",
    "свободные", "свободную", "свободный",
)

SETTLEMENT_MARKERS = (
    "населённый пункт", "населенный пункт", "посёлок городского типа",
    "поселок городского типа", "рабочий посёлок", "рабочий поселок",
    "дачный посёлок", "дачный поселок", "посёлок", "поселок", "пос.", "пос",
    "деревня", "село", "станица", "хутор", "аул", "н.п.", "нп",
    "с.", "д.", "ст.", "х.", "п.", "с", "д", "п",
)

AREA_MARKERS = ("район", "округ", "р-н", "р-н.")

AREA_PREPOSITIONS = (
    "в районе посёлка", "в районе поселка", "в посёлке", "в поселке",
    "в селе", "в деревне", "в станице", "в хуторе", "в ауле", "в городе",
    "в районе", "на территории", "в микрорайоне",
    "рядом с", "около", "возле", "у",
)

TYPE_CUES = (
    "щит", "призматрон", "сити", "пиллар", "видеоэкран", "экран",
    "баннер", "конструкци", "статик", "динамик", "формат", "размер",
    "свободн", "занят", "резерв", "цен", "дешевле", "дороже",
    "первые", "лимит", "в июне", "в июле", "в августе", "в сентябре",
    "в октябре", "в ноябре", "в декабре", "в январе", "в феврале",
    "в марте", "в апреле", "в мае",
)


@dataclass(frozen=True)
class AreaIntent:
    settlement: str
    settlement_norm: str
    kind_hint: Optional[str] = None
    radius_m: int = RADIUS_M_DEFAULT
    raw: str = ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower().replace("ё", "е"))


def _strip_leading_verbs(text: str) -> str:
    result = text
    while True:
        for verb in sorted(LEADING_VERBS, key=len, reverse=True):
            if _norm(result) == _norm(verb):
                return ""
            if _norm(result).startswith(_norm(verb) + " "):
                result = result[len(verb):].strip()
                break
        else:
            return result


def _trim_name(text: str) -> str:
    tokens = text.strip().strip(",.;:").split()
    kept: list[str] = []
    for token in tokens:
        low = token.lower().strip(",.;:")
        if any(low.startswith(cue) for cue in TYPE_CUES):
            break
        kept.append(token)
    return " ".join(kept).strip(",.;:").strip()


def parse_area_intent(text: str) -> Optional[AreaIntent]:
    """Вернуть населённый пункт из запроса или None, если его нет."""
    if not text:
        return None

    raw = text
    normalized = _norm(_strip_leading_verbs(raw))

    kind_hint: Optional[str] = None
    for marker in AREA_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", normalized):
            kind_hint = "район"
            break

    name: Optional[str] = None
    for prep in sorted(AREA_PREPOSITIONS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(_norm(prep))}\s+(.+)$", normalized)
        if not match:
            continue
        rest = match.group(1).strip()
        for marker in sorted(SETTLEMENT_MARKERS, key=len, reverse=True):
            marker_norm = _norm(marker)
            if rest == marker_norm:
                rest = ""
                kind_hint = kind_hint or "посёлок"
                break
            if rest.startswith(marker_norm + " "):
                rest = rest[len(marker_norm):].strip()
                kind_hint = kind_hint or "посёлок"
                break
            if rest.startswith(marker_norm + "."):
                rest = rest[len(marker_norm) + 1:].strip()
                kind_hint = kind_hint or "посёлок"
                break
        name = rest
        break

    if name is None:
        for marker in sorted(SETTLEMENT_MARKERS, key=len, reverse=True):
            marker_norm = _norm(marker)
            match = re.search(rf"\b{re.escape(marker_norm)}\s+(.+)$", normalized)
            if match:
                name = match.group(1).strip()
                kind_hint = kind_hint or "посёлок"
                break
            match = re.search(rf"\b{re.escape(marker_norm)}\.\s*(.+)$", normalized)
            if match:
                name = match.group(1).strip()
                kind_hint = kind_hint or "посёлок"
                break

    if not name:
        return None

    name = _trim_name(name)
    if not name:
        return None

    return AreaIntent(
        settlement=name,
        settlement_norm=_norm(name),
        kind_hint=kind_hint,
        radius_m=RADIUS_M_DEFAULT,
        raw=raw,
    )
