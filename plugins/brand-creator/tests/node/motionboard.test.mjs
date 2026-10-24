// The motion board template as it ships (templates/motion-board.html), opened in Chromium: the ?v=Name filter and the vote of each card. The markup and the lint rows are
// tested in tests/test_motion_board.py (which fills the template with the helper in tests/helpers.py); here the browser decides, on a page made from the template alone.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { needSetup, ROOT, tmpdir } from "./_helpers.mjs";
import { loadDep, readSetup } from "../../scripts/lib/_common.mjs";

const NAMES = ["Settle", "Bounce", "Glide"];

/** The template with its one variant card copied once per name, the name put in where it asks for one, and every other [[fill: ...]] marker outside the comments made "x". */
function filled() {
  const src = fs.readFileSync(path.join(ROOT, "templates/motion-board.html"), "utf8");
  const card = src.match(/ {6}<article class="variant"[\s\S]*?<\/article>\n/)[0];
  const page = src.replace(card, NAMES.map((n) => card.replaceAll("[[fill: Name one]]", n)).join(""));
  return page.split(/(<!--[\s\S]*?-->)/).map((piece) => (piece.startsWith("<!--") ? piece : piece.replace(/\[\[fill:[\s\S]*?\]\](?!\])/g, "x"))).join("");
}

/** The page the template makes, in a folder of its own, and a Chromium of the data folder's Playwright, the way render.mjs starts it; `fn(page url, browser)` runs, then it is closed. */
async function inBrowser(fn) {
  const file = path.join(tmpdir("bc-motion-board-"), "board.html");
  fs.writeFileSync(file, filled());
  process.env.PLAYWRIGHT_BROWSERS_PATH = readSetup().browsers_path;
  const browser = await (await loadDep("playwright-core")).chromium.launch({ headless: true });
  try { return await fn(pathToFileURL(file).href, browser); } finally { await browser.close(); }
}

const cards = (page) => page.evaluate(() => [...document.querySelectorAll("[data-motion-variant]")].map((e) => ({ name: e.getAttribute("data-motion-variant"), hidden: e.hidden, display: getComputedStyle(e).display, height: e.getBoundingClientRect().height })));

test("?v=Name shows the card of that variant only: the other cards are hidden and take no room", async (t) => {
  if (needSetup(t)) return;
  await inBrowser(async (url, browser) => {
    const page = await browser.newPage();
    await page.goto(url);
    assert.deepEqual((await cards(page)).map((c) => [c.name, c.hidden, c.display !== "none" && c.height > 0]), NAMES.map((n) => [n, false, true]));   // no filter: every card is there
    for (const shown of NAMES) {
      await page.goto(`${url}?v=${shown}`);
      assert.deepEqual((await cards(page)).map((c) => [c.name, c.hidden, c.display, c.height > 0]), NAMES.map((n) => (n === shown ? [n, false, "flex", true] : [n, true, "none", false])), shown);
    }
  });
});

test("the vote of each card is a group of its own: a vote on one card leaves the votes on the others where they were", async (t) => {
  if (needSetup(t)) return;
  await inBrowser(async (url, browser) => {
    const page = await browser.newPage();
    await page.goto(url);
    const votes = ["keep", "drop", "unsure"];
    for (const [i, name] of NAMES.entries()) await page.check(`fieldset[data-vote="${name}"] input[value="${votes[i]}"]`);
    const state = await page.evaluate(() => ({
      checked: [...document.querySelectorAll("fieldset[data-vote]")].map((f) => [f.getAttribute("data-vote"), f.querySelector("input:checked")?.value ?? null]),
      groups: [...new Set([...document.querySelectorAll("fieldset[data-vote] input")].map((e) => e.name))],
      reply: document.getElementById("reply-out").textContent,
    }));
    assert.deepEqual(state.checked, NAMES.map((n, i) => [n, votes[i]]));
    assert.equal(state.reply, "Settle keep, Bounce drop, Glide unsure");   // and the reply carries all three
    assert.equal(state.groups.length, NAMES.length);                       // three groups, not one
  });
});
