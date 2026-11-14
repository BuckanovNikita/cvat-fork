-- The release of a claim, stamped on the same clock as the claim (control/lock_claim.sql), taken once as
-- `stamp`.
INSERT INTO $totals_db.refresh_lock (token, holder, action, at, expires)
SELECT {token:String}, {holder:String}, 'release', stamp, stamp
FROM (SELECT ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC')) AS stamp)
