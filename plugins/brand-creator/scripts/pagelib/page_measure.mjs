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

// ---------------------------------------------------------------- in-page helpers
// A collector that walks the page needs the same few tools: a readable selector, "is this element really shown", a colour read as #rrggbb plus alpha (a
// computed colour can be rgb(), oklch(), lab() or color(); a canvas turns any of them into sRGB) and "what is this element drawn on". They are installed once
// per view under window.__bcMeasure by the first collector below, and removed again by collect(), so a collector added later (fonts, marks, motion ...) calls
// `window.__bcMeasure.<name>` inside its own page.evaluate. Nothing here judges.
function installHelpers() {
  if (window.__bcMeasure) return;
  const H = {};
  const skipTags = new Set(["script", "style", "template", "noscript", "option", "optgroup", "datalist"]);
  const notRendered = "defs, symbol, clipPath, mask, pattern, marker, linearGradient, radialGradient, filter";

  /** A short readable path to the element: tag, id or the first two classes, and :nth-of-type among same-tag siblings; at most four levels, ending at an id. */
  H.selector = (el) => {
    const parts = [];
    for (let cur = el, depth = 0; cur && cur.nodeType === 1 && depth < 4; cur = cur.parentElement, depth++) {
      const tag = cur.localName;
      if (cur.id && /^[A-Za-z][\w-]*$/.test(cur.id) && document.getElementById(cur.id) === cur) { parts.unshift(`${tag}#${cur.id}`); break; }
      let part = tag;
      const cls = [...cur.classList].filter((c) => /^[A-Za-z_][\w-]*$/.test(c)).slice(0, 2);
      if (cls.length) part += "." + cls.join(".");
      const same = cur.parentElement ? [...cur.parentElement.children].filter((c) => c.localName === tag) : [];
      if (same.length > 1) part += `:nth-of-type(${same.indexOf(cur) + 1})`;
      parts.unshift(part);
      if (tag === "body" || tag === "html") break;
    }
    return parts.join(" > ");
  };

  /** True when an element that has a box is still not seen: the content of a closed <details> (laid out, never painted), or an element cut to nothing, the
   *  "visually hidden" pattern for screen readers (clip: rect(0 0 0 0), clip-path: inset(50%), overflow cut on a box of 1 css px by 1 or less, or of less than 1 css px
   *  on the cut axis: a collapsed accordion). A hairline, 1 css px high and wide, is still a box that paints. */
  const cutOff = (el, s) => {
    const parent = el.parentElement;
    if (s.display === "contents" || s.display === "none") return false;
    if (parent && parent.localName === "details" && !parent.open && !el.checkVisibility() && el !== [...parent.children].find((c) => c.localName === "summary")) return true;
    const clip = /^rect\(\s*(-?[\d.]+)px,?\s*(-?[\d.]+)px,?\s*(-?[\d.]+)px,?\s*(-?[\d.]+)px\s*\)$/.exec(s.clip);   // computed: rect(top, right, bottom, left)
    if (clip && (+clip[2] - +clip[4] <= 1 || +clip[3] - +clip[1] <= 1)) return true;
    const inset = /^inset\(\s*([\d.]+)%(?:\s+([\d.]+)%)?(?:\s+([\d.]+)%)?(?:\s+([\d.]+)%)?\s*\)$/.exec(s.clipPath);
    if (inset) {   // 1 to 4 values, the CSS shorthand for top right bottom left
      const [t, r = t, b = t, l = r] = inset.slice(1).filter((v) => v !== undefined).map(Number);
      if (t + b >= 100 || r + l >= 100) return true;
    }
    if (el === document.documentElement || el === document.body || s.display === "inline") return false;   // the root's overflow belongs to the viewport; overflow does not apply to an inline box
    const r = el.getBoundingClientRect(), cuts = (v) => v === "hidden" || v === "clip";
    return (cuts(s.overflowX) && r.width < 1) || (cuts(s.overflowY) && r.height < 1) || (cuts(s.overflowX) && cuts(s.overflowY) && r.width <= 1 && r.height <= 1);
  };

  const shownMemo = new Map();
  /** { shown, opacity }: no ancestor-or-self is display:none, content-visibility:hidden, the content of a closed <details> or cut to nothing (the visually hidden
   *  pattern); opacity is the product of the opacities from the root down. */
  H.shown = (el) => {
    if (shownMemo.has(el)) return shownMemo.get(el);
    const s = getComputedStyle(el), parent = el.parentElement;
    const up = parent ? H.shown(parent) : { shown: true, opacity: 1 };
    const info = { shown: up.shown && s.display !== "none" && s.contentVisibility !== "hidden" && !cutOff(el, s), opacity: up.opacity * (parseFloat(s.opacity) || 0) };
    shownMemo.set(el, info);
    return info;
  };

  /** Elements the walkers look at: rendered, not in a template, not inside an SVG definition (a gradient, a clip path, a symbol). */
  H.walkable = (el) => !skipTags.has(el.localName) && !(el instanceof SVGElement && el.closest(notRendered));

  const cv = document.createElement("canvas");
  cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true });
  const colourMemo = new Map();
  const hex2 = (n) => n.toString(16).padStart(2, "0");
  /** A computed colour -> {r, g, b, a, hex}, or null when it cannot be read. The alpha is read from the text (a canvas premultiplies it away); the colour itself
   *  is drawn without it and read back in sRGB, so oklch(), lab() and color() are converted by the browser's own rules. */
  H.colour = (css) => {
    if (colourMemo.has(css)) return colourMemo.get(css);
    let s = String(css).trim(), a = 1, rgb = null;
    const legacy = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)(%?)\s*)?\)$/.exec(s);
    if (legacy) {
      rgb = [Math.round(+legacy[1]), Math.round(+legacy[2]), Math.round(+legacy[3])];
      if (legacy[4] !== undefined) a = +legacy[4] / (legacy[5] ? 100 : 1);
    } else {
      const tail = /\s*\/\s*([\d.]+)(%?)\s*\)\s*$/.exec(s);
      if (tail) { a = +tail[1] / (tail[2] ? 100 : 1); s = s.slice(0, tail.index) + ")"; }
      for (const sentinel of ["#fe01fd", "#01fe02"]) {   // an assignment the canvas cannot parse is ignored and leaves the sentinel behind
        cx.fillStyle = sentinel;
        cx.fillStyle = s;
        if (cx.fillStyle === sentinel) continue;
        cx.clearRect(0, 0, 1, 1);
        cx.fillRect(0, 0, 1, 1);
        const d = cx.getImageData(0, 0, 1, 1).data;
        rgb = [d[0], d[1], d[2]];
        break;
      }
    }
    const out = rgb && Number.isFinite(a) ? { r: rgb[0], g: rgb[1], b: rgb[2], a: Math.min(1, Math.max(0, a)), hex: "#" + rgb.map(hex2).join("") } : null;
    colourMemo.set(css, out);
    return out;
  };

  let canvasColour = null;
  /** The colour of the canvas behind the page: the browser's own Canvas colour for the scheme the page asks for (white, or dark for color-scheme: dark). */
  H.canvas = () => {
    if (canvasColour) return canvasColour;
    const probe = document.createElement("div");
    probe.style.cssText = "position:absolute;width:0;height:0;background-color:Canvas";
    document.documentElement.appendChild(probe);
    canvasColour = H.colour(getComputedStyle(probe).backgroundColor);
    probe.remove();
    return canvasColour;
  };

  const groundMemo = new Map();
  /** What an element is drawn on: the first ancestor-or-self with a background colour of alpha above 0 ({kind: "colour", hex, sel}); a see-through one is
   *  composited over what is behind it (`layered`). A background image (a gradient too) on the way makes it {kind: "image"}. With nothing behind, the canvas. */
  H.ground = (el) => {
    if (groundMemo.has(el)) return groundMemo.get(el);
    const s = getComputedStyle(el), bg = H.colour(s.backgroundColor) || { r: 0, g: 0, b: 0, a: 0 };
    let g;
    if (s.backgroundImage !== "none") g = { kind: "image", sel: H.selector(el) };
    else if (bg.a >= 1) g = { kind: "colour", rgb: [bg.r, bg.g, bg.b], sel: H.selector(el) };
    else {
      const up = el.parentElement ? H.ground(el.parentElement) : { kind: "colour", rgb: [H.canvas().r, H.canvas().g, H.canvas().b], sel: "(canvas)" };
      if (bg.a > 0 && up.kind === "colour") g = { kind: "colour", rgb: [bg.r, bg.g, bg.b].map((v, i) => Math.round(v * bg.a + up.rgb[i] * (1 - bg.a))), sel: H.selector(el), layered: true };
      else g = bg.a > 0 ? { kind: "image", sel: up.sel } : up;
    }
    groundMemo.set(el, g);
    return g;
  };
  H.hex = (rgb) => "#" + rgb.map(hex2).join("");
  Object.defineProperty(window, "__bcMeasure", { value: H, configurable: true });
}

const TEXT_CAP = 4000;       // texts reported per view; the view says so when there were more
const COLOUR_ALSO = 4;       // further selectors named with a colour

/** Every colour the page paints and every text with what it is drawn on, in one walk over the visible elements.
 *  `colours`: one entry per distinct (prop, hex, alpha): {sel, prop, hex, alpha, count, also}. The props are `color` (an element with its own text), `background-color`
 *  (alpha above 0), `border-color` (all four sides) or `border-<side>-color` (a side with a width and a style), `outline-color` (a drawn outline that is not the
 *  browser's own focus ring), `text-decoration-color` (a line is drawn), `-webkit-text-fill-color` (when it is not the text colour) and `fill` / `stroke` of inline
 *  SVG shapes. `texts`: {sel, text, fg, fg_alpha, opacity, ground, ground_kind, ground_sel, font_size_px, font_weight, font_family, rect, sample_label, lang}
 *  for every element with its own text; `fg` is the colour the text is painted in (null, with `fill_clear: true`, when a clipped background paints the glyphs, or with
 *  `fill_server: true` when an SVG text is filled by a gradient or pattern), `ground` what it sits on (null over an image), `sample_label` the label of the
 *  closest [data-sample] (null outside one). `colours_unreadable` lists colours that could not be read; `texts_total` is set when more than TEXT_CAP texts were found. */
async function colourFacts(page) {
  return page.evaluate(([textCap, alsoCap]) => {
    const H = window.__bcMeasure;
    const SHAPES = new Set(["path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan"]);
    const NO_TEXT_INPUT = new Set(["hidden", "checkbox", "radio", "range", "color", "file", "image"]);
    const found = new Map(), unreadable = new Set(), texts = [];
    let textsTotal = 0;
    const round = (v, n = 1) => Math.round(v * 10 ** n) / 10 ** n;
    const opacity = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : 1; };   // an opacity of 0 is 0 (the colour is not painted), not "unset"

    const add = (el, prop, css, scale = 1) => {
      const c = H.colour(css);
      if (!c) { unreadable.add(`${prop}: ${css}`.slice(0, 80)); return null; }
      const alpha = round(c.a * scale, 3);
      if (alpha <= 0) return c;
      const key = `${prop}|${c.hex}|${alpha}`;
      const e = found.get(key);
      if (e) { e.count++; if (e.els.length <= alsoCap) e.els.push(el); } else found.set(key, { prop, hex: c.hex, alpha, count: 1, els: [el] });
      return c;
    };
    // a <path> or <polyline> may enclose no area (a straight diagonal stroke): its default black fill paints nothing, like a <line>'s. Tested on the points of a 24 by 24 grid over
    // its box (the first hit ends it, so a filled shape costs one call); a fill thinner than a cell of that grid is not seen.
    const encloses = (el) => {
      if (el.localName !== "path" && el.localName !== "polyline") return true;
      const b = el.getBBox(), n = 24;
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (el.isPointInFill(new DOMPoint(b.x + ((i + 0.5) / n) * b.width, b.y + ((j + 0.5) / n) * b.height))) return true;
      return false;
    };
    const ownText = (el) => {
      let t = "";
      for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
      return t.replace(/\s+/g, " ").trim();
    };
    const textBox = (el) => {
      let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
      const range = document.createRange();
      for (const n of el.childNodes) {
        if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
        range.selectNodeContents(n);
        for (const r of range.getClientRects()) { x1 = Math.min(x1, r.left); y1 = Math.min(y1, r.top); x2 = Math.max(x2, r.right); y2 = Math.max(y2, r.bottom); }
      }
      return x2 > x1 && y2 > y1 ? { x: x1, y: y1, width: x2 - x1, height: y2 - y1 } : null;
    };

    for (const el of document.querySelectorAll("*")) {
      if (!H.walkable(el)) continue;
      const info = H.shown(el);
      if (!info.shown || info.opacity <= 0) continue;
      const s = getComputedStyle(el), contents = s.display === "contents", svg = el instanceof SVGElement;
      const r = el.getBoundingClientRect();
      const boxed = !contents && r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0;   // an element left of or above the page's origin cannot be scrolled to
      const shownBox = boxed && s.visibility === "visible";

      // the text of the element
      let text = ownText(el), fillColour = s.color, textRect = null, placeholder = false;
      if (el.localName === "input" || el.localName === "textarea") {
        const type = (el.getAttribute("type") || "text").toLowerCase();
        if (el.localName === "input" && NO_TEXT_INPUT.has(type)) text = "";
        else if (el.value) text = type === "password" ? "(password)" : String(el.value).replace(/\s+/g, " ").trim();
        else if (el.placeholder) { text = String(el.placeholder).replace(/\s+/g, " ").trim(); placeholder = true; }
        textRect = text && shownBox ? { x: r.left, y: r.top, width: r.width, height: r.height } : null;
      } else if (text) {
        textRect = textBox(el);
      }
      const ps = placeholder ? getComputedStyle(el, "::placeholder") : null;
      if (ps) fillColour = ps.color;
      const server = svg && s.fill.startsWith("url(");   // SVG text is painted by `fill`; a paint server (a gradient, a pattern) is not a colour: the text is reported, not verified
      if (svg) fillColour = s.fill === "none" || server ? null : s.fill;
      const hasText = Boolean(text) && textRect && textRect.width >= 2 && textRect.height >= 2 && textRect.x + textRect.width > 0 && textRect.y + textRect.height > 0
        && (contents || s.visibility === "visible");

      if (hasText) {
        textsTotal++;
        let fg = fillColour ? H.colour(fillColour) : null, clear = false;
        if (!svg && !placeholder) {   // -webkit-text-fill-color paints the glyphs instead of `color`; transparent with a clipped background means the background paints them
          const fill = H.colour(s.webkitTextFillColor);
          if (fill && fill.hex !== (H.colour(s.color) || {}).hex) add(el, "-webkit-text-fill-color", s.webkitTextFillColor);
          if (fill) { fg = fill; clear = fill.a === 0; }
        }
        if (!svg) add(el, "color", ps ? ps.color : s.color);
        if (svg && fillColour) add(el, "fill", fillColour, opacity(s.fillOpacity));
        if (texts.length < textCap && (fg || server)) {
          const g = H.ground(el), sample = el.closest("[data-sample]"), langed = el.closest("[lang]");
          texts.push({
            sel: H.selector(el), text: text.slice(0, 200), fg: clear || !fg ? null : fg.hex, fg_alpha: fg ? round(fg.a, 3) : 1, opacity: round(info.opacity, 3),
            ground: g.kind === "colour" ? H.hex(g.rgb) : null, ground_kind: g.kind, ground_sel: g.sel, ...(g.layered ? { ground_layered: true } : {}),
            ...(clear ? { fill_clear: true } : {}), ...(server ? { fill_server: true } : {}),
            font_size_px: round(parseFloat(s.fontSize), 2), font_weight: parseInt(s.fontWeight, 10) || 400, font_family: s.fontFamily,
            rect: { x: round(textRect.x + scrollX), y: round(textRect.y + scrollY), width: round(textRect.width), height: round(textRect.height) },
            sample_label: sample ? sample.getAttribute("data-sample") : null, lang: langed ? langed.getAttribute("lang") : "",
          });
        }
      }

      if (svg && !(el.localName === "svg" && !(el.parentElement instanceof SVGElement))) {   // inline SVG shapes: fill and stroke (a paint server, url(#...), is not a colour and is skipped); the outer <svg> is a box like any other
        // a horizontal or vertical line or path has a box of no height or no width, yet its stroke is drawn: for a shape one extent above 0 is a box; only a shape
        // with an area (and never a <line>) is filled, its default fill of black paints nothing on a stroke-only line
        const drawn = !contents && (r.width > 0 || r.height > 0) && r.right >= 0 && r.bottom >= 0;
        if (SHAPES.has(el.localName) && drawn && s.visibility === "visible") {
          if (!hasText && el.localName !== "line" && r.width > 0 && r.height > 0 && s.fill !== "none" && !s.fill.startsWith("url(") && encloses(el)) add(el, "fill", s.fill, opacity(s.fillOpacity));
          if (s.stroke !== "none" && !s.stroke.startsWith("url(") && parseFloat(s.strokeWidth) > 0) add(el, "stroke", s.stroke, opacity(s.strokeOpacity));
        }
        continue;
      }
      if (!shownBox) continue;

      add(el, "background-color", s.backgroundColor);
      const sides = ["top", "right", "bottom", "left"].filter((d) => parseFloat(s[`border-${d}-width`]) > 0 && !["none", "hidden"].includes(s[`border-${d}-style`]));
      if (sides.length) {
        const same = sides.every((d) => s[`border-${d}-color`] === s[`border-${sides[0]}-color`]);
        if (same && sides.length === 4) add(el, "border-color", s.borderTopColor);
        else for (const d of sides) add(el, `border-${d}-color`, s[`border-${d}-color`]);
      }
      if (parseFloat(s.outlineWidth) > 0 && !["none", "auto"].includes(s.outlineStyle)) add(el, "outline-color", s.outlineColor);
      if (s.textDecorationLine !== "none" && text) add(el, "text-decoration-color", s.textDecorationColor);
    }

    const colours = [...found.values()].map((e) => ({ sel: H.selector(e.els[0]), prop: e.prop, hex: e.hex, alpha: e.alpha, count: e.count, also: e.els.slice(1).map((x) => H.selector(x)) }));
    return { colours, texts, ...(textsTotal > texts.length ? { texts_total: textsTotal } : {}), ...(unreadable.size ? { colours_unreadable: [...unreadable].sort() } : {}) };
  }, [TEXT_CAP, COLOUR_ALSO]);
}

/** Each CSS colour of request.colours (the modern oklch(), oklab() or color() values of the project's tokens, from tokens.css) as THIS browser renders it, drawn on the
 *  same canvas as every colour of the page: {role_colours: {css: "#rrggbb" | null}}. A token outside sRGB is clipped by the browser channel by channel, not gamut-mapped by
 *  chroma reduction as the hex of tokens.json was, so the two differ; the judge accepts a page colour that is either. Nothing is judged here. */
async function roleColours(page, request) {
  const list = Array.isArray(request.colours) ? request.colours : [];
  if (!list.length) return {};
  return page.evaluate((css) => ({ role_colours: Object.fromEntries(css.map((c) => { const read = window.__bcMeasure.colour(c); return [c, read ? read.hex : null]; })) }), list);
}

const COLLECTORS = [
  async (page) => { await page.evaluate(installHelpers); return {}; },   // first: the helpers the collectors below call
  async (page) => ({ document: await documentFacts(page) }),
  async (page, request) => ({ selectors: await selectorBoxes(page, request.selectors || []) }),
  async (page) => colourFacts(page),
  async (page, request) => roleColours(page, request),
];

/** Run every collector on the settled page and merge their answers; the in-page helpers are taken out of the page again. */
export async function collect(page, request) {
  const out = {};
  try {
    for (const c of COLLECTORS) Object.assign(out, await c(page, request));
  } finally {
    await page.evaluate(() => { delete window.__bcMeasure; }).catch(() => {});
  }
  return out;
}
