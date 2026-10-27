"""Read-only network-level check that a previously revoked project key gets OTLP HTTP 401.

Reads the same revoked key from stdin; sends an empty valid OTLP protobuf envelope
(no spans, metrics, or logs) to the local Compose API. Never prints the key.
"""

from __future__ import annotations

import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OTLP_TRACES_URL = "http://api:8000/v1/traces"


def check_revoked_key(token: str) -> bool:
    if not token:
        return False
    request = Request(
        OTLP_TRACES_URL,
        data=b"",  # Valid empty ExportTraceServiceRequest; creates no telemetry rows.
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-protobuf",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            return bool(response.status == 401)
    except HTTPError as exc:
        return exc.code == 401
    except OSError:
        return False


def main() -> int:
    token = sys.stdin.readline().strip()
    if not token:
        print("Missing previously revoked key on stdin.")
        return 2
    try:
        revoked = check_revoked_key(token)
    finally:
        token = ""
    if not revoked:
        print("Revoked-key OTLP HTTP 401 NOT VERIFIED (no 401 received).")
        return 1
    print("PASS: the supplied key received HTTP 401 from the live OTLP endpoint.")
    print("Requires operator confirmation that this was the same previously revoked key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
