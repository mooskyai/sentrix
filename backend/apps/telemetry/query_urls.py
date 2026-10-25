from django.urls import path

from .connection_diagnostics_views import ConnectionDiagnosticsView
from .infrastructure_views import InfrastructureView
from .logs_views import LogSearchView
from .metrics_views import MetricCatalogView, MetricSeriesView
from .service_catalog_views import ServiceCatalogView
from .service_detail_views import ServiceDetailView
from .service_map_views import ServiceMapView
from .traces_views import TraceDetailView

urlpatterns = [
    path(
        "projects/<uuid:project_id>/integrations/connection-status/",
        ConnectionDiagnosticsView.as_view(),
        name="project-connection-status",
    ),
    path(
        "projects/<uuid:project_id>/infrastructure/",
        InfrastructureView.as_view(),
        name="project-infrastructure",
    ),
    path(
        "projects/<uuid:project_id>/services/catalog/",
        ServiceCatalogView.as_view(),
        name="project-service-catalog",
    ),
    path(
        "projects/<uuid:project_id>/services/detail/",
        ServiceDetailView.as_view(),
        name="project-service-detail",
    ),
    path(
        "projects/<uuid:project_id>/services/map/",
        ServiceMapView.as_view(),
        name="project-service-map",
    ),
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
    path(
        "projects/<uuid:project_id>/traces/<str:trace_id>/",
        TraceDetailView.as_view(),
        name="project-trace-detail",
    ),
]
