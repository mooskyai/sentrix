from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .clickhouse_schema import (
    LOGS_SCHEMA,
    METRICS_SCHEMA,
    SPANS_SCHEMA,
    TELEMETRY_SCHEMA_VERSION,
    ClickHouseTableSchema,
)
from .protocol import OtlpSignal

if TYPE_CHECKING:
    from .sink import OtlpBatch


def _timestamp_from_unix_nano(value: int) -> datetime:
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        seconds=seconds,
        microseconds=nanoseconds // 1_000,
    )


def _nullable_timestamp_from_unix_nano(value: int) -> datetime | None:
    return _timestamp_from_unix_nano(value) if value else None


def _fixed_hex(value: bytes, width: int) -> str:
    encoded = value.hex()
    return encoded[:width].ljust(width, "0")


def _any_value_to_python(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [_any_value_to_python(item) for item in value.array_value.values]
    if kind == "kvlist_value":
        return {item.key: _any_value_to_python(item.value) for item in value.kvlist_value.values}
    if kind == "bytes_value":
        return value.bytes_value.hex()
    return getattr(value, kind)


def _stringify_any_value(value: Any) -> str:
    normalized = _any_value_to_python(value)
    if normalized is None:
        return ""
    if isinstance(normalized, str):
        return normalized
    if isinstance(normalized, bool):
        return "true" if normalized else "false"
    if isinstance(normalized, int | float):
        return str(normalized)
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True)


def _attributes_to_map(attributes: Any) -> dict[str, str]:
    return {item.key: _stringify_any_value(item.value) for item in attributes}


def _resource_context(resource: Any) -> tuple[str, str, dict[str, str]]:
    attributes = _attributes_to_map(resource.attributes)
    service_name = attributes.get("service.name", "")
    environment = attributes.get(
        "deployment.environment.name",
        attributes.get("deployment.environment", ""),
    )
    return service_name, environment, attributes


def _scope_context(scope: Any) -> tuple[str, str, dict[str, str]]:
    return scope.name, scope.version, _attributes_to_map(scope.attributes)


def _optional_number(message: Any, field: str) -> float | None:
    try:
        if not message.HasField(field):
            return None
    except ValueError:
        pass
    value = getattr(message, field, None)
    return None if value is None else float(value)


def _aggregation_temporality(value: int) -> str:
    return {
        0: "unspecified",
        1: "delta",
        2: "cumulative",
    }.get(value, f"unknown:{value}")


def _base_metric_row(
    *,
    batch: OtlpBatch,
    resource: Any,
    scope: Any,
    metric: Any,
    point: Any,
    metric_type: str,
    aggregation_temporality: str = "",
    is_monotonic: bool = False,
) -> dict[str, Any]:
    service_name, environment, resource_attributes = _resource_context(resource)
    scope_name, scope_version, scope_attributes = _scope_context(scope)
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "organization_id": batch.organization_id,
        "project_id": batch.project_id,
        "timestamp": _timestamp_from_unix_nano(int(point.time_unix_nano)),
        "start_timestamp": _nullable_timestamp_from_unix_nano(
            int(getattr(point, "start_time_unix_nano", 0))
        ),
        "service_name": service_name,
        "environment": environment,
        "scope_name": scope_name,
        "scope_version": scope_version,
        "scope_attributes": scope_attributes,
        "resource_attributes": resource_attributes,
        "metric_name": metric.name,
        "metric_description": metric.description,
        "metric_unit": metric.unit,
        "metric_type": metric_type,
        "aggregation_temporality": aggregation_temporality,
        "is_monotonic": int(is_monotonic),
        "value_type": "",
        "number_value": None,
        "count": None,
        "sum": None,
        "min": None,
        "max": None,
        "bucket_counts": [],
        "explicit_bounds": [],
        "exponential_scale": None,
        "zero_count": None,
        "positive_offset": None,
        "positive_bucket_counts": [],
        "negative_offset": None,
        "negative_bucket_counts": [],
        "quantile_values": [],
        "attributes": _attributes_to_map(point.attributes),
    }


def _metric_rows(batch: OtlpBatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource_metrics in batch.message.resource_metrics:
        resource = resource_metrics.resource
        for scope_metrics in resource_metrics.scope_metrics:
            scope = scope_metrics.scope
            for metric in scope_metrics.metrics:
                metric_type = metric.WhichOneof("data")
                if metric_type == "gauge":
                    for point in metric.gauge.data_points:
                        row = _base_metric_row(
                            batch=batch,
                            resource=resource,
                            scope=scope,
                            metric=metric,
                            point=point,
                            metric_type="gauge",
                        )
                        value_type = point.WhichOneof("value")
                        row["value_type"] = "int" if value_type == "as_int" else "double"
                        if value_type is not None:
                            row["number_value"] = float(getattr(point, value_type))
                        rows.append(row)
                elif metric_type == "sum":
                    temporality = _aggregation_temporality(metric.sum.aggregation_temporality)
                    for point in metric.sum.data_points:
                        row = _base_metric_row(
                            batch=batch,
                            resource=resource,
                            scope=scope,
                            metric=metric,
                            point=point,
                            metric_type="sum",
                            aggregation_temporality=temporality,
                            is_monotonic=metric.sum.is_monotonic,
                        )
                        value_type = point.WhichOneof("value")
                        row["value_type"] = "int" if value_type == "as_int" else "double"
                        if value_type is not None:
                            row["number_value"] = float(getattr(point, value_type))
                        rows.append(row)
                elif metric_type == "histogram":
                    temporality = _aggregation_temporality(metric.histogram.aggregation_temporality)
                    for point in metric.histogram.data_points:
                        row = _base_metric_row(
                            batch=batch,
                            resource=resource,
                            scope=scope,
                            metric=metric,
                            point=point,
                            metric_type="histogram",
                            aggregation_temporality=temporality,
                        )
                        row.update(
                            value_type="histogram",
                            count=int(point.count),
                            sum=_optional_number(point, "sum"),
                            min=_optional_number(point, "min"),
                            max=_optional_number(point, "max"),
                            bucket_counts=[int(value) for value in point.bucket_counts],
                            explicit_bounds=[float(value) for value in point.explicit_bounds],
                        )
                        rows.append(row)
                elif metric_type == "exponential_histogram":
                    temporality = _aggregation_temporality(
                        metric.exponential_histogram.aggregation_temporality
                    )
                    for point in metric.exponential_histogram.data_points:
                        row = _base_metric_row(
                            batch=batch,
                            resource=resource,
                            scope=scope,
                            metric=metric,
                            point=point,
                            metric_type="exponential_histogram",
                            aggregation_temporality=temporality,
                        )
                        row.update(
                            value_type="exponential_histogram",
                            count=int(point.count),
                            sum=_optional_number(point, "sum"),
                            min=_optional_number(point, "min"),
                            max=_optional_number(point, "max"),
                            exponential_scale=int(point.scale),
                            zero_count=int(point.zero_count),
                            positive_offset=int(point.positive.offset),
                            positive_bucket_counts=[
                                int(value) for value in point.positive.bucket_counts
                            ],
                            negative_offset=int(point.negative.offset),
                            negative_bucket_counts=[
                                int(value) for value in point.negative.bucket_counts
                            ],
                        )
                        rows.append(row)
                elif metric_type == "summary":
                    for point in metric.summary.data_points:
                        row = _base_metric_row(
                            batch=batch,
                            resource=resource,
                            scope=scope,
                            metric=metric,
                            point=point,
                            metric_type="summary",
                        )
                        row.update(
                            value_type="summary",
                            count=int(point.count),
                            sum=float(point.sum),
                            quantile_values=[
                                (float(item.quantile), float(item.value))
                                for item in point.quantile_values
                            ],
                        )
                        rows.append(row)
    return rows


def _log_rows(batch: OtlpBatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource_logs in batch.message.resource_logs:
        resource = resource_logs.resource
        service_name, environment, resource_attributes = _resource_context(resource)
        for scope_logs in resource_logs.scope_logs:
            scope = scope_logs.scope
            scope_name, scope_version, scope_attributes = _scope_context(scope)
            for record in scope_logs.log_records:
                timestamp_nano = int(record.time_unix_nano or record.observed_time_unix_nano)
                rows.append(
                    {
                        "schema_version": TELEMETRY_SCHEMA_VERSION,
                        "organization_id": batch.organization_id,
                        "project_id": batch.project_id,
                        "timestamp": _timestamp_from_unix_nano(timestamp_nano),
                        "observed_timestamp": _nullable_timestamp_from_unix_nano(
                            int(record.observed_time_unix_nano)
                        ),
                        "service_name": service_name,
                        "environment": environment,
                        "scope_name": scope_name,
                        "scope_version": scope_version,
                        "scope_attributes": scope_attributes,
                        "resource_attributes": resource_attributes,
                        "severity_number": int(record.severity_number),
                        "severity_text": record.severity_text,
                        "body": _stringify_any_value(record.body),
                        "event_name": getattr(record, "event_name", ""),
                        "trace_id": _fixed_hex(record.trace_id, 32),
                        "span_id": _fixed_hex(record.span_id, 16),
                        "flags": int(record.flags),
                        "dropped_attributes_count": int(record.dropped_attributes_count),
                        "attributes": _attributes_to_map(record.attributes),
                    }
                )
    return rows


def _span_events_json(events: Any) -> str:
    values = [
        {
            "time_unix_nano": int(event.time_unix_nano),
            "name": event.name,
            "attributes": _attributes_to_map(event.attributes),
            "dropped_attributes_count": int(event.dropped_attributes_count),
        }
        for event in events
    ]
    return json.dumps(values, separators=(",", ":"), sort_keys=True)


def _span_links_json(links: Any) -> str:
    values = [
        {
            "trace_id": _fixed_hex(link.trace_id, 32),
            "span_id": _fixed_hex(link.span_id, 16),
            "trace_state": link.trace_state,
            "attributes": _attributes_to_map(link.attributes),
            "dropped_attributes_count": int(link.dropped_attributes_count),
            "flags": int(getattr(link, "flags", 0)),
        }
        for link in links
    ]
    return json.dumps(values, separators=(",", ":"), sort_keys=True)


def _span_rows(batch: OtlpBatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource_spans in batch.message.resource_spans:
        resource = resource_spans.resource
        service_name, environment, resource_attributes = _resource_context(resource)
        for scope_spans in resource_spans.scope_spans:
            scope = scope_spans.scope
            scope_name, scope_version, scope_attributes = _scope_context(scope)
            for span in scope_spans.spans:
                start_nano = int(span.start_time_unix_nano)
                end_nano = int(span.end_time_unix_nano)
                rows.append(
                    {
                        "schema_version": TELEMETRY_SCHEMA_VERSION,
                        "organization_id": batch.organization_id,
                        "project_id": batch.project_id,
                        "start_time": _timestamp_from_unix_nano(start_nano),
                        "end_time": _timestamp_from_unix_nano(end_nano),
                        "duration_ns": max(0, end_nano - start_nano),
                        "service_name": service_name,
                        "environment": environment,
                        "scope_name": scope_name,
                        "scope_version": scope_version,
                        "scope_attributes": scope_attributes,
                        "resource_attributes": resource_attributes,
                        "trace_id": _fixed_hex(span.trace_id, 32),
                        "span_id": _fixed_hex(span.span_id, 16),
                        "parent_span_id": _fixed_hex(span.parent_span_id, 16),
                        "trace_state": span.trace_state,
                        "span_name": span.name,
                        "span_kind": int(span.kind),
                        "status_code": int(span.status.code),
                        "status_message": span.status.message,
                        "flags": int(span.flags),
                        "dropped_attributes_count": int(span.dropped_attributes_count),
                        "dropped_events_count": int(span.dropped_events_count),
                        "dropped_links_count": int(span.dropped_links_count),
                        "attributes": _attributes_to_map(span.attributes),
                        "events_json": _span_events_json(span.events),
                        "links_json": _span_links_json(span.links),
                    }
                )
    return rows


def _rows_for_signal(batch: OtlpBatch) -> tuple[ClickHouseTableSchema, list[dict[str, Any]]]:
    if batch.signal is OtlpSignal.METRICS:
        return METRICS_SCHEMA, _metric_rows(batch)
    if batch.signal is OtlpSignal.LOGS:
        return LOGS_SCHEMA, _log_rows(batch)
    if batch.signal is OtlpSignal.TRACES:
        return SPANS_SCHEMA, _span_rows(batch)
    raise ValueError(f"Unsupported OTLP signal: {batch.signal}")


def normalize_otlp_batch(batch: OtlpBatch) -> tuple[str, list[str], list[list[Any]]]:
    schema, row_dicts = _rows_for_signal(batch)
    column_names = [name for name, _column_type in schema.columns]
    rows = [[row[name] for name in column_names] for row in row_dicts]
    return schema.name, column_names, rows
