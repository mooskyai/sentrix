# Sentrix one-year synthetic demo seed (local development only)

This is **synthetic sample data**, not customer telemetry, a real Express/Django
SDK export, or evidence that M7.3.2 browser/security acceptance has passed.

## One command (PowerShell at repository root)

```powershell
docker compose up -d
docker compose exec -T api /opt/venv/bin/python manage.py seed_demo_year `
    --username admin --days 365 --create-nonmember
```

If `admin` does not exist, run `docker compose exec api /opt/venv/bin/python
manage.py createsuperuser` first. This never recreates a deleted account or
changes its password. Run `docker compose exec -T api /opt/venv/bin/python
manage.py seed_demo --username admin` if you only need recent data.

This command uses the existing `seed_demo` to create/reuse **two reserved demo
organizations** with one project each, panels, alert rules and a disabled
notification channel. It then adds one synthetic daily collection of metrics,
logs and traces across the **latest 365 UTC calendar days**, including today,
with a weekday/weekend rhythm and separate primary/secondary project telemetry.
The primary project also includes `demo-node-express` / `integration` synthetic
HTTP SERVER spans. Their names and `sentrix.demo.seed` markers distinguish them
from actual `m7-node-express-runtime` SDK traces.

The final optional switch `--create-nonmember` creates/reuses an active ordinary
user **`m732-nonmember`** with no organization memberships, no staff/superuser
privileges, and an unusable password for API isolation checks. It does not
create a usable browser credential. If you need to test login in a separate
browser session, set a private password interactively using:

```powershell
docker compose exec api /opt/venv/bin/python manage.py changepassword m732-nonmember
```

Do **not** add that user to either demo organization before the authorization
test; `scripts.m7_node_auth_smoke` refuses to treat a member as a foreign user.
Use its exact current project/run/trace IDs from a **real** Node exporter test.
The seed's generated synthetic trace IDs cannot substitute for that evidence.

## Controls, idempotency and scaling

- `--days` accepts **1–365** and defaults to 365. Dry-runs are not supported;
  this opt-in command makes real local development writes.
- Historical observations are posted to the **existing authenticated OTLP HTTP
  views** in at most seven-day batches, using short-lived project credentials
  which are deleted in `finally`, even after failed ingestion.
- Each day has a stable history marker (`sentrix-history-v1:YYYY-MM-DD`),
  scoped by organization/project. Before writing, the command reads stored
  markers for **each** signal. A rerun skips already persisted signal/day
  combinations; interrupted or partial batches can be resumed without normally
  replaying successfully stored signals. Historical trace IDs, span IDs and
  correlated error logs are deterministic for a project/day.
- Recent `seed_demo` data **is appended every time** the wrapper is run; only
  the additional *year-history* is deduplicated. Avoid running concurrent
  seeders for the same owner/project.
- No ClickHouse tables, volumes, projects, users, or alert rules are deleted;
  no webhook notifications are sent by the disabled demo channel.
- Expect thousands of telemetry rows and up to roughly 318 OTLP HTTP requests
  for 365 days (two projects, three signals, seven-day batches). Plan for
  ClickHouse storage and processing time. Check the final per-project
  `days_written` / `otlp_requests` output and the terminal verified message.
- **Existing UI ranges are only 1h/6h/24h/7d** and some API endpoints limit
  requests to seven days. Creating historical data does *not* add a one-year
  chart selector or authorize queries outside those bounded windows. Use
  supported 7-day windows when inspecting older slices.
- The acceptance security smoke requires an *existing authenticated owner and
  a separate nonmember*. Creating the account alone does not demonstrate 404;
  run the smoke and browser checks separately. Key revocation/HTTP 401 also
  remain separate.

For quicker local smoke testing:

```powershell
docker compose exec -T api /opt/venv/bin/python manage.py seed_demo_year `
    --username admin --days 14 --create-nonmember
```

Keep the source, tests, and this runbook together in the milestone patch; run
`./scripts/verify.ps1` after applying changes. Do not claim that a full-year
seed itself certifies real SDK integrations, project security, or M7 sign-off.
