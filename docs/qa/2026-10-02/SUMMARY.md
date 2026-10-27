# QA summary — 2026-10-02

PR: opened by orchestrator

CI status: pending at time of writing

Counts: Critical=0 High=11 Medium=16 Low=1

**Release recommendation: do not release this snapshot as a working network-accessible scraping service.** All three QA passes completed and identified 28 distinct findings. Ordinary jobs fail, concurrent jobs hang, the intended dashboard URL lacks its script, and network API trust boundaries are absent. No product fixes were applied.

The PR/CI lines above are the orchestrator-required handoff labels. This agent did not create a PR or contact remote CI; no PR URL is available yet. All changes remain uncommitted on `qa/2026-10-02-sweep` for the orchestrator to review, scan, commit, push and open as one draft PR. No CI workflows were found in this checkout. The full local suite is already failing; this report does not claim CI will be green.

## Counts by group

| Group | Critical | High | Medium | Low | Total |
|---|---:|---:|---:|---:|---:|
| Backend (including independent security support) | 0 | 7 | 7 | 1 | 15 |
| Frontend | 0 | 4 | 1 | 0 | 5 |
| UX (including CLI/quickstart developer experience) | 0 | 0 | 8 | 0 | 8 |
| **Total** | **0** | **11** | **16** | **1** | **28** |

Cross-group corroborations are counted once under their canonical ID. Existing lint/type diagnostics and baseline test failures are tracked as quality debt, not inflated into separate finding counts. No actual secret exposure was observed in the scanned scope; BE-015 is a latent logging defect demonstrated with a non-secret marker.

## Top five risks in plain language

1. **BE-010 — High:** anyone who can reach the default network API can create, read or delete jobs without authentication.
2. **BE-011 — High:** the analysis API accepts private-network destinations and unsafe redirects, allowing server-side access outside intended public scraping targets; verified with mock transports only.
3. **BE-001 — High:** ordinary API jobs crash before scraping and leave no terminal result for clients to inspect.
4. **BE-002 — High:** concurrent jobs keep waiting after their work finishes, so users cannot receive a completed result.
5. **FE-001 — High:** the default dashboard page requests a missing script and its controls never initialize.

Additional release concerns include HTML injection in job/results rendering (FE-005), silently ignored page/export choices (FE-002/003), incomplete next-page data (BE-009), broken incremental caching (BE-003), reversed/incomplete workflows (BE-005), mobile controls outside the viewport (UX-001) and inaccessible status/contrast/focus behavior (UX-002/003/004). Full evidence and suggested fixes are in [FINDINGS.md](FINDINGS.md).

## Validation outcome

- **Baseline Python:** 140 passed, 11 failed, 18 errors. **After:** 171 passed, 43 expected failures, the same 11 failed and 18 errors. All 74 added cases are either passing controls (31) or strict expected defects (43); original tests are unchanged.
- **Coverage:** statements 24.92% → 44.33%; branches 25.15% → 37.69%; identical whole-package denominators. Expected failures contribute execution coverage, not proof of correctness.
- **Browser:** 32 executions across Frontend and UX: 16 ordinary passes, 16 expected failures, no unexpected failures/skips. Chromium, Firefox and WebKit verified. Downstream UI tests use `/static/index.html` because the root route is broken; APIs are intercepted with fictional data.
- **Accessibility:** axe reports contrast violations in empty/completed states. Keyboard, semantic attributes and screenshots corroborate narrow-layout, announcement, focus and recovery defects. No full WCAG conformance claim.
- **Build/static:** wheel/sdist and JS syntax pass; baseline Ruff has 1,110 diagnostics and mypy has 443 errors in 33 files. No cleanup or product changes.
- **Dependencies/security:** 143 installed distributions are compatible. Cached advisory coverage is stale and partial (23/143). Gitleaks scans of tracked source, QA docs/artifacts and test sources found zero detections in their explicitly limited scopes; the orchestrator still owns the final pre-commit secret scan.

Evidence and metric definitions: [COVERAGE.md](COVERAGE.md). Separate pass reports: [Backend](BACKEND-REPORT.md), [Frontend](FRONTEND-REPORT.md), [UX](UX-REPORT.md), [security support](SECURITY-REPORT.md). Exact UTC commands, failed attempts and timeboxed charters: [SESSION-LOG.md](SESSION-LOG.md). Independent review: [REVIEW-REPORT.md](REVIEW-REPORT.md).

## Recommended next-fix order

1. Establish the network API trust boundary and outbound destination policy (BE-010/011). Repair raw-token logging before wiring the auth helper (BE-015), and enforce server-owned export paths/work budgets (BE-012/013).
2. Restore terminal job lifecycles (BE-001/002/003) with success/failure/cancellation route tests. Ensure callers receive durable failure results.
3. Repair dashboard asset/origin paths and safe rendering (FE-001/004/005), then honor page/export settings (FE-002/003).
4. Restore complete data flows: workflow ordering and validation, next-button pagination, IDs, item limits, proxies, robots policy and result bounds (BE-004–009/014).
5. Fix mobile, contrast, announcements, focus, full-result retrieval, error recovery, CLI listing and quickstart contracts (UX-001–008). Resolve pre-existing suite drift, then rerun the entire suite and obtain a current dependency audit before release.

## Limits and handoff

No production, credentials, `.env`, billing, deployment, migrations or real scraping/provider/database targets were accessed. Real browser-fetcher launches, live proxies, remote exports, LLM/SMS/email calls, long-running resource/concurrency load, actual screen-reader speech, real browser zoom and production performance were excluded. Current CVE verification is incomplete because advisory API network access was outside scope. Remote CI and the draft PR are pending the orchestrator.

Changed scope is QA documentation/artifacts, new isolated tests/configuration, and two dev-only test dependencies (`pytest-socket` and `hypothesis`). No runtime dependency, product source, CI ignore/baseline, deployment or environment file was edited. No commit, push, PR creation, merge or deploy was performed.

Fix pass: see FIXES.md
