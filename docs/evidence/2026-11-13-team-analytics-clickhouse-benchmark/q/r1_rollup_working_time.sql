-- Rollup read, Q1a equivalent: working time per user per day. (param tbl unused)
WITH toDateTime('2026-11-14 00:00:00', 'Etc/UTC') AS t1, {tbl:String} AS unused
SELECT user_id, toDate(hour) AS day, sum(working_ms) AS working_ms
FROM rollup_hourly FINAL
WHERE hour >= t1 - toIntervalDay({days:UInt32}) AND hour < t1
GROUP BY user_id, day
HAVING working_ms > 0
ORDER BY user_id, day
