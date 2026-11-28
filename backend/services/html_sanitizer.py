"""Серверная очистка HTML из админских полей.

Клиент уже прогоняет ``custom_html`` через DOMPurify (см. InfoPage.vue), но
API не должен отдавать сырой HTML: тот же контент могут запросить мобильное
приложение, экспорт или новый компонент. Здесь — консервативный allowlist
на базе lxml: без скриптов, обработчиков событий, iframe, style и
javascript:-ссылок.
"""
from __future__ import annotations

import re
from typing import Iterable

from lxml import etree, html


# Теги, которые безопасно оставить в текстовом блоке.
_ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "caption",
    "code",
    "div",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "small",
    "source",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
    "video",
}

# Эти теги удаляем вместе с содержимым: простого drop_tag() мало.
_DROP_TREE_TAGS = {
    "applet",
    "audio",
    "base",
    "embed",
    "form",
    "frame",
    "frameset",
    "iframe",
    "input",
    "link",
    "math",
    "meta",
    "object",
    "option",
    "script",
    "select",
    "style",
    "svg",
    "template",
    "textarea",
}

_GLOBAL_ATTRS = {"class", "dir", "lang", "title"}

_TAG_ATTRS = {
    "a": {"href", "rel", "target"},
    "img": {"alt", "height", "loading", "src", "width"},
    "ol": {"start", "type"},
    "source": {"src", "type"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "video": {
        "controls",
        "height",
        "loop",
        "muted",
        "playsinline",
        "poster",
        "preload",
        "src",
        "width",
    },
}

_URL_ATTRS = {"href", "poster", "src"}
_SAFE_URL_PREFIXES = ("http://", "https://", "/", "#")
_SAFE_HREF_PREFIXES = _SAFE_URL_PREFIXES + ("mailto:", "tel:")
_DATA_IMAGE_PREFIX = "data:image/"

_CLASS_RE = re.compile(r"[^A-Za-z0-9_\-\s]")


def _safe_url(value: str, *, allow_data_image: bool = False) -> str:
    raw = str(value or "").strip()

    if not raw or any(ch in raw for ch in ("\x00", "\n", "\r", "\t")):
        return ""

    lowered = raw.lower()

    if lowered.startswith(_SAFE_HREF_PREFIXES):
        return raw

    if allow_data_image and lowered.startswith(_DATA_IMAGE_PREFIX):
        if ";base64," in lowered:
            return raw

    return ""


def _safe_int(value: str) -> str:
    raw = str(value or "").strip()
    return raw if raw.isdigit() else ""


def _clean_element(element: etree._Element) -> None:
    # Родитель уже удалён вместе с опасным контейнером (например, svg).
    if element.getparent() is None:
        return

    if not isinstance(element.tag, str):
        # Комментарии и processing instructions.
        element.drop_tree()
        return

    tag = element.tag.lower()

    if tag in _DROP_TREE_TAGS:
        element.drop_tree()
        return

    if tag not in _ALLOWED_TAGS:
        # Неизвестную разметку убираем, но текст внутри сохраняем.
        element.drop_tag()
        return

    allowed = _GLOBAL_ATTRS | _TAG_ATTRS.get(tag, set())

    for name in list(element.attrib):
        attr = name.lower()
        raw = element.attrib[name]

        if attr not in allowed:
            del element.attrib[name]
            continue

        if attr == "class":
            cleaned = _CLASS_RE.sub("", raw).strip()
            if cleaned:
                element.set(name, cleaned)
            else:
                del element.attrib[name]
            continue

        if attr in _URL_ATTRS:
            safe = _safe_url(
                raw,
                allow_data_image=(tag == "img" and attr == "src"),
            )
            if safe:
                element.set(name, safe)
            else:
                del element.attrib[name]
            continue

        if attr in {"width", "height", "colspan", "rowspan", "start"}:
            safe = _safe_int(raw)
            if safe:
                element.set(name, safe)
            else:
                del element.attrib[name]
            continue

        if attr == "loading":
            element.set(
                name,
                "lazy" if raw.strip().lower() == "lazy" else "eager",
            )
            continue

        if attr == "target":
            if raw.strip() != "_blank":
                del element.attrib[name]
            continue

    if tag == "a" and element.get("target") == "_blank":
        element.set("rel", "noopener noreferrer")


def sanitize_html(value: str) -> str:
    """Возвращает безопасный HTML-фрагмент (или пустую строку)."""
    text = str(value or "")

    if not text.strip():
        return ""

    try:
        root = html.fragment_fromstring(text, create_parent="div")
    except (etree.ParserError, TypeError, ValueError):
        return ""

    if root is None:
        return ""

    for element in list(root.iter()):
        if element is root:
            continue
        _clean_element(element)

    serialized = html.tostring(root, encoding="unicode")

    # fragment_fromstring(create_parent="div") всегда добавляет обёртку.
    if serialized.startswith("<div>") and serialized.endswith("</div>"):
        return serialized[5:-6]

    return serialized


def sanitize_all(values: Iterable[str]) -> list[str]:
    """Удобно для списков: очищает каждое значение."""
    return [sanitize_html(value) for value in values]
