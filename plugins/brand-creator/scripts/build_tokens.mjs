#!/usr/bin/env node
// build_tokens.mjs: the only producer of colour values for code.
//
//   build_tokens.mjs [--project DIR] [--check] [--fix-hex]
//
// Sources (DTCG 2025.10, a Final Community Group Report, not a W3C Standard) in <project>/tokens/:
//   primitives.tokens.json      colours as {colorSpace, components, alpha, hex}; hex is the 6-digit sRGB fallback;
//                               durations as {value, unit: ms|s}; curves as $type cubicBezier, [x1, y1, x2, y2]
//   semantic.light.tokens.json  aliases ("{color.paper}") or literal colours; same token set as dark
//   semantic.dark.tokens.json
// Pairs for contrast checks live in semantic.light.tokens.json under $extensions["brand-creator"].pairs.
// Targets for the colours that touch in the logo artwork live next to them, under $extensions["brand-creator"].touching
// (passed through to tokens.json; `brand-creator contrast` reads them).
// Outputs in <project>/assets/tokens/: tokens.css, tokens.json, swift/BrandColors.swift,
//   android/values/colors.xml, android/values-night/colors.xml, Colors.xcassets/**/Contents.json; and, only when the sources
//   have a duration or a curve: swift/BrandMotion.swift, android/values/motion.xml (durations), android/interpolator/brand_*.xml (curves)
// Style Dictionary 5.7.0 parses the sources, resolves references and applies the custom transforms below.
// Gates (exit 1): stored hex must equal the gamut-mapped oklch value; light/dark must define the same tokens; a curve is four finite
// numbers with x1 and x2 in [0, 1] and a duration is whole milliseconds, each named by its token path when it is not;
// every emitted artefact is parsed back and must equal the source value (round trip per transform).
// --fix-hex rewrites the sources with the computed hex (explicit opt-in). --check writes nothing and fails when the
// outputs on disk differ from what the sources produce.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import {
  EXIT, die, mainGuard, findProject, confine, rel, Report, writeIfChanged, loadDep, today,
} from "./lib/_common.mjs";

const USAGE = "usage: build_tokens.mjs [--project DIR] [--check] [--fix-hex]";
const SRC = { primitives: "primitives.tokens.json", light: "semantic.light.tokens.json", dark: "semantic.dark.tokens.json" };
const EXT = "brand-creator";
const HEX6 = /^#[0-9a-fA-F]{6}$/;

// ---------------------------------------------------------------- colour maths (culori)
let culori;
export async function init() {
  culori = culori || (await loadDep("culori"));
  return culori;
}

/** DTCG colour object -> { hex (computed, gamut-mapped), alpha, css (modern syntax or null) }. */
export function computeColor(v, where = "colour") {
  if (!v || typeof v !== "object" || !Array.isArray(v.components) || !v.colorSpace) {
    throw new Error(`${where}: not a DTCG colour object {colorSpace, components, alpha, hex}`);
  }
  const [a, b, c] = v.components.map(Number);
  if ([a, b, c].some((n) => Number.isNaN(n))) throw new Error(`${where}: components must be numbers (or none is not supported)`);
  const alpha = v.alpha === undefined ? 1 : Number(v.alpha);
  let rgb, css = null;
  const fmt = (n) => String(+Number(n).toFixed(4));
  const al = alpha < 1 ? ` / ${fmt(alpha)}` : "";
  switch (v.colorSpace) {
    case "oklch":
      rgb = culori.toGamut("rgb", "oklch")({ mode: "oklch", l: a, c: b, h: c });
      css = `oklch(${fmt(a)} ${fmt(b)} ${fmt(c)}${al})`;
      break;
    case "oklab":
      rgb = culori.toGamut("rgb", "oklch")(culori.converter("oklch")({ mode: "oklab", l: a, a: b, b: c }));
      css = `oklab(${fmt(a)} ${fmt(b)} ${fmt(c)}${al})`;
      break;
    case "srgb":
      rgb = { mode: "rgb", r: a, g: b, b: c };
      break;
    case "display-p3":
      rgb = culori.toGamut("rgb", "oklch")(culori.converter("oklch")({ mode: "p3", r: a, g: b, b: c }));
      css = `color(display-p3 ${fmt(a)} ${fmt(b)} ${fmt(c)}${al})`;
      break;
    default:
      throw new Error(`${where}: colorSpace "${v.colorSpace}" is not supported (use oklch, oklab, srgb or display-p3)`);
  }
  const hex = culori.formatHex({ mode: "rgb", r: Math.min(1, Math.max(0, rgb.r)), g: Math.min(1, Math.max(0, rgb.g)), b: Math.min(1, Math.max(0, rgb.b)) });
  return { hex, alpha, css };
}

const byteOf = (hex, i) => parseInt(hex.slice(1 + 2 * i, 3 + 2 * i), 16);
const f4 = (n) => (n / 255).toFixed(4);
const upper = (h) => h.toUpperCase();

// ---------------------------------------------------------------- custom Style Dictionary transforms
function registerTransforms(SD) {
  const isColor = (t) => (t.$type || t.type) === "color";
  // Style Dictionary resolves a reference to the already transformed value of the referenced token and then runs the
  // transitive transforms again, so every transform below is idempotent: only a raw DTCG colour object is converted.
  const isRaw = (v) => v && typeof v === "object" && Array.isArray(v.components);
  const hexOf = (v) => ({ hex: String(v.hex).toLowerCase(), alpha: v.alpha === undefined ? 1 : Number(v.alpha) });
  const reg = (name, fn) => SD.registerTransform({ name, type: "value", transitive: true, filter: isColor, transform: (t) => (isRaw(t.$value) ? fn(t.$value, t) : t.$value) });
  reg("brand/color/css", (v, t) => { const c = hexOf(v); return { hex: c.hex, alpha: c.alpha, css: computeColor(v, t.path.join(".")).css }; });
  reg("brand/color/swift", (v) => { const c = hexOf(v); return { r: f4(byteOf(c.hex, 0)), g: f4(byteOf(c.hex, 1)), b: f4(byteOf(c.hex, 2)), a: Number(c.alpha).toFixed(4) }; });
  reg("brand/color/android", (v) => { const c = hexOf(v); return c.alpha < 1 ? "#" + upper(Math.round(c.alpha * 255).toString(16).padStart(2, "0") + c.hex.slice(1)) : upper(c.hex); });
  reg("brand/color/colorset", (v) => {
    const c = hexOf(v); const h = (i) => "0x" + upper(byteOf(c.hex, i).toString(16).padStart(2, "0"));
    return { red: h(0), green: h(1), blue: h(2), alpha: Number(c.alpha).toFixed(3) };
  });
  reg("brand/color/json", (v) => hexOf(v));
}
const PLATFORMS = {
  css: ["brand/color/css"], json: ["brand/color/json"], swift: ["brand/color/swift"],
  android: ["brand/color/android"], colorset: ["brand/color/colorset"],
};

// ---------------------------------------------------------------- source loading and validation
function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) {
    die(EXIT.FAIL, `${file}: ${e.code === "ENOENT" ? "file not found (expected DTCG tokens, see scripts/CONTRACT.md)" : "invalid JSON: " + e.message}`);
  }
}

function* walkTokens(node, p = [], inheritedType = undefined) {
  if (node === null || typeof node !== "object") return;
  const type = node.$type ?? inheritedType;
  if ("$value" in node) { yield { path: p, node, type }; return; }
  for (const [k, v] of Object.entries(node)) {
    if (k.startsWith("$")) continue;
    yield* walkTokens(v, [...p, k], type);
  }
}

function fixHexInFile(file, issues) {
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  let n = 0;
  for (const { path: p, node, type } of walkTokens(doc)) {
    if (type !== "color" || typeof node.$value !== "object") continue;
    const c = computeColor(node.$value, p.join("."));
    if (!node.$value.hex || node.$value.hex.toLowerCase() !== c.hex) { node.$value.hex = c.hex; n++; }
  }
  if (n) fs.writeFileSync(file, JSON.stringify(doc, null, 2) + "\n");
  issues.push(`${path.basename(file)}: wrote ${n} hex value(s)`);
}

const kebabToCamel = (s) => s.replace(/-([a-z0-9])/g, (_, c) => c.toUpperCase());
// Swift keywords a member may still be named with backticks (swiftc 6: each one checked as a static let and a static func)
const SWIFT_RESERVED = new Set(["associatedtype", "class", "deinit", "enum", "extension", "fileprivate", "func", "import", "init", "inout", "internal", "let",
  "operator", "private", "precedencegroup", "protocol", "public", "rethrows", "static", "struct", "subscript", "typealias", "var", "break", "case", "catch",
  "continue", "default", "defer", "do", "else", "fallthrough", "for", "guard", "if", "in", "repeat", "return", "throw", "switch", "where", "while", "Any", "as",
  "false", "is", "nil", "self", "Self", "super", "throws", "true", "try", "_"]);
// names no member can usefully have: BrandColor.Type and BrandMotion.Duration.Protocol mean the metatype, with or without backticks
const SWIFT_UNUSABLE = new Set(["Type", "Protocol"]);
const swiftId = (name) => { let id = kebabToCamel(name); if (/^[0-9]/.test(id)) id = "c" + id[0].toUpperCase() + id.slice(1); return SWIFT_RESERVED.has(id) ? "`" + id + "`" : id; };
const dropGroup = (p) => (p[0] === "color" ? p.slice(1) : p);

// ---------------------------------------------------------------- motion values: durations and cubic-bezier curves
/** A number as a plain decimal, never 1e-7: CSS, Swift and Android spell a curve the same way, so the round trip compares numbers, not spellings.
 *  The exponent form is expanded digit for digit (String() gives the shortest digits that read back as the same number), never rounded. */
export const plain = (n) => {
  const s = String(n), m = /^(-?)(\d)(?:\.(\d+))?e([+-]\d+)$/.exec(s);
  if (!m) return s;
  const digits = m[2] + (m[3] ?? ""), point = 1 + Number(m[4]);   // where the decimal point goes in `digits`
  if (point <= 0) return `${m[1]}0.${"0".repeat(-point)}${digits}`;
  return m[1] + (point >= digits.length ? digits + "0".repeat(point - digits.length) : `${digits.slice(0, point)}.${digits.slice(point)}`);
};

const INT_MAX = 2147483647;   // an Android <integer> is 32-bit

/** A DTCG duration ({value, unit: "ms" | "s"}, or the older "320ms" string) in whole milliseconds; throws naming `where` for anything else. */
export function durationMs(v, where = "duration") {
  const m = typeof v === "string" ? /^(\d+(?:\.\d+)?)(ms|s)$/.exec(v) : null;
  const { value, unit } = m ? { value: Number(m[1]), unit: m[2] } : (v && typeof v === "object" && !Array.isArray(v) ? v : {});
  if (!Number.isFinite(value) || value < 0 || (unit !== "ms" && unit !== "s")) {   // Number.isFinite is false for anything that is not a finite number, a numeric string too
    throw new Error(`${where}: not a DTCG duration {"value": 320, "unit": "ms"} (a number of 0 or more, unit ms or s), got ${JSON.stringify(v)}`);
  }
  const ms = Math.round(value * (unit === "s" ? 1000 : 1) * 1e6) / 1e6;
  if (!Number.isInteger(ms)) throw new Error(`${where}: ${value}${unit} is not a whole number of milliseconds (Android keeps a duration as an integer of ms)`);
  if (ms > INT_MAX) throw new Error(`${where}: ${value}${unit} is longer than ${INT_MAX} ms, the largest integer Android keeps`);
  return ms;
}

/** A DTCG cubicBezier [x1, y1, x2, y2]: four finite numbers, x1 and x2 within [0, 1] (y is unrestricted, a curve may overshoot); throws naming `where`. */
export function checkCurve(v, where = "cubicBezier") {
  if (!Array.isArray(v) || v.length !== 4 || !v.every((n) => Number.isFinite(n))) {
    throw new Error(`${where}: not a DTCG cubicBezier [x1, y1, x2, y2] (four finite numbers), got ${JSON.stringify(v)}`);
  }
  if (v[0] < 0 || v[0] > 1 || v[2] < 0 || v[2] > 1) throw new Error(`${where}: x1 and x2 must be within 0 and 1, got x1 ${v[0]} and x2 ${v[2]}`);
  return [...v];
}

// ---------------------------------------------------------------- formatters
function fmtOther(t) {
  const v = t.original?.$value ?? t.$value;
  if (typeof v === "string" && /^\{.*\}$/.test(v)) return `var(--${v.slice(1, -1).split(".").join("-")})`;
  const resolved = t.$value;
  switch (t.$type) {
    case "dimension": case "duration":
      return typeof resolved === "object" ? `${resolved.value}${resolved.unit}` : String(resolved);
    case "cubicBezier": return `cubic-bezier(${resolved.map(plain).join(", ")})`;
    case "fontFamily": return (Array.isArray(resolved) ? resolved : [resolved]).map((f) => (/^[a-z-]+$/i.test(f) ? f : JSON.stringify(f))).join(", ");
    case "number": case "fontWeight": return String(resolved);
    default: return typeof resolved === "string" ? resolved : JSON.stringify(resolved);
  }
}

const alphaHex = (a) => Math.round(Number(a) * 255).toString(16).padStart(2, "0");
/** A colour as tokens.css writes it: #rrggbb, or #rrggbbaa when it is see-through (8-digit hex: the alpha survives in every browser). */
function cssHex(c) { return Number(c.alpha) < 1 ? c.hex + alphaHex(c.alpha) : c.hex; }

function formatCss({ prims, light, dark, others }) {
  const o = [];
  o.push("/* Generated by brand-creator build_tokens from tokens/*.tokens.json (DTCG 2025.10 sources). Do not edit. */");
  o.push("/* primitives */", ":root {");
  for (const [k, c] of prims) o.push(`  --${k.split(".").join("-")}: ${cssHex(c)};`);
  for (const [k, v] of others) o.push(`  --${k.split(".").join("-")}: ${v};`);
  o.push("}");
  const modern = prims.filter(([, c]) => c.css);
  if (modern.length) {
    o.push("@supports (color: oklch(0 0 0)) {", "  :root {");
    for (const [k, c] of modern) o.push(`    --${k.split(".").join("-")}: ${c.css};`);
    o.push("  }", "}");
  }
  const decl = (map, ind) => [...map].map(([k, s]) => `${ind}--${k.split(".").join("-")}: ${s.ref ? `var(--${s.ref.split(".").join("-")})` : cssHex(s)};`);
  o.push("/* semantic light */", ":root {", "  color-scheme: light dark;", ...decl(light, "  "), "}");
  o.push(':root[data-theme="light"] {', "  color-scheme: light;", ...decl(light, "  "), "}");
  o.push("/* semantic dark: follows the system unless data-theme pins light */");
  o.push("@media (prefers-color-scheme: dark) {", '  :root:not([data-theme="light"]) {', ...decl(dark, "    "), "  }", "}");
  o.push("/* semantic dark: explicit */", ':root[data-theme="dark"] {', "  color-scheme: dark;", ...decl(dark, "  "), "}");
  return o.join("\n") + "\n";
}

function formatSwift({ prims, light }) {
  const o = ["// Generated by brand-creator build_tokens from tokens/*.tokens.json. Do not edit.", "import SwiftUI", "",
    "public enum BrandPrimitive {"];
  for (const [k, c] of prims) o.push(`    public static let ${swiftId(dropGroup(k.split(".")).join("-"))} = Color(.sRGB, red: ${f4(byteOf(c.hex, 0))}, green: ${f4(byteOf(c.hex, 1))}, blue: ${f4(byteOf(c.hex, 2))}, opacity: ${Number(c.alpha).toFixed(4)})`);
  o.push("}", "", "/// Semantic colours resolve through Colors.xcassets (light and dark variants).", "public enum BrandColor {");
  for (const [k] of light) { const n = dropGroup(k.split(".")).join("-"); o.push(`    public static let ${swiftId(n)} = Color("${n}")`); }
  o.push("}");
  return o.join("\n") + "\n";
}

function androidName(k) { return "brand_" + dropGroup(k.split(".")).join("_").replace(/-/g, "_"); }
function formatAndroid(entries, withPrims) {
  const o = ['<?xml version="1.0" encoding="utf-8"?>', "<!-- Generated by brand-creator build_tokens from tokens/*.tokens.json. Do not edit. -->", "<resources>"];
  for (const [k, v] of entries) o.push(`    <color name="${androidName(k)}">${v}</color>`);
  o.push("</resources>");
  return o.join("\n") + "\n";
}

// A motion token's Swift name is its path without the group (motion.base -> Duration.base, easing.standard -> Curve.standard): a duration and a curve sit in their own namespaces.
const motionName = (k) => { const p = k.split("."); return (p.length > 1 ? p.slice(1) : p).join("-"); };
const motionSwiftId = (k) => swiftId(motionName(k));
const GENERATED = "Generated by brand-creator build_tokens from tokens/*.tokens.json. Do not edit.";

function formatSwiftMotion({ durations, curves }) {
  const o = [`// ${GENERATED}`, "import SwiftUI", "", "/// Durations in seconds and cubic-bezier curves. Nothing here reads Reduce Motion: the app does, and plays none of it when it is on.", "public enum BrandMotion {"];
  if (durations.length) {
    o.push("    public enum Duration {");
    for (const [k, ms] of durations) o.push(`        public static let ${motionSwiftId(k)}: Double = ${plain(ms / 1000)}`);
    o.push("    }");
  }
  if (curves.length) {
    o.push("    public enum Curve {");
    for (const [k, c] of curves) o.push(`        public static func ${motionSwiftId(k)}(duration: Double) -> Animation { Animation.timingCurve(${c.map(plain).join(", ")}, duration: duration) }`);
    o.push("    }");
  }
  o.push("}");
  return o.join("\n") + "\n";
}

function formatAndroidMotion(durations) {
  const o = ['<?xml version="1.0" encoding="utf-8"?>', `<!-- ${GENERATED} -->`, "<resources>"];
  for (const [k, ms] of durations) o.push(`    <integer name="${androidName(k)}">${ms}</integer>`);
  o.push("</resources>");
  return o.join("\n") + "\n";
}

function formatInterpolator(c) {
  const [x1, y1, x2, y2] = c.map(plain);
  return ['<?xml version="1.0" encoding="utf-8"?>', `<!-- ${GENERATED} -->`, '<pathInterpolator xmlns:android="http://schemas.android.com/apk/res/android"',
    `    android:controlX1="${x1}"`, `    android:controlY1="${y1}"`, `    android:controlX2="${x2}"`, `    android:controlY2="${y2}"/>`].join("\n") + "\n";
}

/** Names the motion outputs give the tokens: unique inside each namespace (Swift Duration and Curve, Android integers and interpolators) and valid where written. */
function motionNameProblems(durations, curves) {
  const bad = [], dKeys = durations.map(([k]) => k), cKeys = curves.map(([k]) => k);
  const unique = (where, keys, name) => {
    const seen = new Map();
    for (const k of keys) { const n = name(k); if (seen.has(n)) bad.push(`${where}: ${seen.get(n)} and ${k} both become ${n}`); else seen.set(n, k); }
  };
  unique("BrandMotion.Duration", dKeys, motionSwiftId); unique("BrandMotion.Curve", cKeys, motionSwiftId);
  unique("android integer", dKeys, androidName); unique("android interpolator", cKeys, androidName);
  for (const k of [...dKeys, ...cKeys]) {
    const id = motionSwiftId(k).replace(/`/g, "");
    if (!/^[A-Za-z_]\w*$/.test(id)) bad.push(`${k}: ${motionSwiftId(k)} is not a Swift identifier`);
    else if (SWIFT_UNUSABLE.has(id)) bad.push(`${k}: a Swift member cannot be named ${id} (BrandMotion.Duration.${id} means the type itself; rename the token)`);
  }
  for (const k of dKeys) if (!/^\w+$/.test(androidName(k))) bad.push(`${k}: ${androidName(k)} is not an Android resource name (letters, digits, underscores)`);
  for (const k of cKeys) if (!/^[a-z0-9_]+$/.test(androidName(k))) bad.push(`${k}: ${androidName(k)}.xml is not an Android file resource name (lower case letters, digits and underscores only: rename the token, for example fast-in)`);
  return bad;
}

function colorsetJson(l, d) {
  const mk = (c) => ({ "color-space": "srgb", components: { alpha: c.alpha, blue: c.blue, green: c.green, red: c.red } });
  return JSON.stringify({
    colors: [
      { color: mk(l), idiom: "universal" },
      { appearances: [{ appearance: "luminosity", value: "dark" }], color: mk(d), idiom: "universal" },
    ],
    info: { author: "xcode", version: 1 },
  }, null, 2) + "\n";
}

// ---------------------------------------------------------------- round trip parsers (independent of the formatters)
function parseCssBack(css) {
  const rules = [];
  const rx = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = rx.exec(css))) rules.push({ sel: m[1].replace(/\/\*.*?\*\//gs, "").trim(), body: m[2] });
  const decls = (body) => Object.fromEntries([...body.matchAll(/--([\w-]+):\s*([^;]+);/g)].map((x) => [x[1], x[2].trim()]));
  const roots = rules.filter((r) => r.sel === ":root");
  const modernRule = roots[1] && /oklch|oklab|color\(/.test(roots[1].body) ? roots[1] : null;
  return {
    prims: decls(roots[0]?.body || ""),
    modern: modernRule ? decls(modernRule.body) : {},
    light: decls((rules.find((r) => r.sel === ':root[data-theme="light"]') || {}).body || ""),
    darkMedia: decls((rules.find((r) => r.sel === ':root:not([data-theme="light"])') || {}).body || ""),
    dark: decls((rules.find((r) => r.sel === ':root[data-theme="dark"]') || {}).body || ""),
  };
}

/** The motion outputs read back and compared with the source numbers: CSS, Swift, Android and tokens.json. A value that cannot be read, or is missing, is a problem, never skipped. */
function roundTripMotion({ durations, curves }, files, cssDecls) {
  const problems = [], any = durations.length > 0 || curves.length > 0;
  const N = "(-?\\d+(?:\\.\\d+)?)";
  const cssName = (k) => k.split(".").join("-");
  const near = (a, b) => Math.abs(a - b) < 1e-6;
  const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
  const show = (c) => (c === undefined ? "nothing" : Array.isArray(c) ? c.map(String).join(", ") : String(c));   // raw numbers: a spelling problem must show as two different values
  // CSS: a duration is 320ms or 0.32s, a curve cubic-bezier(x1, y1, x2, y2); an alias is var(--other), followed to its end
  const cssValue = (k) => { let v = cssDecls[cssName(k)]; for (let i = 0; i < 10 && /^var\(/.test(v ?? ""); i++) v = cssDecls[(/^var\(--([\w-]+)\)$/.exec(v) || [])[1]]; return v; };
  for (const [k, ms] of durations) {
    const v = cssValue(k), m = /^(\d+(?:\.\d+)?)(ms|s)$/.exec(v ?? "");
    if (v === undefined) problems.push(`css ${cssName(k)}: missing, expected ${ms}ms`);
    else if (!m) problems.push(`css ${cssName(k)}: cannot read ${v}`);
    else if (!near(Number(m[1]) * (m[2] === "s" ? 1000 : 1), ms)) problems.push(`css ${cssName(k)}: got ${m[1]}${m[2]}, expected ${ms}ms`);
  }
  for (const [k, c] of curves) {
    const v = cssValue(k), m = new RegExp(`^cubic-bezier\\(\\s*${N}\\s*,\\s*${N}\\s*,\\s*${N}\\s*,\\s*${N}\\s*\\)$`).exec(v ?? "");
    if (v === undefined) problems.push(`css ${cssName(k)}: missing, expected cubic-bezier(${show(c)})`);
    else if (!m) problems.push(`css ${cssName(k)}: cannot read ${v}`);
    else if (!same(m.slice(1).map(Number), c)) problems.push(`css ${cssName(k)}: got cubic-bezier(${m.slice(1).join(", ")}), expected cubic-bezier(${show(c)})`);
  }
  // Swift: BrandMotion.Duration (seconds) and BrandMotion.Curve (timingCurve), each namespace read line by line
  const sw = files["swift/BrandMotion.swift"];
  if (sw === undefined) { if (any) problems.push("swift BrandMotion.swift: missing"); }
  else if (!any) problems.push("swift BrandMotion.swift: written, but the tokens have no duration or curve");
  else {
    const readNs = (ns, rx, want, conv, unit) => {
      const body = new RegExp(`public enum ${ns} \\{\\n([\\s\\S]*?)\\n    \\}`).exec(sw), got = new Map();
      if (!body && want.size) problems.push(`swift ${ns}: missing`);
      if (body && !want.size) problems.push(`swift ${ns}: written, but the tokens have none`);
      for (const ln of body ? body[1].split("\n") : []) { const m = rx.exec(ln); if (m) got.set(m[1], conv(m.slice(2).map(Number))); else problems.push(`swift ${ns}: cannot read ${ln.trim()}`); }
      for (const [id, w] of want) { const g = got.get(id); if (!g) problems.push(`swift ${ns}.${id}: not found`); else if (!same(g, w)) problems.push(`swift ${ns}.${id}: got ${show(g)}${unit}, expected ${show(w)}${unit}`); }
      for (const id of got.keys()) if (!want.has(id)) problems.push(`swift ${ns}.${id}: not in the tokens`);
    };
    const id = (k) => motionSwiftId(k).replace(/`/g, "");
    // seconds read back as milliseconds, rounded at a millionth of one so 0.15 s is 150 ms and not 150.00000000000003
    readNs("Duration", new RegExp(`^\\s*public static let \`?(\\w+)\`?: Double = ${N}$`), new Map(durations.map(([k, ms]) => [id(k), [ms]])), (a) => [Math.round(a[0] * 1e9) / 1e6], " ms");
    readNs("Curve", new RegExp(`^\\s*public static func \`?(\\w+)\`?\\(duration: Double\\) -> Animation \\{ Animation\\.timingCurve\\(${N}, ${N}, ${N}, ${N}, duration: duration\\) \\}$`),
      new Map(curves.map(([k, c]) => [id(k), c])), (a) => a, "");
  }
  // Android: <integer> milliseconds in values/motion.xml and one pathInterpolator file per curve
  const mxml = files["android/values/motion.xml"];
  if (mxml === undefined) { if (durations.length) problems.push("android values/motion.xml: missing"); }
  else if (!durations.length) problems.push("android values/motion.xml: written, but the tokens have no duration");
  else {
    const got = new Map();
    for (const m of mxml.matchAll(/<integer\b([^>]*)>([^<]*)<\/integer>/g)) {
      const nm = /^\s*name="([^"]*)"\s*$/.exec(m[1]);
      if (nm && /^\d+$/.test(m[2])) got.set(nm[1], Number(m[2])); else problems.push(`android values/motion.xml: cannot read ${m[0]}`);
    }
    for (const [k, ms] of durations) { const g = got.get(androidName(k)); if (g === undefined) problems.push(`android ${androidName(k)}: not found`); else if (g !== ms) problems.push(`android ${androidName(k)}: got ${g} ms, expected ${ms} ms`); }
    for (const nm of got.keys()) if (!durations.some(([k]) => androidName(k) === nm)) problems.push(`android ${nm}: not in the tokens`);
  }
  const want = new Set(curves.map(([k]) => `android/interpolator/${androidName(k)}.xml`));
  for (const [k, c] of curves) {
    const f = `android/interpolator/${androidName(k)}.xml`, xml = files[f];
    if (xml === undefined) { problems.push(`android ${f}: missing`); continue; }
    const got = ["controlX1", "controlY1", "controlX2", "controlY2"].map((a) => { const m = new RegExp(`android:${a}="${N}"`).exec(xml); return m ? Number(m[1]) : null; });
    if (!/<pathInterpolator\b/.test(xml) || got.includes(null)) problems.push(`android ${f}: cannot read the pathInterpolator and its four controls`);
    else if (!same(got, c)) problems.push(`android ${f}: got ${show(got)}, expected ${show(c)}`);
  }
  for (const f of Object.keys(files)) if (f.startsWith("android/interpolator/") && !want.has(f)) problems.push(`android ${f}: not in the tokens`);
  // tokens.json: the numbers under `motion`, and the strings under `other` the same as tokens.css writes them
  const tj = JSON.parse(files["tokens.json"]), mo = tj.motion;
  if (mo !== undefined && !any) problems.push("json motion: written, but the tokens have no duration or curve");
  for (const [k, ms] of durations) {
    if (mo?.durations_ms?.[k] !== ms) problems.push(`json motion duration ${k}: got ${show(mo?.durations_ms?.[k])}, expected ${ms}`);
    if (tj.other?.[k] !== cssDecls[cssName(k)]) problems.push(`json other ${k}: got ${show(tj.other?.[k])}, expected ${cssDecls[cssName(k)]}`);
  }
  for (const [k, c] of curves) {
    if (JSON.stringify(mo?.curves?.[k]) !== JSON.stringify(c)) problems.push(`json motion curve ${k}: got ${show(mo?.curves?.[k])}, expected ${show(c)}`);
    if (tj.other?.[k] !== cssDecls[cssName(k)]) problems.push(`json other ${k}: got ${show(tj.other?.[k])}, expected ${cssDecls[cssName(k)]}`);
  }
  for (const k of Object.keys(mo?.durations_ms ?? {})) if (!durations.some(([d]) => d === k)) problems.push(`json motion duration ${k}: not in the tokens`);
  for (const k of Object.keys(mo?.curves ?? {})) if (!curves.some(([c]) => c === k)) problems.push(`json motion curve ${k}: not in the tokens`);
  return problems;
}

export function roundTrip({ prims, light, dark, durations = [], curves = [] }, files) {
  const problems = [];
  // every colour is compared with its alpha: a see-through token that comes back opaque is a different colour
  const expectPrim = Object.fromEntries(prims.map(([k, c]) => [k.split(".").join("-"), cssHex(c)]));
  const resolveSem = (map) => Object.fromEntries([...map].map(([k, s]) => [k.split(".").join("-"), cssHex(s)]));
  const eq = (what, got, want) => { if (String(got).toLowerCase() !== String(want).toLowerCase()) problems.push(`${what}: got ${got}, expected ${want}`); };
  const a4 = (a) => Number(a ?? 1).toFixed(4);
  // CSS
  const css = parseCssBack(files["tokens.css"]);
  const cssResolve = (v) => { const m = /^var\(--([\w-]+)\)$/.exec(v); return m ? css.prims[m[1]] : v; };
  for (const [k, want] of Object.entries(expectPrim)) eq(`css ${k}`, css.prims[k], want);
  // the @supports block: every modern value (oklch, oklab, display-p3) parses back to the colour and its alpha; one that cannot be read
  // is a problem, never skipped, and so is a primitive with a modern form (c.css, known in the build) that has no line there
  const n = "(-?[\\d.]+)";
  const MODERN = [["oklch", new RegExp(`^oklch\\(${n} ${n} ${n}(?: \\/ ([\\d.]+))?\\)$`)], ["oklab", new RegExp(`^oklab\\(${n} ${n} ${n}(?: \\/ ([\\d.]+))?\\)$`)],
    ["display-p3", new RegExp(`^color\\(display-p3 ${n} ${n} ${n}(?: \\/ ([\\d.]+))?\\)$`)]];
  for (const [k, c] of prims.map(([k, c]) => [k.split(".").join("-"), c])) {
    const mv = css.modern[k];
    if (!mv) {
      if (c.css) problems.push(`css @supports ${k}: missing, expected ${c.css}`);
      continue;
    }
    const hit = MODERN.map(([space, rx]) => [space, rx.exec(mv)]).find(([, m]) => m);
    if (!hit) { problems.push(`css @supports ${k}: cannot read ${mv}`); continue; }
    const [space, m] = hit;
    eq(`css @supports ${k}`, computeColor({ colorSpace: space, components: [m[1], m[2], m[3]], alpha: 1 }).hex, c.hex);
    eq(`css @supports ${k} alpha`, a4(m[4]), a4(c.alpha));
  }
  for (const [name, want] of Object.entries(resolveSem(light))) { eq(`css light ${name}`, cssResolve(css.light[name]), want); }
  for (const [name, want] of Object.entries(resolveSem(dark))) {
    eq(`css dark ${name}`, cssResolve(css.dark[name]), want);
    eq(`css dark (media) ${name}`, cssResolve(css.darkMedia[name]), want);
  }
  // Swift (primitives as floats)
  const sw = files["swift/BrandColors.swift"];
  for (const [k, c] of prims) {
    const id = swiftId(dropGroup(k.split(".")).join("-")).replace(/`/g, "");
    const m = new RegExp(`static let \`?${id}\`? = Color\\(\\.sRGB, red: ([\\d.]+), green: ([\\d.]+), blue: ([\\d.]+), opacity: ([\\d.]+)\\)`).exec(sw);
    if (!m) { problems.push(`swift ${id}: not found`); continue; }
    eq(`swift ${id}`, "#" + [1, 2, 3].map((i) => Math.round(Number(m[i]) * 255).toString(16).padStart(2, "0")).join(""), c.hex);
    eq(`swift ${id} opacity`, a4(m[4]), a4(c.alpha));
  }
  // Android
  // #AARRGGBB (or #RRGGBB, opaque) read back as #rrggbbaa / #rrggbb, the CSS form, so the alpha is compared too
  const andr = (txt) => Object.fromEntries([...txt.matchAll(/<color name="([\w]+)">#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})<\/color>/g)]
    .map((x) => [x[1], x[2].length === 8 && x[2].slice(0, 2).toLowerCase() !== "ff" ? "#" + x[2].slice(2) + x[2].slice(0, 2) : "#" + x[2].slice(-6)]));
  const aL = andr(files["android/values/colors.xml"]), aD = andr(files["android/values-night/colors.xml"]);
  for (const [k, c] of prims) eq(`android ${androidName(k)}`, aL[androidName(k)], cssHex(c));
  for (const [k, s] of light) eq(`android light ${androidName(k)}`, aL[androidName(k)], cssHex(s));
  for (const [k, s] of dark) eq(`android dark ${androidName(k)}`, aD[androidName(k)], cssHex(s));
  // colorsets
  for (const [k, s] of light) {
    const n = dropGroup(k.split(".")).join("-");
    const doc = JSON.parse(files[`Colors.xcassets/${n}.colorset/Contents.json`]);
    const hx = (c) => "#" + ["red", "green", "blue"].map((ch) => parseInt(c.components[ch], 16).toString(16).padStart(2, "0")).join("");
    eq(`colorset ${n} light`, hx(doc.colors[0].color), s.hex);
    eq(`colorset ${n} dark`, hx(doc.colors[1].color), dark.get(k).hex);
    const a3 = (a) => Number(a ?? 1).toFixed(3);    // the colorset writes three decimals
    eq(`colorset ${n} light alpha`, a3(doc.colors[0].color.components.alpha), a3(s.alpha));
    eq(`colorset ${n} dark alpha`, a3(doc.colors[1].color.components.alpha), a3(dark.get(k).alpha));
  }
  // tokens.json
  const tj = JSON.parse(files["tokens.json"]);
  for (const [k, c] of prims) eq(`json primitive ${k}`, cssHex(tj.primitives[k] ?? {}), cssHex(c));
  for (const [k, s] of light) eq(`json light ${k}`, cssHex(tj.modes.light[k] ?? {}), cssHex(s));
  for (const [k, s] of dark) eq(`json dark ${k}`, cssHex(tj.modes.dark[k] ?? {}), cssHex(s));
  problems.push(...roundTripMotion({ durations, curves }, files, css.prims));
  return problems;
}

// ---------------------------------------------------------------- main build
async function build(project, { fixHex }) {
  await init();
  const dir = path.join(project, "tokens");
  const files = Object.fromEntries(Object.entries(SRC).map(([k, f]) => [k, path.join(dir, f)]));
  for (const f of Object.values(files)) if (!fs.existsSync(f)) die(EXIT.FAIL, `${rel(project, f)} not found; the token sources are tokens/{primitives,semantic.light,semantic.dark}.tokens.json`);
  const report = new Report("tokens", project, Object.values(files));
  const notes = [];
  if (fixHex) { for (const f of Object.values(files)) fixHexInFile(f, notes); for (const n of notes) console.log(n); }

  const docs = { primitives: readJson(files.primitives), light: readJson(files.light), dark: readJson(files.dark) };

  // 1. stored hex == gamut-mapped oklch
  const hexIssues = [];
  let nColors = 0;
  for (const { path: p, node, type } of walkTokens(docs.primitives)) {
    if (type !== "color") continue;
    if (typeof node.$value !== "object") { hexIssues.push(`${p.join(".")}: primitives must hold literal colour objects, not references`); continue; }
    nColors++;
    let c;
    try { c = computeColor(node.$value, p.join(".")); } catch (e) { hexIssues.push(e.message); continue; }
    const stored = node.$value.hex;
    if (!stored || !HEX6.test(stored)) hexIssues.push(`${p.join(".")}: hex is missing or not #rrggbb (run: brand-creator tokens --fix-hex)`);
    else if (stored.toLowerCase() !== c.hex) hexIssues.push(`${p.join(".")}: stored hex ${stored} != gamut-mapped ${node.$value.colorSpace} value ${c.hex} (run: brand-creator tokens --fix-hex)`);
  }
  report.add("hex-equals-oklch", hexIssues.length ? "fail" : "pass", "stored hex == gamut-mapped oklch", {
    detail: hexIssues.length ? hexIssues.join("; ") : `${nColors} primitive colour(s) match`, issues: hexIssues });
  const semIssues = [];
  for (const mode of ["light", "dark"]) {
    for (const { path: p, type } of walkTokens(docs[mode])) {
      if (type !== "color") semIssues.push(`${mode}: ${p.join(".")} is not a colour (semantic files carry colours only in this version)`);
    }
  }
  if (semIssues.length) report.add("semantic-colours-only", "fail", "semantic files", { detail: semIssues.join("; ") });
  if (hexIssues.length || semIssues.length) return { report, outputs: null };

  // 2. Style Dictionary per mode
  const SD = (await loadDep("style-dictionary")).default;
  registerTransforms(SD);
  const run = async (semFile) => {
    const sd = new SD({
      source: [files.primitives, semFile], usesDtcg: true,
      log: { verbosity: "silent", warnings: "disabled", errors: { brokenReferences: "throw" } },
      platforms: Object.fromEntries(Object.entries(PLATFORMS).map(([n, tr]) => [n, { transforms: tr, buildPath: "/dev/null/" }])),
    });
    await sd.hasInitialized;
    const out = {};
    for (const n of Object.keys(PLATFORMS)) out[n] = (await sd.getPlatformTokens(n)).allTokens;
    return out;
  };
  let sdLight, sdDark;
  try { sdLight = await run(files.light); sdDark = await run(files.dark); } catch (e) {
    report.add("style-dictionary", "fail", "parse and resolve", { detail: String(e.message).split("\n").slice(0, 3).join(" ") });
    return { report, outputs: null };
  }
  report.add("style-dictionary", "pass", "Style Dictionary 5.7.0 parsed and resolved both modes");

  const isSem = (t, semFile) => path.resolve(t.filePath) === path.resolve(semFile);
  const key = (t) => t.path.join(".");
  // motion tokens are checked before anything is formatted: a bad duration or curve fails here, named by its token path
  const durations = [], curves = [], motionBad = [];
  for (const t of sdLight.css) {
    if (isSem(t, files.light)) continue;
    try {
      if (t.$type === "duration") durations.push([key(t), durationMs(t.$value, key(t))]);
      else if (t.$type === "cubicBezier") curves.push([key(t), checkCurve(t.$value, key(t))]);
    } catch (e) { motionBad.push(e.message); }
  }
  if (motionBad.length) {
    report.add("motion-tokens", "fail", "durations and curves are valid", { detail: motionBad.join("; ") });
    return { report, outputs: null };
  }
  for (const list of [durations, curves]) list.sort((a, b) => (a[0] < b[0] ? -1 : 1));
  if (durations.length || curves.length) report.add("motion-tokens", "pass", "durations and curves are valid", { detail: `${durations.length} duration(s) in whole milliseconds, ${curves.length} curve(s) with x1 and x2 within 0 and 1` });
  const prims = [], others = [], light = new Map(), dark = new Map();
  for (const t of sdLight.css) {
    if (isSem(t, files.light)) {
      if (t.$type !== "color") continue;
      const ov = t.original?.$value;
      light.set(key(t), { ...t.$value, ref: typeof ov === "string" && /^\{.*\}$/.test(ov) ? ov.slice(1, -1) : null });
    } else if (t.$type === "color") prims.push([key(t), t.$value]);
    else others.push([key(t), fmtOther(t)]);
  }
  for (const t of sdDark.css) {
    if (isSem(t, files.dark) && t.$type === "color") {
      const ov = t.original?.$value;
      dark.set(key(t), { ...t.$value, ref: typeof ov === "string" && /^\{.*\}$/.test(ov) ? ov.slice(1, -1) : null });
    }
  }
  prims.sort((a, b) => (a[0] < b[0] ? -1 : 1)); others.sort((a, b) => (a[0] < b[0] ? -1 : 1));
  const sortMap = (m) => new Map([...m].sort((a, b) => (a[0] < b[0] ? -1 : 1)));
  const L = sortMap(light), D = sortMap(dark);
  const missing = [...L.keys()].filter((k) => !D.has(k)).map((k) => `${k} missing in dark`).concat([...D.keys()].filter((k) => !L.has(k)).map((k) => `${k} missing in light`));
  report.add("modes-parity", missing.length ? "fail" : "pass", "light and dark define the same tokens", { detail: missing.length ? missing.join("; ") : `${L.size} semantic token(s) in both modes` });
  const collide = [...L.keys()].filter((k) => prims.some(([p]) => androidName(p) === androidName(k)));
  if (collide.length) report.add("name-collision", "fail", "semantic and primitive names collide in Android/Swift", { detail: collide.join(", ") });
  const unusable = [...prims.map(([k]) => k), ...L.keys()].filter((k) => SWIFT_UNUSABLE.has(swiftId(dropGroup(k.split(".")).join("-"))));
  if (unusable.length) report.add("swift-names", "fail", "colour names a Swift member can have", { detail: `${unusable.join(", ")}: a Swift member cannot be named Type or Protocol (it means the type itself); rename the token` });
  const motionNames = motionNameProblems(durations, curves);
  if (motionNames.length) report.add("motion-names", "fail", "motion token names are unique and valid in Swift and Android", { detail: motionNames.join("; ") });
  if (missing.length || collide.length || unusable.length || motionNames.length) return { report, outputs: null };

  // 3. APCA advisory (colorjs.io) and pair table
  const pairsDef = (docs.light.$extensions?.[EXT]?.pairs) || [];
  const Color = (await loadDep("colorjs.io")).default;
  const pairs = [];
  const bad = [];
  for (const pr of pairsDef) {
    const entry = { fg: pr.fg, bg: pr.bg, kind: pr.kind, min: pr.min ?? null, label: pr.label ?? null, modes: {} };
    for (const [mode, map] of [["light", L], ["dark", D]]) {
      const f = map.get(pr.fg), b = map.get(pr.bg);
      if (!f || !b) { bad.push(`pair ${pr.fg}/${pr.bg}: unknown token in ${mode}`); continue; }
      const lc = Color.contrast(new Color(b.hex), new Color(f.hex), "APCA");
      entry.modes[mode] = { fg_hex: f.hex, bg_hex: b.hex, apca_lc: Math.round(lc * 10) / 10 };
    }
    pairs.push(entry);
  }
  // role-separation pairs ($extensions["brand-creator"].distinct): roles that must stay distinguishable, checked by `contrast --cvd`
  const distinct = [];
  for (const d of (docs.light.$extensions?.[EXT]?.distinct) || []) {
    const entry = { a: d.a, b: d.b, label: d.label ?? null, modes: {} };
    for (const [mode, map] of [["light", L], ["dark", D]]) {
      const x = map.get(d.a), y = map.get(d.b);
      if (!x || !y) { bad.push(`distinct ${d.a}/${d.b}: unknown token in ${mode}`); continue; }
      entry.modes[mode] = { a_hex: x.hex, b_hex: y.hex };
    }
    distinct.push(entry);
  }
  report.add("pairs", bad.length ? "fail" : "pass", "contrast pairs resolve", { detail: bad.length ? bad.join("; ") : `${pairs.length} pair(s), APCA Lc computed with colorjs.io (advisory only)` });
  if (bad.length) return { report, outputs: null };

  // 4. emit
  const out = {};
  out["tokens.css"] = formatCss({ prims, light: L, dark: D, others });
  out["tokens.json"] = JSON.stringify({
    $generator: "brand-creator build_tokens",
    $format: "DTCG 2025.10 sources (a Final Community Group Report, not a W3C Standard); resolved values",
    primitives: Object.fromEntries(prims.map(([k, c]) => [k, { hex: c.hex, alpha: c.alpha }])),
    other: Object.fromEntries(others),
    ...(durations.length || curves.length ? { motion: { durations_ms: Object.fromEntries(durations), curves: Object.fromEntries(curves) } } : {}),
    modes: {
      light: Object.fromEntries([...L].map(([k, s]) => [k, { hex: s.hex, alpha: s.alpha, ref: s.ref }])),
      dark: Object.fromEntries([...D].map(([k, s]) => [k, { hex: s.hex, alpha: s.alpha, ref: s.ref }])),
    },
    pairs,
    touching: docs.light.$extensions?.[EXT]?.touching ?? null,
    ...(distinct.length ? { distinct } : {}),
  }, null, 2) + "\n";
  out["swift/BrandColors.swift"] = formatSwift({ prims, light: L });
  if (durations.length || curves.length) out["swift/BrandMotion.swift"] = formatSwiftMotion({ durations, curves });
  const A = (list) => list.map(([k, c]) => [k, c]);
  const androidVal = (k, mode) => { const t = (mode === "dark" ? sdDark : sdLight).android.find((x) => key(x) === k); return t.$value; };
  const aPrim = prims.map(([k]) => [k, androidVal(k, "light")]);
  out["android/values/colors.xml"] = formatAndroid([...aPrim, ...[...L.keys()].map((k) => [k, androidVal(k, "light")])]);
  out["android/values-night/colors.xml"] = formatAndroid([...D.keys()].map((k) => [k, androidVal(k, "dark")]));
  if (durations.length) out["android/values/motion.xml"] = formatAndroidMotion(durations);
  for (const [k, c] of curves) out[`android/interpolator/${androidName(k)}.xml`] = formatInterpolator(c);
  out["Colors.xcassets/Contents.json"] = JSON.stringify({ info: { author: "xcode", version: 1 } }, null, 2) + "\n";
  const cs = (mode, k) => (mode === "dark" ? sdDark : sdLight).colorset.find((x) => key(x) === k).$value;
  for (const k of L.keys()) out[`Colors.xcassets/${dropGroup(k.split(".")).join("-")}.colorset/Contents.json`] = colorsetJson(cs("light", k), cs("dark", k));

  // 5. round trip
  const rt = roundTrip({ prims: prims.map(([k, c]) => [k, c]), light: L, dark: D, durations, curves }, out);
  const motionNote = durations.length || curves.length ? `; ${durations.length} duration(s), ${curves.length} curve(s)` : "";
  report.add("round-trip", rt.length ? "fail" : "pass", "every emitted artefact parsed back equals the source (colours with their alpha, durations, curves)",
    { detail: rt.length ? rt.slice(0, 6).join("; ") : `css, swift, android, colorset, json: ${prims.length} primitive(s), ${L.size} semantic token(s) x 2 modes${motionNote}`, problems: rt });
  void A;
  return { report, outputs: out };
}

/** Files the build owns under assets/tokens that the sources no longer produce: the colorset of a removed colour role (its whole folder), the motion
 *  files once the last duration or curve is gone, the interpolator of a removed or renamed curve. Paths relative to assets/tokens, sorted. */
export function orphans(base, outputs) {
  const found = [];
  const names = (d) => { try { return fs.readdirSync(path.join(base, d)); } catch { return []; } };
  for (const f of ["swift/BrandMotion.swift", "android/values/motion.xml"]) if (fs.existsSync(path.join(base, f)) && !(f in outputs)) found.push(f);
  for (const n of names("android/interpolator")) if (/^brand_.*\.xml$/.test(n) && !(`android/interpolator/${n}` in outputs)) found.push(`android/interpolator/${n}`);
  for (const n of names("Colors.xcassets")) if (n.endsWith(".colorset") && !(`Colors.xcassets/${n}/Contents.json` in outputs)) found.push(`Colors.xcassets/${n}`);
  return found.sort();
}

/** Move each orphan to removed-<date>/assets/tokens/<path> in the project (never deleted; -2, -3 when that folder already holds it). */
function retireOrphans(project, base, list) {
  const moved = [];
  for (const r of list) {
    const src = confine(project, path.join(base, r), "retired token file");
    let n = 1, dest = confine(project, `removed-${today()}/assets/tokens/${r}`, "removed folder");
    while (fs.existsSync(dest)) { n++; dest = confine(project, `removed-${today()}-${n}/assets/tokens/${r}`, "removed folder"); }
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.renameSync(src, dest);
    moved.push(`${r} -> ${rel(project, dest)}`);
  }
  return moved;
}

async function main() {
  let values;
  try { ({ values } = parseArgs({ args: process.argv.slice(2), options: { project: { type: "string" }, check: { type: "boolean", default: false }, "fix-hex": { type: "boolean", default: false }, help: { type: "boolean", short: "h", default: false } }, strict: true })); }
  catch (e) { die(EXIT.USAGE, `${e.message}\n${USAGE}`); }
  if (values.help) { console.log(USAGE); return EXIT.PASS; }
  const project = findProject(values.project);
  const { report, outputs } = await build(project, { fixHex: values["fix-hex"] });
  if (outputs) {
    const base = confine(project, "assets/tokens", "output folder");
    const stale = [];
    let written = 0;
    for (const [relp, text] of Object.entries(outputs)) {
      const f = path.join(base, relp);
      if (values.check) { if (!fs.existsSync(f) || fs.readFileSync(f, "utf8") !== text) stale.push(relp); } else if (writeIfChanged(f, text)) written++;
    }
    const left = orphans(base, outputs);
    if (values.check) {
      const problems = [...(stale.length ? [`stale or missing: ${stale.join(", ")}`] : []), ...(left.length ? [`no longer produced by the sources: ${left.join(", ")}`] : [])];
      report.add("outputs-current", problems.length ? "fail" : "pass", "assets/tokens matches the sources",
        { detail: problems.length ? `${problems.join("; ")} (run: brand-creator tokens${left.length ? `, which moves what is no longer produced to removed-${today()}/` : ""})` : `${Object.keys(outputs).length} file(s) current` });
    } else {
      report.add("written", "info", "assets/tokens", { detail: `${written} file(s) written, ${Object.keys(outputs).length - written} unchanged` });
      if (left.length) report.add("retired", "warn", "files the sources no longer produce", { detail: `moved, never deleted: ${retireOrphans(project, base, left).join("; ")}` });
    }
  }
  return report.finish();
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await mainGuard(main);
