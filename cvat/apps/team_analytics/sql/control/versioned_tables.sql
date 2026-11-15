-- Tables whose rows a refresh replaces: every table of the totals database with hour and version
-- columns (the totals tables and hour_versions).
SELECT table
FROM system.columns
WHERE database = {totals_db:String} AND name IN ('hour', 'version')
GROUP BY table
HAVING count() = 2
ORDER BY table
