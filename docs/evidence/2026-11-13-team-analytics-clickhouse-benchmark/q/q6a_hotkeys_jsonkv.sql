-- Q6a: hotkey counters per user and key name; dynamic keys via JSONExtractKeysAndValues + arrayJoin.
WITH toDateTime64('2026-11-14 00:00:00', 3, 'Etc/UTC') AS t1
SELECT user_id, substring(kv.1, 5) AS key, sum(kv.2) AS presses
FROM
(
  SELECT user_id,
    arrayJoin(arrayFilter(x -> startsWith(x.1, 'key.'),
                          JSONExtractKeysAndValues(assumeNotNull(payload), 'Int64'))) AS kv
  FROM {tbl:Identifier}
  WHERE source = 'client' AND scope = 'debug:info' AND obj_name = 'input:stats'
    AND timestamp >= t1 - toIntervalDay({days:UInt32}) AND timestamp < t1
)
GROUP BY user_id, key
ORDER BY user_id, key
