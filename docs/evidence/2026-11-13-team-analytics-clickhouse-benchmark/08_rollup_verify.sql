-- Diff the rollup (after year fill + 48 h refresh, read with FINAL) against the direct queries
-- over the same 365 days. Each statement prints compared groups and mismatching groups.

-- Q1a: working time per user per day
SELECT 'q1a working time' AS check, count() AS groups, countIf(d.v != r.v) AS mismatches, sum(d.v) AS direct_total, sum(r.v) AS rollup_total
FROM
(
  SELECT ifNull(user_id, 0) AS user_id, toDate(timestamp) AS day, sum(duration) AS v
  FROM events WHERE scope = 'send:working_time' GROUP BY user_id, day
) AS d
FULL OUTER JOIN
(
  SELECT user_id, toDate(hour) AS day, sum(working_ms) AS v
  FROM rollup_hourly FINAL GROUP BY user_id, day HAVING v > 0
) AS r USING (user_id, day);

-- Q1b: counts per user / project / scope
SELECT 'q1b counts' AS check, count() AS groups, countIf(d.v != r.v) AS mismatches, sum(d.v) AS direct_total, sum(r.v) AS rollup_total
FROM
(
  SELECT ifNull(user_id, 0) AS user_id, ifNull(project_id, 0) AS project_id, scope, count() AS v
  FROM events GROUP BY user_id, project_id, scope
) AS d
FULL OUTER JOIN
(
  SELECT user_id, project_id, kv.1 AS scope, kv.2 AS v
  FROM (SELECT user_id, project_id, arrayJoin(CAST(sumMap(scope_counts), 'Array(Tuple(String, UInt64))')) AS kv
        FROM rollup_hourly FINAL GROUP BY user_id, project_id)
) AS r USING (user_id, project_id, scope);

-- Q2: sessions per user
SELECT 'q2 sessions' AS check, count() AS groups,
  countIf(d.sessions != r.sessions OR d.session_ms != r.session_ms) AS mismatches,
  sum(d.sessions) AS direct_total, sum(r.sessions) AS rollup_total,
  sum(d.session_ms) AS direct_ms, sum(r.session_ms) AS rollup_ms
FROM
(
  SELECT user_id, sum(gap_ms > 300000) AS sessions, sum(if(gap_ms > 300000, 0, gap_ms)) AS session_ms
  FROM
  (
    SELECT ifNull(user_id, 0) AS user_id, toUnixTimestamp64Milli(timestamp) AS ts,
      ts - lagInFrame(ts, 1, 0) OVER (PARTITION BY user_id ORDER BY ts ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS gap_ms
    FROM events WHERE source = 'client' AND job_id IS NOT NULL
  )
  GROUP BY user_id
) AS d
FULL OUTER JOIN
(
  SELECT user_id, sum(session_starts) AS sessions, sum(session_ms) AS session_ms
  FROM rollup_hourly FINAL GROUP BY user_id
) AS r USING (user_id);

-- Q3: time per operation per user / project (JSON rectangle filter)
SELECT 'q3 operations' AS check, count() AS groups,
  countIf(d.ms != r.ms OR d.n != r.n) AS mismatches,
  sum(d.ms) AS direct_ms, sum(r.ms) AS rollup_ms, sum(d.n) AS direct_n, sum(r.n) AS rollup_n
FROM
(
  SELECT user_id, project_id, op, toUInt64(sum(dt)) AS ms, count() AS n
  FROM
  (
    SELECT ifNull(user_id, 0) AS user_id, ifNull(project_id, 0) AS project_id,
      toUnixTimestamp64Milli(timestamp) AS ts,
      toUInt8(multiIf(scope = 'draw:object', 1, scope IN ('drag:object', 'resize:object'), 2,
                      scope = 'debug:info' AND obj_name = 'change:label', 3, scope = 'delete:object', 4, 0)) AS op,
      ifNull(JSONExtractString(payload, 'shape_type') = 'rectangle', 0) AS is_rect,
      ts - lagInFrame(ts, 1, 0) OVER (PARTITION BY user_id ORDER BY ts ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt
    FROM events WHERE source = 'client'
  )
  WHERE dt <= 100000 AND (op = 0 OR is_rect)
  GROUP BY user_id, project_id, op
) AS d
FULL OUTER JOIN
(
  SELECT user_id, project_id, t.1 AS op, t.2 AS ms, t.3 AS n
  FROM
  (
    SELECT user_id, project_id,
      arrayJoin([(toUInt8(0), sum(other_ms), sum(other_n)), (1, sum(creation_ms), sum(creation_n)),
                 (2, sum(alignment_ms), sum(alignment_n)), (3, sum(class_change_ms), sum(class_change_n)),
                 (4, sum(deletion_ms), sum(deletion_n))]) AS t
    FROM rollup_hourly FINAL GROUP BY user_id, project_id
  )
  WHERE t.3 > 0
) AS r USING (user_id, project_id, op)
SETTINGS query_plan_execute_functions_after_sorting = 0;
