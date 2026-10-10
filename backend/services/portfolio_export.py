"""Экспорт портфеля Albion в Excel / Word / PDF.

Портфель приходит с фронтенда (см. frontend/src/composables/usePortfolio.js):

    {
      "title": "Портфель Albion",
      "items": [
        {
          "surfaceId": 123,
          "city": "Ростов-на-Дону",
          "address": "ул. …",
          "side": "A",
          "type": "ЩИТ",
          "size": "6 × 3 м",
          "months": {
            "Октябрь": { "price": 15400, "stale": false }
          }
        }
      ]
    }

Общая логика сбора строк вынесена в build_portfolio(), а три формата
(export_xlsx / export_docx / export_pdf) используют один и тот же
построитель данных, поэтому таблица во всех документах совпадает.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- константы

SUPPORTED_FORMATS = (
    "xls",
    "xlsx",
    "doc",
    "docx",
    "pdf",
    "odt",
    "ods",
    "rtf",
    "csv",
    "txt",
    "md",
    "json",
)

# Форматы «только текст»: отдают текстовую часть без фото/карт и без учёта
# переключателя «полный/краткий вывод» (см. пользовательское ТЗ).
TEXT_FORMATS = ("csv", "txt", "md", "json")

MAX_ITEMS = 500

DEFAULT_TITLE = "Портфель Albion"

COLUMNS = (
    "№",
    "Город",
    "Адрес",
    "Сторона",
    "Формат",
    "Размер",
    "Месяцы",
    "Сумма за месяцы",
)

# Колонки «текстовых» форматов (без фото/карт).
TEXT_COLUMNS = COLUMNS

# Дополнительная колонка, появляется только при with_photos=true.
PHOTO_COLUMN = "Фото"

# Дополнительная колонка, появляется только при with_maps=true.
MAP_COLUMN = "Карта"

# Реквизиты пользователя (печатаются компактным блоком под заголовком).
# Порядок вывода и русские подписи.
REQUISITE_LABELS = (
    ("organization", "Организация"),
    ("inn", "ИНН"),
    ("kpp", "КПП"),
    ("address", "Адрес"),
    ("phone", "Телефон"),
    ("email", "E-mail"),
    ("contact", "Контактное лицо"),
)

# Разумный предел длины одного поля реквизитов при печати.
MAX_REQUISITE_LENGTH = 300

# Корень статики: URL вида /storage/... указывают внутрь этой папки
# (см. backend/main.py и backend/services/media_service.py).
PROJECT_DIR = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_DIR / "storage"

# Фото приходит С КЛИЕНТА (эндпоинт публичный), поэтому жёстко ограничиваем:
_STORAGE_URL_PREFIX = "/storage/"

# Не читаем файлы больше 15 МБ.
MAX_PHOTO_BYTES = 15 * 1024 * 1024

# Размеры миниатюр (в пикселях), до вставки в документ.
XLSX_PHOTO_BOX = (88, 66)
DOCX_PHOTO_BOX = (240, 240)
PDF_PHOTO_BOX = (240, 240)
PDF_PHOTO_WIDTH_MM = 18.0
DOCX_PHOTO_WIDTH_CM = 1.8

# «Полный вывод»: фото и карта встают в один ряд по ширине A4.
# Оба — 8 × 5 см (пропорция 8:5), поэтому ширины и высоты совпадают и
# ряд ровный. Картинка НЕ растягивается: PIL-овский cover-кроп по центру
# приводит её к точному боксу, задание width/height в docx/pdf её не искажает.
FULL_IMAGE_BOX = (800, 500)
FULL_IMAGE_WIDTH_CM = 8.0
FULL_IMAGE_HEIGHT_CM = 5.0

CONTENT_TYPES = {
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "rtf": "application/rtf",
    "csv": "text/csv; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
}


class PortfolioExportError(ValueError):
    """Некорректные данные портфеля — эндпоинт отвечает 400."""


class FontUnavailableError(RuntimeError):
    """Не найден кириллический TTF-шрифт для PDF — эндпоинт отвечает 500."""


# ---------------------------------------------------------------- утилиты


def _to_number(value: Any) -> float | None:
    """Приводит цену к числу: «100 000», «1 500,50» -> 100000.0, 1500.5."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) else None

    text = (
        str(value)
        .replace(" ", " ")
        .replace(" ", "")
        .replace("₽", "")
        .replace(",", ".")
        .strip()
    )

    if text == "":
        return None

    try:
        num = float(text)
    except ValueError:
        return None

    return num if math.isfinite(num) else None


def format_money(value: float | None) -> str:
    """Число -> «15 400 ₽» (разделитель тысяч — пробел)."""
    if value is None:
        return "—"

    num = _to_number(value)

    if num is None:
        return "—"

    if abs(num - round(num)) < 1e-9:
        text = f"{int(round(num)):,}".replace(",", " ")
    else:
        text = f"{num:,.2f}".replace(",", " ")

    return f"{text} ₽"


def _positions_word(count: int) -> str:
    """Русская форма слова «позиция» для числа count."""
    count = abs(int(count))
    last_two = count % 100

    if 11 <= last_two <= 14:
        return "позиций"

    last = count % 10

    if last == 1:
        return "позиция"

    if 2 <= last <= 4:
        return "позиции"

    return "позиций"


def _text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _extract_price(value: Any) -> float | None:
    """Месяц может быть объектом {price, stale} или просто числом."""
    if isinstance(value, dict):
        return _to_number(value.get("price"))

    return _to_number(value)


def build_requisites_block(requisites: Any) -> list[tuple[str, str]]:
    """Превращает реквизиты в список пар (подпись, значение).

    Возвращает только непустые поля в порядке REQUISITE_LABELS; значения
    обрезаются по краям и ограничиваются по длине. Если реквизитов нет
    или все поля пустые — возвращает пустой список (блок не печатается).
    """
    if not isinstance(requisites, dict):
        return []

    block: list[tuple[str, str]] = []

    for key, label in REQUISITE_LABELS:
        raw = requisites.get(key)
        value = "" if raw is None else str(raw).strip()

        if value:
            block.append((label, value[:MAX_REQUISITE_LENGTH]))

    return block


# ---------------------------------------------------------------- фото


def resolve_photo_path(url: Any) -> Path | None:
    """Безопасно превращает клиентский URL фото в путь внутри STORAGE_ROOT.

    Принимает только строки вида ``/storage/...``. Итоговый реальный путь
    (``Path.resolve()``, т.е. после раскрытия ``..`` и симлинков) обязан
    лежать внутри ``STORAGE_ROOT``. Иначе (или если это не файл, или файл
    больше лимита) возвращает ``None`` — ячейка останется пустой.
    """
    if not isinstance(url, str):
        return None

    value = url.strip()

    if not value:
        return None

    # Отбрасываем query/fragment, если клиент их добавил.
    value = value.split("?", 1)[0].split("#", 1)[0]

    if not value.startswith(_STORAGE_URL_PREFIX):
        return None

    relative = unquote(value[len(_STORAGE_URL_PREFIX):])

    if not relative:
        return None

    try:
        root = STORAGE_ROOT.resolve()
        # Абсолютный `relative` заменит STORAGE_ROOT — это поймает проверка ниже.
        candidate = (STORAGE_ROOT / relative).resolve()
        candidate.relative_to(root)
    except (ValueError, OSError, RuntimeError):
        logger.warning("Фото вне хранилища проигнорировано: %r", url)
        return None

    try:
        if not candidate.is_file():
            return None

        if candidate.stat().st_size > MAX_PHOTO_BYTES:
            logger.warning("Фото больше %s МБ проигнорировано: %s",
                           MAX_PHOTO_BYTES // (1024 * 1024), url)
            return None
    except (ValueError, OSError):
        return None

    return candidate


def load_photo_thumbnail(url: Any, box: tuple[int, int]):
    """Читает фото и возвращает уменьшенную копию (PIL Image, RGB).

    Проверка «это изображение» — через Pillow (без выполнения кода).
    При любой проблеме возвращает ``None``: выгрузка не должна падать.
    """
    path = resolve_photo_path(url)

    if path is None:
        return None

    try:
        from PIL import Image

        with Image.open(path) as source:
            source.load()
            image = source.convert("RGB")
    except Exception:  # noqa: BLE001 — битый/не тот файл просто пропускаем
        logger.warning("Не удалось прочитать фото: %r", url)
        return None

    try:
        image.thumbnail(box, Image.Resampling.LANCZOS)
    except Exception:  # noqa: BLE001
        return None

    return image


def photo_to_bytes(image, image_format: str = "JPEG", quality: int = 82) -> bytes:
    """Сериализует PIL-миниатюру в байты (по умолчанию JPEG)."""
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, quality=quality)

    return buffer.getvalue()


def load_full_image(url: Any, box=None):
    """Картинка «полного вывода»: cover-кроп по центру до нужного бокса.

    Возвращает PIL Image ровно ``FULL_IMAGE_BOX`` (600×400, 3:2) или ``None``.
    Благодаря точному боксу width/height в docx/pdf не искажают картинку,
    а высота у фото и карты гарантированно совпадает.
    """
    path = resolve_photo_path(url)

    if path is None:
        return None

    target_box = box or FULL_IMAGE_BOX

    try:
        from PIL import Image, ImageOps

        with Image.open(path) as source:
            source.load()
            image = source.convert("RGB")

        return ImageOps.fit(
            image,
            target_box,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
    except Exception:  # noqa: BLE001 — битый/не тот файл просто пропускаем
        logger.warning("Не удалось подготовить изображение полного вывода: %r", url)
        return None


# ---------------------------------------------------------------- построитель


def build_portfolio(
    items: Any,
    title: Any = None,
    with_photos: bool = False,
    with_maps: bool = False,
    requisites: Any = None,
    full_output: bool = False,
) -> dict:
    """Проверяет входные данные и собирает общую структуру для всех форматов.

    При ``with_photos=True`` в ``columns`` добавляется колонка «Фото»,
    при ``with_maps=True`` — колонка «Карта»; в каждой строке появляются
    поля ``photo`` / ``map`` (исходный URL; чтение файла делает сам формат,
    чтобы можно было отдать пустую ячейку).

    ``requisites`` — необязательный объект реквизитов; непустые поля
    попадают в ``requisites`` (список пар «подпись, значение») и печатаются
    компактным блоком под заголовком.

    ``full_output`` меняет только РАСКЛАДКУ (фото и карта в один ряд вместо
    колонок): набор данных и колонки не меняются, все форматы читают флаг
    из результата. Для картинок «полного вывода» в строках есть поля
    ``photo_full`` / ``map_full`` — крупные варианты с фолбэком на обычные.

    Возвращает::

        {
          "title": str,
          "columns": tuple[str, ...],
          "with_photos": bool,
          "with_maps": bool,
          "full_output": bool,
          "requisites": [(label, value), ...],
          "rows": [ {index, city, address, side, type, size, months, sum, sum_value, photo, map, photo_full, map_full}, ... ],
          "positions": int,
          "total": float,
          "summary": str,   # «ИТОГО: N позиций, S ₽»
        }

    Бросает PortfolioExportError при некорректных данных.
    """
    if not isinstance(items, list):
        raise PortfolioExportError("Поле items должно быть списком позиций.")

    if len(items) == 0:
        raise PortfolioExportError("Портфель пуст.")

    if len(items) > MAX_ITEMS:
        raise PortfolioExportError(
            f"Слишком много позиций: {len(items)}. Максимум — {MAX_ITEMS}."
        )

    rows: list[dict] = []
    total = 0.0

    for position, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            raise PortfolioExportError(
                f"Позиция №{position} должна быть объектом."
            )

        months = raw.get("months") or {}

        if not isinstance(months, dict):
            months = {}

        month_parts: list[str] = []
        item_sum = 0.0

        for month_name, value in months.items():
            label = _text(month_name) or "—"
            price = _extract_price(value)

            if price is None:
                month_parts.append(f"{label} — цена не указана")
            else:
                item_sum += price
                month_parts.append(f"{label} — {format_money(price)}")

        total += item_sum

        photo = _text(raw.get("photo"))
        # Карта-схема: локальный файл. Крупный card, иначе large, иначе
        # миниатюра — если ничего нет, ячейка будет пустой.
        map_url = (
            _text(raw.get("map_card"))
            or _text(raw.get("map_large"))
            or _text(raw.get("map_thumb"))
        )

        rows.append(
            {
                "index": position,
                "city": _text(raw.get("city")),
                "address": _text(raw.get("address")),
                "side": _text(raw.get("side")),
                "type": _text(raw.get("type")),
                "size": _text(raw.get("size")),
                # Пустая позиция остаётся в списке: пишем явный текст,
                # сумма при этом 0 ₽ (см. format_money).
                "months": ", ".join(month_parts) if month_parts else "ничего не выбрано",
                "sum": format_money(item_sum),
                "sum_value": item_sum,
                "photo": photo,
                "map": map_url,
                # Крупные варианты — только для «полного вывода» (7.5 см),
                # с фолбэком на обычные поля.
                "photo_full": _text(raw.get("photo_large")) or photo,
                "map_full": _text(raw.get("map_large")) or map_url,
            }
        )

    positions = len(rows)

    summary = (
        f"ИТОГО: {positions} {_positions_word(positions)}, {format_money(total)}"
    )

    columns = list(COLUMNS)

    if with_photos:
        columns.append(PHOTO_COLUMN)

    if with_maps:
        columns.append(MAP_COLUMN)

    columns = tuple(columns)

    return {
        "title": _text(title) or DEFAULT_TITLE,
        "columns": columns,
        "with_photos": bool(with_photos),
        "with_maps": bool(with_maps),
        "full_output": bool(full_output),
        "requisites": build_requisites_block(requisites),
        "rows": rows,
        "positions": positions,
        "total": total,
        "summary": summary,
    }


# ---------------------------------------------------------------- xlsx


def export_xlsx(portfolio: dict) -> bytes:
    """Excel-книга: жирная шапка, автоширина колонок, перенос строк."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    columns = portfolio["columns"]
    rows = portfolio["rows"]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Портфель"

    # Заголовок документа (строка 1, объединён по всем колонкам).
    sheet.append([portfolio["title"]])
    sheet.merge_cells(
        start_row=1, start_column=1, end_row=1, end_column=len(columns)
    )
    title_cell = sheet.cell(row=1, column=1)
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(vertical="center")

    # Блок реквизитов — сразу под заголовком (только непустые поля).
    requisites = portfolio.get("requisites") or []

    for label, value in requisites:
        sheet.append([f"{label}: {value}"])
        req_row = sheet.max_row
        sheet.merge_cells(
            start_row=req_row,
            start_column=1,
            end_row=req_row,
            end_column=len(columns),
        )
        req_cell = sheet.cell(row=req_row, column=1)
        req_cell.font = Font(size=10)
        req_cell.alignment = Alignment(vertical="center")

    # Шапка таблицы — сразу после заголовка и блока реквизитов.
    sheet.append(list(columns))
    header_row = sheet.max_row

    for col in range(1, len(columns) + 1):
        cell = sheet.cell(row=header_row, column=col)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )

    # Данные.
    wrap = Alignment(vertical="top", wrap_text=True)
    for row in rows:
        sheet.append(
            [
                row["index"],
                row["city"],
                row["address"],
                row["side"],
                row["type"],
                row["size"],
                row["months"],
                row["sum"],
            ]
        )

    last_data_row = sheet.max_row

    for r in range(header_row + 1, last_data_row + 1):
        for c in range(1, len(columns) + 1):
            sheet.cell(row=r, column=c).alignment = wrap

    # Итоговая строка.
    total_row = last_data_row + 1
    total_cell = sheet.cell(row=total_row, column=1, value=portfolio["summary"])
    total_cell.font = Font(bold=True)
    total_cell.alignment = Alignment(vertical="center")
    sheet.merge_cells(
        start_row=total_row,
        start_column=1,
        end_row=total_row,
        end_column=len(columns),
    )

    # Автоширина колонок по содержимому (без строки заголовка и итога).
    for idx, name in enumerate(columns, start=1):
        width = len(name)
        for r in range(header_row, last_data_row + 1):
            value = sheet.cell(row=r, column=idx).value
            if value is None:
                continue

            # Пустая строка даёт [].splitlines() == [] — max() упал бы,
            # поэтому подстраховываемся (поля позиции могут быть пустыми).
            lines = str(value).splitlines() or [""]
            longest = max(len(line) for line in lines)
            width = max(width, longest)
        sheet.column_dimensions[get_column_letter(idx)].width = min(
            max(width + 2, 8), 55
        )

    # Колонки «Фото»/«Карта»: миниатюры, вписанные в ячейку.
    with_photos = bool(portfolio.get("with_photos"))
    with_maps = bool(portfolio.get("with_maps"))

    if with_photos or with_maps:
        from openpyxl.drawing.image import Image as XLImage

        # Ссылки на открытые буферы держим до save(), иначе openpyxl
        # не сможет прочитать картинку.
        embedded: list[tuple[Any, io.BytesIO]] = []

        def add_image_column(field: str, box, col_index: int) -> None:
            letter = get_column_letter(col_index)
            sheet.column_dimensions[letter].width = 13

            for offset, row in enumerate(rows):
                image = load_photo_thumbnail(row.get(field), box)

                if image is None:
                    continue

                image_buffer = io.BytesIO(photo_to_bytes(image))
                excel_image = XLImage(image_buffer)
                excel_image.width = image.width
                excel_image.height = image.height

                row_index = header_row + 1 + offset
                sheet.add_image(excel_image, f"{letter}{row_index}")
                sheet.row_dimensions[row_index].height = max(
                    45, image.height * 0.78
                )

                embedded.append((excel_image, image_buffer))

        base_columns = len(COLUMNS)

        if with_photos:
            add_image_column("photo", XLSX_PHOTO_BOX, base_columns + 1)

        if with_maps:
            offset = 1 if with_photos else 0
            add_image_column("map", XLSX_PHOTO_BOX, base_columns + offset + 1)

    buffer = io.BytesIO()
    workbook.save(buffer)

    return buffer.getvalue()


# ---------------------------------------------------------------- docx


def _export_docx_full(portfolio: dict) -> bytes:
    """Word «полный вывод»: позиция абзацами, фото и карта — в один ряд.

    Портретная A4 с полями 1.5 см (рабочая ширина ~18 см): два изображения
    по 7.5 см встают в один ряд с запасом. Картинки предварительно
    cover-кроплены до 3:2, поэтому width/height (7.5 × 5 см) не искажают их
    и высота у фото и карты одинаковая.
    """
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt

    document = Document()

    section = document.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(1.5)
    section.top_margin = section.bottom_margin = Cm(1.5)

    document.add_heading(portfolio["title"], level=1)

    for label, value in portfolio.get("requisites") or []:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(f"{label}: {value}")
        run.font.size = Pt(9)

    with_photos = bool(portfolio.get("with_photos"))
    with_maps = bool(portfolio.get("with_maps"))

    for row in portfolio["rows"]:
        place = ", ".join(
            part for part in (row["city"], row["address"]) if part
        ) or "Адрес не указан"

        head = document.add_paragraph()
        head_run = head.add_run(
            f'{row["index"]}. {row["type"] or "Формат не указан"} — {place}'
        )
        head_run.bold = True

        meta_parts = []
        if row["side"]:
            meta_parts.append(f'Сторона: {row["side"]}')
        if row["size"]:
            meta_parts.append(f'Размер: {row["size"]}')
        if meta_parts:
            document.add_paragraph(" · ".join(meta_parts))

        # Изображения в один ряд (внутри одного абзаца, инлайн).
        candidates = []
        if with_photos:
            candidates.append(row.get("photo_full"))
        if with_maps:
            candidates.append(row.get("map_full"))

        loaded = []
        for url in candidates:
            image = load_full_image(url)
            if image is not None:
                loaded.append(image)

        if loaded:
            picture_paragraph = document.add_paragraph()
            for position, image in enumerate(loaded):
                if position:
                    picture_paragraph.add_run("    ")
                run = picture_paragraph.add_run()
                run.add_picture(
                    io.BytesIO(photo_to_bytes(image)),
                    width=Cm(FULL_IMAGE_WIDTH_CM),
                    height=Cm(FULL_IMAGE_HEIGHT_CM),
                )

        months_paragraph = document.add_paragraph()
        months_run = months_paragraph.add_run(f'Месяцы: {row["months"]}')
        months_run.font.size = Pt(9)

        sum_paragraph = document.add_paragraph()
        sum_run = sum_paragraph.add_run(f'Сумма: {row["sum"]}')
        sum_run.bold = True

        document.add_paragraph()

    summary_paragraph = document.add_paragraph()
    summary_run = summary_paragraph.add_run(portfolio["summary"])
    summary_run.bold = True

    buffer = io.BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def export_docx(portfolio: dict) -> bytes:
    """Word-документ: заголовок, таблица с теми же колонками, итог."""
    if portfolio.get("full_output"):
        return _export_docx_full(portfolio)

    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Inches, Pt

    document = Document()

    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = (
        section.page_height,
        section.page_width,
    )

    document.add_heading(portfolio["title"], level=1)

    # Компактный блок реквизитов под заголовком (только непустые поля).
    for label, value in portfolio.get("requisites") or []:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(f"{label}: {value}")
        run.font.size = Pt(9)

    columns = portfolio["columns"]
    with_photos = bool(portfolio.get("with_photos"))
    with_maps = bool(portfolio.get("with_maps"))
    table = document.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    table.autofit = False

    header_cells = table.rows[0].cells
    for idx, name in enumerate(columns):
        paragraph = header_cells[idx].paragraphs[0]
        run = paragraph.add_run(str(name))
        run.bold = True

    for row in portfolio["rows"]:
        cells = table.add_row().cells
        values = [
            row["index"],
            row["city"],
            row["address"],
            row["side"],
            row["type"],
            row["size"],
            row["months"],
            row["sum"],
        ]
        for idx, value in enumerate(values):
            cells[idx].text = str(value)

        base_cells = len(values)

        def add_docx_picture(cell_index: int, field: str) -> None:
            image = load_photo_thumbnail(row.get(field), DOCX_PHOTO_BOX)

            if image is None:
                return

            run = cells[cell_index].paragraphs[0].add_run()
            run.add_picture(
                io.BytesIO(photo_to_bytes(image)),
                width=Cm(DOCX_PHOTO_WIDTH_CM),
            )

        if with_photos:
            add_docx_picture(base_cells, "photo")

        if with_maps:
            add_docx_picture(base_cells + (1 if with_photos else 0), "map")

    # Пропорциональные ширины колонок (полезная ширина альбомного листа).
    if with_photos or with_maps:
        width_inches = (0.4, 1.5, 1.5, 0.7, 0.9, 0.8, 1.6, 1.0)
    else:
        width_inches = (0.4, 1.2, 1.8, 0.7, 1.0, 0.9, 2.0, 1.0)

    if with_photos:
        width_inches += (1.0,)

    if with_maps:
        width_inches += (1.0,)

    for idx, width in enumerate(width_inches):
        table.columns[idx].width = Inches(width)
        for row in table.rows:
            row.cells[idx].width = Inches(width)

    document.add_paragraph()
    summary_paragraph = document.add_paragraph()
    summary_run = summary_paragraph.add_run(portfolio["summary"])
    summary_run.bold = True

    buffer = io.BytesIO()
    document.save(buffer)

    return buffer.getvalue()


# ---------------------------------------------------------------- pdf


# Шрифты, в которых гарантированно есть кириллица, в порядке предпочтения.
_FONT_CANDIDATES = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf",
     "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
)

# Подстроки имён TTF-файлов, которые с высокой вероятностью содержат кириллицу.
_KNOWN_FONT_TOKENS = (
    "dejavusans",
    "dejavuserif",
    "liberationsans",
    "freesans",
    "notosans-regular",
    "notosans-bold",
    "notosans-italic",
    "pt_sans",
    "ptsans",
)


def find_cyrillic_fonts() -> tuple[str, str]:
    """Ищет пару (regular, bold) кириллических TTF-шрифтов.

    Сначала известные пути (DejaVuSans), затем — скан /usr/share/fonts
    по именам известных кириллических семейств. Если ничего не найдено,
    бросает FontUnavailableError.
    """
    for regular, bold in _FONT_CANDIDATES:
        regular_path = Path(regular)
        if regular_path.is_file():
            bold_path = Path(bold)
            return (
                str(regular_path),
                str(bold_path) if bold_path.is_file() else str(regular_path),
            )

    fonts_root = Path("/usr/share/fonts")
    if fonts_root.is_dir():
        for pattern in _KNOWN_FONT_TOKENS:
            for path in sorted(fonts_root.rglob("*.ttf")):
                if pattern in path.name.lower():
                    return str(path), str(path)

    raise FontUnavailableError(
        "Не найден кириллический TTF-шрифт для экспорта в PDF. "
        "Установите пакет fonts-dejavu (DejaVuSans.ttf) или другой "
        "шрифт с поддержкой кириллицы в /usr/share/fonts."
    )


def _register_pdf_fonts(regular: str, bold: str) -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_name = "PortfolioSans"
    bold_name = "PortfolioSans-Bold"

    pdfmetrics.registerFont(TTFont(regular_name, regular))
    pdfmetrics.registerFont(TTFont(bold_name, bold))
    pdfmetrics.registerFontFamily(
        regular_name,
        normal=regular_name,
        bold=bold_name,
        italic=regular_name,
        boldItalic=bold_name,
    )

    return regular_name, bold_name


def _pdf_paragraph(text: Any, style) -> "object":
    from reportlab.platypus import Paragraph

    value = escape(str(text if text is not None else ""))
    value = value.replace("\n", "<br/>")

    return Paragraph(value, style)


def _pdf_photo(url: Any, keepalive: list) -> "object":
    """Flowable-миниатюра фото для ячейки PDF (или пустая строка)."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage

    image = load_photo_thumbnail(url, PDF_PHOTO_BOX)

    if image is None:
        return ""

    width_px, height_px = image.size

    if not width_px:
        return ""

    buffer = io.BytesIO(photo_to_bytes(image))
    keepalive.append(buffer)

    display_width = PDF_PHOTO_WIDTH_MM * mm
    display_height = display_width * height_px / width_px

    return RLImage(buffer, width=display_width, height=display_height)


def _export_pdf_full(portfolio: dict) -> bytes:
    """PDF «полный вывод»: позиция абзацами, фото и карта — в один ряд.

    Портретная A4, поля 1.5 см. Изображения предварительно cover-кроплены
    до 3:2 (600×400 px), затем растянуты ровно в 7.5 × 5 см — пропорции
    сохранены, высота у фото и карты одинаковая.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Image as RLImage,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    regular, bold = find_cyrillic_fonts()
    font_regular, font_bold = _register_pdf_fonts(regular, bold)

    margin = 15 * mm

    title_style = ParagraphStyle(
        "FullTitle",
        fontName=font_bold,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#2E74B5"),
        spaceAfter=6,
    )
    head_style = ParagraphStyle(
        "FullHead", fontName=font_bold, fontSize=10.5, leading=13, spaceBefore=4
    )
    line_style = ParagraphStyle(
        "FullLine", fontName=font_regular, fontSize=9, leading=12
    )
    months_style = ParagraphStyle(
        "FullMonths", fontName=font_regular, fontSize=8.5, leading=11
    )
    sum_style = ParagraphStyle(
        "FullSum", fontName=font_bold, fontSize=9.5, leading=12
    )
    summary_style = ParagraphStyle(
        "FullSummary", fontName=font_bold, fontSize=11, leading=14, spaceBefore=4
    )
    requisites_style = ParagraphStyle(
        "FullRequisites",
        fontName=font_regular,
        fontSize=9,
        leading=12,
        spaceAfter=6,
    )

    story = [_pdf_paragraph(portfolio["title"], title_style)]

    for label, value in portfolio.get("requisites") or []:
        story.append(_pdf_paragraph(f"{label}: {value}", requisites_style))

    if portfolio.get("requisites"):
        story.append(Spacer(1, 6))

    with_photos = bool(portfolio.get("with_photos"))
    with_maps = bool(portfolio.get("with_maps"))

    photo_buffers: list[io.BytesIO] = []

    for row in portfolio["rows"]:
        place = ", ".join(
            part for part in (row["city"], row["address"]) if part
        ) or "Адрес не указан"

        story.append(
            _pdf_paragraph(
                f'{row["index"]}. {row["type"] or "Формат не указан"} — {place}',
                head_style,
            )
        )

        meta_parts = []
        if row["side"]:
            meta_parts.append(f'Сторона: {row["side"]}')
        if row["size"]:
            meta_parts.append(f'Размер: {row["size"]}')
        if meta_parts:
            story.append(_pdf_paragraph(" · ".join(meta_parts), line_style))

        image_cells = []
        candidates = []
        if with_photos:
            candidates.append(row.get("photo_full"))
        if with_maps:
            candidates.append(row.get("map_full"))

        for url in candidates:
            image = load_full_image(url)
            if image is None:
                continue
            buffer = io.BytesIO(photo_to_bytes(image))
            photo_buffers.append(buffer)
            image_cells.append(
                RLImage(
                    buffer,
                    width=FULL_IMAGE_WIDTH_CM * cm,
                    height=FULL_IMAGE_HEIGHT_CM * cm,
                )
            )

        if image_cells:
            images_table = Table(
                [image_cells],
                colWidths=[FULL_IMAGE_WIDTH_CM * cm] * len(image_cells),
                hAlign="LEFT",
            )
            images_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(images_table)

        story.append(_pdf_paragraph(f'Месяцы: {row["months"]}', months_style))
        story.append(_pdf_paragraph(f'Сумма: {row["sum"]}', sum_style))
        story.append(Spacer(1, 10))

    story.append(
        _pdf_paragraph(portfolio["summary"], summary_style)
    )

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=portfolio["title"],
    )
    document.build(story)

    return buffer.getvalue()


def export_pdf(portfolio: dict) -> bytes:
    """PDF-документ (альбомная A4) с кириллическим шрифтом DejaVuSans."""
    if portfolio.get("full_output"):
        return _export_pdf_full(portfolio)

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

    regular, bold = find_cyrillic_fonts()
    font_regular, font_bold = _register_pdf_fonts(regular, bold)

    # Поля и оформление — как в DOCX (Word: пустые поля 2 см по кругу,
    # заголовок Heading 1 — синий, реквизиты отдельными строками, таблица
    # «Table Grid» без заливки, «Итого» — отдельный жирный абзац).
    margin = 20 * mm
    left_margin = right_margin = margin
    available_width = landscape(A4)[0] - left_margin - right_margin

    title_style = ParagraphStyle(
        "PortfolioTitle",
        fontName=font_bold,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#2E74B5"),
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "PortfolioCell",
        fontName=font_regular,
        fontSize=9,
        leading=11,
    )
    bold_style = ParagraphStyle(
        "PortfolioCellBold",
        parent=cell_style,
        fontName=font_bold,
    )
    requisites_style = ParagraphStyle(
        "PortfolioRequisites",
        fontName=font_regular,
        fontSize=9,
        leading=12,
        spaceAfter=6,
    )
    summary_style = ParagraphStyle(
        "PortfolioSummary",
        fontName=font_bold,
        fontSize=11,
        leading=14,
        spaceBefore=4,
        spaceAfter=4,
    )

    story = [
        _pdf_paragraph(portfolio["title"], title_style),
        Spacer(1, 4),
    ]

    # Компактный блок реквизитов под заголовком (только непустые поля).
    requisites = portfolio.get("requisites") or []

    for label, value in requisites:
        story.append(_pdf_paragraph(f"{label}: {value}", requisites_style))

    if requisites:
        story.append(Spacer(1, 6))

    columns = portfolio["columns"]
    with_photos = bool(portfolio.get("with_photos"))
    with_maps = bool(portfolio.get("with_maps"))
    data = [[_pdf_paragraph(name, bold_style) for name in columns]]

    # reportlab читает file-like лениво (на этапе build), поэтому буферы
    # миниатюр должны жить до document.build(story).
    photo_buffers: list[io.BytesIO] = []

    for row in portfolio["rows"]:
        cells = [
            _pdf_paragraph(row["index"], cell_style),
            _pdf_paragraph(row["city"], cell_style),
            _pdf_paragraph(row["address"], cell_style),
            _pdf_paragraph(row["side"], cell_style),
            _pdf_paragraph(row["type"], cell_style),
            _pdf_paragraph(row["size"], cell_style),
            _pdf_paragraph(row["months"], cell_style),
            _pdf_paragraph(row["sum"], cell_style),
        ]

        if with_photos:
            cells.append(_pdf_photo(row.get("photo"), photo_buffers))

        if with_maps:
            cells.append(_pdf_photo(row.get("map"), photo_buffers))

        data.append(cells)

    # Пропорциональные ширины колонок: сумма растягивается на лист.
    if with_photos or with_maps:
        base_widths_mm = (7, 20, 40, 12, 17, 18, 66, 24)
    else:
        base_widths_mm = (8, 26, 48, 14, 20, 22, 95, 26)

    if with_photos:
        base_widths_mm += (18,)

    if with_maps:
        base_widths_mm += (18,)

    base_total = sum(base_widths_mm)
    scale = (available_width / mm) / base_total
    col_widths = [w * scale * mm for w in base_widths_mm]

    table = Table(
        data,
        colWidths=col_widths,
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    story.append(table)

    # «Итого» — отдельный жирный абзац под таблицей (как в DOCX).
    story.append(_pdf_paragraph(portfolio["summary"], summary_style))

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=margin,
        bottomMargin=margin,
        title=portfolio["title"],
    )
    document.build(story)

    return buffer.getvalue()


# ---------------------------------------------------------------- фасад


# ---------------------------------------------------------------- LibreOffice
#
# doc/odt/rtf/pdf получаем из ОДНОГО канонического DOCX через LibreOffice —
# так pdf, doc/docx и odt гарантированно идентичны (и на их основе идёт печать).
# xls/ods — аналогично из канонического XLSX. Требуется установленный soffice.


# Фильтры конвертации для «старых» форматов MS Office.
_LO_FILTERS = {
    "doc": "doc:MS Word 97",
    "xls": "xls:MS Excel 97",
}


def _soffice_binary() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)

        if path:
            return path

    return None


def libreoffice_convert(
    content: bytes,
    src_ext: str,
    target_ext: str,
    timeout: int = 120,
) -> bytes:
    """Конвертирует документ через headless LibreOffice.

    Каждый вызов — в своём временном каталоге с отдельным профилем
    (-env:UserInstallation), иначе параллельные конвертации конфликтуют.
    """
    binary = _soffice_binary()

    if not binary:
        raise PortfolioExportError(
            "Конвертер LibreOffice недоступен на сервере."
        )

    workdir = tempfile.mkdtemp(prefix="albion-lo-")

    try:
        src_path = os.path.join(workdir, f"portfolio.{src_ext}")

        with open(src_path, "wb") as handle:
            handle.write(content)

        profile = os.path.join(workdir, "profile")
        target = _LO_FILTERS.get(target_ext, target_ext)

        command = [
            binary,
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            target,
            "--outdir",
            workdir,
            src_path,
        ]

        try:
            subprocess.run(
                command,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PortfolioExportError(
                "Превышено время подготовки файла."
            ) from exc

        out_path = os.path.join(workdir, f"portfolio.{target_ext}")

        if not os.path.exists(out_path):
            raise PortfolioExportError(
                f"Не удалось подготовить файл формата {target_ext}."
            )

        with open(out_path, "rb") as handle:
            return handle.read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- текст
#
# csv/txt/md/json — «только текст»: адрес, сторона, формат, месяцы, суммы.
# Ни фото, ни карт, независимо от переключателя «полный/краткий вывод».


def _position_head(row: dict) -> str:
    place = ", ".join(part for part in (row["city"], row["address"]) if part)
    place = place or "Адрес не указан"

    return f'{row["index"]}. {row["type"] or "Формат не указан"} — {place}'


def export_txt(portfolio: dict) -> bytes:
    lines: list[str] = [portfolio["title"], ""]

    for row in portfolio["rows"]:
        lines.append(_position_head(row))

        if row["side"]:
            lines.append(f'   Сторона: {row["side"]}')

        if row["size"]:
            lines.append(f'   Размер: {row["size"]}')

        lines.append(f'   Месяцы: {row["months"]}')
        lines.append(f'   Сумма: {row["sum"]}')

    lines.append("")
    lines.append(portfolio["summary"])

    for label, value in portfolio["requisites"]:
        lines.append(f"{label}: {value}")

    return ("\n".join(lines)).encode("utf-8")


def export_csv(portfolio: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

    writer.writerow(TEXT_COLUMNS)

    for row in portfolio["rows"]:
        writer.writerow(
            [
                row["index"],
                row["city"],
                row["address"],
                row["side"],
                row["type"],
                row["size"],
                row["months"],
                row["sum"],
            ]
        )

    writer.writerow([])
    writer.writerow(["", "", "", "", "", "", "ИТОГО", format_money(portfolio["total"])])

    # BOM — чтобы Excel распознал UTF-8.
    return buffer.getvalue().encode("utf-8-sig")


def export_md(portfolio: dict) -> bytes:
    lines: list[str] = [f'# {portfolio["title"]}', ""]
    lines.append("| " + " | ".join(TEXT_COLUMNS) + " |")
    lines.append("|" + "---|" * len(TEXT_COLUMNS))

    for row in portfolio["rows"]:
        cells = [
            str(row["index"]),
            row["city"],
            row["address"],
            row["side"],
            row["type"],
            row["size"],
            row["months"].replace("|", "\\|"),
            row["sum"],
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append(
        f'**{portfolio["summary"]}**'
    )

    if portfolio["requisites"]:
        lines.append("")

        for label, value in portfolio["requisites"]:
            lines.append(f"- **{label}:** {value}")

    return ("\n".join(lines)).encode("utf-8")


def export_json(portfolio: dict) -> bytes:
    data = {
        "title": portfolio["title"],
        "positions": portfolio["positions"],
        "total": portfolio["total"],
        "summary": portfolio["summary"],
        "requisites": [
            {"label": label, "value": value}
            for label, value in portfolio["requisites"]
        ],
        "items": [
            {
                "index": row["index"],
                "city": row["city"],
                "address": row["address"],
                "side": row["side"],
                "type": row["type"],
                "size": row["size"],
                "months": row["months"],
                "sum": row["sum"],
                "sum_value": row["sum_value"],
            }
            for row in portfolio["rows"]
        ],
    }

    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


# ---------------------------------------------------------------- render


def render(
    items: Any,
    fmt: str,
    title: Any = None,
    with_photos: bool = False,
    with_maps: bool = False,
    requisites: Any = None,
    full_output: bool = False,
) -> bytes:
    """Собирает портфель и рендерит его в выбранный формат.

    Документы: docx (канонический) → doc/odt/rtf/pdf через LibreOffice,
    поэтому pdf, doc/docx и odt идентичны. xlsx (канонический) → xls/ods.
    «Текстовые» форматы (csv/txt/md/json) отдают только текстовую часть,
    без фото/карт, независимо от full_output.

    Непустые ``requisites`` печатаются компактным блоком под заголовком.
    """
    fmt = (fmt or "").strip().lower()

    if fmt not in SUPPORTED_FORMATS:
        raise PortfolioExportError(
            f"Неподдерживаемый формат: {fmt!r}. "
            "Допустимо: " + ", ".join(SUPPORTED_FORMATS) + "."
        )

    text_only = fmt in TEXT_FORMATS

    portfolio = build_portfolio(
        items,
        title,
        with_photos=False if text_only else with_photos,
        with_maps=False if text_only else with_maps,
        requisites=requisites,
        full_output=False if text_only else full_output,
    )

    if fmt == "xlsx":
        return export_xlsx(portfolio)

    if fmt == "xls":
        return libreoffice_convert(export_xlsx(portfolio), "xlsx", "xls")

    if fmt == "docx":
        return export_docx(portfolio)

    if fmt == "doc":
        return libreoffice_convert(export_docx(portfolio), "docx", "doc")

    if fmt == "odt":
        return libreoffice_convert(export_docx(portfolio), "docx", "odt")

    if fmt == "rtf":
        return libreoffice_convert(export_docx(portfolio), "docx", "rtf")

    if fmt == "ods":
        return libreoffice_convert(export_xlsx(portfolio), "xlsx", "ods")

    if fmt == "pdf":
        # Тот же канонический docx → pdf, что и doc/odt: файлы идентичны.
        # Если LibreOffice недоступен — откат на прежний reportlab-рендер.
        try:
            return libreoffice_convert(export_docx(portfolio), "docx", "pdf")
        except PortfolioExportError:
            return export_pdf(portfolio)

    if fmt == "csv":
        return export_csv(portfolio)

    if fmt == "txt":
        return export_txt(portfolio)

    if fmt == "md":
        return export_md(portfolio)

    if fmt == "json":
        return export_json(portfolio)

    raise PortfolioExportError(
        f"Неподдерживаемый формат: {fmt!r}. "
        "Допустимо: " + ", ".join(SUPPORTED_FORMATS) + "."
    )


def build_filename(fmt: str, today: date | None = None) -> str:
    """albion-portfolio-YYYYMMDD.<ext>"""
    day = today or date.today()

    return f"albion-portfolio-{day.strftime('%Y%m%d')}.{fmt}"
