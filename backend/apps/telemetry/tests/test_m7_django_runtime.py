"""M7.3.1 isolated Django WSGI + real SDK protobuf transport verification."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from scripts import m7_django_readback as readback
from scripts import m7_django_runtime as runtime
from scripts.m6_readback import parse_run_window


class QueryResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.query_params: dict[str, Any] = {}
        self.query_text = ""

    def query(self, sql: str, *, parameters: dict[str, Any]) -> QueryResult:
        self.query_text = sql
        self.query_params = parameters
        return QueryResult(self.rows)


def _window() -> Any:
    return parse_run_window("a" * 32, "b" * 32, "2026-10-25T07:00:00+00:00")


def _valid_row() -> tuple[Any, ...]:
    at = datetime(2026, 10, 25, 7, 0, tzinfo=UTC)
    return (
        "b" * 32,
        "c" * 16,
        runtime.SPAN_NAME,
        2,
        {runtime.RUN_ATTRIBUTE: "a" * 32},
        at,
        at.replace(microsecond=100_000),
    )


def test_django_verifier_uses_typed_project_scope_and_exact_run_filter() -> None:
    org, project = UUID(int=1), UUID(int=2)
    client = FakeClient([_valid_row()])
    rows = readback.read_trace_rows(client, _window(), organization_id=org, project_id=project)
    readback.verify_trace(_window(), rows)
    assert client.query_params["organization_id"] == org
    assert client.query_params["project_id"] == project
    assert client.query_params["run_id"] == "a" * 32
    assert client.query_params["service"] == runtime.SERVICE
    assert client.query_params["environment"] == runtime.ENVIRONMENT
    assert "organization_id = {organization_id:UUID}" in client.query_text
    assert "project_id = {project_id:UUID}" in client.query_text
    assert "LIMIT 2" in client.query_text
    assert "max_rows_to_read = 250000" in client.query_text
    assert "resource_attributes['sentrix.acceptance.run'] = {run_id:String}" in client.query_text


@pytest.mark.parametrize("rows", [[], [_valid_row(), _valid_row()]])
def test_django_verifier_rejects_missing_or_duplicate_rows(rows: list[tuple[Any, ...]]) -> None:
    with pytest.raises(readback.DjangoTraceNotVerified):
        readback.verify_trace(_window(), rows)


@pytest.mark.parametrize(
    "index,replacement",
    [
        (0, "d" * 32),
        (1, "0" * 16),
        (2, "invented.operation"),
        (3, 1),
        (4, {runtime.RUN_ATTRIBUTE: "x" * 32}),
    ],
)
def test_django_verifier_rejects_mismatched_trace_evidence(index: int, replacement: Any) -> None:
    row = list(_valid_row())
    row[index] = replacement
    with pytest.raises(readback.DjangoTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


def test_django_verifier_accepts_naive_utc_clickhouse_datetimes() -> None:
    # ClickHouse Connect returns DateTime64('UTC') as naive Python datetimes.
    row = list(_valid_row())
    row[5] = row[5].replace(tzinfo=None)
    row[6] = row[6].replace(tzinfo=None)
    readback.verify_trace(_window(), [tuple(row)])


def test_django_verifier_rejects_naive_utc_out_of_window_span() -> None:
    row = list(_valid_row())
    row[5] = datetime(2026, 10, 25, 10)
    row[6] = datetime(2026, 10, 25, 10, 0, 1)
    with pytest.raises(readback.DjangoTraceNotVerified, match="outside the evidence window"):
        readback.verify_trace(_window(), [tuple(row)])


@pytest.mark.parametrize("invalid", [None, "2026-10-25T07:00:00Z"])
def test_django_verifier_rejects_non_datetime_timestamp(invalid: Any) -> None:
    row = list(_valid_row())
    row[5] = invalid
    with pytest.raises(readback.DjangoTraceNotVerified, match="timestamp is invalid"):
        readback.verify_trace(_window(), [tuple(row)])


def test_django_verifier_rejects_out_of_window_span() -> None:
    row = list(_valid_row())
    row[5] = datetime(2026, 10, 25, 10, tzinfo=UTC)
    with pytest.raises(readback.DjangoTraceNotVerified):
        readback.verify_trace(_window(), [tuple(row)])


@pytest.mark.parametrize(
    "url",
    [
        "http://external.example",
        "http://localhost:8000/v1",
        "https://user:secret@example.test",
    ],
)
def test_rejects_unsafe_exporter_endpoints(url: str) -> None:
    from scripts.m6_acceptance_smoke import validate_base_url

    with pytest.raises(ValueError):
        validate_base_url(url)


def test_external_django_wsgi_process_emits_real_otlp_protobuf() -> None:
    """An actual Django HTTP request in a separate process posts SDK wire format."""
    pytest.importorskip("django")
    captured: list[tuple[str, str, ExportTraceServiceRequest]] = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            decoded = ExportTraceServiceRequest()
            decoded.ParseFromString(body)
            captured.append((self.path, self.headers.get("Authorization", ""), decoded))
            response = ExportTraceServiceResponse().SerializeToString()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, _format: str, *args: Any) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Collector)
    server.timeout = 12
    thread = threading.Thread(target=server.handle_request, daemon=True)
    env = dict(os.environ)
    env.pop("DJANGO_SETTINGS_MODULE", None)
    env.pop("PYTHONPATH", None)
    root = Path(__file__).resolve().parents[3]
    try:
        thread.start()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.m7_django_runtime",
                "--base-url",
                f"http://localhost:{server.server_port}",
            ],
            input="PRIVATE_TEST_KEY\n",
            text=True,
            capture_output=True,
            cwd=root,
            env=env,
            timeout=20,
            check=False,
        )
        thread.join(timeout=12)
    finally:
        server.server_close()
    assert result.returncode == 0, result.stderr
    assert "PRIVATE_TEST_KEY" not in result.stdout + result.stderr
    assert len(captured) == 1
    path, auth, decoded = captured[0]
    assert path == "/v1/traces"
    assert auth == "Bearer PRIVATE_TEST_KEY"
    assert len(decoded.resource_spans) == 1
    block = decoded.resource_spans[0]
    attributes = {entry.key: entry.value.string_value for entry in block.resource.attributes}
    assert attributes["service.name"] == runtime.SERVICE
    assert attributes["deployment.environment.name"] == runtime.ENVIRONMENT
    assert len(attributes[runtime.RUN_ATTRIBUTE]) == 32
    span = block.scope_spans[0].spans[0]
    assert span.name == runtime.SPAN_NAME
    assert span.kind == span.SPAN_KIND_SERVER
    assert len(span.trace_id) == 16
    assert f"Trace ID: {span.trace_id.hex()}" in result.stdout
    assert f"Run ID: {attributes[runtime.RUN_ATTRIBUTE]}" in result.stdout
