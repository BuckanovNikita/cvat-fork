-- Operations and time per operation, from the annotator's client events. Only job-bound events are
-- operations; every client event (inside a job or not) is a previous action that a gap is measured from.
--
-- Operations (events the stock UI already writes):
--   creation:  draw:object (drawn), paste:object (pasted), propagate:object (propagated), and
--              action:redo of 'Created objects' (redone: a person redid a creation they had undone).
--              Objects = the event's count (1 when empty)
--   alignment: drag:object, resize:object. Consecutive drags and resizes of the same object (same job,
--              browser `client_id`, `object_ref` and `frame`) by the same person are one alignment. Any
--              other operation, a change:frame, or a pause longer than the session gap (300 s, also the
--              look-back) between two of them ends it. Events without `object_ref` (legacy) are one
--              alignment each.
--   deletion:  delete:object; objects = the event's count. action:undo is no operation, so an undone
--              creation is not a deletion.
-- Shapes: an event without shape_type is 'untagged' (legacy). A tagged event's objects split into
-- 'bounding_box' (payload rectangle_count, at most the objects; without it: all objects when
-- shape_type = 'rectangle' and object_type = 'shape') and 'other' (the rest); the operation's time is
-- split between the two in proportion to their objects.
-- Time per operation: from the person's previous client event to the event that ends the
-- operation. A gap over the idle pause (100 s), or no known previous event, leaves the operation
-- untimed: its objects count, but it adds neither time nor timed objects. Draw, canvas paste, drag and
-- resize are logged when they end and cover [timestamp - duration, timestamp]; other events lying
-- inside that interval (zooming, moving between frames) give their gap to that operation, and the
-- operation is untimed if any of those gaps is an idle pause. An alignment runs from the action before
-- its first drag or resize to the end of its last: every gap in between is its time.
-- Events are read from `read_from` (look-back before the window) to 300 s after the window (look-ahead),
-- so gaps at the window's start are exact and an alignment going on at the window's end is left to the
-- window holding its end. Only operations ending inside [window_from, window_to) are stored, in the hour,
-- organization, project and task of the event that ends them. Rows without a user are dropped.
INSERT INTO $totals_db.operations_hourly
    (hour, org_id, project_id, task_id, user_id, user_name, operation, method, shape,
     objects, timed_objects, time_ms, hotkey_objects, mouse_objects, version)
SELECT
    toStartOfHour(fromUnixTimestamp64Milli(op_ts, 'Etc/UTC')) AS row_hour,
    op_org, op_project, op_task, user_id,
    argMax(op_user_name, op_ts),
    op_name, op_method, part_shape,
    sum(part_objects),
    sumIf(part_objects, timed),
    sumIf(part_time, timed),
    0,
    0,
    {version:UInt64}
FROM
(
    -- one row per operation, with the gaps credited to it
    SELECT
        user_id,
        credited,
        anyIf(ts, rn = credited) AS op_ts,
        anyIf(org, rn = credited) AS op_org,
        anyIf(project, rn = credited) AS op_project,
        anyIf(task, rn = credited) AS op_task,
        anyIf(user_name, rn = credited) AS op_user_name,
        anyIf(op, rn = credited) AS op_name,
        anyIf(method, rn = credited) AS op_method,
        anyIf(shape, rn = credited) AS op_shape,
        anyIf(objects, rn = credited) AS op_objects,
        anyIf(box_objects, rn = credited) AS op_box_objects,
        max(dt) <= 100000 AS timed,
        sum(dt) AS op_time
    FROM
    (
        SELECT
            user_id, rn, ts, dt, org, project, task, user_name, op, method, shape, objects, box_objects,
            multiIf(
                op != '', target,
                -- between the first and last adjustment of one alignment
                group_start > 0 AND rn > group_start AND rn < group_end, group_end,
                next_op_rn > 0 AND next_op_start <= ts, next_op_target,
                0) AS credited
        FROM
        (
            SELECT
                *,
                -- walking newest first: the nearest operation that ends at or after this event
                anyLastIf(rn, op != '') OVER newest_first AS next_op_rn,
                anyLastIf(start, op != '') OVER newest_first AS next_op_start,
                anyLastIf(target, op != '') OVER newest_first AS next_op_target
            FROM
            (
                SELECT
                    *,
                    -- an alignment is stored as its last adjustment
                    if(op = 'alignment', group_end, rn) AS target
                FROM
                (
                    SELECT
                        *,
                        maxIf(rn, op = 'alignment') OVER (PARTITION BY user_id, group_start) AS group_end
                    FROM
                    (
                        SELECT
                            *,
                            -- the first adjustment of the latest alignment that started at or before this event
                            anyLastIf(rn, group_starts) OVER (
                                PARTITION BY user_id ORDER BY rn ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                            ) AS group_start
                        FROM
                        (
                            SELECT
                                *,
                                op = 'alignment' AND (
                                    align_key = ''
                                    OR previous_key != align_key
                                    OR ts - previous_ts > 300000
                                ) AS group_starts
                            FROM
                            (
                                SELECT
                                    *,
                                    row_number() OVER oldest_first AS rn,
                                    -- no previous event in the read range: an unknown gap, treated as an idle pause
                                    ts - lagInFrame(ts, 1, toInt64(0)) OVER (oldest_first ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt,
                                    -- the previous event that ends an alignment (an operation or a frame change)
                                    anyLastIf(align_key, ends_alignment) OVER (
                                        oldest_first ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                                    ) AS previous_key,
                                    anyLastIf(ts, ends_alignment) OVER (
                                        oldest_first ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                                    ) AS previous_ts
                                FROM
                                (
                                    SELECT
                                        assumeNotNull(user_id) AS user_id,
                                        toUnixTimestamp64Milli(timestamp) AS ts,
                                        ifNull(org_id, 0) AS org,
                                        ifNull(project_id, 0) AS project,
                                        ifNull(task_id, 0) AS task,
                                        ifNull(user_name, '') AS user_name,
                                        ifNull(payload, '') AS body,
                                        multiIf(
                                            -- outside a job an event is only a previous action, never an operation
                                            job_id IS NULL, '',
                                            scope IN ('draw:object', 'paste:object', 'propagate:object'), 'creation',
                                            scope IN ('drag:object', 'resize:object'), 'alignment',
                                            scope = 'delete:object', 'deletion',
                                            scope = 'action:redo'
                                                AND JSONExtractString(body, 'name') = 'Created objects', 'creation',
                                            '') AS op,
                                        multiIf(
                                            scope = 'draw:object', 'drawn',
                                            scope = 'paste:object', 'pasted',
                                            scope = 'propagate:object', 'propagated',
                                            op = 'creation', 'redone',
                                            '') AS method,
                                        if(op = '', '', if(JSONHas(body, 'shape_type'), 'tagged', 'untagged')) AS shape,
                                        if(op = 'alignment', toUInt64(1), toUInt64(ifNull(count, 1))) AS objects,
                                        if(shape != 'tagged', toUInt64(0), least(objects, if(
                                            JSONHas(body, 'rectangle_count'),
                                            JSONExtractUInt(body, 'rectangle_count'),
                                            if(JSONExtractString(body, 'shape_type') = 'rectangle'
                                                AND JSONExtractString(body, 'object_type') = 'shape', objects, 0)))) AS box_objects,
                                        -- one object of one browser in one job, on one frame; '' = no reference (legacy)
                                        if(op = 'alignment' AND JSONHas(body, 'object_ref'),
                                            concat(toString(assumeNotNull(job_id)), '/', JSONExtractRaw(body, 'client_id'), '/',
                                                   JSONExtractRaw(body, 'object_ref'), '/', JSONExtractRaw(body, 'frame')),
                                            '') AS align_key,
                                        op != '' OR (scope = 'change:frame' AND job_id IS NOT NULL) AS ends_alignment,
                                        if(scope IN ('draw:object', 'paste:object', 'drag:object', 'resize:object'),
                                           ts - toInt64(duration), ts) AS start,
                                        -- a fixed order for events with the same timestamp: an operation after the rest
                                        cityHash64(scope, body, ifNull(obj_id, 0), duration, ifNull(count, 0)) AS tiebreak
                                    FROM $events_db.events
                                    WHERE timestamp >= {read_from:DateTime64(3, 'Etc/UTC')}
                                        AND timestamp < {window_to:DateTime64(3, 'Etc/UTC')} + toIntervalMillisecond(300000)
                                        AND source = 'client'
                                        AND user_id IS NOT NULL
                                )
                                WINDOW oldest_first AS (PARTITION BY user_id ORDER BY ts ASC, op != '' ASC, tiebreak ASC)
                            )
                        )
                    )
                )
            )
            WINDOW newest_first AS (PARTITION BY user_id ORDER BY rn DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
    )
    WHERE credited > 0
    GROUP BY user_id, credited
    HAVING op_ts >= toUnixTimestamp64Milli({window_from:DateTime64(3, 'Etc/UTC')})
        AND op_ts < toUnixTimestamp64Milli({window_to:DateTime64(3, 'Etc/UTC')})
)
-- a tagged operation splits into its bounding boxes and its other objects (time in proportion)
ARRAY JOIN
    if(op_shape = 'untagged', ['untagged'], ['bounding_box', 'other']) AS part_shape,
    if(op_shape = 'untagged', [toUInt64(op_objects)],
        [toUInt64(op_box_objects), toUInt64(op_objects - op_box_objects)]) AS part_objects,
    if(op_shape = 'untagged', [toInt64(op_time)], [
        toInt64(intDiv(toInt64(op_time) * toInt64(op_box_objects), greatest(toInt64(op_objects), toInt64(1)))),
        toInt64(op_time) - toInt64(intDiv(toInt64(op_time) * toInt64(op_box_objects), greatest(toInt64(op_objects), toInt64(1))))
    ]) AS part_time
-- keep the parts with objects; an operation without objects keeps one row for its time
WHERE part_objects > 0 OR (op_objects = 0 AND part_shape != 'bounding_box')
GROUP BY row_hour, op_org, op_project, op_task, user_id, op_name, op_method, part_shape
