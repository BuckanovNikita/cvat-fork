-- Creation methods for [from, to) in the displayed scope: drawn, pasted and propagated, always in that
-- order, zeros included. The rows are the Creation operation's rows of read/overview_operations.sql split
-- by method, under the same shape switch rule (decided over all operations, so a legacy scope shows all
-- shapes here exactly when the operations do), so the three add up to the Creation figures and the total
-- average is the Creation average. Average = time / timed objects (null when none is timed); share =
-- objects / objects of the three (null when there are none). A stored 'redone' row (written before redone
-- creations were attributed to a method) counts as drawn, the fallback for a redo.
WITH
    in_scope AS (
        SELECT operation, method, shape, objects, timed_objects, time_ms
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
    (SELECT countIf(shape != 'untagged') FROM in_scope) AS tagged_rows,
    {bounding_boxes:UInt8} = 0 OR tagged_rows = 0 AS all_shapes,
    scoped AS (
        SELECT if(method = 'redone', 'drawn', method) AS method, objects, timed_objects, time_ms
        FROM in_scope
        WHERE operation = 'creation'
            AND ({bounding_boxes:UInt8} = 0 OR shape = 'bounding_box'
                OR (SELECT countIf(shape != 'untagged') FROM in_scope) = 0)
    ),
    (SELECT sum(objects) FROM scoped) AS all_objects,
    (SELECT sum(timed_objects) FROM scoped) AS all_timed,
    (SELECT sum(time_ms) FROM scoped) AS all_time
SELECT
    names.name AS method,
    totals.objects AS objects,
    totals.timed_objects AS timed_objects,
    totals.time_ms AS time_ms,
    if(timed_objects > 0, time_ms / timed_objects, NULL) AS average_ms,
    if(all_objects > 0, objects / all_objects, NULL) AS share,
    all_objects,
    all_timed,
    all_time,
    if(all_timed > 0, all_time / all_timed, NULL) AS all_average_ms,
    all_shapes
FROM (
    SELECT arrayJoin(['drawn', 'pasted', 'propagated']) AS name
) AS names
LEFT JOIN (
    SELECT method, sum(objects) AS objects, sum(timed_objects) AS timed_objects, sum(time_ms) AS time_ms
    FROM scoped
    GROUP BY method
) AS totals ON totals.method = names.name
ORDER BY indexOf(['drawn', 'pasted', 'propagated'], names.name)
