# SPDX-License-Identifier: MIT

from rest_framework import routers

from . import views

router = routers.DefaultRouter(trailing_slash=False)
router.register("team-analytics", views.TeamAnalyticsViewSet, basename="team_analytics")

urlpatterns = router.urls
