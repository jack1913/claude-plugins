// shot --motion compares the rest frame in the page itself: the mark element's box is screenshotted where it is (rounded outward to whole pixels, the page's
// own background), the static SVG is drawn at the same place and size in the same page (an <img> for an <img>, inline otherwise), the element is hidden and
// the same clip is screenshotted. Same page, same raster tiles: the default tolerance is 0. A reference drawn on a scratch page at the origin is not the same
// raster once the mark is away from it (Chromium draws in tiles about 256 px wide that advance 254), which is why a mark at x = 53 differed from its own still.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, motionProject, run, byId, failing, writeProof, writePage, pageCase, mutateText, writeLockup, LOCKUP, ROOT } from "./_motion.mjs";
import { loadDep, readSetup } from "../../scripts/lib/_common.mjs";

const DOT = (svg, attrs) => svg.replace('<circle cx="44" cy="52" r="9"', '<circle class="lk-dot" cx="44" cy="52" r="9"').replace("<svg ", `<svg ${attrs} `);
// the lockup 53 px from the left (and 20 down), its dot pressing two pixels and back; under reduced motion nothing moves
const CSS = `#mark{display:block;margin:20px 0 0 53px}.lk-dot,.bar{animation:press 320ms steps(2,end) 1 both}.bar{position:absolute;left:200px;top:5px;width:30px;height:10px;background:#c03}`
  + `@keyframes press{0%{transform:translateY(0)}50%{transform:translateY(2px)}100%{transform:translateY(0)}}@media (prefers-reduced-motion: reduce){.lk-dot,.bar{animation:none}}`;
function lockupProject({ mark = DOT(LOCKUP, 'id="mark"'), css = CSS, extra = {} } = {}) {
  const p = motionProject();
  writeLockup(p);
  writePage(p, "inplace", { css, body: mark + '<div class="bar"></div>' });
  const proof = writeProof(p, [pageCase({ page: "motion/inplace.html", static: "assets/logo/lockup.svg", widths: [400], ...extra })]);
  return { p, proof };
}
const rest = (p, proof, which = "normal") => byId(p, proof)[`motion:case:${which}:rest=static`];

test("a mark placed at x = 53 compares exactly in place: 0 px differ, in the normal and the reduced pass", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = lockupProject();
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  for (const which of ["normal", "reduced"]) {
    const row = rest(p, proof, which);
    assert.equal(row.status, "pass", `${which}: ${row.detail}`);
    assert.equal(row.px_differ, 0); assert.equal(row.tolerance, 0);
    assert.match(row.detail, /^0 px differ \(largest difference 0\/255, tolerance 0\); compared in the page itself, 320x90 px at 53,20, the reference is the static SVG inline, over the <svg>'s content box$/);
  }
});

// The still is drawn where the element draws, whatever the page does around it: each of these pages draws the Acme lockup exactly as the still, so each must compare
// equal to the pixel. (Before, the still was placed against <body> at the element's document position, over its border box, outside its ancestors, inline
// where the page's style sheets reach it: every one of these failed by hundreds or thousands of pixels.)
const IMG = (style = "") => `<img id="mark" src="../assets/logo/lockup.svg" width="320" height="90" alt="Acme lockup" style="${style}">`;
const PLACED = {
  "a positioned body, centred with an offset": { css: "body{position:relative;max-width:600px;margin:0 auto}#mark{position:absolute;left:53px;top:20px}" },
  "a positioned body that keeps its 8 px margin": { css: "html,body{margin:revert}body{position:relative}#mark{position:absolute;left:53px;top:20px}" },
  "a parent at half opacity": { css: ".w{opacity:.5;margin:20px 0 0 53px}#mark{display:block}", wrap: true },
  "an ancestor scaled by a transform": { css: ".w{transform:scale(1.5);transform-origin:0 0;margin:20px 0 0 53px}#mark{display:block}", wrap: true },
  "a mark centred by its own transform": { css: "#mark{position:absolute;left:50%;top:20px;transform:translateX(-50%)}" },
  "an <svg> with padding, a border and a background of its own": { css: "#mark{display:block;margin:20px 0 0 53px;padding:6px;border:2px solid #c03;background:#fff}" },
  "a style sheet that animates every svg circle (it must not reach the still)": { css: "#mark{display:block;margin:20px 0 0 53px}svg circle{animation:pop 400ms both}@keyframes pop{from{transform:scale(.2)}to{transform:none}}" },
  "an <img> with padding and a border": { css: "#mark{display:block;margin:20px 0 0 53px;padding:6px;border:2px solid #c03;background:#fff}", mark: IMG() },
  "an <img> in a parent at half opacity": { css: ".w{opacity:.5;margin:20px 0 0 53px}#mark{display:block}", wrap: true, mark: IMG() },
};
test("the still is drawn where the element draws, whatever the page does around it: 0 px differ on every one of these pages", (t) => {
  if (needSetup(t)) return;
  const wrong = [];
  for (const [name, c] of Object.entries(PLACED)) {
    const mark = c.mark ?? DOT(LOCKUP, 'id="mark"');
    const { p, proof } = lockupProject({ mark: c.wrap ? `<div class="w">${mark}</div>` : mark, css: c.css + "@media (prefers-reduced-motion: reduce){*{animation:none!important}}", extra: { widths: [] } });
    run(p, proof);
    for (const which of ["normal", "reduced"]) if (rest(p, proof, which).px_differ !== 0) wrong.push(`${name}, ${which}: ${rest(p, proof, which).detail}`);
  }
  assert.deepEqual(wrong, []);
});

test("a part a CSS transition moved across the mark leaves no old drawing behind: the page's picture is drawn afresh first", (t) => {
  if (needSetup(t)) return;
  // the triangle slides in from 200 px to the left, over the disc, by a transition the page starts as it loads (its style read, then the class removed)
  const mark = LOCKUP.replace('<path d="M44 18 70 64H18Z"', '<path class="slide out" d="M44 18 70 64H18Z"').replace("<svg ", '<svg id="mark" ');
  const css = "#mark{display:block;margin:20px 0 0 53px}.slide{transition:transform 400ms linear}.slide.out{transform:translateX(-200px)}@media (prefers-reduced-motion: reduce){.slide{transition:none}}";
  const start = '<script>const s=document.querySelector(".slide");getComputedStyle(s).transform;s.classList.remove("out")</script>';
  const { p, proof } = lockupProject({ mark: mark + start, css, extra: { widths: [] } });
  run(p, proof);
  assert.match(byId(p, proof)["motion:case:sampling"].detail, /^1 Web Animation\(s\) paused and seeked/); // the transition was stepped through, with a frame drawn at each step
  assert.equal(rest(p, proof).px_differ, 0, rest(p, proof).detail);
});

test("a page that recolours the mark at rest fails: the still is the file as it is, out of reach of the page's style sheets", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = lockupProject({ css: CSS + "svg circle{fill:#c0392b}", extra: { widths: [] } }); // a rule that would reach an inline copy of the still too
  assert.equal(run(p, proof).status, 1);
  for (const which of ["normal", "reduced"]) assert.ok(rest(p, proof, which).px_differ > 1000, `${which}: ${rest(p, proof, which).detail}`);
});

test("a mark an ancestor rotates cannot be placed exactly: the comparison is not verified, never a pass or a false failure", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = lockupProject({ mark: `<div class="w">${DOT(LOCKUP, 'id="mark"')}</div>`, css: CSS + ".w{transform:rotate(10deg);margin:60px 0 0 60px}", extra: { widths: [] } });
  assert.equal(run(p, proof).status, 3);
  for (const which of ["normal", "reduced"]) {
    assert.equal(rest(p, proof, which).status, "skipped");
    assert.match(rest(p, proof, which).detail, /^not verified: the still could not be placed exactly over the mark element \(#mark\): it ended [\d.]+ css px off, as it does when an ancestor rotates or skews the element$/);
  }
});

test("a deliberately wrong rest frame still fails, with both pictures kept outside the project", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = lockupProject();
  mutateText(path.join(p, "assets/logo/lockup.svg"), 'r="34"', 'r="35"'); // the still changed, the page did not
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  assert.deepEqual(failing(p, proof), ["motion:case:normal:rest=static", "motion:case:reduced:rest=static"]);
  for (const which of ["normal", "reduced"]) {
    const row = rest(p, proof, which);
    assert.ok(row.px_differ > 100, `${which}: ${row.px_differ} px differ`);
    const dir = /; both images: (.+)$/.exec(row.detail)?.[1];
    assert.ok(dir && !path.resolve(dir).startsWith(fs.realpathSync(p)), `the pictures are in the data folder, never inside the project: ${dir}`);
    for (const f of [`${which}-element.png`, `${which}-static.png`]) assert.ok(fs.existsSync(path.join(dir, f)), f);
  }
});

test("the reference is drawn the way the element is: in the <img> itself, inline for an svg, and the row says which", (t) => {
  if (needSetup(t)) return;
  const img = '<img id="mark" src="../assets/logo/lockup.svg" width="320" height="90" alt="Acme lockup">';
  const box = `<div id="mark" style="width:320px;height:90px">${LOCKUP.replace("<svg ", '<svg style="display:block" ')}</div>`;
  for (const [kind, mark, said] of [["img", img, /the reference is the static SVG in the <img> itself \(its source swapped\)$/], ["svg", DOT(LOCKUP, 'id="mark"'), /the reference is the static SVG inline, over the <svg>'s content box$/],
    ["div", box, /the reference is the static SVG inline, over the whole <div>$/]]) {
    const { p, proof } = lockupProject({ mark });
    const r = run(p, proof);
    assert.equal(r.status, 0, `${kind}: ${r.stdout}`);
    for (const which of ["normal", "reduced"]) { assert.equal(rest(p, proof, which).px_differ, 0, `${kind} ${which}`); assert.match(rest(p, proof, which).detail, said, `${kind} ${which}`); }
  }
});

test("a difference below the tolerance passes, the same difference at tolerance 0 fails: the key is still accepted", (t) => {
  if (needSetup(t)) return;
  const a = lockupProject();
  mutateText(path.join(a.p, "assets/logo/lockup.svg"), 'fill="#0d1b2d"', 'fill="#0d1b2e"'); // one level of blue in the disc
  assert.equal(run(a.p, a.proof).status, 1);
  assert.ok(rest(a.p, a.proof).px_differ > 1000);
  assert.match(rest(a.p, a.proof).detail, /\(largest difference 1\/255, tolerance 0\)/);
  const b = lockupProject({ extra: { tolerance: 1 } });
  mutateText(path.join(b.p, "assets/logo/lockup.svg"), 'fill="#0d1b2d"', 'fill="#0d1b2e"');
  const r = run(b.p, b.proof);
  assert.equal(r.status, 0, r.stdout);
  assert.equal(rest(b.p, b.proof).px_differ, 0); assert.equal(rest(b.p, b.proof).tolerance, 1);
  assert.match(rest(b.p, b.proof).detail, /^0 px differ by more than 1\/255 \(largest difference 1\/255, tolerance 1\)/);
});

test("a mark larger than the screen, and below its fold, compares exactly too", (t) => {
  if (needSetup(t)) return;
  const big = DOT(LOCKUP, 'id="mark" style="width:1200px;height:338px"');
  const { p, proof } = lockupProject({ mark: big, css: CSS.replace("margin:20px 0 0 53px", "margin:760px 0 0 53px"), extra: { widths: [] } }); // 1200 x 338 at (53, 760) in a 900 x 700 view
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  assert.equal(rest(p, proof).px_differ, 0); assert.equal(rest(p, proof, "reduced").px_differ, 0);
  assert.match(rest(p, proof).detail, /1200x338 px at 53,760/);
});

test("a mark with no box at rest fails the comparison; it is not skipped", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = lockupProject({ css: CSS + "#mark{display:none}" });
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  for (const which of ["normal", "reduced"]) {
    assert.equal(rest(p, proof, which).status, "fail");
    assert.match(rest(p, proof, which).detail, /the mark element \(#mark\) has no box at rest \(display none, or no size\): there is nothing to compare/);
  }
});

test("a gradient in the still is the still's own, even when the page holds the same ids", (t) => {
  if (needSetup(t)) return;
  const drawing = (stop) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#007d71"/>`
    + `<stop offset="1" stop-color="${stop}"/></linearGradient></defs><circle cx="32" cy="32" r="26" fill="url(#g)"/></svg>`;
  const { p, proof } = lockupProject({ mark: drawing("#0d1b2d").replace("<svg ", '<svg id="mark" '), extra: { widths: [] } });
  fs.writeFileSync(path.join(p, "assets/logo/lockup.svg"), drawing("#0d1b2d"));
  assert.equal(run(p, proof).status, 0); // the same gradient on both sides: equal
  assert.equal(rest(p, proof).px_differ, 0);
  fs.writeFileSync(path.join(p, "assets/logo/lockup.svg"), drawing("#c0392b")); // the still's second stop is another colour; both files use the id "g"
  assert.equal(run(p, proof).status, 1);
  assert.ok(rest(p, proof).px_differ > 500, `the still's own gradient was not used: ${rest(p, proof).detail}`);
});

test("a still that cannot be drawn is a usage error that names it, not a crash", (t) => {
  if (needSetup(t)) return;
  const img = '<img id="mark" src="../assets/logo/lockup.svg" width="320" height="90" alt="Acme lockup">';
  for (const [kind, mark, said] of [["inline", DOT(LOCKUP, 'id="mark"'), /static assets\/logo\/lockup\.svg cannot be drawn in the page: it is not a well-formed SVG document/], ["img", img, /static assets\/logo\/lockup\.svg cannot be drawn in the page: /]]) {
    const { p, proof } = lockupProject({ mark });
    fs.writeFileSync(path.join(p, "assets/logo/lockup.svg"), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><g></svg>'); // not well-formed
    const r = run(p, proof);
    assert.equal(r.status, 2, `${kind}: ${r.stdout}${r.stderr}`);
    assert.match(r.stderr, said, kind);
  }
});

test("an animation that cannot be turned into plain style is named in the row, not left unsaid", (t) => {
  if (needSetup(t)) return;
  // an animation on a pseudo-element has no inline style to commit to: it stays on the page for the comparison, and the row says so
  const box = '<div id="mark" style="width:320px;height:90px"></div>';
  const css = CSS + "#mark::before{content:'';display:block;width:40px;height:10px;background:#007d71;animation:press 320ms steps(2,end) 1 both}@media (prefers-reduced-motion: reduce){#mark::before{animation:none}}";
  const { p, proof } = lockupProject({ mark: box, css, extra: { widths: [] } });
  fs.writeFileSync(path.join(p, "assets/logo/lockup.svg"), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="320" height="90"><rect width="40" height="10" fill="#007d71"/></svg>');
  run(p, proof);
  assert.match(rest(p, proof).detail, /; press on ::before could not be turned into plain style and stays on the page, which may colour a few pixels/);
  assert.doesNotMatch(rest(p, proof, "reduced").detail, /plain style/); // under reduced motion there is nothing left to name
});

test("a still hidden by a backwards fill and a moving copy shown by one are, once the motion has ended, the still visible and the copy hidden: the rest frame is compared as drawn", (t) => {
  if (needSetup(t)) return;
  // `hide` holds the still hidden and `show` the copy visible only until the motion ends (fill: backwards): after finish() neither effect applies, the still is visible and the
  // copy hidden. commitStyles() wrote their keyframe values (visibility: hidden on the still, visible on the copy) over that, and the comparison drew the copy
  const still = LOCKUP.replace("<svg ", '<svg class="still" '), copy = LOCKUP.replace('<circle cx="44" cy="52" r="9"', '<circle cx="64" cy="52" r="9"').replace("<svg ", '<svg class="copy" ');
  const mark = `<div id="mark" style="position:relative;width:320px;height:90px">${still}${copy}</div>`;
  const css = "#mark{display:block;margin:20px 0 0 53px}.still,.copy{position:absolute;left:0;top:0}.still{animation:hide 320ms 100ms backwards}"
    + ".copy{visibility:hidden;animation:show 320ms 100ms backwards,shift 320ms 100ms both}@keyframes hide{from,to{visibility:hidden}}@keyframes show{from,to{visibility:visible}}"
    + "@keyframes shift{from{transform:translateX(0)}to{transform:translateX(30px)}}@media (prefers-reduced-motion: reduce){.still,.copy{animation:none}}";
  const { p, proof } = lockupProject({ mark, css, extra: { widths: [] } });
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  for (const which of ["normal", "reduced"]) {
    assert.equal(rest(p, proof, which).status, "pass", `${which}: ${rest(p, proof, which).detail}`);
    assert.equal(rest(p, proof, which).px_differ, 0);
  }
  assert.doesNotMatch(rest(p, proof).detail, /plain style/);          // all three animations were turned into plain style (the third, `shift`, which still applies), or just dropped
  assert.match(byId(p, proof)["motion:case:sampling"].detail, /^3 Web Animation\(s\) paused and seeked/);
});

test("the settle step writes what an animation draws and keeps what it cannot write: a pseudo-element, and a property whose value reads empty", async (t) => {
  if (needSetup(t)) return;
  const src = fs.readFileSync(path.join(ROOT, "scripts/render.mjs"), "utf8");
  const settle = /function inPageSettle\(\) \{[\s\S]*?\n\}\n/.exec(src)?.[0];
  assert.ok(settle, "inPageSettle is in render.mjs");
  process.env.PLAYWRIGHT_BROWSERS_PATH = readSetup().browsers_path;
  const browser = await (await loadDep("playwright-core")).chromium.launch({ headless: true });
  try {
    const page = await (await browser.newContext()).newPage();
    await page.setContent("<!doctype html><style>#a,#b,#c,#d{width:10px;height:10px}#d::before{content:'x'}</style><div id=a></div><div id=b></div><div id=c></div><div id=d></div>");
    const got = await page.evaluate(`(() => {
      ${settle}
      const mk = (id, frames, opts) => { const el = document.getElementById(id), a = el.animate(frames, opts); return { el, a }; };
      const fill = { duration: 100, fill: "both" };
      // a: its effect applies at its end (fill: both): the computed value is written, the animation dropped
      // b: only a backwards fill: nothing applies at the end, so nothing is written (commitStyles would write visibility: hidden) and the animation is dropped
      // c: a property that reads empty (a name no style knows): not written, the animation stays and is named
      // d: an animation on a pseudo-element that still applies: nowhere to write, it stays and is named
      const A = mk("a", [{ width: "10px" }, { width: "40px" }], fill), B = mk("b", [{ visibility: "hidden" }, { visibility: "hidden" }], { duration: 100, delay: 50, fill: "backwards" });
      const C = mk("c", [{ width: "10px" }, { width: "30px" }], fill), D = mk("d", [{ width: "10px" }, { width: "30px" }], { ...fill, pseudoElement: "::before" });
      const all = [["a", A, ["width"]], ["b", B, ["visibility"]], ["c", C, ["fooBar"]], ["d", D, ["width"]]];
      window.__bc = { anims: all.map(([name, x, props]) => ({ a: x.a, seekable: true, name, props, target: x.el, pseudo: name === "d" ? "::before" : null })) };
      for (const x of [A, B, C, D]) x.a.finish();
      const left = inPageSettle();
      return { left, a: document.getElementById("a").style.width, b: document.getElementById("b").style.visibility, c: document.getElementById("c").style.cssText,
        playing: document.getAnimations().map((x) => x.effect.target.id + (x.effect.pseudoElement || "")) };
    })()`);
    assert.deepEqual(got.left, ["c", "d on ::before"]);
    assert.equal(got.a, "40px");                         // written from the computed style
    assert.equal(got.b, "");                             // the effect no longer applied: nothing written
    assert.equal(got.c, "");
    assert.deepEqual(got.playing.sort(), ["c", "d::before"]);   // a and b were dropped; c and d stay
  } finally { await browser.close(); }
});
