# Script contract

Every brand-creator script follows this contract. `scripts/lib/_common.py` and `scripts/lib/_common.mjs` implement it
once; a script that does not use them is wrong, not special.

## Contents

- [Entry point and data directory](#entry-point-and-data-directory)
- [Project discovery and confinement](#project-discovery-and-confinement)
- [Reports](#reports)
- [Exit codes](#exit-codes)
- [Renderer flag](#renderer-flag)
- [Runtimes and locks](#runtimes-and-locks)
- [Project file conventions](#project-file-conventions)
- [BRAND-STATE.md frontmatter](#brand-statemd-frontmatter)
- [Token sources (DTCG 2025.10)](#token-sources-dtcg-202510)
- [Board contract (data attributes)](#board-contract-data-attributes)
- [Hook guard](#hook-guard)
- [Platform specs and emitters](#platform-specs-and-emitters)
- [Name screening](#name-screening)
- [QA gates and mark tooling](#qa-gates-and-mark-tooling)
- [Brand book](#brand-book)
- [Print, press kit and social posts](#print-press-kit-and-social-posts)
- [Adoption, cascade, adapters, applied skill and launch](#adoption-cascade-adapters-applied-skill-and-launch)
- [Tier B emitters: Android, Chrome extension, MSIX](#tier-b-emitters-android-chrome-extension-msix)
- [Tier B: watchOS and tvOS, profiles, and the finish chain](#tier-b-watchos-and-tvos-profiles-and-the-finish-chain)
- [Agents and workflows](#agents-and-workflows)
- [Testing](#testing)
- [Linux validation and CI](#linux-validation-and-ci)

## Entry point and data directory

Skills call `brand-creator [--data <dir>] <subcommand> ...` (Claude Code puts the plugin's `bin/` on the Bash PATH; a host
that does not, such as a `claude plugin eval` run, gets `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"`, the same file, and the
skills say so). `setup`, `prereq`, `state` and `version --check` run on the first `python3` on PATH that starts and is 3.10 or newer (a broken
or older one earlier on PATH is skipped, as uv skips it for the other scripts); none → exit 3 naming each one tried.
Skills pass `--data "${CLAUDE_PLUGIN_DATA}"`, always quoted (a data path may hold a space; a test fails on any
unquoted form in the skills). `BRAND_CREATOR_DATA` is the environment equivalent. Every subcommand
except `help`, `version` (and `version --check`, see the finish chain), `root` and `prereq` needs one of them and exits 2 with a clear message otherwise. The data directory
holds `node_modules/`, the Chromium build (when setup had to install one), `setup.json`, `cache/` (the IANA RDAP
bootstrap, 24 h) and scratch output. Nothing
is ever written under the plugin root (it changes on every update).

`bin/brand-creator` resolves the plugin root from its own path and exports `BRAND_CREATOR_ROOT`, `BRAND_CREATOR_DATA`,
`PYTHONDONTWRITEBYTECODE`. `BRAND_CREATOR_TODAY=YYYY-MM-DD` forces the date written by `state --record`, `new`, `freeze`.

## Project discovery and confinement

Every command takes `--project DIR`, or walks up from the cwd to the first folder holding `BRAND-STATE.md`. When there
is none it exits 2 with: `no brand project found; pass --project`. All writes are confined to the project directory
(a path that resolves outside it, including through symlinks, exits 2). Scratch output (page shots) goes outside the
project, under `<data>/scratch/<slug>-<hash>/`, and `--out` for shots must point outside the project.

## Reports

Every checking tool writes `<project>/assets/_checks/<tool>.json`:

```json
{"tool": "contrast", "version": "<plugin version>", "inputs_sha": "<sha256 over the input files>",
 "inputs": [{"path": "assets/tokens/tokens.json", "sha256": "..."}],
 "renderer": "resvg (default)", "results": [{"id": "...", "status": "pass|fail|warn|info|skipped", "label": "...", "detail": "..."}],
 "status": "pass|fail|not-verified"}
```

`status` is `fail` if any result fails, `not-verified` if any result was skipped (or there were no results), else
`pass`. A skipped check is never reported as a pass. **A run that fails records the failure.** When a run stops through `fail()` (exit
1, 2 or 3) or crashes with any other exception (traceback printed, exit 1) after its report was created, `main_guard()` rewrites that report with status `fail` and an `error` row (the message and
exit code) before it exits, so the previous passing report cannot survive a failed run whose inputs did not change (an Xcode update, a new
`--target`, an actool regression). A failure before the report exists (bad arguments, the wrong platform) writes nothing. An input listed twice is
recorded once. `brand-creator check` reads these reports, recomputes each
report's `inputs` hashes, and treats a stale report (inputs changed since) as not verified. Tool names: `tokens`,
`contrast`, `logo-sheet`, `board-lint`, `shot`, `emit-web`, `emit-social`, `emit-apple`, `emit-windows`, `emit-linux`, `emit-tray`, `emit-tauri`, `emit-wallet`, `emit-developer`, `check`, `names`, `downscale`, `states`, `family`, `fontcheck`,
`motion/<slug>-<hash6>` (from `shot --motion`, one per proof file; see Motion proof) and `frames/<slug>-<hash6>` (from `frames`), `idempotence` (from `verify-idempotent`), `staleness`, `book`, `book-lint`, `book-pdf`, `print-check`, `adoption`, `adapters`, `applied-skill`, `launch-todo`, and one `emit-<target>` per emitter (with several marks, `emit-<target>/<mark>` and `logo-sheet/<mark>` per mark)
(`emit-web`, `emit-social`, `emit-apple`, `emit-windows`, `emit-linux`, `emit-tray`, `emit-tauri`, `emit-wallet`, `emit-developer`, `emit-print`, `emit-presskit`). The renderer in use is stored in the report and
printed on every run.

## Exit codes

| code | meaning |
|---|---|
| 0 | pass (warnings allowed) |
| 1 | a gate failed (a check, a lint, a refused overwrite, a missing recorded gate) |
| 2 | usage error (bad flag, no project, no data directory, path outside the project) |
| 3 | cannot run: a dependency or platform is missing, or the check could not be established; the message names the fix (`/brand-creator:setup`, an install command, or the opt-in flag). Also used for "not yet implemented" stubs. |

## Renderer flag

One fallback flag everywhere: `--renderer=resvg|pillow`. `resvg` (default) rasterises SVG with the resvg program and is
required for any SVG input. `pillow` only resamples PNG input; asked to rasterise SVG it exits 3 and says so. Off
macOS the renderer choice for the downscale check is an explicit opt-in recorded in BRAND-STATE.md
(`renderer: resvg (opted in <date>)`, written by `downscale --renderer=resvg --record-renderer`) and printed on every report. On macOS
`downscale` measures with `sips -z`, the real system downscale. Nothing falls back silently.

## Runtimes and locks

- Python 3.10+ scripts carry PEP 723 inline metadata and a committed lock (`uv lock --script <file>`), and run as
  `uv run --script --locked <file>` (the shebang is the same). They use the standard library, except where a dependency is named in
the script's own block and in `THIRD_PARTY_NOTICES.md` (every one pinned with `==`; a test checks block, lock and notices agree):
fontTools, Brotli and skia-pathops (`outline_glyphs.py`, `fontcheck.py`), Pillow (`downscale_check.py`, PNG resampling only; `emitters/tauri.py`, the
`.icns` writer behind `--renderer pillow`), jsonschema (`emitters/apple.py`, to run the vendored validator) and ColorAide (`contrast.py`, colour-vision simulation) and pikepdf (`book_pdf.py`, `print_check.py`, `emitters/print.py`; these need Python 3.11+).
  `adoption.py` calls ripgrep (`rg`) as an external program (exit 3 with the install command when it is missing); the Node dependency `@google/design.md`
  (pinned in `scripts/package.json`, installed by `setup`) is run by `adapters.py` to lint DESIGN.md.
  Bootstrap scripts that must work before uv or Node exist (`setup.py`, `prereq.py`) and the hook (`guard.py`, which
  must start fast on every tool call) run with plain `python3` and have no lock.
- Node 22+ scripts are ESM (`.mjs`). Dependencies are pinned exactly in `scripts/package.json` with
  `package-lock.json`, installed by `setup` (`npm ci`) into `<data>/node_modules`, and loaded with
  `loadDep(name)` (createRequire resolution from the data directory).
- Chromium is driven by `render.mjs` only. `setup` reuses an existing Playwright build that matches the pinned
  revision (PLAYWRIGHT_BROWSERS_PATH or the default cache) and otherwise installs one into `<data>/browsers`.

## Project file conventions

```text
<project>/
  BRAND-STATE.md  FACTS.md  brief/BRIEF.md
  research/research.md  research/YYYY-MM-DD-<topic>.md  research/positioning-map.md   P1 output (templates/research.md)
  research/cliches.md              (optional; "Forbidden" bullets feed the FORBIDDEN count in shots; templates/cliches.md)
  research/names/<date>-check.md  research/names/<date>-verdict.md  research/names/raw/<date>/run-<n>/   P2 (names, brand-naming)
  INVENTORY.md                     P1c surface inventory (templates/INVENTORY.md); board-lint needs it in Full / product-in-family
  rounds/r0/board.html             round 0: the style board (P1s, from templates/style-board.html); no mark is drawn in it
  rounds/r1/board.html ...         one folder per drawn round; the page is board.html
  rounds/r<N>/<direction>/<item>.svg, <item>-16/-32/-128.png, SOURCE.md   the kept marks of a drawn round: SVG masters, PNGs
                                   exported from them, and where they came from (templates/SOURCE.md; drawing-engines.md)
  rounds/r<N>/<variant>/           a motion round (data-board="motion", templates/motion-board.html; see Board contract): one folder per variant with index.html (the move where it
                                   will be seen), proof.json (a page case named <variant>) and frames/<variant>/ (the stills `frames` took of it)
  brief/canvas-round-<N>.md        the drawing brief of round N (templates/canvas-brief.md)
  .design/<slug>/                  the use-llm design canvas, when the drawing session starts in the project folder
  research/YYYY-MM-DD-style.md  research/style-thumbs/   P1s notes behind the style board and the reference marks it shows as thumbnails
  tokens/{primitives,semantic.light,semantic.dark}.tokens.json
  assets/logo/mark.svg, mark-dark.svg     artwork (pure vector)
  assets/tokens/                   build_tokens output (css, json, swift, android, Colors.xcassets)
  assets/web/  assets/social/  assets/apple/  assets/windows/  assets/linux/  assets/tray/  assets/tauri/  assets/wallet/  assets/developer/   emitter output
  assets/print/  assets/presskit/  assets/social/posts/   print PDFs with their `.print.json` sidecars and the e-mail signature; the press-kit zip; social posts
  assets/fonts/                    the brand's font files (read by fontcheck)
  assets/manifest.json             artefacts written by emitters (put-on-byte-change)
  assets/_checks/                  JSON reports, the logo sheet and the guide overlay
  qa/rules.json                    owner thresholds and size bands (see QA gates); optional, proposals apply without it
  qa/print.json                    owner thresholds of print-check (see Print); optional, stated defaults apply without it
  qa/states.json  qa/idempotence.json   state sets for states-check; the byte-difference allowlist for verify-idempotent
  motion/proof.json                the motion proof's cases (shot --motion); any name, in any folder: one report per proof file; the proof of the approved move
  motion/frames/<case>/            the stills `frames` writes of a page case of a gated proof: <NN>-<pct>.png, strip.png, reduced.png, frames.json (inside the project on purpose: the book
                                   replays them; a try-out proof in the latest round or in removed-*/ keeps its stills beside it, in <its folder>/frames/<case>/; history/ and the earlier rounds are read-only: refused)
  motion/motion.json               the one record of the motion decision (see The motion decision): absent = not decided, "off" = nothing moves, "on" = the approved move, which is the machine-readable
                                   motion spec (see Motion spec): signature move, parts, timeline in tokens, rules; read by the adapters and the book
  motion/SPEC.md                   the motion hand-off (templates/MOTION-SPEC.md), only when something moves
  tray/tray.json                   the tray states and their masters (emit tray); qa/states.tray.json is written by it
  tools/inputs.json                staleness record of a generated pack (staleness --write)
  tools/*.py                       the project's own generators (mark grids, glyph tables); built with scripts/lib/px_lib.py
  book/chapters/<id>[.<lang>].md   the book's chapter content (templates/book/); book/book.json optional settings; see Brand book
  book.html  book.pdf              the book (generated, or hand-authored for authored-vector brands) and its RGB proof PDF
  adoption.json  ADOPTION.md       the adoption rows as data (progress and pins apart) and the document rendered from it; see Adoption
  LAUNCH.md                        the owner's launch checklist (templates/LAUNCH.md); see Adoption, cascade, adapters, applied skill and launch
  BRAND.md  DESIGN.md              generated adapters, opt-in at G5 (`adapters`)
  .claude/skills/<slug>-brand/SKILL.md   the per-brand applied skill, written only by `applied-skill --yes`
  tools/cascade.json                  documents outside the project that `check --cascade` searches too (optional)
  removed-<date>[-n]/              dated copies of what `collapse` changed and of slots an emitter retired (never deleted)
  FAMILY.md                        family modes only (templates/FAMILY.md); read by family-check
  history/<date>-<name>/  history/MANIFEST.sha256     frozen rounds (only `brand-creator freeze` adds files)
  DECISIONS.md  decisions/ADR-<NNNN>-<slug>.md   the decision log and the decision records (templates/DECISIONS.md, templates/ADR.md);
                                   append-only by convention (dated amendments), not read by any check, skipped by the cascade
```

Folders are created when their phase starts. `check` gates only what exists.

## BRAND-STATE.md frontmatter

A `---` block of `key: value` lines, one level of nesting, trailing `# comments` allowed; the body is free markdown.
Keys: `slug, name, created, plugin_version, tier (quick|standard|full), phase, architecture (standalone|family-member|
product-in-family), mark_source (generated|authored-vector|existing), language (chat language), content_languages (language-set
codes of the brand's own text, for example `pl` or `pl,en`; read by fontcheck, never defaulted from `language`), renderer, review_surface, review_url,
incumbent (none or a line), inventory (path or "none (no target repo)"), edition (whole number, the brand book's), approved_edition (the edition G5 approved; `state --record G5` writes it), book_chapters (extra
chapters: tone, photography, components), canonical_direction, reset_rounds ([4, 5]: the style board run again after a full rejection,
then the pick board), g1s_round, fixes_per_area (map), gates (G0 G1 G1s G2 G2b G3 G4 G5 G6 G7)`. A recorded gate reads `"<date> <decision>"`;
empty means not recorded. `brand-creator state --record G3 "<decision>"` writes it, `state --require G3` exits 1 when missing.
`state --set KEY=VALUE` trims the spaces around the key and the value (`"reset_rounds =2,3"` is `reset_rounds`, checked as one), and a
key that is not one word (letters, digits, `_` and `-`, dots between parts) exits 2 with nothing written.
A list key (`reset_rounds`, `book_chapters`) is a flow list: `state --set reset_rounds=4,5` writes `reset_rounds: [4, 5]` (whole numbers
from 1; anything else exits 2) and `state --set book_chapters=tone,photography` writes `book_chapters: [tone, photography]`. An older
project may hold `reset_rounds` as the quoted string `"[4,5]"`; every reader goes through `State.reset_rounds()`, which takes both and
reads runs of digits, so `"[10,11]"` is rounds 10 and 11.
`freeze`, `emit web` and `emit social` require G3. `G1s` is the style pick of the style board: the owner's pick, `skipped by
owner` (before the first pick board only), or for a project that was already past round 1 an honest `n/a: round 1 drawn before the
style step`; every pick board waits for it (see the Board contract). `state --record G1s` also writes `g1s_round`: the highest round
number whose `rounds/rN/board.html` is a style board at that moment (`r0` counts; a page that declares `data-board="style"` and
`data-round="N"` and holds at least four named `territory` sections with content, as `board-lint`'s style gate counts one), or, when
no round holds one, it removes the key. A round folder
that only exists, a copy of an earlier board or a style board not written yet does not count, so a pick recorded before the new style
board is written does not look as if it came after it. Only that command writes it: `state --set g1s_round=...` (and `--bump`) exits 2 with "written by --record G1s"; `--set gates.G1s=...` is refused the same way.
`board-lint` reads it to tell a pick recorded after a full rejection from the one before it. The `## Directions` table in the body
is read by `state --json`, which also reports `rounds` and `latest_round` as `rN` (`r0`, the style board, counts as a round) or
`null` when no round exists, and `motion`, the decision of `brand-creator motion` (see The motion decision).

## Token sources (DTCG 2025.10)

DTCG 2025.10 is a Final Community Group Report. It is not a W3C Standard and nothing here calls it one.

- `tokens/primitives.tokens.json`: colours as `{"$value": {"colorSpace": "oklch", "components": [L, C, H], "alpha": 1,
  "hex": "#rrggbb"}}` under a group with `"$type": "color"`. `hex` is the 6-digit sRGB fallback and must equal the
  gamut-mapped (CSS Color 4 style, culori) conversion of the oklch value; `brand-creator tokens --fix-hex` computes it.
  Supported colour spaces: oklch, oklab, srgb, display-p3. Other types (dimension as `{value, unit}`, fontFamily,
  fontWeight, number) are emitted to CSS custom properties and tokens.json only; durations and curves are described below and reach Swift and Android too.
- `tokens/semantic.light.tokens.json` and `tokens/semantic.dark.tokens.json`: the same set of colour tokens, as aliases
  (`"{color.paper}"`) or literal colours. Semantic files carry colours only in this version.
- Contrast pairs and other brand data live in `$extensions["brand-creator"]` of `semantic.light.tokens.json`:
  `{"pairs": [{"fg": "color.text", "bg": "color.bg", "kind": "ui-text|ui-text-large|ui-component|brand-rule", "min": 4.5,
  "label": "..."}]}`. `ui-*` kinds are WCAG 2.2 AA (4.5, 3, 3; `min` can only be raised). `brand-rule` needs an explicit
  `min` and is labelled "brand rule (logos WCAG-exempt)". Pairs are evaluated in light and dark.
- Touching pairs: `contrast` rasterises `assets/logo/mark.svg` (light ground) and `mark-dark.svg` (dark ground), plus
  `lockup` and `wordmark` when present, with resvg at 512 px, finds in the pixels every pair of flat colours that touch
  and every colour that touches the ground, maps them to token roles and holds them to the targets in
  `$extensions["brand-creator"].touching` of `semantic.light.tokens.json` (passed through to `tokens.json`):
  `{"default": 3.0, "ground": 3.0, "pairs": [{"a": "color.mark", "b": "color.accent", "min": 2.0, "label": "..."}]}`
  (first matching pair wins; 3 when unset). Misses the owner accepts are listed in `tokens/exceptions.json`:
  `{"exceptions": [{"a": "color.mark", "b": "color.accent", "mode": "light|dark|*", "reason": "..."}]}`. An exception
  needs a reason, turns a miss into a warning that carries it, and is itself reported when it matches nothing or the
  pair passes anyway. A missing `mark.svg` is "not verified" (exit 3; `--skip-marks` leaves the check out, printed).
  Artwork with gradients, patterns, filters, masks or images is not analysed and is "not verified", never a pass.
- Role separation: `$extensions["brand-creator"].distinct` of `semantic.light.tokens.json` lists roles that must never be mistaken for
  each other (a brand accent and a danger colour, two state colours): `{"distinct": [{"a": "color.accent", "b": "color.danger",
  "label": "..."}]}`. `tokens` resolves them in light and dark into `tokens.json` (an unknown role fails); `contrast --cvd` holds them
  to the colour-vision distance. A miss the owner accepts goes in `tokens/exceptions.json` like a touching-pair miss.
- Emitters need the semantic tokens `color.bg` and `color.text`; `color.muted` and `color.accent` are used when present.
- Motion tokens (primitives only: a semantic file carries colours only). A duration is `"$type": "duration"` with `{"value": 320, "unit": "ms"}`
  (`unit` is `ms` or `s`; the older `"320ms"` string is read too): a number of 0 or more that comes to whole milliseconds, because Android keeps a
  duration as an integer. A curve is `"$type": "cubicBezier"` with `"$value": [x1, y1, x2, y2]`: four finite numbers, `x1` and `x2` within 0 and 1,
  `y1` and `y2` unrestricted (a curve may overshoot); a duration is at most 2147483647 ms, the largest integer Android keeps. A group named `easing` gives `--easing-*`. A reference (`"{easing.standard}"`) resolves like any
  other. Anything else fails the build (exit 1, report row `motion-tokens`), names the token path and writes nothing. The starter tokens carry three
  curve proposals, `easing.standard` `[0.2, 0, 0, 1]`, `easing.enter` `[0, 0, 0, 1]` and `easing.exit` `[0.3, 0, 1, 1]`, which stay proposals until G4.
- Outputs of the motion tokens, written only when the sources have a duration or a curve (a project with neither gets no motion file and no `motion`
  entry in `tokens.json`, and its other outputs are byte for byte what they were):
  - `tokens.css`: `--<path>: 320ms;` and `--<path>: cubic-bezier(x1, y1, x2, y2);` with the other non-colour primitives (an alias is `var(--other)`).
  - `tokens.json`: under `other` the same strings, and under `motion` the numbers, both sorted by path: `"durations_ms": {"<path>": 320}` and
    `"curves": {"<path>": [x1, y1, x2, y2]}` (an alias holds the numbers it resolves to). The motion spec reads the paths under `motion` to know what
    a token is, and the adapters to know which tokens are durations and curves; the strings under `other` are for people and for the book.
  - `swift/BrandMotion.swift`: `BrandMotion.Duration.<name>`, a `Double` in seconds, and `BrandMotion.Curve.<name>(duration:)`, which returns
    `Animation.timingCurve(x1, y1, x2, y2, duration: duration)` (SwiftUI, iOS 13 and later). Each namespace is written only when it has a token, and a
    duration and a curve of one name cannot clash: they sit in separate nested enums (`Duration`, `Curve`). `<name>` is the token path without its group
    (`motion.base` is `base`), through the same `swiftId` rules as the colours: a Swift keyword is escaped with backticks, and `Type` and `Protocol`,
    which no member can usefully be named, fail the build (`motion-names` for a duration or curve, `swift-names` for a colour).
  - `android/values/motion.xml`: `<integer name="brand_<group>_<name>">` in whole milliseconds; `android/interpolator/brand_<group>_<name>.xml`: one
    `pathInterpolator` per curve, with `controlX1`, `controlY1`, `controlX2` and `controlY2` as plain decimals (a number JavaScript prints as `1e-7`
    is written out digit for digit, never rounded). The names are `androidName` of the token
    path (`motion.base` is `brand_motion_base`, `easing.standard` is `brand_easing_standard`).
  - A name that two tokens share inside one namespace (Swift `Duration`, Swift `Curve`, Android integers, Android interpolators), or that cannot be
    written (not a Swift identifier, not an Android resource name, or an interpolator file name with a capital letter), fails the build (report row
    `motion-names`), as a colour name collision does.
- `build_tokens.mjs` is the only producer of colour values for code. It uses Style Dictionary 5.7.0 with custom
  transforms, then parses every emitted artefact back and compares it with the source colour, alpha included, the `@supports` values in
  oklch, oklab and display-p3 too; a value it cannot read, or a missing one, is a failure (round trip per transform). A see-through colour (alpha under 1) is `#rrggbbaa` in `tokens.css`, `#AARRGGBB` on Android and an opacity in Swift and
  the colorsets. The motion outputs are read back the same way: `tokens.css` (`320ms` or `0.32s`; `cubic-bezier(...)`; an alias followed to its end), the Swift
  constants and `timingCurve` numbers, the Android integers and interpolator controls, and `tokens.json` (the numbers under `motion`, and `other` equal to the
  CSS string). A value that cannot be read, is missing, or is there without a token is a failure, and so is a motion file written for a project with no
  duration or curve.
- Files the build owns under `assets/tokens/` that the sources no longer produce (the colorset folder of a removed colour role, the motion files once the
  last duration or curve is gone, the interpolator of a removed or renamed curve) fail `tokens --check` (`outputs-current`: "no longer produced by the
  sources"), and a build moves them to `removed-<date>/assets/tokens/<path>` (`removed-<date>-2/` when that already holds one), never deletes them, and
  says so in a `retired` warning row.

## Board contract (data attributes)

`brand-creator board-lint <page>` takes the round from the page's folder `rounds/rN/`; `--round N` is for a page outside `rounds/` (the
review page), and on a page under `rounds/rM/` a different N exits 2. It finds sections by `data-section` attributes. Templates and generated boards must
carry them; a required section that is missing, empty or a placeholder (`TODO`, `...`) fails. Template markers
`[[fill: ...]]` left anywhere in text or attribute values fail the page (`page:unfilled`); HTML comments are ignored,
so optional blocks can wait in comments.

Page: `<body data-round="N" data-board="pick|refine|style|motion">`. `data-round` must equal the folder `rounds/rN/` (catches a copied
page that was not updated). Round 1 must be a `pick` board. Round 0 is always the style board (`data-board="style"`,
`rounds/r0/board.html`, from `templates/style-board.html`), and a round listed in `reset_rounds` holds either a style board or a
pick board: after a full rejection the style research runs again on a new style board (required, never skipped), and the round after
it (also listed) holds the pick board of the new territories. A style board anywhere else fails `page:data-board`, and so does a pick
board: it belongs to round 1 or to a round listed in `reset_rounds` (after a full rejection); later rounds are refine boards. A `motion` board is a round from 2 on, in any tier,
with its own rows (see The motion board below); in round 0 or 1, or in a round listed in `reset_rounds`, it fails `page:data-board`. The round and
the kind are read from one tag, the `<body>` (or the `<html>` tag when the body carries neither `data-round` nor `data-board`), by one
module that `board-lint` and `state --record G1s` share, `scripts/boardlib/boardpage.py` (outside `scripts/lib/`, so that a change there
does not make every pack stale). A repeated attribute counts by its first copy, as in a browser.

On a refine board, `board-lint` also measures the kept masters of the round, as warnings only (`masters:*` rows, `scripts/marklib/marks.py`, kept outside `scripts/lib/` so that a change there does not make every pack stale):
every SVG directly in a direction folder (`rounds/rN/<direction>/*.svg`; `drafts/` and `source/` are skipped), each `<name>-dark.svg` twin on
the dark ground (without a twin, the light artwork is measured there too). `masters:ground:<file>:<mode>` names each flat colour that
touches the ground under the target (`touching.ground` of the built tokens, else 3:1; the grounds are `color.bg` of the tokens, else
`#ffffff` and `#111111`); a pixel drawing is read cell by cell, a side shared with a clear cell or with the drawing's edge being a contact,
so two cells that meet only at a corner do not touch. `masters:outline:<direction>:<N>` compares the outline width of the pixel drawings of
one grid size N in a direction (the most common depth of the outline colour, inward from the ground, among runs that end at another colour;
a silhouette has no outline width and gets an info row) and warns when they differ. A pixel drawing is a crispEdges SVG with a square
whole-number viewBox of at most 64 cells. An SVG that cannot be read or drawn is a `masters:file:<file>` warning (NOT measured), never a
crash; `before/` (the old icons adoption replaces), `drafts/` and `source/` are skipped. Without resvg one `masters` warning says the
masters were NOT measured; a round with no masters gets an info row.

| `data-section` | required when | notes |
|---|---|---|
| `what-changed` | round 2 and later (a motion board: from its second) | "What changed since the review" |
| `today` | `incumbent` in BRAND-STATE is not `none` | the incumbent as variant 0 |
| `positioning-map` | round 1 and rounds in `reset_rounds` | must contain an element `data-direction="<name>"` for every direction; at least one direction has `data-far="true"`; in reset rounds also a non-empty `data-field="failed-round"` showing where the failed round sat |
| `strategy-core` | round 1 | shown for reaction |
| `direction` (repeat) | always; at least 3 on pick boards, 1 otherwise | `data-name` (a word of 3+ letters, unique, identical on the board and in chat), optional `data-letter` (one unique capital; off by default, and `question:N:letters` warns when a letter equals an option letter of a question that does not list the directions), `data-register` (required on pick boards, unique per direction: one per emotional register), optional `data-far="true"`, a non-empty child `data-field="idea"`, and on pick boards a non-empty `data-field="reflex"` (the reflex test against `references/ai-defaults.json`: "no hits" or each hit with its argument) |
| `hardest-surface` | always | the one surface where the mark is most likely to fail |
| `weak-points` | round 2 and later (a motion board: from its second) | |
| `losers` | round 2 and later | contains `data-section="loser"` items, each with a one-line (max 200 characters) `data-field="reason"` |
| `none-of-these` | pick boards | |
| `my-call` | always | children `data-field="recommendation"` and `data-field="critique"`; with `data-judge="ran"` also `judge-view`, `lead-view`, `middle-option` |
| `questions` | always | contains `data-section="question"` items with `data-n` = 1, 2, 3 ... in order; each holds at least two options `data-option="a"`, `"b"` ... in order, exactly one with `data-recommended="true"` (none or several fail `question:N:options`); a question that lists the directions carries `data-lists="directions"` in the template and shows their names |
| `reply` | always | how to answer: "Answer with a direction name, or question number plus option (1a)" and one sentence |

Style board (`data-board="style"`, round 0) vocabulary. It has its own required set; the pick-board sections above do not
apply to it except where named here:

| `data-section` | required | notes |
|---|---|---|
| `audience`, `surfaces`, `norm` | yes | who sees the mark, where, the category norm and what to avoid; non-empty |
| `territory` (repeat) | at least 4 | `data-name` (a word of 3+ letters, unique, and not a generic label: "Style 2", "Option B", "Territory 1", "Direction II", "Look 3", "Style-3" and "Option #2" fail, and so does a label word alone; the rule of direction names, see below); a non-empty child `data-field="idea"`; optional `data-field="per-item"` (how the style flexes across a family of marks, not linted); a child `data-field="references"` holding at least 3 `li` items, each with an `<a href="http(s)://...">` and a non-empty `data-field="take"` (`territory:<name>:references` fails with fewer); optionally, per reference, a thumbnail of its real mark: an `<img data-field="thumb">` with an inlined `data:image/...` URI as `src`, no `srcset` and non-empty `alt` text, in a `figure` with a non-empty `figcaption` (a caption naming the owner of the mark; the words and the language are the author's) (`territory:<name>:thumb:N` fails otherwise; a thumbnail outside any territory is checked as `thumb:N`) |
| `none-of-these` | yes | |
| `my-call` | yes | `data-field="recommendation"` and `data-field="critique"` (and the judge panels when `data-judge="ran"`) |
| `questions` | yes | the same rules as pick boards: `data-n` 1, 2, 3 ..., lettered `data-option`s, exactly one `data-recommended="true"`; question 1 (which territories) is multi-pick: checkboxes in a question marked `data-multi="true"`, and the reply the page composes lists every ticked style; when the brief has several marks one question asks shared style or per item |
| `reply` | yes | |

Directions, positioning map, strategy core, hardest surface, reflex and the incumbent "Today" are not asked of a style board. The `[[fill: ...]]` marker rule applies.

Images on a style board (`images:inlined`): every `<img src>`, and every `srcset` on an `<img>` or a `<source>`, is an inlined
`data:image/...` URI. A linked image (`http(s)://`, protocol-relative `//`), a relative path or a missing `src` fails. The lint reads
nothing else about the network: CSS `url()`, `<link>` and SVG `<image>` are not checked. A repeated attribute counts by its first copy, as in
a browser: `<img src="https://x.example.org/a.png" src="data:image/png;base64,...">` is a linked image and fails. A thumbnail has its own result instead (`territory:<name>:thumb:N`, in the territory row above).

Names: a direction or territory `data-name` fails `...:name` unless it is a word of 3+ letters that is not a label. A label is one of
option, direction, variant, style, concept, route, territory, look, mood, idea, version or choice, alone or followed by a number, or
by one letter or a roman numeral after a space, `-` or `#` ("Option 2", "Style A", "Direction II", "Option #2", "Style-3"). Words that
only start like a label (Stylish, Routes, Looker, Moody) pass.

Votes (`page:votes`, on every kind of board: pick, refine, style and motion): the vote of each card is a `<fieldset data-vote="<name>">` of keep / drop / unsure radios, and a radio name is one group for the whole page, so the radios of
a card are named `vote-<name>`, the name as written in its `data-vote`, letter case included (`vote-Compass` for the card Compass, never `vote-compass`), and no two cards share a name. The row fails when two vote fieldsets
share a radio name (a card copied with the name of the one it came from: one group, and a vote on one card clears the vote on the other; every card of the earlier templates said `vote-one`) or when a card's radios are not all named
`vote-<its name>` (a radio with no name counts), names the cards, what it found, and the fix (`name="vote-<name>"` on each card). Two votes that carry the same `data-vote` are told apart by their place ("Compass (vote #1)"). A page
with no vote at all gets an info row: a vote is optional. The motion board has the row too, among its own.

Project level: every pick board (`data-board="pick"`: round 1, and the pick board of each reset round) fails `project:style-gate`
while `gates.G1s` in BRAND-STATE.md is empty; a recorded pick, `skipped by owner` or an honest `n/a` all pass (`state --record G1s
"<decision>"`) for round 1. Refine boards and style boards (round 0, and the style board of a reset round) are not affected.
The pick board of a round R (2 or more) listed in `reset_rounds` follows a full rejection and passes `project:style-gate` only when
the pick from before it no longer stands. With `last` the highest round below R whose `rounds/r<last>/board.html` is not a style board
(`data-board` other than `style`: the rejected round, a pick or a refine board):

- a style board (`data-board="style"`) must sit at `rounds/r<M>/board.html` for an M with `last < M < R` and M in `reset_rounds`
  (the highest such M counts), and it counts only when it declares `data-round="M"` and holds at least four named `territory` sections
  with content, the minimum of the style lint (a page that only says `data-board="style"`, or a copy that still declares the round it
  came from, does not; the failure names it, for example "r2 has 0 of the 4 territories a style board needs" or
  `r2 declares data-round="0" (a copied page)`);
  otherwise it fails with "after a full rejection, show a new style board in a reset round before the next pick board";
- `g1s_round` must be a whole number of at least M; missing or lower it fails with "G1s still holds the pick from before the
  rejection: record the owner's new pick with state --record G1s ...".

So an earlier pick, skip or n/a does not clear a full rejection: the lint reads the order of the rounds and the record, not the words of
the record. `skipped by owner` is for the first pick board only, and the style board comes back after every full rejection, however many
there are in a row (r1 pick, r2 style, r3 pick, r4 style, r5 pick).

The review page of round 0: `review/index.html` has no template of its own in round 0; it is a copy of the style board
(`cp rounds/r0/board.html review/index.html`), linted with `board-lint review/index.html --round 0`. The same holds for the style
board of a reset round (`--round <N>`).

Project level: in round 1, when the tier is `full` or the architecture is `product-in-family`, `INVENTORY.md` must exist or
`inventory:` must start with `none` (for example `none (no target repo)`).

### The motion board (`data-board="motion"`)

A motion round tries the brand's signature move as variants after G3. Standard and Full decide motion for every brand and run it by default (see The motion decision); Quick may run one when something moves. It is a round from 2 on in
any tier: `rounds/rN/board.html`, from `templates/motion-board.html` (built on `templates/round-page.html`: the same tokens, header, hardest surface, My call, questions and reply). A motion board is no pick, style, reset or rejected
round: the map and style-round logic, `reset_rounds` and the style re-arming of a later pick board ignore it (the round "rejected" before a reset is never a motion round), the style gate does not apply to it, and the kept masters of the
round are not measured. Its code is `scripts/boardlib/motionboard.py` (outside `scripts/lib/`, like `boardpage.py`).

One folder per variant, `rounds/rN/<name>/`, made before the page:

| in the folder | what it is |
|---|---|
| `index.html` | the move where it will be seen, with the approved mark in place |
| `proof.json` | its proof: a page case named `<name>` whose `page` is `rounds/rN/<name>/index.html`, the page the card links, with a `selector` and `static` = an approved master of `assets/logo/` (the approved still, never one of the variant's own) |
| `frames/<name>/` | the stills of `brand-creator frames rounds/rN/<name>/proof.json --count 25` (see Frames: a try-out proof keeps them beside it): `strip.png`, `reduced.png`, `frames.json` and the stills |

and, in `assets/_checks/motion/` and `assets/_checks/frames/`, the reports of `brand-creator shot --motion rounds/rN/<name>/proof.json` and of `brand-creator frames rounds/rN/<name>/proof.json --count 25`. One card per variant: an element with `data-motion-variant="<name>"` (the `<article class="variant">` of the template).
The name is a word of 3 or more letters that is not a label ("Variant 2" and "Option B" fail: the rule of direction names), unique (capitals do not tell two apart), and also the name of the folder, so it keeps to letters, digits, `-` and `_`.
Inside the card:

| in the card | what it holds |
|---|---|
| `<img data-field="strip">` | the strip of the stills, `<name>/frames/<name>/strip.png` |
| `<img data-field="reduced">` | the reduced-motion still, `<name>/frames/<name>/reduced.png` |
| `<a data-field="live" href="<name>/index.html">` | the live page, one click away (the board has no replay) |
| an element with `data-proof="pass"` or `"fail"`, and its text | the proof line: what `shot --motion` found for this variant |
| `data-field="what-it-is"`, `"cost"`, `"degrades-to"` | What it is, Cost and Degrades to (what remains with no script and with reduced motion), each with text |
| `<fieldset data-vote="<name>">` | the owner's vote, as on the round page (the `page:votes` row, as on every board); its radios are named `vote-<name>`, a group of their own per card |

The pictures are the project's own files by a relative path, read from the page's folder as a browser reads it, or, in the copy published on a review surface (`review/index.html`, linted with `--round N`), `data:` URIs of the same bytes. The inlined-image
rule of the style board (`images:inlined`) belongs to that board and is not applied here; a picture from the network (`http(s)://`, `//`), an absolute path or a path outside the project fails `motion:stills`. The first motion board of a project (no
earlier round has `data-board="motion"`) shows exactly 3 variants and needs no What changed and Weak points (info rows); a later one, the refine loop on the picked or combined variant, shows 1 or more and needs both, as a refine board does from round 2.
Hardest surface, My call, questions and reply are required as on every board; there is no `positioning-map`, `strategy-core`, `today`, `losers`, `none-of-these` or `direction` section, no `project:*` row and no `masters:*` row, and `--min-directions` is
not used (an info row says so). Each row is one result for the whole board and names the variants it fails:

| row | fails when |
|---|---|
| `motion:g3` | G3 is not recorded ("a motion round follows the approved design (G3)") |
| `motion:off` | `motion/motion.json` says `off` ("nothing moves is recorded: a motion round contradicts it"); "not verified" (`skipped`, exit 3) when it is not a valid answer, read as `brand-creator motion` and `state` read it (`motionspec.decision`: not JSON, not an object, or not valid in itself, such as `off` with no reason), with the message `motion` refuses it with; absent or `on` passes |
| `motion:variants` | the count (exactly 3 on the project's first motion board, 1 or more on a later one) or a name (a word, not a label, a folder name, unique) |
| `motion:files` | a variant has no folder, or one that is not spelt as the card spells it (an entry of `rounds/rN/` equal to the card's name, letter case included: a disk that does not tell letter cases apart, macOS or Windows, opens `settle/` for the card `Settle`, but `shot --motion` and `frames` name their reports after the folder as the disk spells it, so the reports the board asks for are never made; the row says the card and its folder must be spelt alike, on every kind of disk), no `index.html` or no `proof.json`; the proof has no page case named `<name>`, or its `page` is not `rounds/rN/<name>/index.html`, the page the card links (a proof copied from an earlier round and still pointing there fails), or its `static` is not an existing file of `assets/logo/` (an approved master: a variant has no still of its own); `frames/<name>/strip.png` or `reduced.png` is missing; the card has no link to the live page or it does not lead to `<name>/index.html` |
| `motion:proof` | a variant has no motion report of its proof, a stale one (a file it read changed) or one that is no verdict (not-verified), each naming `brand-creator shot --motion rounds/rN/<name>/proof.json` (the row quotes the rows of the report that are not verified, each with its id and detail; one that names `requestAnimationFrame` adds that such a move stays not verified however often the proof runs, and says to write it as CSS animations, CSS transitions or `element.animate()`; the other not-verified rows `shot --motion` writes, a percentage translation on a pseudo-element or a still that cannot be placed over the mark, are quoted and given no such advice); the card's `data-proof` is not `pass` or `fail`, is not the report's status (a failing proof shown as `fail` is honest and passes) or has no text |
| `motion:stills` | a variant has no `frames` report of its proof (`assets/_checks/frames/<slug>-<hash6>.json`), a stale one (the proof, the page or a file the page loaded changed since the stills were taken: `shot --motion` run again does not make the stills current) or one with no passing `frames:<name>` row; the strip or the reduced still the card shows is not the file `frames.json` lists, by sha256; also the file on disk differs from `frames.json`, `frames.json` cannot be read or is of another proof or case (a folder copied from an earlier round), or the card has no, or two, `<img data-field="strip">` or `"reduced"`; each names `brand-creator frames rounds/rN/<name>/proof.json --count 25` |
| `motion:fields` | What it is, Cost or Degrades to is missing, empty, a placeholder or still holds a `[[fill: ...]]` marker, in a card |

`page:data-board` also fails a motion board in round 0 or 1 or in a round listed in `reset_rounds`. The `inputs` of the lint report are the page and, of each variant, `proof.json`, `index.html`, `frames.json`, the strip, the reduced still, the motion report and the frames report, and every file those two reports were made from (their own `inputs`:
the files the page loaded, such as a stylesheet, `tokens.css` or a script, where the move may live), so `check` calls the report stale ("not verified") as soon
as one of them changes: take the stills and the proofs first, lint, and shoot the board last (`shot` writes `assets/_checks/shot.json` for one page, and `check` wants the one of `rounds/r<latest>/board.html`).

## Hook guard

`hooks/hooks.json` runs `scripts/guard.py` before Write, Edit, MultiEdit, NotebookEdit and Bash. It does nothing unless
the target has an ancestor folder containing `BRAND-STATE.md`. In a brand project it blocks (exit 2, reason on stderr):
Edit, overwriting Write and new files in `history/`; deletes, moves, `sed -i`, redirects, `tee`, `truncate`, `dd of=`,
`cp`/`install`/`ln`/`rsync` into `history/`; Edit, Write and Bash writes on any `rounds/rN/` that is not the latest round
(the one exception: `rounds/r0/`, the style board, stays writable while `gates.G1s` in BRAND-STATE.md is empty or missing, so a
project already past round 1 can run its style research as round 0; once G1s is recorded it is read-only like any earlier round. The
exception opens only when `gates:` is a block map the guard fully understands: a state file it cannot read, a tab in a frontmatter
indent, a quoted key, an indented line under a key that has a plain value or before the first key (the state reader rejects those too),
a `gates:` with a value on its own line (a flow map such as `gates: {G1s: ""}`), a repeated `gates:` or a repeated key inside it opens
nothing); deletes anywhere under `rounds/` and moves out of `rounds/` except from the latest (or open) round into a
`removed-*` folder. `patch` asks the same question through the same function (`guard.round_is_open`), so it edits `rounds/r0/` exactly
when the hook lets a write in.
`brand-creator freeze` is always allowed. The same zones are protected from `git mv`, `git stash -u|-a|--include-untracked|--all`, `git clean`, `git checkout -- <path>`, `git restore`, and from `tar -x`, `unzip`, `7z x` and `ditto` extracting into them (listing and testing archives stay allowed). `BRAND_CREATOR_GUARD_STRICT=1` also blocks Bash writes into the latest round.
It is best effort (an interpreter one-liner can still write); the real gate is `history/MANIFEST.sha256`, verified by
`check`. Fail-open applies only to input it cannot parse (it prints a warning): a broken guard must not brick unrelated
sessions. `hooks/hooks.json` sets `onFailure: "block"` on the guard (Claude Code 2.1.295 or later): a missing `python3` (Windows without Python, or the Microsoft Store alias), a crash or a timeout blocks the call with a visible `failed; blocking because onFailure is "block"` notice instead of silently doing nothing; older versions ignore the field.

## Platform specs and emitters

`scripts/emitters/platform-specs.json` holds one row per surface: `{surface, sizes, source_url, checked, status}` with
status V (verified at the source), R (secondary source) or U (unverified), plus `stale_after_days`. Emitters read sizes
only through `emitters/specs.py`, never as literals in code (a test enforces it). Each emitter stamps the rows it used
into `assets/manifest.json` and warns for U, R and stale rows. Files that carry no fingerprint: `favicon.ico` (stable
URL). Fingerprinted only when referenced from HTML or the manifest, and only when the bytes change: `icon.svg`,
`apple-touch-icon.png`, `site.webmanifest`, PWA icons (`?v=<8 hex>`). The Open Graph image gets a new file name per
change (`og-<w>x<h>-<hash>.png`). All User-Agent strings come from one constant (`USER_AGENT` in `_common.py`), with no
personal data and no `@`.

`assets/manifest.json` rows carry `path, sha256, bytes, emitter, specs`, and optionally `slot` (the surface the file serves), `inv` (its
INVENTORY.md slot id), `size` (`WxH`), `resampled_by` (`OURS` our own master at the exact pixels, `SYS` a system downscale of one master, `PAGE`
drawn by the page; the "who" of the plan), `note`, `band` (see QA gates), `exemption` and `qa` (the gates the file needs, from downscale, states, motion, family, fonts, idempotent, print; `check` requires a
current passing report for each), and `downscale_source` (with `qa: ["downscale"]`: the project path of the master the downscale gate must have
measured; `put_slot()` defaults it to the file itself, the Apple pack names its marketing master), and `superseded` (`true` on a row kept on purpose
after a later run replaced its file: the earlier Open Graph card). A multi-size file (an `.ico`) carries `layers`
and `layer_bands` ({"16": band, ...}); `check` re-reads each layer's band against the rule for that layer's own size.
Emitters write rows through `Manifest.put()` or `Manifest.put_slot()`; both write a file only when its bytes change.

### The platform emitters (`brand-creator emit <target>`)

Every emitter needs gate G3, reads sizes only from `platform-specs.json` (a test fails on a literal size in any emitter file), writes under
`assets/<target>/` (`--out-dir` overrides) laid out as the target repo's own paths, records rows through `Manifest.put_slot()` (a file that is a
drawing at a size: slot, size, band, resampled-by) or `Manifest.put()` (a document, a colour set, a rendered card), and writes
`assets/_checks/emit-<target>.json` (with several marks: `--mark <id>`, `assets/<target>/<id>/` and `emit-<target>/<id>.json`, see Several
marks). The drawing for a size is the one the band rule in `qa/rules.json` names (`Emit.drawing()`; the default
mark when the project defines no bands). `--master-band <name>` draws a file the system shrinks from another band and needs `--exemption`
(exit 1 without it, before anything is written). The dark artwork of a drawing is its `<name>-dark.svg` sibling, else the light drawing
recoloured through the token roles light to dark (a warning; a colour the tokens do not map exits 1). A `-dark.svg` must be pure vector like its
drawing (exit 1), and one that leads out of the project, through a symlink, exits 2 before it is read.

| Target | Output | Gates in the emit |
|---|---|---|
| `apple` | `AppIcon.icon/` (icon.json + layer SVGs), `compiled/<platform>.renditions.json` and the actool fallbacks (`compiled/ios/*.png`, `compiled/ios/Info-icons.plist`, `compiled/macos/AppIcon.icns`), `Assets.xcassets/` (visionOS stack, accent colour set, menu-bar template, and the appiconset only for a target below 26), `Colors.xcassets`, `legacy/AppIcon.icns`, `marketing/AppStore-1024.png` (RGB, no alpha), `dmg/` (background, @2x, layout.json), `store/` (frames, frames.json), `_preview/` with `--previews` | vendored schema + validator on the `.icon`; actool compile per platform (iphoneos, macosx, watchos, xros) is exit 1 on any error; rendition checks per platform; icns round trip with iconutil; visionOS safe circle; no-alpha check |
| `windows` | `app.ico`, `nsis/header.bmp`, `nsis/sidebar.bmp` | ico layers equal the spec row; BMP header read back (24 bits, uncompressed, spec size) |
| `linux` | `usr/share/icons/hicolor/<s>x<s>/apps/<icon>.png`, `scalable/apps/<icon>.svg`, `usr/share/metainfo/<id>.metainfo.xml` | metainfo text from FACTS.md only, gaps reported |
| `tray` | `windows/<light\|dark>/<state>-<px>.png`, `linux/<state>-<px>.png`, `macos/<state>Template@2x.png` | `qa/states.tray.json` written, then `states-check` (a failing pair is exit 1) |
| `tauri` | `src-tauri/icons/` PNGs, `icon.ico` (32 first), `icon.icns` | sizes and order; `.icns` by iconutil, or Pillow only with `--renderer pillow`; exit 3 otherwise off macOS |
| `wallet` | `apple/` (icon, logo, primaryLogo, secondaryLogo at @2x and @3x; order-logo.png), `google/` (logo-660.png, wide-logo-1280x400.png) | point size times scale; order logo opaque; circle-safe logo; wide logo transparent |
| `developer` | `email/` (1x, @2x, @3x), `nuget/`, `avatar/`, `cli/identity.txt` and `identity.plain.txt` | registry icon size limit; CLI colour chosen by contrast on a white and a black ground |
| `print` | `business-card-front`, `business-card-back`, `letterhead`, `envelope` as `<piece>.rgb-proof.pdf` or `<piece>.pdfx4-candidate.pdf` with `<piece>.print.json`; `email-signature/` | see Print; Standard and Full tier |
| `presskit` | `<slug>-press-kit.zip` | deterministic zip; Standard and Full tier |

`emit web` draws every favicon.ico layer, the apple-touch icon and each PWA icon through `Emit.drawing(size)` (the band rule for the file's own
size) and records the band (`layer_bands` for the .ico). `icon.svg` is one scalable file, and browsers that read it show it in the tab:
it is `favicon.drawing` from `qa/rules.json` when the owner set one, else the band rule's drawing for the smallest favicon layer (the
tab size), so the default mark only when there are no bands. Its dark switch is the drawing's `<name>-dark.svg`; with none, there is
no switch and a warning names the missing file. The manifest row records the file (`drawing_file`). When the manifest already has a row for
`icon.svg` whose `drawing_file` is another drawing than this run's, the report warns (`note:icon.svg changed`) with both files and the setting
that keeps the old tab icon: `favicon.drawing` in `qa/rules.json`, or `marks.<id>.favicon` for one of several marks. A row with no
`drawing_file` (written before 0.3.1) is not compared.

`emit apple` exits 3 off macOS (and on a Mac without Xcode) before it reads the project. `emit tray` reads `tray/tray.json` (a state's source is a
path, or a map of master size to path, or `{"light": ..., "dark": ...}` of those; a master serves only the sizes it divides, a size with no master
is exit 2). `Assets.car` files are compiled into a scratch folder and compared by their rendition list; only the list is shipped. A row that asks
for `qa: ["downscale"]` needs a current passing downscale report; the emit prints the command (`downscale --source <master>`) but does not run it,
because each master has its own report (`assets/_checks/downscale/<slug>.json`).

**Slots that no longer exist.** Every emitter run ends by retiring the rows it owns (same `emitter` and the same `mark`, under its `--out-dir`) that it did not
write this time: the file is moved to `removed-<date>/<path>` in the project (never deleted), the manifest row is dropped and the report gets a
`retired:<path>` warning and a `retired` list. A removed tray state, a dropped deployment target or a feature option that is gone no longer ships.
`emit social` writes the GitHub social preview and the README headers only when `INVENTORY.md` lists a repository row or `brief/BRIEF.md` names a repository URL, a Repository line or a README/GitHub required surface (`--repo-images yes|no` forces it); otherwise an `note:repo-images` info row says why they were skipped.
A folder the run skipped on purpose (`emit apple --no-cards`) is spared (`Emit.keep()`), and `emit social` spares superseded fingerprinted
Open Graph files (cached link previews may still use their URL; it warns instead). Their rows stay in the manifest marked `"superseded": true`
(a row an emit writes again has no mark), and the book's files chapter lists them with the note "superseded, kept for cached link previews"
instead of as a second current card.

**Report inputs.** An emitter lists every file it read in its report: the marks, `assets/tokens/tokens.json`, `qa/rules.json` (the bands), and
as used `FACTS.md` (store frames, AppStream, CLI identity), `INVENTORY.md` (Apple deployment targets), `tray/tray.json`, `--svg-mono` and the
band drawings. Editing any of them makes the emit report stale.

Chain: `templates/finish.sh.tpl` is the ordered build (`version --check`, generators, tokens, contrast, emitters, gates, `verify-idempotent`,
`staleness --write`, `check`). `version --check` comes first: a session that still runs an older copy of the plugin than the one Claude Code
has installed (`installed_plugins.json` next to the plugin cache: a user install, or a project or local one for this folder) exits 1 there and
says to start a new session; a copy that is not in a plugin cache (a checkout) or a record that cannot be read is "not checked" (exit 0). The
chain runs `contrast --cvd` when `qa/rules.json` has a `cvd` section. It exports `BRAND_CREATOR_CHAIN=1`; a generator that rewrites a whole output folder calls `_common.require_chain()` and exits 1
outside the chain. The options of block 2 are variables (`TAGLINE`, `APP_ID`, `MASTER_BAND`, `EXEMPTION`, `ICON_CONTENT`, `VISIONOS_CONTENT`; an
environment variable of the same name overrides) that reach each emitter as separate quoted arguments, and the idempotence commands are built
with `printf %q`, so a tagline or an exemption with spaces stays one argument. `BRAND_CREATOR_ROOT` (for the generators) comes from
`brand-creator root`. The gates step runs `downscale --source` on every distinct `downscale_source` in the manifest. A test runs the filled
template through to `check`, and the Acme smoke runs it on a copy of the finished pack.

`brand-creator specs-due --write-markdown FILE` regenerates `skills/brand-creator/references/platform-specs.md` from the JSON (a test compares
them).

## Name screening

`brand-creator names <candidate>...` (`scripts/check_names.py`) screens names; it is screening, not clearance. It runs inside
a project (BRAND-STATE.md). Candidates are single tokens (letters, digits, hyphens).

- **States.** Each cell is `REGISTERED` (the source says the name exists), `NOT-FOUND` (the source says it does not exist right
  now) or `UNKNOWN` (not established). No output says a name is "available", "free" or "clear": `NOT-FOUND` does not cover
  price, reserved or premium names, pending releases or trademarks.
- **Privacy gate.** Before any network call the command prints which services receive the names, then needs `--yes` (the skill
  asks the owner first). `--plan` prints the list and exits 0; `--offline <run folder>` makes no network call and needs no `--yes`.
- **Sources.** Domains: RDAP from the IANA bootstrap (cached 24 h in `<data>/cache/`), whois on port 43 at the server
  `whois.iana.org` names for TLDs the bootstrap lacks (also used when an RDAP server does not answer at all, said in the
  cell), plus a DNS NS cross-check through the system resolver (a conflict makes the cell `UNKNOWN`). Profile `software` adds
  npm, GitHub (`gh api` when logged in, else HTTPS; `--no-gh` forces HTTPS), Docker Hub orgs and users, PyPI, crates.io and
  Homebrew formulae and casks. Profiles `consumer` and `personal` check domains only and list manual social-handle links.
  TLDs come from the profile and `--region`, or `--tlds`.
- **Controls.** Every source (every TLD, the resolver) is proven first with a known-taken and a known-unregistered name; either
  failing turns that source's cells into `UNKNOWN` and the reason is in the report and the memo.
- **Politeness.** 0.3 to 1 s between calls to one host (`--spacing`), one retry after a 429 with `Retry-After` honoured (not
  retried above 30 s), one generic User-Agent (`USER_AGENT` in `_common.py`).
- **Raw output.** Every response is saved under `research/names/raw/<date>/run-<n>/` (one JSON file each, key `GET <url>`,
  `WHOIS <server> <query>` or `DNS NS <name>`). `<n>` is the run's memo number: a run takes the first number whose memo and raw
  folder are unused, so a second run the same day never rewrites the first run's evidence. A run folder replays with
  `--offline`; a folder holding several runs is refused (their answers would mix). Bodies are cut at 4 KB and stripped of
  third-party personal data before they are written: JSON bodies of GitHub, Docker Hub, npm, PyPI, crates.io and Homebrew keep
  an allow-list of fields, RDAP vcards keep only their version line, whois answers keep only dates, status, name servers and
  the registrar line (no contact blocks), and e-mail addresses are removed everywhere.
- **Replay date.** `--offline` reports the `fetched` date carried by the recordings (the oldest when they differ), never
  today's: the memo file name, every row's "Checked" and the report's `checked` use it, and the memo header and the report's
  `replayed` and `recorded` fields say when the replay ran. A recording without a valid `fetched` date is refused (exit 2).
- **Outputs.** `assets/_checks/names.json` (a report as above: one result per cell, `info` for an established state, `skipped`
  for `UNKNOWN`, so any `UNKNOWN` makes the report `not-verified` and the exit code 3; extras `controls`, `trademark_links`,
  `manual_links`) and `research/names/<date>-check.md` (never overwritten: a second run the same day writes `-2`, with raw folder `run-2`).
- **Trademarks.** Never queried. The report lists owner-run links by region (TMview deep link, EUIPO eSearch, USPTO, UPRP for
  PL, UK IPO for GB, WIPO's directory otherwise) and WIPO Global Brand Database as manual only (its terms forbid automation).

## QA gates and mark tooling

Every tool below follows the contract above (report in `assets/_checks/<tool>.json`, exit codes 0/1/2/3). A threshold is the owner's;
the numbers in `scripts/lib/qa_rules.py` are the agent's proposals, printed as proposals until `qa/rules.json` sets them (G4).

### qa/rules.json

```json
{"schema": 1,
 "downscale": {"accent_min_px": 4, "accent_rule_max_size": 32, "accent_colour": "color.accent", "accent_tolerance": 40,
               "exemptions": [{"source": "assets/logo/mark-16.svg", "max_px": 16, "reason": "..."}]},
 "states":    {"greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10, "ground": "#808080"},
 "cvd":       {"min_delta_e": 10.0, "deficiencies": ["protan", "deutan", "tritan"]},
 "guides":    {"tolerance_px": 1.5},
 "family":    {"tile_share_tolerance": 0.05},
 "favicon":   {"drawing": "assets/logo/favicon.svg"},
 "bands":     [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "assets/logo/mark.svg"}]}
```

`favicon.drawing` (empty by default) fixes the drawing of `icon.svg` (`emit web`); it must be an existing `.svg` in the
project (exit 2 otherwise) and pure vector (exit 1 otherwise), and so must its `-dark.svg` when there is one.

An unknown section or key, a value of the wrong type or a number at or below 0 exits 2: a typo never falls back to the proposal.
**Size bands:** `qa_rules.pick_band(bands, size_px)` is the one function that names the drawing for a body size (first band whose
`max_px` covers it; every band but the last has a `max_px`, and the last has none: it covers every larger size, and a last band
with one exits 2). `Manifest.put_slot()` records the band a slot used; a slot that uses another
band than the picker names needs a one-line `exemption` (exit 1 without), and `check` re-reads every recorded band from the manifest.

### Several marks (`qa/rules.json` `marks`)

A project whose products share one system but each have their own mark (a family of tools, a marketplace of plugins) lists them in
`marks` instead of the top-level `bands`:

```json
"marks": {"tool-a": {"bands": [{"name": "small", "max_px": 16, "drawing": "assets/logo/tool-a-16.svg"},
                               {"name": "large", "drawing": "assets/logo/tool-a.svg"}],
                     "name": "Tool A", "favicon": "", "accent": "color.tool-a", "tagline": "tool-a one-liner"},
          "tool-b": {"bands": [{"name": "all", "drawing": "assets/logo/tool-b.svg"}]}}
```

- A mark id is lower-case letters and digits joined by hyphens: it names folders and reports. Every mark has at least one band, and the
  last band's drawing is its main drawing. `name` (default: the id) is what its cards say when there is no drawn lettering, `favicon`
  fixes its `icon.svg` drawing, `accent` is the token role of its cards' accent and of the accent `downscale` measures on its drawings and
  on the files its packs emitted (default: `color.accent` on cards, `downscale.accent_colour` in `downscale`; a role the tokens do not define
  exits 1 on a card and 2 in `downscale`), and `tagline` is a `FACTS.md` label
  whose value goes under its name (a label `FACTS.md` lacks exits 1; `--tagline` wins).
- With `marks`, the top-level `bands` and `favicon.drawing` stay empty (exit 2 otherwise), and every emitter and `logo-sheet` take
  `--mark <id>`: a run without it, with an id the file does not list, or with `--svg`/`--svg-dark` exits 2, and so does `--mark` in a
  one-mark project. Nothing is guessed.
- A `--mark` run draws that mark's drawings by its own bands, takes its lettering from `assets/logo/<id>-lockup.svg`, else
  `<id>-wordmark.svg` (each with its `-dark.svg`), writes under `assets/<target>/<id>/` and reports in `assets/_checks/emit-<target>/<id>.json`.
  Its manifest rows carry `"mark": "<id>"`; `check` holds each row to its own mark's bands, and a run retires only rows of its own mark, so
  one mark's run never moves another's files, whatever the folders.
- `emit social` without `--mark` makes the brand-level images from `templates/lineup.html`: the Open Graph card, the GitHub social preview
  and the README headers show every mark side by side in cells of one width, each with its drawn wordmark under it (its name typed, and a
  warning, without one) and the brand's own lettering or typed name above. `--posts` needs `--mark` (exit 2).
- `logo-sheet --mark <id>` writes `assets/_checks/logo-sheet/<id>.png` and the report `logo-sheet/<id>`; `check` expects one per mark, and
  a `marks:<id>` row fails when a drawing the mark's bands name is missing. `contrast` checks the touching colours of every drawing each
  mark's bands name and of its lockup and wordmark. `downscale` measures a master against the bands of the mark it belongs to.
- The book: the cover sets every mark side by side, `{{mark-sizes}}` has a table per mark, `{{donts}}` draws the misuse from the first mark
  (or `{{donts:<id>}}`) and says it stands for every mark, `{{marks}}` and `{{marks:*}}` show every mark, and a name with no file of its own
  is looked up per mark (`{{marks:wordmark?}}` shows each `<id>-wordmark.svg`).
- `finish.sh` runs each emitter once per mark (`--mark <id>`) and `emit social` once more without it.

### downscale (`brand-creator downscale`)

One master (PNG, or an SVG rasterised once at `--master-size`) is shrunk to the sizes systems show (default: the union of the
`downscale-apple` and `favicon-set` rows of platform-specs.json) and the accent is measured at each size: pixel count, bounding box and
the largest solid square. Brand rule (default, owner-adjustable): at `accent_rule_max_size` px and below the accent holds a solid
`accent_min_px` x `accent_min_px` square (fail; a vanished accent is named). A miss the owner accepts is a `downscale.exemptions` entry:
`{"source": <the master's path in the project, as --source names it; ./ and \ are normalised>, "max_px": <size>, "reason": <why>}`. A failing row of that master's report at `max_px` and
below, system or shipped, becomes a warning that carries the reason. Another master's miss is never excused, and an exemption that excused
no row of its master's run is reported as `exemption:<n>` (warn), and so, in every run, is one whose source is not a file of the project. An exemption without a source inside the project, a whole `max_px` above 0
or a reason exits 2. Methods: `sips -z` on macOS (default), `--renderer=resvg`
(SVG source, a vector render per size) or `--renderer=pillow` (Lanczos on a PNG source). Off macOS there is no default: the run exits 3
unless `--renderer` is given or BRAND-STATE records `renderer: <name> (opted in <date>)`. `--previous <older master>` (or the previous
report of the same source) adds `compare:<size>px` rows: a smaller solid square at a rule size is a warning "REGRESSION". The earlier report is
used only when it measured the same source with the same method, master size, accent and ground; otherwise an info row `compare:none` says
there is nothing comparable.
**One report per measured source**: `assets/_checks/downscale/<slug>.json` (tool name `downscale/<slug>`, the slug is the file stem plus six
hex digits of the path hash). `check` ties a manifest row to the report whose `source` equals the row's `downscale_source`. `--png FILE` measures a raster
as shipped (for example an actool output) with no resampling; pass every shipped file of one master in one run, since each run writes
the master's report anew. When the master is one band's drawing (`qa/rules.json` `bands`), an info row `bands` names its sizes and the
drawings that ship the others: its rows outside its band show what a system that shrinks this one master would make of it (an app icon),
and a size drawn per band is measured as shipped, with `--png`. The accent colour and ground come from `tokens.json` (mode
`--mode light|dark`) or `--accent` / `--ground`. The accent is `--accent`, else the `accent` role of the mark whose drawing the master is
(`qa/rules.json` `marks.<id>.accent`), else `downscale.accent_colour`; the report's `accent.role` names the one it measured.

### states-check

`qa/states.json` (plus every `qa/states.*.json`; `emit tray` writes `qa/states.tray.json`, so the owner's file is never edited by a generator; `--states FILE`, repeatable, replaces
the default): `{"schema": 1, "sets": [{"name": "tray-16", "size": 16, "ground": "#808080", "states": {"idle": "assets/tray/idle.svg",
"error": "assets/tray/error.png"}}]}` (a set may override `greyscale_min_diff` and `silhouette_min_diff`). Every pair of states in a set
must differ in greyscale (share of ink pixels whose Rec. 709 luma differs by more than 16/255 on the ground) and in silhouette (share of
the union of the two shapes that is not shared; alpha when the image has transparency, else the ink against the ground), each at or above
the threshold. SVG states are rasterised at the set's `size`; PNG states must share one size.

### family-check (family modes only)

`architecture: family-member | product-in-family`; a standalone brand gets one info row. It reads the ```` ```json family-check ```` block
of `FAMILY.md` (template `templates/FAMILY.md`, which documents every field): `glyphs.shared` names must be cell-equal in the family's
source and this product's source (`compare`: `shape` or `exact`), and the `tiles` marks must agree in ink share of the tile and ink-box
height within `tile_share_tolerance` (the ground is the most frequent colour on the image edge). Sources are read, never executed: a `.py`
file through `ast.literal_eval` of the named top-level assignment, a `.json` file as JSON; a source that is missing or not a literal makes
the check "not verified" (exit 3). Paths are relative to FAMILY.md; a sibling repository is only ever read.

### fontcheck, fonts and outline-glyphs

- `fontcheck` answers three things per font file: glyph coverage per language set (cmap), a licence hint from the name table and OS/2
  `fsType` (a hint from the file, not legal advice; `fsType` restricted embedding fails), and Chromium's platform-font report with a
  control (`render.mjs fonts`: `CSS.getPlatformFontsForNode`; a character the font lacks must come back as another font, else the report
  is "not verified"). Language sets are data files, `scripts/data/languages/<code>.json` (`schema, code, name, letters, symbols, extras,
  basic_latin, rules`; en, pl, de, cs, fr, es, tr); the plugin has no default language. The sets come from `--lang` or
  `content_languages` in BRAND-STATE.md. A missing required letter fails, a missing typographic extra warns, more than two font families
  warns (default budget, owner-adjustable).
- `outline-glyphs` writes text as paths: fontTools instancer pins the variable axes, skia-pathops removes overlaps, `SVGPathPen` writes
  one `<path>` per glyph. The SVG has no `<text>` and no font reference (mark_lint checks) and carries `data-baseline`, `data-cap-height`
  and `data-x-height` that `logo-sheet --guides` draws. Layout is the font's advance widths plus `--tracking` and `--pair`; GPOS kerning
  is not applied.
- `logo-sheet --guides` writes `assets/_checks/logo-guides.png` (the mark at 512 px with baseline, cap line, x-height and grid guides)
  and measures, for each horizontal guide, the distance in px to the strongest ink edge (`guides.tolerance_px`).

Before measuring, `shot` loads every `loading="lazy"` image (one hidden at a width or below the fold never loads otherwise, and would
count as broken), pauses `--wait` ms (default 300), then waits up to 15 s for running animations and transitions that have an end; one
that repeats forever is counted and shot where it is. Each view records `lazy_images` and `animations` (`waited`, `running`, `capped`).
`shot` also records, per view, `gutter_left` and `gutter_right`: the distance in css px from the nearest visible text or image box (outside horizontal scrollers) to the left and right edge of the viewport. They are data, never a verdict (a full-bleed page is legitimate); a page that promises a gutter, such as the generated book (16 px at 390), asserts on them.

### Motion proof (`shot --motion <proof.json>`)

`{"schema": 1, "cases": [...]}`, every case with a unique `name` and a `type`:

- `states`: `file` (the animated mark: the complete still, its moving part in `<g data-motion>` whose children `<g data-state="name">` are
  the named states), `static` (the still it must equal), `rest` (default `rest`), optional `expected` (state -> file), `controls` (pairs of
  states that must differ). Each state is rendered at device scale 1 and 2 (inline SVG and an `<img>` drawn on a canvas); the stored file
  must show its rest frame, rest must equal `static` pixel for pixel, and every control pair must differ (a comparison that cannot see a
  difference proves nothing). A case with no control pair fails.
- `page`: `page`, `selector` (the mark's element), `static`, and the optional keys `settle_ms` (default 1500: how long a page driven by
  `requestAnimationFrame` is given, and how long the reduced pass watches the page), `max_cls` (default 0), `tolerance` (default 0 of 255),
  `pixel` (`true` or `false`) and `widths` (default `[360, 390]`). A bad value is a usage error (exit 2), raised before a browser starts.
  Pages are served from a local server that refuses every non-local request. The rows, in the order of the report:
  - `control`: the normal pass must show motion, an animation or a `requestAnimationFrame` call, else the reduced result below proves nothing.
    A page that shows neither within 150 ms of load is looked at every frame until `settle_ms`: what a script starts later is paused at once, seeked
    from its own start, and the row says when it began (in ms after the page started loading); a page that shows nothing by then fails.
  - **`sampling`: the page is seeked, never waited for.** After load and `fonts.ready`, every Web Animation (CSS animation, CSS transition,
    `element.animate()`) is paused where the page has it, and so is one a script starts within the first 150 ms (or later, as above); each is
    then set to a time. The motion's length is the latest finite `endTime` of them (with none that lasts, the longest first iteration). The
    sample points are 0 and every 1/32 of the length; every keyframe of every animation in page time; the turns of its easings; and every 1/32
    of each animation's own iterations, `delay + (iteration + k/32) x iteration duration`, so that a short animation inside a long motion is not
    stepped over. A keyframe's time is `delay + (iteration + p) x iteration duration`, where p is the input progress at which the easing of
    the whole effect (a CSS transition's timing function, the `easing` of `element.animate()`; linear for a CSS animation) reaches the
    keyframe's offset; a reversed iteration (`direction: reverse`, an odd one of `alternate`, an even one of `alternate-reverse`) counts it
    from the other end, a partial last iteration only up to its end, and an infinite animation only over its first iteration. The turns are
    where an easing turns back or holds a pose: the peak of a `cubic-bezier` whose y1 or y2 lies outside 0..1 (where y'(t) = 0), the middle
    of each step of `steps(n)` (64 steps at most) and the stops of `linear()`, for a keyframe's own easing and for the effect's. An easing the
    proof does not read is taken as linear and named in the row (a warning). All animations are set to the same time, each counted from its
    own start. At most 400 points: past that the even points stay, the keyframes and turns come next and the animations' own points last, each
    kind thinned evenly over the motion (an animation of very many iterations is collected from every n-th one), and the row says so. An
    animation that begins only when another ends is finished, not stepped through, and the row (a warning) names it. The row lists the points
    (`points_ms`, `points_pct`) and the time the normal pass took (`elapsed_ms`).
  - **Motion driven by `requestAnimationFrame` cannot be seeked.** A page that still calls it 150 ms after load, or begins to while the
    animations are stepped through, is waited for `settle_ms` in real time, and the `sampling` row (a warning) says `sampled in real time:
    requestAnimationFrame-driven motion cannot be seeked`. What it draws between two frames is not known, so the `edges:<width>` rows and
    a pixel mark's `whole-pixel` row are "not verified" (`skipped`) unless the seekable points already fail them, never a pass with nothing
    measured. Its calls are counted over the 500 ms after `settle_ms`: a loop that still calls it fails `loops` and `settled`. An animation
    on a scroll or view timeline cannot be seeked either: the row names it.
  - `loops`: an infinite animation fails (it is still sampled over its first iteration), and so does a `requestAnimationFrame` loop (above).
    `settled`: every animation is finite and, after each is seeked to its end (`finish()`; the animations the end of one starts are finished
    in turn, four rounds at most), none is running; one that cannot be finished fails and is named. `settle_ms` is not waited for Web
    Animations: a 10 s animation is seeked, not waited for.
  - `cls:normal`: layout shift is measured while the points are stepped through, with a rendered frame between two steps, so that the
    layout-shift observer sees each. Chromium does not count a move of under 3 css px between two frames as a shift, and a step of the motion
    is often smaller than that, so an animation of a layout property fails the row whatever was measured: `top`, `right`, `bottom`, `left`,
    `inset`, `width`, `height` and their `min-`/`max-` and logical forms, `margin`, `padding`, a border width, `font-size`, `line-height`,
    `letter-spacing`, `word-spacing`, `flex-basis`/`-grow`/`-shrink`, `gap`, the grid templates and `aspect-ratio` (`layout_properties` names
    each with its animation). A `transform` or `opacity` animation does not.
  - `normal:rest=static`: **the rest frame is compared in the page itself.** After the motion ends the mark element's box (rounded outward
    to whole pixels, the page's own background) is screenshotted, after the element is hidden for two frames and shown again (a part a CSS
    transition moved across the mark can leave the old drawing of the places it passed). Then the static SVG is drawn where the element draws,
    and the same clip is screenshotted:
    - an `<img>` shows the still itself: its source is swapped (`srcset`, `sizes` and the `<source>`s of a `<picture>` set aside, its size
      held), so its box, border, padding, ancestors and raster are its own;
    - anything else gets the still in a shadow root, which the page's style sheets cannot reach (a rule for `svg circle` neither styles nor
      animates it, and a page that recolours its mark at rest fails), on a host that resets every inherited property, placed in the element's
      own parent (the parent's opacity, filter and transform apply to it too): over the content box of an outermost `<svg>`, whose children
      are hidden so its own border and background stay, or over the whole box of any other element, which is hidden as a whole; with the
      element's own transform about the same origin. The host is placed by measuring it, so a positioned or offset ancestor does not move it;
      one that ends more than 0.01 css px off, as an ancestor's rotation or skew makes it, is "not verified" (`skipped`), never compared.
    Same page and position, same raster tiles: the comparison is exact (`tolerance` 0; a larger value is accepted). A reference drawn on a
    scratch page at the origin is not the same raster away from it (Chromium draws in tiles about 256 px wide that advance 254 px; a lockup
    at x = 53 differed in dozens of pixels). Before the pictures are taken each animation is turned into plain style and cancelled, since an element that keeps an animation, even a
    finished one, is drawn on a layer of its own with antialiasing a few levels off. What is written is what the page draws: after every animation
    has been finished (and the ones their ends start), for each animation whose effect still applies (progress is not null: a fill holds it) the
    computed style of each property it moves is read, then every animation is cancelled, then the values read are written inline. An animation whose
    effect no longer applies is only cancelled: `animation: hide 1s 1s backwards` with `@keyframes hide {from, to {visibility: hidden}}` leaves the
    element visible once it has ended, and `commitStyles()` (which writes the keyframe value) would have hidden it. A mark the page keeps on a layer
    of its own (`will-change`, a 3D transform), or rotates or scales at rest by its own transform, still is: remove `will-change` from a still (it was the way
    to make the earlier scratch-page comparison pass; the in-page comparison does not need it), or give the case a `tolerance`. An animation on a
    pseudo-element whose effect still applies has no inline style to write to, and one with a property whose value reads empty cannot be written: each
    stays on the page, and the row names it. A mark with no box fails the row. A failing pair is kept in the data folder's scratch area, outside the project, in a folder named after the case (its
    name made a folder name, as for frames).
  - `whole-pixel`: for a pixel mark, the case's static SVG with `shape-rendering="crispEdges"` on its root (the pixel art of `svgtools.pixel_art`),
    or `"pixel": true` (`"pixel": false` turns it off), every sample point must show a whole-pixel translation (the `e` and `f` of the matrix
    of its `translate`, `rotate` and `scale` properties and then its `transform`, in the element's own units; a percentage in `translate` is
    of the element's reference box) of every animated target. A percentage on a pseudo-element cannot be read and makes the row "not
    verified". For a vector mark the row is info: `a vector mark: smooth easing allowed`.
  - `edges:<width>` (one row per width, `edges:360` and `edges:390` unless `widths` says other whole numbers from 200 to 4000; an empty list
    is an info row `edges`): the page is loaded again at that width (800 high), looked at as the normal pass is (a motion a script starts
    later is waited for), and at every sample point of its own animations these must hold: `documentElement.scrollWidth <= clientWidth`
    (the page cannot be swiped sideways), the box of the mark element and of every element inside it with a non-empty box has `left >= 0`,
    `top >= 0` and `right <= clientWidth`, and `scrollHeight` is no more than at rest (every animation at its end). **A box counts only where it
    is painted**: it is cut by every ancestor that clips it, from the element up to and including the mark element (an HTML ancestor with `overflow-x`
    or `overflow-y` other than `visible` clips that axis, to its padding box; `contain: paint`, `strict` or `content` clips both; an `<svg>` clips to
    its viewport, a nested one to its `x`, `y`, `width` and `height`, unless it says `overflow: visible`; a positioned box is cut only by its containing
    block and the ancestors above it), and it is not counted at all while its effective opacity (the product over the element and its ancestors) is 0 or
    it is `visibility: hidden`. A part an `<svg>` mark clips at its own viewport is therefore not past an edge; say `overflow: visible` on the `<svg>` to
    have the parts counted where they move (the page still does not scroll: an `<svg>`'s content never widens it). A failure names the point,
    the element (tag plus id, class or `data-part`), the edge and how far past it, the worst of each, four of them and how many more:
    `at 62% (310 ms): g#letter-a 22 px past the right edge at 360 px`; the page's own line comes after the elements'. A mark with no box at
    that width is a warning, not a pass in silence.
  - Reduced pass (`prefers-reduced-motion: reduce` emulated; the page is watched for `settle_ms`): `reduced:animations` (an animation that
    is running when the proof first sees it fails), `reduced:raf` (no `requestAnimationFrame` call in the last 500 ms of the watch),
    `reduced:listeners` (no `pointermove`, `mousemove`, `touchmove`, `wheel`, `scroll`, `deviceorientation` or `devicemotion` listener,
    script-registered or inline), `cls:reduced`, and `reduced:rest=static` (compared in place as above).
- **One report per proof file**: `assets/_checks/motion/<slug>-<hash6>.json` (tool name `motion/<slug>-<hash6>`, the slug is the proof's
  file stem, the hash the first six hex of the sha256 of its project-relative posix path, as the disk spells it (on macOS `MOTION/PROOF.JSON`
  is `motion/proof.json`, and has its report); `motion_report_tool` in `_common.py` and
  `proofReportTool` in `_common.mjs` give the same name). It carries `proof`, the proof's path. Its `inputs` are the proof, each case's page and still, and every project file the local server answered
  while the pages were open (a linked stylesheet or token file such as `assets/tokens/tokens.css`, a script, an image, a font), so that a motion that
  lives in one of them makes the report stale when it changes, for `check` and for the book. Two runs of different proofs never touch each other's report;
  nothing writes `assets/_checks/motion.json` any more. `check` gates every report there as it gates a downscale one: a proof under
  `rounds/`, `history/` or a `removed-*/` folder is an exploration proof, listed as an info row (`exploration proof, not gated`) and never
  failing; a report whose proof file no longer exists is a warning that names it and says to move the report to `removed-<date>/`; a manifest
  row with `qa: ["motion"]` needs at least one passing gated report (the `qa:motion` row; "not verified" without one, naming the command). A
  `motion.json` of an earlier version is still gated as before, with a warning (`report:motion:legacy`) to run `shot --motion` again. The
  book's Motion chapter and its proof table read the same reports, the gated ones.

### Frames (`frames <proof.json> [--case NAME] [--count N | --at 0,25,50,75,100]`)

For each page case of a proof (or the named one; a states case is skipped with an info row, or a usage error when named) the page is seeked as
above and the mark element's box (its box at rest, rounded outward to whole pixels) is screenshotted at device scale 2 on the page's own
background, at each point: by default five, 0, 25, 50, 75 and 100 percent of the motion's length; `--count N` spreads N points evenly (1 to
100), `--at` names percentages (0 to 100, in the order given). Written into the project, for a gated proof (a proof of the project: the only stills the book replays) in `motion/frames/<case>/`, and for a
try-out proof, one under `rounds/`, `history/` or a `removed-*/` folder (`motion_proof_kind` in `_common.py` and its twin `motionProofKind` in `_common.mjs`; one table of cases in the tests pins both), beside it in
`<the proof's folder>/frames/<case>/`: a motion round keeps the stills of each variant in `rounds/rN/<name>/frames/<name>/` and never touches `motion/frames/`. `history/` is frozen and every round but the latest is read-only (the hook
guard keeps both from an edit, and cannot see what a command writes), so a proof inside `history/`, or inside `rounds/rN/` while a higher `rounds/rM/` exists, is a usage error (exit 2) before a browser starts and before anything is written: it says why and
what to do, take the stills before the round is frozen or the next one begins, or copy the proof and its page into the latest round and run `frames` there. The case name is made a folder name (letters, digits, `.`, `_`, `-`; two names that make one folder are a usage error):

- `<NN>-<pct>.png`: one still per point, `NN` its place from 00, `pct` its percent (`16.67` for a third of a hundred);
- `strip.png`: the stills side by side, in order, with no gap;
- `reduced.png`: the element under `prefers-reduced-motion: reduce`;
- `frames.json`: each frame's `percent`, `ms`, `file` (project-relative) and `sha256`, the strip's and the reduced still's, the motion's
  length and the picture size; no date and no version, so a rerun is byte-identical.

Each file is written only when its bytes change; a rerun says `unchanged`. A still of an earlier run with other points is left where it is
(nothing is deleted) and named in a warning row. A case with no seekable motion (no Web Animation, or only one on a scroll timeline, or
motion driven by `requestAnimationFrame`) exits 1 and says why, and writes no file; so does a page that calls `requestAnimationFrame` while
the stills are taken (they would differ from run to run). A case's folder belongs to one proof: when its `frames.json` names another proof,
or cannot be read, the run is a usage error (exit 2) before a browser starts, naming the folder to move to `removed-<date>/` or the case to
rename. The rule holds per folder: the folder of a try-out proof is its own folder's `frames/`, so a gated proof and a try-out one with a case of the same name never meet, and two try-out proofs of one folder do. A try-out
folder whose `frames.json` names a proof of another folder is a round copied whole, its stills with it: they are taken again in place and an info row, `frames:<case>:copied`, says so. A strip wider or higher than 65535 px (the largest picture Chromium's canvas writes) is a usage error that says how many stills fit. Nothing else in the project is written but the report,
`assets/_checks/frames/<slug>-<hash6>.json` (named like the motion report; `check` gates it as it gates a motion report, below). Its `inputs` are those of the motion report: the proof, the pages
and every project file they loaded. One report per proof file is rewritten by every run and holds the rows of the cases that run took (`--case X` leaves the report
with the row of X alone), which is how the book tells the stills a run vouches for (below). It also records `points_pct`, the points of the run.

`check` gates every report there by the proof it names, as it gates the motion reports (the proof of a report is read from the report): a current, passing report is a pass and a failing
one a failure; a stale one (a page, a stylesheet or a script the page loaded, or the proof, changed since the stills were taken) is "not verified" and names `brand-creator frames <proof>
--count N` (`--at` with the points when they are not evenly spread; `--count 25` when the report records none) **and then `brand-creator book`**, because the book replays the stills the
report vouches for; a report of a proof under `rounds/`, `history/` or a `removed-*/` folder is an info row (`exploration proof, not gated`), and one whose proof file is gone a warning that
says to move it to `removed-<date>/`. The motion report being current says nothing about the stills, so a stylesheet change is not "verified" until `frames` and `book` have run. A current, passing report is
"not verified" as well when a case of its proof has stills in `motion/frames/<case>/` (that `frames.json` names the proof, and the case is still a page case of it) and the report has no passing `frames:<case>`
row for it: a run of `frames --case X` rewrites the report with the row of X alone, so the other cases replay stills that nothing vouches for. The row names the cases and the run that takes every case,
`brand-creator frames <proof> --count N` (or `--at`), **and then `brand-creator book`**.

### Motion spec (`motion/motion.json`)

The one record of the owner's decision on motion, and, when the brand moves, the machine-readable motion spec: the signature move, the moving parts and the timeline written in tokens. Absent means motion is not decided; `"off"`
means nothing moves; `"on"` is the approved move. It is the one source the adapters (see `adapters` and `applied-skill` below) and the book ("Brand book") read; `motion/SPEC.md` (`templates/MOTION-SPEC.md`) is its
prose twin for an implementer. `scripts/lib/motionspec.py` reads it: `load(project)` returns the validated document, or `None` when the file is absent (`load(project, tokens=False)` checks the document alone and leaves its references unresolved: what `decision()` reads).

```json
{"schema": 1,
 "motion": "on",
 "reason": "...",
 "signature": {"name": "...", "description": "...", "where": ["..."]},
 "parts": [{"id": "dot", "description": "..."}],
 "timeline": [{"part": "dot", "property": "transform", "start": "{motion.stagger}", "duration": "{motion.base}", "easing": "{easing.standard}", "note": "..."}],
 "rules": ["reduced motion: nothing moves", "..."]}
```

| key | what it holds |
|---|---|
| `schema` | `1`, a whole number: the only schema this version reads |
| `motion` | `"on"` or `"off"`, the owner's answer on motion (Standard and Full: before G4); `"off"` means nothing moves |
| `reason` | required with `"off"`, a non-empty string (why, in the owner's words); refused with `"on"` |
| `signature` | required with `"on"`, refused with `"off"`: `name` and `description` (non-empty strings) and `where` (a non-empty list of the places the move shows) |
| `parts` | optional list of `{id, description}`, refused with `"off"`; `id` is lower case words joined by single hyphens (`a-z`, `0-9`, `-`) and unique |
| `timeline` | optional list of steps, refused with `"off"`; a step has `part` (the id of a part), `property` (what moves, a non-empty string), `start`, `duration`, `easing` and an optional `note` |
| `rules` | optional list of non-empty strings, the motion rules in plain words (`reduced motion: nothing moves`) |

A step's `start` is `"0"`, a reference to a duration token (`"{motion.stagger}"`), a reference times a number (`"{motion.stagger} * 2"`; the number is 0 or
more), or a sum of those (`"{motion.base} + {motion.stagger} * 2"`: a step that starts when another ends, plus a stagger); every reference in it must name a
duration token. Its `duration` is a reference to a duration token and its `easing` a reference to a cubicBezier token. A reference is `{<token path>}` and must name a
token of the right kind in the built tokens (`assets/tokens/tokens.json`, under `motion`; see Token sources).

An unknown key is refused at every level. Every refusal is exit 2 and names the field path and what is wrong
(`timeline[1].easing: no token named easing.nope (cubicBezier tokens: ...)`); all the problems of one document are listed, the first eight shown. Tokens that
are not built are exit 3, and the message names `brand-creator tokens`; a document that is wrong in itself is exit 2 whether or not the tokens are built, and
a document with no reference (motion off, or no timeline) needs no tokens. `check` validates the file whenever it exists: a failing `motion:spec` row (never a
crash), or "not verified" when the tokens it names are not built.

### The motion decision (`brand-creator motion [--json] [--off "<reason>"]`)

`scripts/motion.py` reads and records the decision in `motion/motion.json` through `scripts/lib/motionspec.py` (`decision()`, `status_lines()`). Standard and Full decide motion for every brand before G4: a motion round after G3 (the
default), or "nothing moves", recorded once by the owner. Quick decides it at G4 and only when something moves: no due line and no `check` row.

- `motion` prints one status line and exits 0: `motion: on (signature: <name>)`, `motion: off (nothing moves: <reason>)` or `motion: not decided`. The last is followed, in Standard and Full once G3 is recorded, by
  `` due before G4: run the motion round, or record nothing moves with `brand-creator motion --off "<the owner's reason>"` ``. `--json` prints `{"motion": "on" | "off" | "undecided", "signature": <name> (on), "reason": <text> (off)}`.
  A `motion/motion.json` that is not valid in itself exits 2 with the message of the motion spec and is never read as an answer. The tokens it names are not looked up: the motion round comes before the tokens are built, so an answer whose timeline names
  tokens not built yet is still printed, `--off` over it is the exit-2 refusal below, and whether the tokens are built is the `motion:spec` row of `check`.
- `motion --off "<reason>"` records that nothing moves, once, in the owner's words. With no `motion/motion.json` it writes `{"schema": 1, "motion": "off", "reason": "<reason>"}` (checked by the motion spec before it writes; it creates
  `motion/`), prints `recorded: nothing moves (<reason>) in motion/motion.json` and exits 0. Already off, it writes nothing and prints `already recorded: nothing moves (<the recorded reason>)`; when the reason given differs it says the
  recorded one stands and that changing it is an edit of `motion/motion.json` followed by `brand-creator check --cascade`; exit 0. On, it writes nothing and exits 2: `` motion/motion.json says the brand moves (signature <name>); turning it
  off is a rule change: edit motion/motion.json and run `brand-creator check --cascade` ``. An empty or blank reason exits 2, and so does `--off` together with `--json`.
- `state` (the summary) prints the same line, so Step 0 of the skill sees the decision and never asks again; `state --json` has it as `"motion"` (the data of `motion --json`). A `motion/motion.json` the summary cannot read is a
  `motion: cannot be read (...)` line and `{"motion": "unreadable", "problem": ...}`, never an exit code: the summary must always print.

### snapshot, verify-idempotent, staleness, specs-due

- `snapshot take|diff|verify`: sha256 lists of folders (read only; a folder may be outside the project). Relative paths are relative to
  the project; `--out` must be inside the project or the data directory. A refactor of a generator is proven by take, change, take, diff.
- `verify-idempotent --cmd "{bc} emit web" ...`: runs a chain twice and compares the output trees (`--root`, default `assets`) by sha256;
  a file that differs, appears or vanishes fails. The determinism rules (`scripts/lib/determinism.py`) are linted over the final tree:
  PNG files have no `tIME` chunk and no `date:*` text chunk (`magick_png_args()` or px_lib), zip files have sorted entries and the fixed
  mtime 1980-01-01 (`fixed_zip()`), PDF `/CreationDate`, `/ModDate`, XMP dates and `/ID` are fixed (`normalise_pdf()`; a PDF with compressed
  object streams cannot be fixed in place and is refused: write it with Ghostscript `-dCompatibilityLevel=1.4`), an `Assets.car` is compared
  by `assetutil --info` with the per-compile UUID in each rendition name, the digests and the timestamp removed (`determinism.car_renditions()`; two
  compiles of one input differ in those and in nothing else), and Chromium PNGs are byte-stable on one machine only. A difference that cannot be removed goes in
  `qa/idempotence.json`: `{"schema": 1, "entries": [{"path": "assets/social/*.png", "reason": "...", "substitute": {"check":
  "pixels-equal"}}]}`; every entry needs a reason and a substitute check from `pixels-equal`, `png-structure`, `json-equal`,
  `zip-entries`, `text-equal-except` (`pattern`), `assetutil`, `command` (`command`, exit 0 = equivalent), which the two versions must
  still pass; an entry matching no difference is a warning.
- `staleness`: `tools/inputs.json` records the sha256 of every upstream input (default globs `tokens/*.json`, `assets/logo/*.svg`,
  `assets/logo/*.png`, `qa/*.json`, `FACTS.md`, `INVENTORY.md`, `tray/*.json`, plus `BRAND.md` and `DESIGN.md` once they exist, extended with `--input`), the plugin version, the sha256 of the emitter code (`scripts/emitters/*.py`,
  `platform-specs.json`, `scripts/lib/*.py`) and needle sentences that must stay in sibling documents. `staleness --write` records after a
  build; `staleness` flags any difference (exit 1); `check` runs the comparison whenever the file exists.
- `specs-due` (needs no project): lists the platform-spec rows that are stale (`checked` older than `stale_after_days`, from
  `BRAND_CREATOR_TODAY` or today), that become stale within `--within` days, or are status U or R; `--fail-on-due` exits 1 on a stale row. A
  row's `checked` date records a person reading the source, never a script run.

### px_lib

`scripts/lib/px_lib.py` is the standard-library raster toolkit for marks generated by code (grids, voxels, geometry): an RGBA buffer
(`Img`), `grid_image()` for marks drawn as text, a deterministic PNG writer (IHDR, IDAT, IEND only), a PNG reader, an ICO writer and a
run-length SVG writer (one path per colour). A project's generator (`tools/*.py`) imports it from `$BRAND_CREATOR_ROOT/scripts/lib`.
The Acme example's `tools/grid_mark.py` and `tools/state_icons.py` are the worked examples; a test rebuilds them byte for byte.

### What `check` gates from these

`motion/motion.json`, when it exists, is validated on every run (the `motion:spec` row; see Motion spec). Standard and Full decide motion before G4 (see The motion decision), so with the tier `standard` or `full` and G4 recorded
`motion:decided` passes when `motion/motion.json` exists (on or off; whether it is valid stays the `motion:spec` row) and fails when it does not: "Standard and Full decide motion before G4: run the motion round, or record nothing moves
with `brand-creator motion --off "<the owner's reason>"`". With motion `on` under the same condition `motion:proof` passes when the report of `motion/proof.json`, the proof of the approved move, is current and passing ("met by the report of motion/proof.json") and no report of it is current and failing: a failure is never outvoted by a passing report of the same file under another name. That report is found among the gated motion reports by the proof it names, as the same file, so a disk that does not tell letter cases apart may name it `Motion/proof.json`. The report of any other proof never counts: another proof of the project (gated in its own row all the same), a report that names no proof, the report of a try-out proof, and the one report of an earlier version, `assets/_checks/motion.json`. Otherwise it fails when
`motion/proof.json` does not exist ("motion/motion.json says the brand moves, but there is no proof of the approved move: write motion/proof.json"), fails when its report is current and failing ("the proof of the approved move fails: <the report's own row>; change the move as its failing rows say, then run `brand-creator shot --motion motion/proof.json`"), and is "not verified" when it has no report or a stale one ("run `brand-creator shot --motion motion/proof.json`");
when the report of that proof is current and says not-verified, the row says why, as `board-lint` says it of a variant (one function, `motionboard.unverified_why`): it quotes up to three of the rows the report could not verify, each with its id and detail, and, only when one names
`requestAnimationFrame`, adds that such a move stays not verified however often the proof runs and says to write it as CSS animations, CSS transitions or `element.animate()`; the row of the report itself, `report:motion/<slug>-<hash6>`, quotes the same rows
(a stale report says it is stale, as for every report);
a failing gated report keeps its own fail row as well. With the tier `standard` or `full`, G3 recorded, G4 not and no `motion/motion.json`, `motion:decided` is an info row ("not decided yet; due before G4: ..."); before G3, and in Quick, there is no row.
A manifest row with `qa: [...]` needs a current, passing report from the matching tool (`downscale`, `states`, `motion`, `family`, `fonts`
= `fontcheck`, `idempotent` = `verify-idempotent`); for `downscale` it is the report of the row's own `downscale_source` (a row without one fails,
and a passing report on another file never counts); for `motion` it is at least one passing gated report (the `qa:motion` row; see Motion proof); a report that exists is gated whether or not a row asks (the `frames` reports too, by the proof each names; see Frames). A missing report is "not
verified" (exit 3), a stale one too, a failing one exit 1. When `qa/rules.json` sets a colour-vision threshold (a key of its `cvd`
section), a passing contrast report without colour-vision rows (one `contrast` wrote without `--cvd`) is "not verified" too
(`report:contrast:cvd`, naming `contrast --cvd`). Slots off the band rule, platform-spec rows stamped stale or U, and
`tools/inputs.json` differences are gated or warned as described above.

## Brand book

`brand-creator book`, `book-lint`, `book-pdf`, `patch` and `collapse` (scripts `book.py`, `book_lint.py`, `book_pdf.py`, `patch.py`,
`collapse.py`; libraries in `scripts/booklib/`, which `staleness` does not hash with the emitters). Needs `content_languages` and `edition`
in BRAND-STATE.md (exit 2 otherwise: the language is never defaulted from `language`).

**Two modes, by `mark_source`.** `generated` and `existing`: the book is generated and never hand-edited; `book` builds `book.html` from
the built tokens (`assets/tokens/tokens.json`), `assets/manifest.json`, BRAND-STATE.md (edition, approval, decided items, directions),
FACTS.md, the contrast and downscale reports and `book/chapters/*.md`, and writes it only when it lints clean (`--self-consistency`
included). The same inputs give the same bytes (no clock, no random numbers; PNG proofs are rasterised by resvg); `book --verify`
rebuilds in memory and compares. `check` gates a generated book three ways: a current passing `book-lint` report made with
`--self-consistency`, a current `book` report, and a `book.html` whose sha256 is the one `book` recorded (a hand edit fails). `authored-vector`:
the book is hand-authored HTML; `book` exits 2, `book-lint` is the gate, `patch` is the only edit path (below). Both reports record
`state_view_sha`, a hash of what the book reads from BRAND-STATE.md and FACTS.md (edition, approval, G6, directions, rules, edition log,
facts); `check` treats a report whose view changed as not verified. A change to the phase or review URL does not. The reports also record `frames_view_sha`, a hash of the list of the stills of the gated proofs: for each `motion/frames/<case>/` the sha256 of its `frames.json` and of its strip and its reduced still, or `absent` for a picture that is not there (so one that goes and comes back is seen). A `check` that finds it different says "not verified" (`report:book:frames`, `report:book-lint:frames`), which is how stills that appeared, went or changed after the book was built are noticed. The list is empty, and the stills are none of the inputs of `book`, `book-lint` and `book-pdf`, for a book that shows none: one whose chapter list has no `motion` (a Quick book) or whose `motion/motion.json` says `off`. They also record `manifest_view_sha`, a hash of the manifest rows the book shows (everything except the press kit, which contains the book's PDF, so the book cannot name its hash and a rebuilt kit must not make the book stale; the files chapter says where the kit is, without a checksum); `assets/manifest.json` is not a report input, and a changed row the book shows makes `book`, `book-lint` and `book-pdf` not verified.

**Chapters.** Registry order, selected from `tier`, `architecture`, the project's files and `book_chapters`: quick `idea, mark, colour,
files, changing` (plus `wordmark` when `assets/logo` has a wordmark or lockup); standard adds `motion` (when `motion/proof.json`,
`motion/SPEC.md` or `motion/motion.json`, on or off, exists), `type`, `use`, `proof`, `donts`, `history`; full adds `adoption` and `launch`; `endorsement` and `family` in the
family modes; `tone`, `photography`, `components` only when named in `book_chapters`. Each chapter is `book/chapters/<id>.md`
(`<id>.<lang>.md` for each language when `content_languages` has several; every language is required). `book --init` copies the skeletons
from `templates/book/` and never overwrites; `[[fill: ...]]` left in a chapter fails the build.

**Chapter Markdown** is a documented subset (`scripts/booklib/bookmd.py`): `## `/`### ` headings, paragraphs, flat lists and task lists,
`>` quotes, pipe tables, fenced code, own-line images (embedded as data URIs; SVG under `assets/` is mark-linted), inline `**`, `*`, `` ` ``,
links. Raw HTML is escaped. Anything else is an error with the line number. Computed blocks on their own line: `{{marks[:stem,stem?]}}`,
`{{mark-sizes}}` (the drawing the size band rule picks, rendered at exactly the size on light and dark, the enlarged copy being the same
pixels, plus the downscale reports' accent measurements), `{{colours}}`, `{{contrast}}` (WCAG ratios computed from the tokens), `{{type}}`,
`{{motion}}`, `{{tokens}}`, `{{files}}` (one row per manifest row and source artwork file with `data-path` and `data-sha`; a row marked `superseded` carries a note saying so), `{{checks}}`,
`{{decided}}`, `{{history}}`, `{{edition-log}}`, `{{donts}}` (five misuse drawings of the mark), `{{facts}}`. Inline: `{{count:NAME}}`
(`files, slots, colours, pairs, roles, sizes, artwork, emitters, chapters`), `{{fact:LABEL}}` (a FACTS.md row's value), `{{edition}}`,
`{{name}}`, `{{approved}}`. `::: variant GROUP NAME` and `::: switcher GROUP` fences are open choices (see `collapse`). Settings in
`book/book.json` (unknown keys are exit 2): `min_label_px` (default 12, stated in the book), `sizes`, `fonts` (`{family, file, weight, style}`,
embedded as data URIs), `labels` (`{lang: {English label: translation}}`; a label with no translation is shown in English and warned),
`output`, `lint` (`history_chapter, forbidden, scratch, round, status_words, count_nouns, allow_external_links, files_exclude`).

**The motion chapter.** `{{motion}}` shows `motion/motion.json` ("Motion spec") and the project's tokens. With the spec `"on"`: the signature move
(`Signature move: <name>.` and its description, then `Shown in:` as a list), the replay (below), a parts table (`Part`, `Description`), a timeline table
(`Part`, `Property`, `Start`, `Duration`, `Easing`, `Note`) in which every reference is its token name and what it resolves to (a start is its sum in ms and the
expression, `560 ms motion.base + motion.stagger × 2`, or `0 ms`; a duration its ms and token; an easing `cubic-bezier(x1, y1, x2, y2)` and token), the tokens of
`tokens.json` `motion` (a table of every duration in ms, a table of every curve with its four numbers and a small drawing of it: an inline `<svg>` with
`role="img"`, an `aria-label` naming the token and the curve, no text, room above 1 and below 0 for an overshoot, 40 px to the unit and the numbers rounded to two
places, so the drawing is the same on every run; then any other `duration.*`, `easing.*` or `motion.*` token as the tokens write it), the motion rules as a list, and
a table per gated motion report (`shot --motion`) with the columns `Case`, `Check` and `Result`: one row per pass, fail or warn row of the report (as before; info and not verified rows are not shown), its `Check` the row id
without `motion:<case>:` (`cls:normal`, `edges:360`), the checks of a case together, and the `Case` cell the name the chapter gives that case's replay (the signature move, numbered like the replay's text), else
`Case` and the case's place in the report's `cases` list (`Case 2`); **the case's own name is never printed** (see "The replay"). The heading of a table is `Motion proof` (`<h4 data-proof="<proof path>">`), or
`Motion proof 1`, `Motion proof 2` ... when there are several, in the order of the proofs' paths (the report of an earlier version, which names no proof, first); the report table of the proof chapter (`{{checks}}`)
names the same reports the same way, the report's name in a `data-report` attribute and its proof in `data-proof`. **A proof's file name and its report's name (`hero-v2`, `motion/hero-v2-3fa1b2`) are the author's working names too, and are never printed.**
The checks of a states case name its states (`1x:control:rest!=draft-v2`, `1x:draft-v2=expected`, `1x:state:draft-v2`, written by `shot --motion`, which keeps them in the row ids): the table prints each state by
its place in the case, in the order the control pairs, then the expected-state checks, then the states a check did not find name them (`1x:control:state 1!=state 2`), and keeps the check as the report
has it in the row's `data-check` attribute (a row whose check names no state has none). A row that belongs to none of the report's `cases` is
shown by its `label` under a case of its own (the state names of an expected-state label by their place too), and a build warning names it. With `"off"`: `Nothing moves: <reason>` and the proof tables, if any; no replay (stills that exist are
left out, and a build warning says so). Without `motion/motion.json` (a project from before it): the table of every `duration.*`, `easing.*` and `motion.*` token as
the tokens write it, the replay if stills exist, the proof tables, and a build warning that the chapter has no signature move and no timeline. A `motion/motion.json`
that is not valid stops the build (exit 2), as it stops the adapters. `templates/book/motion.md` holds only the owner's prose (why it moves, reduced motion); a chapter
file written from an earlier template, with its own `{{motion}}` line, gets all of the above.

**The replay.** For each `motion/frames/<case>/frames.json` (written by `frames`) whose proof is a gated proof of the project the chapter holds one
`<figure class="motion-demo" data-motion-demo="<case>" data-length-ms="<length_ms>" data-frames="<N>">` with, in this order: a checkbox `id="bc-replay-<case-slug>"` and its
`<label for>` (`Replay`); a checkbox `id="bc-slow-<case-slug>"` and its label (`4× slower`, with the multiplication sign); `<div class="motion-stage">` holding the flipbook
(`<picture><source type="image/png" srcset="<strip data: URI> <scale>x"><img class="motion-flip" src="<1 x 1 PNG data: URI>" alt width height></picture>`, `strip.png` in the `<source>`) and the reduced still (`<img class="motion-reduced" alt>`, `reduced.png`); the
percentages and times of the stills in `<p class="cap motion-times">`; and a `<figcaption>`. The case slug is the case name in lower case with each run of other characters
made one hyphen; with several content languages each language's copy ends `-<language>`, so ids stay unique. **The case is an id, not text**: it stays in `data-motion-demo`
and in the ids and animation names, and the text a reader gets (the alts, the figcaption, the proof table) names the replay by the signature move of `motion/motion.json` when motion is on,
else `The mark in motion`, followed by ` (1)`, ` (2)` ... when the chapter has several replays, so a case named `hero-v2` or `draft-x` does not trip the word rules. Every image
is a `data:` URI of the file's exact bytes, and **the strip is embedded once**: the flipbook is the strip `<img>` itself, in a `<picture>` whose `<source>` holds the strip in a `srcset`
with the density `<scale>x` of `frames.json` (so that one still is its css size), `width` and `height` of one still (`size` of `frames.json`) and `object-fit: none` so that it shows one still
at a time; the `<img>` has the `src` the HTML standard asks of it, a 1 × 1 transparent PNG (68 bytes, a `data:` URI of 114 characters) that the browser does not draw while the `<source>` matches, where a `src` with
the strip would embed it twice. book-lint reads the strip from the `<source>` (else from the `<img>`'s own `srcset`, else its `src`), and only from a `<source>` with no `media` attribute and a `type` that is absent or `image/png`: a browser skips a
`<source>` whose media does not match or whose type it does not know and draws the stand-in, which the lint cannot tell from the outside, so `motion:replay` and `motion:stills` fail and name that `<source>`. `object-position: -i × w px 0` moves it from still to still. The keyframes put still i at its percent (`@keyframes`, a keyframe at 0 and at 100
whatever the points are), each held until the next (`step-end`), over `length_ms`, once, fill `both`: it ends on the last still. The checkboxes start it again with CSS alone: four
identical `@keyframes` (`bc-flip-<case-slug>-r0s0`, `-r1s0`, `-r0s1`, `-r1s1`, for the replay and slow boxes unchecked or checked) and the rules `#bc-replay-…:checked`,
`#bc-slow-…:checked` and both, reaching the flipbook through the siblings (`~`), choose among them, so toggling either box is a new `animation-name` and a new run; the slow
box also sets `animation-duration` to 4 × `length_ms`. The inputs are visually hidden with `clip`, never `display:none`, the `hidden` attribute or a negative `tabindex` outside the
media below, so the keyboard reaches them. Under `prefers-reduced-motion: reduce` on a screen (`@media screen and (prefers-reduced-motion: reduce)`) the flipbook is not shown and has `animation: none`, the two controls and
their labels are not shown, and the reduced still is. In print, with the preference on or off, the controls and the reduced still are not shown, and the same flipbook is: no animation
(`!important`, to outweigh the id rules), the full strip width scaled to the page (`width: 100%`, `height: auto`, `object-fit: fill`), with the times under it. The book's rules for replays (`DEMO_CSS` and the block of each case in
`bookgen.py`) follow its own, and only when it has one: a book without is byte for byte what it was. What cannot be shown is a build warning, never silence: stills of an
exploration proof (`rounds/`, `history/`, `removed-*/`) or of a proof that is gone, a `frames.json` that cannot be read (or names a proof outside the project), a folder that is not its case's own, two cases that make one
id, a missing strip or reduced still, and a case the proof no longer has as a page case (`<case> is no longer a page case of <proof>: move motion/frames/<case>/ to
removed-<date>/`): each is left out. Built, and warned about: fewer than 9 stills (the warning says it jumps between N stills and that `brand-creator frames <proof> --count 25`
makes it smooth); a file that is not the one `frames.json` lists; a `frames` report (`assets/_checks/frames/<slug>-<hash6>.json`) that does not vouch for the case, which is
a report that is missing, stale, without a `frames:<case>` row (one report per proof is rewritten by every run, so `frames --case X` leaves the other cases' stills unvouched) or with
that row not passing (each warning names the run to make: `brand-creator frames <proof> --count N` for a proof of several page cases, since a run of one case would leave the
others unvouched, and `brand-creator frames <proof> --case <case> --count N` for a proof of one; `book` does not run `frames`); stills that do not run from 0 to 100 percent, or two at one percent. A motion chapter that is not off and has no replay built (no stills, or
none that can be shown) warns with `brand-creator frames motion/proof.json --count 25` (an info note instead when the proof has no page case, which `frames` needs). Only the stills
of gated proofs are inputs of the `book` and `book-lint` reports (with their proofs and `motion/motion.json`), and only for a book that has the Motion chapter and whose motion is not `off`; a try-out's are not.

**The cover.** Its title (the `<h1>`) is the brand's drawn wordmark when `assets/logo/wordmark.svg` exists: an image whose alt is the name, with
`wordmark-dark.svg` switched like the cover's marks (`sch-l` and `sch-d`; without a dark file the light one shows in both schemes, and a warning says so),
in the cover's art box (at most 320 x 96 px; pixel art, an SVG whose root says `shape-rendering="crispEdges"`, at a whole-number scale: `svgtools.fit_box`,
the rule the cards use). Without a wordmark the name is typed. In print the chapters and the cover keep no bottom padding: Chromium moves the padding of a
box that goes on from an earlier page to a page of its own when the box ends within it of the page's end, and the next forced page break leaves that page empty.

**The cover and adoption.** The `Adoption` row of the cover states only what the data back: `Adoption approved <date>` once G6 (the owner's go) is recorded, else `Adoption not yet approved`, and, when `adoption.json` exists, `; N of M rows done` counted from its `progress`. G6 alone never says "applied". `adoption.json` (row progress) is in the book's state view and inputs, so a progress change makes a built book stale; an `adoption.json` that is not an adoption record exits 2.

**Edition and approval.** `edition` is the book's number. The cover (`data-cover`, `data-edition`, `data-stamp`) shows the stamp word and the G5
date only when G5 is recorded and `approved_edition` equals `edition`; the word is APPROVED, or the `labels` entry of `book/book.json` for `APPROVED`
in the book's first content language (`labels.pl.APPROVED`; English is never translated; an empty entry exits 2), and `book-lint` looks for that word,
in a hand-authored book too; `state --record G5` writes `approved_edition`, so a later edition is pending until it is approved again.
`patch` and `collapse` log under `## Edition log` and refuse to change an approved edition unless `--new-edition` opens the next. A
hand-authored book must show the stamp before G5 is recorded (patch the cover, then record).

**book-lint rows** (each one result in `assets/_checks/book-lint.json`): `html:head`, `ids:duplicate`, `anchors:broken`, `network:refs`
(script, handlers, `<link>`, iframe, `src`/`srcset` that is not `data:`, http(s) in links or text, CSS `url()` that is not `data:`, `@import`),
`links:files` (warn), `marks:lint` (mark_lint on every inline `<svg>`, every `<img data-mark>` data URI and every linked `.svg`; an
`<svg data-diagram>` may hold text but no script or external reference), `images:alt`, `words:scratch`, `words:round` (outside the history
chapter), `words:forbidden` (FORBIDDEN list of BRIEF.md and cliches.md, outside the history chapter), `words:status` (a status word needs a
FACTS.md value that contains it), `variants:open`, `chapters:required`, `edition:stamp`, `counts:data` (every `data-count` equals the data),
`counts:typed` (a digit followed by `files`, `slots`, `colours`, `pairs`, `roles`, `sizes` or `chapters` in prose must equal the data; write it
as `{{count:NAME}}`), `facts:data`, `files:accounting` (every manifest row and artwork file has a `data-path` row with the right `data-sha`),
`legal:<label>` (FACTS.md rows whose label starts `legal` must appear verbatim), `lang:parity` (every `lang=` + `data-key=` block exists in
each content language with the same block structure; text in a language that is not in `content_languages` fails), `lang:<code>:<rule>` (warnings with line and offset: the `check` of each rule in `scripts/data/languages/<code>.json` run on the book text in that language, the whole text with one content language, the `lang=` elements with several; kinds `single-letter-nbsp` and `low-opening-quote`; `fontcheck --print-rules` prints every rule for a prompt), and three rows for the replay of the motion
chapter, which read the book's CSS with its `@media` context, the elements it styles and the cascade (type, `#id`, `.class`, `[attribute]`, `:checked` and the four
combinators). **A rule the cascade does not apply is named, never passed over in silence**: a selector it cannot parse, or one with a pseudo-class other than `:checked`
(`:is`, `:not`, `:where`, `:has`, `:hover` ...), applies to nothing, and so do a rule inside `@layer`, `@scope`, `@container` or `@supports` (the cascade weighs no layers, scopes or
conditions) and a style rule that holds nested rules (CSS nesting: the cascade does not resolve `&`); when such a rule sets what a row reads (`display`, `visibility`, `opacity`, `animation*`,
`transition*` for `motion:reduced` and `motion:replay`; `object-position` for `motion:replay`; `object-fit`, `width`, `height` and their `min-` and `max-` for `motion:stills`) and could reach an element of a demo or an ancestor
of one, that row says `not read: <selector> (sets display)` (`... inside @layer demo` for a rule in an at-rule, `... with nested rules` for a block that holds nested rules, its own declarations and the nested ones
counted) and a row that would pass is a warning. A layer statement (`@layer a, b;`) orders layers the cascade does not weigh: all three rows say `not read: @layer a,b (orders the layers of the cascade)`. A statement
at-rule (`@layer`, `@import`, `@charset`) ends at its semicolon, so the rule after it is read. **A style attribute is weighed**: it beats a rule of the same importance, however specific, and
an `!important` rule beats an inline declaration that is not important (an important inline declaration beats an important rule). `motion:reduced` (under `prefers-reduced-motion: reduce` nothing in the book moves: every rule that starts an
animation, or a transition with a duration above 0, is switched off by a rule inside `@media (prefers-reduced-motion: reduce)` for the same selector, or for `*` with
`!important` (a `*` rule alone is weaker than any class), that sets `animation: none` or `animation-name: none`, or `transition: none`; **the cascade is weighed per longhand,
and a stop counts when it wins on a longhand that stops the thing** (`animation-name: none`; `transition-property: none` or a `transition-duration` of 0), against the declaration that wins in the start's own rule (an
`!important` one before a later plain one) and against every other rule that can select the same element and sets that longhand to a value that does not stop it (importance, then specificity, then the later rule): a start marked
`!important` on that longhand is switched off only by a stop marked `!important`, and not by a `*`, which an `!important` rule for a class outweighs, while `.y{transition-duration:150ms!important;transition-property:color}`
is switched off by a plain `.y{transition:none}` in the reduced-motion block (its property wins, and no transition runs), `.y{transition-property:color!important;transition-duration:150ms!important;transition:color 150ms}`
is not, and `.y{transition-duration:150ms}` with `main .y{transition-property:color}` is not switched off by `.y{transition-property:none}` (the row says `outweighed by 'main .y'`; a rule that starts the same kind of
motion under another selector is checked for itself, and one that only sets a longhand needs a stop under its own selector). A stop inside `@layer`, `@scope`, `@container` or `@supports`, or in a rule that holds nested
rules, is not counted: the gap stays and the row names the stop (`not read: .x (sets animation) inside @layer r`); a start there is weighed as if it applies (an `!important`
start still needs an `!important` stop) and named (`not read: .zz (starts animation) inside @supports (display:grid)`). A rule under `no-preference` needs none; an inline `style` is read like a rule (`!important` needs no
space before it), cannot be switched off and fails; and every motion demo hides its flipbook and stops its animation there, shows its reduced still and hides its controls), `motion:replay` (every
`[data-motion-demo]` has both checkboxes, ids starting `bc-replay-` and `bc-slow-`, each with a `<label for>` holding visible text; neither checkbox removed from the keyboard
(`hidden`, `disabled`, a negative `tabindex`, or it or **any ancestor** `inert`, `hidden`, `display:none` or `visibility:hidden` outside the reduced-motion and print media), and both labels and
the flipbook **shown on a screen** (no ancestor hidden, `display:none`, `visibility:hidden` unless a child says `visible`, or at `opacity:0`); in each of the four states of the boxes the
flipbook has an animation of the right length (`data-length-ms`, and 4 × it with the slow box checked) that **plays once** (an iteration count of 1) with **`step-end`**, **forwards**
(direction `normal`), **running**, held at both ends (fill mode **`both`**) and **at once** (delay 0; an `animation` shorthand that leaves these out sets `normal`, `running`, `none` and 0),
and an `@keyframes` that exists, the four `@keyframes` are the same and **step through the stills of `frames.json`** (a keyframe at the percent of each still, with `object-position: -i × w px 0`,
nothing else in it), and checking either box changes the `animation-name`, so the replay starts again; a `@keyframes` with no name is reported as such; an `object-position` marked `!important` on the flipbook, which the
keyframes cannot override (an animation is below an `!important` declaration), fails with "the replay is frozen"; and the strip's `<source>` is one the lint can read, see "The replay"), `motion:stills` (each demo's flipbook
picture and reduced still are the bytes of the files `frames.json` lists, **and the sha256 it lists**: a picture that is not that file fails with "run brand-creator frames, then
brand-creator book"; its `data-length-ms` and `data-frames` are its `length_ms` and number of stills; the flipbook is one still wide and high (its `width` and `height`, held by `max-width`, `min-width`,
`max-height` and `min-height`; a limit that is not a size in px fails), draws its strip at the density of
`scale` and has `object-fit: none`; a difference fails with "the book shows stills older than motion/frames: run brand-creator book"; a picture of another size is a warning;
**it also fails a generated book that has no replay of a case whose stills the build would make one of** (a gated proof, a motion chapter in the book, motion not off, the case still a page
case, both pictures there: "its stills are in motion/frames/<case>/ and the book has no replay of them: run brand-creator book", the book was built before `frames` ran); for a
hand-written book that is a warning). A book with nothing for a row to measure gets it as info (`no motion demo`), never a pass; `motion:reduced` still reads the
animations and transitions of a book that has no demo. `--self-consistency` adds
`self:durations` (CSS durations and delays are 0 or a `duration.*` or `motion.*` token; a rule whose selectors match elements of one motion demo and of nothing else in the book
may also use that demo's `data-length-ms` and four times it; a selector that matches nothing, or also something outside, or in two demos, keeps the token-only rule), `self:font-size` (no declared size under the minimum label size;
rem and em are taken at 16 px, `var()` cannot be read and fails) and `self:colours` (hex, rgb() or named colours in CSS and SVG paint
attributes must be token colours; other colour functions fail).

**book-pdf.** `render.mjs pdf` prints the book with Chromium (print media, light scheme by default, A4 or Letter, 14 mm margins, background
graphics) after adding the label "RGB, not print-ready" to its first page; `book_pdf.py` (pikepdf) sets Title, Subject, Keywords, XMP
description and fixed dates and ID, and writes `book.pdf`. Chromium's PDF is RGB: the file has no print profile, no bleed and no trim box and
says so (rows `pdf:label-metadata`, `pdf:label-xmp`, `pdf:label-cover`, `pdf:colour`, `pdf:no-output-intent`, `pdf:print-ready` info).
A book that does not lint clean is not exported. Print production (bleed, trim, PDF/X candidate) is a separate step.

**patch** (`patch FILE --old T --new T --count N`): replaces and refuses, writing nothing, unless the text occurs exactly N times. Never edits
`history/`, an earlier round (the hook's rule: only the latest round, and `rounds/r0/` while G1s is empty, are open) or `assets/_checks/`; refuses `book.html` of a generated brand. On a book file it appends
`- <date> edition <n>: patched <file> (<k> replacements)[: note]` to `## Edition log`. **collapse** (`--group G --keep NAME [--apply]`): removes
every `::: variant G x` block of a losing option and every switcher from `book/chapters/*.md`, elements with `data-variant="G:x"` and
`data-switcher="G"` from a hand-authored book, tokens whose `$extensions["brand-creator"].variant` is `G:x`; unwraps the winner; copies every
changed file to `removed-<date>[-n]/<path>` first; records the decision under `## Collapsed`. Without `--apply` it prints the plan.

## Print, press kit and social posts

`brand-creator emit print`, `print-check`, `emit presskit` and `emit social --posts` (scripts `emitters/print.py`, `print_check.py`,
`emitters/presskit.py`, `emitters/social.py`; the shared print code is in `scripts/printlib/printpdf.py`, outside `scripts/lib/` so that a print
change does not make every pack stale). `emit print`, `emit presskit` and `--posts` are Standard and Full tier (exit 2 with the way up in Quick); all
need G3. Print needs `gs` (Ghostscript, called as an external program only) and poppler (`pdfinfo`, `pdftoppm`); pikepdf 10.17.0 is pinned in the
two print scripts (`requires-python >=3.11`).

**Honest print (plan review MUST #12).** Chromium prints the page (`render.mjs pdf --size-mm WxH`, the only Chromium driver); the page is exactly
trim + 2 x bleed with the crop marks drawn in the template, inside the bleed. Ghostscript outlines the text (`-dNoOutputFonts`); pikepdf sets the
MediaBox to trim + 2 x bleed (anchored at the top left, because Chromium rounds the page to its own grid), TrimBox, BleedBox, the metadata, a fixed
date and file ID and no object streams. What the file says about itself depends on `--icc` only:

| | without `--icc` | with `--icc FILE` |
|---|---|---|
| label (Subject, Keywords, XMP description) | `RGB proof, not print-ready` | `PDF/X-4 candidate (preflight with your printer)` |
| file name | `<piece>.rgb-proof.pdf` | `<piece>.pdfx4-candidate.pdf` |
| colour | RGB, no output intent | converted to CMYK through the profile, PDF/X-4 output intent |
| Ghostscript | PDF 1.4, no PDF/X | `-dPDFX=4`, a `PDFX_def.ps` written by the emitter |

`FILE` is the printer's own CMYK output profile (the emitter refuses any other colour space, exit 2); brand-creator bundles no profile. Nothing in the
plugin can check PDF/X conformance (that needs a preflight tool, UNVERIFIED here), so no file says it conforms, is compliant or is print-ready;
spot colours are not produced (a spot is recorded as name plus Lab target in LAUNCH, never "hex equals spot"). Switching `--icc` on or off retires the
other variant (moved to `removed-<date>/`), so a piece exists in one form.

**The print_region table** (`scripts/emitters/print-regions.json`, rows `print-EU`, `print-US`, `print-JP`, read through `specs.py` so they are stamped,
listed by `specs-due` and warned about like any spec row; all status U): business card (85 x 55 mm; 3.5 x 2 in; 91 x 55 mm), paper (A4; Letter; A4),
envelope (DL; #10; DL) and a default bleed (3 mm; 0.125 in; 3 mm) that is stated as printer-specific in the report: ask the printer, pass `--bleed`.
The region is `--region`, else the one region the brief's "Region and language" line names by region or country alias (exit 2 for none or several).
`--card-mm` and `--envelope-mm` replace a size.

**Pieces and templates.** `templates/print/` (`business-card-front`, `business-card-back`, `letterhead`, `envelope`, `email-signature`; `--template-dir`
points at your copy): filled from the built tokens, the outlined logo set (`assets/logo/lockup.svg`, else `wordmark.svg`, else the mark; the dark
partner on dark grounds) and FACTS.md labels `contact name`, `contact role`, `contact email`, `contact phone`, `postal address`, `website` (or
`homepage`) and rows starting `legal`. A missing label is left out and warned, never invented; a card back with none of them exits 1. `--tagline` must be
a FACTS.md value. Text is set in a system font unless `--font-file` names a brand font in the project (warned). The e-mail signature is a table with
inline styles, no style block, absolute image URLs (`--image-base-url`, else a placeholder host and a warning) and its own ground and text colour
(WCAG 2.2 text contrast, from the `email-signature` spec row), with opaque logo PNGs, so a client that darkens a message cannot change the pair.

**The sidecar.** `<piece>.print.json` holds what Chromium measured in the render that made the PDF: the position and size (mm from the trim corner) of
every text run, logo, image, line and bleed element, font and line sizes in pt, the reversed state, and every transparency construct. The text is
outlined in the file, so these cannot be read from it; the sidecar is bound to the PDF by sha256. It also records region, bleed and its source, the label,
the `--icc` profile's hash, the template hash and the font. The manifest rows of the PDFs carry `qa: ["print"]`, so `check` requires a current passing
`print-check` report whenever print PDFs are in the manifest, and not otherwise.

**print-check** reads the files and checks, per piece (rows `<piece>:<rule>`): `bind` (sidecar belongs to the PDF), `pages` (one), `page-size` (page =
TrimBox + 2 x bleed), `trim-box` (the region's trim), `bleed-box` (BleedBox is the page), `bleed-width` (present on all four sides, at least the
stated minimum), `bleed:geometry` (an element marked `data-print-bleed` that reaches a trim edge runs to the page edge), `bleed:ring` (a 200 dpi raster:
artwork at the trim carries on into the bleed), `safe-zone` (nothing within the safe distance of the trim, bleed art and crop marks excepted),
`line-weight`, `text-size`, `reversed-text`, `logo-size` (elements marked `data-print-id="logo"`), `transparency` (opacity, soft mask, blend mode, shadow,
masked image: from the PDF and from the page), `fonts` (none: outlined), `colour`, `label:claims` (PDF/X named without an output intent, or the words
conform, compliant, certified, verified, guaranteed or print-ready outside "not print-ready", fail), `label:icc` (the label, file name, sidecar and output
intent agree; `--icc FILE` also requires the embedded profile to be that file) and `dates`. A row that cannot be established (no sidecar) is skipped,
never a pass. Boxes are read with poppler's `pdfinfo -box`, independent of the pikepdf that wrote them.

Thresholds, `qa/print.json` (`{"schema": 1, <key>: <number>}`; an unknown key or a number at or below 0 exits 2) over stated defaults that are
proposals: `safe_zone_mm` 3, `min_line_pt` 0.25, `min_line_reversed_pt` 0.5, `min_reversed_text_pt` 7, `min_text_pt` 5, `min_logo_mm` 5 (the logo's
height; the brand's own minimum belongs here), `min_bleed_mm` (default: the region's bleed), `box_tolerance_mm` 0.05, `ring_tolerance` 6. Chromium never
draws a border thinner than one CSS pixel (0.75 pt): a border measures what it is; a `height` rule can be thinner. Passing the check does not make a file
print-ready: preflight with the printer's tool and get the printer's proof (an owner step, in LAUNCH).

**Press kit.** `emit presskit` writes `assets/presskit/<slug>-press-kit.zip`: `logos/` (every `.svg` and `.png` in `assets/logo/`), `tokens/`
(`tokens.css`, `tokens.json`), `book/book.pdf` (the RGB proof; `--book` names another file, `--no-book` leaves it out and says so; without either the run
exits 1), `extra/` (`--include`), and a `README.txt` of sha256 and size per file that states what `book.pdf` is and no terms of use. The zip is built
with `determinism.fixed_zip` (sorted entries, mtime 1980-01-01), written only when its bytes change, and every file read is a report input.

**Social posts.** `emit social --posts --post-fact LABEL ...` (at least one; each a FACTS.md label, else exit 1) adds `assets/social/posts/`: a 4:5
carousel (cover, one slide per fact, closing slide), an educational 4:5 post of at most four numbered points and a 1:1 post, from
`templates/social/` (`--post-template-dir`), rendered by `render.mjs card` at the `social-post-4x5` and `social-post-1x1` rows (status U). Every word on a
post is a FACTS.md value or label. When `brief/BRIEF.md` has a `Regulated profession:` line that is not none, the post pages carry
`data-regulated-checklist` and `data-regulated-profession`, `posts/PRE-PUBLICATION.md` lists the checklist (generic guardrails from
`references/regulated-industries.md`) for the owner to tick before anything is posted, and the report warns; an unanswered line (the template's
placeholder) warns that the question is open. A run without `--posts` leaves earlier posts alone; a run with fewer facts retires the slides that go.

## Adoption, cascade, adapters, applied skill and launch

Commands `adoption` (`scripts/adoption.py`), `check --cascade`, `adapters` (`scripts/adapters.py`), `applied-skill` (`scripts/applied_skill.py`) and
`launch-todo` (`scripts/launch.py`); the shared code is in `scripts/adaptlib/` (`adoptdata.py` the adoption data and its rendering, `cascade.py`,
`adapt.py` the builders of BRAND.md, DESIGN.md and the applied skill, `gates.py` what `check` gates), outside `scripts/lib/` so that a change there does
not make every pack stale. The adapters and the applied skill need G5 recorded and are written only with their flag (`--brand-md`, `--design-md`,
`--yes`); the survey and `launch-todo` need no gate because they change nothing outside the project.

### adoption

`adoption survey --repo DIR[=LABEL]... [--old-name T]... [--old-colour #HEX]... [--old-colours-file F] [--keep GLOB::REASON]... [--replace-terms]`
reads each repository with ripgrep (`rg --hidden`, `.gitignore` honoured, `.git` left out, symlinks not followed; the brand project itself is left out when it
lives inside the repository). It never writes in a repository, and proves it: per repository the report's `read-only:<label>` row compares the list of
files with sizes and modification times before and after. Slots (the category of a row):

| category | what is a match |
|---|---|
| `name` | a line holding an old name (as given, hyphenated, with underscores, joined; any case; at least 3 characters) |
| `colour` | an old colour as `#rrggbb`, `0xrrggbb`, `#rgb` (when the colour has a shorthand) or `rgb(r, g, b)`; a longer hex run is not a match; colours as 0-1 floats are not matched |
| `path` | an icon, logo, favicon, wordmark, lockup, launcher or splash image file, or any file under a `.appiconset`, `.iconset`, `.icon`, `.imageset`, `.solidimagestack` or `.colorset` folder, grouped by folder |
| `meta` | the slot lines of package.json, Cargo.toml, pyproject.toml, pubspec.yaml, plists, Tauri config, AppStream metainfo, web manifests, AndroidManifest.xml, .desktop and .nuspec files (name, description, icon, theme and background colour, identifier, author, homepage) |
| `badge` | the badge and header-image lines of README files |
| `change` | a row written by hand with `adoption add` (a change no search finds); a survey never touches it |

Every match is a row or is kept: lock files, change history, licence text, minified output and `dist`, `build`, `target`, `vendor`, `Pods` and similar folders
(and anything `--keep GLOB::REASON` names) go on the **Kept, not counted** list with the reason; the report's `accounting` row fails when the total is not rows plus kept
*or* when a second ripgrep run (per-file counts for names, plain text lines for colours; none of the survey's own code) counts a different number of name or colour lines than the survey
found. Meta, badge and icon-path matches come from the file list, so for them the row checks the bookkeeping only; the row's detail says so.
`adoption.json` holds `rows` (`n, category, repo, file, lines, find, change`), `progress` (`{"<n>": "doing"|"done"}`; to do is the absence of an entry), `pins`
(`{"<n>": "repo|category|file"}`), `nrows`, `seen` (the live lines and hits of each surveyed row at the last survey), `kept`, `identifiers` (package names, bundle ids,
app ids read from metadata), `terms`, `repos` (label and path relative to the project, never an absolute path) and `accounting`. **Rows are append-only**: they are
numbered by position, a survey adds only at the end (a row is keyed by `repo|category|file`) and never edits a row, and `verify` fails a row inserted,
removed, moved or edited, a progress entry for a row that does not exist and an unknown state. Line numbers are the survey's and **may drift**: each row
carries `find`, a content excerpt, and `ADOPTION.md` says so; the live lines are in `seen`. `adoption status --set ROWS=STATE` (ROWS as `N`, `N-M`, `N,M`)
changes progress; `doing` and `done` need G6, to do (the reversal) does not. `ADOPTION.md` is rendered from the data and every sentence about its state is
built from the counts (`adoptdata.sentence`). Its fixed text (the section order and the "How this list is applied" rules) is the frame
`templates/ADOPTION.md` (placeholders `{{name}}`, `{{status}}`, `{{repos}}`, `{{about}}`, `{{groups}}`, `{{drift}}`, `{{rows}}`, `{{kept}}`, filled in one pass;
a missing frame or placeholder exits 2). `check` (`adoption:data`) fails an ADOPTION.md that is not what the data renders, and warns about a row marked done
that still matches at the last survey (`adoption:drift`).

### check --cascade

`check --cascade "<old value or phrase>"` (repeatable; `--ignore-case`; `--also PATH` repeatable) searches every current text file of the project, PDFs as text
(`pdftotext`; a project PDF with no `pdftotext` is "not verified"), and the documents named by `tools/cascade.json` (`{"schema": 1, "also": [paths relative to the
project]}`, an unknown key is exit 2), by `--also` and by the `parent_docs` list of the family-check block of FAMILY.md (relative to FAMILY.md); outside documents
are only read, and one that does not exist fails. A current file holding the value fails with `file:line` for each hit. Skipped on purpose and said so in the
`cascade:scope` row: `history/`, `decisions/`, `BRAND-STATE.md`, `DECISIONS.md`, earlier rounds, `removed-*/`, `assets/_checks/`, `assets/manifest.json`, binary files
and print PDFs (their text is outlines). `_build/` folders are searched: their HTML (OG card, social posts, App Store frames, print pieces) is the only text
layer of an image made from a value given on the command line, which `emit` does not check against FACTS. A line that carries `<!-- target-repo -->` (an ADOPTION.md row, the rename list of LAUNCH.md) and the `find`, `terms`,
`identifiers` and `kept` fields of adoption.json record what a product repository holds: they are counted apart and make a warning, never a failure; any other line
of those files, including the text of an adoption row's `change`, is searched like the rest.

### adapters

`adapters --brand-md --design-md [--primary ROLE] [--bm-type T] [--bm-architecture A] [--replace]` writes `BRAND.md` and `DESIGN.md` at the project root from the built
tokens (`assets/tokens/tokens.json`), BRAND-STATE.md and FACTS.md. BRAND.md: frontmatter `type` and `architecture` (standalone: master, independent; family-member:
master, endorsed; product-in-family: product, endorsed; these pairings are brand-creator's reading, not something the format defines, so they can be overridden),
then Strategy (the facts, the canonical direction), Voice (only `voice` and `tone` facts and the FORBIDDEN list; "no voice facts are recorded" otherwise), Visual
(colour roles in light and dark, type families, the mark files, the G4 rules, motion) and Governance (naming and renames, claims and verbatim legal facts,
the accessibility commitments with the computed ratios, approval). Contact and postal-address facts are left out. DESIGN.md: frontmatter `version: alpha`, `name`,
`colors` (the light roles, `-dark` variants, `primary` when `--primary` names a role), `typography` (families only), `spacing`, `components` (one entry per
`ui-text` pair, light and dark, as `{colors.x}` references), then the sections in the spec's order that have content. A role whose colour is see-through
(alpha under 1 in `tokens.json`) is written `#rrggbbaa`, lower case, as `tokens.css` writes it, wherever a role is listed (BRAND.md, DESIGN.md `colors`, the applied
skill); an opaque role stays `#rrggbb`. The pinned DESIGN.md format lists `#RRGGBBAA` as a colour, and its lint passes it. The report `adapters` records the sha256 of
each output and `adapter_state_sha` (a hash of what the adapters read from BRAND-STATE.md and FACTS.md). DESIGN.md is linted with `@google/design.md` (the version
pinned in `scripts/package.json`, run with Node from `<data>/node_modules`; a different installed version is not trusted): an error or a `contrast-ratio` finding
is `fail`, other warnings are `warn`, and a missing package is `skipped`, so the report is not-verified and the exit code 3. `check` gates the report, fails a file
that is not the bytes the report recorded (a hand edit) and treats a changed source as not verified. A hand-edited file is replaced only with `--replace`, which
moves it to `removed-<date>[-n]/`. When `tools/inputs.json` exists, the adapters add `BRAND.md` and `DESIGN.md` to its globs (the pack then reads as stale until
`staleness --write`), and `staleness --write` includes both whenever they exist.

Motion is the same text in BRAND.md (`### Motion`), DESIGN.md (`## Motion`, prose between Components and Do's and Don'ts: the pinned format keeps a section it does
not name, so no frontmatter key is invented) and the applied skill (`## Motion`): every duration token (by its type, the paths under `tokens.json`
`motion.durations_ms`) and any other token of the `duration` and `motion` groups (`motion.distance`), each as `tokens.css` writes it and in name order (a
`tokens.json` built before the `motion` entry existed lists the two groups only), then the curve tokens (from `motion.curves`: name and `cubic-bezier(x1, y1, x2, y2)`, in name order; a curve named `motion.*` is listed once, as a
curve), then, when `motion/motion.json` exists, `Signature move: <name>. <description>` and `Shown in:` with one bullet per place, or `Nothing moves: <reason>`
for `"off"`, and `Motion rules:` with one bullet per rule. The parts and the timeline stay in the spec. With no duration, no curve and no `motion.json` there is no motion section in
any of the three and the files are as they were; a `motion.json` that is not valid stops the run (exit 2) before anything is written. The spec is an input of
the `adapters` and `applied-skill` reports, and the state hash covers it: a changed, removed or newly added `motion/motion.json` makes both not verified.

### applied-skill

`applied-skill --yes [--plan] [--replace]` writes `.claude/skills/<slug>-brand/SKILL.md` into the project from `templates/applied-skill/SKILL.md`: colours (light and
dark) and the contrast pairs with their ratios, type families, the mark files (relative to the skill), the small-size rule (from `qa/rules.json`, or the plugin's
proposal, said so), motion (the section above, through the template's `{{motion}}`: a whole section or nothing, so a brand without motion gets the file it always
had), what is never done, the G4 rules, the facts that may be claimed (contact facts left out). It needs G5 and `--yes` (without it: the plan on stdout, a
message on stderr, exit 2; `--plan` exits 0). The name is `<slug>-brand` (lower case, hyphens, at most 64 characters, no `claude` or `anthropic`). Gated by `check` like
the adapters (`applied-skill:file`, `applied-skill:state`).

### launch-todo

`launch-todo [--name CANDIDATE]` writes `LAUNCH.md` from `templates/LAUNCH.md` and reads local files only: the names report (`assets/_checks/names.json`: the
trademark links of the candidate, domain and registry states with the date they were checked), the verdict memo's "Launch TODO" seed, `adoption.json` (identifiers),
FACTS.md (`contact email`), BRAND-STATE.md (Still open), the manifest and tokens (the print hand-off, only when print files exist). Sections in this order:
Trademark first, Domains, Handles and registries, E-mail, Deploy, Repositories, packages and app ids, Print hand-off, Decisions for you. Domain and registry states are
REGISTERED, NOT-FOUND or UNKNOWN with "Checked <date>, recheck before buying"; the file never says available, free or clear. Spot colours are a name plus a Lab target
the printer's swatch gives, never "hex equals spot". With several screened candidates `--name` is required (or the project slug must be one of them). Each box carries an
id (`<!-- id:... -->`) and the ticks of an earlier file are kept by id; a ticked box that no longer exists is reported (`launch:ticks`). The module imports no network or
process library: nothing outward is executed, and a test compares the project tree before and after.

## Tier B emitters: Android, Chrome extension, MSIX

`brand-creator emit android`, `emit chrome-ext` and `emit msix` (scripts `emitters/android.py`, `emitters/chrome_ext.py`, `emitters/msix.py`; the shared code
and the gates `check` runs are in `emitters/tierb.py`). They follow the platform-emitter rules above (gate G3, sizes only from `platform-specs.json`, bands
through `Emit.drawing()`, rows through `put_slot()`/`put()`, retirement of slots no longer emitted, deterministic bytes, reports `emit-android`,
`emit-chrome-ext`, `emit-msix`) and add two rules:

- **Full tier only.** In any other tier the command exits 2 and names the way up (`brand-creator state --set tier=full`); nothing is written.
- **Unverified rows are labelled.** A file that serves a spec row of status U carries the label `UNVERIFIED, recheck` (and the row ids) at the start of its manifest
  `note` and in the label of its `file:` result in the report; a file built only from V or R rows has no label. `check` re-reads the manifest: a Tier B file whose
  `specs` include a row stamped U and whose note lacks the label fails (`tierb:labels`). The spec warnings of `finish()` and the `specs:<row>` warnings of `check`
  remain.

| Target | Output (under `assets/<target>/`) | Gates |
|---|---|---|
| `android` | `res/mipmap-anydpi-v26/ic_launcher.xml` and `ic_launcher_round.xml` (`<adaptive-icon>` with `<background>`, `<foreground>`, `<monochrome>`), `res/values/ic_launcher_background.xml` (the light `color.bg`), `res/mipmap-<mdpi..xxxhdpi>/ic_launcher_foreground.png`, `ic_launcher_monochrome.png` (108 dp), `ic_launcher.png`, `ic_launcher_round.png` (48 dp legacy square and circle), `play/ic_launcher-playstore.png` (512, 32-bit, opaque, sRGB chunk), `play/feature-graphic.png` (1024 x 500, 24-bit, no alpha, from `templates/card.html` or `--template`) | safe zone: the ink of the foreground and monochrome layers at every density stays inside the circle of the adaptive row's `safe_dp` (66 dp; the stricter of the circle and the square), plus one pixel of anti-aliasing, else nothing is written and the emit exits 1; the Play icon keeps the same share of the square; PNG sizes read back; colour types and opacity of the Play icon and the feature graphic |
| `chrome-ext` | `icons/icon-<16,32,48,128>.png`, `store/store-icon-128.png` (the same bytes as the 128 icon), `store/promo-small-440x280.png`, `store/promo-marquee-1400x560.png` (opaque), `manifest.icons.json` | the 128 icon follows the Web Store rule of the row (96 px of artwork in 128, transparent padding), read back from the pixels; PNG only (a row that allows another format exits 1); sizes read back |
| `msix` | `Assets/<Name>.scale-<100,200,400>.png` for `Square44x44Logo`, `Square150x150Logo`, `Wide310x150Logo`, `Square310x310Logo`, `Square71x71Logo`, `StoreLogo`; `Assets/Square44x44Logo.targetsize-<S>.png` with `_altform-unplated` (dark theme) and `_altform-lightunplated` (light theme) for each `S` of the `msix-applist` row; `AppxManifest.visual-elements.xml` | every target size has the plain file and both altforms, unplated files have a transparent corner, every PNG is read back at its size, the snippet parses as XML and names every image |

**The Android size of the mark.** Without `--content-dp` the mark's box is the largest size in the logo range (`logo_min_dp` to `logo_max_dp`, 48 to 66) whose ink
still fits the safe circle, measured on the xxxhdpi raster and scaled (a mark whose ink does not fit even at the minimum fails the emit); with `--content-dp` the
size is the owner's and the gate holds it. The monochrome layer is a black silhouette of the drawing for its size, or `--svg-mono`; artwork that cannot be reduced
(gradients, masks, filters) exits 1 and asks for an authored silhouette, because an adaptive icon without a monochrome layer is derived by the system (from Android 16
QPR2) and not by us. The background layer is a colour resource, not a bitmap. Density sizes are `dp x dpi / 160` from the `android-densities` row (status U, so
every density file is labelled).

**What `check` gates from these** (`tierb:` rows, only when a Tier B file is in the manifest): `tierb:labels` (the U label above), `tierb:android` (the adaptive XML
parses, names a background, a foreground and a monochrome layer, and each resolves to a colour resource or to a PNG at every density of the row; a monochrome layer
with no ink fails) and `tierb:msix` (every `targetsizes` entry has the plain file and every altform of the row; an unplated file has a transparent corner).
`finish.sh.tpl` adds the three targets when `state --get tier` is `full`. The Chrome extension's screenshots (real product), the Windows Store listing art and the
Google Play screenshots are not written.

## Tier B: watchOS and tvOS, profiles, and the finish chain

**watchOS and tvOS (in `emit apple`).** Both are written only for a target the repository lists (`- watchOS: 10.0` / `- tvOS: 17.0` under "Deployment targets" in `INVENTORY.md`,
or `--target watchOS=10.0`); with no such line the report says so (`watchos`, `tvos` info rows) and no file is written. Like every Apple output they need macOS with Xcode
(exit 3 elsewhere, no fallback).

| Pack | Output (under `assets/apple/`) | Gates |
|---|---|---|
| watchOS | `watchos/Assets.xcassets/<AppIcon>.appiconset/<AppIcon>-watchOS-<px>.png` (one opaque square at `appiconset_px` of its own U row `apple-watchos-appiconset`, not `apple-app-icon.watchos_px`, RGB, no alpha; the system applies the circular mask) with its `Contents.json` (`platform: watchos`, `idiom: universal`), the catalogue root, `compiled/watchos-appiconset.renditions.json` | the mark's ink stays inside `watchos_safe_circle` of the circle's radius (`check:watchOS circle`, run on the pixels BEFORE anything is written: a failure exits 1 and writes no file of any pack); actool compiles the catalogue for `watchos` as a hard gate (`actool:watchos-appiconset`: an icon image at the layout size) |
| tvOS | `tvos/Assets.xcassets/<AppIcon>TV.brandassets/Small.imagestack/{Back,Front}.imagestacklayer/Content.imageset/{back,front}.png` (800 x 480 at 2x, i.e. 400 x 240 pt; back opaque, front the mark with alpha) with every `Contents.json`, `compiled/tvos.renditions.json` | the mark stays inside the central `tvos_safe_share` of the layer in both directions (`check:tvOS safe area`, before anything is written); the stack has `layers_min` to `layers_max` layers (2 to 5); actool compiles it for `appletvos --target-device tv` (`actool:tvos`: an image stack and the layer images at the layer size) |

The mark's box is automatic by default (the largest whole percent, at most `--content-fraction`, that keeps the ink inside the margin: ink scales linearly about the centre,
so one measurement at a box of 1.0 is enough) and `--watchos-content-fraction` / `--tvos-content-fraction` set it by hand and are held to the same gate. ictool exports a watch
icon only at the size it is given (`--width`/`--height`, passed with `--previews`); it has no tvOS platform, so there is no tvOS preview. The App Store icon (a larger tvOS stack) and
the Top Shelf images are not written (`tvos:other` info row): no verified size exists for them.

**actool reports some errors under another key.** A tvOS stack layer that does not fill the stack makes actool exit 0, write an `Assets.car` and put the error under
`com.apple.actool.document.errors` (with `message`, not `description`). The emitter's compile gate reads both `com.apple.actool.errors` and the document errors (and warnings), for
every platform, so such a catalogue is exit 1 with actool's own words.

**Labels.** The two margins (`apple-watch-tv-safe`) are status U, so every watchOS and tvOS file carries `UNVERIFIED, recheck (apple-watch-tv-safe): ` at the start of its
manifest `note` and the same words in its `file:` report label, and `labelled: true` in its manifest row; `check` holds the label for those files (`tierb:labels`). The Tier A Apple files keep
their notes.

**watchOS appiconset size.** The size of the pre-26 single-size appiconset is the U row `apple-watchos-appiconset` (`appiconset_px`, 1024), not `apple-app-icon.watchos_px` (1088), which
is the Icon Composer layout canvas and stays the ictool export size for `--previews`. No page that states the size Xcode or App Store Connect accept for a watchOS appiconset was read, so every file of the pack
carries `UNVERIFIED, recheck (apple-watch-tv-safe, apple-watchos-appiconset): ` and a person must check the size in Xcode before the pack is relied on.

**`emit profiles`** (`emitters/profiles.py`, template `templates/profile/banner.html`, report `emit-profiles`; every tier: the Quick tier writes the two avatars only and an info row says the banners are Standard; gate G3). It writes under
`assets/profiles/`: `avatar-<px>.png` for each size of the `profile-avatar` row (400 and 800; opaque RGB, the mark centred) and one image per platform at its row's size
(`linkedin-banner`, `x-header`, `youtube-banner`, `facebook-cover`, `instagram-feed`, `instagram-story`, named `<name>-<w>x<h>.png`; the brand's drawn lettering, plus one FACTS.md line with `--tagline`,
laid out inside the row's `safe` rectangle, 24-bit PNG). The lettering is `--logo-svg`, else `assets/logo/lockup.svg` (it stands alone), else `assets/logo/wordmark.svg`
(set next to the mark), shown as an image (`{{lettering}}`, `{{layout}}` = `lockup`, `wordmark` or `type`). Whether a file is a lockup or a wordmark comes from
`--lettering`, else from its file name (a name that says neither or both exits 2). The name is live text in the system font only with `--name` (an info row;
with `--logo-svg` or `--lettering` it exits 2), without a lockup or wordmark (a `note:lettering` warning), or with a template that has no `{{lettering}}` (a
warning). A template with no `{{lettering}}` and no `{{name}}` either (its comments and `<title>` left out) draws its own name, outlined paths for example: a
`note:lettering` info row says so, with or without a lockup or wordmark file, and nothing is typed. The Quick tier reads no lettering: it writes no banners. `emit social`, `emit android` (the feature graphic) and `emit chrome-ext` (the promo tiles)
follow the same rule for their cards (`templates/card.html`), and the dark README header takes the lettering's `<name>-dark.svg` (a warning without one).
Pixel art (an SVG whose root says `shape-rendering="crispEdges"`) is set at a whole-number scale wherever the plugin picks the size, so every
pixel stays square: the mark (card.html's `{{mark_size}}`, the banner's `{{mark_px}}`), the lettering on cards and banners, and the
side-by-side image; at a fixed icon size the band's drawing decides. The accent line under the name has square ends too: the cards
(`card.html`), the banners (`banner.html`) and the side-by-side image (`lineup.html`) take `{{rule_radius}}` for its `border-radius`, which
is 0 when everything drawn on the card is pixel art (the mark unless a lockup stands alone, the lettering unless the name is typed; on the
side-by-side image every mark) and the template's own round ends otherwise (`1vh` on a card, the line's height on a banner and the image).
A template of a project that has no `{{rule_radius}}` keeps its own `border-radius`. With several marks, each follows the rules of Several marks. Every size and safe area is read from `platform-specs.json`. The rows are all status U, so every file is labelled like the other Tier B files.

- **The gate comes before the files.** The avatar's ink must lie inside the `safe_circle` share of the circle (default box: the largest, up to 0.7 of the canvas, that fits; `--content-fraction` sets it
  and is held to the same gate); the ink of a banner (pixels unlike the ground, read from the rendered PNG) must lie inside its safe rectangle, so a name that is too long or a template that draws outside
  fails. Any failure exits 1 and no image is shipped.
- **Proof images.** `_proof/<name>.png` is the same image with the safe areas drawn (the platform's circle crop and the safe circle for an avatar; the safe rectangle dashed and the areas outside shaded
  for a banner). They are written even when a gate fails, so the person can see why; they are never shipped, not in the manifest, and a name starting with `_` is outside the idempotence tree.
- `check` runs `tierb:profiles`: every avatar size and banner of the rows is written, and the ink of each file, read back from its pixels, is still inside the safe area recorded in the manifest row
  (`safe_radius_px`, `safe`), so a file edited afterwards is caught.

**The finish chain.** `templates/finish.sh.tpl` runs the book, print, press-kit and post steps and the Tier B packs, each gated by the tier like the CLI: `emit profiles` (every tier; avatar only in Quick); `emit print` (Standard and Full, and only
when `PRINT_REGION` is set: print is opt-in with the owner; `PRINT_ICC`, `PRINT_BLEED`, `IMAGE_BASE_URL` are optional) followed by `print-check`; `emit social` gets `--posts` and a `--post-fact` per
label of `POST_FACTS` (semicolon separated) when that is set; `book` and `book-pdf` when `book/chapters/` exists (the chain never writes or fills chapters; without the folder the log says `book: skipped`), and before them
a `motion` step in the Standard and Full tier (Quick decides motion at G4 and has none), which never skips in silence: it prints the decision, and with `motion/motion.json` on and a `motion/proof.json` it runs `shot --motion motion/proof.json`
(exit 1 writes a failing report: the chain says `finish.sh: the motion proof failed (see above); ...` and goes on, and `check` fails the report; exit 3 after the step wrote the report of the proof (for example a move driven by `requestAnimationFrame`) is a
report that says not-verified: the chain says `finish.sh: the motion proof is not verified (see above); ...` and goes on, and `check` says why (the step is judged by whether `shot --motion` printed the report it wrote, `report: <path>`: the file is named after the proof as the disk spells its path, which is not always as the chain typed it, so the chain reads the name from that line); any other exit, and an exit 3 that wrote none (Chromium cannot start),
leave nothing for `check` to gate, so the chain says `finish.sh: shot --motion stopped with exit N ...` and stops with that exit code); on without a `motion/proof.json` it says which file is missing and goes on (`check` fails `motion:proof` once G4 is recorded); off it prints `nothing moves: <reason>`; with no `motion/motion.json` it prints
`motion is not decided: ...` and goes on (`check` fails `motion:decided` once G4 is recorded); a `motion/motion.json` that is not valid in itself stops the chain at once with exit 2 (one that is valid in itself but names a token that is not built does not, because `motion` reads the answer from the
document alone: `book` stops the chain on that token, or, with no book, `check` fails `motion:spec`). Then
`frames motion/proof.json` with `FRAMES_ARGS` (a block-2 option, default `--count 25`; fewer stills for a mark too wide for 25) in the Standard and Full tier (the Quick book has no Motion chapter) when `motion/motion.json` says `on` and `motion/proof.json` has a page case, so that the Motion chapter
replays stills of the page as it is now (it writes only `motion/frames/` and its report; a rerun with nothing changed writes nothing; whenever it takes none, a line says why: `finish.sh: no stills taken: ...`). A page `frames` cannot step through (motion driven by
`requestAnimationFrame`, a scroll timeline) makes it exit 1 with a failing report: the chain says so in one line on stderr (`finish.sh: frames could not take the stills (see above); the book keeps the stills of
the last run that worked, if any, and check says why`) and goes on to `book`, and `check` fails the failing `frames` report (see "Frames"). Any other non-zero exit of `frames` (2: a strip wider than Chromium writes, a
case folder that holds another proof's stills; 3: it could not run) leaves no failing report for `check` to gate, so the chain says so (`finish.sh: frames stopped with exit N ...`) and stops with that exit code;
`emit presskit` (Standard and Full; `--no-book` when there was no book). `book`, `book-pdf` and the press kit come after the gates and `verify-idempotent`, because the book reads the downscale and
idempotence reports (a book built before them is stale once they are rewritten, and `check` says "not verified") and the kit holds `book.pdf`; the book's file list leaves the kit out. A value set for a step the tier does
not allow (`PRINT_REGION` or `POST_FACTS` in Quick) stops the chain with exit 2 before any step runs. Every emit step except the press kit is in the idempotence run.

## Agents and workflows

- `agents/*.md`: plugin agents, named `brand-creator:<file name>`. Frontmatter: `name`, `description` (starts with "Only for
  brand-creator workflows or an approved fleet; do not auto-delegate." and names the tier), `model` (`opus` or `sonnet`),
  `tools` (an allowlist, never `Agent`), `maxTurns`, optionally `omitClaudeMd`. Never `permissionMode`, `hooks`, `mcpServers`,
  `initialPrompt` (ignored for plugin agents) or `isolation`. The body carries the RULES line verbatim and takes every path from
  the prompt (no plugin variables).
- `workflows/*.js`: the first statement is `export const meta = {...}`, a pure literal whose `name` equals the file name and whose
  `phases` match the `phase()` titles used. The body uses only `agent()`, `parallel()`, `pipeline()`, `phase()`, `log()` and
  `args`; no clock, randomness, `import()` or `require()`. Each script checks its arguments before the first agent (exit by
  throwing `<workflow>: <message>`), refuses a run that plans more agents than `args.approved_agents`, caps every agent above
  `args.ceiling` with a per-call model, filters fan-out results with `.filter(Boolean)` and guards every awaited `null`.
  `const RULES` holds the RULES line verbatim and `const AGENT_TIER` the tiers of the agent files. `directions` refuses to start without
  `args.g1s` (the G1s record: nothing is drawn before the style pick), as `adopt` refuses without `args.g6`.
- `brand-creator fleet-plan <workflow> --args <json | @file> [--session-model <m>] [--json]` (`scripts/fleet_plan.mjs`, no
  dependencies, no project needed): runs the script in a `node:vm` sandbox with stub hooks (the stub agent answers with the
  smallest value its schema allows; `Date.now()`, `Math.random()` and `new Date()` throw as in the runtime) and prints every
  agent it would start, the model each will run on (per-call model > agent file > `CLAUDE_CODE_SUBAGENT_MODEL` > the session
  model; `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` makes it `CLAUDE_CODE_SUBAGENT_MODEL` or the session model), the size guideline
  (small under 5, medium under 10, large under 50) and the sum of `maxTurns`. Exit 0 = a valid plan, 1 = the script refuses
  the arguments, an agent would run above the session model or an agent type is unknown, 2 = usage. `fleet-plan --check`
  runs the static checks over every workflow and agent file (exit 1 on any problem). It writes no report: it is a plan, not a
  gate over project artefacts.

## Agents and workflows: snapshots, fix runs and the verifier

- Designer snapshot: `snapshot take` and `snapshot verify` both get `--ignore '*rounds/<round>/*' --ignore '*assets/_checks/*'`; the designer's
  answer lists its `screenshots` (required, at least one), the judge reads those and never the shared `shot.json`.
- `adopt`: the prompt names `MODE: apply|fix`; a fix run says the branch exists and snapshots as `adopt-fix-<label>`; the implementer may start on a
  dirty tree only for a fix run or a resume of its own step.
- Agent tools are the only enforced privacy boundary: `brand-namer` (Read, Grep, Glob, Bash) runs the naming hunters, and the screener while
  `lookups_ok` is false. Bash stays an instruction, not a tool limit. The refuting research verifier is `brand-researcher`; `brand-reviewer` has no web
  tools.

## Behaviour evals

`evals/<case>/` follows the `claude plugin eval` format (docs: "Test plugins with evals"): `prompt.md` (frontmatter `name`, `description`,
`tags`, `max_turns`, `timeout_seconds`, `runs`, `allowed_tools`, `expected_outcome`; the body is the prompt), `case.yaml` (only
`schema_version: "1.1"`, `name` and `context.scaffold_script`) and `graders/<name>.md`. Cases that need an empty workspace have no
`case.yaml`. They are opt-in, billed and never run by `tests/run-all.sh` or the smoke test; the README ("Running the evals") has the
commands. Conventions:

- **Fixtures.** `evals/_shared/fixture.sh` holds the builders (`fx_r1_shown`, `fx_before_r1`, `fx_before_style`, `fx_refine`, `fx_judge`,
  `fx_cascade`, `fx_adoption`, `fx_commit`, `fx_brief_family`, `fx_brief_solo`); each `scaffold.sh` sources it by its own path and calls one. They
  copy the synthetic Acme worked brand (without its README, which narrates round 1), write `BRAND-STATE.md` from variables (G1s defaults to a
  recorded skip, so the cases that test the first board of directions are not stopped by the style gate; `ST_G1S=""` leaves it empty, which is
  what `fx_before_style` does) and use no network. A run's workspace is the project root, so step 0 finds `BRAND-STATE.md` at once.
- **Harness note.** The two cases that must prove "nothing was written" (adoption target, git state) end their prompt with a note asking
  the run to execute `bash .eval-verify/verify.sh > verify-result.txt`; a regex grader reads the file (`cmp` of every file against
  the pristine copy; commit, stash, worktree and branch counts). The tool-call graders are the first line, the file is the proof.
- **Graders.** `tool_used` matches `input_match` against the call's JSON-encoded input, so a quote inside a shell command is
  `\"`: use `.*` or `[^;&|]*`, never `[^"]*`. "Never called" needs `min: 0` and `max: 0` (`min` defaults to 1, so `max: 0` alone can
  never pass). Case-insensitivity in a `tool_used` pattern is written with character classes (`[Qq]uick`); `regex` graders take
  `flags: i`. A regex over `trace` also sees the skill text and tool results, so graders on what the agent said use
  `last_message` or a question tool's input. At most one `llm` grader per case, with PASS and FAIL conditions.
- **Static tests (`tests/test_evals.py`).** Layout and limits (`max_turns` >= 40), grader keys (the runner silently ignores a
  misspelt grader key, so the key sets are checked), `min <= max`, skills, subcommands, flags and board attributes the graders name
  exist, file graders point at files the scaffold or the documented layout makes, a grader over a fixture file is not already
  satisfied by the untouched fixture, sample inputs for every key regex in the runner's JSON-encoded form, the verify scripts
  against real mutations (each asserted to have applied), and, when `claude` is on PATH, the real loader: a copy of the suite gets one
  invalid grader per case so that every case is loaded and nothing runs (the load error must name only the injected grader).
- Not covered by any of this: whether the agent behaves as graded. That is what a billed run measures.

## Testing

- **Independent oracle.** A test's expected value comes from outside the code under test: a constant worked out by hand, a
  fixture recorded from the real service or tool, a second implementation, or a property of the output (dimensions, schema,
  alpha). It is never the function's own output, and a test never builds its expectation with a helper imported from the
  module it checks (fixture keys and URLs are written out by hand for that reason).
- **Mutation tests** break a scratch copy of an input and assert that the mutation applied (`mutate()`, `mutate_json()`) and
  that the gate now fails. A mutation that did not apply proves nothing.
- **Skips are not passes.** A test whose prerequisite is missing is skipped with a loud NOT VERIFIED banner;
  `BRAND_CREATOR_REQUIRE_ALL=1` turns every such skip into a failure. Tests marked `requires_network` hit real services, are
  not part of the default run (they are deselected, not skipped) and run only with `BRAND_CREATOR_LIVE=1`.
- **Network** is never touched by the default suite: HTTP, whois and DNS answers are replayed from `tests/fixtures/names/`.
- **Not automatable here** (a person or a real session must look) goes to `docs/internals/manual-checks.md`; a manual check is never
  reported as passed by the suite.

## Quick-tier smoke

`tests/smoke/quick.sh` runs a Quick-tier project of a non-software business (fixtures in `tests/smoke/quick-bakery/`) through `new`, G0 (tier `quick`,
`review_surface: local`), the first board (`board-lint`, `shot`), `tokens`, a mark generated with `px_lib`, `contrast`, `logo-sheet`, `emit web`,
`emit social` (the Open Graph card only: a bakery lists no code repository, so no GitHub preview and no README headers), `emit profiles` (the avatar only), `downscale`, `book --init`, `book` (the short guide, filled with plain text), `book --verify`, `book-lint --self-consistency` and `check`, with every `brand-creator` call under `env PATH=<failing git shim>:<shim>`.

- **The shim** is a folder of symlinks to the tools the path needs and to nothing else (`npm` and `npx` are two-line wrappers); `command -v` and the shim
  python's `shutil.which` find none of sips, iconutil, actool, xcrun, ictool and git there. The git shim logs every call to `git-calls.log` and exits 127;
  the log must be empty. The project folder has no `.git` above it and `GIT_CEILING_DIRECTORIES` is set.
- **The renderer question** is asked by `prereq` and by nothing else: its output holds the marker `--renderer=resvg|pillow choice` once (the `sips` row; off
  macOS or when sips is not on PATH), and no other run of the main project holds it. The owner's answer is recorded with `downscale --renderer=<name>
  --record-renderer`; later `downscale` and `check` runs use it silently. A control project without an answer shows the exit-3 refusal and that nothing is measured.
- **Output rules** for the Quick path: no Apple tool name or Xcode, no platform-pack or deployment-target question, no package-registry host, no traceback
  or `command not found`; `sips` is named only in the prereq question. Runs that are meant to refuse are exempt from the word scan.
- **Refusals**: `emit android|chrome-ext|msix` exit 2 naming `state --set tier=full`; `emit presskit|print` and `emit social --posts` exit 2 naming
  `state --set tier=standard`; none of them writes a file or a report (the tier gate runs after G3 and before the report exists: `Emit.begin(tiers=...)`).
  The Tier A packs have no tier gate (see decision 707); `emit apple` with the Apple tools hidden exits 3 and writes nothing.

## Linux validation and CI

- **Image.** `tests/docker/Dockerfile` is Debian 13 (pinned by version tag) with the distribution's Python 3.13, the official Node 24
  tarball (SHA-256 checked), uv from its official image, resvg, ImageMagick, Ghostscript, poppler, ripgrep, potrace, fonts and the shared
  libraries of Chromium's headless shell, and a non-root user. The plugin and its data directory are not in the image.
- **Run.** `tests/docker/run.sh` builds it and runs `tests/docker/in-container.sh` on a read-only mount of the checkout: copy to a
  scratch folder, `prereq --for full` (only `xcode` may be MISSING once setup ran), `setup --yes` into a data directory inside the
  container, `tests/run-all.sh --smoke` without `BRAND_CREATOR_REQUIRE_ALL`, then `tests/docker/verify_log.py`.
- **What counts as passing off macOS.** pytest and node:test have no failure, the smoke printed `SMOKE PASSED` (`emit apple` exit 3 with its
  message), and every skip is a NOT VERIFIED skip with an expected reason: `not macOS`, `actool is not available`, `the claude CLI is not on
  PATH`, and the missing denylist when `BRAND_CREATOR_DENYLIST` was not mounted. Any other skip is a bug. The exact counts and the banner
  are printed.
- **Off-macOS opt-ins.** `downscale` needs `--renderer=pillow|resvg` (or a recorded opt-in), `emit tauri` needs `--renderer pillow`; tests, the
  smoke and `finish.sh` (`DOWNSCALE_RENDERER`, `ICNS_RENDERER`) name them. Usage errors (exit 2) are reported before "cannot measure here"
  (exit 3), so a bad call gives the same answer on every OS.
- **CI.** `.github/workflows/brand-creator.yml` (at the monorepo root, working directory `plugins/brand-creator`, started only by changes to that folder or the file): `linux` (the Docker run), `validate` (`claude plugin validate --strict` and the manifest-mutation test;
  a documented skip when the CLI cannot be installed), `macos` (`requires_macos` and `requires_actool` tests with REQUIRE_ALL=1, and the
  Acme smoke). It never runs `claude plugin eval`.
