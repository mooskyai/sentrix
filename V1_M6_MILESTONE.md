# Sentrix V1 M6 — Service Catalog & Infrastructure Observability

## Pre-M6.3 UI refinement — committed; final acceptance pending

The shared right-side header selectors, conditional project navigation, compact spacing,
and accessible Services/Logs/trace-span drawers are implemented and pushed at
`a4bcb4c`. The final approved hierarchy uses one content card for
Services/Metrics/Logs/Traces/Settings and sibling cards for Overview/Dashboards/Alerts,
with no nested cards. This is a UI change, not M6.3. Visual approval has been
reported; the full release gate after the final UI correction passed on
2026-10-22 (170 backend and 50 frontend tests). M6.2 manual browser
acceptance has **not** been reported. See
`UI_DENSITY_AND_DRAWERS.md` and `M6_2_BROWSER_ACCEPTANCE.md`.

## M6.2 implementation checkpoint (pushed; manual browser acceptance open)

M6.2 code was pushed at `a0e7881`, with demo seeder at `4b34f3c`. The separate
membership-authorized Services detail API returns bounded metric names, recent errors
and observed trace IDs for exact service/environment and UTC window. The frontend handles
loading, valid empty results, errors and truncation and retains context on trace links.
General Metrics/Logs links remain unfiltered. The full release gate passed: 170 backend,
44 frontend, clean Ruff/mypy/Django/ClickHouse/TypeScript/build checks. Manual browser
acceptance is outstanding; see `M6_2_BROWSER_ACCEPTANCE.md`. M6.3 is blocked until then.

## 1. Goal

V1 M6 turns the telemetry already accepted and queried by Sentrix into a project-scoped service and
infrastructure view. The milestone must remain telemetry-derived: observed services, resources, and
relationships come from ClickHouse rows written through the existing OTLP boundary, while Django
continues to own authentication, tenant membership, and any future user-authored control-plane metadata.

M6 does not create a second telemetry store or a manually curated service registry. A service or
infrastructure resource appears only when the authorized project's bounded telemetry window contains
supporting evidence.

The core trust boundary remains unchanged:

```text
browser session
      |
      v
membership-scoped Project
      |
      | authorized organization_id + project_id
      v
bounded service/infrastructure query
      |
      v
ClickHouse metrics / logs / spans
```

Resource attributes, service names, Kubernetes names, trace IDs, and URL slugs are data. None of them
establish tenant authority.

## 2. Ordered delivery

### M6.1 — Service catalog query foundation

Add a tenant-safe read boundary that discovers observed services from existing metrics, logs, and spans.
The initial service identity is the exact pair `(service_name, environment)`. Empty environment remains
an explicit value; Sentrix does not guess one.

### M6.2 — Service catalog and service-detail workspace

Add the project Services workspace and a service-detail view backed only by M6.1/M6.2 APIs. Correlate
bounded activity across metrics, logs, and traces without creating a PostgreSQL copy of raw telemetry.

### M6.3 — Infrastructure and Kubernetes resource discovery

Discover supported host/Kubernetes resource dimensions from existing OpenTelemetry resource attributes
and expose a project Infrastructure workspace. This slice consumes telemetry only; it does not query the
Kubernetes API or introduce another collector protocol.

### M6.4 — Observed service map

Build a bounded project service map from real cross-service span parent/child relationships. Every edge
must be backed by returned spans from the same tenant and trace; missing parents or same-service
parentage must not become invented dependencies.

### M6.5 — Operational verification and closeout

Send real OTLP telemetry for multiple services with infrastructure attributes and one cross-service
trace, prove catalog/resource/map isolation, confirm the browser surfaces, clean temporary control-plane
fixtures, and run the complete repository release gate.

## 3. M6.1 service-catalog contract

The first service catalog API is:

```text
GET /api/v1/projects/{project_id}/services/catalog/
```

The request is session authenticated. Django resolves the route project through the current user's
membership before ClickHouse is opened. Unknown or foreign project UUIDs return `404` without a telemetry
query.

The catalog accepts a half-open `[start, end)` UTC window. When omitted, it defaults to the previous 24
hours; a single request may cover at most seven days. The response is bounded to 500 unique service
identities and reports truncation explicitly.

M6.1 discovers services from all three existing telemetry tables. A service identity is:

```text
service_name
+
environment
```

Rows with an empty `service_name` do not create anonymous catalog entries. Environment may be empty
because the existing ingestion contract allows telemetry without a deployment-environment attribute.
M6.1 does not reinterpret `service.namespace`, `service.instance.id`, Kubernetes namespace, hostname, or
arbitrary attributes as service identity.

For each returned identity the API may report only telemetry-backed observations such as:

```text
service_name
environment
first_seen
last_seen
metric_points
log_records
span_records
signals: metrics | logs | traces
```

Counts are bounded-window observations, not lifetime totals or billing records.

## 4. M6.1 ClickHouse rules

The query layer must:

- derive both `organization_id` and `project_id` from the authorized Django project;
- use typed parameters for tenant IDs and timestamps;
- preserve the half-open bounded window across all participating signal queries;
- use `timestamp` for metrics/logs and `start_time` for spans according to their existing schemas;
- return only aggregate catalog metadata, never arbitrary raw rows through the catalog endpoint;
- treat ClickHouse failure as HTTP `503`, not an empty catalog;
- close every ClickHouse client in success/failure paths;
- avoid a PostgreSQL service table, ClickHouse migration, projection, materialized view, TTL, or index
  until measured M6 behavior demonstrates a need.

Static `UNION ALL` or separately parameterized per-signal queries are acceptable. Caller-provided SQL,
dynamic table names, expression languages, and attribute predicates are not.

## 5. M6.1 acceptance

M6.1 is green only when:

- the session user must have membership in the route project before any ClickHouse access;
- an actual foreign project UUID returns `404` before the data plane is touched;
- catalog queries include authorized organization/project predicates for every signal;
- default and maximum windows are enforced with half-open semantics;
- metric-only, log-only, trace-only, and multi-signal services are discovered correctly;
- empty service names are excluded and empty environment remains explicit rather than fabricated;
- the same `(service_name, environment)` observed across signals merges into one catalog entry;
- first/last-seen and counts come only from rows inside the requested window;
- 500-entry bounding and explicit truncation are tested;
- dependency failure returns `503` and never masquerades as a healthy empty catalog;
- no PostgreSQL service model or ClickHouse schema optimization is introduced;
- focused tests and the complete repository release gate pass;
- README, architecture, coding, milestone, and testing documentation remain synchronized.

M6.2 must not begin until M6.1 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 6. M6.2 service workspace contract

M6.2 adds a real project Services surface. The list is populated from the service catalog and therefore
represents observed telemetry within the selected time window, not manually registered inventory.

The first service-detail read boundary may add a dedicated endpoint but must keep the same exact service
identity and tenant/time rules. It may expose bounded summaries needed by the UI, including signal
presence/counts, observed first/last timestamps, bounded metric names, recent error-log references, and
recent trace IDs. It must not invent a health score, SLO, owner, deployment, dependency, or canonical
resource attribute when the telemetry contract does not provide one.

The workspace must make the observation window visible. A service disappearing from the selected window
means "not observed in this window", not "deleted" or "down".

## 7. M6.2 navigation and correlation

Service detail may link into existing Metrics, Logs, and Traces surfaces. Such links carry only validated
filter/navigation data; the destination APIs still perform their own project-membership authorization.
A service page cannot turn its service name, trace ID, or browser route into tenant authority.

If a service detail introduces new exact filters to an existing M3/M4 API, those filters must be
implemented end-to-end with typed ClickHouse parameters and tests before the UI relies on them. The
browser must not filter a broader cross-service response locally and present it as server-isolated data.

## 8. M6.2 acceptance

M6.2 is green only when:

- the Services workspace is project-scoped and query keys include immutable project identity plus window;
- list/detail loading, healthy-empty, dependency-error, and truncated states are distinct;
- service identity and observation window are shown explicitly;
- metric/log/trace summaries are telemetry-backed and bounded;
- navigation to existing explorers preserves project context without bypassing backend authorization;
- no raw telemetry or discovered-service inventory is copied into PostgreSQL;
- the UI does not fabricate health, ownership, SLOs, deployments, or dependencies;
- browser tests cover project changes and stale-cache isolation;
- the complete release gate passes and documentation remains synchronized.

M6.3 must not begin until M6.2 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 9. M6.3 infrastructure discovery contract

M6.3 reads infrastructure identity from resource attributes already preserved by OTLP ingestion. Initial
recognized dimensions are:

```text
host.name
k8s.cluster.name
k8s.namespace.name
k8s.node.name
k8s.deployment.name
k8s.statefulset.name
k8s.daemonset.name
k8s.job.name
k8s.cronjob.name
k8s.pod.name
k8s.container.name
```

Support for a key means Sentrix can group and display values observed in the authorized project's bounded
telemetry. It does not mean Sentrix has contacted the Kubernetes API, validated that the object still
exists, or reconstructed the complete Kubernetes ownership graph.

The infrastructure API must use the same maximum seven-day window and explicit response bounds. Empty
or absent keys are omitted rather than replaced with placeholders that look like real resources.

## 10. M6.3 relationship honesty

Parent/containment relationships may be shown only when the same telemetry resource attributes provide
both sides of the relationship needed to support the edge. For example, a row containing both
`k8s.namespace.name` and `k8s.pod.name` can support an observed namespace/pod association. A namespace
name found on one unrelated row and a pod name found on another must not be joined merely because they
were seen in the same project.

M6.3 introduces no cluster credentials, Kubernetes API client, daemonset, agent, discovery controller, or
inventory database.

## 11. M6.3 acceptance

M6.3 is green only when:

- infrastructure queries are membership/project scoped before ClickHouse access;
- supported semantic-convention keys are extracted from existing resource attributes only;
- results are time bounded, size bounded, and explicitly telemetry-derived;
- an actual foreign project cannot discover resource names;
- missing attributes do not create fake hosts/clusters/namespaces/workloads/pods;
- displayed relationships require supporting co-observed attributes;
- no Kubernetes API access or new ingestion protocol is added;
- no PostgreSQL inventory copy or ClickHouse schema optimization is introduced;
- the Infrastructure workspace distinguishes not-observed from dependency failure;
- focused tests and the full release gate pass.

M6.4 must not begin until M6.3 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 12. M6.4 observed service-map contract

The service map is derived from stored spans. An edge exists only when Sentrix can join a child span to
its actual parent span inside the same authorized organization/project and trace, and the parent/child
service identities differ.

The initial edge direction is explicitly "observed parent span service -> child span service". It is not
claimed to be a network topology, Kubernetes service graph, critical path, or universal request direction.

Map requests use a half-open bounded window with the existing 1h/6h/24h/7d product ranges. V1 caps the
response to 100 service nodes and 250 distinct directed edges. Truncation is explicit.

Each edge may expose bounded observations such as:

```text
source service_name/environment
target service_name/environment
observed_span_pairs
first_seen
last_seen
```

No edge may be inferred from naming similarity, logs, metric labels, span links, missing parents, or
cross-project data.

## 13. M6.4 acceptance

M6.4 is green only when:

- the project is authorized before service-map ClickHouse work begins;
- parent/child joins include both organization and project identity plus trace/span identifiers;
- same-service parentage does not produce a cross-service edge;
- a missing parent produces no invented edge;
- identical service names in different environments remain distinct nodes;
- node/edge counts and time ranges are bounded with explicit truncation;
- foreign-project spans never influence a local service map even when trace/span IDs collide;
- UI labels the map as observed span relationships rather than guaranteed infrastructure topology;
- no graph database, ClickHouse projection/materialized view, or speculative dependency model is added;
- focused tests and the complete release gate pass.

M6.5 must not begin until M6.4 is green, committed, pushed, and `main` is aligned with `origin/main`.

## 14. M6.5 operational closeout

The final M6 verifier must use real OTLP telemetry through the public authenticated ingestion boundary.
A disposable project should emit at least two distinct services, infrastructure resource attributes, and
one trace containing a real cross-service parent/child relationship. The closeout then proves the new
service catalog, service detail, infrastructure discovery, and service-map APIs plus their browser
surfaces.

An actual foreign project fixture must remain non-discoverable through every new M6 read boundary.
Temporary PostgreSQL control-plane fixtures are cleaned while uniquely marked raw telemetry may remain in
ClickHouse as ordinary data, matching the earlier operational milestones.

## 15. M6 completion acceptance

V1 M6 is complete only when:

- M6.1-M6.4 focused contracts remain green;
- real OTLP telemetry discovers at least two services through the catalog;
- service detail correlates bounded data without copying telemetry into PostgreSQL;
- supported infrastructure attributes appear only from real resource telemetry;
- one real cross-service trace produces exactly the expected observed map edge;
- tenant isolation is proven with actual local/foreign project fixtures;
- Services, Infrastructure, and service-map browser flows are confirmed;
- temporary control-plane verification state is cleaned without deleting persistent volumes;
- the complete repository release gate passes;
- documentation describes the final M6 behavior;
- closeout is committed, pushed, and `git status -sb` shows `## main...origin/main`.

M6 intentionally does not include incidents, SLOs, Kubernetes API polling, cluster credentials,
automatic ownership/team assignment, arbitrary analytics/query languages, usage billing, SSO, or
speculative ClickHouse optimization. Those require separate later contracts.

## M6.1 implementation checkpoint — completed/pushed as `2c1b5a2`

First API: `GET /api/v1/projects/{project_id}/services/catalog/` (session only).
Code: `backend/apps/telemetry/service_catalog.py`, `service_catalog_views.py`, `query_urls.py`.
Query is a three-signal ClickHouse aggregate scoped to trusted tenant UUIDs and a half-open window;
identity is exact `(service_name, environment)` and empty service names are excluded. Default limit 100,
maximum 500, explicit `truncated`. No persistence/schema/UI changes.
M6.1 passed 15 focused tests plus the complete 150-backend/35-frontend release gate, then was
committed and pushed with clean `main` at `2c1b5a2`. M6.2 may begin from that baseline.

## M6.1 verified baseline and M6.2 implementation checkpoint

M6.1 closed on `2c1b5a2c18d1929b37ff0a55796eaceb41070592` with 15 focused service catalog tests,
150 total backend/35 frontend tests, all Ruff/mypy/Django/ClickHouse/frontend gates green and a clean
pushed `main`. This supersedes the historical "pending acceptance" notes above.

The M6.2 Services workspace is implemented at `a0e7881` and retrieves catalog counts
plus a **separate** authenticated service-detail API with bounded metric names, error logs
and trace-ID references. Links to Metrics/Logs do not silently prefilter; observed trace
links preserve project and window. There are no invented health or ownership assertions.
The optional demo fixture was pushed in `4b34f3c`. Both current code and full tests are
automatically verified on Windows/Docker (170 backend / 44 frontend) but the final manual
browser/project-switch walkthrough is not reported. M6.3 remains gated until it is.
