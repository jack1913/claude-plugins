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
  for (const f of ["tokens.css", "tokens.json", "swift/BrandColors.swift", "android/values/colors.xml", "android/values-night/colors.xml"]) files[f] = out(f);
  for (const d of fs.readdirSync(path.join(p, "assets/tokens/Colors.xcassets")).filter((d) => d.endsWith(".colorset"))) files[`Colors.xcassets/${d}/Contents.json`] = out(`Colors.xcassets/${d}/Contents.json`);
  const tj = JSON.parse(files["tokens.json"]);
  const prims = Object.entries(tj.primitives);
  const mode = (m) => new Map(Object.entries(tj.modes[m]));
  const model = { prims, light: mode("light"), dark: mode("dark") };
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
  for (const f of ["tokens.css", "tokens.json", "swift/BrandColors.swift", "android/values/colors.xml", "android/values-night/colors.xml"]) files[f] = out(f);
  for (const d of fs.readdirSync(path.join(p, "assets/tokens/Colors.xcassets")).filter((d) => d.endsWith(".colorset"))) files[`Colors.xcassets/${d}/Contents.json`] = out(`Colors.xcassets/${d}/Contents.json`);
  const tj = JSON.parse(files["tokens.json"]);
  // the model as the build passes it: each primitive knows its modern form, so a missing @supports line is caught too
  const prims = Object.entries(tj.primitives).map(([k, c]) => [k, { ...c, css: src[k.split(".").pop()] ? b.computeColor(src[k.split(".").pop()]).css : null }]);
  const mode = (m) => new Map(Object.entries(tj.modes[m]));
  const model = { prims, light: mode("light"), dark: mode("dark") };
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
