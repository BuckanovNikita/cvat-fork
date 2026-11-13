-- Q5: "one alignment per object".
-- Rule as implemented (per user, client events in time order):
--   * drag/resize with obj_id = X: continues the current alignment iff the user's previous
--     drag/resize event (whatever lies between) also has obj_id = X;
--   * drag/resize with obj_id NULL: continues iff the user's previous OPERATION event
--     (creation / alignment / class change / deletion; "other" events such as zoom are ignored)
--     is a drag/resize with obj_id NULL;
--   * otherwise it starts a new alignment.
-- No rectangle filter here (adding it costs what Q3 shows for payload extraction).
-- obj code: 0 = no previous event, 1 = obj_id is NULL, obj_id + 2 otherwise
-- (aggregate functions skip NULLs, so NULL has to be encoded before anyLast).
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, project_id,
       sum(is_new) AS alignments, count() AS alignment_events,
       sumIf(dt, dt <= 100000) AS alignment_ms
FROM
(
  SELECT user_id, project_id, op, obj, dt,
    NOT if(obj = 1, prev_op = 2 AND prev_align_obj = 1, prev_align_obj = obj) AS is_new
  FROM
  (
    SELECT user_id, project_id, op, obj,
      ts - lagInFrame(ts, 1, 0) OVER (w ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt,
      anyLastIf(obj, op = 2) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_align_obj,
      anyLastIf(op, op != 0) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_op
    FROM
    (
      SELECT user_id, project_id,
        toUnixTimestamp64Milli(timestamp) AS ts,
        toUInt8(multiIf(scope = 'draw:object', 1,
                        scope IN ('drag:object', 'resize:object'), 2,
                        scope = 'debug:info' AND obj_name = 'change:label', 3,
                        scope = 'delete:object', 4, 0)) AS op,
        if(obj_id IS NULL, toUInt64(1), assumeNotNull(obj_id) + 2) AS obj
      FROM {tbl:Identifier}
      WHERE source = 'client'
        AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
    )
    WINDOW w AS (PARTITION BY user_id ORDER BY ts)
  )
  WHERE op = 2
)
GROUP BY user_id, project_id
ORDER BY user_id, project_id
