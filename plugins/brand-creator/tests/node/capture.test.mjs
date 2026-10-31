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

function bcAsync(args) {
  return new Promise((resolve, reject) => {
    const c = spawn(BIN, ["--data", DATA, ...args], { env: { ...process.env, BRAND_CREATOR_TODAY: "2026-10-17" } });
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
