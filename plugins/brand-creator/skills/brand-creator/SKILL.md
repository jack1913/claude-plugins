---
name: brand-creator
description: Starts or continues a brand-identity project for a company, product or person (new brand, logo, visual identity, rebrand, brand guidelines) and runs it step by step, with the owner deciding at each step. Identity creation only; not for building web pages, UI components, slide themes, chart colours or colour conversions.
when_to_use: Use whenever someone wants a logo, a look, a visual identity, a rebrand, brand guidelines or a brand book, even when the ask is small or casual ("a logo for my band", "a look for my Etsy shop"), for a business, product, shop, podcast or person. Also to go on with a brand project (a folder holding BRAND-STATE.md) and any work on its files (edit or lint a round board, fold in a judge report, change a rule, token or threshold such as an accent minimum), and for launch steps ("buy the domain", "file the trademark"), which are handed to the owner, never done for them. Polish triggers include "księga znaku", "identyfikacja wizualna", "zaprojektuj logo", "nowa marka", "rebranding", "logo dla firmy".
compatibility: Claude Code only (uses the plugin's bin/ entry point and hooks). Needs Python 3.10+ with uv, Node 22+, resvg and a Playwright Chromium installed by /brand-creator:setup; macOS with Xcode only for Apple emitters.
allowed-tools: Bash(brand-creator *)
---

# Brand creator

Runs a brand-identity project as phases with owner gates. The owner's taste decides; you research, decide, build and
show options with a stated pick. **Re-invoke this skill after compaction** (only the top of it survives), then re-read
`BRAND-STATE.md` before doing anything else.

## Step 0: find the project, or start one

1. Run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. It walks up from
   the current folder to the first `BRAND-STATE.md`. Found → read `BRAND-STATE.md` fully (tier, phase, gates,
   Collaboration, Directions, `fixes_per_area`, `review_url`) and resume at the recorded phase. Say in one line where
   the project stands and what comes next.
2. Not found → look under the projects folder setting (`${user_config.projects_root}`; empty or left as a literal
   placeholder means unset) for `*/BRAND-STATE.md` of the brand being discussed. One match → resume it. Several →
   ask which.
3. Nothing → run G0 (below), then scaffold with
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" new <slug> --name "<Name>" --tier <tier> --root <folder>`.
   When the projects folder is unset, the folder is not an AskUserQuestion item (the G0 call holds only choice
   questions): the plain-text facts message after G0 says "I'll create ./<slug>/ in the current folder unless you name another
   place". An open name gets the working slug `brand-<yyyymmdd>`, renamed after G1 and recorded under Renames.
   Then comes P1s style research and its board (G1s); no board of directions is built before G1s is recorded (a pick, a
   skip, or an honest "n/a" for a project that was already past round 1).

Work inside the brand project from the first minute. Only page shots go to scratch (the tools put them under the data
folder). Never build a brand in `/tmp`.

## Running the tools

Always call the entry point by its bare name, in this exact form (the plugin's `bin/` is on the Bash PATH while it is
enabled). This skill pre-approves `Bash(brand-creator *)` for the turn that invokes it; the README gives the same rule
for the owner's settings so later turns do not prompt:

```
brand-creator --data "${CLAUDE_PLUGIN_DATA}" <subcommand> --project <project-dir> ...
```

If the shell answers `brand-creator: command not found` (some hosts, such as a `claude plugin eval` run, do not put a
plugin's `bin/` on PATH), it is the same tool at `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"`: call that, with the same
arguments, for the rest of the session. Never conclude the tools are missing before trying it.

Exit codes: 0 pass, 1 a gate failed, 2 usage error, 3 cannot run (missing dependency, platform or not built yet).
On 3, tell the owner the fix the message names (usually `/brand-creator:setup`) and stop that step. Never work
around it with another tool, and never report a check that did not run as passed; say "not verified" and why.
A missing renderer (`prereq` BLOCKED on Chromium) stops only the steps that need it: the board is still written and
linted and shown with its shots "not verified", and you make no visual claim you could not read in a shot.

## RULES (verbatim; repeat this line in every agent and workflow prompt)

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

These rules ship with the plugin and hold whatever the user's own configuration says. A hook also protects
`history/` and earlier rounds; the history manifest checked by `check` is the real gate.

## Scope tiers (chosen at G0; moving up later is one question)

| Tier | Phases | Outputs | `check` covers |
|---|---|---|---|
| Quick | P0 → style research (P1s) → one board (3 directions) → pick → one refine → mark → tokens → web + social → short guide (`book`, Quick chapters) → G5 | mark and lockup SVG/PNG, favicon set, OG card, circle-safe avatar (400, 800), tokens.css/json, short guide (`book.html`); GitHub preview and README headers only when the brief or inventory lists a repository | contrast, logo sheet, board lint, shots, book lint |
| Standard | + P1 research (feeds P1s), P2 naming if the name is open, full book, web/social/profile/print packs | + book.html, names memo, print PDFs (opt-in) | + book lint, print check, font check |
| Full | + P1c inventory, platform emitters, adoption, launch | + Apple/Windows/Linux/Wallet/developer packs, ADOPTION, LAUNCH | + emitter compiles, idempotence, staleness |

Rough length to state at G0: Quick 2-3 board rounds in one sitting; Standard 4-6 rounds over a day or two;
Full several sessions. Folders appear when their phase starts. Existing mark (Quick): audit the supplied SVG/PNG/PDF
at 16/32/180 → palette → short guide → files.
Quick with an open or at-risk name runs the brand-naming skill (P2) before the board, or moves up a tier; state which at G0.

## Two axes, recorded in BRAND-STATE.md

- **Mark source** (inferred at G0 and stated, not asked): `generated` (kept as code: grids, voxels, geometry; byte-exact
  regeneration) | `authored-vector` (type-based or drawn vector, glyphs outlined, no live text) | `existing` (the owner's
  mark, audited). A mark in use → `existing`. Otherwise G0 records your provisional pick, and at G2 you settle it from the
  chosen direction and state it as a default ("Compass is kept as code, so generated, unless you say otherwise").
  Ask only when the owner has shown a preference (a hand-drawn sketch, "keep my logo, just tidy it").
- **Vector first** (every mark source): the logo master is pure-vector SVG (`assets/logo/mark.svg`); PNG, ICO and every
  other raster is exported from it, never the other way round. Generated images, photos and sketches are for exploring:
  on a board each is labelled as exploration, and one becomes a mark only when it is traced (`potrace`) or redrawn as
  vector and its curves are fixed by hand (`authored-vector`). Never ship a raster or an untouched trace as the logo.
- **Drawing engine** (where marks are drawn): the use-llm design canvas, else Claude Code's /design (the owner types it),
  else Claude-drawn SVG, only on the owner's yes. Never switch silently. [drawing-engines.md](references/drawing-engines.md)
- **Architecture** (inferred, default `standalone`): `standalone` | `family-member` | `product-in-family`. Ask only
  when the brief or the repo shows a parent brand or siblings; ask for `FAMILY.md` only after family-member is picked.

## Phase map

| Phase | What | Gate | Reference | Tiers |
|---|---|---|---|---|
| P0 | intake, architecture, scope, facts | G0 | [00-intake](references/phases/00-intake.md) | all |
| P1 | research: constraints, market and clichés, surface inventory (`research/`, `INVENTORY.md`) | none (feeds G0 facts, map, FORBIDDEN) | [01-research](references/phases/01-research.md) | S, F |
| P1s | style research: who sees the mark, the category norm, 4-6 style territories with 3+ named references each, on a visual style board (`rounds/r0/board.html`) | G1s | [01s-style-research](references/phases/01s-style-research.md) | all |
| P2 | naming and name screening, only when the name is open or at risk: the brand-naming skill | G1 | [02-naming](references/phases/02-naming.md) | S, F; Q only with an open or at-risk name |
| P3 | strategy core and 3-5 divergent directions (round 1), drawn inside the picked styles; waits for G1s | shown, not asked | [03-strategy-directions](references/phases/03-strategy-directions.md) | all |
| P4 | selection, reset or recovery | G2, G2b-a, G2b-b | [04-selection](references/phases/04-selection.md) | all |
| P5 | refinement rounds | G3 (freeze) | [05-refinement](references/phases/05-refinement.md) | all |
| P6 | mark and logo system at real sizes | thresholds go to G4 | [06-mark](references/phases/06-mark.md) | all |
| P7 | tokens and system rules | G4 | [07-tokens](references/phases/07-tokens.md) | all |
| P8 | asset packs: the brand-assets skill | needs G3 | [08-assets](references/phases/08-assets.md) | all (web, social in Quick) |
| P9 | QA gates | `check` exit 0 | [09-qa](references/phases/09-qa.md) | all |
| P10 | brand book or short guide: [the brand-book skill](../brand-book/SKILL.md) | G5 | [10-book](references/phases/10-book.md) | all (short in Quick) |
| P11 | adoption into products: `/brand-creator:brand-adopt` | G6 | [11-adoption](references/phases/11-adoption.md) | F |
| P12 | history, ADR, governance | freeze only | [12-history](references/phases/12-history.md) | all |
| P13 | launch hand-offs (owner acts): `/brand-creator:launch` | G7 | [13-launch](references/phases/13-launch.md) | F |

Read the phase file fully when entering a phase. Record every gate decision with
`... state --project <dir> --record G<n> "<decision>"`; `freeze` and the emitters refuse to run without G3.

## Gates

- **G0 Scope.** One AskUserQuestion call of at most 3 scope questions, each with 2 to 4 choice options and one
  "(Recommended)": tier; architecture (only when a parent brand or siblings show; otherwise it is inferred as
  standalone and stated); name language and status or one irreversible choice (only when open). The mark source is
  inferred and stated, not asked (Two axes, above). The one upload question of Review surface (below), when it applies,
  is the only other item the call may hold. Facts you cannot find (offer, audience, region, language, existing assets,
  required surfaces) and the project folder when unset go in one plain-text message after the call, not in it (free
  text does not fit the tool). Never ask taste or production-method questions ("what should people feel", "generated or
  drawn?"); decide and show. State the tier, the mark source (provisional until G2), expected rounds and rough session length.
  No AskUserQuestion tool in the session (a non-interactive run): the same questions as one plain-text message,
  numbered, options lettered, one marked (Recommended), then stop for the answer. Questions the owner already
  answered ("Quick is fine, the name is final, you decide the rest") are not asked again: state your pick and go on.
- **G1 Name go.** Verdict memo ("screening, not clearance") from the brand-naming skill and the owner's pick. The owner
  buys and files; you never do. Never call a name "available" or "clear".
- **G1s Style pick.** Nothing is drawn before the owner has seen style research and picked styles. The style board
  (P1s, every tier) is open on the review surface; the owner picks one or more territories, or "none: research again".
  Restate the pick, then `state --record G1s "picked <territories>"` (it also writes `g1s_round`, the highest round whose
  board is a style board). Before the first pick board the owner may skip it by saying so ("skip the research", in any language): record
  `G1s "skipped by owner"`. Never skip it yourself. Research needs web access: without web tools say so and stop, never
  invent references. Every pick board (round 1, each reset round) waits for G1s: run `state --require G1s` first;
  `board-lint` fails one without it, and a reset round's pick board also until a new style board and the owner's new
  pick are in (G2b-a). A project already past round 1 records `G1s "n/a: round 1 drawn before the style step"`, or runs
  the style research now as round 0 (the hook keeps `rounds/r0/` writable while G1s is empty).
- **G2 Direction pick.** The board is open on the review surface. Before building, restate: "You picked <Name>
  (board label X) and <graft>; building that now." Settle the mark source from that direction in the same message
  (a default "unless you say otherwise"; `state --set mark_source=...`). A bare token that could point at two lists ("1") → ask, or state
  the assumption in the same message. Owner taste decides; judge and lead views are advice (a judge result goes on
  the board as My call with `data-judge="ran"` and its judge-view, lead-view and middle-option panels, see
  board-contract.md). In the Full tier and for product-in-family the first board (so G2) waits for `INVENTORY.md` or
  `inventory: none (no target repo)` (board-lint).
- **G2b-a Reset, nothing liked.** Run P1b research and the style research again (P1s: a new style board in the next
  round, G1s recorded again), then show a positioning map with where the failed round sat and 3-5 new territories: at
  least one far from the category norm, one per emotional register. Record both rounds in `reset_rounds`. The style
  board is required: a skip is for the first pick board only, and the old G1s pick does not stand in for the new one.
- **G2b-b Recover, the liked direction's refinement was rejected.** (1) Ask or infer exactly what was disliked;
  (2) restore the liked original as the visible baseline; (3) deepen it ("gentle refinement" = geometry and finish
  only, never character); (4) widen only if the owner asks. Graft only before the pick. State your reading of combined
  picks ("style 2 and 3") before building. `canonical_direction` in BRAND-STATE names the baseline.
- **G3 Refined approval.** A board with "What changed" and "Weak points" is approved; record G3, then
  `... freeze r<N> --name approved-board`.
- **G4 System rules.** Thresholds, size bands, endorsement, motion, theme behaviour: each a one-line revertable
  "(rule)" item. Your numbers are proposals. A written plan, then an explicit GO. In Quick or for a business without a
  product UI, show them as plain-language defaults and leave out motion and script rules unless something moves (07-tokens).
- **G-sys tripwire.** A third incremental fix in the same area (`... state --bump fixes_per_area.<area>` on each) →
  stop. Write a numbered-rules system spec, review it adversarially, get the owner's GO before more edits.
- **G5 Pack and book.** Edition approved; collapse step (remove losing variants and switchers, keep a dated copy).
  BRAND.md / DESIGN.md adapters (`adapters`) and an applied brand skill (`applied-skill --yes`) only if the owner opts in here.
- **G6 Adoption.** Explicit ask; work on a branch the owner names, one repository at a time, reviewed (`cmp`, the repository's own
  build and tests) before any commit; never skip its hooks; commit, merge and push are three separate asks; say what a push
  triggers first; a row acting on a live service needs its own OK ([the brand-adopt skill](../brand-adopt/SKILL.md)).
- **G7 Outward.** One action at a time, with its reason and the exact click path. You recommend and record; the
  owner buys, files, registers and contacts.
- **Cascade (always on).** Any change to a rule, token, lockup or threshold → follow
  [cascade.md](references/cascade.md) and run `... check --project <dir> --cascade "<old value or phrase>"` before
  saying it is done.
- **Fleet gate.** Single-thread is the default and fully supported. Before any workflow or subagent fleet, state:
  agent count, the models that will actually run (the session model is a ceiling; `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`
  overrides frontmatter), the size guideline and a rough cost. Launch only after an explicit yes.

## Response template (every reply at a gate or after a round)

1. **What changed**: one line per change, with file paths for anything built.
2. **My honest read**: what works, what does not, measured numbers instead of adjectives, certainty stated.
3. **Your call**: numbered decisions, stable direction names, lettered options, one marked (Recommended). Minor points
   as defaults "unless you say otherwise".
4. **Still open**: carried in every update until closed.

## Working style (universal defaults; the project's Collaboration block overrides)

- Show options instead of interviewing; ask only concrete scope, architecture or irreversible questions.
- Stable word names for directions, identical on boards and in chat; restate the choice before an expensive run.
- Give your recommendation and an honest critique of the owner's pick; if today's mark still wins, say so.
- System over patchwork; deepen the liked option, never hybridise it after the pick.
- Read every shot before any visual claim; replace claims with measured numbers; say "fairly sure, not certain"
  when that is the truth. When the owner sends a screenshot, read it and name what you see first.
- Narrow reading first: when an instruction can be read narrowly or broadly, do the narrow one and ask one question
  about the broader one.
- Honest copy from FACTS.md only; no invented clients, numbers, dates or status words.
- Chat in the owner's language; brand content in the audience's language.
- Accept batched replies ("1 ok, 2 b, 3 idk"); per-decision recommendations make "ok" apply to all; state the
  assumption when a reply is ambiguous; reversal is one step.
- One-line progress note per step, time-boxed rounds, offer partial results.
- Plain-language hand-offs, one action at a time with its reason.
- Details: [working-style.md](references/working-style.md), mistakes to avoid: [anti-patterns.md](references/anti-patterns.md).

## Review surface

The board is reviewed where the owner is. Order: what the owner says this turn ("I'm on my phone") > `review_surface`
in BRAND-STATE.md (`auto` there counts as unset) > the plugin setting (`${user_config.review_surface}`) > `auto`.
Uploading a board to claude.ai is the owner's choice. A resolved `auto` means not answered yet: when the Artifact tool
exists in this session, ask once at G0, or before the first upload of a project that never answered (in the
AskUserQuestion call, or in the plain-text message without the tool): "Show boards as a private Artifact page on claude.ai (uploaded), or as a local file on this
machine?", with local marked (Recommended). Record the answer with `state --set review_surface=artifact` or
`review_surface=local`, and never ask again. Until it is answered, and whenever the tool is missing, use the local file,
opened with `open` / `xdg-open` / `start` (print the absolute path if that fails). The plugin setting `artifact` is the
owner's yes already; `local` means never upload. If Artifact is asked for but the tool is missing, say so before
falling back to the local file. Each round regenerates one stable page, `review/index.html`, published to the same Artifact
URL, recorded as `review_url`. Round 0's page is a copy of the style board. Round folders stay as frozen copies.

---

## Round mechanics

Every board round, in this order (the `/brand-creator:round` skill wraps it). Round 0 is the style board
(`templates/style-board.html`, P1s) and round 1 does not start until G1s is recorded (a pick, "skipped by owner" or "n/a");
after a full rejection the next pick board also waits for a new style board and a new pick (G2b-a):

1. New folder `rounds/r<N>/`; from round 2 copy the previous round first (`cp -R rounds/r<N-1> rounds/r<N>`).
   Earlier rounds are never edited; the hook blocks it. Marks that need drawing are drawn first, on the session's drawing
   engine, and come in as SVG masters with a `SOURCE.md` ([drawing-engines.md](references/drawing-engines.md)).
2. Build the round page at `rounds/r<N>/board.html` from `${CLAUDE_PLUGIN_ROOT}/templates/round-page.html`
   (per-direction deep boards from `templates/board.html` go in `rounds/r<N>/<direction>/board.html`). Fill every
   `[[fill: ...]]`; the lint fails on any left. Follow [board-contract.md](references/board-contract.md).
3. `... board-lint rounds/r<N>/board.html --project <dir>` until exit 0.
4. `... shot rounds/r<N>/board.html --project <dir>`; Read every slice listed in `assets/_checks/shot.json`
   (1440 and 390, light and dark) and fix what you see. Iterate at least twice before showing. `shot` exits 3 (no
   Chromium yet): go on with steps 5 to 7, and the reply says the shots are not verified and names the fix.
5. Regenerate `review/index.html` from `${CLAUDE_PLUGIN_ROOT}/templates/review/index.html`, lint it the same way, and
   publish it to the review surface (same Artifact URL every round). Round 0 has no review template: copy the style
   board (`cp rounds/r0/board.html review/index.html`) and lint it with `board-lint review/index.html --round 0`.
6. Update BRAND-STATE.md: phase, Directions table (rejected / liked / DECIDED), `canonical_direction`, Still open.
7. Reply with the response template and stop at the gate.

## Single-thread path (default)

All phases run in this thread: research with WebSearch/WebFetch, one designer pass per direction in sequence, your
own comparative read as the judge. Subagents and workflows are optional speed-ups for Standard and Full projects,
only after the fleet gate. When `disableWorkflows` is set, nothing changes except speed.

## Fleets and workflows (opt-in, after the fleet gate)

Single-thread stays the default. When a fleet would help (Standard or Full; a round of 3 or 4 directions, a lens panel,
a naming fan-out, an adoption across repositories), propose it and wait:

1. Fill the workflow's arguments (`directions` takes the G1s record as `g1s` and refuses to start without it) and run
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" fleet-plan <workflow> --args @<file> --session-model <your model>`
   (nothing is launched; exit 1 = refused or above your model).
2. State the agent count, the models that will actually run (your session model is the ceiling; `args.ceiling` caps
   every agent to it; `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` overrides the agent files), the size guideline and a rough
   cost (about one single-thread pass per agent), and that you will do it here if they prefer.
3. Only after an explicit yes, run the workflow `/brand-creator:<workflow>` with those arguments as its `args` and
   `approved_agents` set to the approved number. Read the result, then carry on at the gate the workflow stops before.

| Workflow | When | Default agents |
|---|---|---|
| `directions` | round 1 or a reset round (`inventory: true` adds the P1c survey) | 3 designers + judge = 4 |
| `review-panel` | `/brand-creator:review panel` | 3 lenses + judge = 4 |
| `naming` | P2 with an open name | 2 hunters + screener + judge = 4 |
| `adopt` | P11 after G6 | implementer + reviewer per repository |

Refinement is a main-thread loop with at most one `brand-creator:brand-reviewer` call per round. Agents, models,
arguments, resume and the refine loop: [fleet.md](references/fleet.md).

## Recording state

- `... state --project <dir>`: summary. `--json`: everything. `--get tier`.
- `... state --set phase=P5 --set canonical_direction=Compass`.
- `... state --record G2 "picked Compass with Lantern's dot"` and `--require G3`.
- `... state --bump fixes_per_area.lockup`: count incremental fixes (G-sys).
- Decisions with reasons go to `decisions/` or the Notes block; liked/rejected lines are paraphrased owner signals.

## Project layout

```
<project>/
  BRAND-STATE.md  FACTS.md  brief/BRIEF.md  brief/canvas-round-<N>.md (drawing briefs)  INVENTORY.md (Full, product-in-family)
  research/ (research.md, cliches.md, positioning-map.md, dated notes, names/)
  rounds/r0/board.html (style board)  rounds/r1/board.html  rounds/r1/<direction>/ (<item>.svg, -16/-32/-128.png, SOURCE.md)
  .design/<slug>/ (the use-llm design canvas, when one is used)
  review/index.html                        tokens/*.tokens.json
  assets/logo/ assets/tokens/ assets/web/ assets/social/ assets/manifest.json assets/_checks/
  history/<date>-<name>/  history/MANIFEST.sha256   decisions/
```

Full file contract: `${CLAUDE_PLUGIN_ROOT}/scripts/CONTRACT.md`. Templates: `${CLAUDE_PLUGIN_ROOT}/templates/`.

## Commands by phase

| Need | Command (after the entry point and `--data`) |
|---|---|
| tools present for the tier | `prereq --for quick` (or standard, full, apple, print) |
| design tokens from `tokens/*.tokens.json` | `tokens --project <dir>` (`--fix-hex` computes hex fallbacks) |
| contrast report | `contrast --project <dir>` |
| real-size logo sheet | `logo-sheet --project <dir>`, then Read `assets/_checks/logo-sheet.png` |
| mark geometry, fonts, small sizes | `outline-glyphs`, `logo-sheet --guides`, `fontcheck --lang <code>`, `downscale --source <master.png>`, `states-check`, `family-check`, `contrast --cvd` (details: `scripts/CONTRACT.md`, "QA gates and mark tooling") |
| motion proof and its stills, byte identity, stale packs | `shot --motion <proof.json>`, `frames <proof.json>`; `snapshot take|diff`, `verify-idempotent --cmd "<chain>"`, `staleness`, `specs-due` |
| web and social files | `emit web --project <dir>`; `emit social --project <dir> --tagline "<FACTS line>"` |
| platform packs (Full tier, from INVENTORY.md) | `emit apple` (macOS with Xcode only), `emit windows`, `emit linux --app-id <id>`, `emit tray` (needs `tray/tray.json`), `emit tauri`, `emit wallet`, `emit developer`; sizes come from [platform-specs](references/platform-specs.md); the chain is `templates/finish.sh.tpl`; method: [the brand-assets skill](../brand-assets/SKILL.md) |
| Android, Chrome extension and MSIX packs (Full tier; Tier B) | `emit android` (adaptive icon with monochrome layer, Play icon, feature graphic; the mark must fit the 66 dp safe zone), `emit chrome-ext`, `emit msix` (app-list sizes with unplated and lightunplated files); files built from a status U spec row carry the label "UNVERIFIED, recheck" (see [brand-assets](../brand-assets/SKILL.md)) |
| watchOS and tvOS icons, profile images (Tier B) | `emit apple --target watchOS=10.0 --target tvOS=17.0` (or the lines in INVENTORY.md; macOS with Xcode; the mark must fit the watch circle and the tvOS margin); `emit profiles` (every tier; Quick writes the circle-safe avatar 400 and 800 only, Standard and Full add LinkedIn, X, YouTube, Facebook, Instagram feed and story images inside their safe areas, plus `_proof/` images that draw the safe areas). Every size is unverified and the files carry "UNVERIFIED, recheck" (see [brand-assets](../brand-assets/SKILL.md)) |
| print stationery, press kit, social posts (Standard and Full tier; print is opt-in with the owner) | `emit print --region EU|US|JP [--bleed MM] [--icc <the printer's CMYK profile>]`, then `print-check`; `emit presskit` (needs `book-pdf` first, or `--no-book`); `emit social --posts --post-fact "<FACTS label>" ...`. Without `--icc` a print PDF is an "RGB proof, not print-ready"; with it only a "PDF/X-4 candidate (preflight with your printer)". Never call a print file print-ready or conforming: preflight and the printer's proof are the owner's step ([print](references/print.md)) |
| brand book (P10; method in [10-book](references/phases/10-book.md)) | generated: `book --init`, `book`, `book-lint --self-consistency`, `book-pdf` (RGB proof); authored-vector: `patch book.html --old .. --new .. --count N`, then `book-lint`; after a decision: `collapse --group <g> --keep <name>` (plan first, then `--apply`) |
| adoption survey of product repositories (P11, Full tier; read only; method in [11-adoption](references/phases/11-adoption.md)) | `adoption survey --repo <dir>=<label> --old-name "<Old>" --old-colour "#rrggbb"`, `adoption add --repo <label> --file <path> --find "<text>" --change "<sentence>"`, `adoption status [--set 1-5=doing]` (doing and done need G6), `adoption verify` |
| rule change: find the old value everywhere | `check --cascade "<old value or phrase>"` (repeatable; `--also <path>` for a parent brand's document; see [cascade](references/cascade.md)) |
| BRAND.md, DESIGN.md and a per-brand skill (opt-in at G5) | `adapters --brand-md --design-md [--primary <role>]`; `applied-skill --yes` (without `--yes` it only prints the plan); both need G5 and are generated files ([10-book](references/phases/10-book.md)) |
| launch checklist for the owner (P13; method in [13-launch](references/phases/13-launch.md)) | `launch-todo [--name <candidate>]` writes LAUNCH.md from local files; nothing outward is ever executed |
| every gate that applies | `check --project <dir>` |
| name screening (P2, after the owner's privacy OK) | `names <name>... --project <dir> --profile <p> --region <CC> --plan`, then `--yes` |
| freeze an approved round | `freeze r<N> --name approved-board --project <dir>` |

## References (load when the phase needs them)

- [references/_index.md](references/_index.md): every reference file in one table, with what to use it for.
- Phases: [00-intake](references/phases/00-intake.md), [01-research](references/phases/01-research.md),
  [01s-style-research](references/phases/01s-style-research.md), [02-naming](references/phases/02-naming.md), [03-strategy-directions](references/phases/03-strategy-directions.md),
  [04-selection](references/phases/04-selection.md), [05-refinement](references/phases/05-refinement.md),
  [06-mark](references/phases/06-mark.md), [07-tokens](references/phases/07-tokens.md),
  [08-assets](references/phases/08-assets.md), [09-qa](references/phases/09-qa.md),
  [10-book](references/phases/10-book.md), [11-adoption](references/phases/11-adoption.md),
  [12-history](references/phases/12-history.md), [13-launch](references/phases/13-launch.md).
- [board-contract.md](references/board-contract.md): required board sections (pick, refine and style boards), territory card, rubric, generation prompts.
- [drawing-engines.md](references/drawing-engines.md): where marks are drawn (the use-llm design canvas, Claude Code's /design, or Claude-drawn SVG on the owner's yes), the drawing brief, what lands in the round, the canvas's known quirks.
- [The brand-naming skill](../brand-naming/SKILL.md): P2 naming, prior art, screening and the verdict memo.
- [The brand-book skill](../brand-book/SKILL.md): P10 book, self-review checklist, collapse, G5 opt-ins, the RGB proof PDF.
- User-invoked: [brand-adopt](../brand-adopt/SKILL.md) (P11 apply), [check](../check/SKILL.md) (gates and cascade),
  [review](../review/SKILL.md) (self-review, optional lens panel), [launch](../launch/SKILL.md) (P13 hand-off).
- [CONNECTORS.md](../../CONNECTORS.md): optional design-tool connectors (never required, never the source of truth).
- [The brand-assets skill](../brand-assets/SKILL.md): P8 asset packs from INVENTORY.md slots, size bands, downscale proof; also runs
  standalone on a mark file.
- [print.md](references/print.md): stationery, press kit and social posts: the commands, what a print file is and is not, the owner's hand-off.
- [strategy-core.md](references/strategy-core.md): the 7-field strategy core drafted by you, shown on the round 1 board, with the
  Guardrails block.
- [working-style.md](references/working-style.md): collaboration defaults and the per-project Collaboration block.
- [anti-patterns.md](references/anti-patterns.md): case cards of costly mistakes and the check that catches each.
- [architecture.md](references/architecture.md): standalone, family-member, product-in-family; layers; never-borrow.
- [cascade.md](references/cascade.md): what to update when a rule, token or lockup changes.
- [regulated-industries.md](references/regulated-industries.md): professions with promotion or naming rules.
- [prompt-fragments.md](references/prompt-fragments.md): the prompt skeleton for designer, judge and reviewer passes.
- [fleet.md](references/fleet.md): the opt-in workflows and agents, the fleet gate in full, model ceiling, the refine loop, resume.
- [ai-defaults.json](references/ai-defaults.json): the reflex list every direction is tested against.
- [platform-specs.md](references/platform-specs.md): every platform size the emitters use, with source, date and status V, R or U (generated from `scripts/emitters/platform-specs.json`; never edited by hand).
- [examples/acme/README.md](references/examples/acme/README.md): a synthetic worked brand (state, decisions, round 1 page, map).
