# P6 Mark and logo system

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques by mark source](#techniques-by-mark-source)
- [Techniques for every mark](#techniques-for-every-mark)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

A mark that survives every real size and context it will meet, with lockups, colour and reverse variants, and rules
written as numbers the owner approved.

## Inputs

- The approved direction (G3) and its board.
- The hardest surface from BRIEF (or INVENTORY.md), the 5-competitor lineup from research when it exists.
- Platform safe zones for the surfaces in scope (they become size-band constraints).

## Outputs and paths

| Output | Path |
|---|---|
| Mark artwork, pure vector | `assets/logo/mark.svg`, `assets/logo/mark-dark.svg` (and lockups, wordmark) |
| Real-size sheet | `assets/_checks/logo-sheet.png` and `assets/_checks/logo-sheet.json` |
| Contrast report | `assets/_checks/contrast.json` |
| Geometry proof | `assets/_checks/logo-guides.png` and the `guides` rows of `logo-sheet.json` (`--guides`) |
| Small-size proof | `assets/_checks/downscale/<master>-<hash>.json`, one per measured file (accent pixels, box and largest solid square per size) |
| Size bands and thresholds | `qa/rules.json` (`bands`, `downscale`, `guides`); proposals apply until the owner sets them |
| Generators (generated source) | `tools/*.py` built on `scripts/lib/px_lib.py`; their outputs are never hand-edited |
| Proposed rules | BRAND-STATE.md Notes as "(rule)" lines for G4 |

## Techniques by mark source

- **generated** (grid, pixel, voxel or geometry kept as code; drawing it is still the drawing step of
  [drawing-engines](../drawing-engines.md)): the generator in `tools/` is the source; the SVG and PNGs
  are its output and are never edited by hand. Build grids with `scripts/lib/px_lib.py` (`grid_image()` reads a mark
  drawn as text; deterministic PNG, ICO and run-length SVG writers). Rebuilds must be byte-identical; prove a refactor
  with `snapshot take`, change, `snapshot take`, `snapshot diff`. The Acme example's `tools/grid_mark.py` is the worked
  case. A pixel mark ships as SVG rectangles with `shape-rendering="crispEdges"`, and its PNGs stay crisp only at
  whole-number scales: for a size that is not a multiple of the grid (a 16 grid at 180 px is 11.25x), render at the
  largest whole multiple that fits and centre it on the padded canvas.
- **authored-vector** (type-based or drawn), in this order:
  1. `fontcheck --lang <codes>` on the candidate font: coverage for the brand's language sets (`content_languages` in
     BRAND-STATE, never the chat language), a licence hint from the file, Chromium's platform-font report.
  2. `outline-glyphs --font <file> --text "<word>" --axis wght=<n>`: one path per glyph, overlaps removed, no live
     text. The font's kerning is not applied, so set `--pair` and `--tracking` by eye and say so.
  3. `logo-sheet --guides` over the outlined mark: baseline, cap line and x-height from its `data-*` metrics (or
     `--baseline`, `--cap-line`, `--x-line`, `--grid`), with the measured px offset to the nearest ink edge. Report a
     fault as "12 px off the cap line, 0.2 px after the fix", never as "fixed".
  One projection per drawing; mixed projections are a fault even when they look fine.
  From a raster exploration the owner picked (a generated image, photo or sketch): trace it,
  `magick in.png -colorspace Gray -threshold 50% pbm:- | potrace -s -o mark.svg -`, then fix the curves by hand, remove
  specks and set the fill to a token. The raster stays with its round as the source; it never goes in `assets/logo/`.
  Where marks are drawn in the first place, and how a kept one is imported into the round, is
  [drawing-engines](../drawing-engines.md).
- **existing** (the owner's mark), the audit comes before any other work:
  1. Input: SVG must be pure vector (mark_lint); PDF goes through `pdftocairo -svg`; a raster is warned about ("icons
     drawn from it will be soft and the small sizes cannot be redrawn"). Offer the vector from whoever made it, a trace
     (`potrace`) as an explicit, approved step, or a redraw as `authored-vector`. Never a silent trace. The traced or
     redrawn SVG becomes the master; the owner's raster stays as a reference only.
  2. `logo-sheet` at 16, 32 and 180 (and the rest of the sheet) on light and dark; Read it.
  3. `contrast` (every colour of the artwork must be a token; touching pairs and the ground) and `downscale` (the
     accent at the system sizes).
  4. A short audit list in the round page or chat: what holds, what fails, with the numbers; then palette, guide and
     files (the brand-assets skill). Fixes to the mark itself are a new round, not a quiet edit.

## Techniques for every mark

1. **Judge at 16 px first.** Run `... logo-sheet --project <dir>` and Read the sheet: 16/20/32/64/128/180 on light and
   dark, a 4× magnified favicon, a header mock-up. Then the large sizes get their own pass: what holds at 16 can look
   crude at 512.
2. **Light and dark grounds for every tile.** A dark tile on a dark page needs an edge or a contrast pair; the sheet
   measures it (`--min-contrast`, a brand rule).
3. **Lockups in units.** Icon, gap and cap band in one unit system (for example icon 16u, gap 4u, cap band centred),
   colour and reverse variants, and any secondary line must fit inside the tile height; check it with an overlay.
   Check lockup rows with the longest-language strings at 390 px wide.
4. **Accent minimum.** A small accent must stay readable: at 32 px and below it holds a solid 4×4 px square on the real
   downscale (the default rule, `downscale.accent_min_px` and `accent_rule_max_size` in `qa/rules.json`). A vanished
   accent is named as such. A miss the owner accepts (a row of 2 px cells that reads as a row) is an exemption with their
   reason, for that master and size: `downscale.exemptions` in `qa/rules.json`, a warning instead of a failure. A
   low-contrast accent is used only as a fill with an edge, never as text.
5. **Signature move.** Every brand owns one colour role that no sibling uses; a brand that moves also owns one move (it
   presses, slides, crosses, rises). Name the move once: it is the `signature` of `motion/motion.json`, which the book, the
   adapters and the motion round use; in Standard and Full it is tried in the motion round after G3
   ([07-tokens](07-tokens.md)), and a brand that does not move records that once (`brand-creator motion --off "<reason>"`).
   In family modes, compare against the siblings' tiles side by side.
6. **Distinctive assets.** List the non-name assets the brand claims (shape, colour role, move, pattern) and compare
   them with the 5-competitor lineup; drop any that a competitor already owns.
7. **Size bands.** A different drawing per body size, chosen by one function (`qa_rules.pick_band()`), for example
   `{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}` then `{"name": "large", "drawing":
   "assets/logo/mark.svg"}`. Every manifest slot records its band; a slot off the rule needs a one-line exemption.
   Hand masters only where the exact pixels ship (favicon layers, .ico, PNG icons, tray, Linux hicolor): `emit web`,
   `emit windows`, `emit linux` and `emit tray` draw each size by the rule, and `check` re-reads every layer's band.
   Several marks (a family of products on one system) go in `qa/rules.json` `marks`, each with its own bands; the logo sheet,
   the emitters and `check` then run per mark (`--mark <id>`, scripts/CONTRACT.md "Several marks").
   A system that shrinks one master (Apple, the registry icon, the avatar) gets one master, and if its small sizes need
   the coarse drawing the exemption says so. Judge the 16 px version first, then draw the rest, on the session's drawing
   engine ([drawing-engines](../drawing-engines.md)).
8. **Safe zones become size-band constraints.** Platform rules (Android adaptive 66 of 108 dp, the maskable circle, circular
   watch and headset icons, store icons with padding) constrain what the mark may put near its edges. Verified sizes
   live in `scripts/emitters/platform-specs.json`; never type sizes from memory.
9. **Measure, don't claim.** "The notch survives at 16 px" is a claim; the measured accent pixels on a real downscale
   are evidence. Document weaknesses on the board rather than hide them.
10. **Faults get a mini-board.** When a geometric fault is found, show before/after with guides and numbers, and
   rebuild the model rather than patch the output.

## Gate

The owner picks bands and thresholds at G4. Your numbers are proposals; each one is a single revertable "(rule)" line,
for example "(rule) band B from 25 to 79 px" or "(rule) accent at least 4×4 px at 32 px and below".

## Pitfalls

- Mixed projections in one drawing.
- An accent of 1-2 px at 16 px.
- Dark tiles vanishing on dark pages.
- Two sibling marks in different proportions (check tile ratios across products).
- Endorsement spacing broken by new letters; reuse the family's letters.
- Live text left in an SVG (the font is missing on the target machine and the mark changes).
- A raster traced without asking, or an owner's existing mark "tidied" without a round.
- One fine vector shipped as the master a system shrinks, with the accent smudged at 16 px.
- Kerning claimed from the font when `outline-glyphs` did not apply it.

## Enforcement

- `logo-sheet` (script): renders every size on both grounds with resvg and writes the report. Each tile is drawn from the
  drawing its size band names (`qa/rules.json` `bands`, when `--svg` is one of their drawings), a pixel drawing at the largest
  whole-number scale that fits. Only the colours that touch the ground are held to the target (`--min-contrast`, by default
  `touching.ground` of the tokens), so a face inside an outline is not, and `tokens/exceptions.json` can excuse one as it does
  for `contrast`; each tile's own edge must reach the target too, so a keyline thinner than a pixel fails at 16 px. Line art
  whose colours cannot be measured is "not verified", never a pass. `--guides` adds the geometry proof: guide lines (baseline, cap line, x-height from an outlined mark's `data-*` metrics, or `--baseline`,
  `--cap-line`, `--x-line`, `--grid`) over the mark at 512 px, with the measured offset to the nearest ink edge
  (tolerance `guides.tolerance_px` in `qa/rules.json`).
- `outline-glyphs` (script): type-based marks only. fontTools pins the variable axes, skia-pathops removes overlaps,
  the result is one path per glyph with no live text. Run `fontcheck` first (coverage for the brand's language set,
  licence hint, Chromium platform-font report); the font's own kerning is not applied, so kern the pairs by eye.
- `downscale` (script): measures the accent on the real system downscale (`sips` on macOS) at every size systems
  show, with before/after against the previous round; at 32 px and below the accent must hold a solid 4×4 px square
  (a default rule, owner-adjustable). Off macOS only an explicit `--renderer` opt-in measures. `--png` measures a
  shipped raster as it is, with no resampling.
- Size bands (script): `qa/rules.json` `bands` name the drawing per body size (for example a coarse-grid master
  for 32 px and below). One function picks the band; each manifest slot records it; a slot off the rule needs a
  one-line exemption. Marks built from a grid are generated with `scripts/lib/px_lib.py`.
- `family-check` (family modes): shared glyphs must be cell-equal to the family sources named in `FAMILY.md`, and tile
  shares must agree across products.
- `check` mark_lint: any SVG under `assets/` with `<text>`, `<tspan>`, `font-family`, `@font-face` or an external
  href fails.
- `contrast`: brand-rule pairs for marks and lockups are labelled "brand rule (logos WCAG-exempt)"; UI pairs gate on
  WCAG 2.2 AA. Colours that touch in the artwork are found in the raster (not declared by hand), held to the targets in
  the tokens, and a miss fails unless `tokens/exceptions.json` records it with a reason.
