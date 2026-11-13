-- Q2a: sessions per user (count and total length), lag only.
-- A session starts when the gap to the user's previous job-bound client event exceeds 5 minutes.
-- Total session length = sum of the gaps that do not start a session (= sum over sessions of last - first).
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, sum(is_start) AS sessions, sum(if(is_start, 0, gap_ms)) AS session_ms
FROM
(
  SELECT user_id, gap_ms, gap_ms > 300000 AS is_start
  FROM
  (
    SELECT user_id,
      toUnixTimestamp64Milli(timestamp) AS ts,
      ts - lagInFrame(ts, 1, 0) OVER (PARTITION BY user_id ORDER BY ts ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS gap_ms
    FROM {tbl:Identifier}
    WHERE source = 'client' AND job_id IS NOT NULL
      AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
  )
)
GROUP BY user_id
ORDER BY user_id
