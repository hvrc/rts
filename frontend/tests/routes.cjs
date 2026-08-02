/**
 * URLs, invitations, and the lights spelling themselves out.
 *
 * The invitation case is the one worth automating: a second browser that has never
 * seen this app opens /<room> and should land on that room's join form asking only
 * for a name. It is easy to get right by hand once and break on the next refactor.
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:5174';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const results = [];
function check(label, got, want) {
  const ok = got === want;
  results.push({ ok, label, got, want });
  console.log(`   ${ok ? 'ok  ' : 'FAIL'}  ${label.padEnd(40)} ${JSON.stringify(got)}`);
}

(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  const viewport = { width: 1100, height: 800 };
  const room = 'link-' + Math.floor(Math.random() * 1e6);

  // --- ana: solo -> lobby -> makes a room, watching the URL ------------------
  const a = await browser.newContext({ viewport });
  const pa = await a.newPage();
  await pa.goto(APP);
  await pa.waitForSelector('.rts-input');
  console.log('\nana:');
  check('solo is /', new URL(pa.url()).pathname, '/');

  await pa.click('.rts-toggle--r');
  await sleep(600);
  check('r goes to /rooms', new URL(pa.url()).pathname, '/rooms');

  // ...and the lights spell themselves out for three seconds
  const pill = async () => pa.evaluate(() => {
    const b = document.querySelector('.rts-toggle--s');
    // innerText puts a newline between flex children; they sit side by side.
    return { w: Math.round(b.getBoundingClientRect().width),
             text: b.innerText.replace(/\s+/g, '') };
  });
  const open = await pill();
  check('s pill reads "switch"', open.text, 'switch');
  check('s pill is wider than a dot', open.w > 30, true);
  await sleep(3200);
  const shut = await pill();
  check('collapses back to a dot', shut.w <= 20, true);

  await pa.click('.rts-room.is-new');
  await pa.waitForSelector('.rts-field input');
  const fa = await pa.$$('.rts-field input');
  await fa[0].fill(room);
  await fa[1].fill('ana');
  await pa.click('.rts-opt.is-go');
  await pa.waitForSelector('.rts-composer', { timeout: 10000 });
  await sleep(1000);
  check('creating lands on /<room>', new URL(pa.url()).pathname, '/' + room);

  // settings live at /<room>/settings, opened by holding r
  await pa.dispatchEvent('.rts-toggle--r', 'pointerdown');
  await sleep(700);
  await pa.dispatchEvent('.rts-toggle--r', 'pointerup');
  await sleep(400);
  check('holding r opens /<room>/settings',
        new URL(pa.url()).pathname, `/${room}/settings`);
  check('the settings strip is showing',
        await pa.isVisible('.rts-roombar'), true);

  // the bot introduced itself by name
  const firstSpeaker = await pa.evaluate(() =>
    (document.querySelector('.rts-who')?.innerText || '').trim());
  check('bot is called rts', firstSpeaker, 'rts');

  // --- ben: opens the link cold ---------------------------------------------
  const b = await browser.newContext({ viewport });
  const pb = await b.newPage();
  console.log('\nben, arriving on the link with no history:');
  await pb.goto(`${APP}/${room}`);
  await pb.waitForSelector('.rts-lobby, .rts-composer', { timeout: 10000 });
  await sleep(1500);

  const prompts = await pb.evaluate(() =>
    [...document.querySelectorAll('.rts-msg.is-bot .rts-bubble')].map(e => e.innerText.trim()));
  check('offered the join form', prompts.some(t => t.startsWith('joining')), true);
  check('names the room', prompts.some(t => t.includes(room)), true);
  check('asks only for a name', prompts.includes('your name?'), true);
  check('does not ask for a room name', prompts.includes('room name?'), false);
  check('one field to fill', (await pb.$$('.rts-field input')).length, 1);

  await (await pb.$$('.rts-field input'))[0].fill('ben');
  await pb.click('.rts-opt.is-go');
  await pb.waitForSelector('.rts-composer', { timeout: 10000 });
  await sleep(1200);
  check('ben lands in the room', new URL(pb.url()).pathname, '/' + room);
  check('ana sees him', await pa.isVisible('text=ben joined'), true);

  // --- ben reloads: already a member, so no second ask ----------------------
  console.log('\nben reloads:');
  await pb.reload();
  await pb.waitForSelector('.rts-composer', { timeout: 10000 });
  await sleep(2000);
  check('goes straight back in, no form',
        (await pb.$$('.rts-field input')).length, 0);
  check('still in the room', new URL(pb.url()).pathname, '/' + room);

  // --- a room that does not exist -------------------------------------------
  console.log('\na dead link:');
  const c = await browser.newContext({ viewport });
  const pc = await c.newPage();
  await pc.goto(`${APP}/nope-not-a-room-12345`);
  await pc.waitForSelector('.rts-lobby', { timeout: 10000 });
  await sleep(2000);
  check('falls back to the lobby', new URL(pc.url()).pathname, '/rooms');
  check('says so', await pc.isVisible('text=that room has gone'), true);

  // --- back button ----------------------------------------------------------
  console.log('\nback button:');
  await pa.goBack();
  await sleep(600);
  check('back leaves settings', new URL(pa.url()).pathname, '/' + room);

  await browser.close();

  const bad = results.filter(r => !r.ok);
  console.log('\n' + '='.repeat(64));
  if (bad.length) {
    console.log(`FAILED - ${bad.length}/${results.length}`);
    bad.forEach(r => console.log(`  - ${r.label}: got ${JSON.stringify(r.got)}, wanted ${JSON.stringify(r.want)}`));
    process.exit(1);
  }
  console.log(`PASS - ${results.length}/${results.length}`);
})();
