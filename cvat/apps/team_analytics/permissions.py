# SPDX-License-Identifier: MIT

from enum import StrEnum

from django.conf import settings

from cvat.apps.iam.permissions import OpenPolicyAgentPermission


class TeamAnalyticsPermission(OpenPolicyAgentPermission):
    """Who may read Team Analytics (rules/team_analytics.rego): administrators anywhere, owners and
    maintainers inside their organization, nobody else."""

    class Scopes(StrEnum):
        VIEW = "view"

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
        return [
            {
                "status": Scopes.VIEW,
                "overview": Scopes.VIEW,
                "trends": Scopes.VIEW,
                "list_rows": Scopes.VIEW,
                "details": Scopes.VIEW,
            }[view.action]
        ]

    def get_resource(self):
        return None
