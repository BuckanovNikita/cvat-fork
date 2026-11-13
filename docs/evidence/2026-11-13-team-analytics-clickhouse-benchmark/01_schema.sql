-- Exact production schema of CVAT's events table.
CREATE TABLE IF NOT EXISTS events (
  scope String, obj_name Nullable(String), obj_id Nullable(UInt64), obj_val Nullable(String),
  source String, timestamp DateTime64(3,'Etc/UTC'), count Nullable(UInt16), duration UInt32 DEFAULT 0,
  project_id Nullable(UInt64), task_id Nullable(UInt64), job_id Nullable(UInt64),
  user_id Nullable(UInt64), user_name Nullable(String), user_email Nullable(String),
  org_id Nullable(UInt64), org_slug Nullable(String), payload Nullable(String),
  access_token_id Nullable(UInt64), remote_addr Nullable(String)
) ENGINE = MergeTree PARTITION BY toYYYYMM(timestamp) ORDER BY (timestamp) SETTINGS index_granularity = 8192;

-- Same schema, tiny hand-made fixture with known answers (see 04_fixture.sql).
CREATE TABLE IF NOT EXISTS events_fx AS events;
