-- A claim of the refresh lease, or its renewal (the same token again): stamped with the time it lands and
-- live for {ttl_s} seconds from then. The time is ClickHouse's own, the one clock every replica shares,
-- unless the lease's clock supplies one in {now} (the service's never does; see LeaseClock in refresh.py).
INSERT INTO $totals_db.refresh_lock (token, holder, action, at, expires)
VALUES ({token:String}, {holder:String}, 'claim',
        ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC')),
        ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC')) + toIntervalSecond({ttl_s:UInt32}))
