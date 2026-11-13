-- Q1b: event counts per user / project / scope.
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, project_id, scope, count() AS n
FROM {tbl:Identifier}
WHERE timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
GROUP BY user_id, project_id, scope
ORDER BY user_id, project_id, scope
