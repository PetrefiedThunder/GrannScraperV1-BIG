const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const artifacts = process.env.QA_ARTIFACTS_DIR || path.resolve(__dirname, '../../docs/qa/2026-10-02/artifacts');
const target = 'https://example.invalid/catalog';
// Response keys mirror rest_server.py:94-143,306-358,365-410,557-578.
const analysis = {
  url: target, item_selector: '.product',
  fields: { title: { selector: 'h2', type: 'string', confidence: 1, auto_detected: true } },
  pagination: { mode: 'next_button', next_button_selector: 'a.next', confidence: 0.9 },
  analysis: { html_size: 100, links: 2, images: 0, title: 'Fictional catalog' },
};
const sampleJob = {
  id: 'qa_job', name: 'Fictional catalog', start_url: target, enabled: true,
  created_at: '2026-10-02T12:00:00',
};

async function setup(page, overrides = {}) {
  const state = { jobs: [], requests: [], errors: [], failed: [], blocked: [], ...overrides };
  page.on('pageerror', error => state.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') state.errors.push(message.text()); });
  page.on('requestfailed', request => state.failed.push({ url: request.url(), error: request.failure()?.errorText }));
  await page.context().route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/v1/')) {
      // All API calls are intercepted, even the incorrect localhost:8000 origin.
      state.requests.push({ url: request.url(), method: request.method(), body: request.postDataJSON() });
      const json = async (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
      const endpoint = url.pathname.slice('/api/v1'.length);
      if (endpoint === '/info') return json({ version: '1.0.0', name: 'GrandmaScrape API', statistics: { total_jobs: state.jobs.length, running_jobs: 0, completed_jobs: state.jobs.length, workflows: 0 }, features: [] });
      if (endpoint === '/analyze') {
        if (state.analyzeGate) await state.analyzeGate;
        if (state.analyzeStatus) return json({ detail: state.analyzeDetail || 'Fictional analysis failure' }, state.analyzeStatus);
        if (state.analyzeNonJSON) return route.fulfill({ status: 502, contentType: 'text/plain', body: 'Fictional service unavailable' });
        return json(analysis);
      }
      if (endpoint === '/jobs' && request.method() === 'POST') {
        state.created = request.postDataJSON();
        const job = state.created.job;
        state.jobs.push({ ...sampleJob, id: job.id, name: job.name, start_url: job.start_url });
        return json({ job_id: job.id, status: 'created', message: `Job ${job.name} created successfully` });
      }
      if (endpoint === '/jobs') {
        if (state.listStatus) return json({ detail: 'Fictional temporary outage' }, state.listStatus);
        return json({ total: state.jobs.length, jobs: state.jobs });
      }
      if (endpoint.endsWith('/run')) return json({ job_id: state.created?.job.id || 'qa_job', status: 'running', message: 'Job started', concurrent: url.searchParams.get('concurrent') === 'true', incremental: false });
      if (endpoint.endsWith('/status')) return json({ job_id: 'qa_job', is_running: false, has_result: true, status: 'success', items_scraped: 1, pages_visited: 1, errors: 0, duration: 0.5, ...state.status });
      if (endpoint.endsWith('/results')) {
        const items = state.items || [{ title: 'Fictional product', price: '$10.00' }];
        return json({ job_id: 'qa_job', status: 'success', total_items: items.length, pages_visited: 1, errors: [], items: items.slice(0, 10), pagination: { limit: 10, offset: 0, has_more: items.length > 10 } });
      }
      if (request.method() === 'DELETE') {
        state.jobs = state.jobs.filter(job => job.id !== endpoint.split('/').pop());
        return json({ status: 'deleted', job_id: 'qa_job' });
      }
      return json({ detail: 'Unmocked API request' }, 500);
    }
    if (url.origin === 'http://127.0.0.1:18765') return route.continue();
    state.blocked.push(request.url());
    return route.abort('blockedbyclient');
  });
  return state;
}

async function openWorkingAssetPath(page) {
  // Explicit workaround for FE-001; never confuse this with the real / entry page.
  await page.goto('/static/index.html');
  await expect(page.locator('#job-list-loading')).toBeHidden();
}

async function submit(page, { pages = '2', format = 'json' } = {}) {
  await page.locator('#url').fill(target);
  await page.locator('#max-pages').fill(pages);
  await page.locator('#export-format').selectOption(format);
  await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
}

function modelSettings(payload) {
  return JSON.parse(execFileSync(process.env.QA_PYTHON || 'python3', ['-m', 'tests.qa_frontend.validate_contract'], { input: JSON.stringify(payload), encoding: 'utf8', cwd: path.resolve(__dirname, '../..') }));
}

test('FE-001 root dashboard loads its script and initial jobs', async ({ page }) => {
  const state = await setup(page);
  const response = await page.goto('/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('GrandmaScrape Dashboard');
  await expect(page.locator('#auto-scrape-form')).toBeVisible();
  await page.screenshot({ path: path.join(artifacts, 'frontend-root-script-404.png'), fullPage: true });
  fs.writeFileSync(path.join(artifacts, 'frontend-root-errors.json'), JSON.stringify(state, null, 2));
  await expect(page.locator('#job-list')).toContainText('No jobs yet');
});

test('working asset route: empty state then analysis/create/run/list flow', async ({ page }, testInfo) => {
  const state = await setup(page);
  await openWorkingAssetPath(page);
  await expect(page.locator('#job-list')).toContainText('No jobs yet');
  await submit(page);
  await expect(page.locator('#job-list')).toContainText(`Auto-scraped: ${target}`);
  const mutations = state.requests.filter(request => request.method === 'POST');
  expect(mutations.map(request => new URL(request.url).pathname.replace(/job_\d+/, 'ID'))).toEqual(['/api/v1/analyze', '/api/v1/jobs', '/api/v1/jobs/ID/run']);
  expect(new URL(mutations[2].url).searchParams.get('concurrent')).toBe('true');
  await expect(page.locator('#url')).toHaveValue('');
  expect(state.errors).toEqual([]);
  expect(state.blocked).toEqual([]);
  fs.writeFileSync(path.join(artifacts, `frontend-main-flow-${testInfo.project.name}.json`), JSON.stringify({ requests: state.requests, normalized_settings: modelSettings(state.created), console_errors: state.errors, failed_requests: state.failed, blocked: state.blocked }, null, 2));
});

for (const pages of ['1', '2', '1000']) {
  test(`FE-002 selected page limit ${pages} survives API model validation`, async ({ page }) => {
    const state = await setup(page);
    await openWorkingAssetPath(page);
    await submit(page, { pages });
    await expect(page.locator('#job-list .job-item')).toHaveCount(1);
    const persisted = modelSettings(state.created);
    test.fail(true, 'FE-002: max_pages sent at job root is ignored instead of pagination.max_pages');
    expect(persisted.max_pages).toBe(Number(pages));
  });
}

for (const format of ['json', 'excel']) {
  test(`FE-003 selected ${format} export survives API model validation`, async ({ page }) => {
    const state = await setup(page);
    await openWorkingAssetPath(page);
    await submit(page, { format });
    await expect(page.locator('#job-list .job-item')).toHaveCount(1);
    const persisted = modelSettings(state.created);
    test.fail(true, 'FE-003: export.format is ignored; model expects export.formats');
    expect(persisted.formats).toEqual([format]);
  });
}

test('FE-004 dashboard API requests use the serving origin', async ({ page }) => {
  const state = await setup(page);
  await openWorkingAssetPath(page);
  expect([...new Set(state.requests.map(request => new URL(request.url).origin))]).toEqual([new URL(page.url()).origin]);
});

test('FE-005 job names are rendered as text, not HTML elements', async ({ page }) => {
  // Inert formatting only: no scripts, event handlers, requests, or executable payloads.
  const name = '<strong data-qa-fixture="literal">Literal product name</strong>';
  await setup(page, { jobs: [{ ...sampleJob, name }] });
  await openWorkingAssetPath(page);
  await page.screenshot({ path: path.join(artifacts, 'frontend-literal-markup.png'), fullPage: true });
  test.fail(true, 'FE-005: job.name is interpolated into innerHTML');
  await expect(page.locator('[data-qa-fixture="literal"]')).toHaveCount(0);
});

test('FE-005 scraped field names and values remain literal text', async ({ page }) => {
  await setup(page, { jobs: [sampleJob], items: [{ '<em data-qa-fixture="field">literal heading</em>': '<strong data-qa-fixture="value">literal value</strong>' }] });
  await openWorkingAssetPath(page);
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('.results-table')).toBeVisible();
  test.fail(true, 'FE-005: results are interpolated into innerHTML');
  await expect(page.locator('[data-qa-fixture]')).toHaveCount(0);
});

test('results can be opened and closed; null values show a dash', async ({ page }, testInfo) => {
  const state = await setup(page, { jobs: [sampleJob], items: [{ title: 'Fictional product', price: null }] });
  await openWorkingAssetPath(page);
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('.results-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.results-table tbody td').nth(1)).toHaveText('-');
  await page.screenshot({ path: path.join(artifacts, `frontend-results-${testInfo.project.name}.png`), fullPage: true });
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await expect(page.locator('#job-details')).toBeHidden();
  expect(state.errors).toEqual([]);
});

test('delete requires confirmation; cancelling keeps job; confirming removes it', async ({ page }) => {
  const state = await setup(page, { jobs: [sampleJob] });
  await openWorkingAssetPath(page);
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  expect(state.requests.some(request => request.method === 'DELETE')).toBe(false);
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.locator('#job-list')).toContainText('No jobs yet');
  expect(state.requests.filter(request => request.method === 'DELETE')).toHaveLength(1);
});

test('analyze error preserves input and lets user retry successfully', async ({ page }) => {
  const state = await setup(page, { analyzeStatus: 400 });
  await openWorkingAssetPath(page);
  await submit(page);
  await expect(page.locator('#alert-container')).toContainText('Fictional analysis failure');
  await expect(page.getByRole('button', { name: 'Start Auto-Scrape' })).toBeEnabled();
  await expect(page.locator('#url')).toHaveValue(target);
  expect(state.created).toBeUndefined();
  state.analyzeStatus = 0;
  await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  await expect(page.locator('#job-list .job-item')).toHaveCount(1);
});

test('request in progress disables submit until analysis finishes', async ({ page }) => {
  let finish;
  const analyzeGate = new Promise(resolve => { finish = resolve; });
  const state = await setup(page, { analyzeGate });
  await openWorkingAssetPath(page);
  await submit(page);
  await expect(page.getByRole('button', { name: 'Analyzing...' })).toBeDisabled();
  expect(state.requests.filter(request => request.url.endsWith('/analyze'))).toHaveLength(1);
  finish();
  await expect(page.getByRole('button', { name: 'Start Auto-Scrape' })).toBeEnabled();
});

test('browser validation blocks page limits outside the visible range', async ({ page }) => {
  const state = await setup(page);
  await openWorkingAssetPath(page);
  for (const pages of ['0', '1001', '1.5']) {
    await submit(page, { pages });
    expect(await page.locator('#max-pages').evaluate(input => input.validity.valid)).toBe(false);
  }
  expect(state.requests.filter(request => request.method === 'POST')).toHaveLength(0);
});

test('list outage clears spinner and exposes failure', async ({ page }) => {
  await setup(page, { listStatus: 503 });
  await openWorkingAssetPath(page);
  await expect(page.locator('#job-list')).toContainText('Failed to load jobs');
  await page.screenshot({ path: path.join(artifacts, 'frontend-list-error.png'), fullPage: true });
});

test('running details can refresh into an empty completed result', async ({ page }) => {
  const state = await setup(page, { jobs: [sampleJob], status: { is_running: true, has_result: false }, items: [] });
  await openWorkingAssetPath(page);
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('#job-details-content')).toContainText('Job is still running');
  state.status = { is_running: false, has_result: true, items_scraped: 0 };
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await expect(page.locator('#job-details-content')).toContainText('No results yet');
  expect(state.errors).toEqual([]);
});

test('concurrency checkbox can request sequential run', async ({ page }) => {
  const state = await setup(page);
  await openWorkingAssetPath(page);
  await page.locator('#concurrent').uncheck();
  await submit(page, { format: 'csv' });
  await expect(page.locator('#job-list .job-item')).toHaveCount(1);
  const run = state.requests.find(request => new URL(request.url).pathname.endsWith('/run'));
  expect(new URL(run.url).searchParams.get('concurrent')).toBe('false');
  expect(modelSettings(state.created).formats).toEqual(['csv']);
});

test('local navigation performance and console/network evidence', async ({ page, browser }) => {
  const state = await setup(page, { jobs: [sampleJob] });
  await page.coverage.startJSCoverage();
  await openWorkingAssetPath(page);
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('.results-table')).toBeVisible();
  const metrics = await page.evaluate(() => ({
    navigation: performance.getEntriesByType('navigation').map(entry => entry.toJSON()),
    paint: performance.getEntriesByType('paint').map(entry => entry.toJSON()),
    resources: performance.getEntriesByType('resource').map(entry => ({ name: entry.name, duration: entry.duration, transferSize: entry.transferSize })),
    userAgent: navigator.userAgent,
  }));
  const coverage = (await page.coverage.stopJSCoverage()).filter(entry => entry.url.endsWith('/app.js')).map(entry => {
    const ranges = entry.functions.flatMap(fn => fn.ranges);
    const boundaries = [...new Set(ranges.flatMap(range => [range.startOffset, range.endOffset]))].sort((a, b) => a - b);
    let executed = 0;
    for (let i = 0; i < boundaries.length - 1; i++) {
      const start = boundaries[i], end = boundaries[i + 1];
      const enclosing = ranges.filter(range => range.startOffset <= start && range.endOffset >= end).sort((a, b) => (a.endOffset - a.startOffset) - (b.endOffset - b.startOffset));
      if (enclosing[0]?.count > 0) executed += end - start;
    }
    return { url: entry.url, total_utf16_units: entry.source?.length, executed_utf16_units: executed, functions: entry.functions };
  });
  fs.writeFileSync(path.join(artifacts, 'frontend-performance.json'), JSON.stringify({ ...metrics, browserVersion: browser.version(), console_errors: state.errors, failed_requests: state.failed, blocked: state.blocked, coverage, note: 'Unthrottled loopback diagnostic; not Lighthouse or production measurement. Coverage limited to this empty/list/details journey.' }, null, 2));
  expect(state.errors).toEqual([]);
  expect(state.blocked).toEqual([]);
});
