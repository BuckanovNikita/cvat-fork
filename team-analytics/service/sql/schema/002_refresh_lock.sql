-- Claims and releases of the refresh lease, so that only one refresh runs at a time across replicas.
CREATE TABLE IF NOT EXISTS $totals_db.refresh_lock
(
    token String,
    holder String,
    action Enum8('claim' = 1, 'release' = 2),
    at DateTime64(6, 'Etc/UTC') DEFAULT now64(6, 'Etc/UTC'),
    expires DateTime64(6, 'Etc/UTC')
)
ENGINE = MergeTree
ORDER BY (at, token)
TTL toDateTime(at) + INTERVAL 1 DAY
