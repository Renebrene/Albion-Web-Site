"""AI-редактор программного кода баннера.

Модель получает инструкцию и компактный план кода (блок настроек, имена
глобальных функций и переменных), а возвращает JS-фрагмент с новыми
функциями и элементами сцены. Фрагмент вставляется в документ «Дефолта»,
поэтому на выходе снова получается полный HTML-документ, а объём запроса
не зависит от размера баннера (файл ~100 КБ не помещается в контекст
локальной модели).

Используется нейросеть, выбранная в настройках АИ для элементов и надписей
(``scene_llm_mode`` / ``scene_llm_model``).
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from backend.roadrunner.services.llm_agent import get_scene_llm_config

logger = logging.getLogger(__name__)


CODE_SYSTEM_PROMPT = """\
Ты — программист 3D-баннера «Светофорные объекты» (three.js).

Тебе дана инструкция и краткий план кода: блок настроек, имена доступных
глобальных функций/переменных и фрагменты основного скрипта. Верни
ТОЛЬКО JavaScript-фрагмент, который добавит новые функции и/или элементы
сцены. Сервер сам вставит этот фрагмент в полный HTML-документ.

Правила:
1. Никаких пояснений, HTML и markdown вне блока ```js ... ```.
2. Не переопределяй и не удаляй существующие функции и переменные — только
   добавляй новые с уникальными именами (префикс ai_ приветствуется).
3. Используй только доступные глобальные объекты из плана (например, scene,
   THREE, CFG, SET, renderer, camera) и стандартный JavaScript.
4. Не добавляй внешние зависимости и не меняй блок
   <script type="application/json" id="banner-settings">.
5. Фрагмент должен быть готов к вставке внутрь модульного <script>: без
   тегов <script> и без строки </script>.
"""


class CodeEditorError(Exception):
    """Ошибка AI-редактора кода."""


def _strip_markdown(text: str) -> str:
    """Убрать markdown-обёртку и пояснения вокруг HTML-документа."""
    text = (text or "").strip()

    fence = re.search(r"```(?:html)?\s*(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()

    start = text.lower().find("<!doctype")
    if start < 0:
        start = text.lower().find("<html")
    end = text.lower().rfind("</html>")

    if start >= 0 and end > start:
        text = text[start:end + len("</html>")]

    return text.strip()


def is_complete_document(code: str) -> bool:
    """Похож ли ответ модели на целый HTML-документ баннера."""
    lowered = (code or "").lower()
    return (
        "<html" in lowered
        and "</html>" in lowered
        and "banner-settings" in lowered
    )


SETTINGS_RE = re.compile(
    r'<script\s+type="application/json"\s+id="banner-settings"[^>]*>'
    r"(.*?)</script>",
    re.S | re.I,
)


def _condense_code(code: str) -> str:
    """Компактный план кода вместо полного документа (~100 КБ).

    Модели нужны блок настроек, имена доступных глобальных величин и
    несколько фрагментов скрипта, чтобы написать совместимый JS-фрагмент.
    """
    settings_match = SETTINGS_RE.search(code or "")
    settings = (settings_match.group(1).strip() if settings_match else "{}")
    if len(settings) > 2000:
        settings = settings[:2000] + "\n... (обрезано)"

    names = sorted(set(re.findall(
        r"\b(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)", code or ""
    )))[:80]

    scripts = re.findall(r"<script[^>]*>(.*?)</script>", code or "", re.S | re.I)
    main = max(scripts, key=len) if scripts else ""
    head = main[:1400]
    tail = main[-700:] if len(main) > 2100 else ""

    return (
        "Блок настроек banner-settings:\n"
        f"{settings}\n\n"
        "Доступные глобальные имена:\n"
        f"{', '.join(names) or '(не найдены)'}\n\n"
        "Начало основного скрипта:\n"
        f"{head}\n"
        + (f"\n... (пропущено {len(main) - 2100} символов)\n\n" if tail else "\n")
        + ("Конец основного скрипта:\n" + tail if tail else "")
    )


def _extract_snippet(text: str) -> str:
    """Достать JS-фрагмент из ответа модели (ёсли вернула не целый документ)."""
    text = (text or "").strip()

    fence = re.search(r"```(?:js|javascript)?\s*(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()

    # На случай, когда модель обернула фрагмент в тег <script>.
    tag = re.search(r"<script[^>]*>(.*?)</script>", text, re.S | re.I)
    if tag and not is_complete_document(text):
        text = tag.group(1).strip()

    return text.replace("</script", "<\\/script").strip()


INSERT_MARKERS = (
    "/* ================= LIVE-ДАННЫЕ",
    "pollActiveScenario();",
)


def _inject_snippet(code: str, snippet: str) -> str:
    """Вставить JS-фрагмент в последний <script> документа баннера."""
    marker = next((item for item in INSERT_MARKERS if item in code), None)

    if marker:
        return code.replace(marker, snippet + "\n\n" + marker, 1)

    close = code.rfind("</script>")
    if close < 0:
        raise CodeEditorError("В коде баннера не найден модульный <script>")

    return code[:close] + snippet + "\n" + code[close:]


async def _call_ollama(
    config: dict[str, Any], system: str, user: str, max_tokens: int
) -> str:
    payload = {
        "model": config.get("model", "qwen2.5:7b"),
        "stream": False,
        "options": {
            "temperature": config.get("temperature", 0.35),
            "num_predict": max_tokens,
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{str(config.get('url') or 'http://localhost:11434').rstrip('/')}"
            "/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return str(data.get("message", {}).get("content", ""))


async def _call_yandex(
    config: dict[str, Any], system: str, user: str, max_tokens: int
) -> str:
    headers = {
        "Authorization": f"Api-Key {config.get('api_key', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gs://{config.get('model', '')}",
        "completionOptions": {
            "stream": False,
            "temperature": config.get("temperature", 0.35),
            "maxTokens": str(max_tokens),
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            str(config.get("url") or ""), json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()

    return str(data.get("result", {}).get("data", [{}])[0].get("text", ""))


async def _call_openai(
    config: dict[str, Any], system: str, user: str, max_tokens: int
) -> str:
    headers = {
        "Authorization": f"Bearer {config.get('api_key', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.get("model", ""),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": config.get("temperature", 0.35),
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{str(config.get('url') or '').rstrip('/')}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    return str(data["choices"][0]["message"]["content"])


async def edit_code(
    instruction: str,
    code: str,
    *,
    config: dict[str, Any] | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Изменить HTML-код баннера по инструкции на естественном языке."""
    instruction = (instruction or "").strip()
    code = (code or "").strip()

    if not instruction:
        raise CodeEditorError("Не задана инструкция для редактирования")
    if not code:
        raise CodeEditorError("Нет исходного кода для редактирования")

    config = config or get_scene_llm_config()
    provider = str(config.get("provider") or "ollama").lower()

    user_prompt = (
        "Инструкция по изменению баннера:\n"
        f"{instruction}\n\n"
        "План кода баннера (не полный документ):\n"
        f"{_condense_code(code)}"
    )

    try:
        if provider == "ollama":
            raw = await _call_ollama(
                config, CODE_SYSTEM_PROMPT, user_prompt, max_tokens
            )
        elif provider == "yandexgpt":
            raw = await _call_yandex(
                config, CODE_SYSTEM_PROMPT, user_prompt, max_tokens
            )
        elif provider == "openai":
            raw = await _call_openai(
                config, CODE_SYSTEM_PROMPT, user_prompt, max_tokens
            )
        else:
            raise CodeEditorError(f"Неизвестный провайдер: {provider}")
    except httpx.HTTPError as exc:
        raise CodeEditorError(f"Нейросеть недоступна: {exc}") from exc

    if not raw.strip():
        raise CodeEditorError("Нейросеть вернула пустой ответ")

    # Обычно модель возвращает JS-фрагмент — вставляем его в «Дефолт».
    # Если же она вернула целый документ (например, cloud-модель), берём его
    # как есть — это тоже допустимый результат.
    if is_complete_document(_strip_markdown(raw)):
        edited = _strip_markdown(raw)
        mode = "document"
    else:
        snippet = _extract_snippet(raw)
        if not snippet:
            raise CodeEditorError("Нейросеть вернула пустой фрагмент")
        edited = _inject_snippet(code, snippet)
        mode = "snippet"

    return {
        "code": edited,
        "complete": is_complete_document(edited),
        "provider": provider,
        "model": config.get("model", ""),
        "mode": mode,
    }
