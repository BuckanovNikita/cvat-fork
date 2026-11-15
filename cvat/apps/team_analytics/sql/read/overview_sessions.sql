-- Sessions per annotator in [from, to): number, total and average length, most sessions first, with
-- the same figures for the whole scope on every row (all_*). A session belongs to the period that
-- holds its end hour, so a session crossing the period start is counted once, in full.
-- Scope: an organization reads its own set (that organization's events only); instance scope reads
-- the instance-wide set, where a person's work across organizations and personal workspaces is one
-- session. Technical accounts are not annotators.
-- With a project filter a session counts if it touched the project, with only the time inside it as its
-- length; the annotator filter keeps one annotator's sessions.
SELECT
    user_id,
    latest_user_name,
    sessions,
    total_ms,
    intDiv(total_ms, sessions) AS average_ms,
    sum(sessions) OVER () AS all_sessions,
    sum(total_ms) OVER () AS all_total_ms,
    intDiv(all_total_ms, all_sessions) AS all_average_ms
FROM (
    SELECT
        user_id,
        argMax(user_name, end_at) AS latest_user_name,
        count() AS sessions,
        sum(if({has_project:UInt8} = 1, project_ms[indexOf(project_ids, {project:UInt64})], length_ms)) AS total_ms
    FROM $totals_db.session_intervals
    WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
        AND (hour, version) IN (
            SELECT hour, max(version) FROM $totals_db.hour_versions
            WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            GROUP BY hour
        )
        AND instance_wide = {instance:UInt8}
        AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
        AND user_id NOT IN {technical_accounts:Array(UInt64)}
        AND ({has_project:UInt8} = 0 OR has(project_ids, {project:UInt64}))
        AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
    GROUP BY user_id
)
ORDER BY sessions DESC, latest_user_name ASC, user_id ASC
