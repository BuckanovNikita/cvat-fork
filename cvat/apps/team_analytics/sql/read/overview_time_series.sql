-- Working time per viewer day in [from, to), or per Monday week when {weekly} is 1, every day or week
-- of the period present (empty ones as 0). A stored hour belongs to the viewer's day it starts in,
-- kept inside [first_day, last_day] (a zone offset by part of an hour moves the day edge by that part).
-- The first week of a weekly layout starts on the period's first day. Scope: one organization, or
-- every row (personal workspaces included) for instance scope; technical accounts are not annotators.
SELECT
    if({weekly:UInt8} = 1, greatest(toMonday(day), toDate({first_day:String})), day) AS bucket,
    sum(ms) AS working_time_ms
FROM (
    SELECT toDate({first_day:String}) + number AS day, toUInt64(0) AS ms
    FROM numbers(toUInt64(dateDiff('day', toDate({first_day:String}), toDate({last_day:String})) + 1))
    UNION ALL
    SELECT
        least(greatest(toDate(hour, {tz:String}), toDate({first_day:String})), toDate({last_day:String})) AS day,
        working_ms AS ms
    FROM $totals_db.working_time_hourly
    WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
        AND (hour, version) IN (
            SELECT hour, max(version) FROM $totals_db.hour_versions
            WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            GROUP BY hour
        )
        AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
        AND user_id NOT IN {technical_accounts:Array(UInt64)}
        AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
        AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
)
GROUP BY bucket
ORDER BY bucket
