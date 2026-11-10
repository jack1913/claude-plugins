// shot --motion, continued from motion.test.mjs: the page passes (layout shift, reduced motion, listeners, requestAnimationFrame, network) and the
// proof files. Split from motion.test.mjs so that node --test runs them side by side; the helpers are in _motion.mjs.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, mutateText, motionProject, run, rep, byId, failing, writeProof, writePage, demo, PAGE, reportFile, DATA, ROOT, bc } from "./_motion.mjs";

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
