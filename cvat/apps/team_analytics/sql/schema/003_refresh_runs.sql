-- One row per successful refresh, written after its hours were marked. `data_as_of` is the worker's
-- clock when the refresh started: the figures include events up to then. No `hour` column, so the
-- superseded-row removal leaves this table alone.
CREATE TABLE IF NOT EXISTS $totals_db.refresh_runs
(
    data_as_of DateTime64(3, 'Etc/UTC'),
    version UInt64,
    window_from DateTime('Etc/UTC'),
    window_to DateTime('Etc/UTC')
)
ENGINE = MergeTree
ORDER BY data_as_of
TTL toDateTime(data_as_of) + INTERVAL 30 DAY
