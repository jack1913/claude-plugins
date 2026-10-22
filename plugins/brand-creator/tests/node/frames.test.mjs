// frames <proof.json>: stills of a page case's mark along its motion. Each is cut from the page at device scale 2 on the page's own background; the strip puts
// them side by side in order; reduced.png is the element under prefers-reduced-motion; frames.json lists them with their sha256. The files are in the project
// (the book will show them), written only on a byte change, so a rerun is byte-identical. A case with nothing to seek exits 1 and says why.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { needSetup, bc, motionProject, writeProof, writePage, pageCase, readPng, columns, sha256Of, tree } from "./_motion.mjs";
import { proofReportTool } from "../../scripts/lib/_common.mjs";

const frames = (p, ...args) => bc(["frames", ...args, "--project", p]);
const dirOf = (p, name = "demo-page") => path.join(p, "motion/frames", name);
const doc = (p, name) => JSON.parse(fs.readFileSync(path.join(dirOf(p, name), "frames.json"), "utf8"));
const png = (p, file, name) => readPng(fs.readFileSync(path.join(dirOf(p, name), file)));

test("frames writes a still at 0, 25, 50, 75 and 100 percent, a strip, the reduced still and frames.json, and a report", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const before = tree(p);
  const r = frames(p, "motion/proof.json");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const names = fs.readdirSync(dirOf(p)).sort();
  assert.deepEqual(names, ["00-0.png", "01-25.png", "02-50.png", "03-75.png", "04-100.png", "frames.json", "reduced.png", "strip.png"]);
  const d = doc(p);
  assert.deepEqual(d.frames.map((f) => [f.percent, f.ms]), [[0, 0], [25, 80], [50, 160], [75, 240], [100, 320]]);
  assert.equal(d.length_ms, 320); assert.equal(d.scale, 2); assert.deepEqual(d.size, [64, 64]);
  for (const f of d.frames) { assert.equal(sha256Of(fs.readFileSync(path.join(p, f.file))), f.sha256); assert.ok(f.file.startsWith("motion/frames/demo-page/")); }
  assert.equal(sha256Of(fs.readFileSync(path.join(p, d.strip.file))), d.strip.sha256);
  assert.equal(sha256Of(fs.readFileSync(path.join(p, d.reduced.file))), d.reduced.sha256);
  // device scale 2: the 64 px mark is 128 px wide; the strip is the five side by side
  const stills = d.frames.map((f) => readPng(fs.readFileSync(path.join(p, f.file))));
  for (const s of stills) assert.deepEqual([s.w, s.h], [128, 128]);
  const strip = png(p, "strip.png");
  assert.deepEqual([strip.w, strip.h], [640, 128]);
  stills.forEach((s, i) => assert.ok(columns(strip, i * 128, (i + 1) * 128).equals(columns(s, 0, 128)), `frame ${i} is not where it belongs in the strip`));
  assert.notEqual(d.frames[0].sha256, d.frames[2].sha256); // the dot has moved by half-way
  assert.deepEqual([png(p, "reduced.png").w, png(p, "reduced.png").h], [128, 128]);
  // the report, named after the proof; nothing else in the project was written
  const reportFile = path.join(p, "assets/_checks", proofReportTool("motion/proof.json", "frames") + ".json");
  const rep = JSON.parse(fs.readFileSync(reportFile, "utf8"));
  assert.match(rep.tool, /^frames\/proof-[0-9a-f]{6}$/); assert.equal(rep.status, "pass"); assert.equal(rep.proof, "motion/proof.json");
  const after = tree(p);
  const added = Object.keys(after).filter((f) => !(f in before)).sort();
  assert.deepEqual(added, [path.relative(p, reportFile).split(path.sep).join("/"), ...names.map((n) => `motion/frames/demo-page/${n}`)].sort());
  assert.deepEqual(Object.keys(before).filter((f) => before[f] !== after[f]), []); // and nothing that was there changed
  assert.match(r.stdout, /written \(8 of 8 file\(s\) changed\)/);
});

test("a rerun is byte-identical and says unchanged; other points write what changed and leave the old frames in place, said", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  assert.equal(frames(p, "motion/proof.json").status, 0);
  const first = tree(dirOf(p)), when = Object.fromEntries(fs.readdirSync(dirOf(p)).map((n) => [n, fs.statSync(path.join(dirOf(p), n)).mtimeMs]));
  const r = frames(p, "motion/proof.json");
  assert.equal(r.status, 0, r.stdout);
  assert.match(r.stdout, /strip\.png, reduced\.png and frames\.json in motion\/frames\/demo-page\/: unchanged/);
  assert.deepEqual(tree(dirOf(p)), first);
  for (const [n, m] of Object.entries(when)) assert.equal(fs.statSync(path.join(dirOf(p), n)).mtimeMs, m, `${n} was written again`);
  // three points: the first one is the same picture under the same name and is not written again; the others are new; the old ones are kept and named
  const q = frames(p, "motion/proof.json", "--at", "0,50,100");
  assert.equal(q.status, 0, q.stdout);
  assert.match(q.stdout, /3 frame\(s\) at 0, 50, 100% of 320 ms/);
  assert.equal(fs.statSync(path.join(dirOf(p), "00-0.png")).mtimeMs, when["00-0.png"]);
  assert.deepEqual(fs.readdirSync(dirOf(p)).sort(), ["00-0.png", "01-25.png", "01-50.png", "02-100.png", "02-50.png", "03-75.png", "04-100.png", "frames.json", "reduced.png", "strip.png"]);
  assert.match(q.stdout, /\[WARN\] frames:demo-page:stale .*01-25\.png, 02-50\.png, 03-75\.png, 04-100\.png in motion\/frames\/demo-page\/ are not part of this run/);
  assert.equal(doc(p).frames.length, 3);
});

test("--count spreads the points evenly, --at names them, and a wrong value is a usage error", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const r = frames(p, "motion/proof.json", "--count", "3");
  assert.equal(r.status, 0, r.stdout);
  assert.deepEqual(doc(p).frames.map((f) => [f.percent, f.ms, path.basename(f.file)]), [[0, 0, "00-0.png"], [50, 160, "01-50.png"], [100, 320, "02-100.png"]]);
  const seven = frames(p, "motion/proof.json", "--count", "7");
  assert.equal(seven.status, 0);
  assert.deepEqual(doc(p).frames.map((f) => f.percent), [0, 16.67, 33.33, 50, 66.67, 83.33, 100]);
  assert.equal(doc(p).frames[1].file, "motion/frames/demo-page/01-16.67.png");
  const one = frames(p, "motion/proof.json", "--count", "1");
  assert.equal(one.status, 0); assert.deepEqual(doc(p).frames.map((f) => f.percent), [0]);
  for (const args of [["--count", "0"], ["--count", "101"], ["--count", "2.5"], ["--count", "x"], ["--at", "0,150"], ["--at", "0,,50"], ["--at", "-1"], ["--at", "a,b"], ["--count", "3", "--at", "0,50"]]) {
    const bad = frames(p, "motion/proof.json", ...args);
    assert.equal(bad.status, 2, `${args.join(" ")}: ${bad.stdout}${bad.stderr}`);
  }
  assert.equal(frames(p).status, 2); // a proof file is needed
  assert.equal(frames(p, "motion/nope.json").status, 2);
});

test("a case with no seekable motion exits 1 and says why, and writes no frame", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  writePage(p, "still", { css: "#mark{display:block}", body: `${fs.readFileSync(path.join(p, "assets/logo/mark.svg"), "utf8").replace("<svg ", '<svg id="mark" ')}` });
  writePage(p, "raf", { css: "#mark{display:block}", body: `${fs.readFileSync(path.join(p, "assets/logo/mark.svg"), "utf8").replace("<svg ", '<svg id="mark" ')}<script>(function t(){requestAnimationFrame(t)})()</script>` });
  const proof = writeProof(p, [pageCase({ name: "still", page: "motion/still.html" }), pageCase({ name: "raf", page: "motion/raf.html", settle_ms: 300 })]);
  const r = frames(p, proof);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stdout, /\[FAIL\] frames:still .*no seekable motion: the page has no Web Animation\n/);
  assert.match(r.stdout, /\[FAIL\] frames:raf .*no seekable motion: the page has no Web Animation \(its motion is driven by requestAnimationFrame, which cannot be seeked\)\n/);
  assert.ok(!fs.existsSync(path.join(p, "motion/frames")), "a frame was written for a case with nothing to seek");
});

test("--case picks one page case; a states case or an unknown name is a usage error; a case name never leaves its folder", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const demo = JSON.parse(fs.readFileSync(path.join(p, "motion/proof.json"), "utf8")).cases;
  const proof = writeProof(p, [demo[0], { ...demo[1], name: "../escape" }, { ...demo[1], name: "second" }]);
  assert.equal(frames(p, proof, "--case", "dot-press").status, 2);
  assert.equal(frames(p, proof, "--case", "nothing").status, 2);
  const r = frames(p, proof, "--case", "second", "--count", "2");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.deepEqual(fs.readdirSync(path.join(p, "motion/frames")), ["second"]);
  const all = frames(p, proof, "--count", "2");
  assert.equal(all.status, 0, all.stdout + all.stderr);
  assert.deepEqual(fs.readdirSync(path.join(p, "motion/frames")).sort(), ["escape", "second"]); // "../escape" is the folder escape, inside motion/frames
  assert.ok(!fs.existsSync(path.join(p, "motion/escape")) && !fs.existsSync(path.join(p, "escape")));
  assert.match(all.stdout, /\[INFO\] frames:dot-press .*a states case has no page to seek/);
  const twice = writeProof(p, [{ ...demo[1], name: "a b" }, { ...demo[1], name: "a-b" }]);
  assert.equal(frames(p, twice).status, 2); // two names, one folder
});

test("a still is the page at exactly its point of the motion: a bar sliding 200 px in 1000 ms is at 100 px in the still at 50 percent", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  // a 300 x 40 mark of HTML: a red bar 20 x 10 px slides linearly from x 0 to x 200; the stills are cut from the mark's box at device scale 2
  writePage(p, "slide", {
    css: `#mark{position:relative;width:300px;height:40px;background:#fff}#bar{position:absolute;left:0;top:10px;width:20px;height:10px;background:#f00;animation:slide 1000ms linear 1 both}`
      + `@keyframes slide{from{transform:translateX(0)}to{transform:translateX(200px)}}@media (prefers-reduced-motion: reduce){#bar{animation:none}}`,
    body: '<div id="mark"><div id="bar"></div></div>',
  });
  const proof = writeProof(p, [pageCase({ name: "slide", page: "motion/slide.html", widths: [] })]);
  const r = frames(p, proof, "--count", "5");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const left = (png) => { // the first column with a red pixel (device pixels)
    for (let x = 0; x < png.w; x++) for (let y = 0; y < png.h; y++) { const o = (y * png.w + x) * png.bpp; if (png.px[o] > 200 && png.px[o + 1] < 60 && png.px[o + 2] < 60) return x; }
    return -1;
  };
  assert.deepEqual(doc(p, "slide").frames.map((f) => f.percent), [0, 25, 50, 75, 100]);
  const at = ["00-0.png", "01-25.png", "02-50.png", "03-75.png", "04-100.png"].map((f) => left(png(p, f, "slide")));
  assert.deepEqual(at, [0, 100, 200, 300, 400]); // 0, 50, 100, 150, 200 css px, at 2 device pixels each: not a frame later, not a frame earlier
  assert.equal(left(png(p, "reduced.png", "slide")), 0); // under reduced motion the bar is where the page puts it at rest
  // the strip has them side by side in this order (five different pictures: a reversed strip would show it)
  const strip = png(p, "strip.png", "slide"), w = strip.w / 5;
  assert.equal(w, 600);
  doc(p, "slide").frames.forEach((f, i) => assert.ok(columns(strip, i * w, (i + 1) * w).equals(columns(readPng(fs.readFileSync(path.join(p, f.file))), 0, w)), `frame ${i} is not where it belongs in the strip`));
  assert.equal(new Set(doc(p, "slide").frames.map((f) => f.sha256)).size, 5);
});

test("a page that does not load cleanly is refused, and no frame is written", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const bad = fs.readFileSync(path.join(p, "motion/demo.html"), "utf8").replace("<main>", "<script>nothing_is_defined_here()</script><main>");
  fs.writeFileSync(path.join(p, "motion/demo.html"), bad);
  const r = frames(p, "motion/proof.json", "--case", "demo-page");
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stdout, /\[FAIL\] frames:demo-page .*the page does not load cleanly: pageerror: /);
  assert.ok(!fs.existsSync(path.join(p, "motion/frames")));
});

test("a page that also moves by requestAnimationFrame while the stills are taken fails: its stills would change from run to run, and none is written", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  // the demo's seekable dot press, and a wobble a requestAnimationFrame loop draws beside it
  const wobble = '<div id="wob" style="width:10px;height:10px;background:#c03"></div><script>if(!matchMedia("(prefers-reduced-motion: reduce)").matches)(function w(now){document.getElementById("wob").style.transform="translateX("+Math.round(10*Math.sin((now||0)/50))+"px)";requestAnimationFrame(w)})()</script>';
  fs.writeFileSync(path.join(p, "motion/demo.html"), fs.readFileSync(path.join(p, "motion/demo.html"), "utf8").replace("<main>", wobble + "<main>"));
  const r = frames(p, "motion/proof.json", "--case", "demo-page");
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stdout, /\[FAIL\] frames:demo-page .*not reproducible: the page also moves by requestAnimationFrame \(\d+ call\(s\) while the stills were taken\), which cannot be seeked, so the stills would change from run to run; no file was written\n/);
  assert.ok(!fs.existsSync(path.join(p, "motion/frames")));
});

test("a case's stills come from one proof: another proof with a case of the same name is refused before anything is drawn", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  assert.equal(frames(p, "motion/proof.json", "--count", "2").status, 0);
  const before = tree(dirOf(p));
  fs.mkdirSync(path.join(p, "rounds/r2"), { recursive: true });
  const demo = JSON.parse(fs.readFileSync(path.join(p, "motion/proof.json"), "utf8")).cases.find((c) => c.name === "demo-page");
  const tryout = writeProof(p, [demo], "rounds/r2/proof.json");
  const r = frames(p, tryout);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.match(r.stderr, /motion\/frames\/demo-page\/ holds the stills of motion\/proof\.json, and a case's stills come from one proof: rename the case in rounds\/r2\/proof\.json, or move motion\/frames\/demo-page\/ to removed-<date>\//);
  assert.deepEqual(tree(dirOf(p)), before);
  assert.equal(frames(p, "motion/proof.json", "--count", "2").status, 0); // the proof that wrote them may write them again
});

test("a strip wider than Chromium can write is a usage error that says how many stills fit", (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  // a 700 px wide mark: one still is 1400 px at 2x, so 46 fit in 65535 px and 100 do not
  writePage(p, "wide", { css: "#mark{position:relative;width:700px;height:40px;background:#fff}#bar{position:absolute;left:0;top:10px;width:20px;height:10px;background:#f00;animation:slide 1000ms linear 1 both}"
    + "@keyframes slide{from{transform:none}to{transform:translateX(600px)}}@media (prefers-reduced-motion: reduce){#bar{animation:none}}", body: '<div id="mark"><div id="bar"></div></div>' });
  const proof = writeProof(p, [pageCase({ name: "wide", page: "motion/wide.html", widths: [] })]);
  const r = frames(p, proof, "--count", "100");
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.match(r.stderr, /strip\.png would be 140000 x 80 px \(100 still\(s\) of 1400 px at 2x\), and Chromium writes a picture at most 65535 px wide and high: ask for 46 still\(s\) or fewer \(--count or --at\)/);
  assert.ok(!fs.existsSync(path.join(p, "motion/frames")));
  assert.equal(frames(p, proof, "--count", "46").status, 0);
});
