import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { spawn } from "node:child_process";
import { needSetup, bc, makeProject, BIN, DATA } from "./_helpers.mjs";
import { sha, png, jpeg, record, bcAsync, listen, TALL, CSS, MARK, writePage, MOVING, MOVING_CSS, FRAME_FILES, writeMoving, redPixels, REVEAL_HTML, REVEAL_CSS, LAYOUT, ITEMS, SEEN_HEADER, SEEN_SCRIPT, RED_BAND, revealLayout } from "./_capture.mjs";

// ---------------------------------------------------------------- capture <page> --frames: key frames of the first screen (group 4, G4-04)
// The pages are small ones of this test: a hero that rises in when it loads (1500 ms: the page is first looked at some time after it loaded, and on a busy machine that is later than 600 ms), and pages that move in ways that give no frame.

test("capture --frames: a page with an entrance animation gets three key frames that differ, listed in capture.json", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const page = writeMoving(p, "rounds/r1/Rise", MOVING_CSS);
  const dir = path.join(p, "rounds/r1/Rise/shots");
  const r = bc(["capture", page, "--project", p, "--frames"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", ...FRAME_FILES, "capture.json"].sort());
  assert.match(r.stdout, /8 stills and capture\.json in rounds\/r1\/Rise\/shots\/ \(9 of 9 file\(s\) written, the others unchanged\)/);
  assert.match(r.stdout, /key frames: 3 of the first screen \(1440, light\) at 0, 50, 100 % of 1500 ms/);
  for (const f of FRAME_FILES) assert.deepEqual(png(path.join(dir, f)), { width: 1440, height: 900 }, f);
  const bytes = FRAME_FILES.map((f) => fs.readFileSync(path.join(dir, f)));
  assert.equal(new Set(bytes.map(sha)).size, 3, "the three frames must differ: a frame that equals another shows no motion");
  assert.ok(Buffer.compare(fs.readFileSync(path.join(dir, "frame-1440-100.png")), fs.readFileSync(path.join(dir, "1440-light.png"))) === 0, "the frame at 100 % is the first screen at rest, as the still takes it");
  const rec = record(dir);
  assert.deepEqual(rec.frames.map((f) => [f.percent, f.ms, f.file]), [[0, 0, "frame-1440-0.png"], [50, 750, "frame-1440-50.png"], [100, 1500, "frame-1440-100.png"]]);
  for (const f of rec.frames) assert.equal(f.sha256, sha(fs.readFileSync(path.join(dir, f.file))), f.file);
  assert.deepEqual(rec.views.map((v) => v.file), ["1440-light.png", "1440-dark.png", "390-light.png", "390-dark.png"], "the four views are as they were");
  assert.ok(!rec.inputs.some((i) => i.path.includes("/shots/")), "the frames are not inputs of the page");
  // taken again, nothing changes: the frames are seeked, not waited for
  const again = bc(["capture", page, "--project", p, "--frames"], { env: { BRAND_CREATOR_TODAY: "2026-11-30" } });
  assert.equal(again.status, 0, again.stdout + again.stderr);
  assert.match(again.stdout, /\(0 of 9 file\(s\) written, the others unchanged\)/);
  assert.equal(record(dir).date, "2026-10-17");
  // a plain run leaves the frame files where they are and says they are not part of it; capture.json no longer lists them
  const plain = bc(["capture", page, "--project", p]);
  assert.equal(plain.status, 0, plain.stdout + plain.stderr);
  assert.match(plain.stdout, /frame-1440-0\.png, frame-1440-50\.png, frame-1440-100\.png in rounds\/r1\/Rise\/shots\/ are from an earlier run and not part of this one/);
  assert.ok(!("frames" in record(dir)));
  assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", ...FRAME_FILES, "capture.json"].sort());
});

test("capture --frames: a static page, a page whose animations never end and one that holds its animation paused get no frame, and the run says so", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const cases = [
    ["Still", CSS, TALL, /key frames: none written: no animation runs on load/],
    ["Spin", CSS + "@keyframes spin{to{transform:rotate(360deg)}}.rise{animation:spin 2s linear infinite}",
      MOVING, /key frames: none written: every animation that runs on load repeats forever or has no length/],
    ["Held", MOVING_CSS.replace("both}", "both paused}"), MOVING, /key frames: none written: no animation runs on load/],
  ];
  for (const [name, css, html, said] of cases) {
    const page = writeMoving(p, `rounds/r1/${name}`, css, html);
    const dir = path.join(p, `rounds/r1/${name}/shots`);
    const r = bc(["capture", page, "--project", p, "--frames"]);
    assert.equal(r.status, 0, name + r.stdout + r.stderr);
    assert.match(r.stdout, said, name);
    assert.deepEqual(fs.readdirSync(dir).sort(), ["1440-dark.png", "1440-light-full.png", "1440-light.png", "390-dark.png", "390-light.png", "capture.json"], name);
    assert.ok(!("frames" in record(dir)), `${name}: capture.json lists no frame`);
    assert.match(r.stdout, /6 stills and capture\.json|5 stills and capture\.json/, name);
  }
  // a plain run says nothing about frames
  const plain = bc(["capture", "rounds/r1/Still/index.html", "--project", p]);
  assert.equal(plain.status, 0, plain.stdout + plain.stderr);
  assert.ok(!/key frames/.test(plain.stdout), plain.stdout);
});

test("capture --frames: a finite animation beside an infinite one gives frames, and the longest finite one sets the length", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = MOVING_CSS + "@keyframes spin{to{transform:rotate(360deg)}}.spin{animation:spin 2s linear infinite;width:80px;height:80px;background:#c03}";
  const page = writeMoving(p, "rounds/r1/Both", css, MOVING.replace("</body>", "<div class=spin></div></body>"));
  const dir = path.join(p, "rounds/r1/Both/shots");
  const r = bc(["capture", page, "--project", p, "--frames"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /key frames: 3 of the first screen \(1440, light\) at 0, 50, 100 % of 1500 ms/, "the longest finite animation sets the length, not the infinite one");
  assert.deepEqual(record(dir).frames.map((f) => f.ms), [0, 750, 1500]);
});

// A script that starts the motion once the page is up: a CSS transition (a class added after 300 ms, or after two animation frames) and element.animate. The heading starts invisible and 300 px to the left, so the
// first frame must be the page without the heading, which `Blank` below is (the same page, static, its heading at opacity 0): an exact oracle, not a guess at "different enough".
const ENTER_HTML = (script) => "<!doctype html><html><head><meta charset=utf-8><title>Ledger, a demo page</title><link rel=stylesheet href=style.css></head>"
  + `<body><h1 class=hero>Ledger</h1><p>A heading that comes in once the page is up.</p><script>${script}</script></body></html>`;
const ENTER_CSS = (hero) => CSS + `h1{font-size:96px}.hero{opacity:0;transform:translateX(-300px)${hero}}`;
const ENTER_TRANSITION = ENTER_CSS(";transition:opacity 800ms,transform 800ms") + ".hero.in{opacity:1;transform:none}";
const ENTER_STARTERS = [
  ["a transition started by a timer", ENTER_HTML("setTimeout(() => document.querySelector('h1').classList.add('in'), 300)"), ENTER_TRANSITION, 800],
  ["a transition started after two animation frames", ENTER_HTML("requestAnimationFrame(() => requestAnimationFrame(() => document.querySelector('h1').classList.add('in')))"), ENTER_TRANSITION, 800],
  ["element.animate", ENTER_HTML("document.querySelector('h1').animate([{ opacity: 0, transform: 'translateX(-300px)' }, { opacity: 1, transform: 'none' }], { duration: 800, fill: 'both' })"),
    ENTER_CSS(""), 800],
];

test("capture --frames: a motion a script starts when the page loads (a CSS transition, element.animate) is seeked: the first frame is the page before it, the middle one is in between, the last is the page at rest", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const blankPage = writeMoving(p, "rounds/r1/Blank", ENTER_CSS(""), ENTER_HTML(""));
  const blank = bc(["capture", blankPage, "--project", p]);
  assert.equal(blank.status, 0, blank.stdout + blank.stderr);
  const before = fs.readFileSync(path.join(p, "rounds/r1/Blank/shots/1440-light.png"));
  ENTER_STARTERS.forEach(([what, html, css, ms], i) => {
    const page = writeMoving(p, `rounds/r1/Enter${i}`, css, html);
    const dir = path.join(p, `rounds/r1/Enter${i}/shots`);
    const r = bc(["capture", page, "--project", p, "--frames"]);
    assert.equal(r.status, 0, what + r.stdout + r.stderr);
    assert.match(r.stdout, new RegExp(`key frames: 3 of the first screen \\(1440, light\\) at 0, 50, 100 % of ${ms} ms`), what);
    const [f0, f50, f100, rest] = ["frame-1440-0.png", "frame-1440-50.png", "frame-1440-100.png", "1440-light.png"].map((f) => fs.readFileSync(path.join(dir, f)));
    assert.equal(new Set([f0, f50, f100].map(sha)).size, 3, `${what}: the three frames must differ`);
    assert.ok(Buffer.compare(f0, before) === 0, `${what}: the frame at 0 % is the page before the heading comes in (the heading is not there yet), not the heading already on its way`);
    assert.notEqual(sha(f0), sha(rest), `${what}: the frame at 0 % differs from the still at rest`);
    assert.ok(Buffer.compare(f100, rest) === 0, `${what}: the frame at 100 % is the page at rest, as the still takes it`);
    assert.notEqual(sha(f50), sha(before), `${what}: the frame at 50 % shows the heading on its way`);
    assert.notEqual(sha(f50), sha(rest), `${what}: the frame at 50 % is not the page at rest`);
  });
});

test("capture --frames: it goes with a page of the project, not with --url", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const r = bc(["capture", "--url", "http://127.0.0.1:9/", "--name", "nowhere", "--frames", "--project", p]);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.match(r.stderr, /--frames goes with a page of the project, not with --url/);
  assert.ok(!fs.existsSync(path.join(p, "research/site-refs")), "nothing is written");
});
