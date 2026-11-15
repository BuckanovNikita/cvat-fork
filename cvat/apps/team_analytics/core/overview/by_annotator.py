"""Working time per annotator for the period: the largest rows and the rest as one line.

The rows are the full view's (rows.py): the project filter applies, the annotator filter does not (every annotator
stays listed for picking). Each row and the rest carry their operation parts as the full view's rows do, and
`legacy` is the full view's flag for these rows.
"""

from __future__ import annotations

from ..request import Request
from ..rows import top

KEY = "by_annotator"
TOP = 8


def build(request: Request) -> dict:
    listed, rows, rest = top(request, "annotators", TOP)
    return {
        "legacy": listed["legacy"],
        "rows": [
            {
                "user_id": row["id"],
                "user_name": row["user_name"],
                "working_time_ms": row["working_time_ms"],
                "operations": row["operations"],
            }
            for row in rows
        ],
        "rest": rest,
    }
