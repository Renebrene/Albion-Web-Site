BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- CITIES
-- ============================================================

CREATE TABLE IF NOT EXISTS cities (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),

    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    slug TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT cities_uuid_unique UNIQUE (uuid),
    CONSTRAINT cities_normalized_name_unique UNIQUE (normalized_name)
);

-- ============================================================
-- CONSTRUCTIONS
-- Физическая конструкция / место размещения.
-- ============================================================

CREATE TABLE IF NOT EXISTS constructions (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),

    city_id BIGINT REFERENCES cities(id) ON DELETE RESTRICT,

    district TEXT,
    address TEXT NOT NULL,
    name TEXT,

    location geometry(Point, 4326),

    -- Оставляем lat/lng для совместимости и удобного API.
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    -- Адресные поисковые поля.
    address_words TEXT,
    address_roots TEXT,
    address_numbers TEXT,
    street_root TEXT,
    house_number TEXT,
    address_key TEXT,
    street_names TEXT,
    street_roots TEXT,
    house_numbers TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT constructions_uuid_unique UNIQUE (uuid),

    CONSTRAINT constructions_location_coordinates_check
        CHECK (
            location IS NULL
            OR (
                ST_X(location) BETWEEN -180 AND 180
                AND ST_Y(location) BETWEEN -90 AND 90
            )
        )
);

-- ============================================================
-- SURFACES
-- Отдельная рекламная поверхность / сторона конструкции.
-- ============================================================

CREATE TABLE IF NOT EXISTS surfaces (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),

    construction_id BIGINT NOT NULL
        REFERENCES constructions(id) ON DELETE CASCADE,

    side TEXT NOT NULL,
    name TEXT,

    -- Стабильный SHA-256 идентификатор импортированной поверхности.
    -- Может повторяться для ошибочно продублированных строк исходного Excel.
    surface_hash TEXT,

    external_number TEXT,
    temporary_identifier TEXT,

    type TEXT,
    size TEXT,
    price TEXT,

    photo TEXT,
    map TEXT,

    location geometry(Point, 4326),

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    light TEXT,
    material TEXT,

    -- Дополнительные поля из существующего AlbionAI.
    media_type TEXT,

    legacy_surface_id BIGINT,
    source_system TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT surfaces_uuid_unique UNIQUE (uuid)
);

-- ============================================================
-- SURFACE AVAILABILITY
-- Состояние поверхности по месяцам.
-- ============================================================

CREATE TABLE IF NOT EXISTS surface_availability (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),

    surface_id BIGINT NOT NULL
        REFERENCES surfaces(id) ON DELETE CASCADE,

    year INTEGER NOT NULL,
    month INTEGER NOT NULL,

    -- Исходное значение из XLS/XLSX.
    raw_value TEXT,

    -- Нормализованное значение для API/UI.
    status TEXT NOT NULL DEFAULT 'FREE',

    load_percent INTEGER,

    -- Цена, действующая для конкретного месяца.
    price TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT surface_availability_uuid_unique UNIQUE (uuid),

    CONSTRAINT surface_availability_month_check
        CHECK (month BETWEEN 1 AND 12),

    CONSTRAINT surface_availability_year_check
        CHECK (year BETWEEN 2000 AND 2100),

    CONSTRAINT surface_availability_load_check
        CHECK (
            load_percent IS NULL
            OR load_percent BETWEEN 0 AND 100
        ),

    CONSTRAINT surface_availability_unique
        UNIQUE (surface_id, year, month)
);

-- ============================================================
-- CONSTRUCTION MEDIA
-- Локальные варианты фото/карты рекламной поверхности.
-- Не входят в обычную CMS-медиатеку.
-- ============================================================

CREATE TABLE IF NOT EXISTS construction_imports (
    id BIGSERIAL PRIMARY KEY,
    import_key TEXT NOT NULL UNIQUE,

    status TEXT NOT NULL
        CHECK (status IN ('active', 'staging', 'obsolete', 'failed')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS construction_media (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),

    import_id BIGINT
        REFERENCES construction_imports(id) ON DELETE SET NULL,

    surface_id BIGINT
        REFERENCES surfaces(id) ON DELETE SET NULL,

    surface_hash TEXT,

    media_type TEXT NOT NULL
        CHECK (media_type IN ('photo', 'map')),

    -- Исходная внешняя ссылка Yandex.
    original_url TEXT,

    original_name TEXT,
    mime_type TEXT,
    file_size BIGINT,

    width INTEGER,
    height INTEGER,

    -- Локально сохраняются только обработанные варианты.
    large_path TEXT,
    card_path TEXT,
    thumb_path TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT construction_media_uuid_unique UNIQUE (uuid),

    CONSTRAINT construction_media_import_hash_type_unique
        UNIQUE (import_id, surface_hash, media_type)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_cities_normalized_name
    ON cities (normalized_name);

CREATE INDEX IF NOT EXISTS idx_cities_active
    ON cities (is_active);

CREATE INDEX IF NOT EXISTS idx_constructions_city
    ON constructions (city_id);

CREATE INDEX IF NOT EXISTS idx_constructions_address
    ON constructions (address);

CREATE INDEX IF NOT EXISTS idx_constructions_address_key
    ON constructions (address_key);

CREATE INDEX IF NOT EXISTS idx_constructions_active
    ON constructions (is_active);

CREATE INDEX IF NOT EXISTS idx_surfaces_location
    ON surfaces
    USING GIST (location);

CREATE INDEX IF NOT EXISTS idx_surfaces_surface_hash
    ON surfaces (surface_hash);

CREATE INDEX IF NOT EXISTS idx_surfaces_construction
    ON surfaces (construction_id);

CREATE INDEX IF NOT EXISTS idx_surfaces_external_number
    ON surfaces (external_number);

CREATE INDEX IF NOT EXISTS idx_surfaces_temporary_identifier
    ON surfaces (temporary_identifier);

CREATE INDEX IF NOT EXISTS idx_surfaces_side
    ON surfaces (side);

CREATE INDEX IF NOT EXISTS idx_surfaces_legacy_id
    ON surfaces (legacy_surface_id);

CREATE INDEX IF NOT EXISTS idx_surfaces_active
    ON surfaces (is_active);

CREATE INDEX IF NOT EXISTS idx_construction_media_surface
    ON construction_media (surface_id);

CREATE INDEX IF NOT EXISTS idx_construction_media_type
    ON construction_media (media_type);

CREATE INDEX IF NOT EXISTS idx_construction_media_surface_hash_type
    ON construction_media (surface_hash, media_type);

CREATE INDEX IF NOT EXISTS idx_availability_surface
    ON surface_availability (surface_id);

CREATE INDEX IF NOT EXISTS idx_availability_year_month
    ON surface_availability (year, month);

CREATE INDEX IF NOT EXISTS idx_availability_status
    ON surface_availability (status);

CREATE INDEX IF NOT EXISTS idx_availability_active
    ON surface_availability (is_active);

COMMIT;
