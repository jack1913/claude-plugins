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

test("layout shift is measured and must be zero", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "<main>", `<script>setTimeout(()=>{const d=document.createElement("div");d.style.height="120px";d.textContent="late banner";document.body.insertBefore(d,document.querySelector("main"));},150)</script>\n<main>`);
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:demo-page:cls:normal"), failing(p).join());
  const row = byId(p)["motion:demo-page:cls:normal"];
  assert.match(row.detail, /CLS 0\.\d+/); assert.ok(row.detail.indexOf("CLS 0.0000") !== 0);
});

test("a page that ignores prefers-reduced-motion fails the reduced pass", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "@media (prefers-reduced-motion: reduce) { #dot { animation: none; } }", "");
  mutateText(demo(p), "steps(2, end) 1 both", "steps(2, end) 1 both; animation-duration: 3000ms");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  const bad = failing(p);
  assert.ok(bad.includes("motion:demo-page:reduced:animations"), bad.join());
  assert.ok(!bad.includes("motion:demo-page:settled"), bad.join()); // the normal pass seeks to the end of the 3 s animation: it is not waited for
  assert.match(byId(p)["motion:demo-page:reduced:animations"].detail, /running: press/);
});

test("a motion listener fails the reduced pass (script-registered and inline)", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "<main>", "<script>window.addEventListener('pointermove', () => {})</script>\n<main>");
  assert.equal(run(p).status, 1);
  assert.match(byId(p)["motion:demo-page:reduced:listeners"].detail, /pointermove on window/);
  const q = motionProject();
  mutateText(demo(q), "<body>", '<body onmousemove="void 0">');
  assert.equal(run(q).status, 1);
  assert.ok(failing(q).includes("motion:demo-page:reduced:listeners"), failing(q).join());
});

test("a motion listener registered a moment after load still fails the reduced pass: the page is watched for settle_ms", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "<main>", "<script>setTimeout(function () { window.addEventListener('pointermove', function () {}); }, 350)</script>\n<main>");
  assert.equal(run(p).status, 1);
  assert.ok(failing(p).includes("motion:demo-page:reduced:listeners"), failing(p).join());
  assert.match(byId(p)["motion:demo-page:reduced:listeners"].detail, /pointermove on window/);
});

test("a requestAnimationFrame loop fails the reduced pass", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "<main>", "<script>(function t(){requestAnimationFrame(t)})()</script>\n<main>");
  assert.equal(run(p).status, 1);
  assert.ok(failing(p).includes("motion:demo-page:reduced:raf"), failing(p).join());
});

test("a page that never moves fails the control: the reduced result would be vacuous", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "animation: press 320ms steps(2, end) 1 both;", "");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:demo-page:control"), failing(p).join());
  assert.match(byId(p)["motion:demo-page:control"].detail, /would prove nothing/);
});

test("the demo page is network-free: a remote request is refused and fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "<main>", '<img src="https://example.invalid/x.png" width=1 height=1>\n<main>');
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).some((id) => id.startsWith("motion:demo-page")), failing(p).join());
});

test("proof files are validated before any browser starts", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  let name = writeProof(p, [{ name: "a", type: "gif" }]);
  assert.equal(run(p, name).status, 2);
  name = writeProof(p, [PAGE, PAGE]);
  let r = run(p, name);
  assert.equal(r.status, 2); assert.match(r.stderr, /unique name/);
  fs.writeFileSync(path.join(p, "motion/bad.json"), "{nope");
  assert.equal(run(p, "motion/bad.json").status, 2);
  fs.writeFileSync(path.join(p, "motion/old.json"), JSON.stringify({ schema: 2, cases: [] }));
  assert.equal(run(p, "motion/old.json").status, 2);
  name = writeProof(p, [{ ...PAGE, selector: "#nothing-here" }]);
  r = run(p, name);
  assert.equal(r.status, 2); assert.match(r.stderr, /matches nothing/);
  name = writeProof(p, [{ ...PAGE, static: "assets/logo/none.svg" }]);
  assert.equal(run(p, name).status, 2);
  name = writeProof(p, [{ ...PAGE, page: "../escape.html" }]);
  assert.equal(run(p, name).status, 2);
  for (const [key, value, say] of [["widths", [100], /"widths"/], ["widths", [360, 360], /"widths"/], ["widths", "360", /"widths"/], ["pixel", "yes", /"pixel"/], ["tolerance", -1, /"tolerance"/], ["settle_ms", "soon", /"settle_ms"/]]) {
    name = writeProof(p, [{ ...PAGE, [key]: value }]);
    r = run(p, name);
    assert.equal(r.status, 2, `${key} ${JSON.stringify(value)}: ${r.stdout}`); assert.match(r.stderr, say);
  }
});

test("one report per proof file, named after the proof; another proof's run never touches it", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const states = JSON.parse(fs.readFileSync(path.join(p, "motion/proof.json"), "utf8")).cases[0]; // a proof of the one fast case, in two places
  writeProof(p, [states], "motion/proof.json");
  assert.equal(run(p).status, 0);
  const first = reportFile(p);
  assert.match(path.relative(p, first), /^assets\/_checks\/motion\/proof-[0-9a-f]{6}\.json$/);
  assert.ok(!fs.existsSync(path.join(p, "assets/_checks/motion.json")), "nothing writes assets/_checks/motion.json any more");
  const kept = fs.readFileSync(first), when = fs.statSync(first).mtimeMs;
  fs.mkdirSync(path.join(p, "rounds/r2"), { recursive: true });
  writeProof(p, [states], "rounds/r2/proof.json"); // the same file name in another folder: another report
  assert.equal(run(p, "rounds/r2/proof.json").status, 0);
  const second = reportFile(p, "rounds/r2/proof.json");
  assert.notEqual(second, first);
  assert.deepEqual(fs.readdirSync(path.join(p, "assets/_checks/motion")).sort(), [path.basename(first), path.basename(second)].sort());
  assert.equal(rep(p, "rounds/r2/proof.json").proof, "rounds/r2/proof.json");
  assert.equal(rep(p).proof, "motion/proof.json");
  assert.ok(Buffer.compare(fs.readFileSync(first), kept) === 0 && fs.statSync(first).mtimeMs === when, "the report of the first proof was touched by the run of the second");
  assert.ok(!fs.existsSync(path.join(p, "assets/_checks/motion.json")));
});

test("a proof typed in another letter case is the same file: one report, named as the disk spells it", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const states = JSON.parse(fs.readFileSync(path.join(p, "motion/proof.json"), "utf8")).cases[0];
  writeProof(p, [states], "motion/proof.json");
  const r = run(p, "MOTION/PROOF.JSON");
  if (!fs.existsSync(path.join(p, "MOTION/PROOF.JSON"))) { // a file system that tells letter cases apart (Linux): another file, which does not exist
    assert.equal(r.status, 2, r.stdout + r.stderr);
    assert.match(r.stderr, /motion proof not found: MOTION\/PROOF\.JSON/);
    assert.ok(!fs.existsSync(path.join(p, "assets/_checks/motion")), "no report for a proof that is not there");
    return;
  }
  assert.equal(r.status, 0, r.stdout + r.stderr); // macOS: the same file
  assert.deepEqual(fs.readdirSync(path.join(p, "assets/_checks/motion")), [path.basename(reportFile(p))]);
  assert.equal(rep(p).proof, "motion/proof.json");
});

test("a case name never takes the pictures of a failing comparison out of the scratch folder", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(path.join(p, "motion/proof.json"), '"name": "demo-page"', '"name": "../../../escape"'); // three folders up from scratch/<project>/motion/
  mutateText(path.join(p, "assets/logo/mark.svg"), "<svg ", '<svg opacity="0.5" '); // the still differs from the page's rest frame
  assert.equal(run(p).status, 1);
  const dir = /; both images: (.+)$/.exec(byId(p)["motion:../../../escape:normal:rest=static"].detail)?.[1];
  assert.ok(dir, "the pictures were kept");
  assert.equal(path.basename(dir), "escape");
  assert.ok(path.resolve(dir).startsWith(path.join(fs.realpathSync(DATA), "scratch") + path.sep), `inside the data folder's scratch area: ${dir}`);
});

// ---- component cases: the states of one component of a page (hover, press, keyboard focus). The pages are written whole here, so none of these breaks a file.
// The starter's motion tokens built into the project: motion.quick 160 ms, base 320, slow 640, stagger 120; easing.standard, enter, exit.
function withMotionTokens(p) {
  for (const f of fs.readdirSync(path.join(ROOT, "templates/tokens"))) fs.copyFileSync(path.join(ROOT, "templates/tokens", f), path.join(p, "tokens", f));
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
}
/** A page of the project with one row: a button (#b) and a note after it. A page whose css uses the tokens (var(--...)) links the built tokens.css. */
function buttonPage(p, name, { css = "", button = '<button class="btn" id="b">Buy</button>', after = '<span class="after">after</span>' } = {}) {
  return writePage(p, name, {
    head: css.includes("var(--") ? '<link rel="stylesheet" href="../assets/tokens/tokens.css">' : "",
    css: `.row{display:flex;align-items:center;gap:12px;padding:20px}.btn{font:16px sans-serif;padding:8px 16px;border:0;background:#0d1b2d;color:#fff}.after{font:14px sans-serif}${css}`,
    body: `<div class="row">${button}${after}</div>`,
  });
}
const component = (page, extra = {}) => ({ name: "btn", type: "component", page, selector: "#b", rule: "G4: a button answers a hover and a press in motion tokens, and does not move the page", ...extra });

test("a button whose padding grows on hover fails the shift row", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const page = buttonPage(p, "grow", { css: ".btn{transition:padding 160ms ease}.btn:hover{padding:12px 24px}" });
  const name = writeProof(p, [component(page, { states: ["hover"] })]);
  const r = run(p, name);
  assert.equal(r.status, 1, r.stdout);
  const bad = failing(p, name);
  assert.ok(bad.includes("motion:btn:shift:hover:390") && bad.includes("motion:btn:shift:hover:1440"), bad.join());
  const row = byId(p, name)["motion:btn:shift:hover:1440"];
  assert.match(row.detail, /button#b grew wider by 16 px \((entering|leaving), at \d+(\.\d)?% = \d+(\.\d+)? ms\)/); // the largest change, where in the motion it was found
  assert.match(row.detail, /span\.after moved right by 16 px/); // what follows it moved
  assert.match(row.detail, /animates a layout property: .*padding-left \(transition on button#b\)/);
  assert.ok(row.sample_points[0] > 1 && row.length_ms[0] === 160, JSON.stringify([row.sample_points, row.length_ms])); // stepped through the transition, not looked at once
  assert.equal(rep(p, name).cases[0].rule, component(page).rule); // the G4 line the case proves is in the report
});

test("a press that scales with a token duration passes", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const page = buttonPage(p, "press", {
    css: ".btn{transition:transform var(--motion-quick) var(--easing-standard),background-color var(--motion-quick) var(--easing-standard)}"
      + ".btn:hover{background:#007d71;transform:translateY(-2px)}.btn:active{transform:scale(0.97)}@media (prefers-reduced-motion:reduce){.btn{transition:none}}",
  });
  const name = writeProof(p, [component(page)]);
  const r = run(p, name);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const doc = rep(p, name), rows = byId(p, name);
  assert.equal(doc.status, "pass");
  const ids = ["hover", "active"].flatMap((s) => [`shift:${s}:390`, `shift:${s}:1440`, `tokens:${s}`, `reduced:${s}`, `rest:${s}`]).map((x) => `motion:btn:${x}`);
  assert.deepEqual(doc.results.map((x) => x.id), ids);
  assert.ok(doc.results.every((x) => x.status === "pass"), JSON.stringify(doc.results.map((x) => [x.id, x.status])));
  assert.match(rows["motion:btn:tokens:active"].detail, /motion\.quick \(160 ms\)/);
  assert.match(rows["motion:btn:tokens:active"].detail, /easing\.standard/);
  assert.ok(rows["motion:btn:shift:active:390"].sample_points.every((n) => n > 1), "the press was stepped through"); // a scale moves the drawn box and not the layout box: nothing shifted
  assert.match(rows["motion:btn:reduced:active"].detail, /no transition or animation on entering or leaving :active \([1-9]\d* at normal motion\)/); // there was motion to turn off
});

test("a hover transition of 200 ms that is not a token fails the tokens row", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const page = buttonPage(p, "off-token", {
    css: ".btn{transition:background-color 200ms var(--easing-standard)}.btn:hover{background:#007d71}@media (prefers-reduced-motion:reduce){.btn{transition:none}}",
  });
  const name = writeProof(p, [component(page, { states: ["hover"] })]);
  assert.equal(run(p, name).status, 1);
  assert.deepEqual(failing(p, name), ["motion:btn:tokens:hover"]); // the box does not move, it is still at rest, and nothing runs under reduced motion
  assert.match(byId(p, name)["motion:btn:tokens:hover"].detail, /transition of background-color on button#b lasts 200 ms, which is no motion duration token \(.*motion\.quick 160 ms/);
  assert.doesNotMatch(byId(p, name)["motion:btn:tokens:hover"].detail, /easing/); // its curve is the token's
});

test("a component that still animates under reduced motion fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const page = buttonPage(p, "no-reduce", { css: ".btn{transition:background-color var(--motion-quick) var(--easing-standard)}.btn:hover{background:#007d71}" });
  const name = writeProof(p, [component(page, { states: ["hover"] })]);
  assert.equal(run(p, name).status, 1);
  assert.deepEqual(failing(p, name), ["motion:btn:reduced:hover"]);
  assert.match(byId(p, name)["motion:btn:reduced:hover"].detail, /prefers-reduced-motion: reduce emulated; the state change starts transition of background-color on button#b \(390 px\)/);
});

test("a component case without its rule is a usage error", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const page = buttonPage(p, "usage");
  const ok = component(page);
  const { rule, ...noRule } = ok;
  let name = writeProof(p, [noRule]);
  let r = run(p, name);
  assert.equal(r.status, 2, r.stdout + r.stderr); assert.match(r.stderr, /a component case needs "rule" as a non-empty string \(the G4 line it proves\)/);
  assert.ok(!fs.existsSync(reportFile(p, name)), "no browser was started, so no report was written");
  for (const [extra, say] of [[{ rule: "  " }, /"rule"/], [{ page: undefined }, /"page"/], [{ selector: "" }, /"selector"/], [{ states: ["tap"] }, /"states"/], [{ states: [] }, /"states"/],
    [{ states: ["hover", "hover"] }, /"states"/], [{ widths: [100] }, /"widths"/], [{ widths: [390, 390] }, /"widths"/], [{ settle_ms: "soon" }, /"settle_ms"/], [{ state: ["hover"] }, /unknown key "state"/]]) {
    name = writeProof(p, [{ ...ok, ...extra }]);
    r = run(p, name);
    assert.equal(r.status, 2, `${JSON.stringify(extra)}: ${r.stdout}${r.stderr}`); assert.match(r.stderr, say);
  }
  name = writeProof(p, [{ ...ok, selector: "#nothing-here" }]);
  r = run(p, name);
  assert.equal(r.status, 2); assert.match(r.stderr, /matches nothing/);
});

test("a focus ring drawn with outline moves nothing; a border that grows with the focus moves the element after it", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const ring = buttonPage(p, "ring", { css: ".btn{transition:outline-color var(--motion-quick) var(--easing-standard)}.btn:focus-visible{outline:3px solid #007d71;outline-offset:2px}@media (prefers-reduced-motion:reduce){.btn{transition:none}}" });
  let name = writeProof(p, [component(ring, { states: ["focus-visible"] })], "motion/ring.json");
  let r = run(p, name);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(byId(p, name)["motion:btn:tokens:focus-visible"].detail, /motion\.quick \(160 ms\)/); // the focus was a keyboard focus: the ring's transition ran
  const border = buttonPage(p, "border", { css: ".btn{border:2px solid transparent}.btn:focus-visible{border-width:4px}" });
  name = writeProof(p, [component(border, { states: ["focus-visible"] })], "motion/border.json");
  r = run(p, name);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.deepEqual(failing(p, name), ["motion:btn:shift:focus-visible:390", "motion:btn:shift:focus-visible:1440"]);
  const row = byId(p, name)["motion:btn:shift:focus-visible:390"];
  assert.match(row.detail, /button#b grew wider by 4 px/); assert.match(row.detail, /span\.after moved right by 4 px/); // the element, and what follows it
});

test("a state the page does not undo when the pointer leaves fails the rest row", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const page = buttonPage(p, "sticky", { css: ".btn:hover{background:#007d71}", after: "<script>document.getElementById('b').addEventListener('mouseenter', function () { this.style.width = '220px'; });</script>" });
  const name = writeProof(p, [component(page, { states: ["hover"], widths: [1440] })]);
  assert.equal(run(p, name).status, 1);
  assert.ok(failing(p, name).includes("motion:btn:rest:hover"), failing(p, name).join());
  assert.match(byId(p, name)["motion:btn:rest:hover"].detail, /after leaving :hover: button#b grew wider by \d+(\.\d)? px at 1440 px/);
});

test("a press is let go over the element without running its click handler or following its link", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const page = buttonPage(p, "link", {
    css: ".btn{display:inline-block;background:#ccc;color:#000;text-decoration:none;transition:transform var(--motion-quick) var(--easing-standard)}.btn:active{transform:scale(0.95)}@media (prefers-reduced-motion:reduce){.btn{transition:none}}",
    button: '<a class="btn" id="b" href="nowhere.html" onclick="this.style.width = \'300px\'">Go</a>',
  });
  const name = writeProof(p, [component(page, { states: ["active"], widths: [1440] })]);
  const r = run(p, name);
  assert.equal(r.status, 0, r.stdout + r.stderr); // the handler would have widened the link (rest fails), and the link would have left the page (the run would stop)
  assert.equal(byId(p, name)["motion:btn:rest:active"].status, "pass");
});

test("an element a transform rotates is not measured while it is rotated, and the row says so", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const page = buttonPage(p, "tilt", { css: ".btn{transition:transform var(--motion-quick) var(--easing-standard)}.btn:hover{transform:rotate(3deg)}@media (prefers-reduced-motion:reduce){.btn{transition:none}}" });
  const name = writeProof(p, [component(page, { states: ["hover"], widths: [1440] })]);
  const r = run(p, name);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(byId(p, name)["motion:btn:shift:hover:1440"].detail, /not measured while its transform rotates or skews it: button#b/); // the span after it was measured
});

test("an element another element covers cannot be put into a state: the shift row fails and names what covers it, the other rows are not verified", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const page = buttonPage(p, "covered", { css: ".row{position:relative}.cover{position:absolute;inset:0}", after: '<div class="cover"></div>' });
  const name = writeProof(p, [component(page, { states: ["hover"], widths: [1440] })]);
  const r = run(p, name);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.deepEqual(failing(p, name), ["motion:btn:shift:hover:1440"]);
  assert.match(byId(p, name)["motion:btn:shift:hover:1440"].detail, /could not be put into :hover at 1440 px: .*<div class="cover"><\/div> intercepts pointer events/);
  for (const s of ["tokens", "reduced", "rest"]) assert.equal(byId(p, name)[`motion:btn:${s}:hover`].status, "skipped", s);
});

test("a component case cannot judge durations without the built tokens: that row is not verified", (t) => {
  if (needSetup(t)) return;
  const p = motionProject(); // the sources are there, the tokens are not built
  const page = buttonPage(p, "unbuilt", { css: ".btn{transition:background-color 160ms ease}.btn:hover{background:#007d71}@media (prefers-reduced-motion:reduce){.btn{transition:none}}" });
  const name = writeProof(p, [component(page, { states: ["hover"], widths: [1440] })]);
  const r = run(p, name);
  assert.equal(r.status, 3, r.stdout + r.stderr);
  const row = byId(p, name)["motion:btn:tokens:hover"];
  assert.equal(row.status, "skipped"); assert.match(row.detail, /not verified: assets\/tokens\/tokens\.json is not built: run `brand-creator tokens`/);
  assert.deepEqual(failing(p, name), []);
});
