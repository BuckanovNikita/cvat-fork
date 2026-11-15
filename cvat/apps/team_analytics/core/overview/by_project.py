"""Working time per project for the period: the largest rows and the rest as one line.

Rows carry project identifiers only (0 = No project); the page resolves names through CVAT with the viewer's own
rights. The rows are the full view's (rows.py): the annotator filter applies, the project filter does not (every
project stays listed for picking). Each row and the rest carry their operation parts as the full view's rows do,
and `legacy` is the full view's flag for these rows.
"""

from __future__ import annotations

from ..request import Request
from ..rows import top

KEY = "by_project"
TOP = 8


def build(request: Request) -> dict:
    listed, rows, rest = top(request, "projects", TOP)
    return {
        "legacy": listed["legacy"],
        "rows": [
            {
                "project_id": row["id"],
                "working_time_ms": row["working_time_ms"],
                "operations": row["operations"],
            }
            for row in rows
        ],
        "rest": rest,
    }
