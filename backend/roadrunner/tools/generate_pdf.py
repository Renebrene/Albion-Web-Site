"""
Генерация PDF-документации Roadrunner API.

Использует weasyprint (если установлен) или wkhtmltopdf.
Если ни один из инструментов не доступен — выводит HTML в stdout.

Запуск:
  python backend/roadrunner/tools/generate_pdf.py [--output roadrunner-api.pdf]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def generate_pdf_html(output_path: Path) -> bool:
    """Попытаться сгенерировать PDF через weasyprint."""
    try:
        from weasyprint import HTML

        html_path = Path(__file__).resolve().parents[2] / "api" / "roadrunner-api.html"
        if not html_path.exists():
            print(f"HTML не найден: {html_path}", file=sys.stderr)
            return False

        HTML(filename=str(html_path)).write_pdf(str(output_path))
        print(f"PDF создан: {output_path}")
        return True
    except ImportError:
        return False


def generate_pdf_wkhtmltopdf(output_path: Path) -> bool:
    """Попытаться сгенерировать PDF через wkhtmltopdf."""
    import subprocess

    html_path = Path(__file__).resolve().parents[2] / "api" / "roadrunner-api.html"
    if not html_path.exists():
        print(f"HTML не найден: {html_path}", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            [
                "wkhtmltopdf",
                "--encoding", "utf-8",
                "--page-size", "A4",
                "--margin-top", "20",
                "--margin-bottom", "20",
                "--margin-left", "20",
                "--margin-right", "20",
                str(html_path),
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"wkhtmltopdf ошибка: {result.stderr}", file=sys.stderr)
            return False

        print(f"PDF создан: {output_path}")
        return True
    except FileNotFoundError:
        return False


def generate_pdf_chromium(output_path: Path) -> bool:
    """Попытаться сгенерировать PDF через Chrome/Chromium."""
    import subprocess

    html_path = Path(__file__).resolve().parents[2] / "api" / "roadrunner-api.html"
    if not html_path.exists():
        print(f"HTML не найден: {html_path}", file=sys.stderr)
        return False

    chrome_path = (
        "/usr/bin/google-chrome"
        if Path("/usr/bin/google-chrome").exists()
        else "/usr/bin/chromium-browser"
    )

    if not Path(chrome_path).exists():
        return False

    try:
        result = subprocess.run(
            [
                chrome_path,
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
            print(f"Chrome ошибка: {result.stderr}", file=sys.stderr)
            return False

        print(f"PDF создан: {output_path}")
        return True
    except FileNotFoundError:
        return False


def main():
    ap = argparse.ArgumentParser(description="Генерация PDF документации Roadrunner API")
    ap.add_argument(
        "--output",
        "-o",
        default="roadrunner-api.pdf",
        help="Путь к выходному PDF (default: roadrunner-api.pdf)",
    )
    ap.add_argument(
        "--html",
        "-H",
        action="store_true",
        help="Вывести HTML в stdout (без PDF)",
    )
    ap.add_argument(
        "--force-weasyprint",
        action="store_true",
        help="Принудительно использовать weasyprint",
    )
    ap.add_argument(
        "--force-wkhtmltopdf",
        action="store_true",
        help="Принудительно использовать wkhtmltopdf",
    )
    ap.add_argument(
        "--force-chromium",
        action="store_true",
        help="Принудительно использовать Chromium",
    )

    args = ap.parse_args()

    output_path = Path(args.output)

    if args.html:
        html_path = Path(__file__).resolve().parents[2] / "api" / "roadrunner-api.html"
        if html_path.exists():
            print(html_path.read_text(encoding="utf-8"))
        else:
            print(f"HTML не найден: {html_path}", file=sys.stderr)
            sys.exit(1)
        return

    # Пробуем генераторы в порядке приоритета
    generators = []
    if args.force_weasyprint:
        generators.append(generate_pdf_html)
    if args.force_wkhtmltopdf:
        generators.append(generate_pdf_wkhtmltopdf)
    if args.force_chromium:
        generators.append(generate_pdf_chromium)

    if not generators:
        # Попробовать все по порядку
        generators = [generate_pdf_html, generate_pdf_wkhtmltopdf, generate_pdf_chromium]

    for gen in generators:
        try:
            if gen(output_path):
                return
        except Exception as exc:
            print(f"{gen.__name__} ошибка: {exc}", file=sys.stderr)

    print("Ни один генератор PDF не доступен.", file=sys.stderr)
    print("Установите один из:", file=sys.stderr)
    print("  - weasyprint: pip install weasyprint", file=sys.stderr)
    print("  - wkhtmltopdf: apt install wkhtmltopdf", file=sys.stderr)
    print("  - google-chrome:apt install google-chrome-stable", file=sys.stderr)
    print("Или используйте --html для вывода HTML в stdout.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
