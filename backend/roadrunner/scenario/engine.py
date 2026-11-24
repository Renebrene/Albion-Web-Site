"""
Движок сценариев для программной дороги Альбион.

Сценарии — это последовательность событий с временными метками.
Движок воспроизводит их в реальном времени, управляя сценой.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from backend.services.data_service import get_connection

logger = logging.getLogger(__name__)

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "api" / "scenarios"


class ScenarioError(Exception):
    """Ошибка сценария."""


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
        path = SCENARIOS_DIR / scenario_path

        # id сценария не совпадает с именем файла (.json), поэтому пробуем
        # сначала как есть, затем — с расширением.
        if not path.exists() and not scenario_path.endswith(".json"):
            candidate = SCENARIOS_DIR / f"{scenario_path}.json"
            if candidate.exists():
                path = candidate

        if not path.exists():
            raise ScenarioError(f"Сценарий не найден: {path}")

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

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

    valid_dos = {
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
