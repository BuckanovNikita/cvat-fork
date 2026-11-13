-- The live claim that came first: claims neither released nor expired, earliest wins.
SELECT token
FROM $totals_db.refresh_lock
WHERE action = 'claim'
    AND expires > now64(6, 'Etc/UTC')
    AND token NOT IN (SELECT token FROM $totals_db.refresh_lock WHERE action = 'release')
ORDER BY at ASC, token ASC
LIMIT 1
