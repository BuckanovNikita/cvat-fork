-- The details table's whole scope for [from, to) (search left out), one row:
--   legacy      job work (working time or an operation) and no shape-tagged operation, as in
--               read/overview_operations.sql; an empty scope is not legacy;
--   all_shapes  the switch says All shapes, or nothing in the scope is shape-tagged;
--   project_ids every project with job work, ascending (0 = No project), for the page's project name search.
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
    (SELECT countIf(shape != 'untagged') FROM ops_in) AS tagged_rows,
    (SELECT sum(working_ms) FROM wt) AS working_all
SELECT
    (operation_rows > 0 OR working_all > 0) AND tagged_rows = 0 AS legacy,
    {bounding_boxes:UInt8} = 0 OR tagged_rows = 0 AS all_shapes,
    (
        SELECT arraySort(groupUniqArray(project_id))
        FROM (
            SELECT project_id FROM wt GROUP BY project_id HAVING sum(working_ms) > 0
            UNION ALL
            SELECT project_id FROM ops_in GROUP BY project_id HAVING sum(objects) > 0
        )
    ) AS project_ids
