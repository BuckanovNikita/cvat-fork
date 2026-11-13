-- Cross-check of the Q4 window formulation against a brute-force self-join
-- (one day, users 1..20). Both sides compute, per event, "covered by a later-or-same rectangle draw"
-- and "covered by a later-or-same rectangle drag/resize". Expect mismatches = 0.
WITH
base AS
(
  SELECT user_id, toUnixTimestamp64Milli(timestamp) AS ts, toInt64(duration) AS duration,
    toUInt8(multiIf(scope = 'draw:object', 1, scope IN ('drag:object', 'resize:object'), 2,
                    scope = 'debug:info' AND obj_name = 'change:label', 3, scope = 'delete:object', 4, 0)) AS op,
    ifNull(op != 0 AND JSONExtractString(payload, 'shape_type') = 'rectangle', 0) AS is_rect
  FROM events
  WHERE source = 'client' AND user_id <= 20
    AND timestamp >= '2026-11-12 00:00:00' AND timestamp < '2026-11-13 00:00:00'
),
win AS
(
  SELECT user_id, ts,
    min(if(op = 1 AND is_rect, ts - duration, 9000000000000000000))
      OVER (PARTITION BY user_id ORDER BY ts DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) <= ts AS in_draw,
    min(if(op = 2 AND is_rect, ts - duration, 9000000000000000000))
      OVER (PARTITION BY user_id ORDER BY ts DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) <= ts AS in_align
  FROM base
),
brute AS
(
  SELECT e.user_id AS user_id, e.ts AS ts,
    max(a.op = 1 AND a.ts >= e.ts AND a.ts - a.duration <= e.ts) AS in_draw,
    max(a.op = 2 AND a.ts >= e.ts AND a.ts - a.duration <= e.ts) AS in_align
  FROM base AS e
  INNER JOIN (SELECT * FROM base WHERE op IN (1, 2) AND is_rect) AS a ON e.user_id = a.user_id
  GROUP BY user_id, ts
)
SELECT
  count() AS events_compared,
  countIf(w.in_draw != b.in_draw OR w.in_align != b.in_align) AS mismatches,
  sum(w.in_draw) AS covered_by_draw,
  sum(w.in_align) AS covered_by_align,
  sum(w.in_draw AND w.in_align) AS covered_by_both
FROM win AS w
INNER JOIN brute AS b ON w.user_id = b.user_id AND w.ts = b.ts
FORMAT Vertical;
