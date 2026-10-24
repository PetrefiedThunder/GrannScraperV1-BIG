# Coverage and validation

PR: opened by orchestrator

CI status: pending at time of writing

## Python before and after

Both measurements use `pytest --cov=scraper --cov-branch`, Python 3.11.15, coverage.py 7.16.2, the same product source and all 53 Python source files. The baseline ran before adding QA tests. The after run includes the original tests plus all new Python cases. Statements (5,434), branches (1,706) and existing exclusions (16 lines) are unchanged. Socket creation is blocked except Unix sockets needed by the event loop; HTTP transports and scraping collaborators are mocked.

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Statement coverage | 1,354 / 5,434 = **24.92%** | 2,409 / 5,434 = **44.33%** | +19.41 percentage points |
| Branch coverage | 429 / 1,706 = **25.15%** | 643 / 1,706 = **37.69%** | +12.54 points |
| Combined statement + branch | **24.97%** | **42.75%** | +17.77 points |
| Ordinary passing tests | 140 | 171 | +31 |
| Strict expected failures | 0 | 43 | +43 discovery cases |
| Pre-existing failures / setup errors | 11 / 18 | 11 / 18 | Unchanged |
| Total collected cases | 169 | 243 | +74 |

**The full suite still exits 1.** Eleven existing ML assertions/API mismatches and eighteen existing cache-fixture errors remain. No original test was weakened, deleted or quarantined. The 74 new Python cases comprise 31 passes and 43 strict expected failures, with no unexpected failures; defect markers require `AssertionError` and a finding ID. Hypothesis additionally explores 50 deterministic URL-pagination windows within one passing case. Expected-failure execution increases coverage but does not establish working behavior or a fixed defect.

| Selected module (combined coverage) | Before | After |
|---|---:|---:|
| API routes | 0.00% | 78.26% |
| Core engine | 9.87% | 66.37% |
| Concurrent engine | 0.00% | 45.23% |
| Static fetcher | 10.48% | 60.48% |
| Cache/incremental | 18.63% | 65.84% |
| Workflow DAG | 0.00% | 37.29% |
| Security helpers | 0.00% | 38.01% |
| CLI entry point | 0.00% | 31.09% |

Evidence: [baseline JSON](artifacts/backend-coverage-before.json), [baseline HTML](artifacts/backend-coverage-before-html/index.html), [baseline output](artifacts/backend-baseline-suite-d284977e.txt), [after JSON](artifacts/coverage-after.json), [after HTML](artifacts/coverage-after-html/index.html), [after JUnit](artifacts/pytest-after.xml), [after full output](artifacts/coordinator-final-coverage-cd6da79b.txt), [comparison calculation](artifacts/coordinator-coverage-comparison-ce40dace.txt).

## Browser and accessibility coverage

There was no existing JavaScript test/coverage pipeline. Before-coverage is **not measured**, not zero. The new frontend suite has 23 executions: Chromium 19, Firefox 2 and WebKit 2. Fourteen are ordinary passes and nine expose expected defects. UX adds nine Chromium cases: two ordinary passes and seven expected defects. Combined browser evidence is **32 executions: 16 ordinary passes, 16 expected failures, no unexpected failures or skips**. An expected-failure Playwright case appears accepted in the runner but still represents a failing product assertion.

A separate Chromium list/details journey executed 6,087 / 10,747 UTF-16 source units of `app.js` (**56.64%**) using V8 range coverage. This is **not** line coverage, branch coverage, or an aggregate for all browser tests, and cannot be compared with the Python metric. Its unthrottled loopback DOMContentLoaded/load were 17 ms and FCP 24 ms; no Lighthouse score or production speed claim is made. [Diagnostic report](artifacts/frontend-performance.json).

Axe 4.13.0 checked WCAG 2 A/AA, 2.1 A/AA and 2.2 AA tags in empty, completed-results and error states. The empty/completed states have one contrast rule violation each (one/four affected nodes). The error state has zero automated violations, but interaction checks still find announcement/recovery problems. Twelve completed-state nodes require manual contrast review. Keyboard traversal, labels, live-region attributes, focus transitions, 375px and 320px layouts were inspected; actual screen-reader speech and real browser zoom were not tested. The 200% body-font diagnostic is not full zoom compliance evidence.

Evidence: [frontend results](artifacts/frontend-playwright.json), [browser engines](artifacts/frontend-browser-engines.json), [UX results](artifacts/ux-playwright-results.json), [UX report and screenshots](UX-REPORT.md).

## Other quality gates

| Gate | Result |
|---|---|
| Package source distribution and wheel build | Passed; artifacts created under the isolated temporary directory. |
| Product JavaScript syntax | Passed. No framework build or TypeScript application exists. |
| Ruff baseline (`scraper tests`, configured rules) | Failed: 1,110 diagnostics. Kept as existing debt; no style cleanup. |
| mypy baseline (`scraper`) | Failed: 443 errors across 33 files, including missing stubs and annotations. These are diagnostics, not 443 independently confirmed defects. |
| Added Python fatal-error lint | Passed. |
| Installed dependency compatibility | Passed: 143 distributions consistent. |
| Vulnerability audit | Partial and stale: exact cached advisory metadata for 23/143 installed versions, dated 2026-09-08. The other 120 are unassessed. No current vulnerability-free claim. |
| Source and QA secret scans | Gitleaks found no detections in 96 tracked code/doc files, then separate redacted scans of QA docs/artifacts and test sources also found no detections. Credential/environment paths and history were excluded. |

Evidence: [Ruff JSON](artifacts/coordinator-ruff-baseline.json), [mypy output](artifacts/coordinator-mypy-baseline.txt), [build output](artifacts/coordinator-build-package-ad390e94.txt), [security/dependency scope](SECURITY-REPORT.md), [tool versions](artifacts/coordinator-qa-tool-versions-34d9ef1e.txt).

Handoff checks: [QA docs/artifact secret scan](artifacts/coordinator-final-qa-secret-scan-088856c9.txt), [test-source secret scan](artifacts/coordinator-test-source-secret-scan-00796cb5.txt), [artifact inclusion, counts and local links](artifacts/coordinator-handoff-validation-230c5a1f.txt). Narrow Git inclusion rules preserve the evidence; no CI secret-scan ignore/baseline was changed.

## Still untested

3,025 statements and 1,063 branches remain unexecuted. Cloud storage, remote database connectors, premium formats, monitoring/alerts, advanced scheduling and logging infrastructure remain at 0% combined coverage. Browser-fetcher implementation coverage is only 12%; its direct browser-launch path was intentionally not invoked. SDK integration remains mostly mocked. Excel/premium exports, real scraping/browser rendering, external LLMs, cloud/DB writes, SMTP/SMS, deployment/provider settings, production traffic and credential lifecycle were not exercised.

Only Python 3.11.15 was tested. No Python-version matrix, destructive load test, long-duration race/memory soak, DNS rebinding, production latency, real proxy integration, actual assistive-technology speech, touch device study, complete WCAG audit, current full CVE audit or remote CI validation was performed. These boundaries follow the task restrictions and the risk-based time budget; none should be treated as passing evidence.
