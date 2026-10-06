from django.urls import path

from .views import OtlpLogsView, OtlpMetricsView, OtlpTracesView

app_name = "telemetry"

urlpatterns = [
    path("v1/metrics", OtlpMetricsView.as_view(), name="otlp-metrics"),
    path("v1/logs", OtlpLogsView.as_view(), name="otlp-logs"),
    path("v1/traces", OtlpTracesView.as_view(), name="otlp-traces"),
]
