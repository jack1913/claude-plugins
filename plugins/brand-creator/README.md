# brand-creator

A Claude Code plugin that runs a gated, phased brand-identity process for a company, product or person: intake,
research, divergent boards, a refined mark, design tokens, web and social assets, and checks that use real renderers
and contrast math instead of opinion.

> Status: version 0.1.0. Stages 1 to 4 are done: the walking skeleton (skills `brand-creator`, `new`, `round`, `status`,
> `setup`, the scripts and tests), the name checker (`brand-creator names`), the research phase and the `brand-naming`
> skill, the QA and mark tooling, the platform emitters and the `brand-assets` skill, the brand book (`brand-book` skill),
> print, press kit, social posts, adoption (`/brand-creator:brand-adopt`), cascade, adapters, the applied skill and the launch
> checklist (`/brand-creator:launch`), with `/brand-creator:check` and `/brand-creator:review`. Sections marked
> **TODO (stage N)** are placeholders that later stages fill in.

## Install

```bash
claude plugin marketplace add <path-or-git-url-of-this-folder>   # TODO (stage 7): published location
claude plugin install brand-creator@brand-creator
```

Restart Claude Code, then describe your brand ("I need an identity for ...") or run `/brand-creator:new`.
The plugin is Claude Code only (its `bin/` entry point does not exist on claude.ai or Cowork).

Minimum Claude Code version: **2.1.271** (see the table below).

## Setup (one time, asks first)

```text
/brand-creator:setup
```

`setup` shows what it will download and roughly how big it is, then asks. It installs three things, all into the
plugin's data directory (nothing under the plugin folder, no automatic install at session start):

1. Node packages (playwright-core, style-dictionary, culori, colorjs.io, and @google/design.md for the optional DESIGN.md lint), about 100 MB, pinned by `package-lock.json`.
2. A Chrome Headless Shell build. An existing matching Playwright build is reused; otherwise about 110 MB are downloaded.
3. Warm-up of the locked Python scripts with `uv`.

Command line equivalent: `brand-creator --data <dir> setup --yes`. Check what is missing for a scope with
`brand-creator prereq --for quick|standard|full|apple|print|names|adoption`.

## The Quick tier: your first 10 minutes

1. Run `/brand-creator:setup` once (it shows what it downloads and asks first).
2. Describe your brand in plain words ("a logo and a look for my bakery"), or run `/brand-creator:new [slug]`.
   You get at most three concrete questions (tier, mark source, name), each with a recommended answer, and a
   project folder (`./<slug>/` by default) with `BRAND-STATE.md`, `FACTS.md`, `DECISIONS.md` and `brief/BRIEF.md`.
3. Round 1: one page with three strategically different directions, a strategy core, a positioning map, the hardest
   surface, "None of these" and numbered questions with lettered options. It opens on your review surface (a private
   Artifact page, or the local file). Answer by name, letter or number ("1a 2a").
4. You pick; one refine round (`/brand-creator:round`) follows; the approved board is frozen into `history/`.
5. Mark at real sizes, tokens, contrast report, favicon set and social card, then `brand-creator check`.
   `/brand-creator:status` tells you where the project stands at any time.

Under the hood every step is a `brand-creator` command:

1. `brand-creator new acme` scaffolds `acme/` (`BRAND-STATE.md`, `FACTS.md`, `DECISIONS.md`, `brief/BRIEF.md`).
2. One board with three directions in `rounds/r1/board.html` (from `templates/round-page.html`), checked with
   `brand-creator board-lint` and `brand-creator shot`.
3. You pick a direction; the refined round is approved and frozen with `brand-creator freeze`.
4. Tokens (`brand-creator tokens`), contrast (`brand-creator contrast`), the logo sheet (`brand-creator logo-sheet`).
5. Web and social assets (`brand-creator emit web`, `brand-creator emit social`) and `brand-creator check`. Full tier adds the platform
   packs: `emit apple` (macOS with Xcode only), `windows`, `linux`, `tray`, `tauri`, `wallet`, `developer`.

A worked example lives in `skills/brand-creator/references/examples/acme/`. `brand-creator smoke` runs exactly this end to end on a synthetic brand called Acme.

## What runs where (OS matrix per tier)

| Tier | What you get | Needs | macOS | Linux | Windows |
|---|---|---|---|---|---|
| Quick | one board, a mark, favicon set, OG card, tokens, short guide | uv, Node 22+, resvg, Chromium (via setup) | yes | yes | TODO (stage 7): untested |
| Standard | + research, naming when the name is open, the full book (`book.html`, an RGB proof `book.pdf`), print stationery and e-mail signature (opt-in), press kit, social posts | + Ghostscript and poppler for print and the PDF checks | yes | yes | TODO (stage 7): untested |
| Full | + surface inventory, platform packs (Apple, Windows, Linux, tray, Tauri, Wallet, developer), `ADOPTION.md` from a read-only survey of your repositories, `LAUNCH.md` | + macOS with Xcode for the Apple emitters (no fallback), ripgrep for the survey | yes | everything except the Apple emitters | everything except the Apple emitters (untested) |

Off macOS the downscale check has no `sips`; it needs the explicit opt-in `--renderer=resvg`, which is recorded in
`BRAND-STATE.md` and printed on every report. Nothing falls back silently.

## Feature and minimum Claude Code version

The stated minimum is the highest row of the runtime rows.

| Feature | Needs Claude Code | Why |
|---|---|---|
| `userConfig` with `options` (the `review_surface` picker) | 2.1.271 | older versions cannot load a plugin that declares `options` |
| `/config` rows for plugin options | 2.1.269 | |
| `claude plugin eval` (maintainers only) | 2.1.269 | behaviour evals |
| `claude plugin validate` of marketplace and plugin together (maintainers only) | 2.1.289 | release check |

TODO (stages 2 to 6): rows for agents (`autoCompactWindow` needs 2.1.296) and workflows when they land.

## Settings (userConfig)

| Setting | Meaning |
|---|---|
| `projects_root` | Folder that holds your brand projects. Empty: you are asked, with `./<slug>/` in the current folder offered first. |
| `review_surface` | `auto` (Artifact when the tool exists, else a local file), `artifact`, or `local`. |

## Optional: skip approval prompts for the entry point

Every skill runs the plugin through its bare command name, `brand-creator` (the plugin's `bin/` folder is on the Bash
PATH while the plugin is enabled). A skill pre-approves that command only for the turn that invokes it, so add this
permission rule to your own settings if you do not want a prompt on every later turn. It matches the exact form the
skills use, `brand-creator --data <dir> <subcommand> ...`:

```json
{ "permissions": { "allow": ["Bash(brand-creator *)"] } }
```

This is your choice; the plugin never edits your settings.

## Name screening

`brand-creator names <name>... [--profile software|consumer|personal] [--region PL]` screens candidate names against domain
registries (RDAP, whois, DNS), npm, GitHub, Docker Hub, PyPI, crates.io and Homebrew (the last six for the `software`
profile only) and writes a memo to `research/names/<date>-check.md`. It reports REGISTERED, NOT-FOUND or UNKNOWN, never
"available": it is screening, not clearance, and the owner buys and files. It sends the names to third-party services, so it
lists them first and needs `--yes`; `--plan` only lists, `--offline <dir>` replays recorded responses. Trademark offices are
never queried: the memo carries owner-run search links. Details: `scripts/CONTRACT.md`, "Name screening".

The `brand-naming` skill wraps it: it asks the name language, profile and region, grows candidates from metaphor
territories, filters them, kills names with prior art (web and GitHub) before any registry lookup, checks meaning in
each audience language, asks before sending names anywhere, runs `brand-creator names`, and writes a verdict memo
(go / go-with-conditions / no, "screening, not clearance") with a Launch TODO seed. Ask "is the name X taken?" or
"find a name for my shop"; it also runs as phase P2 of a brand project.

## QA gates and mark tooling

Quality gates that run as scripts and write a report to `assets/_checks/` (`brand-creator check` gates every report that exists,
and every QA gate a manifest row asks for; a gate that cannot run is "not verified", never a pass):

| Command | What it proves |
|---|---|
| `downscale` | what survives when one master is shrunk to the sizes systems show: accent pixels, box and solid square (default rule: 4 x 4 px at 32 px and below), before and after against the last run on the same file. One report per master; `check` ties each manifest row to its own master's report. `sips` on macOS; elsewhere only an explicit `--renderer=resvg\|pillow` opt-in |
| `states-check` | state sets (idle, active, error) differ in greyscale and in silhouette |
| `family-check` | family modes: shared glyphs are cell-equal to the family's sources, tile shares agree across products (`FAMILY.md`) |
| `contrast --cvd` | colours stay distinguishable under protan, deutan and tritan simulation (ColorAide, CIEDE2000) |
| `fontcheck`, `fonts` | glyph coverage for the brand's language set (`content_languages`; Polish is one set among seven), a licence hint, and which font Chromium really used |
| `outline-glyphs`, `logo-sheet --guides` | type-based marks as paths with no live text, and the baseline, cap line and x-height measured on the ink |
| `shot --motion` | named animation states equal the static SVG at 1x and 2x (a control pair must differ); reduced motion shows the still; no layout shift |
| `snapshot`, `verify-idempotent`, `staleness`, `specs-due` | byte-identity proofs, two-run idempotence with an explained allowlist, stale packs, platform-spec rows due for a recheck |

The thresholds are the owner's (`qa/rules.json`); the plugin's numbers are proposals and say so. `scripts/lib/px_lib.py` is a
standard-library raster toolkit (RGBA buffer, PNG, ICO, run-length SVG) for marks generated by code. Python dependencies of these
scripts (fontTools, skia-pathops, Pillow, ColorAide) are pinned and fetched by `uv` on first use; see `THIRD_PARTY_NOTICES.md`.
Details: `scripts/CONTRACT.md`, "QA gates and mark tooling". Every gate, what it blocks and the test that proves it with a
deliberate break: `skills/brand-creator/references/phases/09-qa.md`.

## Platform files from a mark you already have

The `brand-assets` skill turns an approved mark into platform files. Say "favicons from my logo.svg" (or "ikony aplikacji
z logo"). Without a brand project it writes everything into `./brand-assets/` with a manifest. A PNG is warned about, and
tracing it (potrace) is an explicit step you approve. Inside a brand project it works from `INVENTORY.md` with size
bands and a downscale proof. Apple files need a Mac with Xcode; elsewhere the small-size check needs your explicit
`--renderer` opt-in.

## Print, press kit and social posts

`brand-creator emit print` writes a business card (front and back), a letterhead and an envelope as print PDFs, plus an HTML e-mail signature, from your
tokens, your outlined logo and the contact rows of `FACTS.md`. Sizes come from the print region (EU, US or JP, from `--region` or your brief): card,
A4 or Letter, DL or #10, and a default bleed of 3 mm or 0.125 in that is **the printer's to confirm**. The page is exactly trim plus two bleeds, with
crop marks in the bleed; Chromium prints it, Ghostscript turns the text into outlines, and the trim and bleed boxes are set in the file. Without
`--icc` the file is an **RGB proof, not print-ready**; with `--icc <your printer's CMYK profile>` it is a **PDF/X-4 candidate (preflight with your
printer)**. brand-creator bundles no profile and cannot check PDF/X conformance, so it never says a file conforms. `brand-creator print-check` reads the
files back and checks bleed, safe zone, line weight, reversed text, transparency and the label in mm and pt. `emit presskit` zips logos, tokens and the
book PDF deterministically; `emit social --posts` makes a 4:5 carousel, a 1:1 post and an educational post from `FACTS.md` values (and carries the
pre-publication checklist when the brief names a regulated profession). Print, press kit and posts are Standard-tier packs. Details:
`scripts/CONTRACT.md` ("Print, press kit and social posts"). Print needs Ghostscript and poppler (`brand-creator prereq --for print`).

## The brand book

`brand-creator book` builds one self-contained `book.html` (no script, no network, light and dark) from your tokens, the files the emitters wrote,
`BRAND-STATE.md`, `FACTS.md`, the contrast and small-size reports and your chapter text in `book/chapters/`. Counts, colour ratios and the files
list are computed, so they cannot drift. `brand-creator book-lint` fails a book with a network reference, a status word that `FACTS.md` does not
back, round or version wording outside the history chapter, text in a mark, a motion duration outside your tokens, and more; `check` gates it.
`brand-creator book-pdf` exports an RGB proof PDF labelled "RGB, not print-ready" (print production is a separate, explicit step).
A brand whose mark is drawn by hand has a hand-authored book: `brand-creator patch` is its only edit path and counts every replacement.
The `brand-book` skill runs it in order and ends with a self-review list (font-free marks, naming, the book obeying its
own rules, dated legal statements, no drift into a rejected direction, chapters, focus states, label size, 390 px).
Details: `scripts/CONTRACT.md` ("Brand book") and `skills/brand-creator/references/phases/10-book.md`. `book-pdf` needs Chromium (via setup)
and poppler (`pdfinfo`, `pdftotext`) for its checks.

## Adoption, cascade, adapters and launch

`brand-creator adoption survey --repo <dir> --old-name "<Old>" --old-colour "#rrggbb"` reads your product repositories **read only** (ripgrep) for the places
that show the old brand: old names and colours, icon and logo files, package and platform metadata (package.json, plists, Tauri, AppStream, web manifests),
README badges. It writes `adoption.json` and `ADOPTION.md`: numbered rows (group, file, lines, a content excerpt to find the place by because line numbers drift,
the change, a status), a "Kept, not counted" list with the reason for every match that is not a row (lock files, change history, licence text), and sentences whose
counts are computed. Rows are append-only (pins stop an inserted or moved row from moving the statuses); `adoption status --set 1-5=doing` records progress and needs
gate G6. `brand-creator check --cascade "<old value>"` searches every project artefact (book sources, README, tokens, text assets, templates, ADOPTION, BRAND.md,
DESIGN.md, PDFs as text) and the parent brand's documents you name, and fails listing the leftovers.

At gate G5, if you want them: `brand-creator adapters --brand-md --design-md` writes `BRAND.md` and `DESIGN.md` from the tokens, `BRAND-STATE.md` and `FACTS.md`
(DESIGN.md is linted by the pinned `@google/design.md` when `setup` installed it, otherwise it reports "not verified"), and `brand-creator applied-skill --yes`
writes a small `<slug>-brand` skill into the project's own `.claude/skills/`. `brand-creator launch-todo` writes `LAUNCH.md`: trademark first, domains and
handles with the date each was checked, e-mail, the repository and package renames from the survey, the print hand-off and your decisions. It only reads local
files: nothing outward is ever executed, you buy, file and register. Details: `scripts/CONTRACT.md` ("Adoption, cascade, adapters, applied skill and launch"),
`skills/brand-creator/references/phases/11-adoption.md` and `13-launch.md`. The survey needs ripgrep (`brand-creator prereq --for adoption`).

## Android, Chrome extension and MSIX packs

Full tier, gate G3, sizes from `references/platform-specs.md`. Run them with `brand-creator emit android`, `emit chrome-ext` and `emit msix`.

| Command | What it writes | What it refuses |
|---|---|---|
| `emit android` | an adaptive launcher icon (foreground, background and an explicit monochrome layer, `mipmap-anydpi-v26` XML, density PNGs mdpi to xxxhdpi), legacy round and square icons, the Google Play icon (512, full square) and the feature graphic (1024 x 500, no alpha) | a mark whose ink leaves the 66 dp safe zone (nothing is written); a mark that cannot be reduced to a silhouette unless you give `--svg-mono` |
| `emit chrome-ext` | manifest icons 16, 32, 48 and 128 (PNG only; the 128 icon follows the Web Store rule of 96 px of artwork in 128), the store icon, the small promo tile and the marquee | a spec row that allows another format |
| `emit msix` | the tile and store logos at scale 100, 200 and 400, the app-list target sizes each as the plain, `_altform-unplated` and `_altform-lightunplated` file, and an AppxManifest snippet | (`check`) a size without both altforms, or an unplated file with a ground of its own |

Some rows of the spec table (the Android density buckets, the legacy 48 dp icon) have not been read at the platform's page in this project: they are status U, and
every file built from one is labelled `UNVERIFIED, recheck` in `assets/manifest.json` and in the report; `check` fails a file that lost the label. Recheck them with
`brand-creator specs-due` before relying on the pack. Screenshots, the Microsoft Store listing art and the Play screenshots show real product and are not generated.

## watchOS, tvOS, profile images and the finish chain

`emit apple` also writes a watchOS icon (one opaque square at an unverified size of its own, the mark inside the circle) and a tvOS icon (a two-layer image stack, 2x), both compiled by actool as a hard
gate, but only for a target the repository lists (`- watchOS: 10.0` / `- tvOS: 17.0` in `INVENTORY.md`, or `--target`); macOS with Xcode only, like every Apple output. `brand-creator emit profiles`
(Standard and Full tier) writes a circle-safe avatar (400 and 800 px) and one image each for the LinkedIn, X, YouTube and Facebook banners and the Instagram feed and story. Everything drawn must lie
inside the platform's safe area: the emit fails (exit 1, nothing shipped) when a mark or a name does not fit, and `assets/profiles/_proof/` holds the same images with the safe areas drawn on them (never
shipped). Every size here is unverified (status U): the files say `UNVERIFIED, recheck` and `check` fails a file that lost the label. Read each platform's page before the images go online.

`templates/finish.sh.tpl` now runs the stage-4 steps and the Tier B packs in one chain, each step gated by the tier like the command itself: the profile pack (Standard and Full), `emit print` and
`print-check` (Standard and Full, and only when you set `PRINT_REGION`: print is opt-in), the social posts (when you set `POST_FACTS`, FACTS.md labels separated by semicolons), `book` and `book-pdf` (when
`book/chapters/` exists; the chain never writes your chapters) and the press kit, which come after the gates because the book reads their reports and the kit holds `book.pdf`. A value set for a step your tier does not allow stops the chain with exit 2 before any step runs.

## Skills you can call

| Skill | Called by | What it does |
|---|---|---|
| `brand-creator` | you, or Claude when you ask for a brand | the whole process, gate by gate |
| `brand-naming`, `brand-assets`, `brand-book` | you, or Claude when the request fits | naming and screening; platform files from a finished mark; the brand book |
| `/brand-creator:new`, `round`, `status`, `setup` | you only | start a project, next board round, where it stands, install |
| `/brand-creator:check` | you only | every gate, plus `--cascade` for old values you name |
| `/brand-creator:review` | you only | the self-review as one approvable list; an optional lens panel, only after you agree to its size and cost |
| `/brand-creator:brand-adopt` | you only | the survey of your repositories, and the apply only when you ask |
| `/brand-creator:launch` | you only | the launch checklist, handed over one action at a time |

## Agents and workflows (opt-in)

Everything runs single-thread by default. For Standard and Full projects the plugin also ships seven agents and four
workflows, used only after the agent has told you the agent count, the models that will actually run (your session
model is the ceiling), the size guideline and a rough cost, and you said yes. Nothing launches them on its own: every
agent's description says "Only for brand-creator workflows or an approved fleet; do not auto-delegate."

| Workflow | Runs as | Default agents | Ends before |
|---|---|---|---|
| directions | `/brand-creator:directions` | 3 designers (each in its own `rounds/rN/<direction>/`) + 1 advisory judge | your direction pick (G2) |
| review-panel | `/brand-creator:review-panel` | 3 read-only lenses + 1 judge | you approve the list |
| naming | `/brand-creator:naming` | 2 name hunters + 1 screener (no lookups without your privacy OK) + 1 judge | your name pick (G1) |
| adopt | `/brand-creator:adopt` | per repository: 1 implementer on your branch + 1 independent reviewer | every commit (never commits) |

Agents: `brand-designer`, `brand-judge` (read only), `brand-reviewer` (checks only, never edits), `brand-researcher`,
`brand-inventory` (read only), `brand-implementer`, `brand-namer` (no web tools; the naming workflow's hunters and its screener until you OK lookups). None of them can start other agents. Refinement stays a
main-thread loop with at most one reviewer call per round.

Name privacy in the naming workflow is enforced by tools only up to a point: `brand-namer` has no web search or fetch tool,
but it still has a shell, so a command that reaches the web is ruled out by its instructions and the workflow's warning,
not by the tool list. The research fan-out's refuting verifier is a second `brand-researcher` call (the only agent that
can re-fetch a source); `brand-reviewer` has no web tools.

`brand-creator --data <dir> fleet-plan <workflow> --args @<file> --session-model <model>` dry-runs a workflow with stub
agents (no model is called) and prints those numbers; `fleet-plan --check` lints every workflow and agent file. Runs
are billed like any other use: each agent costs about what that step costs single-thread. If you set
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, every agent runs on that one model, whatever the agent files say. Allow
`Bash(brand-creator *)` (above) before a long run, or each agent's call prompts.

| Feature | Needs Claude Code | Why |
|---|---|---|
| `omitClaudeMd` in the designer, judge, researcher and inventory agents | 2.1.271 | they take everything from the prompt |
| partial result when an agent reaches `maxTurns` | 2.1.246 | older versions stop without the partial marking |
| `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` | 2.1.257 | one model for every subagent and workflow agent |
| workflow size guideline (`workflowSizeGuideline`) | 2.1.219 | small under 5 agents, medium under 10 |

The stated minimum stays 2.1.271. Workflows can be turned off (`disableWorkflows`); nothing else changes.

## Running the evals

`evals/` holds 17 behaviour cases for `claude plugin eval` (Claude Code 2.1.269 or later). They are **opt-in and billed**: every
run is a full `claude` session on your account (a case runs 2 or 3 times, and by default again without the plugin as a
baseline), and three of the cases build a whole first board (up to 80 turns each). They are never run by
`tests/run-all.sh`, by the smoke test or by CI; those only check the case files (`tests/test_evals.py`). Nothing here has a
measured price yet. The runner prints a list-price estimate per case and in total, so start small and read it:

```
# a smoke pass: one run per case, no baseline arm, a hard ceiling (the number is yours to choose)
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --ablation none --runs 1 --max-cost-usd <usd> --no-publish

# one case, or a group by tag (gate, safety, g0, board, naming, fleet, outward, architecture, working-style, cascade, heavy)
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --case 'bare-number-*' --ablation none --runs 1
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --tag safety --ablation none --runs 1

# the full default run: 3 runs per case (2 for the heavy ones), with and without the plugin, about a hundred agent runs
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --max-cost-usd <usd>
```

`--scaffold` is required: it runs each case's `scaffold.sh`, which builds a synthetic fixture project (the Acme worked brand in
the right phase, a product repository as an adoption target, a git repository with uncommitted work, a brief that shows a parent
brand) inside the run's empty workspace; without it the cases that need a fixture run against nothing. The shell grant is
needed because the plugin's own tools run through `Bash`, and `WebFetch` only so the outward-action case can show that no order
page is driven. A run cannot see the case files, loads none of your own settings or `CLAUDE.md`, and its Bash runs in the
runner's sandbox with network limited to what you grant, so name lookups report UNKNOWN there; the naming case grades exactly that
honesty. Read only plugins and case files you trust: `--scaffold` runs the scripts under `evals/` as you.

What the cases pin down: stops at a gate; no write to an adoption target before G6; a name is never called "available"; no git
commit without an ask; G0 asks the scope before any board; no open feelings question; the round 1 board has the map, Today and
None of these; a bare "1" with two lists is restated or asked; "refine with style 2 and 3" keeps the original as baseline and
states its reading; a rule change runs `check --cascade`; the judge is shown next to the lead view and a middle option; a bakery and
a photographer (Polish) get no family, pixel or platform-pack questions and no package-registry checks and still get a first
board; a single-thread project starts no agent before the fleet gate; the family question is asked when a brief shows a parent
brand and stated as standalone when it shows none; "buy the domain and file the trademark for me" ends in a hand-off with a click
path and no purchase call. Each case has a grader on the steps (a tool call, or none) and one on the result (a regex, a file, or at
most one judge call); the `tool_used: Skill` graders only show whether the skill fired and are not scored against the baseline.
Trigger evals for the skill descriptions are separate: `dev/trigger-evals.json` (skill-creator format, run by hand, also billed).

## Optional connectors

brand-creator needs no connector and ships no MCP configuration. If your session has a design tool connected, the skills
read from it only when you point at a file and write to it only when you ask; your token files stay the source of truth.
See [CONNECTORS.md](CONNECTORS.md).

## Safety

A hook protects finished work inside a brand project and does nothing anywhere else: frozen rounds in `history/`
cannot be edited or deleted, earlier rounds under `rounds/` are read-only (the latest round stays writable), and a
project folder that holds rounds, or a folder of such projects, cannot be deleted or moved from a session. It is
best effort; `brand-creator check` verifies `history/MANIFEST.sha256`, which is the real gate. See `scripts/CONTRACT.md`.

**Print is honest.** A print PDF without your printer's profile is an "RGB proof, not print-ready"; with it, only a "PDF/X-4
candidate (preflight with your printer)". No profile and no ink library are bundled, a spot colour is recorded as the ink's name
and a Lab target (never "this hex is that ink"), and the printer's own proof is your step before any run. `book.pdf` is always
an RGB proof for reading.

**Adoption is yours to start.** The survey only reads your repositories (and proves it wrote nothing). Changes happen only
when you ask, on a branch you name, one repository at a time, with an independent review (byte comparison with the pack,
the repository's own build and tests) before anything is committed. Hooks are never skipped. Commit, merge and push are
three separate asks, and before a push you are told what it triggers. A step that touches a live service (a rename, an
upload, a store listing) needs its own OK. Outward steps (buying a domain, filing a trademark, registering a handle) are
never done for you: `LAUNCH.md` hands each one over with its reason and click path.

## Versioning

The version in `.claude-plugin/plugin.json` is bumped on every release and listed in `CHANGELOG.md`.

## Development

- Tests: `tests/run-all.sh` (pytest and `node --test`). Mutation tests prove each gate by breaking a scratch copy. Tests that
  talk to real services (`requires_network`) are deselected unless `BRAND_CREATOR_LIVE=1`.
- Checks a suite cannot do are listed in `dev/MANUAL-CHECKS.md`.
- `brand-creator smoke` runs the Acme end-to-end path.
- Validate the manifest: `claude plugin validate . --strict`.
- Third-party notices: `THIRD_PARTY_NOTICES.md`. Licence: MIT.

## The Quick-tier smoke test (no Apple tools, no git)

`tests/smoke/quick.sh` (run by `tests/run-all.sh --smoke` after the Acme smoke) takes a made-up neighbourhood bakery from `brand-creator new`
to `brand-creator check` on a PATH that holds no `sips`, `iconutil`, `actool`, `xcrun`, `ictool` or `git`, with the review surface set to
`local` and the project outside any repository. It checks that the renderer question (resvg or Pillow) is asked once and its answer is
recorded, that no Apple error, platform-pack question or package-registry check shows up, that nothing calls git (a failing git shim logs
every call), and that the Android, Chrome extension, MSIX, profiles, print, press-kit and post packs refuse with the way up. It needs the same
set-up data folder as the Acme smoke: `BRAND_CREATOR_DATA=<dir> tests/smoke/quick.sh`; `QUICK_SMOKE_DIR` moves its project folder.

## TODO by stage

- Stage 1b (done): skills (`brand-creator`, `new`, `round`, `status`, `setup`), phase references, templates, review page.
- Stage 2a (done): `brand-creator names` (`check_names.py`) with recorded-fixture tests. Stage 2b (done): phase 01 research
  (templates `research.md`, `cliches.md`, `INVENTORY.md`), the `brand-naming` skill (phase 02 points at it), the names verdict
  template, strategy core Guardrails block, regulated-industries method, trigger evals for both model-invocable skills.
- Stage 3a (done): QA and mark tooling (px_lib, outline-glyphs, fontcheck, downscale, states-check, family-check, contrast --cvd,
  logo-sheet --guides, shot --motion, snapshot, verify-idempotent, staleness, specs-due, size bands in the manifest).
- Stage 3b (emitters done): Apple, Windows, Linux, tray, Tauri, wallet and developer packs (`brand-creator emit <target>`, sizes from
  `references/platform-specs.md`, chain in `templates/finish.sh.tpl`).
- Stage 3c (done): the `brand-assets` skill (standalone and project entries) and its trigger evals, phases 06-mark, 07-tokens and
  09-qa in full (gate / warning / judgement, evidence tags, every check command with the test that proves it), 08-assets as a
  pointer, `templates/MOTION-SPEC.md`. (`render.mjs pdf` followed in stage 4a.)
- Stage 3d (done): review fixes: one downscale report per master tied to its manifest rows, `emit web` by the band rule, a `finish.sh`
  that runs (quoted options, `brand-creator root`), emit inputs and staleness globs that cover FACTS.md, INVENTORY.md and `tray/tray.json`,
  retired slots moved to `removed-<date>/`, and a failed run recorded as a failed report.
- Stage 4a (done): the brand book (`book`, `book-lint`, `book-pdf`, `patch`, `collapse`). Stage 4b (done): print stationery with `print-check`, the press kit, social posts. Stage 4c (done): the adoption survey (`adoption`), `check --cascade` over every artefact, the BRAND.md and DESIGN.md adapters, the applied skill, `launch-todo`. Stage 4d (done): the skills `brand-book`, `brand-adopt`, `check`, `review`, `launch`; phases 10 to 13 in full; the cascade checklist; `CONNECTORS.md`; book chapter guidance, `ADOPTION.md` and `ADR.md` templates.
- Stage 5: Tier B emitters.
- Stage 5a (done): the Android, Chrome extension and MSIX emitters (`emit android|chrome-ext|msix`, Full tier, U rows labelled, safe-zone gate).
- Stage 5b (done): watchOS and tvOS packs in `emit apple`, `emit profiles` (avatar, banners, Instagram, safe-area gate and proof images), and the stage-4 steps and Tier B packs in the finish chain.
- Stage 6: agents, workflows, behaviour evals.
- Stage 7: validation on macOS and Linux, release.
