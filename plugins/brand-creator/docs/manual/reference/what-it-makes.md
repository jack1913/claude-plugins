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
| `logo-sheet`, `logo-sheet --guides` | The mark at real sizes, each size from its own drawing when you have one per size. Baseline, cap line and x-height measured on the ink |
| `downscale` | What survives when one master is shrunk to the sizes systems show: accent pixels, bounding box and the solid-square rule |
| `states-check` | State sets (idle, active, error) differ in greyscale and in silhouette |
| `family-check` | Family modes: shared glyphs equal the family's sources, and tile shares agree across products (`FAMILY.md`) |
| `fontcheck`, `fonts` | Glyph coverage for the brand's languages, a licence hint, and which font Chromium really used |
| `outline-glyphs` | Type-based marks as paths with no live text |
| `shot --motion` | The mark's motion is stepped through, not waited for: no layout shift, the animated parts stay on a phone screen (360 and 390 pixels wide), the rest frame equals the still to the pixel, and pixel marks move in whole pixels. Reduced motion shows the still. Motion a script draws frame by frame (`requestAnimationFrame`) cannot be stepped through, so its phone-screen check says "not verified". One report per proof file |
| `frames` | Stills of the mark along its motion, a strip of them and the reduced-motion still, written into `motion/frames/` for the brand book |
| `snapshot`, `verify-idempotent`, `staleness`, `specs-due` | Byte-identity proofs, two-run idempotence, stale packs, and platform sizes due for a recheck |

The thresholds are yours, kept in `qa/rules.json`. The plugin's numbers are proposals and say so.

## Tokens

`tokens` turns your colour, type and motion tokens into files for code, in `assets/tokens/`: CSS variables, a JSON copy,
Swift colours with an asset catalogue, and Android colours. Durations and easing curves reach the apps too: Swift gets
`BrandMotion`, and Android gets `motion.xml` and one interpolator per curve. Each file is read back and compared with your
tokens before the build passes. A file your tokens no longer produce, like the colour set of a role you removed, is
moved to `removed-<date>/`.

When something moves, `motion/motion.json` says how: the signature move, the moving parts, a timeline written in your
duration and curve tokens, and the motion rules. When nothing moves, it says why. BRAND.md, DESIGN.md and the brand's
own skill repeat it.

## Web, social and profiles

- `emit web`: favicons drawn per size (the browser tab gets your small drawing), PWA icons and a head snippet.
- `emit social`: a social card, plus GitHub and README header images when the brief or inventory lists a code repository.
- `emit profiles`: in every tier, a circle-safe avatar. Standard and Full add banner images for LinkedIn, X, YouTube,
  Facebook and Instagram, each inside the platform's safe area.

Cards and banners show your name as you drew it (your lockup, or your wordmark next to the logo). Without either, the
name is typed in a plain system font, and the report tells you so. Pixel-art logos are scaled by whole numbers, so every
pixel stays square, and the line under the name gets square ends to match.

Several products with their own logos, sharing one look? Each logo gets its own files: favicons, cards and headers. Your
repository also gets images that show all of them side by side.

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
