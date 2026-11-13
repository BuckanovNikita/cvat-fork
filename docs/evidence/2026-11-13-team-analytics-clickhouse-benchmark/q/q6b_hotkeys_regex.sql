-- Q6b: hotkey counters per user and key name; dynamic keys via a regular expression.
-- Depends on the exact text layout of the payload ("key.NAME": n with an optional space).
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, kv[1] AS key, sum(toUInt64(kv[2])) AS presses
FROM
(
  SELECT user_id,
    arrayJoin(extractAllGroupsVertical(assumeNotNull(payload), '"key\\.([^"]+)": ?(\\d+)')) AS kv
  FROM {tbl:Identifier}
  WHERE source = 'client' AND scope = 'debug:info' AND obj_name = 'input:stats'
    AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
)
GROUP BY user_id, key
ORDER BY user_id, key
