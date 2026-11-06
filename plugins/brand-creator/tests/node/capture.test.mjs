import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { spawn } from "node:child_process";
import { needSetup, bc, makeProject, BIN, DATA } from "./_helpers.mjs";

// `capture` stills of a project page and of a real site (scripts/CONTRACT.md "capture"). The real site is a server of this process on 127.0.0.1: nothing here
// reaches another machine. Such a test runs the command asynchronously (a synchronous child would block the server that must answer it).

const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
const png = (file) => { const d = fs.readFileSync(file); return { width: d.readUInt32BE(16), height: d.readUInt32BE(20) }; };
/** Width and height of a baseline or progressive JPEG, read from its start-of-frame marker. */
function jpeg(file) {
  const d = fs.readFileSync(file);
  assert.ok(d[0] === 0xff && d[1] === 0xd8 && d[2] === 0xff, `${file} is not a JPEG`);
  for (let i = 2; i + 9 < d.length;) {
    assert.equal(d[i], 0xff, "marker");
    const m = d[i + 1];
    if (m === 0xc0 || m === 0xc2) return { width: d.readUInt16BE(i + 7), height: d.readUInt16BE(i + 5) };
    i += 2 + d.readUInt16BE(i + 2);
  }
  throw new Error(`${file} has no start-of-frame marker`);
}
const record = (dir) => JSON.parse(fs.readFileSync(path.join(dir, "capture.json"), "utf8"));

function bcAsync(args, env = {}) {
  return new Promise((resolve, reject) => {
    const c = spawn(BIN, ["--data", DATA, ...args], { env: { ...process.env, BRAND_CREATOR_TODAY: "2026-10-17", ...env } });
    let stdout = "", stderr = "";
    c.stdout.on("data", (d) => { stdout += d; });
    c.stderr.on("data", (d) => { stderr += d; });
    c.on("error", reject);
    c.on("close", (status) => resolve({ status, stdout, stderr }));
  });
}

function listen(handler) {
  const hits = [];
  const srv = http.createServer((req, res) => { hits.push(req.url); handler(req, res); });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok({ hits, port: srv.address().port, close: () => new Promise((done) => srv.close(done)) })));
}

const TALL = "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + "<body><h1>Ledger</h1><img src=mark.svg width=40 height=40 alt=''><div class=tall></div><p>The bottom.</p></body></html>";
const CSS = "body{font:18px/1.4 sans-serif;margin:2rem;background:#fff;color:#111}@media (prefers-color-scheme:dark){body{background:#111;color:#eee}}.tall{height:2600px;background:#ccc}";
const MARK = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><rect width='10' height='10' fill='#c03'/></svg>";

function writePage(p, dir = "rounds/r1/Ledger", html = TALL) {
  fs.mkdirSync(path.join(p, dir), { recursive: true });
  fs.writeFileSync(path.join(p, dir, "index.html"), html);
  fs.writeFileSync(path.join(p, dir, "style.css"), CSS);
  fs.writeFileSync(path.join(p, dir, "mark.svg"), MARK);
  return `${dir}/index.html`;
}

test("capture: a project page gets four first-screen stills, a full page and a record of what it loaded", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const page = writePage(p);
  const r = bc(["capture", page, "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const dir = path.join(p, "rounds/r1/Ledger/shots");                       // fixed: beside the page
  assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", "capture.json"]);
  assert.deepEqual(png(path.join(dir, "1440-light.png")), { width: 1440, height: 900 });
  assert.deepEqual(png(path.join(dir, "1440-dark.png")), { width: 1440, height: 900 });
  assert.deepEqual(png(path.join(dir, "390-light.png")), { width: 390, height: 844 });
  assert.deepEqual(png(path.join(dir, "390-dark.png")), { width: 390, height: 844 });
  const rec = record(dir);
  assert.equal(rec.schema, 1);
  assert.equal(rec.tool, "capture");
  assert.deepEqual(rec.source, { page: page });
  assert.equal(rec.date, "2026-10-17");
  assert.deepEqual(rec.views.map((v) => [v.view, v.width, v.height, v.scheme, v.file]),
    [["1440-light", 1440, 900, "light", "1440-light.png"], ["1440-dark", 1440, 900, "dark", "1440-dark.png"],
      ["390-light", 390, 844, "light", "390-light.png"], ["390-dark", 390, 844, "dark", "390-dark.png"]]);
  for (const v of rec.views) assert.equal(v.sha256, sha(fs.readFileSync(path.join(dir, v.file))), v.view);
  assert.notEqual(rec.views[0].sha256, rec.views[1].sha256, "the dark scheme must change the picture, or the stills prove nothing");
  const full = png(path.join(dir, "1440-light-full.png"));
  assert.equal(full.width, 1440);
  assert.ok(full.height > 2600, `the full page is the whole page, not the first screen: ${full.height}`);
  assert.deepEqual(rec.full, { file: "1440-light-full.png", sha256: sha(fs.readFileSync(path.join(dir, "1440-light-full.png"))), height: full.height, cut: false });
  // what the page loaded: the page, its stylesheet and its picture, as project paths; nothing else
  assert.deepEqual(rec.inputs.map((i) => i.path), ["rounds/r1/Ledger/index.html", "rounds/r1/Ledger/mark.svg", "rounds/r1/Ledger/style.css"]);
  for (const i of rec.inputs) assert.equal(i.sha256, sha(fs.readFileSync(path.join(p, i.path))), i.path);
  assert.deepEqual(rec.problems, []);
  assert.ok(!fs.existsSync(path.join(p, "assets/_checks/capture.json")), "capture writes no report");
  assert.ok(!fs.existsSync(path.join(p, "assets/_checks/capture")), "capture writes no report");
});

test("capture: a non-local request on a project page is recorded, never fetched", async (t) => {
  if (needSetup(t)) return;
  const other = await listen((req, res) => { res.writeHead(200, { "content-type": "image/svg+xml" }); res.end(MARK); });
  try {
    const p = makeProject();
    const foreign = `http://127.0.0.1:${other.port}/outside.svg`;
    const page = writePage(p, "rounds/r1/Ledger", TALL.replace("<div class=tall>", `<img src="${foreign}" width=20 height=20 alt=''><div class=tall>`));
    const r = await bcAsync(["capture", page, "--project", p]);
    assert.equal(r.status, 0, r.stdout + r.stderr);                                   // recorded, not gated: page-check gates the page
    assert.match(r.stdout, /problem while loading: non-local request: http:\/\/127\.0\.0\.1:\d+\/outside\.svg/);
    assert.deepEqual(record(path.join(p, "rounds/r1/Ledger/shots")).problems, [`non-local request: ${foreign}`]);
    assert.deepEqual(other.hits, [], "the other origin must not hear from the browser");
  } finally {
    await other.close();
  }
});

test("capture: a second run on an unchanged page leaves capture.json byte for byte", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const page = writePage(p);
  const dir = path.join(p, "rounds/r1/Ledger/shots");
  assert.equal(bc(["capture", page, "--project", p]).status, 0);
  const files = fs.readdirSync(dir).sort();
  const before = Object.fromEntries(files.map((f) => [f, fs.readFileSync(path.join(dir, f))]));
  const mtimes = Object.fromEntries(files.map((f) => [f, fs.statSync(path.join(dir, f)).mtimeMs]));
  const again = bc(["capture", page, "--project", p], { env: { BRAND_CREATOR_TODAY: "2026-11-30" } });   // another day: the date of the record must not move
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /\(0 of 6 file\(s\) written, the others unchanged\)/);
  assert.deepEqual(fs.readdirSync(dir).sort(), files);
  for (const f of files) {
    assert.ok(Buffer.compare(fs.readFileSync(path.join(dir, f)), before[f]) === 0, f);
    assert.equal(fs.statSync(path.join(dir, f)).mtimeMs, mtimes[f], `${f} must not be rewritten`);
  }
  assert.equal(record(dir).date, "2026-10-17");
  // a change to what the page loads does rewrite the record, with the new date
  fs.appendFileSync(path.join(p, "rounds/r1/Ledger/style.css"), "p{color:#036}");
  const changed = bc(["capture", page, "--project", p], { env: { BRAND_CREATOR_TODAY: "2026-11-30" } });
  assert.equal(changed.status, 0, changed.stdout + changed.stderr);
  const rec = record(dir);
  assert.equal(rec.date, "2026-11-30");
  assert.equal(rec.inputs.find((i) => i.path.endsWith("style.css")).sha256, sha(fs.readFileSync(path.join(p, "rounds/r1/Ledger/style.css"))));
  // a page that loads one of its own stills still comes to rest: the stills are not among the inputs
  const own = writePage(p, "rounds/r1/Own", TALL.replace("<p>The bottom.</p>", "<img src=shots/390-light.png style='display:none' alt=''><p>The bottom.</p>"));
  assert.equal(bc(["capture", own, "--project", p]).status, 0);                    // the first run cannot find it yet (a problem is recorded); the second can
  assert.equal(bc(["capture", own, "--project", p]).status, 0);
  const settled = fs.readFileSync(path.join(p, "rounds/r1/Own/shots/capture.json"));
  assert.equal(bc(["capture", own, "--project", p], { env: { BRAND_CREATOR_TODAY: "2026-12-24" } }).status, 0);
  assert.ok(Buffer.compare(fs.readFileSync(path.join(p, "rounds/r1/Own/shots/capture.json")), settled) === 0);
  assert.ok(!JSON.parse(settled).inputs.some((i) => i.path.includes("/shots/")), "the stills of a page are not its inputs");
});

test("capture --url: a page served over http is captured into research/site-refs with its thumbnails", async (t) => {
  if (needSetup(t)) return;
  const site = await listen((req, res) => {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(`<!doctype html><html><head><meta charset=utf-8><title>${"A local reference, with a long title ".repeat(5)}</title><style>${CSS}</style></head>`
      + "<body><h1>A local reference</h1><div class=tall></div><p>The bottom.</p></body></html>");
  });
  try {
    const p = makeProject();
    assert.equal(bc(["state", "--set", "site_research=links-only", "--project", p]).status, 0);
    const address = `http://127.0.0.1:${site.port}/`;
    const r = await bcAsync(["capture", "--url", address, "--name", "local-demo", "--project", p]);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    const dir = path.join(p, "research/site-refs/local-demo");
    assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-full.png", "1440.png", "390.png", "capture.json", "thumb-1440.jpg", "thumb-390.jpg"]);
    assert.deepEqual(png(path.join(dir, "1440.png")), { width: 1440, height: 900 });
    assert.deepEqual(png(path.join(dir, "390.png")), { width: 390, height: 844 });
    const full = png(path.join(dir, "1440-full.png"));
    assert.equal(full.width, 1440);
    assert.ok(full.height > 2600, `${full.height}`);
    assert.equal(jpeg(path.join(dir, "thumb-1440.jpg")).width, 480);
    assert.equal(jpeg(path.join(dir, "thumb-390.jpg")).width, 160);
    const rec = record(dir);
    assert.equal(rec.schema, 1);
    assert.equal(rec.tool, "capture");
    assert.equal(rec.source.url, address);
    assert.equal(rec.source.final_url, address);
    assert.equal(rec.source.status, 200);
    assert.equal(rec.source.title.length, 120, "the title is cut at 120 characters");
    assert.ok(rec.source.title.startsWith("A local reference, with a long title"));
    assert.deepEqual(rec.views.map((v) => [v.view, v.width, v.height, v.file]), [["1440", 1440, 900, "1440.png"], ["390", 390, 844, "390.png"]]);
    for (const v of rec.views) assert.equal(v.sha256, sha(fs.readFileSync(path.join(dir, v.file))), v.view);
    assert.deepEqual(rec.full, { file: "1440-full.png", sha256: sha(fs.readFileSync(path.join(dir, "1440-full.png"))), height: full.height, cut: false });
    assert.deepEqual(rec.thumbs.map((x) => [x.file, x.width]), [["thumb-1440.jpg", 480], ["thumb-390.jpg", 160]]);
    for (const x of rec.thumbs) assert.equal(x.sha256, sha(fs.readFileSync(path.join(dir, x.file))), x.file);
    assert.ok(!fs.existsSync(path.join(p, "assets/_checks/capture.json")) && !fs.existsSync(path.join(p, "assets/_checks/capture")), "capture writes no report");
    // the same address again is taken again in the same folder; another address under the same name is refused, and nothing of the first changes
    const again = await bcAsync(["capture", "--url", address, "--name", "local-demo", "--project", p]);
    assert.equal(again.status, 0, again.stdout + again.stderr);
    assert.match(again.stdout, /\(0 of 6 file\(s\) written, the others unchanged\)/);
    const other = await bcAsync(["capture", "--url", `${address}elsewhere`, "--name", "local-demo", "--project", p]);
    assert.equal(other.status, 2, other.stdout + other.stderr);
    assert.match(other.stderr, /research\/site-refs\/local-demo\/ already holds a capture of http:\/\/127\.0\.0\.1:\d+\/: use another --name/);
    assert.equal(record(dir).source.url, address);
  } finally {
    await site.close();
  }
});

test("capture --url: a second run on an unchanged reference keeps capture.json byte for byte, whatever the day, and a changed reference rewrites it with the new date", async (t) => {
  if (needSetup(t)) return;
  let title = "A local reference";
  const site = await listen((req, res) => {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(`<!doctype html><html><head><meta charset=utf-8><title>${title}</title><style>${CSS}</style></head><body><h1>A local reference</h1><div class=tall></div><p>The bottom.</p></body></html>`);
  });
  try {
    const p = makeProject();
    assert.equal(bc(["state", "--set", "site_research=links-only", "--project", p]).status, 0);
    const args = ["capture", "--url", `http://127.0.0.1:${site.port}/`, "--name", "local-demo", "--project", p];
    const dir = path.join(p, "research/site-refs/local-demo"), file = path.join(dir, "capture.json");
    const first = await bcAsync(args);                                                    // 2026-10-17
    assert.equal(first.status, 0, first.stdout + first.stderr);
    assert.match(first.stdout, /\(6 of 6 file\(s\) written, the others unchanged\)/);
    const before = fs.readFileSync(file), mtime = fs.statSync(file).mtimeMs;
    const files = fs.readdirSync(dir).sort();
    const again = await bcAsync(args, { BRAND_CREATOR_TODAY: "2026-11-30" });             // another day, the same reference: nothing is rewritten
    assert.equal(again.status, 0, again.stdout + again.stderr);
    assert.match(again.stdout, /\(0 of 6 file\(s\) written, the others unchanged\)/);
    assert.ok(Buffer.compare(fs.readFileSync(file), before) === 0, "capture.json must be byte for byte what it was");
    assert.equal(fs.statSync(file).mtimeMs, mtime, "capture.json must not be rewritten");
    assert.equal(record(dir).date, "2026-10-17");
    assert.deepEqual(fs.readdirSync(dir).sort(), files);
    // the reference changes (its title, which no still shows): the record is rewritten, with the new day
    title = "Another title";
    const changed = await bcAsync(args, { BRAND_CREATOR_TODAY: "2026-12-24" });
    assert.equal(changed.status, 0, changed.stdout + changed.stderr);
    assert.match(changed.stdout, /\(1 of 6 file\(s\) written, the others unchanged\)/);
    assert.equal(record(dir).date, "2026-12-24");
    assert.equal(record(dir).source.title, "Another title");
  } finally {
    await site.close();
  }
});

test("capture --url: a 404 writes nothing and exits 1", async (t) => {
  if (needSetup(t)) return;
  const site = await listen((req, res) => { res.writeHead(404, { "content-type": "text/html" }); res.end("<!doctype html><title>Not found</title><h1>No such page</h1>"); });
  try {
    const p = makeProject();
    assert.equal(bc(["state", "--set", "site_research=online", "--project", p]).status, 0);
    const address = `http://127.0.0.1:${site.port}/missing`;
    const r = await bcAsync(["capture", "--url", address, "--name", "gone-site", "--project", p]);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.ok(r.stderr.includes(`could not capture ${address}: the site answered 404; leave the reference out or ask the owner for a screenshot`), r.stderr);
    assert.ok(!fs.existsSync(path.join(p, "research/site-refs")), "nothing is written for a site that does not load");
    assert.ok(site.hits.length >= 1, "the site was asked");
  } finally {
    await site.close();
  }
});

// ---------------------------------------------------------------- capture <page> --frames: key frames of the first screen (group 4, G4-04)
// The pages are small ones of this test: a hero that rises in when it loads (1500 ms: the page is first looked at some time after it loaded, and on a busy machine that is later than 600 ms), and pages that move in ways that give no frame.

const MOVING = "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + "<body><h1 class=rise>Ledger</h1><p class=rise>A hero that rises in when the page loads.</p></body></html>";
const MOVING_CSS = CSS + "@keyframes rise{from{opacity:0;transform:translateY(160px)}to{opacity:1;transform:none}}.rise{animation:rise 1500ms ease-out both}h1{font-size:96px}";
const FRAME_FILES = ["frame-1440-0.png", "frame-1440-100.png", "frame-1440-50.png"];

function writeMoving(p, dir, css, html = MOVING) {
  const page = writePage(p, dir, html);
  fs.writeFileSync(path.join(p, dir, "style.css"), css);
  return page;
}

test("capture --frames: a page with an entrance animation gets three key frames that differ, listed in capture.json", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const page = writeMoving(p, "rounds/r1/Rise", MOVING_CSS);
  const dir = path.join(p, "rounds/r1/Rise/shots");
  const r = bc(["capture", page, "--project", p, "--frames"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", ...FRAME_FILES, "capture.json"].sort());
  assert.match(r.stdout, /8 stills and capture\.json in rounds\/r1\/Rise\/shots\/ \(9 of 9 file\(s\) written, the others unchanged\)/);
  assert.match(r.stdout, /key frames: 3 of the first screen \(1440, light\) at 0, 50, 100 % of 1500 ms/);
  for (const f of FRAME_FILES) assert.deepEqual(png(path.join(dir, f)), { width: 1440, height: 900 }, f);
  const bytes = FRAME_FILES.map((f) => fs.readFileSync(path.join(dir, f)));
  assert.equal(new Set(bytes.map(sha)).size, 3, "the three frames must differ: a frame that equals another shows no motion");
  assert.ok(Buffer.compare(fs.readFileSync(path.join(dir, "frame-1440-100.png")), fs.readFileSync(path.join(dir, "1440-light.png"))) === 0, "the frame at 100 % is the first screen at rest, as the still takes it");
  const rec = record(dir);
  assert.deepEqual(rec.frames.map((f) => [f.percent, f.ms, f.file]), [[0, 0, "frame-1440-0.png"], [50, 750, "frame-1440-50.png"], [100, 1500, "frame-1440-100.png"]]);
  for (const f of rec.frames) assert.equal(f.sha256, sha(fs.readFileSync(path.join(dir, f.file))), f.file);
  assert.deepEqual(rec.views.map((v) => v.file), ["1440-light.png", "1440-dark.png", "390-light.png", "390-dark.png"], "the four views are as they were");
  assert.ok(!rec.inputs.some((i) => i.path.includes("/shots/")), "the frames are not inputs of the page");
  // taken again, nothing changes: the frames are seeked, not waited for
  const again = bc(["capture", page, "--project", p, "--frames"], { env: { BRAND_CREATOR_TODAY: "2026-11-30" } });
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /\(0 of 9 file\(s\) written, the others unchanged\)/);
  assert.equal(record(dir).date, "2026-10-17");
  // a plain run leaves the frame files where they are and says they are not part of it; capture.json no longer lists them
  const plain = bc(["capture", page, "--project", p]);
  assert.equal(plain.status, 0, plain.stdout + plain.stderr);
  assert.match(plain.stdout, /frame-1440-0\.png, frame-1440-50\.png, frame-1440-100\.png in rounds\/r1\/Rise\/shots\/ are from an earlier run and not part of this one/);
  assert.ok(!("frames" in record(dir)));
  assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", ...FRAME_FILES, "capture.json"].sort());
});

test("capture --frames: a static page, a page whose animations never end and one that holds its animation paused get no frame, and the run says so", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const cases = [
    ["Still", CSS, TALL, /key frames: none written: no animation runs on load/],
    ["Spin", CSS + "@keyframes spin{to{transform:rotate(360deg)}}.rise{animation:spin 2s linear infinite}",
      MOVING, /key frames: none written: every animation that runs on load repeats forever or has no length/],
    ["Held", MOVING_CSS.replace("both}", "both paused}"), MOVING, /key frames: none written: no animation runs on load/],
  ];
  for (const [name, css, html, said] of cases) {
    const page = writeMoving(p, `rounds/r1/${name}`, css, html);
    const dir = path.join(p, `rounds/r1/${name}/shots`);
    const r = bc(["capture", page, "--project", p, "--frames"]);
    assert.equal(r.status, 0, name + r.stdout + r.stderr);
    assert.match(r.stdout, said, name);
    assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", "capture.json"], name);
    assert.ok(!("frames" in record(dir)), `${name}: capture.json lists no frame`);
    assert.match(r.stdout, /6 stills and capture\.json|5 stills and capture\.json/, name);
  }
  // a plain run says nothing about frames
  const plain = bc(["capture", "rounds/r1/Still/index.html", "--project", p]);
  assert.equal(plain.status, 0, plain.stdout + plain.stderr);
  assert.ok(!/key frames/.test(plain.stdout), plain.stdout);
});

test("capture --frames: a finite animation beside an infinite one gives frames, and the longest finite one sets the length", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = MOVING_CSS + "@keyframes spin{to{transform:rotate(360deg)}}.spin{animation:spin 2s linear infinite;width:80px;height:80px;background:#c03}";
  const page = writeMoving(p, "rounds/r1/Both", css, MOVING.replace("</body>", "<div class=spin></div></body>"));
  const dir = path.join(p, "rounds/r1/Both/shots");
  const r = bc(["capture", page, "--project", p, "--frames"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /key frames: 3 of the first screen \(1440, light\) at 0, 50, 100 % of 1500 ms/, "the longest finite animation sets the length, not the infinite one");
  assert.deepEqual(record(dir).frames.map((f) => f.ms), [0, 750, 1500]);
});

// A script that starts the motion once the page is up: a CSS transition (a class added after 300 ms, or after two animation frames) and element.animate. The heading starts invisible and 300 px to the left, so the
// first frame must be the page without the heading, which `Blank` below is (the same page, static, its heading at opacity 0): an exact oracle, not a guess at "different enough".
const ENTER_HTML = (script) => "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + `<body><h1 class=hero>Ledger</h1><p>A heading that comes in once the page is up.</p><script>${script}</script></body></html>`;
const ENTER_CSS = (hero) => CSS + `h1{font-size:96px}.hero{opacity:0;transform:translateX(-300px)${hero}}`;
const ENTER_TRANSITION = ENTER_CSS(";transition:opacity 800ms,transform 800ms") + ".hero.in{opacity:1;transform:none}";
const ENTER_STARTERS = [
  ["a transition started by a timer", ENTER_HTML("setTimeout(() => document.querySelector('h1').classList.add('in'), 300)"), ENTER_TRANSITION, 800],
  ["a transition started after two animation frames", ENTER_HTML("requestAnimationFrame(() => requestAnimationFrame(() => document.querySelector('h1').classList.add('in')))"), ENTER_TRANSITION, 800],
  ["element.animate", ENTER_HTML("document.querySelector('h1').animate([{ opacity: 0, transform: 'translateX(-300px)' }, { opacity: 1, transform: 'none' }], { duration: 800, fill: 'both' })"),
    ENTER_CSS(""), 800],
];

test("capture --frames: a motion a script starts when the page loads (a CSS transition, element.animate) is seeked: the first frame is the page before it, the middle one is in between, the last is the page at rest", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const blankPage = writeMoving(p, "rounds/r1/Blank", ENTER_CSS(""), ENTER_HTML(""));
  const blank = bc(["capture", blankPage, "--project", p]);
  assert.equal(blank.status, 0, blank.stdout + blank.stderr);
  const before = fs.readFileSync(path.join(p, "rounds/r1/Blank/shots/1440-light.png"));
  ENTER_STARTERS.forEach(([what, html, css, ms], i) => {
    const page = writeMoving(p, `rounds/r1/Enter${i}`, css, html);
    const dir = path.join(p, `rounds/r1/Enter${i}/shots`);
    const r = bc(["capture", page, "--project", p, "--frames"]);
    assert.equal(r.status, 0, what + r.stdout + r.stderr);
    assert.match(r.stdout, new RegExp(`key frames: 3 of the first screen \\(1440, light\\) at 0, 50, 100 % of ${ms} ms`), what);
    const [f0, f50, f100, rest] = ["frame-1440-0.png", "frame-1440-50.png", "frame-1440-100.png", "1440-light.png"].map((f) => fs.readFileSync(path.join(dir, f)));
    assert.equal(new Set([f0, f50, f100].map(sha)).size, 3, `${what}: the three frames must differ`);
    assert.ok(Buffer.compare(f0, before) === 0, `${what}: the frame at 0 % is the page before the heading comes in (the heading is not there yet), not the heading already on its way`);
    assert.notEqual(sha(f0), sha(rest), `${what}: the frame at 0 % differs from the still at rest`);
    assert.ok(Buffer.compare(f100, rest) === 0, `${what}: the frame at 100 % is the page at rest, as the still takes it`);
    assert.notEqual(sha(f50), sha(before), `${what}: the frame at 50 % shows the heading on its way`);
    assert.notEqual(sha(f50), sha(rest), `${what}: the frame at 50 % is not the page at rest`);
  });
});

test("capture --frames: it goes with a page of the project, not with --url", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const r = bc(["capture", "--url", "http://127.0.0.1:9/", "--name", "nowhere", "--frames", "--project", p]);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.match(r.stderr, /--frames goes with a page of the project, not with --url/);
  assert.ok(!fs.existsSync(path.join(p, "research/site-refs")), "nothing is written");
});

// ---------------------------------------------------------------- capture <page> --reveal: what the page shows once it is scrolled into view (group 5)
// A section that is hidden until an IntersectionObserver sees it. It is tall, far below the first screen and painted red (#c03), so a still shows it or not by a count of red pixels.

/** The number of pixels of a PNG (8 bit, RGB or RGBA, not interlaced: what Chromium writes) that are the brand red #c03. */
function redPixels(file) {
  const d = fs.readFileSync(file);
  assert.equal(d[24], 8, "8 bit PNG"); assert.equal(d[28], 0, "not interlaced");
  const bpp = d[25] === 6 ? 4 : 3, w = d.readUInt32BE(16), h = d.readUInt32BE(20);
  const chunks = [];
  for (let i = 8; i < d.length;) { const n = d.readUInt32BE(i), type = d.toString("latin1", i + 4, i + 8); if (type === "IDAT") chunks.push(d.subarray(i + 8, i + 8 + n)); i += 12 + n; }
  const raw = zlib.inflateSync(Buffer.concat(chunks)), stride = w * bpp, out = Buffer.alloc(stride * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? out[y * stride + x - bpp] : 0, b = y ? out[(y - 1) * stride + x] : 0, c = x >= bpp && y ? out[(y - 1) * stride + x - bpp] : 0;
      const pa = Math.abs(b - c), pb = Math.abs(a - c), pc = Math.abs(a + b - 2 * c);
      const pred = [0, a, b, (a + b) >> 1, pa <= pb && pa <= pc ? a : pb <= pc ? b : c][f];
      out[y * stride + x] = (line[x] + pred) & 255;
    }
  }
  let n = 0;
  for (let i = 0; i < out.length; i += bpp) if (out[i] === 0xcc && out[i + 1] === 0 && out[i + 2] === 0x33) n++;
  return n;
}

const REVEAL_HTML = "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + "<body><h1>Ledger</h1><div class=tall></div><section class=late>Late</section>"
  + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script></body></html>";
const REVEAL_CSS = CSS + ".tall{height:1500px}.late{height:300px;background:#c03;opacity:0;transition:opacity 200ms}.late.in{opacity:1}";

test("capture --reveal: a section that appears only when scrolled into view is hidden in the stills without the flag and shown with it, and a second run writes the same bytes", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const page = writeMoving(p, "rounds/r1/Late", REVEAL_CSS, REVEAL_HTML);
  const dir = path.join(p, "rounds/r1/Late/shots");
  const plain = bc(["capture", page, "--project", p]);
  assert.equal(plain.status, 0, plain.stdout + plain.stderr);
  assert.equal(redPixels(path.join(dir, "1440-light-full.png")), 0, "without --reveal the section is still hidden");
  assert.ok(!("reveal" in record(dir)), "a plain run records no reveal");
  assert.ok(!/reveal/.test(plain.stdout), plain.stdout);
  const r = bc(["capture", page, "--project", p, "--reveal"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(redPixels(path.join(dir, "1440-light-full.png")) > 1440 * 300 * 0.9, "with --reveal the full page shows the section");
  assert.equal(redPixels(path.join(dir, "1440-light.png")), 0, "the first screen is taken back at the top: the section is below it");
  assert.equal(redPixels(path.join(dir, "390-dark.png")), 0);
  const rec = record(dir);
  assert.equal(rec.reveal.capped, false);
  assert.ok(rec.reveal.steps >= 2, JSON.stringify(rec.reveal));
  assert.match(r.stdout, /reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen/);
  assert.ok(!/CAPPED/.test(r.stdout), r.stdout);
  const before = fs.readFileSync(path.join(dir, "capture.json"));
  const again = bc(["capture", page, "--project", p, "--reveal"], { env: { BRAND_CREATOR_TODAY: "2026-11-30" } });
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /0 of 6 file\(s\) written/);
  assert.ok(fs.readFileSync(path.join(dir, "capture.json")).equals(before), "capture.json stays byte for byte, its date included");
});

test("capture --reveal: the walk waits at every step, so a section a scroll handler reveals a moment after the scroll stops is shown", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // the handler waits 150 ms after the last scroll event, then reveals the section if it is in view: a walk that did not wait at each step would be back at the top by then
  const html = REVEAL_HTML.replace(/<script>.*<\/script>/, "<script>let t;addEventListener('scroll',()=>{clearTimeout(t);t=setTimeout(()=>{const s=document.querySelector('.late'),r=s.getBoundingClientRect();if(r.top<innerHeight&&r.bottom>0)s.classList.add('in')},150)})</script>");
  const page = writeMoving(p, "rounds/r1/Debounced", REVEAL_CSS.replace("transition:opacity 200ms", ""), html);
  const r = bc(["capture", page, "--project", p, "--reveal"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(redPixels(path.join(p, "rounds/r1/Debounced/shots/1440-light-full.png")) > 1440 * 300 * 0.9, "the section revealed 150 ms after the scroll is in the full page");
});

test("capture --reveal: a walk that takes longer than --timeout stops there and says so", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // every scroll starts a finite 1.2 s animation, which the walk waits for at each step: with --timeout 1000 the walk of a very long page stops after its first step
  const html = REVEAL_HTML.replace(/<script>.*<\/script>/, "<script>addEventListener('scroll',()=>document.querySelector('h1').animate([{opacity:0.5},{opacity:1}],{duration:1200}))</script>");
  const page = writeMoving(p, "rounds/r1/Slow", REVEAL_CSS.replace(".tall{height:1500px}", ".tall{height:60000px}"), html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", "--timeout", "1000"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const rec = record(path.join(p, "rounds/r1/Slow/shots"));
  assert.equal(rec.reveal.capped, true); assert.equal(rec.reveal.timed_out, true);
  assert.ok(rec.reveal.steps < 40, JSON.stringify(rec.reveal));
  assert.match(r.stdout, /CAPPED: a walk took longer than --timeout/);
});

test("capture --reveal: a page that scrolls inside an element has that element walked, and a page with overflow hidden is still walked (a script can scroll it), never called long", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const snap = REVEAL_CSS + "html,body{height:100%;margin:0;overflow:hidden}main{height:100%;overflow-y:scroll;scroll-snap-type:y mandatory}";
  const html = REVEAL_HTML.replace("<body><h1>Ledger</h1><div class=tall></div><section class=late>Late</section>", "<body><main><h1>Ledger</h1><div class=tall></div><section class=late>Late</section></main>");
  const page = writeMoving(p, "rounds/r1/Snap", snap, html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const rec = record(path.join(p, "rounds/r1/Snap/shots"));
  assert.equal(rec.reveal.boxes, 1, JSON.stringify(rec.reveal));
  assert.ok(rec.reveal.steps >= 1 && !rec.reveal.not_scrolled, JSON.stringify(rec.reveal));
  assert.match(r.stdout, /inside 1 box that scrolls/);
  const clipped = writeMoving(p, "rounds/r1/Clipped", REVEAL_CSS + "html{overflow:hidden}", REVEAL_HTML);
  const c = bc(["capture", clipped, "--project", p, "--reveal", "--wait", "0"]);
  assert.equal(c.status, 0, c.stdout + c.stderr);
  const crec = record(path.join(p, "rounds/r1/Clipped/shots"));
  assert.ok(crec.reveal.steps >= 1 && !crec.reveal.not_scrolled && crec.reveal.capped === false, JSON.stringify(crec.reveal));
  assert.ok(!/CAPPED|NOT SCROLLED/.test(c.stdout), c.stdout);
  assert.equal(crec.reveal.root_hidden, true, "a root with overflow hidden is walked, and the record says a visitor cannot scroll it");
  assert.match(c.stdout, /NOTE: the page's own scrolling is hidden or clipped.*a visitor cannot scroll it with the wheel/);
});

test("capture --reveal: a page longer than the walk is walked as far as the cap allows and says so; --url refuses the flag", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = REVEAL_CSS.replace(".tall{height:1500px}", ".tall{height:60000px}");
  const page = writeMoving(p, "rounds/r1/Long", css, REVEAL_HTML);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const rec = record(path.join(p, "rounds/r1/Long/shots"));
  assert.deepEqual(rec.reveal, { steps: 80, capped: true, page_unfinished: true });
  assert.match(r.stdout, /CAPPED: the page is longer than 40 screens/);
  const url = bc(["capture", "--url", "http://127.0.0.1:9/", "--name", "nowhere", "--reveal", "--project", p]);
  assert.equal(url.status, 2, url.stdout + url.stderr);
  assert.match(url.stdout + url.stderr, /--reveal goes with a page of the project/);
});

// ---------------------------------------------------------------- capture --reveal: the walk of 0.9.0 (dev/specs/2026-11-05-g6-reveal-walk-design.md), one test per layout
// Each page is walked with --wait 0 (the walk itself waits two frames after each step). The record is checked whole: its counts are those of the layout's geometry
// (a step is half of what the screen shows of a scroller: 450 px at 900, 422 px at 844). Box content below a box's first screen is in no still (each box is shown
// at its top), so a box's walk is seen through a page-wide effect: once every item has been seen by a viewport IntersectionObserver (with the options given), body
// gets .seen and the fixed 50 px header turns red (#c03) in the first screen.

const LAYOUT = (body) => `<!doctype html><html><head><meta charset=utf-8><title>Ledger, a layout</title><link rel=stylesheet href=style.css></head><body>${body}</body></html>`;
const ITEMS = (n, h, cls = "i") => `<div class=${cls} style="height:${h}px"></div>`.repeat(n);
const SEEN_HEADER = "header.seen-bar{position:fixed;top:0;left:0;right:0;height:50px;z-index:1}body.seen header.seen-bar{background:#c03}";
const SEEN_SCRIPT = (n, options = "{}") => `<script>let seen=0;const o=new IntersectionObserver((es)=>es.forEach((e)=>{if(e.isIntersecting){o.unobserve(e.target);if(++seen===${n})document.body.classList.add('seen')}}),${options});document.querySelectorAll('.i').forEach((e)=>o.observe(e))</script>`;
const RED_BAND = "<div style='height:100px;background:#c03'></div>";

/** capture --reveal --wait 0 of one layout -> {r: the run, rec: capture.json's reveal, shots: the folder}. */
function revealLayout(p, name, css, html, more = []) {
  const page = writeMoving(p, `rounds/r1/${name}`, CSS + "body{margin:0}" + css, html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", ...more]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const shots = path.join(p, `rounds/r1/${name}/shots`);
  return { r, rec: record(shots).reveal, shots };
}

test("capture --reveal: plain short page: nothing to scroll, and the run says so", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Short", "", LAYOUT(ITEMS(1, 500, "p")));
  assert.deepEqual(rec, { steps: 0, capped: false });
  assert.match(r.stdout, /reveal: nothing to scroll: in every load the page fits its screen and holds no box that scrolls/);
});

test("capture --reveal: body that scrolls itself: walked as a box, never 'scrolled' with no step", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "BodyScrolls", "html{overflow:hidden;height:100%}body{height:100%;overflow-y:auto}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.match(r.stdout, /6 steps at most, of 80 allowed; up to 6 of them inside 1 box that scrolls/);
});

test("capture --reveal: overflow-x:hidden body: its overflow is the window's, so the window is walked and no box", (t) => {
  if (needSetup(t)) return;
  const { rec } = revealLayout(makeProject(), "BodyOverflowX", "html,body{height:100%}body{overflow-x:hidden}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false });
});

test("capture --reveal: html overflow hidden + full-height main, scroll-snap (mandatory, proximity), scroll-behavior smooth (html, box): every step lands, every box back at its top", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const full = "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}";
  const sections = (n, h) => `<main>${Array.from({ length: n }, (_, k) => `<section style="height:${h};scroll-snap-align:start">${k ? "" : RED_BAND}</section>`).join("")}</main>`;
  const cases = {
    FullMain: [full, LAYOUT(`<main>${RED_BAND}${ITEMS(4, 975, "p")}</main>`), { steps: 8, capped: false, boxes: 1, box_steps: 8 }],
    SnapMandatory: [full + "main{scroll-snap-type:y mandatory}", LAYOUT(sections(4, "100%")), { steps: 6, capped: false, boxes: 1, box_steps: 6 }],
    SnapProximity: [full + "main{scroll-snap-type:y proximity}", LAYOUT(sections(6, "70%")), { steps: 7, capped: false, boxes: 1, box_steps: 7 }],
    SmoothBox: [full + "main{scroll-behavior:smooth}", LAYOUT(`<main>${RED_BAND}${ITEMS(4, 975, "p")}</main>`), { steps: 8, capped: false, boxes: 1, box_steps: 8 }],
    SmoothHtml: ["html{scroll-behavior:smooth}", LAYOUT(`${RED_BAND}${ITEMS(4, 975, "p")}`), { steps: 8, capped: false }],
  };
  for (const [name, [css, html, want]] of Object.entries(cases)) {
    const { rec, shots } = revealLayout(p, name, css, html);
    assert.deepEqual(rec, want, name);
    assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 100 * 0.9, `${name}: the first screen shows the top of the page`);
  }
});

test("capture --reveal: main under a 60 px header and under a 220 px header: the window's 60 px and the main are both walked", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const a = revealLayout(p, "Header60", "header{height:60px}main{height:100vh;overflow-y:auto}", LAYOUT(`<header></header><main>${ITEMS(3, 1000, "p")}</main>`));
  assert.deepEqual(a.rec, { steps: 7, capped: false, boxes: 1, box_steps: 6 });
  const b = revealLayout(p, "Header220", "html,body{height:100%;overflow:hidden}body{display:flex;flex-direction:column}header{height:220px;flex:none}main{flex:1;overflow-y:auto}",
    LAYOUT(`<header></header><main>${ITEMS(3, 1000, "p")}</main>`));
  assert.deepEqual(b.rec, { steps: 8, capped: false, boxes: 1, box_steps: 8 });
});

test("capture --reveal: sticky full-height sidebar on a short and on a long page: the sidebar and the window are both walked", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = "body{display:flex;align-items:flex-start}aside{position:sticky;top:0;height:100vh;overflow-y:auto;width:200px;flex:none}main{flex:1}";
  assert.deepEqual(revealLayout(p, "StickyShort", css, LAYOUT(`<aside>${ITEMS(3, 1000, "a")}</aside><main>${ITEMS(1, 500, "p")}</main>`)).rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.deepEqual(revealLayout(p, "StickyLong", css, LAYOUT(`<aside>${ITEMS(3, 1000, "a")}</aside><main>${ITEMS(5, 1000, "p")}</main>`)).rec, { steps: 16, capped: false, boxes: 1, box_steps: 6 });
});

test("capture --reveal: code box with max-height in a long page, and nested full-screen main with a max-height list: the small box is counted, not walked, and every box is back at its top", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const code = revealLayout(p, "CodeBox", ".late{height:300px;background:#c03;opacity:0}.late.in{opacity:1}pre{max-height:300px;overflow-y:auto;margin:0}",
    LAYOUT(`${ITEMS(1, 1800, "p")}<pre>${ITEMS(6, 1000, "c")}</pre>${ITEMS(1, 1200, "p")}<section class=late></section>`
      + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script>"));
  assert.deepEqual(code.rec, { steps: 7, capped: false, small_boxes: 1 });
  assert.ok(redPixels(path.join(code.shots, "1440-light-full.png")) > 1440 * 300 * 0.9, "the window was walked to its bottom, past the code box");
  assert.match(code.r.stdout, /1 box under half a screen tall that scrolls \(a code block, a short list\) was not walked/);
  const nested = revealLayout(p, "Nested", "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}ul{max-height:300px;overflow-y:auto;margin:0;padding:0}",
    LAYOUT(`<main>${RED_BAND}${ITEMS(1, 1100, "p")}<ul>${ITEMS(5, 1000, "l")}</ul>${ITEMS(1, 600, "p")}</main>`));
  assert.deepEqual(nested.rec, { steps: 3, capped: false, boxes: 1, box_steps: 3, small_boxes: 1 });
  assert.ok(redPixels(path.join(nested.shots, "1440-light.png")) > 1440 * 100 * 0.9, "main is back at its top in the first screen");
});

test("capture --reveal: closed off-canvas drawer (moved off the screen, or hidden), and a short list in a closed menu: not walked, not counted", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Drawer",
    "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}nav{position:fixed;top:0;height:100%;width:300px;overflow-y:auto}.left{left:0;transform:translateX(-100%)}.right{right:0;visibility:hidden}"
      + ".menu{position:fixed;top:0;left:0;width:300px;transform:translateX(-100%)}.menu ul{max-height:300px;overflow-y:auto;margin:0}",
    LAYOUT(`<main>${ITEMS(2, 1000, "p")}</main><nav class=left>${ITEMS(9, 1000, "d")}</nav><nav class=right>${ITEMS(9, 1000, "d")}</nav><div class=menu><ul>${ITEMS(10, 100, "m")}</ul></div>`));
  assert.deepEqual(rec, { steps: 3, capped: false, boxes: 1, box_steps: 3 });
  assert.ok(!/under half a screen/.test(r.stdout), r.stdout);
});

test("capture --reveal: grid of 8 tall scrolling cards: the walk stops at 80 steps and names the boxes it did not finish, never a long page", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Cards", ".grid{display:grid;grid-template-columns:repeat(4,1fr)}.card{height:500px;overflow-y:auto}",
    LAYOUT(`<div class=grid>${`<div class=card>${ITEMS(6, 1000, "c")}</div>`.repeat(8)}</div>${ITEMS(1, 3000, "p")}`));
  assert.deepEqual(rec, { steps: 80, capped: true, boxes: 4, box_steps: 73, boxes_unfinished: 5 });
  assert.match(r.stdout, /\(80 steps at most, of 80 allowed; up to 73 of them inside 4 boxes that scroll/);
  assert.match(r.stdout, /CAPPED: the page and its boxes needed more than 80 steps, so what lies further down in 5 boxes that scroll was not revealed/);
  assert.ok(!/longer than 40 screens/.test(r.stdout), r.stdout);
});

test("capture --reveal: box in the first screen whose items reveal by a viewport IntersectionObserver, on a long page: walked with the page scrolled back to show it", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "Panel", SEEN_HEADER + ".panel{height:600px;overflow-y:auto;margin-top:50px}",
    LAYOUT(`<header class=seen-bar></header><div class=panel>${ITEMS(6, 400)}</div>${ITEMS(1, 4000, "p")}${SEEN_SCRIPT(6)}`));
  assert.deepEqual(rec, { steps: 16, capped: false, boxes: 1, box_steps: 6 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all six items of the panel were seen in the viewport");
  assert.ok(redPixels(path.join(shots, "390-dark.png")) > 390 * 50 * 0.9);
});

test("capture --reveal: box taller than two screens: walked in half-screen steps, then carried up by the page until its bottom is shown, so every item is seen", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "TallBox", SEEN_HEADER + ".tall{height:2400px;overflow-y:auto}",
    LAYOUT(`<header class=seen-bar></header><div class=tall>${ITEMS(60, 100)}</div>${ITEMS(1, 3000, "p")}${SEEN_SCRIPT(60)}`));
  // the page: 10 steps at 900, 11 at 844; the box: 8 / 9 steps inside it, then 4 steps of the page carrying it up
  assert.deepEqual(rec, { steps: 24, capped: false, boxes: 1, box_steps: 13 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all 60 items of the tall box were seen in the viewport");
  assert.ok(redPixels(path.join(shots, "390-light.png")) > 390 * 50 * 0.9);
});

test("capture --reveal: a box that the page's walk reveals (opacity 0 until seen) is found after it and walked", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "LateBox", SEEN_HEADER + ".late{opacity:0}.late.in{opacity:1}.panel{height:600px;overflow-y:auto}",
    LAYOUT(`<header class=seen-bar></header>${ITEMS(1, 2000, "p")}<section class=late><div class=panel>${ITEMS(4, 400)}</div></section>`
      + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script>" + SEEN_SCRIPT(4)));
  assert.deepEqual(rec, { steps: 9, capped: false, boxes: 1, box_steps: 4 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "the late box's items were all seen");
});

test("capture --reveal: infinite scroll that appends on reaching the end: followed to its end with --wait 0, and the record says it grew", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Infinite", "",
    LAYOUT(`${ITEMS(1, 1800, "p")}<script>let n=0;addEventListener('scroll',()=>{const d=document.documentElement;if(scrollY+d.clientHeight>=d.scrollHeight-5&&n<5){n++;const e=document.createElement('div');e.style.height='1800px';if(n===5)e.style.background='#c03';document.body.append(e)}})</script>`));
  assert.deepEqual(rec, { steps: 28, capped: false, grew: true });
  assert.ok(redPixels(path.join(shots, "1440-light-full.png")) > 1440 * 1800 * 0.9, "the fifth page appended is in the full page");
  assert.match(r.stdout, /the page or a box grew as it was scrolled/);
});

test("capture --reveal: html overflow:clip: Chromium scrolls the root by script (clip on the root is hidden on the viewport), so the page is walked", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Clip", "html{overflow:clip}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false, root_hidden: true });
  assert.match(r.stdout, /NOTE: the page's own scrolling is hidden or clipped \(overflow: hidden or clip on the root, or on the body when the root's is visible\), so the walk scrolled it by script but a visitor cannot scroll it with the wheel/);
});

test("capture --reveal: a root whose overflow is hidden is walked and flagged, also when it comes from the body; a scrolling body or main under a hidden root is no such page", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  assert.deepEqual(revealLayout(p, "RootHidden", "html{overflow:hidden}", LAYOUT(ITEMS(3, 1000, "p"))).rec, { steps: 6, capped: false, root_hidden: true });
  // html visible: the body's overflow is the viewport's (propagation), so hidden on the body is hidden on the window
  assert.deepEqual(revealLayout(p, "BodyHidden", "body{overflow:hidden}", LAYOUT(ITEMS(3, 1000, "p"))).rec, { steps: 6, capped: false, root_hidden: true });
  // the body scrolls itself under a hidden root: a visitor's wheel scrolls it, so there is nothing to flag
  assert.ok(!("root_hidden" in revealLayout(p, "BodyOwn", "html{overflow:hidden;height:100%}body{height:100%;overflow-y:auto}", LAYOUT(ITEMS(3, 1000, "p"))).rec));
  // overflow-x:clip on the root keeps the root's own overflow out of propagation: the body's hidden is no longer the window's, and a visitor's wheel scrolls the page
  assert.ok(!("root_hidden" in revealLayout(p, "ClipXBodyHidden", "html{overflow-x:clip}body{overflow:hidden}", LAYOUT(ITEMS(3, 1000, "p"))).rec));
  // an ordinary page gets no note
  const plain = revealLayout(p, "NotHidden", "", LAYOUT(ITEMS(3, 1000, "p")));
  assert.ok(!("root_hidden" in plain.rec) && !/NOTE/.test(plain.r.stdout), plain.r.stdout);
});

test("capture --reveal: a page that stops answering during the walk stops capture at once: exit 1, nothing written", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // the page's script never ends once the page has been scrolled
  const page = writeMoving(p, "rounds/r1/Hung", CSS + "body{margin:0}", LAYOUT(`${ITEMS(4, 1000, "p")}<script>addEventListener('scroll',()=>{for(;;);},{once:true})</script>`));
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", "--timeout", "1000"]);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stdout + r.stderr, /the page stopped answering during the --reveal walk; nothing was written/);
  assert.ok(!fs.existsSync(path.join(p, "rounds/r1/Hung/shots")), "no still and no capture.json");
});

test("capture --reveal: a page that pulls itself back to the top: NOT SCROLLED after one step, never a page longer than 40 screens", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Lock", "", LAYOUT(`${ITEMS(3, 1000, "p")}<script>addEventListener('scroll',()=>scrollTo({top:0,behavior:'instant'}))</script>`));
  assert.deepEqual(rec, { steps: 1, capped: false, not_scrolled: true });
  assert.match(r.stdout, /NOT SCROLLED: a scroller did not stay where it was scrolled to/);
  assert.ok(!/CAPPED/.test(r.stdout), r.stdout);
});

test("capture --reveal: reveal scripts with a margin (rootMargin -100px, and 0px 0px -20% 0px): half-screen steps show every item inside the margin", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // 60 items of 120 px, then a 300 px footer no script watches, so that the last item can reach the part of the screen the margin leaves
  for (const [name, margin] of [["Margin100", "-100px"], ["MarginBottom20", "0px 0px -20% 0px"]]) {
    const { rec, shots } = revealLayout(p, name, SEEN_HEADER, LAYOUT(`<header class=seen-bar></header>${ITEMS(60, 120)}${ITEMS(1, 300, "f")}${SEEN_SCRIPT(60, `{rootMargin:"${margin}"}`)}`));
    assert.deepEqual(rec, { steps: 16, capped: false }, name);
    assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, `${name}: all 60 items were seen at 1440`);
    assert.ok(redPixels(path.join(shots, "390-light.png")) > 390 * 50 * 0.9, `${name}: all 60 items were seen at 390`);
  }
});

test("capture --reveal: chat box scrolled to its end on load: walked from its top, then put back at its end, never 'nothing to scroll'", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Chat", SEEN_HEADER + ".chat{height:600px;overflow-y:auto;margin-top:50px}",
    LAYOUT(`<header class=seen-bar></header><div class=chat>${ITEMS(19, 200)}<div class=i style="height:200px;background:#c03"></div></div>`
      + `<script>const c=document.querySelector('.chat');c.scrollTop=c.scrollHeight</script>${SEEN_SCRIPT(20)}`));
  assert.deepEqual(rec, { steps: 12, capped: false, boxes: 1, box_steps: 12 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 250 * 0.9, "all 20 messages were seen, and the chat is back at its end (its last, red message shown)");
  assert.ok(!/nothing to scroll/.test(r.stdout), r.stdout);
});

test("capture --reveal: a banner that collapses once it is above the screen: the window is not pulled back (scroll anchoring off for the walk), so the page is walked to its end", (t) => {
  if (needSetup(t)) return;
  // a 600 px banner that collapses once the page is past 700 px: with scroll anchoring on, the browser pulls the window back by 600 px, which reads as "the page moved it back"
  const { rec, shots } = revealLayout(makeProject(), "Banner", SEEN_HEADER + ".banner{height:600px}.banner.gone{height:0}",
    LAYOUT(`<header class=seen-bar></header><div class=banner></div>${ITEMS(4, 1000)}<script>addEventListener('scroll',()=>{if(scrollY>700)document.querySelector('.banner').classList.add('gone')})</script>${SEEN_SCRIPT(4)}`));
  assert.deepEqual(rec, { steps: 8, capped: false });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all four sections were seen");
});

test("capture --reveal: a page whose IntersectionObserver never answers: the box is not walked, the run says so, and nothing hangs", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "NoObserver", ".b{height:600px;overflow-y:auto}",
    LAYOUT(`<div class=b>${ITEMS(6, 400)}</div>${ITEMS(1, 2000, "p")}<script>window.IntersectionObserver=class{observe(){}unobserve(){}disconnect(){}}</script>`));
  assert.deepEqual(rec, { steps: 5, capped: false, boxes_unmeasured: 1 });
  assert.match(r.stdout, /NOT MEASURED: the page's IntersectionObserver did not answer for 1 box that scrolls/);
});

test("capture --reveal: a box slotted into a shadow scroller (a web-component layout): walked, and the shadow scroller is put back at its top", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "Shadow", ".panel{height:600px;overflow-y:auto}",
    LAYOUT(`<x-layout>${RED_BAND}<div style="height:1400px"></div><div class=panel>${ITEMS(6, 400)}</div></x-layout>`
      + `<script>customElements.define('x-layout',class extends HTMLElement{constructor(){super();this.attachShadow({mode:'open'}).innerHTML='<div style="height:100vh;overflow-y:auto"><slot></slot></div>'}})</script>`));
  assert.deepEqual(rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 100 * 0.9, "the first screen shows the top of the shadow scroller");
});

test("capture --reveal: a column-reverse box (a chat, scrollTop 0 at its end and negative above) is walked from its top to its end, so every item is seen", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Chat", SEEN_HEADER + ".chat{height:600px;margin-top:50px;overflow-y:auto;display:flex;flex-direction:column-reverse}.chat .i{flex:none}",
    LAYOUT(`<header class=seen-bar></header><div class=chat>${ITEMS(20, 200)}</div>${SEEN_SCRIPT(20)}`));
  assert.ok(rec.boxes === 1 && rec.box_steps > 0, JSON.stringify(rec));
  assert.doesNotMatch(r.stdout, /holds no box that scrolls/);
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all 20 items of the chat were seen in the viewport");
});

test("capture --reveal: a column-reverse box the page scrolled to its oldest item on load is still walked", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "ChatOldest", SEEN_HEADER + ".chat{height:600px;margin-top:50px;overflow-y:auto;display:flex;flex-direction:column-reverse}.chat .i{flex:none}",
    LAYOUT(`<header class=seen-bar></header><div class=chat>${ITEMS(20, 200)}</div>${SEEN_SCRIPT(20)}<script>document.querySelector('.chat').scrollTop=-99999</script>`));
  assert.ok(rec.boxes === 1 && rec.box_steps > 0 && !rec.not_scrolled, JSON.stringify(rec));
  assert.doesNotMatch(r.stdout, /NOT SCROLLED/);
});
