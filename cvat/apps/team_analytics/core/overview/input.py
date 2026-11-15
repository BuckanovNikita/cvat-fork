"""Keyboard and mouse for the period: hotkey actions, mouse actions, hotkey share and the most used hotkeys.

Hotkeys are named by action (what the shortcut does), never by key: the page labels them with the viewer's
own keymap. Both filters apply; the shape switch does not (hotkey use is not per shape).
"""

from __future__ import annotations

from ..request import Request

KEY = "input"
TOP = 7


def build(request: Request) -> dict:
    rows = request.sql.rows(
        "read/overview_input.sql", {**request.span().params(), **request.scope_params(), "top": TOP}
    )
    first = rows[0]
    hotkeys = int(first["hotkey_actions"])
    mouse = int(first["mouse_actions"])
    return {
        "hotkey_actions": hotkeys,
        "mouse_actions": mouse,
        # clicks on the canvas: drawing and editing, not mouse actions
        "canvas_clicks": int(first["canvas_clicks"]),
        "hotkey_share": hotkeys / (hotkeys + mouse) if hotkeys + mouse > 0 else None,
        "top_hotkeys": [
            {"action": row["action"], "actions": int(row["used"])} for row in rows if row["action"]
        ],
        "rest": {"count": int(first["rest_count"]), "actions": int(first["rest_actions"])},
    }
