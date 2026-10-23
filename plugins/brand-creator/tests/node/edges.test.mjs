// shot --motion loads a page case again at the phone widths (360 and 390 css px, 800 high) and, at every sample point of its motion, looks at the four
// edges: the page no wider than the screen (it cannot be swiped sideways), no part of the mark past the left, top or right edge, the page no taller than
// at rest. One row per width; a failure names the sample point, the element, the edge and how far past it. Each test pushes a part past one edge. A box of the mark
// counts where it is painted: what an ancestor clips (an overflow, a contain: paint, the viewport of an <svg>) is not past the edge, and neither is a box while it
// is transparent or visibility: hidden. The mark of most of these tests is an <svg> that says overflow: visible, so that its parts are painted where they move.
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
function projectWith({ move, css = "", body = "", svg = 'style="overflow:visible"', html = false, extra = {} }) {
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
  const { p, proof } = projectWith({ move: "translateX(82px)" }); // the svg lets the part out (overflow: visible), and an svg's content never widens the page: scrollWidth stays 360
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
    + "@media (prefers-reduced-motion: reduce){#letter-a{animation:none}}", body: drawing('id="mark" style="overflow:visible"') });
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

// ---- a box counts where it is painted
// The mark of HTML boxes again (the disc is an svg, the part a div, 50 x 40 px at x 250..300), with a wrapper of its own between the mark and the part: `wrap` is the
// wrapper's style, `part` the part's. The wrapper is positioned (it is the part's containing block, so its overflow clips the part) unless its style says otherwise.
const DISC = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="320" height="90" style="display:block"><circle cx="40" cy="45" r="30" fill="#0d1b2d"/></svg>';
const wrapped = (wrap = "", part = "", positioned = true) => `<div id="mark" style="position:relative;width:320px;height:90px">${DISC}<div id="wrap" style="${positioned ? "position:absolute;left:0;top:0;" : ""}width:320px;height:90px;${wrap}">`
  + `<div id="letter-a" style="position:absolute;left:250px;top:10px;width:50px;height:40px;background:#007d71;${part}"></div></div></div>`;
function markProject({ mark, css = "", move = "translateX(82px)" }) {
  const p = motionProject();
  fs.writeFileSync(path.join(p, "assets/logo/edge.svg"), DRAWING());
  writePage(p, "edge", { css: `#mark{display:block}#letter-a{animation:go 400ms linear 1 both}@keyframes go{from{transform:none}50%{transform:${move}}to{transform:none}}@media (prefers-reduced-motion: reduce){#letter-a{animation:none!important}}${css}`, body: mark });
  return { p, proof: writeProof(p, [pageCase({ page: "motion/edge.html", static: "assets/logo/edge.svg", widths: [360] })]) };
}

test("what an ancestor clips is not painted: a part the wrapper's overflow or contain: paint cuts off does not cross the edge, the same part without it does", (t) => {
  if (needSetup(t)) return;
  // at 50% the part is 82 px to the right: its box ends at 382, 22 px past a 360 px screen; the wrapper is 320 px wide, so it paints nothing past 320
  const open = markProject({ mark: wrapped() });
  assert.equal(run(open.p, open.proof).status, 1);                                  // the control: nothing clips it, and it crosses
  assert.match(row(open.p, open.proof, 360).detail, /div#letter-a 22 px past the right edge at 360 px/);
  for (const wrap of ["overflow-x:clip", "overflow:hidden", "contain:paint", "overflow-x:hidden", "contain:strict", "overflow:auto"]) {
    const { p, proof } = markProject({ mark: wrapped(wrap) });
    const r = run(p, proof);
    assert.equal(r.status, 0, `${wrap}: ${r.stdout}`);
    assert.equal(row(p, proof, 360).status, "pass", wrap);
    assert.match(row(p, proof, 360).detail, /33 sample point\(s\) over 400 ms: no part of the mark \(5 box\(es\)\) past the left, top or right edge/, wrap);   // the clipped part is still a box that was looked at
  }
  // a clip cuts the axis it clips: overflow-y does not hold back a part that leaves to the right, and overflow-x does not hold back one that leaves at the top
  const y = markProject({ mark: wrapped("overflow-y:clip") });
  assert.equal(run(y.p, y.proof).status, 1);
  const top = markProject({ mark: wrapped("overflow-x:clip"), move: "translateY(-32px)" });
  assert.equal(run(top.p, top.proof).status, 1);
  assert.match(row(top.p, top.proof, 360).detail, /div#letter-a 22 px past the top edge at 360 px/);
  const topClipped = markProject({ mark: wrapped("overflow-y:clip"), move: "translateY(-32px)" });
  assert.equal(run(topClipped.p, topClipped.proof).status, 0);
});

test("an overflow only clips what it contains: a positioned part whose containing block lies above the wrapper is not cut by it", (t) => {
  if (needSetup(t)) return;
  // the wrapper is not positioned, so the part's containing block is the mark: the wrapper's overflow: hidden does not reach it
  const { p, proof } = markProject({ mark: wrapped("overflow:hidden", "", false) });
  assert.equal(run(p, proof).status, 1);
  assert.match(row(p, proof, 360).detail, /div#letter-a 22 px past the right edge at 360 px/);
});

test("a part is not past the edge while it is transparent: its own opacity or an ancestor's, at the one moment it is out there", (t) => {
  if (needSetup(t)) return;
  // an <svg> mark (its content never widens the page: an invisible HTML box still would). At 0 ms the part is 82 px to the right, past the edge, at opacity 0;
  // from 1 % on it is in place and opaque
  const seen = (from) => `@keyframes hello{0%{transform:translateX(82px);opacity:${from}}1%{transform:none;opacity:1}100%{transform:none;opacity:1}}#letter-a{animation:hello 400ms linear 1 both}`;
  const own = projectWith({ move: "none", css: seen(0), extra: { widths: [360] } });
  const r = run(own.p, own.proof);
  assert.equal(r.status, 0, r.stdout);
  assert.equal(row(own.p, own.proof, 360).status, "pass");
  // the control: the same move with the part a little opaque crosses at 0 ms
  const faint = projectWith({ move: "none", css: seen(0.05), extra: { widths: [360] } });
  assert.equal(run(faint.p, faint.proof).status, 1);
  assert.match(row(faint.p, faint.proof, 360).detail, /^at 0% \(0 ms\): g#letter-a 22 px past the right edge at 360 px/);
  // an ancestor at opacity 0 at that moment (the product over its ancestors is 0) hides the part as well
  const veil = (from) => `#wrap{animation:veil 400ms linear 1 both}@keyframes veil{0%{opacity:${from}}1%{opacity:1}100%{opacity:1}}`;
  const wrapOf = (css) => markProject({ mark: `<svg xmlns="http://www.w3.org/2000/svg" id="mark" style="overflow:visible" viewBox="0 0 320 90" width="320" height="90"><circle cx="40" cy="45" r="30" fill="#0d1b2d"/>`
    + '<g id="wrap"><g id="letter-a"><rect x="250" y="10" width="50" height="40" fill="#007d71"/></g></g></svg>', css: css + "@media (prefers-reduced-motion: reduce){#wrap{animation:none!important}}" });
  const parent = wrapOf(veil(0) + "@keyframes go{0%{transform:translateX(82px)}1%{transform:none}100%{transform:none}}#letter-a{animation:go 400ms linear 1 both}");
  assert.equal(run(parent.p, parent.proof).status, 0);
  const opaque = wrapOf(veil(1) + "@keyframes go{0%{transform:translateX(82px)}1%{transform:none}100%{transform:none}}#letter-a{animation:go 400ms linear 1 both}");
  assert.equal(run(opaque.p, opaque.proof).status, 1);
  // the project's case: a part scaled up and thrown far to the left inside a wrapper that clips that axis, transparent at 0 ms by a backwards fill, was reported past
  // the left edge on six rows while the page never got wider
  const grow = "@keyframes grow{from{transform:translateX(-340px) scaleX(2.2);opacity:0}to{transform:none;opacity:1}}#letter-a{animation:grow 400ms linear 1 backwards}";
  const big = markProject({ mark: wrapped("overflow-x:clip"), move: "none", css: grow });
  assert.equal(run(big.p, big.proof).status, 0, "painted nowhere past the edge: the wrapper clips it");
  const loose = markProject({ mark: wrapped(), move: "none", css: grow });
  assert.equal(run(loose.p, loose.proof).status, 1);              // the control: without the wrapper's clip it is painted past the edge once it is opaque
  assert.match(row(loose.p, loose.proof, 360).detail, /div#letter-a \d+(\.\d)? px past the left edge at 360 px/);
});

test("a part is not past the edge while it is visibility: hidden", (t) => {
  if (needSetup(t)) return;
  const hidden = (v) => `@keyframes hello{0%{transform:translateX(82px);visibility:${v}}1%{transform:none;visibility:visible}100%{transform:none;visibility:visible}}#letter-a{animation:hello 400ms linear 1 both}`;
  const { p, proof } = projectWith({ move: "none", css: hidden("hidden"), extra: { widths: [360] } });
  const r = run(p, proof);
  assert.equal(r.status, 0, r.stdout);
  const shown = projectWith({ move: "none", css: hidden("visible"), extra: { widths: [360] } });
  assert.equal(run(shown.p, shown.proof).status, 1);
  // visibility is inherited: a wrapper that is hidden at that moment hides the part, unless the part says visible
  const wrap = (part) => markProject({ mark: `<svg xmlns="http://www.w3.org/2000/svg" id="mark" style="overflow:visible" viewBox="0 0 320 90" width="320" height="90"><circle cx="40" cy="45" r="30" fill="#0d1b2d"/>`
    + `<g id="wrap"><g id="letter-a" style="${part}"><rect x="250" y="10" width="50" height="40" fill="#007d71"/></g></g></svg>`,
    css: "@keyframes go{0%{transform:translateX(82px)}1%{transform:none}100%{transform:none}}#letter-a{animation:go 400ms linear 1 both}#wrap{animation:veil 400ms linear 1 both}@keyframes veil{0%{visibility:hidden}1%{visibility:visible}100%{visibility:visible}}"
      + "@media (prefers-reduced-motion: reduce){#wrap{animation:none!important}}" });
  const inherits = wrap("");
  assert.equal(run(inherits.p, inherits.proof).status, 0);
  const back = wrap("visibility:visible");
  assert.equal(run(back.p, back.proof).status, 1);
});

test("an <svg> clips what leaves its viewport: its own, the mark element's and a nested one's, unless it says overflow: visible", (t) => {
  if (needSetup(t)) return;
  // the mark is the <svg> itself and keeps the default overflow: the part moves out of the viewport and paints nothing there
  const own = projectWith({ move: "translateX(82px)", svg: "" });
  const r = run(own.p, own.proof);
  assert.equal(r.status, 0, r.stdout);
  assert.equal(row(own.p, own.proof, 360).status, "pass");
  assert.match(row(own.p, own.proof, 360).detail, /33 sample point\(s\) over 400 ms: no part of the mark \(4 box\(es\)\) past the left, top or right edge/);
  const open = projectWith({ move: "translateX(82px)" });
  assert.equal(run(open.p, open.proof).status, 1);               // overflow: visible lets it out
  // an <svg> inside an HTML mark
  const inner = (style) => `<div id="mark" style="position:relative;width:320px;height:90px"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="320" height="90" style="display:block;${style}">`
    + '<circle cx="40" cy="45" r="30" fill="#0d1b2d"/><g id="letter-a"><rect x="250" y="10" width="50" height="40" fill="#007d71"/></g></svg></div>';
  const clipped = markProject({ mark: inner("") });
  assert.equal(run(clipped.p, clipped.proof).status, 0);
  const free = markProject({ mark: inner("overflow:visible") });
  assert.equal(run(free.p, free.proof).status, 1);
  assert.match(row(free.p, free.proof, 360).detail, /g#letter-a 22 px past the right edge at 360 px/);
  // an <svg> nested in the mark's <svg> has a viewport of its own (x, y, width and height)
  const nested = (style) => `<svg xmlns="http://www.w3.org/2000/svg" id="mark" style="overflow:visible" viewBox="0 0 320 90" width="320" height="90"><svg x="0" y="0" width="320" height="90" viewBox="0 0 320 90" style="${style}">`
    + '<circle cx="40" cy="45" r="30" fill="#0d1b2d"/><g id="letter-a"><rect x="250" y="10" width="50" height="40" fill="#007d71"/></g></svg></svg>';
  const nestedClipped = markProject({ mark: nested("") });
  assert.equal(run(nestedClipped.p, nestedClipped.proof).status, 0);
  const nestedFree = markProject({ mark: nested("overflow:visible") });
  assert.equal(run(nestedFree.p, nestedFree.proof).status, 1);
});
