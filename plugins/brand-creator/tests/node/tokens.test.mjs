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
