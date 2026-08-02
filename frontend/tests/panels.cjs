const { chromium } = require('playwright');
const APP = 'http://localhost:5174';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = [];
const check = (l, g, w) => { out.push({ok: g===w, l, g}); console.log(`   ${g===w?'ok  ':'FAIL'}  ${l.padEnd(38)} ${JSON.stringify(g)}`); };

(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await (await b.newContext({ viewport:{width:1100,height:800} })).newPage();
  await p.goto(APP); await p.waitForSelector('.rts-input'); await sleep(5500);

  // hold t -> appearance opens
  await p.dispatchEvent('.rts-toggle--t', 'pointerdown');
  await sleep(700);
  await p.dispatchEvent('.rts-toggle--t', 'pointerup');
  await sleep(400);
  check('hold t opens appearance', await p.isVisible('.rts-appearance'), true);
  check('skin button says bubbly', await p.isVisible('.rts-skin:text-is("bubbly")'), true);
  check('no button says aqua', await p.isVisible('.rts-skin:text-is("aqua")'), false);

  // clicking the conversation closes it
  await p.mouse.click(550, 400);
  await sleep(400);
  check('click away closes it', await p.isVisible('.rts-appearance'), false);

  // escape also closes it
  await p.dispatchEvent('.rts-toggle--t', 'pointerdown');
  await sleep(700);
  await p.dispatchEvent('.rts-toggle--t', 'pointerup');
  await sleep(300);
  await p.keyboard.press('Escape');
  await sleep(300);
  check('escape closes it', await p.isVisible('.rts-appearance'), false);

  /* The bars must float over the conversation in BOTH skins, not bracket it.

     Checking `position` and the scroll area's own box, not just the background: a
     transparent background is also what you get when the whole rule fails to parse
     and the bars drop back into the layout - which is exactly how this regressed, with
     a background-only assertion passing throughout. */
  for (const skin of ['aqua', 'flat']) {
    await p.goto(`${APP}/?skin=${skin}`);
    await p.waitForSelector('.rts-input');
    await sleep(5500);
    const m = await p.evaluate(() => {
      const cs = (s) => getComputedStyle(document.querySelector(s));
      const box = (s) => document.querySelector(s).getBoundingClientRect();
      const win = box('.rts-window'), list = box('.messages-container');
      const head = box('.rts-header-group'), comp = box('.rts-composer');
      const timer = box('.rts-timer');
      return {
        headerPos: cs('.rts-header-group').position,
        composerPos: cs('.rts-composer').position,
        headerBg: cs('.rts-header-group').backgroundColor,
        composerBg: cs('.rts-composer').backgroundColor,
        // The scroll area runs the full height of the window rather than starting
        // where the header ends and stopping where the composer begins.
        listStartsAtTop: Math.round(list.top - win.top) <= 1,
        listEndsAtBottom: Math.round(win.bottom - list.bottom) <= 1,
        // ...so the bars genuinely sit on top of it.
        headerOverlaps: head.bottom > list.top,
        composerOverlaps: comp.top < list.bottom,
        timerOverlaps: timer.bottom > list.top,
      };
    });
    check(`${skin}: header floats`, m.headerPos, 'absolute');
    check(`${skin}: composer floats`, m.composerPos, 'absolute');
    check(`${skin}: header strip is transparent`, m.headerBg, 'rgba(0, 0, 0, 0)');
    check(`${skin}: composer strip is transparent`, m.composerBg, 'rgba(0, 0, 0, 0)');
    check(`${skin}: messages run to the top`, m.listStartsAtTop, true);
    check(`${skin}: messages run to the bottom`, m.listEndsAtBottom, true);
    check(`${skin}: header sits over them`, m.headerOverlaps, true);
    check(`${skin}: composer sits over them`, m.composerOverlaps, true);
    check(`${skin}: timer sits over them`, m.timerOverlaps, true);
  }

  await b.close();
  const bad = out.filter(r => !r.ok);
  console.log('\n' + '='.repeat(60));
  console.log(bad.length ? `FAILED ${bad.length}/${out.length}` : `PASS ${out.length}/${out.length}`);
  process.exit(bad.length ? 1 : 0);
})();
