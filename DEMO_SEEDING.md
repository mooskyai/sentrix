# Sentrix demo seeder (V1 M1–M6.2)

## Opt-in year-long data and independent nonmember account

Use `docker compose exec -T api /opt/venv/bin/python manage.py seed_demo_year --username admin --days 365 --create-nonmember`
for daily synthetic history across two reserved demo projects. The extra year
marker is resumable per project/signal/day. This command does **not** generate
a real SDK trace or prove tenant security. See [year-seed instructions](docs/DEMO_YEAR_SEED.md).

## Optional M7 UI seed expansion — synthetic, not Node SDK proof

Re-running `docker compose exec -T api /opt/venv/bin/python manage.py seed_demo --username admin` appends a `demo-node-express` / `integration` identity to the
**reserved synthetic primary demo project**. It creates bounded demo metrics,
one demo log and one independent HTTP `SERVER` span named `demo.node.checkout`
with a `sentrix.demo.synthetic=true` attribute. The secondary demo project does
not receive this identity. Use Services and Traces to exercise navigation,
empty/error states and time windows; the command does not create a real Node
process, change production project data or certify any real M7.3.2 trace.

The demo service is deliberately **not** named `m7-node-express-runtime` and
never has `sentrix.acceptance.run`. The missing real Express trace must still be
diagnosed through the real exporter, authenticated receiver and exact ClickHouse
read-back. Do not mark M7.3.2 accepted because a synthetic row is visible.

This is an **opt-in synthetic dataset for local development and browser walkthroughs**.
Implementation is pushed at `4b34f3c`; `manage.py seed_demo --username admin` completed on
the acceptance host and six focused plus 170 total backend tests and 44 frontend tests
passed with the full release gate. It is not customer telemetry, production readiness,
or proof of manual M6.2 browser acceptance. M6.3 infrastructure discovery, M6.4 service
map and M6.5 closeout are not implemented. Raw trace parentage is not a service-map UI.
See `M6_2_BROWSER_ACCEPTANCE.md` for browser steps and remaining evidence.

## Requirements and command (PowerShell / Docker Compose)

1. Start the existing Sentrix stack with `docker compose up -d` and apply migrations as usual.
2. Sign in with an **existing active user** (or create one using `docker compose exec -T api /opt/venv/bin/python manage.py createsuperuser`). The command never creates an account or sets a password.
3. Run from the repository root, replacing `YOUR_LOGIN` with that user's actual Django username:

```powershell
docker compose exec -T api /opt/venv/bin/python manage.py seed_demo --username YOUR_LOGIN
```

Then open `http://localhost:5173`, sign in normally, and select either of the two organizations labelled **Sentrix Demo**. The command prints their project IDs and one real stored trace ID for each project. It does **not** print any API key or password.

## What gets created

| V1 slice | Demo data |
| --- | --- |
| M1 | Two reserved demo organizations (`sentrix-demo-u<user_id>-primary` and `...-secondary`) with owner membership for that existing user; one project per organization |
| M2 | Authenticated OTLP/HTTP protobuf metrics, logs and traces written to ClickHouse; a permanently **revoked** demo exporter credential is visible in the primary project's API-key list |
| M3 | Numeric metric series (`demo.http.requests`, `demo.checkout.failures`, `demo.queue.depth`, `demo.http.latency_ms`, etc.) and four persisted dashboard panels |
| M4 | INFO/ERROR logs, correlated trace/span IDs, and a three-span distributed trace visible in the existing Logs and Traces explorers |
| M5 | One evaluation-backed firing alert, one OK alert, one disabled alert, and one **disabled** loopback webhook channel; **no outbound deliveries** |
| M6.1–M6.2 | Exact service/environment catalog (including staging and empty environment), observed signal counts, per-service metric names, recent error logs and navigable trace IDs |

The primary organization includes `demo-api/production`, `demo-checkout/production`, `demo-payments/production`, `demo-checkout/staging`, `demo-worker/(empty)`, `demo-batch/production` (around 3h old) and `demo-archive/production` (around 36h old). The secondary organization deliberately has `demo-checkout/production` with different observations, plus `demo-worker/staging`, so the browser can be checked for **project/organization switching without stale cached results**. Both organizations belong to the same user; this is *not* a foreign-user authorization test.

All records are synthetic and timestamped shortly before the command runs. Each successful run verifies the projects' observed service identities from the real catalog API. The seeder uses temporary project API keys only during ingest and deletes those credentials even on ingestion failure. The demo notification channel remains disabled, so alert evaluation never sends a demo webhook. A marker `sentrix.demo.seed` is attached to OTLP attributes to distinguish the generated records.

## Behavior and limitations

- **Re-run:** demo PostgreSQL organizations, memberships, projects, panels, rules and the disabled channel are reused. Another **append-only** OTLP telemetry batch is inserted on each run; signal counts increase accordingly. It does not truncate or remove any ClickHouse table or volume. Most observations are recent, with additional 3h and 36h observations to exercise the 6h/24h and 7d window selectors.
- **No destructive reset:** this command has no deletion mode. To remove demo records later, use an independently reviewed, demo-ID-scoped cleanup procedure, not `docker compose down -v`.
- **Safe isolation:** all writes are restricted to deterministic reserved demo organization slugs for the chosen user; the command refuses to take ownership of an existing colliding organization/project. This is not suitable for production databases.
- **Operational acceptance:** the generated fixture does not replace real, externally produced OTLP data, a foreign-user tenant-isolation test, or manual browser verification. Record those separately before marking M6.2 fully accepted.
- **Feature limits:** it seeds only features already implemented through M6.2; it does not fabricate infrastructure inventory, health, SLOs, deployment information or a service map.

## Focused checks

```powershell
docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_seed_demo.py -v
.\scripts\verify.ps1
```

The focused tests cover protobuf fixture identity and span correlation, control-plane reuse, safe disabled notifications, missing-user refusal and live three-signal OTLP persistence. If seeding fails, check `docker compose ps`, run `docker compose exec -T api /opt/venv/bin/python manage.py clickhouse_schema --check` and consult `Debugging.md`. Never paste credentials into debugging output.
