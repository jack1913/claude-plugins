# What it makes

What each step of a brand project produces, in more detail. For a short list by task, see the
[how-to pages](../README.md#do-something).

Every step is a `brand-creator` command that the skills run for you. `brand-creator --help` lists them all.
A synthetic worked brand, Acme, shows a finished project: `skills/brand-creator/references/examples/acme/` in the plugin.

## Boards and rounds

Round pages are built from a template, checked by `board-lint` and photographed by `shot` at 1440 and 390 pixels wide, in
light and dark. Approved rounds are frozen with `freeze` into `history/`, with a checksum manifest that `check` verifies.

## Checks

Each check writes a report to `assets/_checks/`. `check` reads every report that exists, and a check that cannot run is
"not verified", never a pass.

| Command | What it proves |
| --- | --- |
| `contrast`, `contrast --cvd` | Text, UI and mark contrast in light and dark. Colours stay distinguishable under protan, deutan and tritan colour-blindness simulation |
| `logo-sheet`, `logo-sheet --guides` | The mark at real sizes. Baseline, cap line and x-height measured on the ink |
| `downscale` | What survives when one master is shrunk to the sizes systems show: accent pixels, bounding box and the solid-square rule |
| `states-check` | State sets (idle, active, error) differ in greyscale and in silhouette |
| `family-check` | Family modes: shared glyphs equal the family's sources, and tile shares agree across products (`FAMILY.md`) |
| `fontcheck`, `fonts` | Glyph coverage for the brand's languages, a licence hint, and which font Chromium really used |
| `outline-glyphs` | Type-based marks as paths with no live text |
| `shot --motion` | Animation states equal the static mark. Reduced motion shows the still. No layout shift |
| `snapshot`, `verify-idempotent`, `staleness`, `specs-due` | Byte-identity proofs, two-run idempotence, stale packs, and platform sizes due for a recheck |

The thresholds are yours, kept in `qa/rules.json`. The plugin's numbers are proposals and say so.

## Web, social and profiles

- `emit web`: favicons drawn per size, PWA icons and a head snippet.
- `emit social`: a social card, plus GitHub and README header images when the brief or inventory lists a code repository.
- `emit profiles`: in every tier, a circle-safe avatar. Standard and Full add banner images for LinkedIn, X, YouTube,
  Facebook and Instagram, each inside the platform's safe area.

Sizes the project has not read at the platform's own page are labelled `UNVERIFIED, recheck`, and `check` fails a file
that lost the label.

## Platform packs (Full tier)

`emit apple` (an Icon Composer `.icon`, compiled per platform, legacy sets, and visionOS, watchOS and tvOS when your
product targets them; macOS with Xcode only), `windows`, `linux`, `tray`, `tauri`, `wallet`, `developer`, `android`
(adaptive icon with a monochrome layer, Play icon and feature graphic; refused when the mark leaves the 66 dp safe
zone), `chrome-ext` and `msix`. The `brand-assets` skill runs them from an approved mark. Without a project it writes
into `./brand-assets/`.

## The brand book

`book` builds one self-contained `book.html` (no script, no network, light and dark) from your tokens, the files the
emitters wrote, the state, the facts, the check reports and your chapter text. In Quick it is a short guide: idea, mark,
colour, files, changing the brand. Counts and colour ratios are computed, so they cannot drift. `book-lint` checks it.
`book-pdf` exports an RGB proof labelled "RGB, not print-ready". A hand-drawn mark has a hand-written book that `patch`
edits with counted replacements.

## Print, press kit and posts (Standard and Full)

- `emit print`: a business card, letterhead and envelope (EU, US or JP sizes, bleed that is the printer's to confirm,
  crop marks, text outlined) and an HTML e-mail signature. `print-check` reads the files back.
- `emit presskit`: a zip of logos, tokens and the book PDF.
- `emit social --posts`: carousel, square and educational posts from your facts, with a pre-publication checklist for
  regulated professions.

## Naming

`brand-creator names <name>...` screens candidates against domain registries (RDAP, whois, DNS) and, for software brands
only, npm, GitHub, Docker Hub, PyPI, crates.io and Homebrew. It lists the services first and needs your yes. Trademark
offices are never queried: the memo carries search links you run yourself. The `brand-naming` skill grows and filters
candidates, checks meaning in each audience language and writes a go, go-with-conditions or no verdict.

## Adoption and launch (Full tier)

- `adoption survey` reads your product repositories read only for every place the old brand shows, and writes
  `ADOPTION.md` as numbered rows.
- `check --cascade "<old value>"` (the leftover search) finds leftovers of a changed rule, token or colour across the project.
- When you approve the finished files, you may opt into `BRAND.md` and `DESIGN.md` for other agents, and a small
  per-brand skill in your project's `.claude/skills/`.
- `launch-todo` writes `LAUNCH.md`: trademark first, then domains and handles with the date each was checked, renames and
  the print hand-off. It only reads local files.

## Connectors

None is needed, and no MCP configuration ships. A connected design tool is read only when you point at a file, and
written only when you ask. See [CONNECTORS.md](../../../CONNECTORS.md).

## Related

- [Glossary](glossary.md)
- [Commands](commands.md)
