INSERT INTO users VALUES
  ('alice', 'Alice (Procurement)'),
  ('bob',   'Bob (East Plant maintenance)'),
  ('carol', 'Carol (Turbine engineering)'),
  ('dave',  'Dave (Warehouse)');

INSERT INTO group_members VALUES
  ('alice', 'group:all-employees'), ('alice', 'group:procurement'),
  ('bob',   'group:all-employees'), ('bob',   'group:plant-east-maintenance'),
  ('carol', 'group:all-employees'), ('carol', 'group:plant-east-maintenance'),
  ('carol', 'group:engineering-confidential'),
  ('dave',  'group:all-employees');

-- Three named contracts the corpus documents describe, plus 97 generated ones = 100
INSERT INTO contracts VALUES
  ('CTR-1001', 'Supplier X', 'active',     '2025-01-01', '2027-12-31', 'eu-west', 'group:procurement'),
  ('CTR-1002', 'Supplier X', 'active',     '2026-02-01', '2028-01-31', 'eu-west', 'group:procurement'),
  ('CTR-1003', 'Supplier X', 'terminated', '2024-06-01', '2026-09-30', 'eu-west', 'group:procurement');
INSERT INTO contracts
SELECT 'CTR-' || (2000 + n),
       'Supplier ' || chr(65 + (n % 20)),               -- Supplier A to Supplier T
       CASE WHEN n % 4 = 0 THEN 'terminated' ELSE 'active' END,
       DATE '2025-01-01' + n,
       DATE '2027-01-01' + n,
       'eu-west',
       'group:procurement'
FROM generate_series(1, 97) AS n;

INSERT INTO assets VALUES
  ('ENG-4573', 'Conveyor C-12 drive', 'East Plant',
   'Quarterly inspection; drive encoder check every 500 operating hours', 'group:plant-east-maintenance'),
  ('ENG-4580', 'Conveyor C-13 drive', 'East Plant', 'Quarterly inspection', 'group:plant-east-maintenance'),
  ('ENG-5102', 'Press P-4 hydraulics', 'East Plant',
   'Monthly hose inspection; annual pump overhaul', 'group:plant-east-maintenance');

INSERT INTO procurement_spend VALUES
  ('2026-Q2', 'Spare parts',          398500.00, 'group:procurement'),
  ('2026-Q2', 'Maintenance services', 251000.00, 'group:procurement'),
  ('2026-Q2', 'Packaging',             91200.00, 'group:procurement'),
  ('2026-Q3', 'Spare parts',          412000.00, 'group:procurement'),
  ('2026-Q3', 'Maintenance services', 268500.00, 'group:procurement'),
  ('2026-Q3', 'Packaging',             97250.00, 'group:procurement');
