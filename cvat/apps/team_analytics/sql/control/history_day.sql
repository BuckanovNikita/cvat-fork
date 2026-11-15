-- What computing one day needs to know first: its raw event rows (stored with the day, so the daily check
-- can tell when they changed), whether any of its hours already hold figures, and, for an empty day, the
-- nearest earlier day with events or figures (the empty days in between are recorded together).
SELECT
    (SELECT count() FROM $events_db.events
     WHERE timestamp >= {day_from:DateTime64(3, 'Etc/UTC')} AND timestamp < {day_to:DateTime64(3, 'Etc/UTC')})
        AS raw_rows,
    (SELECT count() FROM $totals_db.hour_versions
     WHERE hour >= {day_from:DateTime('Etc/UTC')} AND hour < {day_to:DateTime('Etc/UTC')}) AS marked_hours,
    greatest(
        (SELECT toDate(max(timestamp)) FROM $events_db.events WHERE timestamp < {day_from:DateTime64(3, 'Etc/UTC')}),
        (SELECT toDate(max(hour)) FROM $totals_db.hour_versions WHERE hour < {day_from:DateTime('Etc/UTC')})
    ) AS previous_day
