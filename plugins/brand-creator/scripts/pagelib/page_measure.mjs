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

const MOTION_CAP = 500;      // distinct motion declarations reported per view; the view says so when there were more
const MOTION_ALSO = 4;       // further selectors named with a motion declaration
// the pseudo-classes of a state the page is not in while it is measured: a rule that sets motion on one is read from the style sheet
const MOTION_STATES = "hover|active|focus|focus-visible|focus-within|checked|target|disabled|open|popover-open|modal|fullscreen|invalid|user-invalid|indeterminate|placeholder-shown";

/** Every duration and easing the page declares or runs. Two walks: over all elements (hidden ones too: a menu that is closed now animates when it opens), and over the style
 *  sheets' rules for a state (a :hover, :focus or :active rule matches nothing while the page is measured, so its motion is not in any computed style).
 *  `motion_decls`: one entry per distinct (source, name, duration, easing): {sel, source, name, duration_ms, easing, via, count, also, unset?}. `source` is `transition` (the
 *  computed transition-property, -duration and -timing-function of an element or of its generated ::before and ::after, paired the way CSS cycles the lists; a duration of 0 is no
 *  transition), `animation` (animation-name, -duration, -timing-function likewise; `duration_ms: null` is `auto` on a scroll or view timeline: on a time-based animation `auto` is 0
 *  and nothing runs) or `script` (a Web Animation nobody declared in CSS). `via` is `style` (declared on an element at rest), `state` (declared by a style sheet rule whose selector
 *  names a state: `sel` is the rule's selector, `count` the rules with the same values; the values are what the browser computes for the rule's declarations on a probe element that
 *  is not rendered, so `var()` resolves; `unset` lists `duration` and `easing` when the rule leaves them to the rule at rest, and then they are absent) or `running` (found in
 *  `document.getAnimations()`: a CSS one whose declaration was not found, or one a script made; its easings are those of the effect, or of each interval between its keyframes).
 *  `motion_total` is the number of distinct entries when there were more than MOTION_CAP; `motion_unread` the style sheets the browser did not let the walk read (cross origin);
 *  `motion_smil` the number of SVG SMIL animation elements (animate, animateTransform, animateMotion), which are not read. */
async function motionFacts(page) {
  return page.evaluate(([cap, alsoCap, states]) => {
    const H = window.__bcMeasure;
    const found = new Map();
    const round3 = (v) => Math.round(v * 1000) / 1000;
    const split = (v) => {   // a computed list on its top-level commas: "cubic-bezier(0.2, 0, 0, 1), ease" is two items
      const out = [];
      let depth = 0, cur = "";
      for (const ch of String(v)) {
        if (ch === "(") depth++;
        else if (ch === ")") depth--;
        if (ch === "," && depth === 0) { out.push(cur.trim()); cur = ""; } else cur += ch;
      }
      out.push(cur.trim());
      return out.filter((x) => x !== "");
    };
    const toMs = (t) => {
      const m = /^(-?\d*\.?\d+(?:e[+-]?\d+)?)(ms|s)$/i.exec(String(t).trim());
      return m ? round3(parseFloat(m[1]) * (m[2].toLowerCase() === "s" ? 1000 : 1)) : null;   // "auto" and anything else is null
    };
    // `ms` and `easing` are undefined when a state rule does not set them
    const keyOf = (source, name, ms, easing) => JSON.stringify([source, name, ms === undefined ? "unset" : ms, easing === undefined ? "unset" : easing]);
    const whereOf = (w) => w.label ?? (H.selector(w.el) + w.pseudo);
    const add = (w, source, name, ms, easing, via) => {
      const key = keyOf(source, name, ms, easing);
      const e = found.get(key);
      if (e) {
        if (via === "state" && e.via !== "state") return;   // a state that says what the rule at rest says is not a second declaration
        e.count++;
        if (e.els.length <= alsoCap) e.els.push(w);
        return;
      }
      const unset = [...(ms === undefined ? ["duration"] : []), ...(easing === undefined ? ["easing"] : [])];
      found.set(key, { source, name, duration_ms: ms, easing, via, unset, count: 1, els: [w] });
    };
    /** The declarations in a computed style. `has` is null for an element (every property is its own), or the set of longhands a state rule declares. */
    const declared = (w, s, has, via) => {
      const set = (prop) => has === null || has.has(prop);
      const at = (list, i) => (list.length ? list[i % list.length] : undefined);   // the lists of one property are cycled over the longest
      const props = split(s.transitionProperty), durs = split(s.transitionDuration).map(toMs), eases = split(s.transitionTimingFunction);
      const [hp, hd, he] = [set("transition-property"), set("transition-duration"), set("transition-timing-function")];
      const tn = has === null ? props.length : Math.max(hp ? props.length : 0, hd ? durs.length : 0, he ? eases.length : 0);
      for (let i = 0; i < tn; i++) {
        const name = hp ? at(props, i) ?? "" : "";
        const ms = hd ? at(durs, i) : undefined, easing = he ? at(eases, i) : undefined;
        if (name === "none" || ms === null || ms === 0 || (ms === undefined && easing === undefined)) continue;   // a state rule that only names the property sets no motion
        add(w, "transition", name, ms, easing, via);
      }
      const names = split(s.animationName), aDurs = split(s.animationDuration).map(toMs), aEases = split(s.animationTimingFunction), lines = split(s.animationTimeline ?? "");
      const [hn, ha, hae, hl] = [set("animation-name"), set("animation-duration"), set("animation-timing-function"), set("animation-timeline")];
      const an = has === null ? names.length : Math.max(hn ? names.length : 0, ha ? aDurs.length : 0, hae ? aEases.length : 0);
      for (let i = 0; i < an; i++) {
        const name = hn ? at(names, i) ?? "" : "";
        let ms = ha ? at(aDurs, i) : undefined;
        const easing = hae ? at(aEases, i) : undefined;
        // `auto` is a duration only on a scroll or view timeline; on a time-based animation it is 0. A state rule that sets no timeline cannot say which: it stays `auto`.
        if (ms === null && hl && (at(lines, i) ?? "auto") === "auto") ms = 0;
        if (name === "none" || ms === 0 || (ms === undefined && easing === undefined)) continue;
        add(w, "animation", name, ms, easing, via);
      }
    };

    for (const el of document.querySelectorAll("*")) {
      if (!H.walkable(el)) continue;
      for (const pseudo of ["", "::before", "::after"]) {
        const s = getComputedStyle(el, pseudo || null);
        if (pseudo && (s.content === "none" || s.content === "normal" || s.content === "")) continue;   // a pseudo-element with no content is not generated
        declared({ el, pseudo }, s, null, "style");
      }
    }

    // the style sheets' rules for a state; the browser computes what they declare on a probe that is not rendered (display: none starts no animation), put inside the first
    // element the rule styles when there is one, so that a custom property of that element resolves
    let unread = 0;
    const stateG = new RegExp(`:(?:${states})(?![\\w-])`, "gi"), stateTest = new RegExp(`:(?:${states})(?![\\w-])`, "i"), pseudoElement = /::?(?:before|after|first-line|first-letter|marker|placeholder|selection|backdrop)(?![\w-])/gi;
    const hostOf = (sel) => {
      let flat = sel.replace(stateG, "").replace(pseudoElement, "").trim();
      if (flat === "" || /[\s>+~(,]$/.test(flat)) flat += "*";
      try { return document.querySelector(flat); } catch (e) { return null; }
    };
    const probe = document.createElement("div");
    const readState = (rule, sel) => {
      const has = new Set([...rule.style]);
      if (![...has].some((n) => /^(?:transition|animation)(?:-|$)/.test(n))) return;
      probe.style.cssText = rule.style.cssText;
      probe.style.setProperty("display", "none", "important");
      try {
        (hostOf(sel) || document.body).appendChild(probe);
        let s = getComputedStyle(probe);
        if (!s.transitionDuration) { document.body.appendChild(probe); s = getComputedStyle(probe); }   // a host that cannot hold a child computes nothing
        declared({ label: sel }, s, has, "state");
      } finally {
        probe.remove();
      }
    };
    const applies = (m) => /hover|pointer/i.test(m.mediaText) || matchMedia(m.mediaText).matches;   // the input of the measuring browser says nothing of the page's
    const nestedDeclarations = typeof CSSNestedDeclarations === "function" ? CSSNestedDeclarations : null;   // Chromium 130 and later; before it, such declarations were part of the parent rule's own
    const visit = (rules, parent) => {
      for (const r of rules) {
        if (nestedDeclarations && r instanceof nestedDeclarations) {
          // the declarations written after a nested rule (or inside a nested @media or @supports) are a rule of their own with no selector: the parent rule's selector is theirs
          if (parent && stateTest.test(parent)) readState(r, parent);
        } else if (typeof r.selectorText === "string" && r.style) {
          const wrap = (x) => (x.includes(",") ? `:is(${x})` : x);
          const sel = !parent ? r.selectorText : r.selectorText.includes("&") ? r.selectorText.replace(/&/g, wrap(parent)) : `${wrap(parent)} ${r.selectorText}`;   // a nested rule
          if (stateTest.test(sel)) readState(r, sel);
          if (r.cssRules && r.cssRules.length) visit(r.cssRules, sel);
        } else if (r instanceof CSSImportRule) {
          if (!r.media.length || applies(r.media)) visitSheet(r.styleSheet);
        } else if (r.cssRules) {
          if (r instanceof CSSMediaRule && !applies(r.media)) continue;
          if (r instanceof CSSSupportsRule && !CSS.supports(r.conditionText)) continue;
          visit(r.cssRules, parent);   // @layer, @container, @scope ... : read whatever the condition
        }
      }
    };
    const visitSheet = (sheet) => {
      if (!sheet || sheet.disabled || (sheet.media && sheet.media.length && !applies(sheet.media))) return;
      let rules;
      try { rules = sheet.cssRules; } catch (e) { unread++; return; }   // a sheet from another origin
      if (rules) visit(rules, "");
    };
    for (const sheet of [...document.styleSheets, ...(document.adoptedStyleSheets || [])]) visitSheet(sheet);

    // what is running now, or fills forwards: a script's animation, and a CSS one the walks above did not see declared
    const scrollDriven = (a) => typeof ScrollTimeline === "function" && a.timeline instanceof ScrollTimeline;   // a view timeline is one too
    for (const a of document.getAnimations()) {
      const eff = a.effect;
      if (!eff || typeof eff.getTiming !== "function" || !eff.target) continue;
      const t = eff.getTiming(), pseudo = eff.pseudoElement || "";
      const source = a instanceof CSSTransition ? "transition" : a instanceof CSSAnimation ? "animation" : "script";
      const name = (source === "transition" ? a.transitionProperty : source === "animation" ? a.animationName : "") || "";
      const ms = typeof t.duration === "number" ? round3(t.duration) : null;
      if (ms === 0 || (ms === null && !scrollDriven(a))) continue;   // `auto` on a time-based animation is 0: a filled animation that has no duration does not move
      const between = (typeof eff.getKeyframes === "function" ? eff.getKeyframes() : []).slice(0, -1).map((k) => k.easing);   // the easing of an interval is its first keyframe's
      const eases = source === "transition" ? [t.easing] : source === "animation" ? between : [t.easing, ...between.filter((e) => e !== "linear")];
      for (const easing of new Set(eases.length ? eases : [t.easing])) {
        if (!found.has(keyOf(source, name, ms, easing))) add({ el: eff.target, pseudo }, source, name, ms, easing, "running");
      }
    }
    const all = [...found.values()];
    const motion_decls = all.slice(0, cap).map((e) => ({
      sel: whereOf(e.els[0]), source: e.source, name: e.name,
      ...(e.duration_ms === undefined ? {} : { duration_ms: e.duration_ms }), ...(e.easing === undefined ? {} : { easing: e.easing }),
      via: e.via, count: e.count, also: e.els.slice(1).map(whereOf), ...(e.unset.length ? { unset: e.unset } : {}),
    }));
    return { motion_decls, ...(all.length > cap ? { motion_total: all.length } : {}), motion_unread: unread, motion_smil: document.querySelectorAll("animate, animateTransform, animateMotion").length };
  }, [MOTION_CAP, MOTION_ALSO, MOTION_STATES]);
}

const CLAIM_RUNS = 3000;     // runs of text reported per view; the view says so when there were more
const CLAIM_CHARS = 4000;    // characters kept of one run
const SAMPLE_CAP = 200;      // [data-sample] elements reported per view

/** What a claims check reads. `claim_text`: the visible text of the page in runs, {sel, text, sample_label, lang}: a run is the text of one block (the nearest ancestor that is
 *  not inline: inline and inline-block boxes are part of their block's text, so "€<b>5</b>" reads "€5" and a <br> is a break), cut where a [data-sample] begins or ends, so a
 *  labelled sample is a run of its own. `sample_label` is the value of the closest [data-sample] (`null` outside one, `""` when it is empty), `lang` the closest `lang` ("" none;
 *  the document's own is in the view). Elements that are not shown (display: none, a closed <details>, cut to nothing) are left out, a fully transparent one is not: a block that fades in
 *  is still content. Attributes (alt, title, aria-label, placeholder) and pseudo-elements are not read. `claim_text_total` is set when there were more runs than CLAIM_RUNS.
 *  `samples`: every shown [data-sample] element, {sel, label, text (200 characters)}. `claim_h1` is the text of each shown <h1> (at most 20, 300 characters each): the claims
 *  check reads it, and the document title (`document.title`), for one thing, the status code of an error page. Text inside a shadow root is not read (the walk follows child nodes). */
async function claimFacts(page) {
  return page.evaluate(([runCap, charCap, sampleCap]) => {
    const H = window.__bcMeasure;
    const INLINE = new Set(["inline", "inline-block", "contents", "ruby", "ruby-base", "ruby-text"]);
    const runs = new Map(), ids = new Map();
    const idOf = (el) => { if (!ids.has(el)) ids.set(el, ids.size); return ids.get(el); };
    const add = (container, label, lang, text) => {
      const key = `${idOf(container)}|${label}|${lang}`;
      let run = runs.get(key);
      if (!run) { run = { container, label, lang, text: "" }; runs.set(key, run); }
      if (run.text.length < charCap) run.text += text;
    };
    const walk = (node, container, label, lang) => {
      for (const child of node.childNodes) {
        if (child.nodeType === 3) { add(container, label, lang, child.nodeValue); continue; }
        if (child.nodeType !== 1 || !H.walkable(child) || !H.shown(child).shown) continue;
        if (child.localName === "br") { add(container, label, lang, "\n"); continue; }
        const s = getComputedStyle(child);
        walk(child, INLINE.has(s.display) ? container : child,
             child.hasAttribute("data-sample") ? child.getAttribute("data-sample") : label,
             child.hasAttribute("lang") ? child.getAttribute("lang") : lang);
      }
    };
    if (document.body) walk(document.body, document.body, null, document.body.hasAttribute("lang") ? document.body.getAttribute("lang") : "");
    const all = [...runs.values()].map((r) => ({ ...r, text: r.text.replace(/[ \t\r\n\f]+/g, " ").trim() })).filter((r) => r.text);
    const claim_text = all.slice(0, runCap).map((r) => ({ sel: H.selector(r.container), text: r.text.slice(0, charCap), sample_label: r.label, lang: r.lang }));
    const samples = [];
    for (const el of document.querySelectorAll("[data-sample]")) {
      if (!H.walkable(el) || !H.shown(el).shown) continue;
      const text = String(el.innerText ?? el.textContent ?? "").replace(/\s+/g, " ").trim();
      samples.push({ sel: H.selector(el), label: el.getAttribute("data-sample"), text: text.slice(0, 200) });
      if (samples.length >= sampleCap) break;
    }
    const claim_h1 = [];
    for (const el of document.querySelectorAll("h1")) {
      if (!H.walkable(el) || !H.shown(el).shown) continue;
      claim_h1.push(String(el.innerText ?? el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 300));
      if (claim_h1.length >= 20) break;
    }
    return { claim_text, ...(all.length > runCap ? { claim_text_total: all.length } : {}), samples, claim_h1 };
  }, [CLAIM_RUNS, CLAIM_CHARS, SAMPLE_CAP]);
}

const MARK_CAP = 100;           // marks (marked, or named like a logo) reported per view; the view says so when there were more
const IMAGE_CAP = 300;          // other images reported per view: the judge may find one is a logo file by its bytes
const SVG_MARKUP_CAP = 60000;   // characters of an inline SVG mark kept for the judge to compare with the logo drawings
const DATA_URL_CAP = 5 * 1024 * 1024;   // a data: image larger than this is not hashed

/** The brand mark on the page and what stands next to it, in one walk. A mark is an element with `data-brand-mark`, or an image whose file name says it is the logo: the name (without its
 *  extension) is `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more (`logo.svg`, `mark-dark.svg`, `wordmark_light.svg`, `logo@2x.png`; not `partner-logo.svg`,
 *  `ikona-logowanie.svg`, `bookmark.svg`, `marker.svg` or `market-chart.png`, which only hold the word). `mark` and `wordmark` make a name candidate only for an `.svg` file (a photo
 *  `mark.jpg`, `Mark.png` or `mark-kowalski.jpg` is a person, not a logo); `logo` does for any image type. The
 *  third way to be a mark, an image whose bytes equal a logo file of the project, is the judge's (`pagecheck.identified_marks`). The images are `img` (what the
 *  browser chose to show, `currentSrc`, so the `source` of a `picture` is covered), an SVG `image`, a CSS `background-image` of an element and of its `::before` and `::after`.
 *  `data-brand-mark` on an element that is none of them stands for the images inside it. `marks` holds the marked and the named ones, `images` the other visible images (a judge may
 *  find one is a logo file by its bytes, which only the node side saw). An entry is {sel, kind, url, own, declared, named, marked, visible, rect, nearest_px, nearest_sel, nearest_text}
 *  plus `sha256` (a data: URL, hashed here; a file of the page's origin is hashed by render.mjs, see `resources`), `svg_markup` (an inline SVG mark, serialised as XML) and `pseudo`.
 *  `kind` is img, picture, image, background, inline-svg or other (a marked element that shows no image). `url` of a file of the page's origin is its path with the query, the key
 *  of `resources`; `declared` the value of `data-brand-mark` (null when the attribute is not there); `rect` the box in page css px (null for a pseudo-element, which has none to read;
 *  `height_px` is then its computed height when that is a length). `nearest_px` is the gap to the nearest other box that is shown: a line of text, an `img`, `canvas`, `video` or an
 *  outer `svg`, none of them the mark or inside it, and no `img`, `canvas`, `video` or `svg` that holds the mark. The gap is the larger of the horizontal and the vertical distance between the two
 *  boxes (0 when they touch or overlap), because the clear space is a margin round the mark; null when nothing else is on the page. */
async function markFacts(page) {
  return page.evaluate(async ([markCap, imageCap, svgCap, dataCap]) => {
    const H = window.__bcMeasure;
    const round = (v) => Math.round(v * 100) / 100;
    const here = location.origin;

    const fileOf = (u) => {
      try { return decodeURIComponent(new URL(u, document.baseURI).pathname.split("/").pop() || ""); } catch { return ""; }
    };
    // a file is named like the logo when its stem is `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more (`logo.svg`, `mark-dark.svg`, `wordmark_light.svg`,
    // `logo@2x.png`), in any case; a word that merely holds one (`partner-logo.svg`, `ikona-logowanie.svg`, `logos.png`, `bookmark.svg`, `marker.svg`, `market-chart.png`) is not, and a data:
    // URL has no file name at all. `mark` is also a person's name, and both are ordinary words, so they name a candidate only for an .svg file (`mark.jpg`, `Mark.png`,
    // `mark-kowalski.jpg`, `wordmark.png` are not); `logo` names one for any image type (`logo.jpg`, `logo@2x.png`)
    const named = (u) => {
      if (/^data:/i.test(u)) return false;
      const m = /^([\s\S]*?)(?:\.([A-Za-z0-9]{1,5}))?$/.exec(fileOf(u));
      return /^logo(?:[-_@]|$)/i.test(m[1]) || (/^(?:mark|wordmark)(?:[-_@]|$)/i.test(m[1]) && /^svg$/i.test(m[2] || ""));
    };
    const place = (u) => {   // -> {url, own, data?}: where an image lives, as the key of `resources` when it is the page's own
      if (!u) return { url: null, own: false };
      if (/^data:/i.test(u)) return { url: u.slice(0, 80), own: false, data: u };
      try {
        const x = new URL(u, document.baseURI);
        return x.origin === here ? { url: x.pathname + x.search, own: true } : { url: x.href.slice(0, 200), own: false };
      } catch { return { url: String(u).slice(0, 200), own: false }; }
    };
    const dataBytes = (u) => {
      const m = /^data:([^,]*),([\s\S]*)$/i.exec(u);
      if (!m) return null;
      try {
        if (/;base64$/i.test(m[1])) return Uint8Array.from(atob(decodeURIComponent(m[2])), (c) => c.charCodeAt(0));
        const out = [], enc = new TextEncoder(), body = m[2];
        for (let i = 0; i < body.length;) {
          if (body[i] === "%" && /^[0-9a-f]{2}$/i.test(body.slice(i + 1, i + 3))) { out.push(parseInt(body.slice(i + 1, i + 3), 16)); i += 3; continue; }
          const cp = body.codePointAt(i);
          out.push(...enc.encode(String.fromCodePoint(cp)));
          i += cp > 0xffff ? 2 : 1;
        }
        return Uint8Array.from(out);
      } catch { return null; }
    };
    const sha256 = async (u) => {
      const bytes = dataBytes(u);
      if (!bytes || bytes.length > dataCap || !(window.crypto && crypto.subtle)) return null;
      return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((b) => b.toString(16).padStart(2, "0")).join("");
    };
    const boxOf = (el, s) => {
      const r = el.getBoundingClientRect();
      const info = H.shown(el);
      const visible = info.shown && info.opacity > 0 && s.visibility === "visible" && s.display !== "contents" && r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0;
      return { r, visible };
    };
    const markedBy = (el) => el.closest("[data-brand-mark]");

    const found = [];                // {el, kind, u, marked, pseudo?}
    const markedWith = new Set();    // the marked elements that stand for at least one image
    for (const el of document.querySelectorAll("*")) {
      if (!H.walkable(el)) continue;
      const s = getComputedStyle(el), marker = markedBy(el);
      const add = (kind, u, extra = {}) => { found.push({ el, kind, u, marker, ...extra }); if (marker) markedWith.add(marker); };
      if (el.localName === "img") add(el.parentElement && el.parentElement.localName === "picture" ? "picture" : "img", el.currentSrc || el.getAttribute("src") || null);
      else if (el.localName === "svg" && !(el.parentElement instanceof SVGElement)) { if (marker) add("inline-svg", null); }
      else if (el.localName === "image" && el instanceof SVGElement) add("image", el.href && el.href.baseVal ? el.href.baseVal : null);
      if (!(el instanceof SVGElement) && H.shown(el).shown) {   // a background of an element that is not shown is not on the page (and a pseudo-element's style is the dear one to read)
        for (const pseudo of ["", "::before", "::after"]) {
          const ps = pseudo ? getComputedStyle(el, pseudo) : s;
          if (pseudo && (ps.content === "none" || ps.content === "normal")) continue;
          const urls = [...ps.backgroundImage.matchAll(/url\(\s*("([^"]*)"|'([^']*)'|([^)]*))\s*\)/g)].slice(0, 4).map((m) => m[2] ?? m[3] ?? m[4]);
          for (const u of urls) add("background", u, pseudo ? { pseudo } : {});
        }
      }
    }
    for (const el of document.querySelectorAll("[data-brand-mark]")) {
      if (H.walkable(el) && !markedWith.has(el)) found.push({ el, kind: "other", u: null, marker: el });
    }

    // the boxes a mark's neighbours are: lines of text and the images and SVG drawings of the page
    const boxes = [];
    const keep = (r) => r.width >= 1 && r.height >= 1 && r.right > 0 && r.bottom > 0;
    const range = document.createRange();
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
    for (let n; (n = walker.nextNode());) {
      const text = n.nodeValue.trim(), p = n.parentElement;
      if (!text || !p || !H.walkable(p)) continue;
      const info = H.shown(p);
      if (!info.shown || info.opacity <= 0 || getComputedStyle(p).visibility !== "visible") continue;
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) if (keep(r)) boxes.push({ el: p, node: n, r, text: text.slice(0, 40) });
    }
    for (const el of document.querySelectorAll("img, canvas, video, svg")) {
      if (!H.walkable(el) || (el.localName === "svg" && el.parentElement instanceof SVGElement)) continue;
      const { r, visible } = boxOf(el, getComputedStyle(el));
      if (visible) boxes.push({ el, node: null, r, text: null });
    }
    const nearest = (el, r) => {
      let best = null;
      for (const b of boxes) {
        const d = Math.max(Math.max(0, r.left - b.r.right, b.r.left - r.right), Math.max(0, r.top - b.r.bottom, b.r.top - r.bottom));
        if (best && d >= best.d) continue;   // the cheap test first: only a box that would be nearer is asked whether it is the mark, inside it, or a drawing that holds it
        if (b.el === el || el.contains(b.el) || (!b.node && b.el.contains(el))) continue;
        best = { d, b };
      }
      return best ? { nearest_px: round(best.d), nearest_sel: H.selector(best.b.el), nearest_text: best.b.text } : { nearest_px: null, nearest_sel: null, nearest_text: null };
    };

    const marks = [], images = [];
    let marksTotal = 0, imagesTotal = 0;
    for (const f of found) {
      const s = getComputedStyle(f.el), where = place(f.u), isNamed = Boolean(f.u) && named(f.u), marked = Boolean(f.marker);
      if (!marked && !isNamed && !where.url) continue;
      const box = f.pseudo ? { r: null, visible: boxOf(f.el, s).visible } : boxOf(f.el, s);
      if (!marked && !isNamed && !box.visible) continue;   // an image that is not shown and says nothing of a logo is not on the page; a hidden mark (marked, or named like one) is still reported
      const list = marked || isNamed ? marks : images;
      if (list === marks) marksTotal++; else imagesTotal++;
      if (list.length >= (list === marks ? markCap : imageCap)) continue;   // over the cap: neither measured nor hashed (the neighbour search below is the costly part)
      const entry = {
        sel: H.selector(f.el) + (f.pseudo || ""), kind: f.kind, url: where.url, own: where.own, declared: f.marker ? f.marker.getAttribute("data-brand-mark") : null,
        named: isNamed, marked, visible: box.visible,
        rect: box.r ? { x: round(box.r.x + scrollX), y: round(box.r.y + scrollY), width: round(box.r.width), height: round(box.r.height) } : null,
        ...(f.pseudo ? { pseudo: f.pseudo, height_px: /px$/.test(getComputedStyle(f.el, f.pseudo).height) ? round(parseFloat(getComputedStyle(f.el, f.pseudo).height)) : null } : {}),
      };
      if (where.data) entry.sha256 = await sha256(where.data);
      if (f.kind === "inline-svg") {
        let markup = "";
        try { markup = new XMLSerializer().serializeToString(f.el); } catch { /* an element the serializer refuses: no markup, and the judge says it could not compare */ }
        entry.svg_markup = markup.slice(0, svgCap);
        if (markup.length > svgCap) entry.svg_truncated = true;
      }
      Object.assign(entry, box.r && box.visible ? nearest(f.el, box.r) : { nearest_px: null, nearest_sel: null, nearest_text: null });
      list.push(entry);
    }
    return { marks, images, ...(marksTotal > marks.length ? { marks_total: marksTotal } : {}), ...(imagesTotal > images.length ? { images_total: imagesTotal } : {}) };
  }, [MARK_CAP, IMAGE_CAP, SVG_MARKUP_CAP, DATA_URL_CAP]);
}

// ---------------------------------------------------------------- fonts
const FONT_KEYS = 60;    // distinct (first family, weight, style) reported per view; the view says so when there were more
const FONT_FACES = 200;  // @font-face rules (FontFace objects of document.fonts) reported per view
const FONT_PROBE = "data-bc-font-probe";
const FONT_INLINE = 12;  // inline elements in another font that one probe can have taken off its answer; a probe with more is not asked

/** The fonts of the page. `font_faces`: every FontFace of document.fonts, `{family, weight, style, stretch, unicode_range, status}` (status: unloaded, loading, loaded or
 *  error; the page is measured after fonts.ready, so a face its text needs is loaded or in error). `font_usage`: one entry per distinct (first family, weight, style) of the
 *  computed `font-family` of the shown elements with text of their own (an input's value or placeholder counts), in document order: `{family, weight, style, stack, count,
 *  sel, min_px, min_sel, min_text, platform}`. `family` is the first family of the computed stack, quotes taken off; `min_px` is the smallest computed font size of any element
 *  in the entry, on `min_sel`. `sel` is the one element asked what Chromium really used. CDP `CSS.getPlatformFontsForNode` answers for the element AND everything inside it, so the
 *  probe is the element of the entry with the fewest inline elements inside it that draw text of their own in another (family, weight, style) (none, if the page has such a
 *  one), then the one whose text holds the most different characters, the first on a tie; a text area is the last choice, because the debugger has no answer for it. When the
 *  probe still holds such inline elements, the fonts of each (asked the same way) are taken off its answer, glyph for glyph: `inline_other` says how many. `platform` is that
 *  answer, as `render.mjs fonts` asks it: `[{family, postscript, custom, glyphs}]` (`custom` for a web font, an @font-face; `family` is the name inside the font file, which
 *  can differ from the one the CSS gives it); `platform_error` replaces it when CDP could not answer, and when it cannot be asked for this probe (a text area; more than
 *  FONT_INLINE inline elements in another font; one of them `display: contents`, which has no box of its own to be asked about). Nothing is judged here. `font_usage_total` is
 *  set when there were more entries than FONT_KEYS. */
async function fontFacts(page) {
  const found = await page.evaluate(([keyCap, faceCap, probe, inlineCap]) => {
    const H = window.__bcMeasure;
    /** The families of a font-family list, quotes taken off: `"Acme Sans", system-ui` -> ["Acme Sans", "system-ui"]. */
    const families = (css) => {
      const out = []; let cur = "", quote = null;
      for (const ch of String(css)) {
        if (quote) { if (ch === quote) quote = null; else cur += ch; } else if (ch === '"' || ch === "'") quote = ch;
        else if (ch === ",") { out.push(cur.trim()); cur = ""; } else cur += ch;
      }
      if (cur.trim() || out.length) out.push(cur.trim());
      return out.filter(Boolean);
    };
    const unquote = (s) => String(s).trim().replace(/^(["'])(.*)\1$/, "$2");
    const faces = [...document.fonts].map((f) => ({ family: unquote(f.family), weight: f.weight, style: f.style, stretch: f.stretch, unicode_range: f.unicodeRange, status: f.status }));
    const ownText = (el) => {
      if (el.localName === "input" || el.localName === "textarea") {
        const type = (el.getAttribute("type") || "text").toLowerCase();
        if (el.localName === "input" && ["hidden", "checkbox", "radio", "range", "color", "file", "image"].includes(type)) return "";
        return String((type === "password" ? "" : el.value) || el.placeholder || "").replace(/\s+/g, " ").trim();
      }
      let t = "";
      for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
      return t.replace(/\s+/g, " ").trim();
    };
    const hasBox = (el) => {   // the text is laid out: a box of at least 2 by 2 css px that is not wholly above or left of the page's origin
      if (el.localName === "input" || el.localName === "textarea") { const r = el.getBoundingClientRect(); return r.width >= 2 && r.height >= 2 && r.right > 0 && r.bottom > 0; }
      const range = document.createRange();
      for (const n of el.childNodes) {
        if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
        range.selectNodeContents(n);
        for (const r of range.getClientRects()) if (r.width >= 2 && r.height >= 2 && r.right > 0 && r.bottom > 0) return true;
      }
      return false;
    };
    const laidOut = (el) => {   // the text is drawn at all (a hidden one too: the debugger counts it), unlike hasBox, which wants a box a reader can see
      if (el.localName === "input" || el.localName === "textarea") return el.getClientRects().length > 0;
      const range = document.createRange();
      for (const n of el.childNodes) {
        if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
        range.selectNodeContents(n);
        if (range.getClientRects().length) return true;
      }
      return false;
    };
    const fontOf = (s) => {
      const family = families(s.fontFamily)[0] || "", weight = parseInt(s.fontWeight, 10) || 400, style = s.fontStyle;
      return { family, weight, style, key: `${family}\u0000${weight}\u0000${style}` };
    };
    /** The outermost elements inside `root` that draw text of their own in another (family, weight, style) than `key`; what they hold is theirs. `blind`: one of them is
     *  `display: contents`, which has no box of its own for the debugger to be asked about. */
    const foreignIn = (root, key) => {
      const out = []; let blind = false;
      const walk = (parent) => {
        for (const c of parent.children) {
          const s = getComputedStyle(c);
          if (s.display === "none") continue;
          if (ownText(c) && fontOf(s).key !== key && laidOut(c)) { out.push(c); blind = blind || s.display === "contents"; } else walk(c);
        }
      };
      walk(root);
      return { out, blind };
    };
    const groups = new Map();
    for (const el of document.querySelectorAll("*")) {
      if (!H.walkable(el)) continue;
      const info = H.shown(el);
      if (!info.shown || info.opacity <= 0) continue;
      const s = getComputedStyle(el);
      if (s.display === "contents" || s.visibility !== "visible") continue;
      const text = ownText(el);
      if (!text || !hasBox(el)) continue;
      const { family, weight, style, key } = fontOf(s), px = parseFloat(s.fontSize), score = new Set(text).size;
      const g = groups.get(key);
      if (!g) groups.set(key, { family, weight, style, stack: s.fontFamily.slice(0, 300), key, members: [{ el, score }], min_px: px, min_el: el, min_text: text });
      else {
        g.members.push({ el, score });
        if (px < g.min_px) { g.min_px = px; g.min_el = el; g.min_text = text; }
      }
    }
    /** The element of a group to ask the debugger about: no inline element in another font inside it (else the fewest), no text area (else it), then the most different
     *  characters, the first of them on a tie. */
    const pickProbe = (g) => {
      let best = null;
      for (const m of [...g.members].sort((a, b) => b.score - a.score)) {   // stable: document order among equals
        const { out, blind } = foreignIn(m.el, g.key), opaque = m.el.localName === "textarea";
        const bad = (opaque ? 1e6 : 0) + (blind ? 1e5 : 0) + (out.length > inlineCap ? 1e4 : 0) + out.length;
        if (!best || bad < best.bad) best = { el: m.el, out, blind, opaque, bad };
        if (!bad) break;
      }
      return best;
    };
    const entries = [...groups.values()];
    const usage = entries.slice(0, keyCap).map((g, i) => {
      const pick = pickProbe(g), u = { family: g.family, weight: g.weight, style: g.style, stack: g.stack, count: g.members.length, sel: H.selector(pick.el),
                                       min_px: Math.round(g.min_px * 100) / 100, min_sel: H.selector(g.min_el), min_text: g.min_text.slice(0, 40), probe: i };
      if (pick.opaque) u.platform_error = "the browser's debugger has no answer for the text of a text area";
      else if (pick.blind) u.platform_error = "an element inside it is display: contents and set in another font, which the debugger cannot be asked about on its own";
      else if (pick.out.length > inlineCap) u.platform_error = `${pick.out.length} elements inside it are set in other fonts (more than ${inlineCap})`;
      else {
        // marked for the CDP step, taken off again in fontFacts; one element can be the probe of one entry and inside the probe of another, so a mark is one word of a list
        const mark = (el, word) => el.setAttribute(probe, ((el.getAttribute(probe) || "") + " " + word).trim());
        mark(pick.el, String(i));
        pick.out.forEach((c, j) => mark(c, `${i}.${j}`));
        if (pick.out.length) u.inline_other = pick.out.length;
      }
      return u;
    });
    return { faces: faces.slice(0, faceCap), faces_total: faces.length, usage, usage_total: entries.length };
  }, [FONT_KEYS, FONT_FACES, FONT_PROBE, FONT_INLINE]);

  if (found.usage.length) {
    let cdp = null;
    try {
      cdp = await page.context().newCDPSession(page);   // a debugger that cannot be reached is a fact the judge reports as not verified, not a view that fails
      await cdp.send("DOM.enable");
      await cdp.send("CSS.enable");
      const { root } = await cdp.send("DOM.getDocument");
      const ask = async (mark) => {
        const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: `[${FONT_PROBE}~="${mark}"]` });
        if (!nodeId) throw new Error("the element could not be found by the browser's debugger");
        const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
        return fonts.map((f) => ({ family: f.familyName, postscript: f.postScriptName, custom: Boolean(f.isCustomFont), glyphs: f.glyphCount }));
      };
      for (const u of found.usage) {
        if (u.platform_error) continue;   // decided in the page: this probe cannot be asked
        try {
          let platform = await ask(u.probe);
          // the answer holds the glyphs of everything inside the probe: take off those of the inline elements set in another font, which are not this entry's text
          for (let j = 0; j < (u.inline_other || 0); j++) {
            for (const m of await ask(`${u.probe}.${j}`)) {
              const f = platform.find((p) => p.family === m.family && p.postscript === m.postscript && p.custom === m.custom);
              if (f) f.glyphs -= m.glyphs;
            }
          }
          u.platform = platform.filter((p) => p.glyphs > 0);
        } catch (e) {
          u.platform_error = String(e.message).split("\n")[0];
        }
      }
    } catch (e) {
      for (const u of found.usage) if (!u.platform) u.platform_error = u.platform_error || String(e.message).split("\n")[0];
    } finally {
      if (cdp) await cdp.detach().catch(() => {});
      await page.evaluate((probe) => document.querySelectorAll(`[${probe}]`).forEach((e) => e.removeAttribute(probe)), FONT_PROBE).catch(() => {});
    }
  }
  for (const u of found.usage) delete u.probe;
  return { font_faces: found.faces, ...(found.faces_total > found.faces.length ? { font_faces_total: found.faces_total } : {}),
           font_usage: found.usage, ...(found.usage_total > found.usage.length ? { font_usage_total: found.usage_total } : {}) };
}

// ---------------------------------------------------------------- brand rules
const RULE_ITEMS = 300;   // controls or accent elements reported per rule and view; the view says how many there were
const CONTROLS = "button, [role=button], input[type=submit], input[type=button], input[type=reset]";

/** The facts the brand rules of qa/rules.json `page.rules` need from the page's own text. `request.rules` lists the rules that are measured here, `[{id, kind, selector?}]`
 *  (a rule of another kind is judged from facts the view already holds, or not measured); a request with none measures nothing. `rule_facts`: `{<id>: {kind, selector, matched,
 *  shown, items, ...}}`, or `{kind, selector, error}` when the browser does not take the selector as CSS.
 *  `max-words-per-control`: the shown controls (`button`, `[role=button]`, `input[type=submit|button|reset]`, and what the rule's `selector` matches) as `items`
 *  `{sel, text (80 characters), words, via}`, the longest first (`matched` of them, `shown` of those with a box); `text` is the visible text (`innerText`; the value of an input), and
 *  when a control shows none its accessible name (`aria-label`, `aria-labelledby`, the `alt` of an image or `<title>` of an SVG inside it, `title`): `via` says `text`, `name` or `none`.
 *  `words-under-accent`: for each shown element the rule's `selector` matches, `items` `{sel, parent_sel, text, parent_text, own_words, parent_words, around_words}`: the words of its
 *  parent's visible text, those of its own text, and the first minus the second (never below 0). A word is what Unicode word segmentation (`Intl.Segmenter`, UAX #29, in the language of the
 *  closest `lang`) calls word-like: a number is one, a hyphenated compound is two, an arrow, a dot or a symbol is none. Nothing is judged here. */
async function ruleFacts(page, request) {
  const rules = (Array.isArray(request.rules) ? request.rules : []).filter((r) => r && (r.kind === "max-words-per-control" || r.kind === "words-under-accent"));
  if (!rules.length) return {};
  return page.evaluate(([list, cap, controls]) => {
    const H = window.__bcMeasure;
    const segmenters = new Map();
    const segmenter = (lang) => {
      if (!segmenters.has(lang)) {
        let s;
        try { s = new Intl.Segmenter(lang || undefined, { granularity: "word" }); } catch (e) { s = new Intl.Segmenter(undefined, { granularity: "word" }); }   // a lang the browser does not know
        segmenters.set(lang, s);
      }
      return segmenters.get(lang);
    };
    const words = (text, lang) => { let n = 0; for (const seg of segmenter(lang).segment(text)) if (seg.isWordLike) n++; return n; };
    const clean = (t) => String(t ?? "").replace(/\s+/g, " ").trim();
    const langOf = (el) => { const e = el.closest("[lang]"); return e ? e.getAttribute("lang") : ""; };
    const textOf = (el) => clean(el.innerText ?? el.textContent);
    const boxed = (el) => {   // shown to a reader: not hidden or transparent, with a box on the page
      if (!H.walkable(el)) return false;
      const info = H.shown(el);
      if (!info.shown || info.opacity <= 0) return false;
      const s = getComputedStyle(el), r = el.getBoundingClientRect();
      return s.visibility === "visible" && s.display !== "contents" && r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0;
    };
    const nameOf = (el) => {
      const label = clean(el.getAttribute("aria-label"));
      if (label) return label;
      const by = clean((el.getAttribute("aria-labelledby") || "").split(/\s+/).map((id) => (document.getElementById(id) || {}).textContent || "").join(" "));
      if (by) return by;
      const img = el.querySelector("img[alt]"), svgTitle = el.querySelector("svg title");
      return clean((img && img.getAttribute("alt")) || (svgTitle && svgTitle.textContent) || el.getAttribute("title"));
    };
    const out = {};
    for (const rule of list) {
      const facts = { kind: rule.kind, selector: rule.selector ?? null };
      out[rule.id] = facts;
      let els;
      try {
        if (rule.selector) document.querySelector(rule.selector);   // a selector the browser refuses is reported, not guessed at
        els = [...document.querySelectorAll(rule.kind === "max-words-per-control" ? controls + (rule.selector ? ", " + rule.selector : "") : rule.selector)];
      } catch (e) {
        facts.error = String(e.message).split("\n")[0];
        continue;
      }
      const items = [];
      for (const el of els) {
        if (!boxed(el)) continue;
        const lang = langOf(el);
        if (rule.kind === "max-words-per-control") {
          const isInput = el.localName === "input";
          let text = isInput ? clean(el.value) : textOf(el), via = text ? "text" : "none";
          if (!text) { text = nameOf(el); via = text ? "name" : "none"; }
          items.push({ sel: H.selector(el), text: text.slice(0, 80), words: words(text, lang), via });
        } else {
          const parent = el.parentElement, own = textOf(el), around = parent ? textOf(parent) : "";
          const ownWords = words(own, lang), parentWords = words(around, lang);
          items.push({ sel: H.selector(el), parent_sel: parent ? H.selector(parent) : null, text: own.slice(0, 80), parent_text: around.slice(0, 120),
                       own_words: ownWords, parent_words: parentWords, around_words: Math.max(0, parentWords - ownWords) });
        }
      }
      if (rule.kind === "max-words-per-control") items.sort((a, b) => b.words - a.words);   // stable: document order among equals, so a cut loses the shortest
      facts.matched = els.length;
      facts.shown = items.length;
      facts.items = items.slice(0, cap);
    }
    return { rule_facts: out };
  }, [rules, RULE_ITEMS, CONTROLS]);
}

// ---------------------------------------------------------------- generic tells
// The candidates for the generic tells of skills/brand-creator/references/page-tells.json. Each list is what the browser can SEE; pagecheck.py applies the thresholds of that file
// (words, letter spacing, sizes, counts) and the word lists, so a threshold has one home. The floors below only bound how much a view reports.
const TELL = {
  elements: 8000,        // elements walked for separators and boxes; the view says so when the page had more
  eyebrowWords: 12,      // a label of more words than this is no eyebrow candidate (the tell asks for at most 4)
  list: 100,             // arrow candidates, separator runs, headings and details reported per view
  headings: 60,          // headings looked at for an eyebrow
  heroActions: 6,        // actions of the hero reported
  boxFloor: [120, 80, 4],   // a box is a mock-up candidate from this width, height and number of styled descendants (the tell asks for 240 x 160 and 8)
  boxes: 200,
  tileGroups: 40,
};

/** What the generic tells need, in one pass over the visible page; nothing is judged here. `tell_facts`:
 *  `eyebrow`: [{sel, text (80), words, uppercase, letter_spacing_em, font_size_px, heading_sel, heading_tag, heading_font_size_px}]: for every shown h1-h3 the text element directly
 *  before it (an empty box between them, a rule or a spacer, is looked past; an image or an icon is not), when it has 1-12 words and no heading in it and is not a nav, header, footer, list, table or form. `uppercase` is text-transform
 *  uppercase, small caps or text typed in capitals; `letter_spacing_em` the computed letter spacing over the font size.
 *  `arrows`: [{sel, label (80), edge ("start" or "end"), glyph, gap_chars}]: shown links, buttons and submit inputs whose label (the content of ::before and ::after included) starts or
 *  ends with an arrow, a chevron, a double angle, -> or => next to other text; `gap_chars` is the number of white space characters between them: a run of spaces, tabs and line breaks is one (the browser
 *  collapses it), a no-break or an em space is each one (the browser draws every one of them).
 *  `separators`: [{sel, text (80), count, via}]: elements whose own text holds middle dots or bullets with text on both sides on one line (`via: "text"`; a child element is one unit, a <br> or a block child
 *  ends the line, so a dot that starts a line is a list marker and is not counted), and parents whose children carry a ::before or ::after that is a single dot (`via: "pseudo"`, `count` the children
 *  that do and have a sibling beside them in one row; a stacked list with a marker on each item separates nothing).
 *  `hero`: {found, sel, h1_sel, top, words, viewport_height, lang, actions: [{sel, label (80), lang}]}: the first shown h1 and the nearest section, header, [role=banner] or element
 *  named hero around it (else its parent); `words` are the words of its text, outside a nav, that are in the first screen (the top of the page to the viewport height); `actions` are its
 *  shown links, buttons and submit inputs with a label, outside a nav and in the first screen, in document order.
 *  `boxes`: [{id, parent, sel, width, height, styled, in_lists, in_cells, table, list_area, media_px, headings, h1, labelled}]: shown boxes of at least the floor above, `parent` the id of the nearest box above that is also in the list; `styled` is the
 *  number of shown descendants with a background colour or image or a border (not form controls, table parts or rules); `in_lists` how many of those sit in the items of a list (a li of a ul or ol, the li and
 *  everything in it; the items of the outermost list in the box) and `list_area` the area in css px squared of those items themselves, the part of each li box that lies in the rectangle of the box (not the box of the list, which may be stretched past them, and not
 *  what a row of items runs on past the box; a list that holds no styled item adds none), so that
 *  pagecheck.py can tell a box the items fill from a box with a list in it; `in_cells` how many of the `styled` sit in a table cell (a td or th in the box, or the box itself) and `table` whether the box is a table, a table section
 *  or a row (table, thead, tbody, tfoot, tr), so that pagecheck.py can tell a table of badges from a drawing; `media_px` the largest side in css px of the shown media
 *  inside, by element name ({"svg": 24, "img": 600}; img, svg, canvas, video and picture, a picture measured by the img it draws; {} for none): which of them is only an icon is for pagecheck.py to
 *  say; `headings` the shown headings (h1 to h6, [role=heading]) inside and `h1` the shown h1 among them, which tell a section of the page from a drawing; `labelled` whether the box or an ancestor has
 *  a non-empty data-sample.
 *  `tiles`: [{sel, tiles: [{sel, left, top, width, height}]}]: elements with exactly three shown element children (a <template>, a <script> or a hidden child is not counted) that each hold a shown heading.
 *  `headings`: [{sel, text (60), top}] (h1-h6) and `details`: [{sel, top}] (a details element with a summary); `last_band`: the last block of the main content {sel, top, words, headings, actions}.
 *  `viewport` is {width, height}; `truncated` is true when more than TELL.elements elements were on the page. */
async function tellFacts(page) {
  return page.evaluate((K) => {
    const H = window.__bcMeasure;
    const round = (v) => Math.round(v * 100) / 100;
    const clean = (t) => String(t ?? "").replace(/\s+/g, " ").trim();
    const px = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
    const vh = window.innerHeight, vw = window.innerWidth;
    const top = (r) => round(r.top + window.scrollY);
    const langOf = (el) => { const e = el.closest("[lang]"); return e ? e.getAttribute("lang") : ""; };
    const segmenters = new Map();
    const segmenter = (lang) => {
      if (!segmenters.has(lang)) {
        let s;
        try { s = new Intl.Segmenter(lang || undefined, { granularity: "word" }); } catch (e) { s = new Intl.Segmenter(undefined, { granularity: "word" }); }
        segmenters.set(lang, s);
      }
      return segmenters.get(lang);
    };
    const words = (text, lang) => { let n = 0; for (const seg of segmenter(lang).segment(text)) if (seg.isWordLike) n++; return n; };
    const boxed = (el) => {   // shown to a reader: not hidden or transparent, with a box
      if (!H.walkable(el)) return false;
      const info = H.shown(el);
      if (!info.shown || info.opacity <= 0) return false;
      const s = getComputedStyle(el), r = el.getBoundingClientRect();
      return s.visibility === "visible" && s.display !== "contents" && r.width > 0 && r.height > 0;
    };
    const textOf = (el) => clean(el.innerText ?? el.textContent);
    const HEADING = "h1, h2, h3, h4, h5, h6, [role=heading]";
    const CONTROLS = "a[href], button, [role=button], input[type=submit], input[type=button]";
    const MEDIA = "img, svg, picture, canvas, video";
    const NOT_A_LABEL = "nav, header, footer, ul, ol, dl, table, form, [role=navigation]";   // a menu, a list or a form before a heading is not a label over it
    const pseudoText = (el, which) => {
      const c = getComputedStyle(el, which).content;
      const m = /^"((?:[^"\\]|\\.)*)"$/s.exec(c) || /^'((?:[^'\\]|\\.)*)'$/s.exec(c);
      return m ? m[1].replace(/\\(.)/gs, "$1") : "";
    };
    const labelOf = (el) => {   // what a control shows: its text (the value of an input) with the content of its ::before and ::after
      const own = el.localName === "input" ? el.value : (el.innerText ?? el.textContent);
      return clean(pseudoText(el, "::before") + clean(own) + pseudoText(el, "::after"));
    };
    const collapsible = (t) => String(t ?? "").replace(/[ \t\n\r\f]+/g, " ").trim();   // what the browser collapses; a no-break space or an em space is drawn, so it stays
    const spacedLabelOf = (el) => {   // the label with its no-break and em spaces kept, to measure the gap an arrow is set apart by
      const own = el.localName === "input" ? el.value : (el.innerText ?? el.textContent);
      return collapsible(pseudoText(el, "::before") + own + pseudoText(el, "::after"));
    };
    const all = [...document.body.querySelectorAll("*")];
    const truncated = all.length > K.elements;
    const els = truncated ? all.slice(0, K.elements) : all;

    // eyebrow: the text element directly before a heading
    const before = (h) => {
      for (let p = h.previousElementSibling; p; p = p.previousElementSibling) {
        if (!H.walkable(p) || !H.shown(p).shown) continue;
        if (textOf(p)) return p;
        if (p.matches(MEDIA) || p.querySelector(MEDIA)) return null;   // an image or an icon is in between
      }
      return null;   // only empty boxes (a rule, a spacer) or nothing
    };
    const styleSource = (el) => {   // a wrapper's text is styled by the element that holds it
      let cur = el;
      for (let i = 0; i < 4; i++) {
        const kids = [...cur.children].filter((c) => H.walkable(c) && H.shown(c).shown && textOf(c));
        const ownText = [...cur.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());
        if (ownText || kids.length !== 1) break;
        cur = kids[0];
      }
      return cur;
    };
    const eyebrow = [];
    for (const h of document.querySelectorAll("h1, h2, h3")) {
      if (eyebrow.length >= K.headings) break;
      if (!boxed(h)) continue;
      const prev = before(h);
      if (!prev || prev.matches(HEADING) || prev.querySelector(HEADING) || prev.matches(NOT_A_LABEL) || prev.closest("nav, [role=navigation]")) continue;
      const text = textOf(prev), n = words(text, langOf(prev));
      if (n < 1 || n > K.eyebrowWords) continue;
      const s = getComputedStyle(styleSource(prev)), size = px(s.fontSize);
      const caps = s.textTransform === "uppercase" || s.fontVariantCaps === "small-caps" || s.fontVariantCaps === "all-small-caps"
        || (/\p{L}/u.test(text) && text === text.toUpperCase() && text !== text.toLowerCase());
      eyebrow.push({ sel: H.selector(prev), text: text.slice(0, 80), words: n, uppercase: caps, letter_spacing_em: round(s.letterSpacing === "normal" || !size ? 0 : px(s.letterSpacing) / size),
                     font_size_px: round(size), heading_sel: H.selector(h), heading_tag: h.localName, heading_font_size_px: round(px(getComputedStyle(h).fontSize)) });
    }

    // arrows glued to a label
    const ARROW = "(?:[→←↗↘↖↙⟶⟵⟹⟸⇒⇐⇢➔➜➝➞➡↦›»‹«]|->|=>)";
    const lead = new RegExp(`^(${ARROW})(\\s*)(?=\\S)`, "u"), trail = new RegExp(`(?<=\\S)(\\s*)(${ARROW})$`, "u");
    const arrows = [];
    for (const el of document.querySelectorAll(CONTROLS)) {
      if (arrows.length >= K.list) break;
      if (!boxed(el)) continue;
      const label = labelOf(el), spaced = spacedLabelOf(el);
      if (!/[\p{L}\p{N}]/u.test(label)) continue;   // an arrow alone is an icon button, not a label with an arrow glued to it
      const a = lead.exec(spaced), z = trail.exec(spaced);
      if (a) arrows.push({ sel: H.selector(el), label: label.slice(0, 80), edge: "start", glyph: a[1], gap_chars: a[2].length });
      else if (z) arrows.push({ sel: H.selector(el), label: label.slice(0, 80), edge: "end", glyph: z[2], gap_chars: z[1].length });
    }

    // middle dots between items
    const DOTS = "·•‧∙⋅●";
    const isDot = (c) => DOTS.includes(c);
    const BREAK = "\u0002";   // a <br> or a block child ends a line; a line break in the source is no more than white space
    const separators = [];
    const pseudoParents = new Map();
    for (const el of els) {
      if (!H.walkable(el) || !H.shown(el).shown) continue;
      const flowing = !/flex|grid/.test(getComputedStyle(el).display);   // in a flex or grid container the children are items side by side, not lines
      let own = "";
      for (const n of el.childNodes) {
        if (n.nodeType === 3) own += n.nodeValue;
        else if (n.nodeType === 1 && H.walkable(n) && H.shown(n).shown) {
          const inline = n.localName !== "br" && (!flowing || /^(inline|contents|ruby)/.test(getComputedStyle(n).display));
          own += inline ? "\u0001" : BREAK;   // an inline child element stands in the text as one unit
        }
      }
      let count = 0;
      for (const line of own.split(BREAK)) {   // a dot that starts a line is a marker (a bulleted list), not a separator: text must be on both sides of it in its line
        for (let i = 0; i < line.length; i++) if (isDot(line[i]) && line.slice(0, i).trim() && line.slice(i + 1).trim()) count++;
      }
      if (count && separators.length < K.list) separators.push({ sel: H.selector(el), text: textOf(el).slice(0, 80), count, via: "text" });
      if (el.parentElement) {
        for (const which of ["::before", "::after"]) {
          const t = pseudoText(el, which).trim();
          if (t.length === 1 && isDot(t) && boxed(el)) pseudoParents.set(el.parentElement, (pseudoParents.get(el.parentElement) || new Set()).add(el));
        }
      }
    }
    const beside = (a, b) => a.top < b.bottom - 1 && b.top < a.bottom - 1 && (a.right <= b.left + 1 || b.right <= a.left + 1);   // two boxes in one row
    for (const [parent, kids] of pseudoParents) {
      if (separators.length >= K.list * 2) break;
      const rects = new Map([...parent.children].filter(boxed).map((c) => [c, c.getBoundingClientRect()]));
      const count = [...kids].filter((k) => rects.has(k) && [...rects].some(([c, r]) => c !== k && beside(rects.get(k), r))).length;   // a stacked list separates nothing
      if (count) separators.push({ sel: H.selector(parent), text: textOf(parent).slice(0, 80), count, via: "pseudo" });
    }

    // the hero: the block that holds the first h1
    const inNav = (el) => Boolean(el.closest("nav, [role=navigation]"));
    const hero = { found: false };
    const h1 = [...document.querySelectorAll("h1")].find(boxed);
    if (h1) {
      let box = h1.parentElement && h1.parentElement.closest("section, header, [role=banner], [class*=hero i], [id*=hero i]");
      if (!box || box === document.body || box === document.documentElement) box = h1.parentElement || h1;
      const shownText = (node) => {
        const p = node.parentElement;
        if (!p || !H.walkable(p) || inNav(p) || p.closest("script, style, noscript, template")) return false;
        const info = H.shown(p);
        return info.shown && info.opacity > 0 && getComputedStyle(p).visibility === "visible";
      };
      let inScreen = 0;
      const range = document.createRange();
      const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        if (!n.nodeValue.trim() || !shownText(n)) continue;
        range.selectNodeContents(n);
        const r = range.getBoundingClientRect();
        if (r.width <= 0 && r.height <= 0) continue;
        const lang = langOf(n.parentElement);
        if (top(r) >= vh) continue;
        if (r.bottom + window.scrollY <= vh) { inScreen += words(n.nodeValue, lang); continue; }
        for (const seg of segmenter(lang).segment(n.nodeValue)) {   // a text that runs over the fold: count the words above it
          if (!seg.isWordLike) continue;
          range.setStart(n, seg.index);
          range.setEnd(n, seg.index + seg.segment.length);
          const wr = range.getBoundingClientRect();
          if (wr.top + window.scrollY < vh) inScreen++;
        }
      }
      const actions = [];
      for (const el of box.querySelectorAll(CONTROLS)) {
        if (actions.length >= K.heroActions) break;
        if (!boxed(el) || inNav(el) || top(el.getBoundingClientRect()) >= vh) continue;
        const label = labelOf(el) || clean(el.getAttribute("aria-label"));
        if (label) actions.push({ sel: H.selector(el), label: label.slice(0, 80), lang: langOf(el) });
      }
      Object.assign(hero, { found: true, sel: H.selector(box), h1_sel: H.selector(h1), top: top(box.getBoundingClientRect()), words: inScreen, viewport_height: vh, lang: langOf(h1), actions });
    }

    // boxes built from styled boxes: one walk, counting from the leaves up
    const NOT_STYLED = new Set(["input", "select", "textarea", "button", "option", "hr", "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup", "col"]);
    const MEDIA_TAGS = new Set(["img", "svg", "picture", "canvas", "video"]);
    const styledBox = (el, s) => {
      if (NOT_STYLED.has(el.localName)) return false;
      const bg = H.colour(s.backgroundColor);
      if ((bg && bg.a > 0) || s.backgroundImage !== "none") return true;
      for (const side of ["Top", "Right", "Bottom", "Left"]) {
        const style = s[`border${side}Style`];
        if (px(s[`border${side}Width`]) > 0 && style !== "none" && style !== "hidden") { const c = H.colour(s[`border${side}Color`]); if (c && c.a > 0) return true; }
      }
      return false;
    };
    const boxes = [];
    let walked = 0, nextId = 0;
    const nothing = () => ({ styled: 0, media: {}, inLists: 0, inCells: 0, itemRects: [], rect: null, headings: 0, h1: 0 });
    const TABLE_PARTS = new Set(["table", "thead", "tbody", "tfoot", "tr"]);
    const overlap = (a, r) => Math.max(0, Math.min(a.right, r.right) - Math.max(a.left, r.left)) * Math.max(0, Math.min(a.bottom, r.bottom) - Math.max(a.top, r.top));   // the part of a that lies in r
    const walk = (el, nearest) => {   // -> {styled, media: {element name: largest side}, inLists, inCells, itemRects, rect, headings, h1} counted inside el, el itself included; rect is el's own box
      if (!H.walkable(el) || walked++ > K.elements) return nothing();
      if (MEDIA_TAGS.has(el.localName)) {
        const drawn = el.localName === "picture" ? el.querySelector("img") : el;   // a picture is as big as the img it draws: its own box is the line round it
        if (!drawn || !boxed(drawn)) return nothing();
        const m = drawn.getBoundingClientRect();
        return { ...nothing(), media: { [el.localName]: round(Math.max(m.width, m.height)) } };
      }
      if (!H.shown(el).shown) return nothing();
      const s = getComputedStyle(el), r = el.getBoundingClientRect();
      const has = s.display !== "contents" && r.width > 0 && r.height > 0 && s.visibility === "visible";
      const big = has && r.width >= K.boxFloor[0] && r.height >= K.boxFloor[1];
      const me = big ? { id: nextId++, parent: nearest ? nearest.id : null, sel: H.selector(el), width: round(r.width), height: round(r.height), el } : null;
      const isList = el.localName === "ul" || el.localName === "ol";
      const isCell = el.localName === "td" || el.localName === "th";
      let styled = 0, inLists = 0, inCells = 0, items = 0, headings = has && el.matches(HEADING) ? 1 : 0, h1 = has && el.localName === "h1" ? 1 : 0;
      const itemRects = [], itemBoxes = [];   // the boxes of the li of the outermost lists inside el; and, for el a list, those of its own items
      const media = {};
      for (const c of el.children) {
        const got = walk(c, me || nearest);
        styled += got.styled;
        headings += got.headings;
        h1 += got.h1;
        inCells += isCell ? got.styled : got.inCells;   // everything styled in a cell is in the cell, a badge in a td as much as a list in it
        for (const [name, side] of Object.entries(got.media)) media[name] = Math.max(media[name] ?? 0, side);
        if (isList && c.localName === "li") { items += got.styled; if (got.rect) itemBoxes.push(got.rect); }   // an item and all it holds is the list's; a list inside it is part of it
        else { inLists += got.inLists; for (const x of got.itemRects) itemRects.push(x); }
      }
      if (items) { inLists += items; for (const x of itemBoxes) itemRects.push(x); }   // a list that holds no styled item adds nothing; the room of the items themselves, not of the list: a list stretched past its items is not full of them
      if (me && styled >= K.boxFloor[2] && boxes.length < K.boxes) {
        const sample = el.closest("[data-sample]");
        let listArea = 0;
        for (const x of itemRects) listArea += overlap(x, r);   // an item is counted where it lies in this box: a carousel that runs past the box fills no more of it than the box
        boxes.push({ id: me.id, parent: me.parent, sel: me.sel, width: me.width, height: me.height, styled, in_lists: inLists, in_cells: inCells, table: TABLE_PARTS.has(el.localName), list_area: round(listArea), media_px: media, headings, h1,
                     labelled: Boolean(sample && sample.getAttribute("data-sample").trim()) });
      }
      return { styled: styled + (has && styledBox(el, s) ? 1 : 0), media, inLists, inCells, itemRects, rect: has ? { left: r.left, top: r.top, right: r.right, bottom: r.bottom } : null, headings, h1 };
    };
    for (const c of document.body.children) walk(c, null);
    boxes.sort((a, b) => a.id - b.id);

    // a row of three
    const tiles = [];
    for (const parent of els) {
      if (tiles.length >= K.tileGroups) break;
      if (parent.children.length < 3 || !boxed(parent)) continue;
      const kids = [...parent.children].filter(boxed);   // a <template>, a <script> or a hidden child is no tile
      if (kids.length !== 3 || !kids.every((k) => [...k.querySelectorAll(HEADING)].some(boxed))) continue;
      tiles.push({ sel: H.selector(parent), tiles: kids.map((k) => { const r = k.getBoundingClientRect(); return { sel: H.selector(k), left: round(r.left + window.scrollX), top: top(r), width: round(r.width), height: round(r.height) }; }) });
    }

    // where the pieces of a stock page would be
    const headings = [];
    for (const h of document.querySelectorAll(HEADING)) {
      if (headings.length >= K.list) break;
      if (boxed(h)) headings.push({ sel: H.selector(h), text: textOf(h).slice(0, 60), top: top(h.getBoundingClientRect()) });
    }
    const details = [];
    for (const d of document.querySelectorAll("details")) {
      if (details.length >= K.list) break;
      if (boxed(d) && [...d.children].some((c) => c.localName === "summary")) details.push({ sel: H.selector(d), top: top(d.getBoundingClientRect()) });
    }
    let root = document.querySelector("main") || document.body, band = null;
    for (let depth = 0; depth < 4; depth++) {   // a wrapper round the sections is looked into
      const kids = [...root.children].filter((c) => boxed(c) && !c.matches("script, style, noscript, template"));
      if (depth < 3 && kids.length === 1 && !kids[0].matches("section, article, header, footer, aside")) { root = kids[0]; continue; }
      band = [...kids].reverse().find((c) => !c.matches("footer, header, nav, aside, [role=contentinfo], [role=banner], [role=navigation]")) || null;
      break;
    }
    const last_band = band ? { sel: H.selector(band), top: top(band.getBoundingClientRect()), words: words(textOf(band), langOf(band)),
                                headings: [...band.querySelectorAll(HEADING)].filter(boxed).length + (band.matches(HEADING) ? 1 : 0),
                                actions: [...band.querySelectorAll(CONTROLS)].filter(boxed).length } : null;

    return { tell_facts: { viewport: { width: vw, height: vh }, eyebrow, arrows, separators, hero, boxes, tiles, headings, details, last_band, ...(truncated ? { truncated: true } : {}) } };
  }, TELL);
}

const COLLECTORS = [
  async (page) => { await page.evaluate(installHelpers); return {}; },   // first: the helpers the collectors below call
  async (page) => ({ document: await documentFacts(page) }),
  async (page, request) => ({ selectors: await selectorBoxes(page, request.selectors || []) }),
  async (page) => colourFacts(page),
  async (page, request) => roleColours(page, request),
  async (page) => motionFacts(page),
  async (page) => claimFacts(page),
  async (page) => markFacts(page),
  async (page) => fontFacts(page),
  async (page, request) => ruleFacts(page, request),
  async (page) => tellFacts(page),
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
