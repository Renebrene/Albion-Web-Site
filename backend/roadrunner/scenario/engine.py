"""
Движок сценариев для программной дороги Альбион.

Сценарии — это последовательность событий с временными метками.
Движок воспроизводит их в реальном времени, управляя сценой.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

from backend.services.data_service import get_connection

logger = logging.getLogger(__name__)

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "api" / "scenarios"

# Имя файлового сценария: slug без слэшей и «..». Разрешаем буквы, цифры,
# дефис, подчёркивание и необязательное расширение .json.
_SCENARIO_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(?:\.json)?$")


class ScenarioError(Exception):
    """Ошибка сценария."""


def _scenario_path(scenario_path: str) -> Path:
    """Безопасно превращает slug в путь внутри SCENARIOS_DIR.

    Раньше ``scenario_id`` подставлялся в путь как есть: ``..`` открывал
    каталог, и GET /scenarios/.. падал с 500 (IsADirectoryError). Теперь
    имя валидируется, а результат обязан остаться внутри каталога.
    """
    value = str(scenario_path or "").strip()

    if not _SCENARIO_NAME_RE.fullmatch(value):
        raise ScenarioError("Сценарий не найден")

    root = SCENARIOS_DIR.resolve()
    path = (root / value).resolve()

    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ScenarioError("Сценарий не найден") from exc

    if path.is_file():
        return path

    # slug может приходить без расширения — пробуем тот же файл с .json.
    if not value.endswith(".json"):
        candidate = (root / f"{value}.json").resolve()

        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ScenarioError("Сценарий не найден") from exc

        if candidate.is_file():
            return candidate

    raise ScenarioError("Сценарий не найден")


class ScenarioEngine:
    """Воспроизводит сценарий в реальном времени."""

    def __init__(
        self,
        scenario_id: str | None = None,
        events: list[dict] | None = None,
        duration: int = 60,
        on_event: Callable[[str, dict], None] | None = None,
    ):
        self.scenario_id = scenario_id
        self.events = events or []
        self.duration = duration
        self.on_event = on_event
        self._current_index = 0
        self._started_at: float | None = None
        self._running = False

    @classmethod
    def from_file(cls, scenario_path: str) -> "ScenarioEngine":
        """Загрузить сценарий из JSON-файла."""
        path = _scenario_path(scenario_path)

        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Не удалось прочитать сценарий %s: %s", path, exc
            )
            raise ScenarioError("Сценарий не найден") from exc

        if not isinstance(data, dict):
            raise ScenarioError("Сценарий не найден")

        return cls(
            scenario_id=data.get("id"),
            events=data.get("events", []),
            duration=data.get("duration", 60),
        )

    @classmethod
    def from_db(cls, scenario_id: int) -> "ScenarioEngine":
        """Загрузить сценарий из БД."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT scenario_data FROM roadrunner_scenarios WHERE id = %s",
                (scenario_id,),
            ).fetchone()

        if not row:
            raise ScenarioError(f"Сценарий не найден: id={scenario_id}")

        from backend.roadrunner.services.db_json import as_dict

        data = as_dict(row[0])
        return cls(
            scenario_id=data.get("id"),
            events=data.get("events", []),
            duration=data.get("duration", 60),
        )

    def start(self):
        """Запустить воспроизведение."""
        self._started_at = self._now()
        self._current_index = 0
        self._running = True
        logger.info(
            "Сценарий запущен: id=%s, events=%d, duration=%ds",
            self.scenario_id,
            len(self.events),
            self.duration,
        )

    def stop(self):
        """Остановить воспроизведение."""
        self._running = False
        logger.info("Сценарий остановлен")

    def tick(self, current_time: float):
        """
        Проверить события на текущий момент времени.

        Args:
            current_time: Текущее время в секундах от начала сценария.
        """
        if not self._running:
            return

        while (
            self._current_index < len(self.events)
            and self.events[self._current_index]["t"] <= current_time
        ):
            event = self.events[self._current_index]
            do = event["do"]
            params = event.get("params", {})

            if self.on_event:
                self.on_event(do, params)

            logger.debug("Событие: %s=%s", do, params)
            self._current_index += 1

        if self._current_index >= len(self.events):
            self.stop()

    def _now(self) -> float:
        """Текущее время в секундах от начала."""
        if self._started_at is None:
            return 0.0

        import time

        return time.time() - self._started_at

    def is_running(self) -> bool:
        return self._running

    def progress(self) -> float:
        """Прогресс воспроизведения 0..1."""
        if not self._started_at:
            return 0.0

        elapsed = self._now()
        return min(1.0, elapsed / self.duration)


def load_all_scenarios() -> list[dict]:
    """Загрузить все сценарии из папки."""
    scenarios = []

    if not SCENARIOS_DIR.exists():
        return scenarios

    for path in SCENARIOS_DIR.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            scenarios.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Не удалось загрузить сценарий %s: %s", path, exc)

    return scenarios


VALID_SCENARIO_ACTIONS = {
    "start_traffic",
    "stop_traffic",
    "change_traffic_density",
    "add_car",
    "remove_car",
    "change_speed",
    "add_bus",
    "remove_bus",
    "add_pedestrian",
    "remove_pedestrian",
    "change_traffic_light_phase",
    "change_weather",
    "add_holiday_decor",
    "remove_holiday_decor",
    "start_rain",
    "stop_rain",
    "start_snow",
    "stop_snow",
    "change_time_of_day",
    "add_vehicle",
    "remove_vehicle",
    "end",
}

# LLM иногда придумывает близкие действия. Маппим только очевидные алиасы,
# чтобы не отклонять валидный по смыслу сценарий из-за имени действия.
_SCENARIO_ACTION_ALIASES = {
    "start_fog": ("change_weather", {"condition": "fog"}),
    "fog_on": ("change_weather", {"condition": "fog"}),
    "enable_fog": ("change_weather", {"condition": "fog"}),
    "stop_fog": ("change_weather", {"condition": "clear"}),
    "fog_off": ("change_weather", {"condition": "clear"}),
    "disable_fog": ("change_weather", {"condition": "clear"}),
    "start_storm": ("change_weather", {"condition": "storm"}),
    "stop_storm": ("change_weather", {"condition": "clear"}),
}


def normalize_scenario_actions(data: dict) -> dict:
    """Нормализовать очевидные алиасы действий LLM перед валидацией."""
    events = data.get("events")
    if not isinstance(events, list):
        return data

    normalized = []
    for event in events:
        if not isinstance(event, dict):
            normalized.append(event)
            continue
        do = event.get("do")
        alias = _SCENARIO_ACTION_ALIASES.get(do)
        if alias is None:
            normalized.append(event)
            continue
        mapped_do, mapped_params = alias
        merged_params = dict(mapped_params)
        params = event.get("params")
        if isinstance(params, dict):
            merged_params.update(params)
        new_event = dict(event)
        new_event["do"] = mapped_do
        new_event["params"] = merged_params
        normalized.append(new_event)

    result = dict(data)
    result["events"] = normalized
    return result


def validate_scenario(data: dict) -> list[str]:
    """
    Валидировать сценарий по схеме.

    Возвращает список ошибок. Пустой список — валидный сценарий.
    """
    errors = []

    required = ["id", "name", "duration", "events"]
    for field in required:
        if field not in data:
            errors.append(f"Отсутствует поле: {field}")

    if "events" in data and not isinstance(data["events"], list):
        errors.append("events должен быть массивом")

    valid_dos = VALID_SCENARIO_ACTIONS

    for i, event in enumerate(data.get("events", [])):
        if "t" not in event:
            errors.append(f"Событие #{i}: отсутствует 't'")
        if "do" not in event:
            errors.append(f"Событие #{i}: отсутствует 'do'")
        elif event["do"] not in valid_dos:
            errors.append(
                f"Событие #{i}: неизвестное действие '{event['do']}'"
            )

    return errors
