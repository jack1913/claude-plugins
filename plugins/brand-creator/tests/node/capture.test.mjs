import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
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
