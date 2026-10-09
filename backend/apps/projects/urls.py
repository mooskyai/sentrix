from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ProjectApiKeyListCreateView,
    ProjectApiKeyRevokeView,
    ProjectDashboardPanelDeleteView,
    ProjectDashboardPanelListCreateView,
    ProjectViewSet,
)

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = [
    path(
        "projects/<uuid:project_id>/api-keys/",
        ProjectApiKeyListCreateView.as_view(),
        name="project-api-key-list",
    ),
    path(
        "projects/<uuid:project_id>/api-keys/<uuid:api_key_id>/",
        ProjectApiKeyRevokeView.as_view(),
        name="project-api-key-revoke",
    ),
    path(
        "projects/<uuid:project_id>/dashboard-panels/",
        ProjectDashboardPanelListCreateView.as_view(),
        name="project-dashboard-panel-list",
    ),
    path(
        "projects/<uuid:project_id>/dashboard-panels/<uuid:panel_id>/",
        ProjectDashboardPanelDeleteView.as_view(),
        name="project-dashboard-panel-delete",
    ),
    *router.urls,
]
