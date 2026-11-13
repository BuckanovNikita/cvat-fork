-- The next day of history to compute: the newest day, from the first day with events up to `last_day`
-- (yesterday, UTC), that has no figures yet or waits for a recount. No row when there is none.
WITH
    (SELECT count() FROM $events_db.events) AS event_rows,
    (SELECT toDate(min(timestamp)) FROM $events_db.events) AS first_day
SELECT day
FROM system.one
ARRAY JOIN if(event_rows > 0,
              arrayMap(n -> subtractDays({last_day:Date}, n),
                       range(toUInt32(greatest(0, dateDiff('day', first_day, {last_day:Date}) + 1)))),
              []) AS day
WHERE day NOT IN (
    SELECT day FROM $totals_db.history_days GROUP BY day HAVING argMax(pending, version) = 0
)
ORDER BY day DESC
LIMIT 1
