-- The four operations and Other for [from, to) in the displayed scope, all shapes, in a fixed order.
-- Other = working time - operation time over the whole displayed scope, never below zero, so that the
-- operations and Other add up to their own total (`active_ms`) and the shares to 100 %.
-- `legacy` = 1 when the scope (filters included) has job work in the period and no shape-tagged
-- operation; a period with no job work is empty, not legacy.
-- Technical accounts are left out of both operation time and working time.
WITH
    scoped AS (
        SELECT operation, shape, objects, timed_objects, time_ms
        FROM $totals_db.operations_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND user_name NOT IN {technical_accounts:Array(String)}
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
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
            AND user_name NOT IN {technical_accounts:Array(String)}
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
    ) AS working_ms,
    (SELECT toInt64(sum(time_ms)) FROM scoped) AS operations_ms,
    greatest(working_ms - operations_ms, toInt64(0)) AS other_ms,
    operations_ms + other_ms AS active_ms,
    -- job work = working time or an operation; with none, the period is empty, not legacy
    (SELECT count() FROM scoped) AS operation_rows,
    (SELECT countIf(shape != 'untagged') FROM scoped) AS tagged_rows,
    (operation_rows > 0 OR working_ms > 0) AND tagged_rows = 0 AS legacy
SELECT
    names.name AS operation,
    if(names.name = 'other', toUInt64(0), totals.objects) AS objects,
    if(names.name = 'other', toUInt64(0), totals.timed_objects) AS timed_objects,
    if(names.name = 'other', other_ms, toInt64(totals.time_ms)) AS time_ms,
    if(names.name != 'other' AND timed_objects > 0, time_ms / timed_objects, NULL) AS average_ms,
    if(active_ms > 0, time_ms / active_ms, NULL) AS share,
    working_ms,
    active_ms,
    legacy
FROM (
    SELECT arrayJoin(['creation', 'alignment', 'class_change', 'deletion', 'other']) AS name
) AS names
LEFT JOIN (
    SELECT operation, sum(objects) AS objects, sum(timed_objects) AS timed_objects, sum(time_ms) AS time_ms
    FROM scoped
    GROUP BY operation
) AS totals ON totals.operation = names.name
ORDER BY indexOf(['creation', 'alignment', 'class_change', 'deletion', 'other'], names.name)
