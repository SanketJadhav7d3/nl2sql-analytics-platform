-- ============================================================================
-- APP SCHEMA — authentication, RBAC and audit.
-- Also provisions a read-only Postgres role used to execute ad-hoc /query and
-- /nl-query SQL, so least-privilege is enforced at the database level, not just
-- in Python.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS app;

-- Users. role is constrained to the three RBAC roles.
CREATE TABLE IF NOT EXISTS app.users (
    id              bigserial PRIMARY KEY,
    username        text NOT NULL UNIQUE,
    hashed_password text NOT NULL,
    role            text NOT NULL CHECK (role IN ('viewer', 'analyst', 'admin')),
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Audit log: one row per access decision / sensitive action.
CREATE TABLE IF NOT EXISTS app.audit_log (
    id          bigserial PRIMARY KEY,
    username    text,
    role        text,
    action      text NOT NULL,          -- e.g. 'GET /metrics/revenue', 'query', 'admin:create_user'
    detail      text,                   -- SQL text, target user, query string, ...
    status      text NOT NULL,          -- 'allowed' | 'denied' | 'error'
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON app.audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user    ON app.audit_log (username);

-- ---------------------------------------------------------------------------
-- Read-only role for ad-hoc query execution.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_ro') THEN
        CREATE ROLE analytics_ro LOGIN PASSWORD 'readonly';
    END IF;
END $$;

GRANT CONNECT ON DATABASE analytics TO analytics_ro;
GRANT USAGE  ON SCHEMA analytics TO analytics_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO analytics_ro;   -- includes views
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO analytics_ro;

-- Belt and braces: no write/DDL ability anywhere, and no reach into raw/app.
REVOKE CREATE ON SCHEMA analytics FROM analytics_ro;
REVOKE ALL ON SCHEMA raw  FROM analytics_ro;
REVOKE ALL ON SCHEMA app  FROM analytics_ro;
