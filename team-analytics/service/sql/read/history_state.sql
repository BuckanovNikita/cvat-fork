-- How far history is processed. `trailing_from` is where the latest ten-minute refresh began (its hours up
-- to now hold figures); `missing` is the newest day, from the first day with events up to `today` (UTC),
-- that is not processed and not wholly inside those hours. That is an earlier day that has never been
-- computed, or today while hours of it before `trailing_from` wait for the history step (only a refresh
-- window shorter than a day leaves such hours; see control/history_next_day.sql). Everything after `missing`
-- is processed, and of today the hours from `trailing_from`; with no `missing` (and a refresh made), all of
-- history is.
WITH
    (SELECT count() FROM $events_db.events) AS event_rows,
    (SELECT toDate(min(timestamp)) FROM $events_db.events) AS first_day,
    (SELECT if(count() = 0, NULL, argMax(window_from, data_as_of)) FROM $totals_db.refresh_runs) AS trailing,
    (SELECT max(computed_to) FROM $totals_db.history_today) AS today_done
SELECT
    if(event_rows > 0, first_day, NULL) AS first_event_day,
    trailing AS trailing_from,
    maxOrNull(day) AS missing
FROM system.one
ARRAY JOIN if(event_rows > 0,
              arrayMap(n -> subtractDays({today:Date}, n),
                       range(toUInt32(greatest(0, dateDiff('day', first_day, {today:Date}) + 1)))),
              []) AS day
WHERE toDateTime(day, 'Etc/UTC') < trailing
    AND if(day = {today:Date}, today_done < trailing, day NOT IN (SELECT day FROM $totals_db.history_days))
