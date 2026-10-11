#!/usr/bin/env python3
"""Браузерный смоук-тест Albion через Chrome DevTools Protocol.

Проверяет, что ключевые страницы открываются, отдают ожидаемую разметку и
не бросают необработанных JS-исключений. Не входит в pytest (нужны Chrome
и запущенный фронтенд), запускается вручную:

    uv run --with websockets python deploy/browser-smoke.py \
        --base http://localhost:9000

Коды возврата: 0 — всё ок, 1 — есть падения.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import urllib.request

import websockets

# (путь, JS-проверка присутствия ключевого элемента, подпись)
CHECKS = [
    ("/", "document.querySelectorAll('.slide').length > 0", "главная: слайды"),
    (
        "/vozmozhnosti",
        "!!document.querySelector('.leaflet-container')",
        "карта: контейнер Leaflet",
    ),
    ("/portfolio", "!!document.querySelector('#q-app')", "портфель"),
    (
        "/administration",
        "!!document.querySelector('input')",
        "вход в админку: форма",
    ),
]


async def _run(base: str, chrome: str, port: int) -> int:
    profile = tempfile.mkdtemp(prefix="albion-smoke-")

    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            f"--remote-debugging-port={port}",
            "--window-size=1440,900",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    failures = 0

    try:
        ws_url = None

        for _ in range(80):
            try:
                targets = json.load(
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/json")
                )
                page = next(
                    (t for t in targets if t.get("type") == "page"), None
                )
                if page:
                    ws_url = page["webSocketDebuggerUrl"]
                    break
            except Exception:
                await asyncio.sleep(0.2)

        if not ws_url:
            print("FAIL: не удалось подключиться к Chrome", file=sys.stderr)
            return 1

        async with websockets.connect(ws_url) as sock:
            seq = 0
            errors: list[str] = []

            async def cmd(method, params=None):
                nonlocal seq
                seq += 1
                ident = seq
                await sock.send(
                    json.dumps({"id": ident, "method": method, "params": params or {}})
                )
                while True:
                    message = json.loads(await sock.recv())
                    if message.get("method") == "Runtime.exceptionThrown":
                        errors.append(
                            message["params"]["exceptionDetails"].get("text", "")
                        )
                    if message.get("id") == ident:
                        return message.get("result", {})

            async def js(expression: str):
                result = await cmd(
                    "Runtime.evaluate",
                    {"expression": expression, "returnByValue": True},
                )
                return result.get("result", {}).get("value")

            await cmd("Runtime.enable")
            await cmd("Page.enable")

            for path, check, label in CHECKS:
                errors.clear()
                await cmd("Page.navigate", {"url": base + path})
                await asyncio.sleep(3)

                ok = await js(check)
                no_errors = len(errors) == 0
                status = "PASS" if (ok and no_errors) else "FAIL"

                if status == "FAIL":
                    failures += 1

                detail = ""
                if not ok:
                    detail += " (элемент не найден)"
                if not no_errors:
                    detail += f" (JS-исключения: {errors})"

                print(f"{status} {label}{detail}")

        return 1 if failures else 0

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Браузерный смоук-тест Albion")
    parser.add_argument("--base", default="http://localhost:9000")
    parser.add_argument("--chrome", default="google-chrome")
    parser.add_argument("--port", type=int, default=9430)
    args = parser.parse_args()

    return asyncio.run(_run(args.base, args.chrome, args.port))


if __name__ == "__main__":
    raise SystemExit(main())
