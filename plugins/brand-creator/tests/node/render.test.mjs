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

const PNG1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==";

test("shot: lazy images are loaded first, so one hidden at this width or below the fold is never reported broken", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // a page with a desktop and a phone copy of each picture: Chromium never loads a lazy image that is display:none
  const css = "<style>.m{display:none}@media (max-width:600px){.d{display:none}.m{display:block}}</style>";
  const body = `<div style="height:3000px">tall</div><img class="d" loading="lazy" src="${PNG1}" width="40" height="40" alt="">`
    + `<img class="m" loading="lazy" src="${PNG1}" width="20" height="20" alt="">`;
  const rel = page(p, "lazy.html", body, css);
  const r = bc(["shot", rel, "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  for (const v of rep(p).results) {
    assert.deepEqual(v.broken_images, [], v.id);
    assert.equal(v.lazy_images, 2, v.id);
    assert.match(v.detail, /2 lazy image\(s\) loaded first/);
  }
  // a really broken image is still reported
  const bad = page(p, "bad.html", '<img loading="lazy" src="data:image/png;base64,AAAA" width="10" height="10" alt="">');
  assert.equal(bc(["shot", bad, "--project", p]).status, 1);
  assert.equal(rep(p).results[0].broken_images.length, 1);
});

test("shot: running animations are waited for, and one that repeats forever is named, not waited for", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = "<style>@keyframes f{from{opacity:0}to{opacity:1}}.once{animation:f 1.2s forwards}.loop{animation:f 1s infinite}</style>";
  let rel = page(p, "once.html", '<div class="once">moving once</div>', css);
  assert.equal(bc(["shot", rel, "--project", p]).status, 0);
  let v = rep(p).results[0];
  assert.deepEqual(v.animations, { waited: 1, running: 0, capped: false });
  assert.match(v.detail, /waited for 1 animation\(s\) to end/);
  rel = page(p, "loop.html", '<div class="loop">moving forever</div>', css);
  const t0 = Date.now();
  assert.equal(bc(["shot", rel, "--project", p]).status, 0);
  assert.ok(Date.now() - t0 < 60000, "an endless animation must not hold the shot until the cap in every view");
  v = rep(p).results[0];
  assert.deepEqual(v.animations, { waited: 0, running: 1, capped: false });
  assert.match(v.detail, /1 animation\(s\) repeat forever: shot mid-way/);
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
