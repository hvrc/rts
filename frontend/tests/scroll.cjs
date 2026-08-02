/**
 * Does the newest message ever end up behind the composer?
 *
 * Measures the real thing rather than the code that is supposed to cause it: after
 * every message, the bottom of the last bubble against the top of the input bar. If
 * the first is below the second, the message is behind the bar - which is the bug,
 * however it got there.
 *
 * Runs solo and in a room, and checks after every single message rather than at the
 * end, because the report is that it happens inconsistently.
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:5174';
const API = 'http://localhost:5001';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

/* Take the room down on the way out. Every run of this used to leave a room behind,
   and a lobby is a list of places worth going - a column of dead test rooms is the
   one thing that stops it being that. */
async function cleanUp(pages) {
  for (const p of pages) {
    await p.evaluate(() => {
      const id = window.location.pathname.split('/').filter(Boolean)[0];
      const me = localStorage.getItem('rts.user.v1');
      if (!id || !me || id === 'rooms') return;
      return fetch(`http://localhost:5001/rooms/${id}/leave`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: me }),
      }).catch(() => {});
    }).catch(() => {});
  }
}


/** Bottom of the last bubble vs top of the composer, in viewport pixels. */
async function overlap(page) {
  return page.evaluate(() => {
    const msgs = [...document.querySelectorAll('.rts-msg, .rts-note')];
    const composer = document.querySelector('.rts-composer');
    if (!msgs.length || !composer) return null;
    const last = msgs[msgs.length - 1].getBoundingClientRect();
    const bar = composer.getBoundingClientRect();
    const container = document.querySelector('.messages-container');
    return {
      hidden: Math.round(last.bottom - bar.top),   // >0 means it is behind the bar
      text: msgs[msgs.length - 1].innerText.slice(0, 30).replace(/\n/g, ' '),
      atBottom: Math.round(container.scrollHeight - container.scrollTop - container.clientHeight),
    };
  });
}

async function check(page, label, failures) {
  const o = await overlap(page);
  if (!o) return;
  // A couple of pixels of rounding is fine; a bubble is ~35px tall, so anything
  // meaningfully positive is text the player cannot read.
  const bad = o.hidden > 2;
  if (bad) failures.push(`${label}: "${o.text}" is ${o.hidden}px behind the bar`);
  console.log(`   ${bad ? 'FAIL' : 'ok  '}  ${label.padEnd(26)} ` +
              `hidden=${String(o.hidden).padStart(4)}  ` +
              `scrollGap=${String(o.atBottom).padStart(4)}  "${o.text}"`);
}

async function send(page, text) {
  await page.fill('.rts-input', text);
  await page.press('.rts-input', 'Enter');
}

(async () => {
  const failures = [];
  const browser = await chromium.launch({ channel: 'chrome' });

  // --- solo -----------------------------------------------------------------
  {
    const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 } });
    const page = await ctx.newPage();
    await page.goto(APP);
    await page.waitForSelector('.rts-input');
    await sleep(6000);                       // the typed intro
    console.log('\nsolo:');
    await check(page, 'after intro', failures);

    for (const word of ['lamp', 'glow', 'candle']) {
      await send(page, word);
      await page.waitForTimeout(1000);
      await check(page, `sent "${word}"`, failures);
      await page.waitForTimeout(9000);       // the bot answers
      await check(page, `bot replied to "${word}"`, failures);
    }
    await ctx.close();
  }

  // --- a room, two browsers -------------------------------------------------
  {
    const roomName = 'scrolltest-' + Math.floor(Math.random() * 1e6);
    const a = await browser.newContext({ viewport: { width: 1100, height: 800 } });
    const b = await browser.newContext({ viewport: { width: 1100, height: 800 } });
    const pa = await a.newPage();
    const pb = await b.newPage();

    for (const p of [pa, pb]) {
      await p.goto(APP);
      await p.waitForSelector('.rts-input');
    }
    await sleep(5500);

    // ana makes the room
    await pa.click('.rts-toggle--r');
    await pa.waitForSelector('.rts-room.is-new');
    await pa.click('.rts-room.is-new');
    await pa.waitForSelector('.rts-field input');
    const fieldsA = await pa.$$('.rts-field input');
    await fieldsA[0].fill(roomName);
    await fieldsA[1].fill('ana');
    await pa.click('.rts-opt.is-go');
    await pa.waitForSelector('.rts-composer', { timeout: 10000 });
    await sleep(1200);

    // ben joins it
    await pb.click('.rts-toggle--r');
    await pb.waitForSelector('.rts-room');
    await pb.click(`.rts-room:has-text("${roomName}")`);
    await pb.waitForSelector('.rts-field input');
    await (await pb.$$('.rts-field input'))[0].fill('ben');
    await pb.click('.rts-opt.is-go');
    await sleep(1500);

    console.log('\nroom (ana = the one we measure):');
    await check(pa, 'joined', failures);

    const script = [
      [pa, 'moth'], [pb, 'flame'], [pa, 'candle'],
      [pb, 'what u talking bout'], [pa, 'wax'], [pb, 'bye'],
      [pa, 'ok this is a much longer message to make the bubble wrap onto two lines'],
      [pb, 'lol'], [pa, 'wick'],
    ];
    for (const [who, text] of script) {
      const label = (who === pa ? 'ana' : 'ben') + ': ' + text.slice(0, 14);
      await send(who, text);
      await sleep(1200);
      await check(pa, label, failures);
      await sleep(7000);               // give the bot room to take its turn
      await check(pa, label + ' +bot', failures);
    }

    await cleanUp([pa, pb]);
    await a.close();
    await b.close();
  }

  await browser.close();

  console.log('\n' + '='.repeat(64));
  if (failures.length) {
    console.log(`FAILED - ${failures.length} message(s) ended up behind the bar:`);
    failures.forEach(f => console.log('  - ' + f));
    process.exit(1);
  }
  console.log('PASS - every message stayed clear of the composer');
})();
