from __future__ import annotations

import gzip
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from google.rpc.status_pb2 import Status
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    Gauge,
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
)
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectApiKey
from apps.projects.services import create_project_api_key
from apps.telemetry import views as telemetry_views
from apps.telemetry.protocol import OTLP_PROTOBUF_CONTENT_TYPE, OtlpSignal
from apps.telemetry.sink import OtlpBatch


def _metric_request() -> ExportMetricsServiceRequest:
    return ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                scope_metrics=[
                    ScopeMetrics(
                        metrics=[
                            Metric(
                                name="requests",
                                gauge=Gauge(
                                    data_points=[NumberDataPoint(time_unix_nano=1, as_int=1)]
                                ),
                            )
                        ]
                    )
                ]
            )
        ]
    )


def _log_request() -> ExportLogsServiceRequest:
    return ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                scope_logs=[
                    ScopeLogs(
                        log_records=[
                            LogRecord(
                                time_unix_nano=1,
                                body=AnyValue(string_value="hello from Sentrix"),
                            )
                        ]
                    )
                ]
            )
        ]
    )


def _trace_request() -> ExportTraceServiceRequest:
    return ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                scope_spans=[
                    ScopeSpans(
                        spans=[
                            Span(
                                trace_id=b"\x01" * 16,
                                span_id=b"\x02" * 8,
                                name="test-span",
                                start_time_unix_nano=1,
                                end_time_unix_nano=2,
                            )
                        ]
                    )
                ]
            )
        ]
    )


@pytest.mark.django_db
class TestOtlpHttpGateway:
    def _credential(self) -> tuple[APIClient, str, Project, ProjectApiKey]:
        user = User.objects.create_user(username="otlp-owner")
        organization = Organization.objects.create(name="OTLP Org", slug="otlp-org")
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMembership.Role.OWNER,
        )
        project = Project.objects.create(
            organization=organization,
            name="OTLP Project",
            slug="otlp-project",
            created_by=user,
        )
        api_key, token = create_project_api_key(
            project=project,
            name="OTLP exporter",
            created_by=user,
        )
        return APIClient(), token, project, api_key

    def _post(
        self,
        *,
        client: APIClient,
        path: str,
        token: str,
        payload: bytes,
        content_type: str = OTLP_PROTOBUF_CONTENT_TYPE,
        content_encoding: str | None = None,
    ) -> Any:
        headers: dict[str, Any] = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        if content_encoding is not None:
            headers["HTTP_CONTENT_ENCODING"] = content_encoding
        return client.post(path, data=payload, content_type=content_type, **headers)

    @pytest.mark.parametrize(
        ("path", "signal", "message_factory"),
        [
            ("/v1/metrics", OtlpSignal.METRICS, _metric_request),
            ("/v1/logs", OtlpSignal.LOGS, _log_request),
            ("/v1/traces", OtlpSignal.TRACES, _trace_request),
        ],
    )
    def test_binary_otlp_signals_reach_tenant_bound_sink(
        self,
        monkeypatch: pytest.MonkeyPatch,
        path: str,
        signal: OtlpSignal,
        message_factory: Any,
    ) -> None:
        client, token, project, api_key = self._credential()
        accepted: list[OtlpBatch] = []
        monkeypatch.setattr(telemetry_views, "submit_otlp_batch", accepted.append)

        response = self._post(
            client=client,
            path=path,
            token=token,
            payload=message_factory().SerializeToString(),
        )

        assert response.status_code == 200
        assert response["Content-Type"] == OTLP_PROTOBUF_CONTENT_TYPE
        assert len(accepted) == 1
        batch = accepted[0]
        assert batch.signal == signal
        assert batch.project_id == project.id
        assert batch.organization_id == project.organization_id
        assert batch.api_key_id == api_key.id

    def test_missing_machine_credential_is_otlp_unauthorized(self) -> None:
        response = APIClient().post(
            "/v1/metrics",
            data=_metric_request().SerializeToString(),
            content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        )

        assert response.status_code == 401
        status_message = Status()
        status_message.ParseFromString(response.content)
        assert "authentication is required" in status_message.message.lower()

    def test_missing_telemetry_scope_is_forbidden(self) -> None:
        client, token, _project, api_key = self._credential()
        api_key.scopes = []
        api_key.save(update_fields=["scopes", "updated_at"])

        response = self._post(
            client=client,
            path="/v1/metrics",
            token=token,
            payload=_metric_request().SerializeToString(),
        )

        assert response.status_code == 403

    def test_malformed_protobuf_is_non_retryable_bad_request(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/traces",
            token=token,
            payload=b"\x80",
        )

        assert response.status_code == 400
        status_message = Status()
        status_message.ParseFromString(response.content)
        assert "could not be decoded" in status_message.message

    def test_json_encoding_is_rejected_until_compliant_otlp_json_support_exists(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/metrics",
            token=token,
            payload=b"{}",
            content_type="application/json",
        )

        assert response.status_code == 415
        assert response["Content-Type"].startswith("application/json")

    @override_settings(OTLP_MAX_REQUEST_BYTES=1)
    def test_request_body_limit_returns_413(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/metrics",
            token=token,
            payload=_metric_request().SerializeToString(),
        )

        assert response.status_code == 413

    def test_gzip_otlp_request_is_decoded_before_sink(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, token, _project, _api_key = self._credential()
        accepted: list[OtlpBatch] = []
        monkeypatch.setattr(telemetry_views, "submit_otlp_batch", accepted.append)

        response = self._post(
            client=client,
            path="/v1/logs",
            token=token,
            payload=gzip.compress(_log_request().SerializeToString()),
            content_encoding="gzip",
        )

        assert response.status_code == 200
        assert len(accepted) == 1

    def test_invalid_gzip_body_is_bad_request(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/logs",
            token=token,
            payload=b"not-gzip",
            content_encoding="gzip",
        )

        assert response.status_code == 400

    def test_unsupported_content_encoding_is_rejected(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/metrics",
            token=token,
            payload=_metric_request().SerializeToString(),
            content_encoding="br",
        )

        assert response.status_code == 415

    def test_non_empty_payload_is_not_acknowledged_without_persistence(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/traces",
            token=token,
            payload=_trace_request().SerializeToString(),
        )

        assert response.status_code == 503
        status_message = Status()
        status_message.ParseFromString(response.content)
        assert "persistence is not available" in status_message.message

    def test_empty_otlp_request_can_succeed_without_dropping_telemetry(self) -> None:
        client, token, _project, _api_key = self._credential()

        response = self._post(
            client=client,
            path="/v1/metrics",
            token=token,
            payload=ExportMetricsServiceRequest().SerializeToString(),
        )

        assert response.status_code == 200
        assert response.content == b""
