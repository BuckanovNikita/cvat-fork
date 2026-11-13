-- The moment the newest successful refresh reflects; NULL before the first one.
SELECT if(count() = 0, NULL, max(data_as_of)) AS last_success_at
FROM $totals_db.refresh_runs
