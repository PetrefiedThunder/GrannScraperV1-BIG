# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: dashboard.spec.cjs >> UX-004: opening details moves keyboard focus into visible detail context
- Location: tests/qa_ux/dashboard.spec.cjs:170:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: true
Received: false
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
          - heading "Fictional catalogue sample" [level=3] [ref=e40]
          - paragraph [ref=e41]:
            - strong [ref=e42]: "URL:"
            - text: https://catalogue.example.invalid/products/autumn-collection
            - strong [ref=e43]: "ID:"
            - text: qa-fictional-001
            - strong [ref=e44]: "Created:"
            - text: 10/2/2026, 5:00:00 AM
        - generic [ref=e45]:
          - button "View Details" [active] [ref=e46] [cursor=pointer]
          - button "Delete" [ref=e47] [cursor=pointer]
  - generic [ref=e48]:
    - heading "📊 Job Details" [level=2] [ref=e49]
    - generic [ref=e50]:
      - 'heading "Job: qa-fictional-001" [level=3] [ref=e51]'
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
        - text: "25"
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
            - columnheader "name" [ref=e71]
            - columnheader "price" [ref=e72]
            - columnheader "category" [ref=e73]
        - rowgroup [ref=e74]:
          - row [ref=e75]:
            - cell "Fictional product 1" [ref=e76]
            - cell "10" [ref=e77]
            - cell "Sample catalogue" [ref=e78]
          - row [ref=e79]:
            - cell "Fictional product 2" [ref=e80]
            - cell "11" [ref=e81]
            - cell "Sample catalogue" [ref=e82]
          - row [ref=e83]:
            - cell "Fictional product 3" [ref=e84]
            - cell "12" [ref=e85]
            - cell "Sample catalogue" [ref=e86]
          - row [ref=e87]:
            - cell "Fictional product 4" [ref=e88]
            - cell "13" [ref=e89]
            - cell "Sample catalogue" [ref=e90]
          - row [ref=e91]:
            - cell "Fictional product 5" [ref=e92]
            - cell "14" [ref=e93]
            - cell "Sample catalogue" [ref=e94]
          - row [ref=e95]:
            - cell "Fictional product 6" [ref=e96]
            - cell "15" [ref=e97]
            - cell "Sample catalogue" [ref=e98]
          - row [ref=e99]:
            - cell "Fictional product 7" [ref=e100]
            - cell "16" [ref=e101]
            - cell "Sample catalogue" [ref=e102]
          - row [ref=e103]:
            - cell "Fictional product 8" [ref=e104]
            - cell "17" [ref=e105]
            - cell "Sample catalogue" [ref=e106]
          - row [ref=e107]:
            - cell "Fictional product 9" [ref=e108]
            - cell "18" [ref=e109]
            - cell "Sample catalogue" [ref=e110]
          - row [ref=e111]:
            - cell "Fictional product 10" [ref=e112]
            - cell "19" [ref=e113]
            - cell "Sample catalogue" [ref=e114]
      - paragraph [ref=e115]:
        - emphasis [ref=e116]: Showing 10 of 25 items
    - button "Close" [ref=e117] [cursor=pointer]
```

# Test source

```ts
  80  |       status = state.errorJobs ? 503 : 200;
  81  |       payload = state.errorJobs ? { detail: 'Temporary QA fixture outage' } : { jobs: state.jobs };
  82  |     } else if (endpoint.endsWith('/status')) payload = {
  83  |       job_id: jobs[0].id, is_running: false, has_result: true, status: 'success',
  84  |       items_scraped: 25, pages_visited: 1, errors: 0, duration: 0.5,
  85  |     };
  86  |     else if (endpoint.endsWith('/results')) payload = {
  87  |       items: Array.from({ length: 10 }, (_, index) => ({ name: `Fictional product ${index + 1}`, price: index + 10, category: 'Sample catalogue' })),
  88  |       total_items: 25, pagination: { has_more: true, limit: 10, offset: 0 },
  89  |     };
  90  |     else if (endpoint === '/analyze') { status = 503; payload = { detail: 'Temporary QA fixture outage' }; }
  91  |     else { status = 404; payload = { detail: 'Unconfigured QA fixture' }; }
  92  |     await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
  93  |   });
  94  | });
  95  | 
  96  | test.afterEach(async () => {
  97  |   expect(externalBlocked).toEqual([]);
  98  |   await context.close();
  99  | });
  100 | test.afterAll(async () => { await new Promise(resolve => server.close(resolve)); });
  101 | 
  102 | test('baseline: named controls, keyboard operation, native invalid URL, empty/loading semantics evidence', async () => {
  103 |   await open({ jobs: [] });
  104 |   await expect(page.getByText('No jobs yet. Start an auto-scrape above!')).toBeVisible();
  105 |   await expect(page.getByRole('textbox', { name: 'Website URL:' })).toBeVisible();
  106 |   await expect(page.getByRole('spinbutton', { name: 'Maximum Pages:' })).toBeVisible();
  107 |   await shot('desktop-empty-initial');
  108 |   const focusOrder = [];
  109 |   for (let i = 0; i < 5; i++) {
  110 |     await page.keyboard.press('Tab');
  111 |     focusOrder.push(await page.evaluate(() => ({ id: document.activeElement.id, tag: document.activeElement.tagName, text: document.activeElement.textContent.trim() })));
  112 |   }
  113 |   expect(focusOrder.map(item => item.id)).toEqual(['url', 'max-pages', 'export-format', 'concurrent', '']);
  114 |   await page.getByRole('checkbox').focus();
  115 |   await page.keyboard.press('Space');
  116 |   await expect(page.getByRole('checkbox')).not.toBeChecked();
  117 |   await page.locator('#url').fill('invalid-url');
  118 |   await page.getByRole('button', { name: 'Start Auto-Scrape' }).click();
  119 |   expect(await page.locator('#url').evaluate(element => element.validity.typeMismatch)).toBe(true);
  120 |   save('keyboard-order', focusOrder);
  121 |   await audit('empty');
  122 |   await shot('desktop-empty');
  123 |   state.delayJobs = true;
  124 |   await page.evaluate(() => { window.qaLoading = loadJobs(); });
  125 |   await expect(page.locator('#job-list-loading')).toBeVisible();
  126 |   await shot('loading');
  127 |   await page.evaluate(() => window.qaLoading);
  128 | });
  129 | 
  130 | test('UX-001: populated mobile page reflows without document horizontal overflow', async () => {
  131 |   await page.setViewportSize({ width: 375, height: 812 });
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
> 180 |   expect(focus.insideDetails).toBe(true);
      |                               ^ Error: expect(received).toBe(expected) // Object.is equality
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
  232 |   expect(await page.evaluate(() => Boolean(document.activeElement.closest('.hidden')))).toBe(false);
  233 | });
  234 | 
```