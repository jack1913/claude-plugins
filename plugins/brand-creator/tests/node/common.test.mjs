import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { ROOT, tmpdir, makeProject, DATA, SETUP_DATA, bc, needSetup } from "./_helpers.mjs";

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

test("the tools write scratch into a data directory of the test process's own, never into the given one", (t) => {
  if (needSetup(t)) return;
  assert.notEqual(fs.realpathSync(DATA), fs.realpathSync(SETUP_DATA));
  assert.equal(fs.realpathSync(path.join(DATA, "node_modules")), fs.realpathSync(path.join(SETUP_DATA, "node_modules")));
  assert.equal(process.env.BRAND_CREATOR_DATA, DATA);
  const root = tmpdir();
  assert.equal(bc(["new", "probe", "--name", "Probe", "--root", root]).status, 0);
  const r = bc(["snapshot", "take", "brief", "--name", "probe", "--project", path.join(root, "probe")]);   // no --out: <data>/scratch/<project>/snapshots/
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = r.stdout.split("-> ").pop().trim();
  assert.ok(fs.existsSync(out) && out.startsWith(fs.realpathSync(path.join(DATA, "scratch")) + path.sep), out);
  assert.ok(!fs.existsSync(path.join(SETUP_DATA, "scratch", path.basename(path.dirname(path.dirname(out))))));
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

test("missingSharedLibs names the libraries ldd cannot find, and only on Linux", () => {
  const lddOut = [
    "\tlinux-vdso.so.1 (0x0000ffff8a1b0000)",
    "\tlibnss3.so => not found",
    "\tlibgbm.so.1 => not found",
    "\tlibnss3.so => not found",   // listed twice: reported once
    "\tlibc.so.6 => /lib/aarch64-linux-gnu/libc.so.6 (0x0000ffff89e00000)",
  ].join("\n");
  const calls = [];
  const fake = (cmd, args) => { calls.push([cmd, ...args]); return { status: 0, stdout: lddOut, stderr: "" }; };
  assert.deepEqual(C.missingSharedLibs("/x/chrome-headless-shell", { run: fake, platform: "linux" }), ["libgbm.so.1", "libnss3.so"]);
  assert.deepEqual(calls, [["ldd", "/x/chrome-headless-shell"]]);
  // a complete system, a failing ldd, no ldd at all, another OS and no binary: nothing is invented
  assert.deepEqual(C.missingSharedLibs("/x/y", { run: () => ({ status: 0, stdout: "\tlibc.so.6 => /lib/libc.so.6 (0x1)\n" }), platform: "linux" }), []);
  assert.deepEqual(C.missingSharedLibs("/x/y", { run: () => ({ error: new Error("ENOENT"), stdout: null }), platform: "linux" }), []);
  assert.deepEqual(C.missingSharedLibs("/x/y", { run: fake, platform: "darwin" }), []);
  assert.deepEqual(C.missingSharedLibs(null, { run: fake, platform: "linux" }), []);
});

test("findHeadlessShell finds the binary setup installed and says null when it is not there", () => {
  const base = tmpdir("bc-node-browsers-");
  assert.equal(C.findHeadlessShell(base, "1228"), null);
  const linux = path.join(base, "chromium_headless_shell-1228", "chrome-linux");   // the layout Playwright 1.61 unpacks on Linux (seen in the Docker run)
  fs.mkdirSync(linux, { recursive: true });
  fs.writeFileSync(path.join(linux, "headless_shell"), "#!/bin/sh\n");
  assert.equal(C.findHeadlessShell(base, "1228"), path.join(linux, "headless_shell"));
  const mac = path.join(base, "chromium_headless_shell-1300", "chrome-headless-shell-mac-arm64");
  fs.mkdirSync(mac, { recursive: true });
  fs.writeFileSync(path.join(mac, "chrome-headless-shell"), "#!/bin/sh\n");
  assert.equal(C.findHeadlessShell(base, "1300"), path.join(mac, "chrome-headless-shell"));
  assert.equal(C.findHeadlessShell(base, "9999"), null);
});

test("render.mjs reports missing system libraries instead of telling the user to re-run setup", () => {
  const src = fs.readFileSync(path.join(ROOT, "scripts/render.mjs"), "utf8");
  assert.match(src, /missingSharedLibs\(findHeadlessShell\(setup\.browsers_path, setup\.chromium_revision\)\)/);
  assert.match(src, /this system lacks shared libraries it needs/);
});

// the two twins of Python functions that render.mjs needs: the name of a proof's report, and whether a drawing is pixel art
const python = (code, ...args) => {
  const r = spawnSync("python3", ["-c", `import json, sys; sys.path.insert(0, sys.argv[1])\n${code}`, path.join(ROOT, "scripts/lib"), ...args], { encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
};

test("the report name of a proof file is the same in JS and in Python, and the hash is the one of its project-relative path", () => {
  const paths = ["motion/proof.json", "rounds/r2/Motion Proof (v2).json", "\u00fcn\u00ef/\u00e7ode.json", "a.b.c.json", "-.json", "x/y/z/.json", "Z", "motion/proof.json.json", "motion/PROOF.JSON"];
  const want = python("from _common import motion_report_tool\nprint(json.dumps([motion_report_tool(p) for p in json.loads(sys.argv[2])]))", JSON.stringify(paths));
  assert.deepEqual(paths.map((x) => C.proofReportTool(x)), want);
  assert.equal(C.proofReportTool("motion/proof.json"), `motion/proof-${C.sha256("motion/proof.json").slice(0, 6)}`);   // the first six hex of sha256 of the path
  assert.equal(C.proofReportTool("rounds/r2/Motion Proof (v2).json"), `motion/motion-proof-v2-${C.sha256("rounds/r2/Motion Proof (v2).json").slice(0, 6)}`); // the stem, lower-cased, runs of other characters as one dash
  assert.equal(C.proofReportTool("motion/proof.json", "frames"), C.proofReportTool("motion/proof.json").replace("motion/", "frames/"));
  assert.notEqual(C.proofReportTool("motion/proof.json"), C.proofReportTool("rounds/r2/proof.json")); // the same file name in two folders is two reports
});

test("the kind of a motion proof (gated, exploration or gone) is the same rule in JS and in Python: both answer one table of cases", () => {
  const table = JSON.parse(fs.readFileSync(path.join(ROOT, "tests/fixtures/motion-proof-kinds.json"), "utf8")).cases;
  assert.ok(table.length >= 20 && new Set(table.map((c) => c.kind)).size === 3);
  const dirs = table.map((c, i) => {
    const project = tmpdir(`bc-kind-${i}-`);
    for (const f of c.files) { fs.mkdirSync(path.dirname(path.join(project, f)), { recursive: true }); fs.writeFileSync(path.join(project, f), "x\n"); }
    return project;
  });
  table.forEach((c, i) => assert.equal(C.motionProofKind(dirs[i], c.proof), c.kind, c.why));
  const want = python("from pathlib import Path\nfrom _common import motion_proof_kind\nprint(json.dumps([motion_proof_kind(Path(d), p) for d, p in json.loads(sys.argv[2])]))", JSON.stringify(table.map((c, i) => [dirs[i], c.proof])));
  assert.deepEqual(want, table.map((c) => c.kind), "the Python side answers as the table says");
});

test("pixelArt reads the root of an SVG the way svgtools.pixel_art does", () => {
  const NS = 'xmlns="http://www.w3.org/2000/svg"';
  const cases = [
    [`<svg ${NS} shape-rendering="crispEdges" viewBox="0 0 8 8"/>`, true],
    [`<svg ${NS} viewBox="0 0 8 8" width="8" shape-rendering='crispEdges'><rect width="8" height="8"/></svg>`, true],
    [`<?xml version="1.0"?>\n<!-- drawn on a grid -->\n<svg ${NS} shape-rendering="crispEdges"/>`, true],
    [`<svg ${NS} aria-label="a > b" shape-rendering="crispEdges"/>`, true],
    [`<svg ${NS} shape-rendering="geometricPrecision"/>`, false],
    [`<svg ${NS} shape-rendering="crispedges"/>`, false],
    [`<svg ${NS} viewBox="0 0 8 8"/>`, false],
    [`<svg ${NS}><g shape-rendering="crispEdges"/></svg>`, false],
    [`<svg ${NS} style="shape-rendering:crispEdges"/>`, false],
    [`<svg ${NS} data-shape-rendering="crispEdges"/>`, false],
    [`<svg ${NS} aria-label="shape-rendering='crispEdges'"/>`, false],
    [`<!-- <svg shape-rendering="crispEdges"> -->\n<svg ${NS} viewBox="0 0 8 8"/>`, false],
  ];
  const want = python("import svgtools\nprint(json.dumps([svgtools.pixel_art(t) for t in json.loads(sys.argv[2])]))", JSON.stringify(cases.map((c) => c[0])));
  assert.deepEqual(want, cases.map((c) => c[1]), "the Python side answers as written here");
  assert.deepEqual(cases.map((c) => C.pixelArt(c[0])), cases.map((c) => c[1]));
  assert.equal(C.pixelArt("not an svg"), false);
});
