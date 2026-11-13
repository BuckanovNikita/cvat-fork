-- The daily check: processed days (before `before`, today's midnight UTC) whose raw event rows no longer
-- match the count stored when they were computed, together with the processed days on either side of each
-- (a session or an operation that crosses midnight is stored in the day it ends). Days already waiting are
-- left out.
WITH
    stored AS (
        SELECT day, argMax(raw_rows, version) AS raw_rows, argMax(pending, version) AS pending
        FROM $totals_db.history_days
        GROUP BY day
    ),
    counted AS (
        SELECT toDate(timestamp) AS day, count() AS raw_rows
        FROM $events_db.events
        WHERE timestamp < {before:DateTime64(3, 'Etc/UTC')}
        GROUP BY day
    ),
    changed AS (
        SELECT stored.day AS day
        FROM stored LEFT JOIN counted ON counted.day = stored.day
        WHERE stored.day < toDate({before:DateTime64(3, 'Etc/UTC')}) AND counted.raw_rows != stored.raw_rows
    )
SELECT DISTINCT neighbour
FROM changed
ARRAY JOIN [subtractDays(day, 1), day, addDays(day, 1)] AS neighbour
WHERE neighbour IN (SELECT day FROM stored WHERE pending = 0)
    AND neighbour < toDate({before:DateTime64(3, 'Etc/UTC')})
ORDER BY neighbour DESC
