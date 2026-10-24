// The boards that show directions as they ship (templates/round-page.html, style-board.html and review/index.html), opened in Chromium: the vote of each card is a group of its own.
// The markup is tested in tests/test_board_lint.py; here the browser decides, on a page made from the template alone (the motion board has the same test, tests/node/motionboard.test.mjs).
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { needSetup, ROOT, tmpdir } from "./_helpers.mjs";
import { loadDep, readSetup } from "../../scripts/lib/_common.mjs";

const NAMES = ["Compass", "Lantern", "Keystone"];

/** The template with its one card copied once per name, the name put in where it asks for one, and every other [[fill: ...]] marker outside the comments made "x". */
function filled(template) {
  const src = fs.readFileSync(path.join(ROOT, "templates", template), "utf8");
  const card = src.match(/ {6}<article class="(?:direction|territory)"[\s\S]*?<\/article>\n/)[0];
  const page = src.replace(card, NAMES.map((n) => card.replaceAll("[[fill: Name one]]", n)).join(""));
  return page.split(/(<!--[\s\S]*?-->)/).map((piece) => (piece.startsWith("<!--") ? piece : piece.replace(/\[\[fill:[\s\S]*?\]\](?!\])/g, "x"))).join("");
}

for (const template of ["round-page.html", "style-board.html", "review/index.html"]) {
  test(`${template}: the vote of each card is a group of its own, a vote on one card leaves the votes on the others where they were`, async (t) => {
    if (needSetup(t)) return;
    const file = path.join(tmpdir("bc-board-votes-"), "board.html");
    fs.writeFileSync(file, filled(template));
    process.env.PLAYWRIGHT_BROWSERS_PATH = readSetup().browsers_path;
    const browser = await (await loadDep("playwright-core")).chromium.launch({ headless: true });
    try {
      const page = await browser.newPage();
      await page.goto(pathToFileURL(file).href);
      const votes = ["keep", "drop", "unsure"];
      for (const [i, name] of NAMES.entries()) await page.check(`fieldset[data-vote="${name}"] input[value="${votes[i]}"]`);
      const state = await page.evaluate(() => ({
        checked: [...document.querySelectorAll("fieldset[data-vote]")].map((f) => [f.getAttribute("data-vote"), f.querySelector("input:checked")?.value ?? null]),
        groups: [...new Set([...document.querySelectorAll("fieldset[data-vote] input")].map((e) => e.name))],
        reply: document.getElementById("reply-out").textContent,
      }));
      assert.deepEqual(state.checked, NAMES.map((n, i) => [n, votes[i]]));
      assert.equal(state.reply, "Compass keep, Lantern drop, Keystone unsure");   // and the reply carries all three
      assert.equal(state.groups.length, NAMES.length);                           // three groups, not one
    } finally { await browser.close(); }
  });
}
