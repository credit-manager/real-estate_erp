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
    description     VARCHAR(500),
    description_ar  VARCHAR(500),
    max_users       INTEGER NOT NULL DEFAULT 5,
    max_projects    INTEGER NOT NULL DEFAULT 10,
    max_storage_mb  INTEGER NOT NULL DEFAULT 1024,
    modules         JSONB NOT NULL DEFAULT '{}',
    price_monthly   NUMERIC(12,2),
    price_yearly    NUMERIC(12,2),
    badge           VARCHAR(50),
    badge_color     VARCHAR(20),
    badge_bg        VARCHAR(20),
    icon            VARCHAR(10),
    gradient        VARCHAR(200),
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
    port            INTEGER DEFAULT 2222,
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
    id                      SERIAL PRIMARY KEY,
    email                   VARCHAR(150) UNIQUE NOT NULL,
    password_hash           VARCHAR(255) NOT NULL,
    full_name               VARCHAR(150),
    must_change_password    BOOLEAN DEFAULT false,
    role                    VARCHAR(30) DEFAULT 'support',
    is_active               BOOLEAN DEFAULT true,
    last_login              TIMESTAMP,
    created_at              TIMESTAMP DEFAULT NOW()
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

-- ── Company Users (bridge table) ───────────────────────────
CREATE TABLE IF NOT EXISTS lic_company_users (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    email           VARCHAR(150) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(150),
    role            VARCHAR(30) DEFAULT 'admin',
    is_active       BOOLEAN DEFAULT true,
    last_login      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_lic_company_users_company_email UNIQUE (company_id, email)
);

-- ── Activity Log (audit trail) ─────────────────────────────
CREATE TABLE IF NOT EXISTS lic_activity_log (
    id              SERIAL PRIMARY KEY,
    actor_id        INTEGER,
    actor_email     VARCHAR(150),
    action          VARCHAR(100) NOT NULL,
    target_type     VARCHAR(50),
    target_id       INTEGER,
    details         JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Remote Clients (desktop client tracking) ───────────────
CREATE TABLE IF NOT EXISTS remote_clients (
    id                  SERIAL PRIMARY KEY,
    company_id          INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    client_name         VARCHAR(200) NOT NULL,
    client_id           VARCHAR(100) UNIQUE NOT NULL,
    client_type         VARCHAR(20) DEFAULT 'desktop',
    os_info             VARCHAR(200),
    app_version         VARCHAR(20),
    public_ip           VARCHAR(50),
    local_ip            VARCHAR(50),
    mac_address         VARCHAR(30),
    status              VARCHAR(20) DEFAULT 'active',
    last_heartbeat      TIMESTAMP,
    last_sync           TIMESTAMP,
    sync_token          VARCHAR(100),
    pending_commands    JSONB DEFAULT '[]',
    remote_config       JSONB DEFAULT '{}',
    is_authorized       BOOLEAN DEFAULT true,
    client_secret       VARCHAR(100) UNIQUE,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_remote_clients_company ON remote_clients(company_id);
CREATE INDEX IF NOT EXISTS idx_remote_clients_client_id ON remote_clients(client_id);

-- ── Remote Commands (queued commands) ──────────────────────
CREATE TABLE IF NOT EXISTS remote_commands (
    id              SERIAL PRIMARY KEY,
    client_id       INTEGER NOT NULL REFERENCES remote_clients(id) ON DELETE CASCADE,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    command         VARCHAR(50) NOT NULL,
    payload         JSONB DEFAULT '{}',
    status          VARCHAR(20) DEFAULT 'pending',
    result          JSONB,
    issued_by       VARCHAR(150),
    issued_at       TIMESTAMP DEFAULT NOW(),
    executed_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_remote_commands_client ON remote_commands(client_id);
CREATE INDEX IF NOT EXISTS idx_remote_commands_status ON remote_commands(status);

-- ── Remote Sync Log (sync history) ─────────────────────────
CREATE TABLE IF NOT EXISTS remote_sync_log (
    id              SERIAL PRIMARY KEY,
    client_id       INTEGER NOT NULL REFERENCES remote_clients(id) ON DELETE CASCADE,
    company_id      INTEGER NOT NULL REFERENCES lic_companies(id) ON DELETE CASCADE,
    sync_type       VARCHAR(30) NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    records_count   INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'success',
    error_message   TEXT,
    started_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_remote_sync_log_client ON remote_sync_log(client_id);

-- ── Master Sessions (session tracking) ─────────────────────
CREATE TABLE IF NOT EXISTS master_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES lic_master_users(id) ON DELETE CASCADE,
    session_token   VARCHAR(255) UNIQUE NOT NULL,
    ip_address      VARCHAR(50),
    user_agent      TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_master_sessions_user ON master_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_master_sessions_token ON master_sessions(session_token);

-- ── Seed Plans ─────────────────────────────────────────────
INSERT INTO lic_plans (code, name, name_ar, description, description_ar, max_users, max_projects, max_storage_mb, modules, price_monthly, price_yearly, badge, badge_color, badge_bg, icon, gradient, sort_order)
VALUES
('starter', 'Starter', 'المبتدئ',
 'Perfect for small startups and freelancers', 'مثالية للمشاريع الناشئة والأفراد',
 3, 5, 512,
 '{"accounting":true,"projects":false,"procurement":false,"inventory":false,"hr":false,"payroll":false,"equipment":false,"advanced_reports":false,"multi_branch":false,"api_access":false,"priority_support":false}',
 99, 990,
 ' ', '#6366f1', '#eef2ff', ' ', 'linear-gradient(135deg, #6366f1, #8b5cf6)',
 1),
('basic', 'Basic', 'الأساسية',
 'For growing businesses with basic needs', 'للشركات النامية ذات الاحتياجات الأساسية',
 10, 25, 2048,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":false,"payroll":false,"equipment":false,"advanced_reports":false,"multi_branch":false,"api_access":false,"priority_support":false}',
 299, 2990,
 ' ', '#2563eb', '#eff6ff', ' ', 'linear-gradient(135deg, #2563eb, #3b82f6)',
 2),
('professional', 'Professional', 'الاحترافية',
 'Advanced features for established companies', 'ميزات متقدمة للشركات الراسخة',
 50, -1, 10240,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":true,"payroll":true,"equipment":true,"advanced_reports":true,"multi_branch":true,"api_access":false,"priority_support":false}',
 799, 7990,
 ' ', '#059669', '#ecfdf5', ' ', 'linear-gradient(135deg, #059669, #10b981)',
 3),
('enterprise', 'Enterprise', 'المؤسسات',
 'Complete solution for large organizations', 'حل متكامل للمؤسسات الكبيرة',
 200, -1, 51200,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":true,"payroll":true,"equipment":true,"advanced_reports":true,"multi_branch":true,"api_access":true,"priority_support":true}',
 1999, 19990,
 '⭐ Most Popular', '#d97706', '#fffbeb', ' ', 'linear-gradient(135deg, #d97706, #f59e0b)',
 4),
('ultimate', 'Ultimate', 'المتقدمة',
 'White-glove service with custom integrations', 'خدمة متكاملة مع تكاملات مخصصة',
 -1, -1, 102400,
 '{"accounting":true,"projects":true,"procurement":true,"inventory":true,"hr":true,"payroll":true,"equipment":true,"advanced_reports":true,"multi_branch":true,"api_access":true,"priority_support":true}',
 4999, 49990,
 ' ', '#7c3aed', '#f5f3ff', ' ', 'linear-gradient(135deg, #7c3aed, #a855f7)',
 5)
ON CONFLICT (code) DO NOTHING;

-- ── Seed Admin User (password: admin123) ───────────────────
INSERT INTO lic_master_users (email, password_hash, full_name, role)
VALUES ('admin@dynamicpro.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6LrujFvjn7t0z3iO', 'System Admin', 'super_admin')
ON CONFLICT (email) DO NOTHING;

COMMIT;
