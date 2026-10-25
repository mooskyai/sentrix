from __future__ import annotations

from email.message import Message as HeaderMessage
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from scripts import m6_acceptance_smoke as smoke


def _attributes(resource: Any) -> dict[str, str]:
    return {entry.key: entry.value.string_value for entry in resource.attributes}


def test_builds_correlated_three_service_signals_with_real_parentage() -> None:
    evidence = smoke.RunEvidence.create()
    payloads = smoke.build_payloads(evidence)
    assert set(payloads) == {"traces", "metrics", "logs"}
    traces = payloads["traces"].resource_spans
    metrics = payloads["metrics"].resource_metrics
    logs = payloads["logs"].resource_logs
    assert len(traces) == len(metrics) == len(logs) == 3
    for index, (trace, metric, log) in enumerate(zip(traces, metrics, logs, strict=True)):
        attrs = _attributes(trace.resource)
        assert attrs["service.name"] == smoke.SERVICE_NAMES[index]
        assert attrs["deployment.environment.name"] == "acceptance"
        assert attrs["sentrix.acceptance.run"] == evidence.run_id
        assert attrs["host.name"] == evidence.host_name
        assert attrs["k8s.cluster.name"] == "sentrix-acceptance-cluster"
        assert attrs["k8s.pod.name"]
        assert _attributes(metric.resource) == attrs == _attributes(log.resource)
        span = trace.scope_spans[0].spans[0]
        assert span.trace_id == evidence.trace_id
        assert span.span_id == evidence.span_ids[index]
        assert span.parent_span_id == (evidence.span_ids[index - 1] if index else b"")
        assert span.end_time_unix_nano > span.start_time_unix_nano
        assert metric.scope_metrics[0].metrics[0].gauge.data_points[0].as_int == 1
        record = log.scope_logs[0].log_records[0]
        assert record.trace_id == evidence.trace_id
        assert record.span_id == span.span_id


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com",
        "http://localhost:8000/prefix",
        "http://localhost:8000/?token=oops",
        "https://name:secret@example.com",
        "file:///tmp/export",
        "localhost:8000",
    ],
)
def test_rejects_unsafe_or_incorrect_base_urls(value: str) -> None:
    with pytest.raises(ValueError):
        smoke.validate_base_url(value)


def test_accepts_local_http_and_remote_https() -> None:
    assert smoke.validate_base_url("http://localhost:8000/") == "http://localhost:8000"
    assert smoke.validate_base_url("http://api:8000") == "http://api:8000"
    assert smoke.validate_base_url("https://sentrix.example.test") == "https://sentrix.example.test"


def test_submits_protobuf_without_putting_key_in_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[Request] = []

    class Success:
        status = 200

        def __enter__(self) -> Success:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(request: Request, timeout: int) -> Success:
        assert timeout == 10
        visited.append(request)
        return Success()

    monkeypatch.setattr(smoke, "urlopen", fake_urlopen)
    smoke.send_payloads(
        "http://localhost:8000",
        "PRIVATE_TEST_KEY",
        smoke.build_payloads(smoke.RunEvidence.create()),
    )
    assert [req.full_url.rsplit("/", 1)[-1] for req in visited] == ["traces", "metrics", "logs"]
    for request in visited:
        assert request.get_header("Authorization") == "Bearer PRIVATE_TEST_KEY"
        assert request.get_header("Content-type") == "application/x-protobuf"
        assert request.get_method() == "POST"
        assert request.data
        assert "PRIVATE_TEST_KEY" not in request.full_url


def test_http_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_request: Request, timeout: int) -> None:
        del timeout
        raise HTTPError(
            "http://localhost:8000/v1/traces",
            401,
            "Bearer PRIVATE_TEST_KEY",
            HeaderMessage(),
            None,
        )

    monkeypatch.setattr(smoke, "urlopen", fail)
    with pytest.raises(RuntimeError, match="HTTP 401") as failure:
        smoke.send_payloads(
            "http://localhost:8000",
            "PRIVATE_TEST_KEY",
            smoke.build_payloads(smoke.RunEvidence.create()),
        )
    assert "PRIVATE_TEST_KEY" not in str(failure.value)


def test_network_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_request: Request, timeout: int) -> None:
        del timeout
        raise URLError("password=PRIVATE_TEST_KEY")

    monkeypatch.setattr(smoke, "urlopen", fail)
    with pytest.raises(RuntimeError, match="connection failed") as failure:
        smoke.send_payloads(
            "http://localhost:8000",
            "PRIVATE_TEST_KEY",
            smoke.build_payloads(smoke.RunEvidence.create()),
        )
    assert "PRIVATE_TEST_KEY" not in str(failure.value)
