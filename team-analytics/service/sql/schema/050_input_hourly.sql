-- Keyboard and mouse use per hour (UTC), organization, project, task and annotator, from the UI's input
-- summary records. Tall: one row per (kind, name) used.
--   kind: 'hotkey' (name = the shortcut's action name, e.g. NEXT_FRAME) |
--         'mouse'  (name = the interface zone clicked; zone 'canvas' is drawing and editing, not a mouse action)
--   actions: number of hotkey actions or clicks
-- org_id 0 = personal workspace (no organization); project_id 0 = No project.
CREATE TABLE IF NOT EXISTS $totals_db.input_hourly
(
    hour DateTime('Etc/UTC'),
    org_id UInt64,
    project_id UInt64,
    task_id UInt64,
    user_id UInt64,
    user_name String,
    kind LowCardinality(String),
    name LowCardinality(String),
    actions UInt64,
    version UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, org_id, user_id, project_id, task_id, kind, name, version)
