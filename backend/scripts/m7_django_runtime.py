"""Run an isolated real Django HTTP request and export its manual OTel server span.

This is a minimal external Django WSGI example, NOT Django auto-instrumentation
and NOT proof of database persistence. Run m7_django_readback separately.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

from scripts.m6_acceptance_smoke import validate_base_url

SERVICE = "m7-django-runtime"
ENVIRONMENT = "integration"
SPAN_NAME = "m7.django.checkout"
RUN_ATTRIBUTE = "sentrix.acceptance.run"

# Django resolves these URLs by importing this standalone module after setup.
urlpatterns: list[Any] = []


class QuietHandler(WSGIRequestHandler):
    """Suppress request logging, including untrusted headers or paths."""

    def log_message(self, _format: str, *args: Any) -> None:
        return None


def run_django_request(origin: str, token: str, run_id: str) -> tuple[str, datetime]:
    """Launch a separate Django WSGI app and generate one actual localhost request."""
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from django.http import JsonResponse
    from django.urls import path
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
    from opentelemetry.trace import SpanKind

    if settings.configured:
        raise RuntimeError("The Django runtime probe must run in its own clean Python process.")

    class TrackingExporter(SpanExporter):
        def __init__(self, delegate: SpanExporter) -> None:
            self.delegate = delegate
            self.accepted = 0

        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            try:
                status = self.delegate.export(spans)
            except Exception:
                return SpanExportResult.FAILURE
            if status == SpanExportResult.SUCCESS:
                self.accepted += len(spans)
            return status

        def shutdown(self) -> None:
            self.delegate.shutdown()

    exporter = TrackingExporter(
        OTLPSpanExporter(
            endpoint=f"{origin}/v1/traces",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
    )
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": SERVICE,
                "deployment.environment.name": ENVIRONMENT,
                RUN_ATTRIBUTE: run_id,
            }
        )
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("sentrix.m7.django.runtime")

    def checkout(_request: Any) -> Any:
        with tracer.start_as_current_span(SPAN_NAME, kind=SpanKind.SERVER) as span:
            span.set_attribute(RUN_ATTRIBUTE, run_id)
            span.set_attribute("http.request.method", "GET")
            span.set_attribute("http.route", "/checkout/")
            return JsonResponse({"trace_id": f"{span.get_span_context().trace_id:032x}"})

    # A stand-alone Django application, not the Sentrix API/control-plane settings.
    settings.configure(
        DEBUG=False,
        SECRET_KEY="m7-standalone-django-example-only",
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["127.0.0.1", "localhost"],
        MIDDLEWARE=[],
        INSTALLED_APPS=[],
    )
    import django

    django.setup()
    global urlpatterns
    urlpatterns = [path("checkout/", checkout)]
    application = get_wsgi_application()
    server = make_server("127.0.0.1", 0, application, handler_class=QuietHandler)
    server.timeout = 10
    port = server.server_port
    worker = threading.Thread(target=server.handle_request, daemon=True)
    observed_at = datetime.now(UTC)
    try:
        worker.start()
        try:
            with urlopen(f"http://127.0.0.1:{port}/checkout/", timeout=8) as response:
                if response.status != 200:
                    raise RuntimeError("Isolated Django request did not return HTTP 200.")
                body = json.loads(response.read(4096))
        except HTTPError, URLError, TimeoutError, ValueError:
            raise RuntimeError("Isolated Django HTTP request failed.") from None
        finally:
            worker.join(timeout=10)
        if worker.is_alive():
            raise RuntimeError("Isolated Django HTTP server did not finish its request.")
        trace_id = body.get("trace_id")
        if not isinstance(trace_id, str) or len(trace_id) != 32 or trace_id == "0" * 32:
            raise RuntimeError("Isolated Django request returned no valid trace ID.")
        if not provider.force_flush(timeout_millis=10000) or exporter.accepted != 1:
            raise RuntimeError("Trace exporter did not confirm HTTP acceptance.")
        return trace_id, observed_at
    finally:
        server.server_close()
        provider.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated Django request with OTLP SDK export")
    parser.add_argument("--base-url", default="http://api:8000")
    args = parser.parse_args()
    try:
        origin = validate_base_url(args.base_url)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.stdin.isatty():
        print("Supply a temporary project key on stdin, not the command line.", file=sys.stderr)
        return 2
    token = sys.stdin.readline().strip()
    if not token:
        print("Missing project key on stdin.", file=sys.stderr)
        return 2
    run_id = uuid4().hex
    try:
        trace_id, observed_at = run_django_request(origin, token, run_id)
    except Exception:
        print(
            "Django runtime export failed. Check SDK, OTLP endpoint and credentials.",
            file=sys.stderr,
        )
        return 1
    finally:
        token = ""
    print("Isolated Django HTTP request and SDK OTLP export returned success.")
    print(f"Run ID: {run_id}")
    print(f"Trace ID: {trace_id}")
    print(f"Time (UTC): {observed_at.isoformat()}")
    print(f"Service: {SERVICE} (environment: {ENVIRONMENT})")
    print("HTTP export alone does NOT prove ClickHouse persistence; run m7_django_readback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
