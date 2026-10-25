# Sentrix M6.3 Infrastructure — operational and browser acceptance

## Optional co-observed resource smoke — still NOT RUN

`docs/M6_ACCEPTANCE_PRODUCER.md` describes an OTLP producer that sends unique
host, cluster, namespace, pod and container **attributes** together on each
resource. Manually verify actual values and signal counts in Infrastructure;
these are controlled labels, not proof of a live Kubernetes cluster.
Independent foreign-user denial and IR-001–IR-008 operator records remain open.

## Documentation sidebar follow-up (not accepted)

For the separate framework onboarding patch, confirm the Documentation sidebar entry works
without selecting a project; Laravel, Node.js, React and Next.js guides switch correctly,
and copy controls work. Project Settings retains setup instructions only, while the API
reference has no visible navigation link. Confirm the React guide warns against public
keys and the Next.js recipe runs only in the Node server runtime. Verify desktop/mobile,
keyboard controls and full release gate. Record actual results before acceptance.

**Status: NOT RUN.** Code/test/docs candidate only. Do not mark M6.3 accepted from a patch, synthetic seeding, or unit tests. M6.2's separate manual browser gate in `M6_2_BROWSER_ACCEPTANCE.md` remains open.

## Required IR-001 through IR-008 verification

| Case | Evidence required | Result |
| --- | --- | --- |
| IR-001 | Authenticated project resolution precedes ClickHouse, each source has trusted org/project predicate | Not run |
| IR-002 | Host and documented k8s.* attributes exactly match fresh OTLP resource attributes; no arbitrary keys | Not run |
| IR-003 | Missing/empty fields do not materialize placeholder inventory | Not run |
| IR-004 | Namespace/pod/etc. shown together only when co-observed on a single resource, not joined across sources | Not run |
| IR-005 | Default 24h, maximum 7d, 1–500 limit, 500+1 truncation and resource query budgets | Not run |
| IR-006 | Foreign user/project with stored infrastructure attributes yields 404 without query | Not run |
| IR-007 | No K8s API, credentials, collectors, schema migrations, inventory copies or background polling | Not run |
| IR-008 | Full `scripts/verify.ps1` release gate and prior feature regressions | Not run |

## Operator workflow

1. Start Docker Compose without deleting volumes: `docker compose up -d`.
2. Run focused backend tests including the real authenticated-OTLP/ClickHouse integration: `docker compose exec -T api /opt/venv/bin/python -m pytest apps/telemetry/tests/test_infrastructure_api.py -v`.
3. Sign into the first-party browser at `http://localhost:5173`. Use a project for which the OTLP integration sent known unique host, cluster, namespace, pod and container values, or send a separate genuine producer payload through a temporary project credential. Do not paste credentials in acceptance notes.
4. Select the project, open **Infrastructure**, and observe only the exact resource attributes that were ingested. Check metrics/logs/spans counts, timestamps, visible truncation when present, and the empty state in a time window without matching data. Absence must be described as *not observed*, not deleted/down.
5. Switch to a second authorized project and confirm no previous values remain. Use a separate account without membership in a populated foreign project, verify that the foreign API route is 404.
6. Check desktop and mobile layouts, right-side header selectors, conditional navigation, single-level content card (no nested cards), and keyboard usability. Run full `./scripts/verify.ps1` and record its output.
7. Record date/operator, exact code SHA, identifiers of observed fixtures (not secrets), real responses and browser observations, failures/truncation, and the acceptance decision. Commit/push closeout documentation only after real success.

- Operator/date: **Not recorded**
- Tested Git SHA: **Not recorded**
- Real OTLP host/cluster/namespace/pod/container observations: **Not recorded**
- Foreign-user denial: **Not recorded**
- Browser/UX result: **Not recorded**
- Focused/full release gate output: **Not recorded**
- Acceptance: **OPEN; do not start M6.4**
