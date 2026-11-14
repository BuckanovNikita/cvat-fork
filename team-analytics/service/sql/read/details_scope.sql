-- The details table's whole scope for [from, to) (search left out), one row:
--   legacy      a legacy period ({legacy_period}, see cutover.py) with job work (working time or an
--               operation), as in read/overview_operations.sql; an empty scope is not legacy;
--   all_shapes  the switch says All shapes, or the period is legacy;
--   project_ids every project with job work in the table's order (0 = No project), for the page's project name
--               search, which pages the matching projects itself (one page of ids per request).
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
    (SELECT count() FROM ops_in) AS operation_rows,
    (SELECT sum(working_ms) FROM wt) AS working_all
SELECT
    (operation_rows > 0 OR working_all > 0) AND {legacy_period:UInt8} = 1 AS legacy,
    {bounding_boxes:UInt8} = 0 OR {legacy_period:UInt8} = 1 AS all_shapes,
    (
        -- the rows of read/details.sql by project, in its order: working time (most first), then id
        SELECT arrayMap(row -> row.2, arraySort(row -> (-row.1, row.2), groupArray((working, project_id))))
        FROM (
            SELECT project_id, toInt64(sum(working_ms)) AS working, sum(objects) AS objects
            FROM (
                SELECT project_id, working_ms, toUInt64(0) AS objects FROM wt
                UNION ALL
                SELECT project_id, toUInt64(0) AS working_ms, toUInt64(objects) AS objects FROM ops_in
            )
            GROUP BY project_id
            HAVING working > 0 OR objects > 0
        )
    ) AS project_ids
