-- Operations and time per operation, from the annotator's job-bound client events.
--
-- Operations (events the stock UI already writes):
--   creation:  draw:object (drawn), paste:object (pasted), propagate:object (propagated), and
--              action:redo of 'Created objects' (redone: a person redid a creation they had undone).
--              Objects = the event's count (1 when empty)
--   alignment: drag:object, resize:object; each event is one alignment
--   deletion:  delete:object; objects = the event's count. action:undo is no operation, so an undone
--              creation is not a deletion.
-- Time per operation: from the person's previous client event to the event that ends the
-- operation. A gap over the idle pause (100 s), or no known previous event, leaves the operation
-- untimed: its objects count, but it adds neither time nor timed objects. Draw, canvas paste, drag and
-- resize are logged when they end and cover [timestamp - duration, timestamp]; other events lying
-- inside that interval (zooming, moving between frames) give their gap to that operation, and the
-- operation is untimed if any of those gaps is an idle pause.
-- Events are read from `read_from` (look-back before the window) so gaps at the window's start are
-- exact; only operations ending inside [window_from, window_to) are stored, in the hour, organization,
-- project and task of the event that ends them. Rows without a user are dropped.
INSERT INTO $totals_db.operations_hourly
    (hour, org_id, project_id, task_id, user_id, user_name, operation, method, shape,
     objects, timed_objects, time_ms, hotkey_objects, mouse_objects, version)
SELECT
    toStartOfHour(fromUnixTimestamp64Milli(op_ts, 'Etc/UTC')) AS row_hour,
    op_org, op_project, op_task, user_id,
    argMax(op_user_name, op_ts),
    op_name, op_method, op_shape,
    sum(op_objects),
    sumIf(op_objects, timed),
    sumIf(op_time, timed),
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
        max(dt) <= 100000 AS timed,
        sum(dt) AS op_time
    FROM
    (
        SELECT
            user_id, rn, ts, dt, org, project, task, user_name, op, method, shape, objects,
            if(op != '', rn, if(next_op_rn > 0 AND next_op_start <= ts, next_op_rn, 0)) AS credited
        FROM
        (
            SELECT
                *,
                -- walking newest first: the nearest operation that ends at or after this event
                anyLastIf(rn, op != '') OVER newest_first AS next_op_rn,
                anyLastIf(start, op != '') OVER newest_first AS next_op_start
            FROM
            (
                SELECT
                    *,
                    row_number() OVER oldest_first AS rn,
                    -- no previous event in the read range: an unknown gap, treated as an idle pause
                    ts - lagInFrame(ts, 1, toInt64(0)) OVER (oldest_first ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt
                FROM
                (
                    SELECT
                        assumeNotNull(user_id) AS user_id,
                        toUnixTimestamp64Milli(timestamp) AS ts,
                        ifNull(org_id, 0) AS org,
                        ifNull(project_id, 0) AS project,
                        ifNull(task_id, 0) AS task,
                        ifNull(user_name, '') AS user_name,
                        multiIf(
                            scope IN ('draw:object', 'paste:object', 'propagate:object'), 'creation',
                            scope IN ('drag:object', 'resize:object'), 'alignment',
                            scope = 'delete:object', 'deletion',
                            scope = 'action:redo'
                                AND JSONExtractString(ifNull(payload, ''), 'name') = 'Created objects', 'creation',
                            '') AS op,
                        multiIf(
                            scope = 'draw:object', 'drawn',
                            scope = 'paste:object', 'pasted',
                            scope = 'propagate:object', 'propagated',
                            op = 'creation', 'redone',
                            '') AS method,
                        if(op = '', '', multiIf(
                            NOT JSONHas(ifNull(payload, ''), 'shape_type'), 'untagged',
                            JSONExtractString(ifNull(payload, ''), 'shape_type') = 'rectangle'
                                AND JSONExtractString(ifNull(payload, ''), 'object_type') = 'shape', 'bounding_box',
                            'other')) AS shape,
                        if(op = 'alignment', toUInt64(1), toUInt64(ifNull(count, 1))) AS objects,
                        if(scope IN ('draw:object', 'paste:object', 'drag:object', 'resize:object'),
                           ts - toInt64(duration), ts) AS start,
                        -- a fixed order for events with the same timestamp: an operation after the rest
                        cityHash64(scope, ifNull(payload, ''), ifNull(obj_id, 0), duration, ifNull(count, 0)) AS tiebreak
                    FROM $events_db.events
                    WHERE timestamp >= {read_from:DateTime64(3, 'Etc/UTC')}
                        AND timestamp < {window_to:DateTime64(3, 'Etc/UTC')}
                        AND source = 'client'
                        AND job_id IS NOT NULL
                        AND user_id IS NOT NULL
                )
                WINDOW oldest_first AS (PARTITION BY user_id ORDER BY ts ASC, op != '' ASC, tiebreak ASC)
            )
            WINDOW newest_first AS (PARTITION BY user_id ORDER BY rn DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
    )
    WHERE credited > 0
    GROUP BY user_id, credited
    HAVING op_ts >= toUnixTimestamp64Milli({window_from:DateTime64(3, 'Etc/UTC')})
)
GROUP BY row_hour, op_org, op_project, op_task, user_id, op_name, op_method, op_shape
