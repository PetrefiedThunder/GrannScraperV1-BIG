const { defineConfig } = require('@playwright/test');
const path = require('node:path');
const artifacts = process.env.QA_ARTIFACTS_DIR || path.resolve(__dirname, '../../docs/qa/2026-10-02/artifacts');

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: '*.spec.cjs',
  workers: 1,
  fullyParallel: false,
  timeout: 30000,
  expect: { timeout: 1500 },
  reporter: [['list'], ['json', { outputFile: path.join(artifacts, 'ux-playwright-results.json') }]],
  outputDir: path.join(artifacts, 'ux-test-output'),
});
