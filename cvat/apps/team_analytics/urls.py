# SPDX-License-Identifier: MIT

from rest_framework import routers

from . import views

# SimpleRouter: no format-suffix routes (`status.json` and the like, which the actions do not take)
# and no root view; DefaultRouter's root at `api/` was never reached anyway (CVAT's own comes first).
router = routers.SimpleRouter(trailing_slash=False)
router.register("team-analytics", views.TeamAnalyticsViewSet, basename="team_analytics")

urlpatterns = router.urls
