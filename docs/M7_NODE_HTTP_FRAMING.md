# M7.3.2 — Node OTLP HTTP framing investigation and ASGI correction

## Confirmed direct SDK fix (2026-10-26)

The real Node SDK transmitted chunked OTLP protobuf with no Content-Length.
After API recreation on Uvicorn ASGI, **unaltered direct** `probe.cjs`
produced a span that independent project-key-scoped ClickHouse read-back
verified (run `ddbaab4290524f2092254fb23ff01613`, trace
`2f06c0b95492feea6379d231993c5b5d`). This resolves the local direct
SDK persistence failure evidenced under the WSGI development server.
The rebuilt full gate passed 277 backend and 103 frontend tests; Node fixture
4/4 and npm audit with zero vulnerabilities. Browser/security/revocation and
commit/CI still block full M7.3.2 acceptance. See
[M7.3.2 closeout record](M7_NODE_CLOSEOUT_EVIDENCE.md).

**Candidate implementation, not accepted.** The real Express SDK generated
one nested OTLP/protobuf span. An in-memory loopback relay forwarded that
identical body with `Content-Length` set and the independent ClickHouse
read-back passed (run `41e07e34adc641ce822d39649914ccac`, trace
`a42429c7f2c9d8209ee9919057646e76`). The **direct** Node exporter
returned HTTP 200 but no matching persisted row on multiple attempts,
including run `3abe18c8d7594ac6b478ef66e5011b75`.

## Suspected cause and correction

The local Compose API used `python manage.py runserver`, a WSGI server.
Django's WSGI request handling cannot reliably read HTTP/1.1 chunked
bodies that lack a Content-Length. A protobuf decode of zero bytes is a
valid *empty* message, so the old API could acknowledge an SDK POST while
persisting no span. The correction changes local Docker API serving to
`uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload`.
Uvicorn is already pinned in backend dependencies; `config/asgi.py` exists.
The Dockerfile's default executable is also ASGI (without dev reload).
In addition, an empty request presented with chunked framing fails closed
with HTTP 400. This is not a new ingest protocol, schema, dependency or
permission grant. Do not run Django's WSGI `runserver` for OTLP acceptance.

## Validate request framing safely

From repository root (Node fixture dependencies already installed):

```powershell
node .\integrations\m7-node-express\inspect-framing.cjs
```

The fixture uses an internal **fake key** and loopback-only HTTP listener.
It shows Content-Length present or absent, Transfer-Encoding and protobuf
byte count; no raw protobuf, Authorization header or project key is printed.
The hypothesis is supported if the direct SDK uses chunked requests without
Content-Length. If not, stop and investigate another difference before
claiming this as root cause.

## Recreate only API container; preserve databases

```powershell
Set-Location 'C:\working\Projects\Python\sentrix'
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration invalid' }
docker compose up -d --no-deps --force-recreate api
if ($LASTEXITCODE -ne 0) { throw 'API recreation failed' }
docker compose ps api
docker compose logs --tail 25 api
```

Use API logs to confirm it is serving with **Uvicorn**, not `runserver`.
If the API image was not built with uvicorn installed, use
`docker compose up -d --build --no-deps api` instead; this does not remove
PostgreSQL/ClickHouse volumes. Never use `docker compose down -v`.

## Direct SDK acceptance (not the relay)

With the temporary project `telemetry:write` key passed through masked
stdin, run `integrations/m7-node-express/probe.cjs --base-url
http://localhost:8000`. Preserve its run, trace and UTC timestamp.
Re-enter the **same** key on stdin to `python -m scripts.m7_node_readback`
inside `docker compose exec -T api`, supplying `--run-id`, `--trace-id`,
`--time`. Both commands must succeed. The read-back derives tenant IDs
from authenticated Postgres key and matches one exact bounded ClickHouse
SERVER span. HTTP 200 alone does not pass this gate. Re-run `npm test` and
`./scripts/verify.ps1` and record outputs.

Browser Services/Traces, a separate foreign-user 404, invalid/expired/
revoked-key behavior, credential revocation, cleanup, reviewed lockfile,
commit/push and CI are **separately pending**. Keep synthetic
`demo-node-express` and real `m7-node-express-runtime` evidence distinct.
