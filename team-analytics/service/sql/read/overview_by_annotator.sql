-- Working time per annotator in [from, to), largest first. Scope: one organization, or every row
-- (personal workspaces included) for instance scope. Technical accounts are not annotators.
SELECT
    user_id,
    argMax(user_name, hour) AS latest_user_name,
    sum(working_ms) AS working_time_ms
FROM $totals_db.working_time_hourly
WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
    AND (hour, version) IN (
        SELECT hour, max(version) FROM $totals_db.hour_versions
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
        GROUP BY hour
    )
    AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
    AND user_name NOT IN {technical_accounts:Array(String)}
GROUP BY user_id
HAVING working_time_ms > 0
ORDER BY working_time_ms DESC, latest_user_name ASC, user_id ASC
