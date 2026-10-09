from django.urls import path

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
]
