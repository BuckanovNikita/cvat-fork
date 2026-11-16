# SPDX-License-Identifier: MIT

from enum import StrEnum

from django.conf import settings

from cvat.apps.iam.permissions import OpenPolicyAgentPermission


class TeamAnalyticsPermission(OpenPolicyAgentPermission):
    """Who may use Team Analytics (rules/team_analytics.rego): administrators, with or without an
    organization selected; nobody else."""

    class Scopes(StrEnum):
        VIEW = "view"
        UPDATE = "update"

    @classmethod
    def create(cls, request, view, obj, iam_context):
        return [
            cls.create_base_perm(request, view, scope, iam_context, obj)
            for scope in cls.get_scopes(request, view, obj)
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.url = settings.IAM_OPA_DATA_URL + "/team_analytics/allow"

    @classmethod
    def _get_scopes(cls, request, view, obj):
        Scopes = cls.Scopes
        # by action and method: an action missing here is refused with an error (get_scopes). DRF
        # answers HEAD with the GET handler.
        method = "GET" if request.method == "HEAD" else request.method
        return [
            {
                ("status", "GET"): Scopes.VIEW,
                ("overview", "GET"): Scopes.VIEW,
                ("trends", "GET"): Scopes.VIEW,
                ("list_rows", "GET"): Scopes.VIEW,
                ("details", "GET"): Scopes.VIEW,
                ("team_settings", "GET"): Scopes.VIEW,
                ("team_settings", "PUT"): Scopes.UPDATE,
                ("settings_users", "GET"): Scopes.VIEW,
                ("project_names", "GET"): Scopes.VIEW,
            }[(view.action, method)]
        ]

    def get_resource(self):
        return None
