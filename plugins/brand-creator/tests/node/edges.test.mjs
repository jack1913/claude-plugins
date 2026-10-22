// shot --motion loads a page case again at the phone widths (360 and 390 css px, 800 high) and, at every sample point of its motion, looks at the four
// edges: the page no wider than the screen (it cannot be swiped sideways), no part of the mark past the left, top or right edge, the page no taller than
// at rest. One row per width; a failure names the sample point, the element, the edge and how far past it. Each test pushes a part past one edge.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, motionProject, run, byId, failing, writeProof, writePage, pageCase } from "./_motion.mjs";

// A 320 x 90 mark (a disc and a part, g#letter-a) at the top left of its page, and the same drawing as the still. The part is a 50 x 40 box at x 250..300,
// y 10..50, so it ends 60 px inside the 360 px screen; the keyframes (`move`) push it out and bring it back. `svg` holds extra attributes of the mark's root.
const DRAWING = (extra = "") => `<svg xmlns="http://www.w3.org/2000/svg" ${extra} viewBox="0 0 320 90" width="320" height="90" role="img" aria-label="Edge mark">`
  + `<circle cx="40" cy="45" r="30" fill="#0d1b2d"/><g id="letter-a"><rect x="250" y="10" width="50" height="40" fill="#007d71"/></g></svg>`;
// The same mark made of HTML boxes (the disc is an svg, the part a div): what it pushes out of the page counts in the page's width, which an svg's
// own drawing does not (the content of an <svg> never makes the page scroll, whatever its overflow).
const HTML_MARK = `<div id="mark" style="position:relative;width:320px;height:90px"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="320" height="90" style="display:block">`
  + `<circle cx="40" cy="45" r="30" fill="#0d1b2d"/></svg><div id="letter-a" style="position:absolute;left:250px;top:10px;width:50px;height:40px;background:#007d71"></div></div>`;
function projectWith({ move, css = "", body = "", svg = "", html = false, extra = {} }) {
  const p = motionProject();
  fs.writeFileSync(path.join(p, "assets/logo/edge.svg"), DRAWING());
  writePage(p, "edge", {
    css: `#mark{display:block}#letter-a{animation:go 400ms linear 1 both}@keyframes go{from{transform:none}50%{transform:${move}}to{transform:none}}`
      + `@media (prefers-reduced-motion: reduce){#letter-a,.moving{animation:none!important}}${css}`,
    body: (html ? HTML_MARK : DRAWING(`id="mark" ${svg}`)) + body,
  });
  const proof = writeProof(p, [pageCase({ page: "motion/edge.html", static: "assets/logo/edge.svg", ...extra })]);
  return { p, proof };
}
const row = (p, proof, w) => byId(p, proof)[`motion:case:edges:${w}`];

test("a part past the right edge fails the width it crosses and names where, what and how far; the wider screen passes", (t) => {
  if (needSetup(t)) return;
  // at 50% (200 ms) the part is 82 px to the right: its box ends at 300 + 82 = 382, 22 px past a 360 px screen and 8 px inside a 390 px one;
  // it is a box of the page, so the page can be swiped sideways at 360 and not at 390
  const { p, proof } = projectWith({ move: "translateX(82px)", html: true });
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  assert.deepEqual(failing(p, proof), ["motion:case:edges:360"]);
  const bad = row(p, proof, 360);
  assert.match(bad.detail, /^at 50% \(200 ms\): div#letter-a 22 px past the right edge at 360 px; /);
  assert.match(bad.detail, /at 50% \(200 ms\): html 22 px past the right edge at 360 px \(the page can be swiped sideways\)$/);
  assert.equal(row(p, proof, 390).status, "pass");
  assert.match(row(p, proof, 390).detail, /33 sample point\(s\) over 400 ms: no part of the mark \(4 box\(es\)\) past the left, top or right edge/);
});

test("a part past the right edge fails even when the page does not scroll: the mark's own boxes are measured", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith({ move: "translateX(82px)" }); // the svg clips what leaves it: scrollWidth stays 360
  assert.equal(run(p, proof).status, 1);
  const bad = row(p, proof, 360);
  assert.equal(bad.status, "fail");
  assert.match(bad.detail, /g#letter-a 22 px past the right edge at 360 px/);
  assert.doesNotMatch(bad.detail, /swiped sideways/);
  assert.deepEqual(bad.past.map((b) => [b.who, b.edge, b.px]), [["g#letter-a", "right", 22], ["rect", "right", 22]]);
});

test("a part past the left edge fails", (t) => {
  if (needSetup(t)) return;
  // the part's box starts at x 250: a move of 272 px to the left puts its left edge at -22
  const { p, proof } = projectWith({ move: "translateX(-272px)" });
  assert.equal(run(p, proof).status, 1);
  assert.deepEqual(failing(p, proof), ["motion:case:edges:360", "motion:case:edges:390"]);
  for (const w of [360, 390]) assert.match(row(p, proof, w).detail, new RegExp(`^at 50% \\(200 ms\\): g#letter-a 22 px past the left edge at ${w} px`));
});

test("a part past the top edge fails", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith({ move: "translateY(-32px)" }); // the part starts at y 10
  assert.equal(run(p, proof).status, 1);
  assert.deepEqual(failing(p, proof), ["motion:case:edges:360", "motion:case:edges:390"]);
  for (const w of [360, 390]) assert.match(row(p, proof, w).detail, new RegExp(`^at 50% \\(200 ms\\): g#letter-a 22 px past the top edge at ${w} px`));
});

test("a page that grows taller than it is at rest fails the bottom edge", (t) => {
  if (needSetup(t)) return;
  // a block under the mark grows from 100 px to 1400 px and back; at rest the page is the 800 px screen, at the peak 90 + 1400
  const { p, proof } = projectWith({
    move: "none", css: "#grow{height:100px;background:#c03;animation:grow 400ms linear 1 both}@keyframes grow{from{height:100px}50%{height:1400px}to{height:100px}}", body: '<div id="grow" class="moving"></div>',
  });
  assert.equal(run(p, proof).status, 1);
  const bad = row(p, proof, 360);
  assert.equal(bad.status, "fail");
  assert.match(bad.detail, /^at 50% \(200 ms\): html 690 px past the bottom edge at 360 px \(the page is taller than at rest\)$/);
  assert.equal(bad.rest_height, 800);
});

test("a page that can be swiped sideways fails even when the mark itself stays inside", (t) => {
  if (needSetup(t)) return;
  // a bar elsewhere on the page ends at 140 and goes 500 px to the right: the page is 640 wide at its widest
  const { p, proof } = projectWith({
    move: "none", css: ".bar{position:absolute;left:100px;top:100px;width:40px;height:10px;background:#c03;animation:bar 400ms linear 1 both}@keyframes bar{from{transform:none}50%{transform:translateX(500px)}to{transform:none}}",
    body: '<div class="bar moving"></div>',
  });
  assert.equal(run(p, proof).status, 1);
  assert.equal(row(p, proof, 360).detail, "at 50% (200 ms): html 280 px past the right edge at 360 px (the page can be swiped sideways)");
  assert.equal(row(p, proof, 390).detail, "at 50% (200 ms): html 250 px past the right edge at 390 px (the page can be swiped sideways)");
});

test("the widths come from the case: a list of its own replaces 360 and 390", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith({ move: "translateX(82px)", svg: 'style="overflow:visible"', extra: { widths: [320, 400, 500] } });
  const r = run(p, proof);
  assert.equal(r.status, 1, r.stdout);
  const ids = Object.keys(byId(p, proof)).filter((id) => id.includes(":edges:"));
  assert.deepEqual(ids, ["motion:case:edges:320", "motion:case:edges:400", "motion:case:edges:500"]);
  assert.equal(row(p, proof, 320).status, "fail"); // 382 > 320
  assert.match(row(p, proof, 320).detail, /g#letter-a 62 px past the right edge at 320 px/);
  assert.equal(row(p, proof, 400).status, "pass"); // 382 < 400
  assert.equal(row(p, proof, 500).status, "pass");
  const none = projectWith({ move: "none", extra: { widths: [] } });
  assert.equal(run(none.p, none.proof).status, 0);
  assert.equal(byId(none.p, none.proof)["motion:case:edges"].status, "info");
});

test("a mark that is not drawn at a phone width is said, not passed in silence", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith({ move: "translateX(50px)", css: "@media (max-width:400px){#mark{display:none}}" });
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout); // nothing crossed an edge; the warning is not a failure
  for (const w of [360, 390]) {
    assert.equal(row(p, proof, w).status, "warn");
    assert.match(row(p, proof, w).detail, new RegExp(`the mark element has no box at ${w} px \\(not drawn there\\), so only the page was measured`));
  }
});

test("the count of what else crossed is the count of every element past an edge, not of the first eight", (t) => {
  if (needSetup(t)) return;
  // twelve parts of their own (r1..r12, right edges at 254..298) in the group, moved 110 px: each ends past 360, and with the group 13 elements do
  const rects = Array.from({ length: 12 }, (_, k) => `<rect id="r${k + 1}" x="${250 + 4 * k}" y="10" width="4" height="40" fill="#007d71"/>`).join("");
  const drawing = (id = "") => `<svg xmlns="http://www.w3.org/2000/svg" ${id} viewBox="0 0 320 90" width="320" height="90"><circle cx="40" cy="45" r="30" fill="#0d1b2d"/><g id="letter-a">${rects}</g></svg>`;
  const p = motionProject();
  fs.writeFileSync(path.join(p, "assets/logo/edge.svg"), drawing());
  writePage(p, "edge", { css: `#mark{display:block}#letter-a{animation:go 400ms linear 1 both}@keyframes go{from{transform:none}50%{transform:translateX(110px)}to{transform:none}}`
    + "@media (prefers-reduced-motion: reduce){#letter-a{animation:none}}", body: drawing('id="mark"') });
  const proof = writeProof(p, [pageCase({ page: "motion/edge.html", static: "assets/logo/edge.svg", widths: [360] })]);
  assert.equal(run(p, proof).status, 1);
  assert.match(row(p, proof, 360).detail, /; and 9 more$/); // four named, nine more: thirteen
});

test("a keyframe moved in time by the effect's own easing is stepped on: the peak of the crossing is measured in full", (t) => {
  if (needSetup(t)) return;
  // element.animate with easing "ease-in" over the whole effect: the keyframe at offset 0.3 (82 px to the right, 22 px past 360) is reached where
  // ease-in gives 0.3, not at 30 % of the time; the crossing there is 22 px, and a point a little off the peak sees less
  const { p, proof } = projectWith({ move: "none", css: "#letter-a{animation:none}", extra: { widths: [360] },
    body: '<script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.getElementById("letter-a").animate([{transform:"none"},{transform:"translateX(82px)",offset:0.3},{transform:"none"}],{duration:1000,easing:"ease-in",fill:"both"})</script>' });
  assert.equal(run(p, proof).status, 1);
  const g = row(p, proof, 360).past.find((b) => b.who === "g#letter-a" && b.edge === "right");
  assert.equal(g.px, 22);
});

test("an overshooting curve inside a long motion is stepped at its peak: the crossing only the peak makes fails", (t) => {
  if (needSetup(t)) return;
  // the part flies in from 250 px to the left on cubic-bezier(0.34, 1.56, 0.64, 1), starting 140 ms in, inside a 3200 ms motion (a fade elsewhere):
  // the even points are 100 ms apart and see it at 200 ms (well inside) and at rest; only its own points and its peak see the overshoot past 320 px
  const { p, proof } = projectWith({
    move: "none", extra: { widths: [320] }, body: '<div class="fade moving" style="width:10px;height:10px;background:#c03"></div>',
    css: "#letter-a{animation:fly 200ms cubic-bezier(0.34, 1.56, 0.64, 1) 140ms both}@keyframes fly{from{transform:translateX(-250px)}to{transform:none}}"
      + ".fade{animation:fade 3200ms linear both}@keyframes fade{from{opacity:0}to{opacity:1}}",
  });
  assert.equal(run(p, proof).status, 1);
  // the peak: y'(t) = 0 at t = (4.24 - sqrt(1.2576)) / 5.36; there the part is -250 + 250 y(t) px from rest, its right edge at 300 + that
  const tp = (4.24 - Math.sqrt(4.24 * 4.24 - 4 * 2.68 * 1.56)) / (2 * 2.68), y = 3 * (1 - tp) ** 2 * tp * 1.56 + 3 * (1 - tp) * tp ** 2 + tp ** 3;
  const g = row(p, proof, 320).past.find((b) => b.who === "g#letter-a" && b.edge === "right");
  assert.ok(g && Math.abs(g.px - (300 - 250 + 250 * y - 320)) < 0.01, `the crossing at the peak, ${(300 - 250 + 250 * y - 320).toFixed(2)} px: ${JSON.stringify(g)}`);
});

test("a part a script starts moving after the first look is still stepped through at the phone widths", (t) => {
  if (needSetup(t)) return;
  const { p, proof } = projectWith({ move: "translateX(82px)", css: "#letter-a{animation:none}#letter-a.go{animation:go 400ms linear 1 both}", extra: { settle_ms: 1500 },
    body: '<script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)setTimeout(()=>document.getElementById("letter-a").classList.add("go"),400)</script>' });
  assert.equal(run(p, proof).status, 1);
  assert.deepEqual(failing(p, proof), ["motion:case:edges:360"]);
  assert.match(row(p, proof, 360).detail, /^at 50% \(200 ms\): g#letter-a 22 px past the right edge at 360 px/);
});
