-- Every row of a full view for [from, to): one row per annotator ({by_project} = 0) or per project
-- ({by_project} = 1; project_id 0 = No project), largest working time first, then by name and id. The
-- overview's rows by annotator and by project are this list's first rows with working time and its rest
-- is the others with working time (rows.py), so a row's operations are the same in both.
-- The caller drops the row dimension's own filter (every annotator stays listed while one is selected);
-- the other filter narrows as on the overview. Technical accounts are not annotators.
-- Per row: working time and its share of all rows' working time; each operation's objects, timed objects,
-- time and average; Other = max(0, working time - operation time) of the row; creation split by method
-- (a stored 'redone' counts as drawn, as in read/overview_creation_methods.sql); Model (counts only):
-- detector records of the row's annotators, and for a project also what technical accounts saved there
-- (only without an annotator filter).
-- Shape switch: decided once for the whole list as on the overview (bounding box rows only, unless the
-- period is legacy, {legacy_period}); `legacy` = a legacy period with job work in the scope (`job_work`).
WITH
    work AS (
        SELECT if({by_project:UInt8} = 1, project_id, user_id) AS id,
            argMax(user_name, hour) AS work_name, toInt64(sum(working_ms)) AS working_ms
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
        GROUP BY id
    ),
    in_scope AS (
        SELECT if({by_project:UInt8} = 1, project_id, user_id) AS id, hour, user_name,
            operation, if(method = 'redone', 'drawn', method) AS method, shape, objects, timed_objects, time_ms
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
    (SELECT count() FROM in_scope) AS operation_rows,
    {bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1 AS all_shapes,
    (SELECT sum(working_ms) FROM work) AS all_working_ms,
    operation_rows > 0 OR all_working_ms > 0 AS job_work,
    job_work AND {legacy_period:UInt8} = 1 AS legacy,
    ops AS (
        SELECT id, argMax(user_name, hour) AS ops_name,
            sumIf(objects, operation = 'creation') AS creation_objects,
            sumIf(timed_objects, operation = 'creation') AS creation_timed,
            sumIf(time_ms, operation = 'creation') AS creation_ms,
            sumIf(objects, operation = 'alignment') AS alignment_objects,
            sumIf(timed_objects, operation = 'alignment') AS alignment_timed,
            sumIf(time_ms, operation = 'alignment') AS alignment_ms,
            sumIf(objects, operation = 'class_change') AS class_change_objects,
            sumIf(timed_objects, operation = 'class_change') AS class_change_timed,
            sumIf(time_ms, operation = 'class_change') AS class_change_ms,
            sumIf(objects, operation = 'deletion') AS deletion_objects,
            sumIf(timed_objects, operation = 'deletion') AS deletion_timed,
            sumIf(time_ms, operation = 'deletion') AS deletion_ms,
            sumIf(objects, operation = 'creation' AND method = 'drawn') AS drawn_objects,
            sumIf(timed_objects, operation = 'creation' AND method = 'drawn') AS drawn_timed,
            sumIf(time_ms, operation = 'creation' AND method = 'drawn') AS drawn_ms,
            sumIf(objects, operation = 'creation' AND method = 'pasted') AS pasted_objects,
            sumIf(timed_objects, operation = 'creation' AND method = 'pasted') AS pasted_timed,
            sumIf(time_ms, operation = 'creation' AND method = 'pasted') AS pasted_ms,
            sumIf(objects, operation = 'creation' AND method = 'propagated') AS propagated_objects,
            sumIf(timed_objects, operation = 'creation' AND method = 'propagated') AS propagated_timed,
            sumIf(time_ms, operation = 'creation' AND method = 'propagated') AS propagated_ms
        FROM in_scope
        WHERE all_shapes OR shape = 'bounding_box'
        GROUP BY id
        HAVING sum(objects) > 0 OR sum(time_ms) > 0
    ),
    model AS (
        SELECT if({by_project:UInt8} = 1, project_id, user_id) AS id,
            argMax(user_name, hour) AS model_name, sum(objects) AS model_objects
        FROM $totals_db.boxes_hourly
        WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
            AND (hour, version) IN (
                SELECT hour, max(version) FROM $totals_db.hour_versions
                WHERE hour >= {from:DateTime('Etc/UTC')} AND hour < {to:DateTime('Etc/UTC')}
                GROUP BY hour
            )
            AND ({instance:UInt8} = 1 OR org_id = {org_id:UInt64})
            AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})
            AND action = 'create'
            AND (
                (source = 'saved' AND {by_project:UInt8} = 1 AND user_id IN {technical_accounts:Array(UInt64)}
                    AND {has_annotator:UInt8} = 0)
                OR (source = 'detector' AND user_id NOT IN {technical_accounts:Array(UInt64)}
                    AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64}))
            )
            -- as read/overview_creation_methods.sql: all objects under All shapes or in a legacy period;
            -- otherwise single-frame rectangles only
            AND ({bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1
                OR (resource = 'shapes' AND shape_type = 'rectangle'))
        GROUP BY id
        HAVING model_objects > 0
    ),
    ids AS (
        SELECT id FROM work WHERE working_ms > 0
        UNION DISTINCT SELECT id FROM ops
        UNION DISTINCT SELECT id FROM model
    ),
    joined AS (
        SELECT
            ids.id AS id,
            -- the annotator's latest name in working time, else in operations, else in Model records
            if({by_project:UInt8} = 1, '',
                multiIf(work.work_name != '', work.work_name, ops.ops_name != '', ops.ops_name, model.model_name)) AS name,
            work.working_ms AS working_ms,
            ops.creation_objects AS creation_objects, ops.creation_timed AS creation_timed,
            ops.creation_ms AS creation_ms,
            ops.alignment_objects AS alignment_objects, ops.alignment_timed AS alignment_timed,
            ops.alignment_ms AS alignment_ms,
            ops.class_change_objects AS class_change_objects, ops.class_change_timed AS class_change_timed,
            ops.class_change_ms AS class_change_ms,
            ops.deletion_objects AS deletion_objects, ops.deletion_timed AS deletion_timed,
            ops.deletion_ms AS deletion_ms,
            ops.drawn_objects AS drawn_objects, ops.drawn_timed AS drawn_timed, ops.drawn_ms AS drawn_ms,
            ops.pasted_objects AS pasted_objects, ops.pasted_timed AS pasted_timed, ops.pasted_ms AS pasted_ms,
            ops.propagated_objects AS propagated_objects, ops.propagated_timed AS propagated_timed,
            ops.propagated_ms AS propagated_ms,
            model.model_objects AS model_objects
        FROM ids
        LEFT JOIN work ON work.id = ids.id
        LEFT JOIN ops ON ops.id = ids.id
        LEFT JOIN model ON model.id = ids.id
    )
SELECT
    id, name, working_ms,
    if(all_working_ms > 0, working_ms / all_working_ms, NULL) AS share,
    creation_objects, creation_timed, creation_ms,
    if(creation_timed > 0, creation_ms / creation_timed, NULL) AS creation_average_ms,
    alignment_objects, alignment_timed, alignment_ms,
    if(alignment_timed > 0, alignment_ms / alignment_timed, NULL) AS alignment_average_ms,
    class_change_objects, class_change_timed, class_change_ms,
    if(class_change_timed > 0, class_change_ms / class_change_timed, NULL) AS class_change_average_ms,
    deletion_objects, deletion_timed, deletion_ms,
    if(deletion_timed > 0, deletion_ms / deletion_timed, NULL) AS deletion_average_ms,
    greatest(working_ms - toInt64(creation_ms + alignment_ms + class_change_ms + deletion_ms), toInt64(0)) AS other_ms,
    drawn_objects, drawn_timed, drawn_ms,
    if(drawn_timed > 0, drawn_ms / drawn_timed, NULL) AS drawn_average_ms,
    pasted_objects, pasted_timed, pasted_ms,
    if(pasted_timed > 0, pasted_ms / pasted_timed, NULL) AS pasted_average_ms,
    propagated_objects, propagated_timed, propagated_ms,
    if(propagated_timed > 0, propagated_ms / propagated_timed, NULL) AS propagated_average_ms,
    model_objects,
    all_working_ms, all_shapes, legacy, job_work
FROM joined
ORDER BY working_ms DESC, name ASC, id ASC
SETTINGS join_use_nulls = 0
