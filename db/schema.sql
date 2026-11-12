-- Support Ticket System: database schema
--
-- Run ONCE as the database owner (Supabase: SQL Editor, which runs as "postgres").
-- The backend never runs this file. It connects as the restricted role
-- "support_app" created at the bottom, which cannot create, alter or drop tables.
--
-- All tables are prefixed "support_" so they can share one Supabase project
-- with other apps.
--
-- Needs PostgreSQL 13+ (gen_random_uuid() is built in).

BEGIN;

-- ---------------------------------------------------------------------------
-- Users: customers and staff in one table, separated by role.
-- ---------------------------------------------------------------------------
CREATE TABLE support_users (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Stored lowercase so "Ann@x.com" and "ann@x.com" can't both register.
    email         text        NOT NULL UNIQUE
                              CHECK (email = lower(email) AND char_length(email) BETWEEN 3 AND 254),
    name          text        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    password_hash text        NOT NULL,
    role          text        NOT NULL DEFAULT 'customer'
                              CHECK (role IN ('customer', 'staff')),
    created_at    timestamptz NOT NULL DEFAULT now()
);
-- No extra index needed for login: UNIQUE(email) already creates one.

-- Index: GET /staff lists all staff users. Partial index, so it only
-- contains the (few) staff rows instead of every customer.
CREATE INDEX support_users_staff_idx ON support_users (name) WHERE role = 'staff';

-- ---------------------------------------------------------------------------
-- Tickets
-- ---------------------------------------------------------------------------
CREATE TABLE support_tickets (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- RESTRICT: a user with tickets can't be deleted by accident.
    customer_id uuid        NOT NULL REFERENCES support_users (id) ON DELETE RESTRICT,
    -- SET NULL: if a staff account is removed, its tickets become unassigned.
    -- "Assignee must be staff" can't be a CHECK (it spans two tables), so the
    -- backend enforces it and a test covers it.
    assignee_id uuid        NULL     REFERENCES support_users (id) ON DELETE SET NULL,
    title       text        NOT NULL CHECK (char_length(title) BETWEEN 5 AND 120),
    description text        NOT NULL CHECK (char_length(description) BETWEEN 10 AND 5000),
    status      text        NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'in_progress', 'resolved')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    -- Set by the backend on every update (no trigger, to keep it simple).
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (updated_at >= created_at)
);

-- Index: a customer's "My tickets" page filters by customer_id and sorts
-- newest first. Also covers the customer_id foreign key.
CREATE INDEX support_tickets_customer_idx ON support_tickets (customer_id, created_at DESC);

-- Index: staff filter "assigned to me" / a given staff member.
-- Also covers the assignee_id foreign key (ON DELETE SET NULL looks rows up by it).
CREATE INDEX support_tickets_assignee_idx ON support_tickets (assignee_id);

-- Index: the staff dashboard filters by status and sorts newest first.
CREATE INDEX support_tickets_status_idx ON support_tickets (status, created_at DESC);

-- ---------------------------------------------------------------------------
-- Comments: the reply thread on a ticket.
-- ---------------------------------------------------------------------------
CREATE TABLE support_comments (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- CASCADE: comments have no meaning without their ticket.
    ticket_id  uuid        NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    author_id  uuid        NOT NULL REFERENCES support_users (id) ON DELETE RESTRICT,
    body       text        NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Index: loading a ticket's thread, oldest first. Also covers the ticket_id foreign key.
CREATE INDEX support_comments_ticket_idx ON support_comments (ticket_id, created_at);

-- Index: covers the author_id foreign key, so deleting/checking a user
-- doesn't scan every comment.
CREATE INDEX support_comments_author_idx ON support_comments (author_id);

-- ---------------------------------------------------------------------------
-- Restricted app role (least privilege)
-- ---------------------------------------------------------------------------
-- Created WITHOUT a password here, so no secret is ever committed.
-- After running this file, set the password separately (not saved anywhere):
--     ALTER ROLE support_app WITH LOGIN PASSWORD '<generate-a-long-random-password>';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'support_app') THEN
        CREATE ROLE support_app NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO support_app;
-- Can't create tables (PostgreSQL 15+ already blocks this; explicit for older versions).
REVOKE CREATE ON SCHEMA public FROM support_app;

-- Users: read, and insert ONLY email/name/password_hash.
-- "role" isn't in the column list, so new rows always get the default 'customer'.
-- Even a bug in the backend can't create a staff account through this role.
-- Staff are created by backend/create_staff.py using the owner connection.
GRANT SELECT ON support_users TO support_app;
GRANT INSERT (email, name, password_hash) ON support_users TO support_app;

-- Tickets: read, open (status defaults to 'open'), and update only the
-- fields staff can change. No DELETE.
GRANT SELECT ON support_tickets TO support_app;
GRANT INSERT (customer_id, title, description) ON support_tickets TO support_app;
GRANT UPDATE (status, assignee_id, updated_at) ON support_tickets TO support_app;

-- Comments: read and add. No editing or deleting.
GRANT SELECT ON support_comments TO support_app;
GRANT INSERT (ticket_id, author_id, body) ON support_comments TO support_app;

-- ---------------------------------------------------------------------------
-- Row-level security
-- ---------------------------------------------------------------------------
-- With RLS on and no policy, a role sees nothing. Only support_app gets a
-- policy, so any other non-owner role (e.g. Supabase's anon/authenticated)
-- is blocked even if it somehow had table grants.
-- Per-user ownership ("customers see only their tickets") is enforced in the
-- backend, because every request uses the same support_app connection.
ALTER TABLE support_users    ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets  ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_comments ENABLE ROW LEVEL SECURITY;

CREATE POLICY support_app_access ON support_users    FOR ALL TO support_app USING (true) WITH CHECK (true);
CREATE POLICY support_app_access ON support_tickets  FOR ALL TO support_app USING (true) WITH CHECK (true);
CREATE POLICY support_app_access ON support_comments FOR ALL TO support_app USING (true) WITH CHECK (true);

-- Supabase grants its API roles access to new tables by default.
-- The Data API is off for this project, but remove those grants anyway.
-- (Skipped on plain PostgreSQL, where these roles don't exist.)
DO $$
DECLARE
    api_role text;
BEGIN
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON support_users, support_tickets, support_comments FROM %I', api_role);
        END IF;
    END LOOP;
END
$$;

COMMIT;
