# Sentrix M6.2 browser acceptance — operator checklist

**Status: NOT YET REPORTED.** M6.2 code was pushed at `a0e7881`; the optional seeder
was pushed at `4b34f3c`. Automated checks passed (170 backend, 44 frontend tests,
Ruff, mypy, Django, ClickHouse, TypeScript, Vite). This checklist requires an actual
operator in a browser, using the running Sentrix stack. Do not mark any item "passed"
until you have seen it. The demo records are synthetic and not a substitute for a
separately sourced external-OTLP operational smoke.

## Prerequisites

1. Before applying this documentation patch, verify clean `main...origin/main` at `4b34f3c`.
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

A trace ID reported by one example run was `cff76f1956e74b20baa7d21fe750679a`
(Online Store). On repeated seed runs, prefer the newly printed trace ID. Do not use
`git status` or a passing unit test as evidence that an operator visited these screens.

## Acceptance record

Fill this in **after** actual verification, then commit the documentation update:

- Operator/date (UTC or local zone): **Not recorded**
- Repository commit tested: `4b34f3c926b75ce997a2e07f8c15520556624ba8`
- Browser route/project tested: **Not recorded**
- Screens and trace-link observed results: **Not recorded**
- Empty, error, truncation and tenant-switch notes: **Not recorded**
- External producer proof (if claimed): **Not recorded**
- Deviations/screenshots/bugs: **Not recorded**
- Decision: **M6.2 browser gate remains open**

Do not proceed to M6.3 until required checks are recorded, documentation is updated,
all changed files pass `./scripts/verify.ps1`, and the commit is pushed with clean `main`.
