/* Optional development-only browser QA. The delivered HTML has no dependencies. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(root, 'outputs/dashboard_ready/dashboard_data.json')));
const pct = n => (100 * n).toFixed(2) + '%';
const checks = [];

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1512, height: 1100}, deviceScaleFactor: 1, offline: true});
    const page = await context.newPage(), errors = [], network = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root, 'dashboard.html')).href);
    await page.locator('#metrics .value').first().waitFor();
    fs.mkdirSync(path.join(root, 'screenshots'), {recursive: true});
    await page.screenshot({path: path.join(root, 'screenshots/dashboard-overview.png')});
    for (const runName of ['balanced', 'baseline']) {
      await page.selectOption('#run', runName);
      const run = data.runs[runName], m = run.metrics;
      for (const key of ['accuracy', 'balanced_accuracy', 'majority_baseline_accuracy']) {
        assert.equal(await page.locator(`[data-metric="${key}"] .value`).textContent(), pct(m[key]));
      }
      assert.equal(await page.locator('[data-metric="macro_f1"] .value').textContent(), m.macro_f1.toFixed(3));
      assert.equal(await page.locator('#result-count').textContent(), `${m.count} of ${m.count} reviews`);
      for (const [i, c] of m.classes.entries()) for (const [j, d] of m.classes.entries()) {
        const cell = page.locator(`#confusion button[data-reference="${c}"][data-predicted="${d}"]`);
        assert.equal(await cell.getAttribute('data-count'), String(m.confusion_matrix[i][j]));
        await cell.click();
        assert.equal(await page.locator('#result-count').textContent(), `${m.confusion_matrix[i][j]} of ${m.count} reviews`);
      }
      for (const x of run.charts.per_class_performance) {
        assert.equal(await page.locator(`#recall [data-class="${x.class}"] strong`).textContent(), (x.recall * 100).toFixed(0) + '%');
      }
      for (const x of run.charts.class_comparison) {
        assert.deepEqual(await page.locator(`#comparison [data-class="${x.class}"] .pair-line > span`).allTextContents(), [String(x.reference), String(x.predicted)]);
      }
      for (const x of run.charts.emotion_comparison) {
        assert.deepEqual(await page.locator(`#emotion-bars [data-emotion="${x.emotion}"] .pair-line > span`).allTextContents(), [String(x.llm), String(x.nrc)]);
      }
      assert.deepEqual(await page.locator('#emotion-matrix tbody td').allTextContents(), run.emotion_metrics.matrix.flat().map(String));
      for (const distribution of ['population', 'sample']) {
        await page.selectOption('#distribution', distribution);
        const series = distribution === 'population' ? data.population_star_distribution : run.charts.star_distribution;
        for (const x of series) {
          const bar = page.locator(`#stars [data-stars="${x.stars}"]`);
          assert.equal(await bar.getAttribute('data-count'), String(x.count));
          if (x.count) assert.ok((await bar.locator('.fill').boundingBox()).width > 0, 'Nonzero bar collapsed');
        }
      }
      // Use the actual visible controls and count each combined class/result/emotion subset.
      for (const result of ['all', 'correct', 'mismatched']) for (const reference of ['', ...m.classes]) for (const predicted of ['', ...m.classes]) for (const emotion of ['all', 'agree', 'disagree']) {
        await page.selectOption('#correctness', result);
        await page.selectOption('#reference', reference);
        await page.selectOption('#predicted', predicted);
        await page.selectOption('#emotion-filter', emotion);
        const expected = run.reviews.filter(r => (result === 'all' || r.correct === (result === 'correct')) && (!reference || r.true_sentiment === reference) && (!predicted || r.predicted_sentiment === predicted) && (emotion === 'all' || r.emotion_agree === (emotion === 'agree')));
        assert.equal(await page.locator('#result-count').textContent(), `${expected.length} of ${m.count} reviews`);
        assert.deepEqual(await page.locator('#review-rows tr').evaluateAll(rows => rows.map(r => r.dataset.reviewId)), expected.slice(0, 15).map(r => r.review_id));
      }
      await page.click('#reset');
      for (const query of [' DELIVERY ', 'GIFT', 'zzzz-no-match-99999']) {
        await page.fill('#search', query);
        const expected = run.reviews.filter(r => (r.title + ' ' + r.text).toLowerCase().includes(query.trim().toLowerCase()));
        assert.equal(await page.locator('#result-count').textContent(), `${expected.length} of ${m.count} reviews`);
      }
      assert.equal(await page.locator('#empty').isVisible(), true);
      await page.click('#reset');
      let allIds = [];
      do {
        allIds.push(...await page.locator('#review-rows tr').evaluateAll(rows => rows.map(r => r.dataset.reviewId)));
        if (await page.locator('#next').isDisabled()) break;
        await page.click('#next');
      } while (true);
      assert.deepEqual(allIds, run.reviews.map(r => r.review_id));
      await page.selectOption('#correctness', 'mismatched');
      assert.ok((await page.locator('#page-label').textContent()).startsWith('1–'));
      await page.click('#reset');
      await page.locator('.review-title').first().click();
      assert.equal(await page.locator('#review-dialog').isVisible(), true);
      assert.equal(await page.locator('#detail-title').textContent(), run.reviews[0].title);
      assert.equal(await page.locator('#detail-scores .bar-row').count(), 8);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#review-dialog').isVisible(), false);
      assert.equal(await page.evaluate(() => document.activeElement.classList.contains('review-title')), true);
      checks.push({run: runName, metric_and_chart_reconciliation: 'passed', filter_combinations: 3 * (m.classes.length + 1) ** 2 * 3, search_empty_reset_pagination_dialog: 'passed'});
    }
    await page.selectOption('#run', 'balanced');
    await page.selectOption('#distribution', 'sample');
    await page.locator('#emotions').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector('nav a.active').getAttribute('href') === '#emotions');
    await page.screenshot({path: path.join(root, 'screenshots/dashboard-emotions.png')});
    await page.selectOption('#correctness', 'mismatched');
    await page.locator('.review-title').first().click();
    await page.screenshot({path: path.join(root, 'screenshots/dashboard-review-detail.png')});
    await page.keyboard.press('Escape');
    await page.click('#reset');
    await page.setViewportSize({width: 390, height: 844});
    await page.evaluate(() => window.scrollTo(0, 0));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Page overflows mobile viewport');
    await page.screenshot({path: path.join(root, 'screenshots/dashboard-mobile.png'), fullPage: true});
    await page.selectOption('#run', 'baseline');
    await page.selectOption('#correctness', 'mismatched');
    assert.equal(await page.locator('#result-count').textContent(), '2 of 100 reviews');
    await page.locator('.review-title').first().click();
    assert.ok((await page.locator('#review-dialog').boundingBox()).width <= 390);
    await page.click('#close-dialog');
    await page.setViewportSize({width: 1512, height: 1100});
    await page.addStyleTag({content: 'html {font-size:32px!important}'});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Page overflows at 200% text enlargement');
    assert.deepEqual(errors, []); assert.deepEqual(network, []);
    // Optional WebMCP contract checks using an explicit test registry, not native support.
    const toolPage = await context.newPage();
    await toolPage.addInitScript(() => { window.testTools = {}; Object.defineProperty(document, 'modelContext', {value: {registerTool(tool) { window.testTools[tool.name] = tool; }}}); });
    await toolPage.goto(pathToFileURL(path.join(root, 'dashboard.html')).href);
    const valid = await toolPage.evaluate(() => window.testTools.filter_review_analysis.execute({run:'balanced', result:'mismatched', reference:'NEUTRAL', predicted:'NEGATIVE'}));
    assert.equal(valid.count, 21);
    assert.equal(await toolPage.locator('#result-count').textContent(), '21 of 150 reviews');
    const invalid = await toolPage.evaluate(() => { try { window.testTools.filter_review_analysis.execute({run:'baseline',reference:'NEUTRAL'}); return false; } catch { return true; } });
    assert.equal(invalid, true); assert.equal(await toolPage.locator('#result-count').textContent(), '21 of 150 reviews');
    // Hostile text remains text; neither title nor body can create executable DOM or requests.
    const injectionPage = await context.newPage();
    const injectionRequests = [];
    injectionPage.on('request', r => { if (/^https?:/.test(r.url())) injectionRequests.push(r.url()); });
    let fixture = fs.readFileSync(path.join(root, 'dashboard.html'), 'utf8');
    const fixtureData = structuredClone(data);
    fixtureData.runs.balanced.reviews[0].title = '<img src="https://example.invalid/pixel" onerror="window.pwned=1">';
    fixtureData.runs.balanced.reviews[0].text = '</script><script>window.pwned=1</script><img src="https://example.invalid/pixel">Safe &amp; readable<br>Next line';
    fixture = fixture.replace(/(<script id="analysis-data" type="application\/json">)[\s\S]*?(<\/script>)/, (_, start, end) => start + JSON.stringify(fixtureData).replace(/</g,'\\u003c') + end);
    await injectionPage.setContent(fixture);
    await injectionPage.locator('.review-title').first().click();
    assert.equal(await injectionPage.evaluate(() => window.pwned), undefined);
    assert.equal(await injectionPage.locator('#detail-title img, #detail-text img, #detail-text script').count(), 0);
    assert.ok((await injectionPage.locator('#detail-text').textContent()).includes('Safe & readable\nNext line'));
    assert.deepEqual(injectionRequests, []);
    const report = {status:'passed', browser: await browser.version(), dashboard_sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'dashboard.html'))).digest('hex'), offline_file_loading:'passed', external_requests:network, runtime_errors:errors, runs:checks, mobile_390px:'passed', text_enlargement_200_percent:'passed', review_text_safety:'passed', navigation_and_focus:'passed', webmcp:'contract tested with explicit mock registry; native support not required', screenshots:['screenshots/dashboard-overview.png','screenshots/dashboard-emotions.png','screenshots/dashboard-review-detail.png','screenshots/dashboard-mobile.png']};
    fs.writeFileSync(path.join(root,'outputs/browser_verification.json'), JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
