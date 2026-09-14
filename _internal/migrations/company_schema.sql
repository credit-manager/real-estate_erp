-- ============================================================================
-- DynamicPro – Company Database Schema
-- Applied when a new company database is created.
-- PostgreSQL 14+
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. users
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id                  SERIAL PRIMARY KEY,
    username            VARCHAR(80)  NOT NULL UNIQUE,
    email               VARCHAR(120) NOT NULL UNIQUE,
    full_name           VARCHAR(120) NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    role                VARCHAR(50)  NOT NULL DEFAULT 'employee',
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 2. roles
-- ---------------------------------------------------------------------------
CREATE TABLE roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL DEFAULT '',
    is_system   BOOLEAN      NOT NULL DEFAULT FALSE,
    permissions JSONB        NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- 3. companies
-- ---------------------------------------------------------------------------
CREATE TABLE companies (
    id                       SERIAL PRIMARY KEY,
    name                     VARCHAR(200) NOT NULL,
    legal_name               VARCHAR(200),
    tax_number               VARCHAR(50),
    commercial_registration  VARCHAR(50),
    address                  VARCHAR(300),
    phone                    VARCHAR(20),
    email                    VARCHAR(120),
    website                  VARCHAR(120),
    currency                 VARCHAR(10)  NOT NULL DEFAULT 'EGP',
    is_active                BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 4. branches
-- ---------------------------------------------------------------------------
CREATE TABLE branches (
    id            SERIAL PRIMARY KEY,
    company_id    INTEGER      NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    code          VARCHAR(50),
    city          VARCHAR(100),
    address       VARCHAR(300),
    phone         VARCHAR(20),
    manager_name  VARCHAR(120),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_branches_company_id ON branches(company_id);

-- ---------------------------------------------------------------------------
-- 5. financial_years
-- ---------------------------------------------------------------------------
CREATE TABLE financial_years (
    id          SERIAL PRIMARY KEY,
    company_id  INTEGER      NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    start_date  DATE         NOT NULL,
    end_date    DATE         NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT FALSE,
    is_closed   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_financial_year_company_name UNIQUE (company_id, name)
);

CREATE INDEX idx_financial_years_company_id ON financial_years(company_id);

-- ---------------------------------------------------------------------------
-- 6. currencies
-- ---------------------------------------------------------------------------
CREATE TABLE currencies (
    id                      SERIAL PRIMARY KEY,
    company_id              INTEGER      NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name                    VARCHAR(120) NOT NULL,
    code                    VARCHAR(10)  NOT NULL,
    symbol                  VARCHAR(10),
    rate                    DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    is_base                 BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
    exchange_rate_source    VARCHAR(50)  NOT NULL DEFAULT '',
    exchange_rate_updated_at TIMESTAMP,
    created_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_currency_company_code UNIQUE (company_id, code)
);

CREATE INDEX idx_currencies_company_id ON currencies(company_id);

-- ---------------------------------------------------------------------------
-- 7. exchange_rate_history
-- ---------------------------------------------------------------------------
CREATE TABLE exchange_rate_history (
    id          SERIAL PRIMARY KEY,
    currency_id INTEGER        NOT NULL REFERENCES currencies(id) ON DELETE CASCADE,
    company_id  INTEGER        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    rate_date   DATE           NOT NULL,
    buy_rate    DOUBLE PRECISION NOT NULL DEFAULT 0,
    sell_rate   DOUBLE PRECISION NOT NULL DEFAULT 0,
    mid_rate    DOUBLE PRECISION NOT NULL,
    source      VARCHAR(50)    NOT NULL DEFAULT 'manual',
    source_url  VARCHAR(500),
    notes       VARCHAR(200),
    created_by  INTEGER        REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMP      NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_currency_rate_date UNIQUE (currency_id, rate_date)
);

CREATE INDEX idx_exchange_rate_history_currency_id ON exchange_rate_history(currency_id);
CREATE INDEX idx_exchange_rate_history_company_id  ON exchange_rate_history(company_id);

-- ---------------------------------------------------------------------------
-- 8. tax_types
-- ---------------------------------------------------------------------------
CREATE TABLE tax_types (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    rate       NUMERIC(5,2) NOT NULL DEFAULT 0,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    is_default BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 9. system_settings
-- ---------------------------------------------------------------------------
CREATE TABLE system_settings (
    id         SERIAL PRIMARY KEY,
    key        VARCHAR(100) NOT NULL UNIQUE,
    value      TEXT,
    updated_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 10. customers
-- ---------------------------------------------------------------------------
CREATE TABLE customers (
    id         SERIAL PRIMARY KEY,
    full_name  VARCHAR(120) NOT NULL,
    phone      VARCHAR(20),
    email      VARCHAR(120),
    address    VARCHAR(200),
    type       VARCHAR(30)  NOT NULL DEFAULT 'individual',
    company    VARCHAR(150),
    notes      TEXT,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_full_name ON customers(full_name);
CREATE INDEX idx_customers_phone     ON customers(phone);

-- ---------------------------------------------------------------------------
-- 11. suppliers
-- ---------------------------------------------------------------------------
CREATE TABLE suppliers (
    id            SERIAL PRIMARY KEY,
    company_name  VARCHAR(200) NOT NULL,
    contact_name  VARCHAR(120),
    phone         VARCHAR(20),
    email         VARCHAR(120),
    address       VARCHAR(200),
    category      VARCHAR(80),
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_suppliers_company_name ON suppliers(company_name);

-- ---------------------------------------------------------------------------
-- 12. audit_logs
-- ---------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    username    VARCHAR(80),
    action      VARCHAR(30),
    entity      VARCHAR(50),
    entity_id   INTEGER,
    description VARCHAR(300),
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id    ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity     ON audit_logs(entity, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- ---------------------------------------------------------------------------
-- 13. workflow_templates
-- ---------------------------------------------------------------------------
CREATE TABLE workflow_templates (
    id         SERIAL PRIMARY KEY,
    doc_type   VARCHAR(30)  NOT NULL,
    name       VARCHAR(120) NOT NULL,
    min_amount NUMERIC(15,2),
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workflow_templates_doc_type ON workflow_templates(doc_type);

-- ---------------------------------------------------------------------------
-- 14. workflow_steps
-- ---------------------------------------------------------------------------
CREATE TABLE workflow_steps (
    id          SERIAL PRIMARY KEY,
    template_id INTEGER      REFERENCES workflow_templates(id) ON DELETE CASCADE,
    position    INTEGER      NOT NULL DEFAULT 1,
    role        VARCHAR(60)  NOT NULL
);

CREATE INDEX idx_workflow_steps_template_id ON workflow_steps(template_id);

-- ---------------------------------------------------------------------------
-- 15. approval_requests
-- ---------------------------------------------------------------------------
CREATE TABLE approval_requests (
    id            SERIAL PRIMARY KEY,
    doc_type      VARCHAR(30) NOT NULL,
    doc_id        INTEGER     NOT NULL,
    template_id   INTEGER     REFERENCES workflow_templates(id) ON DELETE SET NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    current_step  INTEGER     NOT NULL DEFAULT 1,
    submitted_by  INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    submitted_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    decided_by    INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    decided_at    TIMESTAMP,
    comment       TEXT
);

CREATE INDEX idx_approval_requests_doc          ON approval_requests(doc_type, doc_id);
CREATE INDEX idx_approval_requests_status       ON approval_requests(status);
CREATE INDEX idx_approval_requests_submitted_by ON approval_requests(submitted_by);

-- ---------------------------------------------------------------------------
-- 16. approval_step_records
-- ---------------------------------------------------------------------------
CREATE TABLE approval_step_records (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER     REFERENCES approval_requests(id) ON DELETE CASCADE,
    step_id     INTEGER     REFERENCES workflow_steps(id) ON DELETE SET NULL,
    position    INTEGER     NOT NULL DEFAULT 1,
    role        VARCHAR(60),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    approver_id INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    comment     TEXT,
    decided_at  TIMESTAMP
);

CREATE INDEX idx_approval_step_records_request_id ON approval_step_records(request_id);

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Default admin user (password must be changed on first login)
INSERT INTO users (username, email, full_name, password_hash, role, is_active, must_change_password)
VALUES (
    'admin',
    'admin@dynamicpro.local',
    'Administrator',
    -- placeholder hash; the application replaces this via the before_insert event
    'pbkdf2:sha256:placeholder',
    'admin',
    TRUE,
    TRUE
);

-- Default roles
INSERT INTO roles (name, description, is_system, permissions) VALUES
    ('admin',       'Full system administrator', TRUE,  '{"*": ["*"]}'),
    ('manager',     'Company manager',           FALSE, '{"finance": ["read","write"], "inventory": ["read","write"], "reports": ["read"]}'),
    ('accountant',  'Accounting staff',          FALSE, '{"finance": ["read","write"], "reports": ["read"]}'),
    ('employee',    'General employee',          FALSE, '{"dashboard": ["read"]}'),
    ('viewer',      'Read-only access',          FALSE, '{"*": ["read"]}');

-- Default currency (Egyptian Pound)
INSERT INTO currencies (company_id, name, code, symbol, rate, is_base, is_active)
VALUES
    (1, 'Egyptian Pound',  'EGP', 'ج.م', 1.0,   TRUE,  TRUE),
    (1, 'US Dollar',       'USD', '$',   50.0,  FALSE, TRUE),
    (1, 'Euro',            'EUR', '€',   54.5,  FALSE, TRUE);

-- Default tax types
INSERT INTO tax_types (name, rate, is_active, is_default) VALUES
    ('No Tax',  0.00,  TRUE, TRUE),
    ('VAT 14%', 14.00, TRUE, FALSE),
    ('VAT 5%',  5.00,  TRUE, FALSE),
    ('VAT 0%',  0.00,  TRUE, FALSE);

-- Default system settings
INSERT INTO system_settings (key, value) VALUES
    ('company_name',        'My Company'),
    ('company_currency',    'EGP'),
    ('tax_enabled',         'true'),
    ('default_tax_rate',    '0'),
    ('invoice_prefix',      'INV-'),
    ('po_prefix',           'PO-'),
    ('date_format',         'YYYY-MM-DD'),
    ('fiscal_year_start',   '01'),
    ('language',            'ar'),
    ('theme',               'light');
