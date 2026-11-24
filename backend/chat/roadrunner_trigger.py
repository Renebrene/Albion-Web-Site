"""
Триггеры для умного чата — активация режима Roadrunner.

Ключевые слова: «светофор», «светофоры», «дорога», «баннер», «roadrunner».
При совпадении чат входит в режим написания сценариев и показывает
подсказки о параметрах.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# Ключевые слова, активирующие режим Roadrunner
ROADRUNNER_KEYWORDS = [
    "светофор",
    "светофоры",
    "дорога",
    "баннер",
    "roadrunner",
    "программная дорога",
    "3d дорога",
    "анимация дороги",
]

# Паттерны для более точного распознавания
ROADRUNNER_PATTERNS = [
    r"\bсветофор[ы]?\b",
    r"\bдорог[аы]\b",
    r"\bбаннер[аов]?\b",
    r"\broadrunner\b",
    r"\bпрограммная\s+дорога\b",
    r"\b3d\s+дорога\b",
    r"\bанимация\s+дороги\b",
]


@dataclass
class RoadrunnerTrigger:
    """Результат проверки триггера."""

    active: bool
    mode: str = "default"  # "default" или "roadrunner"
    suggestion: str = ""
    parameters: list[str] = None


def check_roadrunner_trigger(text: str) -> RoadrunnerTrigger:
    """
    Проверить, содержит ли текст ключевые слова Roadrunner.

    Args:
        text: Текст сообщения пользователя.

    Returns:
        RoadrunnerTrigger с результатами проверки.
    """
    text_lower = text.lower().strip()

    # Проверка ключевых слов
    for keyword in ROADRUNNER_KEYWORDS:
        if keyword in text_lower:
            return RoadrunnerTrigger(
                active=True,
                mode="roadrunner",
                suggestion=_get_suggestion(text_lower),
                parameters=_get_parameters()
            )

    # Проверка паттернов
    for pattern in ROADRUNNER_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return RoadrunnerTrigger(
                active=True,
                mode="roadrunner",
                suggestion=_get_suggestion(text_lower),
                parameters=_get_parameters()
            )

    return RoadrunnerTrigger(
        active=False,
        mode="default",
        suggestion="",
        parameters=[]
    )


def _get_suggestion(text: str) -> str:
    """Получить подсказку в зависимости от запроса."""
    if "санта" in text or "новый год" in text or "нов year" in text:
        return (
            "Хочу добавить Санта Клауса на санях с оленями? "
            "Могу сгенерировать сценарий для Нового года: снег, ёлки, "
            "снеговик, салют. Напишите: 'сгенерировать новогодний сценарий'."
        )
    elif "дождь" in text or "дождик" in text:
        return (
            "Хочу вечерний дождь? Могу создать сценарий: дождь, "
            "машины едут медленно, пешеходы с зонтами. "
            "Напишите: 'сгенерировать вечерний дождь'."
        )
    elif "победа" in text or "9 мая" in text:
        return (
            "Хочу День Победы? Могу добавить: флаги победы, танки, "
            "салют. Напишите: 'сгенерировать сценарий 9 Мая'."
        )
    elif "погода" in text or "пробки" in text:
        return (
            "Хочу live-данные? Погода и пробки подтягиваются автоматически "
            "из Open-Meteo и модели пробок. Настройте в 'Баннер-дорога'."
        )
    elif "сценарий" in text or "создать" in text:
        return (
            "Могу сгенерировать сценарий через AI. "
            "Опишите на естественном языке, что хотите увидеть на дороге. "
            "Например: 'вечерний дождь, машины едут медленно, пешеходы с зонтами'."
        )
    else:
        return (
            "Могу помочь с 3D-баннером 'Светофорные объекты'. "
            "Сгенерирую сценарий, настрою погоду/пробки, добавлю праздники. "
            "Опишите что хотите увидеть!"
        )


def _get_parameters() -> list[str]:
    """Список параметров, которые можно менять."""
    return [
        "Наклон камеры (5-85°)",
        "Поворот камеры (-180..180°)",
        "Масштаб (0.5-2.0×)",
        "Цикл день/ночь (10-180 с)",
        "Амплитуда волны скорости (0-0.8)",
        "Плотность трафика (0.2-3.0×)",
        "Количество машин (1-14)",
        "Количество пешеходов (0-8)",
        "Погода (clear/cloudy/rain/snow/fog)",
        "Пробки (модель по времени пик)",
        "Праздники (Новый год, 9 Мая, День Альбиона)",
        "Качество рендеринга (eco/balanced/max)",
    ]


def format_roadrunner_suggestion(trigger: RoadrunnerTrigger) -> str:
    """
    Сформировать ответ чата в режиме Roadrunner.

    Args:
        trigger: Результат проверки триггера.

    Returns:
        Форматированный текст ответа.
    """
    if not trigger.active:
        return ""

    lines = [
        "🎬 **Режим Roadrunner активирован**",
        "",
        trigger.suggestion,
        "",
        "**Можно настроить:**",
    ]

    for param in trigger.parameters:
        lines.append(f"• {param}")

    lines.extend([
        "",
        "Напишите 'сгенерировать сценарий' + описание, или откройте "
        "'Баннер-дорога' в админке для ручного редактирования.",
    ])

    return "\n".join(lines)
