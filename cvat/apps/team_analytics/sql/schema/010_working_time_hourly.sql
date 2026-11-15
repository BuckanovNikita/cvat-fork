-- Working time per hour (UTC), organization, project, task and annotator.
-- org_id 0 = personal workspace (no organization); project_id 0 = No project.
CREATE TABLE IF NOT EXISTS $totals_db.working_time_hourly
(
    hour DateTime('Etc/UTC'),
    org_id UInt64,
    project_id UInt64,
    task_id UInt64,
    user_id UInt64,
    user_name String,
    working_ms UInt64,
    version UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, org_id, user_id, project_id, task_id, version)
