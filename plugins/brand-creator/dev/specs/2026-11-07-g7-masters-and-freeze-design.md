# brand-creator 0.10.0 (group 7): masters and a smaller freeze

- **Status:** owner's answers in (2026-11-07); ready for the plan
- **Date:** 2026-11-07
- **Sources:** two working sessions of the pilot brand, its feedback on 0.6.0 (items 7, 8 and 11), and measurements
  of its project made read-only on 2026-11-07. The other brand projects made no ads or decks and froze nothing
  large, so they add nothing here.

## Why

### Masters: what happened on Pilot

Ads and decks ("masters") are the one deliverable the plugin leaves fully to hand work. On Pilot it went like this:

1. **r19, 2026-10-25.** One ad master in six sizes and a 13-slide deck, built in about 5 minutes as one variant. The owner:
   "Wszystko wymaga dopracowania, nie podoba mi się to do końca." The assistant's own diagnosis: too little of the brand,
   too much empty space. Nothing in the plugin asked for directions, the brand's world or the approved pages first.
2. **r20 and r21.** Three directions (Kalendarz, Lista, Po nowemu), then copy reworked from product facts. Approved.
3. **PPTX on request** ("czy możesz zrobić jeszcze wersję PPTX"). The assistant installed pptxgenjs ad hoc in the scratchpad,
   wrote `build-pptx.mjs`, `media.mjs`, `fonts.py` and `embed.py`, and could only see the result after the owner granted
   macOS automation so PowerPoint could export a PDF. Three faults were found by eye only then: a panel covering the logo
   (slide 7), "13 205,20 zł" running into a "3" (slide 9), a label cut on slide 10. Keynote shows a substitute font
   (it ignores embedded fonts), so the Keynote export used later is a misleading check.
4. **Copying into the brand.** `assets/masters/` filled by hand, its README written by hand, `normalise_pdf()` imported from
   the plugin's library by hand, the book's masters chapter written by hand, the kit synced, then the kit's recipes
   (`ad.md`, `presentation.md`) rewritten by hand.
5. **r32, 2026-11-04.** After the site was approved the owner asked: "czy nie powinniśmy jeszcze przebudować całej sekcji
   Prezentacji oraz ew. materiałów graficznych dla marketingu w adsach?" The masters had fallen behind the site's language
   (sheet, date tiles, arrows, payroll paper). The assistant listed five gaps and rebuilt them all; nothing in the plugin had
   said the masters were now older than the approved site.

The builder that resulted (`rounds/r32/wzory/`) is 1,052 lines across `build.mjs`, `render.mjs` and `pptx/`. Its own
spill check ("every element's box inside the canvas") is the one automated check, and it does not see one element covering
another, which is what the owner and PowerPoint caught.

### Freeze: what happened on Pilot

`freeze` copies the whole round folder. Pilot's `history/` is 291 MB of a 764 MB project:

| Freeze | Whole | What its boards show | Plus build scripts |
| --- | --- | --- | --- |
| 2026-10-21-approved-board (r14) | 128 MB | 4.7 MB, 216 files | 1.9 MB |
| 2026-10-21-approved-rules (r16) | 158 MB | 5.5 MB, 217 files | 2.3 MB |
| 2026-11-04-approved-site (r31) | 4 MB | 2.5 MB, 32 files | 0.1 MB |

- 140 MB of the 291 MB is content stored twice: r16 was a `cp -R` of r14, and both were frozen.
- 43 MB of each early freeze is `_lead/shots/`, the lead's working screenshots that no board shows.
- Cleanup cannot touch `history/` (by design: `history:manifest`), the mirror to `inewi/brand-pilot` carries it, and on
  2026-11-04 the owner force-pushed a fresh mirror to shed old history.

"What its boards show" was measured by following every local reference (`src`, `href`, `srcset`, CSS `url()`, SVG `href`)
from each `board.html`, `index.html`, `preview.html` and `review.html`. A board that builds paths in a script would be
undercounted, which is why the design below loads the pages in a browser as well.

## Goals

1. A masters round, like the site round: directions first, built from what the brand already approved, on a board the
   owner picks from, with a gate.
2. The checks a person did by eye: nothing outside the canvas, no text covered by another element or running into it, the
   PPTX's own boxes inside the slide and its fonts embedded, the PDF normalised.
3. One command that turns approved masters into `assets/masters/`: files byte for byte, the README, the book chapter, and
   the kit picking them up, with the copy rules carried along.
4. The plugin says when the masters are older than the approved site.
5. A freeze keeps what the boards show and the scripts that built it, and nothing else; the existing big freezes can be
   slimmed through cleanup's plan-and-yes flow.

## Non-goals

- A generic HTML-to-PPTX converter. Each brand's deck is different; the round's builder stays the round's own. The plugin
  gives it the parts that are the same everywhere (pptxgenjs installed by `setup`, font embedding, the checks).
- Print (business cards, letterhead, bleed, CMYK, PDF/X): the owner put it in 0.20.0. Masters here are screen ads and decks.
- Deduplicating identical files across freezes. Git already stores identical content once; the closure removes the bulk.
- Any paid API or agent fleet in the tests.

## Anti-goals

- Masters that read as a template filled in: the r19 failure. A masters round that skips the directions or the brand's
  approved pages is worse than none.
- A freeze that drops something a frozen board shows. A frozen board with a broken picture is a lost record; the freeze
  must fail before it writes rather than freeze less than the board shows.
- Rewriting `history/` without the owner's yes, or without a record that restores it.

## Constraints

- `history/` stays write-once through `freeze`; the guard's rules do not loosen. Slimming an existing freeze goes through
  cleanup's flow (plan file, code, `--record-yes`, then `--yes`), changes only files git already has, and writes the
  restore line, exactly as for rounds in 0.9.0 (ADR-0013).
- Fonts: masters may ship font files (`prezentacja/fonty/`); the kit's font rule applies to them as to any font.
- Determinism: every PDF the plugin writes goes through `normalise_pdf()`; PNG and PDF outputs of the same input are byte
  for byte the same across runs, as everywhere else.
- Polish and English copy in masters; the copy rules (no amounts or names in ads, sample data labelled "dane przykładowe",
  placeholders in square brackets) come from the brand, not the plugin.

## Part A: masters

### A1. The masters round (`/brand-creator:round masters`)

- A new board kind, `masters`, after G4 (and after G4p when the brief lists a site), in Standard and Full.
- Inputs it must start from, named on the board: the approved pages in `site/` (when present), `assets/masters/` (when
  present), the motion tokens, FACTS.md. The round's first board shows two or three directions, each in every size the
  brief asks for; it is never a single variant.
- The round holds `masters.json`, the manifest the tools read: one entry per master with `file`, `kind` (`ad`, `slide`,
  `deck-html`, `deck-pdf`, `deck-pptx`, `image`, `font`), `canvas` (`[w, h]` px, for `ad` and `slide`), `direction`, and
  optional `note`; plus the brand's `copy_rules` (lines of text) and `builder` (the command that rebuilds the round).
- Board: `templates/masters-board.html` (`data-board="masters"`), each master at a fixed scale grouped by direction, sizes
  labelled; board-lint gains `masters:*` rows (manifest present and valid, every listed file exists, every canvas matches
  the file's real size, a direction for each entry).
- The owner's pick is gate **G4m** (masters approved), recorded like G4p.

### A2. `brand-creator masters check <round>`

Renders and checks every master in the manifest, headless, with the plugin's Chromium:

- `masters:canvas`: no element's box outside the canvas (the Pilot check, generalised).
- `masters:covered`: no text node's painted box overlaps another element's painted box drawn above it, and no two text
  boxes overlap (the slide 7, 9 and 10 faults). An element marked `data-masters-overlay` (a stamp drawn over text on
  purpose) is excepted, and the board lists each exception.
- `masters:pdf`: the deck PDF's page count equals the slide count, its page size matches the slide canvas, and it is
  normalised (dates and `/ID`).
- `masters:pptx`, structural, from the PPTX's XML with no Office app: every shape's box inside the slide, every font a
  text run names is embedded or listed with a font file in the masters, every picture it points to exists, the slide size
  matches the deck's canvas. Rendering the PPTX is a manual check (the owner's answer): the row
  `masters:pptx-render` is **NOT VERIFIED** until the owner opens the file in PowerPoint (preferred) and says it renders;
  that answer is recorded with G4m. No Office app or LibreOffice is driven by the plugin, and Keynote is never used: it
  ignores embedded fonts.
- PNGs of every ad and slide are written to the round (`png/`), after the logo reveal settles (the wait comes from the
  motion tokens, not a fixed 1500 ms).

### A3. Small tools the round's builder calls

- `brand-creator pdf normalise <file>`: `normalise_pdf()` as a command (in place, or `--out`).
- `brand-creator masters embed-fonts <pptx> --font <file>...`: the generic part of Pilot's `embed.py`.
- `setup` installs `pptxgenjs` (MIT) into the data directory with the other Node packages, so no round installs it ad hoc.

### A4. `brand-creator masters approve <round>` (after G4m)

- Copies every file in the manifest into `assets/masters/` byte for byte, keeping the manifest's paths; the files it
  replaces go to `removed-<date>/assets-masters-r<N>/` as today's hand flow did.
- Writes `assets/masters/masters.json` (the manifest, with the round and the G4m date) and `assets/masters/README.md` from
  it: what each file is, sizes, the copy rules, how to rebuild (the manifest's `builder`), and the font note (PowerPoint
  uses the embedded fonts; Keynote and Google Slides need the font files installed).
- The book gains a generated `masters` block: the previews by direction, sizes, the copy rules, the files. A book with a
  hand-written masters chapter keeps it; the block is offered, not forced.
- The kit already copies `assets/masters/`. New: `kit check` warns when `assets/masters/masters.json` is newer than an
  owner kit file that names a master (by default `recipes/ad.md`, `recipes/presentation.md`), so the recipes rewritten by
  hand on 2026-11-04 are flagged instead of remembered.

### A5. Masters older than the site

`check` (and `status`) report an info row `masters:behind-site` when G4p was recorded after the last G4m: "the masters were
approved before the site; a masters round would bring them to the site's language". Info only: the owner decides.

## Part B: a smaller freeze

### B1. What `freeze` copies

- Starting pages: every `board.html`, `index.html`, `preview.html` and `review.html` in the round, and the round's
  top-level `*.md`.
- The closure: every local file those pages reach, found two ways and merged: by reading references in HTML, CSS, SVG and
  JS files (as measured above), and by loading each starting page in the plugin's Chromium and recording every local file
  it requests (this catches paths a script builds).
- The builders: `*.py`, `*.mjs`, `*.js`, `*.sh` in the round, never `__pycache__`, `node_modules` or `.pyc`.
- Before writing, it loads every starting page again from the copy and fails, writing nothing, if any request finds no
  file. It prints what it left out: the count and size per top folder.
- `freeze --whole` keeps today's behaviour, for the rare round where the owner wants everything.
- The browser pass needs a set-up data directory. Without one, `freeze` stops and names `--static` (references read from
  the files only); it never drops the browser pass silently, and FROZEN.md records `--static` when it was used.
- FROZEN.md records which mode was used and the left-out summary.

### B2. Slimming existing freezes: `brand-creator cleanup --history`

- The 0.9.0 cleanup flow, pointed at `history/<freeze>/`: the plan lists, per freeze, what stays (the B1 closure of that
  freeze) and what goes, with sizes, and a code; `--record-yes` writes the owner's words into DECISIONS.md; `--yes` removes
  with `git rm` only files committed and unchanged, rewrites `history/MANIFEST.sha256` for that freeze, and writes the
  restore record.
- It refuses a freeze whose files do not match the manifest, as `freeze` does today.
- The guard keeps blocking every other way to change `history/`.

On Pilot this would take `history/` from 291 MB to about 17 MB, and the project from about 764 MB to about 490 MB.

## Decided by the owner

- 0.10.0 is masters and a smaller freeze (this session, after 0.9.0).
- The feedback's list for masters: a round type, a nothing-spills-outside-canvas check, a PPTX render check, a
  normalise-pdf CLI, masters in the kit with their copy rules (item 7).
- Freeze only boards, what they show and the builders, or keep large stills outside the manifest (item 11); this design
  takes the first.
- No paid calls or agent fleets in tests; no macOS CI.

## My calls (the builder's, marked for the owner to check)

- The gate is named **G4m**, parallel to G4p.
- `masters approve` does not freeze the round; Pilot froze no masters round, and the owner can still run `freeze`.
- A structural PPTX check with no Office app; never Keynote.
- `pptxgenjs` joins the Node packages `setup` installs.
- The covered-text check excepts elements marked `data-masters-overlay`, and lists them on the board.
- Existing freezes are slimmed only through `cleanup --history`, never by `freeze`.
- Kit file staleness defaults to `recipes/ad.md` and `recipes/presentation.md`, the files Pilot rewrote.

## The owner's answers (2026-11-07)

1. PPTX render: manual, PowerPoint preferred ("1 manual, PP prefered"). No LibreOffice download.
2. The old Pilot freezes: `cleanup --history` may run on the real project ("can be on real project"), after the release,
   with the owner's yes as for any cleanup.
3. Print: in 0.20.0 ("in 0.20").

## Left to the builder

File layout of the new code, the exact board-lint row names, the JSON schema details of `masters.json`, the wait before a
master's PNG, the tests, and the docs (manual pages for the masters round and cleanup's history mode, CONTRACT.md,
CHANGELOG). Calibration: a scratch copy of Pilot with r32's masters as the round, and `cleanup --history` on its
`history/`, measured against the numbers above; after the release, `cleanup --history` on the real project with the owner's yes.
