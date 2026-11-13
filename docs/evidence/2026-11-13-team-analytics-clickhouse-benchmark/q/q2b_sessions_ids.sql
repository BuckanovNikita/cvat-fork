-- Q2b: same result as Q2a, but with explicit session ids (running sum of session starts),
-- so that per-session rows exist (needed if the page lists sessions or needs median/max length).
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, count() AS sessions, sum(len_ms) AS session_ms, max(len_ms) AS longest_ms, sum(events) AS events
FROM
(
  SELECT user_id, sess, max(ts) - min(ts) AS len_ms, count() AS events
  FROM
  (
    SELECT user_id, ts,
      sum(is_start) OVER (PARTITION BY user_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS sess
    FROM
    (
      SELECT user_id,
        toUnixTimestamp64Milli(timestamp) AS ts,
        (ts - lagInFrame(ts, 1, 0) OVER (PARTITION BY user_id ORDER BY ts ROWS BETWEEN 1 PRECEDING AND CURRENT ROW)) > 300000 AS is_start
      FROM {tbl:Identifier}
      WHERE source = 'client' AND job_id IS NOT NULL
        AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
    )
  )
  GROUP BY user_id, sess
)
GROUP BY user_id
ORDER BY user_id
