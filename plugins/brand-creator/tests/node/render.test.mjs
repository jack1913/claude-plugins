import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, bc, makeProject, tmpdir, ROOT } from "./_helpers.mjs";

function page(p, name, body, head = "") {
  const f = path.join(p, "rounds/r1", name);
  fs.writeFileSync(f, `<!doctype html><html><head><meta charset=utf-8><title>t</title>${head}</head><body>${body}</body></html>`);
  return `rounds/r1/${name}`;
}
const rep = (p) => JSON.parse(fs.readFileSync(path.join(p, "assets/_checks/shot.json"), "utf8"));

test("shot: the fixture board passes in four views with a report", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const r = bc(["shot", "rounds/r1/board.html", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const doc = rep(p);
  assert.deepEqual(doc.results.map((x) => x.id), ["view:1440-light", "view:1440-dark", "view:390-light", "view:390-dark"]);
  assert.equal(doc.status, "pass");
  for (const v of doc.results) for (const s of v.slices) assert.ok(fs.existsSync(s));
  assert.ok(!doc.out_dir.startsWith(fs.realpathSync(p)), "shots must be written outside the project");
});

test("shot: horizontal overflow, console errors and non-local requests each fail the gate", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const cases = {
    overflow: [page(p, "o.html", '<div style="width:2000px;height:10px;background:#000">x</div>'), (v) => v.overflow === true],
    console: [page(p, "c.html", "<p>x</p><script>console.error('boom')</script>"), (v) => v.console_errors.some((e) => e.includes("boom"))],
    network: [page(p, "n.html", '<img src="https://example.invalid/a.png" width=5 height=5>'), (v) => v.non_local_requests.length === 1],
  };
  for (const [name, [rel, ok]] of Object.entries(cases)) {
    const r = bc(["shot", rel, "--project", p]);
    assert.equal(r.status, 1, `${name}: ${r.stdout}`);
    assert.ok(ok(rep(p).results[0]), name);
  }
  // the unmutated baseline still passes, so the failures above are caused by the mutations
  assert.equal(bc(["shot", "rounds/r1/board.html", "--project", p]).status, 0);
});

test("shot: forbidden strings are counted from the project list", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  fs.writeFileSync(path.join(p, "brief/BRIEF.md"), "# Brief\n\n## Forbidden\n\n- synergy\n");
  const rel = page(p, "w.html", "<p>Synergy, synergy.</p>");
  assert.equal(bc(["shot", rel, "--project", p]).status, 1);
  assert.deepEqual(rep(p).results[0].forbidden_counts, { synergy: 2 });
});

test("shot --motion takes a proof.json, not a page", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const r = bc(["shot", "rounds/r1/board.html", "--motion", "--project", p]);
  assert.equal(r.status, 2, r.stderr);
  const r2 = bc(["shot", "--motion", "motion/missing.json", "--project", p]);
  assert.equal(r2.status, 2);
  assert.match(r2.stderr, /not found/);
});

test("card: renders exact pixels, writes only on byte change, refuses network", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  fs.mkdirSync(path.join(p, "assets/social"), { recursive: true });
  const html = path.join(p, "assets/social/card.html");
  fs.writeFileSync(html, "<!doctype html><style>html,body{margin:0}</style><div style='width:100vw;height:100vh;background:#c03'></div>");
  const args = ["card", "assets/social/card.html", "--width", "120", "--height", "60", "--out", "assets/social/card.png", "--json", "--project", p];
  let r = bc(args);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(JSON.parse(r.stdout.trim().split("\n").pop()).changed, true);
  const png = fs.readFileSync(path.join(p, "assets/social/card.png"));
  assert.equal(png.readUInt32BE(16), 120);
  assert.equal(png.readUInt32BE(20), 60);
  r = bc(args);
  assert.equal(JSON.parse(r.stdout.trim().split("\n").pop()).changed, false);
  fs.writeFileSync(html, "<img src='https://example.invalid/x.png'>");
  r = bc(args);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /not self-contained/);
});

test("without setup the render commands exit 3 and name the fix", () => {
  const p = makeProject();
  const r = bc(["shot", "rounds/r1/board.html", "--project", p], { data: tmpdir("bc-node-nosetup-") });
  assert.equal(r.status, 3);
  assert.match(r.stderr, /setup/);
  const nodata = tmpdir("bc-node-nosetup-");
  fs.cpSync(path.join(ROOT, "skills/brand-creator/references/examples/acme/motion"), path.join(p, "motion"), { recursive: true });
  const font = path.join(ROOT, "tests/fixtures/fonts/TestFont-subset.ttf");
  for (const args of [["fonts", "--font-file", font, "--text", "A"], ["shot", "--motion", "motion/proof.json", "--project", p]]) {
    const q = bc(args, { data: nodata });
    assert.equal(q.status, 3, args.join(" ")); // the new Chromium commands fail the same explicit way
    assert.match(q.stderr, /setup/);
  }
});
