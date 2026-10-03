// Probe only the supplied browser server. Never launch or install a browser.
const { chromium, firefox, webkit } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const results = [];
  for (const [requested, browserType] of Object.entries({ chromium, firefox, webkit })) {
    let context;
    try {
      const browser = await browserType.connect(process.env.PW_TEST_CONNECT_WS_ENDPOINT || 'ws://127.0.0.1:3950/', { timeout: 4000 });
      context = await browser.newContext({ serviceWorkers: 'block' });
      await context.route('**/*', route => route.abort('blockedbyclient'));
      const page = await context.newPage();
      const userAgent = await page.evaluate(() => navigator.userAgent);
      const actualEngine = /Firefox\//.test(userAgent) ? 'firefox' : /Chrome\//.test(userAgent) ? 'chromium' : /AppleWebKit\//.test(userAgent) ? 'webkit' : 'unknown';
      results.push({ requested, actualEngine, version: browser.version(), userAgent, supportedAsRequested: actualEngine === requested });
    } catch (error) {
      results.push({ requested, supportedAsRequested: false, error: error.message });
    } finally {
      if (context) await context.close();
    }
  }
  fs.writeFileSync(path.resolve(__dirname, '../../docs/qa/2026-10-02/artifacts/frontend-browser-engines.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
  // Closing the process releases client connections; never stop the supplied server.
  process.exit(0);
})().catch(error => { console.error(error); process.exit(1); });
