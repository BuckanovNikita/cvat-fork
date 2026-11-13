-- Rollup read, Q3 equivalent: time per operation per user / project. (param tbl unused)
WITH toDateTime('2026-11-14 00:00:00', 'Etc/UTC') AS t1, {tbl:String} AS unused
SELECT user_id, project_id,
  sum(other_ms), sum(other_n), sum(creation_ms), sum(creation_n), sum(alignment_ms), sum(alignment_n),
  sum(class_change_ms), sum(class_change_n), sum(deletion_ms), sum(deletion_n)
FROM rollup_hourly FINAL
WHERE hour >= t1 - toIntervalDay({days:UInt32}) AND hour < t1
GROUP BY user_id, project_id
ORDER BY user_id, project_id
