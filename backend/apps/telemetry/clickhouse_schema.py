from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import clickhouse_connect
from django.conf import settings

TELEMETRY_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ClickHouseTableSchema:
    name: str
    columns: tuple[tuple[str, str], ...]
    partition_key: str
    sorting_key: tuple[str, ...]

    @property
    def create_sql(self) -> str:
        column_sql = ",\n    ".join(
            f"{name} {column_type}"
            + (f" DEFAULT {TELEMETRY_SCHEMA_VERSION}" if name == "schema_version" else "")
            for name, column_type in self.columns
        )
        sorting_sql = ", ".join(self.sorting_key)
        return (
            f"CREATE TABLE IF NOT EXISTS {self.name} (\n"
            f"    {column_sql}\n"
            ") ENGINE = MergeTree\n"
            f"PARTITION BY {self.partition_key}\n"
            f"ORDER BY ({sorting_sql})"
        )


_COMMON_COLUMNS: tuple[tuple[str, str], ...] = (
    ("schema_version", "UInt16"),
    ("organization_id", "UUID"),
    ("project_id", "UUID"),
    ("service_name", "LowCardinality(String)"),
    ("environment", "LowCardinality(String)"),
    ("scope_name", "LowCardinality(String)"),
    ("scope_version", "String"),
    ("scope_attributes", "Map(String, String)"),
    ("resource_attributes", "Map(String, String)"),
)

METRICS_SCHEMA = ClickHouseTableSchema(
    name="sentrix_metrics",
    columns=(
        ("schema_version", "UInt16"),
        ("organization_id", "UUID"),
        ("project_id", "UUID"),
        ("timestamp", "DateTime64(9, 'UTC')"),
        ("start_timestamp", "Nullable(DateTime64(9, 'UTC'))"),
        *_COMMON_COLUMNS[3:],
        ("metric_name", "String"),
        ("metric_description", "String"),
        ("metric_unit", "String"),
        ("metric_type", "LowCardinality(String)"),
        ("aggregation_temporality", "LowCardinality(String)"),
        ("is_monotonic", "UInt8"),
        ("value_type", "LowCardinality(String)"),
        ("number_value", "Nullable(Float64)"),
        ("count", "Nullable(UInt64)"),
        ("sum", "Nullable(Float64)"),
        ("min", "Nullable(Float64)"),
        ("max", "Nullable(Float64)"),
        ("bucket_counts", "Array(UInt64)"),
        ("explicit_bounds", "Array(Float64)"),
        ("exponential_scale", "Nullable(Int32)"),
        ("zero_count", "Nullable(UInt64)"),
        ("positive_offset", "Nullable(Int32)"),
        ("positive_bucket_counts", "Array(UInt64)"),
        ("negative_offset", "Nullable(Int32)"),
        ("negative_bucket_counts", "Array(UInt64)"),
        ("quantile_values", "Array(Tuple(Float64, Float64))"),
        ("attributes", "Map(String, String)"),
    ),
    partition_key="toYYYYMM(timestamp)",
    sorting_key=("organization_id", "project_id", "metric_name", "timestamp"),
)

LOGS_SCHEMA = ClickHouseTableSchema(
    name="sentrix_logs",
    columns=(
        ("schema_version", "UInt16"),
        ("organization_id", "UUID"),
        ("project_id", "UUID"),
        ("timestamp", "DateTime64(9, 'UTC')"),
        ("observed_timestamp", "Nullable(DateTime64(9, 'UTC'))"),
        *_COMMON_COLUMNS[3:],
        ("severity_number", "UInt8"),
        ("severity_text", "String"),
        ("body", "String"),
        ("event_name", "String"),
        ("trace_id", "FixedString(32)"),
        ("span_id", "FixedString(16)"),
        ("flags", "UInt32"),
        ("dropped_attributes_count", "UInt32"),
        ("attributes", "Map(String, String)"),
    ),
    partition_key="toYYYYMM(timestamp)",
    sorting_key=("organization_id", "project_id", "service_name", "timestamp", "trace_id"),
)

SPANS_SCHEMA = ClickHouseTableSchema(
    name="sentrix_spans",
    columns=(
        ("schema_version", "UInt16"),
        ("organization_id", "UUID"),
        ("project_id", "UUID"),
        ("start_time", "DateTime64(9, 'UTC')"),
        ("end_time", "DateTime64(9, 'UTC')"),
        ("duration_ns", "UInt64"),
        *_COMMON_COLUMNS[3:],
        ("trace_id", "FixedString(32)"),
        ("span_id", "FixedString(16)"),
        ("parent_span_id", "FixedString(16)"),
        ("trace_state", "String"),
        ("span_name", "String"),
        ("span_kind", "UInt8"),
        ("status_code", "UInt8"),
        ("status_message", "String"),
        ("flags", "UInt32"),
        ("dropped_attributes_count", "UInt32"),
        ("dropped_events_count", "UInt32"),
        ("dropped_links_count", "UInt32"),
        ("attributes", "Map(String, String)"),
        ("events_json", "String"),
        ("links_json", "String"),
    ),
    partition_key="toYYYYMM(start_time)",
    sorting_key=("organization_id", "project_id", "service_name", "start_time", "trace_id"),
)

TELEMETRY_TABLE_SCHEMAS = (METRICS_SCHEMA, LOGS_SCHEMA, SPANS_SCHEMA)


def get_clickhouse_client() -> Any:
    config = settings.CLICKHOUSE
    return clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        username=config["username"],
        password=config["password"],
        connect_timeout=3,
        send_receive_timeout=10,
    )


def ensure_clickhouse_schema(client: Any) -> None:
    for schema in TELEMETRY_TABLE_SCHEMAS:
        client.command(schema.create_sql)


def _normalize_expression(value: str) -> str:
    return "".join(value.replace("`", "").split()).lower()


def validate_clickhouse_schema(client: Any) -> list[str]:
    errors: list[str] = []

    for schema in TELEMETRY_TABLE_SCHEMAS:
        table_rows = client.query(
            "SELECT sorting_key, partition_key "
            "FROM system.tables "
            f"WHERE database = currentDatabase() AND name = '{schema.name}'"
        ).result_rows
        if not table_rows:
            errors.append(f"{schema.name}: table is missing")
            continue

        describe_rows = client.query(f"DESCRIBE TABLE {schema.name}").result_rows
        actual_columns = tuple((str(row[0]), str(row[1])) for row in describe_rows)
        if actual_columns != schema.columns:
            errors.append(f"{schema.name}: column/type layout does not match schema v1")

        actual_sorting = _normalize_expression(str(table_rows[0][0]))
        expected_sorting = _normalize_expression(", ".join(schema.sorting_key))
        if actual_sorting != expected_sorting:
            errors.append(f"{schema.name}: sorting key does not match schema v1")

        actual_partition = _normalize_expression(str(table_rows[0][1]))
        expected_partition = _normalize_expression(schema.partition_key)
        if actual_partition != expected_partition:
            errors.append(f"{schema.name}: partition key does not match schema v1")

    return errors
