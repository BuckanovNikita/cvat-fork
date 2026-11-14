-- The next day of history to compute: the newest day, from the first day with events up to `today` (UTC),
-- that has no figures yet or waits for a recount. No row when there is none.
-- Today is such a day only with a refresh window shorter than a day: while hours of it lie before the
-- latest ten-minute refresh (`trailing_from`) and the history step has not computed them since they left the
-- window. `today_computed_to` is where the step got to (1970 when it has never run); it goes on from there,
-- or from today's midnight when that is later. See schema/041_history_today.sql.
WITH
    (SELECT count() FROM $events_db.events) AS event_rows,
    (SELECT toDate(min(timestamp)) FROM $events_db.events) AS first_day,
    (SELECT if(count() = 0, NULL, argMax(window_from, data_as_of)) FROM $totals_db.refresh_runs) AS trailing,
    (SELECT max(computed_to) FROM $totals_db.history_today) AS today_done
SELECT day, trailing AS trailing_from, today_done AS today_computed_to
FROM system.one
ARRAY JOIN if(event_rows > 0,
              arrayMap(n -> subtractDays({today:Date}, n),
                       range(toUInt32(greatest(0, dateDiff('day', first_day, {today:Date}) + 1)))),
              []) AS day
WHERE if(day = {today:Date},
         toDateTime(day, 'Etc/UTC') < trailing AND today_done < trailing,
         day NOT IN (
             SELECT day FROM $totals_db.history_days GROUP BY day HAVING argMax(pending, version) = 0
         ))
ORDER BY day DESC
LIMIT 1
