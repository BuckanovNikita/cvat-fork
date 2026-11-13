-- Keyboard and mouse use: the counts in the UI's input summary records (debug:info named
-- team_analytics:input_summary, logged through the job logger), credited to the hour, organization,
-- project and task of the record. Payload `hotkeys` = action name -> count, `mouse` = zone -> count.
-- Only job-bound records with a user count; only the window is counted (no look-back needed).
INSERT INTO $totals_db.input_hourly
    (hour, org_id, project_id, task_id, user_id, user_name, kind, name, actions, version)
SELECT
    row_hour, row_org, row_project, row_task, row_user,
    argMax(row_user_name, ts),
    entry.1 AS row_kind,
    entry.2 AS row_name,
    sum(entry.3),
    {version:UInt64}
FROM
(
    SELECT
        toStartOfHour(timestamp) AS row_hour,
        timestamp AS ts,
        ifNull(org_id, 0) AS row_org,
        ifNull(project_id, 0) AS row_project,
        ifNull(task_id, 0) AS row_task,
        assumeNotNull(user_id) AS row_user,
        ifNull(user_name, '') AS row_user_name,
        arrayConcat(
            arrayMap(pair -> ('hotkey', pair.1, pair.2), JSONExtractKeysAndValues(ifNull(payload, ''), 'hotkeys', 'UInt64')),
            arrayMap(pair -> ('mouse', pair.1, pair.2), JSONExtractKeysAndValues(ifNull(payload, ''), 'mouse', 'UInt64'))
        ) AS entries
    FROM $events_db.events
    WHERE timestamp >= {window_from:DateTime64(3, 'Etc/UTC')} AND timestamp < {window_to:DateTime64(3, 'Etc/UTC')}
        AND source = 'client'
        AND scope = 'debug:info'
        AND obj_name = 'team_analytics:input_summary'
        AND job_id IS NOT NULL
        AND user_id IS NOT NULL
)
ARRAY JOIN entries AS entry
WHERE entry.3 > 0 AND entry.2 != ''
GROUP BY row_hour, row_org, row_project, row_task, row_user, row_kind, row_name
