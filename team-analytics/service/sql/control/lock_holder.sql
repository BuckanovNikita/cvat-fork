-- The live claim that came first. A claim is renewed by inserting the same token again with a later
-- expiry: it keeps the place of its first insert and lives until its latest expiry. Released or
-- expired claims are not live; the earliest live one wins.
SELECT token
FROM (
    SELECT token, min(at) AS first_at, max(expires) AS expires_at
    FROM $totals_db.refresh_lock
    WHERE action = 'claim'
    GROUP BY token
)
WHERE expires_at > now64(6, 'Etc/UTC')
    AND token NOT IN (SELECT token FROM $totals_db.refresh_lock WHERE action = 'release')
ORDER BY first_at ASC, token ASC
LIMIT 1
