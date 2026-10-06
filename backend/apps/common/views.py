from __future__ import annotations

from collections.abc import Callable

import clickhouse_connect
import redis
from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def live(request) -> JsonResponse:  # type: ignore[no-untyped-def]
    return JsonResponse({"status": "ok"})


def _postgres_check() -> None:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _redis_check() -> None:
    client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    client.ping()


def _clickhouse_check() -> None:
    config = settings.CLICKHOUSE
    client = clickhouse_connect.get_client(
        host=config["host"],
        port=config["port"],
        database=config["database"],
        username=config["username"],
        password=config["password"],
        connect_timeout=1,
        send_receive_timeout=1,
    )
    try:
        client.command("SELECT 1")
    finally:
        client.close()


@require_GET
def ready(request) -> JsonResponse:  # type: ignore[no-untyped-def]
    checks: dict[str, Callable[[], None]] = {
        "postgres": _postgres_check,
        "redis": _redis_check,
        "clickhouse": _clickhouse_check,
    }
    components: dict[str, str] = {}
    healthy = True

    for name, check in checks.items():
        try:
            check()
        except Exception:  # intentionally hide dependency internals from public response
            components[name] = "error"
            healthy = False
        else:
            components[name] = "ok"

    return JsonResponse(
        {"status": "ok" if healthy else "unavailable", "components": components},
        status=200 if healthy else 503,
    )
