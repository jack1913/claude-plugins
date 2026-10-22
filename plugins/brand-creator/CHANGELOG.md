# Changelog

All notable changes are listed here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[SemVer](https://semver.org/). The plugin version is in `.claude-plugin/plugin.json`. How 0.1.0 was built, stage by
stage, and why, is in the [archive](docs/archive/README.md).

## [Unreleased]

## [0.3.5] - 2026-10-22

The motion proof, second release: it steps through a page's motion instead of waiting for it, looks at phone screens, compares
the rest frame in the page itself, and keeps one report per proof. A new command writes stills of the motion. A proof that
passed before can now fail or say "not verified": an animation of `top`, `width` or `margin` fails, and motion driven by
`requestAnimationFrame` cannot be checked at the phone widths. A project made before this version should add two lines to its
`tools/finish.sh` (see Changed).

### Added

- `brand-creator frames <proof.json>` writes stills of a page's mark along its motion into `motion/frames/<case>/`: five by
  default (0, 25, 50, 75 and 100 percent of the motion), or `--count N`, or the points you name with `--at 0,40,100`.
  Next to them: `strip.png` with the stills side by side, `reduced.png` (the mark under reduced motion) and `frames.json`
  with each still's time and checksum. The files are in your project because the brand book will show them. A file is
  written only when its bytes change, so a second run says "unchanged". `--case <name>` picks one case. It writes nothing,
  and says why, for a page with nothing to step through, a page that also moves by `requestAnimationFrame` while the stills
  are taken (they would differ from run to run), and a case whose folder holds the stills of another proof. A strip wider
  than Chromium can write is refused with the number of stills that fit.
- The motion proof looks at phone screens. It loads the page again at 360 and 390 pixels wide (`"widths"` in the case
  changes them) and, at every point of the motion, checks that the page cannot be swiped sideways, that no part of the mark
  goes past the left, top or right edge, and that the page is no taller than at rest. A failure names the moment, the part,
  the edge and how far: `at 62% (310 ms): g#letter-a 22 px past the right edge at 360 px`.
- A pixel mark is held to whole pixels at every point of the motion and at every keyframe, not at nine fixed points, whether
  it moves by `transform` or by the `translate`, `rotate` and `scale` properties. A mark counts as a pixel mark when its still
  says `shape-rendering="crispEdges"` on the root; `"pixel": true` or `"pixel": false` in the case overrides that.
- `brand-creator version --check` says whether the session runs the copy of the plugin that Claude Code has installed. After
  an update, a session that started before it still runs the old copy: the command then exits 1 and says to start a new
  session. In a checkout of the repository it says "not checked".
- A step of `motion/motion.json` can start at a sum: `"{motion.base} + {motion.stagger} * 2"` starts a step when another ends,
  plus a stagger. Every part of the sum must be a duration token.

### Changed

- `shot --motion` writes one report per proof file: `assets/_checks/motion/<name>-<hash>.json`, where the name is the proof
  file's name and the hash comes from its path as the disk spells it. It used to write `assets/_checks/motion.json`, so a
  second proof, or a try-out under `rounds/`, overwrote the report of the first. Run each proof again to get its report. An old
  `motion.json` is still checked, with a warning to run the proof again; move it to `removed-<date>/` afterwards.
- `check` reads every motion report on its own terms. A proof under `rounds/`, `history/` or a `removed-*/` folder is a try-out:
  its report is listed and never fails the check. A report whose proof file is gone gives a warning that names it and says
  to move it to `removed-<date>/`. A pack file that asks for the motion check needs at least one passing report of a proof of
  the project, and says "not verified" and which command to run when there is none. The brand book's motion table shows the
  same reports.
- The motion proof steps through a page instead of waiting for it. It pauses every CSS animation, CSS transition and
  `element.animate()` on the page and sets each to a time: 0 and every 1/32 of the motion, every 1/32 of each animation's own
  run (so a short animation inside a long motion is not stepped over), every keyframe (at its real time when the whole
  animation has an easing), and the peak of every curve that overshoots. A page with a 10 second animation no longer takes 10
  seconds. Motion a script starts later is looked for at every frame until `settle_ms` and stepped through from its own start.
- Motion driven by `requestAnimationFrame` cannot be stepped through. The page is still given `settle_ms` in real time and a
  warning row says so, and now the phone-width rows and a pixel mark's whole-pixel row say "not verified" instead of passing
  with nothing measured. A `requestAnimationFrame` loop that still runs after `settle_ms` fails `loops` and `settled`.
- An animation of a layout property (`top`, `left`, `width`, `height`, `margin`, `padding` and the like) fails the layout-shift
  row: it moves the page around it, and Chromium does not count a step of under 3 pixels as a shift, so stepping through it
  cannot measure all of it. A `transform` or `opacity` animation passes.
- The rest frame is compared in the page itself. The proof cuts the mark's box out of the page and draws your still exactly
  where the mark draws: in the `<img>` itself for an image, and for an inline SVG over its content box, in its own parent and
  out of reach of the page's style sheets, so an offset page, a faded parent or a style rule for `svg circle` changes nothing.
  The default tolerance is now 0, where it was 8 of 255, because the two are drawn the same way; `"tolerance"` in the case
  still works. A mark an ancestor rotates cannot be placed exactly and says "not verified".
- A vector mark may ease smoothly: its whole-pixel row is information only (`a vector mark: smooth easing allowed`). Before,
  every mark was held to whole pixels, which no smooth easing curve can meet.
- `templates/finish.sh.tpl` checks the plugin version first (`version --check`) and runs `contrast --cvd` when your
  `qa/rules.json` sets a colour-vision threshold. A project made before this version should do the same in its
  `tools/finish.sh`: replace the `plugin version` step with `step "plugin version"; "${BC[@]}" version --check`, and add
  `--cvd` to the `contrast` step if `qa/rules.json` has a `cvd` section.

### Fixed

- `check` no longer passes when `qa/rules.json` sets a colour-vision threshold and the contrast report has no colour-vision
  rows (a chain that ran `contrast` without `--cvd` dropped them): it says "not verified" and names `contrast --cvd`.
- In BRAND.md, DESIGN.md and the brand's own skill, the places the signature move shows are a list, one per line, like the
  motion rules. A place with a comma in its name stays one item.

## [0.3.4] - 2026-10-21

Motion becomes data: easing curves are tokens, durations and curves reach Swift and Android, and `motion/motion.json`
holds the motion spec that BRAND.md, DESIGN.md and the brand's own skill repeat. A duration that is not whole
milliseconds, or not written the DTCG way, now stops the build: run `brand-creator tokens` once after updating.

### Added

- Easing curves are tokens now. A `cubicBezier` token (`[x1, y1, x2, y2]`, x between 0 and 1) builds into `tokens.css` as
  `--easing-standard: cubic-bezier(0.2, 0, 0, 1)`, and into the Swift and Android files below. A curve that is not four
  numbers, or whose x leaves 0 to 1, stops the build and names the token. The starter tokens have an `easing` group with
  three curves (`standard`, `enter`, `exit`), offered as proposals until you decide at G4.
- Durations and curves reach the apps. `tokens` writes `swift/BrandMotion.swift` (`BrandMotion.Duration.base` in seconds
  and `BrandMotion.Curve.standard(duration:)` for SwiftUI), `android/values/motion.xml` (durations in milliseconds) and one
  `android/interpolator/brand_<name>.xml` per curve. A brand with no duration and no curve gets none of them. Every file is
  read back and compared with the source before the build passes.
- `motion/motion.json` is the motion spec as data: whether anything moves (and, if not, why, in your words), the signature
  move, the moving parts, a timeline written as references to the duration and curve tokens, and the motion rules.
  `brand-creator check` validates it, and names the field and what is wrong; a reference that is not a built token of the
  right kind is an error.
- BRAND.md, DESIGN.md and the brand's own skill say how the brand moves: the durations and curves, the signature move and
  the rules, or "Nothing moves" with the reason. A change to `motion/motion.json` makes them read as out of date until they
  are generated again.

### Changed

- `tokens.json` has a new `motion` entry (durations in milliseconds, curves as numbers) when the tokens have either;
  `other` is as it was.
- A duration must come to whole milliseconds, because Android keeps it as an integer: `12.5ms` now stops the build, and
  `0.32s` is 320 ms.
- Some token sources that built before now stop the build, each naming the token: a duration written as a bare number
  (`"$value": 150`) or as `.5s` (write `0.5s`), a duration over 2147483647 ms, and two durations that would share a Swift
  name (`duration.fast` next to `motion.fast`). In an existing project `tokens --check` fails until you run
  `brand-creator tokens` once after updating, because of the new files and the new `motion` entry.
- A project with durations but no curve and no motion spec gets the same `tokens.css`, Swift colours, Android colours and
  BRAND.md as before (BRAND.md now also lists a duration outside the `duration` and `motion` groups). Its DESIGN.md and
  brand skill gain a short Motion section that lists the durations.
- The motion hand-off template and the G4 motion rule name the easing tokens, and the template points at
  `motion/motion.json`.

### Fixed

- `emit social` keeps the manifest row of an old Open Graph image only while its file is there. Its warning now says to
  run `emit social` again after moving the old images to `removed-<date>/`, which drops their rows, so `check` and the
  book's file list stop expecting them.
- A file `tokens` no longer produces, such as the colorset of a removed colour role or the interpolator of a renamed curve,
  used to stay in `assets/tokens` while `tokens --check` passed. Now `--check` fails on it, and a build moves it to
  `removed-<date>/`.
- Every Swift keyword in a token name is escaped in the Swift files (the list was short; `Self` or `guard` did not
  compile). A colour, duration or curve named `Type` or `Protocol` stops the build, since no member can use that name.
- The brand skill is filled in one pass, so a G4 rule or a motion rule containing `{{name}}` is written as it is instead
  of being filled in or refused.

## [0.3.3] - 2026-10-21

Fixes from the first projects with several marks and the first approved books: `downscale` measures each mark's own
colour, the book's cover shows the drawn wordmark and its stamp speaks the book's language, and see-through colours keep
their alpha in the generated text.

### Changed

- The accent line under the name has square ends when everything drawn on the card is pixel art, so it matches the pixels:
  on social cards, banners, the Play feature graphic, the Chrome promo tiles and the side-by-side image (there, when every
  mark is pixel art). Vector art keeps its round ends. The templates take a new `{{rule_radius}}`; a template of your own
  without it keeps the rounding it has.
- `emit web` warns when `icon.svg`, the drawing browsers show in the tab, changes to another drawing than on its last run,
  and the warning names both files. The same file written another way, or the same bytes, is no change. To keep the old tab icon, set `favicon.drawing` in `qa/rules.json` to the old file
  (`marks.<id>.favicon` for one of several marks).
- The brand book's cover shows your drawn wordmark as its title when `assets/logo/wordmark.svg` exists: an image with the
  name as its alt text, switched to `wordmark-dark.svg` in dark mode like the marks, and set at a whole-number scale when
  it is pixel art. Without a wordmark the name is typed, as before.
- The approval stamp on the book's cover says its word in the book's content language. Give the word in `book/book.json`
  (`"labels": {"pl": {"APPROVED": "ZATWIERDZONO"}}`) and a Polish book says it; `book-lint` looks for that word, in a
  hand-authored book too, in the stamp itself rather than anywhere on the cover. Without it the stamp stays `APPROVED`, and
  the build says the label is missing. A `labels` entry that is not an object of words stops the build with a clear error.

### Fixed

- `downscale` measured every mark on `downscale.accent_colour`, so a mark with its own colour failed. It now measures the
  drawings of a mark, and the files its packs emitted (an avatar, a registry icon), on that mark's `accent` from
  `qa/rules.json`: `--accent` first, then the mark's accent, then `downscale.accent_colour`.
- `BRAND.md`, `DESIGN.md` and the applied skill printed a see-through colour as if it were opaque. A role with an alpha
  under 1 is now `#rrggbbaa` (as in `tokens.css`) wherever a role is listed, and opaque roles are unchanged. The DESIGN.md
  format the plugin pins accepts the 8-digit form, and its lint passes it.
- A card or banner template that draws its own name (outlined paths, for example) was warned about as typing the name.
  With no `{{lettering}}` and no `{{name}}` it now gets an info row that says so, reads no lettering file, and refuses
  `--name` and `--logo-svg`, which it would ignore; a template that types `{{name}}` is still warned.
- The book PDF could print an empty page between two chapters: a chapter that went on from an earlier page and ended near
  the bottom of its last page sent its bottom padding to a page of its own. The chapters and the cover keep no bottom
  padding in print now.
- The book's files chapter listed an Open Graph file that `emit social` keeps for cached link previews as if it were as
  current as the new one. The manifest marks the kept file `"superseded": true`, and the files chapter says "superseded,
  kept for cached link previews" next to it.

## [0.3.2] - 2026-10-21

Several marks in one project: each product's mark gets its own drawings by size, files, reports and checks, and the
repository's own images show every mark side by side.

### Added

- Several marks in one project: `qa/rules.json` `marks` lists each product's mark with its own size bands, and optionally
  its name, tab drawing, accent colour and tagline. Every emitter and `logo-sheet` take `--mark <id>`. Each mark gets its
  own folder (`assets/<pack>/<id>/`), report and manifest rows, and a run never moves another mark's files. `check`
  expects every mark's reports and drawings, and `contrast` checks the colours that touch in every mark's drawings.
- `emit social` without `--mark` makes the repository's own images: every mark side by side, each with its drawn
  wordmark under it (`templates/lineup.html`).
- The book shows every mark: on the cover, in a size table per mark, and in the wordmark chapter (`<id>-wordmark.svg`).
  `finish.sh` runs each pack once per mark.

### Changed

- Pixel-art marks and lettering (`shape-rendering="crispEdges"`) are scaled by whole numbers on cards, banners and the
  side-by-side image, so every pixel stays square. Vector art is unchanged.

### Fixed

- A `-dark.svg` next to a drawing could be a symlink that leads out of the project, and the emitters, `logo-sheet` and
  `board-lint` read it. Every such path is now confined to the project, as is a logo name in a book chapter
  (`{{marks:../x}}`), which exits 2. Every emitter also checks a `-dark.svg` as pure vector before it uses it.

## [0.3.1] - 2026-10-21

Fixes from the first projects built on 0.3.0: banners and cards show the drawn name, the browser tab shows the small
drawing, and see-through colours keep their alpha.

### Added

- `favicon.drawing` in `qa/rules.json` fixes the drawing of `icon.svg`. It is kept in the project, so a rerun of
  `emit web` keeps it.

### Changed

- Banners (`emit profiles`), social cards (`emit social`), the Play feature graphic (`emit android`) and the Chrome promo
  tiles (`emit chrome-ext`) show the brand's drawn lettering: `lockup.svg` on its own, else `wordmark.svg` next to the
  mark. `--logo-svg` names another file, and `--lettering lockup` or `--lettering wordmark` says which it is when its
  file name does not. `--name` types the name in the system font instead, and cannot be combined with `--logo-svg`.
  Without a lockup or wordmark, or with a template that has no `{{lettering}}` placeholder, the name is typed too and
  the report warns. The dark README header uses the lettering's `-dark.svg`.
- `icon.svg`, the favicon browsers show in the tab, is the band rule's drawing for the tab size instead of the large mark
  shrunk. Its dark switch is that drawing's `-dark.svg`, checked as pure vector like the drawing.
- `shot` loads lazy images first, waits for running animations and transitions to end (at most 15 s), and documents
  `--wait` and `--dsf` in its usage line.
- The designer agent can take 120 turns instead of 60 and is told to return its result before the limit. The
  `directions` workflow names the turn limit as the likely cause when a designer returns nothing, and says where its
  files are.

### Fixed

- `tokens.css` kept a see-through colour opaque (`#3a2448` for a scrim at 56%). It is now `#3a24488f`, and the round
  trip compares the alpha in every output, the `@supports` values in oklch, oklab and display-p3 included, so the loss
  can no longer pass.
- The book's `self:durations` check and `BRAND.md` read only `duration.*` tokens, but the starter tokens name them
  `motion.*`: a book with transitions failed its own check. Both names count now.
- `emit print --font-file` escaped the quotes around the family name, so the pieces printed in Times. The name goes into
  the pieces' CSS as written now, in single quotes, and a name with other characters is refused. Without
  `--font-family` the name comes from the font's file name, with an axis tag such as `[wght]` left out.
- `shot` called a lazy image broken when it was hidden at that width or below the fold.
- The print docs cited an intake question 7 that does not exist; print is the owner's opt-in, set by `PRINT_REGION`.
  The tier table marks print PDFs as opt-in, and the manual check lists the signature images at 1x and 2x.

## [0.3.0] - 2026-10-21

The style research now comes before anything is drawn, marks are drawn on a design tool instead of as code, and the mark
checks judge pixel marks the way they ship.

Breaking changes, each with what to do:

- A round 1 board, and the pick board of a reset round, fail `board-lint` until gate G1s is recorded. A project already
  past round 1: `state --record G1s "n/a: round 1 drawn before the style step"`, or run the style research as round 0.
- A pick board in a round that `reset_rounds` does not list fails `page:data-board`. List the round
  (`state --set reset_rounds=2,3`) or make the page a refine board.
- The `directions` workflow needs the G1s record as its `g1s` argument and does not start without it.
- A last size band with a `max_px` exits 2. Remove `max_px` from the last band: it covers every larger size.
- `logo-sheet` judges only the colours that touch the ground, checks each tile's edge, and says "not verified" for line art
  it cannot measure. Run it again; a deliberate low-contrast edge goes in `tokens/exceptions.json` with a reason.

### Added

- A style research step before anything is drawn, in every tier: Claude researches who sees the mark, where, and what
  the category looks like, then shows a style board (`rounds/r0/board.html`, from `templates/style-board.html`) with
  four to six style territories, each grounded in three or more real, linked references with what to take and what to
  avoid. You tick one or more styles (gate G1s) or say "skip the research". Without web access Claude says the research
  needs it and stops; it never invents references. After a full rejection the style research runs again before the new
  territories, on a new style board in a round listed in `reset_rounds`. That board is required: "skip the research" works
  before the first board of directions only.
- Each reference on the style board can show a small picture of its real mark: an inlined image with alt text, in a figure
  with a caption (the template's caption says "shown for private research"; the words and the language are yours).
  `board-lint` fails a thumbnail without alt text or without a non-empty caption. On a style board it also fails any
  `<img src>`, and any `srcset` on an `<img>` or a `<source>`, that is not an inlined `data:image/` URI: a linked or
  relative image fails. It checks nothing else about the network (CSS `url()` and `<link>` are not read).
- `board-lint` checks the style board (`data-board="style"`, in round 0 or a reset round): audience, surfaces, norm, at
  least four territories with word names and three linked references each, none of these, my call, questions and reply.
  Generic territory names ("Style 1", "Option 2") fail, as they already did for directions.
- After a full rejection the style gate is armed again. The pick board of a reset round fails `board-lint`
  (`project:style-gate`) until a new style board sits in a reset round after the rejected round and the owner's new pick is
  recorded after it, so the first pick no longer stands in. A page that only says `data-board="style"` is not that board: it
  needs the four named territories with content that the style lint asks for, and a copied page that still declares the round
  it came from does not count either. `state --record G1s` now also writes `g1s_round`, the highest round whose
  board is a style board (and removes it when there is none), so a pick recorded before the new style board is written does
  not count as coming after it; `state --set g1s_round=...` is refused.
- The review page of round 0 is a copy of the style board (`board-lint review/index.html --round 0` passes on it).
- Marks are drawn on a design tool: the use-llm design canvas when the session has it, else Claude Code's `/design`,
  which you type because Claude can't start it. Without either, Claude says what is missing and draws the marks as SVG
  itself only after your yes, as a weaker choice. The drawing brief goes to `brief/canvas-round-<N>.md` from a new
  template, and the marks you keep come into the round as SVG with a `SOURCE.md` per direction (the tool, prompts, image
  model, cost, tracing and hand fixes). From round 2 the brief has the drawing session start from a copy of the previous round,
  as every round does. Generated pictures cost money on the canvas, and Claude says the cost in each reply.
- The drawing brief gives every option an ID that names its board (for example `family1-bc-3`, so "the 3" can't mean two
  options), sends your board answers to the brand-creator session, keeps drafts in the project instead of a session's
  scratch folder, and sets an agent budget per run. Each `SOURCE.md` records the lineage of every kept mark and the agents and
  tokens of each run.
- A screening override goes on record: when you keep an option the screening or a judge flagged, a line in
  `BRAND-STATE.md` says why and which extra check it triggered, and that check runs before G3.
- Before you approve a refined round (G3), `board-lint` measures the round's kept marks and warns without failing the board: a
  colour that touches the background under the target (3:1, or your tokens' `touching.ground`), on light or on dark, and
  pixel marks of one family drawn with different outline widths (one at 2 px, its siblings at 1 px).
- A behaviour eval, `style-gate-before-first-board`: on a fresh project the first turn draws no board of directions, and
  without web tools Claude says the style research needs web access and stops.

### Changed

- Logo masters are vector. The mark is a pure-vector SVG and every PNG or icon is exported from it. Generated images,
  photos and sketches are for exploring: a board labels them as exploration, and one becomes the mark only after it is
  traced or redrawn as vector and fixed by hand. Refining a mark means editing the SVG, not generating a new image.
- Every pick board waits for the style pick: `board-lint` fails the round 1 board, and the pick board of a reset round,
  while gate G1s is not recorded (a pick, "skipped by owner" or an honest "n/a" all count for round 1). The state file has
  a new `G1s` gate. Projects already past round 1 record G1s honestly, for example
  `state --record G1s "n/a: round 1 drawn before the style step"`, or run the style research as round 0 now.
- The hook keeps `rounds/r0/` writable while G1s is empty, so a project that is already past round 1 can still run its
  style research as round 0. Once G1s is recorded it is read-only like any earlier round. The hook opens `rounds/r0/` only
  when it reads the state file's `gates:` block with certainty: a tab in the indentation, a quoted key or a `gates:` with a
  value on its own line (`gates: {G1s: ""}`) leaves it locked. `patch` follows the same rule, so it edits `rounds/r0/` exactly
  when the hook allows a write there.
- Direction and territory names are checked against a longer list of labels: "Territory 1", "Style A", "Option B", "Look 2",
  "Mood 3", "Direction II", "Option #2" and "Style-3" fail, as the option, direction, variant, style, concept and route
  labels did. Words that only start like a label (Harbor, Quarry, Looker, Moody, Routes) pass.
- `/brand-creator:round` takes `style` as a board kind, builds round 0 from the style board template and runs
  `state --require G1s` before any round 1 or reset pick board. The `directions` workflow takes the G1s record as its
  `g1s` argument and refuses to start without it, as `adopt` does without `g6`.
- The bakery, photographer and round-1 board evals skip the style research in their prompts (the photographer prompt in
  Polish) so they keep testing the first board of directions.
- A pick board belongs to round 1 or to a round listed in `reset_rounds`. `board-lint` now fails a pick board in any later
  round (`page:data-board`: later rounds are refine boards). It used to accept one, so a pick board in round 2 that nobody had
  listed passed on the old style pick.
- `board-lint` and `state` read a page the same way: its round and its kind come from one tag, the body (or the html tag when
  the body has neither), so `<html data-board="style"><body data-round="2" data-board="pick">` is a pick board.
- In an older project, an earlier reset round's pick board fails `board-lint` when it is linted again (`project:style-gate`: no
  new style board in a reset round after the rejected round, and no `g1s_round`), and so does a pick board in round 2 or later
  that was never listed in `reset_rounds`. `brand-creator check` lints no round itself: it reads the `board-lint` report of the
  latest round only (`rounds/r<N>/board.html`, N the highest) and asks for a new lint when that page changed, so only a round you
  lint again can fail.
- `brand-book`'s listing text names the optional chapters (tone of voice, photography), the clean-up of the options you
  decided against, and says that a brand book for a brand that does not exist yet starts with `brand-creator`, even when the
  ask says "brand book" or "księga znaku". In its trigger evals Sonnet now passes 27 of 27 queries (24 before) and Haiku 25 of
  27 (23); Haiku still misses a clean-up request and still starts it for a new brand's book asked for in Polish.

### Fixed

- `logo-sheet` holds only the colours that touch the ground to the contrast target, found in the pixels as `contrast` finds
  them. A cream face inside a black outline no longer fails on white, while a fill that runs off the drawing's edge still
  counts. The target is your tokens' `touching.ground` unless you pass `--min-contrast`, and `tokens/exceptions.json` excuses
  a colour against the ground as it does for `contrast`. Each tile's own edge must reach the target too, so a keyline thinner
  than a pixel at 16 px fails there. With size bands in `qa/rules.json`, each tile is drawn from its band's drawing, and a
  pixel drawing at the largest whole-number scale that fits, so the 16 px tile shows the 16 px drawing. Artwork with
  gradients, or line art whose colours cannot be measured, says "not verified" instead of passing. A change to the bands or
  the tokens makes the sheet stale for `check`, and a run that stops on a band error records the failure.
- A last size band with a `max_px` (so nothing would draw a larger size, and the emitters would crash there) now exits 2
  with the reason: the last band covers every larger size.
- A small accent that fails the 4×4 rule on purpose (a row of 2 px cells that reads as a row) no longer blocks `check`
  forever: `qa/rules.json` takes an exemption for one master up to a size, with your reason. The miss is then a warning that
  carries the reason; another master's miss still fails, and an exemption that excuses nothing is reported.
- `downscale` says when its master is one size band's drawing: which sizes ship another drawing, and that those are measured
  as shipped with `--png`. Its other rows still show what a system that shrinks the one master (an app icon) would make of it.
- `state` counts round 0 as a real round: `state --json` reports `latest_round` as `r0` for a project whose only round is
  the style board, instead of none.
- `state --set reset_rounds=[2,3]` saved the text "[2,3]" instead of a list, and `board-lint` read it one character at a time,
  so `[10,11]` meant rounds 1, 0, 1 and 1. `state --set` now writes a real list for `reset_rounds` and `book_chapters`
  (`reset_rounds` takes whole numbers from 1 and exits 2 for anything else), and a project that still holds the quoted text
  reads right too, `"[10,11]"` as rounds 10 and 11.
- `state --set "reset_rounds =2,3"` (a space before `=`) skipped the checks and wrote a key that left the state file unreadable.
  Spaces around the key and the value are now trimmed, and a key that is not one word exits 2.
- `board-lint rounds/r2/board.html --round 1` linted the page as round 1. A `--round` that contradicts the page's folder now
  exits 2.

## [0.2.3] - 2026-10-20

### Changed

- Agent descriptions no longer name the model tier ("Opus-tier", "Sonnet-tier"): each agent's `model` field holds it, and `brand-creator fleet-plan --check` no longer asks for it in the prose.

## [0.2.2] - 2026-10-20

### Added

- A commands reference page in the manual lists every command, workflow and agent, who can start each one, and its
  arguments.
- An index of the reference files the `brand-creator` skill reads
  (`skills/brand-creator/references/_index.md`), linked from the skill.

### Changed

- The README is now a short storefront. Everything else moved into a manual under `docs/manual/`: a first-brand
  walk-through, one how-to page per task, and reference pages for commands, settings, permissions, costs, agents and
  workflows, platform support, Claude Code versions and troubleshooting.
- The README's reference and development halves moved: contributor notes are in `docs/internals/`, and the build log
  and decisions log are archived in `docs/archive/`. New decisions are recorded as ADRs in `docs/adr/`.
- The plugin description is now one plain sentence: "Make a logo, colours and every brand file your product needs, step
  by step, with you deciding at each step."
- `CONNECTORS.md` uses plain words instead of internal step codes: writes to a design tool happen only after you approve
  the finished files.
- The listing text of the `brand-creator`, `brand-assets`, `brand-book` and `brand-naming` skills is shorter and in plainer
  words. When they start is unchanged, but the trigger evals have not been re-run for the new wording.
- The `/` menu descriptions of the typed-only commands (`new`, `round`, `status`, `check`, `review`, `launch`, `setup`
  and `brand-adopt`) now say in plain words what each does and end with "Runs only when typed as
  /brand-creator:<name>." `brand-adopt` also says how it differs from the adopt workflow.
- The agent descriptions keep the "Only for brand-creator workflows or an approved fleet; do not auto-delegate." opener,
  then say in one plain sentence what the agent does. The model and tools are set in each agent's own fields.
- The author in `plugin.json` is now Jacek Pytlik, and the marketplace entry carries only the name, source, category and
  tags; the description and links live in `plugin.json`.
- The trigger-eval list moved from `dev/trigger-evals.json` to `evals/trigger-evals.json`.

## [0.2.1] - 2026-10-19

### Changed

- The descriptions in Claude Code's `/` menu, skill list and agent list now say in plain words what each command, workflow
  and agent does and when it may run, instead of internal gate codes such as "G0" or "after G6". What each one does, and
  when it is allowed to run, is unchanged.

## [0.2.0] - 2026-10-19

**Breaking:** brand-creator is now listed in the `jack1913` marketplace, in `plugins/brand-creator/` of
[jack1913/claude-plugins](https://github.com/jack1913/claude-plugins). The install ID changes from
`brand-creator@brand-creator` to `brand-creator@jack1913`. Claude Code can't move an install between marketplaces, so
move it by hand:

- `claude plugin uninstall brand-creator@brand-creator`;
- `claude plugin marketplace remove brand-creator`;
- `claude plugin marketplace add jack1913/claude-plugins`;
- `claude plugin install brand-creator@jack1913`.

If you wrote a permission rule with the plugin's full path, its folder changed from `cache/brand-creator/brand-creator/`
to `cache/jack1913/brand-creator/`. The `Bash(brand-creator *)` rule needs no change.

### Fixed

- The safety hook is stricter about archives: it blocks an extract into a round, a project folder or a folder above one,
  refuses an extract it can't see into, and reads tar, unzip and 7z options the way those tools do.
- The safety hook treats `git stash push -u` or `-a` without a precise path as covering the whole working tree, so it
  can't sweep up locked rounds.

### Changed

- The README is rewritten for users: what to say, what you get, and a troubleshooting table near the top. The reference
  half is unchanged.

## [0.1.0] - 2026-10-18

The first release.

### Added

**The process.**

- The `brand-creator` skill runs a brand-identity project as phases with owner gates (G0 scope to G7 outward hand-offs, plus
  the G-sys tripwire after a third patch in one area), in three tiers: Quick, Standard and Full. It resumes from the
  project's `BRAND-STATE.md`, works for any kind of business or person, and also fires for work on a brand project's files
  and for a brand's launch steps (handed to the owner, never done for them).
- G0 asks at most three concrete scope questions (tier; architecture only when a parent brand or siblings show; the name only
  when it is open), each with a recommended answer, and states the rest as defaults. It asks once before boards are uploaded
  to claude.ai. Without a question tool, the same questions come as one plain-text message.
- Round 1 shows three divergent directions with a strategy core, a positioning map, the hardest surface, "Today" when a mark
  exists, "None of these" and numbered questions with lettered options. Directions keep stable word names; a choice is
  restated before an expensive build; the liked direction is deepened, never hybridised after the pick.
- User skills: `/brand-creator:new`, `round`, `status`, `setup` (a consented install into the plugin's data folder),
  `check` (every gate, plus `--cascade` for old values), `review` (the self-review as one approvable list), `brand-adopt`
  and `launch`. Model-invocable skills: `brand-naming`, `brand-assets` and `brand-book`.
- Phase references 00 to 13, a board contract, working-style defaults, anti-pattern case cards, a strategy core,
  architecture modes (standalone, family-member, product-in-family), a cascade checklist, regulated-industries rules and
  a synthetic worked brand (Acme).

**Checks** (each writes a report; a check that cannot run is "not verified", never a pass).

- `board-lint`, `shot` (1440 and 390 px, light and dark), `contrast` (text, UI and the colours that touch in the mark) and
  `contrast --cvd`, `logo-sheet` and `logo-sheet --guides`, `downscale` (one report per master), `states-check`,
  `family-check`, `fontcheck` with the platform-font report, `outline-glyphs`, `shot --motion`, `snapshot`,
  `verify-idempotent`, `staleness`, `specs-due`, `book-lint`, `print-check`, and `check`, which gates them all and verifies
  the frozen history's checksum manifest.
- Owner thresholds in `qa/rules.json` and size bands; the plugin's numbers are proposals.

**Tokens and assets.**

- Design tokens from DTCG 2025.10 sources to CSS, JSON, Swift, Android XML and colour sets.
- `emit web` (favicons drawn per size band, PWA icons, head snippet), `emit social` (social card, GitHub and README header
  images; `--posts` for carousel, square and educational posts), `emit profiles` (circle-safe avatar and banner images inside
  each platform's safe area).
- Platform packs for the Full tier, every size read from `scripts/emitters/platform-specs.json` with its source, date and
  status: Apple (an Icon Composer `.icon` compiled by actool per platform, legacy sets, visionOS, watchOS and tvOS; macOS with
  Xcode only), Windows, Linux, tray, Tauri, Wallet, developer, Android (adaptive icon with a monochrome layer and a 66 dp
  safe-zone gate), Chrome extension and MSIX. Files built from a size not yet read at the platform's own page are labelled
  `UNVERIFIED, recheck`, and `check` fails a file that lost the label.
- `templates/finish.sh.tpl`: the whole build chain in order, each step gated by the tier.

**Brand book, print and press.**

- `book` builds one self-contained `book.html` (a short guide in Quick, the whole book in Standard and Full), byte-identical
  on rebuild, with computed counts and ratios; `book-pdf` exports an RGB proof; `patch` edits a hand-authored book with counted
  replacements; `collapse` removes losing variants with a dated copy.
- `emit print`: business card, letterhead and envelope (EU, US or JP sizes, bleed, crop marks, outlined text, boxes set) and an
  HTML e-mail signature. Without the printer's profile a file is an "RGB proof, not print-ready", with it only a "PDF/X-4
  candidate". `emit presskit` writes a deterministic zip.

**Naming.**

- `brand-creator names` screens names against domain registries and, for software brands, package registries, and reports
  REGISTERED, NOT-FOUND or UNKNOWN, never "available". It asks before sending names anywhere, saves raw responses for
  replay and links trademark searches for the owner to run. The `brand-naming` skill writes a go / go-with-conditions / no
  verdict memo.

**Adoption and launch.**

- `adoption survey` reads product repositories read-only and writes `ADOPTION.md` as numbered, append-only rows;
  `check --cascade` finds leftovers of an old value across every project file; opt-in `BRAND.md` and `DESIGN.md` adapters and
  a per-brand applied skill; `launch-todo` writes `LAUNCH.md` from local files only.

**Agents and workflows (opt-in).**

- Seven agents (`brand-designer`, `brand-judge`, `brand-reviewer`, `brand-researcher`, `brand-inventory`,
  `brand-implementer`, `brand-namer`), none of which can start other agents or is delegated to automatically, and four
  workflows (`directions`, `review-panel`, `naming`, `adopt`), each ending before an owner gate. A fleet runs only after the
  owner has been told the agent count, models, size and rough cost and said yes; `fleet-plan` dry-runs one with stub agents.

**Safety.**

- A hook keeps `history/` and earlier rounds read-only and stops a brand project folder from being deleted or moved (shell writes,
  deleters, destructive git, and archive extracts it cannot see into are blocked, failing closed when unsure); the RULES
  line in every skill, agent and workflow forbids commits, pushes, deletes and outward actions unless asked.

**Platforms and tests.**

- Tested on macOS; the suite and the end-to-end smoke also run on Linux in a container (`tests/docker/`). Windows is untested.
- pytest and node:test suites with mutation tests for each gate, the Acme end-to-end smoke, a Quick-tier smoke on a PATH with no
  Apple tools and no git, 17 behaviour evals (`evals/`, billed, run by hand) and trigger evals (`dev/trigger-evals.json`),
  and a CI workflow (Linux, `claude plugin validate --strict`, macOS) that runs once the repository is pushed.

Known limits at 0.1.0:

- Windows has never been run. On Windows the safety hook needs `python3` on PATH.
- The behaviour evals were run once (2026-10-18); see [Evals](docs/internals/evals.md) for the results.
- Some platform sizes are unverified and labelled so; recheck them with `brand-creator specs-due`.
- In Quick, `emit social` also writes GitHub and README header images, and profile images need Standard.
