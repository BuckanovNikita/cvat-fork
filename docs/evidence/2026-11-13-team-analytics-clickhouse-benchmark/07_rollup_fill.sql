-- Q7: fill / refresh the rollup for hours in [from, to). `from` must be hour-aligned.
-- Params: from, to (String, 'YYYY-MM-DD hh:mm:ss' UTC), lookback_s (UInt32).
-- The window part reads lookback_s seconds before `from` so that the first event of every user in
-- the range sees its true predecessor; rows of the look-back zone are dropped after the window.
-- lookback_s = 300 is enough for exact results: a predecessor further back than 5 minutes starts a
-- new session anyway, and one further back than 100 s contributes no operation time anyway.
INSERT INTO rollup_hourly
  (org_id, project_id, task_id, user_id, hour, working_ms, events, scope_counts, session_starts, session_ms,
   other_ms, other_n, creation_ms, creation_n, alignment_ms, alignment_n,
   class_change_ms, class_change_n, deletion_ms, deletion_n)
WITH
  toDateTime64({from:String}, 3, 'Etc/UTC') AS t0,
  toDateTime64({to:String}, 3, 'Etc/UTC') AS t1,
  toUnixTimestamp64Milli(t0) AS t0_ms
SELECT org_id, project_id, task_id, user_id, hour,
  sum(working_ms), sum(events), sumMap(scope_counts), sum(session_starts), sum(session_ms),
  sum(other_ms), sum(other_n), sum(creation_ms), sum(creation_n), sum(alignment_ms), sum(alignment_n),
  sum(class_change_ms), sum(class_change_n), sum(deletion_ms), sum(deletion_n)
FROM
(
  -- part 1: plain aggregates over all rows (Q1)
  SELECT org_id, project_id, task_id, user_id, hour,
    sum(w) AS working_ms, sum(c) AS events,
    CAST((groupArray(scope), groupArray(c)), 'Map(LowCardinality(String), UInt64)') AS scope_counts,
    toUInt64(0) AS session_starts, toUInt64(0) AS session_ms,
    toUInt64(0) AS other_ms, toUInt64(0) AS other_n, toUInt64(0) AS creation_ms, toUInt64(0) AS creation_n,
    toUInt64(0) AS alignment_ms, toUInt64(0) AS alignment_n, toUInt64(0) AS class_change_ms,
    toUInt64(0) AS class_change_n, toUInt64(0) AS deletion_ms, toUInt64(0) AS deletion_n
  FROM
  (
    SELECT ifNull(org_id, 0) AS org_id, ifNull(project_id, 0) AS project_id, ifNull(task_id, 0) AS task_id,
      ifNull(user_id, 0) AS user_id, toStartOfHour(timestamp) AS hour, scope,
      count() AS c, sumIf(duration, scope = 'send:working_time') AS w
    FROM events
    WHERE timestamp >= t0 AND timestamp < t1
    GROUP BY org_id, project_id, task_id, user_id, hour, scope
  )
  GROUP BY org_id, project_id, task_id, user_id, hour

  UNION ALL

  -- part 2: window pass over client events (Q2, Q3)
  SELECT org_id, project_id, task_id, user_id, toStartOfHour(fromUnixTimestamp64Milli(ts, 'Etc/UTC')) AS hour,
    toUInt64(0) AS working_ms, toUInt64(0) AS events,
    CAST(map(), 'Map(LowCardinality(String), UInt64)') AS scope_counts,
    countIf(job_bound AND gap_j > 300000) AS session_starts,
    toUInt64(sumIf(gap_j, job_bound AND gap_j <= 300000)) AS session_ms,
    toUInt64(sumIf(dt, keep AND op = 0)) AS other_ms,        countIf(keep AND op = 0) AS other_n,
    toUInt64(sumIf(dt, keep AND op = 1)) AS creation_ms,     countIf(keep AND op = 1) AS creation_n,
    toUInt64(sumIf(dt, keep AND op = 2)) AS alignment_ms,    countIf(keep AND op = 2) AS alignment_n,
    toUInt64(sumIf(dt, keep AND op = 3)) AS class_change_ms, countIf(keep AND op = 3) AS class_change_n,
    toUInt64(sumIf(dt, keep AND op = 4)) AS deletion_ms,     countIf(keep AND op = 4) AS deletion_n
  FROM
  (
    SELECT org_id, project_id, task_id, user_id, ts, op, job_bound,
      ts - lagInFrame(ts, 1, 0) OVER (w ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt,
      ts - anyLastIf(ts, job_bound) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS gap_j,
      dt <= 100000 AND (op = 0 OR is_rect) AS keep
    FROM
    (
      SELECT ifNull(org_id, 0) AS org_id, ifNull(project_id, 0) AS project_id, ifNull(task_id, 0) AS task_id,
        ifNull(user_id, 0) AS user_id,
        toUnixTimestamp64Milli(timestamp) AS ts,
        job_id IS NOT NULL AS job_bound,
        toUInt8(multiIf(scope = 'draw:object', 1,
                        scope IN ('drag:object', 'resize:object'), 2,
                        scope = 'debug:info' AND obj_name = 'change:label', 3,
                        scope = 'delete:object', 4, 0)) AS op,
        ifNull(op != 0 AND JSONExtractString(payload, 'shape_type') = 'rectangle', 0) AS is_rect
      FROM events
      WHERE source = 'client'
        AND timestamp >= t0 - toIntervalSecond({lookback_s:UInt32}) AND timestamp < t1
    )
    WINDOW w AS (PARTITION BY user_id ORDER BY ts)
  )
  WHERE ts >= t0_ms
  GROUP BY org_id, project_id, task_id, user_id, hour
)
GROUP BY org_id, project_id, task_id, user_id, hour
SETTINGS query_plan_execute_functions_after_sorting = 0;
