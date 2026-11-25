"""
API для Roadrunner — программной дороги Альбион.

Эндпоинты:
- GET /api/roadrunner/scenarios — список сценариев
- GET /api/roadrunner/scenarios/{id} — сценарий по id
- POST /api/roadrunner/scenarios — создать сценарий
- DELETE /api/roadrunner/scenarios/{id} — удалить сценарий
- POST /api/roadrunner/generate — сгенерировать сценарий через LLM
- GET /api/roadrunner/weather — текущая погода
- GET /api/roadrunner/traffic — текущие пробки
- GET /api/roadrunner/settings — настройки
- PUT /api/roadrunner/settings — обновить настройки
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.services.auth_api import require_admin
from backend.services.data_service import get_connection
from backend.roadrunner.services.llm_agent import (
    LLMAgent,
    LLMAgentError,
    create_llm_agent,
)
from backend.roadrunner.services.weather import TrafficService, WeatherService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/roadrunner",
    tags=["roadrunner"],
)

# Сервисы (инициализируются при старте)
_weather_service: WeatherService | None = None
_traffic_service: TrafficService | None = None


async def get_weather_service() -> WeatherService:
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service


async def get_traffic_service() -> TrafficService:
    global _traffic_service
    if _traffic_service is None:
        _traffic_service = TrafficService()
    return _traffic_service


@router.get("/weather")
async def get_weather():
    """Текущая погода."""
    service = await get_weather_service()
    data = await service.get_current()

    return {
        "success": True,
        "data": {
            "condition": data.condition,
            "temperature_c": data.temperature_c,
            "humidity": data.humidity,
            "wind_speed_kmh": data.wind_speed_kmh,
            "precipitation_mm": data.precipitation_mm,
            "source": data.source,
        },
    }


@router.get("/weather-proxy")
async def get_weather_proxy():
    """Прокси погоды для баннера (CSP разрешает 127.0.0.1)."""
    service = await get_weather_service()
    data = await service.get_current()

    # Преобразуем condition в weather_code для Open-Meteo
    condition_to_code = {
        "clear": 0,
        "cloudy": 1,
        "fog": 45,
        "rain": 51,
        "snow": 71,
    }
    weather_code = condition_to_code.get(data.condition, 0)

    # Баннер живёт в sandbox-iframe с opaque origin (CSP sandbox), поэтому
    # запрос идёт как cross-origin с Origin: null. Данные публичные —
    # разрешаем чтение из любого origin.
    return JSONResponse(
        content={
            "temperature_c": data.temperature_c,
            "humidity": data.humidity,
            "wind_speed_kmh": data.wind_speed_kmh,
            "precipitation_mm": data.precipitation_mm,
            "weather_code": weather_code,
            "source": data.source,
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/traffic")
async def get_traffic():
    """Текущие пробки."""
    service = await get_traffic_service()
    data = await service.get_current()

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "score": data.score,
                "label": data.label,
                "source": data.source,
            },
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/scenarios")
async def list_scenarios(auth=Depends(require_admin)):
    """Список сценариев."""
    from backend.roadrunner.scenario.engine import load_all_scenarios

    scenarios = load_all_scenarios()

    # Добавляем из БД
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, scenario_data
                FROM roadrunner_scenarios
                ORDER BY created_at DESC
                """
            ).fetchall()

        from backend.roadrunner.services.db_json import as_dict

        for row in rows:
            scenario_data = as_dict(row[1])
            # Не дублировать, если уже есть в файлах
            if not any(s["id"] == scenario_data["id"] for s in scenarios):
                # db_id нужен, чтобы сценарий из БД можно было удалить:
                # внутренний id сценария (slug) не совпадает с PK.
                scenarios.append({**scenario_data, "db_id": row[0]})

    except Exception as exc:
        logger.warning("Не удалось загрузить сценарии из БД: %s", exc)

    return {"success": True, "scenarios": scenarios}


@router.get("/scenarios/active", include_in_schema=False)
async def get_active_scenario():
    """Сценарий, который сейчас применяет баннер (публичный, для iframe)."""
    from backend.roadrunner.services.scenario_state import get_active_scenario

    return JSONResponse(
        content={"active": get_active_scenario()},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.delete("/scenarios/active")
async def clear_active_scenario(auth=Depends(require_admin)):
    """Завершить сценарий и вернуть баннер к настройкам из БД."""
    from backend.roadrunner.services.scenario_state import clear_active_scenario

    clear_active_scenario()
    return {"success": True}


@router.post("/scenarios/apply")
async def apply_scenario(
    payload: dict, auth=Depends(require_admin)
):
    """Применить сценарий к баннеру (из чата или админки)."""
    from backend.roadrunner.services.scenario_state import apply_scenario

    scenario = payload.get("scenario") or payload
    if not scenario.get("events") and not scenario.get("duration"):
        raise HTTPException(
            status_code=400, detail="Пустой сценарий"
        )

    state = apply_scenario(scenario)
    return {
        "success": True,
        "duration": state["duration"],
        "started_at": state["started_at"],
    }


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str, auth=Depends(require_admin)
):
    """Сценарий по id."""
    from backend.roadrunner.scenario.engine import (
        ScenarioError,
        ScenarioEngine,
    )

    # Числовой id — это PK в БД; строковый — slug файлового сценария.
    is_db_id = scenario_id.isdigit()

    if is_db_id:
        try:
            engine = ScenarioEngine.from_db(int(scenario_id))
            return {"success": True, "scenario": engine.events}
        except ScenarioError:
            pass

    try:
        engine = ScenarioEngine.from_file(scenario_id)
        return {"success": True, "scenario": engine.events}
    except ScenarioError:
        raise HTTPException(
            status_code=404, detail=f"Сценарий не найден: {scenario_id}"
        )


@router.post("/scenarios")
async def create_scenario(
    payload: dict, auth=Depends(require_admin)
):
    """Создать сценарий."""
    from backend.roadrunner.scenario.engine import ScenarioError, validate_scenario

    errors = validate_scenario(payload)
    if errors:
        raise HTTPException(
            status_code=400, detail="Ошибка валидации: " + "; ".join(errors)
        )

    # Сохранить в БД
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO roadrunner_scenarios
                    (name, description, scenario_data, created_at, author)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    payload.get("name", "Без названия"),
                    payload.get("description", ""),
                    json.dumps(payload, ensure_ascii=False),
                    datetime.now().isoformat(),
                    payload.get("author", "admin"),
                ),
            ).fetchone()
    except Exception as exc:
        logger.error("Не удалось сохранить сценарий: %s", exc)
        raise HTTPException(
            status_code=500, detail="Не удалось сохранить сценарий"
        )

    return {"success": True, "scenario": payload, "db_id": row[0]}


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str, auth=Depends(require_admin)
):
    """Удалить сценарий из БД по числовому id или по slug (scenario_data.id)."""
    if scenario_id.isdigit():
        query = "DELETE FROM roadrunner_scenarios WHERE id = %s"
        params = (int(scenario_id),)
    else:
        query = (
            "DELETE FROM roadrunner_scenarios "
            "WHERE scenario_data->>'id' = %s"
        )
        params = (scenario_id,)

    with get_connection() as conn:
        cur = conn.execute(query, params)

    if cur.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                "Сценарий не найден в БД. Файловые сценарии "
                "редактируются в репозитории и через API не удаляются."
            ),
        )

    return {"success": True}


@router.post("/generate")
async def generate_scenario(
    payload: dict, auth=Depends(require_admin)
):
    """Сгенерировать сценарий через LLM."""
    request_text = payload.get("request", "")
    if not request_text:
        raise HTTPException(
            status_code=400, detail="Отсутствует 'request'"
        )

    try:
        # Генератор добавляет и меняет элементы и надписи сцены, поэтому
        # использует выбранную для этого нейросеть.
        agent = create_llm_agent(scene=True)
        scenario = await agent.generate(request_text)

        # Валидация
        from backend.roadrunner.scenario.engine import validate_scenario

        errors = validate_scenario(scenario)
        if errors:
            raise HTTPException(
                status_code=422,
                detail="Сгенерированный сценарий не прошёл валидацию: "
                + "; ".join(errors),
            )

        # Сохранить
        scenario["author"] = "ai"
        await create_scenario(scenario, auth)

        return {"success": True, "scenario": scenario}

    except LLMAgentError as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM не ответил: {exc}"
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Ошибка генерации сценария")
        raise HTTPException(
            status_code=500, detail=f"Ошибка генерации: {exc}"
        )


PRESETS_KEY = "camera_presets"
# Пресеты сцены (количество машин, пешеходов и т.п.) и снимок «Дефолт»,
# от которого они создаются.
SCENE_PRESETS_KEY = "scene_presets"
SCENE_DEFAULT_KEY = "scene_default"


def _load_settings_key(key: str) -> dict:
    """Словарь из roadrunner_settings по ключу (пресеты, снимки)."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT settings FROM roadrunner_settings WHERE key = %s",
                (key,),
            ).fetchone()
    except Exception as exc:
        logger.warning("Не удалось загрузить настройки %s: %s", key, exc)
        return {}

    if not row:
        return {}

    from backend.roadrunner.services.db_json import as_dict

    return as_dict(row[0])


def _save_settings_key(key: str, value: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO roadrunner_settings (key, settings)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET settings = EXCLUDED.settings
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )


def _load_camera_presets() -> dict:
    """Пресеты камеры/сцены из настроек Roadrunner."""
    return _load_settings_key(PRESETS_KEY)


def _save_camera_presets(presets: dict) -> None:
    _save_settings_key(PRESETS_KEY, presets)


@router.get("/camera-presets")
async def list_camera_presets(auth=Depends(require_admin)):
    return {"success": True, "presets": _load_camera_presets()}


@router.post("/camera-presets")
async def save_camera_preset(payload: dict, auth=Depends(require_admin)):
    from urllib.parse import unquote

    name = str(payload.get("name") or "").strip()
    values = payload.get("settings") or {}

    if not name:
        raise HTTPException(status_code=400, detail="Не указано имя пресета")
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="Некорректные настройки")

    presets = _load_camera_presets()
    presets[unquote(name)] = values
    _save_camera_presets(presets)
    return {"success": True, "name": unquote(name)}


@router.delete("/camera-presets/{name}")
async def delete_camera_preset(name: str, auth=Depends(require_admin)):
    from urllib.parse import unquote

    presets = _load_camera_presets()
    if unquote(name) not in presets:
        raise HTTPException(status_code=404, detail="Пресет не найден")

    del presets[unquote(name)]
    _save_camera_presets(presets)
    return {"success": True}


# --- Пресеты сцены и «Дефолт» -------------------------------------------
#
# Сцена баннера описывается количеством элементов (машины, пешеходы, поток,
# автобусы). «Дефолт» — снимок текущего состояния; остальные пресеты
# создаются на его основе с другим количеством элементов.


@router.get("/scene-presets")
async def list_scene_presets(auth=Depends(require_admin)):
    return {
        "success": True,
        "presets": _load_settings_key(SCENE_PRESETS_KEY),
        "default": _load_settings_key(SCENE_DEFAULT_KEY),
    }


@router.post("/scene-presets/default")
async def save_scene_default(payload: dict, auth=Depends(require_admin)):
    """Сохранить текущее состояние сцены как «Дефолт»."""
    values = payload.get("settings") or {}

    if not isinstance(values, dict) or not values:
        raise HTTPException(
            status_code=400, detail="Некорректные настройки сцены"
        )

    _save_settings_key(SCENE_DEFAULT_KEY, values)
    return {"success": True, "default": values}


@router.post("/scene-presets")
async def save_scene_preset(payload: dict, auth=Depends(require_admin)):
    """Создать пресет сцены (обычно — на основе «Дефолта»)."""
    from urllib.parse import unquote

    name = str(payload.get("name") or "").strip()
    values = payload.get("settings") or {}

    if not name:
        raise HTTPException(status_code=400, detail="Не указано имя пресета")
    if not isinstance(values, dict) or not values:
        raise HTTPException(status_code=400, detail="Некорректные настройки")

    presets = _load_settings_key(SCENE_PRESETS_KEY)
    presets[unquote(name)] = values
    _save_settings_key(SCENE_PRESETS_KEY, presets)
    return {"success": True, "name": unquote(name)}


@router.delete("/scene-presets/{name}")
async def delete_scene_preset(name: str, auth=Depends(require_admin)):
    from urllib.parse import unquote

    presets = _load_settings_key(SCENE_PRESETS_KEY)
    if unquote(name) not in presets:
        raise HTTPException(status_code=404, detail="Пресет не найден")

    del presets[unquote(name)]
    _save_settings_key(SCENE_PRESETS_KEY, presets)
    return {"success": True}


OLLAMA_MODEL_CATALOG = (
    "qwen2.5:7b",
    "llama3.1:8b",
    "mistral:7b",
    "phi3:mini",
    "gemma2:9b",
)


def _ollama_url() -> str:
    url = os.getenv("ROADRUNNER_LLM_URL") or "http://localhost:11434"
    return url.rstrip("/")


@router.get("/ollama/models", include_in_schema=False)
async def list_ollama_models(auth=Depends(require_admin)):
    """Список моделей, уже загруженных в локальный Ollama."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{_ollama_url()}/api/tags")
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("Ollama недоступен: %s", exc)
        return JSONResponse(
            content={"success": False, "models": [], "error": str(exc)},
            headers={"Access-Control-Allow-Origin": "*"},
        )

    models = sorted(
        {item.get("name", "") for item in data.get("models", []) if item.get("name")}
    )
    return {"success": True, "models": models, "catalog": list(OLLAMA_MODEL_CATALOG)}


@router.post("/ollama/pull", include_in_schema=False)
async def pull_ollama_model(payload: dict, auth=Depends(require_admin)):
    """Скачать модель в Ollama (блокирующий вызов в отдельном потоке)."""
    import httpx

    model = str(payload.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="Не указана модель")

    def _pull() -> tuple[int, str]:
        with httpx.Client(timeout=600) as client:
            response = client.post(
                f"{_ollama_url()}/api/pull",
                json={"name": model, "stream": False},
            )
            return response.status_code, response.text[:500]

    try:
        status, text = await asyncio.to_thread(_pull)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Ollama недоступен: {exc}"
        )

    if status >= 400:
        raise HTTPException(status_code=502, detail=f"Ollama: {text}")

    return {"success": True, "model": model}


DEFAULT_SETTINGS = {
    "default_scenario": "rostov-evening-rain",
    "weather_provider": "gismeteo",
    "weather_enabled": True,
    "traffic_enabled": True,
    "llm_provider": "ollama",
    "llm_model": "qwen2.5:7b",
    # Нейросеть для добавления/редактирования элементов и надписей сцены:
    # локальная (Ollama) или облачная (YandexGPT/OpenAI).
    "scene_llm_mode": "local",
    "scene_llm_model": "qwen2.5:7b",
}


@router.get("/settings")
async def get_settings(auth=Depends(require_admin)):
    """Настройки Roadrunner (сохранённые поверх значений по умолчанию)."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT settings FROM roadrunner_settings WHERE key = 'roadrunner'"
            ).fetchone()

        if row:
            from backend.roadrunner.services.db_json import as_dict

            # Старые записи не содержат новых ключей — дополняем дефолтами,
            # чтобы поля в админке и API всегда были заполнены.
            return {
                "success": True,
                "settings": {**DEFAULT_SETTINGS, **as_dict(row[0])},
            }
    except Exception as exc:
        logger.warning("Не удалось загрузить настройки: %s", exc)

    return {"success": True, "settings": dict(DEFAULT_SETTINGS)}


@router.put("/settings")
async def update_settings(
    payload: dict, auth=Depends(require_admin)
):
    """Обновить настройки."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO roadrunner_settings (key, settings)
                VALUES ('roadrunner', %s)
                ON CONFLICT (key) DO UPDATE SET settings = %s
                """,
                (json.dumps(payload, ensure_ascii=False), json.dumps(payload, ensure_ascii=False)),
            )
    except Exception as exc:
        logger.error("Не удалось сохранить настройки: %s", exc)
        raise HTTPException(
            status_code=500, detail="Не удалось сохранить настройки"
        )

    return {"success": True}


@router.post("/upload-scenario")
async def upload_scenario(
    file: UploadFile, auth=Depends(require_admin)
):
    """Загрузить сценарий из файла."""
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=400, detail="Только .json файлы"
        )

    content = await file.read()
    try:
        scenario = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"Некорректный JSON: {exc}"
        )

    # Валидация
    from backend.roadrunner.scenario.engine import validate_scenario

    errors = validate_scenario(scenario)
    if errors:
        raise HTTPException(
            status_code=422,
            detail="Ошибка валидации: " + "; ".join(errors),
        )

    # Сохранить
    scenario["author"] = "upload"
    await create_scenario(scenario, auth)

    return {"success": True, "scenario": scenario}


@router.get("/api-documentation.html")
async def get_api_documentation_html():
    """Отдать HTML-документацию API Roadrunner (публичная)."""
    from pathlib import Path

    html_path = Path(__file__).resolve().parents[1] / "roadrunner" / "api" / "roadrunner-api.html"

    if not html_path.exists():
        raise HTTPException(
            status_code=404, detail="HTML документация не найдена"
        )

    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


_CHROME_CANDIDATES = (
    os.getenv("ROADRUNNER_CHROME_BIN", ""),
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)


def _find_chrome() -> str | None:
    for candidate in _CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _render_pdf_sync(html_path: Path, output_path: Path) -> None:
    """Синхронный рендер PDF (запускается в отдельном потоке)."""
    chrome = _find_chrome()

    if chrome is None:
        raise FileNotFoundError("Chrome/Chromium не найден")

    result = subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--print-to-pdf={output_path}",
            f"file://{html_path.resolve()}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Chrome завершился с ошибкой")

    if not output_path.exists():
        raise RuntimeError("PDF не сгенерирован")


@router.get("/api-documentation.pdf")
async def get_api_documentation_pdf():
    """Скачать PDF-документацию API Roadrunner (публичная)."""
    html_path = (
        Path(__file__).resolve().parents[1]
        / "roadrunner" / "api" / "roadrunner-api.html"
    )

    if not html_path.exists():
        raise HTTPException(
            status_code=500, detail="HTML документация не найдена"
        )

    # Уникальный временный файл: параллельные запросы не перетирают друг друга.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        output_path = Path(tmp.name)

    try:
        # Chrome — блокирующий подпроцесс; не держим event loop.
        await asyncio.to_thread(_render_pdf_sync, html_path, output_path)
        pdf_content = output_path.read_bytes()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Генерация PDF недоступна: не найден Chrome/Chromium. "
                "Задайте ROADRUNNER_CHROME_BIN."
            ),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504, detail="Таймаут генерации PDF"
        )
    except Exception as exc:
        logger.error("Ошибка генерации PDF: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Ошибка генерации PDF: {exc}"
        )
    finally:
        output_path.unlink(missing_ok=True)

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=roadrunner-api.pdf"
        },
    )
