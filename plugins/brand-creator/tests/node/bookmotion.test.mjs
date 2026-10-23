// The motion chapter's replay in a real browser: a book is built for a project that has motion.json, a motion proof and the stills `frames` took of its page, and
// book.html is opened. The flipbook (the strip <img> itself, cropped by object-fit: none and moved by object-position) is animated by CSS alone, the two labels start
// it again (a new animation-name) and play it four times slower, the checkboxes are reached by the keyboard, reduced motion shows the still and nothing moves, print
// shows the same image whole, and at a time the page is paused at the flipbook is the still of that percent, pixel for pixel, at device scale 1 and 2. The markup, the
// CSS and the lint rows are tested in tests/test_book_motion.py; here the browser decides.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { needSetup, bc, motionProject, readPng, sha256Of, writePage, reportFile as motionReport } from "./_motion.mjs";
import { proofReportTool } from "../../scripts/lib/_common.mjs";
import { loadDep, readSetup } from "../../scripts/lib/_common.mjs";

const CASE = "demo-page", COUNT = 25, LENGTH = 320;   // the Acme demo page: a 320 ms press of the dot, 25 stills of it
const has = (tool) => spawnSync(tool, ["--version"], { encoding: "utf8" }).status === 0;

let built;
/** An Acme project with motion tokens, motion/motion.json (on), the stills of the demo page and every chapter written, and its book built: once for the file. */
function book(t) {
  if (needSetup(t)) return null;
  if (!has("resvg")) { console.error("!!! NOT VERIFIED: resvg is not installed (skipping " + t.name + ")"); t.skip("NOT VERIFIED: resvg is not installed"); return null; }
  if (built) return built;
  const p = motionProject();
  const src = path.join(p, "tokens/primitives.tokens.json"), tok = JSON.parse(fs.readFileSync(src, "utf8"));
  tok.motion = { $type: "duration", base: { $value: { value: 320, unit: "ms" } }, stagger: { $value: { value: 120, unit: "ms" } } };
  tok.easing = { $type: "cubicBezier", standard: { $value: [0.2, 0, 0, 1] } };
  fs.writeFileSync(src, JSON.stringify(tok, null, 2));
  const run = (...args) => { const r = bc([...args, "--project", p]); assert.equal(r.status, 0, `${args.join(" ")}\n${r.stdout}${r.stderr}`); return r; };
  run("tokens");
  run("state", "--set", "tier=standard"); run("state", "--set", "content_languages=en");
  const st = path.join(p, "BRAND-STATE.md");
  fs.writeFileSync(st, fs.readFileSync(st, "utf8").replace("- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)"));
  fs.writeFileSync(path.join(p, "motion/motion.json"), JSON.stringify({
    schema: 1, motion: "on", signature: { name: "Press", description: "The dot presses down two pixels and comes back.", where: ["app icon"] },
    parts: [{ id: "dot", description: "The accent dot of the mark." }],
    timeline: [{ part: "dot", property: "transform", start: "0", duration: "{motion.base}", easing: "{easing.standard}" }], rules: ["reduced motion: nothing moves"],
  }, null, 2));
  const fr = run("frames", "motion/proof.json", "--count", String(COUNT));
  assert.match(fr.stdout, new RegExp(`${COUNT} frame\\(s\\)`));
  run("book", "--init");
  for (const f of fs.readdirSync(path.join(p, "book/chapters"))) {
    const file = path.join(p, "book/chapters", f);
    fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace(/\[\[fill:[\s\S]*?\]\](?!\])/g, "Acme sample text for this slot."));
  }
  const r = run("book");
  assert.doesNotMatch(r.stdout + r.stderr, /jumps between|no stills|frames report/, "the stills of a real run are current and smooth enough");
  const framesDir = path.join(p, "motion/frames", CASE);
  built = { p, file: path.join(p, "book.html"), url: pathToFileURL(path.join(p, "book.html")).href, framesDir, doc: JSON.parse(fs.readFileSync(path.join(framesDir, "frames.json"), "utf8")) };
  return built;
}

/** A Chromium of the data folder's Playwright, the way render.mjs starts it; `fn(browser)` runs, then it is closed. */
async function inBrowser(fn) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = readSetup().browsers_path;
  const browser = await (await loadDep("playwright-core")).chromium.launch({ headless: true });
  try { return await fn(browser); } finally { await browser.close(); }
}

const FLIP = `.motion-demo[data-motion-demo="${CASE}"] .motion-flip`;
const look = (page) => page.evaluate((sel) => {
  const f = document.querySelector(sel), cs = getComputedStyle(f);
  return { name: cs.animationName, duration: cs.animationDuration, count: cs.animationIterationCount, fill: cs.animationFillMode, running: f.getAnimations().map((a) => [a.animationName, a.playState]) };
}, FLIP);
const frame = (page) => page.evaluate(() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok))));
/** The element's picture at the context's device scale (`dsf`), exactly its css size: the clip starts on the device pixel the element is painted from. */
async function shot(page, locator, dsf = 2) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  return readPng(await page.screenshot({ clip: { x: Math.round(box.x * dsf) / dsf, y: Math.round(box.y * dsf) / dsf, width: Math.round(box.width), height: Math.round(box.height) } }));
}
const hidden = (page, sel) => page.evaluate((s) => document.querySelector(s).getClientRects().length === 0, sel);
const display = (page, sel) => page.evaluate((s) => getComputedStyle(document.querySelector(s)).display, sel);

test("the flipbook is animated by CSS alone: the strip, the stills' times, once, ending on the last still", async (t) => {
  const b = book(t); if (!b) return;
  assert.deepEqual(b.doc.frames.map((f) => f.percent).slice(0, 3), [0, 4.17, 8.33]);
  assert.equal(b.doc.length_ms, LENGTH);
  const html = fs.readFileSync(b.file, "utf8");
  assert.doesNotMatch(html, /<script|\son[a-z]+=/);        // no script, no handler: the replay is the page's CSS
  await inBrowser(async (browser) => {
    const ctx = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 1000, height: 800 } }), page = await ctx.newPage();
    await page.goto(b.url);
    const first = await look(page);
    assert.deepEqual([first.name, first.duration, first.count, first.fill], [`bc-flip-${CASE}-r0s0`, "0.32s", "1", "both"]);
    await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
    assert.deepEqual((await look(page)).running, [[`bc-flip-${CASE}-r0s0`, "finished"]]);     // it ran once and stopped
    // the markup the contract names: the flipbook is the strip <img> itself, in a <picture> whose <source> holds the strip, the strip is the file's bytes
    const fig = await page.evaluate((c) => {
      const f = document.querySelector(`figure[data-motion-demo="${c}"]`), i = f.querySelector(".motion-flip"), cs = getComputedStyle(i);
      return { length: f.dataset.lengthMs, frames: f.dataset.frames, tags: [...f.children].map((e) => e.tagName.toLowerCase()), flip: i.tagName.toLowerCase(), fit: cs.objectFit, box: [i.width, i.height],
        natural: [i.naturalWidth, i.naturalHeight], src: i.getAttribute("src"), current: i.currentSrc, picture: [...i.parentElement.children].map((e) => e.tagName.toLowerCase()),
        stage: [...f.querySelector(".motion-stage").children].map((e) => e.tagName.toLowerCase() + (e.className ? "." + e.className : "")), noSrc: document.querySelectorAll("img:not([src])").length };
    }, CASE);
    assert.deepEqual([fig.length, fig.frames, fig.flip, fig.fit], [String(LENGTH), String(COUNT), "img", "none"]);
    assert.deepEqual(fig.tags, ["input", "label", "input", "label", "div", "p", "figcaption"]);      // no print-only strip: the flipbook is the strip, once
    assert.deepEqual(fig.stage, ["picture", "img.motion-reduced"]);
    assert.deepEqual(fig.picture, ["source", "img"]);
    const [w, h] = b.doc.size;
    assert.deepEqual(fig.box, [w, h]);                                                               // the img is one still wide and high ...
    assert.deepEqual(fig.natural, [COUNT * w, h]);                                                   // ... and its strip is COUNT stills at their css size: the density of its <source>'s srcset
    // valid HTML: every <img> has a src. The flipbook's is a 1 x 1 stand-in the browser does not draw: the <source> matches, so the strip is what the img shows
    assert.equal(fig.noSrc, 0);
    assert.match(fig.src, /^data:image\/png;base64,/);
    assert.ok(fig.src.length < 200 && fig.current !== fig.src && fig.current === "data:image/png;base64," + fs.readFileSync(path.join(b.framesDir, "strip.png")).toString("base64"), "the flipbook shows the stand-in, not the strip");
    assert.deepEqual(await page.evaluate((src) => new Promise((ok) => { const im = new Image(); im.onload = () => ok([im.naturalWidth, im.naturalHeight]); im.src = src; }), fig.src), [1, 1]);
    assert.equal(fs.readFileSync(b.file, "utf8").split(fs.readFileSync(path.join(b.framesDir, "strip.png")).toString("base64")).length - 1, 1, "the strip is embedded once");
    await ctx.close();
  });
});

test("the two labels start the flipbook again with a new animation-name and play it four times slower; the keyboard does the same", async (t) => {
  const b = book(t); if (!b) return;
  await inBrowser(async (browser) => {
    const ctx = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 1000, height: 800 } }), page = await ctx.newPage();
    await page.goto(b.url);
    await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
    const name = async () => (await look(page)).name;
    assert.equal(await name(), `bc-flip-${CASE}-r0s0`);
    await page.locator(`label[for="bc-replay-${CASE}"]`).click();
    let l = await look(page);
    assert.deepEqual([l.name, l.duration], [`bc-flip-${CASE}-r1s0`, "0.32s"]);                                   // a new name: a new run, from its first still
    await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
    await page.locator(`label[for="bc-replay-${CASE}"]`).click();
    l = await look(page);
    assert.equal(l.name, `bc-flip-${CASE}-r0s0`);                                                               // and every click starts it again, checked or not
    await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
    // read in the same task as the click, so that a slow machine cannot let the 320 ms run out first: the run that begins is a new one, at its start
    const run = await page.evaluate(({ sel, label }) => { document.querySelector(label).click(); const a = document.querySelector(sel).getAnimations()[0]; return [a.animationName, a.playState, a.currentTime]; },
      { sel: FLIP, label: `label[for="bc-replay-${CASE}"]` });
    assert.equal(run[0], `bc-flip-${CASE}-r1s0`); assert.notEqual(run[1], "finished"); assert.ok(run[2] < 50, `the run starts at ${run[2]} ms`);
    await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
    await page.locator(`label[for="bc-replay-${CASE}"]`).click();                                               // back to the unchecked state
    await page.locator(`label[for="bc-slow-${CASE}"]`).click();
    l = await look(page);
    assert.deepEqual([l.name, l.duration], [`bc-flip-${CASE}-r0s1`, "1.28s"]);                                   // four times the 320 ms
    await page.locator(`label[for="bc-replay-${CASE}"]`).click();
    l = await look(page);
    assert.deepEqual([l.name, l.duration], [`bc-flip-${CASE}-r1s1`, "1.28s"]);                                   // replay while slow: still slow, and again from the start
    // the keyboard: the checkboxes take focus, and Space toggles them like a click
    await page.locator(`label[for="bc-slow-${CASE}"]`).click();
    await page.focus(`#bc-replay-${CASE}`);
    assert.equal(await page.evaluate(() => document.activeElement.id), `bc-replay-${CASE}`);
    const before = await name();
    await page.keyboard.press("Space");
    assert.notEqual(await name(), before);
    await page.focus(`#bc-slow-${CASE}`);
    assert.equal(await page.evaluate(() => document.activeElement.id), `bc-slow-${CASE}`);
    await ctx.close();
  });
});

test("under reduced motion the reduced still is shown, and the flipbook and the controls are not, and nothing is running", async (t) => {
  const b = book(t); if (!b) return;
  await inBrowser(async (browser) => {
    const ctx = await browser.newContext({ reducedMotion: "reduce", deviceScaleFactor: 2, viewport: { width: 1000, height: 800 } }), page = await ctx.newPage();
    await page.goto(b.url);
    assert.equal(await display(page, ".motion-reduced"), "block");
    for (const s of [".motion-flip", ".motion-demo input", ".motion-demo label", ".motion-times"]) assert.ok(await hidden(page, s), `${s} takes room under reduced motion`);
    assert.equal(await page.evaluate((sel) => document.querySelector(sel).getAnimations().length, FLIP), 0);
    assert.equal(await page.evaluate(() => document.getAnimations().length), 0, "nothing in the book moves");
    // the still is reduced.png itself: the reduced still, drawn at its size, is the file's picture to the pixel
    const got = await shot(page, page.locator(`figure[data-motion-demo="${CASE}"] .motion-reduced`));
    const want = readPng(fs.readFileSync(path.join(b.p, b.doc.reduced.file)));
    assert.deepEqual([got.w, got.h], [want.w, want.h]);
    assert.ok(got.px.equals(want.px), "the reduced still differs from reduced.png");
    await ctx.close();
  });
});

test("in print the flipbook is shown whole, with no animation, scaled to the page, and its times; the controls and the reduced still are not", async (t) => {
  const b = book(t); if (!b) return;
  await inBrowser(async (browser) => {
    const ctx = await browser.newContext({ viewport: { width: 1000, height: 800 } }), page = await ctx.newPage();
    await page.goto(b.url);
    assert.equal(await display(page, ".motion-times"), "none");                // on a screen the times are not there
    await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
    const [w, h] = b.doc.size, screen = await page.locator(FLIP).boundingBox();
    assert.deepEqual([screen.width, screen.height], [w, h]);                   // on a screen: one still
    await page.emulateMedia({ media: "print" });
    assert.equal(await display(page, ".motion-times"), "block");
    assert.equal(await display(page, ".motion-flip"), "block");
    for (const s of [".motion-demo input", ".motion-demo label"]) assert.equal(await display(page, s), "none", s);
    assert.ok(await hidden(page, ".motion-reduced"), "the reduced still takes room on the printed page");
    assert.equal(await page.evaluate((sel) => document.querySelector(sel).getAnimations().length, FLIP), 0, "the printed flipbook still moves");
    const box = await page.locator(FLIP).boundingBox(), page_w = await page.evaluate(() => document.documentElement.clientWidth);
    assert.ok(Math.abs(box.width / box.height - (COUNT * w) / h) < 0.01, "the strip keeps its proportions");
    assert.ok(box.width > w && box.width <= page_w, `the strip is scaled to the page (${box.width} px of ${page_w})`);
    await ctx.close();
  });
});

test("in print with reduced motion on the strip is shown whole and the reduced still is not: the reduced-motion rules are for a screen", async (t) => {
  const b = book(t); if (!b) return;
  await inBrowser(async (browser) => {
    const ctx = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1000, height: 800 } }), page = await ctx.newPage();
    await page.goto(b.url);
    assert.equal(await display(page, ".motion-flip"), "none");                 // on a screen with reduced motion: the still, not the strip ...
    assert.equal(await display(page, ".motion-reduced"), "block");
    await page.emulateMedia({ media: "print" });                              // ... and printed with the preference still on: the strip whole, as without it
    assert.equal(await page.evaluate(() => matchMedia("print").matches && matchMedia("(prefers-reduced-motion: reduce)").matches), true, "the page is in print with reduced motion on");
    assert.equal(await display(page, ".motion-flip"), "block");
    assert.ok(await hidden(page, ".motion-reduced"), "the reduced still takes room on a printed page that asked for reduced motion");
    assert.equal(await display(page, ".motion-times"), "block");
    for (const s of [".motion-demo input", ".motion-demo label"]) assert.equal(await display(page, s), "none", s);
    assert.equal(await page.evaluate(() => document.getAnimations().length), 0, "something moves in print");
    const [w, h] = b.doc.size, box = await page.locator(FLIP).boundingBox();
    assert.ok(Math.abs(box.width / box.height - (COUNT * w) / h) < 0.01 && box.width > w, `the whole strip is not shown (${box.width} x ${box.height} px)`);
    await ctx.close();
  });
});

test("paused at the time of a still, the flipbook shows that still, pixel for pixel, and between two stills the earlier one: at device scale 2 and at 1", async (t) => {
  const b = book(t); if (!b) return;
  await inBrowser(async (browser) => {
    for (const dsf of [2, 1]) {
      const ctx = await browser.newContext({ deviceScaleFactor: dsf, viewport: { width: 1000, height: 800 } }), page = await ctx.newPage();
      await page.goto(b.url);
      await page.waitForFunction((sel) => document.querySelector(sel).getAnimations().every((a) => a.playState === "finished"), FLIP);
      const flip = page.locator(FLIP);
      await flip.scrollIntoViewIfNeeded();
      const [w, h] = b.doc.size;
      const still = (k) => readPng(fs.readFileSync(path.join(b.p, b.doc.frames[k].file)));
      // "that still drawn at the same size": the file as an <img> of the flipbook's size on a blank page, at the same scale
      const ref = await ctx.newPage();
      const drawn = async (k) => {
        await ref.setContent(`<body style="margin:0"><img id="r" style="display:block;width:${w}px;height:${h}px" src="data:image/png;base64,${fs.readFileSync(path.join(b.p, b.doc.frames[k].file)).toString("base64")}"></body>`);
        await ref.evaluate(() => document.getElementById("r").decode());
        return readPng(await ref.locator("#r").screenshot());
      };
      const at = async (ms) => {
        await flip.evaluate((el, t) => { const a = el.getAnimations()[0]; a.pause(); a.currentTime = t; }, ms);
        await frame(page);
        return shot(page, flip, dsf);
      };
      const last = COUNT - 1, picks = [0, 6, 12, 18, last], seen = [];
      for (const k of picks) {
        const f = b.doc.frames[k];
        const got = await at(k === last ? LENGTH : f.ms + 0.01);
        assert.deepEqual([got.w, got.h], [w * dsf, h * dsf]);
        if (dsf === 2) assert.ok(got.px.equals(still(k).px), `at ${f.percent}% (${f.ms} ms) the flipbook is not the still ${k}`);      // the stills are 2x: the file itself, one device pixel each
        assert.ok(got.px.equals((await drawn(k)).px), `at dsf ${dsf}, at ${f.percent}% the flipbook is not that still drawn at its size`);
        seen.push(sha256Of(got.px));
        if (k < last) {   // half way to the next still it has not moved on: each still holds until the next
          const mid = await at((f.ms + b.doc.frames[k + 1].ms) / 2);
          assert.ok(mid.px.equals(got.px), `at dsf ${dsf}, half way from still ${k} to the next the flipbook changed`);
        }
      }
      // a comparison that cannot see a difference proves nothing: these stills differ (the dot is pressed down between 25 and 75 percent), and the flipbook follows them
      assert.ok(new Set(seen).size >= 3, "the stills to compare are not different pictures");
      assert.ok(!(await at(b.doc.frames[6].ms + 0.01)).px.equals((await drawn(12)).px), "the flipbook at 25 percent is the still of 50 percent");
      await ctx.close();
    }
  });
});

test("the replay is in the book as one page: no network, and every image is a data: URI", async (t) => {
  const b = book(t); if (!b) return;
  await inBrowser(async (browser) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 800 } }), page = await ctx.newPage();
    const seen = [];
    page.on("request", (r) => seen.push(r.url()));
    await page.goto(b.url);
    await page.waitForLoadState("load");
    assert.deepEqual(seen.filter((u) => !u.startsWith("file:") && !u.startsWith("data:")), [], "the book asked the network for something");
    const srcs = await page.evaluate(() => [...document.images].map((i) => i.currentSrc || i.getAttribute("src")));      // the flipbook's picture is its <source>'s
    assert.ok(srcs.length > 3 && srcs.every((u) => u.startsWith("data:")), "an image of the book is not a data: URI");
    assert.match(await page.evaluate((sel) => document.querySelector(sel).currentSrc, FLIP), /^data:image\/png;base64,/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, "at 390 px the page cannot be swiped sideways");
    await ctx.close();
  });
});

test("a motion that lives in a file the page links is part of the proof: change the token and the frames and motion reports are stale, and the book says so", (t) => {
  if (needSetup(t)) return;
  if (!has("resvg")) { console.error("!!! NOT VERIFIED: resvg is not installed (skipping " + t.name + ")"); t.skip("NOT VERIFIED: resvg is not installed"); return; }
  const p = motionProject();
  const src = path.join(p, "tokens/primitives.tokens.json"), setBase = (ms) => {
    const tok = JSON.parse(fs.readFileSync(src, "utf8"));
    tok.motion = { $type: "duration", base: { $value: { value: ms, unit: "ms" } } };
    tok.easing = { $type: "cubicBezier", standard: { $value: [0.2, 0, 0, 1] } };
    fs.writeFileSync(src, JSON.stringify(tok, null, 2));
  };
  const run = (...args) => { const r = bc([...args, "--project", p]); assert.equal(r.status, 0, `${args.join(" ")}\n${r.stdout}${r.stderr}`); return r; };
  setBase(320);
  run("tokens");
  assert.match(fs.readFileSync(path.join(p, "assets/tokens/tokens.css"), "utf8"), /--motion-base: 320ms;/);
  // the demo page, with its motion in the token: the stylesheet is not the page, and the page does not name the length
  writePage(p, "token", { head: '<link rel="stylesheet" href="../assets/tokens/tokens.css">', css: "#mark{display:block;width:64px;height:64px}#dot{animation:press var(--motion-base) steps(2,end) 1 both}"
    + "@keyframes press{0%{transform:translateY(0)}50%{transform:translateY(2px)}100%{transform:translateY(0)}}@media (prefers-reduced-motion: reduce){#dot{animation:none}}",
    body: fs.readFileSync(path.join(p, "motion/demo.html"), "utf8").match(/<svg[\s\S]*<\/svg>/)[0] });
  const proof = JSON.parse(fs.readFileSync(path.join(p, "motion/proof.json"), "utf8"));
  proof.cases = proof.cases.filter((c) => c.name !== "demo-page");
  proof.cases.push({ name: "token-page", type: "page", page: "motion/token.html", selector: "#mark", static: "assets/logo/mark.svg", settle_ms: 700 });
  fs.writeFileSync(path.join(p, "motion/proof.json"), JSON.stringify(proof, null, 2));
  run("state", "--set", "tier=standard"); run("state", "--set", "content_languages=en");
  const st = path.join(p, "BRAND-STATE.md");
  fs.writeFileSync(st, fs.readFileSync(st, "utf8").replace("- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)"));
  fs.writeFileSync(path.join(p, "motion/motion.json"), JSON.stringify({ schema: 1, motion: "on", signature: { name: "Press", description: "The dot presses down two pixels and comes back.", where: ["app icon"] },
    parts: [{ id: "dot", description: "The accent dot of the mark." }], timeline: [{ part: "dot", property: "transform", start: "0", duration: "{motion.base}", easing: "{easing.standard}" }], rules: ["reduced motion: nothing moves"] }, null, 2));
  run("frames", "motion/proof.json", "--count", "9");
  const shot = run("shot", "--motion", "motion/proof.json");
  const framesFile = path.join(p, "assets/_checks", proofReportTool("motion/proof.json", "frames") + ".json");
  for (const f of [framesFile, motionReport(p)]) {
    const inputs = JSON.parse(fs.readFileSync(f, "utf8")).inputs.map((i) => i.path);
    assert.ok(inputs.includes("assets/tokens/tokens.css") && inputs.includes("motion/token.html"), `${path.basename(f)}: ${inputs.join(", ")}`);
    assert.equal(new Set(inputs).size, inputs.length, "an input is recorded once");
  }
  assert.match(shot.stdout, /demo-page|token-page/);
  run("book", "--init");
  for (const f of fs.readdirSync(path.join(p, "book/chapters"))) { const file = path.join(p, "book/chapters", f); fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace(/\[\[fill:[\s\S]*?\]\](?!\])/g, "Acme sample text for this slot.")); }
  const warnings = (r) => (r.stdout.match(/^\[WARN\] book:motion .*$/gm) || []).join("\n");
  const first = run("book");
  assert.doesNotMatch(warnings(first), /stale|frames report/, "the stills are current: " + warnings(first));
  // the token changes: the stills were taken at 320 ms and the page now runs 640 ms, and no file the report named was the page
  setBase(640);
  run("tokens");
  const framesNow = JSON.parse(fs.readFileSync(framesFile, "utf8")).inputs.filter((i) => sha256Of(fs.readFileSync(path.join(p, i.path))) !== i.sha256).map((i) => i.path);
  const motionNow = JSON.parse(fs.readFileSync(motionReport(p), "utf8")).inputs.filter((i) => sha256Of(fs.readFileSync(path.join(p, i.path))) !== i.sha256).map((i) => i.path);
  assert.deepEqual([framesNow, motionNow], [["assets/tokens/tokens.css"], ["assets/tokens/tokens.css"]]);
  const checked = bc(["check", "--project", p]);
  assert.match(checked.stdout, /\[SKIP\] report:motion\/proof-[0-9a-f]{6} \(gate report\): not verified: motion\/proof-[0-9a-f]{6} report is stale \(assets\/tokens\/tokens\.css changed\)/);   // check sees it too
  const second = run("book");
  assert.match(warnings(second), /the frames report of motion\/proof\.json is stale \(assets\/tokens\/tokens\.css changed\); run `brand-creator frames motion\/proof\.json --case token-page --count 9`/);
  assert.match(warnings(second), /the motion report assets\/_checks\/motion\/proof-[0-9a-f]{6}\.json is stale \(assets\/tokens\/tokens\.css changed\)/);
  // check gates the frames report as it gates the motion one. The stills were taken at 320 ms: they stay "not verified" however often shot --motion and book run, until frames has
  const framesRow = /\[SKIP\] report:frames\/proof-[0-9a-f]{6} \(gate report\): not verified: frames\/proof-[0-9a-f]{6} report is stale \(assets\/tokens\/tokens\.css changed\); re-run `brand-creator frames motion\/proof\.json --count 9` and then `brand-creator book`/;
  assert.match(checked.stdout, framesRow);
  run("shot", "--motion", "motion/proof.json");   // what check asked for of the motion report ...
  run("book");
  const asked = bc(["check", "--project", p]);
  assert.doesNotMatch(asked.stdout, /\[SKIP\] report:motion\/proof/, "the motion report is current now");
  assert.match(asked.stdout, framesRow);          // ... and the book still replays the stills of 320 ms: check does not pass them
  run("frames", "motion/proof.json", "--count", "9");
  run("book");
  const done = bc(["check", "--project", p]);
  assert.match(done.stdout, /\[PASS\] report:frames\/proof-[0-9a-f]{6} \(gate report\): frames\/proof-[0-9a-f]{6} report is current and passing/);
  assert.doesNotMatch(done.stdout, /\[SKIP\] report:(frames|motion)\/proof/);
  assert.equal(JSON.parse(fs.readFileSync(path.join(p, "motion/frames/token-page/frames.json"), "utf8")).length_ms, 640, "the stills are of the page as it is now");
});
