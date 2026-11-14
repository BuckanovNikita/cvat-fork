-- Operations per hour (UTC), organization, project, task and annotator, one row per
-- (operation, method, shape) that occurred. Tall on purpose: a later calculation adds rows, not columns.
--   operation: 'creation' | 'alignment' | 'class_change' | 'deletion'
--   method:    creation only: 'drawn' | 'pasted' | 'propagated'; '' for the other operations. A CVAT redo
--              of created objects is no creation and is not stored. Hours stored under earlier rules still
--              hold it as one: under the method of the creation it restored, else 'drawn', or in the
--              earliest rows as 'redone', which readers count as 'drawn'.
--   shape:     'bounding_box' (single-frame rectangle) | 'other' (any other shape-tagged object) |
--              'untagged' (event without shape_type: legacy, counts only under All shapes)
--   objects:          objects the operation touched (alignment: alignments)
--   timed_objects:    objects whose operation has a measured time (no idle pause before it)
--   time_ms:          time per operation of the timed objects
--   hotkey_objects / mouse_objects: objects whose operation was started by hotkey / by mouse
-- org_id 0 = personal workspace (no organization); project_id 0 = No project.
CREATE TABLE IF NOT EXISTS $totals_db.operations_hourly
(
    hour DateTime('Etc/UTC'),
    org_id UInt64,
    project_id UInt64,
    task_id UInt64,
    user_id UInt64,
    user_name String,
    operation LowCardinality(String),
    method LowCardinality(String),
    shape LowCardinality(String),
    objects UInt64,
    timed_objects UInt64,
    time_ms UInt64,
    hotkey_objects UInt64,
    mouse_objects UInt64,
    version UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, org_id, user_id, project_id, task_id, operation, method, shape, version)
