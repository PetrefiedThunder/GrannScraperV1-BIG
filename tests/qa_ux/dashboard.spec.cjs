/* Offline UX regression checks. The browser is supplied by the orchestrator;
 * only the contexts created here are closed. No external request is allowed.
 */
const { test, expect, chromium } = require('@playwright/test');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const artifacts = process.env.QA_ARTIFACTS_DIR || path.join(root, 'docs/qa/2026-10-02/artifacts');
const origin = 'http://127.0.0.1:8766';
let server;
let browser;
let context;
let page;
let state;
let externalBlocked;
let apiRequests;
const jobs = [{
  id: 'qa-fictional-001', name: 'Fictional catalogue sample',
  start_url: 'https://catalogue.example.invalid/products/autumn-collection',
  created_at: '2026-10-02T12:00:00Z', enabled: true,
}];
function save(name, content) {
  fs.writeFileSync(path.join(artifacts, `ux-${name}.json`), JSON.stringify(content, null, 2));
}
async function shot(name) {
  await page.screenshot({ path: path.join(artifacts, `ux-${name}.png`), fullPage: true });
}
async function open(options = {}) {
  state = { jobs, ...options };
  await page.goto(`${origin}/static/index.html`);
  await expect(page.locator('#job-list-loading')).toHaveClass(/hidden/);
}
async function audit(name) {
  await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
  const result = await page.evaluate(async () => axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
  }));
  save(`axe-${name}`, result);
  fs.writeFileSync(path.join(artifacts, `ux-semantics-${name}.txt`), await page.locator('body').ariaSnapshot());
  return result;
}

test.beforeAll(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  server = http.createServer((request, response) => {
    const pathname = new URL(request.url, origin).pathname;
    const file = pathname === '/' || pathname === '/static/index.html' ? 'index.html'
      : pathname === '/static/app.js' ? 'app.js' : null;
    if (!file) { response.writeHead(404); response.end('Not found'); return; }
    response.setHeader('Content-Type', file.endsWith('.js') ? 'application/javascript' : 'text/html');
    response.end(fs.readFileSync(path.join(root, 'scraper/web/static', file)));
  });
  await new Promise(resolve => server.listen(8766, '127.0.0.1', resolve));
  browser = await chromium.connect(process.env.PW_TEST_CONNECT_WS_ENDPOINT);
});

test.beforeEach(async () => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  externalBlocked = [];
  apiRequests = [];
  state = { jobs };
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      externalBlocked.push(url.origin + url.pathname);
      await route.abort('blockedbyclient'); return;
    }
    if (!url.pathname.startsWith('/api/v1/')) { await route.continue(); return; }
    const endpoint = url.pathname.replace('/api/v1', '');
    const method = route.request().method();
    apiRequests.push({ endpoint, method });
    if (state.delayJobs && endpoint === '/jobs') await new Promise(resolve => setTimeout(resolve, 1000));
    let status = 200;
    let payload;
    if (endpoint === '/info') payload = { statistics: { total_jobs: state.jobs.length, running_jobs: 0, completed_jobs: state.jobs.length, workflows: 0 } };
    else if (endpoint === '/jobs' && method === 'GET') {
      status = state.errorJobs ? 503 : 200;
      payload = state.errorJobs ? { detail: 'Temporary QA fixture outage' } : { jobs: state.jobs };
    } else if (endpoint.endsWith('/status')) payload = {
      job_id: jobs[0].id, is_running: false, has_result: true, status: 'success',
      items_scraped: 25, pages_visited: 1, errors: 0, duration: 0.5,
    };
    else if (endpoint.endsWith('/results')) payload = {
      items: Array.from({ length: 10 }, (_, index) => ({ name: `Fictional product ${index + 1}`, price: index + 10, category: 'Sample catalogue' })),
      total_items: 25, pagination: { has_more: true, limit: 10, offset: 0 },
    };
    else if (endpoint === '/analyze') { status = 503; payload = { detail: 'Temporary QA fixture outage' }; }
    else { status = 404; payload = { detail: 'Unconfigured QA fixture' }; }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
  });
});

test.afterEach(async () => {
  expect(externalBlocked).toEqual([]);
  await context.close();
});
test.afterAll(async () => { await new Promise(resolve => server.close(resolve)); });

test('baseline: named controls, keyboard operation, native invalid URL, empty/loading semantics evidence', async () => {
  await open({ jobs: [] });
  await expect(page.getByText('No jobs yet. Start an auto-scrape above!')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Website URL:' })).toBeVisible();
  await expect(page.getByRole('spinbutton', { name: 'Maximum Pages:' })).toBeVisible();
  await shot('desktop-empty-initial');
  const focusOrder = [];
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press('Tab');
    focusOrder.push(await page.evaluate(() => ({ id: document.activeElement.id, tag: document.activeElement.tagName, text: document.activeElement.textContent.trim() })));
  }
  expect(focusOrder.map(item => item.id)).toEqual(['url', 'max-pages', 'export-format', 'concurrent', '']);
  await page.getByRole('checkbox').focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('checkbox')).not.toBeChecked();
  await page.locator('#url').fill('invalid-url');
  await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  expect(await page.locator('#url').evaluate(element => element.validity.typeMismatch)).toBe(true);
  save('keyboard-order', focusOrder);
  await audit('empty');
  await shot('desktop-empty');
  state.delayJobs = true;
  await page.evaluate(() => { window.qaLoading = loadJobs(); });
  await expect(page.locator('#job-list-loading')).toBeVisible();
  await shot('loading');
  await page.evaluate(() => window.qaLoading);
});

test('UX-001: populated mobile page reflows without document horizontal overflow', async () => {
  await page.setViewportSize({ width: 375, height: 812 });
  await open();
  await shot('mobile-jobs');
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, job: document.querySelector('.job-item').getBoundingClientRect().toJSON() }));
  save('mobile-layout', dimensions);
  await page.setViewportSize({ width: 320, height: 812 });
  await shot('mobile-320-jobs');
  save('mobile-320-layout', await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth })));
  test.fail(true, 'UX-001: job text and horizontal action row overflow the mobile viewport');
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
});

test('UX-002: text has WCAG AA contrast in completed results', async () => {
  await open();
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('table')).toBeVisible();
  const result = await audit('completed');
  await shot('desktop-results');
  test.fail(true, 'UX-002: visible normal-size text does not meet 4.5:1 contrast');
  expect(result.violations.filter(item => item.id === 'color-contrast')).toEqual([]);
});

test('UX-003: dynamic error is announced to screen readers', async () => {
  await open();
  await page.locator('#url').fill('https://catalogue.example.invalid');
  await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  await expect(page.locator('.alert-error').first()).toBeVisible();
  await shot('error-feedback');
  const errorSemantics = await page.locator('.alert-error').evaluateAll(elements => elements.map(element => {
    const region = element.closest('[aria-live], [role="alert"], [role="status"]');
    const live = region?.getAttribute('aria-live');
    const role = region?.getAttribute('role');
    return { text: element.textContent, role: element.getAttribute('role'), live: element.getAttribute('aria-live'), ancestorLive: live === 'polite' || live === 'assertive' || (!live && (role === 'alert' || role === 'status')) };
  }));
  save('error-semantics', errorSemantics);
  test.fail(true, 'UX-003: alert container and inserted feedback lack live-region semantics');
  expect(errorSemantics.some(item => item.ancestorLive)).toBe(true);
});

test('UX-004: opening details moves keyboard focus into visible detail context', async () => {
  await open();
  const details = page.getByRole('button', { name: 'View Details' });
  await details.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('table')).toBeVisible();
  const focus = await page.evaluate(() => ({ text: document.activeElement.textContent, insideDetails: Boolean(document.activeElement.closest('#job-details')) }));
  save('details-focus', focus);
  await shot('details-keyboard-focus');
  test.fail(true, 'UX-004: only visual scroll changes; focus remains on original View Details');
  expect(focus.insideDetails).toBe(true);
});

test('UX-005: users can retrieve result items beyond the preview', async () => {
  await open();
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.getByText('Showing 10 of 25 items')).toBeVisible();
  expect(await page.locator('tbody tr').count()).toBe(10);
  save('result-actions', await page.getByRole('button').allTextContents());
  test.fail(true, 'UX-005: no next-page, export, download or full-results action exists');
  await expect(page.getByRole('button', { name: /next|download|export|all results/i }).or(page.getByRole('link', { name: /next|download|export|all results/i }))).not.toHaveCount(0);
});

test('UX-006: failed job-list load offers an in-app retry', async () => {
  await page.clock.install();
  await open({ errorJobs: true });
  await expect(page.getByText('Failed to load jobs', { exact: true })).toBeVisible();
  await shot('jobs-error');
  await audit('jobs-error');
  const before = apiRequests.filter(item => item.endpoint === '/jobs').length;
  state.errorJobs = false;
  await page.clock.runFor(11000);
  const after = apiRequests.filter(item => item.endpoint === '/jobs').length;
  const pageStillFailed = await page.getByText('Failed to load jobs', { exact: true }).isVisible();
  const recovered = !pageStillFailed && await page.getByRole('button', { name: 'View Details' }).first().isVisible();
  const retryAvailable = await page.getByRole('button', { name: /retry|refresh/i }).first().isVisible();
  save('error-recovery', { jobsRequestsBeforeRecovery: before, jobsRequestsAfter11Seconds: after, infoRequests: apiRequests.filter(item => item.endpoint === '/info').length, pageStillFailed, recovered, retryAvailable });
  test.fail(true, 'UX-006: job list stays failed and has no Retry or Refresh control');
  expect(recovered || retryAvailable).toBe(true);
});

test('evidence: 200 percent text scale and close focus state', async () => {
  await open();
  await page.evaluate(() => { document.body.style.fontSize = '200%'; });
  await shot('text-scale-200');
  save('text-scale-200', await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth })));
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('table')).toBeVisible();
  await page.getByRole('button', { name: 'Close', exact: true }).focus();
  await page.keyboard.press('Enter');
  save('close-focus', await page.evaluate(() => ({ tag: document.activeElement.tagName, id: document.activeElement.id, hidden: Boolean(document.activeElement.closest('.hidden')) })));
  await expect(page.locator('#job-details')).toBeHidden();
});

test('UX-004: closing details restores visible keyboard focus', async () => {
  await open();
  await page.getByRole('button', { name: 'View Details' }).click();
  await expect(page.locator('table')).toBeVisible();
  await page.getByRole('button', { name: 'Close', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#job-details')).toBeHidden();
  test.fail(true, 'UX-004: focus stays on hidden Close button instead of returning to opener');
  expect(await page.evaluate(() => Boolean(document.activeElement.closest('.hidden')))).toBe(false);
});
