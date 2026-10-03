# Offline dashboard regression checks

These tests change no product code. They use fictional data, intercept every API request, abort all other external traffic, and serve only local static assets on `127.0.0.1:18765`. The local static server mirrors the API's `/` and `/static` routes. Downstream UI checks explicitly use `/static/index.html` as a workaround for FE-001.

Prerequisites: Node.js, `@playwright/test` latest (matching the supplied remote server), a Python environment with this repository's Pydantic dependency, and a Playwright browser server. Set `PW_TEST_CONNECT_WS_ENDPOINT` to its WebSocket URL. Do not launch browsers from these tests. All browser access uses `connectOptions` or `browserType.connect()`.

If QA dependencies are installed outside the checkout, set `NODE_PATH` to that prefix's `node_modules`. `QA_PYTHON` can select the Python interpreter; its default is `python3`. The recorded session used `/private/tmp/grann-qa-20261002/node/node_modules` and `/private/tmp/grann-qa-20261002/venv/bin/python`; neither is embedded in test code.

Reproduction commands (also recorded with outcomes in the frontend session log):

```sh
node "$NODE_PATH/@playwright/test/cli.js" test --config tests/qa_frontend/playwright.config.cjs
node tests/qa_frontend/probe_browsers.cjs
node --check scraper/web/static/app.js
```

`validate_contract.py` passes the captured form payload through the actual production `ScrapeJob` model; it does not approximate its normalization in JavaScript. Mock response shapes follow `scraper/api/rest_server.py` and `scraper/strategies/intelligent_extraction.py`. Backend QA also verifies the asset path against the actual ASGI routes.

Known defects use strict Playwright `test.fail` annotations with finding IDs. They fail CI if behavior unexpectedly passes, prompting removal of the expected-failure marker. Setup and preconditions run before these annotations so infrastructure failures remain real failures. Passing tests cover analyze/create/run order, initial and result views, cancellation and confirmation, browser bounds, disabled submission during loading, and recovery after a rejected analysis.

Reports and fictional screenshots are written to `docs/qa/2026-10-02/artifacts/frontend-*`. The performance diagnostic is unthrottled loopback timing, not a Lighthouse score. Its JavaScript byte coverage covers only the list/details journey, not whole-suite line coverage.
