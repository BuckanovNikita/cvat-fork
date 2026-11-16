-- Details table for [from, to): one row per annotator ({by} = 'annotators', key = user id) or per project
-- ({by} = 'projects', key = project id, 0 = No project) with job work in the scope (working time or an
-- operation), sorted by working time (most first), then name and id. By project a project with saved boxes
-- is listed too, so one into which only a technical account saved has a row: no working time, its saved
-- boxes and its Model. The caller clears the filter on the table's own dimension, so every row stays listed
-- for picking; the other filter applies.
--
-- Per row: the other dimension's count (projects an annotator worked in / annotators who worked in a
-- project, working time > 0), sessions (annotators: as read/overview_sessions.sql; projects: sessions that
-- touched the project, from the same set), working time, objects created by each annotator method (a stored
-- 'redone' row counts as drawn), alignments, class changes, deletions, average time to create (time / timed
-- creations), hotkey share (hotkey / hotkey + mouse actions, the canvas left out; null with none), Model
-- (annotators: built-in detector only; projects: also what technical accounts saved, without an annotator
-- filter) and saved boxes (single-frame rectangles the server stored; per annotator without technical
-- accounts, per project from everyone, and under an annotator filter from that annotator, who is never a
-- technical account).
--
-- The shape switch is applied once over the table's whole scope (before search), as in
-- read/overview_operations.sql and read/overview_creation_methods.sql: with {bounding_boxes} = 1 only bounding
-- box rows count unless the period is legacy ({legacy_period}; read/details_scope.sql says so to the page).
--
-- Search: annotators whose name contains {search} (case-insensitive); projects in {ids} when {has_ids} = 1
-- (the page matches project names, which only it knows). Paging: {page_size} rows from row {offset}, moved
-- back to the last page when {offset} is past the end; every row carries `total` (rows matching the search).
WITH
    wt AS (
        SELECT
            toUInt64(if({by:String} = 'annotators', user_id, project_id)) AS key,
            toUInt64(if({by:String} = 'annotators', project_id, user_id)) AS other,
            hour, user_name, working_ms
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
    ),
    ops_in AS (
        SELECT
            toUInt64(if({by:String} = 'annotators', user_id, project_id)) AS key,
            hour, user_name, operation, method, shape, objects, timed_objects, time_ms
        FROM $totals_db.operations_hourly
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
    ),
    work AS (
        SELECT key, sum(ms) AS working_ms, countIf(ms > 0) AS others
        FROM (SELECT key, other, sum(working_ms) AS ms FROM wt GROUP BY key, other)
        GROUP BY key
    ),
    ops AS (
        SELECT
            key,
            sumIf(objects, operation = 'creation' AND method IN ('drawn', 'redone')) AS drawn,
            sumIf(objects, operation = 'creation' AND method = 'pasted') AS pasted,
            sumIf(objects, operation = 'creation' AND method = 'propagated') AS propagated,
            sumIf(timed_objects, operation = 'creation') AS timed_creations,
            sumIf(time_ms, operation = 'creation') AS creation_ms,
            sumIf(objects, operation = 'alignment') AS alignments,
            sumIf(objects, operation = 'class_change') AS class_changes,
            sumIf(objects, operation = 'deletion') AS deletions
        FROM ops_in
        WHERE {bounding_boxes:UInt8} = 0 OR shape = 'bounding_box'
            OR {legacy_period:UInt8} = 1
        GROUP BY key
    ),
    names AS (
        SELECT key, argMax(user_name, hour) AS name
        FROM (SELECT key, hour, user_name FROM wt UNION ALL SELECT key, hour, user_name FROM ops_in)
        GROUP BY key
    ),
    sessions AS (
        SELECT key, count() AS sessions
        FROM (
            SELECT arrayJoin(if({by:String} = 'annotators', [user_id], project_ids)) AS key
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
        )
        GROUP BY key
    ),
    input AS (
        SELECT
            toUInt64(if({by:String} = 'annotators', user_id, project_id)) AS key,
            sumIf(actions, kind = 'hotkey') AS hotkey_actions,
            sumIf(actions, kind = 'mouse' AND name != 'canvas') AS mouse_actions
        FROM $totals_db.input_hourly
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
        GROUP BY key
    ),
    boxes AS (
        SELECT
            toUInt64(if({by:String} = 'annotators', user_id, project_id)) AS key,
            sumIf(objects, action = 'create' AND (
                    (source = 'detector' AND user_id NOT IN {technical_accounts:Array(UInt64)})
                    OR ({by:String} = 'projects' AND source = 'saved' AND {has_annotator:UInt8} = 0
                        AND user_id IN {technical_accounts:Array(UInt64)}))
                -- all shapes when asked for or in a legacy period
                AND ({bounding_boxes:UInt8} = 0
                    OR {legacy_period:UInt8} = 1
                    OR (resource = 'shapes' AND shape_type = 'rectangle'))) AS model,
            sumIf(objects, source = 'saved' AND action = 'create' AND resource = 'shapes'
                AND shape_type = 'rectangle'
                -- a technical account is no annotator: its boxes count per project, and not under an annotator filter
                AND (({by:String} = 'projects' AND {has_annotator:UInt8} = 0)
                    OR user_id NOT IN {technical_accounts:Array(UInt64)})) AS saved_boxes
        FROM $totals_db.boxes_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})
        GROUP BY key
    ),
    worked AS (
        SELECT key FROM work WHERE working_ms > 0
        UNION DISTINCT
        SELECT key FROM ops_in GROUP BY key HAVING sum(objects) > 0
        UNION DISTINCT
        -- by project also the projects with saved boxes, so one only a technical account saved into is listed
        SELECT key FROM boxes WHERE {by:String} = 'projects' AND saved_boxes > 0
    ),
    matched AS (
        SELECT
            worked.key AS id,
            if({by:String} = 'annotators', names.name, '') AS user_name,
            toUInt64(work.others) AS others,
            toUInt64(sessions.sessions) AS sessions,
            toUInt64(work.working_ms) AS working_time_ms,
            toUInt64(ops.drawn) AS drawn,
            toUInt64(ops.pasted) AS pasted,
            toUInt64(ops.propagated) AS propagated,
            toUInt64(boxes.model) AS model,
            toUInt64(boxes.saved_boxes) AS saved_boxes,
            toUInt64(ops.alignments) AS alignments,
            toUInt64(ops.class_changes) AS class_changes,
            toUInt64(ops.deletions) AS deletions,
            if(ops.timed_creations > 0, ops.creation_ms / ops.timed_creations, NULL) AS average_create_ms,
            if(input.hotkey_actions + input.mouse_actions > 0,
               input.hotkey_actions / (input.hotkey_actions + input.mouse_actions), NULL) AS hotkey_share
        FROM worked
        LEFT JOIN names ON names.key = worked.key
        LEFT JOIN work ON work.key = worked.key
        LEFT JOIN ops ON ops.key = worked.key
        LEFT JOIN sessions ON sessions.key = worked.key
        LEFT JOIN input ON input.key = worked.key
        LEFT JOIN boxes ON boxes.key = worked.key
        WHERE if({by:String} = 'annotators',
                 {search:String} = '' OR positionCaseInsensitiveUTF8(names.name, {search:String}) > 0,
                 {has_ids:UInt8} = 0 OR has({ids:Array(UInt64)}, worked.key))
    )
SELECT *
FROM (
    SELECT
        *,
        row_number() OVER (ORDER BY working_time_ms DESC, user_name ASC, id ASC) AS place,
        count() OVER () AS total
    FROM matched
)
WHERE place > least({offset:UInt64}, intDiv(total - 1, {page_size:UInt64}) * {page_size:UInt64})
    AND place <= least({offset:UInt64}, intDiv(total - 1, {page_size:UInt64}) * {page_size:UInt64}) + {page_size:UInt64}
ORDER BY place
