-- Identity provider stand-in (Entra ID in the case study)
CREATE TABLE users (
  user_id      TEXT PRIMARY KEY,
  display_name TEXT NOT NULL
);
CREATE TABLE group_members (
  user_id    TEXT NOT NULL REFERENCES users (user_id),
  group_name TEXT NOT NULL,
  PRIMARY KEY (user_id, group_name)
);

-- Structured operational data (the ERP and database side)
CREATE TABLE contracts (
  contract_id TEXT PRIMARY KEY,
  supplier    TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('active', 'terminated')),
  start_date  DATE NOT NULL,
  end_date    DATE NOT NULL,
  region      TEXT NOT NULL,
  acl_group   TEXT NOT NULL
);
CREATE TABLE assets (
  asset_id             TEXT PRIMARY KEY,
  name                 TEXT NOT NULL,
  site                 TEXT NOT NULL,
  maintenance_schedule TEXT NOT NULL,
  acl_group            TEXT NOT NULL
);
CREATE TABLE procurement_spend (
  quarter    TEXT NOT NULL,
  category   TEXT NOT NULL,
  amount_eur NUMERIC(12, 2) NOT NULL,
  acl_group  TEXT NOT NULL,
  PRIMARY KEY (quarter, category)
);

-- Platform tables
CREATE TABLE quarantine (
  object_key  TEXT PRIMARY KEY,
  reason      TEXT NOT NULL,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE audit_log (
  request_id     UUID PRIMARY KEY,
  ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id        TEXT NOT NULL,
  groups         TEXT[] NOT NULL,
  question       TEXT NOT NULL,
  route          TEXT NOT NULL,
  routing        JSONB NOT NULL,
  tool_calls     JSONB NOT NULL,
  chunks         JSONB NOT NULL,
  model          TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  outcome        TEXT NOT NULL,
  answer         TEXT NOT NULL,
  latency_ms     INTEGER NOT NULL
);

-- The assistant's database role: read-only, row-level security enforced.
CREATE ROLE app_user LOGIN PASSWORD 'app_user';
GRANT SELECT ON contracts, assets, procurement_spend TO app_user;

ALTER TABLE contracts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets            ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_spend ENABLE ROW LEVEL SECURITY;

-- A row is visible only when its acl_group is one of the caller's groups.
-- No groups set means no rows: the policy fails closed.
CREATE POLICY by_group ON contracts FOR SELECT TO app_user
  USING (acl_group = ANY (string_to_array(current_setting('app.groups', true), ',')));
CREATE POLICY by_group ON assets FOR SELECT TO app_user
  USING (acl_group = ANY (string_to_array(current_setting('app.groups', true), ',')));
CREATE POLICY by_group ON procurement_spend FOR SELECT TO app_user
  USING (acl_group = ANY (string_to_array(current_setting('app.groups', true), ',')));
