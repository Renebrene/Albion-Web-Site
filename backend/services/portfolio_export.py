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

import io
import logging
import math
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- константы

SUPPORTED_FORMATS = ("xlsx", "docx", "pdf")

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

# Дополнительная колонка, появляется только при with_photos=true.
PHOTO_COLUMN = "Фото"

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

CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
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


# ---------------------------------------------------------------- построитель


def build_portfolio(
    items: Any,
    title: Any = None,
    with_photos: bool = False,
    requisites: Any = None,
) -> dict:
    """Проверяет входные данные и собирает общую структуру для всех форматов.

    При ``with_photos=True`` в ``columns`` добавляется колонка «Фото»,
    а в каждой строке появляется поле ``photo`` (исходный URL; чтение
    файла делает сам формат, чтобы можно было отдать пустую ячейку).

    ``requisites`` — необязательный объект реквизитов; непустые поля
    попадают в ``requisites`` (список пар «подпись, значение») и печатаются
    компактным блоком под заголовком.

    Возвращает::

        {
          "title": str,
          "columns": tuple[str, ...],
          "with_photos": bool,
          "requisites": [(label, value), ...],
          "rows": [ {index, city, address, side, type, size, months, sum, sum_value, photo}, ... ],
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

        rows.append(
            {
                "index": position,
                "city": _text(raw.get("city")),
                "address": _text(raw.get("address")),
                "side": _text(raw.get("side")),
                "type": _text(raw.get("type")),
                "size": _text(raw.get("size")),
                "months": ", ".join(month_parts) if month_parts else "—",
                "sum": format_money(item_sum),
                "sum_value": item_sum,
                "photo": _text(raw.get("photo")),
            }
        )

    positions = len(rows)

    summary = (
        f"ИТОГО: {positions} {_positions_word(positions)}, {format_money(total)}"
    )

    columns = (
        COLUMNS + (PHOTO_COLUMN,) if with_photos else COLUMNS
    )

    return {
        "title": _text(title) or DEFAULT_TITLE,
        "columns": columns,
        "with_photos": bool(with_photos),
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

    # Колонка «Фото»: миниатюры, вписанные в ячейку (при with_photos=true).
    if portfolio.get("with_photos"):
        from openpyxl.drawing.image import Image as XLImage

        photo_col = len(columns)
        letter = get_column_letter(photo_col)
        sheet.column_dimensions[letter].width = 13

        # Ссылки на открытые буферы держим до save(), иначе openpyxl
        # не сможет прочитать картинку.
        embedded: list[tuple[Any, io.BytesIO]] = []

        for offset, row in enumerate(rows):
            image = load_photo_thumbnail(row.get("photo"), XLSX_PHOTO_BOX)

            if image is None:
                continue

            photo_buffer = io.BytesIO(photo_to_bytes(image))
            excel_image = XLImage(photo_buffer)
            excel_image.width = image.width
            excel_image.height = image.height

            row_index = header_row + 1 + offset
            sheet.add_image(excel_image, f"{letter}{row_index}")
            sheet.row_dimensions[row_index].height = max(
                45, image.height * 0.78
            )

            embedded.append((excel_image, photo_buffer))

    buffer = io.BytesIO()
    workbook.save(buffer)

    return buffer.getvalue()


# ---------------------------------------------------------------- docx


def export_docx(portfolio: dict) -> bytes:
    """Word-документ: заголовок, таблица с теми же колонками, итог."""
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

        if with_photos:
            image = load_photo_thumbnail(row.get("photo"), DOCX_PHOTO_BOX)

            if image is not None:
                run = cells[-1].paragraphs[0].add_run()
                run.add_picture(
                    io.BytesIO(photo_to_bytes(image)),
                    width=Cm(DOCX_PHOTO_WIDTH_CM),
                )

    # Пропорциональные ширины колонок (полезная ширина альбомного листа).
    if with_photos:
        width_inches = (0.4, 1.5, 1.5, 0.7, 0.9, 0.8, 1.6, 1.0, 1.0)
    else:
        width_inches = (0.4, 1.2, 1.8, 0.7, 1.0, 0.9, 2.0, 1.0)

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


def export_pdf(portfolio: dict) -> bytes:
    """PDF-документ (альбомная A4) с кириллическим шрифтом DejaVuSans."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

    regular, bold = find_cyrillic_fonts()
    font_regular, font_bold = _register_pdf_fonts(regular, bold)

    left_margin = right_margin = 10 * mm
    available_width = landscape(A4)[0] - left_margin - right_margin

    title_style = ParagraphStyle(
        "PortfolioTitle",
        fontName=font_bold,
        fontSize=14,
        leading=18,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "PortfolioCell",
        fontName=font_regular,
        fontSize=7.5,
        leading=9.5,
    )
    bold_style = ParagraphStyle(
        "PortfolioCellBold",
        parent=cell_style,
        fontName=font_bold,
    )
    requisites_style = ParagraphStyle(
        "PortfolioRequisites",
        fontName=font_regular,
        fontSize=8,
        leading=10,
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

        data.append(cells)

    # Итоговая строка — объединена по всем колонкам.
    summary_index = len(data)
    data.append(
        [_pdf_paragraph(portfolio["summary"], bold_style)]
        + [""] * (len(columns) - 1)
    )

    # Пропорциональные ширины колонок: сумма растягивается на лист.
    if with_photos:
        base_widths_mm = (7, 20, 40, 12, 17, 18, 66, 24, 18)
    else:
        base_widths_mm = (8, 26, 48, 14, 20, 22, 95, 26)

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
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9a9a9a")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9e9e9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("SPAN", (0, summary_index), (-1, summary_index)),
                (
                    "BACKGROUND",
                    (0, summary_index),
                    (-1, summary_index),
                    colors.HexColor("#f2f2f2"),
                ),
                ("TOPPADDING", (0, summary_index), (-1, summary_index), 6),
                ("BOTTOMPADDING", (0, summary_index), (-1, summary_index), 6),
            ]
        )
    )

    story.append(table)

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=portfolio["title"],
    )
    document.build(story)

    return buffer.getvalue()


# ---------------------------------------------------------------- фасад


def render(
    items: Any,
    fmt: str,
    title: Any = None,
    with_photos: bool = False,
    requisites: Any = None,
) -> bytes:
    """Собирает портфель и рендерит его в выбранный формат.

    При ``with_photos=True`` добавляется колонка «Фото» с миниатюрами.
    Непустые ``requisites`` печатаются компактным блоком под заголовком.
    """
    portfolio = build_portfolio(
        items, title, with_photos=with_photos, requisites=requisites
    )

    if fmt == "xlsx":
        return export_xlsx(portfolio)

    if fmt == "docx":
        return export_docx(portfolio)

    if fmt == "pdf":
        return export_pdf(portfolio)

    raise PortfolioExportError(
        f"Неподдерживаемый формат: {fmt}. Допустимо: xlsx, docx, pdf."
    )


def build_filename(fmt: str, today: date | None = None) -> str:
    """albion-portfolio-YYYYMMDD.<ext>"""
    day = today or date.today()

    return f"albion-portfolio-{day.strftime('%Y%m%d')}.{fmt}"
