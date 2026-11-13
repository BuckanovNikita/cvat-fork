-- Working time per annotator in [from, to): the {top} largest, each row carrying the number and
-- working time of the annotators not shown (rest_*). Scope: one organization, or every row (personal
-- workspaces included) for instance scope. Technical accounts are not annotators. Only the project
-- filter applies, so that every annotator stays listed for picking while an annotator is selected.
SELECT user_id, latest_user_name, working_time_ms, rest_count, rest_ms
FROM (
    SELECT
        user_id,
        latest_user_name,
        working_time_ms,
        place,
        sum(if(place > {top:UInt32}, 1, 0)) OVER () AS rest_count,
        sum(if(place > {top:UInt32}, working_time_ms, 0)) OVER () AS rest_ms
    FROM (
        SELECT
            user_id,
            latest_user_name,
            working_time_ms,
            row_number() OVER (ORDER BY working_time_ms DESC, latest_user_name ASC, user_id ASC) AS place
        FROM (
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
                AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            GROUP BY user_id
            HAVING working_time_ms > 0
        )
    )
)
WHERE place <= {top:UInt32}
ORDER BY place
