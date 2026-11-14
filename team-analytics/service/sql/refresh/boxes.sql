-- Saved and detector objects (table boxes_hourly), credited to the hour of the row's timestamp. Needs no
-- look-back: only the window is counted.
--   saved:    the server's saved-annotation rows, one per (action, resource, shape type) and save, count =
--             top-level objects. A full replace (re-upload, import) writes delete for everything and then
--             create for everything, so it counts again. Rows without a job still belong to their project.
--   detector: the UI's team_analytics:model_creation records: `rectangle_count` single-frame rectangles
--             (capped at the count) and the rest of the `count` objects it made.
-- Rows without a user are dropped.
INSERT INTO $totals_db.boxes_hourly
    (hour, org_id, project_id, task_id, user_id, user_name, source, action, resource, shape_type, objects, version)
SELECT
    toStartOfHour(timestamp) AS row_hour,
    ifNull(org_id, 0) AS row_org,
    ifNull(project_id, 0) AS row_project,
    ifNull(task_id, 0) AS row_task,
    assumeNotNull(user_id) AS row_user,
    argMax(ifNull(user_name, ''), timestamp),
    row_source,
    row_action,
    part.1 AS row_resource,
    part.2 AS row_shape,
    sum(part.3),
    {version:UInt64}
FROM (
    SELECT
        timestamp, org_id, project_id, task_id, user_id, user_name,
        if(source = 'server', 'saved', 'detector') AS row_source,
        if(source = 'server', splitByChar(':', scope)[1], 'create') AS row_action,
        toUInt64(ifNull(count, 0)) AS objects,
        if(source = 'server', toUInt64(0),
            least(toUInt64(JSONExtractUInt(ifNull(payload, ''), 'rectangle_count')), objects)) AS rectangles,
        if(source = 'server',
            [(splitByChar(':', scope)[2], ifNull(obj_name, ''), objects)],
            [('shapes', 'rectangle', rectangles), ('objects', '', toUInt64(objects - rectangles))]) AS parts
    FROM $events_db.events
    WHERE timestamp >= {read_from:DateTime64(3, 'Etc/UTC')} AND timestamp < {window_to:DateTime64(3, 'Etc/UTC')}
        AND timestamp >= {window_from:DateTime64(3, 'Etc/UTC')}
        AND user_id IS NOT NULL
        AND (
            (source = 'server' AND scope IN ('create:shapes', 'update:shapes', 'delete:shapes',
                'create:tracks', 'update:tracks', 'delete:tracks', 'create:tags', 'update:tags', 'delete:tags'))
            OR (source = 'client' AND scope = 'debug:info' AND obj_name = 'team_analytics:model_creation'
                AND job_id IS NOT NULL)
        )
) AS facts
ARRAY JOIN parts AS part
WHERE part.3 > 0
GROUP BY row_hour, row_org, row_project, row_task, row_user, row_source, row_action, row_resource, row_shape
