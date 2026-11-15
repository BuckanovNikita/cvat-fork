-- The details table's whole scope for [from, to) (search left out), one row:
--   legacy      a legacy period ({legacy_period}, see cutover.py) with job work (working time or an
--               operation), as in read/overview_operations.sql; an empty scope is not legacy;
--   job_work    the scope has working time or an operation (an empty scope is not partly legacy either);
--   all_shapes  the switch says All shapes, or the period is legacy;
--   project_ids every project read/details.sql lists by project (job work or saved boxes), in the table's order
--               (0 = No project), for the page's project name search, which pages the matching projects itself
--               (one page of ids per request).
-- Filters as read/details.sql gets them (the table's own dimension cleared by the caller).
WITH
    wt AS (
        SELECT project_id, working_ms
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
    ),
    ops_in AS (
        SELECT project_id, shape, objects
        FROM $totals_db.operations_hourly
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
    ),
    saved AS (
        -- saved boxes as read/details.sql counts them per project
        SELECT project_id, objects AS boxes
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
            AND source = 'saved' AND action = 'create' AND resource = 'shapes' AND shape_type = 'rectangle'
            AND ({has_annotator:UInt8} = 0 OR user_name NOT IN {technical_accounts:Array(String)})
    ),
    (SELECT count() FROM ops_in) AS operation_rows,
    (SELECT sum(working_ms) FROM wt) AS working_all
SELECT
    operation_rows > 0 OR working_all > 0 AS job_work,
    job_work AND {legacy_period:UInt8} = 1 AS legacy,
    {bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1 AS all_shapes,
    (
        -- the rows of read/details.sql by project, in its order: working time (most first), then id
        SELECT arrayMap(row -> row.2, arraySort(row -> (-row.1, row.2), groupArray((working, project_id))))
        FROM (
            SELECT project_id, toInt64(sum(working_ms)) AS working, sum(objects) AS objects, sum(boxes) AS boxes
            FROM (
                SELECT project_id, working_ms, toUInt64(0) AS objects, toUInt64(0) AS boxes FROM wt
                UNION ALL
                SELECT project_id, toUInt64(0) AS working_ms, toUInt64(objects) AS objects, toUInt64(0) AS boxes
                FROM ops_in
                UNION ALL
                SELECT project_id, toUInt64(0) AS working_ms, toUInt64(0) AS objects, boxes FROM saved
            )
            GROUP BY project_id
            HAVING working > 0 OR objects > 0 OR boxes > 0
        )
    ) AS project_ids
