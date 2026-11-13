-- Q4: "action interval" rule.
-- draw/drag/resize are logged when the action ENDS; the action covers [ts - duration, ts].
-- Any event of the same user whose timestamp falls inside the interval of a LATER rectangle draw
-- (or drag/resize) gives its delta to that action's operation instead of its own.
--
-- How: walk each user's events newest-first and keep a running minimum of the start times of the
-- actions seen so far (= all later actions, plus the row itself, which is harmless: an action
-- always "covers" itself and maps to its own operation). An event is covered by some later draw
-- iff that minimum <= its own timestamp. One running minimum per operation class.
-- This is exact for "covered by at least one later draw" / "... one later drag/resize".
-- When an event is covered by BOTH a draw and a drag/resize, the draw wins (fixed priority);
-- "the nearest covering action wins" is NOT expressed here.
-- A plain suffix frame (1 FOLLOWING .. UNBOUNDED FOLLOWING) in ascending order gives the same
-- answer but recomputes the frame for every row (quadratic), hence the descending order.
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, project_id, ['other', 'creation', 'alignment', 'class_change', 'deletion'][op_final + 1] AS operation,
       sum(dt) AS ms, count() AS n
FROM
(
  SELECT user_id, project_id, op, is_rect, dt,
    next_draw_start <= ts AS in_draw,
    next_align_start <= ts AS in_align,
    multiIf(in_draw, 1, in_align, 2, op) AS op_final
  FROM
  (
    SELECT user_id, project_id, ts, op, is_rect,
      ts - leadInFrame(ts, 1, 0) OVER (w ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING) AS dt,
      min(if(op = 1 AND is_rect, ts - duration, 9000000000000000000))
        OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS next_draw_start,
      min(if(op = 2 AND is_rect, ts - duration, 9000000000000000000))
        OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS next_align_start
    FROM
    (
      SELECT user_id, project_id, toInt64(duration) AS duration,
        toUnixTimestamp64Milli(timestamp) AS ts,
        toUInt8(multiIf(scope = 'draw:object', 1,
                        scope IN ('drag:object', 'resize:object'), 2,
                        scope = 'debug:info' AND obj_name = 'change:label', 3,
                        scope = 'delete:object', 4, 0)) AS op,
        ifNull(op != 0 AND JSONExtractString(payload, 'shape_type') = 'rectangle', 0) AS is_rect
      FROM {tbl:Identifier}
      WHERE source = 'client'
        AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
    )
    WINDOW w AS (PARTITION BY user_id ORDER BY ts DESC)
  )
)
WHERE dt <= 100000 AND (in_draw OR in_align OR op = 0 OR is_rect)
GROUP BY user_id, project_id, op_final
ORDER BY user_id, project_id, op_final
