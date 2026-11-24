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

// capture --reveal: the walk of 0.9.0, continued from capture-reveal.test.mjs (split in two so that node --test runs them side by side).

test("capture --reveal: a root whose overflow is hidden is walked and flagged, also when it comes from the body; a scrolling body or main under a hidden root is no such page", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  assert.deepEqual(revealLayout(p, "RootHidden", "html{overflow:hidden}", LAYOUT(ITEMS(3, 1000, "p"))).rec, { steps: 6, capped: false, root_hidden: true });
  // html visible: the body's overflow is the viewport's (propagation), so hidden on the body is hidden on the window
  assert.deepEqual(revealLayout(p, "BodyHidden", "body{overflow:hidden}", LAYOUT(ITEMS(3, 1000, "p"))).rec, { steps: 6, capped: false, root_hidden: true });
  // the body scrolls itself under a hidden root: a visitor's wheel scrolls it, so there is nothing to flag
  assert.ok(!("root_hidden" in revealLayout(p, "BodyOwn", "html{overflow:hidden;height:100%}body{height:100%;overflow-y:auto}", LAYOUT(ITEMS(3, 1000, "p"))).rec));
  // overflow-x:clip on the root keeps the root's own overflow out of propagation: the body's hidden is no longer the window's, and a visitor's wheel scrolls the page
  assert.ok(!("root_hidden" in revealLayout(p, "ClipXBodyHidden", "html{overflow-x:clip}body{overflow:hidden}", LAYOUT(ITEMS(3, 1000, "p"))).rec));
  // an ordinary page gets no note
  const plain = revealLayout(p, "NotHidden", "", LAYOUT(ITEMS(3, 1000, "p")));
  assert.ok(!("root_hidden" in plain.rec) && !/NOTE/.test(plain.r.stdout), plain.r.stdout);
});

test("capture --reveal: a page that stops answering during the walk stops capture at once: exit 1, nothing written", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // the page's script never ends once the page has been scrolled
  const page = writeMoving(p, "rounds/r1/Hung", CSS + "body{margin:0}", LAYOUT(`${ITEMS(4, 1000, "p")}<script>addEventListener('scroll',()=>{for(;;);},{once:true})</script>`));
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", "--timeout", "1000"]);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stdout + r.stderr, /the page stopped answering during the --reveal walk; nothing was written/);
  assert.ok(!fs.existsSync(path.join(p, "rounds/r1/Hung/shots")), "no still and no capture.json");
});

test("capture --reveal: a page that pulls itself back to the top: NOT SCROLLED after one step, never a page longer than 40 screens", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Lock", "", LAYOUT(`${ITEMS(3, 1000, "p")}<script>addEventListener('scroll',()=>scrollTo({top:0,behavior:'instant'}))</script>`));
  assert.deepEqual(rec, { steps: 1, capped: false, not_scrolled: true });
  assert.match(r.stdout, /NOT SCROLLED: a scroller did not stay where it was scrolled to/);
  assert.ok(!/CAPPED/.test(r.stdout), r.stdout);
});

test("capture --reveal: reveal scripts with a margin (rootMargin -100px, and 0px 0px -20% 0px): half-screen steps show every item inside the margin", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  // 60 items of 120 px, then a 300 px footer no script watches, so that the last item can reach the part of the screen the margin leaves
  for (const [name, margin] of [["Margin100", "-100px"], ["MarginBottom20", "0px 0px -20% 0px"]]) {
    const { rec, shots } = revealLayout(p, name, SEEN_HEADER, LAYOUT(`<header class=seen-bar></header>${ITEMS(60, 120)}${ITEMS(1, 300, "f")}${SEEN_SCRIPT(60, `{rootMargin:"${margin}"}`)}`));
    assert.deepEqual(rec, { steps: 16, capped: false }, name);
    assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, `${name}: all 60 items were seen at 1440`);
    assert.ok(redPixels(path.join(shots, "390-light.png")) > 390 * 50 * 0.9, `${name}: all 60 items were seen at 390`);
  }
});

test("capture --reveal: chat box scrolled to its end on load: walked from its top, then put back at its end, never 'nothing to scroll'", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Chat", SEEN_HEADER + ".chat{height:600px;overflow-y:auto;margin-top:50px}",
    LAYOUT(`<header class=seen-bar></header><div class=chat>${ITEMS(19, 200)}<div class=i style="height:200px;background:#c03"></div></div>`
      + `<script>const c=document.querySelector('.chat');c.scrollTop=c.scrollHeight</script>${SEEN_SCRIPT(20)}`));
  assert.deepEqual(rec, { steps: 12, capped: false, boxes: 1, box_steps: 12 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 250 * 0.9, "all 20 messages were seen, and the chat is back at its end (its last, red message shown)");
  assert.ok(!/nothing to scroll/.test(r.stdout), r.stdout);
});

test("capture --reveal: a banner that collapses once it is above the screen: the window is not pulled back (scroll anchoring off for the walk), so the page is walked to its end", (t) => {
  if (needSetup(t)) return;
  // a 600 px banner that collapses once the page is past 700 px: with scroll anchoring on, the browser pulls the window back by 600 px, which reads as "the page moved it back"
  const { rec, shots } = revealLayout(makeProject(), "Banner", SEEN_HEADER + ".banner{height:600px}.banner.gone{height:0}",
    LAYOUT(`<header class=seen-bar></header><div class=banner></div>${ITEMS(4, 1000)}<script>addEventListener('scroll',()=>{if(scrollY>700)document.querySelector('.banner').classList.add('gone')})</script>${SEEN_SCRIPT(4)}`));
  assert.deepEqual(rec, { steps: 8, capped: false });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all four sections were seen");
});

test("capture --reveal: a page whose IntersectionObserver never answers: the box is not walked, the run says so, and nothing hangs", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "NoObserver", ".b{height:600px;overflow-y:auto}",
    LAYOUT(`<div class=b>${ITEMS(6, 400)}</div>${ITEMS(1, 2000, "p")}<script>window.IntersectionObserver=class{observe(){}unobserve(){}disconnect(){}}</script>`));
  assert.deepEqual(rec, { steps: 5, capped: false, boxes_unmeasured: 1 });
  assert.match(r.stdout, /NOT MEASURED: the page's IntersectionObserver did not answer for 1 box that scrolls/);
});

test("capture --reveal: a box slotted into a shadow scroller (a web-component layout): walked, and the shadow scroller is put back at its top", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "Shadow", ".panel{height:600px;overflow-y:auto}",
    LAYOUT(`<x-layout>${RED_BAND}<div style="height:1400px"></div><div class=panel>${ITEMS(6, 400)}</div></x-layout>`
      + `<script>customElements.define('x-layout',class extends HTMLElement{constructor(){super();this.attachShadow({mode:'open'}).innerHTML='<div style="height:100vh;overflow-y:auto"><slot></slot></div>'}})</script>`));
  assert.deepEqual(rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 100 * 0.9, "the first screen shows the top of the shadow scroller");
});

test("capture --reveal: a column-reverse box (a chat, scrollTop 0 at its end and negative above) is walked from its top to its end, so every item is seen", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Chat", SEEN_HEADER + ".chat{height:600px;margin-top:50px;overflow-y:auto;display:flex;flex-direction:column-reverse}.chat .i{flex:none}",
    LAYOUT(`<header class=seen-bar></header><div class=chat>${ITEMS(20, 200)}</div>${SEEN_SCRIPT(20)}`));
  assert.ok(rec.boxes === 1 && rec.box_steps > 0, JSON.stringify(rec));
  assert.doesNotMatch(r.stdout, /holds no box that scrolls/);
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all 20 items of the chat were seen in the viewport");
});

test("capture --reveal: a column-reverse box the page scrolled to its oldest item on load is still walked", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "ChatOldest", SEEN_HEADER + ".chat{height:600px;margin-top:50px;overflow-y:auto;display:flex;flex-direction:column-reverse}.chat .i{flex:none}",
    LAYOUT(`<header class=seen-bar></header><div class=chat>${ITEMS(20, 200)}</div>${SEEN_SCRIPT(20)}<script>document.querySelector('.chat').scrollTop=-99999</script>`));
  assert.ok(rec.boxes === 1 && rec.box_steps > 0 && !rec.not_scrolled, JSON.stringify(rec));
  assert.doesNotMatch(r.stdout, /NOT SCROLLED/);
});
