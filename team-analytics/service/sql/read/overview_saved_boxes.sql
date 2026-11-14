-- Saved boxes in [from, to): single-frame rectangles the server stored when jobs were saved (create rows of
-- shapes with shape type rectangle), whatever their creation method. Both filters apply; the shape switch
-- does not (they are boxes). Rows by kind:
--   'total'     one row: every saved box in the scope (technical accounts included);
--   'annotator' per annotator (technical accounts are no annotators), most boxes first;
--   'project'   per project (every method, technical accounts included), most boxes first.
WITH saved AS (
    SELECT project_id, user_id, user_name, hour, objects
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
)
SELECT kind, id, name AS user_name, boxes
FROM (
    SELECT 'total' AS kind, toUInt64(0) AS id, '' AS name, sum(objects) AS boxes
    FROM saved
    UNION ALL
    SELECT 'annotator' AS kind, user_id AS id, argMax(user_name, hour) AS name, sum(objects) AS boxes
    FROM saved
    WHERE user_name NOT IN {technical_accounts:Array(String)}
    GROUP BY user_id
    HAVING boxes > 0
    UNION ALL
    SELECT 'project' AS kind, project_id AS id, '' AS name, sum(objects) AS boxes
    FROM saved
    GROUP BY project_id
    HAVING boxes > 0
)
ORDER BY indexOf(['total', 'annotator', 'project'], kind), boxes DESC, id ASC
