# Sentrix — Interface and Experience Design

## Experience direction — guided connection to investigation (2026-10-24)

See [ROADMAP.md](ROADMAP.md). Keep **Documentation** in the global sidebar;
start with choosing framework/runtime, one-time project key, safe local/Docker/
HTTPS exporter endpoint, copyable SDK config, real test signal, verified arrival
and a direct link to Services/Traces. Use understandable error/empty states;
do not show 'connected', healthy or inferred topology without evidence.

Current Laravel/Node/React/Next.js instructions are code-shipped guidance,
**not certified runtime integrations**. React is backend-observation-only:
never inject `VITE_*`/`NEXT_PUBLIC_*` telemetry write secrets. Detailed API
reference remains accessible by its direct URL but is hidden from navigation.
Preserve compact single-level cards, authorized project selectors and
accessible responsive controls. See `docs/FRAMEWORK_QUICKSTART.md`.

## Historical documentation UI proposal (implemented; operator review open)

The global sidebar includes a single Documentation link independent of project selection.
Inside, framework-choice buttons reveal only the selected Laravel/Node.js/React/Next.js recipe,
with readable copyable code and clear numbered steps. Do not add API reference to navigation;
retain its existing direct route. Keep the single-surface compact layout and accessible buttons.

## M6.3 Infrastructure — implementation candidate (not accepted)

Infrastructure is a project-scoped section visible only after valid organization/project
selection. Preserve right-aligned unlabeled header selectors, compact spacing and one content card
with unboxed toolbar/table. Show observed attribute sets with signal counts and timestamps;
distinguish loading, empty, error and truncated. Do not label resources healthy, running, deleted,
current inventory, or confirmed Kubernetes ownership. Mobile and keyboard acceptance remain
required.

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

## V1 M6.2 Services screen — code pushed; browser acceptance pending

The Services project section uses the existing sidebar and project switcher. A 1h/6h/24h/7d selector
and refresh anchor control a bounded M6.1 aggregate query. The screen displays the server-reported
catalog window, service name, exact environment (including empty), signals, counts, and last observed
UTC time. An Inspect action selects a service and displays first/last observations and signal counts.

The URL selection contains only the service name/environment; Django still authorizes all data reads.
Loading, healthy empty, error, truncation and selected-but-not-returned states must be distinct.
Links to the existing explorers preserve project context and are labelled as **not prefiltered**.
Never color-code counts as health or derive ownership, SLOs, deployments or dependencies.

### Pre-M6.3 flat workspace layout

The common `workspace-section` is an unbordered layout region. Do not add an
outer card around every Services/Metrics/Logs/Traces/Dashboards/Alerts/Settings
screen. Keep separate fact/alert panels only for meaningful content groups.
The Services inspection drawer contains flat detail content, not a second card.

Keep one clear page title and flat control bars/table surfaces. Use border-bottom
separators for overview facts, metric statistics and discrete alert/dashboard
items rather than nesting complete panels inside other panels.

### Pre-M6.3 card hierarchy correction

Use one content card for each data-heavy explorer (Services, Metrics, Logs,
Traces, Settings). Overview, Dashboards and Alerts instead render their
individual fact/data cards as siblings, without a shared enclosing card.
Toolbar rows, tables, plots and metric statistics inside a content card
remain visually flat. Do not remove all cards; avoid nested cards.

## Linked documentation in Settings

Show two inline links (Telemetry setup guide and API reference) near the API-key controls, including read-only roles. Linked pages use the shared app header and a single readable content surface; do not add a Documentation section to project navigation, nested panels, or a tab bar. Links must not include raw API keys in their URLs.
