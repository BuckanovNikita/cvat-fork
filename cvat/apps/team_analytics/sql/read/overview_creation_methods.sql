-- Creation methods for [from, to) in the displayed scope: drawn, pasted and propagated, always in that
-- order, zeros included. The rows are the Creation operation's rows of read/overview_operations.sql split
-- by method, under the same shape switch rule ({legacy_period}, so a legacy period shows all
-- shapes here exactly when the operations do), so the three add up to the Creation figures and the total
-- average is the Creation average. Average = time / timed objects (null when none is timed). A stored
-- 'redone' row (written before redone creations were attributed to a method) counts as drawn, the fallback
-- for a redo.
-- Model (`model_objects`) is the fourth method, with a count and no time, never part of Creation: objects a
-- technical account saved (create rows; only without an annotator filter, since a technical account is no
-- annotator) plus objects the built-in detector made for annotators. Under bounding boxes only single-frame
-- rectangles count; under all shapes (or in a legacy period) every object. Share = objects / (objects of the three + Model), null
-- when there are none.
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
    {bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1 AS all_shapes,
    scoped AS (
        SELECT if(method = 'redone', 'drawn', method) AS method, objects, timed_objects, time_ms
        FROM in_scope
        WHERE operation = 'creation'
            AND ({bounding_boxes:UInt8} = 0 OR shape = 'bounding_box' OR {legacy_period:UInt8} = 1)
    ),
    (SELECT sum(objects) FROM scoped) AS all_objects,
    (SELECT sum(timed_objects) FROM scoped) AS all_timed,
    (SELECT sum(time_ms) FROM scoped) AS all_time,
    (
        SELECT sum(objects)
        FROM $totals_db.boxes_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND action = 'create'
            AND (
                (source = 'saved' AND user_name IN {technical_accounts:Array(String)} AND {has_annotator:UInt8} = 0)
                OR (source = 'detector' AND user_name NOT IN {technical_accounts:Array(String)}
                    AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64}))
            )
            -- all shapes when asked for or in a legacy period (before the cutover to the new logging)
            AND ({bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1
                OR (resource = 'shapes' AND shape_type = 'rectangle'))
    ) AS model_objects,
    all_objects + model_objects AS every_object
SELECT
    names.name AS method,
    totals.objects AS objects,
    totals.timed_objects AS timed_objects,
    totals.time_ms AS time_ms,
    if(timed_objects > 0, time_ms / timed_objects, NULL) AS average_ms,
    if(every_object > 0, objects / every_object, NULL) AS share,
    all_objects,
    all_timed,
    all_time,
    if(all_timed > 0, all_time / all_timed, NULL) AS all_average_ms,
    model_objects,
    if(every_object > 0, model_objects / every_object, NULL) AS model_share,
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
