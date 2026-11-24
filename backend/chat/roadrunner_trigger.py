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
    # Быстрые кнопки со сценариями в ответе чата.
    prompts: list[str] = None
    # Сценарий, соответствующий одному из примеров (если запрос точный).
    scenario: dict = None


# Готовые сценарии: каждый использует другой набор настроек проекции.
# banner применяет события, а по окончании возвращается к коду из БД.
EXAMPLE_SCENARIOS = [
    {
        "prompt": "Ночная гроза: молнии, поток 2×, камера «Угол улицы»",
        "name": "Ночная гроза",
        "duration": 45,
        "events": [
            {"t": 0, "do": "change_time_of_day", "params": {"phase": "night"}},
            {"t": 1, "do": "change_weather", "params": {"condition": "storm"}},
            {"t": 2, "do": "change_traffic_density", "params": {"density": 2.0}},
            {"t": 43, "do": "end"},
        ],
    },
    {
        "prompt": "Новогодний вечер: снег, ёлки, гирлянды, камера «Остановка»",
        "name": "Новогодний вечер",
        "duration": 50,
        "events": [
            {"t": 0, "do": "change_weather", "params": {"condition": "snow"}},
            {"t": 1, "do": "add_holiday_decor", "params": {"type": "new-year"}},
            {"t": 2, "do": "change_speed", "params": {"factor": 0.7}},
            {"t": 48, "do": "end"},
        ],
    },
    {
        "prompt": "Утренний час пик: пробки 8, поток 3×, камера «Сверху»",
        "name": "Утренний час пик",
        "duration": 40,
        "events": [
            {"t": 0, "do": "change_traffic_density", "params": {"density": 3.0}},
            {"t": 1, "do": "change_speed", "params": {"factor": 0.6}},
            {"t": 2, "do": "change_time_of_day", "params": {"phase": "morning"}},
            {"t": 38, "do": "end"},
        ],
    },
    {
        "prompt": "Тихий день: ясно, скорость 0.6×, без праздника",
        "name": "Тихий день",
        "duration": 35,
        "events": [
            {"t": 0, "do": "change_weather", "params": {"condition": "clear"}},
            {"t": 1, "do": "change_speed", "params": {"factor": 0.6}},
            {"t": 2, "do": "change_traffic_density", "params": {"density": 0.8}},
            {"t": 33, "do": "end"},
        ],
    },
    {
        "prompt": "День Победы: флаги, гирлянды, яркий свет, камера «Фронт»",
        "name": "День Победы",
        "duration": 45,
        "events": [
            {"t": 0, "do": "add_holiday_decor", "params": {"type": "victory-day"}},
            {"t": 1, "do": "change_time_of_day", "params": {"phase": "day"}},
            {"t": 2, "do": "change_weather", "params": {"condition": "clear"}},
            {"t": 43, "do": "end"},
        ],
    },
]

EXAMPLE_PROMPTS = [item["prompt"] for item in EXAMPLE_SCENARIOS]

EXIT_PROMPT = "выход"
EXIT_WORDS = ("выход", "выйти", "exit", "вернись", "обычный режим")


def is_exit_command(text: str) -> bool:
    """Команда выхода из пасхалки."""
    normalized = " ".join((text or "").lower().split())
    return any(word in normalized for word in EXIT_WORDS)


def match_example_scenario(text: str) -> dict | None:
    """Найти готовый сценарий по точному тексту подсказки."""
    normalized = " ".join((text or "").lower().split())
    for item in EXAMPLE_SCENARIOS:
        if " ".join(item["prompt"].lower().split()) == normalized:
            return {
                "id": "chat-" + item["name"].lower().replace(" ", "-"),
                "name": item["name"],
                "duration": item["duration"],
                "events": item["events"],
            }
    return None


def check_roadrunner_trigger(text: str) -> RoadrunnerTrigger:
    """
    Проверить, содержит ли текст ключевые слова Roadrunner.

    Args:
        text: Текст сообщения пользователя.

    Returns:
        RoadrunnerTrigger с результатами проверки.
    """
    text_lower = text.lower().strip()
    matched_scenario = match_example_scenario(text)

    # Проверка ключевых слов
    for keyword in ROADRUNNER_KEYWORDS:
        if keyword in text_lower:
            return RoadrunnerTrigger(
                active=True,
                mode="roadrunner",
                suggestion=_get_suggestion(text_lower),
                parameters=_get_parameters(),
                prompts=EXAMPLE_PROMPTS,
                scenario=matched_scenario
            )

    # Проверка паттернов
    for pattern in ROADRUNNER_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return RoadrunnerTrigger(
                active=True,
                mode="roadrunner",
                suggestion=_get_suggestion(text_lower),
                parameters=_get_parameters(),
                prompts=EXAMPLE_PROMPTS,
                scenario=matched_scenario
            )

    return RoadrunnerTrigger(
        active=False,
        mode="default",
        suggestion="",
        parameters=[],
        prompts=[],
        scenario=None
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
        "**Готовые сценарии (нажмите кнопку ниже):**",
    ])
    for prompt in EXAMPLE_PROMPTS:
        lines.append(f"• {prompt}")

    lines.extend([
        "",
        "После окончания сценария баннер вернётся к настройкам по умолчанию "
        "из базы данных.",
    ])

    return "\n".join(lines)
