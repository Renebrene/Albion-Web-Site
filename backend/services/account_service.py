"""Логика личных кабинетов (ЛК) клиентов и менеджеров.

Авторизация только по логину и паролю (логин может быть на русском).
Персональные данные не хранятся — только логин, хеши пароля и секретной
фразы. Восстановление пароля — по секретной фразе.

В БД хранится только SHA-256 хеш session token (как в auth_service).
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Json
from pwdlib import PasswordHash

from backend.services.data_service import get_connection


PASSWORD_HASH = PasswordHash.recommended()

SESSION_LIFETIME = timedelta(days=7)

# Логин: буквы (в т.ч. русские), цифры, точка, подчёркивание, дефис.
LOGIN_RE = re.compile(r"^[A-Za-z0-9._\-Ѐ-ӿ]{3,}$")

MIN_PASSWORD_LENGTH = 4
MIN_SECRET_PHRASE_LENGTH = 4

ALLOWED_ROLES = {"client", "manager"}

# Реквизиты пользователя ЛК для выгрузки/печати портфеля. Все поля — строки.
REQUISITE_FIELDS = (
    "organization",
    "inn",
    "kpp",
    "address",
    "phone",
    "email",
    "contact",
)

# Разумный предел длины одного поля реквизитов.
MAX_REQUISITE_LENGTH = 300


def normalize_login(login: str) -> str:
    """Нормализация логина: обрезка пробелов по краям."""
    return (login or "").strip()


def hash_token(token: str) -> str:
    """SHA-256 хеш session token (в БД хранится только он)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_requisites(value) -> dict:
    """Приводит реквизиты к dict с 7 строковыми ключами.

    Отсутствующие/None значения превращаются в пустые строки, значения
    обрезаются по краям и ограничиваются MAX_REQUISITE_LENGTH. Лишние
    ключи отбрасываются.
    """
    source = value if isinstance(value, dict) else {}

    result: dict[str, str] = {}

    for field in REQUISITE_FIELDS:
        raw = source.get(field, "")
        text = "" if raw is None else str(raw).strip()
        result[field] = text[:MAX_REQUISITE_LENGTH]

    return result


def _row_to_user(row) -> dict:
    user_id, login, role, is_active, requisites = row
    return {
        "id": user_id,
        "login": login,
        "role": role,
        "is_active": is_active,
        "requisites": normalize_requisites(requisites),
    }


def register(
    login: str,
    password: str,
    secret_phrase: str,
    role: str = "client",
) -> dict:
    """
    Регистрирует аккаунт и сразу выдаёт session token (авто-логин).

    Возвращает {"token": str, "user": {...}}.
    При ошибке валидации/занятости логина бросает ValueError.
    """
    login = normalize_login(login)
    password = password or ""
    secret_phrase = (secret_phrase or "").strip()
    role = (role or "client").strip().lower()

    if not LOGIN_RE.match(login):
        raise ValueError(
            "Логин должен быть не короче 3 символов и может содержать "
            "буквы (включая русские), цифры, точку, дефис и подчёркивание"
        )

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Пароль должен быть не короче 4 символов")

    if len(secret_phrase) < MIN_SECRET_PHRASE_LENGTH:
        raise ValueError("Секретная фраза должна быть не короче 4 символов")

    if role not in ALLOWED_ROLES:
        raise ValueError("Недопустимая роль")

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM user_accounts
            WHERE lower(login) = lower(%s)
            LIMIT 1
            """,
            (login,),
        ).fetchone()

        if existing is not None:
            raise ValueError("Такой логин уже занят")

        password_hash = PASSWORD_HASH.hash(password)
        secret_hash = PASSWORD_HASH.hash(secret_phrase)

        row = conn.execute(
            """
            INSERT INTO user_accounts
                (login, password_hash, role, secret_phrase_hash)
            VALUES
                (%s, %s, %s, %s)
            RETURNING id, login, role, is_active, requisites
            """,
            (login, password_hash, role, secret_hash),
        ).fetchone()

    user = _row_to_user(row)
    token = create_session(user["id"])

    return {
        "token": token,
        "user": user,
    }


def authenticate(login: str, password: str) -> dict | None:
    """
    Проверяет логин и пароль активного аккаунта.

    Возвращает данные пользователя либо None.
    """
    login = normalize_login(login)

    if not login or not password:
        return None

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, login, password_hash, role, is_active, requisites
            FROM user_accounts
            WHERE lower(login) = lower(%s)
              AND is_active = TRUE
            LIMIT 1
            """,
            (login,),
        ).fetchone()

    if user is None:
        return None

    user_id, user_login, stored_hash, role, is_active, requisites = user

    try:
        valid = PASSWORD_HASH.verify(password, stored_hash)
    except Exception:
        valid = False

    if not valid:
        return None

    return {
        "id": user_id,
        "login": user_login,
        "role": role,
        "is_active": is_active,
        "requisites": normalize_requisites(requisites),
    }


def create_session(account_id: int) -> str:
    """
    Создаёт сессию аккаунта сроком 7 дней.

    Возвращает сам token; в PostgreSQL сохраняется только его SHA-256 хеш.
    """
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO account_sessions
                (account_id, token_hash, expires_at)
            VALUES
                (%s, %s, %s)
            """,
            (account_id, token_hash, expires_at),
        )

    return token


def get_current_user(token: str | None) -> dict | None:
    """Проверяет session token и возвращает активного пользователя."""
    if not token:
        return None

    token_hash = hash_token(token)

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT u.id, u.login, u.role, u.is_active, u.requisites
            FROM account_sessions s
            JOIN user_accounts u
              ON u.id = s.account_id
            WHERE s.token_hash = %s
              AND s.expires_at > NOW()
              AND u.is_active = TRUE
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()

    if user is None:
        return None

    return _row_to_user(user)


def revoke_session(token: str | None) -> bool:
    """
    Отзывает (удаляет) текущую сессию.

    У таблицы account_sessions нет флага revoked_at, поэтому строка удаляется.
    """
    if not token:
        return False

    token_hash = hash_token(token)

    with get_connection() as conn:
        result = conn.execute(
            """
            DELETE FROM account_sessions
            WHERE token_hash = %s
            RETURNING id
            """,
            (token_hash,),
        ).fetchone()

    return result is not None


def save_requisites(account_id: int, data) -> dict:
    """Сохраняет реквизиты аккаунта и возвращает сохранённый объект.

    Принимает dict либо pydantic-модель с 7 полями. Значения обрезаются
    по краям и ограничиваются по длине, лишние ключи отбрасываются.
    Пустые значения сохраняются как пустые строки.
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump()

    requisites = normalize_requisites(data)

    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE user_accounts
            SET requisites = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING requisites
            """,
            (Json(requisites), account_id),
        ).fetchone()

    saved = row[0] if row is not None else None

    return normalize_requisites(saved)


def recover_password(login: str, secret_phrase: str, new_password: str) -> bool:
    """
    Восстановление пароля по секретной фразе.

    При неверной паре логин/секретная фраза бросает ValueError.
    """
    login = normalize_login(login)
    secret_phrase = (secret_phrase or "").strip()
    new_password = new_password or ""

    if not login or not secret_phrase:
        raise ValueError("Укажите логин и секретную фразу")

    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Пароль должен быть не короче 4 символов")

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, secret_phrase_hash
            FROM user_accounts
            WHERE lower(login) = lower(%s)
              AND is_active = TRUE
            LIMIT 1
            """,
            (login,),
        ).fetchone()

        if user is None:
            raise ValueError("Неверный логин или секретная фраза")

        account_id, stored_secret = user

        try:
            valid = PASSWORD_HASH.verify(secret_phrase, stored_secret)
        except Exception:
            valid = False

        if not valid:
            raise ValueError("Неверный логин или секретная фраза")

        new_hash = PASSWORD_HASH.hash(new_password)

        conn.execute(
            """
            UPDATE user_accounts
            SET password_hash = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (new_hash, account_id),
        )

        # Сбрасываем все активные сессии — после смены пароля нужно войти заново.
        conn.execute(
            "DELETE FROM account_sessions WHERE account_id = %s",
            (account_id,),
        )

    return True


def create_request(
    account_id: int | None,
    title: str,
    surface_id: int | None = None,
    payload: dict | None = None,
) -> dict:
    """
    Создаёт заявку клиента в client_requests и возвращает её.

    ``account_id = None`` — заявка без личного кабинета (форма с сайта):
    контакты клиента при этом лежат в ``payload``. title по умолчанию
    пустая строка; при ошибке данных бросает ValueError.
    """
    clean_title = (title or "").strip()

    if surface_id is not None:
        try:
            surface_id = int(surface_id)
        except (TypeError, ValueError):
            raise ValueError("Некорректный идентификатор поверхности")

    if payload is not None and not isinstance(payload, dict):
        raise ValueError("Поле payload должно быть объектом")

    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO client_requests
                (account_id, title, surface_id, payload)
            VALUES
                (%s, %s, %s, %s)
            RETURNING id, title, status, created_at, payload, surface_id
            """,
            (account_id, clean_title, surface_id, Json(payload or {})),
        ).fetchone()

    return {
        "id": row[0],
        "title": row[1],
        "status": row[2],
        "created_at": row[3].isoformat() if row[3] else None,
        "payload": row[4] or {},
        "surface_id": row[5],
    }


def list_requests(account_id: int) -> list[dict]:
    """Список заявок аккаунта (свежие сверху)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, status, created_at, payload
            FROM client_requests
            WHERE account_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (account_id,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "payload": row[4] or {},
        }
        for row in rows
    ]


def list_all_requests(limit: int = 200) -> list[dict]:
    """Все заявки для админки — включая анонимные (account_id IS NULL)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                r.id,
                r.title,
                r.status,
                r.created_at,
                r.payload,
                r.surface_id,
                r.account_id,
                u.login
            FROM client_requests r
            LEFT JOIN user_accounts u ON u.id = r.account_id
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "payload": row[4] or {},
            "surface_id": row[5],
            "account_id": row[6],
            "account_login": row[7],
        }
        for row in rows
    ]


def get_portfolio(account_id: int) -> dict:
    """
    Портфель аккаунта (корзина избранных поверхностей).

    Возвращает payload целиком либо {} — если строки ещё нет.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT payload
            FROM account_portfolios
            WHERE account_id = %s
            LIMIT 1
            """,
            (account_id,),
        ).fetchone()

    if row is None:
        return {}

    payload = row[0]

    return payload if isinstance(payload, dict) else {}


def save_portfolio(account_id: int, payload: dict) -> dict:
    """
    Сохраняет портфель аккаунта (UPSERT по account_id).

    При повторном сохранении обновляет payload и updated_at.
    Возвращает сохранённый payload.
    """
    if not isinstance(payload, dict):
        payload = {}

    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO account_portfolios (account_id, payload)
            VALUES (%s, %s)
            ON CONFLICT (account_id) DO UPDATE
            SET payload = EXCLUDED.payload,
                updated_at = NOW()
            RETURNING payload
            """,
            (account_id, Json(payload)),
        ).fetchone()

    saved = row[0] if row is not None else None

    return saved if isinstance(saved, dict) else {}


# ----------------------------------------------------------- чаты умного чата


def get_chats(account_id: int) -> dict:
    """Сохранённые чаты аккаунта: payload целиком или {}."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT payload
            FROM account_chats
            WHERE account_id = %s
            LIMIT 1
            """,
            (account_id,),
        ).fetchone()

    if row is None:
        return {}

    payload = row[0]

    return payload if isinstance(payload, dict) else {}


def save_chats(account_id: int, payload: dict) -> dict:
    """Сохраняет чаты аккаунта (UPSERT по account_id)."""
    if not isinstance(payload, dict):
        payload = {}

    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO account_chats (account_id, payload)
            VALUES (%s, %s)
            ON CONFLICT (account_id) DO UPDATE
            SET payload = EXCLUDED.payload,
                updated_at = NOW()
            RETURNING payload
            """,
            (account_id, Json(payload)),
        ).fetchone()

    saved = row[0] if row is not None else None

    return saved if isinstance(saved, dict) else {}


def _updated_at(table: str, account_id: int) -> str | None:
    """Дата последнего сохранения строки аккаунта (ISO) либо None."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT updated_at FROM {table} WHERE account_id = %s LIMIT 1",
            (account_id,),
        ).fetchone()

    if row is None or row[0] is None:
        return None

    return row[0].isoformat()


def get_portfolio_updated_at(account_id: int) -> str | None:
    return _updated_at("account_portfolios", account_id)


def get_chats_updated_at(account_id: int) -> str | None:
    return _updated_at("account_chats", account_id)


def clear_portfolio(account_id: int) -> None:
    """Очищает сохранённый портфель аккаунта (только список ЛК).

    Содержание конструкций хранится в основной базе и не удаляется.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM account_portfolios WHERE account_id = %s",
            (account_id,),
        )


def clear_chats(account_id: int) -> None:
    """Очищает сохранённые чаты аккаунта (только список ЛК).

    Текстовая история вопросов и ответов остаётся в журнале чата.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM account_chats WHERE account_id = %s",
            (account_id,),
        )
