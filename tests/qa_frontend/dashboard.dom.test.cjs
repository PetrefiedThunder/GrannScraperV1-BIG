// Isolated DOM regressions. Requires the dev-only jsdom package in NODE_PATH.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const staticDirectory = path.resolve(__dirname, '../../scraper/web/static');
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
  window.fetch = async (input, options = {}) => {
    const url = new URL(input, window.location.href);
    const request = { url, method: options.method || 'GET', body: options.body && JSON.parse(options.body) };
    state.requests.push(request);
    const endpoint = url.pathname.slice('/api/v1'.length);
    const json = (body, status = 200) => ({ ok: status < 400, json: async () => body });
    if (endpoint === '/info') return json({ statistics: { total_jobs: state.jobs.length, running_jobs: 0, completed_jobs: 0, workflows: 0 } });
    if (endpoint === '/jobs') return json({ jobs: state.jobs });
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
