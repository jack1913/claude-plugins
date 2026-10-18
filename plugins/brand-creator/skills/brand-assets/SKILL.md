---
name: brand-assets
description: Turns an approved logo or mark into the platform files a product ships, with a manifest and size checks at real pixels. Covers favicons and PWA icons, Open Graph and social images, Apple app icons, Windows .ico and installer art, Linux icon themes, tray icons, Tauri, Wallet passes and developer surfaces. Works from a mark file and a target list, or from a brand project's surface inventory. Files from an existing, approved mark only; not for designing or redrawing a logo, fixing how a page shows a logo, resizing one image or building UI.
when_to_use: Use when someone has a finished mark and needs it as platform files ("favicons from my logo.svg", "app icon set for iOS and macOS from this SVG", "make the .ico and tray icons", "OG image from our logo"), or when a brand-creator project reaches P8 asset packs. Polish triggers include "favicony z logo", "ikony aplikacji z logo", "wygeneruj ikony", "zestaw ikon dla iOS", "plik .ico z logo".
compatibility: Claude Code only (calls the plugin's bin/ entry point). Apple packs need macOS with Xcode and have no fallback. Off macOS the small-size check needs an explicit --renderer opt-in and the Tauri .icns needs --renderer pillow. Social images and store frames need the Chromium installed by /brand-creator:setup.
allowed-tools: Bash(brand-creator *)
---

# Brand assets

Turns a mark the owner has already approved into the files each platform needs, at the sizes the platforms publish, with
a manifest and measured small-size checks. It never designs, redraws or "improves" the mark. A fault found at small sizes
is reported with numbers and handed back to the owner. Fixing it is design work, done in a brand-creator project (P6).

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

## Contents

- [Pick the entry](#pick-the-entry)
- [Running the tools](#running-the-tools)
- [What runs where](#what-runs-where)
- [Standalone entry: a mark and a target list](#standalone-entry-a-mark-and-a-target-list)
- [Project entry: INVENTORY.md to packs](#project-entry-inventorymd-to-packs)
- [Rules every pack follows](#rules-every-pack-follows)
- [Apple](#apple)
- [Tray](#tray)
- [Pitfalls](#pitfalls)
- [References](#references)

## Pick the entry

1. Run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. A brand project above the current folder → the
   **project entry**. It is also the entry when the brand-creator skill sends you here at P8.
2. No project, and the person has a mark file (SVG, PNG, JPG or PDF) → the **standalone entry**. It writes everything
   into `./brand-assets/` and nowhere else.
3. No mark yet, or the person wants the mark changed → this skill does not apply. Offer the brand-creator skill.

## Running the tools

Call the entry point by its bare name, always in this form:

```
brand-creator --data "${CLAUDE_PLUGIN_DATA}" <subcommand> --project <project-dir> ...
```

Exit codes: 0 pass, 1 a gate failed, 2 usage error, 3 cannot run (a missing tool, the wrong platform or a missing
opt-in). On 3, stop that target, tell the person the fix the message names, and carry on with the targets that can run.
Never produce the file another way and never call a check that did not run "passed". Say "not verified" and why.

## What runs where

| Target | macOS | Linux and Windows |
|---|---|---|
| `emit web`, `emit social`, `emit windows`, `emit linux`, `emit tray`, `emit wallet`, `emit developer` | yes | yes; Windows runs are untested in this version |
| `emit apple` (`.icon`, actool compile, `.icns`, visionOS stack) | yes, with Xcode | no: exit 3, no fallback. Say so plainly: the Apple files must be built on a Mac |
| `emit tauri` `.icns` | iconutil (default) | only with `--renderer pillow`, which has no 16 px entry (the report says so); otherwise exit 3 |
| `downscale` (the small-size proof) | `sips -z`, the real system downscale | exit 3 until the owner opts in to `--renderer=resvg` (SVG) or `--renderer=pillow` (PNG). Record the opt-in once with `--record-renderer`; every report then prints the method |

Numbers from different downscale methods are not comparable. Compare a size only with a report made by the same method;
`--previous` falls back to the last report whatever its method, so read the method line of both.
For non-mac users, say this up front: "The Apple files need a Mac with Xcode. On this machine the small-size check
runs only if you agree to use resvg instead of the macOS resampler, and its numbers differ from what macOS will show."

## Standalone entry: a mark and a target list

1. **Ask once.** One AskUserQuestion call, at most 4 questions, each with 2 to 4 options and one "(Recommended)":
   targets (web only (Recommended) / web and social / web and app icons / every target), and whether a dark version of the
   mark exists. Name, site URL and any tagline go in one plain-text message after the call. Social images copy only words
   the person confirms, and those go in FACTS.md first.
2. **Check the input before anything else.**
   - **SVG:** it must be pure vector. Live text, `font-family`, `@font-face` and external references fail `check`
     (mark_lint). Ask for an export with outlined text. Do not outline it yourself unless the person names the font and
     asks (`outline-glyphs`, see [06-mark](../brand-creator/references/phases/06-mark.md)).
   - **PDF:** convert with `pdftocairo -svg logo.pdf logo.svg` (poppler), then treat it as SVG. Live text in the PDF
     will fail mark_lint.
   - **PNG or JPG:** warn first: "This is a raster. Icons drawn from it will be soft at large sizes and the small sizes
     cannot be redrawn." Then offer three options: (a) the vector file from whoever made the logo (Recommended);
     (b) a traced vector as an explicit step; (c) a redraw, which is a brand-creator project with mark source
     `authored-vector`. Trace only after a yes. Never trace silently, and never ship a trace without the person's
     approval.
   - **Tracing (b):** run `magick logo.png -background white -alpha remove -alpha off -colorspace Gray -threshold 50% logo.pbm`,
     then `potrace logo.pbm -s -o traced.svg`. potrace draws one colour. Set the fill to the mark's colour. A mark with
     several colours needs one trace per colour, or a redraw. Show the original and the trace side by side
     (`logo-sheet --svg traced.svg`), say what changed, and record the approval in DECISIONS.md.
3. **Scaffold.** Run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" new brand-assets --name "<Name>" --tier quick --root .`.
   This refuses an existing non-empty `./brand-assets/`, so ask for another folder. Then run
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project brand-assets --set mark_source=existing`, record G0
   (`--record G0 "standalone brand-assets: existing mark; targets <list>"`) and G3 (`--record G3 "owner's existing mark,
   used as supplied"`). Every emitter refuses to run without G3.
4. **Place the mark** as `brand-assets/assets/logo/mark.svg` and, when it exists, `mark-dark.svg`. These are copies; the
   person's file stays where it was.
5. **Tokens from the mark's own colours.** Copy `${CLAUDE_PLUGIN_ROOT}/templates/tokens/*` to `brand-assets/tokens/`.
   Write every flat colour of the mark as a primitive in `srgb` (`{"colorSpace": "srgb", "components": [r, g, b],
   "hex": "#rrggbb"}`, components 0 to 1). That is exact, with no conversion. Point `color.mark` (and `color.accent` when
   the mark has one) at them, and pick `color.bg` and `color.text` for the grounds. Never invent brand colours. Run
   `tokens`, then `contrast`. It names every colour of the artwork that is not a token, and every colour that touches a
   ground below the target.
6. **Audit before emitting.** Run `logo-sheet` and Read `assets/_checks/logo-sheet.png` (16 to 180 px, light and dark).
   Run `downscale --source assets/logo/mark.svg` (see [What runs where](#what-runs-where)). Report what you measured:
   "the accent keeps a 2 px solid square at 16 px" is useful; "looks fine" is not. Each finding gets options, and the
   person decides; record the decision in DECISIONS.md with the measured value:
   - A mark with no dark version usually fails on a dark ground, or its colours touch too softly there: (a) the person
     supplies a dark version; (b) a rule that the mark always sits on a light tile; (c) an exception with a reason in
     `tokens/exceptions.json`.
   - An accent under the 4×4 px rule at 16 px fails `downscale`, and a failing report blocks `check`: (a) a small-size
     drawing, which is design work (a brand-creator project); (b) the person sets their own minimum in `qa/rules.json`
     (`{"schema": 1, "downscale": {"accent_min_px": 2}}`). Never change the number yourself to make the gate pass.
   Ship weaknesses named, never hidden.
7. **Emit** each chosen target (`emit web`, `emit social --tagline "<FACTS line>"`, and the others). Read each report and
   the smallest image of each pack.
8. **Gate and hand off.** Run `check --project brand-assets` until it exits 0 (or 3 with the reason stated). Then list
   the files by target, point at `assets/manifest.json` and `assets/web/head.html`, and say what to copy where. Copying
   into the person's site or app is a separate ask, done one step at a time.

## Project entry: INVENTORY.md to packs

Preconditions: G3 is recorded (`state --require G3`), tokens are built, and `INVENTORY.md` exists from P1c (Full tier,
product-in-family) or BRAND-STATE records `inventory: none (no target repo)`. With no inventory, the targets are the
required surfaces in `brief/BRIEF.md`.

1. **Slot table.** Read the inventory's Slots and Deployment targets. Show one table in chat: slot ID, target and file,
   platform-spec row and its status, resampled by (`OURS` our drawing at the exact pixels, `SYS` one master the system
   shrinks, `PAGE` drawn by the page), and band. Build only slots whose state is MISSING or STALE, plus whatever the
   owner adds. A spec row with status U or R is named, with what U means: nobody has read the platform's page yet.
   `specs-due` lists them.
2. **Size bands.** `qa/rules.json` `bands` name the drawing per body size, for example a coarse-grid drawing up to 32 px
   and the fine vector above. They are G4 "(rule)" items and the owner's call. Hand masters exist only where the exact
   pixels ship: favicon layers, `.ico`, PNG icons, tray, Linux hicolor. Apple builds every size from one master.
   `emit web`, `emit windows`, `emit linux` and `emit tray` draw each size by the band rule, and `check` fails a layer
   recorded off the rule. `icon.svg` is one scalable file and stays the default mark.
3. **Emit in chain order.** Copy `${CLAUDE_PLUGIN_ROOT}/templates/finish.sh.tpl` to `tools/finish.sh` and fill its
   three marked blocks (the options of block 2 are variables; a tagline or exemption with spaces is fine). The order is
   generators, tokens, contrast, emitters, gates, idempotence, staleness, check. Run the emitters one at a time while you
   build, then the whole chain. An emitter moves the files of slots that no longer exist (a removed tray state) to
   `removed-<date>/` and says so in its report.
4. **Downscale proof.** For each `SYS` master run `downscale --source <master>`, with `--previous <older master>` for a
   before/after. Each master has its own report and `check` ties every manifest row to the report of its own master
   (`downscale_source`): a passing report on another file never vouches for it. The default content fraction of a master
   can leave the 16 px accent under the rule (`--content-fraction`, in finish.sh `ICON_CONTENT`): measure, then set. For a raster as shipped run `downscale --png <file>`. Read the numbers. At 32 px and below the accent
   must hold a solid 4×4 px square (the default rule; the owner may change it in `qa/rules.json`). A shrunk master that
   fails needs `--master-band <band> --exemption "<one line why>"`, then a new measurement.
5. **Tray and state sets.** `emit tray` reads `tray/tray.json`, writes `qa/states.tray.json` and runs `states-check`.
   Two states that look alike in greyscale or silhouette fail the emit.
6. **Prove and gate.** Run `verify-idempotent --cmd "<the chain>"` (two runs, byte-identical), then `staleness --write`,
   then `check --project <dir>` until it exits 0.
7. **Report** with the brand-creator response template. Set each built slot to EXISTS in INVENTORY.md. Copying into the
   product repos is P11 and waits for G6.

## Rules every pack follows

- **Sizes come only from the spec table** ([platform-specs](../brand-creator/references/platform-specs.md), generated from
  `scripts/emitters/platform-specs.json`). Never type a size from memory. Each emitter stamps the rows it used into the
  manifest and warns for U, R and stale rows.
- **One master per shrinking system, one drawing per shipped size.** A file a system shrinks (the Apple master, the
  registry icon, the avatar) is one large file. If its small sizes need the coarse drawing, pass `--master-band` and an
  `--exemption`. The manifest records it and `check` re-reads it.
- **No invented text.** Store frames, the AppStream stub and the CLI identity copy only FACTS.md rows. `--tagline` must
  be one of them, and a field with no row stays empty and is reported. Frames carry the mark, the name, one real line and
  an empty screenshot area. Never an interface, a rating or a feature.
- **No silent fallbacks.** A missing tool is exit 3 with the install command. See [What runs where](#what-runs-where).
- **Write only on a byte change; two runs are byte-identical.** Compiled catalogues are compared by their rendition list,
  not by bytes.
- **Dark artwork** is `<drawing>-dark.svg` next to the drawing. Without it, the light drawing is recoloured through the
  token roles light to dark, with a warning. A colour the tokens do not map stops the emit.

## Apple

- The `.icon` is validated against the vendored schema before actool compiles it for iOS, macOS, watchOS and visionOS.
  A failure is exit 1 with actool's own words. The compiled watch icon is 1024 px. The 1088 px HIG layout size only
  matters for `--previews` (ictool, iOS, macOS and watchOS only, masked output, never shipped).
- The legacy appiconset and `.icns` exist only when INVENTORY.md's Deployment targets (or `--target iOS=17.0`) show a
  platform below 26.
- visionOS keeps the mark inside its safe circle. A mark that fills the square needs a lower
  `--visionos-content-fraction`; the gate fails rather than shrinking it silently.
- The marketing icon is RGB with no alpha channel. The App Store no-alpha rule is status U in the spec table.
- Without Chromium set up, pass `--no-cards`. Otherwise the DMG background and store frames stop the emit with exit 3.

## Tray

State names and artwork are the project's (`tray/tray.json`). A master is used at its own size and enlarged only by a
whole factor. A size with no fitting master is an error, never a blurry resample. The dark set is an exact recolour
through the token roles. Colour alone never tells two states apart.

## Pitfalls

- Shipping a fine vector as the one master a system shrinks, so the accent smudges at 16 px. Measure with `downscale`,
  choose the band and record the exemption.
- Tracing a raster without asking, or presenting a trace as "the logo".
- A size table copied from an old pack. Read the spec row and its status instead.
- Running one generator alone and wiping files the chain refills. Use the chain; `require_chain()` refuses a lone run.
- Store or package copy nobody confirmed. Use FACTS.md only.
- Telling a Linux or Windows user the Apple pack "failed". It cannot run there; say where it can run.

## References

- [platform-specs.md](../brand-creator/references/platform-specs.md): every size, its source, date and status.
- [06-mark](../brand-creator/references/phases/06-mark.md): size bands, accent rule, guides, outlined glyphs.
- [09-qa](../brand-creator/references/phases/09-qa.md): every gate, what it blocks, and the test that proves it.
- `${CLAUDE_PLUGIN_ROOT}/scripts/CONTRACT.md`, "Platform specs and emitters" and "QA gates and mark tooling": flags and
  report fields.
