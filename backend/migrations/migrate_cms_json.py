from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg


PROJECT_DIR = Path(__file__).resolve().parents[2]
ABOUT_FILE = PROJECT_DIR / "backend" / "data" / "about_company.json"
CONTACTS_FILE = PROJECT_DIR / "backend" / "data" / "contacts.json"


MONTHS = {
    "Январь": 1,
    "Февраль": 2,
    "Март": 3,
    "Апрель": 4,
    "Май": 5,
    "Июнь": 6,
    "Июль": 7,
    "Август": 8,
    "Сентябрь": 9,
    "Октябрь": 10,
    "Ноябрь": 11,
    "Декабрь": 12,
}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"Файл не найден: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise RuntimeError(f"Ожидался JSON-объект: {path}")

    return data


def require_keys(data: dict, keys: list[str], name: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise RuntimeError(
            f"{name}: отсутствуют обязательные поля: {', '.join(missing)}"
        )


ENV_FILE = PROJECT_DIR / ".env"


def load_env() -> None:
    if not ENV_FILE.exists():
        raise RuntimeError(f"Файл .env не найден: {ENV_FILE}")

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


def db_connection():
    required = [
        "ALBION_DB_HOST",
        "ALBION_DB_NAME",
        "ALBION_DB_USER",
        "ALBION_DB_PASSWORD",
    ]

    missing = [key for key in required if not os.environ.get(key)]

    if missing:
        raise RuntimeError(
            "В .env отсутствуют: " + ", ".join(missing)
        )

    return psycopg.connect(
        host=os.environ["ALBION_DB_HOST"],
        port=os.getenv("ALBION_DB_PORT", "5432"),
        dbname=os.environ["ALBION_DB_NAME"],
        user=os.environ["ALBION_DB_USER"],
        password=os.environ["ALBION_DB_PASSWORD"],
    )


def validate_about(data: dict) -> None:
    require_keys(
        data,
        [
            "eyebrow",
            "title",
            "intro",
            "stats",
            "network",
            "activities",
            "production",
            "images",
        ],
        "about_company.json",
    )

    if len(data["stats"]) != 4:
        raise RuntimeError("Ожидалось 4 статистических показателя.")

    if len(data["network"]["cities"]) != 6:
        raise RuntimeError("Ожидалось 6 городов в network.cities.")

    if len(data["network"]["highways"]) != 4:
        raise RuntimeError("Ожидалось 4 трассы в network.highways.")

    if len(data["activities"]["items"]) != 8:
        raise RuntimeError("Ожидалось 8 направлений деятельности.")

    if len(data["production"]["items"]) != 3:
        raise RuntimeError("Ожидалось 3 производственных пункта.")


def validate_contacts(data: dict) -> None:
    require_keys(
        data,
        ["seo", "hero", "general", "offices", "departments", "callback"],
        "contacts.json",
    )

    if len(data["offices"]) != 2:
        raise RuntimeError("Ожидалось 2 офиса.")

    if len(data["departments"]) != 2:
        raise RuntimeError("Ожидалось 2 отдела.")

    employee_count = sum(
        len(department.get("employees", []))
        for department in data["departments"]
    )

    if employee_count != 12:
        raise RuntimeError(
            f"Ожидалось 12 сотрудников, получено {employee_count}."
        )

    if len(data["callback"]["fields"]) != 4:
        raise RuntimeError("Ожидалось 4 поля callback-формы.")

    if len(data["callback"]["recipientEmails"]) != 1:
        raise RuntimeError(
            "Ожидался 1 получатель callback-формы."
        )


def migrate_about(conn, data: dict) -> dict:
    page_id = conn.execute(
        """
        INSERT INTO pages (
            slug,
            title,
            seo_title,
            seo_description,
            is_published
        )
        VALUES (
            'o-kompanii',
            %s,
            %s,
            %s,
            TRUE
        )
        RETURNING id
        """,
        (
            data["title"],
            data["title"],
            data["intro"],
        ),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO page_blocks (
            page_id,
            block_key,
            block_type,
            eyebrow,
            title,
            body,
            sort_order,
            is_active
        )
        VALUES (
            %s,
            'hero',
            'hero',
            %s,
            %s,
            %s,
            10,
            TRUE
        )
        """,
        (
            page_id,
            data["eyebrow"],
            data["title"],
            data["intro"],
        ),
    )

    for sort_order, item in enumerate(data["stats"], start=10):
        conn.execute(
            """
            INSERT INTO page_stats (
                page_id,
                value,
                label,
                sort_order,
                is_active
            )
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (
                page_id,
                item["value"],
                item["label"],
                sort_order,
            ),
        )

    conn.execute(
        """
        INSERT INTO page_blocks (
            page_id,
            block_key,
            block_type,
            eyebrow,
            title,
            body,
            sort_order,
            is_active
        )
        VALUES (
            %s,
            'network',
            'network',
            %s,
            %s,
            %s,
            20,
            TRUE
        )
        """,
        (page_id, "", data["network"]["title"], ""),
    )

    for sort_order, city in enumerate(data["network"]["cities"], start=10):
        conn.execute(
            """
            INSERT INTO about_network_items (
                page_id,
                item_type,
                title,
                sort_order,
                is_active
            )
            VALUES (%s, 'city', %s, %s, TRUE)
            """,
            (page_id, city, sort_order),
        )

    for sort_order, highway in enumerate(data["network"]["highways"], start=20):
        conn.execute(
            """
            INSERT INTO about_network_items (
                page_id,
                item_type,
                title,
                sort_order,
                is_active
            )
            VALUES (%s, 'highway', %s, %s, TRUE)
            """,
            (page_id, highway, sort_order),
        )

    conn.execute(
        """
        INSERT INTO page_blocks (
            page_id,
            block_key,
            block_type,
            eyebrow,
            title,
            body,
            sort_order,
            is_active
        )
        VALUES (
            %s,
            'activities',
            'activities',
            %s,
            %s,
            %s,
            30,
            TRUE
        )
        """,
        (page_id, "", data["activities"]["title"], ""),
    )

    for sort_order, title in enumerate(data["activities"]["items"], start=10):
        conn.execute(
            """
            INSERT INTO about_activity_items (
                page_id,
                title,
                sort_order,
                is_active
            )
            VALUES (%s, %s, %s, TRUE)
            """,
            (page_id, title, sort_order),
        )

    conn.execute(
        """
        INSERT INTO page_blocks (
            page_id,
            block_key,
            block_type,
            eyebrow,
            title,
            body,
            sort_order,
            is_active
        )
        VALUES (
            %s,
            'production',
            'production',
            %s,
            %s,
            %s,
            40,
            TRUE
        )
        """,
        (page_id, "", data["production"]["title"], ""),
    )

    for sort_order, item in enumerate(data["production"]["items"], start=10):
        conn.execute(
            """
            INSERT INTO about_production_items (
                page_id,
                title,
                body,
                sort_order,
                is_active
            )
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (
                page_id,
                item["title"],
                item["text"],
                sort_order,
            ),
        )

    return {
        "page_id": page_id,
        "stats": len(data["stats"]),
        "cities": len(data["network"]["cities"]),
        "highways": len(data["network"]["highways"]),
        "activities": len(data["activities"]["items"]),
        "production": len(data["production"]["items"]),
    }


def migrate_contacts(conn, data: dict) -> dict:
    conn.execute(
        """
        INSERT INTO pages (
            slug,
            title,
            seo_title,
            seo_description,
            is_published
        )
        VALUES (
            'kontakty',
            'Контакты',
            %s,
            %s,
            TRUE
        )
        """,
        (
            data["seo"]["title"],
            data["seo"]["description"],
        ),
    )

    conn.execute(
        """
        INSERT INTO contact_settings (
            id,
            seo_title,
            seo_description,
            hero_eyebrow,
            hero_title,
            hero_text,
            phone,
            email
        )
        VALUES (
            1,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            data["seo"]["title"],
            data["seo"]["description"],
            data["hero"]["eyebrow"],
            data["hero"]["title"],
            data["hero"]["text"],
            data["general"]["phone"],
            data["general"]["email"],
        ),
    )

    for sort_order, email in enumerate(
        data["general"].get("additionalEmails", []),
        start=10,
    ):
        conn.execute(
            """
            INSERT INTO contact_emails (
                email,
                sort_order,
                is_active
            )
            VALUES (%s, %s, TRUE)
            """,
            (email, sort_order),
        )

    for office in data["offices"]:
        office_id = conn.execute(
            """
            INSERT INTO contact_offices (
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
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                office["id"],
                office["name"],
                office["address"],
                office["phone"],
                office["email"],
                office["schedule"],
                office["lat"],
                office["lng"],
                office["sortOrder"],
                office["active"],
            ),
        ).fetchone()[0]

        for sort_order, email in enumerate(
            office.get("additionalEmails", []),
            start=10,
        ):
            conn.execute(
                """
                INSERT INTO contact_office_emails (
                    office_id,
                    email,
                    sort_order
                )
                VALUES (%s, %s, %s)
                """,
                (office_id, email, sort_order),
            )

    department_count = 0
    employee_count = 0

    for department in data["departments"]:
        department_id = conn.execute(
            """
            INSERT INTO contact_departments (
                external_key,
                name,
                sort_order,
                is_active
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                department["id"],
                department["name"],
                department["sortOrder"],
                department["active"],
            ),
        ).fetchone()[0]

        department_count += 1

        for employee in department["employees"]:
            conn.execute(
                """
                INSERT INTO contact_employees (
                    external_key,
                    department_id,
                    name,
                    position,
                    phone,
                    extension,
                    email,
                    sort_order,
                    is_active
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    employee["id"],
                    department_id,
                    employee["name"],
                    employee["position"],
                    employee["phone"],
                    employee["extension"],
                    employee["email"],
                    employee["sortOrder"],
                    employee["active"],
                ),
            )

            employee_count += 1

    callback = data["callback"]

    conn.execute(
        """
        INSERT INTO contact_callback (
            id,
            title,
            body,
            is_enabled
        )
        VALUES (1, %s, %s, %s)
        """,
        (
            callback["title"],
            callback["text"],
            callback["enabled"],
        ),
    )

    for field in callback["fields"]:
        conn.execute(
            """
            INSERT INTO contact_callback_fields (
                callback_id,
                field_name,
                label,
                field_type,
                is_required,
                sort_order,
                is_active
            )
            VALUES (1, %s, %s, %s, %s, %s, TRUE)
            """,
            (
                field["name"],
                field["label"],
                field["type"],
                field["required"],
                callback["fields"].index(field),
            ),
        )

    for sort_order, email in enumerate(
        callback["recipientEmails"],
        start=0,
    ):
        conn.execute(
            """
            INSERT INTO contact_callback_recipients (
                callback_id,
                email,
                sort_order,
                is_active
            )
            VALUES (1, %s, %s, TRUE)
            """,
            (email, sort_order),
        )

    return {
        "offices": len(data["offices"]),
        "departments": department_count,
        "employees": employee_count,
        "additional_emails": len(data["general"].get("additionalEmails", [])),
        "callback_fields": len(callback["fields"]),
        "callback_recipients": len(callback["recipientEmails"]),
    }


def verify(conn) -> None:
    expected = {
        "pages": 2,
        "page_blocks": 4,
        "page_stats": 4,
        "about_network_items": 10,
        "about_activity_items": 8,
        "about_production_items": 3,
        "contact_settings": 1,
        "contact_emails": 1,
        "contact_offices": 2,
        "contact_office_emails": 1,
        "contact_departments": 2,
        "contact_employees": 12,
        "contact_callback": 1,
        "contact_callback_fields": 4,
        "contact_callback_recipients": 1,
    }

    for table, expected_count in expected.items():
        actual = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        if actual != expected_count:
            raise RuntimeError(
                f"CONTROL CHECK FAILED: {table}: "
                f"actual={actual}, expected={expected_count}"
            )

        print(
            f"CHECK OK: {table}: "
            f"actual={actual}, expected={expected_count}"
        )


def main() -> None:
    print("ALBION CMS JSON → POSTGRESQL")
    print(f"About:    {ABOUT_FILE}")
    print(f"Contacts: {CONTACTS_FILE}")
    print()

    about = load_json(ABOUT_FILE)
    contacts = load_json(CONTACTS_FILE)

    validate_about(about)
    validate_contacts(contacts)

    print("JSON validation: OK")
    print()

    load_env()

    with db_connection() as conn:
        with conn.transaction():
            # CMS tables must be empty for the first migration.
            existing = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM pages),
                    (SELECT COUNT(*) FROM page_blocks),
                    (SELECT COUNT(*) FROM page_stats),
                    (SELECT COUNT(*) FROM about_network_items),
                    (SELECT COUNT(*) FROM about_activity_items),
                    (SELECT COUNT(*) FROM about_production_items),
                    (SELECT COUNT(*) FROM contact_settings),
                    (SELECT COUNT(*) FROM contact_offices),
                    (SELECT COUNT(*) FROM contact_departments),
                    (SELECT COUNT(*) FROM contact_employees),
                    (SELECT COUNT(*) FROM contact_callback)
                """
            ).fetchone()

            if any(value != 0 for value in existing):
                raise RuntimeError(
                    "CMS уже содержит данные. "
                    "Миграция остановлена, чтобы не создавать дубликаты."
                )

            about_result = migrate_about(conn, about)
            contacts_result = migrate_contacts(conn, contacts)

            print("About migrated:", about_result)
            print("Contacts migrated:", contacts_result)
            print()

            verify(conn)

        print()
        print("COMMIT: CMS migration completed successfully.")


if __name__ == "__main__":
    main()
