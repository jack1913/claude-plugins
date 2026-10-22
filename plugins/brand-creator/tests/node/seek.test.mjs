// shot --motion samples a page by seeking: every Web Animation is paused and set to a time, never waited for. The sample points (0, every 1/32 of
// the motion's length, every keyframe in page time), the infinite animation, the animation that ends another, motion driven by requestAnimationFrame
// (said in a row, never silent), the layout shift measured while the motion is stepped through, and the time a long animation takes.
// Each page here is written for its test (a purpose-built input), next to the Acme mark; the report is the proof's own.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, motionProject, run, rep, byId, failing, writeProof, writePage, inlineMark, pageCase } from "./_motion.mjs";

const REDUCED = "@media (prefers-reduced-motion: reduce){.bar,.box{animation:none!important}}";   // the pages respect reduced motion: only the normal pass moves
/** A project with one page of its own and a proof of one page case on it; `markup` is the page body besides the mark. */
function projectWith(css, markup, extra = {}, head = "") {
  const p = motionProject();
  writePage(p, "t", { css: `#mark{position:absolute;left:8px;top:8px;width:64px;height:64px}.bar{position:absolute;left:100px;width:40px;height:10px;background:#007d71}${REDUCED}${css}`, body: `${inlineMark(p)}${markup}`, head });
  const proof = writeProof(p, [pageCase({ page: "motion/t.html", ...extra })]);
  return { p, proof };
}
const sampling = (p, proof) => byId(p, proof)["motion:case:sampling"];
const r3 = (x) => Math.round(x * 1000) / 1000;
/** The points every 1/32 of an animation's own iterations (delay + (n + k/32) x duration), up to where it ends: as the proof takes them. */
const own = (delay, duration, iterations, end) => Array.from({ length: Math.ceil(iterations) * 32 + 1 }, (_, m) => r3(delay + (m / 32) * duration)).filter((x) => x <= end);
const union = (...lists) => [...new Set(lists.flat())].sort((a, b) => a - b);

test("the sample points are 0, every 1/32 of the motion's length, every keyframe offset in page time and every 1/32 of each animation's own iterations", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`
    #a{top:10px;animation:a 800ms linear 160ms 2 alternate both} #b{top:30px;animation:b 1000ms linear 1 both} #d{top:50px;animation:d 400ms linear 2.5 both}
    @keyframes a{from{transform:translateX(0)}25%{transform:translateX(10px)}to{transform:translateX(20px)}}
    @keyframes b{from{transform:translateX(0)}50%{transform:translateX(10px)}to{transform:translateX(20px)}}
    @keyframes d{from{transform:translateX(0)}to{transform:translateX(30px)}}`,
  `<div class="bar" id="a"></div><div class="bar" id="b"></div><div class="bar" id="d"></div><div class="bar" id="e" style="top:70px"></div>
   <script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.getElementById("e").animate([{transform:"translateX(0)"},{transform:"translateX(10px)",offset:0.3},{transform:"translateX(0)"}],{duration:1200,delay:40,fill:"both"})</script>`);
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const row = sampling(p, proof);
  // The motion lasts as long as its longest finite animation: a, 160 ms delay + 2 x 800 ms = 1760 ms, so the even points are 55 ms apart.
  // Keyframes in page time, worked out by hand:
  //   a (alternate, 2 iterations): 160, 360, 960 forward; reversed, an offset counts from the other end: 960, 1560, 1760  (not 1160: that is the forward formula)
  //   b: 500 (its 50%) and 1000;  d (2.5 iterations of 400 ms): 400, 800, and nothing at 1200, which is past its end at 1000
  //   e (element.animate, 40 ms delay, 1200 ms, offsets 0 / 0.3 / 1): 40, 400, 1240
  // and each animation's own 1/32: a every 25 ms from 160, b every 31.25 ms, d every 12.5 ms up to its end at 1000, e every 37.5 ms from 40
  const even = Array.from({ length: 33 }, (_, k) => 55 * k);
  const keyframes = [40, 160, 360, 400, 500, 800, 960, 1000, 1240, 1560];
  const owns = union(own(160, 800, 2, 1760), own(0, 1000, 1, 1000), own(0, 400, 2.5, 1000), own(40, 1200, 1, 1240)).filter((x) => !even.includes(x) && !keyframes.includes(x));
  const want = union(even, keyframes, owns);
  assert.deepEqual(row.points_ms, want);
  assert.equal(row.length_ms, 1760); assert.equal(row.animations, 4); assert.equal(want.length, 33 + 10 + owns.length);
  assert.deepEqual(row.points_pct, want.map((ms) => Math.round((1000 * ms) / 1760) / 10));
  assert.equal(row.points_pct[row.points_ms.indexOf(880)], 50); assert.equal(row.points_pct[row.points_ms.indexOf(40)], 2.3);
  assert.equal(row.status, "info");
  assert.equal(row.detail, `4 Web Animation(s) paused and seeked at ${want.length} sample point(s) over 1760 ms (0, every 1/32 of it, 10 more at keyframes, ${owns.length} at every 1/32 of each animation's own iterations)`);
});

test("a short animation inside a long motion is stepped through at its own 1/32 and at the peak of its overshooting curve", (t) => {
  if (needSetup(t)) return;
  // a 200 ms fly-in on cubic-bezier(0.34, 1.56, 0.64, 1), inside a motion that lasts 3200 ms: the even points are 100 ms apart, so only its own points see it.
  // The curve turns back where y'(t) = 0: 2.68 t^2 - 4.24 t + 1.56 = 0, t = 0.58209, at x(t) = 57.28 % of its time, 114.56 ms
  const { p, proof } = projectWith(`.bar{top:10px}#fly{animation:fly 200ms cubic-bezier(0.34, 1.56, 0.64, 1) both}#fade{top:30px;animation:fade 3200ms linear both}
    @keyframes fly{from{transform:translateX(-60px)}to{transform:none}}@keyframes fade{from{opacity:0}to{opacity:1}}`, `<div class="bar" id="fly"></div><div class="bar" id="fade"></div>`);
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const row = sampling(p, proof);
  assert.equal(row.length_ms, 3200);
  for (const ms of own(0, 200, 1, 200)) assert.ok(row.points_ms.includes(ms), `${ms} ms (the fly-in's own 1/32) is a sample point`);
  const t0 = (4.24 - Math.sqrt(4.24 * 4.24 - 4 * 2.68 * 1.56)) / (2 * 2.68), x = 3 * (1 - t0) ** 2 * t0 * 0.34 + 3 * (1 - t0) * t0 ** 2 * 0.64 + t0 ** 3;
  assert.ok(row.points_ms.some((ms) => Math.abs(ms - 200 * x) < 0.01), `the peak at ${(200 * x).toFixed(3)} ms is a sample point`);
  assert.match(row.detail, /, 1 where an easing turns back or holds a step,/);
});

test("an animation a script starts after the first look is waited for, seeked from its own start and said", (t) => {
  if (needSetup(t)) return;
  // nothing moves for 400 ms; then a script starts the motion. The proof looks at every frame until settle_ms (here 1500), pauses it at once and seeks it
  const { p, proof } = projectWith(`.bar{top:10px}.bar.go{animation:go 320ms linear both}@keyframes go{from{transform:none}50%{transform:translateX(30px)}to{transform:none}}`,
    `<div class="bar"></div><script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)setTimeout(()=>document.querySelector(".bar").classList.add("go"),400)</script>`, { settle_ms: 1500 });
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const control = byId(p, proof)["motion:case:control"];
  assert.equal(control.status, "pass");
  assert.match(control.detail, /^normal pass: 1 animation\(s\) seen, .*; the motion began \d+ ms after the page started loading \(a script started it\), found by looking at every frame$/);
  const began = Number(/began (\d+) ms after the page started loading/.exec(control.detail)[1]);
  assert.ok(began >= 400 && began < 1500, `began at ${began} ms`);
  const row = sampling(p, proof);
  assert.equal(row.length_ms, 320); assert.ok(row.points_ms.includes(160), "its 50% keyframe is a sample point");
  assert.match(row.detail, /; the motion began \d+ ms after the page started loading and was seeked from its own start$/);
  assert.equal(byId(p, proof)["motion:case:settled"].detail, "1 animation(s) seen, every one finite, none running once each was seeked to its end");
});

test("an infinite animation is sampled over its first iteration only, and fails loops and settled", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`
    #f{top:10px;animation:f 960ms linear 1 both} #s{top:30px;animation:s 400ms linear infinite}
    @keyframes f{from{transform:translateX(0)}to{transform:translateX(20px)}}
    @keyframes s{from{transform:translateX(0)}50%{transform:translateX(10px)}to{transform:translateX(0)}}`,
  `<div class="bar" id="f"></div><div class="bar" id="s"></div>`);
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  const bad = failing(p, proof);
  assert.ok(bad.includes("motion:case:loops") && bad.includes("motion:case:settled"), bad.join());
  assert.ok(!bad.includes("motion:case:normal:rest=static"), bad.join());
  assert.match(byId(p, proof)["motion:case:loops"].detail, /infinite animation\(s\): s;/);
  // the finite animation lasts 960 ms: the even points are 30 ms apart (its own points too); the spinner adds its 50% (200), its first iteration's end
  // (400) and its own 1/32 of that first iteration (every 12.5 ms), never a point past 400
  const row = sampling(p, proof);
  assert.equal(row.length_ms, 960);
  assert.deepEqual(row.points_ms, union(Array.from({ length: 33 }, (_, k) => 30 * k), [200, 400], own(0, 400, 1, 400)));
});

test("a page with only an infinite animation is sampled over its first iteration", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`#s{top:30px;animation:s 640ms linear 100ms infinite}@keyframes s{from{transform:translateX(0)}25%{transform:translateX(10px)}to{transform:translateX(0)}}`, `<div class="bar" id="s"></div>`);
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  assert.deepEqual(failing(p, proof), ["motion:case:loops", "motion:case:settled"]);
  const row = sampling(p, proof);
  assert.equal(row.length_ms, 740); // its delay and its first iteration: the finite end it does not have
  assert.deepEqual(row.points_ms, union(Array.from({ length: 33 }, (_, k) => r3((740 * k) / 32)), [100, 260, 740], own(100, 640, 1, 740)));
});

test("an animation a script starts shortly after load is paused and seeked like the rest", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`.bar{top:10px}#a{animation:a 320ms linear 1 both}@keyframes a{from{transform:none}to{transform:translateX(20px)}}`,
    `<div class="bar" id="a"></div><div class="bar" id="late" style="top:30px"></div>
     <script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)setTimeout(()=>document.getElementById("late").animate([{transform:"none"},{transform:"translateX(20px)",offset:0.3},{transform:"none"}],{duration:640,fill:"both"}),100)</script>`);
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const row = sampling(p, proof);
  assert.equal(row.animations, 2); // the one the stylesheet starts and the one the script starts 100 ms in
  assert.equal(row.length_ms, 640);
  assert.ok(row.points_ms.includes(192), "its keyframe at 30% (192 ms) is a sample point");
});

test("a long run of keyframes is thinned to 400 points, and the row says so", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`#a{top:10px;animation:a 100ms linear 300 both}@keyframes a{from{transform:none}50%{transform:translateX(10px)}to{transform:none}}`, `<div class="bar" id="a"></div>`);
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const row = sampling(p, proof);
  assert.equal(row.length_ms, 30000);
  assert.equal(row.points_ms.length, 400); // 33 even points and the 367 of the 600 keyframe points that are kept; the keyframes come before the own points
  assert.match(row.detail, /over 30000 ms \(0, every 1\/32 of it, 367 more at keyframes; thinned to 400 in all, the keyframes and turns kept first\)$/);
  for (let b = 0; b < 10; b++) { // the points kept span the whole motion, not its first iterations
    const n = row.points_ms.filter((x) => x >= 3000 * b && x < 3000 * (b + 1)).length;
    assert.ok(n >= 30, `${n} point(s) from ${3000 * b} to ${3000 * (b + 1)} ms`);
  }
  assert.deepEqual(row.points_ms, [...row.points_ms].sort((a, b) => a - b));
  assert.ok(row.points_ms.includes(0) && row.points_ms.includes(30000)); // the ends are never thinned away
});

test("a finite animation the end of another starts is finished too, and the page settles", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`
    #a{top:10px;animation:a 300ms linear 1 both} #b{top:30px} #b.go{animation:b 600ms linear 1 both}
    @keyframes a{from{transform:translateX(0)}to{transform:translateX(20px)}} @keyframes b{from{transform:translateX(0)}to{transform:translateX(20px)}}`,
  `<div class="bar" id="a"></div><div class="bar" id="b"></div>
   <script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.getElementById("a").addEventListener("animationend",()=>document.getElementById("b").classList.add("go"))</script>`);
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const row = byId(p, proof)["motion:case:settled"];
  assert.equal(row.status, "pass");
  assert.match(row.detail, /2 animation\(s\) seen/); // a, and b which the end of a started while it was seeked to its end
});

test("an animation that cannot be finished fails settled and names it", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`.bar{top:10px;animation:go 300ms linear 1 both}@keyframes go{from{transform:none}to{transform:translateX(20px)}}`,
    `<div class="bar"></div><script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.querySelector(".bar").getAnimations()[0].playbackRate=0</script>`); // at rate 0 it never ends
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  assert.deepEqual(failing(p, proof), ["motion:case:settled"]);
  assert.equal(byId(p, proof)["motion:case:settled"].detail, "not ended: go: InvalidStateError");
});

/** A page whose ball is moved by requestAnimationFrame (`dx` px out and back over `ms`; forever when `ms` is 0), on the Acme mark's page. */
const RAF_BALL = (dx, ms) => `<div id="ball"></div><script>
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const t0 = performance.now(), ball = document.getElementById("ball");
    (function tick(now) { const k = ${ms} ? Math.min(1, (now - t0) / ${ms}) : ((now - t0) / 300) % 1; ball.style.transform = "translateX(" + Math.round(${dx} * Math.sin(Math.PI * k)) + "px)"; if (!${ms} || k < 1) requestAnimationFrame(tick); })(t0);
  }</script>`;

test("motion driven by requestAnimationFrame is waited for in real time and said; the edges it may cross are not verified", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`#ball{position:absolute;left:100px;top:10px;width:20px;height:20px;background:#c03}`, RAF_BALL(40, 300), { settle_ms: 700 });
  const r = run(p, proof);
  assert.equal(r.status, 3, r.stdout); // not verified: no row failed, and the edges could not be stepped through
  const row = sampling(p, proof);
  assert.equal(row.status, "warn"); assert.equal(row.real_time, true);
  assert.match(row.detail, /^sampled in real time: requestAnimationFrame-driven motion cannot be seeked \(\d+ call\(s\) in the first 150 ms after load; the page was given 700 ms\)$/);
  assert.equal(byId(p, proof)["motion:case:control"].status, "pass"); // the requestAnimationFrame calls are the motion the control sees
  assert.ok(row.elapsed_ms >= 700, `the page was given its 700 ms: ${row.elapsed_ms}`);
  for (const w of [360, 390]) {
    const e = byId(p, proof)[`motion:case:edges:${w}`];
    assert.equal(e.status, "skipped", `${w}: ${e.detail}`);
    assert.match(e.detail, /^not verified: the mark is also moved by requestAnimationFrame, which cannot be seeked, so what it draws between two frames is not known; /);
  }
  // the loop stopped within settle_ms: it is no infinite loop, and that was looked at
  assert.equal(byId(p, proof)["motion:case:loops"].detail, "no infinite animation, and no requestAnimationFrame call in the 500 ms after settle_ms");
  assert.equal(byId(p, proof)["motion:case:settled"].status, "pass");
});

test("a pixel mark moved by requestAnimationFrame is not verified to move in whole pixels, never passed with nothing measured", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`#ball{position:absolute;left:100px;top:10px;width:20px;height:20px;background:#c03}`, RAF_BALL(40, 300), { settle_ms: 700, pixel: true, widths: [] });
  assert.equal(run(p, proof).status, 3);
  const row = byId(p, proof)["motion:case:whole-pixel"];
  assert.equal(row.status, "skipped");
  assert.match(row.detail, /^not verified: the mark is also moved by requestAnimationFrame, which cannot be seeked, so what it draws between two frames is not known; a pixel mark \(the case says "pixel": true\)/);
});

test("a requestAnimationFrame loop that never stops fails loops and settled", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`#ball{position:absolute;left:100px;top:10px;width:20px;height:20px;background:#c03}`, RAF_BALL(40, 0), { settle_ms: 700, widths: [] });
  assert.equal(run(p, proof).status, 1);
  assert.deepEqual(failing(p, proof), ["motion:case:loops", "motion:case:settled"]);
  for (const id of ["loops", "settled"]) assert.match(byId(p, proof)[`motion:case:${id}`].detail, /a requestAnimationFrame loop: \d+ call\(s\) in the 500 ms after the page was given 700 ms \(settle_ms\)$/);
});

test("a requestAnimationFrame loop that starts after the first look is found while the animations are stepped through", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`#ball{position:absolute;left:100px;top:40px;width:20px;height:20px;background:#c03}.bar{top:10px;animation:go 400ms linear 1 both}@keyframes go{from{transform:none}to{transform:translateX(20px)}}`,
    `<div class="bar"></div><div id="ball"></div><script>
      if (!matchMedia("(prefers-reduced-motion: reduce)").matches) setTimeout(() => {   // 350 ms in: after the first look (150 ms), within the stepping that follows
        const t0 = performance.now(), ball = document.getElementById("ball");
        (function tick(now) { const k = Math.min(1, (now - t0) / 150); ball.style.transform = "translateX(" + Math.round(40 * Math.sin(Math.PI * k)) + "px)"; if (k < 1) requestAnimationFrame(tick); })(t0);
      }, 350);</script>`, { settle_ms: 700 });
  const r = run(p, proof);
  assert.equal(r.status, 3, r.stdout); // its edges are not verified
  const row = sampling(p, proof);
  assert.equal(row.status, "warn"); assert.equal(row.real_time, true);
  // found by the look at the page, or while it was stepped through (a slow machine moves the 350 ms): either way it is waited for and said
  assert.match(row.detail, /^sampled in real time: requestAnimationFrame-driven motion cannot be seeked \(\d+ call\(s\) (while the animations were stepped through|in the first 150 ms after load); the page was given 700 ms\); 1 Web Animation\(s\) paused and seeked at 33 sample point\(s\)/);
  assert.equal(byId(p, proof)["motion:case:edges:360"].status, "skipped");
});

test("an animation of a layout property fails cls:normal under seeking, a transform passes", (t) => {
  if (needSetup(t)) return;
  // Chromium counts no shift under 3 css px between two frames: a big move is measured step by step, a small one is caught by the property it animates
  const variants = {
    top: [`.box{position:absolute;left:100px;top:10px;width:40px;height:40px;background:#c03;animation:s 400ms linear 100ms both}@keyframes s{from{top:10px}to{top:310px}}`, `<div class="box"></div>`],
    "top, small steps": [`.box{position:absolute;left:100px;top:10px;width:40px;height:40px;background:#c03;animation:s 400ms linear 100ms both}@keyframes s{from{top:10px}to{top:70px}}`, `<div class="box"></div>`],
    width: [`.row{display:flex;position:absolute;left:100px;top:10px}.box{height:40px;width:40px;background:#c03;animation:s 400ms linear both}.sib{width:30px;height:40px;background:#0a6}@keyframes s{from{width:40px}to{width:200px}}`, `<div class="row"><div class="box"></div><div class="sib"></div></div>`],
    margin: [`.row{display:flex;position:absolute;left:100px;top:10px}.box{height:40px;width:40px;background:#c03;animation:s 400ms linear both}.sib{width:30px;height:40px;background:#0a6}@keyframes s{from{margin-left:0}to{margin-left:100px}}`, `<div class="row"><div class="box"></div><div class="sib"></div></div>`],
    transform: [`.box{position:absolute;left:100px;top:10px;width:40px;height:40px;background:#c03;animation:s 400ms linear both}@keyframes s{from{transform:translateX(0)}to{transform:translateX(200px)}}`, `<div class="box"></div>`],
  };
  for (const [kind, [css, markup]] of Object.entries(variants)) {
    const { p, proof } = projectWith(css, markup);
    const r = run(p, proof);
    const row = byId(p, proof)["motion:case:cls:normal"];
    if (kind === "transform") {
      assert.equal(r.status, 0, `${kind}: ${r.stdout}`); assert.equal(row.status, "pass"); assert.equal(row.cls, 0); assert.deepEqual(row.layout_properties, []);
    } else {
      assert.equal(r.status, 1, `${kind}: ${r.stdout}`); assert.deepEqual(failing(p, proof), ["motion:case:cls:normal"], kind);
      const prop = { top: "top", "top, small steps": "top", width: "width", margin: "margin-left" }[kind];
      assert.deepEqual(row.layout_properties, [`${prop} (s)`], kind);
      assert.match(row.detail, new RegExp(`; animates a layout property: ${prop} \\(s\\); it moves the page around it as it runs, and a step under 3 css px is not counted as a shift`), kind);
      if (kind !== "top, small steps") {
        assert.ok(row.cls > 0 && /^CLS 0\.\d+ over load \+ \d+ sample point\(s\)/.test(row.detail), `${kind}: ${row.detail}`);
        assert.ok(row.shifts >= 30, `${kind}: ${row.shifts} shift(s): a rendered frame between two steps gives each its own`); // one per step, not one for the whole motion
      }
    }
  }
});

test("a 10 s finite animation is seeked, not waited for: the normal pass takes a fraction of it", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith(`.bar{top:10px;animation:slow 10s linear 1 both}@keyframes slow{from{transform:translateX(0)}to{transform:translateX(30px)}}`, `<div class="bar"></div>`);
  const started = Date.now();
  const r = run(p, proof);
  const whole = Date.now() - started;
  assert.equal(r.status, 0, r.stdout);
  const row = sampling(p, proof);
  assert.equal(row.length_ms, 10000);
  assert.equal(byId(p, proof)["motion:case:settled"].status, "pass"); // it ended: each animation is finished by seeking, with no wait for it
  assert.ok(row.elapsed_ms < 6000, `the normal pass took ${row.elapsed_ms} ms for a 10 000 ms animation`);
  assert.ok(whole < 12000, `the whole proof took ${whole} ms`);
});
