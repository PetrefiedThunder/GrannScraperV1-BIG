# QA fix pass — 2026-10-02

Branch: `qa/2026-10-02-fixes`. Starting commit: `d8e6678`. All commits are local. No push, PR, deployment or remote system access. Execution date crossed into 2026-10-03 UTC.

Critical/High work followed SUMMARY order: BE-010/011 assessment, BE-001/002/003, FE-001/004/005/002, BE-005/009. Independent preparation ran in parallel; commits remained separated by finding. Review/type-check follow-ups are listed with their original finding. Optional work started only after all High findings were handled.

| Finding ID | Severity | Title | Status | Commit SHA | Proving test (file::name) | Notes or reason deferred |
|---|---|---|---|---|---|---|
| BE-010 | High | Network job API has no authentication boundary | deferred | — | `tests/qa_security/test_security_boundaries.py::test_api_rejects_unauthenticated_job_access` | No server credential provisioning/persistence path; dashboard and documented SDK usage lack required identity. Wiring the empty key manager would lock out existing workflows. Needs credential setup and public-contract decisions prohibited in this pass; auth expected failures retained. |
| BE-011 | High | Analyze route fetches nonpublic URLs; redirects bypass destination checks | deferred | — | `tests/qa_security/test_security_boundaries.py::test_analyze_rejects_nonpublic_url; test_static_fetch_blocks_public_to_private_redirect` | Needs an explicit outbound policy, connection-time DNS/address enforcement, redirect validation and browser/subresource coverage while preserving trusted SDK usage. A literal-IP-only patch is incomplete; compatibility and network-egress decisions exceed this safe pass. Expected failures retained. |
| BE-001 | High | Ordinary API jobs crash before scraping and expose no terminal result | fixed | `98277e7`, `e71985b`, `35e4b29`, `d8b06a9` | `tests/qa_backend/test_execution.py::test_standard_api_run_persists_success; tests/qa_backend/test_lifecycle_fixes.py::test_deleted_run_cannot_publish_into_recreated_job` | Removed shadowed engine imports; persist safe terminal failures/cancellation, preserve export-failure data, clear stale rerun state and guard result publication by job/task identity. Review found and resolved delete/recreate race. Results remain in-memory, not durable across process restarts. |
| BE-002 | High | Concurrent jobs never finish after all work completes | fixed | `0355b67`, `5152a81`, `3f4bfda` | `tests/qa_backend/test_execution.py::test_concurrent_scraper_finishes_after_completed_work; tests/qa_backend/test_concurrent_fixes.py::test_concurrent_callback_cancellation_propagates_and_stops_workers` | Queue completion plus worker cancellation/join; retry attempts retain one logical task. Review found and resolved callback-cancellation hang. Empty, success, failure, retry, API and cancellation paths covered. |
| BE-003 | High | Incremental mode fails at the API and does not provide working replay caching | fixed | `36d9483`, `d6d65cb`, `f9966cc` | `tests/qa_backend/test_execution.py::test_incremental_repeat_uses_cache; tests/qa_backend/test_incremental_api_fixes.py::test_incremental_api_cache_isolated_by_job_configuration` | Per-URL item callbacks; failed/partial callbacks cannot become fresh success. Exact snapshots, including empty success, stored in existing metadata without schema changes. API cache keys include a job-configuration hash; existing cache management still applies. Cached and newly fetched items returned; grouped new/cached ordering remains the existing return convention. |
| FE-001 | High | Root dashboard never loads its JavaScript | fixed | `ebafcc3` | `tests/qa_backend/test_api_contracts.py::test_dashboard_script_is_available; tests/qa_frontend/dashboard.dom.test.cjs::FE-001 root dashboard resolves its script and initializes jobs` | Use mounted /static/app.js from both entry URLs. Real ASGI asset test and DOM initialization pass. Matching browser expected failure promoted; real-browser rerun blocked by environment. |
| FE-004 | High | Dashboard always calls the visitor's localhost port 8000 | fixed | `b8270c7`, `e38749e` | `tests/qa_frontend/dashboard.dom.test.cjs::FE-004 dashboard requests use the serving origin` | Use same-origin /api/v1. Updated dependent UX API fixture to intercept that origin, block external origins, and preserve original evidence using QA_ARTIFACTS_DIR. Browser execution remains blocked. |
| FE-005 | High | API/job/scraped strings are interpreted as HTML | fixed | `c2551ab` | `tests/qa_frontend/dashboard.dom.test.cjs::FE-005 job names, URLs, and IDs remain literal text; FE-005 scraped headers, values, and result counts remain literal text` | Untrusted strings use text nodes; event listeners replace interpolated inline actions; path IDs encoded; status classes allowlisted. Seven inert negative controls failed before. Nine DOM cases at this commit passed; local security review clean. No active script payload used. |
| FE-002 | High | Maximum Pages selection is silently ignored | fixed | `89be068` | `tests/qa_frontend/dashboard.dom.test.cjs::FE-002 selected page limit 2 survives dashboard submission and API validation` | Nested pagination.max_pages honors 1, 2 and 1000 while preserving detected mode/selector. Actual JavaScript submissions validated through production ScrapeJob. Python companion uses corrected payload; no backend compatibility alias or API contract change. |
| BE-005 | High | Workflow dependencies produce an incomplete, reversed execution plan | fixed | `f0c6237` | `tests/qa_backend/test_execution.py::test_workflow_orders_prerequisites_before_dependents; tests/qa_backend/test_api_contracts.py::test_bad_workflow_returns_validation_error` | Correct prerequisite in-degrees, validate references/cycles/complete plans, and return generic HTTP 400 before storing invalid definitions. Branching, duplicates, execution ordering and malformed API definitions covered; 16 related tests passed. |
| BE-009 | High | Next-button pagination silently stops after the first page | fixed | `8558c63` | `tests/qa_backend/test_execution.py::test_engine_follows_next_button; tests/qa_backend/test_pagination_fixes.py::test_api_next_links_persist_complete_bounded_results` | Discover next links, resolve against each page, enforce max_pages and existing domain policy, reject unsafe schemes/credentials and stop cycles. Sequential discovery applies even when concurrency is requested. Standard/concurrent/incremental API data and page counters proved; DNS/redirect SSRF policy remains BE-011. |
| BE-004 | Medium | Server-generated job IDs cannot be read or deleted | fixed | `400a3de` | `tests/qa_backend/test_api_contracts.py::test_server_generated_job_id_round_trips` | Generate prefixed UUID hex IDs accepted by existing detail/delete routes. Caller-supplied ID validation contract unchanged. |
| BE-008 | Low | Invalid result-page bounds return misleading successful responses | fixed | `d3fe242` | `tests/qa_backend/test_api_contracts.py::test_invalid_results_pagination_is_rejected` | Require limit >= 1 and offset >= 0; valid request limits/defaults preserved. No arbitrary upper quota introduced; broader work budgets remain BE-013. |
| FE-003 | Medium | JSON and Excel export selections become CSV | fixed | `52076eb` | `tests/qa_frontend/dashboard.dom.test.cjs::FE-003 selected json export survives dashboard submission and API validation` | Send export.formats list. Actual CSV/JSON/Excel submissions validate through production model. Python companion and browser markers updated; no real Excel export performed. |
| BE-006 | Medium | `max_items` is exceeded by a single page | partial | `841a632` | `tests/qa_backend/test_execution.py::test_engine_respects_item_limit_within_page; tests/qa_backend/test_item_limit_fixes.py::test_accepted_rows_respect_remaining_item_budget` | Fixed positive per-engine item budgets within and across pages. Global budgets across independent concurrent/incremental callbacks remain unresolved; changing zero/negative model semantics needs a compatibility decision. Existing None/zero behavior preserved. Original expected failure is now a normal passing test. |
| UX-007 | Medium | `scraper list` crashes when saved jobs exist | fixed | `f39b390` | `tests/qa_ux/test_cli_docs.py::test_saved_jobs_are_listed` | Rename Python callback to list_jobs while keeping public CLI command list. Related CLI suite: 4 passed, 2 unrelated README expected failures. |

## Counts

FixCounts: fixed=9 partial=0 deferred=2

The machine-readable line counts Critical and High only. No Critical findings were reported.

| Severity | Fixed | Partial | Deferred |
|---|---:|---:|---:|
| Critical | 0 | 0 | 0 |
| High | 9 | 0 | 2 |
| Medium (touched) | 3 | 1 | 0 |
| Low (touched) | 1 | 0 | 0 |
| **Included total** | **13** | **1** | **2** |

The other 12 Medium findings were not attempted: BE-007/012/013/014/015 and UX-001/002/003/004/005/006/008. They require broader behavior, policy/compatibility decisions or browser verification; their expected failures and original findings remain unchanged.

## Full-suite results

| Run | Passed | Failed | Errors | Xfailed | Ordinary skipped | Total |
|---|---:|---:|---:|---:|---:|---:|
| Sweep before added QA cases (COVERAGE.md) | 140 | 11 | 18 | 0 | 0 | 169 |
| Sweep final / live starting fixes-branch baseline | 171 | 11 | 18 | 43 | 0 | 243 |
| Final fix pass | **264** | **11** | **18** | **24** | **0** | **317** |

Full Python command: `/private/tmp/grann-qa-20261002/venv/bin/python -m pytest --disable-socket --allow-unix-socket -q --junitxml=/private/tmp/grann-fixes-20261002/after.xml`. Exit 1. The 11 failing ML tests in `tests/test_data_intelligence.py` and 18 cache fixture errors in `tests/test_smart_cache.py` are exactly the same test IDs/categories as before. Cache fixtures pass a string to the existing Path-only constructor; no pre-existing tests were weakened or repaired. There are **no new Python failures/errors**. Nineteen expected defects became ordinary passes and 74 regression cases were added. No fix required `git revert` after final regression comparison.

**DOM suite:** 15 passed, 0 failed, 0 skipped. Actual production dashboard JavaScript runs under jsdom with intercepted APIs, and selected page/export payloads are checked by the production Python model. jsdom is an isolated test tool installed under `/private/tmp/grann-fixes-20261002/dom`; no runtime dependency or manifest changes. Run with `NODE_PATH` pointing to that directory and `QA_PYTHON` pointing to the isolated Python interpreter, using `node --test tests/qa_frontend/dashboard.dom.test.cjs`.

**Real-browser full suites attempted:** frontend 24 setup failures; UX 1 setup failure and 8 not run. All fail before product assertions because the supplied WebSocket browser at `127.0.0.1:3950` refuses connections. Attempts to start isolated Chromium/Firefox/WebKit failed under the macOS sandbox (Chromium bootstrap permission denial). These are environment blockers, not observed product regressions or passing browser evidence. The sweep had 32 browser executions (16 ordinary passes, 16 expected failures); the current suite discovers 33 because one safe-action case was added. Original browser expected-failure markers for fixed FE findings were removed. Browser proof still requires rerun in a permitted runtime.

## Build, typecheck, lint and review

| Check | Before | After |
|---|---|---|
| Wheel + source distribution (`uv build --out-dir /private/tmp/grann-fixes-20261002/dist`) | Pass | Pass |
| Product JavaScript syntax (`node --check scraper/web/static/app.js`) | Pass | Pass |
| Typecheck (`mypy scraper`, 53 source files) | 443 errors / 33 files | 440 errors / 33 files; no new diagnostics after normalizing line shifts |
| Configured Ruff (`ruff check scraper tests`) | Sweep recorded 1,110 before its QA additions; exact `d8e6678` snapshot has 1,351 | 1,329; no new diagnostics after normalizing line shifts |
| Newly added Python regression files, configured Ruff | Not present | Pass without ignores/suppressions |
| Independent local review | QA evidence review only | Final code and documentation review passed; all proving-test references verified |
| Redacted Gitleaks scan of all changed source/tests plus QA handoff files | Sweep scoped scans passed | 27 files, zero detections; scanner configuration unchanged |

There is no TypeScript application or framework frontend build. Existing lint/type errors remain pre-existing debt. No dependencies were upgraded because the Critical/High list contains no dependency-upgrade finding; no current vulnerability-audit claim is made. No secret-scan baseline or ignore list was changed.

## Remaining risks and handoff

- BE-010 and BE-011 still prevent approval as a network-accessible service. Authentication provisioning/compatibility and complete outbound policy are owner decisions; no production controls were changed.
- BE-006 is partial: global multi-callback budgets and model lower-bound semantics remain unresolved. BE-012 export containment, BE-013 resource budgets, BE-014 robots enforcement and BE-015 credential-identifier logging remain known untouched findings.
- Results still use the existing process-local dictionaries. No persistence migration was attempted. Concurrent scraper instance reuse, long-running races/load, DNS rebinding, live proxies, real browser fetching, production/provider calls, actual screen-reader behavior and remote CI are unverified.
- Real-browser rerun and the 29 existing Python failure/error cases remain blockers to a green complete validation run. DOM/ASGI checks are useful proof of these fixes, not a replacement for browser/layout/accessibility verification.
- All original sweep evidence files remain unchanged. Final command outcomes, negative controls, decisions and dead ends are preserved in [FIX-SESSION-LOG.md](FIX-SESSION-LOG.md); full local outputs are under `/private/tmp/grann-fixes-20261002/`. The orchestrator owns review/push/PR creation.
