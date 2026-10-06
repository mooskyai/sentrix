from enum import StrEnum
from typing import Any, cast

from google.protobuf.message import DecodeError  # type: ignore[import-untyped]
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

OTLP_PROTOBUF_CONTENT_TYPE = "application/x-protobuf"


class OtlpSignal(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"


_REQUEST_TYPES: dict[OtlpSignal, type[Any]] = {
    OtlpSignal.METRICS: ExportMetricsServiceRequest,
    OtlpSignal.LOGS: ExportLogsServiceRequest,
    OtlpSignal.TRACES: ExportTraceServiceRequest,
}
_RESPONSE_TYPES: dict[OtlpSignal, type[Any]] = {
    OtlpSignal.METRICS: ExportMetricsServiceResponse,
    OtlpSignal.LOGS: ExportLogsServiceResponse,
    OtlpSignal.TRACES: ExportTraceServiceResponse,
}
_RESOURCE_FIELDS: dict[OtlpSignal, str] = {
    OtlpSignal.METRICS: "resource_metrics",
    OtlpSignal.LOGS: "resource_logs",
    OtlpSignal.TRACES: "resource_spans",
}


class OtlpDecodeError(ValueError):
    pass


def decode_otlp_request(*, signal: OtlpSignal, payload: bytes) -> Any:
    message = _REQUEST_TYPES[signal]()
    try:
        message.ParseFromString(payload)
    except DecodeError as exc:
        raise OtlpDecodeError("The OTLP protobuf payload could not be decoded.") from exc
    return message


def has_telemetry_records(*, signal: OtlpSignal, message: Any) -> bool:
    return bool(getattr(message, _RESOURCE_FIELDS[signal]))


def success_response_payload(signal: OtlpSignal) -> bytes:
    return cast(bytes, _RESPONSE_TYPES[signal]().SerializeToString())
