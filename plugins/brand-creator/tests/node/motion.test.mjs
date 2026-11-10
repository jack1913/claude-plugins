// shot --motion: named states at dsf 1 and 2 against the static SVG (with a control pair that must differ), and a page pass
// under normal and emulated prefers-reduced-motion (no running animation, no rAF loop, no motion listeners, CLS 0, rest == static).
// Every negative test breaks a scratch copy of the Acme demo and proves the mutation applied (mutateText throws otherwise).
// The report is one per proof file (assets/_checks/motion/<slug>-<hash6>.json); the page is sampled by seeking (seek.test.mjs), at phone widths
// (edges.test.mjs) and compared in place (inplace.test.mjs); the helpers are in _motion.mjs.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, mutateText, motionProject, run, rep, byId, failing, writeProof, writePage, demo, PAGE, reportFile, DATA, ROOT, bc } from "./_motion.mjs";

test("the Acme proof passes: states at dsf 1 and 2, a control pair, and both page passes", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const r = run(p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const doc = rep(p);
  assert.match(doc.tool, /^motion\/proof-[0-9a-f]{6}$/); assert.equal(doc.status, "pass"); assert.equal(doc.proof, "motion/proof.json");
  const ids = doc.results.map((x) => x.id);
  for (const dsf of ["1x", "2x"]) for (const s of [`file=rest`, `rest=static`, `control:rest!=pressed`]) assert.ok(ids.includes(`motion:dot-press:${dsf}:${s}`), `${dsf} ${s}`);
  for (const s of ["control", "sampling", "loops", "settled", "cls:normal", "normal:rest=static", "whole-pixel", "edges:360", "edges:390", "reduced:animations", "reduced:raf", "reduced:listeners", "cls:reduced", "reduced:rest=static"]) assert.ok(ids.includes(`motion:demo-page:${s}`), s);
  assert.equal(doc.results.length, 20);
  const ctl = byId(p)["motion:dot-press:2x:control:rest!=pressed"];
  assert.match(ctl.detail, /differ in \d+ px/); // the control saw a real difference, so the equality checks above are not vacuous
  const rest = byId(p)["motion:demo-page:normal:rest=static"];
  assert.equal(rest.px_differ, 0); assert.equal(rest.tolerance, 0); // in the page itself, exact: the default tolerance is 0
  assert.equal(byId(p)["motion:demo-page:whole-pixel"].status, "info"); // the Acme mark is a vector mark: smooth easing allowed
});

test("a control pair that does not differ fails (an equality proof that cannot see a difference proves nothing)", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(path.join(p, "assets/logo/mark-animated.svg"), 'cy="43"', 'cy="41"'); // the pressed state now equals rest
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:dot-press:1x:control:rest!=pressed"), failing(p).join());
  assert.match(byId(p)["motion:dot-press:1x:control:rest!=pressed"].detail + byId(p)["motion:dot-press:1x:control:rest!=pressed"].label, /differ|control/i);
});

test("a case without any control pair fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const proof = JSON.parse(fs.readFileSync(path.join(p, "motion/proof.json"), "utf8"));
  const c = proof.cases[0]; delete c.controls;
  c.rest = "rest";
  const svg = path.join(p, "assets/logo/mark-animated.svg");
  mutateText(svg, '    <g data-state="pressed" display="none"><circle cx="32" cy="43" r="9" fill="#007d71"/></g>\n', "");
  fs.writeFileSync(path.join(p, "motion/p.json"), JSON.stringify({ schema: 1, cases: [c] }));
  const r = run(p, "motion/p.json");
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p, "motion/p.json").some((id) => id.endsWith(":control")), failing(p, "motion/p.json").join());
});

test("a rest frame that differs from the static SVG fails at both pixel ratios", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(path.join(p, "assets/logo/mark.svg"), 'r="9"', 'r="10"'); // the still changed, the animated file did not
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  const bad = failing(p);
  assert.ok(bad.includes("motion:dot-press:1x:rest=static") && bad.includes("motion:dot-press:2x:rest=static"), bad.join());
});

test("a state called for as the rest frame must exist", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const name = writeProof(p, [{ name: "x", type: "states", file: "assets/logo/mark-animated.svg", static: "assets/logo/mark.svg", rest: "idle", controls: [["rest", "pressed"]] }]);
  const r = run(p, name);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p, name).some((id) => id.endsWith(":states")), failing(p, name).join());
  assert.match(rep(p, name).results.find((x) => x.status === "fail").detail, /no state called idle/);
});

test("an animation that loops forever fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "steps(2, end) 1 both", "steps(2, end) infinite both");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:demo-page:loops"), failing(p).join());
});

// the Acme mark as pixel art: shape-rendering="crispEdges" on the root of the still, of the animated file and of the page's own copy of it
function pixelMark(p) {
  for (const f of ["mark.svg", "mark-animated.svg"]) mutateText(path.join(p, "assets/logo", f), "<svg ", '<svg shape-rendering="crispEdges" ');
  mutateText(demo(p), '<svg id="mark"', '<svg id="mark" shape-rendering="crispEdges"');
}

test("whole pixels only: a smooth in-between position fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  pixelMark(p);
  mutateText(demo(p), "steps(2, end) 1 both", "linear 1 both");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:demo-page:whole-pixel"), failing(p).join());
  const row = byId(p)["motion:demo-page:whole-pixel"];
  assert.match(row.detail, /a pixel mark \(the static SVG says shape-rendering="crispEdges"\): press at \d+(\.\d)?% \(\d+(\.\d+)? ms\): translate\(0\.00px, 0\.\d\dpx\)/);
});

test("a pose off the pixel grid that lasts a few milliseconds is found at its keyframe, not by chance", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  pixelMark(p);
  // steps(1, end) holds the first value of each interval until the next keyframe: 0.5px from 47% (150.4 ms) to 50% (160 ms) and nowhere else. That lies between
  // two of the even sample points (every 10 ms: 150 and 160), so only the point taken at the keyframe at 48% (153.6 ms) sees it
  mutateText(demo(p), "@keyframes press { 0% { transform: translateY(0); } 50% { transform: translateY(2px); } 100% { transform: translateY(0); } }",
    "@keyframes press { 0% { transform: translateY(0); } 47% { transform: translateY(0.5px); } 48% { transform: translateY(0.5px); } 50% { transform: translateY(0); } 100% { transform: translateY(0); } }");
  mutateText(demo(p), "steps(2, end) 1 both", "steps(1, end) 1 both");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.deepEqual(failing(p), ["motion:demo-page:whole-pixel"]);
  const detail = byId(p)["motion:demo-page:whole-pixel"].detail;
  assert.match(detail, /press at \d+(\.\d)?% \(\d+(\.\d+)? ms\): translate\(0\.00px, 0\.50px\)/);
  const ms = Number(/\((\d+(?:\.\d+)?) ms\)/.exec(detail)[1]);
  assert.ok(ms > 150 && ms < 160, `found at ${ms} ms`); // inside the 10 ms gap between two even points
});

test("whole pixels only: motion through the translate property is read as well as through transform", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  pixelMark(p);
  mutateText(demo(p), "@keyframes press { 0% { transform: translateY(0); } 50% { transform: translateY(2px); } 100% { transform: translateY(0); } }",
    "@keyframes press { 0% { translate: 0 0; } 50% { translate: 0 0.5px; } 100% { translate: 0 0; } }");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.deepEqual(failing(p), ["motion:demo-page:whole-pixel"]);
  assert.match(byId(p)["motion:demo-page:whole-pixel"].detail, /press at \d+(\.\d)?% \(\d+(\.\d+)? ms\): translate\(0\.00px, 0\.(25|50)px\)/);
});

test("a pose held by a step between every sample point is found at the middle of the step", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  pixelMark(p);
  // steps(32) over each half of 640 ms: the dot holds k/2 px for 10 ms at a time, half a pixel on every odd step. The even points and the dot's own
  // points (every 20 ms) and its keyframes (0, 320, 640) all land on even steps; only the middle of each step (5, 15, 25 ... ms) finds a half pixel
  mutateText(demo(p), "@keyframes press { 0% { transform: translateY(0); } 50% { transform: translateY(2px); } 100% { transform: translateY(0); } }",
    "@keyframes press { 0% { transform: translateY(0); } 50% { transform: translateY(16px); } 100% { transform: translateY(0); } }");
  mutateText(demo(p), "press 320ms steps(2, end) 1 both", "press 640ms steps(32, end) 1 both");
  assert.equal(run(p).status, 1);
  assert.deepEqual(failing(p), ["motion:demo-page:whole-pixel"]);
  const detail = byId(p)["motion:demo-page:whole-pixel"].detail;
  assert.match(detail, /press at \d+(\.\d)?% \((\d+)5 ms\): translate\(0\.00px, \d+\.50px\)/);
  assert.match(byId(p)["motion:demo-page:sampling"].detail, /, \d+ where an easing turns back or holds a step/);
});

test("a vector mark may ease smoothly: its whole-pixel row is info", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "steps(2, end) 1 both", "linear 1 both"); // the same smooth motion as above, on the Acme vector mark
  const r = run(p);
  assert.equal(r.status, 0, r.stdout);
  const row = byId(p)["motion:demo-page:whole-pixel"];
  assert.equal(row.status, "info");
  assert.match(row.detail, /a vector mark: smooth easing allowed/);
});

test("the case's pixel key overrides what the still says", (t) => {
  if (needSetup(t)) return;
  const on = motionProject(); // a vector mark held to whole pixels on the case's say-so
  mutateText(demo(on), "steps(2, end) 1 both", "linear 1 both");
  mutateText(path.join(on, "motion/proof.json"), '"settle_ms": 700', '"settle_ms": 700, "pixel": true');
  assert.equal(run(on).status, 1);
  assert.ok(failing(on).includes("motion:demo-page:whole-pixel"), failing(on).join());
  assert.match(byId(on)["motion:demo-page:whole-pixel"].detail, /the case says "pixel": true/);
  const off = motionProject(); // pixel art let off the rule the same way
  pixelMark(off);
  mutateText(demo(off), "steps(2, end) 1 both", "linear 1 both");
  mutateText(path.join(off, "motion/proof.json"), '"settle_ms": 700', '"settle_ms": 700, "pixel": false');
  assert.equal(run(off).status, 0);
  assert.equal(byId(off)["motion:demo-page:whole-pixel"].status, "info");
  assert.match(byId(off)["motion:demo-page:whole-pixel"].detail, /the case says "pixel": false/);
});
