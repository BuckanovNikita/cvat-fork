"""Headline figures of the scope and both filters: active annotators and the number of projects they worked in."""

from __future__ import annotations

from ..request import Request

KEY = "headline"


def build(request: Request) -> dict:
    rows = request.sql.rows(
        "read/overview_headline.sql", {**request.span().params(), **request.scope_params()}
    )
    first = rows[0] if rows else {"annotators": 0, "projects": 0}
    return {"annotators": int(first["annotators"]), "projects": int(first["projects"])}
