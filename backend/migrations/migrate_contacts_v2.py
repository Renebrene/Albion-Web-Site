"""Миграция структуры «Контакты» v2.

Что делает (идемпотентно, можно перезапускать):

1. Добавляет в contact_employees недостающие колонки:
     subdivision      TEXT          — подразделение (внутри отдела)
     personal_phone   TEXT          — личный телефон
2. Приводит разделы (contact_departments) и сотрудников
   (contact_employees) к канонической структуре v2.
   Структура задана ниже в DEPARTMENTS — это «сброс к эталону»:
   разделы и сотрудники пересоздаются заново. Изменения, сделанные
   позже через админку, этой миграцией не затрагиваются.
3. Обновляет тексты двух карточек офисов (адрес, режим работы,
   список эл. почт) под новый макет карточки.

Запуск:  .venv/bin/python -m backend.migrations.migrate_contacts_v2
"""
from __future__ import annotations

from backend.services.data_service import get_connection, load_env_file
from backend.services.data_service import PROJECT_DIR


load_env_file(PROJECT_DIR / ".env")


# ------------------------------------------------------------------ колонки


def ensure_columns(conn) -> None:
    for column, definition in {
        "subdivision": "TEXT",
        "personal_phone": "TEXT",
    }.items():
        exists = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'contact_employees'
              AND column_name = %s
            """,
            (column,),
        ).fetchone()

        if not exists:
            conn.execute(
                f"ALTER TABLE contact_employees ADD COLUMN {column} {definition}"
            )
            print(f"  + колонка contact_employees.{column}")


# ------------------------------------------------------------------ данные


OFFICE_CARDS = [
    {
        "key": "central-office",
        "name": "Центральный офис",
        "address": "344002, Ростов-на-Дону, \nул. Социалистическая, 73 (2-й этаж)",
        "phone": "+7 (863) 320-30-20",
        "emails": ["reclama@albion.su", "albion3@albion.su"],
        "schedule": "Пн|Вт|Ср|Чт|Пт| с 09:00 до 18:00",
    },
    {
        "key": "production-base",
        "name": "Производственная база",
        "address": "344064, г. Ростов-на-Дону, \nпер. Радиаторный, 7E",
        "phone": "+7 (863) 223-18-56",
        "emails": ["baza@albion.su"],
        "schedule": "Пн|Вт|Ср|Чт|Пт| с 09:00 до 18:00",
    },
]


# Разделы по умолчанию. Каждый сотрудник:
#   key        external_key (стабильный id)
#   name       ФИО (может быть пустым — «без имени»)
#   position   должность (обязательная строка)
#   subdivision подразделение (внутри отдела), опционально
#   work_phone рабочий телефон, личный_телефон personal_phone, email
DEPARTMENTS = [
    {
        "key": "general-director",
        "name": "Генеральный директор ГК «Альбион»",
        "sort_order": 10,
        "employees": [
            {
                "key": "vyacheslav-sukhomlinov",
                "name": "Сухомлинов Вячеслав Николаевич",
                "position": "Генеральный директор",
            },
        ],
    },
    {
        "key": "administration",
        "name": "Администрация",
        "sort_order": 20,
        "employees": [
            {
                "key": "natalia-teplinskaya",
                "name": "Теплинская Наталья",
                "position": "Коммерческий директор",
                "email": "tepl@albion.su",
            },
            {
                "key": "mikhail-schastnev",
                "name": "Счастнев Михаил Борисович",
                "position": "Технический директор",
            },
            {
                "key": "galina-sedush",
                "name": "Седуш Галина Николаевна",
                "position": "Главный бухгалтер",
            },
            {
                "key": "dmitry-krivoshlykov",
                "name": "Дмитрий Кривошлыков",
                "position": "Начальник ПХБ",
                "work_phone": "+7 (863) 223-18-56",
                "email": "baza@albion.su",
            },
            {
                "key": "ad-roukovoditel",
                "name": "",
                "position": "Руководитель рекламного агентства",
            },
            {
                "key": "urist",
                "name": "",
                "position": "Юрист",
            },
        ],
    },
    {
        "key": "ad-team",
        "name": "Команда рекламного агентства",
        "sort_order": 30,
        "employees": [
            {
                "key": "elena-ivanova",
                "name": "Елена Иванова",
                "position": "Менеджер отдела размещения",
                "work_phone": "+7 (863) 320-30-20",
                "extension": "166",
                "email": "albion2@albion.su",
            },
            {
                "key": "elena-marysheva",
                "name": "Елена Марышева",
                "position": "Менеджер отдела размещения рекламы",
                "work_phone": "+7 (863) 320-30-20",
                "extension": "127",
                "email": "board@albion.su",
            },
            {
                "key": "angelina-krivoshlykova",
                "name": "Ангелина Кривошлыкова",
                "position": "Менеджер отдела размещения рекламы",
                "work_phone": "+7 (863) 320-30-20",
                "extension": "177",
                "email": "albion1982@albion.su",
            },
            {
                "key": "tatiana-putilina",
                "name": "Татьяна Путилина",
                "position": "Менеджер отдела размещения рекламы",
                "work_phone": "+7 (863) 320-30-20",
                "extension": "118",
                "email": "unr@albion.su",
            },
            {
                "key": "ilya-annin",
                "name": "Аннин Илья Анатольевич",
                "position": "Менеджер отдела размещения рекламы",
                "work_phone": "+7 (863) 320-30-20",
                "email": "reclama@albion.su",
            },
            {
                "key": "olga-butovchenko",
                "name": "Ольга Бутовченко",
                "position": "Менеджер типографии",
                "work_phone": "+7 (863) 320-30-20",
                "extension": "167",
                "email": "klient@albion.su",
            },
            {
                "key": "elena-golovko",
                "name": "Головко Елена Васильевна",
                "position": "Офис-менеджер",
                "work_phone": "+7 (863) 320-30-20",
                "extension": "102",
            },
            {
                "key": "doc-specialist",
                "name": "",
                "position": "Специалист по документообороту",
            },
        ],
    },
    {
        "key": "technical",
        "name": "Технический отдел",
        "sort_order": 40,
        "employees": [
            {
                "key": "tech-head",
                "name": "",
                "position": "Начальник технического отдела",
            },
            {
                "key": "tech-specialist",
                "name": "",
                "position": "Специалист технического отдела",
            },
            {
                "key": "tech-engineer",
                "name": "",
                "position": "Инженер технического отдела",
            },
        ],
    },
    {
        "key": "design",
        "name": "Отдел дизайна и высоких технологий",
        "sort_order": 50,
        "employees": [
            {
                "key": "designer-a",
                "name": "",
                "position": "Дизайнер",
                "subdivision": "Дизайнер А",
            },
            {
                "key": "designer-b",
                "name": "",
                "position": "Дизайнер",
                "subdivision": "Дизайнер Б",
            },
            {
                "key": "sysadmin",
                "name": "",
                "position": "Системный администратор",
            },
            {
                "key": "digital-operator",
                "name": "",
                "position": "Оператор диджитал",
            },
        ],
    },
    {
        "key": "accounting",
        "name": "Бухгалтерия и ОК",
        "sort_order": 60,
        "employees": [
            {
                "key": "acc-skyline",
                "name": "",
                "position": "Бухгалтер ООО Скайлайн",
            },
            {
                "key": "acc-albion-media",
                "name": "",
                "position": "Бухгалтер ООО «Альбион медиа»",
            },
        ],
    },
]


def _employee_values(department_id, data) -> tuple:
    return (
        data.get("key"),
        department_id,
        data.get("name") or "",
        data.get("position") or "",
        data.get("subdivision"),
        data.get("work_phone"),
        data.get("extension"),
        data.get("personal_phone"),
        data.get("email"),
        data.get("media_id"),
        data.get("sort_order") or 10,
        True,
    )


def rebuild_departments(conn) -> None:
    conn.execute("DELETE FROM contact_departments")

    for index, department in enumerate(DEPARTMENTS):
        row = conn.execute(
            """
            INSERT INTO contact_departments (external_key, name, sort_order, is_active)
            VALUES (%s, %s, %s, TRUE)
            RETURNING id
            """,
            (
                department["key"],
                department["name"],
                department.get("sort_order") or (index + 1) * 10,
            ),
        ).fetchone()
        department_id = row[0]

        for sort_index, employee in enumerate(
            department["employees"]
        ):
            conn.execute(
                """
                INSERT INTO contact_employees (
                    external_key, department_id, name, position,
                    subdivision, phone, extension, personal_phone,
                    email, media_id, sort_order, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                _employee_values(
                    department_id,
                    {
                        **employee,
                        "sort_order": (sort_index + 1) * 10,
                    },
                ),
            )

    total = conn.execute(
        "SELECT COUNT(*) FROM contact_employees"
    ).fetchone()[0]
    print(f"  • пересоздано разделов: {len(DEPARTMENTS)}")
    print(f"  • пересоздано сотрудников: {total}")


def update_office_cards(conn) -> None:
    for card in OFFICE_CARDS:
        office = conn.execute(
            """
            SELECT id, email
            FROM contact_offices
            WHERE external_key = %s
            """,
            (card["key"],),
        ).fetchone()

        if office is None:
            print(f"  ! офиса не найдено: {card['key']}")
            continue

        office_id, primary_email = office
        emails = [e for e in card["emails"]]

        if not emails:
            new_primary = None
            additional = []
        else:
            new_primary = emails[0]
            additional = emails[1:]

        conn.execute(
            """
            UPDATE contact_offices
            SET name = %s, address = %s, phone = %s, email = %s,
                schedule = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (
                card["name"],
                card["address"],
                card["phone"],
                new_primary,
                card["schedule"],
                office_id,
            ),
        )

        conn.execute(
            "DELETE FROM contact_office_emails WHERE office_id = %s",
            (office_id,),
        )

        for sort_index, email in enumerate(additional):
            conn.execute(
                """
                INSERT INTO contact_office_emails (office_id, email, sort_order)
                VALUES (%s, %s, %s)
                """,
                (office_id, email, (sort_index + 1) * 10),
            )

        print(f"  • офис «{card['name']}»: email={new_primary}, "
              f"доп.={additional or '-'}")


def main() -> None:
    print("ALBION · Миграция контактов v2")
    print()

    with get_connection() as conn:
        with conn.transaction():
            ensure_columns(conn)
            rebuild_departments(conn)
            update_office_cards(conn)

    print()
    print("COMMIT: миграция контактов v2 завершена.")


if __name__ == "__main__":
    main()