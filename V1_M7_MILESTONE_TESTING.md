# Sentrix V1 M7 — Integration Testing and Acceptance

## M7.2 automated and operator acceptance — NOT RUN

| Case | Expected result |
| --- | --- |
| GIN-001 | Host/Compose origins resolve correctly; remote accepts only HTTPS root without credentials/paths |
| GIN-002 | Service/environment fields reject quotes, whitespace, shell and multiline injection |
| GIN-003 | Django CLI and Node SDK recipes export traces to OTLP/HTTP protobuf with server-only placeholders |
| GIN-004 | No browser key entry/storage; no query until user requests a service check |
| GIN-005 | Exact project/service/environment match; nonmatching row not shown as connected |
| GIN-006 | Bounded UTC 24h catalog query; empty, truncated and failure states remain distinct |
| GIN-007 | Framework/input/project change never displays stale other-service evidence |
| GIN-008 | Full `scripts/verify.ps1` (backend/frontend/tests, Ruff, mypy, build, schema) |

Manual operator: apply from clean SHA; run a real Django process and a real
Node/Express process with temporary *server-only* project key and collect
nonsecret runtime/SDK versions, exact service/environment, signal times and
actual ClickHouse/browser comparison. Verify no key in DevTools, no unexpected
ingest from the browser, secure remote origin validation, wrong-project data
isolation, truncated/503 states, keyboard/narrow view and key revocation.
Record CI for pushed SHA, unresolved deviations and operator approval here.
A passing mocked test or historical acceptance producer is **not** a real
framework runtime certification. Keep M6/M7.1 browser gates open.

Commands:

```powershell
docker compose exec -T web npm run test -- --run src/guidedIntegration.test.ts src/components/GuidedIntegrationPanel.test.tsx
.\scripts\verify.ps1
```

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
