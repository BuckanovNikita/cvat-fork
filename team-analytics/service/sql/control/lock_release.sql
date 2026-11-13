INSERT INTO $totals_db.refresh_lock (token, holder, action, expires)
VALUES ({token:String}, {holder:String}, 'release', now64(6, 'Etc/UTC'))
