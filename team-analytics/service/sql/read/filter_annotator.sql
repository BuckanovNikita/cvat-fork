-- The latest user name of the selected annotator within the caller's scope (any stored hour), so the
-- page can name a filter that came from a shared link. No row when the scope holds no work of theirs.
SELECT argMax(user_name, hour) AS latest_user_name
FROM $totals_db.working_time_hourly
WHERE user_id = {annotator:UInt64}
    AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
    AND user_name NOT IN {technical_accounts:Array(String)}
GROUP BY user_id
