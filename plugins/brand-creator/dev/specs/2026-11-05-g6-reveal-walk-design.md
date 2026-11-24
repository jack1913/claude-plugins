# G6 design: the `capture --reveal` walk

Design date 2026-11-05. Release target: brand-creator 0.9.0. This is a working file, not a doc. It lives in `dev/specs/` while the
work runs and moves to `docs/archive/` when it ships. It holds no personal path and no client name.

Status: designed, reviewed once, and revised (see "Review" at the end). The reference implementation was run in Chromium 149 (the
plugin's own, through playwright-core) at 1440 x 900 and 390 x 844. Nothing here is in the code yet. Appendix A is the proposed code
and Appendix B the proposed tests, each exactly as it was run.

## Why

`capture <page> --reveal` must scroll a page so that what it reveals on scroll is in the stills, then bring everything back so that
the first screens show the top. 0.8.0 shipped a walk that is wrong on real layouts. Four redesigns were rejected after review, and
the first version of this design was revised after its own review:

| Walk | What went wrong |
| --- | --- |
| 0.8.0 / 0.8.1 (shipped) | Walks the window, or the largest shown box when the window cannot scroll. Misses a body that scrolls itself (0 steps) and still prints success. Walks a closed drawer instead of `main`. Walks 40 times a page that moves itself back, and calls it "longer than 40 screens". Its screen-sized steps skip items that a reveal script watches with a margin. |
| Design A | Chose the "best" scroller again at every step: switched into a code box mid-walk and left an outer box scrolled. |
| Design B | Chose one scroller once, with a 0.8-of-the-screen rule: missed a `main` under a 220 px header, and a sticky sidebar beside a scrolling window. |
| Design C | Window, then every big box, found with a 1 px test scroll and one shared 40-step cap: snap points and `scroll-behavior: smooth` undid the 1 px test, and boxes that used up the cap were reported as "the page is longer than 40 screens". |
| Design D | Instant test scroll and a separate 20-step box budget: a box in the first screen was walked while the window was still at the page's bottom, so a viewport `IntersectionObserver` never saw its items. Its line "N steps at most, of 40 allowed" was false, because N counted box steps under the other budget. |
| This design, first version | Screen-sized steps (items inside a reveal margin skipped); a box over two screens tall had a band never on screen; a box the page had scrolled (a chat at its end) got 0 steps and "nothing to scroll"; scroll anchoring read as "the page moved it back"; the page's `IntersectionObserver` was awaited with no bound (a hang); a slotted box's shadow scroller was left scrolled; a small list in a closed menu was counted. |

Three more faults turned up while the first version was tested. They are in 0.8.1 and in D:

- With `--wait 0` the walk does not wait for a frame after a step. The page's `IntersectionObserver` callbacks and scroll handlers
  may not have run before the next step or the return. The probe showed random misses in 0.8.1 and D at `--wait 0`.
- A box taller than the screen is stepped by its own height, so the parts below the screen are never in the viewport.
- A box that the page's own walk reveals (opacity 0 until seen) is not found, because D looks for boxes before the walk.

## 1. The walk

### Words

- **The window** is the page's own scroller (`document.scrollingElement`). It is walked when its content is taller than it. This
  includes a root with `overflow: hidden`, and a root with `overflow: clip`, which Chromium applies as `hidden` on the viewport
  (CSS Overflow 3). A script can scroll both, so both are walked, as in 0.8.
- **A box** is an element that scrolls on its own. It has `overflow-y` of `auto`, `scroll` or `overlay`, content taller than its
  client height, and it is shown (`checkVisibility` with visibility, opacity and `content-visibility: auto`). It must also move
  when scrolled: an instant test scroll to its end (or its top), put back at once. The body counts as a box only when its overflow
  is its own: when the root's overflow is not `visible`. Otherwise the body's overflow belongs to the window (propagation), and
  `overflow-x: hidden` only makes its `overflow-y` compute to `auto`.
- **A small box** is a box under half the screen's height (`CAPTURE_REVEAL_BOX_MIN = 0.5`), such as a code block or a short list.
  It is counted, not walked, and only when it is ever on the screen (see below).
- **What the screen shows** of a scroller: for the window, its client height; for a box, the height of the `intersectionRect` a
  viewport `IntersectionObserver` reports once the box is put on the screen (at most its client height).
- **A step** moves one scroller down by half of what the screen shows of it (`CAPTURE_REVEAL_STEP = 0.5`), and is followed by the
  settle below.
- **The scrollers around** an element are its ancestors in the flat tree (a slotted element's slot, a shadow root's host) whose
  overflow is not `visible`.

### Why half a screen

Reveal scripts often watch with a margin or a threshold: Framer Motion's `viewport={{ margin: "-100px" }}`,
`rootMargin: "0px 0px -20% 0px"`, `threshold: 0.6`. The part of the screen the script watches is then smaller than the screen. With
screen-sized steps, an item that sits in the part left out at one step is above the screen at the next, and is never revealed. The
review's probe showed 52 of 60 items at 390 px with a -20 % bottom margin, and 56 of 60 at 1440 px with -100 px (rows 29 to 31 in
the table show the same for 0.8.1 and D).

With steps of `s`, every item passes every band of the screen that is taller than `s` minus the item's height. So an item of height
`H` is seen at some step when `band + H x (1 - 2t) > s`, where `band` is the screen's height minus the script's margins and `t` is
its threshold. With `s` = half a screen this holds for any margins that leave more than half the screen, at any threshold up to
0.5, and above 0.5 for items not much taller than the screen (`t = 0.6`: items under 2.5 screens). It costs twice the steps.

### Order, and where the window is

1. **The window.** If it is not at its top (a page that scrolls itself on load), it is put there and the page settles (no step).
   Then it is walked down to its end, one step at a time.
2. **The boxes**, found after step 1, so a box that the window's walk revealed is among them. They are walked in document order, so
   an outer box comes before the boxes inside it. After each box the boxes are found again, and a box seen for the first time joins
   the ones still to walk, in document order. For each box:
   - **Put at its top and on the screen.** `box.scrollTo(0)`, then
     `box.scrollIntoView({block: "start", inline: "nearest", behavior: "instant"})`, which scrolls the window and every scroller
     around the box until its top is at the top of the screen, or as near as they go. So a box that the page had scrolled (a chat
     at its end) is walked from its top, and while a box is walked the window is where that call put it, never where the window's
     walk left it (D's fault). Every scroller around the box is noted, to be put back. The page then settles (no step).
   - **What the screen shows of it** is measured. If that rect has no width, the box only touches the screen's edge (a drawer moved
     off with `transform`). Such a box is off the screen however the page is scrolled: it is not walked and not counted.
   - **Walked** from its top to its end, in steps of half of what the screen shows of it.
   - **Carried up.** At its end, while its bottom edge is not on the screen (a box taller than the screen), the nearest scroller
     around it that still carries it up (the window last) is scrolled down by the same step, and the page settles. These are steps:
     they count in `box_steps` and in the budget. So a box over two screens tall is seen whole: inside it, the walk showed its
     content down to its end minus what lies below the screen, and carrying it up shows that last part. (The first version put the
     box once by its bottom instead, which left a band of a box over two screens tall never on screen.)
   - **Counted** in `boxes` once it took a step.
3. **The small boxes.** Each is put on the screen in the same way and measured. It is counted (`small_boxes`) only when the rect has
   width and height, so a short list in a closed menu is not counted. Past the budget, the small boxes left are counted untested.
4. **The return.** Every box and every scroller around a box goes back to where the walk found it, and so does the window: the top,
   on a page that does not scroll itself on load; a chat box goes back to its end. The pinned styles are put back, then the page
   settles once more. Then each of those scrollers is checked: one not where it was put (a script moved it) sets `not_returned`.

### The settle after each step

Two animation frames and a task (`requestAnimationFrame` twice, then `setTimeout 0`): by then the page's scroll events,
`IntersectionObserver` callbacks and what they append have run. If the page's frames do not come within
`CAPTURE_REVEAL_ANSWER_MS = 1000`, the walk goes on. Then `--wait`, then the animations that end (`waitAnimations`, at most 15 s),
as after load. A placement and the return get the same settle.

### Snapping, smooth scrolling and scroll anchoring

- Every scroll the walk makes is `behavior: "instant"`, which overrides `scroll-behavior: smooth` on the root or on a box.
- For the walk, the root, every box found and every scroller around a placed box are pinned: the inline
  `scroll-snap-type: none !important` (when its computed value is not `none`) and `overflow-anchor: none !important`. Each step then
  lands where it was sent, and the test scroll cannot be snapped back (C's fault). Without anchoring, content that shrinks above the
  screen after a step (a banner that collapses once scrolled past, a bar that hides) does not pull the scroller back, so the walk
  does not read it as "the page moved it back" (the first version's fault: 1 step and NOT SCROLLED; row 42).
- At the end each property is put back, or removed when it was not inline before. When the page did not change that inline style
  meanwhile, the `style` attribute goes back letter for letter, or is removed when there was none. Chromium writes an inline style
  back to the attribute lazily, so the attribute is read before it is removed: without that read, `style=""` comes back.

### Budgets, timeout, and a page that does not answer

- **One step budget for a load:** `CAPTURE_REVEAL_MAX_STEPS = 80` steps, the window's and the boxes' together. 80 half screens are
  40 screens, the reach of 0.8. The window goes first, so it is never cut by boxes, and a capped window really is longer than 40
  screens. The placements, the test scrolls and the small-box tests are not steps.
- **Time:** the whole walk of one load stops once it has taken `--timeout` ms. The check comes before every step, every placement,
  every carry step and every small-box test.
- **A page that does not answer.** The page's `IntersectionObserver` gets 1 s to answer a measure. A box it does not answer for is
  not walked, and is counted in `boxes_unmeasured`. Every call into the page also runs under `withTimeout`: the time left of
  `--timeout`, plus `CAPTURE_REVEAL_GUARD_MS = 15 s + 5 s`, longer than any settle. A call that runs out (a script that never ends)
  stops the walk: `capped`, `timed_out`, `not_returned`, and the scroller being walked is unfinished. The page is left where it is,
  since it does not answer. The run goes on to the stills, which then fail as they would for any hung page (row 41).
- When the steps or the time run out, the walk stops where it is. The record says whether the page was left before its end
  (`page_unfinished`), and how many boxes were left before theirs (`boxes_unfinished`: the box being walked and every box found but
  not yet walked).

### A page that grows, and one that does not move

- **Grows.** Each scroller's height is read again before every step, so content appended at the end (infinite scroll) is followed
  until it stops or the budget ends. A height larger than at the start sets `grew`.
- **Does not move.** A step that does not move the scroller, or after whose settle the scroller is back where it was or above (the
  page moved it), ends that scroller's walk and sets `not_scrolled`. That is never reported as a long page (0.8.0's fault).

### What the walk changes on the page while it runs

Positions (put back); each box at its top before its walk (put back); the inline `scroll-snap-type` and `overflow-anchor` above (put
back); a state object under `Symbol.for("brand-creator.reveal")` on `window` (deleted at the end); one instant test scroll of each
box (put back in the same task); one `IntersectionObserver` per measure (disconnected). The functions run through `page.evaluate`, by
the browser's debugger protocol, so a page whose Content-Security-Policy forbids eval is walked too (row 27).

## 2. The record and the line

### `capture.json` `reveal`

The four loads are merged: the most of each count, and any of each flag. Keys come in a fixed order, and an optional key is
written only when it says something. An unchanged page gives the same record (see "Byte-stable" below).

| Key | Written | Meaning |
| --- | --- | --- |
| `steps` | always | the most steps a load took, the window's and the boxes' together (at most 80) |
| `capped` | always | a load stopped at the 80 steps, at `--timeout`, or because the page stopped answering, before every scroller it found reached its end |
| `timed_out` | when true | that stop was the time (`--timeout`, or a page that stopped answering) |
| `page_unfinished` | when true | the window was not at its end when the walk stopped |
| `boxes` | when > 0 | the most boxes a load walked (at least one step each, to its end or not) |
| `box_steps` | with `boxes` | the most steps a load took inside boxes and carrying them up |
| `boxes_unfinished` | when > 0 | the most boxes a load left before their end (cut, or never reached) |
| `boxes_unmeasured` | when > 0 | the most boxes a load could not measure (the page's `IntersectionObserver` did not answer): not walked, or not carried up |
| `small_boxes` | when > 0 | the most small boxes (under half a screen tall) on the screen a load found: not walked |
| `grew` | when true | the page or a box grew while it was walked, and the walk followed it |
| `not_scrolled` | when true | a scroller did not move, or did not stay where it was scrolled to |
| `not_returned` | when true | after the walk, a scroller was not where the walk put it back, or the page stopped answering and was not put back |

`inner_scroller` (0.8) is gone: `boxes` says more. The 0.8 keys `steps`, `capped`, `timed_out` and `not_scrolled` keep their names.
`capped` now covers the boxes as well as the page; `page_unfinished` says when the page itself is cut.

### The printed line

One line, `  reveal: ...`, made of a head and clauses joined by `; `. Every clause is true of the merged record, and a count is
"at most" or "up to" because it is the most of the four loads. Real output of the reference run:

| Outcome | Line or clause (layout row) |
| --- | --- |
| nothing to scroll | `reveal: nothing to scroll: in every load the page fits its screen and holds no box that scrolls` (2) |
| nothing to scroll, a list in a closed menu | `reveal: nothing to scroll: in every load the page fits its screen and holds no box that scrolls` (36) |
| walked to the end | `reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen (10 steps at most, of 80 allowed)` (1) |
| with boxes | `reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen (15 steps at most, of 80 allowed; up to 6 of them inside 1 box that scrolls, each with the page scrolled to show it)` (18) |
| small boxes | `reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen (7 steps at most, of 80 allowed); 1 box under half a screen tall that scrolls (a code block, a short list) was not walked, so what it reveals on scroll is not shown` (14) |
| grew | `reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen (28 steps at most, of 80 allowed); the page or a box grew as it was scrolled (content added at its end), and the walk followed it` (21) |
| page cut at 80 steps | `reveal: before the stills, each load was scrolled down and back in steps of at most half a screen (80 steps at most, of 80 allowed); the page or a box grew as it was scrolled (content added at its end), and the walk followed it; CAPPED: the page is longer than 40 screens, so what lies below the walk was not revealed` (22) |
| boxes cut at 80 steps | `reveal: before the stills, each load was scrolled down and back in steps of at most half a screen (80 steps at most, of 80 allowed; up to 73 of them inside 4 boxes that scroll, each with the page scrolled to show it); CAPPED: the page and its boxes needed more than 80 steps, so what lies further down in 5 boxes that scroll was not revealed` (17) |
| timeout | `reveal: before the stills, each load was scrolled down and back in steps of at most half a screen (1 step at most, of 80 allowed); CAPPED: a walk took longer than --timeout and stopped before the end of the page and 1 box that scrolls, so what lies past where it stopped was not revealed` (40) |
| not measured | `reveal: before the stills, each load was scrolled down and back in steps of at most half a screen (5 steps at most, of 80 allowed); NOT MEASURED: the page's IntersectionObserver did not answer for 1 box that scrolls, so what lies further down in it may not be revealed` (37) |
| not scrolled | `reveal: before the stills, each load was scrolled down and back in steps of at most half a screen (1 step at most, of 80 allowed); NOT SCROLLED: a scroller did not stay where it was scrolled to (it does not move, or the page moved it back), so what lies below where it stopped was not revealed` (25) |
| not returned | `reveal: before the stills, each load was scrolled to the end in steps of at most half a screen (6 steps at most, of 80 allowed); NOT RETURNED: after the walk a scroller was not back where the walk found it (a script moved it, or the page stopped answering), so a first screen may not show the top` (26) |
| a page that stopped answering | `reveal: before the stills, each load was scrolled down in steps of at most half a screen (1 step at most, of 80 allowed); CAPPED: a walk took longer than --timeout and stopped before the end of the page, so what lies past where it stopped was not revealed; NOT RETURNED: after the walk a scroller was not back where the walk found it (a script moved it, or the page stopped answering), so a first screen may not show the top` (41) |

Why each is true: the 80 in "of 80 allowed" is the one budget that `steps` counts (unlike D). "The page is longer than 40 screens" is
printed only when the window itself is cut after 80 half-screen steps, and the window goes first (unlike C). "Nothing to scroll" is
printed only when no load took a step and nothing was cut, stuck or unmeasured, so a walk that did nothing never reads as a success
(unlike 0.8.0 and the first version's chat box). A box placed but cut before its first step is not in `boxes` (unlike the first
version's "up to 0 of them inside 1 box"). "And back" is left out when a scroller was not returned.

### Byte-stable

On an unchanged page every count comes from the page's geometry, so the record is the same on every run. The probe's records and
lines were byte-identical over three runs at `--wait 0` (42 of 42 rows, records and lines identical). The adapted end-to-end test still checks that a second run
writes `0 of 6 file(s)` and leaves `capture.json` byte for byte. Only `timed_out`, and with it the cut counts, depends on the
machine's speed, as in 0.8.

## 3. Layout table

How it was run: each layout is a page of fixed-height blocks. Every block with class `r` is marked `.in` the first time a viewport
`IntersectionObserver` sees it (with the margin or threshold named in rows 29 to 31), which is the usual reveal script. One load per
size (1440 x 900, 390 x 844). The probe ran the walk exactly as in Appendix A, cut out of the integrated `render.mjs`, and checked
four things against the expectation:

- the record;
- the blocks that must end `.in`, and the ones that must not (a stated limit);
- that no element (shadow trees included) and not the window is left scrolled, except where the row says so;
- that every inline `style` attribute is as before.

The expectations were written from the geometry before the run: `steps(content, shown) = ceil((content - shown - 1) / floor(shown / 2))`,
a box over the screen adds `ceil((height - screen - 1) / floor(screen / 2))` carry steps, and infinite scroll comes from a separate
model of the walk. **All 42 layouts matched their expectation at both sizes, at `--wait 0` (three runs) and at `--wait 300` (84 of 84 each).** The "0.8.1" and "D" columns are the same probe run with those walks at `--wait 300`: blocks
seen, out of all blocks. Times are per load at `--wait 300`.

| # | Layout (geometry) | Expected walk (1440 / 390) | Expected record (both sizes merged) | Reference result (seen 1440, 390; time per load) | 0.8.1 | D |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Plain long page (5000 px) | window, 10 / 10 steps | `{steps:10, capped:false}` | as expected; seen 5/5; 3.6 s | 5/5 | 5/5 |
| 2 | Plain short page (500 px) | nothing | `{steps:0, capped:false}` | as expected; seen 1/1; 0.3 s; line "nothing to scroll" | 1/1, line "scrolled ... (0 steps)" | 1/1 |
| 3 | Body that scrolls itself (`html` hidden, body 100 % auto, 3000 px) | body as a box, 5 / 6 | `{steps:6, capped:false, boxes:1, box_steps:6}` | as expected; seen 3/3; 2.3 / 2.6 s | 1/3, 0 steps, success printed | 3/3 |
| 4 | `overflow-x: hidden` body (`html, body` 100 %, 3000 px) | window, 5 / 6; body is no box | `{steps:6, capped:false}` | as expected; seen 3/3; 1.9 / 2.3 s | 3/3 | 3/3 |
| 5 | `html` overflow hidden + full-height `main` (4000 px) | main, 7 / 8 | `{steps:8, capped:false, boxes:1, box_steps:8}` | as expected; seen 4/4; 2.9 / 3.2 s | 4/4 | 4/4 |
| 6 | Scroll-snap `main`, mandatory, 4 sections of 100 % | main, 6 / 6, snapping off during the walk and back after | `{steps:6, capped:false, boxes:1, box_steps:6}` | as expected; seen 4/4; 2.6 s; style attributes as before | 4/4 | 4/4 |
| 7 | Scroll-snap `main`, proximity, 6 sections of 70 % | main, 7 / 7 | `{steps:7, capped:false, boxes:1, box_steps:7}` | as expected; seen 6/6; 2.9 s | 6/6 | 6/6 |
| 8 | `scroll-behavior: smooth` on `html` (4000 px) | window, 7 / 8 instant steps | `{steps:8, capped:false}` | as expected; seen 4/4; 2.6 / 2.9 s | 4/4 | 4/4 |
| 9 | `scroll-behavior: smooth` on the box (full-height `main`, 4000 px) | main, 7 / 8 instant steps | `{steps:8, capped:false, boxes:1, box_steps:8}` | as expected; seen 4/4; 2.9 / 3.2 s | 4/4 | 4/4 |
| 10 | `main` (100vh, auto, 3000 px) under a 60 px header | window 1 step (60 px), then main 5 / 6 | `{steps:7, capped:false, boxes:1, box_steps:6}` | as expected; seen 3/3; 2.6 / 2.9 s | 1/3 (main missed) | 3/3 |
| 11 | `main` (flex 1, auto, 3000 px) under a 220 px header, `html` hidden | main, 7 / 8 steps of 340 / 312 px | `{steps:8, capped:false, boxes:1, box_steps:8}` | as expected; seen 3/3; 2.9 / 3.2 s | 3/3 | 3/3 |
| 12 | Sticky full-height sidebar (3000 px) on a short page (500 px) | sidebar, 5 / 6 | `{steps:6, capped:false, boxes:1, box_steps:6}` | as expected; seen 4/4; 2.3 / 2.6 s | 4/4 | 4/4 |
| 13 | Sticky full-height sidebar (3000 px) on a long page (5000 px) | window 10, then sidebar 5 / 6 | `{steps:16, capped:false, boxes:1, box_steps:6}` | as expected; seen 8/8; 5.5 / 5.9 s | 6/8 (sidebar missed) | 8/8 |
| 14 | Code box (`max-height: 300px`, 6000 px) in a long page (3600 px) | window 6 / 7; code box on the screen, counted, not walked | `{steps:7, capped:false, small_boxes:1}` | as expected; seen 3/8; 2.3 / 2.6 s; code items below its first screen not seen (limit 2) | 3/8 | 3/8 |
| 15 | Nested: full-screen `main` (2100 px) holding a `max-height: 300px` list | main 3; list counted; main back at its top | `{steps:3, capped:false, boxes:1, box_steps:3, small_boxes:1}` | as expected; seen 3/7; 1.6 s; list items below its first screen not seen (limit 2) | 5/7, walked the list 16 steps, missed main's end | 3/7 |
| 16 | Closed off-canvas drawers (one `translateX(-100%)`, one `visibility: hidden`, 9000 px each) beside a full-height `main` (2000 px) | main 3; drawers not walked, not counted | `{steps:3, capped:false, boxes:1, box_steps:3}` | as expected; seen 4/20; 1.6 s; drawer items not seen | walked the drawer 9 / 10 steps, missed main's end | as expected |
| 17 | Grid of 8 tall scrolling cards (500 px, 6000 px each) above 3000 px | window 7 / 8, then cards of 22 steps each until 80 | `{steps:80, capped:true, boxes:4, box_steps:73, boxes_unfinished:5}` | as expected; seen 26/49; 27.6 s; "needed more than 80 steps" | 9/49 (no card) | 9/49, 24 steps, `boxCapped` |
| 18 | Box in the first screen (600 px, 6 items of 400 px, viewport `IntersectionObserver`) on a long page (4600 px) | window 9, then the window back up to show the box, box 6 | `{steps:15, capped:false, boxes:1, box_steps:6}` | as expected; seen 7/7; 5.5 s | 3/7 | 3/7 (the fault the review found) |
| 19 | Box taller than the screen (1400 px, 42 items of 100 px) on a long page (4400 px) | window 8 / 9; box 7 steps of 450 / 422 px, then 2 steps of the window carrying it up | `{steps:18, capped:false, boxes:1, box_steps:9}` | as expected; seen 43/43; 6.2 / 6.5 s | 16/43 | 16/43 |
| 20 | Box revealed by the page's walk (`opacity: 0` until seen) holding a 600 px panel | window 4 / 5; panel found after it, 4 steps | `{steps:9, capped:false, boxes:1, box_steps:4}` | as expected; seen 6/6; 3.2 / 3.6 s | 4/6 | 4/6 |
| 21 | Infinite scroll: 1800 px, 1800 px more each time the end is reached, 5 times | window followed to 10800 px: 22 / 28 steps | `{steps:28, capped:false, grew:true}` | as expected; seen 6/6; 7.5 / 9.4 s; also at `--wait 0` | 6/6 at 300, misses at 0 | 6/6 at 300, misses at 0 |
| 22 | Endless scroll (appends at every end) | window 80, capped | `{steps:80, capped:true, page_unfinished:true, grew:true}` | as expected; seen 1/1; 26.3 s | 40, `capped` | timed out (see note) |
| 23 | `html { overflow: clip }` (3000 px) | window 5 / 6 (Chromium scrolls it by script) | `{steps:6, capped:false}` | as expected; seen 3/3; 1.9 / 2.3 s | 3/3 | 3/3 |
| 24 | `html { overflow: hidden }` (3000 px) | window 5 / 6, as in 0.8 | `{steps:6, capped:false}` | as expected; seen 3/3; 1.9 / 2.3 s | 3/3 | 3/3 |
| 25 | A page that scrolls itself back to the top on every scroll | 1 step, then stuck | `{steps:1, capped:false, not_scrolled:true}` | as expected; seen 1/3; 0.6 s; no CAPPED | 40 steps, `capped`, "longer than 40 screens" | timed out |
| 26 | A page that jumps to 300 px when it reaches its top after being scrolled | window 5 / 6, return checked | `{steps:6, capped:false, not_returned:true}` | as expected; seen 3/3; 2.0 / 2.3 s; left at 300 px (on purpose) | left at 300 px, nothing said | left at 300 px, nothing said |
| 27 | Full-height `main` on a page whose CSP forbids eval | main 7 / 8 | `{steps:8, capped:false, boxes:1, box_steps:8}` | as expected; seen 4/4; 2.9 / 3.3 s | 4/4 | 4/4 |
| 28 | Scroll-driven animation (`animation-timeline: view()`) at the end of 3300 px | window 6 / 6; the stills show it at its top-of-page state (limit 4) | `{steps:6, capped:false}` | as expected; seen 3/3; 2.2 s | 3/3 | 3/3 |
| 29 | Reveal script with `rootMargin: "0px 0px -20% 0px"`, 60 items of 120 px | window 14 / 16 | `{steps:16, capped:false}` | as expected; seen 59/60; 4.9 / 5.5 s; the last item is never in the top 80 % of the screen, for a visitor either (limit 10) | 59/60, 52/60 | 59/60, 52/60 |
| 30 | Reveal script with `rootMargin: "-100px"`, 60 items of 120 px | window 14 / 16 | `{steps:16, capped:false}` | as expected; seen 60/60; 4.9 / 5.5 s | 56/60, 58/60 | 56/60, 58/60 |
| 31 | Reveal script with `threshold: 0.6`, 30 items of 300 px | window 18 / 20 | `{steps:20, capped:false}` | as expected; seen 30/30; 6.2 / 6.8 s | 30/30, 28/30 | 30/30, 28/30 |
| 32 | Box over two screens tall (2400 px, 60 items of 100 px) on a long page (5400 px) | window 10 / 11; box 8 / 9 steps inside, then 4 carrying it up | `{steps:24, capped:false, boxes:1, box_steps:13}` | as expected; seen 61/61; 7.8 / 8.4 s | 26/61 | 26/61 |
| 33 | Chat box (600 px, 20 items of 200 px) scrolled to its end on load | box put at its top, 12 steps, then back at its end | `{steps:12, capped:false, boxes:1, box_steps:12}` | as expected; seen 20/20; 4.5 / 4.6 s; the chat is left at its end (where it was found) | 8/20, 0 steps | 4/20, 0 steps |
| 34 | A 100vh intro that collapses on the first scroll, then 4 x 1000 px | window 7 / 8 | `{steps:8, capped:false}` | as expected; seen 4/4; 2.6 / 2.9 s; with half steps the intro is still on the screen at the first step, so it is the anchor and nothing is pulled back | 4/4 | 4/4 |
| 35 | A 900 px block 3000 px down that collapses once the page is past 3200 px, then 40 items of 100 px | window 14 / 15 | `{steps:15, capped:false}` | as expected; seen 38/41; 4.9 / 5.2 s; p2 to p4 (1440) and p0 to p2 (390) missed: limit 9 | 36/41, 38/41 | 36/41, 38/41 |
| 36 | A 300 px list inside a closed off-canvas menu, on a short page | nothing; the list is not counted | `{steps:0, capped:false}` | as expected; seen 5/11; 0.3 s; line "nothing to scroll" | 11/11: walked the closed menu's list, 3 steps | 5/11 |
| 37 | A page whose `IntersectionObserver` never answers; a 600 px box on a 2600 px page | window 4 / 5; the box not walked after 1 s | `{steps:5, capped:false, boxes_unmeasured:1}` | as expected; seen 0/7; 2.6 / 2.9 s; NOT MEASURED | 0/7, no hang (no observer used) | 0/7, no hang (no observer used) |
| 38 | A page whose `requestAnimationFrame` never calls back (3000 px) | window 5 / 6, each settle 1 s | `{steps:6, capped:false}` | as expected; seen 3/3; 7.8 / 9.1 s | 3/3 | 3/3 |
| 39 | A 600 px box slotted into a shadow scroller (100vh), after 1500 px | box 6; the shadow scroller put back | `{steps:6, capped:false, boxes:1, box_steps:6}` | as expected; seen 6/6; 2.6 s; nothing left scrolled, in the shadow tree too | 1/6 | 0/6, 0 steps |
| 40 | Every scroll starts a 5 s animation; `--timeout 3000`; a 600 px box | window 1 step, then the time is spent | `{steps:1, capped:true, timed_out:true, page_unfinished:true, boxes_unfinished:1}` | as expected; seen 3/7; 5.3 s; no "up to 0 of them inside 1 box" | not run | not run |
| 41 | A script that never ends once the page is scrolled; `--timeout 2000` | window 1 step, then given up | `{steps:1, capped:true, timed_out:true, page_unfinished:true, not_returned:true}` | as expected; 22.0 s; then a still fails after 30 s (scratch probe) | not run | not run |
| 42 | A 600 px banner at the top that collapses once the page is past 700 px (wholly above the screen by then), then 4 x 1000 px | window 7 / 8 (anchoring off: not pulled back) | `{steps:8, capped:false}` | as expected; seen 4/4; 2.6 / 2.9 s; with anchoring on: 2 steps, NOT SCROLLED, 2/4 (scratch probe) | 4/4 | 4/4 |

Note on D's times in the first version: the D run took 100 s to 1100 s on rows that take about 1 s elsewhere, and three of its walks
timed out. That looked like a stall of the machine, so D's times are not used. Its "seen" counts are.

**A finding about boxes: what a box reveals below its first screen is in no still.** Every still shows each box where it was found
(at its top), and the full page is the window's page. A page that scrolls inside `main` has a full page exactly one screen tall.
Checked end to end in the first version: a full-height `main` whose red section at its bottom is revealed by the walk gives 0 red
pixels in `1440-light.png`, `390-light.png` and `1440-light-full.png` (which is 900 px tall). So the box walk changes a still only
through page-wide effects: a class a scroll handler or an observer puts on `body` or `html` (the tests use one), a header that
changes once something was seen, a counter. The record and the line still say honestly what was walked. See owner question O1.

## 4. Tests

All in `tests/node/capture.test.mjs`. The new ones go after the test "a page longer than the walk ...". Each runs `capture --reveal
--wait 0` on one layout, so the walk's own frame wait is what is tested. Each checks the whole record with `deepEqual`, plus pixels
where a still can show the result. A box's walk is shown through a page-wide effect: once every item has been seen by a viewport
`IntersectionObserver` (with the test's margin, if any), `body` gets `.seen` and a fixed 50 px header turns red (`#c03`) in the first
screen.

**Evidence.** All 25 reveal tests (5 adapted, 20 new) pass against the integrated walk in a scratch copy of the plugin (25 pass, 0 fail, 99 s). Each rejected design's fault, and each fault the review found, was then put back into the integrated code as a
mutation, and the tests named for it were run against it: 19 of 19 were caught.

| New test (name after `capture --reveal: `) | Layout rows | Catches (mutation replayed: result) |
| --- | --- | --- |
| plain short page: nothing to scroll, and the run says so | 2 | 0.8.0's line "scrolled ... (0 steps)" on a page with nothing to walk |
| body that scrolls itself: walked as a box, never 'scrolled' with no step | 3 | 0.8.0 (0 steps, success printed). "no box when the window scrolls": caught |
| overflow-x:hidden body: its overflow is the window's, so the window is walked and no box | 4 | B (took that body for the scroller) |
| html overflow hidden + full-height main, scroll-snap (mandatory, proximity), scroll-behavior smooth (html, box): every step lands, every box back at its top | 5 to 9 | C: "1 px test scroll, snapping left on": caught. A: "a walked box left scrolled": caught |
| main under a 60 px header and under a 220 px header: the window's 60 px and the main are both walked | 10, 11 | B: "a box must be 0.8 of the screen": caught. B: "one scroller": caught. 0.8.0 (60 px header: window only) |
| sticky full-height sidebar on a short and on a long page: the sidebar and the window are both walked | 12, 13 | B: "one scroller" (above). 0.8.0: "no box when the window scrolls" (above) |
| code box with max-height in a long page, and nested full-screen main with a max-height list: the small box is counted, not walked, and every box is back at its top | 14, 15 | A (switched into the code box, left main scrolled): "a walked box left scrolled" (above) |
| closed off-canvas drawer (moved off the screen, or hidden), and a short list in a closed menu: not walked, not counted | 16, 36 | 0.8.0 (walked the drawer): "no off-screen test": caught. Review 7: "small boxes with no off-screen test": caught |
| grid of 8 tall scrolling cards: the walk stops at 80 steps and names the boxes it did not finish, never a long page | 17 | C: "every cap called 'the page is longer than 40 screens'": caught. D's line (checks "80 steps at most, of 80 allowed; up to 73 of them inside 4 boxes") |
| box in the first screen whose items reveal by a viewport IntersectionObserver, on a long page: walked with the page scrolled back to show it | 18 | D: "box walked with the window where the page walk left it": caught |
| box taller than two screens: walked in half-screen steps, then carried up by the page until its bottom is shown, so every item is seen | 19, 32 | Review 2 (first version's single bottom placement): "not carried up after its end": caught. "stepped by half its own height": caught. (0.8.1 and D: row 32) |
| a box that the page's walk reveals (opacity 0 until seen) is found after it and walked | 20 | D: "boxes chosen before the page's walk": caught |
| infinite scroll that appends on reaching the end: followed to its end with --wait 0, and the record says it grew | 21 | 0.8.0 and D: "no frame wait after a step": caught |
| html overflow:clip: Chromium scrolls the root by script (clip on the root is hidden on the viewport), so the page is walked | 23 | None of them: it pins the clip behaviour of the browser this ships with |
| a page that pulls itself back to the top: NOT SCROLLED after one step, never a page longer than 40 screens | 25 | 0.8.0 (40 steps, "longer than 40 screens"): "a page that moves itself back is walked to the cap": caught |
| reveal scripts with a margin (rootMargin -100px, and 0px 0px -20% 0px): half-screen steps show every item inside the margin | 29, 30 | Review 1 and 0.8.1: "screen-sized steps": caught |
| chat box scrolled to its end on load: walked from its top, then put back at its end, never 'nothing to scroll' | 33 | Review 3: "a box walked from where the page left it": caught |
| a banner that collapses once it is above the screen: the window is not pulled back (scroll anchoring off for the walk), so the page is walked to its end | 42 | Review 4: "scroll anchoring left on": caught |
| a page whose IntersectionObserver never answers: the box is not walked, the run says so, and nothing hangs | 37 | Review 5: "the page's IntersectionObserver awaited with no bound": caught |
| a box slotted into a shadow scroller (a web-component layout): walked, and the shadow scroller is put back at its top | 39 | Review 6: "the scrollers around a box by parentElement only": caught |

Changes to the five existing reveal tests:

- "a section that appears only when scrolled into view ...": the line regex becomes
  `/reveal: before the stills, each load was scrolled to the end and back in steps of at most half a screen/`.
- "a page that scrolls inside an element ...": `inner_scroller === true` becomes `boxes === 1`, and the regex
  `/scrolls inside an element/` becomes `/inside 1 box that scrolls/`.
- "a page longer than the walk ...": the record becomes `{steps: 80, capped: true, page_unfinished: true}`, and the regex becomes
  `/CAPPED: the page is longer than 40 screens/`.
- "the walk waits at every step ..." and "a walk that takes longer than --timeout ...": unchanged; both pass.

Rows with no test of their own: 1, 22 and 24 are covered by the existing tests (the late section, the long page, the
`overflow: hidden` page). Rows 26 to 28 are probe-only: `not_returned` needs a page built to cheat, CSP is a property of
`page.evaluate`, and scroll-driven animations are a stated limit. Row 31 (threshold) is the same fault as rows 29 and 30. Row 34 is the reviewer's intro, which half steps already pass with anchoring on; row 42's test covers anchoring. Row 35 is a
stated limit. Row 38 (no frames) costs 1 s per step. Row 40 (timeout line) is close to the existing timeout test. Row 41 (a page that
never answers) takes over 20 s per load and then fails the stills, so it stays a probe.

**The mutation ledger.** `tests/mutation_ledger.py` runs pytest ids only, and these are node tests. Either the ledger learns node
test names (`node --test --test-name-pattern`), or the mutations are replayed once by hand during G6. Their old and new texts are in
Appendix C. The ledger takes one exact `old` and one `new` text per entry, and every one of these fits that.

## 5. Docs

### `scripts/CONTRACT.md`, the Reveal paragraph (replaces the current list item; its first line keeps the `- `)

> **Reveal (`--reveal`).** A page that shows content on scroll (an `IntersectionObserver`, a class a scroll handler adds,
> `data-reveal`) is otherwise shot without scrolling, so the stills show what lies below the first screen unrevealed. With
> `--reveal`, in each of the four loads, after the page has settled as above and before the stills are taken, the page and every
> box that scrolls inside it are walked to their end. A step moves a scroller by half of what the screen shows of it, so a reveal
> script that watches with a margin or a threshold sees every item too. A step is followed by two frames, `--wait`, and the
> animations that end (at most 15 s), as after load. First the window, from its top down. Then the boxes, in document order: every
> shown element with `overflow-y` `auto`, `scroll` or `overlay`, content taller than itself and that moves when scrolled (the body
> only when the root's overflow is not `visible`). Boxes are found after the window's walk and again after each box. A box is put
> at its own top and on the screen (the window and the scrollers around it scrolled to show its top), walked down, and then, while
> its bottom is below the screen, carried up by the scroller around it. A box under half a screen tall (a code block, a short
> list) is counted (`"small_boxes"`), not walked. A box that is off the screen however the page is scrolled (a closed drawer, a
> list in a closed menu) is neither. Every scroll is instant, whatever the page's `scroll-behavior`, and the page's scroll snapping
> and scroll anchoring are off for the walk and put back after it. The height of each scroller is read again at every step, so a
> page that grows as it is scrolled is followed (`"grew": true`). The window and the boxes share 80 steps (40 screens) per load,
> and the walk of one load also stops after `--timeout` ms. A walk that stops before the end says where:
> `"page_unfinished": true` (the run prints `CAPPED: the page is longer than 40 screens, ...`), `"boxes_unfinished": N`
> (`CAPPED: the page and its boxes needed more than 80 steps, ...`), or `"timed_out": true` (`CAPPED: a walk took longer than
> --timeout, ...`). A box whose size the page's `IntersectionObserver` does not report within 1 s is not walked
> (`"boxes_unmeasured": N`, `NOT MEASURED: ...`), and a page that stops answering is given up 20 s after `--timeout` and left as it
> is. A scroller that does not move, or that the page moves back, ends its walk (`"not_scrolled": true`, `NOT SCROLLED: ...`), never
> called long. Then every scroller is put back where the walk found it (the top, on a page that does not scroll itself on load),
> the page settles again, and a scroller that is not there is reported (`"not_returned": true`, `NOT RETURNED: ...`). The four
> first screens and the full page then show the revealed state, with the window at its top and each box where the page had it.
> What a box reveals below its first screen is in no still: each box is shown where it was found, and the full page is the
> window's. A page whose root has `overflow: hidden` or `clip` is still walked (a script can scroll it). The record gets
> `"reveal": {"steps": <the most steps any load took>, "capped": false}`, after `full` and before `frames`, with `boxes` and
> `box_steps` when a box was walked, and each key above only when it is true or above 0. The run prints one line, `reveal: ...`,
> whose counts are the most any load had, or `reveal: nothing to scroll: ...` when there was nothing to walk. A run without
> `--reveal` writes no `reveal` key, and a run with it on an unchanged page writes the same bytes, as any other run. `--reveal` is
> a usage error (exit 2) with `--url`. Content that reveals on something other than scrolling (a click, a timer longer than
> `--wait`), scroll-driven animations (they follow the scroll, so the stills show them at the top), boxes that scroll sideways, and
> boxes inside a shadow root or an iframe are not walked; a box slotted into a shadow scroller is.

### The manual, `docs/manual/reference/what-it-makes.md` (replaces the two sentences after "photographed with `capture --reveal`")

> A page that shows content only as you scroll to it is photographed with `capture --reveal`. Claude first scrolls the page to the
> bottom and back to the top, half a screen at a time, and does the same inside any big box on the page that scrolls on its own,
> such as a main area or a sidebar. The pictures then show what a visitor sees after scrolling. If the walk stops early (more than
> 40 screens in all, or it took too long), the run and `capture.json` say where. Each box is photographed where the page shows it,
> so what a box shows further down is not in the pictures.

### Also to change in the same release

- `scripts/render.mjs`, the help text for `capture --reveal` (USAGE): "first scrolls the page and every box that scrolls inside it
  to the end and back, half a screen at a time, waiting at each step as it waits after load (at most 80 steps in all, and no longer
  than --timeout per load: a walk that stops early says where in capture.json and the run's line)". Also the header comment of the
  capture section (done in Appendix A).
- `skills/brand-creator/references/board-contract.md` and `skills/brand-creator/references/phases/07p-site-round.md`. Both say that
  `reveal.capped` true means the page is longer than 40 screens. It now means "the walk stopped before the end of the page
  (`page_unfinished`) or of some boxes (`boxes_unfinished`); the run's line says which, and the card says what was not revealed".
  Both files have uncommitted edits from other work in this tree: merge, do not overwrite.
- `CHANGELOG.md` (0.9.0, Changed): `capture --reveal` walks every box that scrolls as well as the page, in steps of half a screen
  (so reveal scripts with a margin see every item), shows each box on screen while it is walked and carries a tall box up until its
  bottom is shown, waits two frames after each step, turns scroll snapping and scroll anchoring off for the walk, says where a
  capped walk stopped, and reports a page that will not scroll, will not stay at its top, or does not answer. The budget is 80
  half-screen steps (40 screens, as before). `capture.json` `reveal` drops `inner_scroller` and gains `boxes`, `box_steps`,
  `page_unfinished`, `boxes_unfinished`, `boxes_unmeasured`, `small_boxes`, `grew` and `not_returned`.

## Stated limits

1. What a box reveals below its first screen is in no still (see the finding in section 3).
2. A small box (under half a screen tall) is counted, not walked.
3. Boxes that scroll sideways (carousels) are not walked. Neither are boxes inside a shadow root (an Ionic `ion-content`) or an
   iframe: the search does not enter them. A light-DOM box slotted into a shadow scroller is walked, and the shadow scroller the
   placement moved is put back (row 39).
4. A scroll-driven animation (`animation-timeline: scroll()` or `view()`) runs during the walk but follows the scroll, so the stills
   show it at its state for the top. A reveal that removes its class when the element leaves the view is undone by the return.
5. Content appended later than `--wait` after the end is reached (a slow fetch) is not followed.
6. A box off the screen however the page is scrolled is not walked and not counted. But after the budget runs out,
   `boxes_unfinished` counts every box found and not yet reached, and a closed drawer among them is counted; so does
   `small_boxes`, for the small boxes left untested.
7. `--timeout` is checked before every step, placement, carry step and small-box test. After it passes, the walk still finishes the
   settle in flight, then the return and its settle: each settle is at most 1 s of frames, `--wait` and 15 s of animations (row 40:
   about 5 s for `--timeout 3000`). A page that stops answering is given up `--timeout` + 20 s after the walk began (row 41: 22 s),
   and the stills that follow then fail after Playwright's 30 s (exit 1, nothing written).
8. The walk measures with the page's own `IntersectionObserver`. A polyfill measures by its own rules; one that never answers leaves
   the box unwalked and counted in `boxes_unmeasured` (row 37).
9. Steps are discrete. Content that collapses as the page is scrolled, in the middle of the page, can carry up to a step of what
   follows past the screen between two steps (row 35: 3 items of 100 px at each size; the same with scroll anchoring on, so it is
   not caused by turning anchoring off). At the top of the page the return shows what was skipped (row 34).
10. Margins and thresholds: an item is seen when `band + H x (1 - 2t)` is over half a screen (section 1). A margin that leaves half
    the screen or less, or a high threshold on an item much taller than the screen, can still miss items. The last band of a page
    under a bottom margin is never in the watched part (row 29), for a visitor either.
11. While it runs, the walk changes the page: inline `scroll-snap-type` and `overflow-anchor`, one test scroll per box, each box at
    its top before its walk, and a symbol on `window`. All are put back, but a `MutationObserver` on `style` attributes, or a scroll
    handler, sees them. When the page changes a pinned element's inline style during the walk, the properties are put back one by
    one and the attribute may be re-serialized (same declarations, other text).
12. The return puts each scroller where the walk found it. On a page that scrolls a box on load (a chat at its end), that is not the
    top. When the page moves a scroller afterwards, `not_returned` says so, but the still is taken as it is.
13. The budget is shared and the window goes first. A page of 38 screens with a scrolling sidebar leaves 6 half-screen steps for the
    sidebar.
14. Time: half steps double the steps. 80 steps take about 27.7 s per load at `--wait 300` (row 17), so about 2 minutes for the four
    loads at the cap; a 5000 px page takes 3.6 s per load (row 1), against about 2 s in the first version. See O7.

## Owner answers (2026-11-06)

The owner took the recommended answer to every question below ("all recommended"). These override the text above where they differ:

- **O1.** Keep walking boxes, as designed.
- **O2.** The record key change is fine for 0.9.0; the CHANGELOG says `capture.json` `reveal` changes (`inner_scroller` replaced by the
  eight keys).
- **O3.** Keep 0.5.
- **O4. Changed:** keep walking a root with `overflow: hidden` or `clip`, and add a clause to the printed line saying a visitor cannot
  scroll it with the wheel (record it too, as a key or a value the line reads). Test it with a table row.
- **O5.** Return each scroller where it was found, as designed.
- **O6. Changed:** a page that stops answering during the walk stops `capture` at once (exit 1, nothing written) with "the page stopped
  answering during the --reveal walk", instead of going on to fail on the stills. Limit 7 and the timeout text change to match.
- **O7.** Keep 80 steps.

## Open questions for the owner (answered above)

- **O1. Boxes in the stills.** What a box reveals below its first screen is in no still. Should 0.9.0 still walk boxes? The walk
  catches page-wide effects, and the record and line are honest about the page. Or should it only count them until `capture`
  can take a still of a page's main box (a stitched still of the box, scrolled screen by screen, as a separate item)? The design
  walks them, as the task asked.
- **O2. Record keys.** `inner_scroller` goes and eight keys come. A `capture.json` from 0.8.x changes on its first 0.9.0 run. No
  script reads these keys; only the two skill references above mention `reveal.capped`. Is the change fine as a minor release?
- **O3. The small-box line.** 0.5 of the screen is the line between walked and counted. A 400 px panel on a 900 px screen (0.44) is
  only counted. Keep 0.5?
- **O4. A root with `overflow: hidden` or `clip`.** It is walked by script, as in 0.8. A visitor cannot scroll it with the wheel, so
  the full page may show revealed content that no visitor reaches. Keep walking it, add a clause to the line, or skip it?
- **O5. Where the return goes.** The return puts each scroller where it was found, not at 0, so a page that scrolls a box on load
  keeps that position (a chat stays at its end). Is that what the first screens should show?
- **O6. A page that stops answering.** The walk gives up after `--timeout` + 20 s and the run goes on, so the stills then fail after
  30 s more. Should `capture` stop at once instead, with "the page stopped answering during the --reveal walk"?
- **O7. The cost of half steps.** Half steps reveal items inside reveal margins, at twice the steps: about 2 minutes per capture at
  the 80-step cap, and twice 0.8's time on every page. Keep 80 steps (40 screens, as in 0.8), or keep 40 steps (20 screens, the
  time of 0.8)?

## Appendix A: the proposed code (`scripts/render.mjs`)

These are the exact texts that were run in the probe and in the end-to-end tests. The constants replace the line
`const CAPTURE_REVEAL_MAX_STEPS = 40; ...` (`ANIMATION_CAP_MS` and `withTimeout` are already defined above it):

```js
const CAPTURE_REVEAL_MAX_STEPS = 80;          // --reveal: the steps one load may take, down the page and inside its boxes together (80 half screens: 40 screens); a walk that needs more stops there and capture.json says where
const CAPTURE_REVEAL_STEP = 0.5;              // --reveal: a step moves a scroller by this part of the height the screen shows of it, so an item a reveal script sees only inside a margin (rootMargin down to -50 %, threshold up to 0.5) is seen at some step
const CAPTURE_REVEAL_BOX_MIN = 0.5;           // --reveal: a box that scrolls is walked when it is at least this part of the screen's height; a smaller one (a code block) is counted, not walked
const CAPTURE_REVEAL_ANSWER_MS = 1000;        // --reveal: the longest the walk waits for the page's IntersectionObserver or its next frames before it goes on without them
const CAPTURE_REVEAL_GUARD_MS = ANIMATION_CAP_MS + 5000;   // --reveal: once --timeout has passed, a call into the page that has not answered after this long is given up (a page whose script never ends)
const CAPTURE_REVEAL_KEY = "brand-creator.reveal";   // the walk's state in the page, under Symbol.for(this), deleted at the end
```

The block replaces `revealWalk` and its doc comment (from `/** --reveal: scroll the page from the top to the bottom` to the end of
the function):

```js
// ---- in the page (each is passed to page.evaluate whole: no closure over this module)

/** The walk starts: its state on window (where each scroller was found, the inline styles it changes, the helpers below), and the root pinned for the walk. */
function inPageRevealBegin(key) {
  const S = { found: new Map(), pinned: new Map(), boxes: [], walked: 0, seen: new Set(), small: [], win: { top: scrollY, left: scrollX } };
  window[Symbol.for(key)] = S;
  // a scroller pinned for the walk: no scroll snapping (a step lands where it was sent) and no scroll anchoring (content that shrinks above the screen does not pull it back)
  S.pin = (el) => {
    if (S.pinned.has(el)) return;
    const cs = getComputedStyle(el), was = { attr: el.getAttribute("style"), css: el.style.cssText, props: [] };
    for (const prop of ["scroll-snap-type", "overflow-anchor"]) {
      if (cs.getPropertyValue(prop) === "none") continue;
      was.props.push([prop, el.style.getPropertyValue(prop), el.style.getPropertyPriority(prop)]);
      el.style.setProperty(prop, "none", "important");
    }
    S.pinned.set(el, was);
  };
  S.keep = (el) => { if (!S.found.has(el)) S.found.set(el, { top: el.scrollTop, left: el.scrollLeft }); };
  // the element around `a` in the flat tree: a slotted element's slot, a shadow root's host
  S.up = (a) => a.assignedSlot ?? a.parentElement ?? (a.parentNode instanceof ShadowRoot ? a.parentNode.host : null);
  // every element around `el` that may scroll (its overflow is not visible) is kept, to be put back, and pinned
  S.hold = (el) => {
    for (let a = S.up(el); a && a !== document.documentElement; a = S.up(a)) {
      const cs = getComputedStyle(a);
      if (cs.overflowY !== "visible" || cs.overflowX !== "visible") { S.keep(a); S.pin(a); }
    }
  };
  // what a viewport IntersectionObserver sees of `el` -> {width, height, bottom: its bottom edge is on the screen}, or null when the page's observer does not answer within `ms`
  S.see = (el, ms) => new Promise((resolve) => {
    let io = null;
    const t = setTimeout(() => { io?.disconnect(); resolve(null); }, ms);
    try {
      io = new IntersectionObserver((es) => {
        clearTimeout(t); io.disconnect();
        const e = es[es.length - 1], r = e.intersectionRect;
        resolve({ width: r.width, height: r.height, bottom: r.height > 0 && r.bottom >= e.boundingClientRect.bottom - 1 });
      });
      io.observe(el);
    } catch { clearTimeout(t); resolve(null); }
  });
  S.pin(document.documentElement);
  if (document.scrollingElement) S.pin(document.scrollingElement);
}

/** Two animation frames and a task (the page's scroll events, IntersectionObserver callbacks and what they append have run), or `ms` when the page's frames do not come. */
function inPageRevealFrames(ms) {
  return new Promise((done) => {
    const t = setTimeout(done, ms);
    try { requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => { clearTimeout(t); done(); }, 0))); } catch { /* the timer ends it */ }
  });
}

/** Where scroller `i` is (-1: the window, else the i-th box): its position, the height it shows, and its scroll height. */
function inPageRevealAt({ key, i }) {
  const S = window[Symbol.for(key)], doc = document.scrollingElement || document.documentElement, el = i < 0 ? null : S.boxes[i];
  return el ? { y: Math.round(el.scrollTop), vh: el.clientHeight, total: el.scrollHeight } : { y: Math.round(scrollY), vh: doc.clientHeight, total: doc.scrollHeight };
}

/** Scroller `i` to `top`, at once (behavior "instant" overrides the page's scroll-behavior: smooth). -> where it is now. */
function inPageRevealScroll({ key, i, top }) {
  const S = window[Symbol.for(key)], el = i < 0 ? null : S.boxes[i], o = { top, behavior: "instant" };
  if (el) el.scrollTo(o); else scrollTo(o);
  return Math.round(el ? el.scrollTop : scrollY);
}

/** The boxes that scroll, found again (after the page's walk and after each box): every element shown whose content is taller than it and that
 *  moves when scrolled (overflow-y auto, scroll or overlay; a body only when its overflow is its own, not the window's). A box new to the walk
 *  joins the boxes still to walk, in document order; one under `min` of the screen's height is a small box, put aside. -> {boxes, small}. */
function inPageRevealFind({ key, min }) {
  const S = window[Symbol.for(key)], doc = document.scrollingElement || document.documentElement, html = getComputedStyle(document.documentElement);
  const rootOwnsOverflow = html.overflowX === "visible" && html.overflowY === "visible";   // then the body's overflow is the window's (CSS Overflow 3, propagation)
  const fresh = [];
  for (const el of document.querySelectorAll("body, body *")) {
    if (S.seen.has(el) || el.scrollHeight - el.clientHeight <= 1 || !el.clientHeight) continue;
    if (!["auto", "scroll", "overlay"].includes(getComputedStyle(el).overflowY) || (el === document.body && rootOwnsOverflow)) continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true })) continue;   // not seen yet: found again later
    S.seen.add(el);
    S.keep(el); S.pin(el);
    const was = el.scrollTop, to = (top) => { el.scrollTo({ top, behavior: "instant" }); return el.scrollTop !== was; };
    const moves = to(el.scrollHeight) || to(0);   // an instant test to its end (or its top), put back at once
    el.scrollTo({ top: was, behavior: "instant" });
    if (!moves) continue;
    if (el.clientHeight < min * doc.clientHeight) S.small.push(el); else fresh.push(el);
  }
  const rest = S.boxes.splice(S.walked).concat(fresh).sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
  S.boxes.push(...rest);
  return { boxes: S.boxes.length, small: S.small.length };
}

/** Box `i` put on the screen: first at its own top, then the window and every scroller around it (in the flat tree: also the shadow scroller a slotted box
 *  sits in) scrolled at once so that its top is at the top of the screen, or as near as they go. Every scroller moved is kept, to be put back.
 *  -> {shown: the height of it a viewport IntersectionObserver sees (0: off the screen, a box that only touches its edge), measured: false when the observer did not answer} */
async function inPageRevealPlace({ key, i, ms }) {
  const S = window[Symbol.for(key)], el = S.boxes[i];
  S.walked = i + 1;
  S.hold(el);
  el.scrollTo({ top: 0, behavior: "instant" });   // a box the page had scrolled (a chat at its end) is walked from its top
  el.scrollIntoView({ block: "start", inline: "nearest", behavior: "instant" });
  const seen = await S.see(el, ms);
  return { shown: seen && seen.width >= 1 ? Math.floor(Math.min(seen.height, el.clientHeight)) : 0, measured: seen !== null };
}

/** Box `i` is at its end: is its bottom on the screen? If not (a box taller than the screen), and `move`, the nearest scroller around it that still
 *  carries it up (the window last) is scrolled down by `step`. -> "shown" (its bottom is on the screen, or nothing around it carries it up), "moved",
 *  "more" (not shown, and not to move), or "unmeasured" (the page's observer did not answer). */
async function inPageRevealOver({ key, i, step, move, ms }) {
  const S = window[Symbol.for(key)], el = S.boxes[i];
  if (!el.isConnected) return "shown";
  const seen = await S.see(el, ms);
  if (!seen) return "unmeasured";
  if (seen.bottom) return "shown";
  if (!move) return "more";
  const top = el.getBoundingClientRect().top;
  for (let a = S.up(el); a; a = S.up(a)) {
    if (a === document.documentElement) scrollBy({ top: step, behavior: "instant" });   // the window
    else if (getComputedStyle(a).overflowY === "visible" || a.scrollHeight - a.clientHeight <= 1) continue;
    else { S.keep(a); S.pin(a); a.scrollBy({ top: step, behavior: "instant" }); }
    if (el.getBoundingClientRect().top < top - 0.5) return "moved";
  }
  return "shown";
}

/** Small box `j`: put on the screen as a box is, to tell whether it is ever on it (one in a closed drawer is not). -> true: on the screen, or the observer did not answer. */
async function inPageRevealSmall({ key, j, ms }) {
  const S = window[Symbol.for(key)], el = S.small[j];
  S.hold(el);
  el.scrollIntoView({ block: "start", inline: "nearest", behavior: "instant" });
  const seen = await S.see(el, ms);
  return !seen || (seen.width >= 1 && seen.height >= 1);
}

/** The end: every box and the window back where the walk found them (their top, on a page that does not scroll itself on load), the pinned styles as they were. */
function inPageRevealEnd(key) {
  const S = window[Symbol.for(key)];
  for (const [el, at] of S.found) el.scrollTo({ top: at.top, left: at.left, behavior: "instant" });
  scrollTo({ top: S.win.top, left: S.win.left, behavior: "instant" });
  for (const [el, was] of S.pinned) {
    for (const [prop, value, priority] of was.props) if (value) el.style.setProperty(prop, value, priority); else el.style.removeProperty(prop);
    // the page did not change this inline style meanwhile: the attribute goes back letter for letter. The inline style reaches the attribute lazily
    // and re-serialized: it is read first, or a removed attribute comes back as style="".
    const now = el.getAttribute("style");
    if (el.style.cssText === was.css && now !== was.attr) { if (was.attr === null) el.removeAttribute("style"); else el.setAttribute("style", was.attr); }
  }
}

/** After the return has settled: is every scroller the walk moved still where it was found? (A page may scroll itself back.) Deletes the state. */
function inPageRevealReturned(key) {
  const S = window[Symbol.for(key)];
  delete window[Symbol.for(key)];
  const off = (a, b) => Math.abs(a - b) > 1;
  return !(off(scrollY, S.win.top) || off(scrollX, S.win.left) || [...S.found].some(([el, at]) => off(el.scrollTop, at.top) || off(el.scrollLeft, at.left)));
}

// ---- in node

/** --reveal: before the stills of one load, scroll the page and every box that scrolls inside it to the end and back, in steps of half of what the screen shows of each,
 *  waiting after each step as after load.
 *  1. The window, put at its top, then walked down (a page that grows is followed: its height is read again at every step).
 *  2. Then the boxes (found after 1, so a box the page's walk revealed is among them), in document order. Each is put at its own top and on the screen (the window and
 *     the scrollers around it scrolled to show its top), walked down, and then, while its bottom is not on the screen (a box taller than the screen), carried up by
 *     the nearest scroller around it. The boxes are found again after each box. A small box is only counted, when it is ever on the screen.
 *  3. Every scroller back where it was found, the pinned styles put back, waited for, and checked.
 *  One budget: CAPTURE_REVEAL_MAX_STEPS steps for the window and the boxes together, and `timeout` ms for the whole walk, checked before every step and every placement.
 *  Every call into the page is given up CAPTURE_REVEAL_GUARD_MS after the timeout: the walk then stops, and the page is left as it is.
 *  -> {steps, boxSteps, boxes, boxesUnfinished, unmeasured, small, capped, timedOut, pageUnfinished, grew, notScrolled, notReturned} */
async function revealWalk(page, waitMs, timeout) {
  const key = CAPTURE_REVEAL_KEY, started = Date.now(), ms = CAPTURE_REVEAL_ANSWER_MS;
  const out = { steps: 0, boxSteps: 0, boxes: 0, boxesUnfinished: 0, unmeasured: 0, small: 0, capped: false, timedOut: false, pageUnfinished: false, grew: false, notScrolled: false, notReturned: false };
  const guard = (p) => withTimeout(p, Math.max(timeout - (Date.now() - started), 0) + CAPTURE_REVEAL_GUARD_MS, "the --reveal walk");
  const ev = (fn, arg) => guard(page.evaluate(fn, arg));
  const settle = async () => { await ev(inPageRevealFrames, ms); await page.waitForTimeout(waitMs); await guard(waitAnimations(page)); };
  const spent = () => (Date.now() - started >= timeout ? "time" : out.steps >= CAPTURE_REVEAL_MAX_STEPS ? "steps" : null);
  const stop = (why) => { out.capped = true; if (why === "time") out.timedOut = true; };
  const took = (i) => { out.steps += 1; if (i >= 0) out.boxSteps += 1; };
  // one scroller from its top to its end, by CAPTURE_REVEAL_STEP of `shown` px (null: of its own height, read again at each step) -> "end" | "spent" | "stuck"
  const walkOne = async (i, shown) => {
    let first = null;
    for (;;) {
      const at = await ev(inPageRevealAt, { key, i });
      first ??= at.total;
      if (at.total > first) out.grew = true;
      if (at.y + at.vh >= at.total - 1) return "end";
      const why = spent();
      if (why) { stop(why); return "spent"; }
      const y = await ev(inPageRevealScroll, { key, i, top: Math.min(at.y + Math.max(1, Math.floor(CAPTURE_REVEAL_STEP * (shown ?? at.vh))), at.total - at.vh) });
      if (y <= at.y) return "stuck";   // it does not move when scrolled
      took(i);
      await settle();
      if ((await ev(inPageRevealAt, { key, i })).y <= at.y) return "stuck";   // the page moved it back
    }
  };
  let where = -1, found = { boxes: 0, small: 0 };   // where: what is being walked (-1: the window, i: box i, null: neither), for a call that is given up
  try {
    await ev(inPageRevealBegin, key);
    if ((await ev(inPageRevealAt, { key, i: -1 })).y > 0) { await ev(inPageRevealScroll, { key, i: -1, top: 0 }); await settle(); }   // a page loaded scrolled (an anchor) is walked from its top
    const page1 = await walkOne(-1, null);
    if (page1 === "spent") out.pageUnfinished = true;
    if (page1 === "stuck") out.notScrolled = true;
    found = await ev(inPageRevealFind, { key, min: CAPTURE_REVEAL_BOX_MIN });
    for (let i = 0; i < found.boxes; i++) {
      where = i;
      const why = spent();
      if (why) { stop(why); out.boxesUnfinished = found.boxes - i; break; }
      const { shown, measured } = await ev(inPageRevealPlace, { key, i, ms });
      if (!measured) { out.unmeasured += 1; continue; }   // the page's IntersectionObserver did not answer: not walked, and said so
      if (shown < 1) continue;   // off the screen however the page is scrolled (a closed drawer): not walked, not counted
      await settle();
      const before = out.boxSteps;
      let r = await walkOne(i, shown);
      // at its end, but its bottom may be below the screen (a box taller than the screen): the scrollers around it carry it up, step by step, until its bottom is shown
      for (const step = Math.max(1, Math.floor(CAPTURE_REVEAL_STEP * shown)); r === "end";) {
        const why = spent();
        const o = await ev(inPageRevealOver, { key, i, step, move: !why, ms });
        if (o === "more") { stop(why); r = "spent"; break; }
        if (o === "unmeasured") out.unmeasured += 1;
        if (o !== "moved") break;
        took(i);
        await settle();
      }
      if (out.boxSteps > before) out.boxes += 1;   // a box counts as walked once it took a step
      if (r === "stuck") out.notScrolled = true;
      if (r === "spent") { out.boxesUnfinished = found.boxes - i; break; }
      found = await ev(inPageRevealFind, { key, min: CAPTURE_REVEAL_BOX_MIN });
    }
    where = null;
    for (let j = 0; j < found.small; j++) if (spent() || await ev(inPageRevealSmall, { key, j, ms })) out.small += 1;   // past the budget, every small box is counted
    await ev(inPageRevealEnd, key);
    await settle();
    out.notReturned = !(await ev(inPageRevealReturned, key));
  } catch (e) {
    if (!/the --reveal walk timed out/.test(String(e?.message))) throw e;
    // the page stopped answering (a script that never ends): the walk stops, and the page is left where it is
    out.capped = out.timedOut = out.notReturned = true;
    if (where === -1) out.pageUnfinished = true; else if (where !== null) out.boxesUnfinished = found.boxes - where;
  }
  return out;
}

// ---- the record and the line (captureProjectPage)

/** The four loads' walks, merged: the most of each count, any of each flag. */
function mergeReveal(a, w) {
  if (!a) return { ...w };
  const m = {};
  for (const k of Object.keys(w)) m[k] = typeof w[k] === "number" ? Math.max(a[k], w[k]) : a[k] || w[k];
  return m;
}

/** capture.json's `reveal`, keys in a fixed order, the optional ones only when they say something. */
function revealRecord(r) {
  return {
    steps: r.steps, capped: r.capped,
    ...(r.timedOut ? { timed_out: true } : {}),
    ...(r.pageUnfinished ? { page_unfinished: true } : {}),
    ...(r.boxes ? { boxes: r.boxes, box_steps: r.boxSteps } : {}),
    ...(r.boxesUnfinished ? { boxes_unfinished: r.boxesUnfinished } : {}),
    ...(r.unmeasured ? { boxes_unmeasured: r.unmeasured } : {}),
    ...(r.small ? { small_boxes: r.small } : {}),
    ...(r.grew ? { grew: true } : {}),
    ...(r.notScrolled ? { not_scrolled: true } : {}),
    ...(r.notReturned ? { not_returned: true } : {}),
  };
}

const revealCount = (k, one, many) => `${k} ${k === 1 ? one : many}`;

/** The one line the run prints for the walk. Every clause is true of the merged record: a count is the most any load had. */
function revealLine(r) {
  const max = CAPTURE_REVEAL_MAX_STEPS, screens = Math.round(max * CAPTURE_REVEAL_STEP), boxes = (k) => revealCount(k, "box that scrolls", "boxes that scroll");
  const done = !r.capped && !r.notScrolled && !r.unmeasured;
  const head = r.steps === 0 && done
    ? `reveal: nothing to scroll: in every load the page fits its screen and holds no box that scrolls${r.small ? " and is at least half a screen tall" : ""}`
    : r.steps === 0 ? "reveal: no step was taken"
    : `reveal: before the stills, each load was scrolled ${done ? "to the end" : "down"}${r.notReturned ? "" : " and back"} in steps of at most half a screen (${revealCount(r.steps, "step", "steps")} at most, of ${max} allowed`
      + (r.boxes ? `; up to ${r.boxSteps} of them inside ${boxes(r.boxes)}, each with the page scrolled to show it` : "") + ")";
  const parts = [head];
  if (r.grew) parts.push("the page or a box grew as it was scrolled (content added at its end), and the walk followed it");
  const left = [r.pageUnfinished ? "the page" : null, r.boxesUnfinished ? boxes(r.boxesUnfinished) : null].filter(Boolean).join(" and ");
  if (r.timedOut) parts.push(`CAPPED: a walk took longer than --timeout and stopped before the end of ${left || "a scroller"}, so what lies past where it stopped was not revealed`);
  else if (r.pageUnfinished) parts.push(`CAPPED: the page is longer than ${screens} screens, so what lies below the walk was not revealed` + (r.boxesUnfinished ? `, nor what lies further down in ${boxes(r.boxesUnfinished)}` : ""));
  else if (r.capped) parts.push(`CAPPED: the page and its boxes needed more than ${max} steps, so what lies further down in ${boxes(r.boxesUnfinished)} was not revealed`);
  if (r.unmeasured) parts.push(`NOT MEASURED: the page's IntersectionObserver did not answer for ${boxes(r.unmeasured)}, so what lies further down in ${r.unmeasured === 1 ? "it" : "them"} may not be revealed`);
  if (r.small) parts.push(`${revealCount(r.small, "box", "boxes")} under half a screen tall that ${r.small === 1 ? "scrolls" : "scroll"} (a code block, a short list) ${r.small === 1 ? "was" : "were"} not walked, so what ${r.small === 1 ? "it reveals" : "they reveal"} on scroll is not shown`);
  if (r.notScrolled) parts.push("NOT SCROLLED: a scroller did not stay where it was scrolled to (it does not move, or the page moved it back), so what lies below where it stopped was not revealed");
  if (r.notReturned) parts.push("NOT RETURNED: after the walk a scroller was not back where the walk found it (a script moved it, or the page stopped answering), so a first screen may not show the top");
  return "  " + parts.join("; ");
}
```

In `captureProjectPage`, three places change:

```js
// the merge of the four loads (was: const walk = ...; reveal = { steps: Math.max(...), ... })
          reveal = mergeReveal(reveal, await revealWalk(page, waitMs, timeout));
// the record (was: ...(reveal ? { reveal: { steps: reveal.steps, capped: reveal.capped, ... } } : {}),)
    ...(reveal ? { reveal: revealRecord(reveal) } : {}),
// the line (was: if (reveal) { console.log(`  reveal: each page was scrolled ...`) })
  if (reveal) console.log(revealLine(reveal));
```

The header comment of the capture section:

```js
//   capture <page.html> --reveal      before each still, the page and every box that scrolls inside it are scrolled to their end in steps of half a screen (waiting at each as after load)
//                                     and back, so that what they reveal on scroll is shown; at most CAPTURE_REVEAL_MAX_STEPS steps in all, and capture.json records the walk (revealWalk).
```

## Appendix B: the proposed tests (`tests/node/capture.test.mjs`)

They go after the test "capture --reveal: a page longer than the walk ...". They use the file's own `CSS`, `writeMoving`, `record`,
`redPixels`, `bc`, `makeProject` and `needSetup`.

```js
// ---------------------------------------------------------------- capture --reveal: the walk of 0.9.0 (dev/specs/2026-11-05-g6-reveal-walk-design.md), one test per layout
// Each page is walked with --wait 0 (the walk itself waits two frames after each step). The record is checked whole: its counts are those of the layout's geometry
// (a step is half of what the screen shows of a scroller: 450 px at 900, 422 px at 844). Box content below a box's first screen is in no still (each box is shown
// at its top), so a box's walk is seen through a page-wide effect: once every item has been seen by a viewport IntersectionObserver (with the options given), body
// gets .seen and the fixed 50 px header turns red (#c03) in the first screen.

const LAYOUT = (body) => `<!doctype html><html><head><meta charset=utf-8><title>Ledger, a layout</title><link rel=stylesheet href=style.css></head><body>${body}</body></html>`;
const ITEMS = (n, h, cls = "i") => `<div class=${cls} style="height:${h}px"></div>`.repeat(n);
const SEEN_HEADER = "header.seen-bar{position:fixed;top:0;left:0;right:0;height:50px;z-index:1}body.seen header.seen-bar{background:#c03}";
const SEEN_SCRIPT = (n, options = "{}") => `<script>let seen=0;const o=new IntersectionObserver((es)=>es.forEach((e)=>{if(e.isIntersecting){o.unobserve(e.target);if(++seen===${n})document.body.classList.add('seen')}}),${options});document.querySelectorAll('.i').forEach((e)=>o.observe(e))</script>`;
const RED_BAND = "<div style='height:100px;background:#c03'></div>";

/** capture --reveal --wait 0 of one layout -> {r: the run, rec: capture.json's reveal, shots: the folder}. */
function revealLayout(p, name, css, html, more = []) {
  const page = writeMoving(p, `rounds/r1/${name}`, CSS + "body{margin:0}" + css, html);
  const r = bc(["capture", page, "--project", p, "--reveal", "--wait", "0", ...more]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const shots = path.join(p, `rounds/r1/${name}/shots`);
  return { r, rec: record(shots).reveal, shots };
}

test("capture --reveal: plain short page: nothing to scroll, and the run says so", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Short", "", LAYOUT(ITEMS(1, 500, "p")));
  assert.deepEqual(rec, { steps: 0, capped: false });
  assert.match(r.stdout, /reveal: nothing to scroll: in every load the page fits its screen and holds no box that scrolls/);
});

test("capture --reveal: body that scrolls itself: walked as a box, never 'scrolled' with no step", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "BodyScrolls", "html{overflow:hidden;height:100%}body{height:100%;overflow-y:auto}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.match(r.stdout, /6 steps at most, of 80 allowed; up to 6 of them inside 1 box that scrolls/);
});

test("capture --reveal: overflow-x:hidden body: its overflow is the window's, so the window is walked and no box", (t) => {
  if (needSetup(t)) return;
  const { rec } = revealLayout(makeProject(), "BodyOverflowX", "html,body{height:100%}body{overflow-x:hidden}", LAYOUT(ITEMS(3, 1000, "p")));
  assert.deepEqual(rec, { steps: 6, capped: false });
});

test("capture --reveal: html overflow hidden + full-height main, scroll-snap (mandatory, proximity), scroll-behavior smooth (html, box): every step lands, every box back at its top", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const full = "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}";
  const sections = (n, h) => `<main>${Array.from({ length: n }, (_, k) => `<section style="height:${h};scroll-snap-align:start">${k ? "" : RED_BAND}</section>`).join("")}</main>`;
  const cases = {
    FullMain: [full, LAYOUT(`<main>${RED_BAND}${ITEMS(4, 975, "p")}</main>`), { steps: 8, capped: false, boxes: 1, box_steps: 8 }],
    SnapMandatory: [full + "main{scroll-snap-type:y mandatory}", LAYOUT(sections(4, "100%")), { steps: 6, capped: false, boxes: 1, box_steps: 6 }],
    SnapProximity: [full + "main{scroll-snap-type:y proximity}", LAYOUT(sections(6, "70%")), { steps: 7, capped: false, boxes: 1, box_steps: 7 }],
    SmoothBox: [full + "main{scroll-behavior:smooth}", LAYOUT(`<main>${RED_BAND}${ITEMS(4, 975, "p")}</main>`), { steps: 8, capped: false, boxes: 1, box_steps: 8 }],
    SmoothHtml: ["html{scroll-behavior:smooth}", LAYOUT(`${RED_BAND}${ITEMS(4, 975, "p")}`), { steps: 8, capped: false }],
  };
  for (const [name, [css, html, want]] of Object.entries(cases)) {
    const { rec, shots } = revealLayout(p, name, css, html);
    assert.deepEqual(rec, want, name);
    assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 100 * 0.9, `${name}: the first screen shows the top of the page`);
  }
});

test("capture --reveal: main under a 60 px header and under a 220 px header: the window's 60 px and the main are both walked", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const a = revealLayout(p, "Header60", "header{height:60px}main{height:100vh;overflow-y:auto}", LAYOUT(`<header></header><main>${ITEMS(3, 1000, "p")}</main>`));
  assert.deepEqual(a.rec, { steps: 7, capped: false, boxes: 1, box_steps: 6 });
  const b = revealLayout(p, "Header220", "html,body{height:100%;overflow:hidden}body{display:flex;flex-direction:column}header{height:220px;flex:none}main{flex:1;overflow-y:auto}",
    LAYOUT(`<header></header><main>${ITEMS(3, 1000, "p")}</main>`));
  assert.deepEqual(b.rec, { steps: 8, capped: false, boxes: 1, box_steps: 8 });
});

test("capture --reveal: sticky full-height sidebar on a short and on a long page: the sidebar and the window are both walked", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const css = "body{display:flex;align-items:flex-start}aside{position:sticky;top:0;height:100vh;overflow-y:auto;width:200px;flex:none}main{flex:1}";
  assert.deepEqual(revealLayout(p, "StickyShort", css, LAYOUT(`<aside>${ITEMS(3, 1000, "a")}</aside><main>${ITEMS(1, 500, "p")}</main>`)).rec, { steps: 6, capped: false, boxes: 1, box_steps: 6 });
  assert.deepEqual(revealLayout(p, "StickyLong", css, LAYOUT(`<aside>${ITEMS(3, 1000, "a")}</aside><main>${ITEMS(5, 1000, "p")}</main>`)).rec, { steps: 16, capped: false, boxes: 1, box_steps: 6 });
});

test("capture --reveal: code box with max-height in a long page, and nested full-screen main with a max-height list: the small box is counted, not walked, and every box is back at its top", (t) => {
  if (needSetup(t)) return;
  const p = makeProject();
  const code = revealLayout(p, "CodeBox", ".late{height:300px;background:#c03;opacity:0}.late.in{opacity:1}pre{max-height:300px;overflow-y:auto;margin:0}",
    LAYOUT(`${ITEMS(1, 1800, "p")}<pre>${ITEMS(6, 1000, "c")}</pre>${ITEMS(1, 1200, "p")}<section class=late></section>`
      + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script>"));
  assert.deepEqual(code.rec, { steps: 7, capped: false, small_boxes: 1 });
  assert.ok(redPixels(path.join(code.shots, "1440-light-full.png")) > 1440 * 300 * 0.9, "the window was walked to its bottom, past the code box");
  assert.match(code.r.stdout, /1 box under half a screen tall that scrolls \(a code block, a short list\) was not walked/);
  const nested = revealLayout(p, "Nested", "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}ul{max-height:300px;overflow-y:auto;margin:0;padding:0}",
    LAYOUT(`<main>${RED_BAND}${ITEMS(1, 1100, "p")}<ul>${ITEMS(5, 1000, "l")}</ul>${ITEMS(1, 600, "p")}</main>`));
  assert.deepEqual(nested.rec, { steps: 3, capped: false, boxes: 1, box_steps: 3, small_boxes: 1 });
  assert.ok(redPixels(path.join(nested.shots, "1440-light.png")) > 1440 * 100 * 0.9, "main is back at its top in the first screen");
});

test("capture --reveal: closed off-canvas drawer (moved off the screen, or hidden), and a short list in a closed menu: not walked, not counted", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Drawer",
    "html,body{height:100%;overflow:hidden}main{height:100%;overflow-y:auto}nav{position:fixed;top:0;height:100%;width:300px;overflow-y:auto}.left{left:0;transform:translateX(-100%)}.right{right:0;visibility:hidden}"
      + ".menu{position:fixed;top:0;left:0;width:300px;transform:translateX(-100%)}.menu ul{max-height:300px;overflow-y:auto;margin:0}",
    LAYOUT(`<main>${ITEMS(2, 1000, "p")}</main><nav class=left>${ITEMS(9, 1000, "d")}</nav><nav class=right>${ITEMS(9, 1000, "d")}</nav><div class=menu><ul>${ITEMS(10, 100, "m")}</ul></div>`));
  assert.deepEqual(rec, { steps: 3, capped: false, boxes: 1, box_steps: 3 });
  assert.ok(!/under half a screen/.test(r.stdout), r.stdout);
});

test("capture --reveal: grid of 8 tall scrolling cards: the walk stops at 80 steps and names the boxes it did not finish, never a long page", (t) => {
  if (needSetup(t)) return;
  const { r, rec } = revealLayout(makeProject(), "Cards", ".grid{display:grid;grid-template-columns:repeat(4,1fr)}.card{height:500px;overflow-y:auto}",
    LAYOUT(`<div class=grid>${`<div class=card>${ITEMS(6, 1000, "c")}</div>`.repeat(8)}</div>${ITEMS(1, 3000, "p")}`));
  assert.deepEqual(rec, { steps: 80, capped: true, boxes: 4, box_steps: 73, boxes_unfinished: 5 });
  assert.match(r.stdout, /\(80 steps at most, of 80 allowed; up to 73 of them inside 4 boxes that scroll/);
  assert.match(r.stdout, /CAPPED: the page and its boxes needed more than 80 steps, so what lies further down in 5 boxes that scroll was not revealed/);
  assert.ok(!/longer than 40 screens/.test(r.stdout), r.stdout);
});

test("capture --reveal: box in the first screen whose items reveal by a viewport IntersectionObserver, on a long page: walked with the page scrolled back to show it", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "Panel", SEEN_HEADER + ".panel{height:600px;overflow-y:auto;margin-top:50px}",
    LAYOUT(`<header class=seen-bar></header><div class=panel>${ITEMS(6, 400)}</div>${ITEMS(1, 4000, "p")}${SEEN_SCRIPT(6)}`));
  assert.deepEqual(rec, { steps: 16, capped: false, boxes: 1, box_steps: 6 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all six items of the panel were seen in the viewport");
  assert.ok(redPixels(path.join(shots, "390-dark.png")) > 390 * 50 * 0.9);
});

test("capture --reveal: box taller than two screens: walked in half-screen steps, then carried up by the page until its bottom is shown, so every item is seen", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "TallBox", SEEN_HEADER + ".tall{height:2400px;overflow-y:auto}",
    LAYOUT(`<header class=seen-bar></header><div class=tall>${ITEMS(60, 100)}</div>${ITEMS(1, 3000, "p")}${SEEN_SCRIPT(60)}`));
  // the page: 10 steps at 900, 11 at 844; the box: 8 / 9 steps inside it, then 4 steps of the page carrying it up
  assert.deepEqual(rec, { steps: 24, capped: false, boxes: 1, box_steps: 13 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "all 60 items of the tall box were seen in the viewport");
  assert.ok(redPixels(path.join(shots, "390-light.png")) > 390 * 50 * 0.9);
});

test("capture --reveal: a box that the page's walk reveals (opacity 0 until seen) is found after it and walked", (t) => {
  if (needSetup(t)) return;
  const { rec, shots } = revealLayout(makeProject(), "LateBox", SEEN_HEADER + ".late{opacity:0}.late.in{opacity:1}.panel{height:600px;overflow-y:auto}",
    LAYOUT(`<header class=seen-bar></header>${ITEMS(1, 2000, "p")}<section class=late><div class=panel>${ITEMS(4, 400)}</div></section>`
      + "<script>new IntersectionObserver((es,o)=>es.forEach((e)=>{if(e.isIntersecting){e.target.classList.add('in');o.unobserve(e.target)}})).observe(document.querySelector('.late'))</script>" + SEEN_SCRIPT(4)));
  assert.deepEqual(rec, { steps: 9, capped: false, boxes: 1, box_steps: 4 });
  assert.ok(redPixels(path.join(shots, "1440-light.png")) > 1440 * 50 * 0.9, "the late box's items were all seen");
});

test("capture --reveal: infinite scroll that appends on reaching the end: followed to its end with --wait 0, and the record says it grew", (t) => {
  if (needSetup(t)) return;
  const { r, rec, shots } = revealLayout(makeProject(), "Infinite", "",
    LAYOUT(`${ITEMS(1, 1800, "p")}<script>let n=0;addEventListener('scroll',()=>{const d=document.documentElement;if(scrollY+d.clientHeight>=d.scrollHeight-5&&n<5){n++;const e=document.createElement('div');e.style.height='1800px';if(n===5)e.style.background='#c03';document.body.append(e)}})</script>`));
  assert.deepEqual(rec, { steps: 28, capped: false, grew: true });
  assert.ok(redPixels(path.join(shots, "1440-light-full.png")) > 1440 * 1800 * 0.9, "the fifth page appended is in the full page");
  assert.match(r.stdout, /the page or a box grew as it was scrolled/);
});

test("capture --reveal: html overflow:clip: Chromium scrolls the root by script (clip on the root is hidden on the viewport), so the page is walked", (t) => {
  if (needSetup(t)) return;
  assert.deepEqual(revealLayout(makeProject(), "Clip", "html{overflow:clip}", LAYOUT(ITEMS(3, 1000, "p"))).rec, { steps: 6, capped: false });
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
```

## Appendix C: the mutations replayed

Each was applied once to the integrated `scripts/render.mjs`, and the tests named for it were run (`node --test --test-name-pattern`).

The anchoring mutation (review 4) was replayed a second time, after its test moved from the reviewer's intro to the banner; the
first replay, against the intro, missed it (see Review, item 4). Every other result is from one replay of the final code.

- **D: box walked with the window where the page walk left it (no placement).** Tests: the ones named for `box in the first screen`. Result: caught.

  ```js
  // old
    el.scrollIntoView({ block: "start", inline: "nearest", behavior: "instant" });
    const seen = await S.see(el, ms);
    return { shown:
  // new
    const seen = await S.see(el, ms);
    return { shown:
  ```

- **A: a walked box left scrolled (only the window put back).** Tests: the ones named for `scroll-snap \(mandatory|nested full-screen main`. Result: caught.

  ```js
  // old
    for (const [el, at] of S.found) el.scrollTo({ top: at.top, left: at.left, behavior: "instant" });
  // new
  (removed)
  ```

- **B: a box must be 0.8 of the screen.** Tests: the ones named for `220 px header`. Result: caught.

  ```js
  // old
  const CAPTURE_REVEAL_BOX_MIN = 0.5;
  // new
  const CAPTURE_REVEAL_BOX_MIN = 0.8;
  ```

- **B: one scroller: the window is not walked when the page has a box.** Tests: the ones named for `sticky full-height sidebar|60 px header`. Result: caught.

  ```js
  // old
      const page1 = await walkOne(-1, null);
  // new
      const page1 = (await ev(inPageRevealFind, { key, min: CAPTURE_REVEAL_BOX_MIN })).boxes ? "end" : await walkOne(-1, null);
  ```

- **C: a 1 px test scroll, snapping left on.** Tests: the ones named for `scroll-snap \(mandatory`. Result: caught.

  ```js
  // old
      S.keep(el); S.pin(el);
      const was = el.scrollTop, to = (top) => { el.scrollTo({ top, behavior: "instant" }); return el.scrollTop !== was; };
      const moves = to(el.scrollHeight) || to(0);
  // new
      S.keep(el);
      const was = el.scrollTop, to = (top) => { el.scrollTo({ top, behavior: "instant" }); return el.scrollTop !== was; };
      const moves = to(was + 1);
  ```

- **C: every cap called 'the page is longer than 40 screens'.** Tests: the ones named for `8 tall scrolling cards`. Result: caught.

  ```js
  // old
    else if (r.pageUnfinished) parts.push(
  // new
    else if (r.capped) parts.push(
  ```

- **0.8.0/D: no frame wait after a step.** Tests: the ones named for `infinite scroll`. Result: caught.

  ```js
  // old
  const settle = async () => { await ev(inPageRevealFrames, ms); 
  // new
  const settle = async () => { 
  ```

- **0.8.0: a page that moves itself back is walked to the cap.** Tests: the ones named for `pulls itself back`. Result: caught.

  ```js
  // old
        if ((await ev(inPageRevealAt, { key, i })).y <= at.y) return "stuck";   // the page moved it back
  // new
  (removed)
  ```

- **0.8.0: no box when the window scrolls.** Tests: the ones named for `body that scrolls itself|sticky full-height sidebar`. Result: caught.

  ```js
  // old
      for (let i = 0; i < found.boxes; i++) {
  // new
      for (let i = 0; i < (found.boxes && 0); i++) {
  ```

- **0.8.0: the largest box, a closed drawer included (no off-screen test).** Tests: the ones named for `closed off-canvas drawer`. Result: caught.

  ```js
  // old
  shown: seen && seen.width >= 1 ? 
  // new
  shown: seen ? 
  ```

- **a box stepped by half its own height, not half of what the screen shows of it.** Tests: the ones named for `box taller than two screens`. Result: caught.

  ```js
  // old
        let r = await walkOne(i, shown);
  // new
        let r = await walkOne(i, null);
  ```

- **D: boxes chosen before the page's walk (a box it reveals is never found).** Tests: the ones named for `page's walk reveals`. Result: caught.

  ```js
  // old
      const page1 = await walkOne(-1, null);
      if (page1 === "spent") out.pageUnfinished = true;
      if (page1 === "stuck") out.notScrolled = true;
      found = await ev(inPageRevealFind, { key, min: CAPTURE_REVEAL_BOX_MIN });
  // new
      found = await ev(inPageRevealFind, { key, min: CAPTURE_REVEAL_BOX_MIN });
      const page1 = await walkOne(-1, null);
      if (page1 === "spent") out.pageUnfinished = true;
      if (page1 === "stuck") out.notScrolled = true;
  ```

- **review 1 / 0.8.1: screen-sized steps (an item inside a reveal margin is skipped).** Tests: the ones named for `with a margin`. Result: caught.

  ```js
  // old
  const CAPTURE_REVEAL_STEP = 0.5;
  // new
  const CAPTURE_REVEAL_STEP = 1;
  ```

- **review 2: a tall box's middle never shown (not carried up after its end).** Tests: the ones named for `box taller than two screens`. Result: caught.

  ```js
  // old
  r === "end";) {
  // new
  false;) {
  ```

- **review 3: a box walked from where the page left it (a chat at its end: 0 steps).** Tests: the ones named for `chat box`. Result: caught.

  ```js
  // old
    el.scrollTo({ top: 0, behavior: "instant" });   // a box the page had scrolled (a chat at its end) is walked from its top
  // new
  (removed)
  ```

- **review 4: scroll anchoring left on (a banner that collapses above the screen pulls the window back).** Tests: the ones named for `banner that collapses`. Result: caught.

  ```js
  // old
  for (const prop of ["scroll-snap-type", "overflow-anchor"])
  // new
  for (const prop of ["scroll-snap-type"])
  ```

- **review 5: the page's IntersectionObserver awaited with no bound.** Tests: the ones named for `never answers`. Result: caught.

  ```js
  // old
  const t = setTimeout(() => { io?.disconnect(); resolve(null); }, ms);
  // new
  const t = 0;
  ```

- **review 6: the scrollers around a box by parentElement only (a shadow scroller left scrolled).** Tests: the ones named for `shadow scroller`. Result: caught.

  ```js
  // old
  S.up = (a) => a.assignedSlot ?? a.parentElement ?? (a.parentNode instanceof ShadowRoot ? a.parentNode.host : null);
  // new
  S.up = (a) => a.parentElement;
  ```

- **review 7: small boxes counted with no off-screen test (a list in a closed menu).** Tests: the ones named for `closed off-canvas drawer`. Result: caught.

  ```js
  // old
  if (spent() || await ev(inPageRevealSmall, { key, j, ms })) out.small += 1;
  // new
  out.small += 1;
  ```

## Review

The first version of this design was reviewed adversarially. Each finding, and what was done:

1. **Major: screen-sized steps skip items inside a reveal margin or threshold.** Accepted and changed. A step is now half of what the
   screen shows (`CAPTURE_REVEAL_STEP = 0.5`), for the window and the boxes. The budget went from 40 to 80 steps, so the reach stays 40
   screens and the line "the page is longer than 40 screens" stays true (section 1, "Why half a screen", gives the exact condition).
   Every expected record in the table and the tests was recomputed from the new formula before the run. Rows 29 to 31 are the
   reviewer's three layouts: all items seen, except the last item under a -20 % bottom margin, which no visitor sees either (limit
   10). The new test "reveal scripts with a margin" uses `-100px` and `0px 0px -20% 0px`, and catches the screen-sized step. The cost
   is O7 and limit 14.
2. **Major: a box over two screens tall has a band never on screen.** Accepted and changed. The single placement by the box's bottom
   is gone. At its end, while the box's bottom edge is not on the screen, the nearest scroller around it that still carries it up
   (the window last) is scrolled down by a step, and these steps count. Row 32 is the reviewer's 2400 px box: 61 of 61 at both sizes.
   Row 19's expectation now adds the carry steps. The test "box taller than two screens" uses a 2400 px box (2.8 screens at 844) and
   catches the missing carry.
3. **Major: a box the page had scrolled is walked only from where it is; "nothing to scroll" is then false; "up to 0 of them inside 1
   box".** Accepted and changed. Each box is put at its own top before it is put on the screen, and walked from there; the window is
   also put at its top first. The return still puts each where it was found (a chat back at its end), and the CONTRACT text now says
   "the window at its top and each box where the page had it" (limit 12, O5). "Nothing to scroll" now needs no step, no cut, no
   stuck scroller and no unmeasured box. A box counts in `boxes` only once it took a step. Row 33 is the reviewer's chat: 12 steps,
   20 of 20, left at its end; row 40 is the reviewer's timeout page, whose line no longer says "up to 0 of them inside 1 box". The
   test "chat box scrolled to its end on load" catches it.
4. **Major: scroll anchoring reads as "the page moved it back".** Accepted and changed as proposed: `overflow-anchor: none !important`
   is pinned with `scroll-snap-type`, on the root, every box and every scroller around a placed box, and put back the same way. Row 34
   is the reviewer's collapsing intro: 4 of 4. With half steps that intro is still on the screen at the first step, so Chromium
   anchors to it and nothing is pulled back; the same page passes with anchoring left on. So the test uses a layout that does pull
   the window back: a 600 px banner that collapses once it is wholly above the screen (row 42). With anchoring left on it gives 2
   steps, NOT SCROLLED and 2 of 4 seen; with the fix, 4 of 4. I also checked whether turning anchoring off opens a gap of its own (content that
   collapses above the screen moves what follows past it). At the top of the page it does not: the return shows that part (40 small
   items after a collapsing 100vh intro: 40 of 40). In the middle of the page, 3 items of 100 px are missed (row 35), but a variant
   that kept anchoring on with a shrink-aware stuck test missed the same 3: the cause is the step size, not anchoring. That is limit
   9. The test "a banner that collapses once it is above the screen" catches anchoring left on (the
   first replay used the reviewer's intro and missed the mutation, for the reason above).
5. **Minor: in-page awaits have no bound; the time is not checked before placements.** Accepted and changed. The measure races the
   page's `IntersectionObserver` against 1 s; with no answer the box is not walked and is counted in the new key `boxes_unmeasured`,
   with the clause `NOT MEASURED: ...`. The frames of the settle race 1 s too. Every call into the page runs under `withTimeout(time
   left of --timeout + 20 s)`; on expiry the walk stops with `capped`, `timed_out` and `not_returned`, the cut scroller is marked, and
   the run goes on (the page is not returned, since it does not answer). The time is now checked before every step, placement, carry
   step and small-box test. Limit 7 is restated. Row 37 is the reviewer's no-op observer (no hang, 1 s more per load); row 38 is a
   page with no frames; row 41 is a script that never ends (given up at 22 s with `--timeout 2000`; the still after it then fails after
   30 s, exit 1, nothing written, see O6). The test "a page whose IntersectionObserver never answers" catches the unbounded wait: the
   replay failed the test rather than hang it, because the outer guard is still there to end the walk.
6. **Minor: a slotted box's shadow scroller is left scrolled.** Accepted and changed. The scrollers around a box are found in the flat
   tree (`assignedSlot`, then `parentElement`, then a shadow root's host); they are kept, pinned and put back, and the carry step uses
   the same chain. Row 39 is the reviewer's layout: 6 steps, nothing left scrolled in the shadow tree (the probe now looks inside
   shadow roots). Limit 3 says it. The test "a box slotted into a shadow scroller" catches `parentElement` only.
7. **Minor: a small list in a closed drawer is counted.** Accepted and changed. A small box is put on the screen as a box is and
   counted only when the measured rect has width and height. Row 36 is the reviewer's menu: `{steps: 0, capped: false}` and the line
   "nothing to scroll", with no small-box clause. The closed-drawer test now holds a short list in a closed menu and checks there is
   no small-box clause; it catches the missing test.

Two things changed beyond the findings, both found while checking them: the inline `style` attribute of a pinned element is put back
letter for letter when the page did not touch it (the first version could re-serialize an attribute the page had), and the head of
the line leaves out "and back" when a scroller was not returned.
