-- Q3: time per operation. Variant: q3f_like_ops_only
-- For each user's ordered client events: dt = time since that user's previous client event,
-- dropped if over 100 s, attributed to the current event's operation.
-- The four named operations are kept only when the payload says shape_type = rectangle.
-- The delta is computed over ALL of the user's client events first; filtering happens outside.
-- op codes: 0 other, 1 creation, 2 alignment, 3 class_change, 4 deletion
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, project_id, ['other', 'creation', 'alignment', 'class_change', 'deletion'][op + 1] AS operation,
       sum(dt) AS ms, count() AS n
FROM
(
  SELECT user_id, project_id,
    toUnixTimestamp64Milli(timestamp) AS ts,
    toUInt8(multiIf(scope = 'draw:object', 1,
                    scope IN ('drag:object', 'resize:object'), 2,
                    scope = 'debug:info' AND obj_name = 'change:label', 3,
                    scope = 'delete:object', 4, 0)) AS op,
    ifNull(op != 0 AND payload LIKE '%"shape_type": "rectangle"%', 0) AS is_rect,
    ts - lagInFrame(ts, 1, 0) OVER (PARTITION BY user_id ORDER BY ts ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt
  FROM {tbl:Identifier}
  WHERE source = 'client'
    AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
)
WHERE dt <= 100000 AND (op = 0 OR is_rect)
GROUP BY user_id, project_id, op
ORDER BY user_id, project_id, op
