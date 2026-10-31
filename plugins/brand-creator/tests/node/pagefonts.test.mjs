// The fonts collector of scripts/pagelib/page_measure.mjs, called directly on a page of its own in Chromium. The page-check tests in tests/test_page_check.py go through
// render.mjs and the judge; here the collector alone is held to what it promises: the mark it puts on an element is always taken off, a debugger that cannot be reached is a
// fact on each entry (not a view that fails), and the first family and the probe element are chosen as documented in scripts/CONTRACT.md.
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { needSetup, ROOT } from "./_helpers.mjs";
import { loadDep, readSetup } from "../../scripts/lib/_common.mjs";
import { collect } from "../../scripts/pagelib/page_measure.mjs";

const PROBE = "[data-bc-font-probe]";
const FONT = fs.readFileSync(path.join(ROOT, "tests", "fixtures", "fonts", "TestFont-subset.ttf")).toString("base64");   // a web font that needs no server and no installed font
const FACES = `@font-face { font-family: "Acme Sans"; src: url(data:font/ttf;base64,${FONT}); } @font-face { font-family: "Acme Mono"; src: url(data:font/ttf;base64,${FONT}); }`;
const glyphs = (u) => u.platform.reduce((n, p) => n + p.glyphs, 0);

/** `html` in a Chromium of the data folder's Playwright, once its fonts are settled; `fn(page)` runs, then the browser is closed. */
async function inPage(html, fn) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = readSetup().browsers_path;
  const browser = await (await loadDep("playwright-core")).chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.setContent(html);
    await page.evaluate(() => document.fonts.ready);
    return await fn(page);
  } finally {
    await browser.close();
  }
}

/** How many elements still carry the probe mark: asked through the `selectors` collector, which runs before the fonts collector, so a second collect() sees what the first left. */
const marked = async (page) => (await collect(page, { selectors: [PROBE] })).selectors[PROBE].count;

test("the mark the fonts collector puts on an element is taken off again, whether the debugger answers or not", async (t) => {
  if (needSetup(t)) return;
  await inPage('<p style="font-family: serif">one</p><p style="font-family: monospace">two</p>', async (page) => {
    assert.equal(await marked(page), 0);
    const first = await collect(page, { selectors: [] });
    assert.equal(first.font_usage.length, 2);
    assert.ok(first.font_usage.every((u) => Array.isArray(u.platform) && u.platform.length > 0 && !("probe" in u) && !("platform_error" in u)));
    assert.equal(await marked(page), 0);   // the second collect() asks, and finds none left by the first
    const real = page.context.bind(page);
    page.context = () => ({ newCDPSession: async () => { throw new Error("no debugger"); } });
    const cut = await collect(page, { selectors: [] });
    page.context = real;
    assert.deepEqual(cut.font_usage.map((u) => [u.platform, u.platform_error]), [[undefined, "no debugger"], [undefined, "no debugger"]]);   // a fact on each entry, not a failed view
    assert.equal(await marked(page), 0);   // and the marks were taken off all the same
  });
});

test("the first family is the first of the computed list, quotes taken off, and the probe is the element whose text holds the most different characters", async (t) => {
  if (needSetup(t)) return;
  await inPage(`<style>.f { font-family: "Foo, Bar", 'Second Family', serif; } .g { font-family: Plain, serif; font-size: 11px; }</style>
    <p class="f" id="plain">aaaa aaaa</p><p class="f" id="rich">abcd efgh</p><p class="f" style="font-size: 30px">aaaa</p><p class="g">Plain</p><span class="g" style="font-size: 9px">small</span>`, async (page) => {
    const { font_usage: usage, font_faces: faces } = await collect(page, { selectors: [] });
    assert.deepEqual(faces, []);
    const bar = usage.find((u) => u.family === "Foo, Bar");
    assert.ok(bar, JSON.stringify(usage.map((u) => u.family)));   // a comma inside the quotes does not end the family
    assert.equal(bar.count, 3);
    assert.equal(bar.sel, "p#rich");                      // the most different characters, not the first and not the longest
    assert.equal(bar.min_px, 16);
    assert.equal(bar.stack.startsWith('"Foo, Bar"'), true);
    const plain = usage.find((u) => u.family === "Plain");
    assert.deepEqual([plain.count, plain.min_px, plain.min_sel, plain.min_text], [2, 9, "body > span.g", "small"]);   // the smallest of its elements, and what it says
    assert.deepEqual(usage.map((u) => u.family), ["Foo, Bar", "Plain"]);   // document order
  });
});

test("text that is not shown is not a font in use, and the faces of document.fonts are reported with their status", async (t) => {
  if (needSetup(t)) return;
  await inPage(`<style>
      @font-face { font-family: "Never Asked"; src: local("Arial"); }
      .gone { display: none; font-family: "Hidden One"; } .hidden { visibility: hidden; font-family: "Hidden Two"; } .faded { opacity: 0; font-family: "Hidden Three"; }
    </style><p>shown</p><p class="gone">a</p><p class="hidden">b</p><p class="faded">c</p><input placeholder="Name" style="font-family: 'Field Face', sans-serif">`, async (page) => {
    const { font_usage: usage, font_faces: faces } = await collect(page, { selectors: [] });
    assert.deepEqual(faces.map((f) => [f.family, f.status]), [["Never Asked", "unloaded"]]);
    assert.equal(usage.length, 2);                                  // the shown paragraph (in the browser's own default family) and the field
    assert.ok(!usage.some((u) => /Hidden/.test(u.family)));         // display: none, visibility: hidden and opacity: 0 draw nothing
    assert.ok(usage.some((u) => u.family === "Field Face"));        // an input's placeholder is a text
  });
});

test("what is set in another font inside the probe is taken off its answer: the debugger answers for the element and everything in it", async (t) => {
  if (needSetup(t)) return;
  await inPage(`<style>${FACES} body { font-family: "Acme Sans", serif; } code { font-family: "Acme Mono", monospace; }</style>
    <p>Install the widget with <code>npm i widget</code> and then run it.</p>`, async (page) => {
    const { font_usage: usage } = await collect(page, { selectors: [] });
    const sans = usage.find((u) => u.family === "Acme Sans"), mono = usage.find((u) => u.family === "Acme Mono");
    assert.equal(sans.sel, "body > p");
    assert.equal(sans.inline_other, 1);
    assert.equal(glyphs(sans), 41);   // "Install the widget with  and then run it.": the 12 glyphs of the code are not the paragraph's
    assert.equal(mono.sel, "body > p > code");
    assert.equal(mono.inline_other, undefined);
    assert.equal(glyphs(mono), 12);
    assert.ok(usage.every((u) => !u.platform_error));
    assert.equal(await marked(page), 0);   // the code was the probe of one entry and inside the probe of another: both marks are gone
  });
});

test("an element with no inline text in another font inside it is the probe before one with more different characters, and the answer is then not changed", async (t) => {
  if (needSetup(t)) return;
  await inPage(`<style>${FACES} body { font-family: "Acme Sans", serif; }</style>
    <p id="mixed">abcdefg hijklm <strong>bold</strong> nopq</p><p id="plain">aaa</p>`, async (page) => {
    const { font_usage: usage } = await collect(page, { selectors: [] });
    const regular = usage.find((u) => u.weight === 400);
    assert.equal(regular.sel, "p#plain");               // p#mixed holds more different characters but has a bold word in it
    assert.equal(regular.inline_other, undefined);
    assert.equal(glyphs(regular), 3);
    assert.equal(usage.find((u) => u.weight === 700).sel, "p#mixed > strong");
  });
});

test("a probe the debugger cannot be asked about is said on the entry, and a text area is the last choice of its entry", async (t) => {
  if (needSetup(t)) return;
  await inPage(`<style>.s { font-family: serif; } .m { font-family: monospace; }</style>
    <textarea class="s">abcdefghij klmnop</textarea><p class="s">aaa</p>
    <textarea class="m">only a text area</textarea>
    <p id="contents" style="font-family: Georgia">text <span style="display: contents; font-family: Courier">more</span></p>
    <p id="many" style="font-family: Menlo">x ${Array.from({ length: 14 }, (_, i) => `<b>b${i}</b>`).join(" ")}</p>`, async (page) => {
    const { font_usage: usage } = await collect(page, { selectors: [] });
    const by = (family) => usage.find((u) => u.family === family && u.weight === 400);
    assert.equal(by("serif").sel, "body > p.s:nth-of-type(1)");   // the text area has more different characters and is still not chosen
    assert.equal(by("serif").platform_error, undefined);
    assert.ok(by("serif").platform.length > 0);
    assert.match(by("monospace").platform_error, /text area/);
    assert.equal(by("monospace").platform, undefined);
    assert.match(by("Georgia").platform_error, /display: contents/);
    assert.match(by("Menlo").platform_error, /14 elements inside it are set in other fonts \(more than 12\)/);
    assert.equal(await marked(page), 0);
  });
});
