-- Hands every hour of the window to the refresh that just wrote its totals.
INSERT INTO $totals_db.hour_versions (hour, version)
SELECT {window_from:DateTime('Etc/UTC')} + toIntervalHour(number), {version:UInt64}
FROM numbers({window_hours:UInt32})
