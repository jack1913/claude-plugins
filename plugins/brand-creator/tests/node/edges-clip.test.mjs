// shot --motion's edges, continued from edges.test.mjs: a box counts where it is painted. Split from edges.test.mjs so that node --test runs them side
// by side; the shared mark is in _edges.mjs.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, motionProject, run, byId, failing, writeProof, writePage, pageCase } from "./_motion.mjs";
import { DRAWING, HTML_MARK, projectWith, row } from "./_edges.mjs";

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
