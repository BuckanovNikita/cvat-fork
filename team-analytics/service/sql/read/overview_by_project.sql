-- Working time per project in [from, to): the {top} largest (project_id 0 = No project), each row
-- carrying the number and working time of the projects not shown (rest_*). Scope rules as in
-- overview_by_annotator.sql. Only the annotator filter applies, so that every project stays listed
-- for picking while a project is selected.
SELECT project_id, working_time_ms, rest_count, rest_ms
FROM (
    SELECT
        project_id,
        working_time_ms,
        place,
        sum(if(place > {top:UInt32}, 1, 0)) OVER () AS rest_count,
        sum(if(place > {top:UInt32}, working_time_ms, 0)) OVER () AS rest_ms
    FROM (
        SELECT
            project_id,
            working_time_ms,
            row_number() OVER (ORDER BY working_time_ms DESC, project_id ASC) AS place
        FROM (
            SELECT project_id, sum(working_ms) AS working_time_ms
            FROM $totals_db.working_time_hourly
            WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                AND (hour, version) IN (
                    SELECT hour, max(version) FROM $totals_db.hour_versions
                    WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                    GROUP BY hour
                )
                AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
                AND user_name NOT IN {technical_accounts:Array(String)}
                AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
            GROUP BY project_id
            HAVING working_time_ms > 0
        )
    )
)
WHERE place <= {top:UInt32}
ORDER BY place
