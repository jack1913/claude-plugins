# Changelog

All notable changes are listed here. The plugin version in `.claude-plugin/plugin.json` is bumped on every release
(this keeps `claude plugin validate --strict` and update detection predictable).

## 0.1.0 (unreleased)

### Stage 5

- Stage 5 review S5R-1: the watchOS appiconset is no longer drawn at the Icon Composer canvas (1088). It has its own spec row `apple-watchos-appiconset` (status U, 1024 px), so the pack stays labelled UNVERIFIED until a person checks the size in Xcode.
- Stage 5a: Tier B emitters. `brand-creator emit android` writes an adaptive launcher icon (foreground, background and an explicit monochrome layer; `mipmap-anydpi-v26`
  XML and density PNGs mdpi to xxxhdpi), legacy round and square icons, the Google Play icon (512, opaque 32-bit, sRGB chunk) and the feature graphic (1024 x 500,
  no alpha, from `templates/card.html`); a safe-zone gate refuses a mark whose ink leaves the 66 dp circle (nothing is written) and the monochrome layer is never
  skipped. `emit chrome-ext` writes the manifest icons 16, 32, 48 and 128 (PNG only, the 128 icon with the Web Store 96-in-128 rule), the store icon and the small
  and marquee promo tiles. `emit msix` writes the tile and store logos at scale 100, 200 and 400, the app-list target sizes each as the plain, unplated and
  lightunplated file, and an AppxManifest snippet. Full tier only; every size is a row of `platform-specs.json` (nine new rows: V, R and U); a file built from a
  U row carries the label "UNVERIFIED, recheck" and `check` fails one that lost it; `check` also gates the adaptive layers and the MSIX unplated trio
  (`tierb:` rows); the targets are in `finish.sh.tpl` for Full-tier projects.
- Stage 5b: `emit apple` writes a watchOS icon (one opaque square at the layout size, the mark inside the circle) and a tvOS icon (a two-layer image stack, 800 x 480 at 2x) for
  the targets `INVENTORY.md` or `--target` lists, each compiled by actool as a hard gate (watchOS has its own appiconset compile; tvOS uses `--platform appletvos --target-device tv`); the margins gate runs
  before any file is written. The actool gate now also reads `com.apple.actool.document.errors`: a tvOS stack layer that does not fill the stack makes actool exit 0 and write an `Assets.car`, which used
  to pass. `brand-creator emit profiles` (Standard and Full tier) writes a circle-safe avatar (400 and 800), the LinkedIn, X, YouTube and Facebook banners and the Instagram feed and story images from
  `templates/profile/banner.html`, each inside its safe area (a gate: a mark or name outside exits 1 and ships nothing), with `_proof/` images that draw the safe areas (never shipped); all new rows are status U and
  labelled, and `check` gates the labels and re-measures the ink (`tierb:profiles`). `templates/finish.sh.tpl` now runs `emit profiles`, `emit print` with `print-check` (opt-in with `PRINT_REGION`),
  the social posts (`POST_FACTS`), `book` and `book-pdf` (when `book/chapters/` exists) and `emit presskit`, each gated by the tier like the CLI; a value set for a step the tier does not allow
  stops the chain with exit 2. The Acme smoke now runs every Tier B emitter that applies and the whole Full-tier chain.

- Stage 4 review fixes. The brand book's cover and colophon keep the 16 px side gutter (and `shot` now records `gutter_left` and `gutter_right` per view); the
  cover's Adoption row says "approved <date>" for G6 and counts rows done from `adoption.json` instead of claiming "applied"; `check --cascade` searches `_build/`
  HTML (the text layer of OG cards, social posts and store frames); the adoption `accounting` row recounts name and colour lines with a second ripgrep run; a
  manual check for the e-mail signature in real mail clients.
- Stage 4d: the skills. `brand-book` (model-invocable, narrow: build, update, self-review, collapse, approve and export the book of an approved
  identity; generated books rebuilt byte for byte and never hand-edited, hand-authored books edited only by counted `patch` with an edition bump;
  a ten-item self-review table; BRAND.md, DESIGN.md and the applied skill only on the owner's yes at G5; `book.pdf` called an RGB proof).
  User-invoked wrappers: `/brand-creator:brand-adopt` (read-only survey; apply only on an explicit ask, on a branch the owner names, one repository at a
  time, an independent review with `cmp` and the repository's own build and tests, then fixes, then decisions; hooks never skipped; commit, merge and
  push separate asks, what a push triggers said first; live-service rows need their own OK; parent-site lockups byte-copied and previewed in a scratch
  copy), `/brand-creator:check` (gates plus `--cascade`), `/brand-creator:review` (self-review as one approvable list, optional lens panel behind the
  fleet gate) and `/brand-creator:launch` (one owner action at a time, with the reason and the click path). Phase 12 (history, ADR, governance, the
  project's memory) is written in full; phases 10, 11 and 13 gain the governance section, the apply and parent-site method, the trademark screening
  steps with dates and the print hand-off (spot colour as a name and a Lab target, no bundled profile, the printer's proof). `references/cascade.md` is
  a nine-step checklist with the surfaces that embed the old look. `CONNECTORS.md` documents optional `~~design tool` connectors (no MCP
  configuration ships). New templates `ADR.md` and `ADOPTION.md` (the frame `adoption` now renders through, adding the apply rules); the book chapter
  skeletons carry guidance in their fill markers and a Governance section. Trigger evals for `brand-book` and negatives for the new wrappers.
- Stage 4c: adoption, cascade, adapters, applied skill, launch. `brand-creator adoption survey` reads product repositories read only (ripgrep, `.gitignore`
  honoured) for old names and colours, icon and logo files, package and platform metadata and README badges, and writes `adoption.json` and `ADOPTION.md`:
  numbered rows with a content excerpt (line numbers drift), progress and pins stored apart so rows are append-only, a "Kept, not counted" list with a reason for
  every match that is not a row, identifiers for the rename list, counts built into the sentences; the survey proves it wrote nothing in a repository. `adoption add`
  appends a hand-written code-change row, `adoption status --set` records progress (doing and done need G6), `adoption verify` checks pins and rendering. `check
  --cascade` now searches every project artefact (book sources, README, tokens, text assets, templates, ADOPTION, LAUNCH, BRAND.md, DESIGN.md, the applied skill, PDFs
  as text) and the documents named by `tools/cascade.json`, `--also` or FAMILY.md `parent_docs`; adoption records of the old value in a product repository warn instead
  of failing. `brand-creator adapters --brand-md --design-md` (opt-in at G5) generates BRAND.md (Strategy, Voice, Visual, Governance; `type` and `architecture`
  frontmatter) and DESIGN.md from the tokens, BRAND-STATE.md and FACTS.md, both read by `staleness` and `check --cascade`; DESIGN.md is linted by `@google/design.md`
  0.4.0 (pinned in `scripts/package.json`, installed by `setup`), "not verified" when it is not installed. `brand-creator applied-skill --yes` writes a small
  `<slug>-brand` skill into the project's `.claude/skills/`. `brand-creator launch-todo` writes LAUNCH.md (trademark first, domains and handles with their check date,
  e-mail, renames, print hand-off, decisions; nothing outward is executed). Phases 11 and 13 are written in full. `prereq --for adoption` names ripgrep.
- Stage 4b: honest print, press kit and social posts. `emit print` writes a business card (front, back), letterhead and envelope as print PDFs and an
  HTML e-mail signature from the tokens, the outlined logo set and FACTS.md contact rows (`templates/print/`): the page is exactly trim + 2 x bleed with
  crop marks drawn in the template, Chromium prints it (`render.mjs pdf --size-mm`, which also measures every text, logo and line), Ghostscript outlines the
  text (`-dNoOutputFonts`), pikepdf sets MediaBox, TrimBox and BleedBox, the metadata and a fixed date and ID. Sizes come from the print_region table
  (`scripts/emitters/print-regions.json`: EU, US, JP; card, A4 or Letter, DL or #10, default bleed stated as printer-specific), chosen by `--region` or the
  brief. Without `--icc` the PDFs are labelled "RGB proof, not print-ready" (metadata and file name); `-dPDFX=4` is used only with `--icc` (a CMYK profile
  the owner supplies; none is bundled) and the file is then only a "PDF/X-4 candidate (preflight with your printer)". Nothing claims conformance.
  `print-check` (wired into `check` when print PDFs are in the manifest) reads the boxes back with poppler and checks page size, bleed, safe zone, line
  weight, reversed text, logo size, transparency, fonts, colour and the label against `--icc`, with owner thresholds in `qa/print.json`. `emit presskit`
  writes a deterministic press-kit zip; `emit social --posts` adds 4:5 carousel, 1:1 and educational post templates (`templates/social/`) filled from
  FACTS.md values, with the pre-publication checklist for a regulated profession. Print, press kit and posts are Standard-tier packs.
- Stage 4a: the brand book. `brand-creator book` generates a self-contained `book.html` (fonts and images inline, no script, no network, light and
  dark) from tokens, the manifest, BRAND-STATE.md, FACTS.md, the contrast and downscale reports and `book/chapters/*.md` (skeletons in
  `templates/book/`, a documented Markdown subset, computed blocks and counts), byte-identical on rebuild; `book-lint` (ids, anchors, network and
  script references, scratch, round and forbidden words, status words backed by FACTS.md, per-language key parity, mark_lint on every mark, required
  chapters, edition and APPROVED stamp, counts, manifest accounting, legal disclosures, leftover variants; `--self-consistency`: CSS durations
  within the motion tokens, font sizes at or above the minimum label size, colours within the tokens) is wired into `check`; `patch` is the assert-
  counted edit path of a hand-authored book and logs the edition; `collapse` removes losing variants and switchers from book sources and tokens
  with a dated copy; `book-pdf` (Chromium, pikepdf) exports an RGB proof labelled "RGB, not print-ready" in the metadata and on the cover
  (`render.mjs pdf`). BRAND-STATE.md gains `edition`, `approved_edition` (written by `state --record G5`) and `book_chapters`. Phase 10 is
  written in full; the Acme smoke builds, lints, exports and mutates the book.
- Walking skeleton, stage 1a: plugin manifest, `bin/brand-creator` entry point, script contract, setup and prereq,
  history/rounds guard hook, project scaffold, state and freeze, Chromium driver (shots, cards), logo sheet,
  contrast, board lint, mark lint, design-token build (DTCG 2025.10 to CSS, JSON, Swift, Android XML, colorsets),
  web and social emitters, tests and the Acme smoke.
- Stage 1b: orchestrator skill `brand-creator` (tiers, phase map, gates, RULES, response template, working style,
  review surface), user skills `new`, `round`, `status`, `setup`; references (phases 00/03/04/05/06 in full, stubs for
  the rest, board contract, working style, anti-pattern case cards, strategy core, prompt fragments, ai-defaults,
  architecture, cascade); templates `round-page.html`, `board.html`, `review/index.html`, `DECISIONS.md`,
  `tokens/*.tokens.json`; board-lint checks numbered questions with lettered options, the reflex test and unfilled
  `[[fill: ...]]` markers; the Acme worked example replaces the test fixture.
- Stage 1 review fixes: `contrast` now finds the colours that touch in the logo raster (resvg) and holds them to token
  targets with an exceptions register (`tokens/exceptions.json`, a reason per entry); G0 fits the AskUserQuestion tool
  (at most 4 choice questions, facts as plain text); skills call the bare `brand-creator` so the README permission rule
  matches; the guard also protects project roots and their parent folders, sees `bash -c`, `eval`, the bulk-argument
  runner and destructive `git` commands; `state --set` validates enum keys and the phase; `state` runs without uv.
- Stage 2a: `brand-creator names` (`scripts/check_names.py`): domain screening through RDAP (IANA bootstrap cached 24 h), whois
  and a DNS cross-check, plus npm, GitHub, Docker Hub, PyPI, crates.io and Homebrew for the software profile; known-taken and
  known-unregistered controls per source, REGISTERED / NOT-FOUND / UNKNOWN only, rate-limit handling, raw responses saved and
  replayable with `--offline`, a privacy gate (`--yes`), owner-run trademark links and a "screening, not clearance" memo.
  Recorded-response fixtures and tests; the live smoke is manual (`requires_network`). Skills always quote
  `--data "${CLAUDE_PLUGIN_DATA}"`; CONTRACT gains name-screening and testing sections; `dev/MANUAL-CHECKS.md` added.
- Stage 2b: phase 01 research in full (P1a constraints with tagged claims and a refute pass, P1b alternatives with the status
  quo first, five-competitor lineup, clichés and a map from them, P1c read-only surface inventory before round 1, optional
  site audit) with templates `research.md`, `cliches.md`, `INVENTORY.md`; the `brand-naming` skill (name language and profile
  asked first, metaphor territories, six styles, distinctiveness class, internal filter, meaning check per language, privacy
  OK, prior-art kill before screening, `brand-creator names`, owner-run trademark links, verdict memo from
  `templates/names-verdict.md` with a Launch TODO seed, G1); phase 02 points at it; strategy core drafting table and
  Guardrails block; regulated-industries 7-step method with a dated rules table; trigger evals for brand-naming and the
  user-invoked skills, with a shape test.
- Stage 2 review fixes: `names` writes raw responses to `raw/<date>/run-<n>/` (a second run the same day no longer rewrites the
  first run's evidence; a folder with several runs is refused for replay); `--offline` reports the date the recordings carry and
  says when it was replayed; raw files drop third-party personal data (allow-lists for GitHub, Docker Hub, npm, PyPI, crates.io
  and Homebrew bodies, RDAP vcards cut to their version line, whois contact blocks removed); a Quick project with an open name
  runs P2 before the board, stated at G0.
- Stage 3a: QA and mark tooling. `scripts/lib/px_lib.py` (RGBA buffer, deterministic PNG, ICO and run-length SVG writers, PNG
  reader) and a generated grid mark in the Acme example; `outline-glyphs` (fontTools instancer, skia-pathops overlap removal, one path
  per glyph, no live text) and `fontcheck` (cmap coverage per language set from data files en/pl/de/cs/fr/es/tr, licence hint, Chromium
  platform-font report with a control; `render.mjs fonts`); `downscale` (real `sips` downscale on macOS, explicit `--renderer` opt-in
  elsewhere, accent pixels, box and solid square, 4x4 px at 32 px and below as an owner-adjustable default, before/after);
  `logo-sheet --guides` (baseline, cap line, x-height and grid guides with measured offsets); `states-check`, `family-check` (family
  modes, `FAMILY.md` block), `contrast --cvd` (ColorAide Brettel and Viénot simulation, CIEDE2000, shared pair list with `distinct`
  role pairs); `shot --motion` (named states at 1x and 2x against the static SVG with a control pair, emulated reduced motion, layout
  shift 0); `snapshot`, `verify-idempotent` (explained allowlist with substitute checks, determinism rules for PNG, zip and PDF),
  `staleness` (`tools/inputs.json`), `specs-due`; size bands (`qa/rules.json`, one picker, slots record their band, exemptions) and
  `qa` gates on manifest rows, all wired into `check`; `content_languages` in BRAND-STATE; Acme smoke extended; the Inter test font
  and the Python dependencies are credited in THIRD_PARTY_NOTICES.
- Stage 3b: Tier A platform emitters, all reading sizes only from `scripts/emitters/platform-specs.json` (21 new rows with source,
  checked date and status V, R or U; `references/platform-specs.md` is generated from it and a test compares the two) and all
  writing as target-repo paths under `assets/<target>/` with manifest rows (slot, size, band, resampled-by, qa) on byte change only.
  `emit apple` (macOS with Xcode; exit 3 elsewhere): an Icon Composer `.icon` (default, dark, tinted) validated against the
  vendored giginet schema and validator, compiled with actool per platform (iOS, macOS, watchOS) as a hard gate with the fallback PNGs and
  `.icns` shipped and the Assets.car compared by its `assetutil --info` rendition list; the appiconset and an iconutil `.icns` only
  when INVENTORY.md or `--target` shows a target below 26; a visionOS solid image stack inside the safe circle (compiled for xros);
  colour sets from build_tokens; the menu-bar template, a flattened 1024 marketing icon with no alpha channel, a DMG background at 1x and
  2x and App Store screenshot frames (frames only); ictool previews on request. `emit windows` (.ico, 24-bit NSIS BMPs with the bit depth
  read back), `emit linux` (hicolor, scalable SVG, AppStream stub whose text fields come from FACTS.md only), `emit tray` (shape-coded state
  sets from `tray/tray.json`, light and dark taskbars, Linux, macOS template, then the states-check gate; `states-check` now reads
  `qa/states.*.json` too), `emit tauri` (icons folder; `.icns` by iconutil, or Pillow only behind `--renderer pillow`), `emit wallet`
  (Apple pass images at @2x and @3x, Google logo and wide logo), `emit developer` (e-mail logo at 1x to 3x, registry icon, org avatar, CLI
  identity text with 24-bit colour only where it reaches 4.5:1 on a white and a black ground). `templates/finish.sh.tpl` (the ordered
  chain with the `BRAND_CREATOR_CHAIN` guard; `require_chain()`), INVENTORY.md gains a Deployment targets section, `check` reads every
  `emit-<target>` report, `verify-idempotent`'s assetutil compare now strips the UUID, digest and timestamp that made two compiles of one
  catalogue differ (found on the first real Assets.car), the Acme smoke emits every pack.
- Stage 3c: the `brand-assets` skill (model-invocable; standalone entry from a mark file into `./brand-assets/` with srgb tokens
  from the mark's own colours, an audit and owner decisions; raster input warned, tracing with potrace only as an approved step;
  project entry from INVENTORY.md slots through size bands, emitters and the downscale proof to `check`; what runs where for
  non-mac users). Phases 07-tokens and 09-qa written in full, 06-mark extended (existing-mark audit, outlined-glyph order, size
  bands, accent rule), 08-assets reduced to a pointer. 09-qa lists every check command, what it blocks and the test that
  proves it (a test fails on a cited test that does not exist, a wrong mutation label, or a check command missing from the
  table). `templates/MOTION-SPEC.md`. Trigger evals for brand-assets with sibling cases; the Acme smoke runs the standalone entry.
- Stage 3 re-check fixes: a crash (any unexpected exception) now records `fail` in the open reports and exits 1; retirement warnings name
  the real `removed-<date>[-n]/` folder.
- Stage 3d (review fixes): `downscale` writes one report per master (`assets/_checks/downscale/<slug>.json`) and a manifest row with
  `qa: ["downscale"]` records `downscale_source`; `check` needs the passing, current report of that very file, so a pass on another
  master no longer vouches for a failing one. Before/after compares only the earlier report of the same source, method, master size,
  accent and ground. `emit web` follows the size bands (every favicon layer and PNG icon is drawn for its own size, recorded in the
  manifest, and `check` re-reads every `.ico` layer's band). `templates/finish.sh.tpl` passes options as quoted arrays (multi-word
  taglines and exemptions work), gets `BRAND_CREATOR_ROOT` from the new `brand-creator root`, runs the downscale gate for every master a
  row names, and is run end to end by a test and the smoke. Emit reports list every file the emitter read (FACTS.md, INVENTORY.md,
  `tray/tray.json`, `qa/rules.json`) once, and the staleness globs cover FACTS.md, INVENTORY.md and `tray/*.json`. Rows and files of slots
  an emitter no longer writes are moved to `removed-<date>/` and reported. A run that stops through an error rewrites its report as failed.
  `emit developer` gains `--content-fraction`.
