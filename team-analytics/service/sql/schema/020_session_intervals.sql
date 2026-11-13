-- Sessions as whole intervals: one row per session, with the time the session spent in each project.
-- Two sets: instance_wide = 0 holds sessions per organization (org_id 0 = personal workspace), formed
-- from that organization's events only; instance_wide = 1 holds sessions over all of a person's work
-- (org_id 0), for instance scope.
-- `hour` is the hour (UTC) in which the session ends: a session belongs to that hour, so a refresh
-- whose window holds the end rewrites the whole session and the usual hour replacement applies.
-- project_ids / project_ms are parallel arrays sorted by project id (0 = No project); a project the
-- session touched without time credited to it is listed with 0 ms.
CREATE TABLE IF NOT EXISTS $totals_db.session_intervals
(
    hour DateTime('Etc/UTC'),
    instance_wide UInt8,
    org_id UInt64,
    user_id UInt64,
    user_name String,
    start_at DateTime64(3, 'Etc/UTC'),
    end_at DateTime64(3, 'Etc/UTC'),
    length_ms UInt64,
    project_ids Array(UInt64),
    project_ms Array(UInt64),
    version UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, instance_wide, org_id, user_id, start_at, version)
