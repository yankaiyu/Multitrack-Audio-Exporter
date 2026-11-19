// Run with PYTHON_BIN and PLAYWRIGHT_MODULE set when using a bundled runtime.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const server = spawn(process.env.PYTHON_BIN || 'python3', [path.join(__dirname, 'peak_ui_server.py')], { stdio: ['ignore', 'pipe', 'pipe'] });
  let browser;
  server.stderr.on('data', () => {});
  try {
    const lines = createInterface({ input: server.stdout });
    const setup = await new Promise((resolve, reject) => {
      lines.once('line', (line) => resolve(JSON.parse(line)));
      server.once('exit', (code) => reject(new Error(`Test server exited: ${code}`)));
    });
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome' });
    const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('dialog', async (dialog) => { errors.push(dialog.message()); await dialog.dismiss(); });
    await page.goto(setup.url);
    await page.locator('#language-select option[value=en]').waitFor({ state: 'attached' });
    await page.selectOption('#language-select', 'en');
    assert.deepEqual(await page.evaluate(async () => {
      const { audibleSelection } = await import('/track-selection.js');
      return audibleSelection([{peak: null}, {peak: -Infinity}, {peak: -40}, {peak: -39.9}, {peak: 12}, {peak: NaN}], -40);
    }), [false, false, false, true, true, false]);
    const load = async (folder, count) => {
      await page.fill('#source', folder);
      await page.click('#load-waveforms');
      await page.waitForFunction((count) => document.querySelectorAll('.wave-track').length === count, count);
    };
    const mask = () => page.locator('input[name=selectedFiles]').evaluateAll((items) => items.map((item) => item.checked));
    const detect = async () => {
      await page.click('#detect-peaks');
      await page.waitForFunction(() => !document.querySelector('#detect-peaks').disabled);
    };
    await load(setup.folders[0], 2);
    await page.locator('input[name=selectedFiles]').nth(1).uncheck();
    await load(setup.folders[1], 2);
    assert.deepEqual(await mask(), [true, false]);
    // All/none masks are valid choices too; trim and gain are never inherited.
    await page.click('#select-none');
    await load(setup.folders[0], 2);
    assert.deepEqual(await mask(), [false, false]);
    await load(setup.folders[2], 3);
    assert.deepEqual(await mask(), [true, true, true]);
    await load(setup.folders[0], 2);
    await detect();
    await page.locator('.peak-flag').first().waitFor();
    assert.equal(await page.locator('.peak-flag').count(), 1);
    await page.locator('.peak-flag').click();
    assert.ok(await page.locator('.peak-panel:visible').count());
    await page.screenshot({ path: '/tmp/mae-peak-editor.png', fullPage: true });
    const geometry = await page.locator('.wave-track').first().evaluate((row) => {
      const image = row.querySelector('.wave-image').getBoundingClientRect();
      const layer = row.querySelector('.peak-layer').getBoundingClientRect();
      return { left: Math.abs(image.left - layer.left), right: Math.abs(image.right - layer.right), height: Math.abs(image.height - layer.height) };
    });
    assert.ok(Object.values(geometry).every((delta) => delta < 1));
    const first = page.locator('.wave-track').first();
    const original = await first.locator('audio').getAttribute('src');
    await page.getByRole('button', { name: '▶ Edited nearby', exact: true }).click();
    await page.waitForFunction((original) => document.querySelector('.track-preview-audio').getAttribute('src') !== original, original);
    await page.getByRole('button', { name: 'Apply', exact: true }).click();
    await page.locator('.peak-flag.applied').waitFor();
    assert.ok((await first.locator('audio').getAttribute('src')) !== original);
    await page.locator('.peak-flag').click();
    await page.getByRole('button', { name: 'Undo edit', exact: true }).click();
    await page.waitForFunction((original) => document.querySelector('.track-preview-audio').getAttribute('src') === original, original);
    assert.equal(await page.locator('.peak-flag.applied').count(), 0);
    // A cancelled draft must not leak into export or leave edited audition active.
    await detect();
    await page.locator('.peak-flag').waitFor();
    await page.locator('.peak-flag').click();
    await page.getByRole('button', { name: '▶ Edited nearby', exact: true }).click();
    await page.waitForFunction((original) => document.querySelector('.track-preview-audio').getAttribute('src') !== original, original);
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    assert.equal(await first.locator('audio').getAttribute('src'), original);
    // Detect/apply again, then inspect a real export request.
    await detect();
    await page.locator('.peak-flag').waitFor();
    await page.locator('.peak-flag').click();
    await page.getByRole('button', { name: 'Apply', exact: true }).click();
    await page.locator('.peak-flag.applied').waitFor();
    await page.selectOption('#output-format', 'wav');
    // Transient control is opt-in, tracks applied settings, and affects export
    // independently of preview gain. All fixtures are synthesized by our server.
    await first.locator('.transient-panel summary').click();
    assert.equal(await first.locator('.transient-enable').isChecked(), false);
    assert.equal(await first.locator('.transient-drive').isDisabled(), true);
    await first.locator('.transient-enable').check();
    await first.locator('.transient-after').waitFor();
    await page.waitForFunction(() => !document.querySelector('.transient-after').disabled);
    assert.equal(await first.locator('.transient-drive').inputValue(), '0');
    await first.locator('.transient-drive').fill('6');
    assert.equal(await first.locator('.transient-after').isDisabled(), true);
    await first.locator('.transient-apply').click();
    await page.waitForFunction(() => !document.querySelector('.transient-after').disabled);
    assert.match(await first.locator('.transient-status').textContent(), /Maximum reduction/);
    const measuredReduction = Number((await first.locator('.transient-status').textContent()).match(/Maximum reduction: ([\d.]+)/)[1]);
    assert.ok(measuredReduction <= 6.1); // No release-stage gain collapse.
    // A/B uses the same timeline position, not the beginning of the trim.
    await first.locator('audio').evaluate(audio => { audio.currentTime = 1.25; audio.dataset.previewPosition = '1.25'; });
    await first.locator('.transient-before').click();
    await page.waitForFunction(() => {
      const a = document.querySelector('.track-preview-audio'); return !a.paused && a.currentTime >= 1.25;
    });
    const beforePosition = await first.locator('audio').evaluate(a => a.currentTime);
    await first.locator('.transient-after').click();
    await page.waitForFunction(() => !document.querySelector('.track-preview-audio').paused);
    const afterPosition = await first.locator('audio').evaluate(a => a.currentTime);
    assert.ok(afterPosition >= beforePosition - .1 && afterPosition < beforePosition + 1);
    await first.locator('.track-preview-button').click();
    await page.fill('#trim-start', '1');
    assert.equal(await first.locator('.transient-after').isDisabled(), true);
    assert.match(await first.locator('.transient-status').textContent(), /changed/);
    await first.locator('.transient-apply').click();
    await page.waitForFunction(() => !document.querySelector('.transient-after').disabled);
    await first.locator('input[name=selectedFiles]').uncheck();
    assert.equal(await first.locator('.transient-enable').isDisabled(), true);
    await first.locator('input[name=selectedFiles]').check();
    assert.equal(await first.locator('.transient-enable').isDisabled(), false);
    // Language changes preserve DSP settings and translate the expanded panel.
    await page.selectOption('#language-select', 'ja');
    await page.waitForFunction(() => document.querySelector('.transient-panel summary').textContent.includes('トランジェント'));
    assert.equal(await first.locator('.transient-drive').inputValue(), '6');
    await page.selectOption('#language-select', 'en');
    await page.waitForFunction(() => document.querySelector('.transient-panel summary').textContent.includes('Transient'));
    // Checkbox and label share a row; panel must not alter marker geometry.
    const sameRow = await first.locator('.transient-enable').evaluate(input => {
      const a = input.getBoundingClientRect(), b = input.nextElementSibling.getBoundingClientRect();
      return Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < 3;
    });
    assert.ok(sameRow);
    await page.screenshot({ path: '/tmp/mae-transient-ui.png', fullPage: true });
    await page.uncheck('#open-output-toggle');
    const request = page.waitForRequest((req) => req.url().endsWith('/api/convert'));
    await page.click('#convert-button');
    const payload = (await request).postDataJSON();
    assert.equal(payload.peakEdits['Track01.wav'].length, 1);
    assert.equal(payload.applyPreviewGain, false);
    assert.deepEqual(payload.transientControls['Track01.wav'], { enabled: true, drive: 6 });
    await page.waitForFunction(() => !document.querySelector('#convert-button').disabled);
    assert.equal(await page.locator('#job-state').textContent(), 'Done');
    // Switching folders invalidates old processing results and clears all edits.
    await load(setup.folders[1], 2);
    assert.equal(await page.locator('.peak-flag').count(), 0);
    assert.equal(await page.locator('#auto-audible-on-load').isChecked(), false);
    await page.check('#auto-audible-on-load');
    assert.deepEqual(await mask(), [true, false]);
    await page.locator('input[name=selectedFiles]').nth(1).check();
    assert.deepEqual(await mask(), [true, true]); // Manual override remains until the next load.
    await load(setup.folders[0], 2);
    assert.deepEqual(await mask(), [true, false]); // Automatic filtering wins over the reused mask.
    await page.reload();
    await page.locator('#language-select option[value=en]').waitFor({ state: 'attached' });
    assert.equal(await page.locator('#auto-audible-on-load').isChecked(), true);
    await load(setup.folders[0], 2);
    assert.deepEqual(await mask(), [true, false]);
    await page.uncheck('#auto-audible-on-load');
    await page.locator('input[name=selectedFiles]').nth(1).check();
    await load(setup.folders[1], 2);
    assert.deepEqual(await mask(), [true, true]);
    await page.screenshot({ path: '/tmp/mae-peak-ui.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log('Browser selection reuse, detection, edited preview, apply, undo and export passed.');
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
