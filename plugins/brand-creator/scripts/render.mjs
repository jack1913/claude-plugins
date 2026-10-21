#!/usr/bin/env node
// render.mjs: the only Chromium driver in brand-creator.
//
//   render.mjs shot <page.html>  four-view page shots + report (assets/_checks/shot.json)
//   render.mjs card <card.html>  HTML card -> PNG (OG, repo social, README header)
//   render.mjs selftest          launch the browser once and print its version (used by setup)
//
//   render.mjs shot --motion <proof.json>  motion proof: named states vs the static SVG at dsf 1 and 2, reduced motion, CLS
//   render.mjs fonts             which fonts Chromium really uses for a text (CSS.getPlatformFontsForNode), with a control
//   render.mjs pdf <page.html>  the page as a PDF (print media, RGB), with a label on its first page; book_pdf.py finishes the file
//   render.mjs pdf <page.html> --size-mm WxH [--measure FILE.json]  print stationery: exact page size in mm, no margins, no label on the
//                               page, and the geometry of every text, image and rule measured in the same render (emitters/print.py)
// Needs `brand-creator setup` (Playwright in <data>/node_modules, Chromium build recorded in <data>/setup.json).
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import { parseArgs } from "node:util";
import {
  EXIT, die, mainGuard, dataDir, readSetup, loadDep, findProject, confine, outsideProject, scratchDir, rel,
  Report, forbiddenTerms, writeIfChanged, sha256, readStateTop, missingSharedLibs, findHeadlessShell,
} from "./lib/_common.mjs";

const ANIMATION_CAP_MS = 15000;   // shot waits at most this long for running animations and transitions to end

const USAGE = `usage:
  render.mjs shot <page.html> [--project DIR] [--name NAME] [--out DIR] [--slice CSS_PX] [--forbidden-file FILE] [--timeout MS] [--dsf N] [--wait MS]
  render.mjs card <card.html> --width W --height H --out FILE.png [--project DIR] [--dsf N] [--scheme light|dark] [--json]
  render.mjs shot --motion <proof.json> [--project DIR]
  render.mjs fonts --text TEXT (--font-file FILE | --family NAME) [--json]
  render.mjs pdf <page.html> --out FILE.pdf --label TEXT [--project DIR] [--format A4|Letter] [--scheme light|dark] [--label-px N] [--timeout MS]
  render.mjs pdf <page.html> --out FILE.pdf --size-mm WxH [--bleed-mm N] [--measure FILE.json] [--project DIR] [--scheme light|dark] [--timeout MS]
  render.mjs selftest
shots are written outside the project (default: <data>/scratch/...); the report goes to <project>/assets/_checks/shot.json.
shot loads lazy images first, pauses --wait MS after load (default 300), then waits for running animations and transitions to end
(at most ${ANIMATION_CAP_MS / 1000} s; one that repeats forever is shot where it is, and the report says so).`;

const MIME = {
  ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  ".gif": "image/gif", ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
  ".otf": "font/otf", ".webmanifest": "application/manifest+json", ".txt": "text/plain; charset=utf-8",
  ".md": "text/plain; charset=utf-8",
};

function parse(argv, options, allowPositionals = true) {
  try {
    return parseArgs({ args: argv, options, allowPositionals, strict: true });
  } catch (e) {
    die(EXIT.USAGE, `${e.message}\n${USAGE}`);
  }
}

// ---------------------------------------------------------------- browser + server
async function launch() {
  const setup = readSetup();
  process.env.PLAYWRIGHT_BROWSERS_PATH = setup.browsers_path;
  const pw = await loadDep("playwright-core");
  try {
    return await pw.chromium.launch({ headless: true });
  } catch (e) {
    const why = String(e.message).split("\n")[0];
    const missing = missingSharedLibs(findHeadlessShell(setup.browsers_path, setup.chromium_revision));
    if (missing.length) {   // not a setup problem: the system lacks libraries, and re-running setup would fail the same way
      die(EXIT.CANNOT, `Chromium could not start (${why}): this system lacks shared libraries it needs: ${missing.join(", ")}. `
        + `Install Chromium's system dependencies, then re-run: on Debian or Ubuntu, as root, \`node ${path.join(dataDir(), "node_modules", "playwright-core", "cli.js")} `
        + `install-deps chromium-headless-shell\` (Playwright's own list), or install the packages that provide them with your package manager.`);
    }
    die(EXIT.CANNOT, `Chromium could not start (${why}). Re-run /brand-creator:setup. `
      + `Expected the Playwright build ${setup.chromium_revision} in ${setup.browsers_path}.`);
  }
}

function startServer(root) {
  const realRoot = fs.realpathSync(root);
  const srv = http.createServer((req, res) => {
    try {
      const u = new URL(req.url, "http://x");
      const f = path.join(realRoot, decodeURIComponent(u.pathname));
      let real;
      try { real = fs.realpathSync(f); } catch { res.writeHead(404); res.end(); return; }
      const r = path.relative(realRoot, real);
      if (r.startsWith("..") || path.isAbsolute(r) || fs.statSync(real).isDirectory()) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "content-type": MIME[path.extname(real).toLowerCase()] || "application/octet-stream", "cache-control": "no-store" });
      res.end(fs.readFileSync(real));
    } catch (e) {
      res.writeHead(500); res.end(String(e.message));
    }
  });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok({
    origin: `http://127.0.0.1:${srv.address().port}`,
    close: () => new Promise((done) => srv.close(done)),
  })));
}

function withTimeout(p, ms, what) {
  let t;
  const timeout = new Promise((_, rej) => { t = setTimeout(() => rej(new Error(`${what} timed out after ${ms} ms`)), ms); });
  return Promise.race([p, timeout]).finally(() => clearTimeout(t));
}

function checkPage(project, file) {
  const abs = confine(project, file, "page");
  if (!fs.existsSync(abs) || fs.statSync(abs).isDirectory()) die(EXIT.USAGE, `page not found: ${file}`);
  return abs;
}
function pageUrl(project, origin, file) {
  const abs = checkPage(project, file);
  return { abs, url: origin + "/" + rel(project, abs).split("/").map(encodeURIComponent).join("/") };
}

/** Attach request/console collectors; non-local requests are recorded and aborted (a board never needs the network). */
async function instrument(context, origin) {
  const seen = { nonLocal: [], failedLocal: [], local: 0, errors: [], warnings: [] };
  await context.route("**/*", (route) => {
    const u = route.request().url();
    if (u.startsWith("data:") || u.startsWith("blob:") || u.startsWith("about:")) return route.continue();
    if (u.startsWith(origin + "/")) { seen.local++; return route.continue(); }
    seen.nonLocal.push(u.slice(0, 160));
    return route.abort("blockedbyclient");
  });
  return seen;
}
function watch(page, seen, origin) {
  page.on("pageerror", (e) => seen.errors.push("pageerror: " + String(e.message || e).split("\n")[0]));
  page.on("console", (m) => {
    if (m.type() === "error") {
      const t = m.text();
      // a request we aborted on purpose is reported under non_local_requests, not as a console error
      if (!/net::ERR_BLOCKED_BY_CLIENT/.test(t)) seen.errors.push("console: " + t.slice(0, 200));
    } else if (m.type() === "warning") seen.warnings.push(m.text().slice(0, 200));
  });
  page.on("response", (r) => { if (r.url().startsWith(origin + "/") && r.status() >= 400) seen.failedLocal.push(`${r.status()} ${r.url().slice(origin.length)}`); });
}

// ---------------------------------------------------------------- shot
const VIEWS = [[1440, "light"], [1440, "dark"], [390, "light"], [390, "dark"]];

async function measure(page, terms) {
  return page.evaluate((forbidden) => {
    const doc = document.documentElement;
    const sw = doc.scrollWidth, cw = doc.clientWidth;
    const visible = (e) => { const s = getComputedStyle(e); return s.display !== "none" && s.visibility !== "hidden" && e.getClientRects().length > 0; };
    const inScroller = (e) => {
      for (let p = e.parentElement; p && p !== document.body && p !== doc; p = p.parentElement) {
        const s = getComputedStyle(p);
        if (/(auto|scroll)/.test(s.overflowX)) return true;
      }
      return false;
    };
    const sel = (e) => e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (typeof e.className === "string" && e.className.trim() ? "." + e.className.trim().split(/\s+/).slice(0, 2).join(".") : "");
    const wide = [...document.querySelectorAll("body *")]
      .filter((e) => visible(e) && e.getBoundingClientRect().right > cw + 0.5 && !inScroller(e))
      .slice(0, 6).map(sel);
    // the side gutter: how close the nearest text or image box comes to the left and right edge of the viewport (recorded, never a verdict:
    // a full-bleed page is legitimate; a page that promises a gutter asserts on these numbers)
    let gl = Infinity, gr = Infinity;
    const edge = (r, e) => {
      if (r.width < 1 || r.height < 1 || r.right <= 0 || r.left >= cw || (e && inScroller(e))) return;
      gl = Math.min(gl, r.left); gr = Math.min(gr, cw - r.right);
    };
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      if (!n.nodeValue.trim() || !n.parentElement || !visible(n.parentElement)) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const r of rg.getClientRects()) edge(r, n.parentElement);
    }
    for (const e of document.querySelectorAll("body img, body svg")) if (visible(e)) edge(e.getBoundingClientRect(), e);
    const isSvg = (i) => /\.svg(\?|#|$)/i.test(i.currentSrc || i.src || "") || /^data:image\/svg/i.test(i.currentSrc || "");
    const broken = [...document.images].filter((i) => !i.complete || (i.naturalWidth === 0 && !isSvg(i))).map((i) => (i.getAttribute("src") || "").slice(0, 80));
    const text = (document.body.innerText || "") + " " + [...document.querySelectorAll("[alt],[title],[aria-label]")].map((e) => (e.getAttribute("alt") || "") + " " + (e.getAttribute("title") || "") + " " + (e.getAttribute("aria-label") || "")).join(" ");
    const counts = {};
    for (const t of forbidden) {
      const rx = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      counts[t] = (text.match(rx) || []).length;
    }
    const scripts = [...document.scripts];
    return {
      scrollWidth: sw, clientWidth: cw, height: doc.scrollHeight, overflow: sw > cw + 0.5 || wide.length > 0, overflowing: wide,
      gutterLeft: Number.isFinite(gl) ? Math.round(gl * 10) / 10 : null, gutterRight: Number.isFinite(gr) ? Math.round(gr * 10) / 10 : null,
      brokenImages: broken, images: document.images.length,
      fonts: [...document.fonts].map((f) => ({ family: f.family, status: f.status })),
      scripts: { total: scripts.length, external: scripts.filter((s) => s.src).length },
      forbidden: counts,
    };
  }, terms);
}

// Wait for the page's running animations and transitions with an end to finish, at most ANIMATION_CAP_MS (a capture after a fixed
// pause lands mid-animation on a page that moves). One that repeats forever has no end: it is counted, not waited for.
async function waitAnimations(page) {
  return page.evaluate(async (cap) => {
    const running = () => document.getAnimations().filter((a) => a.playState === "running");
    const ends = (a) => Number.isFinite(a.effect?.getComputedTiming().endTime);
    const finite = running().filter(ends);
    let capped = false;
    if (finite.length) {
      await Promise.race([Promise.all(finite.map((a) => a.finished.catch(() => null))), new Promise((r) => setTimeout(() => { capped = true; r(); }, cap))]);
    }
    const left = running();
    return { waited: finite.length, running: left.length, capped: capped && left.some(ends) };
  }, ANIMATION_CAP_MS);
}

async function cmdShot(argv) {
  const { values, positionals } = parse(argv, {
    project: { type: "string" }, name: { type: "string" }, out: { type: "string" }, slice: { type: "string", default: "2000" },
    "forbidden-file": { type: "string" }, timeout: { type: "string", default: "60000" }, dsf: { type: "string", default: "2" },
    wait: { type: "string", default: "300" }, motion: { type: "boolean", default: false },
  });
  if (values.motion) return cmdMotion(values, positionals);
  if (positionals.length !== 1) die(EXIT.USAGE, "shot needs exactly one page\n" + USAGE);
  const project = findProject(values.project);
  const dsf = Number(values.dsf), sliceH = Number(values.slice), timeout = Number(values.timeout), waitMs = Number(values.wait);
  if (![1, 2, 3].includes(dsf)) die(EXIT.USAGE, "--dsf must be 1, 2 or 3");
  if (!(sliceH >= 200) || sliceH * dsf >= 16384) die(EXIT.USAGE, `--slice ${values.slice} css px at dsf ${dsf} gives ${sliceH * dsf} px; slices must stay under 16384 px (the Chromium texture limit)`);
  const pageFile = positionals[0];
  const name = values.name || rel(project, confine(project, pageFile, "page")).replace(/\.[a-z]+$/i, "").replace(/[^A-Za-z0-9._-]+/g, "-");
  const outDir = values.out ? outsideProject(project, values.out, "--out") : scratchDir(project, path.join("shots", name));
  fs.mkdirSync(outDir, { recursive: true });
  let terms;
  if (values["forbidden-file"]) {
    terms = fs.readFileSync(values["forbidden-file"], "utf8").split("\n").map((s) => s.trim()).filter((s) => s && !s.startsWith("#"));
  } else terms = forbiddenTerms(project);

  checkPage(project, pageFile);
  const browser = await launch(); // a missing setup fails before anything else is opened
  const server = await startServer(project);
  const report = new Report("shot", project, [confine(project, pageFile, "page")]);
  const { abs, url } = pageUrl(project, server.origin, pageFile);
  report.extra = { page: rel(project, abs), out_dir: outDir, forbidden_terms: terms, dsf };
  try {
    for (const [width, scheme] of VIEWS) {
      const view = `${width}-${scheme}`;
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: scheme, deviceScaleFactor: dsf });
      const seen = await instrument(ctx, server.origin);
      const page = await ctx.newPage();
      watch(page, seen, server.origin);
      try {
        await withTimeout(page.goto(url, { waitUntil: "load", timeout }), timeout + 5000, `loading ${url}`);
        await withTimeout(page.evaluate(() => document.fonts.ready), timeout, "fonts.ready");
        // lazy images below the fold never load in a full-page shot: load them first, so they are drawn and not reported broken
        const lazy = await withTimeout(page.evaluate(async () => {
          const imgs = [...document.images].filter((i) => i.loading === "lazy");
          for (const i of imgs) i.loading = "eager";
          await Promise.all(imgs.map((i) => (i.complete ? null : new Promise((r) => { i.addEventListener("load", r, { once: true }); i.addEventListener("error", r, { once: true }); }))));
          return imgs.length;
        }), timeout, "lazy images");
        await page.waitForTimeout(waitMs);
        const motion = await waitAnimations(page);
        const m = await measure(page, terms);
        const slices = [];
        for (let y = 0, n = 0; y < m.height; y += sliceH, n++) {
          const f = path.join(outDir, `${view}-${String(n).padStart(2, "0")}.png`);
          await page.screenshot({ path: f, fullPage: true, clip: { x: 0, y, width, height: Math.min(sliceH, m.height - y) } });
          slices.push(f);
        }
        const hits = Object.entries(m.forbidden).filter(([, c]) => c > 0);
        const problems = [];
        if (m.overflow) problems.push(`horizontal overflow ${m.scrollWidth}>${m.clientWidth}${m.overflowing.length ? " (" + m.overflowing.join(", ") + ")" : ""}`);
        if (seen.errors.length) problems.push(`${seen.errors.length} console/page error(s): ${seen.errors.slice(0, 2).join(" | ")}`);
        if (seen.nonLocal.length) problems.push(`${seen.nonLocal.length} non-local request(s): ${seen.nonLocal.slice(0, 2).join(" ")}`);
        if (seen.failedLocal.length) problems.push(`${seen.failedLocal.length} failed local request(s): ${seen.failedLocal.slice(0, 2).join(" ")}`);
        if (m.brokenImages.length) problems.push(`${m.brokenImages.length} broken image(s): ${m.brokenImages.slice(0, 2).join(" ")}`);
        if (hits.length) problems.push("forbidden strings: " + hits.map(([t, c]) => `${t} x${c}`).join(", "));
        report.add(`view:${view}`, problems.length ? "fail" : "pass", `${width}px ${scheme}, dsf ${dsf}`, {
          detail: (problems.length ? problems.join("; ") : `height ${m.height}px, ${slices.length} slice(s), ${m.images} image(s), ${m.fonts.length} font face(s), ${m.scripts.total} script(s), no overflow, no console errors, no non-local requests`)
            + (lazy ? `; ${lazy} lazy image(s) loaded first` : "") + (motion.waited ? `; waited for ${motion.waited} animation(s) to end` : "")
            + (motion.running ? `; ${motion.running} animation(s) ${motion.capped ? `still running after ${ANIMATION_CAP_MS / 1000} s` : "repeat forever"}: shot mid-way` : ""),
          lazy_images: lazy, animations: motion,
          height: m.height, scroll_width: m.scrollWidth, client_width: m.clientWidth, overflow: m.overflow, overflowing: m.overflowing,
          gutter_left: m.gutterLeft, gutter_right: m.gutterRight,
          console_errors: seen.errors, console_warnings: seen.warnings, non_local_requests: seen.nonLocal, failed_local_requests: seen.failedLocal,
          local_requests: seen.local, broken_images: m.brokenImages, images: m.images, fonts: m.fonts, scripts: m.scripts,
          forbidden_counts: m.forbidden, slices,
        });
      } catch (e) {
        report.add(`view:${view}`, "fail", `${width}px ${scheme}`, { detail: `could not render: ${String(e.message).split("\n")[0]}` });
      } finally {
        await ctx.close();
      }
    }
  } finally {
    await browser.close();
    await server.close();
  }
  return report.finish();
}

// ---------------------------------------------------------------- card
async function cmdCard(argv) {
  const { values, positionals } = parse(argv, {
    project: { type: "string" }, width: { type: "string" }, height: { type: "string" }, out: { type: "string" },
    dsf: { type: "string", default: "1" }, scheme: { type: "string", default: "light" }, wait: { type: "string", default: "300" },
    timeout: { type: "string", default: "60000" }, json: { type: "boolean", default: false },
  });
  if (positionals.length !== 1) die(EXIT.USAGE, "card needs exactly one HTML file\n" + USAGE);
  const W = Number(values.width), H = Number(values.height), dsf = Number(values.dsf), timeout = Number(values.timeout);
  if (!(W > 0 && H > 0 && Number.isInteger(W) && Number.isInteger(H))) die(EXIT.USAGE, "--width and --height are required integers");
  if (!["light", "dark"].includes(values.scheme)) die(EXIT.USAGE, "--scheme must be light or dark");
  if (!values.out) die(EXIT.USAGE, "--out FILE.png is required");
  const project = findProject(values.project);
  const out = confine(project, values.out, "--out");
  checkPage(project, positionals[0]);
  const browser = await launch();
  const server = await startServer(project);
  let result;
  try {
    const { url } = pageUrl(project, server.origin, positionals[0]);
    const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: dsf, colorScheme: values.scheme });
    const seen = await instrument(ctx, server.origin);
    const page = await ctx.newPage();
    watch(page, seen, server.origin);
    await withTimeout(page.goto(url, { waitUntil: "load", timeout }), timeout + 5000, `loading ${url}`);
    await withTimeout(page.evaluate(() => document.fonts.ready), timeout, "fonts.ready");
    await page.waitForTimeout(Number(values.wait));
    const problems = [];
    if (seen.nonLocal.length) problems.push(`non-local requests: ${seen.nonLocal.slice(0, 3).join(" ")}`);
    if (seen.errors.length) problems.push(`console/page errors: ${seen.errors.slice(0, 3).join(" | ")}`);
    if (seen.failedLocal.length) problems.push(`failed local requests: ${seen.failedLocal.slice(0, 3).join(" ")}`);
    if (problems.length) die(EXIT.FAIL, `card ${positionals[0]} is not self-contained or has errors: ${problems.join("; ")}`);
    const png = await page.screenshot({ clip: { x: 0, y: 0, width: W, height: H } });
    const changed = writeIfChanged(out, png);
    result = { out: rel(project, out), changed, bytes: png.length, sha256: sha256(png), width: W * dsf, height: H * dsf };
    await ctx.close();
  } finally {
    await browser.close();
    await server.close();
  }
  if (values.json) console.log(JSON.stringify(result));
  else console.log(`card ${result.out}: ${result.changed ? "written" : "unchanged"} (${result.width}x${result.height}, ${result.bytes} bytes)`);
  return EXIT.PASS;
}


// ---------------------------------------------------------------- motion proof (shot --motion <proof.json>)
// proof.json: {"schema": 1, "cases": [ {type: "states", ...} | {type: "page", ...} ]}. See scripts/CONTRACT.md "Motion proof".
//  states: an animated mark file = the complete still, its moving part in <g data-motion> whose children <g data-state="name">
//          are the named states (the stored file shows "rest"). Each state is rendered at dsf 1 and 2 (inline SVG screenshot and
//          <img> drawn on a canvas); rest must equal the static SVG, a state with an "expected" file must equal it, and every
//          control pair must DIFFER (a comparison that cannot see a difference proves nothing).
//  page:   a page that animates the mark. Normal pass: no infinite loop, every animation ends (settle_ms), whole-pixel motion,
//          CLS = 0, rest frame = static SVG. Reduced pass (prefers-reduced-motion: reduce): no running animation, no
//          requestAnimationFrame loop, no motion listener, CLS = 0, rest frame = static SVG. A control: the normal pass must
//          show motion, else the reduced result is vacuous.
const MOTION_EVENTS = ["pointermove", "mousemove", "touchmove", "wheel", "scroll", "deviceorientation", "devicemotion"];
const INIT_SCRIPT = `(() => {
  const w = window; const bc = (w.__bc = { listeners: [], raf: 0, cls: 0, shifts: [] });
  const MOTION = new Set(${JSON.stringify(MOTION_EVENTS)});
  const who = (t) => (t === w ? "window" : t === document ? "document" : (t && t.tagName ? t.tagName.toLowerCase() : "target"));
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, ...rest) { if (MOTION.has(type)) bc.listeners.push(type + " on " + who(this)); return orig.call(this, type, ...rest); };
  const raf = w.requestAnimationFrame.bind(w); w.requestAnimationFrame = (cb) => { bc.raf++; return raf(cb); };
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { bc.cls += e.value; bc.shifts.push(e.value); } }).observe({ type: "layout-shift", buffered: true }); } catch {}
})();`;

function svgBox(text, what) {
  const root = /<svg\b[^>]*>/i.exec(text);
  if (!root) die(EXIT.USAGE, `${what} is not an SVG document`);
  const attr = (n) => { const m = new RegExp(`\\s${n}\\s*=\\s*["']([^"']+)["']`, "i").exec(root[0]); return m ? m[1] : null; };
  const num = (v) => (v && /^[0-9.]+(px)?$/.test(v.trim()) ? parseFloat(v) : null);
  let w = num(attr("width")), h = num(attr("height"));
  if (!(w && h)) {
    const vb = (attr("viewBox") || "").split(/[\s,]+/).map(Number);
    if (vb.length === 4 && vb[2] > 0 && vb[3] > 0) { w = vb[2]; h = vb[3]; }
  }
  if (!(w && h)) die(EXIT.USAGE, `${what} needs a width and height or a viewBox`);
  return { w, h };
}

/** Pixel difference of two PNG buffers (same size required), counted in a scratch page. A pixel counts as different when any
 *  channel differs by more than `tol` (0 = exact); `max` is the largest channel difference seen, so noise stays visible. */
async function pngDiff(page, a, b, tol = 0) {
  return page.evaluate(async ([x, y, tol]) => {
    const load = async (b64) => {
      const bmp = await createImageBitmap(await (await fetch("data:image/png;base64," + b64)).blob());
      const c = new OffscreenCanvas(bmp.width, bmp.height); const g = c.getContext("2d"); g.drawImage(bmp, 0, 0);
      return { w: bmp.width, h: bmp.height, d: g.getImageData(0, 0, bmp.width, bmp.height).data };
    };
    const A = await load(x), B = await load(y);
    if (A.w !== B.w || A.h !== B.h) return { sizeDiffers: true, a: [A.w, A.h], b: [B.w, B.h], diff: -1 };
    let n = 0, max = 0;
    for (let i = 0; i < A.d.length; i += 4) {
      const m = Math.max(Math.abs(A.d[i] - B.d[i]), Math.abs(A.d[i + 1] - B.d[i + 1]), Math.abs(A.d[i + 2] - B.d[i + 2]), Math.abs(A.d[i + 3] - B.d[i + 3]));
      if (m > max) max = m;
      if (m > tol) n++;
    }
    return { sizeDiffers: false, diff: n, max, size: [A.w, A.h] };
  }, [a.toString("base64"), b.toString("base64"), tol]);
}

async function statesCase(browser, project, c, report, inputs) {
  const read = (p, what) => { const f = confine(project, p, what); if (!fs.existsSync(f)) die(EXIT.USAGE, `motion case ${c.name}: ${what} not found: ${p}`); inputs.push(f); return fs.readFileSync(f, "utf8"); };
  if (!c.file || !c.static) die(EXIT.USAGE, `motion case ${c.name}: a states case needs "file" (the animated mark) and "static" (the still it must equal at rest)`);
  const fileText = read(c.file, "file"), staticText = read(c.static, "static");
  const expected = Object.fromEntries(Object.entries(c.expected || {}).map(([s, p]) => [s, read(p, `expected.${s}`)]));
  const box = svgBox(staticText, "static");
  const restName = c.rest || "rest";
  for (const dsf of [1, 2]) {
    const ctx = await browser.newContext({ deviceScaleFactor: dsf, viewport: { width: 800, height: 800 } });
    const page = await ctx.newPage();
    await page.setContent("<!doctype html><body style='margin:0;background:transparent'><div id=d style='line-height:0;display:inline-block'></div></body>");
    // the states of the file, and each state as an SVG string
    const info = await page.evaluate((txt) => {
      const doc = new DOMParser().parseFromString(txt, "image/svg+xml");
      if (doc.querySelector("parsererror")) return { error: "the file is not well-formed SVG" };
      const groups = [...doc.querySelectorAll("[data-motion]")];
      const names = [...new Set(groups.flatMap((g) => [...g.children].filter((e) => e.hasAttribute("data-state")).map((e) => e.getAttribute("data-state"))))];
      return { groups: groups.length, names };
    }, fileText);
    if (info.error) die(EXIT.USAGE, `motion case ${c.name}: ${info.error}`);
    const states = c.states || info.names;
    if (!info.groups || !info.names.length) { report.add(`motion:${c.name}:${dsf}x:states`, "fail", "named states", { detail: `${c.file} has no <g data-motion> group with <g data-state="..."> children` }); await ctx.close(); continue; }
    if (!states.includes(restName)) { report.add(`motion:${c.name}:${dsf}x:states`, "fail", "named states", { detail: `no state called ${restName} (has: ${info.names.join(", ")}); every animation must end on a named rest frame` }); await ctx.close(); continue; }
    const frames = { "@stored": fileText, "@static": staticText, ...Object.fromEntries(Object.entries(expected).map(([s, t]) => [`@expected:${s}`, t])) };
    for (const s of states) {
      const svg = await page.evaluate(([txt, name]) => {
        const doc = new DOMParser().parseFromString(txt, "image/svg+xml");
        let hit = false;
        for (const g of doc.querySelectorAll("[data-motion]")) for (const e of g.children) if (e.hasAttribute("data-state")) {
          if (e.getAttribute("data-state") === name) { e.removeAttribute("display"); hit = true; } else e.setAttribute("display", "none");
        }
        return hit ? new XMLSerializer().serializeToString(doc.documentElement) : null;
      }, [fileText, s]);
      if (svg === null) { report.add(`motion:${c.name}:${dsf}x:state:${s}`, "fail", "named states", { detail: `state ${s} not found in ${c.file}` }); continue; }
      frames[s] = svg;
    }
    const shots = {}, px = {};
    for (const [k, svg] of Object.entries(frames)) {
      await page.evaluate((s) => { document.getElementById("d").innerHTML = s; }, svg);
      shots[k] = await page.locator("#d svg").screenshot({ omitBackground: true });
    }
    for (const [k, svg] of Object.entries(frames)) {
      px[k] = await page.evaluate(async ([s, d, bw, bh]) => {
        const im = new Image(); im.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(s))); await im.decode();
        const cv = document.createElement("canvas"); cv.width = Math.round(bw * d); cv.height = Math.round(bh * d);
        const g = cv.getContext("2d"); g.drawImage(im, 0, 0, cv.width, cv.height); return Array.from(g.getImageData(0, 0, cv.width, cv.height).data);
      }, [svg, dsf, box.w, box.h]);
    }
    const cmp = (a, b) => {
      const A = px[a], B = px[b]; let n = 0;
      if (A.length !== B.length) return { img: -1, inline: false };
      for (let i = 0; i < A.length; i += 4) if (A[i] !== B[i] || A[i + 1] !== B[i + 1] || A[i + 2] !== B[i + 2] || A[i + 3] !== B[i + 3]) n++;
      return { img: n, inline: Buffer.compare(shots[a], shots[b]) === 0, px: A.length / 4 };
    };
    const equalPair = (id, label, a, b) => {
      const r = cmp(a, b), ok = r.img === 0 && r.inline;
      report.add(`motion:${c.name}:${dsf}x:${id}`, ok ? "pass" : "fail", label, {
        detail: ok ? `${a} = ${b}: 0 of ${r.px} px differ (inline SVG and <img> canvas, dsf ${dsf})` : `${a} != ${b}: ${r.img} px differ in the <img> canvas${r.inline ? "" : ", the inline SVG screenshots differ"} (dsf ${dsf})`,
        px_differ: r.img, inline_equal: r.inline, dsf,
      });
    };
    equalPair("file=rest", "the stored file shows its rest frame", "@stored", restName);
    equalPair("rest=static", "rest frame equals the static SVG", restName, "@static");
    for (const s of Object.keys(expected)) { if (frames[s]) equalPair(`${s}=expected`, `state ${s} equals its reference drawing`, s, `@expected:${s}`); }
    const others = states.filter((s) => s !== restName && frames[s]);
    const controls = c.controls || (others.length ? [[restName, others[0]]] : []);
    if (!controls.length) report.add(`motion:${c.name}:${dsf}x:control`, "fail", "control pair", { detail: "no control pair: a case needs at least one pair of states that must differ (add a state besides rest, or controls)" });
    for (const [a, b] of controls) {
      if (!frames[a] || !frames[b]) { report.add(`motion:${c.name}:${dsf}x:control:${a}!=${b}`, "fail", "control pair differs", { detail: `control state ${!frames[a] ? a : b} does not exist` }); continue; }
      const r = cmp(a, b);
      report.add(`motion:${c.name}:${dsf}x:control:${a}!=${b}`, r.img > 0 ? "pass" : "fail", "control pair differs", {
        detail: r.img > 0 ? `${a} and ${b} differ in ${r.img} px, so the equality checks can see a difference` : `${a} and ${b} are pixel-identical: the control failed, the equality checks prove nothing`, px_differ: r.img, dsf,
      });
    }
    await ctx.close();
  }
}

async function pageCase(browser, project, server, c, report, inputs) {
  if (!c.page || !c.selector || !c.static) die(EXIT.USAGE, `motion case ${c.name}: a page case needs "page", "selector" (the mark's element) and "static" (the still SVG)`);
  const { abs, url } = pageUrl(project, server.origin, c.page); inputs.push(abs);
  const staticFile = confine(project, c.static, "static"); if (!fs.existsSync(staticFile)) die(EXIT.USAGE, `motion case ${c.name}: static not found: ${c.static}`); inputs.push(staticFile);
  const staticText = fs.readFileSync(staticFile, "utf8");
  const settle = Number(c.settle_ms ?? 1500), maxCls = Number(c.max_cls ?? 0), tol = Number(c.tolerance ?? 8);
  const id = (s) => `motion:${c.name}:${s}`;

  async function scratch(ctx) { const p = await ctx.newPage(); await p.setContent("<!doctype html><body style='margin:0'></body>"); return p; }
  async function staticShot(ctx, w, h) {
    const p = await scratch(ctx);
    await p.setContent(`<!doctype html><body style='margin:0;background:transparent'>${staticText.replace(/<\?xml[^>]*\?>/, "").replace(/<svg\b/, `<svg style="display:block;width:${w}px;height:${h}px"`)}</body>`);
    const b = await p.locator("svg").first().screenshot({ omitBackground: true }); await p.close(); return b;
  }
  async function pass(reduced) {
    const tag = reduced ? "reduced" : "normal";
    const ctx = await browser.newContext({ viewport: { width: 900, height: 700 }, deviceScaleFactor: 1, reducedMotion: reduced ? "reduce" : "no-preference" });
    const seen = await instrument(ctx, server.origin);
    await ctx.addInitScript(INIT_SCRIPT);
    const page = await ctx.newPage(); watch(page, seen, server.origin);
    await withTimeout(page.goto(url, { waitUntil: "load", timeout: 60000 }), 65000, `loading ${url}`);
    await withTimeout(page.evaluate(() => document.fonts.ready), 30000, "fonts.ready");
    if (!reduced) await page.waitForTimeout(80);
    const early = await page.evaluate(() => ({ anims: document.getAnimations().length, raf: window.__bc.raf }));
    await page.waitForTimeout(settle);
    const state = await page.evaluate(() => {
      const all = document.getAnimations();
      const info = all.map((a) => { const t = a.effect ? a.effect.getComputedTiming() : {}; return { name: a.animationName || a.transitionProperty || a.id || "animation", playState: a.playState, infinite: t.iterations === Infinity || t.endTime === Infinity }; });
      return { total: all.length, running: info.filter((a) => a.playState === "running").length, infinite: info.filter((a) => a.infinite).map((a) => a.name), runningNames: info.filter((a) => a.playState === "running").map((a) => a.name) };
    });
    // a requestAnimationFrame loop still alive after the settle time? count the calls in a quiet window
    const raf = await page.evaluate(async () => { const b0 = window.__bc.raf; await new Promise((r) => setTimeout(r, 500)); return window.__bc.raf - b0; });
    const hooks = await page.evaluate(() => ({ listeners: [...window.__bc.listeners], cls: window.__bc.cls, shifts: [...window.__bc.shifts] }));
    // motion listeners also as the browser sees them (inline on* handlers are not seen by the addEventListener hook)
    const cdp = await ctx.newCDPSession(page); const cdpListeners = [];
    for (const expr of ["window", "document", "document.documentElement", "document.body", `document.querySelector(${JSON.stringify(c.selector)})`]) {
      const { result } = await cdp.send("Runtime.evaluate", { expression: expr });
      if (!result.objectId) continue;
      const { listeners } = await cdp.send("DOMDebugger.getEventListeners", { objectId: result.objectId });
      for (const l of listeners) if (MOTION_EVENTS.includes(l.type)) cdpListeners.push(`${l.type} on ${expr.replace("document.", "").replace(/\(.*/, "")}`);
    }
    const el = page.locator(c.selector).first();
    if (!(await el.count())) die(EXIT.USAGE, `motion case ${c.name}: selector ${c.selector} matches nothing on ${c.page}`);
    const bb = await el.boundingBox();
    await page.addStyleTag({ content: "html,body{background:transparent!important}" });
    const shot = await el.screenshot({ omitBackground: true });
    const ref = await staticShot(ctx, Math.round(bb.width), Math.round(bb.height));
    const cmp = await pngDiff(await scratch(ctx), shot, ref, tol);
    if (cmp.diff !== 0) { // keep both images so the difference can be read, outside the project
      const dir = scratchDir(project, path.join("motion", c.name));
      fs.writeFileSync(path.join(dir, `${tag}-element.png`), shot); fs.writeFileSync(path.join(dir, `${tag}-static.png`), ref); cmp.saved = dir;
    }
    const result = { tag, early, state, raf, hooks, cdpListeners, cmp, errors: seen.errors, nonLocal: seen.nonLocal };
    return { ctx, page, result };
  }

  const normal = await pass(false);
  const n = normal.result;
  const motionSeen = n.early.anims > 0 || n.early.raf > 0 || n.state.total > 0;
  report.add(id("control"), motionSeen ? "pass" : "fail", "control: the normal pass shows motion", {
    detail: motionSeen ? `normal pass: ${n.early.anims} animation(s) at load, ${n.early.raf} requestAnimationFrame call(s)` : "no animation and no requestAnimationFrame call in the normal pass: the reduced-motion result below would prove nothing",
  });
  report.add(id("loops"), n.state.infinite.length ? "fail" : "pass", "no infinite loops", {
    detail: n.state.infinite.length ? `infinite animation(s): ${n.state.infinite.join(", ")}; every animation must end on its rest frame` : "no infinite animation",
  });
  report.add(id("settled"), n.state.running ? "fail" : "pass", `every animation has ended after ${settle} ms`, {
    detail: n.state.running ? `${n.state.running} still running: ${n.state.runningNames.join(", ")}` : `${n.state.total} animation(s) seen, none running`,
  });
  report.add(id("cls:normal"), n.hooks.cls > maxCls ? "fail" : "pass", "layout shift (CLS) while the mark moves", {
    detail: `CLS ${n.hooks.cls.toFixed(4)} over load + ${settle} ms (limit ${maxCls}); ${n.hooks.shifts.length} shift(s)`, cls: n.hooks.cls,
  });
  const restOk = (r) => r.cmp.diff === 0;
  report.add(id("normal:rest=static"), restOk(n) ? "pass" : "fail", "rest frame equals the static SVG (after the animation)", {
    detail: n.cmp.sizeDiffers ? `size differs: element ${n.cmp.a} vs static ${n.cmp.b}` : `${n.cmp.diff} px differ by more than ${tol}/255 (largest difference ${n.cmp.max}/255; antialiasing noise below that is ignored)${n.cmp.saved ? ` (both images: ${n.cmp.saved})` : ""}`, px_differ: n.cmp.diff,
  });
  if (n.errors.length || n.nonLocal.length) report.add(id("page:errors"), "fail", "page loads cleanly", { detail: [...n.errors, ...n.nonLocal].slice(0, 3).join(" | ") });
  // whole pixels: seek every finite animation across its length and read the translation of its target
  const sample = await normal.page.evaluate(() => {
    const bad = [];
    for (const a of document.getAnimations()) {
      const t = a.effect && a.effect.getComputedTiming(); const target = a.effect && a.effect.target;
      if (!t || !target || !Number.isFinite(t.endTime) || !t.endTime) continue;
      a.pause();
      for (let k = 0; k <= 8; k++) {
        a.currentTime = (t.endTime * k) / 8;
        const m = new DOMMatrix(getComputedStyle(target).transform === "none" ? undefined : getComputedStyle(target).transform);
        if (Math.abs(m.e - Math.round(m.e)) > 0.01 || Math.abs(m.f - Math.round(m.f)) > 0.01) bad.push(`${a.animationName || "animation"} at ${Math.round((100 * k) / 8)}%: translate(${m.e.toFixed(2)}px, ${m.f.toFixed(2)}px)`);
      }
    }
    return bad.slice(0, 4);
  });
  report.add(id("whole-pixel"), sample.length ? "fail" : "pass", "motion moves in whole pixels", { detail: sample.length ? sample.join("; ") : "translation was whole pixels at nine points of every finite animation" });
  await normal.ctx.close();

  const red = await pass(true); const r = red.result;
  report.add(id("reduced:animations"), r.state.running ? "fail" : "pass", "reduced motion: no running animation", {
    detail: r.state.running ? `${r.state.running} running: ${r.state.runningNames.join(", ")}` : `prefers-reduced-motion: reduce emulated; ${r.state.total} animation(s), none running`,
  });
  report.add(id("reduced:raf"), r.raf ? "fail" : "pass", "reduced motion: no requestAnimationFrame loop", { detail: `${r.raf} call(s) in a 500 ms quiet window` });
  const listeners = [...new Set([...r.hooks.listeners, ...r.cdpListeners])];
  report.add(id("reduced:listeners"), listeners.length ? "fail" : "pass", "reduced motion: no motion listeners", {
    detail: listeners.length ? `registered: ${listeners.slice(0, 5).join(", ")} (${MOTION_EVENTS.join(", ")} count as motion)` : `no ${MOTION_EVENTS.join(", ")} listener on window, document, body or the mark`,
  });
  report.add(id("cls:reduced"), r.hooks.cls > maxCls ? "fail" : "pass", "reduced motion: layout shift (CLS)", { detail: `CLS ${r.hooks.cls.toFixed(4)} (limit ${maxCls})`, cls: r.hooks.cls });
  report.add(id("reduced:rest=static"), restOk(r) ? "pass" : "fail", "reduced motion: the rest frame equals the static SVG", {
    detail: r.cmp.sizeDiffers ? `size differs: element ${r.cmp.a} vs static ${r.cmp.b}` : `${r.cmp.diff} px differ by more than ${tol}/255 (largest difference ${r.cmp.max}/255; antialiasing noise below that is ignored)${r.cmp.saved ? ` (both images: ${r.cmp.saved})` : ""}`, px_differ: r.cmp.diff,
  });
  await red.ctx.close();
}

async function cmdMotion(values, positionals) {
  if (positionals.length !== 1) die(EXIT.USAGE, "shot --motion needs exactly one proof.json\n" + USAGE);
  const project = findProject(values.project);
  const specFile = confine(project, positionals[0], "proof.json");
  if (!fs.existsSync(specFile)) die(EXIT.USAGE, `motion proof not found: ${positionals[0]}`);
  let spec;
  try { spec = JSON.parse(fs.readFileSync(specFile, "utf8")); } catch (e) { die(EXIT.USAGE, `${positionals[0]} is not valid JSON: ${e.message}`); }
  if (spec.schema !== 1 || !Array.isArray(spec.cases) || !spec.cases.length) die(EXIT.USAGE, `${positionals[0]} needs {"schema": 1, "cases": [ ... ]}`);
  const names = new Set();
  for (const c of spec.cases) {
    if (!c.name || names.has(c.name)) die(EXIT.USAGE, `every motion case needs a unique name (${c.name ?? "missing"})`);
    names.add(c.name);
    if (!["states", "page"].includes(c.type)) die(EXIT.USAGE, `motion case ${c.name}: type must be "states" or "page"`);
  }
  const inputs = [specFile];
  const report = new Report("motion", project, inputs);
  const browser = await launch();
  const server = await startServer(project);
  report.extra = { proof: rel(project, specFile), cases: spec.cases.map((c) => ({ name: c.name, type: c.type })), engine: "Chromium (Playwright)" };
  try {
    for (const c of spec.cases) {
      if (c.type === "states") await statesCase(browser, project, c, report, inputs);
      else await pageCase(browser, project, server, c, report, inputs);
    }
  } finally {
    await browser.close();
    await server.close();
  }
  return report.finish();
}

// ---------------------------------------------------------------- fonts (which font does Chromium really use?)
const FONT_MIME = { ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2" };
// Candidates for the control, tried in this order: hiragana, han, thai, hebrew, devanagari (a Mac has fonts for all of them), then Greek,
// Cyrillic and Arabic, which a bare Linux box (no CJK font installed) still has a system font for. All are absent from a Latin-only font.
const CONTROL_CHARS = ["あ", "中", "ก", "א", "अ", "α", "ж", "ع"];

async function cmdFonts(argv) {
  const { values } = parse(argv, {
    "font-file": { type: "string" }, family: { type: "string" }, text: { type: "string" }, json: { type: "boolean", default: false },
  }, false);
  if (!values.text) die(EXIT.USAGE, "fonts needs --text\n" + USAGE);
  if (!!values["font-file"] === !!values.family) die(EXIT.USAGE, "fonts needs exactly one of --font-file FILE (a font to load) or --family NAME (an installed family)\n" + USAGE);
  const chars = [...new Set([...values.text].filter((c) => !/\s/.test(c)))];
  if (!chars.length) die(EXIT.USAGE, "--text holds no visible characters");
  let faceCss = "", requested;
  if (values["font-file"]) {
    const f = path.resolve(values["font-file"]);
    if (!fs.existsSync(f)) die(EXIT.USAGE, `font file not found: ${values["font-file"]}`);
    const mime = FONT_MIME[path.extname(f).toLowerCase()];
    if (!mime) die(EXIT.USAGE, "--font-file must be .ttf, .otf, .woff or .woff2");
    requested = "bc-font-under-test";
    faceCss = `@font-face{font-family:"${requested}";src:url(data:${mime};base64,${fs.readFileSync(f).toString("base64")});font-synthesis:none}`;
  } else requested = values.family;
  // Chromium picks a fallback font only when some installed font holds the character. A system with no font for the first candidate (a
  // Linux container without CJK fonts) would show the requested font's .notdef instead, and the control would fail for no good reason:
  // every candidate the text does not use is rendered, and the first one that really fell back to another font is the control.
  const candidates = CONTROL_CHARS.filter((c) => !chars.includes(c));
  if (!candidates.length) die(EXIT.USAGE, "--text uses every control character; use a shorter text");
  const browser = await launch();
  try {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    // a fallback family that cannot exist, so a missing glyph shows up as the browser's own choice
    const stack = `"${requested}", "bc-no-such-family-9f3a"`;
    const spans = [...chars, ...candidates].map((c, i) => `<span id="c${i}">${c.replace("&", "&amp;").replace("<", "&lt;")}</span>`).join(" ");
    await page.setContent(`<!doctype html><meta charset=utf-8><style>${faceCss}body{font:32px ${stack};font-synthesis:none}</style><body>${spans}</body>`);
    if (values["font-file"]) await withTimeout(page.evaluate(([r, t]) => document.fonts.load(`32px "${r}"`, t).then(() => document.fonts.ready), [requested, chars.join("") + candidates.join("")]), 30000, "font load");
    const cdp = await ctx.newCDPSession(page);
    await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
    const { root } = await cdp.send("DOM.getDocument");
    const results = [];
    const all = [...chars, ...candidates];
    for (let i = 0; i < all.length; i++) {
      const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: `#c${i}` });
      const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
      results.push({ char: all[i], codepoint: "U+" + all[i].codePointAt(0).toString(16).toUpperCase().padStart(4, "0"),
        fonts: fonts.map((f) => ({ family: f.familyName, postscript: f.postScriptName, custom: !!f.isCustomFont, glyphs: f.glyphCount })) });
    }
    const ua = await page.evaluate(() => navigator.userAgent);
    const usesRequested = (r) => r.fonts.length > 0 && r.fonts.every((f) => (values["font-file"] ? f.custom : f.family === requested));
    const charRes = results.slice(0, chars.length);
    const candRes = results.slice(chars.length);
    const ctrl = candRes.find((r) => !usesRequested(r)) ?? candRes[0];   // none fell back: the first candidate, reported as a failed control
    const out = {
      requested: values["font-file"] ? path.basename(values["font-file"]) : requested, mode: values["font-file"] ? "font-file" : "installed-family",
      chromium: (/(Headless)?Chrome\/[\d.]+/.exec(ua) || [ua])[0],
      chars: charRes.map((r) => ({ ...r, uses_requested: usesRequested(r) })),
      fallback: charRes.filter((r) => !usesRequested(r)).map((r) => r.char),
      control: { char: ctrl.char, codepoint: ctrl.codepoint, fonts: ctrl.fonts, ok: !usesRequested(ctrl),
        meaning: "a character the font under test does not hold: Chromium must pick another font for it, otherwise this report cannot tell a covered character from a fallback" },
    };
    if (values.json) console.log(JSON.stringify(out));
    else {
      console.log(`requested ${out.requested} (${out.mode}); ${out.chromium}`);
      for (const r of out.chars) console.log(`  ${r.char} ${r.codepoint}  ${r.uses_requested ? "requested font" : "FALLBACK"}  ${r.fonts.map((f) => f.family + (f.custom ? " (loaded)" : "")).join(", ") || "none"}`);
      console.log(`control ${out.control.char} ${out.control.codepoint}: ${out.control.ok ? "OK, Chromium chose another font" : "FAILED, the requested font was used for a character it should not hold"}`);
    }
    if (!out.control.ok) { console.error("fonts: the control failed; the report cannot be trusted"); return EXIT.FAIL; }
    return out.fallback.length ? EXIT.FAIL : EXIT.PASS;
  } finally {
    await browser.close();
  }
}

// ---------------------------------------------------------------- print geometry (runs inside the page)
// Text is outlined in the finished PDF, so its size and position can no longer be read from the file. They are measured here, in the same
// render that produced the PDF, and print_check.py reads them from the sidecar that emitters/print.py binds to the PDF by its hash.
// Units: mm from the top-left corner of the TRIM box (the page origin shifted by the bleed); font and line sizes in pt.
const PX_PER_MM = 96 / 25.4;
function measurePrint({ bleedMm, pxPerMm, pageMm }) {
  const toMm = (px) => Math.round((px / pxPerMm) * 1000) / 1000;
  const rectMm = (r) => [toMm(r.left) - bleedMm, toMm(r.top) - bleedMm, toMm(r.width), toMm(r.height)].map((v) => Math.round(v * 1000) / 1000);
  const parse = (c) => { const m = /rgba?\(([^)]+)\)/.exec(c || ""); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const hex = (c) => "#" + [c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const inMark = (el) => !!el.closest("[data-print-mark]");
  const bleedArt = (el) => el.hasAttribute("data-print-bleed");   // the ground itself, never its descendants
  const out = { page_mm: pageMm, bleed_mm: bleedMm, elements: [], transparency: [], unverifiable: [] };
  const background = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return { image: true };
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) return { colour: c };
    }
    return { colour: { r: 255, g: 255, b: 255, a: 1 } };   // unpainted: the paper
  };
  const all = [...document.body.querySelectorAll("*")];
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    const text = n.nodeValue.replace(/\s+/g, " ").trim();
    const el = n.parentElement;
    if (!text || !el || inMark(el) || ["SCRIPT", "STYLE", "TITLE"].includes(el.tagName)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const range = document.createRange(); range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const fg = parse(cs.color), bg = background(el);
    const e = { kind: "text", text: text.slice(0, 48), rect: rectMm(r), font_pt: Math.round(parseFloat(cs.fontSize) * 0.75 * 100) / 100,
      weight: Number(cs.fontWeight) || 400, color: fg ? hex(fg) : null, bleed_art: false };
    if (bg.image) { e.bg = null; out.unverifiable.push({ text: e.text, why: "text over a background image or gradient: reversal cannot be decided" }); }
    else { e.bg = hex(bg.colour); e.reversed = !!fg && lum(fg) > lum(bg.colour); }
    out.elements.push(e);
  }
  for (const el of all) {
    if (inMark(el)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none") continue;
    const r = el.getBoundingClientRect();
    const art = bleedArt(el);
    const tag = el.tagName.toLowerCase();
    if (tag === "img" || (tag === "svg" && !el.parentElement.closest("svg"))) {
      const host = el.closest("[data-print-id]");
      out.elements.push({ kind: tag === "img" ? "image" : "svg", rect: rectMm(r), id: host ? host.getAttribute("data-print-id") : null, bleed_art: art });
    }
    if (el instanceof SVGElement && tag !== "svg") {
      const sw = parseFloat(cs.strokeWidth), sc = cs.stroke;
      if (sc && sc !== "none" && sw > 0 && !el.closest("[data-print-mark]")) {
        const ctm = el.getScreenCTM(); const k = ctm ? Math.sqrt(Math.abs(ctm.a * ctm.d - ctm.b * ctm.c)) : 1;
        const col = parse(sc), bg = background(el.closest("svg").parentElement || document.body);
        out.elements.push({ kind: "stroke", weight_pt: Math.round(sw * k * 0.75 * 1000) / 1000, rect: rectMm(r), color: col ? hex(col) : null,
          reversed: !!col && !bg.image && lum(col) > lum(bg.colour), bleed_art: art });
      }
    } else if (!(el instanceof SVGElement)) {
      const hasText = [...el.childNodes].some((c) => c.nodeType === 3 && c.nodeValue.trim());
      for (const side of ["Top", "Right", "Bottom", "Left"]) {
        const bw = parseFloat(cs[`border${side}Width`]);
        const col = parse(cs[`border${side}Color`]);
        if (bw > 0 && cs[`border${side}Style`] !== "none" && col && col.a > 0) {
          const bg = background(el.parentElement || el);
          out.elements.push({ kind: "border", side: side.toLowerCase(), weight_pt: Math.round(bw * 0.75 * 1000) / 1000, rect: rectMm(r), color: hex(col),
            reversed: !bg.image && lum(col) > lum(bg.colour), bleed_art: art });
        }
      }
      const bgc = parse(cs.backgroundColor);
      if (!hasText && !art && bgc && bgc.a > 0 && tag !== "body" && tag !== "html" && Math.min(r.width, r.height) / pxPerMm < 0.5 && Math.max(r.width, r.height) > 0 && el.children.length === 0) {
        const par = background(el.parentElement || el);
        out.elements.push({ kind: "rule", weight_pt: Math.round(Math.min(r.width, r.height) * 0.75 * 1000) / 1000, rect: rectMm(r), color: hex(bgc),
          reversed: !par.image && lum(bgc) > lum(par.colour), bleed_art: false });
      }
      if (art) out.elements.push({ kind: "bleed", rect: rectMm(r), tag, bleed_art: true });
    }
    // transparency in any form
    const alphaOf = (c) => { const p = parse(c); return p ? p.a : 1; };
    const why = [];
    if (parseFloat(cs.opacity) < 1) why.push(`opacity ${cs.opacity}`);
    if (cs.filter && cs.filter !== "none") why.push(`filter ${cs.filter}`);
    if (cs.mixBlendMode && cs.mixBlendMode !== "normal") why.push(`mix-blend-mode ${cs.mixBlendMode}`);
    if (cs.boxShadow && cs.boxShadow !== "none") why.push("box-shadow");
    if (cs.textShadow && cs.textShadow !== "none") why.push("text-shadow");
    if (cs.backdropFilter && cs.backdropFilter !== "none") why.push("backdrop-filter");
    if (!(el instanceof SVGElement)) {
      if (alphaOf(cs.color) < 1 && [...el.childNodes].some((c) => c.nodeType === 3 && c.nodeValue.trim())) why.push("text colour with alpha");
      const bga = parse(cs.backgroundColor); if (bga && bga.a > 0 && bga.a < 1) why.push("background colour with alpha");
    } else {
      for (const prop of ["fillOpacity", "strokeOpacity"]) if (parseFloat(cs[prop]) < 1) why.push(`${prop} ${cs[prop]}`);
    }
    if (why.length) out.transparency.push({ tag, id: el.id || null, why });
  }
  out.elements.sort((a, b) => a.kind.localeCompare(b.kind) || a.rect[1] - b.rect[1] || a.rect[0] - b.rect[0]);
  return out;
}

// ---------------------------------------------------------------- pdf (book.html -> an RGB PDF proof)
// Print media, background graphics on, the colour scheme chosen (default light), the page's own cover labelled with --label (the label is
// added to the DOM before printing, so a hand-authored book needs no special element). The raw PDF goes outside the project (scratch);
// book_pdf.py sets the metadata and writes book.pdf. Chromium's PDF is RGB: this is a proof, never a print-ready file.
async function cmdPdf(argv) {
  const { values, positionals } = parse(argv, {
    project: { type: "string" }, out: { type: "string" }, label: { type: "string" }, format: { type: "string", default: "A4" },
    scheme: { type: "string", default: "light" }, "label-px": { type: "string", default: "12" }, timeout: { type: "string", default: "90000" },
    json: { type: "boolean", default: false },
    "size-mm": { type: "string" }, "bleed-mm": { type: "string", default: "0" }, measure: { type: "string" },
  });
  if (positionals.length !== 1) die(EXIT.USAGE, "pdf needs exactly one HTML file\n" + USAGE);
  if (!values.out) die(EXIT.USAGE, "--out FILE.pdf is required");
  let sizeMm = null;
  if (values["size-mm"] !== undefined) {
    const m = /^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$/.exec(values["size-mm"]);
    if (!m || !(Number(m[1]) > 0) || !(Number(m[2]) > 0)) die(EXIT.USAGE, "--size-mm must look like 91x61 (millimetres)");
    sizeMm = [Number(m[1]), Number(m[2])];
  } else if (values.measure) die(EXIT.USAGE, "--measure needs --size-mm");
  if (!sizeMm && (!values.label || !values.label.trim())) die(EXIT.USAGE, "--label TEXT is required (the label printed on the first page)");
  if (!["A4", "Letter"].includes(values.format)) die(EXIT.USAGE, "--format must be A4 or Letter");
  const bleedMm = Number(values["bleed-mm"]);
  if (!(bleedMm >= 0)) die(EXIT.USAGE, "--bleed-mm must be a number of 0 or more");
  if (!["light", "dark"].includes(values.scheme)) die(EXIT.USAGE, "--scheme must be light or dark");
  const labelPx = Number(values["label-px"]), timeout = Number(values.timeout);
  if (!(labelPx >= 10)) die(EXIT.USAGE, "--label-px must be a number of 10 or more");
  const project = findProject(values.project);
  const out = outsideProject(project, values.out, "--out");
  checkPage(project, positionals[0]);
  const browser = await launch();
  const server = await startServer(project);
  let result;
  try {
    const { url } = pageUrl(project, server.origin, positionals[0]);
    const ctx = await browser.newContext({ viewport: { width: 1000, height: 1400 }, colorScheme: values.scheme });
    const seen = await instrument(ctx, server.origin);
    const page = await ctx.newPage();
    watch(page, seen, server.origin);
    await withTimeout(page.goto(url, { waitUntil: "load", timeout }), timeout + 5000, `loading ${url}`);
    await withTimeout(page.evaluate(() => document.fonts.ready), timeout, "fonts.ready");
    await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => null))));
    const problems = [];
    if (seen.nonLocal.length) problems.push(`non-local requests: ${seen.nonLocal.slice(0, 3).join(" ")}`);
    if (seen.errors.length) problems.push(`console/page errors: ${seen.errors.slice(0, 3).join(" | ")}`);
    if (seen.failedLocal.length) problems.push(`failed local requests: ${seen.failedLocal.slice(0, 3).join(" ")}`);
    if (problems.length) die(EXIT.FAIL, `${positionals[0]} is not self-contained or has errors: ${problems.join("; ")}`);
    if (!sizeMm) await page.evaluate(([text, px]) => {
      const el = document.createElement("p");
      el.setAttribute("data-pdf-label", "");
      el.textContent = text;
      el.style.cssText = `display:inline-block;border:1px solid currentColor;padding:0 8px;margin:0 0 16px;font-size:${px}px;line-height:22px;letter-spacing:.04em`;
      const host = document.querySelector("[data-cover]") || document.querySelector("main") || document.body;
      host.insertBefore(el, host.firstChild);
    }, [values.label, labelPx]);
    await page.emulateMedia({ media: "print", colorScheme: values.scheme });
    if (sizeMm) await page.setViewportSize({ width: Math.ceil(sizeMm[0] * PX_PER_MM), height: Math.ceil(sizeMm[1] * PX_PER_MM) });
    let measured = null;
    if (sizeMm && values.measure) {
      measured = await page.evaluate(measurePrint, { bleedMm, pxPerMm: PX_PER_MM, pageMm: sizeMm });
      const mo = outsideProject(project, values.measure, "--measure");
      fs.mkdirSync(path.dirname(mo), { recursive: true });
      fs.writeFileSync(mo, JSON.stringify(measured, null, 1) + "\n");
    }
    const pdf = await withTimeout(sizeMm
      ? page.pdf({ width: `${sizeMm[0]}mm`, height: `${sizeMm[1]}mm`, printBackground: true, preferCSSPageSize: false, margin: { top: "0", bottom: "0", left: "0", right: "0" } })
      : page.pdf({ format: values.format, printBackground: true, preferCSSPageSize: false,
        margin: { top: "14mm", bottom: "14mm", left: "14mm", right: "14mm" } }), timeout, "page.pdf");
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, pdf);
    result = sizeMm ? { out, bytes: pdf.length, size_mm: sizeMm, bleed_mm: bleedMm, scheme: values.scheme, measured: measured ? measured.elements.length : 0 }
      : { out, bytes: pdf.length, format: values.format, scheme: values.scheme };
    await ctx.close();
  } finally {
    await browser.close();
    await server.close();
  }
  if (values.json) console.log(JSON.stringify(result));
  else console.log(`pdf ${result.out}: ${result.bytes} bytes (${result.format || result.size_mm.join("x") + " mm"}, ${result.scheme} scheme)`);
  return EXIT.PASS;
}

// ---------------------------------------------------------------- selftest
async function cmdSelftest() {
  const browser = await launch();
  try {
    const page = await browser.newPage();
    await page.setContent("<p>ok</p>");
    const ua = await page.evaluate(() => navigator.userAgent);
    console.log(`chromium OK (${(/(Headless)?Chrome\/[\d.]+/.exec(ua) || [ua])[0]})`);
  } finally {
    await browser.close();
  }
  return EXIT.PASS;
}

mainGuard(async () => {
  dataDir(); // fail early with the standard message when --data is missing
  const [cmd, ...rest] = process.argv.slice(2);
  switch (cmd) {
    case "shot": return cmdShot(rest);
    case "card": return cmdCard(rest);
    case "selftest": return cmdSelftest();
    case "fonts": return cmdFonts(rest);
    case "pdf": return cmdPdf(rest);
    case undefined: case "-h": case "--help": console.log(USAGE); return cmd ? EXIT.PASS : EXIT.USAGE;
    default: return die(EXIT.USAGE, `unknown command ${cmd}\n${USAGE}`);
  }
});
