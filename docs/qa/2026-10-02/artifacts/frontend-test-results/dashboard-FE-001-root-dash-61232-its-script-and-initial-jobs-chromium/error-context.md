# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: dashboard.spec.cjs >> FE-001 root dashboard loads its script and initial jobs
- Location: tests/qa_frontend/dashboard.spec.cjs:85:1

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: locator('#job-list')
Expected substring: "No jobs yet"
Received string:    ""
Timeout: 2500ms

Call log:
  - Expect "toContainText" locator('#job-list') with timeout 2500ms
  - waiting for locator('#job-list')
    9 × locator resolved to <ul id="job-list" class="job-list"></ul>
      - unexpected value ""

```

```yaml
- heading "🧓 GrandmaScrape Dashboard" [level=1]
- paragraph: Enterprise web scraping made grandma-simple
- heading "0" [level=3]
- paragraph: Total Jobs
- heading "0" [level=3]
- paragraph: Running
- heading "0" [level=3]
- paragraph: Completed
- heading "0" [level=3]
- paragraph: Workflows
- heading "🚀 Auto-Scrape (Grandma-Simple!)" [level=2]
- text: "Website URL:"
- textbox "Website URL:":
  - /placeholder: https://example.com
- text: "Maximum Pages:"
- spinbutton "Maximum Pages:": "10"
- text: "Export Format:"
- combobox "Export Format:":
  - option "JSON" [selected]
  - option "CSV"
  - option "Excel"
- checkbox "Use concurrent scraping (10x faster)" [checked]
- text: Use concurrent scraping (10x faster)
- button "Start Auto-Scrape"
- heading "📋 Your Jobs" [level=2]
- list
```

# Test source

```ts
  1   | const { test, expect } = require('@playwright/test');
  2   | const fs = require('node:fs');
  3   | const path = require('node:path');
  4   | const { execFileSync } = require('node:child_process');
  5   | const artifacts = path.resolve(__dirname, '../../docs/qa/2026-10-02/artifacts');
  6   | const target = 'https://example.invalid/catalog';
  7   | // Response keys mirror rest_server.py:94-143,306-358,365-410,557-578.
  8   | const analysis = {
  9   |   url: target, item_selector: '.product',
  10  |   fields: { title: { selector: 'h2', type: 'string', confidence: 1, auto_detected: true } },
  11  |   pagination: { mode: 'next_button', next_button_selector: 'a.next', confidence: 0.9 },
  12  |   analysis: { html_size: 100, links: 2, images: 0, title: 'Fictional catalog' },
  13  | };
  14  | const sampleJob = {
  15  |   id: 'qa_job', name: 'Fictional catalog', start_url: target, enabled: true,
  16  |   created_at: '2026-10-02T12:00:00',
  17  | };
  18  | 
  19  | async function setup(page, overrides = {}) {
  20  |   const state = { jobs: [], requests: [], errors: [], failed: [], blocked: [], ...overrides };
  21  |   page.on('pageerror', error => state.errors.push(error.message));
  22  |   page.on('console', message => { if (message.type() === 'error') state.errors.push(message.text()); });
  23  |   page.on('requestfailed', request => state.failed.push({ url: request.url(), error: request.failure()?.errorText }));
  24  |   await page.context().route('**/*', async route => {
  25  |     const request = route.request();
  26  |     const url = new URL(request.url());
  27  |     if (url.pathname.startsWith('/api/v1/')) {
  28  |       // All API calls are intercepted, even the incorrect localhost:8000 origin.
  29  |       state.requests.push({ url: request.url(), method: request.method(), body: request.postDataJSON() });
  30  |       const json = async (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  31  |       const endpoint = url.pathname.slice('/api/v1'.length);
  32  |       if (endpoint === '/info') return json({ version: '1.0.0', name: 'GrandmaScrape API', statistics: { total_jobs: state.jobs.length, running_jobs: 0, completed_jobs: state.jobs.length, workflows: 0 }, features: [] });
  33  |       if (endpoint === '/analyze') {
  34  |         if (state.analyzeGate) await state.analyzeGate;
  35  |         if (state.analyzeStatus) return json({ detail: state.analyzeDetail || 'Fictional analysis failure' }, state.analyzeStatus);
  36  |         if (state.analyzeNonJSON) return route.fulfill({ status: 502, contentType: 'text/plain', body: 'Fictional service unavailable' });
  37  |         return json(analysis);
  38  |       }
  39  |       if (endpoint === '/jobs' && request.method() === 'POST') {
  40  |         state.created = request.postDataJSON();
  41  |         const job = state.created.job;
  42  |         state.jobs.push({ ...sampleJob, id: job.id, name: job.name, start_url: job.start_url });
  43  |         return json({ job_id: job.id, status: 'created', message: `Job ${job.name} created successfully` });
  44  |       }
  45  |       if (endpoint === '/jobs') {
  46  |         if (state.listStatus) return json({ detail: 'Fictional temporary outage' }, state.listStatus);
  47  |         return json({ total: state.jobs.length, jobs: state.jobs });
  48  |       }
  49  |       if (endpoint.endsWith('/run')) return json({ job_id: state.created?.job.id || 'qa_job', status: 'running', message: 'Job started', concurrent: url.searchParams.get('concurrent') === 'true', incremental: false });
  50  |       if (endpoint.endsWith('/status')) return json({ job_id: 'qa_job', is_running: false, has_result: true, status: 'success', items_scraped: 1, pages_visited: 1, errors: 0, duration: 0.5, ...state.status });
  51  |       if (endpoint.endsWith('/results')) {
  52  |         const items = state.items || [{ title: 'Fictional product', price: '$10.00' }];
  53  |         return json({ job_id: 'qa_job', status: 'success', total_items: items.length, pages_visited: 1, errors: [], items: items.slice(0, 10), pagination: { limit: 10, offset: 0, has_more: items.length > 10 } });
  54  |       }
  55  |       if (request.method() === 'DELETE') {
  56  |         state.jobs = state.jobs.filter(job => job.id !== endpoint.split('/').pop());
  57  |         return json({ status: 'deleted', job_id: 'qa_job' });
  58  |       }
  59  |       return json({ detail: 'Unmocked API request' }, 500);
  60  |     }
  61  |     if (url.origin === 'http://127.0.0.1:18765') return route.continue();
  62  |     state.blocked.push(request.url());
  63  |     return route.abort('blockedbyclient');
  64  |   });
  65  |   return state;
  66  | }
  67  | 
  68  | async function openWorkingAssetPath(page) {
  69  |   // Explicit workaround for FE-001; never confuse this with the real / entry page.
  70  |   await page.goto('/static/index.html');
  71  |   await expect(page.locator('#job-list-loading')).toBeHidden();
  72  | }
  73  | 
  74  | async function submit(page, { pages = '2', format = 'json' } = {}) {
  75  |   await page.locator('#url').fill(target);
  76  |   await page.locator('#max-pages').fill(pages);
  77  |   await page.locator('#export-format').selectOption(format);
  78  |   await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  79  | }
  80  | 
  81  | function modelSettings(payload) {
  82  |   return JSON.parse(execFileSync(process.env.QA_PYTHON || 'python3', ['-m', 'tests.qa_frontend.validate_contract'], { input: JSON.stringify(payload), encoding: 'utf8', cwd: path.resolve(__dirname, '../..') }));
  83  | }
  84  | 
  85  | test('FE-001 root dashboard loads its script and initial jobs', async ({ page }) => {
  86  |   const state = await setup(page);
  87  |   const response = await page.goto('/');
  88  |   expect(response.status()).toBe(200);
  89  |   await expect(page.getByRole('heading', { level: 1 })).toContainText('GrandmaScrape Dashboard');
  90  |   await expect(page.locator('#auto-scrape-form')).toBeVisible();
  91  |   await page.screenshot({ path: path.join(artifacts, 'frontend-root-script-404.png'), fullPage: true });
  92  |   fs.writeFileSync(path.join(artifacts, 'frontend-root-errors.json'), JSON.stringify(state, null, 2));
  93  |   test.fail(true, 'FE-001: app.js resolves to /app.js; only /static/app.js exists');
> 94  |   await expect(page.locator('#job-list')).toContainText('No jobs yet');
      |                                           ^ Error: expect(locator).toContainText(expected) failed
  95  | });
  96  | 
  97  | test('working asset route: empty state then analysis/create/run/list flow', async ({ page }, testInfo) => {
  98  |   const state = await setup(page);
  99  |   await openWorkingAssetPath(page);
  100 |   await expect(page.locator('#job-list')).toContainText('No jobs yet');
  101 |   await submit(page);
  102 |   await expect(page.locator('#job-list')).toContainText(`Auto-scraped: ${target}`);
  103 |   const mutations = state.requests.filter(request => request.method === 'POST');
  104 |   expect(mutations.map(request => new URL(request.url).pathname.replace(/job_\d+/, 'ID'))).toEqual(['/api/v1/analyze', '/api/v1/jobs', '/api/v1/jobs/ID/run']);
  105 |   expect(new URL(mutations[2].url).searchParams.get('concurrent')).toBe('true');
  106 |   await expect(page.locator('#url')).toHaveValue('');
  107 |   expect(state.errors).toEqual([]);
  108 |   expect(state.blocked).toEqual([]);
  109 |   fs.writeFileSync(path.join(artifacts, `frontend-main-flow-${testInfo.project.name}.json`), JSON.stringify({ requests: state.requests, normalized_settings: modelSettings(state.created), console_errors: state.errors, failed_requests: state.failed, blocked: state.blocked }, null, 2));
  110 | });
  111 | 
  112 | for (const pages of ['1', '2', '1000']) {
  113 |   test(`FE-002 selected page limit ${pages} survives API model validation`, async ({ page }) => {
  114 |     const state = await setup(page);
  115 |     await openWorkingAssetPath(page);
  116 |     await submit(page, { pages });
  117 |     await expect(page.locator('#job-list .job-item')).toHaveCount(1);
  118 |     const persisted = modelSettings(state.created);
  119 |     test.fail(true, 'FE-002: max_pages sent at job root is ignored instead of pagination.max_pages');
  120 |     expect(persisted.max_pages).toBe(Number(pages));
  121 |   });
  122 | }
  123 | 
  124 | for (const format of ['json', 'excel']) {
  125 |   test(`FE-003 selected ${format} export survives API model validation`, async ({ page }) => {
  126 |     const state = await setup(page);
  127 |     await openWorkingAssetPath(page);
  128 |     await submit(page, { format });
  129 |     await expect(page.locator('#job-list .job-item')).toHaveCount(1);
  130 |     const persisted = modelSettings(state.created);
  131 |     test.fail(true, 'FE-003: export.format is ignored; model expects export.formats');
  132 |     expect(persisted.formats).toEqual([format]);
  133 |   });
  134 | }
  135 | 
  136 | test('FE-004 dashboard API requests use the serving origin', async ({ page }) => {
  137 |   const state = await setup(page);
  138 |   await openWorkingAssetPath(page);
  139 |   test.fail(true, 'FE-004: API_BASE is permanently http://localhost:8000/api/v1');
  140 |   expect([...new Set(state.requests.map(request => new URL(request.url).origin))]).toEqual([new URL(page.url()).origin]);
  141 | });
  142 | 
  143 | test('FE-005 job names are rendered as text, not HTML elements', async ({ page }) => {
  144 |   // Inert formatting only: no scripts, event handlers, requests, or executable payloads.
  145 |   const name = '<strong data-qa-fixture="literal">Literal product name</strong>';
  146 |   await setup(page, { jobs: [{ ...sampleJob, name }] });
  147 |   await openWorkingAssetPath(page);
  148 |   await page.screenshot({ path: path.join(artifacts, 'frontend-literal-markup.png'), fullPage: true });
  149 |   test.fail(true, 'FE-005: job.name is interpolated into innerHTML');
  150 |   await expect(page.locator('[data-qa-fixture="literal"]')).toHaveCount(0);
  151 | });
  152 | 
  153 | test('FE-005 scraped field names and values remain literal text', async ({ page }) => {
  154 |   await setup(page, { jobs: [sampleJob], items: [{ '<em data-qa-fixture="field">literal heading</em>': '<strong data-qa-fixture="value">literal value</strong>' }] });
  155 |   await openWorkingAssetPath(page);
  156 |   await page.getByRole('button', { name: 'View Details' }).click();
  157 |   await expect(page.locator('.results-table')).toBeVisible();
  158 |   test.fail(true, 'FE-005: results are interpolated into innerHTML');
  159 |   await expect(page.locator('[data-qa-fixture]')).toHaveCount(0);
  160 | });
  161 | 
  162 | test('results can be opened and closed; null values show a dash', async ({ page }, testInfo) => {
  163 |   const state = await setup(page, { jobs: [sampleJob], items: [{ title: 'Fictional product', price: null }] });
  164 |   await openWorkingAssetPath(page);
  165 |   await page.getByRole('button', { name: 'View Details' }).click();
  166 |   await expect(page.locator('.results-table tbody tr')).toHaveCount(1);
  167 |   await expect(page.locator('.results-table tbody td').nth(1)).toHaveText('-');
  168 |   await page.screenshot({ path: path.join(artifacts, `frontend-results-${testInfo.project.name}.png`), fullPage: true });
  169 |   await page.getByRole('button', { name: 'Close', exact: true }).click();
  170 |   await expect(page.locator('#job-details')).toBeHidden();
  171 |   expect(state.errors).toEqual([]);
  172 | });
  173 | 
  174 | test('delete requires confirmation; cancelling keeps job; confirming removes it', async ({ page }) => {
  175 |   const state = await setup(page, { jobs: [sampleJob] });
  176 |   await openWorkingAssetPath(page);
  177 |   page.once('dialog', dialog => dialog.dismiss());
  178 |   await page.getByRole('button', { name: 'Delete', exact: true }).click();
  179 |   expect(state.requests.some(request => request.method === 'DELETE')).toBe(false);
  180 |   page.once('dialog', dialog => dialog.accept());
  181 |   await page.getByRole('button', { name: 'Delete', exact: true }).click();
  182 |   await expect(page.locator('#job-list')).toContainText('No jobs yet');
  183 |   expect(state.requests.filter(request => request.method === 'DELETE')).toHaveLength(1);
  184 | });
  185 | 
  186 | test('analyze error preserves input and lets user retry successfully', async ({ page }) => {
  187 |   const state = await setup(page, { analyzeStatus: 400 });
  188 |   await openWorkingAssetPath(page);
  189 |   await submit(page);
  190 |   await expect(page.locator('#alert-container')).toContainText('Fictional analysis failure');
  191 |   await expect(page.getByRole('button', { name: 'Start Auto-Scrape' })).toBeEnabled();
  192 |   await expect(page.locator('#url')).toHaveValue(target);
  193 |   expect(state.created).toBeUndefined();
  194 |   state.analyzeStatus = 0;
```