"""Working time per project for the period: the largest rows and the rest as one line.

Rows carry project identifiers only (0 = No project); the page resolves names through CVAT with the
viewer's own rights. The annotator filter applies, the project filter does not (every project stays
listed for picking).
"""

from __future__ import annotations

from team_analytics.service import Request

KEY = "by_project"
TOP = 8


def build(request: Request) -> dict:
    rows = request.sql.rows("read/overview_by_project.sql",
                            {**request.span().params(), **request.scope_params(), "top": TOP})
    first = rows[0] if rows else {"rest_count": 0, "rest_ms": 0}
    return {
        "rows": [{"project_id": int(row["project_id"]), "working_time_ms": int(row["working_time_ms"])}
                 for row in rows],
        "rest": {"count": int(first["rest_count"]), "working_time_ms": int(first["rest_ms"])},
    }
