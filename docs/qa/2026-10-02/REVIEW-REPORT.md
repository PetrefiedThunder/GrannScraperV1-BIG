# Independent QA evidence review

PR: opened by orchestrator

CI status: pending at time of writing

## Review outcome

**PASS for QA evidence handoff. No remaining QA-package blocker. This is not approval to release the product.** The confirmed product defects and pre-existing failing suite remain unchanged. All changes stay uncommitted on the required branch for the orchestrator.

## Source review conclusion

The highest-impact lifecycle findings are supported by source and isolated tests. API standard execution binds `ScraperEngine` as a local variable only in incremental/concurrent branches, then accesses it unbound in the standard branch (`scraper/api/rest_server.py:241`, `:267`, `:287`). Concurrent idle workers can never all exit when active work reaches zero because the exit condition requires one active worker (`scraper/core/concurrent_engine.py:93`, `:216`). These defects block useful work before export and justify prioritizing execution reliability.

The existing baseline is already red: 140 passed, 11 failed, 18 setup errors, as recorded in `artifacts/backend-baseline-suite-d284977e.txt`. New strict expected failures preserve desired behavior without disguising the pre-existing baseline failures. Do not claim the full suite or CI is green.

## Evidence and severity guardrails

| Topic | Review assessment | Report constraint |
|---|---|---|
| Unauthenticated API | High risk when network reachable; `run_server` defaults to all interfaces at `scraper/api/rest_server.py:624`, and job reads/deletes/runs have no mounted auth dependency. | README explicitly calls the project a single-node toolkit and puts RBAC/multi-tenant hardening on the roadmap. Avoid claiming a demonstrated cross-tenant breach or regression from an existing tenant model. |
| Arbitrary URL fetching | The `/api/v1/analyze` request directly reaches `StaticFetcher.fetch` at `scraper/api/rest_server.py:380-383`; private-target acceptance is a meaningful server boundary defect. | Raw URLs are normal in a local scraping SDK. Report the hosted/API threat boundary and stubbed proof; no real internal host or metadata service was contacted. |
| Export path containment | `filename_template`, `job_name` and `base_path` flow into filesystem paths (`scraper/export/export_manager.py:54-61`, `:100-107`). | Direct-library temporary-file proof establishes missing containment. Do not claim successful unauthenticated end-to-end arbitrary file overwrite through an API execution path currently blocked by execution defects. |
| Auth token logging | Rate limiting logs its `key` at `scraper/security/auth.py:317`; `verify_api_key` passes the raw token at `:383-385`. | Latent risk if this currently unmounted dependency is integrated. A code sink is not proof of an actual exposed credential. Never put a real value into the report. |
| Coverage increase | Coverage includes statements/branches traversed by expected-failure tests. | Improved coverage is additional observation, not a quality or correctness score. Preserve the same denominator and list the baseline failures. |
| Frontend/UX mocks | Fixture states are appropriate for offline interaction testing. | Separate shipped root-route behavior from mounted static dashboard behavior, and identify any asset routing repair made only in the test harness. |

## Additional useful checks sent to the coordinator

1. Proxy-enabled fetch calls `httpx.AsyncClient.get(..., proxies=...)` at `scraper/core/fetcher_static.py:157-166`. Verify compatibility offline with the installed pinned HTTPX signature or mock transport; the handler catches errors and could silently turn every proxy fetch into `(None, None)`.
2. The README promises robots.txt enforcement, but `engine.run_job` passes only the domain to `RateLimiter.acquire`, and the rate limiter has no robots checks. Verify the whole repository before adding a finding; do not infer legal noncompliance.
3. Preserve source-vs-runtime evidence distinctions for auth/SSRF/path controls and avoid double-counting downstream symptoms of the serial execution crash.

## Final review

The consolidated PLAN, SESSION-LOG, FINDINGS, COVERAGE and SUMMARY documents are present. Findings contain 28 unique IDs with independently recounted severities: **Critical=0, High=11, Medium=16, Low=1**. Backend/security has 15 findings, Frontend 5, and UX/DX 8. No cross-group corroboration is counted twice.

Coverage JSON independently confirms identical 53-file source inventories and denominators: 5,434 statements and 1,706 branches. Before: 1,354 statements and 429 branches executed. After: 2,409 statements and 643 branches executed. This supports statement coverage 24.92% to 44.33% and branch coverage 25.15% to 37.69%. Baseline outcomes remain 140 passed/11 failed/18 errors; final combined Python outcomes are 171 passed/43 strict expected failures/the same 11 failed and 18 errors. Thus all 74 new Python cases are accounted for as 31 passing controls and 43 expected defects.

Structured browser reports independently show Frontend 14 ordinary passes plus 9 expected failures and UX 2 ordinary passes plus 7 expected failures: 32 executions, 16 ordinary passes and 16 expected failures, without unexpected failures. Final UX rerun preserves these counts after the semantic/recovery assertion refinements. Actual Chromium/Firefox/WebKit identification is retained in the frontend artifacts. No broader cross-browser UX or real scraping claim is made.

The only tracked pre-existing file modification is `pyproject.toml`, adding `pytest-socket` and Hypothesis in dev dependencies. Every untracked file is inside the requested QA docs/artifacts or new QA test directories. `git diff --check` passes; branch remains `qa/2026-10-02-sweep`. Product code, runtime dependencies, pre-existing tests, deployment settings, environment files, migration files and CI secret-scan ignores/baselines remain unchanged.

**Resolved handoff blocker:** the first final audit found 153 evidence files hidden by existing Git ignore rules. Scoped QA-document inclusion rules and coverage-report-local overrides now make every QA artifact unignored. This was rechecked independently, not assumed from the edit. The coordinator validator found all 299 referenced local Markdown links present at its snapshot; lane-report links were also independently checked. The coordinator owns the final redacted QA-addition secret scan and reported zero detections; no credential values were used by this review.

Corrected two evidence claims during final review: BE-005 now points to workflow construction/build lines 467/470; FE-002 states that the selected page cap is not persisted and does not claim actual over-fetching through the currently broken next-button flow.

Readback evidence: [scope/count/coverage audit](artifacts/review-final-scope-audit-5ecf1b36.txt), [resolved artifact blocker and final UX run](artifacts/review-final-blocker-readback-9c1b785f.txt), [coordinator link/inclusion validator](artifacts/coordinator-handoff-validation-230c5a1f.txt).

No commits, pushes, PR creation, hosted CI requests, deployments or real external target calls were performed by this reviewer. The PR URL and hosted CI remain orchestrator-owned and pending, exactly as stated in SUMMARY. The current CVE audit is explicitly partial and stale; real screen-reader speech, browser zoom, providers, production and long-running load are explicitly untested. These are limits of the sweep, not passing results.

## Added-test review follow-up

- Backend and security expected-failure contracts must use `raises=AssertionError` where applicable, so unrelated runtime errors remain failures. The backend owner confirmed narrowing the remaining API markers and a deliberate `--runxfail` run reproduced 19 intended assertion failures alongside 24 passing controls.
- Frontend FE-003 must normalize the captured payload before `test.fail`; otherwise a Python harness error could be accepted as the expected failure. FE-001 must establish a real HTTP 200 dashboard with form/heading before testing its failed initial job loading. The frontend owner confirmed both changes.
- UX expected-failure annotations follow visible-state preconditions. The body-font-size 200% diagnostic is not full browser zoom or WCAG text-resize compliance. Inline detail-panel focus behavior is a usability finding; missing automatic focus alone is not a blanket WCAG failure.
- Both browser fixtures make downstream interaction coverage explicit after using the working `/static/index.html` asset path. The root route is checked independently by frontend and backend tests.

## Review-request closure

Backend and security owners narrowed expected failures to the intended assertion type. Frontend moved model normalization outside expected-failure handling and verified root-document setup before its known-failure assertion. UX now tests the error message's own live-region ancestry and accepts either automatic list recovery or an explicit visible retry control. These requests changed only tests/documentation and were rerun by their owning QA groups. This reviewer inspected source, test contracts and stored results rather than repeating the entire suite.
