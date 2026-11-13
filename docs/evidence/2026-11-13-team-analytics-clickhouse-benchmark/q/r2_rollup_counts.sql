-- Rollup read, Q1b equivalent: counts per user / project / scope. (param tbl unused)
WITH toDateTime('2026-11-14 00:00:00', 'Etc/UTC') AS t1, {tbl:String} AS unused
SELECT user_id, project_id, kv.1 AS scope, kv.2 AS n
FROM
(
  SELECT user_id, project_id, arrayJoin(CAST(sumMap(scope_counts), 'Array(Tuple(String, UInt64))')) AS kv
  FROM rollup_hourly FINAL
  WHERE hour >= t1 - toIntervalDay({days:UInt32}) AND hour < t1
  GROUP BY user_id, project_id
)
ORDER BY user_id, project_id, scope
