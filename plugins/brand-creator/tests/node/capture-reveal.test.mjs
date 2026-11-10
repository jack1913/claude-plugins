import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { spawn } from "node:child_process";
import { needSetup, bc, makeProject, BIN, DATA } from "./_helpers.mjs";
import { sha, png, jpeg, record, bcAsync, listen, TALL, CSS, MARK, writePage, MOVING, MOVING_CSS, FRAME_FILES, writeMoving, redPixels, REVEAL_HTML, REVEAL_CSS, LAYOUT, ITEMS, SEEN_HEADER, SEEN_SCRIPT, RED_BAND, revealLayout } from "./_capture.mjs";

// ---------------------------------------------------------------- capture <page> --reveal: what the page shows once it is scrolled into view (group 5)
// A section that is hidden until an IntersectionObserver sees it. It is tall, far below the first screen and painted red (#c03), so a still shows it or not by a count of red pixels.

test("capture --reveal: a section that appears only when scrolled into view is hidden in the stills without the flag and shown with it, and a second run writes the same bytes", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const page = writeMoving(p, "rounds/r1/Late", REVEAL_CSS, REVEAL_HTML);
  const dir = path.join(p, "rounds/r1/Late/shots");
  const plain = bc(["capture", page, "--project", p]);
  assert.equal(plain.status, 0, plain.stdout + plain.stderr);
  assert.equal(redPixels(path.join(dir, "1440-light-full.png")), 0, "without --reveal the section is still hidden");
  assert.ok(!("reveal" in record(dir)), "a plain run records no reveal");
  assert.ok(!/reveal/.test(plain.stdout), plain.stdout);
  const r = bc(["capture", page, "--project", p, "--reveal"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(redPixels(path.join(dir, "1440-light-full.png")) > 1440 * 300 * 0.9, "with --reveal the full page shows the section");
  assert.equal(redPixels(path.join(dir, "1440-light.png")), 0, "the first screen is taken back at the top: the section is below it");
  assert.equal(redPixels(path.join(dir, "390-dark.png")), 0);
  const rec = record(dir);
  assert.equal(rec.reveal.capped, false);
  assert.ok(rec.reveal.steps >= 2, JSON.stringify(rec.reveal));
  assert.match(r.stdout, /reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen/);
  assert.ok(!/CAPPED/.test(r.stdout), r.stdout);
  const before = fs.readFileSync(path.join(dir, "capture.json"));
  const again = bc(["capture", page, "--project", p, "--reveal"], { env: { BRAND_CREATOR_TODAY: "2026-11-30" } });
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /0 of 6 file\(s\) written/);
  assert.ok(fs.readFileSync(path.join(dir, "capture.json")).equals(before), "capture.json stays byte for byte, its date included");
});

test("capture --reveal: the walk waits at every step, so a section a scroll handler reveals a moment after the scroll stops is shown", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // the handler waits 150 ms after the last scroll event, then reveals the section if it is in view: a walk that did not wait at each step would be back at the top by then
  const html = REVEAL_HTML.replace(/<script>.*<\/script>/, "<script>let t;addEventListener('scroll',()=>{clearTimeout(t);t=setTimeout(()=>{const s=document.querySelector('.late'),r=s.getBoundingClientRect();if(r.top<innerHeight&&r.bottom>0)s.classList.add('in')},150)})</script>");
  const page = writeMoving(p, "rounds/r1/Debounced", REVEAL_CSS.replace("transition:opacity 200ms", ""), html);
  const r = bc(["capture", page, "--project", p, "--reveal"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(redPixels(path.join(p, "rounds/r1/Debounced/shots/1440-light-full.png")) > 1440 * 300 * 0.9, "the section revealed 150 ms after the scroll is in the full page");
});

test("capture --reveal: a walk that takes longer than --timeout stops there and says so", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // every scroll starts a finite 1.2 s animation, which the walk waits for at each step: with --timeout 1000 the walk of a very long page stops after its first step
  const html = REVEAL_HTML.replace(/<script>.*<\/script>/, "<script>addEventListener('scroll',()=>document.querySelector('h1').animate([{opacity:0.5},{opacity:1}],{duration:1200}))</script>");
  const page = writeMoving(p, "rounds/r1/Slow", REVEAL_CSS.replace(".tall{height:1500px}", ".tall{height:60000px}"), html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", "--timeout", "1000"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const rec = record(path.join(p, "rounds/r1/Slow/shots"));
  assert.equal(rec.reveal.capped, true); assert.equal(rec.reveal.timed_out, true);
  assert.ok(rec.reveal.steps < 40, JSON.stringify(rec.reveal));
  assert.match(r.stdout, /CAPPED: a walk took longer than --timeout/);
});

test("capture --reveal: a page that scrolls inside an element has that element walked, and a page with overflow hidden is still walked (a script can scroll it), never called long", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const snap = REVEAL_CSS + "html,body{height:100%;margin:0;overflow:hidden}main{height:100%;overflow-y:scroll;scroll-snap-type:y mandatory}";
  const html = REVEAL_HTML.replace("<body><h1>Ledger</h1><div class=tall></div><section class=late>Late</section>", "<body><main><h1>Ledger</h1><div class=tall></div><section class=late>Late</section></main>");
  const page = writeMoving(p, "rounds/r1/Snap", snap, html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const rec = record(path.join(p, "rounds/r1/Snap/shots"));
  assert.equal(rec.reveal.boxes, 1, JSON.stringify(rec.reveal));
  assert.ok(rec.reveal.steps >= 1 && !rec.reveal.not_scrolled, JSON.stringify(rec.reveal));
  assert.match(r.stdout, /inside 1 box that scrolls/);
  const clipped = writeMoving(p, "rounds/r1/Clipped", REVEAL_CSS + "html{overflow:hidden}", REVEAL_HTML);
  const c = bc(["capture", clipped, "--project", p, "--reveal", "--wait", "0"]);
  assert.equal(c.status, 0, c.stdout + c.stderr);
  const crec = record(path.join(p, "rounds/r1/Clipped/shots"));
  assert.ok(crec.reveal.steps >= 1 && !crec.reveal.not_scrolled && crec.reveal.capped === false, JSON.stringify(crec.reveal));
  assert.ok(!/CAPPED|NOT SCROLLED/.test(c.stdout), c.stdout);
  assert.equal(crec.reveal.root_hidden, true, "a root with overflow hidden is walked, and the record says a visitor cannot scroll it");
  assert.match(c.stdout, /NOTE: the page's own scrolling is hidden or clipped.*a visitor cannot scroll it with the wheel/);
});

test("capture --reveal: a page longer than the walk is walked as far as the cap allows and says so; --url refuses the flag", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = REVEAL_CSS.replace(".tall{height:1500px}", ".tall{height:60000px}");
  const page = writeMoving(p, "rounds/r1/Long", css, REVEAL_HTML);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const rec = record(path.join(p, "rounds/r1/Long/shots"));
  assert.deepEqual(rec.reveal, { steps: 80, capped: true, page_unfinished: true });
  assert.match(r.stdout, /CAPPED: the page is longer than 40 screens/);
  const url = bc(["capture", "--url", "http://127.0.0.1:9/", "--name", "nowhere", "--reveal", "--project", p]);
  assert.equal(url.status, 2, url.stdout + url.stderr);
  assert.match(url.stdout + url.stderr, /--reveal goes with a page of the project/);
});

// ---------------------------------------------------------------- capture --reveal: the walk of 0.9.0 (dev/specs/2026-11-05-g6-reveal-walk-design.md), one test per layout
// Each page is walked with --wait 0 (the walk itself waits two frames after each step). The record is checked whole: its counts are those of the layout's geometry
// (a step is half of what the screen shows of a scroller: 450 px at 900, 422 px at 844). Box content below a box's first screen is in no still (each box is shown
// at its top), so a box's walk is seen through a page-wide effect: once every item has been seen by a viewport IntersectionObserver (with the options given), body
// gets .seen and the fixed 50 px header turns red (#c03) in the first screen.

test("capture --reveal: plain short page: nothing to scroll, and the run says so", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Short", "", LAYOUT(ITEMS(1, 500, "p")));
  assert.deepEqual(rec, { steps: 0, capped: false });
  assert.match(r.stdout, /reveal: nothing to scroll: in every load the page fits its screen and holds no box that scrolls/);
});

test("capture --reveal: body that scrolls itself: walked as a box, never 'scrolled' with no step", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "BodyScrolls", "html{overflow:hidden;height:100%}body{height:100%;overflow-y:auto}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.match(r.stdout, /6 steps at most, of 80 allowed; up to 6 of them inside 1 box that scrolls/);
});

test("capture --reveal: overflow-x:hidden body: its overflow is the window's, so the window is walked and no box", (t) => {
  if (needSetup(t)) return;
  const { rec } = revealLayout(makeProject(), "BodyOverflowX", "html,body{height:100%}body{overflow-x:hidden}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false });
});

test("capture --reveal: html overflow hidden + full-height main, scroll-snap (mandatory, proximity), scroll-behavior smooth (html, box): every step lands, every box back at its top", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const full = "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}";
  const sections = (n, h) => `<main>${Array.from({ length: n }, (_, k) => `<section style="height:${h};scroll-snap-align:start">${k ? "" : RED_BAND}</section>`).join("")}</main>`;
  const cases = {
    FullMain: [full, LAYOUT(`<main>${RED_BAND}${ITEMS(4, 975, "p")}</main>`), { steps: 8, capped: false, boxes: 1, box_steps: 8 }],
    SnapMandatory: [full + "main{scroll-snap-type:y mandatory}", LAYOUT(sections(4, "100%")), { steps: 6, capped: false, boxes: 1, box_steps: 6 }],
    SnapProximity: [full + "main{scroll-snap-type:y proximity}", LAYOUT(sections(6, "70%")), { steps: 7, capped: false, boxes: 1, box_steps: 7 }],
    SmoothBox: [full + "main{scroll-behavior:smooth}", LAYOUT(`<main>${RED_BAND}${ITEMS(4, 975, "p")}</main>`), { steps: 8, capped: false, boxes: 1, box_steps: 8 }],
    SmoothHtml: ["html{scroll-behavior:smooth}", LAYOUT(`${RED_BAND}${ITEMS(4, 975, "p")}`), { steps: 8, capped: false }],
  };
  for (const [name, [css, html, want]] of Object.entries(cases)) {
    const { rec, shots } = revealLayout(p, name, css, html);
    assert.deepEqual(rec, want, name);
    assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 100 * 0.9, `${name}: the first screen shows the top of the page`);
  }
});

test("capture --reveal: main under a 60 px header and under a 220 px header: the window's 60 px and the main are both walked", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const a = revealLayout(p, "Header60", "header{height:60px}main{height:100vh;overflow-y:auto}", LAYOUT(`<header></header><main>${ITEMS(3, 1000, "p")}</main>`));
  assert.deepEqual(a.rec, { steps: 7, capped: false, boxes: 1, box_steps: 6 });
  const b = revealLayout(p, "Header220", "html,body{height:100%;overflow:hidden}body{display:flex;flex-direction:column}header{height:220px;flex:none}main{flex:1;overflow-y:auto}",
    LAYOUT(`<header></header><main>${ITEMS(3, 1000, "p")}</main>`));
  assert.deepEqual(b.rec, { steps: 8, capped: false, boxes: 1, box_steps: 8 });
});

test("capture --reveal: sticky full-height sidebar on a short and on a long page: the sidebar and the window are both walked", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = "body{display:flex;align-items:flex-start}aside{position:sticky;top:0;height:100vh;overflow-y:auto;width:200px;flex:none}main{flex:1}";
  assert.deepEqual(revealLayout(p, "StickyShort", css, LAYOUT(`<aside>${ITEMS(3, 1000, "a")}</aside><main>${ITEMS(1, 500, "p")}</main>`)).rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.deepEqual(revealLayout(p, "StickyLong", css, LAYOUT(`<aside>${ITEMS(3, 1000, "a")}</aside><main>${ITEMS(5, 1000, "p")}</main>`)).rec, { steps: 16, capped: false, boxes: 1, box_steps: 6 });
});

test("capture --reveal: code box with max-height in a long page, and nested full-screen main with a max-height list: the small box is counted, not walked, and every box is back at its top", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const code = revealLayout(p, "CodeBox", ".late{height:300px;background:#c03;opacity:0}.late.in{opacity:1}pre{max-height:300px;overflow-y:auto;margin:0}",
    LAYOUT(`${ITEMS(1, 1800, "p")}<pre>${ITEMS(6, 1000, "c")}</pre>${ITEMS(1, 1200, "p")}<section class=late></section>`
      + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script>"));
  assert.deepEqual(code.rec, { steps: 7, capped: false, small_boxes: 1 });
  assert.ok(redPixels(path.join(code.shots, "1440-light-full.png")) > 1440 * 300 * 0.9, "the window was walked to its bottom, past the code box");
  assert.match(code.r.stdout, /1 box under half a screen tall that scrolls \(a code block, a short list\) was not walked/);
  const nested = revealLayout(p, "Nested", "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}ul{max-height:300px;overflow-y:auto;margin:0;padding:0}",
    LAYOUT(`<main>${RED_BAND}${ITEMS(1, 1100, "p")}<ul>${ITEMS(5, 1000, "l")}</ul>${ITEMS(1, 600, "p")}</main>`));
  assert.deepEqual(nested.rec, { steps: 3, capped: false, boxes: 1, box_steps: 3, small_boxes: 1 });
  assert.ok(redPixels(path.join(nested.shots, "1440-light.png")) > 1440 * 100 * 0.9, "main is back at its top in the first screen");
});

test("capture --reveal: closed off-canvas drawer (moved off the screen, or hidden), and a short list in a closed menu: not walked, not counted", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Drawer",
    "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}nav{position:fixed;top:0;height:100%;width:300px;overflow-y:auto}.left{left:0;transform:translateX(-100%)}.right{right:0;visibility:hidden}"
      + ".menu{position:fixed;top:0;left:0;width:300px;transform:translateX(-100%)}.menu ul{max-height:300px;overflow-y:auto;margin:0}",
    LAYOUT(`<main>${ITEMS(2, 1000, "p")}</main><nav class=left>${ITEMS(9, 1000, "d")}</nav><nav class=right>${ITEMS(9, 1000, "d")}</nav><div class=menu><ul>${ITEMS(10, 100, "m")}</ul></div>`));
  assert.deepEqual(rec, { steps: 3, capped: false, boxes: 1, box_steps: 3 });
  assert.ok(!/under half a screen/.test(r.stdout), r.stdout);
});

test("capture --reveal: grid of 8 tall scrolling cards: the walk stops at 80 steps and names the boxes it did not finish, never a long page", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Cards", ".grid{display:grid;grid-template-columns:repeat(4,1fr)}.card{height:500px;overflow-y:auto}",
    LAYOUT(`<div class=grid>${`<div class=card>${ITEMS(6, 1000, "c")}</div>`.repeat(8)}</div>${ITEMS(1, 3000, "p")}`));
  assert.deepEqual(rec, { steps: 80, capped: true, boxes: 4, box_steps: 73, boxes_unfinished: 5 });
  assert.match(r.stdout, /\(80 steps at most, of 80 allowed; up to 73 of them inside 4 boxes that scroll/);
  assert.match(r.stdout, /CAPPED: the page and its boxes needed more than 80 steps, so what lies further down in 5 boxes that scroll was not revealed/);
  assert.ok(!/longer than 40 screens/.test(r.stdout), r.stdout);
});

test("capture --reveal: box in the first screen whose items reveal by a viewport IntersectionObserver, on a long page: walked with the page scrolled back to show it", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "Panel", SEEN_HEADER + ".panel{height:600px;overflow-y:auto;margin-top:50px}",
    LAYOUT(`<header class=seen-bar></header><div class=panel>${ITEMS(6, 400)}</div>${ITEMS(1, 4000, "p")}${SEEN_SCRIPT(6)}`));
  assert.deepEqual(rec, { steps: 16, capped: false, boxes: 1, box_steps: 6 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all six items of the panel were seen in the viewport");
  assert.ok(redPixels(path.join(shots, "390-dark.png")) > 390 * 50 * 0.9);
});

test("capture --reveal: box taller than two screens: walked in half-screen steps, then carried up by the page until its bottom is shown, so every item is seen", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "TallBox", SEEN_HEADER + ".tall{height:2400px;overflow-y:auto}",
    LAYOUT(`<header class=seen-bar></header><div class=tall>${ITEMS(60, 100)}</div>${ITEMS(1, 3000, "p")}${SEEN_SCRIPT(60)}`));
  // the page: 10 steps at 900, 11 at 844; the box: 8 / 9 steps inside it, then 4 steps of the page carrying it up
  assert.deepEqual(rec, { steps: 24, capped: false, boxes: 1, box_steps: 13 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all 60 items of the tall box were seen in the viewport");
  assert.ok(redPixels(path.join(shots, "390-light.png")) > 390 * 50 * 0.9);
});

test("capture --reveal: a box that the page's walk reveals (opacity 0 until seen) is found after it and walked", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "LateBox", SEEN_HEADER + ".late{opacity:0}.late.in{opacity:1}.panel{height:600px;overflow-y:auto}",
    LAYOUT(`<header class=seen-bar></header>${ITEMS(1, 2000, "p")}<section class=late><div class=panel>${ITEMS(4, 400)}</div></section>`
      + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script>" + SEEN_SCRIPT(4)));
  assert.deepEqual(rec, { steps: 9, capped: false, boxes: 1, box_steps: 4 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "the late box's items were all seen");
});

test("capture --reveal: infinite scroll that appends on reaching the end: followed to its end with --wait 0, and the record says it grew", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Infinite", "",
    LAYOUT(`${ITEMS(1, 1800, "p")}<script>let n=0;addEventListener('scroll',()=>{const d=document.documentElement;if(scrollY+d.clientHeight>=d.scrollHeight-5&&n<5){n++;const e=document.createElement('div');e.style.height='1800px';if(n===5)e.style.background='#c03';document.body.append(e)}})</script>`));
  assert.deepEqual(rec, { steps: 28, capped: false, grew: true });
  assert.ok(redPixels(path.join(shots, "1440-light-full.png")) > 1440 * 1800 * 0.9, "the fifth page appended is in the full page");
  assert.match(r.stdout, /the page or a box grew as it was scrolled/);
});

test("capture --reveal: html overflow:clip: Chromium scrolls the root by script (clip on the root is hidden on the viewport), so the page is walked", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Clip", "html{overflow:clip}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false, root_hidden: true });
  assert.match(r.stdout, /NOTE: the page's own scrolling is hidden or clipped \(overflow: hidden or clip on the root, or on the body when the root's is visible\), so the walk scrolled it by script but a visitor cannot scroll it with the wheel/);
});
