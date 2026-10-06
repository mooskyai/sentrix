from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .clickhouse_schema import get_clickhouse_client
from .clickhouse_writer import normalize_otlp_batch
from .protocol import OtlpSignal


@dataclass(frozen=True, slots=True)
class OtlpBatch:
    organization_id: UUID
    project_id: UUID
    api_key_id: UUID
    signal: OtlpSignal
    message: Any


class TelemetrySinkUnavailable(RuntimeError):
    pass


def submit_otlp_batch(batch: OtlpBatch) -> None:
    table_name, column_names, rows = normalize_otlp_batch(batch)
    if not rows:
        return

    client: Any | None = None
    try:
        client = get_clickhouse_client()
        client.insert(table_name, rows, column_names=column_names)
    except Exception as exc:
        raise TelemetrySinkUnavailable("ClickHouse telemetry persistence failed.") from exc
    finally:
        if client is not None:
            client.close()
