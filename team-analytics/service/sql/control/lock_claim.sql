INSERT INTO $totals_db.refresh_lock (token, holder, action, expires)
VALUES ({token:String}, {holder:String}, 'claim', now64(6, 'Etc/UTC') + toIntervalSecond({ttl_s:UInt32}))
