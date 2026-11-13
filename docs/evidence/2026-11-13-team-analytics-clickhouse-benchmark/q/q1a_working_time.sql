-- Q1a: working time per user per day.
-- Params: tbl (Identifier), days (UInt32). Range = [end - days, end), end fixed at 2026-11-14 00:00 UTC.
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, toDate(timestamp) AS day, sum(duration) AS working_ms
FROM {tbl:Identifier}
WHERE scope = 'send:working_time'
  AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
GROUP BY user_id, day
ORDER BY user_id, day
