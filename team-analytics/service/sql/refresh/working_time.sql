-- Working time: the figure Grafana shows, i.e. payload.working_time of the server's
-- send:working_time rows that carry a job, credited to the hour of the row's timestamp.
-- Rows without a user are dropped. Working time needs no look-back: only the window is counted.
INSERT INTO $totals_db.working_time_hourly
    (hour, org_id, project_id, task_id, user_id, user_name, working_ms, version)
SELECT
    toStartOfHour(timestamp) AS row_hour,
    ifNull(org_id, 0) AS row_org,
    ifNull(project_id, 0) AS row_project,
    ifNull(task_id, 0) AS row_task,
    assumeNotNull(user_id) AS row_user,
    argMax(ifNull(user_name, ''), timestamp),
    sum(JSONExtractUInt(ifNull(payload, ''), 'working_time')),
    {version:UInt64}
FROM $events_db.events
WHERE timestamp >= {read_from:DateTime64(3, 'Etc/UTC')} AND timestamp < {window_to:DateTime64(3, 'Etc/UTC')}
    AND timestamp >= {window_from:DateTime64(3, 'Etc/UTC')}
    AND scope = 'send:working_time'
    AND job_id IS NOT NULL
    AND user_id IS NOT NULL
GROUP BY row_hour, row_org, row_project, row_task, row_user
