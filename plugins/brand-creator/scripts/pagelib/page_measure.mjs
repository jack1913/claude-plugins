// page_measure.mjs: the in-page collectors of `brand-creator page-check`. ESM, Node >= 22, no dependency of its own.
//
// render.mjs (the only Chromium driver) loads a page in one view (a width and a colour scheme) and calls collect(page, request) once the page has settled.
// A collector only MEASURES: it returns raw facts about the rendered page and judges nothing; scripts/pagelib/pagecheck.py judges them against the brand.
// What collect returns is spread into the view's entry of the measurements file, so a later family of facts (colours, texts, fonts, marks, motion
// declarations, controls, tell candidates) is one more function added to COLLECTORS below, with its own key.

const SELECTOR_BOXES = 20;   // how many boxes of one requested selector are reported

/** Boxes of the elements the request asked about (request.selectors): how many match, and the first few visible ones as rounded css px rectangles. */
async function selectorBoxes(page, selectors) {
  if (!selectors.length) return {};
  return page.evaluate(([list, cap]) => {
    const out = {};
    for (const sel of list) {
      let els;
      try { els = [...document.querySelectorAll(sel)]; } catch (e) { out[sel] = { error: String(e.message).split("\n")[0] }; continue; }
      const boxes = [];
      for (const e of els) {
        const s = getComputedStyle(e), r = e.getBoundingClientRect();
        if (s.display === "none" || s.visibility === "hidden" || r.width <= 0 || r.height <= 0) continue;
        boxes.push({ x: Math.round(r.x * 100) / 100, y: Math.round(r.y * 100) / 100, width: Math.round(r.width * 100) / 100, height: Math.round(r.height * 100) / 100 });
      }
      out[sel] = { count: els.length, visible: boxes.length, boxes: boxes.slice(0, cap) };
    }
    return out;
  }, [selectors, SELECTOR_BOXES]);
}

/** The document itself: its title and how wide and tall the page is against the viewport. */
async function documentFacts(page) {
  return page.evaluate(() => ({
    title: document.title,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    scroll_height: document.documentElement.scrollHeight,
  }));
}

const COLLECTORS = [
  async (page) => ({ document: await documentFacts(page) }),
  async (page, request) => ({ selectors: await selectorBoxes(page, request.selectors || []) }),
];

/** Run every collector on the settled page and merge their answers. */
export async function collect(page, request) {
  const out = {};
  for (const c of COLLECTORS) Object.assign(out, await c(page, request));
  return out;
}
