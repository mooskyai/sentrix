# Sentrix V1 M6 — Service Catalog & Infrastructure Observability Test and Acceptance Plan

## M6.2 synthetic browser fixture (not an acceptance substitute)

Optional `manage.py seed_demo --username YOUR_LOGIN` (documented in `DEMO_SEEDING.md`)
provides two authorized demo organizations, exact service/environment variants,
OTLP-backed metric/log/span summaries, cross-service trace references, and an isolated
second project's reused service identity. This allows manual checking of the Services
list/detail, project switching, empty-environment handling and trace links. It does
**not** replace foreign-user isolation or real external exporter proof; M6.2 browser
acceptance and M6.3 gating requirements above remain in force.

## M6.2 detail test addition (verification pending)

SD-003 now requires API tests for exact tenant/project/service/environment/time scoping,
including empty environment, bounded metric-name/error-log/trace-reference responses and independent
truncation flags. SD-005 requires browser trace-ID navigation retaining the current project/window,
and SD-006 requires separate detail loading, empty, dependency-error and truncated states. The
complete regression gate, actual OTLP data and foreign-project proof remain mandatory before
commit/push. Existing historical checkpoint notes describe the initial M6.2 candidate only.

## 1. Gate philosophy

M6 derives higher-level views from telemetry, so the primary risk is turning descriptive attributes into
false authority or fabricated topology. Every acceptance slice must prove tenant isolation, bounded query
behavior, and evidence-backed aggregation before browser presentation is considered complete.

Operational verification must enter through real OTLP ingestion. Direct ClickHouse inserts are not valid
acceptance for discovery or topology behavior.

## 2. M6.1 automated matrix

### SC-001 — Membership before ClickHouse

An authenticated local member can read the service catalog. A real foreign project UUID returns `404`
and the ClickHouse query helper is not called.

### SC-002 — Tenant predicates

Every metrics/logs/spans catalog query receives organization/project IDs derived from the authorized
project. Caller input cannot override those IDs.

### SC-003 — Window contract

Omitted timestamps use the previous 24 hours. Explicit windows are timezone aware, half open, ordered,
and no longer than seven days.

### SC-004 — Signal coverage

Discover metric-only, log-only, trace-only, and multi-signal service identities. Merge the same exact
`(service_name, environment)` across signals into one response entry.

### SC-005 — Empty identity handling

Rows with empty `service_name` do not create catalog entries. Empty environment remains an empty value and
is not rewritten as `unknown`, `default`, or another invented environment.

### SC-006 — Observation aggregates

First/last timestamps and per-signal counts reflect only rows inside the requested window.

### SC-007 — Bounds and truncation

Return at most 500 services and expose `truncated=true` when additional observed identities exist.

### SC-008 — Dependency failure

ClickHouse exceptions return HTTP `503` with a generic dependency error. They are not converted to a
healthy empty list.

### SC-009 — No persistence/schema drift

M6.1 adds no Django model/migration for discovered services and no ClickHouse schema/index/projection/
materialized-view change.

### SC-010 — Regression gate

All M1-M5 backend/frontend/schema/build checks remain green.

## 3. Focused M6.1 checks

Expected focused commands after implementation should include the service-query module and API tests,
for example:

```powershell
docker compose exec api /opt/venv/bin/python -m pytest `
  apps/telemetry/tests/test_service_catalog_api.py -v

docker compose exec api /opt/venv/bin/ruff check apps/telemetry
docker compose exec api /opt/venv/bin/ruff format --check apps/telemetry
docker compose exec api /opt/venv/bin/mypy apps/telemetry
docker compose exec api /opt/venv/bin/python manage.py check
docker compose exec api /opt/venv/bin/python manage.py makemigrations --check --dry-run
```

Then run:

```powershell
./scripts/verify.ps1
```

The exact test filename may follow the repository's final implementation layout, but the acceptance
behaviors above are mandatory.

## 4. Manual M6.1 smoke

Use a project with recent OTLP telemetry from at least two services:

1. request the default service catalog and confirm only project-local observed identities appear;
2. request a narrow explicit window and confirm entries outside that window disappear;
3. confirm one metric-only/log-only/trace-only identity when corresponding fixtures exist;
4. use an unrelated membership/project and confirm the foreign project UUID returns `404`;
5. stop ClickHouse or mock dependency failure in the focused test path and confirm it is an error, not an
   empty catalog.

## 5. M6.1 stop condition

M6.1 is complete only after focused tests, live tenant-isolation evidence, the full release gate, commit,
push, and a clean:

```text
## main...origin/main
```

Only then may M6.2 begin.

## 6. M6.2 automated matrix

### SD-001 — Project-scoped Services workspace

Every service-list/detail query key contains project UUID plus the selected observation window. Project
navigation cannot reuse a previous project's catalog response.

### SD-002 — Explicit observed identity

List and detail render the exact service name/environment and observation window returned by the API.

### SD-003 — Bounded detail summaries

Metric names, log references, trace IDs, and counts returned for service detail remain bounded and scoped
to the selected identity/window.

### SD-004 — No invented health metadata

The backend/browser does not synthesize health status, SLO attainment, owner/team, deployment version, or
canonical resource metadata from absence or partial telemetry.

### SD-005 — Explorer navigation

Links into Metrics, Logs, and Traces preserve project context and supported exact filters/IDs. Destination
APIs still perform normal membership authorization.

### SD-006 — Failure-state honesty

Loading, healthy empty, dependency unavailable, and truncated results are distinct in both service list
and detail.

### SD-007 — No PostgreSQL telemetry copy

No discovered-service inventory, metric/log/span samples, or service activity history is written to
PostgreSQL.

### SD-008 — Regression gate

M1-M6.1 checks plus frontend lint/typecheck/tests/build remain green.

## 7. M6.2 browser smoke

Using a project with fresh multi-signal telemetry:

1. open Services and confirm observed identities from the selected window;
2. open one service detail and confirm exact service/environment plus bounded activity;
3. follow one supported Metrics/Logs/Trace navigation target and confirm tenant/project context remains
   correct;
4. switch project and confirm the previous service state does not remain visible;
5. verify an empty observation window is described as not observed, not deleted/down.

## 8. M6.2 stop condition

M6.2 is complete only after service API/UI tests, browser smoke, full release gate, commit, push, and a
clean synchronized `main`.

Only then may M6.3 begin.

## 9. M6.3 automated matrix

### IR-001 — Infrastructure tenancy

Infrastructure discovery authorizes the project before ClickHouse access and includes credential/session-
derived organization/project predicates in every query.

### IR-002 — Supported resource keys

Recognized host/Kubernetes keys are read from stored resource attributes without renaming arbitrary
customer attributes into infrastructure objects.

### IR-003 — Missing-attribute honesty

Absent/empty supported attributes do not create placeholder hosts, clusters, namespaces, workloads,
pods, or containers.

### IR-004 — Co-observed relationships

A displayed parent/containment association requires the necessary related attributes on the same observed
resource. Independently observed names are not joined merely because they occur in one project.

### IR-005 — Bounds/window

Default/maximum windows and result limits are enforced before ClickHouse execution and truncation is
explicit.

### IR-006 — Foreign-project non-discovery

A real foreign project containing recognizable Kubernetes attributes still returns `404` to the local
session.

### IR-007 — No Kubernetes control-plane dependency

Tests verify M6.3 does not require Kubernetes credentials, API clients, cluster polling, or another
collector protocol.

### IR-008 — Regression gate

All prior backend/frontend/schema/build checks remain green.

## 10. M6.3 browser smoke

Send OTLP telemetry containing a known cluster, namespace, workload, pod, container, and host resource
shape. Open Infrastructure and verify only the actually observed values/relationships appear. Change the
time window so the fixture falls outside it and confirm the resources become not observed rather than
reported as deleted.

## 11. M6.3 stop condition

M6.3 is complete only after infrastructure query/UI tests, real resource-attribute smoke, full release
gate, commit, push, and a clean synchronized `main`.

Only then may M6.4 begin.

## 12. M6.4 automated matrix

### SM-001 — Authorized span join

Service-map queries use only spans inside one authorized organization/project and bounded window.

### SM-002 — Real parent/child edge

A child span with a returned parent span in another service produces exactly one directed observed edge
from parent service identity to child service identity.

### SM-003 — Same-service suppression

Parent/child spans with the same `(service_name, environment)` do not create a cross-service map edge.

### SM-004 — Missing-parent honesty

A span whose parent is absent from the authorized bounded data produces no inferred edge.

### SM-005 — Environment identity

The same service name in different environments remains separate nodes and cannot be merged merely by
name.

### SM-006 — Tenant collision isolation

Foreign-project spans may deliberately reuse the same trace/span IDs as local fixtures; they must not
change local nodes, edge counts, or timestamps.

### SM-007 — Node/edge bounds

Responses cap at 100 nodes and 250 edges with explicit truncation behavior.

### SM-008 — UI semantics

The browser labels relationships as observed span parent/child service relationships and does not present
them as guaranteed network/Kubernetes topology.

### SM-009 — No speculative graph storage

No graph database, PostgreSQL edge table, ClickHouse materialized view/projection, or background topology
builder is introduced for V1 M6.4.

### SM-010 — Regression gate

All prior tests and the complete repository release gate remain green.

## 13. M6.4 browser smoke

Export one trace with:

```text
service-a root/server span
        |
        v
service-b child/client-or-internal span
```

Confirm the bounded service map shows one `service-a -> service-b` observed edge. Also export same-service
parentage and a child whose parent is not present; neither should create an additional cross-service edge.

## 14. M6.4 stop condition

M6.4 is complete only after live span-map proof, browser confirmation, full release gate, commit, push,
and clean synchronized `main`.

Only then may M6.5 begin.

## 15. M6.5 operational matrix

### SO-001 — Isolated temporary project

Create a disposable writable project and one temporary project telemetry key through the normal session
control plane. Do not reuse operator production rules/configuration or print the raw key.

### SO-002 — Real multi-service OTLP telemetry

Send metrics/logs/traces for at least two service identities through public authenticated OTLP/HTTP.
Include unique run markers plus recognized host/Kubernetes resource attributes.

### SO-003 — Service catalog proof

Require both temporary services in the project catalog with expected signal presence and bounded
observation timestamps.

### SO-004 — Service detail proof

Require service detail to return only the selected service/window and expected bounded telemetry
references.

### SO-005 — Infrastructure proof

Require the expected cluster/namespace/workload/pod/container/host observations and only evidence-backed
relationships.

### SO-006 — Service-map proof

Require exactly the expected real cross-service parent/child edge from the generated trace and no
cross-project contamination.

### SO-007 — Tenant isolation

Create an actual foreign organization/project with no membership for the browser session. All M6 catalog,
detail, infrastructure, and service-map routes must return `404`.

### SO-008 — Browser acceptance

Confirm the real Services, Infrastructure, and service-map surfaces display the temporary telemetry and
correct project context.

### SO-009 — Cleanup and regression gate

Remove temporary PostgreSQL control-plane fixtures/receiver artifacts as applicable, preserve volumes,
and run the complete `scripts/verify.ps1` release gate. Uniquely marked raw telemetry may remain as normal
ClickHouse data.

## 16. M6 final operational command

M6.5 should provide one repository-root PowerShell verifier following the established operational pattern,
for example:

```powershell
./scripts/verify-m6.ps1
```

Debug-only skip switches may exist, but final acceptance must run Compose recreation, browser confirmation,
and the complete release gate.

## 17. M6 stop condition

V1 M6 is complete only after the operational matrix, browser acceptance, cleanup, complete release gate,
closeout commit/push, and a clean:

```text
## main...origin/main
```

## M6.1 implementation-specific test file and commands

`backend/apps/telemetry/tests/test_service_catalog_api.py` tests the SC-001–SC-010 contracts, with
a live OTLP `@pytest.mark.integration` test for same-name metrics/logs/traces across two distinct
authenticated project keys. Run: `docker compose exec -T api /opt/venv/bin/python -m pytest
apps/telemetry/tests/test_service_catalog_api.py -v`, then `./scripts/verify.ps1`.
Before acceptance require runtime SQL against the current ClickHouse schema, a real foreign-project
`404` without a ClickHouse read, no schema/migration drift, and clean commit/push.

## M6.1 accepted evidence and M6.2 verification checkpoint

M6.1: 15 focused tests, real three-signal OTLP/tenant-isolation test, 150 total backend tests,
35 frontend tests and the complete release gate passed before commit `2c1b5a2` and clean push.

M6.2 candidate focused coverage must verify: an exact service/environment can be selected,
including an explicitly empty environment; the backend's window/cap/truncation fields are preserved;
empty, failed and truncated catalogs produce different messages; changes in project UUID must not
reuse another project's data; links into Metrics/Logs/Traces preserve project URL and disclose that
they are **not** prefiltered; no health, ownership, SLO or dependencies are manufactured.

Frontend test pass plus full `./scripts/verify.ps1` and a manual real-data browser visit with project
switching are mandatory acceptance. This document must not mark M6.2 delivered based on the patch alone.
