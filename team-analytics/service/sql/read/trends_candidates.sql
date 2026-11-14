-- Who can be compared in a trend: every annotator ({kind} 'annotators', project filter applied) or every
-- project ({kind} 'projects', annotator filter applied) with working time in [from, to) inside the caller's
-- scope, technical accounts left out; most working time first. Annotators carry their latest user name.
SELECT
    toUInt64(if({kind:String} = 'annotators', user_id, project_id)) AS id,
    if({kind:String} = 'annotators', argMax(user_name, hour), '') AS name,
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
    AND ({has_project:UInt8} = 0 OR {kind:String} = 'projects' OR project_id = {project:UInt64})
    AND ({has_annotator:UInt8} = 0 OR {kind:String} = 'annotators' OR user_id = {annotator:UInt64})
GROUP BY id
HAVING working_time_ms > 0
ORDER BY working_time_ms DESC, id ASC
