"""CMS-сервис контактов: чтение и редактирование офисов,
разделов и сотрудников из админки.

Только операции с PostgreSQL — HTTP-слой (роутер, авторизация)
живёт в backend/api/admin_contacts.py.
"""
from __future__ import annotations

from typing import Any

from backend.services.contacts_service import _media_url
from backend.services.data_service import get_connection


def _clean(value: Any) -> str:
    return (value or "").strip() if value is not None else ""


def _clean_or_none(value: Any) -> str | None:
    value = _clean(value)
    return value or None


def _next_sort_order(
    conn,
    table: str,
    column: str = "sort_order",
) -> int:
    row = conn.execute(
        f"SELECT COALESCE(MAX({column}), 0) + 10 FROM {table}"
    ).fetchone()
    return int(row[0]) if row else 10


def _office_row(conn, row) -> dict:
    return {
        "id": row[0],
        "external_key": row[1],
        "name": row[2],
        "address": row[3] or "",
        "phone": row[4] or "",
        "email": row[5] or "",
        "emails": None,  # заполняется ниже списком
        "schedule": row[6] or "",
        "lat": row[7],
        "lng": row[8],
        "media_id": row[9],
        "media_url": _media_url(conn, row[9]),
        "sort_order": row[10],
        "is_active": row[11],
    }


def _employee_row(conn, row) -> dict:
    return {
        "id": row[0],
        "external_key": row[1],
        "name": row[2] or "",
        "position": row[3] or "",
        "subdivision": row[4] or "",
        "phone": row[5] or "",
        "personal_phone": row[6] or "",
        "extension": row[7] or "",
        "email": row[8] or "",
        "media_id": row[9],
        "media_url": _media_url(conn, row[9]),
        "sort_order": row[10],
        "is_active": row[11],
        "department_id": row[12],
    }


def get_admin_contacts() -> dict:
    with get_connection() as conn:
        settings = conn.execute(
            """
            SELECT seo_title, seo_description, phone, email
            FROM contact_settings
            WHERE id = 1
            """
        ).fetchone()

        additional_emails = (
            conn.execute(
                """
                SELECT email
                FROM contact_emails
                WHERE is_active = TRUE
                ORDER BY sort_order
                """
            ).fetchall()
        )

        offices = conn.execute(
            """
            SELECT id, external_key, name, address, phone, email,
                   schedule, latitude, longitude, media_id, sort_order, is_active
            FROM contact_offices
            ORDER BY sort_order, id
            """
        ).fetchall()

        office_emails = {}
        for office_id, email in conn.execute(
            "SELECT office_id, email FROM contact_office_emails ORDER BY office_id, sort_order"
        ).fetchall():
            office_emails.setdefault(office_id, []).append(email)

        departments = conn.execute(
            """
            SELECT id, external_key, name, sort_order, is_active
            FROM contact_departments
            ORDER BY sort_order, id
            """
        ).fetchall()

        employees = conn.execute(
            """
            SELECT id, external_key, name, position, subdivision,
                   phone, personal_phone, extension, email, media_id,
                   sort_order, is_active, department_id
            FROM contact_employees
            ORDER BY department_id, sort_order, id
            """
        ).fetchall()

        employees_by_department = {}
        for row in employees:
            department_id = row[12]
            employees_by_department.setdefault(
                department_id, []
            ).append(_employee_row(conn, row))

        offices_payload = []
        for row in offices:
            item = _office_row(conn, row)
            emails = [item["email"]] if item["email"] else []
            for extra in office_emails.get(row[0], []):
                if extra and extra not in emails:
                    emails.append(extra)
            item["emails"] = emails
            offices_payload.append(item)

        return {
            "settings": {
                "seo_title": settings[0],
                "seo_description": settings[1],
                "phone": settings[2] or "",
                "email": settings[3] or "",
                "additionalEmails": [row[0] for row in additional_emails],
            },
            "offices": offices_payload,
            "departments": [
                {
                    "id": row[0],
                    "external_key": row[1],
                    "name": row[2],
                    "sort_order": row[3],
                    "is_active": row[4],
                    "employees": employees_by_department.get(row[0], []),
                }
                for row in departments
            ],
        }


# ---------------------------------------------------------------- settings


def update_settings(
    *,
    seo_title: str | None = None,
    seo_description: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    additional_emails: list[str] | None = None,
) -> dict:
    with get_connection() as conn:
        with conn.transaction():
            fields = []
            values = []

            for column, value in (
                ("seo_title", seo_title),
                ("seo_description", seo_description),
                ("phone", phone),
                ("email", email),
            ):
                if value is not None:
                    fields.append(f"{column} = %s")
                    values.append(_clean_or_none(value))

            if fields:
                fields.append("updated_at = NOW()")
                conn.execute(
                    f"""
                    UPDATE contact_settings
                    SET {", ".join(fields)}
                    WHERE id = 1
                    """,
                    values,
                )

            if additional_emails is not None:
                conn.execute(
                    "DELETE FROM contact_emails WHERE is_active = TRUE"
                )
                for index, item in enumerate(
                    _clean(e) for e in additional_emails
                ):
                    if not item:
                        continue
                    conn.execute(
                        """
                        INSERT INTO contact_emails (email, sort_order)
                        VALUES (%s, %s)
                        """,
                        (item, (index + 1) * 10),
                    )

    return {"success": True}


# ---------------------------------------------------------------- office


def create_office(
    *,
    name: str,
    address: str,
    phone: str | None = None,
    emails: list[str] | None = None,
    schedule: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    media_id: int | None = None,
    sort_order: int | None = None,
    is_active: bool = True,
) -> dict:
    name = _clean(name)

    if not name:
        raise ValueError("Не указано название офиса")

    with get_connection() as conn:
        with conn.transaction():
            if sort_order is None:
                sort_order = _next_sort_order(conn, "contact_offices")

            row = conn.execute(
                """
                INSERT INTO contact_offices (
                    name, address, phone, schedule,
                    latitude, longitude, media_id, sort_order, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, external_key
                """,
                (
                    name,
                    address,
                    _clean_or_none(phone),
                    _clean_or_none(schedule),
                    lat,
                    lng,
                    media_id,
                    sort_order,
                    is_active,
                ),
            ).fetchone()

            office_id = row[0]
            _set_office_emails(conn, office_id, emails or [])

            return {"id": office_id}


def _set_office_emails(conn, office_id: int, emails: list[str]) -> None:
    emails = [_clean(e) for e in emails if _clean(e)]

    conn.execute(
        "DELETE FROM contact_office_emails WHERE office_id = %s",
        (office_id,),
    )

    primary = emails[0] if emails else None
    conn.execute(
        """
        UPDATE contact_offices
        SET email = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (primary, office_id),
    )

    for index, email in enumerate(emails[1:], start=1):
        conn.execute(
            """
            INSERT INTO contact_office_emails (office_id, email, sort_order)
            VALUES (%s, %s, %s)
            """,
            (office_id, email, index * 10),
        )


def update_office(
    office_id: int,
    **fields,
) -> dict:
    emails = fields.pop("emails", None)

    # name -> SQL-столбец и можно ли обнулить (снять картинку/координаты).
    # Обычные поля (name/address/sort_order и т.п.) в NULL не обнуляем,
    # если фронт не прислал значение.
    allowed = {
        "name": ("name", False),
        "address": ("address", False),
        "phone": ("phone", False),
        "schedule": ("schedule", False),
        "lat": ("latitude", True),
        "lng": ("longitude", True),
        "media_id": ("media_id", True),
        "sort_order": ("sort_order", False),
        "is_active": ("is_active", False),
    }

    with get_connection() as conn:
        with conn.transaction():
            updates = []
            values = []

            for key, value in fields.items():
                entry = allowed.get(key)
                if entry is None:
                    continue
                column, nullable = entry
                if value is None and not nullable:
                    continue
                updates.append(f"{column} = %s")
                values.append(value)

            if updates:
                updates.append("updated_at = NOW()")
                conn.execute(
                    f"""
                    UPDATE contact_offices
                    SET {', '.join(updates)}
                    WHERE id = %s
                    """,
                    (*values, office_id),
                )

            if emails is not None:
                _set_office_emails(conn, office_id, emails)

    return {"id": office_id}


def delete_office(office_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM contact_offices WHERE id = %s",
                (office_id,),
            )


# ---------------------------------------------------------------- department


def create_department(
    *,
    name: str,
    sort_order: int | None = None,
    is_active: bool = True,
) -> dict:
    name = _clean(name)

    if not name:
        raise ValueError("Не указано название раздела")

    with get_connection() as conn:
        with conn.transaction():
            if sort_order is None:
                sort_order = _next_sort_order(conn, "contact_departments")

            row = conn.execute(
                """
                INSERT INTO contact_departments (name, sort_order, is_active)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (name, sort_order, is_active),
            ).fetchone()

    return {"id": row[0]}


def update_department(
    department_id: int,
    *,
    name: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> dict:
    with get_connection() as conn:
        with conn.transaction():
            fields = []
            values = []

            if name is not None:
                fields.append("name = %s")
                values.append(_clean(name))
            if sort_order is not None:
                fields.append("sort_order = %s")
                values.append(sort_order)
            if is_active is not None:
                fields.append("is_active = %s")
                values.append(is_active)

            if fields:
                fields.append("updated_at = NOW()")
                conn.execute(
                    f"""
                    UPDATE contact_departments
                    SET {', '.join(fields)}
                    WHERE id = %s
                    """,
                    (*values, department_id),
                )

    return {"id": department_id}


def delete_department(department_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM contact_departments WHERE id = %s",
                (department_id,),
            )


# ---------------------------------------------------------------- employee


def _validate_department(conn, department_id: int) -> None:
    ok = conn.execute(
        "SELECT 1 FROM contact_departments WHERE id = %s",
        (department_id,),
    ).fetchone()

    if not ok:
        raise ValueError("Указанный раздел не найден")


def create_employee(
    *,
    department_id: int,
    name: str = "",
    position: str = "",
    subdivision: str | None = None,
    phone: str | None = None,
    personal_phone: str | None = None,
    extension: str | None = None,
    email: str | None = None,
    media_id: int | None = None,
    sort_order: int | None = None,
    is_active: bool = True,
) -> dict:
    with get_connection() as conn:
        with conn.transaction():
            _validate_department(conn, department_id)

            if sort_order is None:
                row = conn.execute(
                    """
                    SELECT COALESCE(MAX(sort_order), 0) + 10
                    FROM contact_employees
                    WHERE department_id = %s
                    """,
                    (department_id,),
                ).fetchone()
                sort_order = int(row[0])

            employee_row = conn.execute(
                """
                INSERT INTO contact_employees (
                    department_id, name, position, subdivision,
                    phone, personal_phone, extension, email,
                    media_id, sort_order, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    department_id,
                    _clean(name),
                    _clean(position),
                    _clean_or_none(subdivision),
                    _clean_or_none(phone),
                    _clean_or_none(personal_phone),
                    _clean_or_none(extension),
                    _clean_or_none(email),
                    media_id,
                    sort_order,
                    is_active,
                ),
            ).fetchone()

    return {"id": employee_row[0]}


def update_employee(
    employee_id: int,
    *,
    department_id: int | None = None,
    name: str | None = None,
    position: str | None = None,
    subdivision: str | None = None,
    phone: str | None = None,
    personal_phone: str | None = None,
    extension: str | None = None,
    email: str | None = None,
    media_id: int | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> dict:
    with get_connection() as conn:
        with conn.transaction():
            if department_id is not None:
                _validate_department(conn, department_id)

            fields = []
            values = []

            def add(column, value):
                fields.append(f"{column} = %s")
                values.append(value)

            if department_id is not None:
                add("department_id", department_id)
            if name is not None:
                add("name", _clean(name))
            if position is not None:
                add("position", _clean(position))
            if subdivision is not None:
                add("subdivision", _clean_or_none(subdivision))
            if phone is not None:
                add("phone", _clean_or_none(phone))
            if personal_phone is not None:
                add("personal_phone", _clean_or_none(personal_phone))
            if extension is not None:
                add("extension", _clean_or_none(extension))
            if email is not None:
                add("email", _clean_or_none(email))
            # media_id передаётся всегда (может быть NULL — снять фото)
            add("media_id", media_id)
            if sort_order is not None:
                add("sort_order", sort_order)
            if is_active is not None:
                add("is_active", is_active)

            if fields:
                fields.append("updated_at = NOW()")
                conn.execute(
                    f"""
                    UPDATE contact_employees
                    SET {', '.join(fields)}
                    WHERE id = %s
                    """,
                    (*values, employee_id),
                )

    return {"id": employee_id}


def delete_employee(employee_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM contact_employees WHERE id = %s",
                (employee_id,),
            )


# ---------------------------------------------------------------- reorder


def reorder(
    *,
    offices: list[dict] | None = None,
    departments: list[dict] | None = None,
) -> dict:
    """Атомарно обновляет порядок офисов, разделов и сотрудников
    внутри разделов. Сотрудника можно перенести в другой раздел,
    указав department_id в его записи.
    """
    with get_connection() as conn:
        with conn.transaction():
            for index, office in enumerate(offices or []):
                conn.execute(
                    "UPDATE contact_offices SET sort_order = %s WHERE id = %s",
                    (office.get("sort_order", (index + 1) * 10), office["id"]),
                )

            for index, department in enumerate(departments or []):
                conn.execute(
                    """
                    UPDATE contact_departments
                    SET sort_order = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (department.get("sort_order", (index + 1) * 10), department["id"]),
                )

                for employee_index, employee in enumerate(
                    department.get("employees", [])
                ):
                    fields = []
                    values = []
                    fields.append("sort_order = %s")
                    values.append(
                        employee.get("sort_order", (employee_index + 1) * 10)
                    )

                    target_department = employee.get(
                        "department_id", department["id"]
                    )

                    if target_department:
                        _validate_department(conn, target_department)
                        fields.append("department_id = %s")
                        values.append(target_department)

                    fields.append("updated_at = NOW()")
                    conn.execute(
                        f"""
                        UPDATE contact_employees
                        SET {', '.join(fields)}
                        WHERE id = %s
                        """,
                        (*values, employee["id"]),
                    )

    return {"success": True}