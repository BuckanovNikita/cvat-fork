-- The four operations and Other for [from, to) in the displayed scope, in a fixed order.
-- Shape switch: with {bounding_boxes} = 1 only bounding box rows count (shape 'bounding_box'), unless the
-- period is legacy ({legacy_period} = 1: it ends before the cutover to the new logging, see cutover.py),
-- which shows all shapes; `all_shapes` says what was applied.
-- Other = working time - operation time over the whole displayed scope, never below zero, so that the
-- operations and Other add up to their own total (`active_ms`) and the shares to 100 %.
-- `legacy` = 1 when the period is legacy and the scope (filters included) has job work in it; a period
-- with no job work is empty, not legacy (nor partly legacy: `job_work`, see cutover.py).
-- hotkey_objects / mouse_objects: objects of operations started by hotkey / by mouse (neither when the
-- input method was not recorded).
-- Technical accounts are left out of both operation time and working time.
WITH
    in_scope AS (
        SELECT operation, shape, objects, timed_objects, time_ms, hotkey_objects, mouse_objects
        FROM $totals_db.operations_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND user_id NOT IN {technical_accounts:Array(UInt64)}
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
    ),
    -- job work = working time or an operation; with none, the period is empty, not legacy
    (SELECT count() FROM in_scope) AS operation_rows,
    {bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1 AS all_shapes,
    scoped AS (
        SELECT operation, shape, objects, timed_objects, time_ms, hotkey_objects, mouse_objects
        FROM in_scope
        WHERE ({bounding_boxes:UInt8} = 0 OR shape = 'bounding_box' OR {legacy_period:UInt8} = 1)
    ),
    (
        SELECT toInt64(sum(working_ms))
        FROM $totals_db.working_time_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND user_id NOT IN {technical_accounts:Array(UInt64)}
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
    ) AS working_ms,
    (SELECT toInt64(sum(time_ms)) FROM scoped) AS operations_ms,
    greatest(working_ms - operations_ms, toInt64(0)) AS other_ms,
    operations_ms + other_ms AS active_ms,
    operation_rows > 0 OR working_ms > 0 AS job_work,
    job_work AND {legacy_period:UInt8} = 1 AS legacy
SELECT
    names.name AS operation,
    if(names.name = 'other', toUInt64(0), totals.objects) AS objects,
    if(names.name = 'other', toUInt64(0), totals.timed_objects) AS timed_objects,
    if(names.name = 'other', other_ms, toInt64(totals.time_ms)) AS time_ms,
    if(names.name != 'other' AND timed_objects > 0, time_ms / timed_objects, NULL) AS average_ms,
    if(active_ms > 0, time_ms / active_ms, NULL) AS share,
    if(names.name = 'other', toUInt64(0), totals.hotkey_objects) AS hotkey_objects,
    if(names.name = 'other', toUInt64(0), totals.mouse_objects) AS mouse_objects,
    working_ms,
    active_ms,
    legacy,
    job_work,
    all_shapes
FROM (
    SELECT arrayJoin(['creation', 'alignment', 'class_change', 'deletion', 'other']) AS name
) AS names
LEFT JOIN (
    SELECT operation, sum(objects) AS objects, sum(timed_objects) AS timed_objects, sum(time_ms) AS time_ms,
        sum(hotkey_objects) AS hotkey_objects, sum(mouse_objects) AS mouse_objects
    FROM scoped
    GROUP BY operation
) AS totals ON totals.operation = names.name
ORDER BY indexOf(['creation', 'alignment', 'class_change', 'deletion', 'other'], names.name)
