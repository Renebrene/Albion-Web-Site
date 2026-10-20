BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- ALBION CMS
-- Текст и структурированный контент хранятся в PostgreSQL.
-- Файлы хранятся отдельно в filesystem (/storage).
-- ============================================================


-- ============================================================
-- SITE SETTINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS site_settings (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    value_type TEXT NOT NULL DEFAULT 'text',
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- PAGES
-- ============================================================

CREATE TABLE IF NOT EXISTS pages (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    seo_title TEXT,
    seo_description TEXT,
    is_published BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- PAGE BLOCKS
-- Универсальные текстовые блоки страниц.
-- ============================================================

CREATE TABLE IF NOT EXISTS page_blocks (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    block_key TEXT NOT NULL,
    block_type TEXT NOT NULL,
    eyebrow TEXT,
    title TEXT,
    subtitle TEXT,
    body TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT page_blocks_unique_key UNIQUE (page_id, block_key)
);


-- ============================================================
-- PAGE STATS
-- Например:
-- 1995 / год основания
-- 6 / городов присутствия
-- ============================================================

CREATE TABLE IF NOT EXISTS page_stats (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- ABOUT: NETWORK
-- ============================================================

CREATE TABLE IF NOT EXISTS about_network_items (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL,
    title TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- ABOUT: ACTIVITIES
-- ============================================================

CREATE TABLE IF NOT EXISTS about_activity_items (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT,
    icon TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- ABOUT: PRODUCTION
-- ============================================================

CREATE TABLE IF NOT EXISTS about_production_items (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- MEDIA CATEGORIES
-- Виртуальные категории. Физические файлы не перемещаются.
-- ============================================================

CREATE TABLE IF NOT EXISTS media_categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- MEDIA
-- Файлы физически находятся в /storage.
-- PostgreSQL хранит только метаданные и относительный путь.
-- ============================================================

CREATE TABLE IF NOT EXISTS media (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    original_name TEXT NOT NULL,
    category_id BIGINT[],
    storage_path TEXT NOT NULL UNIQUE,
    mime_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    width INTEGER,
    height INTEGER,
    alt TEXT,
    title TEXT,
    storage_backend TEXT NOT NULL DEFAULT 'local',
    external_url TEXT,
    external_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT media_uuid_unique UNIQUE (uuid),
    CONSTRAINT media_file_size_check CHECK (file_size >= 0),
    CONSTRAINT media_width_check CHECK (width IS NULL OR width > 0),
    CONSTRAINT media_height_check CHECK (height IS NULL OR height > 0),
    CONSTRAINT media_storage_backend_check
        CHECK (storage_backend IN ('local', 'albion'))
);


-- ============================================================
-- MEDIA VARIANTS
-- Варианты оптимизированных изображений:
-- large — основной файл,
-- card — карточка,
-- thumb — миниатюра.
-- ============================================================

CREATE TABLE IF NOT EXISTS media_variants (
    id BIGSERIAL PRIMARY KEY,
    media_id BIGINT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    variant TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    mime_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'local',
    external_url TEXT,
    external_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT media_variants_variant_check
        CHECK (variant IN ('large', 'card', 'thumb')),
    CONSTRAINT media_variants_storage_backend_check
        CHECK (storage_backend IN ('local', 'albion')),
    CONSTRAINT media_variants_file_size_check
        CHECK (file_size >= 0),
    CONSTRAINT media_variants_width_check
        CHECK (width > 0),
    CONSTRAINT media_variants_height_check
        CHECK (height > 0),
    CONSTRAINT media_variants_media_variant_unique
        UNIQUE (media_id, variant)
);

CREATE INDEX IF NOT EXISTS idx_media_variants_media
    ON media_variants(media_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON media_variants TO albion_app;

GRANT USAGE, SELECT, UPDATE
    ON SEQUENCE media_variants_id_seq TO albion_app;


-- ============================================================
-- PAGE BLOCK MEDIA
-- ============================================================

CREATE TABLE IF NOT EXISTS page_block_media (
    id BIGSERIAL PRIMARY KEY,
    block_id BIGINT NOT NULL REFERENCES page_blocks(id) ON DELETE CASCADE,
    media_id BIGINT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
    role TEXT NOT NULL DEFAULT 'image',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_cover BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT page_block_media_unique UNIQUE (block_id, media_id, role)
);


-- ============================================================
-- NEWS
-- ============================================================

CREATE TABLE IF NOT EXISTS news_categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS news (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    excerpt TEXT,
    content TEXT NOT NULL,
    category_id BIGINT REFERENCES news_categories(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    seo_title TEXT,
    seo_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT news_uuid_unique UNIQUE (uuid)
);


CREATE TABLE IF NOT EXISTS news_media (
    id BIGSERIAL PRIMARY KEY,
    news_id BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    media_id BIGINT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_cover BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT news_media_unique UNIQUE (news_id, media_id)
);


-- ============================================================
-- CONTACTS
-- ============================================================

CREATE TABLE IF NOT EXISTS contact_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    seo_title TEXT,
    seo_description TEXT,
    hero_eyebrow TEXT,
    hero_title TEXT,
    hero_text TEXT,
    phone TEXT,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT contact_settings_singleton CHECK (id = 1)
);


CREATE TABLE IF NOT EXISTS contact_emails (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    label TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS contact_socials (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS contact_offices (
    id BIGSERIAL PRIMARY KEY,
    external_key TEXT UNIQUE,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    schedule TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    media_id BIGINT REFERENCES media(id) ON DELETE SET NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT contact_offices_coordinates_check
        CHECK (
            (latitude IS NULL AND longitude IS NULL)
            OR (
                latitude BETWEEN -90 AND 90
                AND longitude BETWEEN -180 AND 180
            )
        )
);


CREATE TABLE IF NOT EXISTS contact_office_emails (
    id BIGSERIAL PRIMARY KEY,
    office_id BIGINT NOT NULL REFERENCES contact_offices(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS contact_departments (
    id BIGSERIAL PRIMARY KEY,
    external_key TEXT UNIQUE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS contact_employees (
    id BIGSERIAL PRIMARY KEY,
    external_key TEXT UNIQUE,
    department_id BIGINT NOT NULL REFERENCES contact_departments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position TEXT,
    phone TEXT,
    extension TEXT,
    email TEXT,
    media_id BIGINT REFERENCES media(id) ON DELETE SET NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- ADMIN USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS admin_users (
    id BIGSERIAL PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT admin_users_role_check
        CHECK (role IN ('admin', 'editor'))
);


-- ============================================================
-- ADMIN SESSIONS
-- Храним только хеш токена, не сам токен.
-- ============================================================

CREATE TABLE IF NOT EXISTS admin_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT
);


-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES admin_users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id BIGINT,
    details TEXT,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_pages_published
    ON pages (is_published);

CREATE INDEX IF NOT EXISTS idx_page_blocks_page
    ON page_blocks (page_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_page_stats_page
    ON page_stats (page_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_about_network_page
    ON about_network_items (page_id, item_type, sort_order);

CREATE INDEX IF NOT EXISTS idx_about_activity_page
    ON about_activity_items (page_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_about_production_page
    ON about_production_items (page_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_page_block_media_block
    ON page_block_media (block_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_news_published
    ON news (is_published, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_category
    ON news (category_id);

CREATE INDEX IF NOT EXISTS idx_news_media_news
    ON news_media (news_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_contact_offices_active
    ON contact_offices (is_active, sort_order);

CREATE INDEX IF NOT EXISTS idx_contact_departments_active
    ON contact_departments (is_active, sort_order);

CREATE INDEX IF NOT EXISTS idx_contact_employees_department
    ON contact_employees (department_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_user
    ON admin_sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires
    ON admin_sessions (expires_at);

CREATE INDEX IF NOT EXISTS idx_admin_audit_created
    ON admin_audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_entity
    ON admin_audit_log (entity_type, entity_id);

-- ============================================================
-- CONTACT CALLBACK
-- ============================================================

CREATE TABLE IF NOT EXISTS contact_callback (
    id INTEGER PRIMARY KEY DEFAULT 1,
    title TEXT NOT NULL,
    body TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT contact_callback_singleton CHECK (id = 1)
);


CREATE TABLE IF NOT EXISTS contact_callback_fields (
    id BIGSERIAL PRIMARY KEY,
    callback_id INTEGER NOT NULL REFERENCES contact_callback(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT contact_callback_fields_unique
        UNIQUE (callback_id, field_name)
);


CREATE TABLE IF NOT EXISTS contact_callback_recipients (
    id BIGSERIAL PRIMARY KEY,
    callback_id INTEGER NOT NULL REFERENCES contact_callback(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_contact_callback_fields
    ON contact_callback_fields (callback_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_contact_callback_recipients
    ON contact_callback_recipients (callback_id, sort_order);

COMMIT;
