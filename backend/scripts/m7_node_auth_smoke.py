"""Read-only M7.3.2 project authorization smoke against persisted Node telemetry.

This exercises DRF's authenticated views with two distinct persisted Django users.
It is NOT a real browser session, SDK write, or key-revocation test.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

SERVICE_NAME = "m7-node-express-runtime"
ENVIRONMENT = "integration"
SPAN_NAME = "m7.node.checkout"
RUN_ATTRIBUTE = "sentrix.acceptance.run"


class AcceptanceFailed(ValueError):
    pass


def _hex_id(raw: str, name: str) -> str:
    if re.fullmatch(r"[0-9a-f]{32}", raw) is None or set(raw) == {"0"}:
        raise AcceptanceFailed(f"{name} must be 32 nonzero lowercase hex characters.")
    return raw


def _utc_time(raw: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AcceptanceFailed("Timestamp must be RFC3339 UTC.") from exc
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise AcceptanceFailed("Timestamp must have a UTC offset.")
    return value.astimezone(UTC)


def _matching_server_spans(payload: dict[str, Any], trace_id: str, run_id: str) -> int:
    spans = payload.get("spans")
    if not isinstance(spans, list) or payload.get("truncated") is not False:
        raise AcceptanceFailed("Owner trace response missing spans or is truncated.")
    matches = 0
    for item in spans:
        if not isinstance(item, dict):
            raise AcceptanceFailed("Malformed span in owner response.")
        resource = item.get("resource_attributes")
        if (
            item.get("trace_id") == trace_id
            and item.get("span_name") == SPAN_NAME
            and item.get("span_kind") == 2
            and item.get("service_name") == SERVICE_NAME
            and item.get("environment") == ENVIRONMENT
            and isinstance(resource, dict)
            and resource.get(RUN_ATTRIBUTE) == run_id
        ):
            matches += 1
    return matches


def run(
    *,
    owner_username: str,
    foreign_username: str,
    project_id: UUID,
    trace_id: str,
    run_id: str,
    timestamp: datetime,
) -> None:
    from django.contrib.auth.models import User
    from rest_framework.test import APIClient

    from apps.projects.selectors import projects_for_user

    if owner_username == foreign_username:
        raise AcceptanceFailed("Owner and foreign user must be different accounts.")
    try:
        owner = User.objects.get(username=owner_username, is_active=True)
        foreign = User.objects.get(username=foreign_username, is_active=True)
    except User.DoesNotExist as exc:
        raise AcceptanceFailed(
            "Both usernames must identify existing active Django users."
        ) from exc

    if not projects_for_user(owner).filter(pk=project_id).exists():
        raise AcceptanceFailed("Owner lacks access to the requested project.")
    if projects_for_user(foreign).filter(pk=project_id).exists():
        raise AcceptanceFailed("Foreign user is already authorized; choose a nonmember.")

    start = (timestamp - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    end = (timestamp + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    window = {"start": start, "end": end}
    trace_path = f"/api/v1/projects/{project_id}/traces/{trace_id}/"
    catalog_path = f"/api/v1/projects/{project_id}/services/catalog/"

    owner_client = APIClient(HTTP_HOST="localhost")
    owner_client.force_authenticate(user=owner)
    trace_response = owner_client.get(trace_path, window)
    if trace_response.status_code != 200:
        raise AcceptanceFailed(f"Authorized trace read returned HTTP {trace_response.status_code}.")
    trace_body = trace_response.json()
    if (
        not isinstance(trace_body, dict)
        or _matching_server_spans(trace_body, trace_id, run_id) != 1
    ):
        raise AcceptanceFailed("Authorized trace read did not include one exact SDK SERVER span.")

    catalog_response = owner_client.get(catalog_path, {**window, "limit": "500"})
    if catalog_response.status_code != 200:
        raise AcceptanceFailed(
            f"Authorized services catalog returned HTTP {catalog_response.status_code}."
        )
    catalog = catalog_response.json()
    if not isinstance(catalog, dict) or not isinstance(catalog.get("services"), list):
        raise AcceptanceFailed("Authorized services catalog response is malformed.")
    if not any(
        isinstance(item, dict)
        and item.get("service_name") == SERVICE_NAME
        and item.get("environment") == ENVIRONMENT
        for item in catalog["services"]
    ):
        raise AcceptanceFailed("Authorized services catalog lacks the exact SDK service identity.")

    foreign_client = APIClient(HTTP_HOST="localhost")
    foreign_client.force_authenticate(user=foreign)
    for label, path, params in (
        ("trace", trace_path, window),
        ("services", catalog_path, {**window, "limit": "500"}),
    ):
        response = foreign_client.get(path, params)
        if response.status_code != 404:
            raise AcceptanceFailed(
                f"Foreign-user {label} read returned HTTP {response.status_code}, expected 404."
            )

    print("PASS: owner authenticated API reads show exact stored Node span and service.")
    print("PASS: existing foreign user's trace and services requests both return HTTP 404.")
    print(f"Project ID: {project_id}")
    print(f"Trace ID: {trace_id}")
    print("IN-PROCESS API proof only: real browser session and revoked-key checks remain OPEN.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-username", required=True)
    parser.add_argument("--foreign-username", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--time", required=True)
    args = parser.parse_args()
    try:
        run(
            owner_username=str(args.owner_username),
            foreign_username=str(args.foreign_username),
            project_id=UUID(str(args.project_id)),
            trace_id=_hex_id(str(args.trace_id), "trace_id"),
            run_id=_hex_id(str(args.run_id), "run_id"),
            timestamp=_utc_time(str(args.time)),
        )
    except (AcceptanceFailed, ValueError) as exc:
        print(f"M7.3.2 authorization smoke NOT VERIFIED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
