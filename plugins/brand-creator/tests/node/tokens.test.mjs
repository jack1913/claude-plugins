import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { ROOT, DATA, needSetup, bc, makeProject, mutateText } from "./_helpers.mjs";

let B;
async function lib(t) {
  if (needSetup(t)) return null;
  process.env.BRAND_CREATOR_DATA = DATA;
  B ||= await import(path.join(ROOT, "scripts/build_tokens.mjs"));
  await B.init();
  return B;
}

/** The durations and curves of the round-trip model, read back from a built tokens.json: [path, ms] and [path, [x1, y1, x2, y2]]. */
const motionOf = (tj) => ({ durations: Object.entries(tj.motion?.durations_ms ?? {}), curves: Object.entries(tj.motion?.curves ?? {}) });

test("computeColor: known conversions", async (t) => {
  const b = await lib(t); if (!b) return;
  assert.equal(b.computeColor({ colorSpace: "oklch", components: [1, 0, 0] }).hex, "#ffffff");
  assert.equal(b.computeColor({ colorSpace: "oklch", components: [0, 0, 0] }).hex, "#000000");
  assert.equal(b.computeColor({ colorSpace: "srgb", components: [1, 0, 0] }).hex, "#ff0000");
  assert.equal(b.computeColor({ colorSpace: "srgb", components: [0.2, 0.4, 0.6], alpha: 0.5 }).alpha, 0.5);
  assert.equal(b.computeColor({ colorSpace: "oklch", components: [0.975, 0.012, 95] }).css, "oklch(0.975 0.012 95)");
  assert.equal(b.computeColor({ colorSpace: "oklch", components: [0.5, 0.1, 30, ], alpha: 0.5 }).css, "oklch(0.5 0.1 30 / 0.5)");
});

test("computeColor: out-of-gamut oklch is gamut-mapped into a valid hex, not clipped channel by channel", async (t) => {
  const b = await lib(t); if (!b) return;
  const wild = b.computeColor({ colorSpace: "oklch", components: [0.7, 0.4, 150] }).hex;
  assert.match(wild, /^#[0-9a-f]{6}$/);
  const clipped = b.computeColor({ colorSpace: "srgb", components: [0, 1, 0] }).hex; // naive clip of a neon green
  assert.notEqual(wild, clipped);
});

test("computeColor: rejects what it cannot convert", async (t) => {
  const b = await lib(t); if (!b) return;
  assert.throws(() => b.computeColor({ colorSpace: "cmyk", components: [0, 0, 0] }), /not supported/);
  assert.throws(() => b.computeColor("#fff"), /not a DTCG colour object/);
  assert.throws(() => b.computeColor({ colorSpace: "oklch", components: ["x", 0, 0] }), /numbers/);
});

test("build: every output is written and the round trip passes; mutating a source hex fails the gate", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  let r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  for (const f of ["tokens.css", "tokens.json", "swift/BrandColors.swift", "android/values/colors.xml", "android/values-night/colors.xml", "Colors.xcassets/Contents.json"]) {
    assert.ok(fs.existsSync(path.join(p, "assets/tokens", f)), f);
  }
  const rep = JSON.parse(fs.readFileSync(path.join(p, "assets/_checks/tokens.json"), "utf8"));
  assert.equal(rep.status, "pass");
  assert.ok(rep.results.find((x) => x.id === "round-trip" && x.status === "pass"));
  const src = path.join(p, "tokens/primitives.tokens.json");
  const hex = JSON.parse(fs.readFileSync(src, "utf8")).color.paper.$value.hex;
  mutateText(src, `"hex": "${hex}"`, '"hex": "#010203"');
  r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 1);
  assert.match(r.stdout, /stored hex #010203 != gamut-mapped/);
});

test("build: a see-through colour keeps its alpha in every output, and the round trip compares the alpha", async (t) => {
  if (needSetup(t)) return;
  const b = await lib(t); if (!b) return;
  const p = makeProject();
  const edit = (f, fn) => { const file = path.join(p, "tokens", f); const d = JSON.parse(fs.readFileSync(file, "utf8")); fn(d); fs.writeFileSync(file, JSON.stringify(d, null, 2) + "\n"); };
  // a scrim at 56%: #3a2448 with alpha 0.56, alpha byte 0x8f (143 / 255)
  edit("primitives.tokens.json", (d) => { d.color.plum = { $value: { colorSpace: "srgb", components: [58 / 255, 36 / 255, 72 / 255], alpha: 0.56, hex: "#3a2448" } }; });
  for (const f of ["semantic.light.tokens.json", "semantic.dark.tokens.json"]) edit(f, (d) => { d.color.scrim = { $value: "{color.plum}" }; });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = (f) => fs.readFileSync(path.join(p, "assets/tokens", f), "utf8");
  assert.match(out("tokens.css"), /--color-plum: #3a24488f;/);
  assert.match(out("tokens.css"), /--color-scrim: var\(--color-plum\);/);
  assert.match(out("android/values/colors.xml"), /<color name="brand_plum">#8F3A2448<\/color>/);
  assert.match(out("android/values/colors.xml"), /<color name="brand_scrim">#8F3A2448<\/color>/);
  assert.match(out("swift/BrandColors.swift"), /plum = Color\(\.sRGB, red: [\d.]+, green: [\d.]+, blue: [\d.]+, opacity: 0\.5600\)/);
  assert.deepEqual(JSON.parse(out("tokens.json")).primitives["color.plum"], { hex: "#3a2448", alpha: 0.56 });
  const rep = JSON.parse(fs.readFileSync(path.join(p, "assets/_checks/tokens.json"), "utf8"));
  assert.ok(rep.results.find((x) => x.id === "round-trip" && x.status === "pass"));
  // the round trip itself: a tokens.css that drops the alpha is caught, and so is an Android file that does
  const files = {};
  for (const f of ["tokens.css", "tokens.json", "swift/BrandColors.swift", "swift/BrandMotion.swift", "android/values/colors.xml", "android/values-night/colors.xml", "android/values/motion.xml"]) files[f] = out(f);
  for (const d of fs.readdirSync(path.join(p, "assets/tokens/Colors.xcassets")).filter((d) => d.endsWith(".colorset"))) files[`Colors.xcassets/${d}/Contents.json`] = out(`Colors.xcassets/${d}/Contents.json`);
  const tj = JSON.parse(files["tokens.json"]);
  const prims = Object.entries(tj.primitives);
  const mode = (m) => new Map(Object.entries(tj.modes[m]));
  const model = { prims, light: mode("light"), dark: mode("dark"), ...motionOf(tj) };
  assert.deepEqual(b.roundTrip(model, files), []);
  assert.match(b.roundTrip(model, { ...files, "tokens.css": files["tokens.css"].replace("#3a24488f", "#3a2448") }).join(";"), /css color-plum: got #3a2448, expected #3a24488f/);
  assert.match(b.roundTrip(model, { ...files, "android/values/colors.xml": files["android/values/colors.xml"].replaceAll("#8F3A2448", "#3A2448") }).join(";"), /android brand_plum: got #3a2448, expected #3a24488f/i);
});

test("build: the round trip reads every modern form back (oklch, oklab, display-p3) with its alpha, and a lost alpha is caught in every output", async (t) => {
  if (needSetup(t)) return;
  const b = await lib(t); if (!b) return;
  const p = makeProject();
  const edit = (f, fn) => { const file = path.join(p, "tokens", f); const d = JSON.parse(fs.readFileSync(file, "utf8")); fn(d); fs.writeFileSync(file, JSON.stringify(d, null, 2) + "\n"); };
  const src = {
    veil: { colorSpace: "oklch", components: [0.32, 0.09, 305], alpha: 0.4 },
    haze: { colorSpace: "oklab", components: [0.62, -0.06, 0.035], alpha: 0.7 },   // a negative component: the reader takes the sign
    glass: { colorSpace: "display-p3", components: [0.21, 0.52, 0.43], alpha: 0.3 },
  };
  edit("primitives.tokens.json", (d) => { for (const [k, v] of Object.entries(src)) d.color[k] = { $value: { ...v, hex: b.computeColor(v).hex } }; });
  for (const f of ["semantic.light.tokens.json", "semantic.dark.tokens.json"]) edit(f, (d) => { d.color.scrim = { $value: "{color.veil}" }; });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = (f) => fs.readFileSync(path.join(p, "assets/tokens", f), "utf8");
  assert.match(out("tokens.css"), /--color-veil: oklch\(0\.32 0\.09 305 \/ 0\.4\);/);
  assert.match(out("tokens.css"), /--color-haze: oklab\(0\.62 -0\.06 0\.035 \/ 0\.7\);/);
  assert.match(out("tokens.css"), /--color-glass: color\(display-p3 0\.21 0\.52 0\.43 \/ 0\.3\);/);
  const files = {};
  for (const f of ["tokens.css", "tokens.json", "swift/BrandColors.swift", "swift/BrandMotion.swift", "android/values/colors.xml", "android/values-night/colors.xml", "android/values/motion.xml"]) files[f] = out(f);
  for (const d of fs.readdirSync(path.join(p, "assets/tokens/Colors.xcassets")).filter((d) => d.endsWith(".colorset"))) files[`Colors.xcassets/${d}/Contents.json`] = out(`Colors.xcassets/${d}/Contents.json`);
  const tj = JSON.parse(files["tokens.json"]);
  // the model as the build passes it: each primitive knows its modern form, so a missing @supports line is caught too
  const prims = Object.entries(tj.primitives).map(([k, c]) => [k, { ...c, css: src[k.split(".").pop()] ? b.computeColor(src[k.split(".").pop()]).css : null }]);
  const mode = (m) => new Map(Object.entries(tj.modes[m]));
  const model = { prims, light: mode("light"), dark: mode("dark"), ...motionOf(tj) };
  assert.deepEqual(b.roundTrip(model, files), []);
  const broken = (f, fn) => b.roundTrip(model, { ...files, [f]: fn(files[f]) }).join(";");
  assert.match(broken("tokens.css", (s) => s.replace("305 / 0.4)", "305 / 0.5)")), /css @supports color-veil alpha: got 0\.5000, expected 0\.4000/);
  assert.match(broken("tokens.css", (s) => s.replace("0.035 / 0.7)", "0.035)")), /css @supports color-haze alpha: got 1\.0000, expected 0\.7000/);
  assert.match(broken("tokens.css", (s) => s.replace("0.43 / 0.3)", "0.43 / 0.9)")), /css @supports color-glass alpha: got 0\.9000, expected 0\.3000/);
  assert.match(broken("tokens.css", (s) => s.replace(/--color-glass: color\(display-p3 [^;]+;/, "--color-glass: color(rec2020 0.2 0.5 0.4);")), /css @supports color-glass: cannot read/);
  assert.match(broken("tokens.css", (s) => s.replace(/\n\s+--color-veil: oklch\([^;]+;/, "")), /css @supports color-veil: missing, expected oklch/);
  assert.match(broken("swift/BrandColors.swift", (s) => s.replace(/(veil = Color\([^)]*opacity: )0\.4000/, "$11.0000")), /swift veil opacity: got 1\.0000, expected 0\.4000/);
  const colorset = "Colors.xcassets/scrim.colorset/Contents.json";
  assert.match(broken(colorset, (s) => { const d = JSON.parse(s); d.colors[0].color.components.alpha = "1.000"; return JSON.stringify(d); }), /colorset scrim light alpha: got 1\.000, expected 0\.400/);
  assert.match(broken("tokens.json", (s) => { const d = JSON.parse(s); d.primitives["color.veil"].alpha = 1; return JSON.stringify(d); }), /json primitive color\.veil: got #[0-9a-f]{6}, expected #[0-9a-f]{6}66/);
});

test("build: a broken output is caught by --check and repaired by a rebuild", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  const xml = path.join(p, "assets/tokens/android/values/colors.xml");
  mutateText(xml, "#F9F7EE", "#000000");
  const r = bc(["tokens", "--project", p, "--check"]);
  assert.equal(r.status, 1);
  assert.match(r.stdout, /stale or missing: android\/values\/colors.xml/);
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  assert.equal(bc(["tokens", "--project", p, "--check"]).status, 0);
});

test("build: unknown flags are a usage error", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  assert.equal(bc(["tokens", "--project", p, "--bogus"]).status, 2);
});

// ---------------------------------------------------------------- motion: durations and cubic-bezier curves

const editTokens = (p, f, fn) => { const file = path.join(p, "tokens", f); const d = JSON.parse(fs.readFileSync(file, "utf8")); fn(d); fs.writeFileSync(file, JSON.stringify(d, null, 2) + "\n"); };
const built = (p, f) => fs.readFileSync(path.join(p, "assets/tokens", f), "utf8");
const walkFiles = (dir, base = dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walkFiles(path.join(dir, e.name), base) : [path.relative(base, path.join(dir, e.name)).split(path.sep).join("/")]));
const lines = (...l) => l.join("\n") + "\n";
const GENERATED = "Generated by brand-creator build_tokens from tokens/*.tokens.json. Do not edit.";

/** Acme (one duration, duration.fast) plus a motion group in three spellings of a duration and an easing group with a curve, an alias and an overshoot. */
function motionProject() {
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => {
    d.motion = { $type: "duration", base: { $value: { value: 320, unit: "ms" } }, secs: { $value: { value: 0.64, unit: "s" } }, legacy: { $value: "90ms" } };
    d.easing = { $type: "cubicBezier", standard: { $value: [0.2, 0, 0, 1] }, enter: { $value: "{easing.standard}" }, bounce: { $value: [0.34, 1.56, 0.64, 1] } };
  });
  return p;
}

test("durationMs and checkCurve: what a duration and a curve may be, and the token path in every refusal", async (t) => {
  const b = await lib(t); if (!b) return;
  assert.equal(b.durationMs({ value: 320, unit: "ms" }), 320);
  assert.equal(b.durationMs({ value: 0.32, unit: "s" }), 320);
  assert.ok(1.001 * 1000 !== 1001, "the premise: 1.001 * 1000 is 1000.9999999999999 in floating point");
  assert.equal(b.durationMs({ value: 1.001, unit: "s" }), 1001);        // a whole number of milliseconds, though the product is not exact
  assert.equal(b.durationMs("150ms"), 150);
  assert.equal(b.durationMs("0.5s"), 500);
  assert.equal(b.durationMs({ value: 0, unit: "ms" }), 0);
  assert.throws(() => b.durationMs({ value: -1, unit: "ms" }, "motion.x"), /^Error: motion\.x: not a DTCG duration/);
  assert.throws(() => b.durationMs({ value: 1, unit: "min" }, "motion.x"), /motion\.x: not a DTCG duration/);
  assert.throws(() => b.durationMs({ value: Infinity, unit: "ms" }, "motion.x"), /motion\.x: not a DTCG duration/);
  assert.throws(() => b.durationMs([320, "ms"], "motion.x"), /motion\.x: not a DTCG duration/);
  assert.throws(() => b.durationMs("soon", "motion.x"), /motion\.x: not a DTCG duration .* got "soon"/);
  assert.throws(() => b.durationMs({ value: 12.5, unit: "ms" }, "motion.x"), /motion\.x: 12\.5ms is not a whole number of milliseconds/);
  assert.equal(b.durationMs({ value: 2147483647, unit: "ms" }), 2147483647);                        // the largest integer an Android <integer> holds
  assert.throws(() => b.durationMs({ value: 2147483648, unit: "ms" }, "motion.x"), /motion\.x: 2147483648ms is longer than 2147483647 ms, the largest integer Android keeps/);
  assert.throws(() => b.durationMs({ value: 3000000, unit: "s" }, "motion.forever"), /motion\.forever: 3000000s is longer than 2147483647 ms/);
  assert.deepEqual(b.checkCurve([0.2, 0, 0, 1]), [0.2, 0, 0, 1]);
  assert.deepEqual(b.checkCurve([0, -0.5, 1, 1.5]), [0, -0.5, 1, 1.5]);   // x is held to [0, 1] at both ends, y is not held at all
  assert.throws(() => b.checkCurve([0.2, 0, 0], "easing.x"), /^Error: easing\.x: not a DTCG cubicBezier \[x1, y1, x2, y2\] \(four finite numbers\)/);
  assert.throws(() => b.checkCurve([0.2, 0, 0, NaN], "easing.x"), /easing\.x: not a DTCG cubicBezier/);
  assert.throws(() => b.checkCurve([0.2, Infinity, 0, 1], "easing.x"), /easing\.x: not a DTCG cubicBezier/);
  assert.throws(() => b.checkCurve("ease", "easing.x"), /easing\.x: not a DTCG cubicBezier/);
  assert.throws(() => b.checkCurve([1.01, 0, 0, 1], "easing.x"), /easing\.x: x1 and x2 must be within 0 and 1, got x1 1\.01 and x2 0/);
  assert.throws(() => b.checkCurve([0, 0, -0.01, 1], "easing.x"), /easing\.x: x1 and x2 must be within 0 and 1, got x1 0 and x2 -0\.01/);
  assert.throws(() => b.checkCurve([-0.01, 0, 1, 1], "easing.x"), /got x1 -0\.01 and x2 1/);
  assert.throws(() => b.checkCurve([0, 0, 1.01, 1], "easing.x"), /got x1 0 and x2 1\.01/);
});

test("build: a curve and a duration in every spelling reach CSS, tokens.json, Swift and Android, and the round trip reads them all back", async (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const css = built(p, "tokens.css");
  for (const re of [/--duration-fast: 150ms;/, /--motion-base: 320ms;/, /--motion-secs: 0\.64s;/, /--motion-legacy: 90ms;/, /--easing-standard: cubic-bezier\(0\.2, 0, 0, 1\);/,
    /--easing-enter: var\(--easing-standard\);/, /--easing-bounce: cubic-bezier\(0\.34, 1\.56, 0\.64, 1\);/]) assert.match(css, re);
  assert.ok(css.indexOf("--easing-bounce") < css.indexOf("@supports"), "curves are written with the other non-colour primitives");
  const tj = JSON.parse(built(p, "tokens.json"));
  assert.equal(tj.other["easing.standard"], "cubic-bezier(0.2, 0, 0, 1)");
  assert.equal(tj.other["easing.enter"], "var(--easing-standard)");
  assert.equal(tj.other["duration.fast"], "150ms");
  assert.equal(tj.other["motion.secs"], "0.64s");
  assert.deepEqual(tj.motion, { durations_ms: { "duration.fast": 150, "motion.base": 320, "motion.legacy": 90, "motion.secs": 640 },
    curves: { "easing.bounce": [0.34, 1.56, 0.64, 1], "easing.enter": [0.2, 0, 0, 1], "easing.standard": [0.2, 0, 0, 1] } });
  assert.deepEqual(Object.keys(tj.motion.curves), ["easing.bounce", "easing.enter", "easing.standard"]);   // sorted, like every other map in the file
  assert.equal(built(p, "swift/BrandMotion.swift"), lines(`// ${GENERATED}`, "import SwiftUI", "",
    "/// Durations in seconds and cubic-bezier curves. Nothing here reads Reduce Motion: the app does, and plays none of it when it is on.", "public enum BrandMotion {",
    "    public enum Duration {", "        public static let fast: Double = 0.15", "        public static let base: Double = 0.32", "        public static let legacy: Double = 0.09",
    "        public static let secs: Double = 0.64", "    }", "    public enum Curve {",
    "        public static func bounce(duration: Double) -> Animation { Animation.timingCurve(0.34, 1.56, 0.64, 1, duration: duration) }",
    "        public static func enter(duration: Double) -> Animation { Animation.timingCurve(0.2, 0, 0, 1, duration: duration) }",
    "        public static func standard(duration: Double) -> Animation { Animation.timingCurve(0.2, 0, 0, 1, duration: duration) }", "    }", "}"));
  assert.equal(built(p, "android/values/motion.xml"), lines('<?xml version="1.0" encoding="utf-8"?>', `<!-- ${GENERATED} -->`, "<resources>",
    '    <integer name="brand_duration_fast">150</integer>', '    <integer name="brand_motion_base">320</integer>', '    <integer name="brand_motion_legacy">90</integer>',
    '    <integer name="brand_motion_secs">640</integer>', "</resources>"));
  const interpolator = (...c) => lines('<?xml version="1.0" encoding="utf-8"?>', `<!-- ${GENERATED} -->`, '<pathInterpolator xmlns:android="http://schemas.android.com/apk/res/android"',
    `    android:controlX1="${c[0]}"`, `    android:controlY1="${c[1]}"`, `    android:controlX2="${c[2]}"`, `    android:controlY2="${c[3]}"/>`);
  assert.equal(built(p, "android/interpolator/brand_easing_standard.xml"), interpolator(0.2, 0, 0, 1));
  assert.equal(built(p, "android/interpolator/brand_easing_enter.xml"), interpolator(0.2, 0, 0, 1));           // an alias is written out in full
  assert.equal(built(p, "android/interpolator/brand_easing_bounce.xml"), interpolator(0.34, 1.56, 0.64, 1));   // y above 1: an overshoot is a curve too
  assert.deepEqual(walkFiles(path.join(p, "assets/tokens/android/interpolator")), ["brand_easing_bounce.xml", "brand_easing_enter.xml", "brand_easing_standard.xml"]);
  const rep = JSON.parse(fs.readFileSync(path.join(p, "assets/_checks/tokens.json"), "utf8"));
  assert.equal(rep.status, "pass");
  assert.match(rep.results.find((x) => x.id === "motion-tokens" && x.status === "pass").detail, /^4 duration\(s\).*3 curve\(s\)/);
  assert.match(rep.results.find((x) => x.id === "round-trip" && x.status === "pass").detail, /4 duration\(s\), 3 curve\(s\)/);
  assert.equal(bc(["tokens", "--project", p, "--check"]).status, 0);
});

test("build: a curve or a duration that is not valid fails the build, names its token path and writes nothing", async (t) => {
  if (needSetup(t)) return;
  const curves = [
    ["three numbers", [0.2, 0, 0], /easing\.bad: not a DTCG cubicBezier \[x1, y1, x2, y2\] \(four finite numbers\), got \[0\.2,0,0\]/],
    ["five numbers", [0.2, 0, 0, 1, 1], /easing\.bad: not a DTCG cubicBezier .* got \[0\.2,0,0,1,1\]/],
    ["a word for a number", [0.2, "slow", 0, 1], /easing\.bad: not a DTCG cubicBezier .* got \[0\.2,"slow",0,1\]/],
    ["not an array", "ease-in", /easing\.bad: not a DTCG cubicBezier .* got "ease-in"/],
    ["an infinite number", [0.2, "__INF__", 0, 1], /easing\.bad: not a DTCG cubicBezier .* got \[0\.2,null,0,1\]/],
    ["x1 above 1", [1.5, 0, 0, 1], /easing\.bad: x1 and x2 must be within 0 and 1, got x1 1\.5 and x2 0/],
    ["x1 below 0", [-0.1, 0, 0, 1], /easing\.bad: x1 and x2 must be within 0 and 1, got x1 -0\.1 and x2 0/],
    ["x2 above 1", [0.2, 0, 1.1, 1], /easing\.bad: x1 and x2 must be within 0 and 1, got x1 0\.2 and x2 1\.1/],
    ["x2 below 0", [0.2, 0, -0.1, 1], /easing\.bad: x1 and x2 must be within 0 and 1, got x1 0\.2 and x2 -0\.1/],
    ["a reference to a duration", "{duration.fast}", /easing\.bad: not a DTCG cubicBezier .* got \{"value":150,"unit":"ms"\}/],
  ];
  for (const [what, value, expected] of curves) {
    const p = makeProject();
    editTokens(p, "primitives.tokens.json", (d) => { d.easing = { $type: "cubicBezier", standard: { $value: [0.2, 0, 0, 1] }, bad: { $value: value } }; });
    fs.writeFileSync(path.join(p, "tokens/primitives.tokens.json"), fs.readFileSync(path.join(p, "tokens/primitives.tokens.json"), "utf8").replace('"__INF__"', "1e999"));
    const r = bc(["tokens", "--project", p]);
    assert.equal(r.status, 1, `${what}: ${r.stdout}${r.stderr}`);
    assert.match(r.stdout, /\[FAIL\] motion-tokens/, what);
    assert.match(r.stdout, expected, what);
    assert.doesNotMatch(r.stdout, /easing\.standard/, `${what}: only the bad token is named`);
    assert.ok(!fs.existsSync(path.join(p, "assets/tokens")), `${what}: nothing is written from invalid sources`);
  }
  const durations = [
    ["a negative value", { value: -1, unit: "ms" }, /motion\.bad: not a DTCG duration/],
    ["a unit that is not ms or s", { value: 2, unit: "min" }, /motion\.bad: not a DTCG duration .* got \{"value":2,"unit":"min"\}/],
    ["a word for the value", { value: "fast", unit: "ms" }, /motion\.bad: not a DTCG duration/],
    ["no unit", { value: 320 }, /motion\.bad: not a DTCG duration .* got \{"value":320\}/],
    ["a string that is not a duration", "soon", /motion\.bad: not a DTCG duration .* got "soon"/],
    ["a fraction of a millisecond", { value: 12.5, unit: "ms" }, /motion\.bad: 12\.5ms is not a whole number of milliseconds/],
    ["a reference to a colour", "{color.paper}", /motion\.bad: not a DTCG duration/],
  ];
  for (const [what, value, expected] of durations) {
    const p = makeProject();
    editTokens(p, "primitives.tokens.json", (d) => { d.motion = { $type: "duration", base: { $value: { value: 320, unit: "ms" } }, bad: { $value: value } }; });
    const r = bc(["tokens", "--project", p]);
    assert.equal(r.status, 1, `${what}: ${r.stdout}${r.stderr}`);
    assert.match(r.stdout, /\[FAIL\] motion-tokens/, what);
    assert.match(r.stdout, expected, what);
    assert.doesNotMatch(r.stdout, /motion\.base/, `${what}: only the bad token is named`);
    assert.ok(!fs.existsSync(path.join(p, "assets/tokens")), `${what}: nothing is written from invalid sources`);
  }
  // every bad token is named, not only the first
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => { d.easing = { $type: "cubicBezier", one: { $value: [2, 0, 0, 1] }, two: { $value: [0, 0, 0] } }; });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 1);
  assert.match(r.stdout, /easing\.one: x1 and x2 must be within 0 and 1.*easing\.two: not a DTCG cubicBezier/);
  // a reference to a token that does not exist is Style Dictionary's own failure, as for a colour
  const q = makeProject();
  editTokens(q, "primitives.tokens.json", (d) => { d.easing = { $type: "cubicBezier", enter: { $value: "{easing.nope}" } }; });
  const rq = bc(["tokens", "--project", q]);
  assert.equal(rq.status, 1);
  assert.match(rq.stdout, /\[FAIL\] style-dictionary/);
});

test("build: motion names that collide, or cannot be written in Swift or Android, fail the build; a duration and a curve of one name do not collide", async (t) => {
  if (needSetup(t)) return;
  const cases = [
    ["two durations with one Swift name", { motion: { $type: "duration", "fast-in": { $value: { value: 1, unit: "ms" } }, fastIn: { $value: { value: 2, unit: "ms" } } } },
      /BrandMotion\.Duration: motion\.fast-in and motion\.fastIn both become fastIn/],
    ["two curves with one Swift name", { easing: { $type: "cubicBezier", "fast-in": { $value: [0, 0, 1, 1] }, fastIn: { $value: [0, 0, 1, 1] } } },
      /BrandMotion\.Curve: easing\.fast-in and easing\.fastIn both become fastIn/],
    ["two durations with one Android name", { motion: { $type: "duration", "a-b": { $value: { value: 1, unit: "ms" } }, a_b: { $value: { value: 2, unit: "ms" } } } },
      /android integer: motion\.a-b and motion\.a_b both become brand_motion_a_b/],
    ["two curves with one Android name", { easing: { $type: "cubicBezier", "a-b": { $value: [0, 0, 1, 1] }, a_b: { $value: [0, 0, 1, 1] } } },
      /android interpolator: easing\.a-b and easing\.a_b both become brand_easing_a_b/],
    ["a curve whose Android file name would have a capital", { easing: { $type: "cubicBezier", fastIn: { $value: [0, 0, 1, 1] } } },
      /easing\.fastIn: brand_easing_fastIn\.xml is not an Android file resource name \(lower case letters, digits and underscores only: rename the token, for example fast-in\)/],
    ["a duration that is no Swift identifier", { motion: { $type: "duration", "a b": { $value: { value: 1, unit: "ms" } } } }, /motion\.a b: a b is not a Swift identifier/],
    ["a duration that is no Android resource name", { motion: { $type: "duration", "a b": { $value: { value: 1, unit: "ms" } } } }, /motion\.a b: brand_motion_a b is not an Android resource name/],
    ["a duration Swift cannot name", { motion: { $type: "duration", Type: { $value: { value: 1, unit: "ms" } } } },
      /motion\.Type: a Swift member cannot be named Type \(BrandMotion\.Duration\.Type means the type itself; rename the token\)/],
    ["a curve Swift cannot name", { easing: { $type: "cubicBezier", Protocol: { $value: [0, 0, 1, 1] } } }, /easing\.Protocol: a Swift member cannot be named Protocol/],
  ];
  for (const [what, groups, expected] of cases) {
    const p = makeProject();
    editTokens(p, "primitives.tokens.json", (d) => Object.assign(d, groups));
    const r = bc(["tokens", "--project", p]);
    assert.equal(r.status, 1, `${what}: ${r.stdout}${r.stderr}`);
    assert.match(r.stdout, /\[FAIL\] motion-names/, what);
    assert.match(r.stdout, expected, what);
    assert.ok(!fs.existsSync(path.join(p, "assets/tokens")), `${what}: nothing is written`);
  }
  // the same name in the two namespaces is fine: Duration.standard and Curve.standard, brand_motion_standard and brand_easing_standard
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => { d.motion = { $type: "duration", standard: { $value: { value: 300, unit: "ms" } } }; d.easing = { $type: "cubicBezier", standard: { $value: [0.2, 0, 0, 1] } }; });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(built(p, "swift/BrandMotion.swift"), /public enum Duration \{\n(?:.*\n)*?        public static let standard: Double = 0\.3\n/);
  assert.match(built(p, "swift/BrandMotion.swift"), /public enum Curve \{\n        public static func standard\(duration: Double\)/);
  assert.match(built(p, "android/values/motion.xml"), /<integer name="brand_motion_standard">300<\/integer>/);
  assert.ok(fs.existsSync(path.join(p, "assets/tokens/android/interpolator/brand_easing_standard.xml")));
});

test("build: the Swift names of motion tokens follow the colours' rules (a reserved word is escaped, a leading digit gets a prefix) and a token with no group keeps its name", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => {
    d.motion = { $type: "duration", default: { $value: { value: 200, unit: "ms" } }, Self: { $value: { value: 210, unit: "ms" } }, guard: { $value: { value: 220, unit: "ms" } } };
    d.easing = { $type: "cubicBezier", default: { $value: [0.2, 0, 0, 1] }, "2x": { $value: [0, 0, 1, 1] }, repeat: { $value: [0.1, 0, 1, 1] } };
    d.snap = { $type: "duration", $value: { value: 90, unit: "ms" } };           // no group at all
    d.punch = { $type: "cubicBezier", $value: [0.5, 0, 1, 0.5] };
  });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const swift = built(p, "swift/BrandMotion.swift");
  assert.match(swift, /public static let `default`: Double = 0\.2\n/);
  assert.match(swift, /public static let `Self`: Double = 0\.21\n/);                                 // every Swift keyword is escaped, not just the common ones
  assert.match(swift, /public static let `guard`: Double = 0\.22\n/);
  assert.match(swift, /public static func `repeat`\(duration: Double\)/);
  assert.match(swift, /public static func `default`\(duration: Double\) -> Animation \{ Animation\.timingCurve\(0\.2, 0, 0, 1, duration: duration\) \}/);
  assert.match(swift, /public static func c2x\(duration: Double\)/);                                  // a name that starts with a digit gets the colours' prefix
  assert.match(swift, /public static let snap: Double = 0\.09\n/);
  assert.match(swift, /public static func punch\(duration: Double\) -> Animation \{ Animation\.timingCurve\(0\.5, 0, 1, 0\.5, duration: duration\) \}/);
  assert.match(built(p, "android/values/motion.xml"), /<integer name="brand_snap">90<\/integer>/);
  assert.ok(fs.existsSync(path.join(p, "assets/tokens/android/interpolator/brand_punch.xml")));
  assert.match(built(p, "tokens.css"), /--snap: 90ms;/);
});

test("build: a duration whose seconds are not exact in binary floating point (1001 ms is 1.001 s) is written and read back", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => { d.motion = { $type: "duration", long: { $value: { value: 1001, unit: "ms" } } }; });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(1.001 * 1000 !== 1001, "the premise: 1.001 * 1000 is 1000.9999999999999");
  assert.match(built(p, "swift/BrandMotion.swift"), /public static let long: Double = 1\.001\n/);
  assert.match(built(p, "android/values/motion.xml"), /<integer name="brand_motion_long">1001<\/integer>/);
});

test("plain: a number in exponent form is expanded digit for digit, never rounded, and reads back as the same number", async (t) => {
  const b = await lib(t); if (!b) return;
  for (const [n, s] of [[1.2345678901234566e-7, "0.00000012345678901234566"], [5.551115123125783e-17, "0.00000000000000005551115123125783"],
    [1e-21, "0.000000000000000000001"], [1.5e22, "15000000000000000000000"], [-2.5e-8, "-0.000000025"], [1e21, "1000000000000000000000"],
    [0.2, "0.2"], [1, "1"], [0, "0"], [-0.5, "-0.5"]]) {
    assert.equal(b.plain(n), s, String(n));
    assert.equal(Number(b.plain(n)), n, `${s} reads back as ${n}`);
  }
});

test("build: a number JavaScript prints as 1e-7 or 1e+21 is a plain decimal in CSS, Swift and Android, and reads back", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => { d.easing = { $type: "cubicBezier", odd: { $value: [0.2, 1e-7, 0.5, 1e21] } }; });
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(built(p, "tokens.css"), /--easing-odd: cubic-bezier\(0\.2, 0\.0000001, 0\.5, 1000000000000000000000\);/);
  assert.match(built(p, "swift/BrandMotion.swift"), /Animation\.timingCurve\(0\.2, 0\.0000001, 0\.5, 1000000000000000000000, duration: duration\)/);
  assert.match(built(p, "android/interpolator/brand_easing_odd.xml"), /android:controlY1="0\.0000001"\n    android:controlX2="0\.5"\n    android:controlY2="1000000000000000000000"\/>/);
  assert.deepEqual(JSON.parse(built(p, "tokens.json")).motion.curves["easing.odd"], [0.2, 1e-7, 0.5, 1e21]);
  // many digits behind the exponent (float noise from a design tool) and a number below 1e-20: every digit is kept, none becomes 0
  editTokens(p, "primitives.tokens.json", (d) => { d.easing.noise = { $value: [0.25, 5.551115123125783e-17, 0.25, 1] }; d.easing.tiny = { $value: [0.2, 1.2345678901234566e-7, 0, 1e-21] }; });
  const again = bc(["tokens", "--project", p]);
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(built(p, "tokens.css"), /--easing-noise: cubic-bezier\(0\.25, 0\.00000000000000005551115123125783, 0\.25, 1\);/);
  assert.match(built(p, "tokens.css"), /--easing-tiny: cubic-bezier\(0\.2, 0\.00000012345678901234566, 0, 0\.000000000000000000001\);/);
  assert.match(built(p, "swift/BrandMotion.swift"), /Animation\.timingCurve\(0\.2, 0\.00000012345678901234566, 0, 0\.000000000000000000001, duration: duration\)/);
  assert.match(built(p, "android/interpolator/brand_easing_tiny.xml"), /android:controlY1="0\.00000012345678901234566"\n    android:controlX2="0"\n    android:controlY2="0\.000000000000000000001"\/>/);
});

test("build: no duration and no curve writes no motion file and no motion entry; adding curves changes nothing else", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  editTokens(p, "primitives.tokens.json", (d) => { delete d.duration; });
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  const before = Object.fromEntries(walkFiles(path.join(p, "assets/tokens")).map((f) => [f, built(p, f)]));
  assert.deepEqual(Object.keys(before).filter((f) => /motion|interpolator/i.test(f)), []);
  assert.ok(!fs.existsSync(path.join(p, "assets/tokens/android/interpolator")));
  assert.equal(JSON.parse(before["tokens.json"]).motion, undefined);
  assert.doesNotMatch(before["tokens.css"], /duration|easing|cubic-bezier/);
  // the same project with the motion and easing groups: the colour outputs are byte for byte the same, and tokens.css gains only the new lines
  editTokens(p, "primitives.tokens.json", (d) => { d.motion = { $type: "duration", base: { $value: { value: 320, unit: "ms" } } }; d.easing = { $type: "cubicBezier", standard: { $value: [0.2, 0, 0, 1] } }; });
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  const after = Object.fromEntries(walkFiles(path.join(p, "assets/tokens")).map((f) => [f, built(p, f)]));
  assert.deepEqual(Object.keys(after).filter((f) => !(f in before)).sort(), ["android/interpolator/brand_easing_standard.xml", "android/values/motion.xml", "swift/BrandMotion.swift"]);
  for (const f of Object.keys(before)) {
    if (f === "tokens.css") assert.equal(after[f].split("\n").filter((l) => !/^  --(motion|easing)-/.test(l)).join("\n"), before[f], "tokens.css: only the motion lines are new");
    else if (f === "tokens.json") assert.deepEqual({ ...JSON.parse(after[f]), other: undefined, motion: undefined }, { ...JSON.parse(before[f]), other: undefined, motion: undefined });
    else assert.equal(after[f], before[f], `${f} is unchanged`);
  }
});

test("build: --check covers the motion files, and a rebuild repairs them", async (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  assert.equal(bc(["tokens", "--project", p, "--check"]).status, 0);
  for (const [f, from, to] of [["android/interpolator/brand_easing_standard.xml", 'controlY2="1"', 'controlY2="0.5"'], ["android/values/motion.xml", ">320<", ">321<"],
    ["swift/BrandMotion.swift", "0.32", "0.33"]]) {
    mutateText(path.join(p, "assets/tokens", f), from, to);
    const r = bc(["tokens", "--project", p, "--check"]);
    assert.equal(r.status, 1, f);
    assert.match(r.stdout, new RegExp(`stale or missing: ${f.replace(/[./]/g, "\\$&")}`));
    assert.equal(bc(["tokens", "--project", p]).status, 0);
    assert.equal(bc(["tokens", "--project", p, "--check"]).status, 0, f);
  }
  const again = bc(["tokens", "--project", p]);
  assert.match(again.stdout, /0 file\(s\) written/);     // put-on-byte-change for the new files too
});

test("build: a colour Swift cannot name (Type, Protocol) fails the build, names the token and writes nothing", async (t) => {
  if (needSetup(t)) return;
  for (const name of ["Type", "Protocol"]) {
    const p = makeProject();
    editTokens(p, "primitives.tokens.json", (d) => { d.color[name] = structuredClone(d.color.paper); });
    const r = bc(["tokens", "--project", p]);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(r.stdout, new RegExp(`\\[FAIL\\] swift-names.*color\\.${name}: a Swift member cannot be named Type or Protocol`));
    assert.ok(!fs.existsSync(path.join(p, "assets/tokens")), `${name}: nothing is written`);
  }
});

test("build: a file the sources no longer produce fails --check and a build moves it to removed-<date>/ (a renamed curve, the last duration, a removed colour role)", async (t) => {
  if (needSetup(t)) return;
  const p = motionProject();
  const role = (fn) => { for (const f of ["semantic.light.tokens.json", "semantic.dark.tokens.json"]) editTokens(p, f, fn); };
  role((d) => { d.color.extra = { $value: "{color.paper}" }; });
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  const at = (f) => path.join(p, "assets/tokens", f), moved = (dir, f) => path.join(p, dir, "assets/tokens", f);
  assert.ok(fs.existsSync(at("Colors.xcassets/extra.colorset/Contents.json")));
  editTokens(p, "primitives.tokens.json", (d) => { d.easing.springy = d.easing.bounce; delete d.easing.bounce; delete d.motion; delete d.duration; });
  role((d) => { delete d.color.extra; });
  const gone = ["Colors.xcassets/extra.colorset", "android/interpolator/brand_easing_bounce.xml", "android/values/motion.xml"];
  let r = bc(["tokens", "--project", p, "--check"]);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.ok(r.stdout.includes(`no longer produced by the sources: ${gone.join(", ")} (run: brand-creator tokens, which moves what is no longer produced to removed-2026-10-17/)`), r.stdout);
  assert.ok(gone.every((f) => fs.existsSync(at(f))), "--check moves nothing");
  r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);                                                  // a warning, not a failure: the sources are fine
  assert.match(r.stdout, /\[WARN\] retired/);
  for (const f of gone) assert.ok(!fs.existsSync(at(f)) && fs.existsSync(moved("removed-2026-10-17", f)), f);   // moved, never deleted
  assert.ok(fs.existsSync(moved("removed-2026-10-17", "Colors.xcassets/extra.colorset/Contents.json")), "a colorset goes as a whole folder");
  assert.doesNotMatch(built(p, "swift/BrandMotion.swift"), /enum Duration/);                        // the curves are still there, the durations are not
  assert.ok(fs.existsSync(at("android/interpolator/brand_easing_springy.xml")));
  assert.equal(bc(["tokens", "--project", p, "--check"]).status, 0);
  // the last curve goes too: no motion file is left; a name already in removed-<date>/ goes to removed-<date>-2/
  editTokens(p, "primitives.tokens.json", (d) => { d.motion = { $type: "duration", base: { $value: { value: 320, unit: "ms" } } }; });
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  editTokens(p, "primitives.tokens.json", (d) => { delete d.motion; delete d.easing; });
  r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(fs.existsSync(moved("removed-2026-10-17-2", "android/values/motion.xml")) && fs.existsSync(moved("removed-2026-10-17", "swift/BrandMotion.swift")));
  assert.deepEqual(walkFiles(path.join(p, "assets/tokens")).filter((f) => /motion|interpolator/i.test(f)), []);
  assert.equal(bc(["tokens", "--project", p, "--check"]).status, 0);
});

test("build: the starter tokens carry three curve proposals next to the durations, and every one reaches Swift and Android", async (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  for (const f of fs.readdirSync(path.join(ROOT, "templates/tokens"))) fs.copyFileSync(path.join(ROOT, "templates/tokens", f), path.join(p, "tokens", f));
  const r = bc(["tokens", "--project", p]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const tj = JSON.parse(built(p, "tokens.json"));
  assert.deepEqual(tj.motion.curves, { "easing.enter": [0, 0, 0, 1], "easing.exit": [0.3, 0, 1, 1], "easing.standard": [0.2, 0, 0, 1] });
  assert.deepEqual(tj.motion.durations_ms, { "motion.base": 320, "motion.quick": 160, "motion.slow": 640, "motion.stagger": 120 });
  assert.match(built(p, "tokens.css"), /--easing-exit: cubic-bezier\(0\.3, 0, 1, 1\);/);
  const swift = built(p, "swift/BrandMotion.swift");
  for (const id of ["base", "quick", "slow", "stagger"]) assert.match(swift, new RegExp(`public static let ${id}: Double = `));
  for (const id of ["standard", "enter", "exit"]) assert.match(swift, new RegExp(`public static func ${id}\\(duration: Double\\) -> Animation`));
  assert.ok(swift.indexOf("let base") < swift.indexOf("let quick") && swift.indexOf("let quick") < swift.indexOf("let slow"), "sorted by name, not in file order");
  assert.deepEqual(walkFiles(path.join(p, "assets/tokens/android/interpolator")), ["brand_easing_enter.xml", "brand_easing_exit.xml", "brand_easing_standard.xml"]);
  assert.match(built(p, "android/values/motion.xml"), /<integer name="brand_motion_stagger">120<\/integer>/);
});

test("roundTrip: every motion output is parsed back, and a deliberate break in each one is a problem, never skipped", async (t) => {
  if (needSetup(t)) return;
  const b = await lib(t); if (!b) return;
  const p = motionProject();
  assert.equal(bc(["tokens", "--project", p]).status, 0);
  const files = Object.fromEntries(walkFiles(path.join(p, "assets/tokens")).map((f) => [f, built(p, f)]));
  const tj = JSON.parse(files["tokens.json"]);
  const mode = (m) => new Map(Object.entries(tj.modes[m]));
  const model = { prims: Object.entries(tj.primitives), light: mode("light"), dark: mode("dark"), ...motionOf(tj) };
  assert.equal(model.durations.length, 4);
  assert.equal(model.curves.length, 3);
  assert.deepEqual(b.roundTrip(model, files), []);
  const breaks = (what, f, fn, expected) => {
    const text = fn(files[f]);
    assert.notEqual(text, files[f], `${what}: the break did not change ${f}`);
    const problems = b.roundTrip(model, { ...files, [f]: text }).join(";");
    assert.match(problems, expected, what);
  };
  const json = (fn) => (s) => { const d = JSON.parse(s); fn(d); return JSON.stringify(d, null, 2) + "\n"; };
  // tokens.css: a duration, a curve and an alias, each changed, unreadable and missing
  const css = "tokens.css", tjn = "tokens.json";
  breaks("css duration changed", css, (s) => s.replace("--motion-base: 320ms;", "--motion-base: 321ms;"), /css motion-base: got 321ms, expected 320ms/);
  breaks("css duration in the wrong unit", css, (s) => s.replace("--motion-base: 320ms;", "--motion-base: 320s;"), /css motion-base: got 320s, expected 320ms/);
  breaks("css duration unreadable", css, (s) => s.replace("--motion-base: 320ms;", "--motion-base: fast;"), /css motion-base: cannot read fast/);
  breaks("css duration missing", css, (s) => s.replace("  --motion-base: 320ms;\n", ""), /css motion-base: missing, expected 320ms/);
  assert.deepEqual(b.roundTrip(model, { ...files, [css]: files[css].replace("--motion-base: 320ms;", "--motion-base: 0.32s;"),
    [tjn]: json((d) => { d.other["motion.base"] = "0.32s"; })(files[tjn]) }), [], "0.32s is 320ms");
  breaks("css curve changed", css, (s) => s.replace("--easing-standard: cubic-bezier(0.2, 0, 0, 1);", "--easing-standard: cubic-bezier(0.2, 0, 0, 0.9);"),
    /css easing-standard: got cubic-bezier\(0\.2, 0, 0, 0\.9\), expected cubic-bezier\(0\.2, 0, 0, 1\)/);
  breaks("css curve unreadable", css, (s) => s.replace("--easing-standard: cubic-bezier(0.2, 0, 0, 1);", "--easing-standard: cubic-bezier(0.2, 0, 0);"), /css easing-standard: cannot read cubic-bezier\(0\.2, 0, 0\)/);
  breaks("css curve missing", css, (s) => s.replace("  --easing-standard: cubic-bezier(0.2, 0, 0, 1);\n", ""), /css easing-standard: missing, expected cubic-bezier\(0\.2, 0, 0, 1\)/);
  breaks("css alias that no longer reaches its curve", css, (s) => s.replace("--easing-enter: var(--easing-standard);", "--easing-enter: cubic-bezier(0, 0, 0, 1);"), /css easing-enter: got cubic-bezier\(0, 0, 0, 1\)/);
  breaks("css alias to a curve that is missing", css, (s) => s.replace("--easing-enter: var(--easing-standard);", "--easing-enter: var(--easing-nowhere);"), /css easing-enter: missing/);
  // swift/BrandMotion.swift
  const sw = "swift/BrandMotion.swift";
  breaks("swift duration changed", sw, (s) => s.replace("base: Double = 0.32", "base: Double = 0.33"), /swift Duration\.base: got 330 ms, expected 320 ms/);
  breaks("swift duration unreadable", sw, (s) => s.replace("base: Double = 0.32", "base: Double = fast"), /swift Duration: cannot read public static let base: Double = fast/);
  breaks("swift duration missing", sw, (s) => s.replace("        public static let base: Double = 0.32\n", ""), /swift Duration\.base: not found/);
  breaks("swift duration that is not in the tokens", sw, (s) => s.replace("    public enum Curve {", "        public static let ghost: Double = 1\n    }\n    public enum Curve {").replace("    }\n        public static let ghost", "        public static let ghost"), /swift Duration\.ghost: not in the tokens/);
  breaks("swift curve changed", sw, (s) => s.replace("standard(duration: Double) -> Animation { Animation.timingCurve(0.2, 0, 0, 1,", "standard(duration: Double) -> Animation { Animation.timingCurve(0.2, 0, 0, 0.9,"),
    /swift Curve\.standard: got 0\.2, 0, 0, 0\.9, expected 0\.2, 0, 0, 1/);
  breaks("swift curve unreadable", sw, (s) => s.replace("timingCurve(0.2, 0, 0, 1, duration: duration) }\n    }", "timingCurve(0.2, 0, duration: duration) }\n    }"), /swift Curve: cannot read public static func standard/);
  breaks("swift curve missing", sw, (s) => s.replace(/        public static func bounce.*\n/, ""), /swift Curve\.bounce: not found/);
  breaks("swift curve that is not in the tokens", sw, (s) => s.replace("    public enum Curve {\n", "    public enum Curve {\n        public static func ghost(duration: Double) -> Animation { Animation.timingCurve(0, 0, 1, 1, duration: duration) }\n"), /swift Curve\.ghost: not in the tokens/);
  breaks("swift Curve namespace missing", sw, (s) => s.replace("public enum Curve {", "public enum Curves {"), /swift Curve: missing/);
  assert.match(b.roundTrip(model, Object.fromEntries(Object.entries(files).filter(([f]) => f !== sw))).join(";"), /swift BrandMotion\.swift: missing/);
  // android/values/motion.xml and the interpolators
  const mx = "android/values/motion.xml";
  breaks("android duration changed", mx, (s) => s.replace(">320<", ">321<"), /android brand_motion_base: got 321 ms, expected 320 ms/);
  breaks("android duration unreadable", mx, (s) => s.replace(">320<", ">fast<"), /android values\/motion\.xml: cannot read <integer name="brand_motion_base">fast<\/integer>/);
  breaks("android duration missing", mx, (s) => s.replace('    <integer name="brand_motion_base">320</integer>\n', ""), /android brand_motion_base: not found/);
  breaks("android duration that is not in the tokens", mx, (s) => s.replace("</resources>", '    <integer name="brand_motion_ghost">5</integer>\n</resources>'), /android brand_motion_ghost: not in the tokens/);
  assert.match(b.roundTrip(model, Object.fromEntries(Object.entries(files).filter(([f]) => f !== mx))).join(";"), /android values\/motion\.xml: missing/);
  const ip = "android/interpolator/brand_easing_standard.xml";
  breaks("android curve changed", ip, (s) => s.replace('controlY2="1"', 'controlY2="0.9"'), /android android\/interpolator\/brand_easing_standard\.xml: got 0\.2, 0, 0, 0\.9, expected 0\.2, 0, 0, 1/);
  breaks("android curve control unreadable", ip, (s) => s.replace('controlX2="0"', 'controlX2="zero"'), /android android\/interpolator\/brand_easing_standard\.xml: cannot read the pathInterpolator and its four controls/);
  breaks("android curve control missing", ip, (s) => s.replace('    android:controlX1="0.2"\n', ""), /cannot read the pathInterpolator/);
  breaks("android curve that is no pathInterpolator", ip, (s) => s.replace("<pathInterpolator", "<accelerateInterpolator"), /cannot read the pathInterpolator/);
  assert.match(b.roundTrip(model, Object.fromEntries(Object.entries(files).filter(([f]) => f !== ip))).join(";"), /android android\/interpolator\/brand_easing_standard\.xml: missing/);
  assert.match(b.roundTrip(model, { ...files, "android/interpolator/brand_easing_ghost.xml": "<pathInterpolator/>" }).join(";"), /android android\/interpolator\/brand_easing_ghost\.xml: not in the tokens/);
  // tokens.json: the numbers under motion and the strings under other
  breaks("json duration changed", tjn, json((d) => { d.motion.durations_ms["motion.base"] = 321; }), /json motion duration motion\.base: got 321, expected 320/);
  breaks("json duration missing", tjn, json((d) => { delete d.motion.durations_ms["motion.base"]; }), /json motion duration motion\.base: got nothing, expected 320/);
  breaks("json duration that is not in the tokens", tjn, json((d) => { d.motion.durations_ms["motion.ghost"] = 5; }), /json motion duration motion\.ghost: not in the tokens/);
  breaks("json curve changed", tjn, json((d) => { d.motion.curves["easing.standard"] = [0.2, 0, 0, 0.9]; }), /json motion curve easing\.standard: got 0\.2, 0, 0, 0\.9, expected 0\.2, 0, 0, 1/);
  breaks("json curve missing", tjn, json((d) => { delete d.motion.curves["easing.standard"]; }), /json motion curve easing\.standard: got nothing/);
  breaks("json curve that is not in the tokens", tjn, json((d) => { d.motion.curves["easing.ghost"] = [0, 0, 1, 1]; }), /json motion curve easing\.ghost: not in the tokens/);
  breaks("json motion gone", tjn, json((d) => { delete d.motion; }), /json motion duration duration\.fast: got nothing, expected 150/);
  breaks("json other string changed", tjn, json((d) => { d.other["easing.standard"] = "cubic-bezier(0, 0, 1, 1)"; }), /json other easing\.standard: got cubic-bezier\(0, 0, 1, 1\), expected cubic-bezier\(0\.2, 0, 0, 1\)/);
  breaks("json other string of a duration changed", tjn, json((d) => { d.other["motion.secs"] = "0.65s"; }), /json other motion\.secs: got 0\.65s, expected 0\.64s/);
  // a model with durations only (or curves only) expects the other namespace to be empty, not merely absent from the model
  assert.match(b.roundTrip({ ...model, curves: [] }, files).join(";"), /swift Curve: written, but the tokens have none/);
  assert.match(b.roundTrip({ ...model, durations: [] }, files).join(";"), /swift Duration: written, but the tokens have none/);
  // a model with nothing in motion expects no motion output at all
  const none = { prims: model.prims, light: model.light, dark: model.dark };
  const noMotion = b.roundTrip(none, files).join(";");
  for (const re of [/swift BrandMotion\.swift: written, but the tokens have no duration or curve/, /android values\/motion\.xml: written, but the tokens have no duration/,
    /android android\/interpolator\/brand_easing_bounce\.xml: not in the tokens/, /json motion: written, but the tokens have no duration or curve/]) assert.match(noMotion, re);
  // a value that comes back rounded shows as two different numbers: "expected" prints the source number as it is, not respelled
  const noisy = { ...model, curves: model.curves.map(([k, c]) => [k, k === "easing.standard" ? [0.2, 5.551115123125783e-17, 0, 1] : c]) };
  const rounded = b.roundTrip(noisy, { ...files, [css]: files[css].replace("--easing-standard: cubic-bezier(0.2, 0, 0, 1);", "--easing-standard: cubic-bezier(0.2, 0.0000000000000000555111512313, 0, 1);") }).join(";");
  assert.match(rounded, /css easing-standard: got cubic-bezier\(0\.2, 0\.0000000000000000555111512313, 0, 1\), expected cubic-bezier\(0\.2, 5\.551115123125783e-17, 0, 1\)/);
});
