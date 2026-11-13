-- Marks days for computing again; the stored raw count is kept until the day is computed.
INSERT INTO $totals_db.history_days (day, raw_rows, pending, version, at)
SELECT day, argMax(raw_rows, version), 1, {version:UInt64}, {at:DateTime64(3, 'Etc/UTC')}
FROM $totals_db.history_days
WHERE day IN {days:Array(Date)}
GROUP BY day
