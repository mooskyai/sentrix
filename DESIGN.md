# Sentrix — Interface and Experience Design

**Scope:** V1 M1–M5 implemented UI; future service/infrastructure design is proposed. For system architecture see `ARCHITECTURE.md`.

## 1. Product experience

Sentrix is an operational dashboard, not a marketing website. Favor information density, stable tenant context, direct interaction with raw observations, and explicit unavailable/error/empty states. The UI never authorizes access: Django enforces it.

## 2. Stack and design tokens

React 19 + TypeScript + React Router 7 + TanStack Query 5; Tailwind CSS 4 via `@tailwindcss/vite`. CSS-first product tokens are in `frontend/src/theme.css`; shared semantics in `frontend/src/styles.css`. The named design system is **Sentrix Spectrum** with compact sidebar/top bar, restrained teal primary controls, violet accent, legible soft text, and semantic success/warning/error colors. Never introduce arbitrary component-specific colors that defeat tokens, or lose keyboard focus visibility.

## 3. Navigation model

```text
/login (unauthenticated experience)
/ (authenticated overview)
/orgs/:organizationSlug/projects/:projectSlug
/orgs/:organizationSlug/projects/:projectSlug/:section
```

Implemented sections: `overview`, `metrics`, `logs`, `traces`, `dashboards`, `alerts`, `settings`. The organization/project picker is membership-scoped and section context is retained only for authorized projects. Unknown or foreign slugs render a nondisclosing unavailable state.

## 4. Screen contracts

| Surface | What is visible | What must not be implied |
| --- | --- | --- |
| Login | username/password, validation errors | credentials exposed in URL/logs |
| Overview | member orgs/projects, creation forms by role | foreign resources |
| Project overview | org, project name, immutable ID, role | synthetic telemetry |
| Metrics | catalog, scalar observed-point plot, raw table, exact filters | rates, averages, histogram-to-scalar conversion |
| Logs | bounded search, raw attributes, severity, correlation | invalid or all-zero IDs as navigable traces |
| Traces | exact trace ID and raw spans, parent relationships | fabricated waterfall/critical path |
| Dashboards | configured project panels reading metrics API | persisted metric copies |
| Alerts | rule form, current state, refresh, write controls by role | browser-run evaluator or implied notification cadence |
| Settings | machine API-key metadata, one-time creation secret | raw key cached or retrievable later |

M5 notification channels have API/worker support but **no dedicated channel-management browser screen**. Do not claim the Alerts workspace edits channels.

## 5. Component conventions

- Use `frontend/src/components/` and `frontend/src/api/resources.ts` for API-backed features.
- React Query keys include immutable `projectId` and all query-defining filters/time windows. Remount project-specific explorers when switching projects.
- Keep draft text filters separate from applied query state; refresh advances time anchors rather than fabricating new points.
- Expose loading, healthy-empty, dependency error, forbidden/unavailable, and truncated states distinctly.
- Confirmation precedes destructive actions; backend error text is not silently swallowed.
- Browser interpolates user strings as escaped text (never unsafe HTML). The UI may hide write controls but must handle backend 403.

## 6. Accessibility and responsive requirements

Keyboard-visible focus; associated form labels and descriptive messages; sufficient contrast on actual surfaces; state conveyed by copy/icon as well as color; compressed but not cramped table/panel layout; safe horizontal overflow on small screens. Test focus and error states with React Testing Library where relevant.

## 7. Planned M6 experience (not implemented)

Service list/detail and resource discovery must label findings as **observed within the selected window**, not authoritative inventory or health. Observed service edges require real cross-service spans; missing observations are not guaranteed disconnections. Use the existing project workspace and data/query boundaries; no new direct browser-to-ClickHouse path.

## 8. Design review on every slice

For every UI change update this file, the relevant PRD workflow, API contract, component tests, README, and `ProjectImplementation.md`. Review tenant-switch reset, role mode, focus, empty/error/truncation states, responsive handling, and actual browser smoke before commit.

## 8. M6 screen and interaction blueprint (planned; not deployed)

| Slice | Future user-facing behavior | Honest state contract |
| --- | --- | --- |
| M6.1 | No new route; tenant-safe query foundation only | UI must not imply discovery exists |
| M6.2 | Services list and per-service detail with links to existing Metrics/Logs/Traces | Label last observation and selected time window; show empty/error/truncation separately |
| M6.3 | Host/cluster/namespace/workload/pod resource facets where attributes exist | Missing attributes are **unknown**, not absent resources |
| M6.4 | Service relationship graph derived from matched parent-child spans | Label edges **observed span relationship**; never claim complete network topology |
| M6.5 | Browser confirmation of fresh real OTLP smoke signals | Verify actual values/relationships, not placeholder sample cards |

Tenant changes must invalidate M6 React Query keys, remount project-scoped detail views, and navigate only through the authorized workspace. Query controls require a bounded UTC time window, deterministic selection, meaningful accessible labels, capped result state, and explicit `503`/retry feedback. Do not introduce speculative Kubernetes status badges, critical-path calculations, or service ownership fields as though they are data-plane facts. See `V1_M6_MILESTONE.md` for staged rollout.
