-- Rollup read, Q2 equivalent: sessions per user. (param tbl unused)
WITH toDateTime('2026-11-14 00:00:00', 'Etc/UTC') AS t1, {tbl:String} AS unused
SELECT user_id, sum(session_starts) AS sessions, sum(session_ms) AS session_ms
FROM rollup_hourly FINAL
WHERE hour >= t1 - toIntervalDay({days:UInt32}) AND hour < t1
GROUP BY user_id
ORDER BY user_id
