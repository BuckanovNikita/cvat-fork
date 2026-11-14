-- The live claim that came first. A claim is renewed by inserting the same token again with a later
-- expiry: it keeps the place of its first insert and lives until its latest expiry, as long as every
-- renewal landed before the expiry it extends. A renewal that landed after that (the claim had already
-- expired, and another replica may have claimed meanwhile) ends the claim for good: an expired claim is
-- never revived. Released or expired claims are not live; the earliest live one wins. Expiry is judged on
-- the clock the claims were stamped on (control/lock_claim.sql).
SELECT token
FROM (
    SELECT token, min(at) AS first_at, max(expires) AS expires_at, countIf(n > 1 AND at >= expired_at) AS late
    FROM (
        SELECT token, at, expires,
            row_number() OVER (PARTITION BY token ORDER BY at ASC, expires ASC) AS n,
            max(expires) OVER (
                PARTITION BY token ORDER BY at ASC, expires ASC ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS expired_at
        FROM $totals_db.refresh_lock
        WHERE action = 'claim'
    )
    GROUP BY token
)
WHERE late = 0
    AND expires_at > ifNull({now:Nullable(DateTime64(6, 'Etc/UTC'))}, now64(6, 'Etc/UTC'))
    AND token NOT IN (SELECT token FROM $totals_db.refresh_lock WHERE action = 'release')
ORDER BY first_at ASC, token ASC
LIMIT 1
