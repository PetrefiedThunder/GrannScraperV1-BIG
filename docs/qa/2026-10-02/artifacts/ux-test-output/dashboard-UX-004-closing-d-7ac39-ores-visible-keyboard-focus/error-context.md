# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: dashboard.spec.cjs >> UX-004: closing details restores visible keyboard focus
- Location: tests/qa_ux/dashboard.spec.cjs:224:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true
```

# Test source

```ts
  132 |   await open();
  133 |   await shot('mobile-jobs');
  134 |   const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, job: document.querySelector('.job-item').getBoundingClientRect().toJSON() }));
  135 |   save('mobile-layout', dimensions);
  136 |   await page.setViewportSize({ width: 320, height: 812 });
  137 |   await shot('mobile-320-jobs');
  138 |   save('mobile-320-layout', await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth })));
  139 |   test.fail(true, 'UX-001: job text and horizontal action row overflow the mobile viewport');
  140 |   expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  141 | });
  142 | 
  143 | test('UX-002: text has WCAG AA contrast in completed results', async () => {
  144 |   await open();
  145 |   await page.getByRole('button', { name: 'View Details' }).click();
  146 |   await expect(page.locator('table')).toBeVisible();
  147 |   const result = await audit('completed');
  148 |   await shot('desktop-results');
  149 |   test.fail(true, 'UX-002: visible normal-size text does not meet 4.5:1 contrast');
  150 |   expect(result.violations.filter(item => item.id === 'color-contrast')).toEqual([]);
  151 | });
  152 | 
  153 | test('UX-003: dynamic error is announced to screen readers', async () => {
  154 |   await open();
  155 |   await page.locator('#url').fill('https://catalogue.example.invalid');
  156 |   await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  157 |   await expect(page.locator('.alert-error').first()).toBeVisible();
  158 |   await shot('error-feedback');
  159 |   const errorSemantics = await page.locator('.alert-error').evaluateAll(elements => elements.map(element => {
  160 |     const region = element.closest('[aria-live], [role="alert"], [role="status"]');
  161 |     const live = region?.getAttribute('aria-live');
  162 |     const role = region?.getAttribute('role');
  163 |     return { text: element.textContent, role: element.getAttribute('role'), live: element.getAttribute('aria-live'), ancestorLive: live === 'polite' || live === 'assertive' || (!live && (role === 'alert' || role === 'status')) };
  164 |   }));
  165 |   save('error-semantics', errorSemantics);
  166 |   test.fail(true, 'UX-003: alert container and inserted feedback lack live-region semantics');
  167 |   expect(errorSemantics.some(item => item.ancestorLive)).toBe(true);
  168 | });
  169 | 
  170 | test('UX-004: opening details moves keyboard focus into visible detail context', async () => {
  171 |   await open();
  172 |   const details = page.getByRole('button', { name: 'View Details' });
  173 |   await details.focus();
  174 |   await page.keyboard.press('Enter');
  175 |   await expect(page.locator('table')).toBeVisible();
  176 |   const focus = await page.evaluate(() => ({ text: document.activeElement.textContent, insideDetails: Boolean(document.activeElement.closest('#job-details')) }));
  177 |   save('details-focus', focus);
  178 |   await shot('details-keyboard-focus');
  179 |   test.fail(true, 'UX-004: only visual scroll changes; focus remains on original View Details');
  180 |   expect(focus.insideDetails).toBe(true);
  181 | });
  182 | 
  183 | test('UX-005: users can retrieve result items beyond the preview', async () => {
  184 |   await open();
  185 |   await page.getByRole('button', { name: 'View Details' }).click();
  186 |   await expect(page.getByText('Showing 10 of 25 items')).toBeVisible();
  187 |   expect(await page.locator('tbody tr').count()).toBe(10);
  188 |   save('result-actions', await page.getByRole('button').allTextContents());
  189 |   test.fail(true, 'UX-005: no next-page, export, download or full-results action exists');
  190 |   await expect(page.getByRole('button', { name: /next|download|export|all results/i }).or(page.getByRole('link', { name: /next|download|export|all results/i }))).not.toHaveCount(0);
  191 | });
  192 | 
  193 | test('UX-006: failed job-list load offers an in-app retry', async () => {
  194 |   await page.clock.install();
  195 |   await open({ errorJobs: true });
  196 |   await expect(page.getByText('Failed to load jobs', { exact: true })).toBeVisible();
  197 |   await shot('jobs-error');
  198 |   await audit('jobs-error');
  199 |   const before = apiRequests.filter(item => item.endpoint === '/jobs').length;
  200 |   state.errorJobs = false;
  201 |   await page.clock.runFor(11000);
  202 |   const after = apiRequests.filter(item => item.endpoint === '/jobs').length;
  203 |   const pageStillFailed = await page.getByText('Failed to load jobs', { exact: true }).isVisible();
  204 |   const recovered = !pageStillFailed && await page.getByRole('button', { name: 'View Details' }).first().isVisible();
  205 |   const retryAvailable = await page.getByRole('button', { name: /retry|refresh/i }).first().isVisible();
  206 |   save('error-recovery', { jobsRequestsBeforeRecovery: before, jobsRequestsAfter11Seconds: after, infoRequests: apiRequests.filter(item => item.endpoint === '/info').length, pageStillFailed, recovered, retryAvailable });
  207 |   test.fail(true, 'UX-006: job list stays failed and has no Retry or Refresh control');
  208 |   expect(recovered || retryAvailable).toBe(true);
  209 | });
  210 | 
  211 | test('evidence: 200 percent text scale and close focus state', async () => {
  212 |   await open();
  213 |   await page.evaluate(() => { document.body.style.fontSize = '200%'; });
  214 |   await shot('text-scale-200');
  215 |   save('text-scale-200', await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth })));
  216 |   await page.getByRole('button', { name: 'View Details' }).click();
  217 |   await expect(page.locator('table')).toBeVisible();
  218 |   await page.getByRole('button', { name: 'Close', exact: true }).focus();
  219 |   await page.keyboard.press('Enter');
  220 |   save('close-focus', await page.evaluate(() => ({ tag: document.activeElement.tagName, id: document.activeElement.id, hidden: Boolean(document.activeElement.closest('.hidden')) })));
  221 |   await expect(page.locator('#job-details')).toBeHidden();
  222 | });
  223 | 
  224 | test('UX-004: closing details restores visible keyboard focus', async () => {
  225 |   await open();
  226 |   await page.getByRole('button', { name: 'View Details' }).click();
  227 |   await expect(page.locator('table')).toBeVisible();
  228 |   await page.getByRole('button', { name: 'Close', exact: true }).focus();
  229 |   await page.keyboard.press('Enter');
  230 |   await expect(page.locator('#job-details')).toBeHidden();
  231 |   test.fail(true, 'UX-004: focus stays on hidden Close button instead of returning to opener');
> 232 |   expect(await page.evaluate(() => Boolean(document.activeElement.closest('.hidden')))).toBe(false);
      |                                                                                         ^ Error: expect(received).toBe(expected) // Object.is equality
  233 | });
  234 | 
```