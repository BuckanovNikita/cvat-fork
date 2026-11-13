-- Objects that exist without an operation by a person, per hour (UTC), organization, project, task and user:
-- what the server stored when jobs were saved, and what the built-in detector made in the annotation view.
-- Raw facts per user; whether a user is a technical account is decided when the figures are read, so the
-- configured list can change without recomputing history.
--   source:     'saved' (server rows create|update|delete:shapes|tracks|tags) |
--               'detector' (client record team_analytics:model_creation)
--   action:     'create' | 'update' | 'delete' (detector: 'create')
--   resource:   'shapes' (single-frame) | 'tracks' | 'tags'; detector: 'shapes' for its rectangles,
--               'objects' for the rest of what it made
--   shape_type: the server row's obj_name ('rectangle', 'polygon', ..., '' for tags),
--               detector: 'rectangle' for its single-frame rectangles, '' for the rest
--   objects:    top-level objects (the row's count)
-- org_id 0 = personal workspace (no organization); project_id 0 = No project; task 0 = no task.
CREATE TABLE IF NOT EXISTS $totals_db.boxes_hourly
(
    hour DateTime('Etc/UTC'),
    org_id UInt64,
    project_id UInt64,
    task_id UInt64,
    user_id UInt64,
    user_name String,
    source LowCardinality(String),
    action LowCardinality(String),
    resource LowCardinality(String),
    shape_type LowCardinality(String),
    objects UInt64,
    version UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, org_id, user_id, project_id, task_id, source, action, resource, shape_type, version)
