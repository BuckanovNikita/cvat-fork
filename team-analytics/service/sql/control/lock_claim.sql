-- A claim of the refresh lease, or its renewal (the same token again): stamped with the time it lands and
-- live for {ttl_s} seconds from then. The time is ClickHouse's own, the one clock every replica shares,
-- unless the lease's clock supplies one in {now} (the service's never does; see LeaseClock in refresh.py).
-- `stamp` is that time, taken once, so the claim's `at` and `expires` come from one value.
INSERT INTO $totals_db.refresh_lock (token, holder, action, at, expires)
SELECT {token:String}, {holder:String}, 'claim', stamp, stamp + toIntervalSecond({ttl_s:UInt32})
FROM (SELECT ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC')) AS stamp)
