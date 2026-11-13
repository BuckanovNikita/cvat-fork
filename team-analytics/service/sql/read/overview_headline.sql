-- Active annotators in [from, to) within the scope and both filters, and the number of projects they
-- worked in (No project counts as one, as it is one row of the projects chart). Active = job work time.
SELECT
    uniqExactIf(user_id, user_ms > 0) AS annotators,
    (
        SELECT uniqExact(project_id) FROM (
            SELECT project_id, sum(working_ms) AS project_ms
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
                AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
            GROUP BY project_id
            HAVING project_ms > 0
        )
    ) AS projects
FROM (
    SELECT user_id, sum(working_ms) AS user_ms
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
        AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
    GROUP BY user_id
)
