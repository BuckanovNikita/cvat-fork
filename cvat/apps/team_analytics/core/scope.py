"""Whose figures a request reads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    """`org_id` None means instance scope (every organization and personal workspaces). Only
    administrators read Team Analytics, so every caller sees the same answer for the same scope."""

    org_id: int | None
    user_id: int
    username: str

    @property
    def instance(self) -> bool:
        return self.org_id is None
