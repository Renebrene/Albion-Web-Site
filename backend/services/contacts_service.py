from urllib.parse import quote

from backend.services.data_service import get_connection


def _media_url(conn, media_id, variant: str = "card") -> str:
    """Возвращает публичный URL картинки из медиа-хранилища
    (предпочтительно вариант ``card``, иначе основной файл).

    Изображение всегда отдаётся с ведущим слэшем, чтобы не ломаться
    на вложенных роутах (/kontakty и т.п.).
    """
    if not media_id:
        return ""

    row = conn.execute(
        """
        SELECT
            (SELECT storage_path
               FROM media_variants mv
              WHERE mv.media_id = m.id AND mv.variant = %s
              LIMIT 1),
            m.storage_path
        FROM media m
        WHERE m.id = %s
        """,
        (variant, media_id),
    ).fetchone()

    if row is None:
        return ""

    path = row[0] or row[1]

    if not path:
        return ""

    # storage_path хранится относительно /storage (например
    # "media/xxx.png"). Публичный URL — со слэш-префиксом /storage/.
    path = path.lstrip("/")

    if path.startswith("storage/"):
        return "/" + path

    return "/storage/" + path


def _yandex_maps_url(address: str) -> str:
    """Строит ссылку «смотреть на карте» для Яндекс.Карт.

    Адрес может содержать переносы строк (текст карточки) — для
    поискового запроса схлопываем пробельные символы в запятую.
    """
    cleaned = " ".join(
        part.strip()
        for part in address.replace("\n", ",").split(",")
        if part.strip()
    )

    if not cleaned:
        return ""

    return "https://yandex.ru/maps/?text=" + quote(cleaned)


def get_contacts():
    with get_connection() as conn:
        settings = conn.execute(
            """
            SELECT seo_title, seo_description, phone, email
            FROM contact_settings
            WHERE id = 1
            """
        ).fetchone()

        if settings is None:
            raise RuntimeError("Настройки контактов не найдены")

        additional_emails = conn.execute(
            """
            SELECT email
            FROM contact_emails
            WHERE is_active = TRUE
            ORDER BY sort_order
            """
        ).fetchall()

        offices_rows = conn.execute(
            """
            SELECT
                id,
                external_key,
                name,
                address,
                phone,
                email,
                schedule,
                latitude,
                longitude,
                media_id,
                sort_order,
                is_active
            FROM contact_offices
            WHERE is_active = TRUE
            ORDER BY sort_order
            """
        ).fetchall()

        office_emails_rows = conn.execute(
            """
            SELECT office_id, email
            FROM contact_office_emails
            WHERE office_id IN (
                SELECT id FROM contact_offices WHERE is_active = TRUE
            )
            ORDER BY office_id, sort_order
            """
        ).fetchall()

        office_emails: dict[int, list[str]] = {}
        for office_id, email in office_emails_rows:
            office_emails.setdefault(office_id, []).append(email)

        offices = []
        for row in offices_rows:
            (
                office_id,
                external_key,
                name,
                address,
                phone,
                email,
                schedule,
                latitude,
                longitude,
                media_id,
                sort_order,
                is_active,
            ) = row

            emails = [email] if email else []

            for extra in office_emails.get(office_id, []):
                if extra and extra not in emails:
                    emails.append(extra)

            offices.append(
                {
                    "id": external_key,
                    "name": name,
                    "address": address,
                    "mapUrl": _yandex_maps_url(address or ""),
                    "phone": phone,
                    "emails": emails,
                    "schedule": schedule,
                    "lat": latitude,
                    "lng": longitude,
                    "image": _media_url(conn, media_id),
                    "sortOrder": sort_order,
                    "active": is_active,
                }
            )

        departments_rows = conn.execute(
            """
            SELECT
                id,
                external_key,
                name,
                sort_order,
                is_active
            FROM contact_departments
            WHERE is_active = TRUE
            ORDER BY sort_order
            """
        ).fetchall()

        employees_rows = conn.execute(
            """
            SELECT
                department_id,
                external_key,
                name,
                position,
                subdivision,
                phone,
                extension,
                personal_phone,
                email,
                media_id,
                sort_order,
                is_active
            FROM contact_employees
            WHERE is_active = TRUE
            ORDER BY department_id, sort_order
            """
        ).fetchall()

        employees_by_department: dict[int, list] = {}
        for row in employees_rows:
            (
                department_id,
                external_key,
                name,
                position,
                subdivision,
                phone,
                extension,
                personal_phone,
                email,
                media_id,
                sort_order,
                is_active,
            ) = row

            employees_by_department.setdefault(
                department_id,
                [],
            ).append(
                {
                    "id": external_key,
                    "name": name or "",
                    "position": position or "",
                    "subdivision": subdivision or "",
                    "workPhone": phone or "",
                    "personalPhone": personal_phone or "",
                    "extension": extension or "",
                    "email": email or "",
                    "photo": _media_url(conn, media_id),
                    "sortOrder": sort_order,
                    "active": is_active,
                }
            )

        departments = []
        for row in departments_rows:
            (
                department_id,
                external_key,
                name,
                sort_order,
                is_active,
            ) = row

            departments.append(
                {
                    "id": external_key,
                    "name": name,
                    "sortOrder": sort_order,
                    "active": is_active,
                    "employees": employees_by_department.get(
                        department_id,
                        [],
                    ),
                }
            )

        return {
            "seo": {
                "title": settings[0],
                "description": settings[1],
            },
            "general": {
                "phone": settings[2],
                "email": settings[3],
                "additionalEmails": [
                    row[0] for row in additional_emails
                ],
                "socials": [],
            },
            "offices": offices,
            "departments": departments,
        }