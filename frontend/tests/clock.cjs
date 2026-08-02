/**
 * The clock only runs when there is a word to answer.
 *
 * An opening move is not a response, so nothing on the board means nothing to be late
 * for. That has to hold after every way a board can empty - not just at the start -
 * because the failure is silent: the timer keeps counting against a word that is no
 * longer there and the round "times out" seconds after it already ended.
 */
const { chromium } = require('playwright');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = [];
const check = (l,g,w) => { out.push({ok:g===w,l,g}); console.log(`   ${g===w?'ok  ':'FAIL'}  ${l.padEnd(44)} ${JSON.stringify(g)}`); };

// `is-idle` is the class the arc wears when there is no deadline.
const idle = p => p.evaluate(() => !!document.querySelector('.rts-timer.is-idle'));
const lastBot = p => p.evaluate(() =>
  [...document.querySelectorAll('.rts-msg.is-bot .rts-bubble')].pop()?.innerText.trim() || '');

async function send(p, text) {
  await p.fill('.rts-input', text);
  await p.press('.rts-input', 'Enter');
}

(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await (await b.newContext({ viewport:{width:1000,height:760} })).newPage();
  await p.goto('http://localhost:5174'); await p.waitForSelector('.rts-input');
  await sleep(6000);

  check('nothing played yet, clock is down', await idle(p), true);

  await send(p, 'lamp'); await sleep(11000);
  check('a word is in play, clock is running', await idle(p), false);

  // break the letter rule: the round is lost, the board empties, the clock must stop
  await send(p, 'red'); await sleep(12000);
  const said = await lastBot(p);
  console.log(`        bot said: "${said}"`);
  check('a rule break loses the round', /lost|mine|new game|another game/i.test(said), true);
  check('...and does not say try again', /try again|go again/i.test(said), false);
  check('board is empty, clock is down', await idle(p), true);

  // and it stays down while you decide - no clock on the opening move
  await sleep(9000);
  check('still down 9s later', await idle(p), true);

  await send(p, 'moth'); await sleep(11000);
  check('new game underway, clock is running again', await idle(p), false);

  await b.close();
  const bad = out.filter(r=>!r.ok);
  console.log('\n' + '='.repeat(60));
  console.log(bad.length ? `FAILED ${bad.length}/${out.length}` : `PASS ${out.length}/${out.length}`);
  process.exit(bad.length?1:0);
})();
