-- Keyboard and mouse use in [from, to) for the displayed scope (both filters; technical accounts left
-- out). One row per hotkey action among the {top} most used (most first), each carrying the scope's
-- totals and the number and actions of the hotkeys not shown (rest_*). With no hotkey action at all, one
-- row with action '' carries the totals. Mouse actions leave out the canvas zone (counted apart).
WITH
    scoped AS (
        SELECT kind, name, actions
        FROM $totals_db.input_hourly
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
    (SELECT toUInt64(sumIf(actions, kind = 'hotkey')) FROM scoped) AS hotkey_actions,
    (SELECT toUInt64(sumIf(actions, kind = 'mouse' AND name != 'canvas')) FROM scoped) AS mouse_actions,
    (SELECT toUInt64(sumIf(actions, kind = 'mouse' AND name = 'canvas')) FROM scoped) AS canvas_clicks,
    ranked AS (
        SELECT
            action,
            used,
            place,
            sum(if(place > {top:UInt32}, 1, 0)) OVER () AS rest_count,
            sum(if(place > {top:UInt32}, used, 0)) OVER () AS rest_actions
        FROM (
            SELECT action, used, row_number() OVER (ORDER BY used DESC, action ASC) AS place
            FROM (
                SELECT name AS action, sum(actions) AS used
                FROM scoped
                WHERE kind = 'hotkey'
                GROUP BY name
                HAVING used > 0
            )
        )
    )
SELECT
    action, used, place, rest_count, rest_actions, hotkey_actions, mouse_actions, canvas_clicks
FROM (
    SELECT toString(action) AS action, toUInt64(used) AS used, toUInt64(place) AS place,
           toUInt64(rest_count) AS rest_count, toUInt64(rest_actions) AS rest_actions
    FROM ranked
    WHERE place <= {top:UInt32}
    UNION ALL
    SELECT '', toUInt64(0), toUInt64(0), toUInt64(0), toUInt64(0)
    WHERE (SELECT count() FROM ranked) = 0
)
ORDER BY place
