import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { ROOT, tmpdir, makeProject, DATA, needSetup } from "./_helpers.mjs";

process.env.BRAND_CREATOR_DATA = process.env.BRAND_CREATOR_DATA || tmpdir("bc-node-nodata-");
const C = await import(path.join(ROOT, "scripts/lib/_common.mjs"));

test("exit codes follow the contract", () => {
  assert.deepEqual(C.EXIT, { PASS: 0, FAIL: 1, USAGE: 2, CANNOT: 3 });
});

test("findProject walks up to BRAND-STATE.md and errors clearly otherwise", () => {
  const p = makeProject();
  const deep = path.join(p, "a", "b");
  fs.mkdirSync(deep, { recursive: true });
  assert.equal(C.findProject(undefined, deep), fs.realpathSync(p));
  assert.equal(C.findProject(p), fs.realpathSync(p));
  const empty = tmpdir();
  assert.throws(() => C.findProject(undefined, empty), (e) => e.code === 2 && /no brand project found; pass --project/.test(e.message));
  assert.throws(() => C.findProject(empty), (e) => e.code === 2);
});

test("confine keeps writes inside the project, including through symlinks", () => {
  const p = makeProject();
  const outside = tmpdir();
  assert.throws(() => C.confine(p, path.join(outside, "x.txt")), (e) => e.code === 2);
  assert.throws(() => C.confine(p, "../escape.txt"), (e) => e.code === 2);
  fs.symlinkSync(outside, path.join(p, "sneaky"));
  assert.throws(() => C.confine(p, "sneaky/x.txt"), (e) => e.code === 2);
  assert.equal(C.confine(p, "assets/new/x.txt"), path.join(fs.realpathSync(p), "assets/new/x.txt"));
  assert.equal(C.outsideProject(p, path.join(outside, "shots")), fs.realpathSync(outside) + "/shots");
  assert.throws(() => C.outsideProject(p, path.join(p, "shots")), (e) => e.code === 2);
});

test("Report writes assets/_checks/<tool>.json with the contract fields and statuses", () => {
  const p = makeProject();
  const input = path.join(p, "rounds/r1/board.html");
  const rep = new C.Report("demo", fs.realpathSync(p), [input]);
  rep.add("a", "pass", "first");
  assert.equal(rep.status, "pass");
  rep.add("b", "skipped", "second");
  assert.equal(rep.status, "not-verified");
  assert.equal(rep.exitCode(), 3);
  rep.add("c", "fail", "third");
  assert.equal(rep.status, "fail");
  assert.equal(rep.exitCode(), 1);
  const out = rep.write();
  const doc = JSON.parse(fs.readFileSync(out, "utf8"));
  assert.equal(out, path.join(fs.realpathSync(p), "assets/_checks/demo.json"));
  assert.deepEqual(Object.keys(doc).slice(0, 4), ["tool", "version", "inputs_sha", "inputs"]);
  assert.equal(doc.tool, "demo");
  assert.equal(doc.version, C.pluginVersion());
  assert.equal(doc.inputs[0].path, "rounds/r1/board.html");
  assert.match(doc.inputs_sha, /^[0-9a-f]{64}$/);
  assert.equal(doc.status, "fail");
  assert.throws(() => rep.add("x", "bogus"));
  assert.equal(new C.Report("empty", fs.realpathSync(p)).status, "not-verified");
});

test("inputs_sha follows the input bytes", () => {
  const p = fs.realpathSync(makeProject());
  const f = path.join(p, "rounds/r1/board.html");
  const sha = () => { const r = new C.Report("sha", p, [f]); r.add("a", "pass"); r.write(); return JSON.parse(fs.readFileSync(path.join(p, "assets/_checks/sha.json"), "utf8")).inputs_sha; };
  const a = sha();
  assert.equal(sha(), a);
  fs.appendFileSync(f, "<!-- changed -->");
  assert.notEqual(sha(), a);
});

test("writeIfChanged is put-on-byte-change", () => {
  const d = tmpdir();
  const f = path.join(d, "x", "y.txt");
  assert.equal(C.writeIfChanged(f, "one"), true);
  const m = fs.statSync(f).mtimeMs;
  assert.equal(C.writeIfChanged(f, "one"), false);
  assert.equal(fs.statSync(f).mtimeMs, m);
  assert.equal(C.writeIfChanged(f, "two"), true);
});

test("forbiddenTerms reads Forbidden bullets from the brief and the cliches file", () => {
  const p = makeProject();
  fs.writeFileSync(path.join(p, "brief/BRIEF.md"), "# Brief\n\n## Forbidden\n\n- synergy\n- `world-class`\n\n## Other\n\n- not-forbidden\n");
  fs.mkdirSync(path.join(p, "research"));
  fs.writeFileSync(path.join(p, "research/cliches.md"), "# Cliches\n\n### Forbidden words\n* leverage\n- synergy\n");
  assert.deepEqual(C.forbiddenTerms(p), ["synergy", "world-class", "leverage"]);
});

test("readStateTop reads scalars and strips comments", () => {
  const p = makeProject();
  const s = C.readStateTop(p);
  assert.equal(s.slug, "acme");
  assert.equal(s.tier, "quick");
  assert.equal(s.review_url, "");
});

test("loadDep names the setup command when the data directory has no packages", async () => {
  const saved = process.env.BRAND_CREATOR_DATA;
  process.env.BRAND_CREATOR_DATA = tmpdir("bc-node-empty-");
  try {
    await assert.rejects(() => C.loadDep("culori"), (e) => e.code === 3 && /setup/.test(e.message) && /culori/.test(e.message));
    assert.throws(() => C.readSetup(), (e) => e.code === 3 && /setup has not been run/.test(e.message));
  } finally {
    process.env.BRAND_CREATOR_DATA = saved;
  }
});

test("loadDep loads ESM packages from <data>/node_modules (createRequire resolution)", async (t) => {
  if (needSetup(t)) return;
  const saved = process.env.BRAND_CREATOR_DATA;
  process.env.BRAND_CREATOR_DATA = DATA;
  try {
    const culori = await C.loadDep("culori");
    assert.equal(typeof culori.formatHex, "function");
    const sd = await C.loadDep("style-dictionary");
    assert.equal(typeof sd.default, "function");
    const pw = await C.loadDep("playwright-core");
    assert.ok(pw.chromium);
    const cj = await C.loadDep("colorjs.io");
    assert.equal(typeof cj.default, "function");
  } finally {
    process.env.BRAND_CREATOR_DATA = saved;
  }
});

test("dataDir requires BRAND_CREATOR_DATA", () => {
  const saved = process.env.BRAND_CREATOR_DATA;
  delete process.env.BRAND_CREATOR_DATA;
  try {
    assert.throws(() => C.dataDir(), (e) => e.code === 2 && /--data/.test(e.message));
  } finally {
    process.env.BRAND_CREATOR_DATA = saved;
  }
});
