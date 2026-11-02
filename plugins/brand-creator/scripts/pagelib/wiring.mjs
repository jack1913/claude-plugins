// wiring.mjs: the DOM side of `brand-creator adoption wiring --page`. ESM, Node >= 22, no dependency of its own.
//
// render.mjs (the only Chromium driver) loads one page of the owner's own local server and calls collectWiring(page) once the page has loaded. This reads what
// the page is wired to as it stands in the DOM and judges nothing: the same six kinds as scripts/adaptlib/wiring.py reads from source (docs/adr/ADR-0012), with the
// same rules for what is skipped, so a value found in both places is the same item. Values are read with getAttribute, as written, never as the browser resolves
// them (a link is `/pricing`, not `http://127.0.0.1:5173/pricing`). Listeners a script adds are not attributes and cannot be seen here: only inline `on*`
// attributes are handlers, and the rest is read from source.

import fs from "node:fs";

export const KINDS = ["link", "field", "handler", "hook", "id", "script"];
/** The one list of event-handler attribute names (scripts/data/event-handlers.json), the file scripts/adaptlib/wiring.py reads for the source: an attribute is a handler when it is on the list. */
export const EVENT_HANDLERS = new Set(JSON.parse(fs.readFileSync(new URL("../data/event-handlers.json", import.meta.url), "utf8")).events);
export const MAX_VALUE = 120;   // code points of an item after `kind:`, as wiring.py cuts it

/** Everything the page is wired to, as `{kind: [values]}` with every kind present, in document order, without repeats:
 *    link     `a[href]`, `area[href]`, `form[action]`, `[formaction]`; not an empty value or `#`
 *    field    `[name]` on input, select, textarea and button
 *    handler  an inline attribute with a value whose name is on the list of EVENT_HANDLERS (`onclick`, `onsubmit` ...; `onboarding`, `one` and `only` are not): `<attribute>=<value>`
 *    hook     `data-testid`, `data-test`, `data-cy`, `data-qa`, `data-track*`, `data-analytics*`, `data-event*`, `data-gtm*` with a value: `<attribute>=<value>`
 *    id       `[id]` with no braces and no white space in it
 *    script   `script[src]` without its query and without a leading `./`
 *  White space is squashed and a value is cut at MAX_VALUE code points. */
export async function collectWiring(page) {
  return page.evaluate(([kinds, cap, events]) => {
    const out = Object.fromEntries(kinds.map((k) => [k, []]));
    const seen = Object.fromEntries(kinds.map((k) => [k, new Set()]));
    const HOOK = /^data-(?:testid|test|cy|qa)$|^data-(?:track|analytics|event|gtm)[\w-]*$/;
    const HANDLERS = new Set(events);
    const squash = (s) => s.replace(/\s+/g, " ").trim();
    const add = (kind, text) => {
      if (text === null) return;
      const v = [...text].slice(0, cap).join("");
      if (!seen[kind].has(v)) { seen[kind].add(v); out[kind].push(v); }
    };
    for (const el of document.querySelectorAll("*")) {
      const tag = el.localName;
      const get = (name) => squash(el.getAttribute(name) ?? "");
      if ((tag === "a" || tag === "area") && el.hasAttribute("href")) { const v = get("href"); add("link", v === "" || v === "#" ? null : v); }
      if (tag === "form" && el.hasAttribute("action")) { const v = get("action"); add("link", v === "" || v === "#" ? null : v); }
      if (el.hasAttribute("formaction")) { const v = get("formaction"); add("link", v === "" || v === "#" ? null : v); }
      if (["input", "select", "textarea", "button"].includes(tag) && el.hasAttribute("name")) { const v = get("name"); add("field", v === "" ? null : v); }
      if (el.hasAttribute("id")) { const v = get("id"); add("id", v === "" || /[{}\s]/.test(v) ? null : v); }
      if (tag === "script" && el.hasAttribute("src")) { const v = get("src").split("?", 1)[0].replace(/^\.\//, ""); add("script", v === "" ? null : v); }
      for (const name of el.getAttributeNames()) {
        const kind = HOOK.test(name) ? "hook" : HANDLERS.has(name) ? "handler" : null;   // the one list of event names, as in the source reader (`one` and `onboarding` are no handlers)
        if (kind === null) continue;
        const v = get(name);
        add(kind, v === "" ? null : `${name}=${v}`);
      }
    }
    return out;
  }, [KINDS, MAX_VALUE, [...EVENT_HANDLERS]]);
}
