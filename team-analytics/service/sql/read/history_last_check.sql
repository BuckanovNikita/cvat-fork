-- When the raw counts were last compared; NULL before the first check.
SELECT if(count() = 0, NULL, max(checked_at)) AS checked_at FROM $totals_db.history_checks
