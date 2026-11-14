-- The release of a claim, stamped on the same clock as the claim (control/lock_claim.sql).
INSERT INTO $totals_db.refresh_lock (token, holder, action, at, expires)
VALUES ({token:String}, {holder:String}, 'release',
        ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC')),
        ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC')))
