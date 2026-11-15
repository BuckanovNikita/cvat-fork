-- Every hotkey action used in [from, to) in the displayed scope (both filters; technical accounts left out),
-- most used first, then by action name, with its share of all hotkey actions. Same rows and order as the
-- top hotkeys of read/overview_input.sql, so the overview's top rows are this list's first rows.
WITH
    used AS (
        SELECT name AS action, toUInt64(sum(actions)) AS actions
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
            AND kind = 'hotkey'
        GROUP BY name
        HAVING actions > 0
    ),
    (SELECT sum(actions) FROM used) AS hotkey_actions
SELECT toString(action) AS action, actions, actions / hotkey_actions AS share, hotkey_actions
FROM used
ORDER BY actions DESC, action ASC
