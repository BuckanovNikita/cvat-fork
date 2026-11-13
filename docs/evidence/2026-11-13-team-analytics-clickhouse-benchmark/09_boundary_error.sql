-- What happens if hour buckets are computed independently (no look-back across the hour boundary),
-- e.g. an hourly job that only reads its own hour? Last 30 days, all users.
-- "true" = lag over the user's whole stream; "naive" = lag restarted in every (user, hour).
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT
  sum(job_bound AND gap_true > 300000)  AS sessions_true,
  sum(job_bound AND gap_naive > 300000) AS sessions_naive,
  round(sumIf(gap_true, job_bound AND gap_true <= 300000) / 3600000, 1)   AS session_hours_true,
  round(sumIf(gap_naive, job_bound AND gap_naive <= 300000) / 3600000, 1) AS session_hours_naive,
  round(sumIf(dt_true, dt_true <= 100000) / 3600000, 1)   AS op_hours_true,
  round(sumIf(dt_naive, dt_naive <= 100000) / 3600000, 1) AS op_hours_naive
FROM
(
  SELECT job_bound,
    ts - lagInFrame(ts, 1, 0) OVER (w ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt_true,
    ts - lagInFrame(ts, 1, 0) OVER (wh ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS dt_naive,
    ts - anyLastIf(ts, job_bound) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS gap_true,
    ts - anyLastIf(ts, job_bound) OVER (wh ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS gap_naive
  FROM
  (
    SELECT user_id, toUnixTimestamp64Milli(timestamp) AS ts, toStartOfHour(timestamp) AS hour, job_id IS NOT NULL AS job_bound
    FROM events
    WHERE source = 'client' AND timestamp >= t1 - toIntervalDay(30) AND timestamp < t1
  )
  WINDOW w AS (PARTITION BY user_id ORDER BY ts), wh AS (PARTITION BY user_id, hour ORDER BY ts)
)
FORMAT Vertical;
