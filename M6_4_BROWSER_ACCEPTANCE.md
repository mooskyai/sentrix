# Sentrix M6.4 — Observed service relationships operator acceptance

> **Cross-milestone checklist:**
> [MILESTONE_ACCEPTANCE_CHECKLIST.md](MILESTONE_ACCEPTANCE_CHECKLIST.md)
> indexes this operator gate and the common evidence template. This
> browser acceptance record remains authoritative; no previously
> unrun check is accepted by the master document.

## Optional three-service OTLP relationship smoke — still NOT RUN

Run `backend/scripts/m6_acceptance_smoke.py` as described in
`docs/M6_ACCEPTANCE_PRODUCER.md`. Its three explicit span IDs create exactly
two trace-proven directed edges in the fresh run. Record the run/trace IDs,
actual browser view, time window, project switch, deep links and empty/error
states; **HTTP 200 or pytest do not prove browser acceptance**. Do not close
SM-001–SM-008 or the separate M6.2/M6.3 gates without operator evidence.

## Global header selection regression — added after M6.4 commit, NOT RUN

With two authorized organizations/projects and a real browser, verify initial
auto-selection, persisted manual project selection after reload, automatic
first-project selection when switching organization, and stale localStorage
flag/recovery after removing access to the saved choice. A foreign/unknown
workspace deep link must remain unavailable rather than being rerouted to a
different project. Check fresh sign-in, sign-out/in, narrow viewport and
keyboard controls; record actual operator/date/SHA before marking complete.
This check does not close any previously outstanding M6 manual acceptance.

**Status: NOT RUN.** M6.2 and M6.3 manual browser acceptance are still open and
must be completed before this slice can be accepted. Candidate patch baseline:
`8337cc14d17bc76413d5a6c9cd5418020163a737`.

## Required evidence

| Case | Live requirement | Result |
| --- | --- | --- |
| SM-001 | Readable project membership precedes every ClickHouse query; foreign/unknown project 404 | Not run |
| SM-002 | Send real OTLP/HTTP protobuf with two services, same trace and explicit parent span; observe exactly one directed link | Not run |
| SM-003 | A separate trace sharing a span ID, an orphan, same-service child, and ambiguous IDs create no edges | Not run |
| SM-004 | Exact environments, sample trace navigation, UTC time window and current selected project preserved | Not run |
| SM-005 | Empty, loading, 503 and both result/scan truncation visible; absence does not imply downtime | Not run |
| SM-006 | Project switching, foreign-user isolation, browser desktop/mobile and keyboard controls | Not run |
| SM-007 | No new ClickHouse tables, graph cache, background jobs, Kubernetes/collector APIs or secret leakage | Not run |
| SM-008 | Focused backend/frontend suites and complete `scripts/verify.ps1` passed; GitHub CI green | Not run |

## Operator steps

1. Verify M6.2 and M6.3 separately; retain their acceptance records.
2. Start existing Compose dependencies without destroying volumes: `docker compose up -d`.
3. Create a temporary project credential securely, send genuine parent/child OTLP spans from two services with a unique trace ID; never paste credentials into this document.
4. In Services choose a window containing the producer trace and click **Show observed relationships**. Confirm direction, exact environment, count and sample trace link. Switch project and verify absence without a leak.
5. Repeat with missing parent/cross-trace/same-service cases and an observation window with no matching spans. Verify no invented topology or health.
6. Prove `404` for a separate unauthorized account and `503` when the query dependency is unavailable; check desktop/mobile and keyboard behavior.
7. Run focused tests and `./scripts/verify.ps1`; check hosted GitHub CI. Record final SHAs and real outcomes, then commit/push closeout docs separately.

- Operator/date: **Not recorded**
- Tested Git SHA: **Not recorded**
- Real trace/service/environment evidence IDs (no secrets): **Not recorded**
- Foreign-user denial and error/empty/truncation: **Not recorded**
- Browser/mobile/keyboard observations: **Not recorded**
- Focused/full gate and GitHub CI: **Not recorded**
- Acceptance: **OPEN — implementation candidate only**
