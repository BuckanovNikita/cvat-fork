-- The newest version a row of processed history carries; a new row takes a larger one.
SELECT max(version) AS version FROM $totals_db.history_days
