-- Trends: one row per line and bucket (twelve Monday weeks, or calendar months when {monthly} is 1, in the
-- viewer's zone {tz}), every bucket of every line present, empty ones as zeros. The buckets are the dates
-- {buckets}; an hour belongs to the bucket of the viewer day it starts in, kept from {first_bucket} on (a
-- zone offset by part of an hour moves the edge by that part).
--
-- Lines: {line_kind} 'scope' = one line (key 0) for the scope under both filters; 'annotators' = one line
-- per user id in {ids}, 'projects' = one per project id in {ids}. The compared dimension replaces its own
-- filter; the other filter still applies. Scope conditions and technical accounts as everywhere else.
--
-- Per line and bucket: working time; objects created by annotator methods (drawn, pasted, propagated, and
-- stored 'redone' rows written before redone creations got a method) with their timed objects and time;
-- hotkey and mouse actions (the canvas left out). `legacy` = the line has job work in the bucket and the
-- bucket is in {legacy_buckets} (it ends before the cutover to the new logging, see cutover.py; the bucket
-- holding the cutover is not). `all_shapes`: the switch says All shapes, or {all_legacy} (every bucket is
-- before the cutover, as a legacy period in the overview). Otherwise,
-- under Bounding boxes, a legacy bucket's boxes cannot be told apart, so its creation figures are NULL (never
-- all shapes on a line of boxes). Hotkey use is not recorded in a legacy bucket without any input row.
WITH
    work AS (
        SELECT
            toUInt64(multiIf({line_kind:String} = 'annotators', user_id,
                             {line_kind:String} = 'projects', project_id, 0)) AS line,
            greatest(if({monthly:UInt8} = 1, toStartOfMonth(toDate(hour, {tz:String})),
                        toMonday(toDate(hour, {tz:String}))), toDate({first_bucket:String})) AS bucket,
            sum(working_ms) AS working_ms
        FROM $totals_db.working_time_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND user_id NOT IN {technical_accounts:Array(UInt64)}
            AND ({has_project:UInt8} = 0 OR {line_kind:String} = 'projects' OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR {line_kind:String} = 'annotators' OR user_id = {annotator:UInt64})
            AND ({line_kind:String} = 'scope' OR line IN {ids:Array(UInt64)})
        GROUP BY line, bucket
    ),
    ops AS (
        SELECT
            toUInt64(multiIf({line_kind:String} = 'annotators', user_id,
                             {line_kind:String} = 'projects', project_id, 0)) AS line,
            greatest(if({monthly:UInt8} = 1, toStartOfMonth(toDate(hour, {tz:String})),
                        toMonday(toDate(hour, {tz:String}))), toDate({first_bucket:String})) AS bucket,
            sum(objects) AS op_objects,
            sumIf(objects, operation = 'creation' AND method IN ('drawn', 'pasted', 'propagated', 'redone')) AS made_all,
            sumIf(timed_objects, operation = 'creation' AND method IN ('drawn', 'pasted', 'propagated', 'redone')) AS timed_all,
            sumIf(time_ms, operation = 'creation' AND method IN ('drawn', 'pasted', 'propagated', 'redone')) AS time_all,
            sumIf(objects, operation = 'creation' AND method IN ('drawn', 'pasted', 'propagated', 'redone')
                AND shape = 'bounding_box') AS made_boxes,
            sumIf(timed_objects, operation = 'creation' AND method IN ('drawn', 'pasted', 'propagated', 'redone')
                AND shape = 'bounding_box') AS timed_boxes,
            sumIf(time_ms, operation = 'creation' AND method IN ('drawn', 'pasted', 'propagated', 'redone')
                AND shape = 'bounding_box') AS time_boxes
        FROM $totals_db.operations_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND user_id NOT IN {technical_accounts:Array(UInt64)}
            AND ({has_project:UInt8} = 0 OR {line_kind:String} = 'projects' OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR {line_kind:String} = 'annotators' OR user_id = {annotator:UInt64})
            AND ({line_kind:String} = 'scope' OR line IN {ids:Array(UInt64)})
        GROUP BY line, bucket
    ),
    input AS (
        SELECT
            toUInt64(multiIf({line_kind:String} = 'annotators', user_id,
                             {line_kind:String} = 'projects', project_id, 0)) AS line,
            greatest(if({monthly:UInt8} = 1, toStartOfMonth(toDate(hour, {tz:String})),
                        toMonday(toDate(hour, {tz:String}))), toDate({first_bucket:String})) AS bucket,
            count() AS input_rows,
            sumIf(actions, kind = 'hotkey') AS hotkey_actions,
            sumIf(actions, kind = 'mouse' AND name != 'canvas') AS mouse_actions
        FROM $totals_db.input_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND user_id NOT IN {technical_accounts:Array(UInt64)}
            AND ({has_project:UInt8} = 0 OR {line_kind:String} = 'projects' OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR {line_kind:String} = 'annotators' OR user_id = {annotator:UInt64})
            AND ({line_kind:String} = 'scope' OR line IN {ids:Array(UInt64)})
        GROUP BY line, bucket
    ),
    grid AS (
        SELECT line, bucket
        FROM (SELECT arrayJoin(if({line_kind:String} = 'scope', [toUInt64(0)], {ids:Array(UInt64)})) AS line) AS lines
        CROSS JOIN (SELECT arrayJoin(arrayMap(day -> toDate(day), {buckets:Array(String)})) AS bucket) AS buckets
    )
SELECT
    grid.line AS line,
    grid.bucket AS bucket,
    toUInt64(work.working_ms) AS working_time_ms,
    (work.working_ms > 0 OR ops.op_objects > 0)
        AND has(arrayMap(day -> toDate(day), {legacy_buckets:Array(String)}), grid.bucket) AS legacy,
    -- as in the overview: when every bucket is before the cutover, all shapes are shown
    {bounding_boxes:UInt8} = 0 OR {all_legacy:UInt8} = 1 AS all_shapes,
    NOT all_shapes AND legacy AS boxes_unknown,
    if(boxes_unknown, NULL, toUInt64(if(all_shapes, ops.made_all, ops.made_boxes))) AS boxes,
    if(boxes_unknown, NULL, toUInt64(if(all_shapes, ops.timed_all, ops.timed_boxes))) AS timed_boxes,
    if(boxes_unknown, NULL, toUInt64(if(all_shapes, ops.time_all, ops.time_boxes))) AS box_time_ms,
    if(timed_boxes > 0, box_time_ms / timed_boxes, NULL) AS average_ms,
    NOT (legacy AND input.input_rows = 0) AS hotkey_recorded,
    toUInt64(input.hotkey_actions) AS hotkey_actions,
    toUInt64(input.mouse_actions) AS mouse_actions,
    if(hotkey_recorded AND hotkey_actions + mouse_actions > 0,
       hotkey_actions / (hotkey_actions + mouse_actions), NULL) AS hotkey_share
FROM grid
LEFT JOIN work ON work.line = grid.line AND work.bucket = grid.bucket
LEFT JOIN ops ON ops.line = grid.line AND ops.bucket = grid.bucket
LEFT JOIN input ON input.line = grid.line AND input.bucket = grid.bucket
ORDER BY indexOf(if({line_kind:String} = 'scope', [toUInt64(0)], {ids:Array(UInt64)}), line), bucket
