-- How far history is processed. `trailing_from` is where the latest ten-minute refresh began (its hours up
-- to now hold figures); `missing` is the newest day, from the first day with events up to the day before
-- `today` (UTC), that is not processed and not wholly inside those hours: an earlier day that has never been
-- computed. `waiting_from` is set while hours of today before `trailing_from` wait for the history step (only
-- a refresh window shorter than a day leaves such hours): they run from there to `trailing_from`, and today's
-- hours before `waiting_from` are computed. Everything after `missing` is processed except those waiting
-- hours; with neither (and a refresh made), all of history is.
-- Kept in step with control/history_next_day.sql, which decides the same for the worker: the four `WITH`
-- values (event_rows, first_day, trailing, today_done), the days from the first day with events up to `today`
-- (the ARRAY JOIN), and the condition that today waits (its start before `trailing` and
-- `today_done < trailing`). The SQL files cannot share a fragment, so a change to one of these
-- belongs in both, or the worker and the readers disagree about whether today is processed.
WITH
    (SELECT count() FROM $events_db.events) AS event_rows,
    (SELECT toDate(min(timestamp)) FROM $events_db.events) AS first_day,
    (SELECT if(count() = 0, NULL, argMax(window_from, data_as_of)) FROM $totals_db.refresh_runs) AS trailing,
    (SELECT max(computed_to) FROM $totals_db.history_today) AS today_done
SELECT
    if(event_rows > 0, first_day, NULL) AS first_event_day,
    trailing AS trailing_from,
    maxOrNullIf(day, day < {today:Date}) AS missing,
    if(countIf(day = {today:Date}) > 0, greatest(toDateTime({today:Date}, 'Etc/UTC'), today_done), NULL)
        AS waiting_from
FROM system.one
ARRAY JOIN if(event_rows > 0,
              arrayMap(n -> subtractDays({today:Date}, n),
                       range(toUInt32(greatest(0, dateDiff('day', first_day, {today:Date}) + 1)))),
              []) AS day
WHERE toDateTime(day, 'Etc/UTC') < trailing
    AND if(day = {today:Date}, today_done < trailing, day NOT IN (SELECT day FROM $totals_db.history_days))
