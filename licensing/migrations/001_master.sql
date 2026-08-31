-- ============================================================
-- Master Database Migration 001: Licensing Schema
-- Run: psql -d master_db -f 001_master.sql
-- All tables prefixed with 'lic_' to avoid conflicts
-- ============================================================

BEGIN;

-- ── Plans ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lic_plans (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(30) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    name_ar         VARCHAR(100) NOT NULL,
    max_users       INTEGER NOT NULL DEFAULT 5,
    max_projects    INTEGER NOT NULL DEFAULT 10,
    max_storage_mb  INTEGER NOT NULL DEFAULT 1024,
    modules         JSONB NOT NULL DEFAULT '{}',
    price_monthly   NUMERIC(12,2),
    price_yearly    NUMERIC(12,2),
    is_active       BOOLEAN DEFAULT true,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Companies ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lic_companies (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    name_ar         VARCHAR(200),
    tax_number      VARCHAR(50),
    email           VARCHAR(150),
    phone           VARCHAR(30),
    address         TEXT,
    db_name         VARCHAR(100) UNIQUE NOT NULL,
    db_host         VARCHAR(200) DEFAULT 'localhost',
    db_port         INTEGER DEFAULT 5432,
    status          VARCHAR(20) DEFAULT 'active',
    is_trial        BOOLEAN DEFAULT false,
    trial_ends_at   DATE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ── Subscriptions ──────────────────────────────────────────
-- trial | active | grace | expired | cancelled
CREATE TABLE IF NOT EXISTS lic_subscriptions (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    plan_id         INTEGER NOT NULL REFERENCES lic_plans(id),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    status          VARCHAR(20) DEFAULT 'active',
    auto_renew      BOOLEAN DEFAULT false,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lic_sub_company ON lic_subscriptions(company_id);
CREATE INDEX IF NOT EXISTS idx_lic_sub_status ON lic_subscriptions(status);

-- ── Licenses ───────────────────────────────────────────────
-- active | suspended | revoked
CREATE TABLE IF NOT EXISTS lic_licenses (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES lic_subscriptions(id),
    license_key     VARCHAR(50) UNIQUE NOT NULL,
    status          VARCHAR(20) DEFAULT 'active',
    issued_at       DATE NOT NULL,
    expires_at      DATE NOT NULL,
    last_validated  TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lic_license_company ON lic_licenses(company_id);
CREATE INDEX IF NOT EXISTS idx_lic_license_key ON lic_licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_lic_license_status ON lic_licenses(status);

-- ── Payments ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lic_payments (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES lic_subscriptions(id),
    amount          NUMERIC(12,2) NOT NULL,
    currency        VARCHAR(3) DEFAULT 'EGP',
    payment_method  VARCHAR(30),
    reference_no    VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'pending',
    paid_at         TIMESTAMP,
    confirmed_by    VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lic_pay_company ON lic_payments(company_id);

-- ── Master Users (Admin Panel) ─────────────────────────────
CREATE TABLE IF NOT EXISTS lic_master_users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(150) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(150),
    role            VARCHAR(30) DEFAULT 'support',
    is_active       BOOLEAN DEFAULT true,
    last_login      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Database Registry ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS lic_database_registry (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    db_name         VARCHAR(100) NOT NULL,
    db_host         VARCHAR(200) NOT NULL,
    db_port         INTEGER DEFAULT 5432,
    db_user         VARCHAR(100),
    db_password_enc VARCHAR(255),
    schema_version  VARCHAR(20),
    last_migration  TIMESTAMP,
    size_mb         NUMERIC(10,2),
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lic_dbreg_company ON lic_database_registry(company_id);

-- ── Seed Plans ─────────────────────────────────────────────
INSERT INTO lic_plans (code, name, name_ar, max_users, max_projects, max_storage_mb, modules, sort_order)
VALUES
('basic', 'Basic', 'الأساسية', 5, 10, 1024,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":false,"payroll":false,"equipment":false,"advanced_reports":false,"multi_branch":false,"api_access":false,"priority_support":false}',
 1),
('professional', 'Professional', 'الاحترافية', 20, -1, 5120,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":true,"payroll":true,"equipment":true,"advanced_reports":true,"multi_branch":true,"api_access":false,"priority_support":false}',
 2),
('enterprise', 'Enterprise', 'المؤسسات', 100, -1, 20480,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":true,"payroll":true,"equipment":true,"advanced_reports":true,"multi_branch":true,"api_access":true,"priority_support":true}',
 3)
ON CONFLICT (code) DO NOTHING;

-- ── Seed Admin User (password: admin123) ───────────────────
INSERT INTO lic_master_users (email, password_hash, full_name, role)
VALUES ('admin@dynamicpro.com', '$2b$12$LJ3m4ys4Gz8k5Q9v5Q9v5OeQHYLQhHlQhHlQhHlQhHlQhHlQhHlQ', 'System Admin', 'super_admin')
ON CONFLICT (email) DO NOTHING;

COMMIT;
