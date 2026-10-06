from typing import Any

from apps.telemetry.clickhouse_schema import (
    LOGS_SCHEMA,
    METRICS_SCHEMA,
    SPANS_SCHEMA,
    TELEMETRY_TABLE_SCHEMAS,
    ensure_clickhouse_schema,
    validate_clickhouse_schema,
)


class _QueryResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = rows


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.schemas = {schema.name: schema for schema in TELEMETRY_TABLE_SCHEMAS}

    def command(self, sql: str) -> None:
        self.commands.append(sql)

    def query(self, sql: str) -> _QueryResult:
        for name, schema in self.schemas.items():
            if f"DESCRIBE TABLE {name}" in sql:
                return _QueryResult([tuple(column) for column in schema.columns])
            if f"name = '{name}'" in sql:
                return _QueryResult(
                    [
                        (
                            ", ".join(schema.sorting_key),
                            schema.partition_key,
                        )
                    ]
                )
        return _QueryResult([])


def test_schema_apply_is_idempotent_create_if_not_exists() -> None:
    client = FakeClickHouseClient()

    ensure_clickhouse_schema(client)

    assert len(client.commands) == 3
    assert all(command.startswith("CREATE TABLE IF NOT EXISTS") for command in client.commands)
    assert {schema.name for schema in TELEMETRY_TABLE_SCHEMAS} == {
        "sentrix_metrics",
        "sentrix_logs",
        "sentrix_spans",
    }


def test_every_table_has_tenant_columns_month_partition_and_tenant_first_ordering() -> None:
    for schema in TELEMETRY_TABLE_SCHEMAS:
        column_names = [name for name, _ in schema.columns]
        assert column_names[:3] == ["schema_version", "organization_id", "project_id"]
        assert schema.partition_key.startswith("toYYYYMM(")
        assert schema.sorting_key[:2] == ("organization_id", "project_id")
        assert "TTL" not in schema.create_sql.upper()


def test_metrics_schema_preserves_metric_family_shapes() -> None:
    columns = {name for name, _ in METRICS_SCHEMA.columns}

    assert {
        "number_value",
        "bucket_counts",
        "explicit_bounds",
        "exponential_scale",
        "positive_bucket_counts",
        "negative_bucket_counts",
        "quantile_values",
    }.issubset(columns)


def test_logs_and_spans_keep_trace_correlation_contracts() -> None:
    log_types = dict(LOGS_SCHEMA.columns)
    span_types = dict(SPANS_SCHEMA.columns)

    assert log_types["trace_id"] == "FixedString(32)"
    assert log_types["span_id"] == "FixedString(16)"
    assert span_types["trace_id"] == "FixedString(32)"
    assert span_types["span_id"] == "FixedString(16)"
    assert span_types["parent_span_id"] == "FixedString(16)"
    assert {"events_json", "links_json"}.issubset(span_types)


def test_schema_validation_accepts_matching_live_layout() -> None:
    client = FakeClickHouseClient()

    assert validate_clickhouse_schema(client) == []


def test_schema_validation_reports_drift() -> None:
    client = FakeClickHouseClient()
    client.schemas[METRICS_SCHEMA.name] = type(METRICS_SCHEMA)(
        name=METRICS_SCHEMA.name,
        columns=METRICS_SCHEMA.columns[:-1],
        partition_key=METRICS_SCHEMA.partition_key,
        sorting_key=METRICS_SCHEMA.sorting_key,
    )

    errors = validate_clickhouse_schema(client)

    assert any("sentrix_metrics: column/type layout" in error for error in errors)
