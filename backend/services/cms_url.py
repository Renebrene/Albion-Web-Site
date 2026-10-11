"""Validation for URLs editable through the site's CMS."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

_CONTROL_OR_BACKSLASH = re.compile(r"[\x00-\x1f\x7f\\]")
_TEL_NUMBER = re.compile(r"^\+?[0-9(). -]{3,40}$")
_EMAIL_ADDRESS = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def clean_cms_url(value: object) -> str:
    """Return a safe relative, web, mail, telephone, or fragment URL.

    Empty values are allowed for optional buttons. Protocol-relative URLs and
    executable/unknown schemes are rejected rather than stored.
    """
    url = str(value or "").strip()
    if not url:
        return ""
    if any(char in url for char in "\r\n\t"):
        raise ValueError("Ссылка содержит недопустимые символы")
    url = url.replace(" ", "%20")
    if _CONTROL_OR_BACKSLASH.search(url):
        raise ValueError("Ссылка содержит недопустимые символы")

    if url.startswith("#"):
        return url

    if url.startswith("/"):
        if url.startswith("//"):
            raise ValueError("Ссылка должна быть относительной или начинаться с https://")
        return url

    parts = urlsplit(url)
    scheme = parts.scheme.lower()

    # Bare relative routes (e.g. "novosti") have no scheme and are safe.
    if not scheme:
        return url

    if (
        scheme in {"http", "https"}
        and parts.hostname
        and not parts.username
        and not parts.password
    ):
        return url
    if scheme == "mailto" and _EMAIL_ADDRESS.fullmatch(parts.path):
        return url
    if scheme == "tel" and _TEL_NUMBER.fullmatch(unquote(parts.path)):
        return url

    raise ValueError(
        "Допустимы относительные ссылки, http(s), mailto, tel и якоря (#...)"
    )


def safe_cms_href(value: object) -> str:
    """Defensive frontend-like fallback for persisted legacy content."""
    try:
        return clean_cms_url(value)
    except ValueError:
        return ""
