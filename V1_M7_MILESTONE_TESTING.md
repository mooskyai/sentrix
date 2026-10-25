# Sentrix V1 M7 — Integration Testing and Acceptance

**State:** M7.1 implementation candidate. No M7 runtime/operational
acceptance has been recorded. The M6 browser gates remain open independently.

## M7.1 automated matrix

| Case | Expectation |
| --- | --- |
| INT-001 | Project viewer reads observed metrics/logs/spans and exact UTC 24h window |
| INT-002 | All three queries use typed organization/project UUIDs from Django membership |
| INT-003 | Separate foreign user and missing project return 404 without opening ClickHouse |
| INT-004 | Anonymous request denied; Bearer machine key is not a read-session substitute |
| INT-005 | Empty window returns `not_observed` and null timestamps; not unhealthy |
| INT-006 | Any ClickHouse error or malformed summary returns sanitized 503; client closes |
| INT-007 | Fixed 24h, max row-read and execution limits; no client time/tenant/table input |
| INT-008 | Settings panel handles loading, partial signals, empty, 503, refetch, switching |
| INT-009 | No browser API keys or arbitrary raw telemetry in the diagnostic response |
| INT-010 | Full `scripts/verify.ps1` including backend/frontend/live schema and build |

## Operator acceptance — NOT RUN

1. From a clean pushed baseline and healthy Compose, instrument a real
   server process/Collector with a temporary project-specific key stored only
   on the server. Record safe SDK version/endpoint/runtime.
2. Send a real workload, independently query ClickHouse; in project Settings
   click **Check again** and compare per-signal counts/timestamps, including
   a partial-signal project and an empty time window.
3. Sign in as another independent user without project membership and request
   the route directly: require 404 and no ClickHouse query. Switch an authorized
   project in browser and ensure stale query data does not persist.
4. Safely induce ClickHouse query failure (503), check recovery and keyboard/
   narrow viewport. Verify no raw key is sent in any browser request.
5. Revoke temporary credential; record full gate and GitHub CI; update
   `MILESTONE_ACCEPTANCE_CHECKLIST.md`, README and implementation evidence.

Use:

```powershell
docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_connection_diagnostics_api.py -v
docker compose exec -T web npm run test -- --run src/components/ConnectionDiagnosticsPanel.test.tsx
.\scripts\verify.ps1
```

## Release decision

**M7.1: OPEN.** No framework runtime is certified, and M6 human acceptance
is not retroactively completed by successful M7 automated checks.
