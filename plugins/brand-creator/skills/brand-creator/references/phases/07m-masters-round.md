# P7m The masters round (ads and decks)

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [The round](#the-round)
- [Checks](#checks)
- [Gate](#gate)
- [After the approval](#after-the-approval)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

Standard and Full, after G4, and after G4p when the brief lists a site: the approved ads and decks ("masters") every later
ad or presentation starts from, in two or three directions first, checked by the plugin and approved by the owner (G4m).

On the pilot brand the first ads and deck were built as one variant in minutes, and the owner rejected all of them as
generic. Three directions made from the brand's own world were approved. After the site was approved, the masters had to be
rebuilt in the site's language, and four layout faults were found only by eye in PowerPoint (a panel over the logo, an
amount running into a number, a cut label, a stamp over a word).

## Inputs

Name each on the board, and start from them:

- the approved pages in `site/` (when there is a site): the masters speak the site's language;
- `assets/masters/` (when masters were approved before): the round changes them, it does not start over;
- the motion tokens (`motion/motion.json`): a logo reveal in an ad uses them;
- FACTS.md: no copy that FACTS.md does not hold; sample data is labelled as sample data.

## Outputs and paths

- `rounds/r<N>/board.html` (`templates/masters-board.html`), `rounds/r<N>/masters.json`, the masters, the round's builder,
  `rounds/r<N>/png/` (from `masters check`), the report `masters` and the `board-lint` report.
- After G4m: `assets/masters/` with `README.md` and `masters.json` (`masters approve`).

## The round

1. A new, empty folder `rounds/r<N>/` (do not copy an earlier round). Board: `templates/masters-board.html`
   (`data-board="masters"`).
2. Build the masters with a script in the round (`build.mjs` or similar, named in `masters.json` as `builder`). Each ad and
   slide is an HTML file at its canvas and declares it: `<meta name="masters-canvas" content="1080x1350">`. The first
   masters board shows **two or three directions**, each in every size the brief asks for (`masters:directions` fails one).
3. A deck in PowerPoint, when asked: build it with `pptxgenjs` (installed by `setup` in the data directory), then embed the
   brand fonts with `brand-creator masters embed-fonts <deck.pptx> --font <file.ttf>...`. A deck PDF goes through
   `brand-creator pdf normalise <file.pdf>`.
4. Write `masters.json`: every master with `file`, `kind` (`ad`, `slide`, `deck-html`, `deck-pdf`, `deck-pptx`, `image`,
   `font`), `canvas` (for an ad and a slide), `direction`, an optional `note`; and the brand's `copy_rules` (for example
   "no amounts or names in ads").

## Checks

1. `brand-creator masters check` opens each ad and slide at its canvas after its animations end, writes `png/`, and fails
   an element outside the canvas, a text that runs into another text, a deck PDF with the wrong pages or its own dates,
   and a font not embedded in the PowerPoint file (a shape box past the slide edge warns). An element painted over a text warns; mark one drawn
   there on purpose (a stamp) with `data-masters-overlay`, and the board lists it.
2. `brand-creator board-lint rounds/r<N>/board.html`.
3. The PowerPoint render is the owner's check: ask them to open the deck in PowerPoint (preferred; Keynote and Google Slides
   ignore embedded fonts) and say whether it renders with the brand fonts and nothing overlaps. Until their answer is in
   G4m, `masters:pptx-render` is NOT VERIFIED.

## Gate

`brand-creator state --record G4m "<the directions approved>; PowerPoint: <their answer>"` (leave out the PowerPoint part when
there is no deck). Then run `masters check` again: the PowerPoint row passes once the answer is recorded.

## After the approval

1. `brand-creator masters approve` copies the masters, and every file they load, into `assets/masters/` byte for byte, with
   `README.md` (what each file is, its size, the copy rules, how to rebuild, the font note) and `masters.json`.
   `--replace` moves earlier masters to `removed-<date>/assets-masters/` first.
2. `brand-creator kit build --yes`: the kit carries `assets/masters/`. `kit check` names the recipes that use the masters
   (`recipes/ad.md`, `recipes/presentation.md`) once the masters change, until they are read against them.
3. The book: the opt-in chapter "Ads and decks" (`masters` in `book_chapters`) or the `{{masters}}` block in a chapter.
4. Freeze the round if the owner wants it kept as written: `freeze r<N> --name approved-masters`.
5. When the site is approved later, `check` shows `masters:behind-site`: offer a new masters round.

## Pitfalls

- One variant built fast reads as a template: the first board shows directions made from the brand's world, not a layout
  any company could have.
- A Keynote export is no proof of a PowerPoint deck: Keynote shows a substitute font for embedded ones.
- Copy the masters only through `masters approve`: a file copied by hand into `assets/masters/` has no README row and no
  record of the approval.

## Enforcement

`board-lint` (`masters:gate`, `masters:manifest`, `masters:files`, `masters:canvas-size`, `masters:directions`), `masters
check` (`masters:canvas`, `masters:covered`, `masters:pdf`, `masters:pptx`, `masters:pptx-boxes`, `masters:pptx-render`), `masters approve`
(refuses without G4m and a current passing `masters` report and lint), `check` (`masters:behind-site`), `kit check`
(`kit:behind` after new masters).
