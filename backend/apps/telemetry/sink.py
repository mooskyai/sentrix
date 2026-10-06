from dataclasses import dataclass
from typing import Any
from uuid import UUID

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
    del batch
    raise TelemetrySinkUnavailable("Telemetry persistence is not connected yet.")
