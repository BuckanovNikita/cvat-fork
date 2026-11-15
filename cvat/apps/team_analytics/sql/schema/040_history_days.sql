-- Processed history: one row each time a day (UTC) was computed as a whole, with the number of raw event
-- rows stamped in that day, counted just before computing it. The daily check adds a row with pending = 1
-- for a day whose raw count no longer matches; computing the day again adds a row with pending = 0.
-- The newest row of a day (largest version) is its state. A day with any row has figures (processed).
-- No `hour` column, so the superseded-row removal of refreshes leaves this table alone.
CREATE TABLE IF NOT EXISTS $totals_db.history_days
(
    day Date,
    raw_rows UInt64,
    pending UInt8,
    version UInt64,
    at DateTime64(3, 'Etc/UTC')
)
ENGINE = MergeTree
ORDER BY (day, version);

-- One row per daily check of the raw counts (the worker's clock when it ran).
CREATE TABLE IF NOT EXISTS $totals_db.history_checks
(
    checked_at DateTime64(3, 'Etc/UTC'),
    changed_days UInt32
)
ENGINE = MergeTree
ORDER BY checked_at
TTL toDateTime(checked_at) + INTERVAL 30 DAY
