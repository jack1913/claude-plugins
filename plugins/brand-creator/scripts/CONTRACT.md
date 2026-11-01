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
- [Page check](#page-check)
- [Website references and reference pages](#website-references-and-reference-pages)
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
project, under `<data>/scratch/<slug>-<hash>/`. `shot --out DIR` may point outside the project or into `<project>/specimens/` (any depth, the folder itself
included), the one folder of the project where shots may be kept; anywhere else in the project it exits 2 with `--out <DIR> must be outside the project, or under
specimens/` (`<DIR>` is the folder as typed; a symlink is followed first, so a link out of `specimens/` into the rest of the project is refused too). A relative `--out` is read from the current
folder, as before. The report's `out_dir` records the folder the slices were written to.

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
`motion/<slug>-<hash6>` (from `shot --motion`, one per proof file; see Motion proof) and `frames/<slug>-<hash6>` (from `frames`), `page-check/<slug>-<hash6>` (from `page-check`, one per page; see Page check), `idempotence` (from `verify-idempotent`), `staleness`, `book`, `book-lint`, `book-pdf`, `print-check`, `adoption`, `adoption-wiring`, `adapters`, `applied-skill`, `launch-todo`, and one `emit-<target>` per emitter (with several marks, `emit-<target>/<mark>` and `logo-sheet/<mark>` per mark)
(`emit-web`, `emit-social`, `emit-apple`, `emit-windows`, `emit-linux`, `emit-tray`, `emit-tauri`, `emit-wallet`, `emit-developer`, `emit-print`, `emit-presskit`). The renderer in use is stored in the report and
printed on every run.

**An input may stand for a part of a file.** An entry of `inputs` is a whole file, `{"path", "sha256"}`, unless it also has `"part"`: `{"path": "BRAND-STATE.md", "part": "g4-rules", "sha256": "<hex>"}` stands for one named part of the file,
and its `sha256` is that of the part's canonical text, not of the file. One registry reads the parts (`PART_READERS` in `scripts/lib/_common.py`: the part's name, the file it belongs to, what to call it in a sentence, how to read it);
a `Report` takes `PartInput(path, "<part>")` among its inputs. The only part so far is `g4-rules` of `BRAND-STATE.md`: the G4 record (white space collapsed) and, once G4 is recorded, the recorded `(rule)` lines of Rules (G4) in file order
(white space collapsed; `adapt.g4_rules`, the one reading `adapt.view(project)["rules"]` also makes), as one line of JSON. The rest of the file (the phase, the other gates, the Directions table, Still open, a line of Rules (G4) that is no `(rule)`
line) is not in it. `_common.stale_inputs`, the rule `check`, the boards and the book apply, recomputes the part: the input is stale when the part changed (`BRAND-STATE.md (the G4 rules) changed`) and when it cannot be read, with a sentence that says why
(`BRAND-STATE.md (the G4 rules) cannot be read: ...`: no frontmatter, a part this plugin does not know, a part of another file). A part that cannot be read when the report is written is recorded as unreadable, so the report reads as stale and never as
current. `inputs_sha` hashes the part name after the path for a part input; a record without `part` is judged and hashed as it always was, so older reports keep their meaning. A board lint that copies the records of the reports it stands on
(`board-lint` of a site board, from its page-check reports) copies a part as it is, so it follows.

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
  research/site-cliches.md         (the website references: the category's site clichés under "Avoid unless argued", no Forbidden section; templates/site-cliches.md)
  research/names/<date>-check.md  research/names/<date>-verdict.md  research/names/raw/<date>/run-<n>/   P2 (names, brand-naming)
  INVENTORY.md                     P1c surface inventory (templates/INVENTORY.md); board-lint needs it in Full / product-in-family
  rounds/r0/board.html             round 0: the style board (P1s, from templates/style-board.html); no mark is drawn in it
  rounds/r1/board.html ...         one folder per drawn round; the page is board.html
  rounds/r<N>/<direction>/<item>.svg, <item>-16/-32/-128.png, SOURCE.md   the kept marks of a drawn round: SVG masters, PNGs
                                   exported from them, and where they came from (templates/SOURCE.md; drawing-engines.md)
  rounds/r<N>/<variant>/           a motion round (data-board="motion", templates/motion-board.html; see Board contract): one folder per variant with index.html (the move where it
                                   will be seen), proof.json (a page case named <variant>) and frames/<variant>/ (the stills `frames` took of it)
  rounds/r<N>/board.html           a website references round (data-board="site-refs", templates/site-refs-board.html; see Board contract): groups of real sites, from round 2 on
  rounds/r<N>/<variant>/index.html a site round at the hero stage (data-board="site", templates/site-board.html; see Board contract): one folder per variant of the home page's first screen, beside rounds/r<N>/board.html
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
  specimens/<name>/                page shots kept as specimens (shot --out specimens/<name>); any depth, the only project folder `shot --out` may write
  research/site-refs/<name>/       a real site's stills from `capture --url`: 1440.png 390.png 1440-full.png thumb-1440.jpg thumb-390.jpg capture.json (see capture)
  research/site-refs/owner/        screenshots the owner sent (not captured; the board's caption says so; `capture --url --name owner` is refused)
  <page folder>/shots/             a project page's stills from `capture <page>`: 1440-light.png 1440-dark.png 390-light.png 390-dark.png 1440-light-full.png capture.json
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
site_research (auto|online|links-only|none: the owner's answer to online research for website references; `capture --url` needs online or links-only),
incumbent (none or a line), inventory (path or "none (no target repo)"), edition (whole number, the brand book's), approved_edition (the edition G5 approved; `state --record G5` writes it), book_chapters (extra
chapters: tone, photography, components, site), canonical_direction, reset_rounds ([4, 5]: the style board run again after a full rejection,
then the pick board), g1s_round, fixes_per_area (map), gates (G0 G1 G1s G2 G2b G3 G4 G4w G4p G5 G6 G7)`. A recorded gate reads `"<date> <decision>"`;
empty means not recorded. `brand-creator state --record G3 "<decision>"` writes it, `state --require G3` exits 1 when missing.
`G4w` is the website references pick (or `skipped by owner`) and `G4p` the site's reference pages approved; `state` prints the gates in the
order above, `--record` and `--require` accept both, and a project made before them gets the key on its first `--record`.
`state --set site_research=...` takes only its four answers: any other value exits 2, names them and writes nothing.
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
- Text grounds: `$extensions["brand-creator"].grounds` of `semantic.light.tokens.json` lists the colours text sits on, each with its five roles:
  `{"grounds": {"named_by_owner": "<YYYY-MM-DD> <the owner's words>", "list": [{"ground": "color.bg", "text": "color.text", "action": "color.accent",
  "on-action": "color.on-accent", "focus": "color.focus", "border": "color.border"}]}}`. Every value is the name of a semantic colour token. `named_by_owner`
  is the date and the owner's words naming the grounds and stays `""` while nobody has: the model never guesses which colours text sits on. The starter
  carries the roles `color.on-accent` (light `{color.paper}`, dark `{color.night}`) and `color.focus` (light `{color.signal}`, dark `{color.signal-bright}`),
  the pairs `color.on-accent`/`color.accent` (`ui-text`, 4.5) and `color.focus`/`color.bg` (`ui-component`, 3), and a proposal for `color.bg` with
  `named_by_owner` empty. `tokens` checks the block only when it is present: `grounds` an object with a string `named_by_owner` and a `list` of objects
  with a string `ground`, and each of the five roles a string or left out. A block of the wrong shape is a failing `grounds` row (exit 1) that
  names every problem and writes nothing, as for a pair that names an unknown token. A name that is no semantic colour token (the ground included) is a
  `grounds` warning that names it, and resolves as `null`; a role left out is `null` and `tokens` says nothing, because `contrast` is the check that
  asks for all five. `tokens.json` then gains a last key `grounds`: `{"named_by_owner": "...", "list": [{"ground": "color.bg", "roles": {"text":
  "color.text", "action": "color.accent", "on-action": "color.on-accent", "focus": "color.focus", "border": "color.border"}, "modes": {"light": {"ground":
  "#f3f5f8", "text": "#16181d", "action": "#375587", "on-action": "#f3f5f8", "focus": "#375587", "border": "#565b63"}, "dark": {...}}}]}`: `roles` keeps
  the names as written (`null` for a role left out), `modes` holds the six-digit hex of each in that mode (`null` when it did not resolve). Without the
  block, `tokens.json` and every other output are byte for byte what they were, and the report has no `grounds` row.
- Text-ground checks: `contrast` reads `grounds` of `tokens.json` (nothing when the key is absent but the one `grounds:named` row) and writes the section
  `grounds`. Every row is a pass or a warning that says it is a failure from the next release; the report's status and the exit code never change because of
  them. `grounds:named` warns when `tokens.json` has no `grounds` ("ask the owner which colours text sits on; record them in `grounds` with the date and their
  words; never guess"), when `named_by_owner` does not start with a real `YYYY-MM-DD` date (the starter's `""`: "a proposal, not named by the owner"), when it is only
  a date, and when `list` is empty; it passes naming the owner's words. A ground listed more than once keeps its rows apart by `#2`, `#3` after its id. For each ground and mode:
  `grounds:<mode>:<ground>:roles` warns naming the role (or `ground`) that has no colour (left out, `null`, or a name that is no semantic colour token), and
  the rows that need that colour are then not written, never invented; `grounds:<mode>:<ground>:<role>` is the WCAG 2.2 ratio of `text` on the ground (4.5:1),
  `action` against the ground (3:1), `on-action` on the action (4.5:1), `focus` against the ground (3:1) and `border` against the ground (3:1), with `ratio`,
  `required`, `fg`, `bg`, `ground`, `mode` and `role`. With `--cvd`, `cvd:<mode>:grounds:<ground>:<action|focus>` holds the action and the focus ring to the
  colour-vision distance of the shared rule (`qa/rules.json` `cvd.min_delta_e`), in the fields of the other `cvd:` rows, in the same section; a missing colour is
  said once, in the roles row. A `tokens.json` whose `grounds` has the wrong shape is a usage error (exit 2). The proposal in the starter is judged like the owner's grounds.
- Emitters need the semantic tokens `color.bg` and `color.text`; `color.muted` and `color.accent` are used when present.
- Motion tokens (primitives only: a semantic file carries colours only). A duration is `"$type": "duration"` with `{"value": 320, "unit": "ms"}`
  (`unit` is `ms` or `s`; the older `"320ms"` string is read too): a number of 0 or more that comes to whole milliseconds, because Android keeps a
  duration as an integer. A curve is `"$type": "cubicBezier"` with `"$value": [x1, y1, x2, y2]`: four finite numbers, `x1` and `x2` within 0 and 1,
  `y1` and `y2` unrestricted (a curve may overshoot); a duration is at most 2147483647 ms, the largest integer Android keeps. A group named `easing` gives `--easing-*`. A reference (`"{easing.standard}"`) resolves like any
  other. Anything else fails the build (exit 1, report row `motion-tokens`), names the token path and writes nothing. The starter tokens carry three
  curve proposals, `easing.standard` `[0.2, 0, 0, 1]`, `easing.enter` `[0, 0, 0, 1]` and `easing.exit` `[0.3, 0, 1, 1]`, which stay proposals until G4.
- Layout slots in the starter tokens (`templates/tokens/primitives.tokens.json`; proposals until G4, each group's `$description` says so): `space.1` to
  `space.8` (4, 8, 12, 16, 24, 32, 48, 64 px), `radius.sm`, `md`, `lg`, `pill` (4, 8, 16, 999 px), `layout.container` (1200 px) and `layout.gutter` (24 px),
  `breakpoint.sm`, `md`, `lg`, `xl` (640, 768, 1024, 1280 px), all `"$type": "dimension"` with `{"value", "unit": "px"}`; and `leading.display` (1.1), `leading.body`
  (1.5), `tracking.display` (-0.01) and `tracking.body` (0), `"$type": "number"` (tracking is in em, as DTCG 2025.10 dimensions are px or rem only:
  `letter-spacing: calc(var(--tracking-display) * 1em)`). `dimension` and `number` tokens reach `tokens.css` (`--space-1: 4px;`, `--leading-display: 1.1;`) and
  `tokens.json` under `other` only (`"space.1": "4px"`); they are not durations or curves and have no Swift or Android output.
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

Page: `<body data-round="N" data-board="pick|refine|style|motion|site-refs|site">`. `data-round` must equal the folder `rounds/rN/` (catches a copied
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
| `direction` (repeat) | always; at least 3 on pick boards, 1 otherwise | `data-name` (a word of 3+ letters, unique, identical on the board and in chat), optional `data-letter` (one unique capital; off by default, and `question:N:letters` warns when a letter equals an option letter of a question that does not list the directions), `data-register` (required on pick boards, unique per direction: one per emotional register), optional `data-far="true"`, a non-empty child `data-field="idea"`, and on pick boards a non-empty `data-field="reflex"` (the reflex test against `references/ai-defaults.json` and the project's `research/cliches.md`: `no hits`, or one `hit: <id> \| <argument>` per hit; see Reflex test below) |
| `hardest-surface` | always | the one surface where the mark is most likely to fail |
| `weak-points` | round 2 and later (a motion board: from its second) | |
| `losers` | round 2 and later | contains `data-section="loser"` items, each with a one-line (max 200 characters) `data-field="reason"` |
| `none-of-these` | pick boards | |
| `my-call` | always | children `data-field="recommendation"` and `data-field="critique"`; with `data-judge="ran"` also `judge-view`, `lead-view`, `middle-option` |
| `questions` | always | contains `data-section="question"` items with `data-n` = 1, 2, 3 ... in order; each holds at least two options `data-option="a"`, `"b"` ... in order, exactly one with `data-recommended="true"` (none or several fail `question:N:options`); a question that lists the directions carries `data-lists="directions"` in the template and shows their names |
| `reply` | always | how to answer: "Answer with a direction name, or question number plus option (1a)" and one sentence |

Reflex test (pick boards). The `data-field="reflex"` line of each direction is one parseable line: `no hits`, or one `hit: <id> | <argument>` per hit, and
optionally `near miss: <id> (<why>)` for a pattern that looks close and is not one (recorded, never counted); an optional leading `Reflex test:` is allowed.
`<id>` is an id of `references/ai-defaults.json` or an item of the project's `research/cliches.md` under "Avoid unless argued" (compared by casefolded name,
a trailing parenthetical dropped). The rules are in `scripts/boardlib/reflex.py` (`parse`, `line_rows`, `shared_hit`), outside `scripts/lib/`, so another board can
reuse them with its own cliché file. Five rows, the first four per direction as `direction:<name>:<suffix>`:

| row | status | when |
|---|---|---|
| `reflex-format` | warn (else pass) | the line is not in the format: free text, a `hit:` with no `\|` or no argument, text before the first marker, `no hits` together with a hit; the detail quotes the problems and the format |
| `reflex-ids` | warn (else pass) | a hit names neither an id of `ai-defaults.json` nor an item of `research/cliches.md`; the detail says when the project has no `research/cliches.md` |
| `reflex-count` | **fail** (else pass) | two or more hits in one direction: replace a part before showing it |
| `reflex-grounded` | warn (else pass; no row for a line with no hit) | the argument of a hit shares no word with the owner's own material (the detail names the hit and asks for the fact, place or craft that earns it); the pass names the shared words. With neither `FACTS.md` nor `brief/BRIEF.md` holding a word of the owner's own (missing, or still the templates; the title line with the brand's name filled in, as `brand-creator new` writes it, is still the template) the argument is checked against nothing: the warning says `NOT verified` |
| `directions:reflex-shared` | **fail** (else pass; info with fewer than two directions that have a reflex line) | every direction hits the same name: the directions are not divergent |

Grounding is a floor, not a judgement of the argument's quality. The words are runs of Unicode letters (digits and `_` excluded), casefolded, four letters or
more, with no stop list of any language and no stemming. They are taken from the lines of `FACTS.md` and `brief/BRIEF.md` that are the owner's own: lines that
are not lines of the plugin's `templates/FACTS.md` and `templates/BRIEF.md` (verbatim, or with a `{{...}}` placeholder filled in: the title line
`# Acme: facts` is a template line, so the brand's name alone is no ground word), minus the words of those templates' prose (the lines that do not start with
`|`). A hit's argument is grounded when it shares at least one such word; nothing else is read.

A warning says "a failure from the next release": the three warnings become failures in the next release, so a board passes now that fails then.
`research/cliches.md`, `FACTS.md` and `brief/BRIEF.md` are inputs of the report when they exist (a changed list, fact or brief makes the lint stale). A refine
board has no reflex line and none of these rows.

The judge's list (pick boards, only when `my-call` has `data-judge="ran"`). A judge lists, for each direction, the ids of `references/ai-defaults.json` and the
items of `research/cliches.md` it sees, before it reads the argument; the lead puts that list beside the reflex line as `data-field="reflex-seen"` (a paragraph
`judge saw: <id>; <id>` or `judge saw: none seen`, or a list with one `li` per pattern; the templates carry it in a comment to uncomment). Two warnings per
direction, `direction:<name>:<suffix>`; both become failures in the next release. Without `data-judge="ran"` the list is not looked at and neither row exists.

| row | status | when |
|---|---|---|
| `reflex-seen` | warn (else pass) | the judge ran and the direction has no non-empty `data-field="reflex-seen"`, or its list names no pattern and does not say `none seen` (a list that is only its label, `judge saw:`, is no answer); `none seen` is an answer |
| `reflex-unargued` | warn, once per pattern (else one pass) | a pattern on the list is neither a hit nor a near miss of the reflex line (compared by `norm`: casefolded, a trailing parenthetical dropped); the detail names it and says to argue it as a hit, or to say why it is a near miss. No row without a list, or without a reflex line (that is its own failure) |

Colour divergence (pick boards). Each `direction` carries its light-mode colours in its own `style` attribute: `--d-paper`, `--d-ink` and `--d-accent`, each
`#rgb` or `#rrggbb` (the board templates and the Acme example write them so). A direction that does not carry all three as such values is not measured. The rule
is in `scripts/boardlib/divergence.py` (`read_colours`, `oklab`, `distance`, `row`), outside `scripts/lib/`. One row, never a failure:

| row | status | when |
|---|---|---|
| `directions:divergence` | warn (else pass; info when fewer than two directions carry all three) | two directions whose paper and ink are both within 0.04 and whose accents are within 0.06 of each other, as OKLab distance (Euclidean in L, a, b; L from 0 to 1): "they look alike in colour". The detail names each such pair with its three distances. The pass names, for each of paper, ink and accent, the smallest distance between two directions and which two. The info row says `not measured` and how many directions could be read |

The two thresholds are a practice proposal, not a measured rule (a just-noticeable difference is about 0.02), and the detail of the row says so in every status.
A refine board, a style board and a motion board have no such row.

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
| `motion:off` | `motion/motion.json` says `off` ("nothing moves is recorded: a motion round contradicts it"); "not verified" (`skipped`, exit 3) when it is not a valid answer, read as `brand-creator motion` and `state` read it (`motionspec.decision`: not JSON, not an object, or not valid in itself, such as `off` with no reason), with the message `motion` refuses it with; absent or `on` passes, and so does a file that says `on` but is not valid in itself, naming the error (it records no "nothing moves"; `check` fails it in `motion:spec`) |
| `motion:variants` | the count (exactly 3 on the project's first motion board, 1 or more on a later one) or a name (a word, not a label, a folder name, unique) |
| `motion:files` | a variant has no folder, or one that is not spelt as the card spells it (an entry of `rounds/rN/` equal to the card's name, letter case included: a disk that does not tell letter cases apart, macOS or Windows, opens `settle/` for the card `Settle`, but `shot --motion` and `frames` name their reports after the folder as the disk spells it, so the reports the board asks for are never made; the row says the card and its folder must be spelt alike, on every kind of disk), no `index.html` or no `proof.json`; the proof has no page case named `<name>`, or its `page` is not `rounds/rN/<name>/index.html`, the page the card links (a proof copied from an earlier round and still pointing there fails), or its `static` is not an existing file of `assets/logo/` (an approved master: a variant has no still of its own); `frames/<name>/strip.png` or `reduced.png` is missing; the card has no link to the live page or it does not lead to `<name>/index.html` |
| `motion:proof` | a variant has no motion report of its proof, a stale one (a file it read changed) or one that is no verdict (not-verified), each naming `brand-creator shot --motion rounds/rN/<name>/proof.json` (the row quotes the rows of the report that are not verified, each with its id and detail; one that names `requestAnimationFrame` adds that such a move stays not verified however often the proof runs, and says to write it as CSS animations, CSS transitions or `element.animate()`; the other not-verified rows `shot --motion` writes, a percentage translation on a pseudo-element or a still that cannot be placed over the mark, are quoted and given no such advice); the card's `data-proof` is not `pass` or `fail`, is not the report's status (a failing proof shown as `fail` is honest and passes) or has no text |
| `motion:stills` | a variant has no `frames` report of its proof (`assets/_checks/frames/<slug>-<hash6>.json`), a stale one (the proof, the page or a file the page loaded changed since the stills were taken: `shot --motion` run again does not make the stills current) or one with no passing `frames:<name>` row; the strip or the reduced still the card shows is not the file `frames.json` lists, by sha256; also the file on disk differs from `frames.json`, `frames.json` cannot be read or is of another proof or case (a folder copied from an earlier round), or the card has no, or two, `<img data-field="strip">` or `"reduced"`; each names `brand-creator frames rounds/rN/<name>/proof.json --count 25` |
| `motion:fields` | What it is, Cost or Degrades to is missing, empty, a placeholder or still holds a `[[fill: ...]]` marker, in a card |
| `motion:timelines` | never a failure. Warn when two variants have the same number of animations and lengths within 5 % of the longer one or within 20 ms ("they look alike in time": three variants should try three moves), read from the `sampling` row of each variant's current motion report (`length_ms`, `animations`); the detail names each such pair with its two timelines and says the limits are a practice proposal. Pass when every variant was compared and no two are alike. Info (never a pass) when a variant is not compared, never a guess: its motion report is missing or stale (`motion:proof` says why), or current but with no `sampling` row or no number in it (the detail says the report has no sampling row; `motion:proof` has nothing to say then), or its row says the motion was sampled in real time (`real_time`) or found no animation (`animations` 0, written with a length of 0), so no timeline was measured; the others are still compared, so a pair alike among them still warns. Info too when there is no variant card, or when the board shows one variant (nothing to compare) |

`page:data-board` also fails a motion board in round 0 or 1 or in a round listed in `reset_rounds`. The `inputs` of the lint report are the page, `motion/motion.json` when it exists (`motion:off` reads it, so an answer changed after the lint makes the report stale) and, of each variant, `proof.json`, `index.html`, `frames.json`, the strip, the reduced still, the motion report and the frames report, and every file those two reports were made from (their own `inputs`:
the files the page loaded, such as a stylesheet, `tokens.css` or a script, where the move may live), so `check` calls the report stale ("not verified") as soon
as one of them changes: take the stills and the proofs first, lint, and shoot the board last (`shot` writes `assets/_checks/shot.json` for one page, and `check` wants the one of `rounds/r<latest>/board.html`).

### The website references board (`data-board="site-refs"`)

A website references round shows the owner groups of real sites to learn from, before any page of the site is built. It runs in the Standard and Full tiers, after G4, and only when `brief/BRIEF.md` lists a site; the owner's
pick of a group is gate G4w. It is a round from 2 on: `rounds/rN/board.html`, from `templates/site-refs-board.html` (built on the frame of `templates/style-board.html`: the same tokens, header, theme switch, questions and reply).
A website references board is no pick, style, reset or rejected round: the map and the style-round logic, `reset_rounds`, the kept masters and the style re-arming of a later pick board ignore it (the round "rejected" before a reset is never a
references round), and a references board in round 0 or 1, or in a round listed in `reset_rounds`, fails `page:data-board` ("a website references board is a round of its own from round 2 on"). Its rows are in
`scripts/boardlib/siteboard.py` (outside `scripts/lib/`, like `boardpage.py`), which also reads the brief; `boardpage.py` counts the groups (`is_site_refs_board`: the page declares `site-refs` and the round of its own folder, and holds at least four named
groups with content, as a style board is counted by its territories).

| `data-section` | required | notes |
|---|---|---|
| `visitor-job` | yes | who visits, the job they came to do, the one action that serves it; non-empty |
| `norm` | yes | what most sites in the category do; non-empty |
| `owner-sites` | yes | the sites the owner likes and dislikes (the template gives each an `<li data-like="like\|dislike">` with a link and `data-field="why"`), or one line saying the owner named none; non-empty |
| `group` (repeat) | 4 to 6 (`groups:count`) | `data-name` (a word) and content beyond a heading: a group without a name or without content is not counted; the template gives each group a `data-field="idea"`, a `data-field="references"` list of three sites (a link, a screenshot `<img data-field="shot">`, `data-field="take"`, `data-field="avoid"`) and a vote |
| `site-cliches` | yes | the category's site clichés, as in `research/site-cliches.md`; non-empty |
| `none-of-these` | yes | the way out: research again |
| `my-call` | yes | `data-field="recommendation"` and `data-field="critique"` (and the judge panels when `data-judge="ran"`) |
| `questions` | yes | the same rules as every board; question 1 (which groups) is multi-pick: checkboxes in a question marked `data-multi="true"`, and the reply lists every ticked group |
| `reply` | yes | |

Hardest surface, directions, the positioning map, the strategy core, reflex lines, the incumbent "Today" and the kept masters are not asked of a references board; `--min-directions` is not used (an info row `directions:count` says so). The
`[[fill: ...]]` marker rule and `page:votes` apply as on every board (a group's vote is `<fieldset data-vote="<name>">`, its radios named `vote-<name>`).

| row | fails when |
|---|---|
| `site-refs:tier` | the tier is not `standard` or `full` ("the site work is Standard and Full") |
| `site-refs:brief` | `brief/BRIEF.md` does not list a site on its `Required surfaces:` line (the first such line, in any letter case, the label bold or not). The value is read against a word list in English and Polish: `site`, `website`, `microsite`, `web page`, `landing page`, `www`, `strona` (with its endings, never `strong`) and `witryna` (with its endings). A value wrapped in parentheses is the untouched line of the template, "(site, app icon, ...)", and does not count; a brief in another language needs the word `site` on that line. The detail names the line it read |
| `site-refs:g4` | G4 is not recorded ("website references come after the system rules (G4)") |
| `site-refs:research` | `site_research` in `BRAND-STATE.md` is `auto` or missing: the owner has not answered the online-research question (`state --set site_research=online\|links-only\|none`); each of the three answers passes, `none` included (the owner sends screenshots) |
| `site-refs:cliches-file` | `research/site-cliches.md` is missing, or holds fewer than three bullets under `## Avoid unless argued` that are not a placeholder such as `(...)` |
| `groups:count` | fewer than four groups count (a warning, never a failure, above six: "more than 6 is a menu, not a choice") |
| `group:<name>:name` | a group's `data-name` is not a word of three letters or more, is a label (`Option 2`, `Group B`, `Cluster 3`: the shared label words, and also `group`, `cluster`, `type`, `set`, `category`, `approach`, `pattern`, `layout`), or repeats another group's name in other letters. A group with no name is listed by its place (`group:#2:name`) |
| `group:<name>:idea` | the group has no non-empty `data-field="idea"` (one sentence: how these sites serve the visitor's job) |
| `group:<name>:references` | `data-field="references"` holds fewer than three `<li>`, or one of them lacks: a link `<a href="http(s)://...">` to the site (the first `<a href>` of the item is the site's: if it is not http(s), a later http link in the take or the caption does not stand in for it); a screenshot `<img data-field="shot">` that is an inlined `data:image/` URI with alt text, no `srcset`, in a `<figure>` with a non-empty `<figcaption>` (the rule of a style board's thumbnail, `thumb_problems` in `boardpage.py`; here the template's own ` · shown for private research` after the author's words is not a caption); a `data-field="take"` and a `data-field="avoid"` that hold words (the `Take:` and `Avoid:` the template puts inside the field are not words, so a field left with only its label, the bare word, or a dash or a dot after it is empty). The `<li>` counted are those of the list itself: a list inside a take or a why belongs to that item. The detail names each reference (by place and link text) and what it lacks |
| `group:<name>:layout` | only when the group declares `data-layout`: the value is neither an id of `skills/brand-creator/references/page-layouts.json` (the detail names the ids) nor `own:<word>` (lower case letters, digits and hyphens). `own:<word>` is a warning: "say in the idea why none of the references fits" |
| `group:<name>:shot:<k>` | never fails. One row per reference that has a screenshot (`k` is its place in the list). The picture's bytes (a `data:` URI decoded) must equal a `thumbs[].sha256` or a `views[].sha256` of a `research/site-refs/*/capture.json` whose `source.url` or `source.final_url` is the address the reference links to (compared with no fragment, one trailing slash dropped, scheme and host in lower case, and the default port of the scheme dropped: `:443` on https, `:80` on http); that passes. Anything else is a warning, "not matched to a capture of <address>: capture it (`brand-creator capture --url <address> --name <name>`), or say in the caption that the owner sent the screenshot", and the detail says whether the picture is a capture of another address, whether the address has a capture whose pictures this is not, or that there is none (and names a `capture.json` that could not be read) |
| `owner-sites:items` | an `<li>` of the owner-sites section (each is a site the owner named) whose `data-like` is not `like` or `dislike` (or is missing), that has neither an http(s) link nor an inlined image, or has no non-empty `data-field="why"`. A section with no `<li>` passes when it has text (the owner named none); an empty section fails `section:owner-sites` and has no items row |
| `images:inlined` | an `<img src>` or `srcset` anywhere on the board (a group's screenshots, a screenshot the owner sent) that is not an inlined `data:image/` URI: nothing on the page asks the network |

The `inputs` of the lint report are the page, `brief/BRIEF.md` and `research/site-cliches.md` when they exist, and every `research/site-refs/*/capture.json`, so a changed brief or cliché list, or a capture made again, makes the report stale (`check` then calls `board-lint` not verified). A `capture.json` that did not exist when the board was linted is not an input yet: lint again after a first capture.

### The site board (`data-board="site"`)

The site round makes reference pages for the brand's site: the home page's first screen first, as two or three variants (the hero stage, `data-site-stage="hero"`), then the other pages (the pages stage, `data-site-stage="pages"`). It runs in
the Standard and Full tiers, after G4 and after the owner's pick of website references (G4w, or their skip), and only when `brief/BRIEF.md` lists a site. It is a round from 2 on: `rounds/rN/board.html`, from `templates/site-board.html` (built on
the frame of `templates/motion-board.html`: the same tokens, header, hardest surface, My call, questions and reply). A site board is no pick, style, reset or rejected round: the map and the style-round logic, `reset_rounds`, the kept masters and the
style re-arming of a later pick board ignore it (the round "rejected" before a reset is never a site round), and a site board in round 0 or 1, or in a round listed in `reset_rounds`, fails `page:data-board` ("a site board is a round of its own
from round 2 on"). The page declares its stage on the element that declares its kind, the `<body>`: a missing stage, or one that is not `hero` or `pages`, fails `page:site-stage`, and no variant row is read then. Its rows are in
`scripts/boardlib/siteboard.py` (outside `scripts/lib/`, like `boardpage.py`).

One folder per variant of the hero stage, `rounds/rN/<name>/`, made before the page:

| in the folder | what it is |
|---|---|
| `index.html` | the home page's first screen, built from the picked references and the tokens. Its `<body>` declares `data-layout` (an id of `skills/brand-creator/references/page-layouts.json`, or `own:<word>`) and `data-page` (the page id: lowercase letters, digits and `-`, 2 to 32 characters, starting with a letter; `start` for the home page) |

One card per variant: an element with `data-site-variant="<name>"` (the `<article class="variant">` of the template). The name is a word of 3 or more letters that is not a label ("Variant 2" and "Option B" fail: the rule of direction names), unique
(capitals do not tell two apart), and also the name of the folder, so it keeps to letters, digits, `-` and `_`. Inside the card:

| in the card | what it holds |
|---|---|
| `<img data-field="still" data-view="1440-light\|1440-dark\|390-light\|390-dark">` | the four stills of the first screen, `<name>/shots/<view>.png` |
| `<a data-field="live" href="<name>/index.html">` | the live page, one click away (the board has no replay) |
| an element with `data-check="pass"` or `"fail"`, and its text | the check line: what `page-check` found for this variant |
| `data-field="what-it-is"`, `"from-refs"`, `"cost"` | What it is, Takes from (the group of the references board, or the owner's site, the structure comes from) and Cost, each with text |
| `data-field="tells"`, `data-field="reflex"` | the tells `page-check` found and what will be done about them, and the reflex line of the variant |
| `data-field="layout"` with `data-layout="<id>"` | the layout reference of the page, the same id the page declares |
| an element with `data-cold="ship"` or `"fix"`, and its text | the cold review's verdict |
| `<fieldset data-vote="<name>">` | the owner's vote, as on every board (the `page:votes` row); its radios are named `vote-<name>`, a group of their own per card |

The pictures are the project's own files by a relative path, read from the page's folder as a browser reads it, or, in the copy published on a review surface (`review/index.html`, linted with `--round N`), `data:` URIs of the same bytes. The first hero
board of a project (no earlier round has a site board at the same stage) shows 2 or 3 variants and needs no What changed and Weak points (info rows); a later one, the refine loop on the picked or combined variant, shows 1 or more and needs both,
as a refine board does from round 2. Hardest surface, My call, questions and reply are required as on every board; there is no `positioning-map`, `strategy-core`, `today`, `losers`, `none-of-these` or `direction` section, no `project:*` row and no
`masters:*` row, and `--min-directions` is not used (an info row says so). The pages stage is described after the rows (its page cards and choices). Each row below is one result for the whole board and names the variants it fails:

| row | fails when |
|---|---|
| `page:site-stage` | `data-site-stage` is missing or is not `hero` or `pages` |
| `site:tier` | the tier is not `standard` or `full` ("the site round is Standard and Full") |
| `site:brief` | `brief/BRIEF.md` does not list a site on its `Required surfaces:` line (the same word list and the same reading as `site-refs:brief`; the detail names the line it read) |
| `site:g4` | G4 is not recorded ("the site round comes after the system rules (G4)") |
| `site:g4w` | G4w is not recorded; or it names a pick (it is anything but `skipped by owner`, read after the date `state --record` writes before the decision) and no round before this one holds a website references board that counts (`boardpage.is_site_refs_board`: `data-board="site-refs"`, the round of its own folder, at least four groups with a name and content): "G4w names a pick but no website references board came before this round". A skip needs no references board |
| `site:variants` | the count (2 or 3 on the first hero board of a project, 1 or more on a later one) or a name (a word, not a label, a folder name, unique) |
| `site:files` | a variant has no folder, or one that is not spelt as the card spells it (an entry of `rounds/rN/` equal to the card's name, letter case included: a disk that does not tell letter cases apart, macOS or Windows, opens `ledger/` for the card `Ledger`, but the reports of `page-check` and `capture` are named after the page's path, so a card spelt otherwise never finds them; the row says the card and its folder must be spelt alike, on every kind of disk); no `index.html`; an `index.html` with no `<body>` tag, or whose `<body>` declares no `data-layout` or no `data-page`, or a `data-page` that is no page id; a card with no link to the live page, or one that does not lead to `<name>/index.html` |
| `site:layout` | the page's `data-layout` is missing, or is neither an id of `page-layouts.json` nor `own:<word>` (the detail lists the known ids); the card has no `data-field="layout"` line, or its `data-layout` differs from the page's. A layout of its own (`own:<word>`) is a warning, never a failure: "say on the card why none of the references fit" |
| `site:fields` | What it is, Takes from or Cost is missing, empty, a placeholder or still holds a `[[fill: ...]]` marker, in a card |
| `site:check` | a variant has no page-check report: `assets/_checks/<tool>.json` with `tool = pagecheck.report_tool("rounds/rN/<name>/index.html")` (`page-check/<slug>-<hash6>`, named after the page's path; `scripts/pagelib/pagecheck.py` owns the rule and the board imports it); the report is not that page's (its top-level `target` is not `{"kind": "project", "page": "rounds/rN/<name>/index.html"}`); it is stale (a file in its `inputs` is gone or changed, `_common.stale_inputs`, the rule `check` applies; or it does not list the page among them, so a change to the page would not show); its `status` is not `pass` or `fail` (`not-verified`: the detail quotes up to three of its rows that were not verified); the card has not exactly one check line (an element with `data-check`), its value is not `pass` or `fail`, it differs from the report's status, or it has no text. A failing check shown as `fail` is honest and passes the row. Every failure names `brand-creator page-check rounds/rN/<name>/index.html` |
| `site:tells` | a `warn` row `tell:<id>` of a variant's page-check report (`<id>` an id of `page-tells.json`; the row `tell:<id>` is a `pass` when none was found) is not named, by its id, on the card's `data-field="tells"` line: "show every tell page-check found, with what you will do about it". An id counts as named when no letter, digit or `-` touches it (`eyebrows` is not `eyebrow`). A `tell:<id>` warning with `hits: []` is page-check saying it could not check the page for that tell (no `lang`, a language with no word list, past the element cap), not that it found one: the card must still name it, and the message says page-check could not verify it ("show every tell page-check found or could not verify"), never that it found it. Other warnings of the report, and the `page:rule:<id>` row of a tell the owner adopted as a brand rule, are not read here. A variant whose report is missing, stale or no verdict is not judged: when nothing else fails the row is "not verified" (`skipped`, exit 3), and `site:check` says why |
| `site:stills` | `rounds/rN/<name>/shots/capture.json` (`brand-creator capture`) is missing or unreadable; it is not the capture of the variant's page (`source.page`); it is stale (a file in its `inputs` is gone or changed, or the page is not among them); it lists no sha256 for one of the four views `1440-light`, `1440-dark`, `390-light`, `390-dark`; the file it names for a view is not there or has other bytes than the listed sha256; the card has not exactly one `<img data-field="still">` per view (by `data-view`, and no other view), or the bytes of one of them are not the listed sha256: the project's file by a relative path read from the board's folder, or on the review copy a `data:` URI of the same bytes (an address, or a path outside the project, is no capture). Every failure names `brand-creator capture rounds/rN/<name>/index.html` |
| `site:<name>:reflex` | the card `<name>` has no reflex line (`data-field="reflex"`), or it is empty or a placeholder: the same required field as `direction:<name>:reflex` on a style board. A card with no line is no way round `site:<name>:reflex-count` or `site:reflex-shared`; it earns this failure alone and no other `site:<name>:reflex-*` row but `reflex-measured` |
| `site:<name>:reflex-format` | the reflex line of the card `<name>` (the first non-empty `data-field="reflex"`) is not `no hits` or one `hit: <id> \| <argument>` per hit (`near miss: <id> (<why>)` is allowed and never counted): free text, an empty line, a hit with no `\|` or no argument, text before the first marker, `no hits` together with a hit. A warning for now ("a failure from the next release"): the rule of `scripts/boardlib/reflex.py` (`reflex.parse`, `reflex.line_rows`), the same as on a style board's direction. |
| `site:<name>:reflex-ids` | a hit names no tell of `page-tells.json`, no id of `ai-defaults.json` (its layout items name the stock product page) and no item under "Avoid unless argued" of `research/site-cliches.md` (compared by `reflex.norm`: letter case, spaces and one trailing parenthetical do not matter). A warning for now. A pass says where each name comes from: `(page-tells)`, `(ai-defaults)` or `(cliches)`. A project with no cliché file says so ("no cliché of the category's sites can be named") |
| `site:<name>:reflex-count` | two or more hits on one card (near misses are not hits): "replace a part before showing it" |
| `site:<name>:reflex-grounded` | only for a card with an argued hit, and a warning for now: the argument shares no word of four letters or more with the owner's own words in `FACTS.md` and `brief/BRIEF.md` (`reflex.ground_words`); "NOT verified" when those hold no words of the owner's own |
| `site:<name>:reflex-measured` | a warning: the page-check report of the card's page has a `tell:<id>` warning that the reflex line neither hits nor names as a near miss ("page-check found <id>; argue it on the card or change the page"; a `tell:<id>` warning with `hits: []` reads "page-check could not verify <id>" instead, and asks the same). Not verified (`skipped`) for a card without a current page-check verdict (`site:check` says why). `site:tells` asks that the card name the tell; this row asks that the reflex line argue it |
| `site:reflex-shared` | every card has a reflex line and one pattern (`reflex.shared_hit`) is hit by all of them: the heroes are not divergent. An info row ("not required here") with fewer than two cards, or when a card has no line (`site:<name>:reflex` has failed then) |
| `site:refs` | G4w names a pick (not `skipped by owner`) and: it names none of the groups (`data-name`) of the references board, nor the text or the host of the link of a site the owner liked (`data-like="like"`; a disliked site is never a name) in its owner-sites section ("record the pick under their names"); or the `data-field="from-refs"` line of a card names none of those that the G4w record names (a whole word or whole words, any letter case): "take from what the owner picked (G4w)". The record is read up to the word `dislikes` (`picked <groups>; likes <...>; dislikes <...>`): a group or a site named after it is one the owner turned away from, and is no pick. An info row when G4w is `skipped by owner`; not verified (`skipped`) without a G4w, a references board to read the names from, or a variant card |
| `site:cold` | a hero has no `rounds/rN/<name>/cold-review.md`; its first non-empty line is not `verdict: ship` or `verdict: fix` (letter case and spacing do not matter); it has no `by:` line; its `inputs:` list is missing, holds a line that is not `- <path> sha256:<hex>`, lists a file twice or is not exactly the four stills of the variant (`rounds/rN/<name>/shots/<view>.png`), `brief/BRIEF.md` and `FACTS.md`; one of those files is missing or has another sha256 than the review lists ("the page or its stills changed after the cold review: review again", or the brief or the facts); it has more than five findings (numbered lines); the card has not exactly one `data-cold`, its value is not `ship` or `fix`, or it differs from the verdict. A `fix` shown as `fix` is honest and passes |

The `inputs` of the lint report are the page, `brief/BRIEF.md` when it exists, the website references board that G4w stands on (when it names a pick) and the `index.html` of each variant, so `check` calls the report stale ("not verified") as soon as one of
them changes.

The proof rows add to those inputs, for each variant: its page-check report, `shots/capture.json`, the four stills and the files named by `capture.json` for them, and every file the two records list as made from (the page, `tokens.css`, a stylesheet, a script; a page-check report also lists
`BRAND-STATE.md` by its G4 rules (the part `g4-rules`, see Reports), `qa/rules.json` and `FACTS.md`, and the lint keeps those records as they are: a changed G4 record or `(rule)` line makes the page-check reports, and with them this lint report, stale; recording G4p, G5 or G6 or setting the phase does not, unless a rule of the choices cites a line only `BRAND-STATE.md` holds: see `site:choices` below). Without a variant card the three rows are "not verified" (`skipped`); the fixtures of `tests/test_site_board.py` write the reports and the stills by hand, in the shape
`page-check` and `capture` give them, so the tests need no browser.

The cold review of a hero is the file `rounds/rN/<name>/cold-review.md`:

```text illustrative
verdict: ship
by: in-thread
inputs:
- rounds/r2/Ledger/shots/1440-light.png sha256:<hex>
- rounds/r2/Ledger/shots/1440-dark.png sha256:<hex>
- rounds/r2/Ledger/shots/390-light.png sha256:<hex>
- rounds/r2/Ledger/shots/390-dark.png sha256:<hex>
- brief/BRIEF.md sha256:<hex>
- FACTS.md sha256:<hex>

1. The finding that costs the visitor most, short enough for one line.
```

The reader sees only those six files, never the board, the references or the reasons (the prompt is in `skills/brand-creator/references/prompt-fragments.md`, **Review**). `by:` is `in-thread` (not blind: the same session that built the page reads it) or `agent`, and an agent
only after the fleet gate. The reflex, references and cold rows add to the inputs of the lint report: `FACTS.md`, `research/site-cliches.md` (when it exists) and the `cold-review.md` of each variant, so a changed fact, cliché or review makes it stale.

### The site board, pages stage (`data-site-stage="pages"`)

Once the owner picked a hero, the next site round shows the other pages. The same board, `templates/site-board.html`, with the three comments at its end put to use (the pages in place of the variants, the choices section, the two questions of the pages), and `<body data-round="N" data-board="site"
data-site-stage="pages" data-hero="<name>">`. The gates, `page:site-stage`, the sections (What changed and Weak points from the second pages board, Hardest surface, My call, questions and reply) and `--min-directions` are those of the hero stage; a pages board is the first of its own stage whatever came before.
One folder per page, `rounds/rN/<id>/`, made before the board, with the files of a variant's folder (`index.html` declaring `data-layout` and `data-page`, `shots/` from `brand-creator capture`; `cold-review.md` is optional). One card per page: an element with `data-site-page="<id>"` (the
`<article class="page">` of the template). The id is a page id, the pattern of `data-page` (`^[a-z][a-z0-9-]{1,31}$`: lowercase letters, digits and `-`, starting with a letter), unique, and also the name of the folder and what `<body data-page>` declares. The card holds what a variant's card holds
(four stills, the live link, the check line, What it is and Cost, the tells line, the layout line, the vote), except that **Takes from** (`data-field="from-refs"`) and the **cold line** (`data-cold`) are optional (a line that is there is filled in) and there is **no reflex line**: the hero carried the reflex test,
and a page is built from the hero, not from the references.

The choices section (`data-section="choices"`) lists every structural and visual choice the pages make, one `<li data-choice="c1" data-tag="rule|example" data-source="..." data-pages="start pricing">text</li>` each:

| attribute | what it holds |
|---|---|
| `data-choice` | the choice's id: `c` and a number (`c1`, `c2`), unique on the board |
| `data-tag` | `rule` (the owner decided it: it holds wherever the brand shows a site) or `example` (may change) |
| `data-source` | for a rule, where the owner decided it: text quoted from a line of `BRAND-STATE.md`, `DECISIONS.md` or a record under `decisions/*.md` (found there in any letter case, with white space collapsed; at least six characters). For an example, nothing |
| `data-pages` | optional: the page ids the choice applies to, separated by white space or commas, all of them on this board; left out, the choice applies to every page |

The rows of the pages stage (the gates and the sections above apply as well):

| row | fails when |
|---|---|
| `site:hero-first` | no round before this one holds a site board at the hero stage ("hero first: show the hero variants and record the owner's pick before the other pages"); the `<body>` that declares the kind has no `data-hero`; or `data-hero` is none of the variant cards (`data-site-variant`, spelt alike, letter case included) of a hero board in an earlier round (the latest board that holds the name is the one read; the detail lists the names it looked at). The hero board it found is an input of the lint report |
| `site:pages` | no page card; a page card whose `data-site-page` is not a page id, or is used twice; a page whose `<body data-page>` is not its card's id. A page whose folder or `index.html` is missing is `site:files`' to say |
| `site:files`, `site:layout`, `site:fields`, `site:check`, `site:tells`, `site:stills` | the rows of the hero stage (see above), one result each for the whole board, read for the page cards: the same folder, `index.html`, `<body>` declarations and live link (`rounds/rN/<id>/index.html`), the same layout line, the same page-check report and four stills; `site:fields` asks for What it is and Cost, and for Takes from only where a card has the line. Without a page card they are "not verified" (`skipped`, "there is no page card to look at (site:pages says why)") |
| `site:cold` | as at the hero stage, but only for a page that has a `cold-review.md` (or a card that claims one, which fails: "the card has a cold line (`data-cold`) but ... does not exist"): the file is held to the rules of a hero's, and the card's cold line says its verdict. No page with a review is an info row ("not required here") |
| `section:choices` | the page has no `data-section="choices"` element, or it is empty |
| `site:choices` | no item with `data-choice`; an id that is not `c` and a number, or is used twice; an item with no text; `data-tag` missing or neither `rule` nor `example`; a rule whose `data-source` is empty, is shorter than six characters, or is found in none of `BRAND-STATE.md`, `DECISIONS.md` and `decisions/*.md` ("a rule says where it was decided: record the owner's decision in DECISIONS.md, then cite it"); a `data-pages` that is empty, or names an id that is no page card of this board |

The `inputs` of the lint report add the `index.html` of each page, `DECISIONS.md` and `decisions/*.md` (a changed decision makes it stale) and the rest the proof rows add (see above). `BRAND-STATE.md` is searched for the choices too, and the page-check reports hold only its G4 rules, so the lint lists the whole file itself (a record without `part`) when a rule's `data-source` is found in it and in none of the other files: deleting or changing the cited line, or recording a gate, makes the lint stale, and linting again settles it (the finish chain lints the board of the latest round again). A source that `DECISIONS.md` or a record under `decisions/` holds too does not add the file: those are inputs already. A changed G4 record or `(rule)` line makes the lint stale through the page-check reports, as above.

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
drawn by the page; it says who made the pixels), `note`, `band` (see QA gates), `exemption` and `qa` (the gates the file needs, from downscale, states, motion, family, fonts, idempotent, print; `check` requires a
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
`board-lint` on the board of the latest round, `staleness --write`, `check`). `version --check` comes first: a session that still runs an older copy of the plugin than the one Claude Code
has installed (`installed_plugins.json` next to the plugin cache: a user install, or a project or local one for this folder) exits 1 there and
says to start a new session; a copy that is not in a plugin cache (a checkout) or a record that cannot be read is "not checked" (exit 0). The
chain runs `contrast --cvd` when `qa/rules.json` has a `cvd` section. The `board-lint` step is "The last lint" below (which board, and what an exit other than 0 does). It exports `BRAND_CREATOR_CHAIN=1`; a generator that rewrites a whole output folder calls `_common.require_chain()` and exits 1
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
 "page":      {"widths": [360, 390, 768, 1024, 1440, 1920], "display_min_px": 20, "clear_space": 0.25, "rules": []},
 "bands":     [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "assets/logo/mark.svg"}]}
```

`favicon.drawing` (empty by default) fixes the drawing of `icon.svg` (`emit web`); it must be an existing `.svg` in the
project (exit 2 otherwise) and pure vector (exit 1 otherwise), and so must its `-dark.svg` when there is one.

An unknown section or key, a value of the wrong type or a number at or below 0 exits 2: a typo never falls back to the proposal.
`page` is read by `page-check` (see Page check); `page.widths` is a non-empty list of different whole numbers from 200 to 4000, and `page.rules` is a list.
`page.rules` holds the brand's own rules for pages (see "Brand rules" under Page check). Each entry is `{"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"}`: `id`
(a lower-case slug, unique), `kind`, `g4` (a non-empty string of at most 500 characters: the words of a recorded "(rule)" line) and the keys of its kind. `max-marks-per-view`: `max`.
`max-words-per-control`: `max` and, optionally, `selector`. `words-under-accent`: `selector` and `min`, `max` or both. `tell`: `tell`, a non-empty string. `max` and `min` are whole numbers, 0 or more, and
`min` is not above `max`. An unknown kind, a key the kind does not have, a missing key, a repeated `id` or a value of the wrong type exits 2 (`qa_rules.validate_page_rules`).
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
  warns (default budget, owner-adjustable). The `licence:<font>` row also carries `family` (name ID 16, else name ID 1, else the file
  stem), `weight` (OS/2 `usWeightClass`, else 400) and `style` (`italic` when OS/2 `fsSelection` bit 0 or `head.macStyle` bit 1 is
  set, else `normal`); its status and detail do not depend on them.
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
- `component` (it proves how a component answers a hover, a press and, when the case lists `focus-visible`, the keyboard, for one line of G4): `page`, `selector` (the component's
  element), `rule` (a non-empty string: the G4 line the case proves; the report keeps it in `cases`, next to the case's `name` and `type`) and the optional keys `states` (different values from `hover`, `active` and `focus-visible`; default
  `["hover", "active"]`), `widths` (different whole numbers from 200 to 4000; default `[390, 1440]`) and `settle_ms` (default 300: how long the page is
  given after load). A missing or blank `page`, `selector` or `rule`, a bad value and any other key are a usage error (exit 2), raised before a browser
  starts; a `selector` that matches nothing is exit 2 as for a page case. There is no still: a component case compares no rest frame with a drawing. The
  page is loaded at each width (900 high), once with motion on and once with `prefers-reduced-motion: reduce` emulated, and the animations the page
  starts on load are finished before the first state. For each state the element is put into it with the real input: `hover` moves the pointer onto the
  element; `active` hovers it and then presses the mouse button (the button is let go over the element, and the click it ends in is cancelled, so no
  handler of the page runs and no link is followed); `focus-visible` presses a key and focuses the element, as the keyboard does. The row says so when
  the element does not match the state afterwards (another element covers it, it is hidden at that width, it cannot take focus). The Web Animations
  the input starts on the element or inside it (CSS transitions, CSS animations, `element.animate()`; a pseudo-element's included) are paused where
  they begin and stepped through the sample points of a page case (see `sampling` above), never waited for; the others the state starts elsewhere on the
  page stay where they began, and the row says how many. The state is then left (the pointer moved to a corner of the view the element is not in, or out of the view when the element fills it, which hovers
  nothing, and the `rest` row says so; the button let go; the element blurred) and what that starts is stepped through the same way. A report
  starts with `page:errors` only when it fails (the page did not load cleanly at the first width: a console or page error, a request to anything but
  the local server); it is no row of a state. Then come the rows of each state, in the order of the report:
  - `shift:<state>:<width>` (one per width): the **layout box** of the element and of every element after it, at its own level and at each level above
    it (what moves when the element grows), stays within 0.5 css px of where it was at rest, in position and in size, at every sample point of entering
    and of leaving; and no animation on the element or inside it is of a layout property (the list of `cls:normal`). The element's own `transform`,
    `translate`, `rotate` and `scale` are taken out of its box (a lift or a press by transform moves nothing), as long as they only move and scale it; an
    element they rotate, skew, flip or take into 3D is not measured while they do, and the row names it (the elements after it still are; with nothing
    left to measure the row is "not verified"). A failure names the box, how it moved or resized, how far and where in the motion
    (`button#b grew wider by 16 px (entering, at 100% = 160 ms)`); a state the element cannot be put into fails the row with the reason.
  - `tokens:<state>`: every duration and every easing of the animations the state starts on the element or inside it, on entering and on leaving, at every
    width, is a motion token of the built `assets/tokens/tokens.json` (`motion.durations_ms`; `motion.curves`, a named easing or `linear` compared as its
    four numbers). A transition's easing is its timing function, a CSS animation's is that of each interval between its keyframes, a script animation's
    both. Delays are not checked. The row names what is no token and the tokens there are. With no animation on the state it passes and says so. Without
    built tokens it is "not verified" (`skipped`) and names `brand-creator tokens`; the file is an input of the report, so a changed token makes it stale.
    It judges the widths the element could be put into the state at (the normal-motion run); when that is not every width, the row says `judged at
    1440 px only` and names the others, whose `shift` rows fail with the reason.
  - `reduced:<state>`: under reduced motion the state change starts no transition or animation on the element or inside it, on entering or on leaving, at any
    width (an animation that ended before the proof looked at it is still seen, from the browser's `transitionrun` and `animationstart` events). The row says
    how many there were at normal motion. A shorter animation is still an animation: it fails. The reduced-motion run has no `shift` row of its own, so a width the
    element could not be put into under reduced motion (another element covers it there, it is hidden there) is never left out in silence: when no animation was
    found at the other widths the row is "not verified" (`skipped`) and names each such width and why (`under reduced motion at 390 px: <reason>`), and when one
    was found it fails and names the width it could not judge beside it.
  - `rest:<state>`: after the state is left and its animations finished, the element and the elements after it are where they were before the state (0.5 css
    px), and the element no longer matches the state; a page that leaves a state behind fails here. Like `tokens` it judges the widths the element
    could be put into the state at, and says `judged at … only` when that is not all of them. When no corner of the view is outside the element (it fills
    the view) the pointer is moved out of the view, and the row names the widths where that happened.
  A state the element could not be put into at a width, in the normal-motion run, fails that width's `shift` row with the reason; the `tokens` and `rest` rows
  judge the other widths, and are "not verified" when there is none. Like the other cases it needs `brand-creator setup`; `frames` skips it (an info row), and the book lists its checks under `Case N`.
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

For each page case of a proof (or the named one; a states or component case is skipped with an info row, or a usage error when named) the page is seeked as
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
`motion/proof.json` does not exist ("motion/motion.json says the brand moves, but there is no proof of the approved move: write motion/proof.json"), fails when its report is current and failing ("the proof of the approved move fails: <the report's own row>; change the move as its failing rows say, then run `brand-creator shot --motion motion/proof.json`"; when another report of the same file passes, the row names it and says that one of the two may be left from before its folder was renamed by letter case, to be moved to `removed-<date>/`), and is "not verified" when it has no report, a stale one or one that cannot be read, which fails its own row but is no verdict on the move ("run `brand-creator shot --motion motion/proof.json`");
when the report of that proof is current and says not-verified, the row says why, as `board-lint` says it of a variant (one function, `motionboard.unverified_why`): it quotes up to three of the rows the report could not verify, each with its id and detail, and, only when one names
`requestAnimationFrame`, adds that such a move stays not verified however often the proof runs and says to write it as CSS animations, CSS transitions or `element.animate()`; the row of the report itself, `report:motion/<slug>-<hash6>`, quotes the same rows
(a stale report says it is stale, as for every report);
a failing gated report keeps its own fail row as well. With the tier `standard` or `full`, G3 recorded, G4 not and no `motion/motion.json`, `motion:decided` is an info row ("not decided yet; due before G4: ..."); before G3, and in Quick, there is no row.
A manifest row with `qa: [...]` needs a current, passing report from the matching tool (`downscale`, `states`, `motion`, `family`, `fonts`
= `fontcheck`, `idempotent` = `verify-idempotent`); for `downscale` it is the report of the row's own `downscale_source` (a row without one fails,
and a passing report on another file never counts); for `motion` it is at least one passing gated report (the `qa:motion` row; see Motion proof); a report that exists is gated whether or not a row asks (the `frames` reports too, by the proof each names; see Frames). A missing report is "not
verified" (exit 3), a stale one too, a failing one exit 1, and so is one that cannot be read: not JSON, or JSON that is no report (a list,
`"inputs": null`, an input with no path), its own failing row, never a crash. A report that `check` reads again after its own row passed (the
colour-vision rows of `contrast`, the output `book` recorded, the stills a `frames` report vouches for, the files `adapters` and `applied-skill`
wrote) gives a row that says what it lacks when it lacks it, never a crash. When `qa/rules.json` sets a colour-vision threshold (a key of its `cvd`
section), a passing contrast report without colour-vision rows (one `contrast` wrote without `--cvd`) is "not verified" too
(`report:contrast:cvd`, naming `contrast --cvd`). Slots off the band rule, platform-spec rows stamped stale or U, and
`tools/inputs.json` differences are gated or warned as described above.

Once G4 is recorded and `tokens/primitives.tokens.json` exists, `check` compares every token of it with the same path in the plugin's starter, `templates/tokens/primitives.tokens.json`
(`$value`, as canonical JSON; a key starting with `$` is not a group), and the row `tokens:starter` warns: "still the starter's proposal: <paths> (N); ask the owner to keep them (list them in
`$extensions["brand-creator"]["starter-kept"]` of tokens/primitives.tokens.json with the date and their words) or change them". The row's `left` lists those paths and `kept` the ones the owner kept. The owner keeps
a value by listing its path in `{"decided": "<YYYY-MM-DD> <the owner's words>", "paths": ["motion.quick", ...]}` under `starter-kept`; a path listed there is kept only while its value is still the starter's, and the row passes
("kept by the owner (<decided>): <paths> (N)") when every starter value left is kept. A `starter-kept` that is no object, whose `decided` is not a calendar date followed by words, or whose `paths` is not a list of
strings, keeps nothing and the same row warns and says what is wrong. Before G4, or with no primitives file, there is no row; the row is never a failure and never an exit 2 (an unreadable primitives file is a warning that it was
not compared; the `tokens` build is what fails it). `brand-creator tokens` skips `$extensions` of the primitives, so the entry changes no output.

## Page check

`brand-creator page-check` (`scripts/page_check.py`) opens one rendered page in Chromium at each width in each colour scheme, offline, and reports what it
finds. The browser only measures (`render.mjs page-measure`, with the in-page collectors of `scripts/pagelib/page_measure.mjs`, the one Chromium driver); the
judging is Python (`scripts/pagelib/pagecheck.py`) against the built tokens, `FACTS.md` and the `page` block of `qa/rules.json`.

```text
brand-creator page-check <page.html> [--project DIR] [--widths 360,390,...] [--schemes light,dark]
brand-creator page-check --from DIR <page.html> [--project DIR] ...
brand-creator page-check --url http://localhost:<port>/<path> [--project DIR] ...
```

- **Targets.** A page of the project (a path inside it). `--from DIR <page>`: a built site anywhere, the page written relative to DIR; DIR is copied into a new run
  folder `<data>/scratch/<project>/page-check/<hash6>/<n>/` (`n` is one more than the highest run folder there; `.git`, `node_modules` and symlinks are not
  copied) and the copy is served, so the site is only read; every run keeps its folder and nothing prunes them (the manual tells the owner that old ones can be deleted). `--url`: a page already served on this machine, `http` or `https` on `localhost`, `127.0.0.1` or
  `[::1]` and nothing else, the host written as one of the three (`127.1` or `2130706433` reach this machine and are refused all the same: both functions of the loopback
  rule read the host as written); a remote URL is a usage error (a remote page is built locally and given with `--from`).
- **Exit codes.** 2, with nothing written: no target, two target forms, a page that does not exist or is not a file inside the project (or inside DIR), a `--from`
  that is not a folder or holds more than 5000 files or 200 MB (the files and bytes that would be copied), a `--url` that is not a loopback URL, a width that is
  not a whole number from 200 to 4000 or listed twice, a scheme other than `light` or `dark`, a bad `qa/rules.json` `page` block, a `tell` rule that names no generic tell. 3: `assets/tokens/tokens.json` or `assets/tokens/tokens.css`
  missing (`brand-creator tokens`), `node` missing, `render.mjs` exiting 3 (setup missing, Chromium cannot start), or no view measured. 1: a row failed. 0: pass,
  warnings allowed.
- **Widths and schemes.** `--widths`, else `qa/rules.json` `page.widths`, else 360, 390, 768, 1024, 1440, 1920 css px; `--schemes`, else `light,dark`. One browser context per
  width and scheme, with the viewport height 800 at 360, 844 at 390, 1024 at 768, 768 at 1024, 900 at 1440, 1080 at 1920 and 900 at any other width; device scale 1; service workers
  blocked.
- **The request.** `page_check.py` writes `<data>/scratch/<project>/page-check/<slug>-<hash6>/request.json` and runs
  `node scripts/render.mjs page-measure --request <request.json> --out <measures.json> --project <project>`:

  ```json
  {"schema": 1, "root": "<the project, or a run folder of --from>", "page": "pages/index.html", "url": null,
   "widths": [390, 1440], "schemes": ["light", "dark"], "selectors": [], "rules": [{"id": "short-buttons", "kind": "max-words-per-control"}],
   "colours": ["oklch(0.52 0.12 185)"], "dsf": 1}
  ```

  `rules` (optional, default `[]`) are the brand rules whose facts the browser collects from the page's text (see "Brand rules"): `page_check.py` sends `{id, kind, selector?}` for each entry of `qa/rules.json`
  `page.rules` of kind `max-words-per-control` or `words-under-accent`, with the rule's `selector` when it names one (`selectors` then holds it too, once); a rule of any other kind asks the browser for nothing. Up to 200
  objects with a string `id` and `kind` and an optional non-empty string `selector`, else exit 2. The views then hold `rule_facts`.

  `colours` (optional) are CSS colours the browser is asked to render for the judge: `page_check.py` sends the modern values (`oklch()`, `oklab()`, `color()`) that
  `tokens.css` serves for the primitives. Up to 500 strings of up to 200 characters, else exit 2.

  Either `root` with `page` (served by the local server) or `url`, never both (exit 2). `root` must be the project or a folder inside `<data>/scratch/`; `page`
  must stay inside it; a `url` that is not a loopback URL is refused with exit 2 whatever `page_check.py` did (the second gate). `--out` must be outside the project.
- **The measurements** (`measures.json`, outside the project): `{"schema": 1, "chromium": "<version>", "target": {"kind", "page", "url"}, "views": [...]}`. A view is
  `{width, scheme, viewport: {width, height}, lang, height, errors, non_local, failed_local, resources, served, animations, ...collectors}`. `errors` are page and
  console errors; `non_local` the requests to another origin, which are recorded and aborted (a WebSocket: closed before it connects); `failed_local` the answers of 400 and above from the page's own origin;
  `resources` maps the path of every image and SVG file the page loaded from its own origin (the URL with its query, without its origin, which is left out because its
  port changes with every view) to `{sha256, content_type}` (the bytes of the response, so a mark can be compared byte for byte with its file); `served` the files the local server answered
  (empty for `--url`); `animations` what the settle step waited for or left running. A view that could not be rendered is `{width, scheme, viewport, error}`. The collectors add `document` (title, scroll and client width, scroll height) and `selectors`
  (for each selector the request names: how many elements match and the first visible boxes). The facts are never a verdict.
- **Redirects.** Chromium asks the route handler about the first URL of a redirect chain only, so `render.mjs` answers every request to the page's own origin itself:
  the answer is fetched without following redirects and the chain is walked hop by hop (GET) before the browser is given the first response. A hop to another origin is
  recorded in `non_local` and the request is aborted, so the other server is never asked; a chain of more than 10 hops is stopped and recorded in `failed_local`. A page
  that sends the browser to another origin (a redirect, a refresh, a script) cannot be measured: the navigation is aborted and the view is `{error}`, with `--url` too.
  Two checks stay behind: a redirect hop that went to another origin all the same (the server answered differently the second time) and a page that ends on another
  origin make the view `{error}` ("not stopped", "ended on"). One limit: the answer is fetched in full, so a response from the page's own origin that never ends (an
  event stream, a long poll) never reaches the page; the request waits up to 60 s and then fails.
- **WebSockets.** A route does not see a WebSocket, so `render.mjs` takes the page's own in hand: one to the page's own origin goes through (a dev server's hot reload);
  one to any other origin is recorded in `non_local` and closed before it connects, so that server hears nothing. A document `render.mjs` answers itself is taken by Chromium
  for a public one, and its local-network check would block even the page's own socket to this machine (`net::ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`, a console error
  that fails every view), so the page's own origin is granted the `local-network-access` permission. One exception: a WebSocket opened inside a worker is not intercepted,
  and connects to any host the machine can reach.
- **The report.** Tool `page-check/<slug>-<hash6>` (`assets/_checks/page-check/<slug>-<hash6>.json`), one per page: the slug is the page's file stem (for a URL, the stem of the last
  segment of its path), else `page`, and the hash is the first six hex of the sha256 of the ident, which is the project-relative posix path of a project page,
  `from:<real DIR>/<page>`, or `url:<URL>`. Inputs: `assets/tokens/tokens.json`, `assets/tokens/tokens.css`, `qa/rules.json`, `FACTS.md` and `BRAND-STATE.md` by its G4 rules (the part `g4-rules`: the G4 record and the recorded `(rule)` lines, the only things the check reads from it; see Reports) (when they exist) and, for a
  project page, the page and every project file the browser was served (`tokens.css` included), so a change to one makes the report stale; a `--from` or `--url`
  report lists the brand's files only. The report holds these keys at its top level: `target` (`{"kind": "project"|"from"|"url", "page", "from", "url"}`), `widths`,
  `schemes` and `measures` (the path of the measurements). `check` does not gate page-check reports.
- **Rows.** `page:target` (info): what was checked, the widths, schemes, Chromium version and where the thresholds came from. `page:load:<width>-<scheme>`: fails on a
  page or console error, an answer of 400 and above from the page's own origin, or (a project page or a built site) a request to another origin; with `--url` a request
  to another origin is a warning ("aborted: page-check runs offline"). A view that cannot be rendered fails its row. When no view was measured the row `page:load` is
  `skipped` and the exit code is 3. With `--url` only a file the page loads from another origin is a warning; a page that is itself sent to another origin fails its row.
- **Colour and text facts.** Every view of the measurements also holds `colours` and `texts`, collected over the elements that are shown: not `display: none` (nor inside
  one), not `content-visibility: hidden`, not the content of a closed `<details>` (the summary is shown), not cut to nothing (the visually hidden pattern for screen
  readers: `clip: rect(0 0 0 0)`, `clip-path: inset(50%)`, or `overflow: hidden` on a box 1 css px by 1 or less, or under 1 css px on the cut axis, such as a collapsed
  accordion; a hairline 1 css px high is still shown), not `visibility: hidden`, not fully transparent through `opacity`, and with a box that is not wholly above or left of the
  page's origin (it cannot be scrolled to). `script`, `style`, `template`, `option` and the contents of an SVG definition (`defs`, `symbol`, `clipPath`, a gradient, a
  pattern, a marker) are skipped. `colours` has one entry per distinct property, colour and alpha, `{sel, prop, hex, alpha, count, also}`: `sel` is the short selector of the first
  element (tag, id or the first two classes, `:nth-of-type`, at most four levels), `count` the number of elements and `also` the selectors of up to four more. The properties are
  `color` (an element with text of its own, an input's value or placeholder included), `background-color` (alpha above 0), `border-color` (all four sides alike) or
  `border-<side>-color` (a side with a width and a style other than none), `outline-color` (a drawn outline whose style is neither `none` nor `auto`),
  `text-decoration-color` (a line is drawn), `-webkit-text-fill-color` (when it differs from `color`) and `fill` and `stroke` of inline SVG shapes (`none` and a paint
  server, `url(#...)`, are not colours; a fill or stroke opacity of 0 paints nothing and is not read; a horizontal or vertical `line` or `path` has a box of no height
  or no width and is still read, for its stroke only: a `line` and a shape without an area have no fill; a `path` or `polyline` whose fill covers no point of a 24 by 24 grid
  over its box, a straight diagonal stroke, has no fill either, so its default black is not read). A computed colour in any form (`rgb()`, `oklch()`, `lab()`, `color()`) is read as sRGB `#rrggbb` plus the alpha from its text. `texts` has one
  entry per element with text of its own (an SVG `<text>` filled by a paint server, `url(#...)`, has `fg: null` and `fill_server: true`), `{sel, text (200 characters), fg, fg_alpha, opacity, ground, ground_kind, ground_sel, font_size_px, font_weight, font_family, rect,
  sample_label, lang}`: `fg` is the colour the glyphs are painted in (`null` and `fill_clear: true` when `-webkit-text-fill-color` is transparent, so the background paints them),
  `opacity` the product of the element's and its ancestors' opacities, `ground` what the text sits on and `ground_kind` is `colour` or `image`. The ground is the first
  ancestor-or-self with a background colour of alpha above 0; a see-through one is composited over what is behind it (`ground_layered: true`), a background image or gradient on
  the way makes it `image` (and `ground` null), and with nothing behind it the ground is the browser's canvas colour for the scheme (`ground_sel` is `(canvas)`).
  `sample_label` is the `data-sample` of the closest element that has one (`null` outside one; `""` when it is empty), `lang` the closest `lang`. Limits: pseudo-elements,
  iframes and shadow roots are not measured; the colours inside a gradient, a box or text shadow and `accent-color` are not read; a view holds at most 4000 texts, and
  `texts_total` says how many there were when it held more; `colours_unreadable` lists a colour the browser gave in a form that could not be read.
  An element and everything inside it is skipped when it is cut to nothing, an absolutely positioned descendant that is placed elsewhere included; the content of a closed
  `<details>` is skipped unless the page makes it visible (`checkVisibility()` is what is asked), and a fill thinner than a cell of the 24 by 24 grid is not seen.
  Also not read: an icon sprite (`<svg><use href="#id">`: `use` is not a shape and the contents of a `symbol` are skipped, so the sprite's colours are never checked);
  the ground of an SVG `<text>` is the first background colour among its ancestors (the `<svg>` element's own included), never the SVG shape it is drawn on, and its `fill-opacity` is not applied to `fg`; the
  `text-decoration-color` of an element whose text sits in a child element (`<a><span>...</span></a>`) is not read.
- **Colour rows.** `page:colours:<scheme>`, one per scheme over all widths. Fails when a colour the page paints is not the colour of a semantic role of that scheme in
  `tokens.json` `modes.<scheme>`: an opaque colour must equal an opaque role, a see-through colour (alpha under 1) a see-through role of the same colour and alpha (within
  0.01). A role is two colours, and a page colour that is either one is the role: the `hex` of `tokens.json` (what a page that uses the hex fallback paints) and the
  colour this browser renders for the role's modern value in `tokens.css`. The two differ when a token lies outside sRGB: `tokens.css` serves the real `oklch()` value,
  which the browser clips channel by channel, while the `hex` was gamut-mapped by chroma reduction (an `oklch(0.7 0.25 30)` is `#ff412d` in the browser and `#ff5843` in
  the hex: 23 units apart; the token build accepts such a token). The rendered colour is a fact of every view, `role_colours`: `{<css value>: "#rrggbb" | null}` for each of
  the request's `colours`, drawn on the same canvas as the colours of the page (`null`: the browser could not read it). The judge takes the value of a role from
  `tokens.css` through the `ref` of the role in `tokens.json`; a role with no modern value, or a view with no `role_colours`, is judged by the hex alone. Colours count as
  equal when no channel differs by more than 2 of 255: that absorbs a hand-typed copy of a token (a hex, or an `oklch()` with fewer digits) a unit or two off; a page made of
  the tokens matches exactly, in either form. The detail names up to six offenders, each with the selector, the property, the colour, the nearest role of the same kind with
  its OKLab distance (to the nearer of the role's two colours), and the first width it was seen at; the row holds them all in `offenders` and the number of distinct colours in `colours_seen`. Pass: the number of distinct
  colours, each a semantic colour of the theme. A colour that could not be read makes a pass a warning. `skipped` (not verified, exit 3 unless another row failed) when
  `tokens.json` holds no semantic colours for the scheme or no view of the scheme was measured (the `page:load` rows say why).
- **Pair rows.** `page:pairs:<scheme>`, one per scheme over all widths, judges each text's colour on its ground. A text whose colour and ground equal the two colours of a `pairs`
  entry of `tokens.json` in that scheme (the direction counts) passes, whatever the entry's `kind` and `min`: `contrast` is the check of the pair itself. Each of the two
  colours of an entry is its hex or the colour the browser renders for the role the entry names (`fg`, `bg`), as for the colour rows, so a pair of a token outside sRGB is
  still declared. Any other pair is
  measured: a ratio under 4.5:1 (3:1 for text of 24 px and up, or of 18.66 px and up at weight 700 or more) fails, a ratio above it warns "declare them in pairs". A see-through
  text colour, or text in an element that is faded through `opacity`, is measured as painted (composited over its ground) and is never a declared pair. Text over an image or gradient,
  text painted by its own background, and an SVG text filled by a paint server (`fill_server`), is "NOT verified" in a warning. Texts alike in colours, ground and floor are one entry (`texts` counts them, `also` names
  up to six more selectors). The row holds `texts_checked`, `declared` and the lists `failing`, `undeclared` and `over_image` (up to 100 each). Not checked: whether the
  `kind` of a declared pair suits the size of the text (an accent declared only for large text, `ui-text-large`, passes at 14 px), APCA and colour vision.
- **Motion facts.** Every view also holds `motion_decls`, `motion_unread` and `motion_smil`, from two walks. One is over every element of the page, hidden ones too (a menu that is closed now animates when it opens),
  and over the `::before` and `::after` of an element that generates them (`content` is not `none`): the computed style at rest. The other is over the style sheets' rules for a state, because a `:hover` rule matches nothing while the
  page is measured. `motion_decls` has one entry per distinct source, name, duration and easing,
  `{sel, source, name, duration_ms, easing, via, count, also, unset?}`. `source` is `transition` (the computed `transition-property`, `-duration` and `-timing-function`, paired the way CSS cycles a shorter list over the properties; `none` and a duration of 0 are no transition),
  `animation` (`animation-name`, `-duration`, `-timing-function` likewise; `duration_ms: null` is `auto` on a scroll or view timeline; `auto` on a time-based animation, a name and no duration, is 0 and is not listed) or `script` (a Web Animation no CSS declared).
  `via` is `style` (declared on an element: its computed style at rest), `state` or `running` (found in `document.getAnimations()` at rest: a script's, or a CSS one the walks did not see declared; its easing is the effect's, or that of
  each interval between its keyframes). A `state` entry comes from a rule of a style sheet whose selector names `:hover`, `:active`, `:focus`, `:focus-visible`, `:focus-within`, `:checked`, `:target`, `:disabled`, `:open`, `:popover-open`,
  `:modal`, `:fullscreen`, `:invalid`, `:user-invalid`, `:indeterminate` or `:placeholder-shown`, nested rules included, and the declarations written after a nested rule, which belong to the rule that holds it (`sel` is the rule's selector, a nested one written out with its parent's; `count` is the number of rules with the same values).
  The walk reads the document's style sheets, its `adoptedStyleSheets` and the sheets it `@import`s, and goes into `@layer`, `@container`, `@scope` and CSS nesting; an `@media` rule counts when it matches the view or asks about `hover` or `pointer`
  (the measuring browser's own input says nothing of the visitor's), an `@supports` rule when the browser supports its condition. The values are what the browser computes for the rule's declarations on a probe element that is not rendered, put
  inside the first element the rule styles when there is one, so `var()` and a custom property of that element resolve; the probe is taken out again, and a rule counts whether or not an element on the page matches it. A rule that sets only a duration or
  only an easing is judged on that part: `unset` then lists `duration` and `easing`, whichever it leaves to the rule at rest, and that key is absent. A state declaration with the same values as one read at rest is not listed twice.
  A running CSS animation or transition with the same source, name, duration and easing as a declared one is not listed twice.
  `motion_total` is set when there were more than 500 distinct entries; `motion_unread` is the number of style sheets the browser did not let the walk read (from another origin); `motion_smil` is the number of SVG SMIL animation elements (`animate`,
  `animateTransform`, `animateMotion`), which are counted and not read. Not seen: motion a script starts on a user's input, or one driven by `requestAnimationFrame`; motion in a rule that is not for a state and matches nothing now (a class a
  script adds, `[aria-expanded="true"]`); a rule inside a shadow tree.
- **Motion row.** `page:motion`, once over all widths and schemes. Fails when a non-zero duration is not a duration token (`tokens.json` `motion.durations_ms`, within 0.001 ms) or an
  easing is not a curve token (`motion.curves`, within 0.00001): a keyword (`ease`, `ease-in`, `ease-out`, `ease-in-out`, `linear`) is the curve CSS defines for it and counts
  only when a token holds the same four numbers; `steps()`, `step-start` and `linear()` never do. A `state` entry that leaves its duration or its easing to the rule at rest is judged on the other part alone. The detail names up to six declarations, each with the selector
  (the rule's, for a state), what is wrong and the first width it was seen at, and the row holds `declarations`, `offenders`, `used` (the tokens the page uses) and `durations_checked`. A page that moves while
  `tokens.json` holds no duration and no curve fails and says so ("the page moves ... while the brand has no motion tokens"); a page that does not move passes. A scroll-driven animation (no
  duration), a style sheet the browser would not let the walk read (`motion_unread`: the states it declares are not seen) and SVG SMIL animations are "NOT verified": a warning unless something fails. `skipped` when no view was measured.
- **Claim facts.** Every view also holds `claim_text` and `samples`. `claim_text` is the visible text of the page in runs, `{sel, text, sample_label, lang}`: a run is the text of one
  block, the nearest ancestor that is not `inline` or `inline-block`, so `€<b>5</b>` reads `€5` and a `<br>` is a break; it is cut where a `data-sample` begins or ends, so a sample is a
  run of its own. `sample_label` is the value of the closest `data-sample` (`null` outside one, `""` when empty) and `lang` the closest `lang` (`""` for none: the document's is the view's
  `lang`). Elements that are not shown are left out (`display: none`, a closed `<details>`, cut to nothing); an element with `opacity: 0` is kept, because a block that fades in
  is still content. At most 3000 runs of 4000 characters per view (`claim_text_total` says when there were more). Attributes (`alt`, `title`, `aria-label`, `placeholder`, and the `value` of an `<input>`, so a button written `<input type="submit" value="Buy 48 zł">`), the text of an `<option>`, `<optgroup>` and `<datalist>`, the
  document title and pseudo-element text are not read. `samples` is every shown `[data-sample]` element, `{sel, label, text (200 characters)}`. Every view also holds `claim_h1`, the text of each shown `<h1>` (at most 20, 300 characters each), which the claims row reads together with the view's `document.title` for one thing only, the status code of an error page (below). Text inside a shadow root is not read by the claims collector (it walks child nodes, which never enter a shadow root), as for colours and fonts.
- **Claim rows.** `page:claims`, once over all widths and schemes, reads `claim_text` outside a non-empty `data-sample` and fails on (1) a number no `FACTS.md` value holds: the
  table's `value` cells, a row labelled `(example ...` left out. A claim is a number of two digits or more (`1.5` has two), or a single digit next to `%`, a currency sign or
  code (`€`, `$`, `£`, `zł`, `PLN`, `EUR`, `USD`, `GBP`, `CHF`: a sign before the number or after it, with or without a space, so `€5`, `5€` and `9 €`; a code before or after it, so `PLN 5` and `5 PLN`) or a unit (`mln`, `mld`, `tys.`, `km`, `kg`, `mm`, `cm`, `ml`, `min`, `ms`, `px`, `GB`, `MB`, `KB`, `TB`, and, written right against the number, `k`, `m`, `g`, `l`, `h`, `s`, `x`);
  a bare single digit (a step label) is not a claim, and neither is a digit written against letters (`mp3`, `A4`, `3rd`) or in a dotted version. Numbers are compared as numbers
  (`1 200`, `1,200`, `1.200` and `1200` are one; `12,5` and `12.50` are `12.5`; with both signs the last is the decimal point, so `100.000,50`, `100,000.50` and `100 000,50` are `100000.5`); a date is its numbers, in both forms: `2026-10-17` and `17.10.2026` need `2026`, `10` and `17` in the facts (a day or month with or without its leading `0` is one number: `5.11.2026` is backed by `2026-11-05`), and a dotted `17.10` (day 1 to 31, month 1 to 12, two digits each: `30.10`, `05.11`) needs `17` and `10`, or the decimal `17.1` that it also reads as; a dotted date with a year (`1.5.2026`, and glued as `17.10.2026r.` or `1.5.2026r.`) may have one digit in its day or month; `12.5`, `2.10` and `10.1`, a day or month of one digit and no year, are decimals only, on the page and in the facts, and so is a dotted number with a currency sign, code or unit (`4.5 kg`). A date written with a month name is one date, read only in a block whose language is `pl` or `en` (another language, or none, keeps its numbers): Polish `21 października 2026`, `21 października`, and a month with a year in the nominative, genitive or locative (`Październik 2026`, `w październiku 2026`) in any letter case; English `October 21, 2026`, `October 21st`, `21 October 2026`, `21 October`, `October 2026`, the month with a capital letter or in capitals (a lower-case `may` or `march` is a word), the abbreviated `Oct` not read. A day is part of a month-name date only when no number runs past it: a day followed by `%` (`March 15% of users` holds the percent `15%`, not the date March 15), or by a digit glued with `.` or `,` (`May 3.5 kg`, `October 12,5`, `March 15.11.2026`, a dotted date), is a number of its own, while a day followed by a comma and a four-digit year, with a space after the comma or without, is the full date (`October 21,2026` is `October 21, 2026`). After a day only the genitive of a Polish month makes a date: `21 październik` and `21 październiku` are the number `21`. It is one number of the check, a claim whatever the digits of its day, listed as written (`22 października 2026`), and backed as a dotted date is, by its day, month number and year (`premiera 2026-10-21` backs every form above); a month-name date in a `FACTS.md` value (the names of both languages) backs the other forms the same way. Digits grouped by spaces (a no-break space too) are one number only when the first group has 1 to 3 digits and each later group exactly 3, so `13 205,20 zł` is `13205.2` and `In 2026 200 tools` holds `2026` and `200`. Two numbers are never claims: a year of 19xx or 20xx right after a copyright sign (`©`, `(c)`) or the word `copyright` in any letter case, or after such a year and a dash (`© 2024–2026`), and the status code of an error page, a bare number from 400 to 599 (no sign, code or unit). A page is an error page when its file name without the extension is such a code (`404.html`, `500.html`; for `--url`, the last segment of the path), or its `<title>` or one of its shown `<h1>` holds one as the only number of that text, with no `+` before or after it (every number counts there: a single digit and a copyright year too) and the same text holds an error word of the page's language, the document's `lang` (`pagecheck.ERROR_WORDS`, whole words in any letter case: English `error`, `not found`, `forbidden`, `unauthorized`, `unavailable`, `gone`, `bad request`, `server error`; Polish `błąd`, `nie znaleziono`, `nie istnieje`, `brak dostępu`, `odmowa dostępu`, `niedostępna`, `niedostępny`): `Błąd 404 | Acme`, `404 · Nie znaleziono` and `Błąd 404 – strona nie istnieje` do on a Polish page and `Error 500` on an English one; a count in a heading (`Ponad 400 projektów`, `Zaufało nam 500 firm`, `Over 400 clients`), `500+ firm nam ufa`, `+500 klientów`, `5 lat, 500 klientów`, `Error 500 (1 of 3)`, `404 or 500` and `Acme 2026 – Błąd 404` do not, nor does an error word of the other listed language. A page in any other language, or one that sets no `lang`, is an error page by its file name only. On an error page that code is no claim anywhere on the page, a small `Błąd 404` label and a large `404` alike, and only that code: `500` still is. Phone numbers, postal codes and street numbers are claims and need a fact or a `data-sample`. (2) A status word no
  `FACTS.md` value contains (as a lower-case substring, as `book-lint`'s `words:status`): English from `bookdata.LINT_DEFAULTS["status_words"]`, Polish from `pagecheck.STATUS_WORDS_PL`
  (`wkrótce`, `dostępne`, `dostępny`, `dostępna`, `w przygotowaniu`, `w budowie`, `premiera`, `przedsprzedaż`, `nowość`), whole words in any letter case; the Polish list applies to text
  whose language is Polish. (3) A `data-sample` whose label is empty or white space ("label the sample"). The language of a run is its closest `lang`, else the document's; any other than
  English or Polish, or none, adds "status words NOT verified for <lang>" (the numbers are still checked): a warning unless something fails. The row holds `claims_checked`, `unbacked_numbers`,
  `unbacked_status_words`, `unlabelled_samples` and `languages`. A block of text is judged and counted once however many views show it (the same selector, text and language), and a finding names the first view that has it: at the
  default 6 widths and 2 schemes `claims_checked` and the pass detail count the numbers of the page, not 12 times as many. `skipped` when no view was measured.
  `page:samples` (info, only when the page has a labelled sample) lists each one with its label, an excerpt, its selector and the first view it was seen in, `<width>-<scheme>`: the
  before-publishing list. The report also holds it at its top level as `samples`, `[{label, text, selector, view}]` (always present, `[]` when there is none); a sample on the page
  is never a failure, and must be replaced with real content before the page is published. Convention: `data-sample="<what it stands for>"` on any element marks sample content; its text,
  and the text of everything inside it that has no `data-sample` of its own, is not checked as a claim.
- **Mark facts.** Every view also holds `marks` and `images`, collected over the same shown elements. A mark is an element with `data-brand-mark`, or an image whose file name says
  it is the logo: the name without its extension (its stem) is `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more, in any case (`logo.svg`, `mark.svg`, `wordmark.svg`,
  `logo@2x.png`, `mark-dark.svg`, `Wordmark_light.svg`). `mark` is also a person's name, and both are ordinary words (a team page holds photos of people named Mark), so they make a candidate
  by name only for an `.svg` file: `mark.svg` and `wordmark-dark.svg` are candidates, `mark.jpg`, `Mark.png`, `mark-kowalski.jpg` and `wordmark.png` are not; `logo` makes one for any image type
  (`logo.jpg`, `logo@2x.png`). A stem that only holds one of the words (`partner-logo.svg`, `ikona-logowanie.svg`, `logos.png`, `bookmark.svg`, `marker.svg`, `market-chart.png`)
  or says something else (`site-mark.svg`, `lockup.svg`) is not a mark by its name, and a `data:` URL has no file name. A name only makes an image a candidate: the image is then judged as any mark
  is, so a `mark.svg` that is no logo file of the project fails `page:mark-file`. Any other image is a
  mark only by its bytes (equal to a logo file of the project: a `mark.png` that is one is found, whatever its name) or by `data-brand-mark`, which is also how a logo under another name opts in. The images are an `img` (what the browser chose to show, `currentSrc`, so the `source` of a `picture` is covered; `kind: "picture"` then), an SVG `image`, a CSS
  `background-image` of an element and of its `::before` and `::after`, and an inline `<svg>` that has `data-brand-mark` (`kind: "inline-svg"`). **`data-brand-mark` convention:** put it
  on the `<img>` or the inline `<svg>` of the brand mark; its value may name the logo file the mark shows (`data-brand-mark="assets/logo/mark.svg"`), or be empty. On any other
  element it stands for the images inside it, and an element with none is reported as `kind: "other"`. `marks` holds the marked and the named ones, shown or not (`visible: false`, so a logo hidden at one width is known; up to 100 a view, `marks_total` says how
  many there were when more; a mark over the cap is not measured), `images` the other visible images (up to 300; `images_total`): `pagecheck.identified_marks(view, hashes)` is the one place that decides what a
  mark is, and it promotes an image of `images` whose bytes equal a logo file of the project (the node side hashed it, see `resources`). An entry is `{sel, kind, url, own, declared,
  named, marked, visible, rect, nearest_px, nearest_sel, nearest_text}` plus `sha256` (a `data:` image, hashed in the page), `svg_markup` (an inline SVG serialised as XML, up to
  60,000 characters, `svg_truncated: true` beyond) and `pseudo` with `height_px` (a pseudo-element has no box to read: `rect` is null and `height_px` is its computed height when that is a
  length). `url` of a file of the page's own origin is its path with the query, the key of `resources`, and `own` is true; `declared` is the value of `data-brand-mark` (null when
  the attribute is not on or above the element); `visible` says it is shown; `rect` is the box in page css px. `nearest_px` is the gap to the nearest other box that is shown: a line
  of text, an `img`, a `canvas`, a `video` or an outer `svg`, none of them the mark, inside it or (a drawing) holding it; the text of an element that holds the mark counts. The gap is
  the larger of the horizontal and the vertical distance between the two boxes (0 when they touch or overlap), because the clear space is a margin round the mark; null when nothing
  else is on the page. Not measured: an inline `<svg>` that is a mark without `data-brand-mark` (and one that draws through `<use>` is compared as written: the drawing it points to is not followed, so it is "NOT verified" in a warning when it matches no logo file), an `<object>` or `<embed>`, `mask-image`, `border-image` and `list-style-image`, the box of
  a pseudo-element, and the size a background is drawn at (`background-size`): a background mark is measured by its element's box.
- **Mark rows.** Only a shown mark is judged (not `display: none`, hidden, transparent or off the page). `page:mark-file`, over all views: fails a mark whose bytes equal no file of
  `assets/logo/` and no drawing `qa/rules.json` names (`bands`, `favicon.drawing`, `marks.<id>.bands` and `marks.<id>.favicon`, each with its `-dark.svg` twin). An inline SVG is
  compared after canonicalisation (`pagecheck.canonical_svg`) with every SVG of that set, and the detail says so: namespaces and prefixes dropped, attributes sorted, white space
  collapsed (so a space at the edge of a run of text is not told apart), comments and the `title`, `desc` and `metadata` elements left out, and on the root `<svg>` also `width`, `height`, `class`, `style`, `id`, `role`, `focusable`, `tabindex`,
  `aria-*` and `data-*` (how a page sizes, styles and labels its copy); the `viewBox` and everything inside the root must be the same, in the same order, with the text that
  follows a child element (`Ac<tspan>m</tspan>e`) as much a part of it as the text before. The root's `style` and `class` are not compared at all, and a recolour through them (or
  through the page's CSS) is not caught here: `page:colours` still fails a colour that is no token colour, but not a swap to another token colour; the same colour as a `fill` attribute
  on the root fails here. A `data-brand-mark` value names the file the mark shows: the mark must be that file or its twin,
  and a name that is no logo file of the project fails. A mark whose bytes were not seen (its file is on another
  origin, aborted, or was reached through a redirect), and an inline SVG that draws through `<use>` and matches no logo file, is "NOT verified" in a warning. With no logo file in the project the row is `skipped`; with no shown mark it is `info` and says
  what counts as a mark, so a page with a logo the check cannot recognise is not passed in silence. `page:mark-band`, only for a page with a verified mark (`info` when `qa/rules.json` lists no
  bands): fails a banded drawing (a file a band names, or its `-dark.svg` twin, in either theme, because a dark header on a light page shows the twin) that is not the drawing
  `qa_rules.pick_band` names for the mark's rendered height, its box height rounded to a whole pixel; with `marks`, a mark is judged by the bands that name its file (a band's drawing is read as the project's path: `./assets/logo/x.svg` and a symlink are the file they lead to). A wordmark or a
  lockup is in no band and is not judged (`info` when no mark on the page is a banded drawing); a mark whose box cannot be read is "NOT verified". `page:mark-clear-space`: fails a mark
  with another box nearer than `page.clear_space` (0.25 until `qa/rules.json` sets it, and the row says it is a proposal) x its rendered height. The rows hold their offenders (up
  to 100), each with where it was first seen. Once a view was measured the logo files are inputs of the report, whether or not a mark is shown (a logo is found by its bytes, so even "no mark shown" rests on them), so a changed
  logo file makes it stale. `check` does not gate them.
- **Font facts.** Every view also holds `font_faces` and `font_usage`, collected after `document.fonts.ready` over the shown elements of the colour facts (an input's value or
  placeholder is a text; `display: contents`, `visibility: hidden` and what is not shown are not). `font_faces`: every `FontFace` of `document.fonts`,
  `{family, weight, style, stretch, unicode_range, status}`, the family with its quotes taken off and the status `unloaded` (declared and not needed yet), `loading`,
  `loaded` or `error` (at most 200; `font_faces_total` says how many there were). `font_usage`: one entry per distinct first family, weight and style of the computed
  `font-family` of a text, in document order, `{family, weight, style, stack, count, sel, min_px, min_sel, min_text, platform}`. `family` is the first family of the computed
  list with its quotes taken off (a comma inside quotes does not end it) and `stack` the whole computed list; `count` the elements; `min_px` the smallest computed font size
  of the entry's elements, `min_sel` that element and `min_text` the start of its text. `sel` is the one element the browser is asked about, the probe. CDP
  `CSS.getPlatformFontsForNode` answers for an element AND everything inside it (an inline `<code>` in a paragraph, a `<strong>`, a hidden span), so the probe is the element of
  the entry with the fewest elements inside it that draw text of their own in another family, weight or style (none, where the page has one such element), then the one whose own
  text holds the most different characters, the first on a tie; a text area comes last, because the debugger has no answer for one. When the probe still holds such elements,
  the fonts of each (the outermost ones; what they hold is theirs) are asked the same way and taken off its answer, glyph for glyph, and `inline_other` says how many. `platform`
  is that answer, as `render.mjs fonts` asks it: `[{family, postscript, custom, glyphs}]`, `custom` true for a web font (an `@font-face` of the page), `family` the name inside
  the font file (it can differ from the name the CSS gives the face) and `glyphs` how many glyphs of the probe's own text were drawn in it. `platform_error` replaces `platform`
  when the debugger could not answer, and when it cannot be asked for the probe: the entry's only element is a text area; the probe holds more than 12 elements in other fonts; one
  of them is `display: contents`, which has no box of its own to ask about. The view does not fail. The elements are marked `data-bc-font-probe` while they are asked (a mark is
  a word of a list: one element can be the probe of one entry and inside the probe of another), and the marks are taken off again whatever the debugger said. At most 60 entries
  per view (`font_usage_total` says how many there were). Not measured: text in pseudo-elements, iframes and shadow roots, and a fallback glyph in an element that is not the
  entry's probe.
- **Font rows.** `page:fonts` (one row for all widths and both schemes) judges every view and reports each distinct first family, weight and style once, at the first width and scheme where
  it went wrong (a later view that breaks what an earlier one passed is still caught). The families the brand names are those of every `font.*` stack in `tokens.json` `other` (quotes taken off, names compared
  without case; `var(--font-x)` is followed; a `font.*` token that holds a size or number is no stack). Fails: (1) a first family no stack names, a generic family
  (`serif`, `monospace`, `system-ui`, `ui-sans-serif` ...) included unless a stack writes it, so a page that sets no `font-family` and is drawn in the browser's default
  fails; (2) a named family that the browser did not draw the text in. A family the page declares with `@font-face`, and any named family that is neither generic nor an alias,
  must show in `platform` as an installed font of that name, or as a web font AND the page declares that family with at least one face `loaded`: a web font in the answer
  for a family that is not declared, or whose faces all failed or never loaded, is the fallback of its stack (often the body face), not the family's own face. So a face that
  did not load (`error`), a family the page does not declare and the machine does not have ("on this machine": the answer depends on the fonts installed where the check runs),
  or faces that cover none of the text, fail the row whatever else the stack fell to, and the detail names what Chromium used instead. A generic family, or a browser alias
  (`-apple-system`, `BlinkMacSystemFont`: the operating system's interface font, no font of that name exists), that a stack names and the page does not declare is the
  browser's own font and is not asked for. A system face (`Segoe UI`, `Roboto`, `Cantarell`, `Ubuntu`, `Noto Sans`, `Helvetica Neue`, `Helvetica`, `Arial`: faces some
  operating systems ship, several also brand web fonts) that a stack names and the page does not declare is asked for like any other family, but where this machine has no
  installed font of that name the answer is "NOT verified" in a warning that names what Chromium used, never a pass and never a failure (the stack is meant to fall through to
  its next family). Not checked: which face of a family the text needed (a family with one face `loaded` counts as drawn, so a bold face that failed while the regular one
  loaded, with the text falling to another web font, is not told apart). A warning: a text of which only some glyphs are drawn in another font (the face lacks a character the text uses: `3 of 38 glyph(s)`; `fontcheck --lang` is the check of
  coverage), a system face this machine does not have, a debugger that could not answer or reported no font, or a probe it cannot be asked about ("NOT verified"), and a view cut at 60 fonts. `skipped` (not verified, exit 3 unless another row failed) when the
  tokens name no font family or no view was measured. Pass: the number of fonts and their families. The row holds `fonts` (family, weight, style, selector, elements, platform;
  up to 100), `offenders` (each with `kind` `not-named` or `not-loaded`, and the `faces` statuses), `partly` and `token_families`.
  `page:display-size` holds the text set in the first family of the `font.display` token to `qa/rules.json` `page.display_min_px` css px (the computed font size; 20 is the
  proposal, and the detail says "a proposal" and the row `proposal: true` until the project sets the key): any text under it fails, naming up to six with the width and scheme.
  Pass when every text in the face is at least that size, or when the page sets none in it. Info: no `font.display` token, or a display face that is also the first family of
  another font token (the body face), whose text cannot be told from body text, so no size is held to it. The row holds `display_face`, `minimum_px`, `proposal`,
  `smallest_px` and `small`.
- **Brand rules.** `qa/rules.json` `page.rules` (validated as above) are the owner's own rules for pages. Each is tied by its `g4` words to a "(rule)" line of BRAND-STATE.md "Rules (G4)": the system
  rules the owner approves at G4 stay the one place a rule is decided, and a page rule only enforces one of them. Three kinds are measured:
  - `max-marks-per-view` (`max`): the most identified brand marks (the marks `page:mark-file` judges: `data-brand-mark`, an image named `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more (`mark` and `wordmark` only for an `.svg` file), or an image with the bytes of a logo file; only a shown
    mark) in one screen, over every width and scheme. A screen is a window one viewport high; the windows start at the top of the page and every half a viewport down, the last one reaching the end of the
    page. A mark is in a window when the vertical middle of its box is, and one box found two ways counts once. It needs nothing from the browser beyond the marks every view holds. Not seen: a mark
    that is `position: fixed` or `sticky` is placed where it is at rest at the top of the page, and two marks more than half a viewport apart are in one window only if a window starts between them; a
    pseudo-element mark has no box to place and is reported "NOT verified".
  - `max-words-per-control` (`max`, optional `selector`): no shown control says more words than `max`. A control is a `button`, a `[role=button]`, an `input[type=submit]`, `[type=button]` or `[type=reset]`,
    or an element the rule's `selector` matches. Its words are those of its visible text (`innerText`; the value of an input) and, when it shows none, of its accessible name (`aria-label`,
    `aria-labelledby`, the `alt` of an image or `<title>` of an SVG inside it, `title`).
  - `words-under-accent` (`selector`, `min` and/or `max`): for each shown element the `selector` matches, the words of its parent's visible text minus the words of its own are within `min` and `max`.
  - A word is what Unicode word segmentation (`Intl.Segmenter`, UAX #29, in the language of the closest `lang`, the browser's own when it does not know that one) calls word-like: a number is one word, an apostrophe inside a word does not split it, a
    hyphen does (`e-mail` is two), and an arrow, a dot or a symbol is none. A `tell` rule names one of the generic tells below; its row is judged from the same candidates (see "Tell rows").
- **Rule facts.** `page_check.py` sends the selectors the rules name, once each and in the order of the rules, in the request's `selectors` (so every view also holds their `selectors` boxes), and one
  `{id, kind, selector?}` per rule measured in the page's text in `rules` (an optional list of up to 200; `render.mjs` refuses anything else with exit 2). A request with no rule asks for nothing and the
  views hold no `rule_facts`. Otherwise every view also holds `rule_facts`: `{<id>: {kind, selector, matched, shown, items}}`, or `{kind, selector, error}` when the browser does not take the selector as CSS.
  For `max-words-per-control`, `items` are `{sel, text (80 characters), words, via}` (`via`: `text`, `name` or `none`), the longest first and at most 300, `matched` the elements found and `shown` those
  with a box; a control that is `display: none`, cut to nothing, `visibility: hidden` or fully transparent has no words to count and is left out. For `words-under-accent`, `items` are `{sel, parent_sel, text,
  parent_text, own_words, parent_words, around_words}` in document order, at most 300. Nothing is judged in the browser.
- **Rule rows.** `page:rule:<id>`, one per entry of `page.rules` in its order, none when there are none. A rule that holds passes, and its detail says whether it is a recorded G4 rule. A rule that is broken
  fails when G4 is recorded in BRAND-STATE.md and one recorded "(rule)" line (`adapt.view(project)["rules"]`, the list the adapters read: a "(rule)" bullet of "Rules (G4)", the template's `(...)` placeholder
  left out) holds the rule's `g4` words, white space collapsed and letter case ignored. The words must be a meaningful part of the line: the whole line (the "(rule)" marker may be left out) or a run of its whole words with at least two content words
  (English and Polish function words such as `a`, `the`, `per`, `w` and `na` do not count; a piece of a longer word is not a word of the line), so `rule` (the marker of every line) or one word such as `mark` ties nothing and the row says the text is too short. When it is not tied the row warns and says "not a recorded G4 rule line yet": G4 not recorded, no line with those words, or
  BRAND-STATE.md unreadable. So a proposal never fails a page; the owner's approval does. The row holds `rule` (the entry), `tied`, `g4_line` (the line or null) and, per kind, `max` (and `min`),
  `most_in_one_screen`, `screen` (`{width, scheme, top, bottom}`) and `marks` for marks; `controls_checked`, `longest` and `offenders` for controls; `accents_checked` and `offenders` for accents. A
  selector the browser does not take as CSS fails the row whether or not it is tied (the rule cannot be judged), and says so; a selector that matches nothing passes and says so. A rule that
  could not be measured (no view rendered, a mark with no box) is `skipped` or "NOT verified" in a warning, never a pass. The rows read the G4 record and the `(rule)` lines of `BRAND-STATE.md`, which are already an input of the report (the part `g4-rules`). The
  judging imports `scripts/adaptlib/adapt.py` (next to `pagelib`) only when a project has page rules.
- **Generic tells.** `skills/brand-creator/references/page-tells.json` (`{"$description", "version": 1, "languages": ["en", "pl"], "tells": [...], "notes": [...]}`) lists the patterns that read as a template whatever
  the brand. A tell is `{id, name, what, why, measure}` plus, where it has them, `threshold` (the numbers) and `words` (a list per language of `languages`). The browser reports candidates and
  `pagecheck.find_tells` applies the numbers and the lists, so a number has one home. A tell is a warning, never a failure, until the owner adopts it as a brand rule.
  - `eyebrow`: the text element directly before an `h1`, `h2` or `h3` (an empty box between them, such as a rule, is looked past; an image or an icon is not) with at most 4 words (`max_words`), in capitals (`text-transform:
    uppercase`, small caps, or typed in capitals) or letter-spaced `min_letter_spacing_em` (0.05 em) or more, and set smaller than the heading.
  - `arrow-glued`: a shown link, button or submit input whose label (its text, with the content of its `::before` and `::after`) starts or ends with an arrow, a chevron, a double angle, `->` or `=>`
    next to other text, with at most `max_gap_chars` (1) white space characters between them. A run of spaces, tabs and line breaks is one character (the browser collapses it); a no-break space or an em space is
    counted each, so `Spare parts&nbsp;&nbsp;&nbsp;&nbsp;→` has a gap of 4 and is not glued. An arrow alone is an icon button. A gap made with margin or a flex gap is not seen.
  - `middot-run`: an element whose own text holds `min_separators` (2) or more middle dots or bullets (`· • ‧ ∙ ⋅ ●`) with text on both sides on the same line (an inline child element stands in the text as one
    unit; a `<br>` and a block child end the line, so a dot that starts a line is a list marker and is not counted), or a parent whose children carry that many `::before` or `::after` that are one dot and sit side by
    side in one row (a child with a sibling beside it, overlapping in height; a stacked list with a marker on every item is not a run, an inline breadcrumb or a flex row is).
  - `stock-second-action`: the second action (link, button or submit input with a label, outside a `nav`, in the first screen) of the hero, the nearest `section`, `header`, `[role=banner]` or element named
    hero around the first `h1`, else the `h1`'s parent. Its label, case, arrows, punctuation and white space ignored, is a word of the list for its language (`en` or `pl`, the closest `lang`).
  - `hero-text-budget`: the hero shows more than `max_words` (45) words in the first screen (the top of the page to the viewport height); a `nav` and text below the fold are not counted.
  - `styled-div-mock`: the innermost shown box of `min_width_px` x `min_height_px` (240 x 160) css px or more with `min_styled_descendants` (8) or more shown descendants that have a background colour or
    image or a border (form controls, table parts and rules are not counted: the `table`, `thead`, `tbody`, `tfoot`, `tr`, `td` and `th` of a table are data, so a table of styled cells is not a mock-up), no `img`, `svg` or `picture` inside with a side over `max_icon_px` (48) css px (a smaller one is an icon and does not exempt
    the box; a `picture` is as big as the `img` it draws), no `canvas` or `video`, and no non-empty `data-sample` on it or an ancestor. The items of a list, the `li` of a `ul` or `ol` with everything in them (the
    outermost list in the box; a list inside one of its items is part of it), excuse a box only when the box is the list or the items are nearly all of it: at most `max_unlisted_styled` (1) of its styled
    descendants are outside the items, or the items themselves (the boxes of the `li`, each clipped to the rectangle of the box, so a row of items that runs on past it fills no more of it than lies in it; not the room of the list round them, which may be stretched past them) take `min_list_area_ratio` (0.8) of its area. So a styled checklist or timeline is not a mock-up, but a panel with its own styled head, figures or footer beside
    a list is judged on all its styled boxes, the items of the list each counted. Styled boxes inside a table cell (a status badge in a `td` or `th`) count as part of the table: a box that is a `table`, `thead`, `tbody`, `tfoot` or `tr`, or
    whose styled descendants are all in cells (a cell itself too), is not judged, so an index table whose rows end in a badge is data; a table with a styled head or footer beside it is judged on all its styled boxes, the badges too, and a drawing in a cell is its own box. A box that holds an `h1`,
    or more than `max_headings` (1) headings (`h1` to `h6`, `[role=heading]`), is a section of the page, not a drawing in it, and is not judged: the whole page, or a band of cards with icons, is not a mock-up,
    while a figure drawn as a panel with a header, rows and small svg icons, with no heading or one, is.
  - `three-equal-tiles`: in a view of `min_viewport_px` (1024) or more, an element with exactly three shown element children (a `<template>`, a `<script>` or a hidden child is not counted), side by side in one row, widths within `width_tolerance_px` (2), the shorter at
    least `min_height_ratio` (0.8) of the taller, each holding a shown heading.
  - Note `stock-anatomy` (info): in one view, from the top of the page down, the hero, a `three-equal-tiles` row, an FAQ (a `details` with a `summary`, or a heading that is a word of the note's lists) and a
    closing band (the last block of `main`, or of the body without one: a heading, an action and at most `cta_max_words` (40) words).
- **Tell facts.** Every view holds `tell_facts` from `page_measure.mjs`, whatever the rules: `viewport`; `eyebrow` (`{sel, text, words, uppercase, letter_spacing_em, font_size_px, heading_sel, heading_tag,
  heading_font_size_px}`, the candidates of 1 to 12 words); `arrows` (`{sel, label, edge, glyph, gap_chars}`, `gap_chars` as counted above); `separators` (`{sel, text, count, via}`, `via` is `text` or `pseudo`); `hero` (`{found, sel, h1_sel, top,
  words, viewport_height, lang, actions: [{sel, label, lang}]}`, at most 6 actions); `boxes` (`{id, parent, sel, width, height, styled, in_lists, in_cells, table, list_area, media_px, headings, h1, labelled}` for boxes of 120 x 80 css px with 4 styled
  descendants or more, `parent` the id of the nearest box above that is in the list, at most 200; `in_lists` of the `styled` sit in the items of lists, and `list_area` is the area in css px squared of those items themselves, the sum of the part of each `li` box that lies in the rectangle of the box (not of the list, which may be stretched past them, and not what a row of items runs on past the box; a list with no styled item adds none); `in_cells` of the `styled` sit in a `td` or `th` (in the box, or the box itself) and `table` is true for a `table`, `thead`, `tbody`, `tfoot` or `tr` box; `media_px` is the
  largest side in css px of the shown media inside by element name, `{"svg": 24, "img": 600}` or `{}` (a `picture` by the `img` it draws), and `page-tells.json` says which are icons; `headings` is the number of shown
  headings inside and `h1` the number of shown `h1` among them); `tiles` (`{sel, tiles: [{sel, left, top, width, height}]}`, at most 40); `headings`, `details` and
  `last_band` (where the pieces of a stock page are). The lists are capped (60 eyebrow candidates, 100 arrows, headings and details, 200 separators); `truncated` is true when the page has more than 8000 elements, which the walks over every element (`middot-run`,
  `styled-div-mock`, `three-equal-tiles`) stop at. Nothing is judged in the browser.
- **Tell rows.** `tell:<id>`, one per tell of the file in its order, none for a tell a brand rule has adopted. The thresholds are applied to every view and a place seen in several views is one hit with its `widths`.
  Pass: "none found in N view(s)". Warn: "N found: <selector>: <what was seen> (at <widths> px)" (up to six named; the row's `hits` keeps up to 100 as `{selector, text, widths}`) and the tell's `why`. Skipped:
  no view was measured. `tell:stock-second-action` also warns "NOT verified: no word list for <lang>" when the page's `lang`, or the closest `lang` of its second action, is not in `languages` (a page that sets
  no `lang` too); the other tells need no word list. `middot-run`, `styled-div-mock` and `three-equal-tiles` warn "NOT verified beyond the first elements of a view" when a view was cut at 8000 elements.
  `note:stock-anatomy` (info, with `anatomy`: `{view, hero, tiles, faq, closing_band}`, the tops in css px) appears only when one view shows the stock order. A `page.rules` entry of kind `tell` (`tell` is an id of the file;
  any other id exits 2 before a page is opened) gives `page:rule:<id>` in place of `tell:<tell>`: the same hits, a warning while the rule is not tied to a recorded G4 line and a failure after, a pass when none are
  found; the row holds `tell` and `hits`. `pagecheck.load_tells()`, `tell_ids()` and `check_tell_rules(rules)` are the readers other tools import; the file ships with the plugin (exit 3 if it cannot be read).
- **Writing a collector.** `page_measure.mjs` installs `window.__bcMeasure` for the length of one view (`collect` removes it again): `selector(el)`, `shown(el)` (`{shown, opacity}`),
  `walkable(el)`, `colour(css)` (`{r, g, b, a, hex}` or null), `canvas()`, `ground(el)` and `hex([r, g, b])`. A later collector calls them inside its own `page.evaluate`.
- **For other tools.** `scripts/pagelib/pagecheck.py` imports only the standard library and `scripts/lib`, and the claims rows also load `scripts/booklib/bookdata.py` (the FACTS.md table and the English status words), found next to the module; a tool puts `scripts/pagelib` on `sys.path` and calls
  `report_tool(ident)` (the report name above) and `is_loopback_url(url)` (the one loopback rule; `isLoopbackUrl(url)` in `scripts/lib/_common.mjs` is its twin and
  a test pins both to one table of cases, the forms a parser turns into 127.0.0.1 among them). Each family of rows is a function `(rep, measures, ctx)` listed in `pagecheck.ROW_CHECKS`; a family adds its keys to the
  report through `ctx.extra`.

## Website references and reference pages

The tools of the two optional steps after G4 in Standard and Full: the website references and the site round. Each has its own heading.

### capture

`brand-creator capture <page.html>` and `brand-creator capture --url <url> --name <name>` (`render.mjs capture`) take stills. They write no report in
`assets/_checks/`: the record is `capture.json` beside the stills. Every refusal below comes before the browser starts, and every picture is taken before the
first file is written, so a page or a site that does not load leaves nothing behind.

**A page of the project:** `capture <page.html> [--project DIR] [--wait MS] [--timeout MS]`.

- The page is confined to the project (a path outside it exits 2). The stills go to `<the page's folder>/shots/`, which is fixed. A page under `history/`, and a
  page in a round before the latest (`rounds/r<K>/` with `K` below the latest round), exit 2 with `<page> is inside ..., which is read-only (capture writes its
  stills beside the page): copy the page into the latest round and capture it there`; `frames` refuses the same folders with its own wording.
- The project is served by `render.mjs`'s own local server. A request to another origin is recorded in `problems` and aborted, as in `shot`. The page is waited for
  as `shot` waits: `load`, `document.fonts.ready`, lazy images loaded first, `--wait` (default 300 ms), then the running animations that have an end (at most 15 s).
  `--timeout` (default 60000 ms) bounds the load. A page whose animation never ends is captured where it is, so its stills may differ from run to run.
- Written, each only when its bytes change (`writeIfChanged`), at device scale 1: `1440-light.png` and `1440-dark.png` (viewport 1440 x 900), `390-light.png` and
  `390-dark.png` (390 x 844), the first screen only, and `1440-light-full.png` (the whole page at 1440, light, at most 12000 css px tall; a taller page is cut and
  `capture.json` says so).
- `shots/capture.json`:

  ```json
  {"schema": 1, "tool": "capture", "source": {"page": "rounds/r2/Ledger/index.html"}, "date": "2026-11-04",
   "views": [{"view": "1440-light", "width": 1440, "height": 900, "scheme": "light", "file": "1440-light.png", "sha256": "<hex>"}],
   "full": {"file": "1440-light-full.png", "sha256": "<hex>", "height": 2725, "cut": false},
   "inputs": [{"path": "rounds/r2/Ledger/index.html", "sha256": "<hex>"}],
   "problems": ["non-local request: https://example.invalid/x.png"]}
  ```

  `views` holds the four first screens in the order above; `full.height` is the picture's height, and a cut page adds `full.page_height` (its real height).
  `inputs` are the page and every project file the server answered (a stylesheet, a script, an image, a font, `tokens.css`), as project paths, sorted, each with its
  hash, so a still is detectably stale when one of them changes; files inside `shots/` itself are left out, so a page that loads one of its own stills still comes
  to rest. `problems` are what went wrong while the page loaded (a request to another origin, a page or console error, a failed request of the page's own),
  sorted, at most 40 and then `"<n> more"`: they are recorded, never gated (`page-check` gates the page).
- `capture.json` is rewritten only when a still, an input or a problem changed. Otherwise the old file, its `date` included, stays byte for byte, so a run that
  finds nothing new does not make a report that read it stale.
- Exit 0 when written. Exit 1 when the page cannot be loaded or rendered (nothing is written). Exit 2 for a usage error, a page outside the project, a page in
  `history/` or a round before the latest. Exit 3 when Chromium is missing.

**A real site:** `capture --url <url> --name <name> [--project DIR] [--timeout MS]`. It takes no page and no `--wait`.

- Refused with exit 2, in this order, before anything is fetched:
  1. an address that does not parse or is not `http:` or `https:` (`capture takes an http(s) address`), or that holds a user name or password;
  2. a `--name` that does not match `^[a-z0-9][a-z0-9-]{1,40}$`, or that is `owner` (reserved: `research/site-refs/owner/` holds the screenshots the owner sent, which a capture
     would overwrite);
  3. `site_research` in `BRAND-STATE.md` that is not `online` or `links-only`: the message says to ask the owner first, names the phase file
     `07w-website-references` and gives the command `brand-creator state --set site_research=online` (or `links-only`);
  4. a `research/site-refs/<name>/capture.json` that holds another address (`use another --name`) or cannot be read; or a `research/site-refs/<name>` that holds files (or is a
     file) and has no `capture.json`: what is there was not written by a capture and is never overwritten (an empty folder is taken).

  The same address again is taken again into the same folder.
- **The only command that lets Chromium reach the network, and only with `--url`.** Nothing is blocked: a fresh browser context per view (no cookies or storage from
  an earlier visit), `acceptDownloads: false`, default `--timeout` 45000 ms. The address is loaded at 1440 x 900 and again at 390 x 844 (light scheme); each load
  waits for `load`, the fonts, the lazy images (at most 10 s; the output says how many were missing) and the animations that end, and pauses one second.
- Written into `research/site-refs/<name>/`: `1440.png` (the first screen), `390.png`, `1440-full.png` (at most 12000 css px, cut and recorded as above),
  `thumb-1440.jpg` (480 px wide) and `thumb-390.jpg` (160 px wide), JPEG at quality 0.75 on white, shrunk in a blank page with a canvas, and `capture.json`:

  ```json
  {"schema": 1, "tool": "capture",
   "source": {"url": "<address>", "final_url": "<where it ended>", "status": 200, "title": "<document.title, at most 120 characters>"},
   "date": "2026-11-04",
   "views": [{"view": "1440", "width": 1440, "height": 900, "scheme": "light", "file": "1440.png", "sha256": "<hex>"}],
   "full": {"file": "1440-full.png", "sha256": "<hex>", "height": 2725, "cut": false},
   "thumbs": [{"file": "thumb-1440.jpg", "width": 480, "sha256": "<hex>"}, {"file": "thumb-390.jpg", "width": 160, "sha256": "<hex>"}]}
  ```

  The board inlines the thumbnails, and its provenance row matches their bytes with `thumbs[].sha256`. A record is rewritten when anything in it differs,
  so a capture on a later day carries the later `date`.
- An answer of 400 or more, a navigation error or a timeout exits 1 with `could not capture <url>: <why>; leave the reference out or ask the owner for a
  screenshot`, and nothing is written. Exit 3 when Chromium is missing.
- It never captures a page behind a login: the phase file says so, and the tool cannot tell.

### site approve

`brand-creator site approve [--round N] [--replace] [--project DIR]` (`scripts/site_pages.py`: the subcommand is `site`, and the script is never `site.py`, which would shadow the standard
library's `site` module wherever `scripts/` is on `sys.path`) puts the pages the owner approved into `site/`. It writes no report in `assets/_checks/`: the record is `site/site.json`
(below). Approved pages are references for whoever builds the real site, never fill-in templates.

- Refused, in this order, before anything is written:
  1. exit 1 when G4p is not recorded (`site approve needs the owner's approval of the pages (G4p) recorded first`, with the `state --record G4p` command);
  2. exit 2 when `rounds/r<N>/board.html` (`N` is `--round`, else the latest round) does not exist, or is not a `data-board="site"` page at `data-site-stage="pages"`, or when `rounds`, `rounds/r<N>` or the board file is a symbolic link,
     wherever it leads (`rounds/r3 is a symbolic link: the pages board is read as it is, and a link can lead out of the project`; this is looked at before the file is looked for or read);
  3. exit 1 unless `assets/_checks/board-lint.json` is the lint of that very board, current and `pass` (`lint the pages board first: brand-creator board-lint rounds/r<N>/board.html`).
     Current is `check`'s rule: no file the lint was made from is gone or changed. A page-check report holds `BRAND-STATE.md` by its G4 rules (the part `g4-rules`, see Reports) and the lint keeps
     those records, so recording G4p, G5 or G6 leaves the lint current, and a changed G4 record or `(rule)` line makes it stale: the message then names `page-check` for each page and the lint, and both have to be
     run again. One case differs: a lint of a board with a rule
     whose source only `BRAND-STATE.md` holds lists the whole file itself (see `site:choices`), so recording G4p makes it stale and the message asks for the lint again alone;
  4. exit 1 when `site/` exists and `--replace` is not given (`site/ holds approved pages already`).
- **Pages.** One page per page card of the board (`data-site-page`); each needs its folder `rounds/r<N>/<id>/`, its `index.html` and a `data-layout` on `<body>`. The folder is copied into
  `site/<id>/` except `shots/` and `cold-review.md` at the top of it (`capture` writes `shots/` again beside the approved page) and `.DS_Store`. A symbolic link anywhere in a page folder exits 2, and so does a page folder that is itself a symbolic link or has one above it, wherever it leads
  (`rounds/r3/start is a symbolic link: a page folder is copied as it is, and a link can lead out of the project`), and a page folder whose real path (`confine`) is not inside the project: this is looked at after
  refusals 1 to 4 and before any page is copied or its paths are read, for every page card (refusal 3 has hashed the page files by then, as inputs of the lint, but nothing from a page outside the project is ever copied), and is listed as `nothing was written: N problem(s) stop the pages of rounds/r<N>/board.html`. A link inside a page folder is named by its place in the
  folder (`rounds/r3/start/img`), also when it leads out of the project.
- **Paths.** In each `.html` and `.css` file (UTF-8; any other file is copied byte for byte) a relative URL is read in `src`, `href`, `poster`, `xlink:href`, `srcset` and `imagesrcset` (every URL in the
  list), the `data` of an `<object>`, and `url()` and `@import` in a `<style>` element, a `style` attribute and a `.css` file. One that resolves to a file of the project outside the page's
  folder is written again so that it leads to the same file from `site/<id>/` (`../../../assets/tokens/tokens.css` becomes `../../assets/tokens/tokens.css`); one that leads into the folder of another
  page of the board leads to where that page goes (`../pricing/index.html` stays); one inside the page's own folder, `#...`, an empty value, `data:`, `mailto:` and `tel:` stay as written, and so do the
  query and the fragment of a path. Not read: the text of a `<script>`, a comment, `action`, `content` and `data-*` attributes, a URL a script builds, and a bare string in `image-set()`.
  - exit 1 on an `http(s)://`, `ftp(s)://`, `ws(s)://` or `//` address, on any other scheme, and on a path starting with `/`: `a reference page needs no network`;
  - exit 1 on a URL whose file does not exist; exit 2 on a URL that resolves outside the project, or through a link to a place outside it.
  Every problem is listed with its file and line, up to twelve, and nothing is written when there is one (exit 2 when any of them is exit 2, else 1).
- **Writing.** The pages and `site.json` are written into a staging folder in the project and then take the place of `site/`, so a failure leaves no half-written `site/`. With `--replace`, an existing
  `site/` is first moved to `removed-<date>/site/` (`removed-<date>-2/site/` when that folder has a `site/` already): it is never deleted, and it is put back when the new pages fail.
- It prints what it wrote and, per page, `brand-creator capture site/<id>/index.html` and `brand-creator page-check site/<id>/index.html`, then `brand-creator check`.
  The approved copy has no `shots/` until `capture` is run on it.

### site/site.json

The decision record of the approved pages (schema 1), written by `site approve`:

```json
{
  "schema": 1,
  "approved": "2026-11-04 approved start, pricing; rules c1 c3",
  "round": 9,
  "hero": "Ledger",
  "pages": [{"id": "start", "path": "site/start/index.html", "layout": "walkthrough", "sha256": "<hex>"}],
  "choices": [
    {"id": "c1", "text": "The stamp appears once per view", "tag": "rule", "source": "DECISIONS.md 14", "pages": ["start", "pricing"]},
    {"id": "c2", "text": "Pricing sits under the stages", "tag": "example", "source": "", "pages": ["start"]}
  ]
}
```

- `approved` is the G4p record as `state` holds it, `round` the round of the pages board, `hero` its `data-hero`. A page's `id` matches `^[a-z][a-z0-9-]{1,31}$` and is the folder `site/<id>/`
  (the home page is `start`); `layout` is the `data-layout` of the page, an id of `page-layouts.json` or `own:<word>`; `sha256` is the hash of the `index.html` that was written, after its paths were
  rewritten.
- `choices` come from the choices section of the board, in its order: `id` is `c<number>`, `tag` is `rule` or `example`, a `rule` has a non-empty `source` (the words of the decision it cites, found in
  `BRAND-STATE.md`, `DECISIONS.md` or `decisions/*.md` when the board was linted), `pages` names page ids of the record (the board's `data-pages`, else every page).
- `scripts/boardlib/sitedata.py` is the one reading: `load_site(project)` (the record as written; exit 1 when the file is missing or is not a JSON object), `validate_site(project) -> list[str]` (sentences, `[]`
  when sound: schema 1, the keys above, page ids and paths, a known layout, choices tagged and rules sourced, `pages` of a choice known, and each page file present with the sha256 the record holds; a page
  edited after approval reads `changed since it was approved`) and `rewrite_urls(text, kind, project=, file_dir=, new_file_dir=, moves=, label=)`, the path rule above, which
  `site approve` uses to carry a reference page into `site/`. A tool that reads the approved pages reads the record through `load_site` and `validate_site`, never by a parsing of its own.

### check and the approved pages

`brand-creator check` gates the approved pages with three rows, `site:record`, `site:pages` and `site:stills`, **only when G4p is recorded or `site/site.json` exists**. A project with neither (every project
made before the site round, and a site round not yet approved) gets no `site:` row, and a `site/` folder without `site/site.json` and without G4p is the owner's own and is not read.

- `site:record`: G4p recorded and `site/site.json` there. G4p without the file fails (`G4p is recorded but site/site.json does not exist: run brand-creator site approve`), and so does the file without G4p
  (`exists but G4p, the owner's approval of the pages, is not recorded`): nothing but `site approve` after G4p puts pages in `site/`. Then `sitedata.validate_site(project)` must find nothing: a record that is not
  schema 1, a layout that is no reference and no `own:<word>`, a choice without a tag, a rule without where it was decided, a choice naming a page the record does not hold, and a page that is gone or whose sha256 is
  not the one approved (`changed since it was approved ... run brand-creator site approve --replace from the round, or put the approved page back`). The row fails; it is "not verified" only when the layout file
  of the plugin cannot be used (a damaged install).
- `site:pages`: one row for the pages the record can name (an id and the path `site/<id>/index.html`, each once, whatever else is wrong with the record). Each needs the page-check report of that very page,
  `assets/_checks/<tool>.json` with `tool = pagecheck.report_tool("site/<id>/index.html")` (`scripts/pagelib/pagecheck.py`, which `check` puts on `sys.path`; the name is never rebuilt by hand), current by
  `check`'s rule (no file it was made from is gone or changed), with `target` a `project` target whose `page` is that path, the page among its `inputs`, and a verdict. A report whose status is `fail` fails the
  row (`<id>: page-check/<slug>-<hash6> report is failing (<failing rows>)`); the row fails whatever the other pages say, and the pages that are not verified are named after it. A page with no report, a stale
  report, one of another target or page, one that does not list the page, or one that is no verdict (`not-verified`, with up to three of its skipped rows quoted) makes the row "not verified" and names
  `brand-creator page-check site/<id>/index.html`. A report that is no JSON, or no report, fails like any other report `check` reads.
- `site:stills`: each page has `site/<id>/shots/capture.json` (`brand-creator capture site/<id>/index.html`) that is the capture of that page (`source.page`), current by the same rule with the page among its
  `inputs`, and lists the four first-screen stills (`1440-light`, `1440-dark`, `390-light`, `390-dark`) by file and sha256 where the files in `shots/` have those bytes. Otherwise the row is "not verified" and
  names `brand-creator capture site/<id>/index.html` (a capture is a record of the page, not a gate on it, so it never fails the row).

`site approve` writes no report, so right after it `site:pages` and `site:stills` are "not verified" until `page-check` and `capture` have run on each page, which is what its output asks for. The page-check report of a page
in `site/` holds `BRAND-STATE.md` by its G4 rules only, so recording G5 or G6 or setting the phase afterwards leaves it current; a changed G4 record or `(rule)` line makes it stale. A page that `check` passes has not changed since approval, was checked against
the brand rules as it is, and has stills of the page as it is.

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
family modes; `tone`, `photography`, `components`, `site` only when named in `book_chapters`. Each chapter is `book/chapters/<id>.md`
(`<id>.<lang>.md` for each language when `content_languages` has several; every language is required). `book --init` copies the skeletons
from `templates/book/` and never overwrites; `[[fill: ...]]` left in a chapter fails the build.

**Chapter Markdown** is a documented subset (`scripts/booklib/bookmd.py`): `## `/`### ` headings, paragraphs, flat lists and task lists,
`>` quotes, pipe tables, fenced code, own-line images (embedded as data URIs; SVG under `assets/` is mark-linted), inline `**`, `*`, `` ` ``,
links. Raw HTML is escaped. Anything else is an error with the line number. Computed blocks on their own line: `{{marks[:stem,stem?]}}`,
`{{mark-sizes}}` (the drawing the size band rule picks, rendered at exactly the size on light and dark, the enlarged copy being the same
pixels, plus the downscale reports' accent measurements), `{{colours}}`, `{{contrast}}` (WCAG ratios computed from the tokens), `{{type}}`,
`{{motion}}`, `{{tokens}}`, `{{files}}` (one row per manifest row and source artwork file with `data-path` and `data-sha`; a row marked `superseded` carries a note saying so), `{{checks}}`,
`{{decided}}`, `{{history}}`, `{{edition-log}}`, `{{donts}}` (five misuse drawings of the mark), `{{facts}}`, `{{site}}` (the approved pages, below). Inline: `{{count:NAME}}`
(`files, slots, colours, pairs, roles, sizes, artwork, emitters, chapters`), `{{fact:LABEL}}` (a FACTS.md row's value), `{{edition}}`,
`{{name}}`, `{{approved}}`. `::: variant GROUP NAME` and `::: switcher GROUP` fences are open choices (see `collapse`). Settings in
`book/book.json` (unknown keys are exit 2): `min_label_px` (default 12, stated in the book), `sizes`, `fonts` (`{family, file, weight, style}`,
embedded as data URIs), `labels` (`{lang: {English label: translation}}`; a label with no translation is shown in English and warned),
`output`, `lint` (`history_chapter, forbidden, scratch, round, status_words, count_nouns, allow_external_links, files_exclude`).

**The site chapter.** Opt-in (`book_chapters: [site]`), Standard and Full; it sits after `components` and before `use`. `{{site}}` shows the approved pages of the site round (`site/site.json`, written by
`site approve`, see "site/site.json"). It reads the record with `sitedata.validate_site` (`scripts/boardlib/sitedata.py`), the reading `check` shares, and stops the book with exit 1 and
`the site chapter needs the approved pages (site/site.json, from site approve): run the site round, or drop site from book_chapters` when `site/site.json` is missing, when the record is not sound, or when
a page file is gone or is not the one the record holds (that message then ends with the first problems, in parentheses), and with exit 1 and `the site chapter needs the stills of the approved pages: site/<id>/shots/ has no
<file>` (one clause for each page that lacks a still, then the `brand-creator capture site/<id>/index.html` that takes them) when a still is missing; nothing is written. When `{{site}}` stands in a chapter of the book while `site` is not in `book_chapters`, the
message begins `{{site}}` instead of `the site chapter` and ends with `take {{site}} out of the chapter that holds it`. For each page of the record, in record order: an
`<h3 data-site-page="<id>">` with the page id; a `<p data-site-layout="<layout>">` with the `job` sentence of its layout in `page-layouts.json`, or `A layout of its own.` for an `own:<word>` layout; the
1440 and 390 px light stills `site/<id>/shots/1440-light.png` and `390-light.png` (written by `capture site/<id>/index.html`) as `<figure class="pic" data-site-still="<view>">` with the picture as a `data:` URI
and the alt text `The <id> page at 1440 px, light` (390 for the other; the alt is a label of `book/book.json` `labels`, written with `{id}` and `{px}` where the page id and the width go); and one table with
the columns `Choice`, `Rule or example` and `Where it was decided`, one row (`data-choice`, `data-tag`) for each choice that names the page in `pages` or has no `pages`, in record order, the third
cell the choice's `source` (`-` when it has none). A page whose choices are none gets the sentence `No choice is recorded for this page.` (a label of `book/book.json` `labels`) instead of the table. A still that is not there stops the build, as above:
a book built without a picture would stay current for `check` when the still is taken later. Each still is resolved with `confine` before it is read (`site still <path> is outside the project ...`, exit 2: a link out of the project is never embedded). The page files are hashed first, by the
check of the record that `check` shares, and then resolved the same way (`site page <path> is outside the project ...`, exit 2); nothing from a page outside the project is ever embedded. Those two refusals end
`brand-creator only reads inside the project`, where the refusal of a path that may be written ends `only writes`. A still whose first eight bytes are not the PNG signature stops the build with exit 1 and
`the site chapter needs the stills of the approved pages: site/<id>/shots/<view>-light.png is not a PNG picture (it does not start with the PNG signature)`, then the `brand-creator capture site/<id>/index.html` that takes it again. The inputs of the `book` report are `site/site.json`, each page file and each still shown, so a page, a record or a still
that changes makes the report stale. `templates/book/site.md` holds the owner's prose: what the pages are for (references for whoever builds the real site; a rule is the brand's, an example may
change) and how the real site is built (in the product repositories, from the tokens and the rules). A book without `site` in `book_chapters` is byte for byte what it was.

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

**Honest print.** Chromium prints the page (`render.mjs pdf --size-mm WxH`, the only Chromium driver); the page is exactly
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
`templates/ADOPTION.md` (placeholders `{{name}}`, `{{status}}`, `{{repos}}`, `{{about}}`, `{{groups}}`, `{{drift}}`, `{{rows}}`, `{{wiring}}`, `{{kept}}`, filled in one pass;
a missing frame or placeholder exits 2). `check` (`adoption:data`) fails an ADOPTION.md that is not what the data renders, and warns about a row marked done
that still matches at the last survey (`adoption:drift`).

### adoption wiring

`adoption wiring --repo LABEL (--before [--again] | --after | --compare | --drop "ITEM::REASON"...)` records the wiring of a surveyed repository's source: the links, form field names, handlers,
test hooks, ids and scripts that a redesign can drop without the adoption list noticing ([ADR-0012](../docs/adr/ADR-0012-a-redesign-records-the-sites-wiring.md)).
`LABEL` must be a repository of the survey (exit 2 otherwise), and exactly one of `--before`, `--after`, `--compare` and `--drop` is given (exit 2 otherwise). The command needs no gate, as the survey needs none:
it changes nothing outside the project, and it proves that.

Files are listed with ripgrep as the survey lists them (`.gitignore` honoured, `.git` left out, symlinks not followed, the brand project left out when it
lives inside the repository). A file is read when its extension is one of `.html .htm .jsx .tsx .js .ts .mjs .vue .svelte .astro .erb .ejs .hbs .handlebars
.njk .liquid .twig .php .mdx` and the survey's keep rules (`keep_reason(path, [])`) do not keep it: lock files, change history, licence text, minified output,
and `dist`, `build`, `target`, `out`, `.next`, `.nuxt`, `coverage`, `vendor`, `Pods`, `DerivedData`, `__pycache__` and `node_modules` folders. The owner's `--keep` globs
are about brand slots and do not apply here. HTML comments are removed first, and the body of a `<script>` or `<style>` is not read as markup. Attributes are read
from tags (`<name ...>`, across lines); a value is a quoted string or a `{...}` expression kept with its braces, balanced to three levels, with white space
squashed. An unquoted value is not read, and nor is a `{...}` nested deeper than three levels (the `wiring:scope` row counts them). An item is `kind:value`, with
everything after the colon cut at 120 characters:

| kind | what is an item |
|---|---|
| `link` | the value of `href`, `to`, `action` and `formAction` (`formaction` too); not an empty value or `#`, and not `href` on `link`, `script`, `base`, `use`, `image` and `style` tags |
| `field` | `name` on any tag but `meta`, `link`, `a`, `iframe`, `param`, `slot`, `map` and `object`; and the string argument of `register("...")` (not of `x.register(...)`) |
| `handler` | an attribute `on[A-Z]...` or `on[a-z]...`, `@event`, `v-on:event` or `on:event` that has a value: `handler:<attribute>=<value>` |
| `hook` | `data-testid`, `data-test`, `data-cy`, `data-qa` and `data-track*`, `data-analytics*`, `data-event*`, `data-gtm*`: `hook:<attribute>=<value>` |
| `id` | a static `id="..."`: no braces and no white space in the value |
| `script` | the `src` of a `<script>`, without its query and without a leading `./` |

The record is `adoption.json` `wiring[<repository id>]["before" | "after"]` = `{"date", "head", "files", "items"}`: the day, the repository's git head (or `no git head`), the number of
files read, and `items`, sorted, each mapped to up to five files that held it. A repository id is the survey's (`r1`, `r2`). `--before` is the baseline: over an existing
before record it exits 1 ("pass --again to replace it"), and `--again` replaces the before record only. `--after` needs a before record (exit 2) and replaces an earlier after record. The key
`kept` of `adoption.json` is the survey's list of lines left out of the count, so the record has its own key. `verify` (and `check`, `adoption:data`) fails a `wiring` entry for a repository that was
never surveyed, a record whose `items` are not an object of lists of strings and a `dropped` that is not an object of item to non-empty reason; `check --cascade` does not search the record.

The report is `adoption-wiring` with the rows `read-only:<label>`, `wiring:<label>` (info: the count per kind) and `wiring:scope` (info: the files read, the files of
those kinds the keep rules left out, and the values not read). The scan lists the files with sizes and modification times before and after reading; a difference fails
`read-only:<label>`, exits 1 and stores nothing. Without ripgrep the command exits 3 with the install command and stores nothing; a file that cannot be read exits 3.
The extraction is by pattern, so it is approximate (a value built at run time, a tag a template engine assembles): ADR-0012 says why a noisy item is dropped with a reason rather
than hidden.

A loss is an item of the before record that the repository no longer has and nobody dropped.

- `--compare` reads the repository now with the same scan and the same read-only proof, and **writes nothing**: no record, no report, no ADOPTION.md. It needs a before record (exit 2 without
  one) and ripgrep (exit 3). It prints the repository, the date of the before record and the item counts; `lost, not recorded as dropped: N` with one line per item and the files it was in;
  `dropped with a reason: N` with one line per dropped item and its reason; `new items: N`; and a verdict line, `wiring compare: PASS` or `wiring compare: FAIL`. Exit 1 when a loss is not
  recorded as dropped, 0 when none is. A repository that changed while it was read is exit 1 with no verdict.
- `--drop "ITEM::REASON"` (repeatable) records, in `wiring[<id>]["dropped"]` as `{item: reason}`, why an item of the before record goes. The item must be in the before record and the reason
  must not be empty, else exit 2 and nothing is stored (all or none). An item may hold `::` itself: the item is the first start of the text, ending at a `::`, that is an item of the before
  record. White space in the reason is squashed; a second drop of an item replaces its reason; `--before --again` keeps the drops. Claude never writes the reason: it is the owner's. It reads
  no repository, so it needs no ripgrep. It rewrites adoption.json and ADOPTION.md and writes no report.
- `check` gives each repository with a before record the row `adoption:wiring:<label>`: **fail** when the after record lost an item that nobody dropped (it names up to five, then "and N more"),
  **pass** otherwise, and **info** ("record --after when the redesign is applied") with a before record only. A record of the wrong shape gets no row; `adoption:data` names it.
- `ADOPTION.md` shows the record in the section `## Wiring kept`, between the rows and "How this list is applied" (the placeholder `{{wiring}}`, empty when no repository has a before
  record, so a list without wiring renders the bytes it always did). Per repository: one line of counts per kind, before and after; under it one line per lost item, `- <item>: dropped, <reason>`
  or `- <item>: lost, not recorded`. Every line carries `<!-- target-repo -->`, so the cascade counts it as a record.

### check --cascade

`check --cascade "<old value or phrase>"` (repeatable; `--ignore-case`; `--also PATH` repeatable) searches every current text file of the project, PDFs as text
(`pdftotext`; a project PDF with no `pdftotext` is "not verified"), and the documents named by `tools/cascade.json` (`{"schema": 1, "also": [paths relative to the
project]}`, an unknown key is exit 2), by `--also` and by the `parent_docs` list of the family-check block of FAMILY.md (relative to FAMILY.md); outside documents
are only read, and one that does not exist fails. A current file holding the value fails with `file:line` for each hit. Skipped on purpose and said so in the
`cascade:scope` row: `history/`, `decisions/`, `BRAND-STATE.md`, `DECISIONS.md`, earlier rounds, `removed-*/`, `assets/_checks/`, `assets/manifest.json`, binary files
and print PDFs (their text is outlines). `_build/` folders are searched: their HTML (OG card, social posts, App Store frames, print pieces) is the only text
layer of an image made from a value given on the command line, which `emit` does not check against FACTS. A line that carries `<!-- target-repo -->` (an ADOPTION.md row, the rename list of LAUNCH.md) and the `find`, `terms`,
`identifiers`, `kept` and `wiring` fields of adoption.json record what a product repository holds: they are counted apart and make a warning, never a failure; any other line
of those files, including the text of an adoption row's `change`, is searched like the rest.

### adapters

`adapters --brand-md --design-md [--primary ROLE] [--bm-type T] [--bm-architecture A] [--replace]` writes `BRAND.md` and `DESIGN.md` at the project root from the built
tokens (`assets/tokens/tokens.json`), BRAND-STATE.md and FACTS.md. BRAND.md: frontmatter `type` and `architecture` (standalone: master, independent; family-member:
master, endorsed; product-in-family: product, endorsed; these pairings are brand-creator's reading, not something the format defines, so they can be overridden),
then Strategy (the facts, the canonical direction), Voice (only `voice` and `tone` facts and the FORBIDDEN list; "no voice facts are recorded" otherwise), Visual
(colour roles in light and dark, type families with the sizes, weights, line height and tracking the tokens define, the spacing, radius and layout values, the mark files, the G4 rules, motion) and Governance (naming and renames, claims and verbatim legal facts,
the accessibility commitments with the computed ratios, approval). Contact and postal-address facts are left out. DESIGN.md: frontmatter `version: alpha`, `name`,
`colors` (the light roles, `-dark` variants, `primary` when `--primary` names a role), `typography` (families, sizes, weights, line height and tracking), `spacing`, `rounded`, `components` (one entry per
`ui-text` pair, light and dark, as `{colors.x}` references, and the action of each text ground, below), then the sections in the spec's order that have content. A role whose colour is see-through
(alpha under 1 in `tokens.json`) is written `#rrggbbaa`, lower case, as `tokens.css` writes it, wherever a role is listed (BRAND.md, DESIGN.md `colors`, the applied
skill); an opaque role stays `#rrggbb`. The pinned DESIGN.md format lists `#RRGGBBAA` as a colour, and its lint passes it. The report `adapters` records the sha256 of
each output and `adapter_state_sha` (a hash of what the adapters read from BRAND-STATE.md and FACTS.md). DESIGN.md is linted with `@google/design.md` (the version
pinned in `scripts/package.json`, run with Node from `<data>/node_modules`; a different installed version is not trusted): an error or a `contrast-ratio` finding
is `fail`, other warnings are `warn`, and a missing package is `skipped`, so the report is not-verified and the exit code 3. `check` gates the report, fails a file
that is not the bytes the report recorded (a hand edit) and treats a changed source as not verified. A hand-edited file is replaced only with `--replace`, which
moves it to `removed-<date>[-n]/`. When `tools/inputs.json` exists, the adapters add `BRAND.md` and `DESIGN.md` to its globs (the pack then reads as stale until
`staleness --write`), and `staleness --write` includes both whenever they exist.

Type and layout values are read wherever `tokens.json` `other` holds them, by the name of the key (`adaptlib/adapt.py` `layout_tokens`; a leading `dimension.` is dropped
first). By its first segment, or for a one-segment name by the word it starts with before a hyphen: `space`/`spacing` are spacing steps, `radius`/`rounded` corner radius, `weight`
weights, `leading`/`line-height` line height, `tracking`/`letter-spacing` tracking, `layout`/`container`/`gutter`/`breakpoint` layout values; a name with a segment starting `text-`
(`size.text-sm`) is a text size. Fonts, durations and curves are read as before; an alias (`var(--space-3)`) is read as the value it names; every group is in name order. Nothing is
invented: a kind the tokens do not hold is not written, and a brand with no size and no weight keeps the sentence "The tokens define no sizes or weights." in DESIGN.md.
DESIGN.md `typography` has one entry per `font.*` family; a `leading.<n>` or `tracking.<n>` joins the entry of the family of that name (`lineHeight`, `letterSpacing` in em: a plain
number such as `-0.01` is written `-0.01em`) or, when no family has that name, makes an entry `<n>`; each size is an entry `text-<step>` (`fontSize`) and each weight an entry
`weight-<name>` (`fontWeight`). A weight that is not a whole number, a size that is not a px, em or rem dimension, and a line height or tracking that is neither a number nor such a dimension stay in the
prose and out of the frontmatter, because the format holds nothing else. `spacing` entries are named `space-<rest>` (`space.1` and `dimension.space-1` are `space-1`) and `rounded` entries after the
radius (`radius.sm` and `dimension.radius-sm` are `sm`). No key of the frontmatter is written twice (`adaptlib/adapt.py` `one_each`): YAML takes a repeated key for an error, and the pinned lint then
reads nothing of the file and passes it. When two tokens give one name (`space.1` with `dimension.space-1`, `radius.sm` with `dimension.radius-sm`) or one property of one `typography` entry
(`leading.sans` with `line-height.sans`, `size.text-sm` with `dimension.text-sm`) the same value, they make one entry; with different values the first in name order keeps the name and the next
is numbered `<name>-2`, `-3` (a name no token has of its own), and the prose (`## Typography`, `## Layout`) says which token it is: "`space-2-2` is `space.2`". Every token is still listed in
the prose with its own value. The DESIGN.md prose lists them: `## Typography` the families, sizes, weights, line heights and tracking, `## Layout` the groups the
spacing steps come from and the radius, container, gutter and breakpoint values. BRAND.md `### Type` and the applied skill's `## Type` list the same, one bullet per token path; BRAND.md
`### Layout` and the applied skill's `## Layout` list the spacing, radius and layout values, and are left out when there are none.

Text grounds are read from `grounds` of `tokens.json` (see Token sources; absent, nothing changes and the three files are byte for byte what they were). DESIGN.md `components` gains
`action-on-<ground>` for each listed ground (`<ground>` is the role name without `color.`): `backgroundColor` the action role and `textColor` the on-action role, as `{colors.x}`
references, and an `action-on-<ground>-dark` twin when both roles have a colour in dark. A name already taken (a ground listed twice, a `ui-text` pair that makes the same name) takes
`-2`, `-3`, so that no key repeats. A role the tokens give no colour for (`null`: left out of the block, or a name that is no semantic colour token) is left out and never filled in:
a ground without its action or on-action in a mode has no entry for that mode (`action-on-<ground>` for light, the `-dark` twin for dark). An entry is also left out for a mode in which the
on-action text is under 4.5:1 on the action (the ratio of `grounds:<mode>:<ground>:on-action` in `contrast`): the lint of the pinned format fails a component with such a pair (`contrast-ratio`), while
`contrast` only warns about it in this release and exits 0, and `adapters --design-md` must not exit 1 for a pair that `contrast` passes. The other mode keeps its entry, and `## Components` lists
each ground, mode, pair and ratio under "The text on the action is under 4.5:1"; once the colours pass, the entry is written. DESIGN.md `## Components` then also names the grounds and says whether the owner
named them (`named_by_owner` starts with a real `YYYY-MM-DD` date and has words after it, the rule `contrast` holds it to) or they are the starter's proposal, and lists under "The tokens
give no colour for the following" each ground and mode with the roles it lacks (`ground colour`, text, action, on-action, focus, border). BRAND.md `### Grounds` (after `### Colour`) and
the applied skill (a `### Grounds` block appended to the `{{colours}}` fill, so under its `## Colour`; no new placeholder) hold the same block, a sentence on who named the grounds and one
table, a row per ground and mode: ground, mode, text, action, on-action, focus, border. A cell is the role name and its colour as the colour table prints it (`#rrggbbaa` when see-through), or "missing: ask the
owner". A `grounds` block of another shape in `tokens.json` stops `adapters` and `applied-skill` (exit 2) before anything is written.

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
dark) with the table of text grounds when the tokens list any (above), and the contrast pairs with their ratios, type families with the sizes, weights, line height and tracking the tokens define (`{{type}}`), the spacing, radius and layout values
(the optional `## Layout` section, through the template's `{{layout}}`: a whole section or nothing, as for motion, and left out when the tokens hold none), the mark files (relative to the skill), the small-size rule (from `qa/rules.json`, or the plugin's
proposal, said so), motion (the section above, through the template's `{{motion}}`: a whole section or nothing, so a brand without motion gets the file it always
had), what is never done, the G4 rules, the facts that may be claimed (contact facts left out). It needs G5 and `--yes` (without it: the plan on stdout, a
message on stderr, exit 2; `--plan` exits 0). The name is `<slug>-brand` (lower case, hyphens, at most 64 characters, no `claude` or `anthropic`). Gated by `check` like
the adapters (`applied-skill:file`, `applied-skill:state`).
The same builder (`adapt.applied_skill_md(project, template, kit=...)`) writes the kit's SKILL.md, with every path inside the kit (the tokens, the marks and the band drawings
under `brand/`, and the template's `{{kit}}` line filled with the kit section; see `kit`). Without a kit the template's `{{kit}}` line is dropped, as `{{motion}}` is, and the file is the bytes it always was.

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

**The last lint.** After the press kit, the chain lints the board of the latest round again (`board-lint rounds/rN/board.html` of the highest N, the board `check` looks for; when that round has no `board.html`, no step), then runs `staleness --write` and `check`. The lint report of a pick
board lists `FACTS.md`, `brief/BRIEF.md` and `research/cliches.md` as inputs and `check` wants a report that is current for the latest round, so an edit of the facts or the brief since the last lint would otherwise turn `check` not verified. A lint that exits 1 or 3
after it printed `report: <path>` goes on (`finish.sh: board-lint failed on <page> (see above); ...` or `finish.sh: board-lint could not verify <page> (see above); ...`), and `check` fails the report or says why; any other exit leaves no report of this board for
`check` to gate, so the chain says `finish.sh: board-lint stopped with exit N ...` and stops with that exit code.

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

- **Fixtures.** `evals/_shared/fixture.sh` holds the builders (`fx_r1_shown`, `fx_before_r1`, `fx_before_style`, `fx_before_site_refs`, `fx_refine`, `fx_judge`,
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
  container, `tests/run-all.sh --smoke` without `BRAND_CREATOR_REQUIRE_ALL` (only the parts `BRAND_CREATOR_TEST_PARTS` names, stopped
  at the deadline `BRAND_CREATOR_SUITE_MINUTES`), then `tests/docker/verify_log.py`, which also fails a part that was asked for and left
  no summary. `docker run --init --ipc=host`; with `BRAND_CREATOR_TEST_OUT` the run log and pytest's JUnit file are kept.
- **What counts as passing off macOS.** pytest and node:test have no failure, the smoke printed `SMOKE PASSED` (`emit apple` exit 3 with its
  message), and every skip is a NOT VERIFIED skip with an expected reason: `not macOS`, `actool is not available`, `the claude CLI is not on
  PATH`, and the missing denylist when `BRAND_CREATOR_DENYLIST` was not mounted. Any other skip is a bug. The exact counts and the banner
  are printed.
- **Off-macOS opt-ins.** `downscale` needs `--renderer=pillow|resvg` (or a recorded opt-in), `emit tauri` needs `--renderer pillow`; tests, the
  smoke and `finish.sh` (`DOWNSCALE_RENDERER`, `ICNS_RENDERER`) name them. Usage errors (exit 2) are reported before "cannot measure here"
  (exit 3), so a bad call gives the same answer on every OS.
- **CI.** `.github/workflows/brand-creator.yml` (at the monorepo root, working directory `plugins/brand-creator`, started by a push to `main` or a pull request that changes that folder or the file, never by a tag): `linux-suite` (the Docker run, one job per part: pytest, node, smoke), `validate` (`claude plugin validate --strict` and the manifest-mutation test;
  it fails when the CLI cannot be installed), `macos-suite` (one job for the `requires_macos` and `requires_actool` tests with REQUIRE_ALL=1,
  and one for each half of the Acme smoke, `ACME_SMOKE_PART=finish` and `rest`), and `brand-creator`, the verdict: it passes only when every other
  job passed, and a release tag `brand-creator--v*` is accepted only on a commit where it and `docs` passed. It never runs `claude plugin eval`.
