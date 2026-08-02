/** --chrome-top must always match the header's real height, in every combination. */
const { chromium } = require('playwright');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = [];
const check = (l, g, w) => { out.push({ok:g===w,l,g}); console.log(`   ${g===w?'ok  ':'FAIL'}  ${l.padEnd(44)} ${JSON.stringify(g)}`); };

const gap = (p) => p.evaluate(() => {
  const win = document.querySelector('.rts-window');
  const head = document.querySelector('.rts-header-group').getBoundingClientRect();
  const first = document.querySelector('.rts-msg, .rts-note');
  const top = getComputedStyle(win).getPropertyValue('--chrome-top').trim();
  return {
    varTop: Math.round(parseFloat(top)),
    realHeader: Math.round(head.height),
    // gap between where the header ends and the first bubble starts
    slack: first ? Math.round(first.getBoundingClientRect().top - head.bottom) : null,
  };
});

const hold = async (p, sel) => {
  await p.dispatchEvent(sel, 'pointerdown'); await sleep(700);
  await p.dispatchEvent(sel, 'pointerup'); await sleep(500);
};

(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await (await b.newContext({ viewport:{width:1100,height:800} })).newPage();
  await p.goto('http://localhost:5174'); await p.waitForSelector('.rts-input'); await sleep(5500);

  let m = await gap(p);
  check('solo: var matches header', m.varTop, m.realHeader);
  check('solo: first bubble sits just under it', m.slack >= 0 && m.slack < 24, true);

  await hold(p, '.rts-toggle--t');
  m = await gap(p);
  check('panel open: var matches header', m.varTop, m.realHeader);
  check('panel open: no dead space', m.slack >= 0 && m.slack < 24, true);

  // close it and go straight to the lobby - the case that used to freeze the var
  await p.keyboard.press('Escape'); await sleep(400);
  await p.click('.rts-toggle--r'); await sleep(900);
  m = await gap(p);
  check('lobby: var matches header', m.varTop, m.realHeader);
  check('lobby: no dead space', m.slack >= 0 && m.slack < 24, true);

  // the original report: open the panel, then enter the lobby with it open
  await hold(p, '.rts-toggle--t');
  await p.keyboard.press('Escape'); await sleep(500);
  m = await gap(p);
  check('lobby after panel: var matches header', m.varTop, m.realHeader);
  check('lobby after panel: no dead space', m.slack >= 0 && m.slack < 24, true);

  // ...and back to solo
  await p.click('.rts-toggle--r'); await sleep(700);
  m = await gap(p);
  check('back to solo: var matches header', m.varTop, m.realHeader);
  check('back to solo: no dead space', m.slack >= 0 && m.slack < 24, true);

  await b.close();
  const bad = out.filter(r=>!r.ok);
  console.log('\n' + '='.repeat(60));
  console.log(bad.length ? `FAILED ${bad.length}/${out.length}` : `PASS ${out.length}/${out.length}`);
  process.exit(bad.length?1:0);
})();
