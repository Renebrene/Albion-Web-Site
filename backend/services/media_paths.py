"""Разрешение путей к медиа-файлам конструкций для CMS-контента.

Файлы конструкций лежат в папках импорта:

    /storage/constructions/imports/<import_key>/<category>/<variant>/<hash>.<ext>

`import_key` — метка времени импорта. При новом импорте создаётся новая
папка, а старая удаляется. Если в CMS (слайды главной, фото geo) сохранён
абсолютный путь со старым `import_key`, после импорта он начинает отдавать
404 — «фото пропадает».

Имя файла (контентный хэш) между импортами стабильно, поэтому достаточно
переписать сегмент `import_key` на текущий активный импорт — фото находится
без ручной перенастройки CMS.
"""
from __future__ import annotations

_PREFIX = "/storage/constructions/imports/"


def fetch_active_import_key(conn) -> str | None:
    """Ключ текущего активного импорта конструкций (или None)."""
    row = conn.execute(
        """
        SELECT import_key
        FROM construction_imports
        WHERE status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    return row[0] if row else None


def _to_absolute(path: str | None) -> str:
    value = str(path or "").strip()

    if not value:
        return ""

    if value.startswith("/"):
        return value

    return f"/storage/{value}"


def resolve_import_url(path: str | None, active_key: str | None) -> str:
    """Приводит сохранённый путь к рабочему URL текущего импорта.

    Пути вне `constructions/imports` и пути с уже актуальным ключом
    возвращаются без изменений.
    """
    url = _to_absolute(path)

    if not url.startswith(_PREFIX):
        return url

    rest = url[len(_PREFIX) :]
    parts = rest.split("/", 1)

    if len(parts) != 2:
        return url

    old_key, tail = parts

    if not active_key or old_key == active_key:
        return url

    return f"{_PREFIX}{active_key}/{tail}"
