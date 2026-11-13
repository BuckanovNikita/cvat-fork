-- How far history is processed. `trailing_from` is where the latest ten-minute refresh began (its hours up
-- to now hold figures); `missing` is the newest day from the first day with events up to `last_day`
-- (yesterday, UTC) that has never been computed and is not wholly inside those hours. Everything after
-- `missing` is processed; with no `missing` (and a refresh made), all of history is.
WITH
    (SELECT count() FROM $events_db.events) AS event_rows,
    (SELECT toDate(min(timestamp)) FROM $events_db.events) AS first_day,
    (SELECT if(count() = 0, NULL, argMax(window_from, data_as_of)) FROM $totals_db.refresh_runs) AS trailing
SELECT
    if(event_rows > 0, first_day, NULL) AS first_event_day,
    trailing AS trailing_from,
    maxOrNull(day) AS missing
FROM system.one
ARRAY JOIN if(event_rows > 0,
              arrayMap(n -> subtractDays({last_day:Date}, n),
                       range(toUInt32(greatest(0, dateDiff('day', first_day, {last_day:Date}) + 1)))),
              []) AS day
WHERE day NOT IN (SELECT day FROM $totals_db.history_days)
    AND toDateTime(day, 'Etc/UTC') < trailing
