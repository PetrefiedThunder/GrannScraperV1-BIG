// Isolated DOM regressions. Requires the dev-only jsdom package in NODE_PATH.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { JSDOM } = require('jsdom');

const staticDirectory = path.resolve(__dirname, '../../scraper/web/static');
const sampleJob = {
  id: 'qa_job', name: 'Fictional catalog', start_url: 'https://example.invalid/catalog',
  created_at: '2026-10-02T12:00:00',
};
async function dashboard(t, overrides = {}) {
  const dom = new JSDOM(fs.readFileSync(path.join(staticDirectory, 'index.html'), 'utf8'), {
    url: 'http://127.0.0.1:18765/', runScripts: 'outside-only',
  });
  t.after(() => dom.window.close());
  const state = { jobs: [], requests: [], ...overrides };
  const { window } = dom;
  window.setInterval = () => 0;
  window.HTMLElement.prototype.scrollIntoView = () => {};
  window.confirm = () => true;
  window.console.error = () => {}; // Deliberate fictional error responses are asserted below.
  window.fetch = async (input, options = {}) => {
    const url = new URL(input, window.location.href);
    const request = { url, method: options.method || 'GET', body: options.body && JSON.parse(options.body) };
    state.requests.push(request);
    const endpoint = url.pathname.slice('/api/v1'.length);
    const json = (body, status = 200) => ({ ok: status < 400, json: async () => body });
    if (endpoint === '/info') return json({ statistics: { total_jobs: state.jobs.length, running_jobs: 0, completed_jobs: 0, workflows: 0 } });
    if (endpoint === '/analyze') return json({
      item_selector: '.product', fields: { title: { selector: 'h2', type: 'string' } },
      pagination: { mode: 'next_button', next_button_selector: 'a.next', max_pages: 10 },
    });
    if (endpoint === '/jobs' && request.method === 'POST') {
      state.created = request.body;
      state.jobs.push({ ...sampleJob, ...state.created.job });
      return json({ job_id: state.created.job.id });
    }
    if (endpoint === '/jobs') return json({ jobs: state.jobs });
    if (endpoint.endsWith('/run')) return json({ status: 'running' });
    if (endpoint.endsWith('/status')) {
      if (state.statusError) return json({ detail: state.statusError }, 503);
      return json({ is_running: false, has_result: true, status: 'success', items_scraped: 1, pages_visited: 1, errors: 0, duration: 0.5, ...state.status });
    }
    if (endpoint.endsWith('/results')) {
      if (state.resultsError) return json({ detail: state.resultsError }, 503);
      const items = state.items || [{ title: 'Fictional product', price: null }];
      return json({ items, total_items: items.length, pagination: { has_more: false }, ...state.results });
    }
    if (request.method === 'DELETE') {
      const id = decodeURIComponent(endpoint.slice('/jobs/'.length));
      state.jobs = state.jobs.filter(job => job.id !== id);
      return json({ status: 'deleted' });
    }
    throw new Error(`Unexpected mocked endpoint: ${endpoint}`);
  };
  // No resources or real requests are loaded; evaluate only the checked-in script.
  await window.eval(fs.readFileSync(path.join(staticDirectory, 'app.js'), 'utf8'));
  return { window, document: window.document, state };
}

test('FE-001 root dashboard resolves its script and initializes jobs', async t => {
  const { document } = await dashboard(t);
  const script = new URL(document.querySelector('script[src]').src);
  assert.equal(script.pathname, '/static/app.js');
  assert.equal(script.origin, 'http://127.0.0.1:18765');
  assert.match(document.querySelector('#job-list').textContent, /No jobs yet/);
  assert.equal(document.querySelector('#job-list-loading').classList.contains('hidden'), true);
});

test('FE-004 dashboard requests use the serving origin', async t => {
  const { state } = await dashboard(t);
  assert.ok(state.requests.length > 0);
  assert.deepEqual([...new Set(state.requests.map(request => request.url.origin))], ['http://127.0.0.1:18765']);
});

// Inert text fixtures only: no scripts, executable event handlers, or requests.
const markup = '<strong data-qa-fixture="literal">Literal product</strong>';

test('FE-005 job names, URLs, and IDs remain literal text', async t => {
  const { document } = await dashboard(t, { jobs: [{ ...sampleJob, id: markup, name: markup, start_url: markup }] });
  assert.equal(document.querySelectorAll('[data-qa-fixture]').length, 0);
  assert.equal(document.querySelector('.job-info h3').textContent, markup);
  assert.equal(document.querySelectorAll('[onclick*="viewJobDetails"], [onclick*="deleteJob"]').length, 0);
  assert.equal(document.querySelector('.job-info p').textContent.split(markup).length - 1, 2);
});

test('FE-005 scraped headers, values, and result counts remain literal text', async t => {
  const { window, document } = await dashboard(t, {
    jobs: [sampleJob], items: [{ [markup]: markup, empty: null }],
    results: { total_items: markup, pagination: { has_more: true } },
  });
  await window.viewJobDetails(sampleJob.id);
  assert.equal(document.querySelectorAll('[data-qa-fixture]').length, 0);
  assert.equal(document.querySelector('th').textContent, markup);
  assert.equal(document.querySelector('td').textContent, markup);
  assert.equal(document.querySelectorAll('td')[1].textContent, '-');
  assert.ok(document.querySelector('#job-details-content').textContent.includes(`Showing 10 of ${markup} items`));
});

test('FE-005 status text cannot create elements or attributes', async t => {
  const { window, document } = await dashboard(t, {
    jobs: [sampleJob], status: { status: markup, items_scraped: markup, pages_visited: markup, errors: markup },
  });
  await window.viewJobDetails(sampleJob.id);
  assert.equal(document.querySelectorAll('[data-qa-fixture]').length, 0);
  assert.equal(document.querySelector('.status-badge').textContent, markup);
  assert.equal(document.querySelector('.status-badge').className, 'status-badge');
});

for (const field of ['statusError', 'resultsError']) {
  test(`FE-005 ${field} remains literal text`, async t => {
    const { window, document } = await dashboard(t, { jobs: [sampleJob], [field]: markup });
    await window.viewJobDetails(sampleJob.id);
    assert.equal(document.querySelectorAll('[data-qa-fixture]').length, 0);
    assert.ok(document.querySelector('#job-details-content').textContent.includes(markup));
  });
}

test('FE-005 job action listeners preserve quoted and URL-significant IDs', async t => {
  const id = "qa_'/segment?query#fragment";
  const { document, state } = await dashboard(t, { jobs: [{ ...sampleJob, id }] });
  document.querySelector('.job-actions .btn').click();
  await new Promise(setImmediate);
  assert.ok(document.querySelector('#job-details-content').textContent.includes(`Job: ${id}`));
  assert.ok(state.requests.some(request => request.url.pathname === `/api/v1/jobs/${encodeURIComponent(id)}/status`));
  assert.ok(state.requests.some(request => request.url.pathname === `/api/v1/jobs/${encodeURIComponent(id)}/results`));
  document.querySelector('.job-actions .btn-secondary').click();
  await new Promise(setImmediate);
  assert.ok(state.requests.some(request => request.method === 'DELETE' && request.url.pathname === `/api/v1/jobs/${encodeURIComponent(id)}`));
  assert.equal(state.jobs.length, 0);
});

test('FE-005 refresh listener preserves job ID and renders successful results', async t => {
  const id = "qa_'/segment?query#fragment";
  const { window, document, state } = await dashboard(t, {
    jobs: [{ ...sampleJob, id }], status: { is_running: true, has_result: false },
  });
  await window.viewJobDetails(id);
  state.status = {};
  document.querySelector('#job-details-content button').click();
  await new Promise(setImmediate);
  assert.equal(document.querySelector('.status-badge').className, 'status-badge status-success');
  assert.equal(document.querySelector('td').textContent, 'Fictional product');
  assert.equal(document.querySelectorAll('td')[1].textContent, '-');
  assert.equal(state.requests.filter(request => request.url.pathname === `/api/v1/jobs/${encodeURIComponent(id)}/status`).length, 2);
});

for (const pages of [1, 2, 1000]) {
  test(`FE-002 selected page limit ${pages} survives dashboard submission and API validation`, async t => {
    const { window, document, state } = await dashboard(t);
    document.querySelector('#url').value = sampleJob.start_url;
    document.querySelector('#max-pages').value = String(pages);
    document.querySelector('#auto-scrape-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(setImmediate);
    assert.ok(state.created, 'Dashboard sends a create-job request');
    const persisted = JSON.parse(execFileSync(process.env.QA_PYTHON || 'python3', ['-m', 'tests.qa_frontend.validate_contract'], {
      input: JSON.stringify(state.created), encoding: 'utf8', cwd: path.resolve(__dirname, '../..'),
    }));
    assert.equal(persisted.max_pages, pages);
    assert.equal(state.created.job.pagination.mode, 'next_button');
    assert.equal(state.created.job.pagination.next_button_selector, 'a.next');
    assert.equal(Object.hasOwn(state.created.job, 'max_pages'), false);
    assert.equal(document.querySelectorAll('.job-item').length, 1);
    assert.equal(document.querySelector('#auto-scrape-form button[type="submit"]').disabled, false);
  });
}

for (const format of ['csv', 'json', 'excel']) {
  test(`FE-003 selected ${format} export survives dashboard submission and API validation`, async t => {
    const { window, document, state } = await dashboard(t);
    document.querySelector('#url').value = sampleJob.start_url;
    document.querySelector('#export-format').value = format;
    document.querySelector('#auto-scrape-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(setImmediate);
    assert.ok(state.created, 'Dashboard sends a create-job request');
    const persisted = JSON.parse(execFileSync(process.env.QA_PYTHON || 'python3', ['-m', 'tests.qa_frontend.validate_contract'], {
      input: JSON.stringify(state.created), encoding: 'utf8', cwd: path.resolve(__dirname, '../..'),
    }));
    assert.deepEqual(persisted.formats, [format]);
    assert.equal(document.querySelectorAll('.job-item').length, 1);
  });
}
