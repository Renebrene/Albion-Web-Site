from backend.services.data_service import get_connection


def get_contacts():
    with get_connection() as conn:
        settings = conn.execute(
            """
            SELECT
                seo_title,
                seo_description,
                hero_eyebrow,
                hero_title,
                hero_text,
                phone,
                email
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
            ORDER BY office_id, sort_order
            """
        ).fetchall()

        office_emails = {}
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
                sort_order,
                is_active,
            ) = row

            offices.append(
                {
                    "id": external_key,
                    "name": name,
                    "address": address,
                    "phone": phone,
                    "email": email,
                    "additionalEmails": office_emails.get(office_id, []),
                    "schedule": schedule,
                    "lat": latitude,
                    "lng": longitude,
                    "image": "",
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
                phone,
                extension,
                email,
                sort_order,
                is_active
            FROM contact_employees
            WHERE is_active = TRUE
            ORDER BY department_id, sort_order
            """
        ).fetchall()

        employees_by_department = {}
        for row in employees_rows:
            (
                department_id,
                external_key,
                name,
                position,
                phone,
                extension,
                email,
                sort_order,
                is_active,
            ) = row

            employees_by_department.setdefault(
                department_id,
                [],
            ).append(
                {
                    "id": external_key,
                    "name": name,
                    "position": position,
                    "phone": phone,
                    "extension": extension,
                    "email": email,
                    "photo": "",
                    "active": is_active,
                    "sortOrder": sort_order,
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
                    "active": is_active,
                    "sortOrder": sort_order,
                    "employees": employees_by_department.get(
                        department_id,
                        [],
                    ),
                }
            )

        callback = conn.execute(
            """
            SELECT title, body, is_enabled
            FROM contact_callback
            WHERE id = 1
            """
        ).fetchone()

        if callback is None:
            raise RuntimeError("Настройки callback не найдены")

        callback_id = 1

        callback_fields = conn.execute(
            """
            SELECT
                field_name,
                label,
                field_type,
                is_required
            FROM contact_callback_fields
            WHERE callback_id = %s
              AND is_active = TRUE
            ORDER BY sort_order
            """,
            (callback_id,),
        ).fetchall()

        callback_recipients = conn.execute(
            """
            SELECT email
            FROM contact_callback_recipients
            WHERE callback_id = %s
              AND is_active = TRUE
            ORDER BY sort_order
            """,
            (callback_id,),
        ).fetchall()

        return {
            "seo": {
                "title": settings[0],
                "description": settings[1],
            },
            "hero": {
                "eyebrow": settings[2],
                "title": settings[3],
                "text": settings[4],
            },
            "general": {
                "phone": settings[5],
                "email": settings[6],
                "additionalEmails": [
                    row[0]
                    for row in additional_emails
                ],
                "socials": [],
            },
            "offices": offices,
            "departments": departments,
            "callback": {
                "title": callback[0],
                "text": callback[1],
                "enabled": callback[2],
                "fields": [
                    {
                        "name": row[0],
                        "label": row[1],
                        "type": row[2],
                        "required": row[3],
                    }
                    for row in callback_fields
                ],
                "recipientEmails": [
                    row[0]
                    for row in callback_recipients
                ],
            },
        }
