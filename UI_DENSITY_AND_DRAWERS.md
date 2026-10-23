# Sentrix UI refinement — pre-M6.3 acceptance

Baseline: `8b8d3fd5cdd3304a5919aa7ddafdbce682fb8f86` (pushed clean main).
This is a presentation/navigation slice and does not introduce M6.3 infrastructure features.
The final single-level card correction was pushed at `a4bcb4c` and visually
approved. The full Windows/Docker release gate passed on 2026-10-22 with
170 backend and 50 frontend tests. Manual M6.2 browser acceptance remains open.
Historical flat-layout proposals
below are superseded by "Card hierarchy correction — one surface, not zero".

## Contract

1. Lower vertical density in shell, headings, cards, forms and explorer lists; preserve readable text and visible focus.
2. A single organization/project selector pair lives in the authenticated header (including the management overview). The chosen validated IDs remain in session storage for the signed-in user and in the workspace route when navigating to project pages. Project selection never grants authorization; server returned memberships/projects remain authoritative. On organization change, clear the project and navigate to management overview. Changing projects keeps a valid explorer section where possible.
3. Sidebar always shows Organizations & projects. Show project-scoped Overview/Services/Metrics/Logs/Traces/Dashboards/Alerts/Settings **only** when both selected IDs resolve to one accessible workspace. Show no disabled placeholder links.
4. Services detail, log record inspection and trace-span inspection appear in a right-side modal drawer on desktop and a full-width drawer on small viewports. The drawer exposes an accessible title, focuses on open, closes via Escape, backdrop or Close, traps Tab and restores focus. Link navigation closes it by leaving its owner route.
5. Keep log/trace selectors and data queries on their existing project-scoped routes; do not duplicate queries or infer missing data.

## Acceptance (Windows / Docker)

- Start with cleared session storage or a new browser session: only management navigation visible; both header selectors show placeholders.
- Select an organization: project choices filter to that organization and project links remain hidden until a project is chosen.
- Select a project: sidebar links appear. Navigate Logs > Traces > Services; header selection stays constant. Refresh and return to overview: selection stays for this user/session.
- Switch organization: project is cleared, sidebar project links vanish, and previous project data is not shown. Select a new project; data/routes reflect new tenant only.
- Inspect a service, log and individual span: right drawer opens, data remains sourced from the existing authorized response, Esc/backdrop/Close dismiss it, focus returns, no background scroll, and no broad accidental page navigation. On narrow width drawer fills viewport.
- Run `docker compose exec -T web npm run lint`, `typecheck`, `test -- --run`, `build`; then `./scripts/verify.ps1`. Note observed pass/fail results before committing. Repeat manual browser checks on the seeded Online Store and Isolated Store projects.

### Header alignment refinement

On desktop, the two dropdowns share the right side of the global top bar with the signed-in account and Sign out. No visible Organization or Project labels appear above the dropdowns; their accessible `aria-label` names remain available. Narrow screens keep the selectors usable with responsive wrapping.

### Flat project pages (no nested container cards)

The shared project page is a semantic, unbordered layout section, **not** an outer
`panel` around each explorer. Remove the redundant per-section eyebrow. Overview's
organization/project/access fact cards and independent metric, log, alert, and
settings groupings remain where they distinguish actual data. Service detail in
its right drawer also uses a flat layout rather than an extra bordered card.

Browser acceptance: inspect each project route (Overview, Services, Metrics,
Logs, Traces, Dashboards, Alerts, Settings), verify no single oversized outer
card wraps its content, and confirm contained lists, controls, small information
cards, loading/error/empty states and drawer interactions remain legible.

### Data-first page presentation (follow-up to the flat container change)

Each project screen now has one route title (the workspace name is already visible in
header selectors). Filter/control rows sit on the page without their own card chrome.
Table rows and column headings remain readable, but the data table has no enclosing
card border. Overview facts, metrics summary values, individual alert rules and
Dashboard charts use whitespace and subtle rules rather than nested boxed surfaces.
Notices/errors and real input focus styles retain their semantics. Services detail
remains in a right-hand drawer. This is a visual-only refinement; project scoping,
query payloads, authentication, and data semantics are unchanged.

Browser acceptance: compare Services/Logs/Metrics/Traces/Alerts/Dashboards/Settings,
including empty/error states and mobile widths. No duplicated page title or nested
filter/table cards. The project selector and sign-out remain in the global header.

### Card hierarchy correction — one surface, not zero

The data-first follow-up was too aggressive: it removed all meaningful cards.
The corrected layout distinguishes two patterns:

- Services, Metrics, Logs, Traces and Settings get **one** content card,
  containing unboxed filters, data tables and summaries.
- Overview, Dashboards and Alerts use **sibling** fact, dashboard or alert
  cards directly on the page, without an enclosing workspace card.

No screen should display a bordered card inside another bordered card.
Restore clear section boundaries, compact spacing and subtle table rows. The
shared header selectors and right-side inspection drawers are unchanged.
Test this visually at desktop/mobile widths, then run the full release gate.
