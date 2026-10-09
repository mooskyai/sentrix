import sys

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

token = sys.stdin.readline().strip()
if not token:
    raise SystemExit("No project API key was provided on stdin.")

exporter = OTLPMetricExporter(
    endpoint="http://127.0.0.1:8000/v1/metrics",
    headers={"Authorization": f"Bearer {token}"},
    timeout=5,
)

reader = PeriodicExportingMetricReader(
    exporter,
    export_interval_millis=60_000,
)

provider = MeterProvider(
    resource=Resource.create(
        {
            "service.name": "sentrix-m3-browser-smoke",
            "deployment.environment.name": "local",
        }
    ),
    metric_readers=[reader],
)

meter = provider.get_meter("sentrix.m3.browser-smoke", "1.0.0")
counter = meter.create_counter(
    "sentrix.m3.browser.smoke",
    unit="1",
    description="M3.2 real browser explorer smoke metric",
)

counter.add(
    42,
    {
        "route": "/metrics",
        "source": "manual-smoke",
    },
)

provider.force_flush(timeout_millis=5_000)
provider.shutdown()

print("Real OTLP metric sent: sentrix.m3.browser.smoke = 42")
