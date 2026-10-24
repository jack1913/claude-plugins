#!/usr/bin/env node
// render.mjs: the only Chromium driver in brand-creator.
//
//   render.mjs shot <page.html>  four-view page shots + report (assets/_checks/shot.json)
//   render.mjs card <card.html>  HTML card -> PNG (OG, repo social, README header)
//   render.mjs selftest          launch the browser once and print its version (used by setup)
//
//   render.mjs shot --motion <proof.json>  motion proof: named states vs the static SVG at dsf 1 and 2; a page seeked through its motion (whole
//                               pixels, CLS, phone-width edges, the rest frame compared in the page), reduced motion; one report per proof file
//   render.mjs frames <proof.json>  stills of a page case's mark along its motion, a strip and the reduced-motion still, into motion/frames/
//                               (a try-out proof in the latest round or removed-*/ keeps them in its own folder, <folder>/frames/; history/ and earlier rounds are refused)
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
  Report, forbiddenTerms, writeIfChanged, sha256, readStateTop, missingSharedLibs, findHeadlessShell, proofReportTool, pixelArt, motionProofKind,
} from "./lib/_common.mjs";

const ANIMATION_CAP_MS = 15000;   // shot waits at most this long for running animations and transitions to end

const USAGE = `usage:
  render.mjs shot <page.html> [--project DIR] [--name NAME] [--out DIR] [--slice CSS_PX] [--forbidden-file FILE] [--timeout MS] [--dsf N] [--wait MS]
  render.mjs card <card.html> --width W --height H --out FILE.png [--project DIR] [--dsf N] [--scheme light|dark] [--json]
  render.mjs shot --motion <proof.json> [--project DIR]
  render.mjs frames <proof.json> [--case NAME] [--count N | --at 0,25,50,75,100] [--project DIR]
  render.mjs fonts --text TEXT (--font-file FILE | --family NAME) [--json]
  render.mjs pdf <page.html> --out FILE.pdf --label TEXT [--project DIR] [--format A4|Letter] [--scheme light|dark] [--label-px N] [--timeout MS]
  render.mjs pdf <page.html> --out FILE.pdf --size-mm WxH [--bleed-mm N] [--measure FILE.json] [--project DIR] [--scheme light|dark] [--timeout MS]
  render.mjs selftest
shots are written outside the project (default: <data>/scratch/...); the report goes to <project>/assets/_checks/shot.json.
shot loads lazy images first, pauses --wait MS after load (default 300), then waits for running animations and transitions to end
(at most ${ANIMATION_CAP_MS / 1000} s; one that repeats forever is shot where it is, and the report says so).
shot --motion writes one report per proof file: <project>/assets/_checks/motion/<slug>-<hash6>.json. frames writes its stills inside the project, into
motion/frames/<case>/ (a try-out proof, one in the latest round or a removed-*/ folder: <its folder>/frames/<case>/; a proof in history/ or in an earlier round is refused, those are read-only), each file only on a byte change, and its report to
<project>/assets/_checks/frames/<slug>-<hash6>.json. Both reports take as inputs the proof, the pages and every project file the pages loaded (a stylesheet, tokens.css, a
script, an image), so a change to one of them makes the report stale.`;

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
  const served = new Set();   // every project file that was answered with its bytes (a stylesheet, a script, an image, a font ... of the page)
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
      served.add(real);
    } catch (e) {
      res.writeHead(500); res.end(String(e.message));
    }
  });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok({
    origin: `http://127.0.0.1:${srv.address().port}`,
    served: () => [...served],
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


// ---------------------------------------------------------------- motion proof (shot --motion <proof.json>) and frames
// proof.json: {"schema": 1, "cases": [ {type: "states", ...} | {type: "page", ...} ]}. See scripts/CONTRACT.md "Motion proof".
//  states: an animated mark file = the complete still, its moving part in <g data-motion> whose children <g data-state="name">
//          are the named states (the stored file shows "rest"). Each state is rendered at dsf 1 and 2 (inline SVG screenshot and
//          <img> drawn on a canvas); rest must equal the static SVG, a state with an "expected" file must equal it, and every
//          control pair must DIFFER (a comparison that cannot see a difference proves nothing).
//  page:   a page that animates the mark. Its Web Animations (CSS animations, CSS transitions, element.animate) are paused where the page
//          has them and SEEKED, never waited for: the motion's length is the latest finite end of them, stepped through at 0, at every 1/32
//          of it and at every keyframe offset (in page time), with a rendered frame between the steps. Motion driven by requestAnimationFrame
//          cannot be seeked: the page is then waited for settle_ms in real time, and a row says so. Normal pass (900 x 700): no infinite
//          loop, every animation ends, CLS = 0 while it is stepped through, whole-pixel motion for a pixel mark, rest frame = the static SVG
//          drawn in the same page at the same place (equal to the pixel). The same page at the phone widths (360 and 390, 800 high): at every
//          step no horizontal overflow, no painted part of the mark past the left, top or right edge, the page no taller than at rest. Reduced pass
//          (prefers-reduced-motion: reduce): no running animation, no requestAnimationFrame loop, no motion listener, CLS = 0, rest frame =
//          static SVG. A control: the normal pass must show motion, else the reduced result is vacuous.
//  frames: the same seeking, to write stills of the mark (motion/frames/<case>/), see cmdFrames.
const MOTION_EVENTS = ["pointermove", "mousemove", "touchmove", "wheel", "scroll", "deviceorientation", "devicemotion"];
const SAMPLE_STEPS = 32;          // the motion is stepped through at 0 and at every 1/32 of its length, plus every keyframe offset
const MAX_SAMPLE_POINTS = 400;    // keyframe points past this are thinned (a finite animation of hundreds of iterations), and the row says so
const PHONE_WIDTHS = [360, 390];  // the page is loaded again at these viewport widths (a case key "widths" replaces them), PHONE_HEIGHT high
const PHONE_HEIGHT = 800;
const RAF_PROBE_MS = 150;         // a page that still calls requestAnimationFrame this long after load is driven by it: it cannot be seeked
const QUIET_MS = 500;             // requestAnimationFrame calls are counted over this many ms after settle_ms: a loop that still calls it never ends
// the properties an animation moves the page's layout with (as getKeyframes names them): cls:normal fails an animation of one (transform and opacity do not)
const LAYOUT_PROPS = /^(top|right|bottom|left|inset\w*|width|height|(min|max)(Width|Height)|(min|max)?(Block|Inline)Size|margin\w*|padding\w*|border\w*Width|fontSize|lineHeight|letterSpacing|wordSpacing|flex(Basis|Grow|Shrink)?|gap|rowGap|columnGap|gridTemplate\w*|aspectRatio)$/;
/** A case name as a folder name (letters, digits, . _ -), for the frames folder and the scratch folder of a failing comparison; "" when nothing is left. */
const caseFolder = (name) => String(name).replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[.-]+/, "");
const INIT_SCRIPT = `(() => {
  const w = window; const bc = (w.__bc = { listeners: [], raf: 0, cls: 0, shifts: [], anims: [] });
  const MOTION = new Set(${JSON.stringify(MOTION_EVENTS)});
  const who = (t) => (t === w ? "window" : t === document ? "document" : (t && t.tagName ? t.tagName.toLowerCase() : "target"));
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, ...rest) { if (MOTION.has(type)) bc.listeners.push(type + " on " + who(this)); return orig.call(this, type, ...rest); };
  const raf = w.requestAnimationFrame.bind(w); w.requestAnimationFrame = (cb) => { bc.raf++; return raf(cb); };
  // the proof's own wait for a rendered frame goes round the counter above, which counts the page's calls only
  bc.frame = () => new Promise((ok, no) => { const t = setTimeout(() => no(new Error("the page rendered no frame within 3 s")), 3000); raf(() => { clearTimeout(t); ok(); }); });
  // every adopted animation to the time t (an infinite one only over its first iteration)
  bc.seek = (t) => { for (const s of bc.anims) if (s.seekable) s.a.currentTime = s.infinite ? Math.min(t, s.delay + s.duration) : t; };
  const add = (e) => { if (!e.hadRecentInput) { bc.cls += e.value; bc.shifts.push(e.value); } };
  let po = null;
  try { po = new PerformanceObserver((l) => { for (const e of l.getEntries()) add(e); }); po.observe({ type: "layout-shift", buffered: true }); } catch {}
  bc.drain = () => { if (po) for (const e of po.takeRecords()) add(e); };   // the entries the observer has not been handed yet
})();`;

/** The keys of a page case, checked: a bad one is a usage error, raised before a browser is started. */
function pageOptions(c) {
  const num = (k, d) => { const v = Number(c[k] ?? d); if (!Number.isFinite(v) || v < 0) die(EXIT.USAGE, `motion case ${c.name}: "${k}" must be a number of 0 or more`); return v; };
  if (c.pixel !== undefined && typeof c.pixel !== "boolean") die(EXIT.USAGE, `motion case ${c.name}: "pixel" must be true or false`);
  const widths = c.widths ?? PHONE_WIDTHS;
  if (!Array.isArray(widths) || widths.some((w) => !Number.isInteger(w) || w < 200 || w > 4000) || new Set(widths).size !== widths.length) {
    die(EXIT.USAGE, `motion case ${c.name}: "widths" must be a list of different whole numbers from 200 to 4000 (css px)`);
  }
  return { settle: num("settle_ms", 1500), maxCls: num("max_cls", 0), tol: num("tolerance", 0), pixel: c.pixel ?? null, widths };
}

// ---- easings: an animation's easing on the whole effect (a CSS transition's timing function, element.animate's `easing`) moves its keyframes in
// time, and a keyframe's easing that overshoots (a cubic-bezier with y1 or y2 outside 0..1) turns back between two keyframes, at its peak
const NAMED_EASINGS = { ease: [0.25, 0.1, 0.25, 1], "ease-in": [0.42, 0, 1, 1], "ease-out": [0, 0, 0.58, 1], "ease-in-out": [0.42, 0, 0.58, 1] };
const MAX_STEP_TURNS = 64;   // a steps() easing adds the middle of each of its steps (each a pose of its own) up to this many steps
function cubicBezier(x1, y1, x2, y2) {
  const bx = (t) => 3 * (1 - t) * (1 - t) * t * x1 + 3 * (1 - t) * t * t * x2 + t * t * t;
  const by = (t) => 3 * (1 - t) * (1 - t) * t * y1 + 3 * (1 - t) * t * t * y2 + t * t * t;
  const tOf = (x) => { let lo = 0, hi = 1; for (let k = 0; k < 60; k++) { const m = (lo + hi) / 2; if (bx(m) < x) lo = m; else hi = m; } return (lo + hi) / 2; };   // x rises with t
  let turns = [];
  if (y1 < 0 || y1 > 1 || y2 < 0 || y2 > 1) {   // where y turns back: y'(t) = 0, (1 + 3y1 - 3y2) t^2 + 2(y2 - 2y1) t + y1 = 0
    const a = 1 + 3 * y1 - 3 * y2, b = 2 * (y2 - 2 * y1), c = y1, d = b * b - 4 * a * c;
    const ts = Math.abs(a) < 1e-12 ? (Math.abs(b) < 1e-12 ? [] : [-c / b]) : d < 0 ? [] : [(-b - Math.sqrt(d)) / (2 * a), (-b + Math.sqrt(d)) / (2 * a)];
    turns = ts.filter((t) => t > 0 && t < 1).map(bx);
  }
  return { f: (x) => (x <= 0 ? 0 : x >= 1 ? 1 : by(tOf(x))), turns, known: true };
}
function stepsEasing(n, pos) {
  const start = pos === "jump-start" || pos === "start" || pos === "jump-both", jumps = pos === "jump-none" ? n - 1 : pos === "jump-both" ? n + 1 : n;
  const f = (x) => { let k = Math.floor(x * n) + (start ? 1 : 0); if (x >= 0 && k < 0) k = 0; if (x <= 1 && k > jumps) k = jumps; return k / jumps; };
  return { f, turns: n <= MAX_STEP_TURNS ? Array.from({ length: n }, (_, k) => (k + 0.5) / n) : [], known: jumps > 0 };
}
/** linear(0, 0.25 75%, 1) as Chromium writes it -> its stops [[x, y]], positions filled in as CSS Easing says; null when it does not read. */
function linearStops(body) {
  const pts = [];
  for (const part of body.split(",")) {
    const w = part.trim().split(/\s+/), y = Number(w[0]), at = w.slice(1).map((s) => (/^-?[\d.]+%$/.test(s) ? parseFloat(s) / 100 : NaN));
    if (!Number.isFinite(y) || at.some((v) => !Number.isFinite(v)) || at.length > 2) return null;
    if (!at.length) pts.push([null, y]); else for (const x of at) pts.push([x, y]);
  }
  if (pts.length < 2) return null;
  if (pts[0][0] === null) pts[0][0] = 0;
  if (pts.at(-1)[0] === null) pts.at(-1)[0] = 1;
  for (let i = 1, top = pts[0][0]; i < pts.length; i++) if (pts[i][0] !== null) top = pts[i][0] = Math.max(pts[i][0], top);
  for (let i = 1; i < pts.length; i++) {
    if (pts[i][0] !== null) continue;
    let j = i; while (pts[j][0] === null) j++;
    for (let k = i; k < j; k++) pts[k][0] = pts[i - 1][0] + ((pts[j][0] - pts[i - 1][0]) * (k - i + 1)) / (j - i + 1);
  }
  return pts;
}
function linearEasing(pts) {
  const f = (x) => {
    if (x <= pts[0][0]) return pts[0][1];
    for (let i = 1; i < pts.length; i++) if (x <= pts[i][0]) { const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; return x1 === x0 ? y1 : y0 + ((y1 - y0) * (x - x0)) / (x1 - x0); }
    return pts.at(-1)[1];
  };
  return { f, turns: pts.slice(1, -1).map((p) => p[0]).filter((x) => x > 0 && x < 1), known: true };
}
/** An easing as Chromium writes it (getTiming().easing, a keyframe's easing) -> {f: input progress -> output progress, turns: input progresses where
 *  the output turns back or holds a pose (the peak of an overshooting curve, the middle of each step, the stops of linear()), known}. An easing this does
 *  not read is known: false and taken as linear, and the sampling row names it. */
function easingOf(s) {
  const e = String(s ?? "linear").trim();
  if (e === "linear") return { f: (x) => x, turns: [], known: true, linear: true };
  const bez = NAMED_EASINGS[e] ?? /^cubic-bezier\(([^)]*)\)$/.exec(e)?.[1].split(",").map(Number);
  if (bez && bez.length === 4 && bez.every(Number.isFinite) && bez[0] >= 0 && bez[0] <= 1 && bez[2] >= 0 && bez[2] <= 1) return cubicBezier(...bez);
  const st = e === "step-start" ? ["1", "jump-start"] : e === "step-end" ? ["1", "jump-end"] : /^steps\(\s*(\d+)\s*(?:,\s*([a-z-]+)\s*)?\)$/.exec(e)?.slice(1);
  if (st && Number(st[0]) >= 1) return stepsEasing(Number(st[0]), st[1] || "jump-end");
  const lin = /^linear\((.+)\)$/.exec(e), pts = lin && linearStops(lin[1]);
  if (pts) return linearEasing(pts);
  return { f: (x) => x, turns: [], known: false, linear: true };
}
/** Every input progress p in 0..1 where an easing gives `o` (one for a curve that only rises; more for one that overshoots; the first moment of a held step). */
function progressesAt(E, o) {
  if (E.linear) return o >= 0 && o <= 1 ? [o] : [];
  const N = 256, out = [], g = (x) => E.f(x) - o, near = (v) => Math.abs(v) < 1e-9;
  let x0 = 0, y0 = g(0), run = near(y0);
  if (run) out.push(0);
  for (let i = 1; i <= N; i++) {
    const x1 = i / N, y1 = g(x1);
    if (near(y1)) { if (!run) out.push(x1); run = true; } else {
      if (!run && y0 * y1 < 0) {
        let lo = x0, hi = x1, flo = y0;
        for (let k = 0; k < 50; k++) { const m = (lo + hi) / 2, fm = g(m); if (fm < 0 === flo < 0) { lo = m; flo = fm; } else hi = m; }
        out.push(hi);
      }
      run = false;
    }
    x0 = x1; y0 = y1;
  }
  return out;
}

/** The sample points (ms) of a page's Web Animations (`items`: what inPageDescribe returns). The length is the latest finite end (with no finite
 *  animation that lasts, the longest first iteration); an infinite animation is only sampled over its first iteration. The points: 0 and every 1/32 of
 *  the length; every keyframe and every turn of an easing (an overshooting curve's peak, the middle of a step), in page time; and every 1/32 of each
 *  animation's own iterations, so that a short animation inside a long motion is not stepped over. A time in page time is delay + (iteration + p) x
 *  iteration duration, p the input progress at which the effect's own easing reaches the keyframe's offset, counted from the other end in a reversed
 *  iteration. Past MAX_SAMPLE_POINTS the even points stay, the keyframes and turns come next, then the animations' own points, each thinned evenly.
 *  -> {length, points: [{ms, pct}], keyframes, turns, own (points of each kind past the even ones), thinned, unknown (easings not read)}. */
function samplePoints(items) {
  const its = items.filter((i) => i.seekable);
  const first = (i) => i.delay + i.duration;
  const ends = Math.max(0, ...its.filter((i) => !i.infinite).map((i) => i.end));
  const length = ends > 0 ? ends : Math.max(0, ...its.map(first));
  const r3 = (x) => Math.round(x * 1000) / 1000, r1 = (x) => Math.round(x * 10) / 10;
  const even = new Set([0]);
  for (let k = 1; k <= SAMPLE_STEPS; k++) even.add(r3((length * k) / SAMPLE_STEPS));
  const key = new Set(), turn = new Set(), own = new Set(), unknown = new Set(), CAP = 4 * MAX_SAMPLE_POINTS;
  let strided = false;
  for (const i of its) {
    const span = i.infinite ? first(i) : i.end, reps = i.infinite ? 1 : Math.ceil(i.iterations);
    const E = easingOf(i.easing);
    if (!E.known) unknown.add(i.easing);
    const kf = i.keyframes.map((k) => ({ o: k.o, e: easingOf(k.e) }));
    i.keyframes.forEach((k, j) => { if (!kf[j].e.known) unknown.add(k.e); });
    // input progresses (0..1 of one iteration) at the keyframes, and at the turns of the keyframe easings and of the effect's own easing
    const atKey = [...new Set(kf.flatMap((k) => progressesAt(E, k.o)))];
    const atTurn = [...new Set([...E.turns, ...kf.slice(0, -1).flatMap((k, j) => k.e.turns.flatMap((L) => progressesAt(E, k.o + L * (kf[j + 1].o - k.o))))])];
    // an animation of very many iterations is looked at in every stride-th one (and its last), so that what is collected spans the whole of it
    const keyStride = Math.max(1, Math.ceil((reps * (atKey.length + atTurn.length)) / CAP)), ownStride = Math.max(1, Math.ceil((reps * (SAMPLE_STEPS + 1)) / CAP));
    strided ||= keyStride > 1 || ownStride > 1;
    for (let n = 0; n < reps; n++) {
      const withKey = n % keyStride === 0 || n === reps - 1, withOwn = n % ownStride === 0 || n === reps - 1;
      if (!withKey && !withOwn) continue;
      const reversed = i.direction === "reverse" || (i.direction === "alternate" && n % 2 === 1) || (i.direction === "alternate-reverse" && n % 2 === 0);
      const at = (p) => r3(i.delay + (n + (reversed ? 1 - p : p)) * i.duration), keep = (t) => t >= 0 && t <= span && t <= length;
      if (withKey) {
        for (const p of atKey) { const t = at(p); if (keep(t)) key.add(t); }
        for (const p of atTurn) { const t = at(p); if (keep(t)) turn.add(t); }
      }
      if (withOwn) for (let k = 0; k <= SAMPLE_STEPS; k++) { const t = r3(i.delay + (n + k / SAMPLE_STEPS) * i.duration); if (keep(t)) own.add(t); }
    }
  }
  const sorted = (s, ...not) => [...s].filter((t) => !not.some((x) => x.has(t))).sort((a, b) => a - b);
  const thin = (list, room) => (list.length > room ? Array.from({ length: room }, (_, j) => list[Math.floor((j * list.length) / room)]) : list);
  const keyAll = sorted(new Set([...key, ...turn]), even), ownAll = sorted(own, even, key, turn);
  const keyKept = thin(keyAll, Math.max(0, MAX_SAMPLE_POINTS - even.size)), ownKept = thin(ownAll, Math.max(0, MAX_SAMPLE_POINTS - even.size - keyKept.length));
  const points = [...even, ...keyKept, ...ownKept].sort((a, b) => a - b).map((ms) => ({ ms, pct: length ? r1((100 * ms) / length) : 0 }));
  return {
    length, points, keyframes: keyKept.filter((t) => key.has(t)).length, turns: keyKept.filter((t) => !key.has(t)).length, own: ownKept.length,
    thinned: strided || keyKept.length < keyAll.length || ownKept.length < ownAll.length, unknown: [...unknown],
  };
}

// In-page stages of a pass. Each is serialised into the page by page.evaluate, so none may use anything of this module; they share window.__bc.
/** Pause every Web Animation the page has not had paused yet (CSS animations, CSS transitions, element.animate) and keep it in __bc.anims. -> how many are new. */
function inPageAdopt() {
  const bc = window.__bc, have = new Set(bc.anims.map((s) => s.a));
  let n = 0;
  for (const a of document.getAnimations()) {
    if (have.has(a) || !a.effect || typeof a.effect.getComputedTiming !== "function") continue;
    const t = a.effect.getComputedTiming();
    const seekable = a.timeline === document.timeline && typeof t.endTime === "number";   // a scroll or view timeline has no time to seek
    const infinite = seekable && (t.iterations === Infinity || t.endTime === Infinity);
    const wasRunning = a.playState === "running";
    a.pause();
    const kfs = typeof a.effect.getKeyframes === "function" ? a.effect.getKeyframes() : [];
    const props = [...new Set(kfs.flatMap((k) => Object.keys(k).filter((p) => !["offset", "computedOffset", "easing", "composite"].includes(p))))];
    bc.anims.push({ a, seekable, infinite, wasRunning, name: a.animationName || a.transitionProperty || a.id || "animation", delay: seekable ? t.delay : 0,
      duration: seekable ? Number(t.duration) || 0 : 0, iterations: seekable && !infinite ? t.iterations : null, direction: t.direction,
      end: seekable && !infinite ? t.endTime : null, easing: t.easing, keyframes: kfs.map((k) => ({ o: k.computedOffset, e: k.easing })), props,
      target: a.effect.target || null, pseudo: a.effect.pseudoElement || null });
    n++;
  }
  return n;
}
/** What the pass knows of its animations, as plain data. */
function inPageDescribe() {
  return window.__bc.anims.map((s) => ({ name: s.name, seekable: s.seekable, infinite: s.infinite, wasRunning: s.wasRunning, delay: s.delay, duration: s.duration,
    iterations: s.iterations, direction: s.direction, end: s.end, easing: s.easing, keyframes: s.keyframes, props: s.props, pseudo: s.pseudo }));
}
/** Step through the points: seek every animation, with a rendered frame before each step when `paced` (so the layout-shift observer sees each),
 *  and read what was asked for. pixel: the translation of every animated target must be whole pixels. edges: nothing of the mark past the
 *  left, top or right edge, the page no wider than the screen and no taller than at rest. A box of the mark counts where it is painted: cut by every
 *  ancestor that clips it up to the mark element's own clip, and not at all while it is transparent (opacity 0, its own or an ancestor's) or visibility:
 *  hidden. Reports the worst of each. */
async function inPageSample({ el, points, end, pixel, edges, paced }) {
  const bc = window.__bc, doc = document.documentElement;
  const out = { pixelBad: [], pixelUnread: [], targets: 0, edgeBad: [], edgeCount: 0, boxes: 0, restHeight: null };
  // the box a percentage in `translate` is of: the element's reference box (transform-box), in its own units
  const refBox = (e) => {
    const cs = getComputedStyle(e), px = (p) => parseFloat(cs.getPropertyValue(p)) || 0;
    if (e instanceof SVGGraphicsElement && e.ownerSVGElement) {
      if (cs.transformBox === "view-box") { const v = e.ownerSVGElement, vb = v.viewBox.baseVal; return vb && vb.width ? [vb.width, vb.height] : [v.width.baseVal.value, v.height.baseVal.value]; }
      const b = e.getBBox(); return [b.width, b.height];
    }
    const bw = e instanceof HTMLElement ? e.offsetWidth : e.clientWidth + px("border-left-width") + px("border-right-width");
    const bh = e instanceof HTMLElement ? e.offsetHeight : e.clientHeight + px("border-top-width") + px("border-bottom-width");
    return cs.transformBox === "content-box" ? [bw - px("border-left-width") - px("border-right-width") - px("padding-left") - px("padding-right"),
      bh - px("border-top-width") - px("border-bottom-width") - px("padding-top") - px("padding-bottom")] : [bw, bh];
  };
  // how an element is drawn moved: its translate, rotate and scale properties, then its transform (CSS Transforms 2); null when it cannot be read
  const matrix = (e, pseudo) => {
    const cs = getComputedStyle(e, pseudo);
    let fns = "", ref = null;
    if (cs.translate && cs.translate !== "none") {
      const [x, y = "0px", z = "0px"] = cs.translate.split(" ");
      const len = (v, k) => (!v.endsWith("%") ? parseFloat(v) : pseudo ? NaN : (parseFloat(v) / 100) * (ref ??= refBox(e))[k]);   // a pseudo-element's box is not in the DOM
      const tx = len(x, 0), ty = len(y, 1);
      if (!Number.isFinite(tx) || !Number.isFinite(ty)) return null;
      fns += `translate3d(${tx}px, ${ty}px, ${parseFloat(z) || 0}px) `;
    }
    if (cs.rotate && cs.rotate !== "none") {
      const w = cs.rotate.split(" "), axis = { x: "1, 0, 0", y: "0, 1, 0", z: "0, 0, 1" };
      fns += w.length === 1 ? `rotate(${w[0]}) ` : w.length === 2 ? `rotate3d(${axis[w[0]]}, ${w[1]}) ` : `rotate3d(${w.slice(0, 3).join(", ")}, ${w[3]}) `;
    }
    if (cs.scale && cs.scale !== "none") { const w = cs.scale.split(" "); fns += w.length === 3 ? `scale3d(${w.join(", ")}) ` : `scale(${w.join(", ")}) `; }
    if (cs.transform && cs.transform !== "none") fns += cs.transform;
    try { return new DOMMatrix(fns.trim() || undefined); } catch { return null; }
  };
  const worst = new Map(), EPS = 0.01;   // css px of float noise: a box this close to an edge is not past it
  const note = (who, edge, px, i) => { const k = who + "|" + edge, w = worst.get(k); if (!w || px > w.px) worst.set(k, { who, edge, px, i }); };
  const name = (e) => {
    const tag = e.tagName.toLowerCase(), cls = (e.getAttribute("class") || "").trim().split(/\s+/).filter(Boolean).slice(0, 2), part = e.getAttribute("data-part");
    return tag + (e.id ? "#" + e.id : cls.length ? "." + cls.join(".") : part ? `[data-part=${part}]` : "");
  };
  // the part of a box that is painted: the box cut by what clips it, between the element and the mark element (the mark's own overflow, or an <svg>'s viewport,
  // included), as [left, top, right, bottom]; null when none of it is painted. Read afresh at every point: the clips move with the animation.
  const OPEN = [-Infinity, -Infinity, Infinity, Infinity], cut = (a, b) => [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])];
  const padBox = (a) => {   // the padding box of an element (what its overflow clips to), in the viewport
    const r = a.getBoundingClientRect(), cs = getComputedStyle(a), px = (p) => parseFloat(cs.getPropertyValue(p)) || 0;
    return [r.left + px("border-left-width"), r.top + px("border-top-width"), r.right - px("border-right-width"), r.bottom - px("border-bottom-width")];
  };
  const ownClip = (a) => {   // what an ancestor clips of its content
    const cs = getComputedStyle(a);
    if (cs.display === "contents") return OPEN;
    if (a instanceof SVGSVGElement) {   // an <svg> clips what leaves its viewport, unless it says overflow: visible
      if (cs.overflowX === "visible" && cs.overflowY === "visible") return OPEN;
      if (!a.ownerSVGElement) return padBox(a);
      const m = a.parentNode.getScreenCTM?.();   // a nested <svg>: its x, y, width and height, in the user space it is placed in
      if (!m) return OPEN;
      const xs = [[0, 0], [1, 0], [0, 1], [1, 1]].map(([i, j]) => new DOMPoint(a.x.baseVal.value + i * a.width.baseVal.value, a.y.baseVal.value + j * a.height.baseVal.value).matrixTransform(m));
      return [Math.min(...xs.map((q) => q.x)), Math.min(...xs.map((q) => q.y)), Math.max(...xs.map((q) => q.x)), Math.max(...xs.map((q) => q.y))];
    }
    if (a instanceof SVGElement) return OPEN;
    const both = cs.contain.split(" ").some((c) => c === "paint" || c === "strict" || c === "content"), ox = both || cs.overflowX !== "visible", oy = both || cs.overflowY !== "visible";
    if (!ox && !oy) return OPEN;
    const b = padBox(a);
    return [ox ? b[0] : -Infinity, oy ? b[1] : -Infinity, ox ? b[2] : Infinity, oy ? b[3] : Infinity];
  };
  const containing = (e, cs) => {   // the element whose clip reaches e: a positioned box escapes the overflow of the ancestors between it and its containing block
    if (cs.position !== "absolute" && cs.position !== "fixed") return e.parentElement;
    for (let n = e.parentElement; n; n = n.parentElement) {
      const c = getComputedStyle(n);
      if ((cs.position === "absolute" && c.position !== "static") || c.transform !== "none" || c.perspective !== "none" || c.filter !== "none" || /paint|layout|strict|content/.test(c.contain)) return n;
    }
    return null;
  };
  let seen = new Map();   // element -> {alpha: the product of the opacity of it and its ancestors, clip: what clips it between the mark element and it}
  const state = (e) => {
    let m = seen.get(e);
    if (m) return m;
    const cs = getComputedStyle(e);
    let alpha = parseFloat(cs.opacity), clip = OPEN;
    if (e === el) for (let n = e.parentElement; n; n = n.parentElement) alpha *= parseFloat(getComputedStyle(n).opacity);
    else {
      alpha *= state(e.parentElement).alpha;
      const cb = containing(e, cs);
      if (cb && el.contains(cb)) clip = cut(state(cb).clip, ownClip(cb));
    }
    m = { alpha, clip, hidden: cs.visibility === "hidden" || cs.visibility === "collapse" };
    seen.set(e, m);
    return m;
  };
  const painted = (e) => {
    const m = state(e);
    if (!(m.alpha > 0) || m.hidden) return null;
    const r = e.getBoundingClientRect(), box = [r.left, r.top, r.right, r.bottom];   // the box of a nested <svg> is that of its content, which its own viewport clips as well
    const p = cut(e instanceof SVGSVGElement && e.ownerSVGElement ? cut(box, ownClip(e)) : box, m.clip), w = p[2] - p[0], h = p[3] - p[1];
    return w >= 0 && h >= 0 && (w > 0 || h > 0) ? p : null;   // a box with no extent, or none of it inside what clips it, is not painted
  };
  if (edges) { bc.seek(end); out.restHeight = doc.scrollHeight; }   // "at rest": every animation at its end
  out.targets = new Set(bc.anims.filter((s) => s.target).map((s) => s.target)).size;
  for (let i = 0; i < points.length; i++) {
    if (paced) await bc.frame();
    bc.seek(points[i]);
    if (pixel) {
      for (const s of bc.anims) {
        if (!s.target) continue;
        const m = matrix(s.target, s.pseudo);
        if (!m) { if (!out.pixelUnread.includes(s.name)) out.pixelUnread.push(s.name); continue; }
        if (Math.abs(m.e - Math.round(m.e)) > 0.01 || Math.abs(m.f - Math.round(m.f)) > 0.01) out.pixelBad.push({ i, name: s.name, e: m.e, f: m.f });
      }
    }
    if (edges) {
      const cw = doc.clientWidth;
      if (doc.scrollWidth > cw) note("html", "right", doc.scrollWidth - cw, i);
      if (doc.scrollHeight > out.restHeight) note("html", "bottom", doc.scrollHeight - out.restHeight, i);
      let boxes = 0;
      seen = new Map();
      for (const e of [el, ...el.querySelectorAll("*")]) {
        const r = painted(e);
        if (!r) continue;
        boxes++;
        if (r[0] < -EPS) note(name(e), "left", -r[0], i);
        if (r[1] < -EPS) note(name(e), "top", -r[1], i);
        if (r[2] > cw + EPS) note(name(e), "right", r[2] - cw, i);
      }
      out.boxes = Math.max(out.boxes, boxes);
    }
  }
  if (paced) { await bc.frame(); await bc.frame(); }
  bc.drain();
  out.edgeCount = worst.size;
  out.edgeBad = [...worst.values()].sort((a, b) => b.px - a.px || (a.who === "html") - (b.who === "html")).slice(0, 8);   // the page itself after the elements that crossed
  return out;
}
/** Seek every finite animation to its end (finish()), let two frames render, and say what refused. */
async function inPageFinish() {
  const bc = window.__bc, stuck = [];
  for (const s of bc.anims) if (s.seekable && !s.infinite) { try { s.a.finish(); } catch (e) { stuck.push(`${s.name}: ${e.name}`); } }
  await bc.frame(); await bc.frame();
  bc.drain();
  return stuck;
}
/** Turn the state every animation is in (the end of a finished one, the end of the first iteration of an infinite one) into plain style and drop the
 *  animation. A page that keeps an animation is drawn with layers of its own, and what is drawn after them is drawn with antialiasing a few levels off the
 *  same drawing made without one: that is the compositor's noise, not a difference of the rest frame, and it would fail an exact comparison. What is written
 *  is what the page draws, read before anything is cancelled: the computed style of each property an animation moves, for an animation whose effect still
 *  applies (a fill holds it). One whose effect no longer applies (`animation: hide 1s 1s backwards` after its end) is only cancelled: commitStyles() would
 *  write its keyframe value (visibility: hidden) over the style the page has at rest. An animation on a pseudo-element, which has no inline style, and one
 *  with a value that reads empty stay, and are named. */
function inPageSettle() {
  const left = [], plan = [];
  const kebab = (p) => (p.startsWith("--") ? p : p === "cssFloat" ? "float" : p === "cssOffset" ? "offset" : p.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase()));
  for (const s of window.__bc.anims) {
    if (!s.seekable) continue;
    const name = s.name + (s.pseudo ? " on " + s.pseudo : "");
    if (s.a.effect.getComputedTiming().progress === null) { plan.push({ s, vals: [] }); continue; }   // nothing of it applies any more: the style without it is the rest state
    if (s.pseudo || !s.target) { left.push(name); continue; }                                       // nowhere to write the style (a pseudo-element): it stays
    const cs = getComputedStyle(s.target), vals = s.props.map((p) => [kebab(p), cs.getPropertyValue(kebab(p))]);
    if (vals.some(([, v]) => v === "")) { left.push(name); continue; }                              // a value it cannot read is not written: it stays
    plan.push({ s, vals });
  }
  for (const { s } of plan) s.a.cancel();
  for (const { s, vals } of plan) for (const [p, v] of vals) s.target.style.setProperty(p, v);
  return left;
}
/** The animations that are running right now: after every one of the page's has been finished, a started one is a motion that did not end. */
function inPageRunning() {
  return document.getAnimations().filter((a) => a.playState === "running").map((a) => a.animationName || a.transitionProperty || a.id || "animation");
}
/** The mark element's box, in the viewport and in the document, and how it is drawn ("svg" is an outermost <svg>, which has a CSS box of its own). */
function inPageGeometry(el) {
  const r = el.getBoundingClientRect();
  return { vx: r.left, vy: r.top, x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, tag: el.tagName.toLowerCase(),
    inView: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
    kind: el instanceof HTMLImageElement ? "img" : el instanceof SVGSVGElement && !el.ownerSVGElement ? "svg" : "other" };
}
/** Hide the element for two rendered frames and show it again, so that what the screenshot takes is a fresh drawing of its box: a part a CSS transition
 *  moved across the mark can leave the old drawing of the places it passed until something draws them again. */
async function inPageRepaint(el) {
  const bc = window.__bc, keep = ["visibility", "transition"].map((p) => [p, el.style.getPropertyValue(p), el.style.getPropertyPriority(p)]);
  el.style.setProperty("transition", "none", "important"); el.style.setProperty("visibility", "hidden", "important");
  await bc.frame(); await bc.frame();
  for (const [p, v, pr] of keep) v ? el.style.setProperty(p, v, pr) : el.style.removeProperty(p);
  await bc.frame(); await bc.frame();
}
/** Draw the static SVG where the element draws at rest and hide what the element draws: the same page and place, so the same raster tiles.
 *  - An <img> shows the still itself: its source is swapped (its size held), so its box, border, padding, ancestors and raster are its own.
 *  - Anything else: the still in a shadow root (the page's style sheets cannot reach it, so they neither style nor animate it; the host resets every
 *    inherited property), on a host in the element's own parent (the parent's opacity, filter and transform apply to it too), over the content box of
 *    an <svg> (whose children are hidden, so its own border and background stay) or the whole box of anything else (hidden as a whole), with the
 *    element's own transform about the same origin. The host is placed by measuring it, so a positioned or offset ancestor does not move it.
 *  -> {off}: how far, in css px, the placed box ended from the element's (more than 0.01 when an ancestor rotates or skews it). inPageRestore undoes. */
async function inPageReference({ el, g, text, url }) {
  const bc = window.__bc, undo = [];
  bc.undo = () => { for (const u of undo.reverse()) u(); };
  const hold = (n, props) => { const keep = props.map((p) => [p, n.style.getPropertyValue(p), n.style.getPropertyPriority(p)]); undo.push(() => { for (const [p, v, pr] of keep) v ? n.style.setProperty(p, v, pr) : n.style.removeProperty(p); }); };
  if (g.kind === "img") {
    const cs = getComputedStyle(el), attrs = ["src", "srcset", "sizes", "loading"].map((a) => [a, el.getAttribute(a)]);
    const pic = el.parentElement instanceof HTMLPictureElement ? el.parentElement : null, sources = pic ? [...pic.querySelectorAll(":scope > source")] : [];
    hold(el, ["width", "height"]);
    undo.push(() => { for (const [a, v] of attrs) v === null ? el.removeAttribute(a) : el.setAttribute(a, v); for (const s of sources) pic.insertBefore(s, el); });
    el.style.setProperty("width", cs.width, "important"); el.style.setProperty("height", cs.height, "important");
    for (const s of sources) s.remove();
    el.removeAttribute("srcset"); el.removeAttribute("sizes"); el.setAttribute("loading", "eager"); el.setAttribute("src", url);
    await el.decode();
    await bc.frame(); await bc.frame();
    return { off: 0 };
  }
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  if (doc.querySelector("parsererror") || doc.documentElement.localName !== "svg") throw new Error("it is not a well-formed SVG document");
  const svg = document.importNode(doc.documentElement, true);
  svg.removeAttribute("width"); svg.removeAttribute("height");
  for (const [k, v] of [["display", "block"], ["width", "100%"], ["height", "100%"]]) svg.style.setProperty(k, v, "important");
  const host = document.createElement("bc-reference");
  host.attachShadow({ mode: "open" }).appendChild(svg);
  const cs = getComputedStyle(el), px = (p) => parseFloat(cs.getPropertyValue(p)) || 0, inner = g.kind === "svg";
  const ox = inner ? px("border-left-width") + px("padding-left") : 0, oy = inner ? px("border-top-width") + px("padding-top") : 0;
  // the element's box in its own css px, measured with its own transform off; the ancestors' scale is what the viewport adds
  hold(el, ["transform", "translate", "rotate", "scale"]);
  for (const p of ["transform", "translate", "rotate", "scale"]) el.style.setProperty(p, "none", "important");
  const R = el.getBoundingClientRect();
  const BW = el instanceof HTMLElement ? el.offsetWidth : inner ? el.clientWidth + px("border-left-width") + px("border-right-width") : R.width;
  const BH = el instanceof HTMLElement ? el.offsetHeight : inner ? el.clientHeight + px("border-top-width") + px("border-bottom-width") : R.height;
  const W = inner ? el.clientWidth - px("padding-left") - px("padding-right") : BW, H = inner ? el.clientHeight - px("padding-top") - px("padding-bottom") : BH;
  const sx = BW ? R.width / BW : 1, sy = BH ? R.height / BH : 1;
  undo.pop()();   // the element's own transform back
  const set = (k, v) => host.style.setProperty(k, v, "important");
  host.style.setProperty("all", "initial", "important");
  for (const [k, v] of Object.entries({ display: "block", position: "absolute", left: "0px", top: "0px", width: W + "px", height: H + "px", "pointer-events": "none" })) set(k, v);
  if (cs.position !== "static" && cs.zIndex !== "auto") set("z-index", cs.zIndex);
  let parent = el.parentElement;
  while (parent && !(parent instanceof HTMLElement)) parent = parent.parentElement;   // an element inside an <svg>: the host goes next to that <svg>
  (parent || document.body).insertBefore(host, parent === el.parentElement ? el.nextSibling : null);
  undo.push(() => host.remove());
  const r0 = host.getBoundingClientRect();
  set("left", (R.left + ox * sx - r0.left) / sx + "px"); set("top", (R.top + oy * sy - r0.top) / sy + "px");
  const r1 = host.getBoundingClientRect();
  const off = Math.max(Math.abs(r1.left - (R.left + ox * sx)), Math.abs(r1.top - (R.top + oy * sy)), Math.abs(r1.width - W * sx), Math.abs(r1.height - H * sy));
  for (const p of ["transform", "translate", "rotate", "scale"]) set(p, cs.getPropertyValue(p));
  const [tx = 0, ty = 0] = cs.transformOrigin.split(" ").map(parseFloat);
  set("transform-origin", `${tx - ox}px ${ty - oy}px`);
  for (const n of inner ? [...el.children] : [el]) {
    hold(n, ["visibility", "transition"]);
    n.style.setProperty("transition", "none", "important"); n.style.setProperty("visibility", "hidden", "important");
  }
  await bc.frame(); await bc.frame();
  return { off };
}
function inPageRestore() { const bc = window.__bc; if (bc.undo) bc.undo(); bc.undo = null; }

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

/** A scratch page (never navigated, never the page under test) in which two PNGs are compared and the frames of a strip are joined. */
async function scratchPage(browser) {
  const p = await (await browser.newContext()).newPage();
  await p.setContent("<!doctype html><body style='margin:0'></body>");
  return p;
}

/** A browser context and a page loaded, with its fonts, for one pass of a page case. */
async function openPage(browser, server, url, { width = 900, height = 700, dsf = 1, reduced = false } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dsf, reducedMotion: reduced ? "reduce" : "no-preference" });
  const seen = await instrument(ctx, server.origin);
  await ctx.addInitScript(INIT_SCRIPT);
  const page = await ctx.newPage(); watch(page, seen, server.origin);
  await withTimeout(page.goto(url, { waitUntil: "load", timeout: 60000 }), 65000, `loading ${url}`);
  await withTimeout(page.evaluate(() => document.fonts.ready), 30000, "fonts.ready");
  return { ctx, page, seen };
}

async function markElement(page, c) {
  const loc = page.locator(c.selector).first();
  if (!(await loc.count())) die(EXIT.USAGE, `motion case ${c.name}: selector ${c.selector} matches nothing on ${c.page}`);
  return loc.elementHandle();
}

/** How many requestAnimationFrame calls the page makes in the next `ms` (the proof's own frames are not counted). */
const countRaf = (page, ms) => page.evaluate((ms) => { const bc = window.__bc, n0 = bc.raf; return new Promise((r) => setTimeout(() => r(bc.raf - n0), ms)); }, ms);

/** The first moments of a pass: pause every Web Animation where the page has it, watch the page for requestAnimationFrame calls, pause what a script
 *  started meanwhile. A page that keeps calling requestAnimationFrame is driven by it, which cannot be seeked: it is waited for settle_ms in real time
 *  (mode "normal"). A page that shows neither within RAF_PROBE_MS may start its motion later from a script: it is looked at every frame until settle_ms,
 *  and what starts is paused at once and seeked from its own start. Mode "repeat" (the same page at another width) looks the same way and does not wait
 *  for a requestAnimationFrame-driven page. Mode "reduced" (nothing should move, start or be listened for) always watches the page for settle_ms, and
 *  counts the requestAnimationFrame calls of the last QUIET_MS of it.
 *  -> {early: calls while loading, probe: calls after it, alive: calls in the quiet window (reduced), realTime, late: when the motion began, in ms after the page
 *  started loading (performance.now()), when it began after the first look; else null}. */
async function startPass(page, settle, mode = "normal") {
  const early = await page.evaluate(() => window.__bc.raf), t0 = Date.now();
  await page.evaluate(inPageAdopt);
  let calls = await countRaf(page, RAF_PROBE_MS), alive = 0, late = null;
  await page.evaluate(inPageAdopt);
  if (mode === "reduced") {
    await page.waitForTimeout(Math.max(0, settle - RAF_PROBE_MS - QUIET_MS));
    await page.evaluate(inPageAdopt);
    alive = await countRaf(page, QUIET_MS);
    await page.evaluate(inPageAdopt);
    return { early, probe: calls, alive, realTime: false, late };
  }
  if (!calls && !(await page.evaluate(() => window.__bc.anims.length))) {
    const r0 = await page.evaluate(() => window.__bc.raf);
    while (Date.now() - t0 < settle) {
      const raf = await page.evaluate(async () => { await window.__bc.frame(); return window.__bc.raf; });
      if ((await page.evaluate(inPageAdopt)) || raf > r0) { late = Math.round(await page.evaluate(() => performance.now())); calls = raf - r0; break; }
    }
  }
  if (calls > 0 && mode === "normal") { await page.waitForTimeout(Math.max(0, settle - (Date.now() - t0))); await page.evaluate(inPageAdopt); }
  return { early, probe: calls, alive, realTime: calls > 0, late };
}

/** Seek every finite animation to its end (finish()), then the ones this started in turn (the end of one may start the next), a few rounds at most.
 *  -> what refused to finish, what is still running, what could not be turned into plain style, what the pass now knows. */
async function finishAll(page) {
  let stuck = [], more = 0;
  for (let round = 0; round < 4; round++) {
    stuck = await page.evaluate(inPageFinish);
    more = await page.evaluate(inPageAdopt);
    if (!more) break;
  }
  if (more) stuck.push("animations keep starting new ones");
  const running = await page.evaluate(inPageRunning);
  const unsettled = await page.evaluate(inPageSettle);
  return { stuck, running, unsettled, anims: await page.evaluate(inPageDescribe) };
}

/** The screenshot clip of a box: rounded outward to whole pixels, in the viewport when the box lies in it, else in the document (fullPage). */
function clipOf(g) {
  const x = g.inView ? g.vx : g.x, y = g.inView ? g.vy : g.y;
  return { clip: { x: Math.floor(x), y: Math.floor(y), width: Math.ceil(x + g.w) - Math.floor(x), height: Math.ceil(y + g.h) - Math.floor(y) }, fullPage: !g.inView };
}

/** A stage that runs in the page and fails there (no frame was rendered in 3 s: the page is stuck or hidden) is a clear message, exit 3, not a stack. */
const stepped = (c, p) => p.catch((e) => die(EXIT.CANNOT, `motion case ${c.name}: ${String(e.message).split("\n")[0].replace(/^page\.evaluate: (Error: )?/, "")}`));

/** The mark element at rest against the static SVG, in the page itself: a screenshot of the element's box (the page's own background, freshly drawn),
 *  then the static SVG drawn where the element draws (inPageReference) and a screenshot of the same clip. Same page, same position, same raster tiles:
 *  the two pictures are equal to the pixel when the rest frame is the still. (A reference drawn on a scratch page at the origin is not: Chromium
 *  rasterises in tiles about 256 px wide that advance 254 px, so the same drawing differs at another position.) */
async function compareInPlace(page, diff, el, ref, tol) {
  const g = await page.evaluate(inPageGeometry, el);
  if (!(g.w > 0 && g.h > 0)) return { empty: true, g };
  const { clip, fullPage } = clipOf(g);
  await page.evaluate(inPageRepaint, el);
  const shot = await page.screenshot({ clip, fullPage });
  let still, placed;
  try {
    placed = await page.evaluate(inPageReference, { el, g, text: ref.text, url: ref.url });
    still = await page.screenshot({ clip, fullPage });
  } catch (e) {   // the still is the proof's own input: one that cannot be drawn is the proof's fault, not the page's
    die(EXIT.USAGE, `${ref.what} cannot be drawn in the page: ${String(e.message).split("\n")[0].replace(/^page\.evaluate: (\w*Error: )?/, "")}`);
  } finally { await page.evaluate(inPageRestore); }
  if (placed.off > 0.01) return { unplaced: placed.off, g };
  return { g, clip, shot, still, cmp: await pngDiff(diff, shot, still, tol) };
}

/** The row of a rest-frame comparison; the two pictures are kept in the scratch folder (outside the project) when they differ. */
function restRow(report, rid, label, r, tol, saveAs, c, project) {
  if (r.empty) return report.add(rid, "fail", label, { detail: `the mark element (${c.selector}) has no box at rest (display none, or no size): there is nothing to compare`, px_differ: null });
  if (r.unplaced) {
    return report.add(rid, "skipped", label, { detail: `not verified: the still could not be placed exactly over the mark element (${c.selector}): it ended ${Number(r.unplaced.toFixed(2))} css px off, `
      + "as it does when an ancestor rotates or skews the element", px_differ: null });
  }
  const { g, cmp } = r, n2 = (x) => Number(x.toFixed(2));
  if (cmp.diff !== 0) {
    const dir = scratchDir(project, path.join("motion", caseFolder(c.name) || "case"));
    fs.writeFileSync(path.join(dir, `${saveAs}-element.png`), r.shot); fs.writeFileSync(path.join(dir, `${saveAs}-static.png`), r.still); cmp.saved = dir;
  }
  const how = g.kind === "img" ? "the static SVG in the <img> itself (its source swapped)" : g.kind === "svg" ? "the static SVG inline, over the <svg>'s content box"
    : `the static SVG inline, over the whole <${g.tag}>`;
  const left = r.unsettled?.length ? `; ${r.unsettled.join(", ")} could not be turned into plain style and stays on the page, which may colour a few pixels` : "";
  return report.add(rid, cmp.diff === 0 ? "pass" : "fail", label, {
    detail: `${cmp.diff} px differ${tol ? ` by more than ${tol}/255` : ""} (largest difference ${cmp.max}/255, tolerance ${tol}); compared in the page itself, ${n2(g.w)}x${n2(g.h)} px at ${n2(g.x)},${n2(g.y)}, the reference is ${how}${left}${cmp.saved ? `; both images: ${cmp.saved}` : ""}`,
    px_differ: cmp.diff, tolerance: tol,
  });
}

/** The row of one phone width: where, in the motion, the mark or the page went past an edge, and by how much. Motion driven by requestAnimationFrame
 *  (`raf`, the reason) was not stepped through: a crossing found at the points that were is a failure, and nothing found is "not verified". */
function edgesRow(report, rid, w, plan, r, raf = null) {
  const pt = (b) => plan.points[b.i], n1 = (x) => Number(x.toFixed(1));
  const lines = r.edgeBad.map((b) => `at ${pt(b).pct}% (${pt(b).ms} ms): ${b.who} ${n1(b.px)} px past the ${b.edge} edge at ${w} px`
    + (b.who === "html" ? (b.edge === "right" ? " (the page can be swiped sideways)" : " (the page is taller than at rest)") : ""));
  const ok = !lines.length;
  const detail = ok
    ? `${raf ? `not verified: ${raf}; ` : ""}${plan.points.length} sample point(s) over ${plan.length} ms: ${r.boxes ? `no part of the mark (${r.boxes} box(es)) past the left, top or right edge` : `the mark element has no box at ${w} px (not drawn there), so only the page was measured`}; `
      + `the page never wider than ${w} px, never taller than at rest (${r.restHeight} px)`
    : lines.slice(0, 4).join("; ") + (r.edgeCount > 4 ? `; and ${r.edgeCount - 4} more` : "");
  return report.add(rid, !ok ? "fail" : raf ? "skipped" : r.boxes ? "pass" : "warn", `no part of the mark crosses an edge at ${w} px`, {
    detail, width: w, sample_points: plan.points.length, rest_height: r.restHeight, past: r.edgeBad.map((b) => ({ ...b, px: Number(b.px.toFixed(2)) })),
  });
}

async function pageCase(browser, project, server, c, report, inputs, scratch) {
  if (!c.page || !c.selector || !c.static) die(EXIT.USAGE, `motion case ${c.name}: a page case needs "page", "selector" (the mark's element) and "static" (the still SVG)`);
  const { abs, url } = pageUrl(project, server.origin, c.page); inputs.push(abs);
  const staticFile = confine(project, c.static, "static"); if (!fs.existsSync(staticFile)) die(EXIT.USAGE, `motion case ${c.name}: static not found: ${c.static}`); inputs.push(staticFile);
  const staticText = fs.readFileSync(staticFile, "utf8");
  const ref = { text: staticText, url: server.origin + "/" + rel(project, staticFile).split("/").map(encodeURIComponent).join("/"), what: `motion case ${c.name}: static ${c.static}` };
  const o = pageOptions(c), id = (s) => `motion:${c.name}:${s}`;
  const pixel = o.pixel ?? pixelArt(staticText);
  const pixelWhy = o.pixel !== null ? `the case says "pixel": ${o.pixel}` : pixel ? 'the static SVG says shape-rendering="crispEdges"' : "the static SVG is not pixel art";
  const diff = await scratch();

  // ---- normal pass, 900 x 700: seek through the motion, then compare the rest frame in place
  const started = Date.now();
  const N = await openPage(browser, server, url);
  const el = await markElement(N.page, c);
  const sp = await startPass(N.page, o.settle);
  const snap = await N.page.evaluate(inPageDescribe);
  const plan = samplePoints(snap);
  const raf0 = await N.page.evaluate(() => window.__bc.raf);
  const sampled = await stepped(c, N.page.evaluate(inPageSample, { el, points: plan.points.map((p) => p.ms), end: plan.length, pixel, edges: false, paced: true }));
  const during = (await N.page.evaluate(() => window.__bc.raf)) - raf0;   // a requestAnimationFrame loop that began after the first look
  const realTime = sp.realTime || during > 0;
  if (!sp.realTime && during > 0) { await N.page.waitForTimeout(o.settle); await N.page.evaluate(inPageAdopt); }
  // the page was given settle_ms: a requestAnimationFrame loop that still runs never ends
  const alive = realTime ? await countRaf(N.page, QUIET_MS) : 0;
  const fin = await stepped(c, finishAll(N.page));
  const cls = await N.page.evaluate(() => { window.__bc.drain(); return { value: window.__bc.cls, shifts: window.__bc.shifts.length }; });
  const nRest = await compareInPlace(N.page, diff, el, ref, o.tol);
  nRest.unsettled = fin.unsettled;
  const elapsed = Date.now() - started;
  const pt = (b) => plan.points[b.i];
  const rafWhy = realTime ? "the mark is also moved by requestAnimationFrame, which cannot be seeked, so what it draws between two frames is not known" : null;

  const motionSeen = snap.length > 0 || sp.early > 0 || sp.probe > 0 || during > 0;
  const lateSaid = sp.late !== null ? `; the motion began ${sp.late} ms after the page started loading (a script started it), found by looking at every frame` : "";
  report.add(id("control"), motionSeen ? "pass" : "fail", "control: the normal pass shows motion", {
    detail: motionSeen ? `normal pass: ${snap.length} animation(s) seen, ${sp.early + sp.probe + during} requestAnimationFrame call(s) (${sp.early} while the page loaded)${lateSaid}`
      : `no animation and no requestAnimationFrame call within ${o.settle} ms (settle_ms) of load in the normal pass: the reduced-motion result below would prove nothing`,
  });
  const odd = snap.filter((a) => !a.seekable), later = fin.anims.slice(snap.length);
  const kinds = [`${plan.keyframes} more at keyframes`, plan.turns ? `${plan.turns} where an easing turns back or holds a step` : "", plan.own ? `${plan.own} at every 1/${SAMPLE_STEPS} of each animation's own iterations` : ""];
  const seeked = `${snap.length - odd.length} Web Animation(s) paused and seeked at ${plan.points.length} sample point(s) over ${plan.length} ms (0, every 1/${SAMPLE_STEPS} of it, `
    + kinds.filter(Boolean).join(", ") + (plan.thinned ? `; thinned to ${MAX_SAMPLE_POINTS} in all, the keyframes and turns kept first` : "") + ")";
  report.add(id("sampling"), realTime || odd.length || later.length || plan.unknown.length ? "warn" : "info", "how the motion is sampled", {
    detail: (realTime ? `sampled in real time: requestAnimationFrame-driven motion cannot be seeked (${sp.realTime ? `${sp.probe} call(s) ${sp.late !== null ? `from ${sp.late} ms after the page started loading` : `in the first ${RAF_PROBE_MS} ms after load`}` : `${during} call(s) while the animations were stepped through`}; the page was given ${o.settle} ms)`
      + (snap.length > odd.length ? `; ${seeked}` : "") : snap.length > odd.length ? seeked : "no Web Animation on the page: nothing to seek")
      + (sp.late !== null && !sp.realTime ? `; the motion began ${sp.late} ms after the page started loading and was seeked from its own start` : "")
      + (odd.length ? `; ${odd.length} animation(s) on a scroll or view timeline cannot be seeked and are not sampled: ${odd.map((a) => a.name).join(", ")}` : "")
      + (later.length ? `; ${later.length} animation(s) began only when another ended and were finished, not stepped through: ${later.map((a) => a.name).join(", ")}` : "")
      + (plan.unknown.length ? `; easing(s) this proof does not read, taken as linear for the keyframe times: ${plan.unknown.join(", ")}` : ""),
    animations: snap.length, length_ms: plan.length, real_time: realTime, points_ms: plan.points.map((p) => p.ms), points_pct: plan.points.map((p) => p.pct),
    elapsed_ms: elapsed,   // the normal pass, from the page being opened to the rest frame compared: the motion's length is not waited for
  });
  const infinite = fin.anims.filter((a) => a.infinite).map((a) => a.name);
  const rafLoop = alive ? `a requestAnimationFrame loop: ${alive} call(s) in the ${QUIET_MS} ms after the page was given ${o.settle} ms (settle_ms)` : "";
  report.add(id("loops"), infinite.length || alive ? "fail" : "pass", "no infinite loops", {
    detail: infinite.length || alive ? [infinite.length ? `infinite animation(s): ${infinite.join(", ")}; every animation must end on its rest frame (sampled over the first iteration only)` : "", rafLoop].filter(Boolean).join("; ")
      : realTime ? `no infinite animation, and no requestAnimationFrame call in the ${QUIET_MS} ms after settle_ms` : "no infinite animation",
  });
  const open = [...fin.stuck, ...fin.running.map((n) => `${n} still running`)];
  const settled = !infinite.length && !open.length && !alive;
  report.add(id("settled"), settled ? "pass" : "fail", "every animation ends (each is finite and finishes when seeked to its end)", {
    detail: settled ? `${fin.anims.length} animation(s) seen, every one finite, none running once each was seeked to its end${realTime ? "; the requestAnimationFrame calls stopped within settle_ms" : ""}`
      : [infinite.length ? `infinite: ${infinite.join(", ")}` : "", open.length ? `not ended: ${open.join(", ")}` : "", rafLoop].filter(Boolean).join("; "),
  });
  // a layout property moves the page as it runs; Chromium counts no shift under 3 css px between two frames, so a step of the motion that small is never
  // measured: the property itself fails (a transform moves nothing else)
  const layout = [...new Set(fin.anims.flatMap((a) => a.props.filter((p) => LAYOUT_PROPS.test(p)).map((p) => `${p.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase())} (${a.name})`)))];
  report.add(id("cls:normal"), cls.value > o.maxCls || layout.length ? "fail" : "pass", "layout shift (CLS) while the mark moves", {
    detail: `CLS ${cls.value.toFixed(4)} over load + ${plan.points.length} sample point(s) (limit ${o.maxCls}); ${cls.shifts} shift(s)`
      + (layout.length ? `; animates a layout property: ${layout.slice(0, 4).join(", ")}${layout.length > 4 ? ` and ${layout.length - 4} more` : ""}; it moves the page around it as it runs, `
        + "and a step under 3 css px is not counted as a shift, so seeking cannot measure it: move the mark with transform or opacity" : ""),
    cls: cls.value, shifts: cls.shifts, layout_properties: layout,
  });
  restRow(report, id("normal:rest=static"), "rest frame equals the static SVG (after the animation)", nRest, o.tol, "normal", c, project);
  if (N.seen.errors.length || N.seen.nonLocal.length) report.add(id("page:errors"), "fail", "page loads cleanly", { detail: [...N.seen.errors, ...N.seen.nonLocal].slice(0, 3).join(" | ") });
  // whole pixels: the translation of every animated target at every sample point (a pixel mark only; a vector mark may ease smoothly)
  if (pixel) {
    const bad = sampled.pixelBad, unread = sampled.pixelUnread;
    const st = bad.length ? "fail" : realTime || unread.length ? "skipped" : "pass";
    report.add(id("whole-pixel"), st, "motion moves in whole pixels", {
      detail: bad.length ? `a pixel mark (${pixelWhy}): ` + bad.slice(0, 4).map((b) => `${b.name} at ${pt(b).pct}% (${pt(b).ms} ms): translate(${b.e.toFixed(2)}px, ${b.f.toFixed(2)}px)`).join("; ")
        : (st === "skipped" ? `not verified: ${[rafWhy, unread.length ? `the translation of ${unread.join(", ")} cannot be read (a percentage on a pseudo-element)` : ""].filter(Boolean).join("; ")}; ` : "")
          + `a pixel mark (${pixelWhy}): translation was whole pixels at ${plan.points.length} sample point(s) of ${sampled.targets} animated target(s)`,
    });
  } else report.add(id("whole-pixel"), "info", "motion moves in whole pixels (a pixel mark only)", { detail: `a vector mark: smooth easing allowed (${pixelWhy})` });
  await N.ctx.close();

  // ---- the page again at the phone widths: at every sample point, nothing past an edge
  for (const w of o.widths) {
    const W = await openPage(browser, server, url, { width: w, height: PHONE_HEIGHT });
    const wel = await markElement(W.page, c);
    const wsp = await startPass(W.page, o.settle, "repeat");
    const wplan = samplePoints(await W.page.evaluate(inPageDescribe));
    const r = await W.page.evaluate(inPageSample, { el: wel, points: wplan.points.map((p) => p.ms), end: wplan.length, pixel: false, edges: true, paced: false });
    edgesRow(report, id(`edges:${w}`), w, wplan, r, rafWhy ?? (wsp.realTime ? "the page calls requestAnimationFrame at this width, which cannot be seeked" : null));
    await W.ctx.close();
  }
  if (!o.widths.length) report.add(id("edges"), "info", "edges at phone widths", { detail: '"widths" is empty: the edges are not checked at a phone width' });

  // ---- reduced pass: nothing may move
  const R = await openPage(browser, server, url, { reduced: true });
  const rp = await startPass(R.page, o.settle, "reduced");
  const rAnims = await R.page.evaluate(inPageDescribe);
  // the motion listeners are read before Playwright needs a handle of the element, which puts listeners of its own on the window
  const rHooks = await R.page.evaluate(() => [...window.__bc.listeners]);
  // ... also as the browser sees them (inline on* handlers are not seen by the addEventListener hook)
  const cdp = await R.ctx.newCDPSession(R.page); const cdpListeners = [];
  for (const expr of ["window", "document", "document.documentElement", "document.body", `document.querySelector(${JSON.stringify(c.selector)})`]) {
    const { result } = await cdp.send("Runtime.evaluate", { expression: expr });
    if (!result.objectId) continue;
    const { listeners } = await cdp.send("DOMDebugger.getEventListeners", { objectId: result.objectId });
    for (const l of listeners) if (MOTION_EVENTS.includes(l.type)) cdpListeners.push(`${l.type} on ${expr.replace("document.", "").replace(/\(.*/, "")}`);
  }
  const rel0 = await markElement(R.page, c);
  const rfin = await finishAll(R.page);
  const rCls = await R.page.evaluate(() => { window.__bc.drain(); return window.__bc.cls; });
  const rRest = await compareInPlace(R.page, diff, rel0, ref, o.tol);
  rRest.unsettled = rfin.unsettled;
  const running = rAnims.filter((a) => a.wasRunning).map((a) => a.name);
  report.add(id("reduced:animations"), running.length ? "fail" : "pass", "reduced motion: no running animation", {
    detail: running.length ? `${running.length} running: ${running.join(", ")}` : `prefers-reduced-motion: reduce emulated; ${rAnims.length} animation(s), none running`,
  });
  report.add(id("reduced:raf"), rp.alive ? "fail" : "pass", "reduced motion: no requestAnimationFrame loop", {
    detail: `${rp.alive} call(s) in the last ${QUIET_MS} ms of the ${Math.max(o.settle, RAF_PROBE_MS + QUIET_MS)} ms the page was watched (${rp.probe} in the first ${RAF_PROBE_MS} ms after load)`,
  });
  const listeners = [...new Set([...rHooks, ...cdpListeners])];
  report.add(id("reduced:listeners"), listeners.length ? "fail" : "pass", "reduced motion: no motion listeners", {
    detail: listeners.length ? `registered: ${listeners.slice(0, 5).join(", ")} (${MOTION_EVENTS.join(", ")} count as motion)` : `no ${MOTION_EVENTS.join(", ")} listener on window, document, body or the mark`,
  });
  report.add(id("cls:reduced"), rCls > o.maxCls ? "fail" : "pass", "reduced motion: layout shift (CLS)", { detail: `CLS ${rCls.toFixed(4)} (limit ${o.maxCls})`, cls: rCls });
  restRow(report, id("reduced:rest=static"), "reduced motion: the rest frame equals the static SVG", rRest, o.tol, "reduced", c, project);
  await R.ctx.close();
}

/** Read and check a proof file (used before any browser starts). */
function readProof(project, arg) {
  const specFile = confine(project, arg, "proof.json");
  if (!fs.existsSync(specFile)) die(EXIT.USAGE, `motion proof not found: ${arg}`);
  let spec;
  try { spec = JSON.parse(fs.readFileSync(specFile, "utf8")); } catch (e) { die(EXIT.USAGE, `${arg} is not valid JSON: ${e.message}`); }
  if (spec.schema !== 1 || !Array.isArray(spec.cases) || !spec.cases.length) die(EXIT.USAGE, `${arg} needs {"schema": 1, "cases": [ ... ]}`);
  const names = new Set();
  for (const c of spec.cases) {
    if (!c.name || names.has(c.name)) die(EXIT.USAGE, `every motion case needs a unique name (${c.name ?? "missing"})`);
    names.add(c.name);
    if (!["states", "page"].includes(c.type)) die(EXIT.USAGE, `motion case ${c.name}: type must be "states" or "page"`);
    if (c.type === "page") pageOptions(c);
  }
  // the proof's path as the disk spells it (macOS takes MOTION/PROOF.JSON for motion/proof.json): its report is named after it, so one file has one name
  const specRel = path.relative(fs.realpathSync.native(project), fs.realpathSync.native(specFile)).split(path.sep).join("/");
  return { specFile, spec, specRel };
}

async function cmdMotion(values, positionals) {
  if (positionals.length !== 1) die(EXIT.USAGE, "shot --motion needs exactly one proof.json\n" + USAGE);
  const project = findProject(values.project);
  const { specFile, spec, specRel } = readProof(project, positionals[0]);
  const inputs = [specFile];
  const report = new Report(proofReportTool(specRel), project, inputs);   // one report per proof file: assets/_checks/motion/<slug>-<hash6>.json
  const browser = await launch();
  const server = await startServer(project);
  report.extra = { proof: specRel, cases: spec.cases.map((c) => ({ name: c.name, type: c.type })), engine: "Chromium (Playwright)" };
  let diff = null;
  const scratch = async () => (diff ??= await scratchPage(browser));
  try {
    for (const c of spec.cases) {
      if (c.type === "states") await statesCase(browser, project, c, report, inputs);
      else await pageCase(browser, project, server, c, report, inputs, scratch);
    }
  } finally {
    await browser.close();
    await server.close();
  }
  inputs.push(...server.served());   // what the page loaded (tokens.css, a stylesheet, a script, an image): a motion that lives there makes the report stale when it changes
  return report.finish();
}

// ---------------------------------------------------------------- frames <proof.json>: stills of the mark along its motion
// For each page case of a proof (or the one named): seek to each point of the motion (default 0, 25, 50, 75, 100 percent of its length), cut the mark
// element's box out of the page at device scale 2 (the page's own background), and write motion/frames/<case>/<NN>-<pct>.png, strip.png (the frames
// side by side, in order), reduced.png (the element under prefers-reduced-motion: reduce) and frames.json. The files are in the project on purpose (the
// brand book shows them); each is written only on a byte change, so a rerun is byte-identical. A case with nothing to seek fails, and says why.
// A try-out proof (an exploration proof: under rounds/ or a removed-*/ folder; history/ and every round but the latest are refused, see readOnlyWhy) keeps its stills beside it, in
// <its folder>/frames/<case>/, so that a motion round holds its own stills and never touches motion/frames/, the only stills the book replays.
const FRAMES_DSF = 2;
const MAX_PICTURE_PX = 65535;   // the widest and highest picture Chromium's canvas writes (one more is an IndexSizeError)

/** The frames of a strip joined side by side, in order, on a transparent canvas as high as the highest. */
async function joinStrip(diff, pngs) {
  const b64 = await diff.evaluate(async (list) => {
    const bmps = [];
    for (const b of list) bmps.push(await createImageBitmap(await (await fetch("data:image/png;base64," + b)).blob()));
    const cv = new OffscreenCanvas(bmps.reduce((s, b) => s + b.width, 0), Math.max(...bmps.map((b) => b.height))), g = cv.getContext("2d");
    let x = 0;
    for (const b of bmps) { g.drawImage(b, x, 0); x += b.width; }
    const bytes = new Uint8Array(await (await cv.convertToBlob({ type: "image/png" })).arrayBuffer());
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }, pngs.map((b) => b.toString("base64")));
  return Buffer.from(b64, "base64");
}

async function framesCase(browser, server, project, c, slug, base, pcts, specRel, report, inputs, diff) {
  if (!c.page || !c.selector) die(EXIT.USAGE, `motion case ${c.name}: a page case needs "page" and "selector" (the mark's element)`);
  const { abs, url } = pageUrl(project, server.origin, c.page); inputs.push(abs);
  const o = pageOptions(c), rid = `frames:${c.name}`, label = "frames of the mark's motion", dir = `${base}/${slug}`;
  const fail = (detail, extra = {}) => report.add(rid, "fail", label, { detail, ...extra });
  let plan, clip, shots = [], reducedShot;
  const N = await openPage(browser, server, url, { dsf: FRAMES_DSF });
  try {
    const el = await markElement(N.page, c);
    const sp = await startPass(N.page, o.settle);
    const snap = await N.page.evaluate(inPageDescribe);
    plan = samplePoints(snap);
    if (N.seen.errors.length || N.seen.nonLocal.length) return fail(`the page does not load cleanly: ${[...N.seen.errors, ...N.seen.nonLocal].slice(0, 3).join(" | ")}`);
    if (!snap.some((a) => a.seekable) || !(plan.length > 0)) {
      return fail(`no seekable motion: ${!snap.length ? `the page has no Web Animation${sp.realTime ? " (its motion is driven by requestAnimationFrame, which cannot be seeked)" : ""}`
        : snap.some((a) => a.seekable) ? "every animation has zero length" : "its animations run on a scroll or view timeline, which cannot be seeked"}`);
    }
    await N.page.evaluate((t) => window.__bc.seek(t), plan.length);   // the box the frames are cut from: the mark's box at rest
    const g = await N.page.evaluate(inPageGeometry, el);
    if (!(g.w > 0 && g.h > 0)) return fail(`the mark element (${c.selector}) has no box at rest (display none, or no size)`);
    const cut = clipOf(g); clip = cut.clip;
    const one = clip.width * FRAMES_DSF;
    if (one * pcts.length > MAX_PICTURE_PX || clip.height * FRAMES_DSF > MAX_PICTURE_PX) {
      die(EXIT.USAGE, `motion case ${c.name}: strip.png would be ${one * pcts.length} x ${clip.height * FRAMES_DSF} px (${pcts.length} still(s) of ${one} px at ${FRAMES_DSF}x), and Chromium `
        + `writes a picture at most ${MAX_PICTURE_PX} px wide and high: ${one <= MAX_PICTURE_PX && clip.height * FRAMES_DSF <= MAX_PICTURE_PX ? `ask for ${Math.floor(MAX_PICTURE_PX / one)} still(s) or fewer (--count or --at)` : "the mark is too large for a still"}`);
    }
    const raf0 = await N.page.evaluate(() => window.__bc.raf);
    for (const p of pcts) {
      const ms = Math.round(plan.length * p) / 100;
      await N.page.evaluate(async (t) => { window.__bc.seek(t); await window.__bc.frame(); }, ms);
      shots.push({ percent: p, ms, png: await N.page.screenshot({ clip, fullPage: cut.fullPage }) });
    }
    const moving = (await N.page.evaluate(() => window.__bc.raf)) - raf0;
    if (moving) return fail(`not reproducible: the page also moves by requestAnimationFrame (${moving} call(s) while the stills were taken), which cannot be seeked, `
      + "so the stills would change from run to run; no file was written");
  } finally { await N.ctx.close(); }
  const R = await openPage(browser, server, url, { dsf: FRAMES_DSF, reduced: true });
  try {
    const el = await markElement(R.page, c);
    await startPass(R.page, o.settle, "repeat");
    await finishAll(R.page);
    const g = await R.page.evaluate(inPageGeometry, el);
    if (!(g.w > 0 && g.h > 0)) return fail(`the mark element (${c.selector}) has no box under reduced motion (display none, or no size)`);
    const cut = clipOf(g);
    reducedShot = await R.page.screenshot({ clip: cut.clip, fullPage: cut.fullPage });
  } finally { await R.ctx.close(); }

  const strip = await joinStrip(diff, shots.map((s) => s.png));
  const pad = Math.max(2, String(shots.length - 1).length);
  const files = shots.map((s, i) => ({ rel: `${dir}/${String(i).padStart(pad, "0")}-${s.percent}.png`, buf: s.png }));
  files.push({ rel: `${dir}/strip.png`, buf: strip }, { rel: `${dir}/reduced.png`, buf: reducedShot });
  const doc = {
    schema: 1, case: c.name, proof: specRel, page: c.page, selector: c.selector, length_ms: plan.length, scale: FRAMES_DSF, size: [clip.width, clip.height],
    frames: shots.map((s, i) => ({ percent: s.percent, ms: s.ms, file: files[i].rel, sha256: sha256(s.png) })),
    strip: { file: files[shots.length].rel, sha256: sha256(strip) }, reduced: { file: files[shots.length + 1].rel, sha256: sha256(reducedShot) },
  };
  files.push({ rel: `${dir}/frames.json`, buf: Buffer.from(JSON.stringify(doc, null, 2) + "\n") });
  const changed = files.filter((f) => writeIfChanged(confine(project, f.rel, "frames file"), f.buf)).map((f) => f.rel);
  report.add(rid, "pass", label, {
    detail: `${shots.length} frame(s) at ${pcts.join(", ")}% of ${plan.length} ms, ${clip.width}x${clip.height} px at ${FRAMES_DSF}x, strip.png, reduced.png and frames.json in ${dir}/: `
      + (changed.length ? `written (${changed.length} of ${files.length} file(s) changed)` : "unchanged"),
    dir, files: files.map((f) => f.rel), changed,
  });
  // frames of an earlier run with other points stay where they are (nothing is deleted): say so
  const dirAbs = confine(project, dir, "frames folder"), keep = new Set(files.map((f) => path.basename(f.rel)));
  const old = fs.readdirSync(dirAbs).filter((n) => /^\d+-[\d.]+\.png$/.test(n) && !keep.has(n)).sort();
  if (old.length) report.add(`${rid}:stale`, "warn", "frames left from an earlier run", { detail: `${old.join(", ")} in ${dir}/ are not part of this run (other points, or fewer); move them to removed-<date>/` });
}

/** Why the folder of a proof is not written to (null when it can be). history/ is frozen and every round before the latest is read-only: the guard keeps both from an edit, but it cannot see what a
 *  command writes, and `frames` writes its stills beside the proof. */
function readOnlyWhy(project, specRel) {
  const [top, round] = specRel.split("/");
  const tail = "(frames writes its stills beside the proof)";
  const how = "copy the proof and its page into the latest round and run frames there";
  if (top === "history") return `${specRel} is inside history/, which is read-only ${tail}: take the stills before \`freeze\`, or ${how}`;
  if (top !== "rounds" || !/^r\d+$/.test(round ?? "")) return null;
  const dir = path.join(project, "rounds");
  const latest = Math.max(...fs.readdirSync(dir).filter((n) => /^r\d+$/.test(n) && fs.statSync(path.join(dir, n)).isDirectory()).map((n) => Number(n.slice(1))));
  return Number(round.slice(1)) < latest ? `${specRel} is inside rounds/${round}/, and every round before the latest (rounds/r${latest}/) is read-only ${tail}: ${how}` : null;
}

async function cmdFrames(argv) {
  const { values, positionals } = parse(argv, { project: { type: "string" }, case: { type: "string" }, count: { type: "string" }, at: { type: "string" } });
  if (positionals.length !== 1) die(EXIT.USAGE, "frames needs exactly one proof.json\n" + USAGE);
  if (values.count !== undefined && values.at !== undefined) die(EXIT.USAGE, "frames takes --count or --at, not both\n" + USAGE);
  let pcts;
  if (values.at !== undefined) {
    pcts = values.at.split(",").map((s) => (s.trim() === "" ? NaN : Number(s)));
    if (pcts.some((p) => !(p >= 0 && p <= 100))) die(EXIT.USAGE, "--at needs percentages from 0 to 100 separated by commas, such as 0,25,50,75,100");
  } else {
    const n = values.count === undefined ? 5 : Number(values.count);
    if (!Number.isInteger(n) || n < 1 || n > 100) die(EXIT.USAGE, "--count needs a whole number from 1 to 100");
    pcts = n === 1 ? [0] : Array.from({ length: n }, (_, i) => (100 * i) / (n - 1));
  }
  pcts = pcts.map((p) => Math.round(p * 100) / 100);
  const project = findProject(values.project);
  const { specFile, spec, specRel } = readProof(project, positionals[0]);
  let picked = spec.cases.filter((c) => c.type === "page");
  if (values.case !== undefined) {
    const named = spec.cases.find((c) => c.name === values.case);
    if (!named) die(EXIT.USAGE, `no case called ${values.case} in ${positionals[0]} (it has: ${spec.cases.map((c) => c.name).join(", ")})`);
    if (named.type !== "page") die(EXIT.USAGE, `case ${values.case} is a states case; frames works on page cases`);
    picked = [named];
  }
  if (!picked.length) die(EXIT.USAGE, `${positionals[0]} has no page case: frames needs a page that moves the mark`);
  const slugs = picked.map((c) => caseFolder(c.name));   // the case name is a folder name
  if (slugs.some((s) => !s) || new Set(slugs).size !== slugs.length) die(EXIT.USAGE, "the case names must make different folder names (letters, digits, . _ -)");
  const readOnly = readOnlyWhy(project, specRel);   // before the browser starts, before anything is written
  if (readOnly) die(EXIT.USAGE, readOnly);
  // where the stills go: a gated proof (a proof of the project) keeps them in motion/frames/, the one folder the book replays; a try-out proof (in the latest round or a removed-*/ folder)
  // keeps them beside it, in <its folder>/frames/, which no other proof writes to, so a motion round holds its own stills and never touches the project's
  const exploring = motionProofKind(project, specRel) === "exploration";
  const base = exploring ? `${path.posix.dirname(specRel)}/frames` : "motion/frames";
  // a case's folder belongs to one proof: a second proof with a case of the same name never overwrites the stills of the first. A try-out folder whose frames.json names a proof of
  // another folder is a copy of an earlier round (the stills came along with it): it is taken again in place, said in the report
  const copied = [];
  for (const [i, s] of slugs.entries()) {
    const fj = confine(project, `${base}/${s}/frames.json`, "frames file");
    if (!fs.existsSync(fj)) continue;
    let owner;
    try { owner = JSON.parse(fs.readFileSync(fj, "utf8")).proof; } catch (e) { die(EXIT.USAGE, `${base}/${s}/frames.json cannot be read (${e.message}): move ${base}/${s}/ to removed-<date>/ first`); }
    if (owner === specRel) continue;
    if (exploring && typeof owner === "string" && path.posix.dirname(owner) !== path.posix.dirname(specRel)) { copied.push({ name: picked[i].name, dir: `${base}/${s}`, owner }); continue; }
    die(EXIT.USAGE, `${base}/${s}/ holds the stills of ${typeof owner === "string" ? owner : "another proof"}, and a case's stills come from one proof: rename the case in ${specRel}, or move ${base}/${s}/ to removed-<date>/`);
  }
  const inputs = [specFile];
  const report = new Report(proofReportTool(specRel, "frames"), project, inputs);
  report.extra = { proof: specRel, cases: picked.map((c) => ({ name: c.name })), points_pct: pcts, engine: "Chromium (Playwright)" };
  for (const k of copied) report.add(`frames:${k.name}:copied`, "info", "stills copied along with an earlier round", { detail: `${k.dir}/ held the stills of ${k.owner} (the round was copied whole): they are taken again here, for ${specRel}` });
  const browser = await launch();
  const server = await startServer(project);
  try {
    const diff = await scratchPage(browser);
    for (const c of spec.cases) {
      if (picked.includes(c)) await framesCase(browser, server, project, c, slugs[picked.indexOf(c)], base, pcts, specRel, report, inputs, diff);
      else if (values.case === undefined) report.add(`frames:${c.name}`, "info", "frames of the mark's motion", { detail: "a states case has no page to seek; frames works on page cases" });
    }
  } finally {
    await browser.close();
    await server.close();
  }
  inputs.push(...server.served());   // what the page loaded: the stills are stale when one of those files changes
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
    case "frames": return cmdFrames(rest);
    case undefined: case "-h": case "--help": console.log(USAGE); return cmd ? EXIT.PASS : EXIT.USAGE;
    default: return die(EXIT.USAGE, `unknown command ${cmd}\n${USAGE}`);
  }
});
