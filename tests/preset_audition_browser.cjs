// Run with the bundled Playwright package against a completed local audition.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  assert(process.argv[2] && process.argv[3], 'Usage: node preset_audition_browser.cjs <package> <reports>');
  const root = path.resolve(process.argv[2]);
  const reportDirectory = path.resolve(process.argv[3]);
  const manifest = JSON.parse(await fs.readFile(path.join(root, 'manifest.json'), 'utf8'));
  const candidates = manifest.candidates;
  const groupOf = item => item.group || (Number(item.id) <= 5 ? 'qwen' : 'kokoro');
  const defaultGroups = [
    { id: 'minimal', title: 'VoiceDesign 极简女声', detail: '' },
    { id: 'design', title: 'VoiceDesign 设计声线', detail: '' },
    { id: 'qwen', title: 'Qwen3-TTS', detail: '1.7B · 5 款' },
    { id: 'kokoro', title: 'Kokoro', detail: '82M v1.0 · 8 款' }
  ];
  const sourceGroupOrder = [...new Set([
    ...(manifest.groups || defaultGroups).map(group => group.id), ...candidates.map(groupOf)
  ])].filter(id => candidates.some(item => groupOf(item) === id));
  const groupOrder = sourceGroupOrder.map((id, index) => ({
    id, index,
    priority: (manifest.groups || []).find(group => group.id === id)?.priority ?? (id === 'design' ? 1 : 2)
  })).sort((left, right) => left.priority - right.priority || left.index - right.index).map(group => group.id);
  const ordered = groupOrder.flatMap(group => candidates.filter(item => groupOf(item) === group));
  assert.equal(new Set(candidates.map(item => item.id)).size, candidates.length);
  assert(ordered.length >= 3 && groupOrder.length >= 2, 'Expected a multi-group audition package');
  await fs.mkdir(reportDirectory, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(root, 'index.html')).href);
    await page.waitForSelector('audio');
    assert.deepEqual(await page.locator('#data').evaluate(el => JSON.parse(el.textContent)), manifest);
    assert.equal(await page.locator('audio').count(), candidates.length);
    assert.deepEqual(await page.locator('#groups section').evaluateAll(nodes => nodes.map(node => node.dataset.group)), groupOrder);
    assert.deepEqual(await page.locator('.voice').evaluateAll(nodes => nodes.map(node => node.dataset.id)), ordered.map(item => item.id));
    assert.equal(await page.title(), manifest.title ?? '中文预设音色试听');
    assert.equal(await page.locator('h1').textContent(), await page.title());
    assert.equal(await page.locator('#subtitle').textContent(), manifest.subtitle ?? `本地生成 · 同文 · ${candidates.length} 款`);
    assert(!(await page.locator('#subtitle').textContent()).includes('无人设指令'));
    assert.equal(await page.locator('#script').textContent(), manifest.request.input);
    if (manifest.footer != null) assert.equal(await page.locator('#footer').textContent(), manifest.footer);
    const hasDesign = candidates.some(item => item.kind === 'design' || groupOf(item) === 'design' || item.description);
    assert.equal(await page.locator('#design-note').isVisible(), hasDesign);
    const groupCounts = {};
    for (const id of groupOrder) {
      const section = page.locator(`#groups section[data-group=${JSON.stringify(id)}]`);
      const definition = (manifest.groups || []).find(group => group.id === id)
        || defaultGroups.find(group => group.id === id) || { title: id, detail: '' };
      groupCounts[id] = candidates.filter(item => groupOf(item) === id).length;
      assert.equal(await section.locator('audio').count(), groupCounts[id]);
      assert.equal((await section.locator('h2').textContent()).trim(), `${definition.title} ${definition.detail ?? ''}`.trim());
    }

    const cardFor = item => page.locator(`.voice[data-id=${JSON.stringify(item.id)}]`);
    const audioFor = item => cardFor(item).locator('audio');
    const checkFor = item => cardFor(item).locator('input[type=checkbox]');
    for (const item of candidates) {
      assert.equal(await cardFor(item).getAttribute('data-group'), groupOf(item));
      assert.equal(await audioFor(item).getAttribute('src'), item.listening);
      assert.equal(await cardFor(item).locator('a').getAttribute('href'), item.raw);
      assert.equal(await cardFor(item).locator('.description').count(), item.description ? 1 : 0);
      if (item.description) assert.equal(await cardFor(item).locator('.description').textContent(), `声线目标：${item.description}`);
    }

    // Do not call load(): that would hide a regression in native metadata preloading.
    async function readMedia() {
      await page.waitForFunction(() => [...document.querySelectorAll('audio')].every(audio => audio.error || audio.readyState >= 1));
      const result = await page.locator('audio').evaluateAll(nodes => nodes.map(audio => ({
        id: audio.closest('.voice').dataset.id, source: audio.getAttribute('src'),
        seconds: audio.duration, ready: audio.readyState, preload: audio.preload,
        controls: audio.controls, error: audio.error && audio.error.message
      })));
      assert(result.every(item => !item.error && item.preload === 'metadata' && item.controls
        && Number.isFinite(item.seconds) && item.seconds > 0), JSON.stringify(result));
      return result;
    }
    const media = await readMedia();
    const selectedIds = new Set();
    const filterResults = {};
    async function assertVisible(value) {
      const expected = ordered.filter(item => {
        if (value === 'all') return true;
        if (value === 'minimal') return groupOf(item) === 'minimal';
        if (value === 'design') return item.kind === 'design' || groupOf(item) === 'design';
        if (value === 'fixed') return ['qwen', 'kokoro'].includes(groupOf(item));
        if (value === 'dialect') return item.dialect !== '普通话';
        if (value === 'picked') return selectedIds.has(item.id);
        return item.gender === value;
      });
      assert.deepEqual(await page.locator('.voice:visible').evaluateAll(nodes => nodes.map(node => node.dataset.id)), expected.map(item => item.id));
      assert.deepEqual(await page.locator('#groups section:visible').evaluateAll(nodes => nodes.map(node => node.dataset.group)),
        groupOrder.filter(id => expected.some(item => groupOf(item) === id)));
      assert.equal(await page.locator('#selection').textContent(), `已选 ${selectedIds.size} 款`);
      filterResults[value] = expected.length;
      return expected;
    }
    async function assertStopped() {
      assert(await page.locator('audio').evaluateAll(nodes => nodes.every(audio => audio.paused && audio.currentTime === 0)));
      assert.deepEqual(await page.evaluate(() => ({ length: queue.length, index: queueIndex })), { length: 0, index: -1 });
      assert.equal(await page.locator('#now').textContent(), '');
    }
    async function filter(value) {
      await page.locator('#filter').selectOption(value);
      const expected = await assertVisible(value);
      await assertStopped();
      return expected;
    }
    async function waitPlaying(item) {
      await page.waitForFunction(id => {
        const audio = [...document.querySelectorAll('.voice')].find(card => card.dataset.id === id).querySelector('audio');
        return !audio.paused && audio.currentTime > 0;
      }, item.id);
      assert.deepEqual(await page.locator('audio').evaluateAll(nodes => nodes.filter(audio => !audio.paused).map(audio => audio.closest('.voice').dataset.id)), [item.id]);
      assert.deepEqual(await page.locator('.voice.playing').evaluateAll(nodes => nodes.map(node => node.dataset.id)), [item.id]);
    }
    async function finish(item) {
      await audioFor(item).evaluate(audio => { audio.currentTime = Math.max(0, audio.duration - 0.05); });
      await page.waitForFunction(id => [...document.querySelectorAll('.voice')]
        .find(card => card.dataset.id === id).querySelector('audio').ended, item.id);
    }
    for (const value of ['女声', '男声', 'dialect', 'minimal', 'design', 'fixed', 'picked', 'all']) await filter(value);
    const filterQueues = {};
    for (const value of ['minimal', 'design', 'fixed']) {
      const expected = await filter(value);
      filterQueues[value] = expected.map(item => item.id);
      await page.locator('#sequence').click();
      if (expected.length) {
        await waitPlaying(expected[0]);
        assert.deepEqual(await page.evaluate(() => queue.map(audio => audio.closest('.voice').dataset.id)), expected.map(item => item.id));
        if (value === 'minimal') {
          for (const item of expected) {
            await waitPlaying(item);
            await finish(item);
          }
          assert(await page.locator('audio').evaluateAll(nodes => nodes.every(audio => audio.paused)));
          assert.equal(await page.locator('#now').textContent(), '连续试听结束');
        }
        await page.locator('#stop').click();
      }
      await assertStopped();
    }
    await filter('all');

    // Both choices are real, non-first candidates, with the second in another group.
    const firstChoice = ordered[1];
    const secondChoice = ordered.find((item, index) => index > 1 && groupOf(item) !== groupOf(firstChoice));
    assert(secondChoice, 'Expected a non-first candidate from another group');
    await checkFor(firstChoice).check();
    selectedIds.add(firstChoice.id);
    await filter('picked');
    await filter('all');
    await checkFor(secondChoice).check();
    selectedIds.add(secondChoice.id);
    await filter('picked');
    const downloading = page.waitForEvent('download');
    await page.locator('#export').click();
    const download = await downloading;
    const selectionPath = await download.path();
    const selected = JSON.parse(await fs.readFile(selectionPath, 'utf8'));
    assert.equal(download.suggestedFilename(), 'voice-selection.json');
    assert.deepEqual(selected.selected, candidates.filter(item => selectedIds.has(item.id)).map(item => ({
      id: item.id, voice: item.voice, group: groupOf(item),
      ...(item.description ? { description: item.description } : {}), engine: item.engine, wav_sha256: item.wav_sha256
    })));
    assert.equal(selected.scope, 'audition_selection_not_final_voice_approval');
    await page.locator('#sequence').click();
    await waitPlaying(firstChoice);
    await checkFor(firstChoice).uncheck();
    selectedIds.delete(firstChoice.id);
    await assertVisible('picked');
    await assertStopped();
    await audioFor(firstChoice).evaluate(audio => audio.dispatchEvent(new Event('ended')));
    await assertStopped();
    await page.locator('#sequence').click();
    await waitPlaying(secondChoice);
    await finish(secondChoice);
    assert(await page.locator('audio').evaluateAll(nodes => nodes.every(audio => audio.paused)));
    assert.equal(await page.locator('#now').textContent(), '连续试听结束');
    await checkFor(secondChoice).uncheck();
    selectedIds.delete(secondChoice.id);
    await assertVisible('picked');
    await assertStopped();
    await page.locator('#sequence').click();
    await assertStopped();
    await filter('all');
    await page.locator('#sequence').click();
    await waitPlaying(ordered[0]);
    await finish(ordered[0]);
    await waitPlaying(ordered[1]);
    await page.locator('#stop').click();
    await assertStopped();

    const crossGroupPlayback = [];
    for (let index = 1; index < groupOrder.length; index++) {
      const pair = [groupOrder[index - 1], groupOrder[index]].map(id => ordered.find(item => groupOf(item) === id));
      for (const item of [pair[0], pair[1], pair[0]]) {
        await audioFor(item).evaluate(audio => audio.play());
        await waitPlaying(item);
      }
      crossGroupPlayback.push(pair.map(item => item.id));
      await page.locator('#stop').click();
      await assertStopped();
    }

    await page.locator('#sequence').click();
    await waitPlaying(ordered[0]);
    await page.locator('#level').uncheck();
    await assertStopped();
    for (const item of candidates) assert.equal(await audioFor(item).getAttribute('src'), item.raw);
    const rawMedia = await readMedia();
    await page.locator('#level').check();
    await assertStopped();
    for (const item of candidates) assert.equal(await audioFor(item).getAttribute('src'), item.listening);
    await readMedia();
    const layouts = [];
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await page.evaluate(() => scrollTo(0, 0));
      const layout = await page.evaluate(() => {
        const cards = [...document.querySelectorAll('.voice')];
        return {
          width: innerWidth,
          overflow: document.documentElement.scrollWidth > innerWidth,
          fit: cards.every(card => card.scrollWidth <= card.clientWidth + 1),
          contained: cards.every(card => {
            const outer = card.getBoundingClientRect();
            return [...card.children].every(child => {
              const box = child.getBoundingClientRect();
              return box.left >= outer.left && box.right <= outer.right && box.bottom <= outer.bottom;
            });
          })
        };
      });
      assert(!layout.overflow && layout.fit && layout.contained);
      layouts.push(layout);
      await page.screenshot({ path: path.join(reportDirectory, `audition-${viewport.width}.png`), fullPage: true });
    }
    assert.deepEqual(errors, []);
    await fs.writeFile(path.join(reportDirectory, 'browser-check.json'), JSON.stringify({
      media, rawMedia, groupOrder, groupCounts, filterResults, filterQueues, crossGroupPlayback, layouts, errors,
      selectionExport: selected, cancelledCandidate: firstChoice.id,
      playback: 'non_first_selection_cancel_clears_queue_and_cross_group_exclusive'
    }, null, 2));
    console.log(JSON.stringify({ audioFiles: media.length, groupCounts, layouts, errors, playback: 'passed' }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
