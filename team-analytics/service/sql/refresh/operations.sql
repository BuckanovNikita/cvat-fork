-- Operations and time per operation, from the annotator's client events. Only job-bound events are
-- operations; every client event (inside a job or not) is a previous action that a gap is measured from.
--
-- Operations (events the stock UI already writes):
--   creation:  draw:object (drawn), paste:object (pasted), propagate:object (propagated).
--              Objects = the event's count (1 when empty). An action:redo is no operation: redoing a
--              creation is not a second one, so it has no method, and the gap before it is no
--              operation's time (it stays in Other).
--   alignment: drag:object, resize:object. Consecutive drags and resizes of the same object (same job,
--              browser `client_id`, `object_ref` and `frame`) by the same person are one alignment. Any
--              other operation, a change:frame, an action:redo of 'Created objects', or a pause longer
--              than the session gap (300 s, also the look-back) between two of them ends it. Events
--              without `object_ref` (legacy) are one alignment each.
--              A group move (payload `group` = 'move': selected objects dragged together, or the
--              selection box moved) is one alignment per object moved: objects = the event's count, and
--              the gesture's time is shared between them like any operation's. It ends the runs before
--              it and is continued by none. CVAT's own drag of the grabbed object of that gesture
--              (`group` = 'grabbed') is no operation: only a previous action, like a zoom.
--   class_change: the UI's debug:info record named 'team_analytics:class_change'; objects = the
--              record's count (only objects whose label changed; a change back is another record).
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
-- Input method: hotkey_objects / mouse_objects count the objects of operations whose payload
-- `input_method` is 'hotkey' / 'mouse'; operations without it (legacy) are in neither.
-- The UI's input summary records (team_analytics:input_summary) are no action: they are written at the
-- moment of one, so they are left out of the stream and never take an operation's gap.
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
    sumIf(part_objects, op_input = 'hotkey'),
    sumIf(part_objects, op_input = 'mouse'),
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
        anyIf(input, rn = credited) AS op_input,
        max(dt) <= 100000 AS timed,
        sum(dt) AS op_time
    FROM
    (
        SELECT
            user_id, rn, ts, dt, org, project, task, user_name, op, method, shape, objects, box_objects, input,
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
                                    -- the previous event that ends an alignment (see `ends_alignment`)
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
                                            -- the grabbed object's drag of a group move: counted in the group event
                                            scope = 'drag:object' AND JSONExtractString(body, 'group') = 'grabbed', '',
                                            scope IN ('draw:object', 'paste:object', 'propagate:object'), 'creation',
                                            scope IN ('drag:object', 'resize:object'), 'alignment',
                                            scope = 'delete:object', 'deletion',
                                            scope = 'debug:info'
                                                AND obj_name = 'team_analytics:class_change', 'class_change',
                                            '') AS op,
                                        multiIf(
                                            scope = 'draw:object', 'drawn',
                                            scope = 'paste:object', 'pasted',
                                            scope = 'propagate:object', 'propagated',
                                            '') AS method,
                                        if(op = '', '', if(JSONHas(body, 'shape_type'), 'tagged', 'untagged')) AS shape,
                                        -- a group move counts the objects moved; any other drag or resize one object
                                        JSONExtractString(body, 'group') = 'move' AS group_move,
                                        if(op = 'alignment' AND NOT group_move, toUInt64(1), toUInt64(ifNull(count, 1))) AS objects,
                                        if(shape != 'tagged', toUInt64(0), least(objects, if(
                                            JSONHas(body, 'rectangle_count'),
                                            JSONExtractUInt(body, 'rectangle_count'),
                                            if(JSONExtractString(body, 'shape_type') = 'rectangle'
                                                AND JSONExtractString(body, 'object_type') = 'shape', objects, 0)))) AS box_objects,
                                        -- one object of one browser in one job, on one frame; '' = no reference (legacy,
                                        -- or a group move): an alignment of its own
                                        if(op = 'alignment' AND NOT group_move AND JSONHas(body, 'object_ref'),
                                            concat(toString(assumeNotNull(job_id)), '/', JSONExtractRaw(body, 'client_id'), '/',
                                                   JSONExtractRaw(body, 'object_ref'), '/', JSONExtractRaw(body, 'frame')),
                                            '') AS align_key,
                                        -- what started the operation: 'hotkey' | 'mouse' | '' (not recorded)
                                        if(op = '', '', JSONExtractString(body, 'input_method')) AS input,
                                        -- an operation, a frame change, or a redo of created objects (no operation itself)
                                        op != '' OR (job_id IS NOT NULL AND (
                                            scope = 'change:frame'
                                            OR (scope = 'action:redo'
                                                AND JSONExtractString(body, 'name') = 'Created objects'))) AS ends_alignment,
                                        if(scope IN ('draw:object', 'paste:object', 'drag:object', 'resize:object'),
                                           ts - toInt64(duration), ts) AS start,
                                        -- a fixed order for events with the same timestamp: an operation after the rest
                                        cityHash64(scope, body, ifNull(obj_id, 0), duration, ifNull(count, 0)) AS tiebreak
                                    FROM $events_db.events
                                    WHERE timestamp >= {read_from:DateTime64(3, 'Etc/UTC')}
                                        AND timestamp < {window_to:DateTime64(3, 'Etc/UTC')} + toIntervalMillisecond(300000)
                                        AND source = 'client'
                                        AND user_id IS NOT NULL
                                        -- the input summary is written at the moment of an action, not as one
                                        AND NOT (scope = 'debug:info'
                                            AND ifNull(obj_name, '') = 'team_analytics:input_summary')
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
