// Shared by the capture tests (capture, capture-frames, capture-reveal, capture-reveal-walk): pages, a local server, the readers of the stills
// and of capture.json, and the reveal walk's layouts.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { spawn } from "node:child_process";
import { bc, BIN, DATA } from "./_helpers.mjs";

export const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
export const png = (file) => { const d = fs.readFileSync(file); return { width: d.readUInt32BE(16), height: d.readUInt32BE(20) }; };
/** Width and height of a baseline or progressive JPEG, read from its start-of-frame marker. */
export function jpeg(file) {
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
export const record = (dir) => JSON.parse(fs.readFileSync(path.join(dir, "capture.json"), "utf8"));

export function bcAsync(args, env = {}) {
  return new Promise((resolve, reject) => {
    const c = spawn(BIN, ["--data", DATA, ...args], { env: { ...process.env, BRAND_CREATOR_TODAY: "2026-10-17", ...env } });
    let stdout = "", stderr = "";
    c.stdout.on("data", (d) => { stdout += d; });
    c.stderr.on("data", (d) => { stderr += d; });
    c.on("error", reject);
    c.on("close", (status) => resolve({ status, stdout, stderr }));
  });
}

export function listen(handler) {
  const hits = [];
  const srv = http.createServer((req, res) => { hits.push(req.url); handler(req, res); });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok({ hits, port: srv.address().port, close: () => new Promise((done) => srv.close(done)) })));
}

export const TALL = "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + "<body><h1>Ledger</h1><img src=mark.svg width=40 height=40 alt=''><div class=tall></div><p>The bottom.</p></body></html>";
export const CSS = "body{font:18px/1.4 sans-serif;margin:2rem;background:#fff;color:#111}@media (prefers-color-scheme:dark){body{background:#111;color:#eee}}.tall{height:2600px;background:#ccc}";
export const MARK = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><rect width='10' height='10' fill='#c03'/></svg>";

export function writePage(p, dir = "rounds/r1/Ledger", html = TALL) {
  fs.mkdirSync(path.join(p, dir), { recursive: true });
  fs.writeFileSync(path.join(p, dir, "index.html"), html);
  fs.writeFileSync(path.join(p, dir, "style.css"), CSS);
  fs.writeFileSync(path.join(p, dir, "mark.svg"), MARK);
  return `${dir}/index.html`;
}

export const MOVING = "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + "<body><h1 class=rise>Ledger</h1><p class=rise>A hero that rises in when the page loads.</p></body></html>";
export const MOVING_CSS = CSS + "@keyframes rise{from{opacity:0;transform:translateY(160px)}to{opacity:1;transform:none}}.rise{animation:rise 1500ms ease-out both}h1{font-size:96px}";
export const FRAME_FILES = ["frame-1440-0.png", "frame-1440-100.png", "frame-1440-50.png"];

export function writeMoving(p, dir, css, html = MOVING) {
  const page = writePage(p, dir, html);
  fs.writeFileSync(path.join(p, dir, "style.css"), css);
  return page;
}

/** The number of pixels of a PNG (8 bit, RGB or RGBA, not interlaced: what Chromium writes) that are the brand red #c03. */
export function redPixels(file) {
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

export const REVEAL_HTML = "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + "<body><h1>Ledger</h1><div class=tall></div><section class=late>Late</section>"
  + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script></body></html>";
export const REVEAL_CSS = CSS + ".tall{height:1500px}.late{height:300px;background:#c03;opacity:0;transition:opacity 200ms}.late.in{opacity:1}";


export const LAYOUT = (body) => `<!doctype html><html><head><meta charset=utf-8><title>Ledger, a layout</title><link rel=stylesheet href=style.css></head><body>${body}</body></html>`;
export const ITEMS = (n, h, cls = "i") => `<div class=${cls} style="height:${h}px"></div>`.repeat(n);
export const SEEN_HEADER = "header.seen-bar{position:fixed;top:0;left:0;right:0;height:50px;z-index:1}body.seen header.seen-bar{background:#c03}";
export const SEEN_SCRIPT = (n, options = "{}") => `<script>let seen=0;const o=new IntersectionObserver((es)=>es.forEach((e)=>{if(e.isIntersecting){o.unobserve(e.target);if(++seen===${n})document.body.classList.add('seen')}}),${options});document.querySelectorAll('.i').forEach((e)=>o.observe(e))</script>`;
export const RED_BAND = "<div style='height:100px;background:#c03'></div>";

/** capture --reveal --wait 0 of one layout -> {r: the run, rec: capture.json's reveal, shots: the folder}. */
export function revealLayout(p, name, css, html, more = []) {
  const page = writeMoving(p, `rounds/r1/${name}`, CSS + "body{margin:0}" + css, html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", ...more]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const shots = path.join(p, `rounds/r1/${name}/shots`);
  return { r, rec: record(shots).reveal, shots };
}
