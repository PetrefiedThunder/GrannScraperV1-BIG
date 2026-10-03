# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: dashboard.spec.cjs >> FE-005 scraped field names and values remain literal text
- Location: tests/qa_frontend/dashboard.spec.cjs:153:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  locator('[data-qa-fixture]')
Expected: 0
Received: 2
Timeout:  2500ms

Call log:
  - Expect "toHaveCount" locator('[data-qa-fixture]') with timeout 2500ms
  - waiting for locator('[data-qa-fixture]')
    9 × locator resolved to 2 elements
      - unexpected value "2"

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - generic [ref=e3]:
    - heading "🧓 GrandmaScrape Dashboard" [level=1] [ref=e4]
    - paragraph [ref=e5]: Enterprise web scraping made grandma-simple
  - generic [ref=e6]:
    - generic [ref=e7]:
      - heading "1" [level=3] [ref=e8]
      - paragraph [ref=e9]: Total Jobs
    - generic [ref=e10]:
      - heading "0" [level=3] [ref=e11]
      - paragraph [ref=e12]: Running
    - generic [ref=e13]:
      - heading "1" [level=3] [ref=e14]
      - paragraph [ref=e15]: Completed
    - generic [ref=e16]:
      - heading "0" [level=3] [ref=e17]
      - paragraph [ref=e18]: Workflows
  - generic [ref=e19]:
    - heading "🚀 Auto-Scrape (Grandma-Simple!)" [level=2] [ref=e20]
    - generic [ref=e21]:
      - generic [ref=e22]:
        - generic [ref=e23]: "Website URL:"
        - textbox "Website URL:" [ref=e24]:
          - /placeholder: https://example.com
      - generic [ref=e25]:
        - generic [ref=e26]: "Maximum Pages:"
        - spinbutton "Maximum Pages:" [ref=e27]: "10"
      - generic [ref=e28]:
        - generic [ref=e29]: "Export Format:"
        - combobox "Export Format:" [ref=e30]:
          - option "JSON" [selected]
          - option "CSV"
          - option "Excel"
      - generic [ref=e32]:
        - checkbox "Use concurrent scraping (10x faster)" [checked] [ref=e33]
        - text: Use concurrent scraping (10x faster)
      - button "Start Auto-Scrape" [ref=e34] [cursor=pointer]
  - generic [ref=e35]:
    - heading "📋 Your Jobs" [level=2] [ref=e36]
    - list [ref=e37]:
      - listitem [ref=e38]:
        - generic [ref=e39]:
          - heading "Fictional catalog" [level=3] [ref=e40]
          - paragraph [ref=e41]:
            - strong [ref=e42]: "URL:"
            - text: https://example.invalid/catalog
            - strong [ref=e43]: "ID:"
            - text: qa_job
            - strong [ref=e44]: "Created:"
            - text: 10/2/2026, 12:00:00 PM
        - generic [ref=e45]:
          - button "View Details" [active] [ref=e46] [cursor=pointer]
          - button "Delete" [ref=e47] [cursor=pointer]
  - generic [ref=e48]:
    - heading "📊 Job Details" [level=2] [ref=e49]
    - generic [ref=e50]:
      - 'heading "Job: qa_job" [level=3] [ref=e51]'
      - paragraph [ref=e52]:
        - strong [ref=e53]: "Running:"
        - text: "No"
      - paragraph [ref=e54]:
        - strong [ref=e55]: "Has Results:"
        - text: "Yes"
      - paragraph [ref=e56]:
        - strong [ref=e57]: "Status:"
        - generic [ref=e58]: success
      - paragraph [ref=e59]:
        - strong [ref=e60]: "Items Scraped:"
        - text: "1"
      - paragraph [ref=e61]:
        - strong [ref=e62]: "Pages Visited:"
        - text: "1"
      - paragraph [ref=e63]:
        - strong [ref=e64]: "Errors:"
        - text: "0"
      - paragraph [ref=e65]:
        - strong [ref=e66]: "Duration:"
        - text: 0.50s
      - heading "Results (first 10 items):" [level=3] [ref=e67]
      - table [ref=e68]:
        - rowgroup [ref=e69]:
          - row [ref=e70]:
            - columnheader [ref=e71]:
              - emphasis [ref=e72]: literal heading
        - rowgroup [ref=e73]:
          - row [ref=e74]:
            - cell [ref=e75]:
              - strong [ref=e76]: literal value
    - button "Close" [ref=e77] [cursor=pointer]
```

# Test source

```ts
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
  94  |   await expect(page.locator('#job-list')).toContainText('No jobs yet');
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
> 159 |   await expect(page.locator('[data-qa-fixture]')).toHaveCount(0);
      |                                                   ^ Error: expect(locator).toHaveCount(expected) failed
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
  195 |   await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  196 |   await expect(page.locator('#job-list .job-item')).toHaveCount(1);
  197 | });
  198 | 
  199 | test('request in progress disables submit until analysis finishes', async ({ page }) => {
  200 |   let finish;
  201 |   const analyzeGate = new Promise(resolve => { finish = resolve; });
  202 |   const state = await setup(page, { analyzeGate });
  203 |   await openWorkingAssetPath(page);
  204 |   await submit(page);
  205 |   await expect(page.getByRole('button', { name: 'Analyzing...' })).toBeDisabled();
  206 |   expect(state.requests.filter(request => request.url.endsWith('/analyze'))).toHaveLength(1);
  207 |   finish();
  208 |   await expect(page.getByRole('button', { name: 'Start Auto-Scrape' })).toBeEnabled();
  209 | });
  210 | 
  211 | test('browser validation blocks page limits outside the visible range', async ({ page }) => {
  212 |   const state = await setup(page);
  213 |   await openWorkingAssetPath(page);
  214 |   for (const pages of ['0', '1001', '1.5']) {
  215 |     await submit(page, { pages });
  216 |     expect(await page.locator('#max-pages').evaluate(input => input.validity.valid)).toBe(false);
  217 |   }
  218 |   expect(state.requests.filter(request => request.method === 'POST')).toHaveLength(0);
  219 | });
  220 | 
  221 | test('list outage clears spinner and exposes failure', async ({ page }) => {
  222 |   await setup(page, { listStatus: 503 });
  223 |   await openWorkingAssetPath(page);
  224 |   await expect(page.locator('#job-list')).toContainText('Failed to load jobs');
  225 |   await page.screenshot({ path: path.join(artifacts, 'frontend-list-error.png'), fullPage: true });
  226 | });
  227 | 
  228 | test('running details can refresh into an empty completed result', async ({ page }) => {
  229 |   const state = await setup(page, { jobs: [sampleJob], status: { is_running: true, has_result: false }, items: [] });
  230 |   await openWorkingAssetPath(page);
  231 |   await page.getByRole('button', { name: 'View Details' }).click();
  232 |   await expect(page.locator('#job-details-content')).toContainText('Job is still running');
  233 |   state.status = { is_running: false, has_result: true, items_scraped: 0 };
  234 |   await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  235 |   await expect(page.locator('#job-details-content')).toContainText('No results yet');
  236 |   expect(state.errors).toEqual([]);
  237 | });
  238 | 
  239 | test('concurrency checkbox can request sequential run', async ({ page }) => {
  240 |   const state = await setup(page);
  241 |   await openWorkingAssetPath(page);
  242 |   await page.locator('#concurrent').uncheck();
  243 |   await submit(page, { format: 'csv' });
  244 |   await expect(page.locator('#job-list .job-item')).toHaveCount(1);
  245 |   const run = state.requests.find(request => new URL(request.url).pathname.endsWith('/run'));
  246 |   expect(new URL(run.url).searchParams.get('concurrent')).toBe('false');
  247 |   expect(modelSettings(state.created).formats).toEqual(['csv']);
  248 | });
  249 | 
  250 | test('local navigation performance and console/network evidence', async ({ page, browser }) => {
  251 |   const state = await setup(page, { jobs: [sampleJob] });
  252 |   await page.coverage.startJSCoverage();
  253 |   await openWorkingAssetPath(page);
  254 |   await page.getByRole('button', { name: 'View Details' }).click();
  255 |   await expect(page.locator('.results-table')).toBeVisible();
  256 |   const metrics = await page.evaluate(() => ({
  257 |     navigation: performance.getEntriesByType('navigation').map(entry => entry.toJSON()),
  258 |     paint: performance.getEntriesByType('paint').map(entry => entry.toJSON()),
  259 |     resources: performance.getEntriesByType('resource').map(entry => ({ name: entry.name, duration: entry.duration, transferSize: entry.transferSize })),
```