// shot --motion, continued from motion.test.mjs: component cases. Split from motion.test.mjs so that node --test runs them side by side; the helpers
// are in _motion.mjs.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, mutateText, motionProject, run, rep, byId, failing, writeProof, writePage, demo, PAGE, reportFile, DATA, ROOT, bc } from "./_motion.mjs";

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

test("a width the element cannot be put into under reduced motion makes the reduced row not verified, never a pass", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  // under reduced motion below 1000 px an overlay covers the button, and the button keeps its transition there; at 1440 px it has none
  const tr = "transition:background-color var(--motion-quick) var(--easing-standard)";
  const page = buttonPage(p, "reduced-covered", {
    css: `.btn{${tr}}.btn:hover{background:#007d71}@media (prefers-reduced-motion:reduce){.btn{transition:none}}`
      + `@media (prefers-reduced-motion:reduce) and (max-width:999px){.btn{${tr}}.row{position:relative}.cover{position:absolute;inset:0}}`,
    after: '<div class="cover"></div>',
  });
  const name = writeProof(p, [component(page, { states: ["hover"] })]);
  const r = run(p, name);
  assert.equal(r.status, 3, r.stdout + r.stderr); // not verified: no failing row, and no pass
  const rows = byId(p, name);
  assert.equal(rows["motion:btn:reduced:hover"].status, "skipped");
  assert.match(rows["motion:btn:reduced:hover"].detail, /^not verified: the element could not be put into :hover under reduced motion at 390 px: .*<div class="cover"><\/div> intercepts pointer events/);
  assert.match(rows["motion:btn:reduced:hover"].detail, /; no transition or animation on entering or leaving :hover at 1440 px /); // what was judged is said as well
  assert.doesNotMatch(rows["motion:btn:reduced:hover"].detail, /could not be put into[^;]*1440/); // 1440 px could be, and is not named as a width it could not
  assert.equal(rep(p, name).status, "not-verified");
  assert.deepEqual(failing(p, name), []);
  // the normal pass could be put into the state at both widths: its rows judged both and say nothing of a missing width
  for (const s of ["tokens", "rest"]) assert.doesNotMatch(rows[`motion:btn:${s}:hover`].detail, /only/);
});

test("a width the element cannot be put into under reduced motion does not hide an animation found at another width", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const tr = "transition:background-color var(--motion-quick) var(--easing-standard)";
  const page = buttonPage(p, "reduced-mixed", {
    css: `.btn{${tr}}.btn:hover{background:#007d71}@media (prefers-reduced-motion:reduce) and (max-width:999px){.row{position:relative}.cover{position:absolute;inset:0}}`,
    after: '<div class="cover"></div>',
  });
  const name = writeProof(p, [component(page, { states: ["hover"] })]);
  assert.equal(run(p, name).status, 1);
  assert.deepEqual(failing(p, name), ["motion:btn:reduced:hover"]); // 1440 px animates under reduced motion: that is a finding, and 390 px is said beside it
  const d = byId(p, name)["motion:btn:reduced:hover"].detail;
  assert.match(d, /starts transition of background-color on button#b \(1440 px\)/); assert.match(d, /not verified under reduced motion at 390 px: .*intercepts pointer events/);
});

test("the tokens and rest rows name the widths they judged when the element could not be put into the state at another", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  const tr = "transition:background-color var(--motion-quick) var(--easing-standard)";
  const page = buttonPage(p, "normal-covered", {
    css: `.btn{${tr}}.btn:hover{background:#007d71}@media (prefers-reduced-motion:reduce){.btn{transition:none}}@media (max-width:999px){.row{position:relative}.cover{position:absolute;inset:0}}`,
    after: '<div class="cover"></div>',
  });
  const name = writeProof(p, [component(page, { states: ["hover"] })]);
  assert.equal(run(p, name).status, 1);
  assert.deepEqual(failing(p, name), ["motion:btn:shift:hover:390"]); // the width it could not be put into fails its shift row, as before
  const rows = byId(p, name);
  for (const s of ["tokens", "rest"]) {
    assert.equal(rows[`motion:btn:${s}:hover`].status, "pass", s);
    assert.match(rows[`motion:btn:${s}:hover`].detail, /judged at 1440 px only: the element could not be put into :hover at 390 px \(see the shift rows\)/, s);
  }
  assert.equal(rows["motion:btn:reduced:hover"].status, "skipped"); // reduced motion at 390 px is covered as well, and says which width and why
  assert.match(rows["motion:btn:reduced:hover"].detail, /at 390 px: /);
});

test("an element that fills the view is left with the pointer taken out of the view, and the rest row says so", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  withMotionTokens(p);
  // the link is the whole view: no corner of it is outside the element, so the pointer has no corner to go to
  const tr = "transition:background-color var(--motion-quick) var(--easing-standard)";
  const page = buttonPage(p, "whole-view", {
    css: `.row{padding:0;display:block}.btn{display:block;box-sizing:border-box;width:100vw;height:100vh;padding:0;${tr}}.btn:hover{background:#007d71}.btn:active{background:#005f56}@media (prefers-reduced-motion:reduce){.btn{transition:none}}`,
    button: '<a class="btn" id="b" href="nowhere.html">Go</a>', after: "",
  });
  const name = writeProof(p, [component(page, { widths: [390] })]); // hover, then press: the press must not start with the pointer still on the element
  const r = run(p, name);
  assert.equal(r.status, 0, r.stdout + r.stderr); // not a failure of the page: it is the pointer that had nowhere to go
  const rows = byId(p, name);
  for (const s of ["hover", "active"]) {
    assert.equal(rows[`motion:btn:rest:${s}`].status, "pass", s);
    assert.match(rows[`motion:btn:rest:${s}`].detail, /at 390 px the pointer left the view, because no corner of it is outside the element/, s); // said, not done in silence
    assert.match(rows[`motion:btn:tokens:${s}`].detail, /^[1-9]\d* animation\(s\) on the state change; every duration and easing is a motion token/, s); // each state was entered from rest: its transition ran
  }
});
