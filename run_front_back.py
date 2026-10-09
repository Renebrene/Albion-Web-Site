# run_front_back.py — одновременный запуск frontend (quasar dev) и backend (uvicorn).
# Запуск:  .venv/bin/python run_front_back.py   (или: bash -c 'source .venv/bin/activate && python run_front_back.py')
# Остановка: Ctrl+C (останавливает оба процесса).
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"

if not PYTHON.exists():
    print("ОШИБКА: venv не найден:", PYTHON)
    sys.exit(1)

procs = []


def stop(sig=None, frame=None):
    print("\nОстанавливаю процессы...")
    for p in procs:
        if p.poll() is None:
            p.terminate()

    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()

    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    # backend: uvicorn backend.main:app — нужен venv проекта
    # (в системном python3 нет fastapi).
    #
    # Воркеры = половина ядер (сборка/сериализация /api/constructions и gzip
    # грузят CPU). С несколькими воркерами --reload недоступен (uvicorn не
    # совмещает их) — при workers>1 запускаем без авто-перезагрузки.
    import os as _os

    workers = max(1, (_os.cpu_count() or 2) // 2)

    backend_args = [
        str(PYTHON),
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]

    if workers > 1:
        backend_args += ["--workers", str(workers)]
    else:
        backend_args += ["--reload"]

    procs = [
        subprocess.Popen(
            backend_args,
            cwd=str(PROJECT_DIR),
        ),
        # frontend: quasar dev на порту 9000.
        # Важно: shell=False со списком аргументов — иначе
        # аргументы уходят шеллу, а не npm.
        subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", "9000"],
            cwd=str(PROJECT_DIR / "frontend"),
        ),
    ]

    print("ALBION DEV запущен:")
    print("  backend : http://127.0.0.1:8000   (uvicorn backend.main:app)")
    print("  frontend: http://localhost:9000   (quasar dev)")
    print("  Ctrl+C — остановить всё\n")

    for p in procs:
        try:
            p.wait()
        except KeyboardInterrupt:
            stop()