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
- [Testing](#testing)

## Entry point and data directory

Skills call `brand-creator [--data <dir>] <subcommand> ...` (Claude Code puts the plugin's `bin/` on the Bash PATH).
Skills pass `--data "${CLAUDE_PLUGIN_DATA}"`, always quoted (a data path may hold a space; a test fails on any
unquoted form in the skills). `BRAND_CREATOR_DATA` is the environment equivalent. Every subcommand
except `help`, `version` and `prereq` needs one of them and exits 2 with a clear message otherwise. The data directory
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
`motion` (from `shot --motion`), `idempotence` (from `verify-idempotent`), `staleness`, `book`, `book-lint`, `book-pdf`, `print-check`, `adoption`, `adapters`, `applied-skill`, `launch-todo`, and one `emit-<target>` per emitter
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

```
<project>/
  BRAND-STATE.md  FACTS.md  brief/BRIEF.md
  research/research.md  research/YYYY-MM-DD-<topic>.md  research/positioning-map.md   P1 output (templates/research.md)
  research/cliches.md              (optional; "Forbidden" bullets feed the FORBIDDEN count in shots; templates/cliches.md)
  research/names/<date>-check.md  research/names/<date>-verdict.md  research/names/raw/<date>/run-<n>/   P2 (names, brand-naming)
  INVENTORY.md                     P1c surface inventory (templates/INVENTORY.md); board-lint needs it in Full / product-in-family
  rounds/r1/board.html ...         one folder per round; the page is board.html
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
  motion/proof.json                the motion proof's cases (shot --motion)
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
chapters: tone, photography, components), canonical_direction, reset_rounds ([4]),
fixes_per_area (map), gates (G0 G1 G2 G2b G3 G4 G5 G6 G7)`. A recorded gate reads `"<date> <decision>"`; empty means
not recorded. `brand-creator state --record G3 "<decision>"` writes it, `state --require G3` exits 1 when missing.
`freeze`, `emit web` and `emit social` require G3. The `## Directions` table in the body is read by `state --json`.

## Token sources (DTCG 2025.10)

DTCG 2025.10 is a Final Community Group Report. It is not a W3C Standard and nothing here calls it one.

- `tokens/primitives.tokens.json`: colours as `{"$value": {"colorSpace": "oklch", "components": [L, C, H], "alpha": 1,
  "hex": "#rrggbb"}}` under a group with `"$type": "color"`. `hex` is the 6-digit sRGB fallback and must equal the
  gamut-mapped (CSS Color 4 style, culori) conversion of the oklch value; `brand-creator tokens --fix-hex` computes it.
  Supported colour spaces: oklch, oklab, srgb, display-p3. Other types (dimension and duration as `{value, unit}`,
  fontFamily, fontWeight, number) are emitted to CSS custom properties and tokens.json only.
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
- `build_tokens.mjs` is the only producer of colour values for code. It uses Style Dictionary 5.7.0 with custom
  transforms, then parses every emitted artefact back and compares it with the source hex (round trip per transform).

## Board contract (data attributes)

`brand-creator board-lint <page>` finds sections by `data-section` attributes. Templates and generated boards must
carry them; a required section that is missing, empty or a placeholder (`TODO`, `...`) fails. Template markers
`[[fill: ...]]` left anywhere in text or attribute values fail the page (`page:unfilled`); HTML comments are ignored,
so optional blocks can wait in comments.

Page: `<body data-round="N" data-board="pick|refine">`. `data-round` must equal the folder `rounds/rN/` (catches a copied
page that was not updated). Round 1 and every round listed in `reset_rounds` must be `pick` boards.

| `data-section` | required when | notes |
|---|---|---|
| `what-changed` | round 2 and later | "What changed since the review" |
| `today` | `incumbent` in BRAND-STATE is not `none` | the incumbent as variant 0 |
| `positioning-map` | round 1 and rounds in `reset_rounds` | must contain an element `data-direction="<name>"` for every direction; at least one direction has `data-far="true"`; in reset rounds also a non-empty `data-field="failed-round"` showing where the failed round sat |
| `strategy-core` | round 1 | shown for reaction |
| `direction` (repeat) | always; at least 3 on pick boards, 1 otherwise | `data-name` (a word of 3+ letters, unique, identical on the board and in chat), optional `data-letter` (one unique capital), `data-register` (required on pick boards, unique per direction: one per emotional register), optional `data-far="true"`, a non-empty child `data-field="idea"`, and on pick boards a non-empty `data-field="reflex"` (the reflex test against `references/ai-defaults.json`: "no hits" or each hit with its argument) |
| `hardest-surface` | always | the one surface where the mark is most likely to fail |
| `weak-points` | round 2 and later | |
| `losers` | round 2 and later | contains `data-section="loser"` items, each with a one-line (max 200 characters) `data-field="reason"` |
| `none-of-these` | pick boards | |
| `my-call` | always | children `data-field="recommendation"` and `data-field="critique"`; with `data-judge="ran"` also `judge-view`, `lead-view`, `middle-option` |
| `questions` | always | contains `data-section="question"` items with `data-n` = 1, 2, 3 ... in order; each holds at least two options `data-option="a"`, `"b"` ... in order, at most one with `data-recommended="true"` |
| `reply` | always | how to answer: a name or letter and one sentence |

Project level: in round 1, when the tier is `full` or the architecture is `product-in-family`, `INVENTORY.md` must exist or
`inventory:` must start with `none` (for example `none (no target repo)`).

## Hook guard

`hooks/hooks.json` runs `scripts/guard.py` before Write, Edit, MultiEdit, NotebookEdit and Bash. It does nothing unless
the target has an ancestor folder containing `BRAND-STATE.md`. In a brand project it blocks (exit 2, reason on stderr):
Edit, overwriting Write and new files in `history/`; deletes, moves, `sed -i`, redirects, `tee`, `truncate`, `dd of=`,
`cp`/`install`/`ln`/`rsync` into `history/`; Edit, Write and Bash writes on any `rounds/rN/` that is not the latest round;
deletes anywhere under `rounds/` and moves out of `rounds/` except from the latest round into a `removed-*` folder.
`brand-creator freeze` is always allowed. `BRAND_CREATOR_GUARD_STRICT=1` also blocks Bash writes into the latest round.
It is best effort (an interpreter one-liner can still write); the real gate is `history/MANIFEST.sha256`, verified by
`check`. Fail-open applies only to input it cannot parse (it prints a warning): a broken guard must not brick unrelated
sessions.

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
measured; `put_slot()` defaults it to the file itself, the Apple pack names its marketing master). A multi-size file (an `.ico`) carries `layers`
and `layer_bands` ({"16": band, ...}); `check` re-reads each layer's band against the rule for that layer's own size.
Emitters write rows through `Manifest.put()` or `Manifest.put_slot()`; both write a file only when its bytes change.

### The platform emitters (`brand-creator emit <target>`)

Every emitter needs gate G3, reads sizes only from `platform-specs.json` (a test fails on a literal size in any emitter file), writes under
`assets/<target>/` (`--out-dir` overrides) laid out as the target repo's own paths, records rows through `Manifest.put_slot()` (a file that is a
drawing at a size: slot, size, band, resampled-by) or `Manifest.put()` (a document, a colour set, a rendered card), and writes
`assets/_checks/emit-<target>.json`. The drawing for a size is the one the band rule in `qa/rules.json` names (`Emit.drawing()`; the default
mark when the project defines no bands). `--master-band <name>` draws a file the system shrinks from another band and needs `--exemption`
(exit 1 without it, before anything is written). The dark artwork of a drawing is its `<name>-dark.svg` sibling, else the light drawing
recoloured through the token roles light to dark (a warning; a colour the tokens do not map exits 1).

| Target | Output | Gates in the emit |
|---|---|---|
| `apple` | `AppIcon.icon/` (icon.json + layer SVGs), `compiled/<platform>.renditions.json` and the actool fallbacks (`compiled/ios/*.png`, `compiled/ios/Info-icons.plist`, `compiled/macos/AppIcon.icns`), `Assets.xcassets/` (visionOS stack, accent colour set, menu-bar template, and the appiconset only for a target below 26), `Colors.xcassets`, `legacy/AppIcon.icns`, `marketing/AppStore-1024.png` (RGB, no alpha), `dmg/` (background, @2x, layout.json), `store/` (frames, frames.json), `_preview/` with `--previews` | vendored schema + validator on the `.icon`; actool compile per platform (iphoneos, macosx, watchos, xros) is exit 1 on any error; rendition checks per platform; icns round trip with iconutil; visionOS safe circle; no-alpha check |
| `windows` | `app.ico`, `nsis/header.bmp`, `nsis/sidebar.bmp` | ico layers equal the spec row; BMP header read back (24 bits, uncompressed, spec size) |
| `linux` | `usr/share/icons/hicolor/<s>x<s>/apps/<icon>.png`, `scalable/apps/<icon>.svg`, `usr/share/metainfo/<id>.metainfo.xml` | metainfo text from FACTS.md only, gaps reported |
| `tray` | `windows/<light|dark>/<state>-<px>.png`, `linux/<state>-<px>.png`, `macos/<state>Template@2x.png` | `qa/states.tray.json` written, then `states-check` (a failing pair is exit 1) |
| `tauri` | `src-tauri/icons/` PNGs, `icon.ico` (32 first), `icon.icns` | sizes and order; `.icns` by iconutil, or Pillow only with `--renderer pillow`; exit 3 otherwise off macOS |
| `wallet` | `apple/` (icon, logo, primaryLogo, secondaryLogo at @2x and @3x; order-logo.png), `google/` (logo-660.png, wide-logo-1280x400.png) | point size times scale; order logo opaque; circle-safe logo; wide logo transparent |
| `developer` | `email/` (1x, @2x, @3x), `nuget/`, `avatar/`, `cli/identity.txt` and `identity.plain.txt` | registry icon size limit; CLI colour chosen by contrast on a white and a black ground |
| `print` | `business-card-front`, `business-card-back`, `letterhead`, `envelope` as `<piece>.rgb-proof.pdf` or `<piece>.pdfx4-candidate.pdf` with `<piece>.print.json`; `email-signature/` | see Print; Standard and Full tier |
| `presskit` | `<slug>-press-kit.zip` | deterministic zip; Standard and Full tier |

`emit web` draws every favicon.ico layer, the apple-touch icon and each PWA icon through `Emit.drawing(size)` (the band rule for the file's own
size) and records the band (`layer_bands` for the .ico). `icon.svg` is one scalable file and stays the default mark. 

`emit apple` exits 3 off macOS (and on a Mac without Xcode) before it reads the project. `emit tray` reads `tray/tray.json` (a state's source is a
path, or a map of master size to path, or `{"light": ..., "dark": ...}` of those; a master serves only the sizes it divides, a size with no master
is exit 2). `Assets.car` files are compiled into a scratch folder and compared by their rendition list; only the list is shipped. A row that asks
for `qa: ["downscale"]` needs a current passing downscale report; the emit prints the command (`downscale --source <master>`) but does not run it,
because each master has its own report (`assets/_checks/downscale/<slug>.json`).

**Slots that no longer exist.** Every emitter run ends by retiring the rows it owns (same `emitter`, under its `--out-dir`) that it did not
write this time: the file is moved to `removed-<date>/<path>` in the project (never deleted), the manifest row is dropped and the report gets a
`retired:<path>` warning and a `retired` list. A removed tray state, a dropped deployment target or a feature option that is gone no longer ships.
A folder the run skipped on purpose (`emit apple --no-cards`) is spared (`Emit.keep()`), and `emit social` spares superseded fingerprinted
Open Graph files (cached link previews may still use their URL; it warns instead).

**Report inputs.** An emitter lists every file it read in its report: the marks, `assets/tokens/tokens.json`, `qa/rules.json` (the bands), and
as used `FACTS.md` (store frames, AppStream, CLI identity), `INVENTORY.md` (Apple deployment targets), `tray/tray.json`, `--svg-mono` and the
band drawings. Editing any of them makes the emit report stale.

Chain: `templates/finish.sh.tpl` is the ordered build (generators, tokens, contrast, emitters, gates, `verify-idempotent`, `staleness --write`,
`check`). It exports `BRAND_CREATOR_CHAIN=1`; a generator that rewrites a whole output folder calls `_common.require_chain()` and exits 1
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
 "downscale": {"accent_min_px": 4, "accent_rule_max_size": 32, "accent_colour": "color.accent", "accent_tolerance": 40},
 "states":    {"greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10, "ground": "#808080"},
 "cvd":       {"min_delta_e": 10.0, "deficiencies": ["protan", "deutan", "tritan"]},
 "guides":    {"tolerance_px": 1.5},
 "family":    {"tile_share_tolerance": 0.05},
 "bands":     [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "assets/logo/mark.svg"}]}
```

An unknown section or key, a value of the wrong type or a number at or below 0 exits 2: a typo never falls back to the proposal.
**Size bands:** `qa_rules.pick_band(bands, size_px)` is the one function that names the drawing for a body size (first band whose
`max_px` covers it; only the last band may omit `max_px`). `Manifest.put_slot()` records the band a slot used; a slot that uses another
band than the picker names needs a one-line `exemption` (exit 1 without), and `check` re-reads every recorded band from the manifest.

### downscale (`brand-creator downscale`)

One master (PNG, or an SVG rasterised once at `--master-size`) is shrunk to the sizes systems show (default: the union of the
`downscale-apple` and `favicon-set` rows of platform-specs.json) and the accent is measured at each size: pixel count, bounding box and
the largest solid square. Brand rule (default, owner-adjustable): at `accent_rule_max_size` px and below the accent holds a solid
`accent_min_px` x `accent_min_px` square (fail; a vanished accent is named). Methods: `sips -z` on macOS (default), `--renderer=resvg`
(SVG source, a vector render per size) or `--renderer=pillow` (Lanczos on a PNG source). Off macOS there is no default: the run exits 3
unless `--renderer` is given or BRAND-STATE records `renderer: <name> (opted in <date>)`. `--previous <older master>` (or the previous
report of the same source) adds `compare:<size>px` rows: a smaller solid square at a rule size is a warning "REGRESSION". The earlier report is
used only when it measured the same source with the same method, master size, accent and ground; otherwise an info row `compare:none` says
there is nothing comparable.
**One report per measured source**: `assets/_checks/downscale/<slug>.json` (tool name `downscale/<slug>`, the slug is the file stem plus six
hex digits of the path hash). `check` ties a manifest row to the report whose `source` equals the row's `downscale_source`. `--png FILE` measures a raster
as shipped (for example an actool output) with no resampling. The accent colour and ground come from `tokens.json` (the role in
`downscale.accent_colour`, mode `--mode light|dark`) or `--accent` / `--ground`.

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

`shot` also records, per view, `gutter_left` and `gutter_right`: the distance in css px from the nearest visible text or image box (outside horizontal scrollers) to the left and right edge of the viewport. They are data, never a verdict (a full-bleed page is legitimate); a page that promises a gutter, such as the generated book (16 px at 390), asserts on them.

### Motion proof (`shot --motion <proof.json>`)

`{"schema": 1, "cases": [...]}`, every case with a unique `name` and a `type`:

- `states`: `file` (the animated mark: the complete still, its moving part in `<g data-motion>` whose children `<g data-state="name">` are
  the named states), `static` (the still it must equal), `rest` (default `rest`), optional `expected` (state -> file), `controls` (pairs of
  states that must differ). Each state is rendered at device scale 1 and 2 (inline SVG and an `<img>` drawn on a canvas); the stored file
  must show its rest frame, rest must equal `static` pixel for pixel, and every control pair must differ (a comparison that cannot see a
  difference proves nothing). A case with no control pair fails.
- `page`: `page`, `selector` (the mark's element), `static`, optional `settle_ms` (default 1500), `max_cls` (default 0), `tolerance`
  (default 8 of 255). Normal pass: no infinite animation, every animation ended after `settle_ms`, whole-pixel motion, layout shift 0,
  rest frame equals the still; a control requires that the normal pass shows motion. Reduced pass (`prefers-reduced-motion: reduce`
  emulated): no running animation, no `requestAnimationFrame` loop, no `pointermove`, `mousemove`, `touchmove`, `wheel`, `scroll`,
  `deviceorientation` or `devicemotion` listener (script-registered or inline), layout shift 0, rest frame equals the still. Pages are
  served from a local server that refuses every non-local request.

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

A manifest row with `qa: [...]` needs a current, passing report from the matching tool (`downscale`, `states`, `motion`, `family`, `fonts`
= `fontcheck`, `idempotent` = `verify-idempotent`); for `downscale` it is the report of the row's own `downscale_source` (a row without one fails,
and a passing report on another file never counts); a report that exists is gated whether or not a row asks. A missing report is "not
verified" (exit 3), a stale one too, a failing one exit 1. Slots off the band rule, platform-spec rows stamped stale or U, and
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
facts); `check` treats a report whose view changed as not verified. A change to the phase or review URL does not. The reports also record `manifest_view_sha`, a hash of the manifest rows the book shows (everything except the press kit, which contains the book's PDF, so the book cannot name its hash and a rebuilt kit must not make the book stale; the files chapter says where the kit is, without a checksum); `assets/manifest.json` is not a report input, and a changed row the book shows makes `book`, `book-lint` and `book-pdf` not verified.

**Chapters.** Registry order, selected from `tier`, `architecture`, the project's files and `book_chapters`: quick `idea, mark, colour,
files, changing` (plus `wordmark` when `assets/logo` has a wordmark or lockup); standard adds `motion` (when `motion/proof.json` or
`motion/SPEC.md` exists), `type`, `use`, `proof`, `donts`, `history`; full adds `adoption` and `launch`; `endorsement` and `family` in the
family modes; `tone`, `photography`, `components` only when named in `book_chapters`. Each chapter is `book/chapters/<id>.md`
(`<id>.<lang>.md` for each language when `content_languages` has several; every language is required). `book --init` copies the skeletons
from `templates/book/` and never overwrites; `[[fill: ...]]` left in a chapter fails the build.

**Chapter Markdown** is a documented subset (`scripts/booklib/bookmd.py`): `## `/`### ` headings, paragraphs, flat lists and task lists,
`>` quotes, pipe tables, fenced code, own-line images (embedded as data URIs; SVG under `assets/` is mark-linted), inline `**`, `*`, `` ` ``,
links. Raw HTML is escaped. Anything else is an error with the line number. Computed blocks on their own line: `{{marks[:stem,stem?]}}`,
`{{mark-sizes}}` (the drawing the size band rule picks, rendered at exactly the size on light and dark, the enlarged copy being the same
pixels, plus the downscale reports' accent measurements), `{{colours}}`, `{{contrast}}` (WCAG ratios computed from the tokens), `{{type}}`,
`{{motion}}`, `{{tokens}}`, `{{files}}` (one row per manifest row and source artwork file with `data-path` and `data-sha`), `{{checks}}`,
`{{decided}}`, `{{history}}`, `{{edition-log}}`, `{{donts}}` (five misuse drawings of the mark), `{{facts}}`. Inline: `{{count:NAME}}`
(`files, slots, colours, pairs, roles, sizes, artwork, emitters, chapters`), `{{fact:LABEL}}` (a FACTS.md row's value), `{{edition}}`,
`{{name}}`, `{{approved}}`. `::: variant GROUP NAME` and `::: switcher GROUP` fences are open choices (see `collapse`). Settings in
`book/book.json` (unknown keys are exit 2): `min_label_px` (default 12, stated in the book), `sizes`, `fonts` (`{family, file, weight, style}`,
embedded as data URIs), `labels` (`{lang: {English label: translation}}`; a label with no translation is shown in English and warned),
`output`, `lint` (`history_chapter, forbidden, scratch, round, status_words, count_nouns, allow_external_links, files_exclude`).

**The cover and adoption.** The `Adoption` row of the cover states only what the data back: `Adoption approved <date>` once G6 (the owner's go) is recorded, else `Adoption not yet approved`, and, when `adoption.json` exists, `; N of M rows done` counted from its `progress`. G6 alone never says "applied". `adoption.json` (row progress) is in the book's state view and inputs, so a progress change makes a built book stale; an `adoption.json` that is not an adoption record exits 2.

**Edition and approval.** `edition` is the book's number. The cover (`data-cover`, `data-edition`, `data-stamp`) shows APPROVED and the G5
date only when G5 is recorded and `approved_edition` equals `edition`; `state --record G5` writes `approved_edition`, so a later edition is
pending until it is approved again. `patch` and `collapse` log under `## Edition log` and refuse to change an approved edition unless
`--new-edition` opens the next. A hand-authored book must show the stamp before G5 is recorded (patch the cover, then record).

**book-lint rows** (each one result in `assets/_checks/book-lint.json`): `html:head`, `ids:duplicate`, `anchors:broken`, `network:refs`
(script, handlers, `<link>`, iframe, `src`/`srcset` that is not `data:`, http(s) in links or text, CSS `url()` that is not `data:`, `@import`),
`links:files` (warn), `marks:lint` (mark_lint on every inline `<svg>`, every `<img data-mark>` data URI and every linked `.svg`; an
`<svg data-diagram>` may hold text but no script or external reference), `images:alt`, `words:scratch`, `words:round` (outside the history
chapter), `words:forbidden` (FORBIDDEN list of BRIEF.md and cliches.md, outside the history chapter), `words:status` (a status word needs a
FACTS.md value that contains it), `variants:open`, `chapters:required`, `edition:stamp`, `counts:data` (every `data-count` equals the data),
`counts:typed` (a digit followed by `files`, `slots`, `colours`, `pairs`, `roles`, `sizes` or `chapters` in prose must equal the data; write it
as `{{count:NAME}}`), `facts:data`, `files:accounting` (every manifest row and artwork file has a `data-path` row with the right `data-sha`),
`legal:<label>` (FACTS.md rows whose label starts `legal` must appear verbatim), `lang:parity` (every `lang=` + `data-key=` block exists in
each content language with the same block structure; text in a language that is not in `content_languages` fails). `--self-consistency` adds
`self:durations` (CSS durations and delays are 0 or a `duration.*` token), `self:font-size` (no declared size under the minimum label size;
rem and em are taken at 16 px, `var()` cannot be read and fails) and `self:colours` (hex, rgb() or named colours in CSS and SVG paint
attributes must be token colours; other colour functions fail).

**book-pdf.** `render.mjs pdf` prints the book with Chromium (print media, light scheme by default, A4 or Letter, 14 mm margins, background
graphics) after adding the label "RGB, not print-ready" to its first page; `book_pdf.py` (pikepdf) sets Title, Subject, Keywords, XMP
description and fixed dates and ID, and writes `book.pdf`. Chromium's PDF is RGB: the file has no print profile, no bleed and no trim box and
says so (rows `pdf:label-metadata`, `pdf:label-xmp`, `pdf:label-cover`, `pdf:colour`, `pdf:no-output-intent`, `pdf:print-ready` info).
A book that does not lint clean is not exported. Print production (bleed, trim, PDF/X candidate) is a separate step.

**patch** (`patch FILE --old T --new T --count N`): replaces and refuses, writing nothing, unless the text occurs exactly N times. Never edits
`history/`, an earlier round or `assets/_checks/`; refuses `book.html` of a generated brand. On a book file it appends
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
sub-brand, endorsed; product-in-family: product, endorsed; these pairings are brand-creator's reading, not something the format defines, so they can be overridden),
then Strategy (the facts, the canonical direction), Voice (only `voice` and `tone` facts and the FORBIDDEN list; "no voice facts are recorded" otherwise), Visual
(colour roles in light and dark, type families, the mark files, the G4 rules, motion durations) and Governance (naming and renames, claims and verbatim legal facts,
the accessibility commitments with the computed ratios, approval). Contact and postal-address facts are left out. DESIGN.md: frontmatter `version: alpha`, `name`,
`colors` (the light roles, `-dark` variants, `primary` when `--primary` names a role), `typography` (families only), `spacing`, `components` (one entry per
`ui-text` pair, light and dark, as `{colors.x}` references), then the sections in the spec's order that have content. The report `adapters` records the sha256 of
each output and `adapter_state_sha` (a hash of what the adapters read from BRAND-STATE.md and FACTS.md). DESIGN.md is linted with `@google/design.md` (the version
pinned in `scripts/package.json`, run with Node from `<data>/node_modules`; a different installed version is not trusted): an error or a `contrast-ratio` finding
is `fail`, other warnings are `warn`, and a missing package is `skipped`, so the report is not-verified and the exit code 3. `check` gates the report, fails a file
that is not the bytes the report recorded (a hand edit) and treats a changed source as not verified. A hand-edited file is replaced only with `--replace`, which
moves it to `removed-<date>[-n]/`. When `tools/inputs.json` exists, the adapters add `BRAND.md` and `DESIGN.md` to its globs (the pack then reads as stale until
`staleness --write`), and `staleness --write` includes both whenever they exist.

### applied-skill

`applied-skill --yes [--plan] [--replace]` writes `.claude/skills/<slug>-brand/SKILL.md` into the project from `templates/applied-skill/SKILL.md`: colours (light and
dark) and the contrast pairs with their ratios, type families, the mark files (relative to the skill), the small-size rule (from `qa/rules.json`, or the plugin's
proposal, said so), what is never done, the G4 rules, the facts that may be claimed (contact facts left out). It needs G5 and `--yes` (without it: the plan on stdout, a
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
- **Not automatable here** (a person or a real session must look) goes to `dev/MANUAL-CHECKS.md`; a manual check is never
  reported as passed by the suite.
