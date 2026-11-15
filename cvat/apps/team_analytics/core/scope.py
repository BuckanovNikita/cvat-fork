"""Whose figures a request reads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    """`org_id` None means instance scope (every organization and personal workspaces). `admin`: the caller
    is in CVAT's admin group, whether or not an organization is named."""

    org_id: int | None
    user_id: int
    username: str
    admin: bool = False

    @property
    def instance(self) -> bool:
        return self.org_id is None
