-- Q7: hourly rollup holding the additive pieces of Q1-Q3.
-- NULL project/task (client events not bound to a job) are stored as 0.
-- ReplacingMergeTree: re-inserting an hour replaces the old row (newest `version` wins);
-- readers must use FINAL until background merges have removed the old rows.
DROP TABLE IF EXISTS rollup_hourly;
CREATE TABLE rollup_hourly
(
  org_id UInt64, project_id UInt64, task_id UInt64, user_id UInt64, hour DateTime('Etc/UTC'),
  -- Q1
  working_ms UInt64,
  events UInt64,
  scope_counts Map(LowCardinality(String), UInt64),
  -- Q2: session starts / in-session gap time, attributed to the hour (and project/task) of the
  -- event that starts the session / ends the gap. Sessions are per user across all projects.
  session_starts UInt64, session_ms UInt64,
  -- Q3: time since the user's previous client event (<= 100 s), by operation of the current event,
  -- the four named operations only when payload shape_type = rectangle
  other_ms UInt64, other_n UInt64,
  creation_ms UInt64, creation_n UInt64,
  alignment_ms UInt64, alignment_n UInt64,
  class_change_ms UInt64, class_change_n UInt64,
  deletion_ms UInt64, deletion_n UInt64,
  version DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(hour)
ORDER BY (org_id, project_id, task_id, user_id, hour);
