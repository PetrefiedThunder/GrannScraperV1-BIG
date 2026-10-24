const { defineConfig } = require('@playwright/test');
const path = require('node:path');
const artifacts = path.resolve(__dirname, '../../docs/qa/2026-10-02/artifacts');
module.exports = defineConfig({
  testDir: __dirname,
  testMatch: 'dashboard.spec.cjs',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 20000,
  expect: { timeout: 2500 },
  reporter: [['list'], ['json', { outputFile: path.join(artifacts, 'frontend-playwright.json') }]],
  outputDir: path.join(artifacts, 'frontend-test-results'),
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', grep: /working asset route:|results can be opened/, use: { browserName: 'firefox' } },
    { name: 'webkit', grep: /working asset route:|results can be opened/, use: { browserName: 'webkit' } },
  ],
  use: {
    browserName: 'chromium',
    baseURL: 'http://127.0.0.1:18765',
    viewport: { width: 1440, height: 1000 },
    serviceWorkers: 'block',
    screenshot: 'off',
    trace: 'off',
    connectOptions: { wsEndpoint: process.env.PW_TEST_CONNECT_WS_ENDPOINT || 'ws://127.0.0.1:3950/' },
  },
  webServer: {
    command: `node ${JSON.stringify(path.join(__dirname, 'server.cjs'))}`,
    url: 'http://127.0.0.1:18765/',
    reuseExistingServer: false,
    timeout: 10000,
  },
});
