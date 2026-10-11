"""Ремонт схемы таблиц конструкций: DEFAULT / PRIMARY KEY / UNIQUE / FK / CHECK / индексы.

Только операции с PostgreSQL (как в backend/db/schema.sql).

Зачем: `pg_restore -t <таблица>` восстанавливает таблицу и данные, но
отдельные записи дампа — колоночный DEFAULT и CONSTRAINT (PK/UNIQUE/FK) —
пропускает (у них другие имена в TOC). Поэтому после такого восстановления
(и после старого неполного восстановления) схему нужно «дотянуть».

Используется:
  * миграцией backend/migrations/migrate_repair_constructions_schema.py;
  * восстановлением из архива (import_archive_service.restore_archive).
"""
from __future__ import annotations

# Таблицы с автоинкрементным id (BIGSERIAL) — DEFAULT и PK.
IDENTITY_TABLES = (
    "cities",
    "constructions",
    "surfaces",
    "surface_availability",
    "construction_imports",
    "construction_media",
    "media_import_registry",
)

# (таблица, имя ограничения, определение) — UNIQUE/FK/CHECK как в schema.sql.
CONSTRAINTS = [
    ("cities", "cities_uuid_unique", "UNIQUE (uuid)"),
    ("cities", "cities_normalized_name_unique", "UNIQUE (normalized_name)"),
    ("constructions", "constructions_uuid_unique", "UNIQUE (uuid)"),
    (
        "constructions",
        "constructions_city_id_fkey",
        "FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE RESTRICT",
    ),
    (
        "constructions",
        "constructions_location_coordinates_check",
        "CHECK (location IS NULL OR ("
        "ST_X(location) BETWEEN -180 AND 180 AND "
        "ST_Y(location) BETWEEN -90 AND 90))",
    ),
    ("surfaces", "surfaces_uuid_unique", "UNIQUE (uuid)"),
    (
        "surfaces",
        "surfaces_construction_id_fkey",
        "FOREIGN KEY (construction_id) REFERENCES constructions(id) "
        "ON DELETE CASCADE",
    ),
    (
        "surface_availability",
        "surface_availability_uuid_unique",
        "UNIQUE (uuid)",
    ),
    (
        "surface_availability",
        "surface_availability_unique",
        "UNIQUE (surface_id, year, month)",
    ),
    (
        "surface_availability",
        "surface_availability_surface_id_fkey",
        "FOREIGN KEY (surface_id) REFERENCES surfaces(id) ON DELETE CASCADE",
    ),
    (
        "surface_availability",
        "surface_availability_month_check",
        "CHECK (month BETWEEN 1 AND 12)",
    ),
    (
        "surface_availability",
        "surface_availability_year_check",
        "CHECK (year BETWEEN 2000 AND 2100)",
    ),
    (
        "surface_availability",
        "surface_availability_load_check",
        "CHECK (load_percent IS NULL OR load_percent BETWEEN 0 AND 100)",
    ),
    (
        "construction_imports",
        "construction_imports_import_key_key",
        "UNIQUE (import_key)",
    ),
    (
        "construction_imports",
        "construction_imports_status_check",
        "CHECK (status IN ('active','staging','obsolete','failed'))",
    ),
    ("construction_media", "construction_media_uuid_unique", "UNIQUE (uuid)"),
    (
        "construction_media",
        "construction_media_import_hash_type_unique",
        "UNIQUE (import_id, surface_hash, media_type)",
    ),
    (
        "construction_media",
        "construction_media_import_id_fkey",
        "FOREIGN KEY (import_id) REFERENCES construction_imports(id) "
        "ON DELETE SET NULL",
    ),
    (
        "construction_media",
        "construction_media_surface_id_fkey",
        "FOREIGN KEY (surface_id) REFERENCES surfaces(id) ON DELETE SET NULL",
    ),
    (
        "construction_media",
        "construction_media_media_type_check",
        "CHECK (media_type IN ('photo','map'))",
    ),
    (
        "media_import_registry",
        "media_import_registry_media_type_check",
        "CHECK (media_type IN ('photo','map'))",
    ),
]

# Индексы из schema.sql (CREATE INDEX IF NOT EXISTS — безопасно повторять).
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cities_normalized_name ON cities (normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_cities_active ON cities (is_active)",
    "CREATE INDEX IF NOT EXISTS idx_constructions_city ON constructions (city_id)",
    "CREATE INDEX IF NOT EXISTS idx_constructions_address ON constructions (address)",
    "CREATE INDEX IF NOT EXISTS idx_constructions_address_key ON constructions (address_key)",
    "CREATE INDEX IF NOT EXISTS idx_constructions_active ON constructions (is_active)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_location ON surfaces USING GIST (location)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_surface_hash ON surfaces (surface_hash)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_construction ON surfaces (construction_id)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_external_number ON surfaces (external_number)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_temporary_identifier ON surfaces (temporary_identifier)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_side ON surfaces (side)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_legacy_id ON surfaces (legacy_surface_id)",
    "CREATE INDEX IF NOT EXISTS idx_surfaces_active ON surfaces (is_active)",
    "CREATE INDEX IF NOT EXISTS idx_construction_media_surface ON construction_media (surface_id)",
    "CREATE INDEX IF NOT EXISTS idx_construction_media_type ON construction_media (media_type)",
    "CREATE INDEX IF NOT EXISTS idx_construction_media_surface_hash_type ON construction_media (surface_hash, media_type)",
    "CREATE INDEX IF NOT EXISTS idx_availability_surface ON surface_availability (surface_id)",
    "CREATE INDEX IF NOT EXISTS idx_availability_year_month ON surface_availability (year, month)",
    "CREATE INDEX IF NOT EXISTS idx_availability_status ON surface_availability (status)",
    "CREATE INDEX IF NOT EXISTS idx_availability_active ON surface_availability (is_active)",
]


def _constraint_exists(cur, table: str, name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = %s::regclass
          AND conname = %s
        """,
        (f"public.{table}", name),
    )
    return cur.fetchone() is not None


def repair_schema(conn) -> dict:
    """Возвращает таблицы конструкций к виду schema.sql. Идемпотентно."""
    defaults = 0
    primary_keys = 0
    constraints = 0
    indexes = 0

    with conn.cursor() as cur:
        # 1. DEFAULT на id + привязка последовательности к колонке.
        for table in IDENTITY_TABLES:
            cur.execute(
                f'ALTER TABLE public."{table}" ALTER COLUMN id '
                f"SET DEFAULT nextval('{table}_id_seq')"
            )
            cur.execute(
                f'ALTER SEQUENCE public."{table}_id_seq" '
                f'OWNED BY public."{table}".id'
            )
            defaults += 1

        # 2. PRIMARY KEY.
        for table in IDENTITY_TABLES:
            name = f"{table}_pkey"

            if not _constraint_exists(cur, table, name):
                cur.execute(
                    f'ALTER TABLE public."{table}" '
                    f'ADD CONSTRAINT "{name}" PRIMARY KEY (id)'
                )
                primary_keys += 1

        # 3. UNIQUE / FK / CHECK.
        for table, name, definition in CONSTRAINTS:
            if not _constraint_exists(cur, table, name):
                cur.execute(
                    f'ALTER TABLE public."{table}" '
                    f'ADD CONSTRAINT "{name}" {definition}'
                )
                constraints += 1

        # 4. Индексы.
        for statement in INDEXES:
            cur.execute(statement)
            indexes += 1

    return {
        "defaults": defaults,
        "primary_keys": primary_keys,
        "constraints": constraints,
        "indexes": indexes,
    }
