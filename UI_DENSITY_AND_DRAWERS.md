# Sentrix UI refinement — pre-M6.3 acceptance

Baseline: `8b8d3fd5cdd3304a5919aa7ddafdbce682fb8f86` (pushed clean main).
This is a presentation/navigation slice and does not introduce M6.3 infrastructure features.

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
