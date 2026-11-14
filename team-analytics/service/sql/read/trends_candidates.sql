-- Who can be compared in a trend: every annotator ({kind} 'annotators', project filter applied) or every
-- project ({kind} 'projects', annotator filter applied) with working time in [from, to) inside the caller's
-- scope, technical accounts left out. Annotators carry their latest user name.
--
-- `working_time_ms` counts only the buckets that are fully processed: those from {counted_from} on (processed
-- buckets are always the newest ones), and none when {counted} is 0. An hour belongs to the bucket of the
-- viewer day it starts in, in {tz}, kept from {first_bucket} on, as in read/trends.sql. Most counted working
-- time first, then by id, so that time in a bucket not fully processed never ranks anyone.
SELECT
    toUInt64(if({kind:String} = 'annotators', user_id, project_id)) AS id,
    if({kind:String} = 'annotators', argMax(user_name, hour), '') AS name,
    sumIf(working_ms, {counted:UInt8} = 1
        AND greatest(toDate(hour, {tz:String}), toDate({first_bucket:String})) >= toDate({counted_from:String}))
        AS working_time_ms
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
HAVING sum(working_ms) > 0
ORDER BY working_time_ms DESC, id ASC
