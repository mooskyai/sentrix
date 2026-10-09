from django.urls import path

from .logs_views import LogSearchView
from .metrics_views import MetricCatalogView, MetricSeriesView

urlpatterns = [
    path(
        "projects/<uuid:project_id>/metrics/catalog/",
        MetricCatalogView.as_view(),
        name="project-metric-catalog",
    ),
    path(
        "projects/<uuid:project_id>/metrics/series/",
        MetricSeriesView.as_view(),
        name="project-metric-series",
    ),
    path(
        "projects/<uuid:project_id>/logs/search/",
        LogSearchView.as_view(),
        name="project-log-search",
    ),
]
