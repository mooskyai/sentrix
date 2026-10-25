# Sentrix M6.2 browser acceptance — operator checklist

## Optional fresh OTLP run identifier (not acceptance evidence by itself)

For a fresh trace/metric/log set, execute the separate-process producer using
`docs/M6_ACCEPTANCE_PRODUCER.md`, record its nonsecret run ID and time, then
verify actual received records in the browser. This script's controlled
fixtures do **not** replace external instrumented application evidence, real
foreign-user denial, visual inspection or manually observed error states.
All unchecked cases below remain **Not run**.

**Status: AUTOMATED GATE PASSED; MANUAL BROWSER ACCEPTANCE OPEN.**
M6.2 code was pushed at `a0e7881`, the seeder at `4b34f3c`, and the
approved UI at `a4bcb4c`. The final UI `scripts/verify.ps1` run passed
on 2026-10-22: 170 backend tests (one warning), 50 frontend tests,
Ruff, mypy, Django, ClickHouse, ESLint, TypeScript and Vite.
The documentation-only follow-up was pushed at `fb36906`.
This checklist requires an actual
operator in a browser, using the running Sentrix stack. Do not mark any item "passed"
until you have seen it. The demo records are synthetic and not a substitute for a
separately sourced external-OTLP operational smoke.

## Prerequisites

1. Verify `main` is clean and matches `origin/main`. The documentation-only correction was pushed at `fb36906230c31ff6b7eccba03ec45c8bbe384379`; if GitHub has advanced, rebaseline rather than resetting legitimate work.
2. Run `docker compose up -d`, then sign in at `http://localhost:5173` as an existing user.
3. If no demo services remain in the last-hour window, run the **append-only** fixture once:

   ```powershell
   docker compose exec -T api /opt/venv/bin/python manage.py seed_demo --username admin
   ```

   This reuses two reserved organizations/projects and adds a new set of synthetic
   observations. It does not purge any telemetry. Record the printed trace IDs.

The original seeder's primary project is `sentrix-demo-u1-primary/online-store`
(`07e54c2a-7cb5-4ff1-8c50-09f7a3a4fc4d`) and the secondary is
`sentrix-demo-u1-secondary/isolated-store` (`2f3b67c1-4ba5-4423-ad90-29641ac41ec1`).
These are **only examples** from a particular local run: use the slugs/IDs reported by
**your** current seed command if they differ. Both organizations belong to the same
user; switching them tests browser/project query isolation, not a foreign-user denial.

## Browser walkthrough (record actual result)

| Check | Expected observable result | Result / notes |
| --- | --- | --- |
| Services list | In Online Store, Services shows `demo-api`, `demo-checkout`, and other observed names with actual signal counts in the 1h window | Not run |
| Service detail | Inspect `demo-checkout` / `production`: actual metric names, error-log references and trace IDs, not inferred health | Not run |
| Empty environment | `demo-worker` / `(empty)` is separately selectable and accurately labeled | Not run |
| Trace navigation | Open an observed trace-ID link: Traces stays under Online Store and uses the selected time window | Not run |
| Metrics / Logs | Existing explorers show seeded samples; generic service links do not falsely claim pre-applied filters | Not run |
| Dashboards / Alerts | Persisted demo panels render observed points; firing/OK/disabled demo rules are visible | Not run |
| Time-range selection | 1h has recent services, 6h includes `demo-batch`, 7d includes `demo-archive` when inside their seeded windows | Not run |
| Project switching | Isolated Store shows its own `demo-checkout` and `demo-worker/staging`; Online Store-only rows/detail never remain as active data | Not run |
| No-data / error / truncation | Validate visible healthy empty, error and truncation states where you can produce them without changing production data; automated tests already cover their logic | Not run |
| Header and project navigation | Select organization and project from unlabeled right-side header controls; project navigation is hidden without both valid selections | Not run |
| Inspection drawers | Open service, log and trace-span details; check right-side desktop/mobile width, Escape/backdrop/Close, focus return and no stale project detail | Not run |
| Approved cards and responsive layout | Confirm one content card for Services/Metrics/Logs/Traces/Settings, independent sibling cards for Overview/Dashboards/Alerts, no nested cards, usable at mobile width | Not run |
| Foreign-user access (separate from project switching) | As a session user with no membership in a telemetry-containing foreign project, verify project routes return 404; do not count two projects of the same user as this proof | Not run |

A trace ID reported by one example run was `cff76f1956e74b20baa7d21fe750679a`
(Online Store). On repeated seed runs, prefer the newly printed trace ID. Do not use
`git status` or a passing unit test as evidence that an operator visited these screens.

## Acceptance record

Fill this in **after** actual verification, then commit the documentation update:

- Operator/date (UTC or local zone): **Not recorded**
- Repository UI commit tested: `a4bcb4c4274fde5b5199a973f46060c375c4286b`
- Final UI `./scripts/verify.ps1` command/result/date: **Passed 2026-10-22; 170 backend, 50 frontend, all release checks green**
- Browser route/project tested: **Not recorded**
- Screens and trace-link observed results: **Not recorded**
- Empty, error, truncation and tenant-switch notes: **Not recorded**
- Header/sidebar, drawer keyboard/focus and responsive-card notes: **Not recorded**
- Real foreign-user/foreign-project proof (session, expected 404, no secrets): **Not recorded**
- External producer proof (if claimed): **Not recorded**
- Deviations/screenshots/bugs: **Not recorded**
- Decision: **M6.2 browser gate remains open**

Do not proceed to M6.3 until required checks are recorded, documentation is updated,
all changed files pass `./scripts/verify.ps1`, and the commit is pushed with clean `main`.
