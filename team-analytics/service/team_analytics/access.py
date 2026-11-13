"""Who may read what: asks CVAT, with the caller's own credentials, and decides the scope.

Rules: a member of CVAT's admin group may read the named organization, or instance scope when none
is named. An owner or maintainer may read their organization. Everyone else is refused, including
an owner or maintainer who names no organization. The organization id every query is limited to
comes from CVAT's answers, never from the request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from team_analytics.config import Config

FORWARDED_HEADERS = ("Cookie", "Authorization")
READING_ROLES = ("owner", "maintainer")


@dataclass(frozen=True)
class Scope:
    """`org_id` None means instance scope (every organization and personal workspaces)."""

    org_id: int | None
    user_id: int
    username: str

    @property
    def instance(self) -> bool:
        return self.org_id is None


class Refused(Exception):
    """The caller may not read. `status` and `reason` go into the response."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


class Access:
    def __init__(self, config: Config) -> None:
        self._config = config

    def scope(self, headers: dict[str, str], org_slug: str) -> Scope:
        credentials = {name: headers.get(name) for name in FORWARDED_HEADERS if headers.get(name)}
        if not credentials:
            raise Refused(401, "not_authenticated")
        me = self._get("/api/users/self", credentials, {})
        user_id, username = int(me["id"]), str(me["username"])
        is_admin = "admin" in (me.get("groups") or [])
        if not org_slug:
            if is_admin:
                return Scope(org_id=None, user_id=user_id, username=username)
            raise Refused(403, "organization_required")

        organizations = self._get("/api/organizations", credentials, {"slug": org_slug})
        matches = [org for org in organizations.get("results", []) if org.get("slug") == org_slug]
        if len(matches) != 1:
            raise Refused(403, "forbidden")
        org_id = int(matches[0]["id"])
        if is_admin:
            return Scope(org_id=org_id, user_id=user_id, username=username)

        memberships = self._get("/api/memberships", credentials, {"org": org_slug, "user": username})
        for membership in memberships.get("results", []):
            if (
                membership.get("user", {}).get("id") == user_id
                and membership.get("organization") == org_id
                and membership.get("is_active") is True
                and membership.get("role") in READING_ROLES
            ):
                return Scope(org_id=org_id, user_id=user_id, username=username)
        raise Refused(403, "forbidden")

    def _get(self, path: str, credentials: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self._config.cvat_url}{path}", headers={**credentials, "Accept": "application/json"},
                params={**params, "page_size": 100} if path != "/api/users/self" else params,
                timeout=self._config.cvat_timeout_s, allow_redirects=False,
            )
        except requests.RequestException as error:
            raise Refused(503, "cvat_unavailable") from error
        if response.status_code == 401:
            raise Refused(401, "not_authenticated")
        if response.status_code in (403, 404):
            raise Refused(403, "forbidden")
        if response.status_code != 200:
            raise Refused(503, "cvat_unavailable")
        try:
            return response.json()
        except ValueError as error:
            raise Refused(503, "cvat_unavailable") from error
