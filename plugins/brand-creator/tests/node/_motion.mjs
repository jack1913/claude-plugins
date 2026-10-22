// Shared by the motion tests (motion, seek, edges, inplace, frames): a scratch Acme project with the example's motion folder, runs of the proof,
// its report (one per proof file) and small page builders. Every page is written into the project's motion/ folder.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { needSetup, bc, makeProject, mutateText, ROOT, DATA } from "./_helpers.mjs";
import { proofReportTool } from "../../scripts/lib/_common.mjs";

export { needSetup, bc, mutateText, ROOT, DATA };
export const EX = path.join(ROOT, "skills/brand-creator/references/examples/acme");

export function motionProject() {
  const p = makeProject();
  fs.cpSync(path.join(EX, "motion"), path.join(p, "motion"), { recursive: true });
  return p;
}
export const run = (p, proof = "motion/proof.json") => bc(["shot", "--motion", proof, "--project", p]);
export const reportFile = (p, proof = "motion/proof.json") => path.join(p, "assets/_checks", proofReportTool(proof) + ".json");
export const rep = (p, proof = "motion/proof.json") => JSON.parse(fs.readFileSync(reportFile(p, proof), "utf8"));
export const byId = (p, proof) => Object.fromEntries(rep(p, proof).results.map((r) => [r.id, r]));
export const failing = (p, proof) => rep(p, proof).results.filter((r) => r.status === "fail").map((r) => r.id);
export const writeProof = (p, cases, name = "motion/p.json") => { fs.writeFileSync(path.join(p, name), JSON.stringify({ schema: 1, cases })); return name; };
export const demo = (p) => path.join(p, "motion/demo.html");
export const PAGE = { name: "demo-page", type: "page", page: "motion/demo.html", selector: "#mark", static: "assets/logo/mark.svg", settle_ms: 700 };

/** A page of the project (motion/<name>.html): `css` and `body` go into a plain skeleton on the Acme ground; returns its project-relative path. */
export function writePage(p, name, { css = "", body = "", head = "" } = {}) {
  const file = `motion/${name}.html`;
  fs.writeFileSync(path.join(p, file), `<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>${name}</title>\n`
    + `<meta name="viewport" content="width=device-width, initial-scale=1">\n<style>html,body{margin:0;background:#f9f7ee}${css}</style>${head}</head>\n<body>${body}</body></html>\n`);
  return file;
}
/** The Acme mark's inline markup (the drawing of assets/logo/mark.svg) with the given attributes on its root, so a page can hold the mark as an element. */
export function inlineMark(p, attrs = 'id="mark"') {
  return fs.readFileSync(path.join(p, "assets/logo/mark.svg"), "utf8").replace(/<\?xml[^>]*\?>\s*/, "").replace(/<svg\b/, `<svg ${attrs}`).trim();
}
/** A page case on a page of the project, with the Acme mark as its still, and the proof file that holds it. */
export function pageCase(extra = {}) { return { name: "case", type: "page", selector: "#mark", static: "assets/logo/mark.svg", settle_ms: 300, ...extra }; }

/** A synthetic lockup (a disc, a triangle and curved letter-like shapes, 320 x 90): large and curved enough that Chromium's raster tiles show in it
 *  when it is placed away from the origin. Written as assets/logo/lockup.svg by `writeLockup`. */
export const LOCKUP = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="320" height="90" role="img" aria-label="Acme lockup">
<circle cx="44" cy="45" r="34" fill="#0d1b2d"/><path d="M44 18 70 64H18Z" fill="#f9f7ee"/><circle cx="44" cy="52" r="9" fill="#007d71"/>
<path d="M100 66V24h14c11 0 17 6 17 14s-6 14-17 14h-6v14zm8-28h5c6 0 9-2 9-6s-3-6-9-6h-5z" fill="#0d1b2d"/>
<path d="M146 66V24h8v36h22v6zM190 66l16-42h8l16 42h-8l-4-10h-20l-4 10zm14-17h14l-7-19z" fill="#0d1b2d"/>
<path d="M246 24h30c9 0 14 4 14 10 0 5-3 8-8 9 6 1 10 5 10 11 0 7-6 12-16 12h-30zm8 6v11h20c5 0 8-2 8-5s-3-6-8-6zm0 17v13h22c6 0 9-2 9-6s-3-7-9-7z" fill="#007d71"/></svg>
`;
export function writeLockup(p, name = "lockup.svg") { fs.writeFileSync(path.join(p, "assets/logo", name), LOCKUP); return `assets/logo/${name}`; }

/** An 8 x 8 pixel drawing (a staircase and a dot): crispEdges on its root, like the marks the pixel engines write. */
export const PIXEL = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" width="8" height="8" shape-rendering="crispEdges" role="img" aria-label="Pixel mark">
<rect x="0" y="6" width="8" height="2" fill="#0d1b2d"/><rect x="1" y="4" width="6" height="2" fill="#0d1b2d"/><rect x="2" y="2" width="4" height="2" fill="#0d1b2d"/><rect id="dot" x="3" y="0" width="2" height="2" fill="#007d71"/></svg>
`;
export function writePixel(p, name = "pixel.svg") { fs.writeFileSync(path.join(p, "assets/logo", name), PIXEL); return `assets/logo/${name}`; }

/** A PNG as pixels (8-bit RGB or RGBA, not interlaced: what Chromium writes), so a test can compare pictures. -> {w, h, bpp, px}. */
export function readPng(buf) {
  if (!buf.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) throw new Error("not a PNG");
  let w = 0, h = 0, depth = 0, kind = 0;
  const idat = [];
  for (let o = 8; o < buf.length;) {
    const len = buf.readUInt32BE(o), type = buf.toString("latin1", o + 4, o + 8), data = buf.subarray(o + 8, o + 8 + len);
    if (type === "IHDR") { w = data.readUInt32BE(0); h = data.readUInt32BE(4); depth = data[8]; kind = data[9]; if (data[12]) throw new Error("interlaced PNG"); }
    if (type === "IDAT") idat.push(data);
    o += 12 + len;
  }
  if (depth !== 8 || (kind !== 2 && kind !== 6)) throw new Error(`unsupported PNG: ${depth} bit, colour type ${kind}`);
  const bpp = kind === 6 ? 4 : 3, stride = w * bpp, raw = zlib.inflateSync(Buffer.concat(idat)), px = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)), out = px.subarray(y * stride, (y + 1) * stride);
    const prev = y ? px.subarray((y - 1) * stride, y * stride) : null;
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? out[x - bpp] : 0, b = prev ? prev[x] : 0, c = prev && x >= bpp ? prev[x - bpp] : 0;
      let pr = 0;
      if (f === 1) pr = a; else if (f === 2) pr = b; else if (f === 3) pr = (a + b) >> 1;
      else if (f === 4) { const q = a + b - c, pa = Math.abs(q - a), pb = Math.abs(q - b), pc = Math.abs(q - c); pr = pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      out[x] = (line[x] + pr) & 255;
    }
  }
  return { w, h, bpp, px };
}
/** The RGB of the pixel columns x0..x1 of a decoded picture, row by row (alpha, when there is one, must be opaque). */
export function columns(png, x0, x1) {
  const rows = [];
  for (let y = 0; y < png.h; y++) for (let x = x0; x < x1; x++) { const o = (y * png.w + x) * png.bpp; rows.push(png.px[o], png.px[o + 1], png.px[o + 2]); if (png.bpp === 4 && png.px[o + 3] !== 255) throw new Error("not opaque"); }
  return Buffer.from(rows);
}
export const sha256Of = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
/** Every file of a folder tree as {relative path: sha256}, to see what a command wrote (the folders named in `skip` are left out). */
export function tree(root, skip = []) {
  const out = {};
  const walk = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const f = path.join(d, e.name); if (e.isDirectory()) { if (!skip.includes(e.name)) walk(f); } else out[path.relative(root, f).split(path.sep).join("/")] = sha256Of(fs.readFileSync(f)); } };
  walk(root);
  return out;
}
