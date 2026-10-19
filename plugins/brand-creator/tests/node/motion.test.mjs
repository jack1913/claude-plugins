// shot --motion: named states at dsf 1 and 2 against the static SVG (with a control pair that must differ), and a page pass
// under normal and emulated prefers-reduced-motion (no running animation, no rAF loop, no motion listeners, CLS 0, rest == static).
// Every negative test breaks a scratch copy of the Acme demo and proves the mutation applied (mutateText throws otherwise).
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, bc, makeProject, mutateText, ROOT } from "./_helpers.mjs";

const EX = path.join(ROOT, "skills/brand-creator/references/examples/acme");

function motionProject() {
  const p = makeProject();
  fs.cpSync(path.join(EX, "motion"), path.join(p, "motion"), { recursive: true });
  return p;
}
const run = (p, proof = "motion/proof.json") => bc(["shot", "--motion", proof, "--project", p]);
const rep = (p) => JSON.parse(fs.readFileSync(path.join(p, "assets/_checks/motion.json"), "utf8"));
const byId = (p) => Object.fromEntries(rep(p).results.map((r) => [r.id, r]));
const failing = (p) => rep(p).results.filter((r) => r.status === "fail").map((r) => r.id);
const writeProof = (p, cases, name = "motion/p.json") => { fs.writeFileSync(path.join(p, name), JSON.stringify({ schema: 1, cases })); return name; };
const demo = (p) => path.join(p, "motion/demo.html");
const PAGE = { name: "demo-page", type: "page", page: "motion/demo.html", selector: "#mark", static: "assets/logo/mark.svg", settle_ms: 700 };

test("the Acme proof passes: states at dsf 1 and 2, a control pair, and both page passes", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const r = run(p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const doc = rep(p);
  assert.equal(doc.tool, "motion"); assert.equal(doc.status, "pass");
  const ids = doc.results.map((x) => x.id);
  for (const dsf of ["1x", "2x"]) for (const s of [`file=rest`, `rest=static`, `control:rest!=pressed`]) assert.ok(ids.includes(`motion:dot-press:${dsf}:${s}`), `${dsf} ${s}`);
  for (const s of ["control", "loops", "settled", "cls:normal", "normal:rest=static", "whole-pixel", "reduced:animations", "reduced:raf", "reduced:listeners", "cls:reduced", "reduced:rest=static"]) assert.ok(ids.includes(`motion:demo-page:${s}`), s);
  assert.equal(doc.results.length, 17);
  const ctl = byId(p)["motion:dot-press:2x:control:rest!=pressed"];
  assert.match(ctl.detail, /differ in \d+ px/); // the control saw a real difference, so the equality checks above are not vacuous
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
  assert.ok(failing(p).some((id) => id.endsWith(":control")), failing(p).join());
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
  assert.ok(failing(p).some((id) => id.endsWith(":states")), failing(p).join());
  assert.match(rep(p).results.find((x) => x.status === "fail").detail, /no state called idle/);
});

test("an animation that loops forever fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "steps(2, end) 1 both", "steps(2, end) infinite both");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:demo-page:loops"), failing(p).join());
});

test("whole pixels only: a smooth in-between position fails", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  mutateText(demo(p), "steps(2, end) 1 both", "linear 1 both");
  const r = run(p);
  assert.equal(r.status, 1, r.stdout);
  assert.ok(failing(p).includes("motion:demo-page:whole-pixel"), failing(p).join());
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
  assert.ok(bad.includes("motion:demo-page:settled")); // normal pass: still running after the settle time
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
});
