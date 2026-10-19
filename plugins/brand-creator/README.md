# brand-creator

A Claude Code plugin that makes a brand identity with you: a logo or mark, colours, type, the files every surface needs
and a guide that says how to use them. It works for any kind of business or person, not only software: a bakery, a
photographer, a law practice, a podcast, a band, a shop, a nonprofit, or an app. Claude runs the work as short phases that
each end at a decision of yours. It reads what already exists, shows you three different directions on one page, builds
the one you pick, and checks the result with real renderers and contrast arithmetic, not with opinions. You decide on
taste. Claude researches, proposes a pick, builds, and tells you plainly what works and what does not.

Version 0.1.0. macOS is fully supported, Linux has been verified in a container, and Windows is untested (see
[Platform support](#platform-support)).

## Install

Inside Claude Code:

```text
/plugin marketplace add jack1913/claude-plugins
/plugin install brand-creator@jack1913
```

Or from a shell: `claude plugin marketplace add jack1913/claude-plugins`, then `claude plugin install brand-creator@jack1913`.
The plugin is listed in the [jack1913 marketplace](https://github.com/jack1913/claude-plugins); this repository holds the plugin only.
Restart Claude Code (or run `/reload-plugins`) afterwards.

To work on the plugin itself, load a local checkout for one session instead: `claude --plugin-dir /path/to/brand-creator`.

The plugin works in Claude Code only. Its `bin/` entry point and its hook do not exist on claude.ai or in Cowork.
Minimum Claude Code version: **2.1.271** (see [Claude Code versions](#claude-code-versions)).

## First run: your first 10 minutes

1. **Install the tools once:** `/brand-creator:setup`. It first shows what it will download, where from, roughly how big it
   is and where it goes, and it installs nothing until you say yes. It installs Node packages (about 90 MB, pinned by a lock
   file) and a Chrome Headless Shell build (about 110 MB to download; an existing matching Playwright build is reused) into
   the plugin's own data folder, and warms up the pinned Python scripts with `uv`. It writes nothing into the plugin folder
   and nothing runs automatically at session start.
2. **Start a brand:** say what you need in plain words ("a logo and a look for my bakery") or run `/brand-creator:new [slug]`.
   You get at most three short questions, each with a recommended answer: the tier, how this brand relates to others you
   run (only when your brief shows a parent brand or siblings), and the name (only when it is still open). Claude decides
   how the mark is made (drawn by code, drawn as vector, or your existing mark) and tells you, so you can say otherwise. If
   boards could be shown as a private page on claude.ai, it also asks once whether you want that or a local file; until you
   answer, boards stay local. The project folder is `./<slug>/` unless you name another place.
3. **Round 1:** one page with three clearly different directions, a strategy core, a positioning map, the hardest surface
   (for example the 16 px browser tab), "None of these", and numbered questions with lettered options. Reply by direction
   name, or by question and option ("1a 2b"); "ok" accepts every recommendation.
4. **Pick and refine:** one refine round (`/brand-creator:round`), then the approved board is frozen into `history/`.
5. **Build and check:** the mark at real sizes, design tokens, a contrast report, the favicon set and social card, a short
   guide, then `/brand-creator:check`. `/brand-creator:status` tells you where the project stands at any time.

## Tiers

You choose the tier at the start. Moving up later is one question.

| Tier | What you get | Extra tools needed |
|---|---|---|
| Quick | one board of 3 directions, one refine round, the mark and lockup (SVG and PNG), favicon set, social card, design tokens, a short guide | uv, Node 22+, Python 3.10+, resvg, Chromium (installed by setup) |
| Standard | + research, naming when the name is open, the full brand book (`book.html` and an RGB proof PDF), profile images, print stationery and an e-mail signature (opt-in), a press kit, social posts | + Ghostscript and poppler for print and the PDF checks |
| Full | + an inventory of your product's icon slots, platform packs (Apple, Windows, Linux, Android, Chrome extension, MSIX, tray, Tauri, Wallet, developer), a read-only survey of your repositories (`ADOPTION.md`), a launch checklist (`LAUNCH.md`) | + macOS with Xcode for the Apple packs (no fallback), ripgrep for the survey |

Rough length: Quick is 2 to 3 board rounds in one sitting, Standard 4 to 6 rounds over a day or two, Full several sessions.

## What it never does

- **No outward actions.** It never buys a domain, files a trademark, registers a handle, uploads to a store or contacts
  anyone. `/brand-creator:launch` hands each of those steps to you, one at a time, with the reason and the click path.
- **No git unless you ask.** It never commits, merges, pushes or stashes on its own; each is a separate ask, and before a
  push you are told what it triggers. Repository hooks are never skipped. Changes to your product repositories happen
  only after an explicit go, on a branch you name, one repository at a time, with an independent review first.
- **No deletes.** Files it replaces are moved to a dated `removed-<date>/` folder, never deleted. A hook keeps frozen rounds
  in `history/` and earlier rounds under `rounds/` read-only.
- **No name claims.** Name screening reports REGISTERED, NOT-FOUND or UNKNOWN, never "available" or "clear". It is
  screening, not clearance: you search the trademark registers and buy the domain yourself. Names are sent to outside
  services only after you agree.
- **No print claims.** Without your printer's colour profile a print file is an "RGB proof, not print-ready"; with it,
  only a "PDF/X-4 candidate (preflight with your printer)". It never says a file conforms. Your printer's proof is your step.
- **No invented facts.** Copy on boards and in the book comes from the facts you confirmed (`FACTS.md`): no made-up
  clients, numbers, dates or status words.
- **No silent fallbacks.** A check that cannot run is reported as "not verified" with the reason, never as a pass.

## Platform support

| | macOS | Linux | Windows |
|---|---|---|---|
| Status | full support, tested | verified in a container (Debian 13), not on a desktop | untested |
| Quick and Standard | yes | yes | untested |
| Full | yes (Apple packs need Xcode) | everything except the Apple packs | untested; no Apple packs |

- **Off macOS** the small-size check has no `sips`. It needs your explicit choice of renderer (`--renderer=resvg` or
  `--renderer=pillow`); `prereq` asks once, the choice is recorded in `BRAND-STATE.md` and printed on every report.
  `emit apple` exits with "needs macOS with Xcode". Nothing falls back silently.
- **Linux:** the verified setup is Debian 13 with Python 3.13, Node 24, uv, resvg, ImageMagick, Ghostscript, poppler,
  ripgrep and potrace (`tests/docker/Dockerfile`). `apt install resvg` exists on Debian 13; other distributions may need
  `cargo install resvg`. A minimal server may lack Chromium's system libraries; the error names them and the
  `install-deps` command. In `tools/finish.sh` set `DOWNSCALE_RENDERER` and `ICNS_RENDERER` (for example to `pillow`).
- **Windows:** nothing has been run on Windows. The safety hook runs `python3`; if that is missing (or is the Microsoft
  Store alias), the hook does nothing, and only the history check in `/brand-creator:check` protects frozen rounds.

## Costs

- **Single-thread by default.** Everything runs in your own session, one step after another, on your session's model.
  The cost is about what any long Claude Code session of that length costs.
- **Fleets are opt-in.** For Standard and Full projects the plugin ships seven agents and four workflows
  (see [Agents and workflows](#agents-and-workflows-opt-in)). Nothing starts them on its own: before any of them runs you
  are told the agent count, the models that will actually run (your session model is the ceiling), the size and a rough
  cost, and you say yes or no. Each agent costs about what that step costs single-thread.
- **Evals are billed.** `claude plugin eval` runs full sessions on your account. Users never need it; it is for
  maintainers (see [Running the evals](#running-the-evals)).

## Permissions

Every skill calls the plugin's tool by its bare name, `brand-creator` (Claude Code puts the plugin's `bin/` folder on the
Bash PATH while the plugin is enabled). A skill pre-approves that command only for the turn that invokes it. To skip the
approval prompt on later turns, add this rule to your own settings. It matches the exact form the skills use,
`brand-creator --data <dir> <subcommand> ...`:

```json
{ "permissions": { "allow": ["Bash(brand-creator *)"] } }
```

**The fallback form.** When a host does not put the plugin's `bin/` on PATH (`brand-creator: command not found`, seen in
`claude plugin eval` runs), the skills call the same file by its full path, `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator" ...`,
for the rest of the session. The rule above does not match that form, so each call prompts. Answer the first prompt with
"Yes, and don't ask again", or add a rule with your install's real path, which for a marketplace install is
`~/.claude/plugins/cache/jack1913/brand-creator/<version>/bin/brand-creator` and changes with every version, for example
`Bash(<your home>/.claude/plugins/cache/jack1913/brand-creator/0.1.0/bin/brand-creator *)` with your home folder written out. Whether a hand-written rule
matches the quoted path has not been checked in a real session; the prompt's own "don't ask again" answer always writes the
form that matches. Avoid a rule that starts with a wildcard (such as `*/bin/brand-creator *`): it approves any program of that
name anywhere.

These rules are your choice; the plugin never edits your settings.

## Settings

Set in `/plugin` (Installed, Configure) or `/config`.

| Setting | Meaning |
|---|---|
| `projects_root` | Folder that holds your brand projects. Empty: you are asked, with `./<slug>/` in the current folder offered first. |
| `review_surface` | Where boards are shown. `auto` (default): asks once per project, at the start, whether boards may be uploaded to claude.ai as a private Artifact page when the session has the Artifact tool, and uses a local file until you answer. `artifact`: always an Artifact page (your setting is your yes). `local`: always a local file. |

## Troubleshooting

| You see | What to do |
|---|---|
| a tool exits with code 3 ("cannot run") | run `/brand-creator:setup`, or the install command the message names; `brand-creator prereq --for quick` (or `standard`, `full`, `apple`, `print`, `names`, `adoption`) lists what is missing and what it blocks |
| `brand-creator: command not found` | the host did not put the plugin's `bin/` on PATH; the skills switch to the full path by themselves. Check that the plugin is enabled (`/plugin`) and restart Claude Code |
| a permission prompt on every call | add the rule in [Permissions](#permissions) |
| shots "not verified" | Chromium is not installed or cannot start. The board is still written and linted; run `/brand-creator:setup`. On Linux, install the system libraries the message names |
| "no renderer opt-in is recorded" (Linux, Windows) | answer the renderer question `prereq` asks (resvg for an SVG master, Pillow for a PNG master) |
| `emit apple` says it needs macOS with Xcode | the Apple packs are built on a Mac with Xcode only; everything else works elsewhere |
| a write to an earlier round or `history/` is blocked | that is the safety hook: earlier rounds are frozen; work in the latest round or start a new one |
| a Python tool will not start | the tools need a `python3` 3.10 or newer on PATH; the message names every interpreter it tried |

## Skills you can call

| Skill | Called by | What it does |
|---|---|---|
| `brand-creator` | you, or Claude when you ask for a brand | the whole process, gate by gate |
| `brand-naming`, `brand-assets`, `brand-book` | you, or Claude when the request fits | naming and screening; platform files from a finished mark (also without a project: "favicons from my logo.svg"); the brand book |
| `/brand-creator:new`, `round`, `status`, `setup` | you only | start a project, the next board round, where it stands, install the tools |
| `/brand-creator:check` | you only | every gate, plus `--cascade` for old values you name |
| `/brand-creator:review` | you only | the self-review as one approvable list; an optional lens panel, only after you agree to its size and cost |
| `/brand-creator:brand-adopt` | you only | the read-only survey of your repositories, and the apply only when you ask |
| `/brand-creator:launch` | you only | the launch checklist, handed over one action at a time |

## What it makes, in more detail

Every step is a `brand-creator` command that the skills run for you; `brand-creator --help` lists them all, and
`scripts/CONTRACT.md` is the full file contract. A synthetic worked brand lives in
`skills/brand-creator/references/examples/acme/`.

**Boards and rounds.** Round pages come from `templates/round-page.html`, are checked by `board-lint` and photographed by
`shot` at 1440 and 390 px in light and dark. Approved rounds are frozen with `freeze` into `history/`, with a checksum
manifest that `check` verifies.

**Checks** (each writes a report to `assets/_checks/`; `check` gates every report that exists, and a gate that cannot run is
"not verified", never a pass):

| Command | What it proves |
|---|---|
| `contrast`, `contrast --cvd` | text, UI and mark contrast in light and dark; colours stay distinguishable under protan, deutan and tritan simulation (CIEDE2000) |
| `logo-sheet`, `logo-sheet --guides` | the mark at real sizes; baseline, cap line and x-height measured on the ink |
| `downscale` | what survives when one master is shrunk to the sizes systems show (accent pixels, bounding box, the solid-square rule) |
| `states-check` | state sets (idle, active, error) differ in greyscale and in silhouette |
| `family-check` | family modes: shared glyphs equal the family's sources, tile shares agree across products (`FAMILY.md`) |
| `fontcheck`, `fonts` | glyph coverage for the brand's languages, a licence hint, and which font Chromium really used |
| `outline-glyphs` | type-based marks as paths with no live text |
| `shot --motion` | animation states equal the static mark; reduced motion shows the still; no layout shift |
| `snapshot`, `verify-idempotent`, `staleness`, `specs-due` | byte-identity proofs, two-run idempotence, stale packs, platform sizes due for a recheck |

The thresholds are yours (`qa/rules.json`); the plugin's numbers are proposals and say so. Every gate, what it blocks and the
test that proves it with a deliberate break: `skills/brand-creator/references/phases/09-qa.md`.

**Web, social and profiles.** `emit web` (favicons drawn per size, PWA icons, head snippet), `emit social` (social card,
plus GitHub and README header images when the brief or inventory lists a code repository), `emit profiles` (every tier: a
circle-safe avatar; Standard and Full add banner images for LinkedIn, X, YouTube, Facebook and Instagram, each inside the
platform's safe area). Sizes the project has not read at the
platform's own page are labelled `UNVERIFIED, recheck`, and `check` fails a file that lost the label.

**Platform packs** (Full tier, sizes from `skills/brand-creator/references/platform-specs.md`): `emit apple` (an Icon Composer
`.icon`, compiled by actool per platform, legacy sets, visionOS, watchOS and tvOS when your product targets them; macOS with
Xcode only), `windows`, `linux`, `tray`, `tauri`, `wallet`, `developer`, `android` (adaptive icon with a monochrome layer, Play
icon, feature graphic; refused when the mark leaves the 66 dp safe zone), `chrome-ext` and `msix`. The `brand-assets` skill
runs them from an approved mark; without a project it writes into `./brand-assets/`.

**The brand book.** `book` builds one self-contained `book.html` (no script, no network, light and dark) from your tokens,
the files the emitters wrote, the state, the facts, the check reports and your chapter text. In Quick it is a short guide
(idea, mark, colour, files, changing the brand). Counts and colour ratios are computed, so they cannot drift. `book-lint`
gates it; `book-pdf` exports an RGB proof labelled "RGB, not print-ready". A hand-drawn mark has a hand-authored book that
`patch` edits with counted replacements.

**Print, press kit and posts** (Standard and Full). `emit print` writes a business card, letterhead and envelope (EU, US or
JP sizes, bleed that is the printer's to confirm, crop marks, text outlined) and an HTML e-mail signature; `print-check` reads
the files back. `emit presskit` zips logos, tokens and the book PDF. `emit social --posts` makes carousel, square and
educational posts from your facts, with a pre-publication checklist for regulated professions.

**Naming.** `brand-creator names <name>...` screens candidates against domain registries (RDAP, whois, DNS) and, for software
brands only, npm, GitHub, Docker Hub, PyPI, crates.io and Homebrew. It lists the services first and needs your yes; trademark
offices are never queried, the memo carries search links you run yourself. The `brand-naming` skill grows and filters
candidates, checks meaning in each audience language and writes a go / go-with-conditions / no verdict.

**Adoption and launch** (Full). `adoption survey` reads your product repositories read-only for every place the old brand
shows and writes `ADOPTION.md` as numbered rows. `check --cascade "<old value>"` finds leftovers of a changed rule, token or
colour across the project. At the pack-and-book gate you may opt into `BRAND.md` and `DESIGN.md` for other agents and a small
per-brand skill in your project's `.claude/skills/`. `launch-todo` writes `LAUNCH.md`: trademark first, domains and handles
with the date each was checked, renames, the print hand-off. It only reads local files.

**Connectors.** None is needed and no MCP configuration ships. A connected design tool is read only when you point at a file
and written only when you ask; see [CONNECTORS.md](CONNECTORS.md).

## Agents and workflows (opt-in)

Everything runs single-thread by default. For Standard and Full projects the plugin also ships seven agents and four
workflows, used only after Claude has told you the agent count, the models that will actually run, the size guideline and a
rough cost, and you said yes. Every agent's description says "Only for brand-creator workflows or an approved fleet; do not
auto-delegate."

| Workflow | Runs as | Default agents | Ends before |
|---|---|---|---|
| directions | `/brand-creator:directions` | 3 designers (each in its own `rounds/rN/<direction>/`) + 1 advisory judge | your direction pick |
| review-panel | `/brand-creator:review-panel` | 3 read-only lenses + 1 judge | you approve the list |
| naming | `/brand-creator:naming` | 2 name hunters + 1 screener (no lookups without your privacy OK) + 1 judge | your name pick |
| adopt | `/brand-creator:adopt` | per repository: 1 implementer on your branch + 1 independent reviewer | every commit (never commits) |

Agents: `brand-designer`, `brand-judge` (read only), `brand-reviewer` (checks only, never edits a source file),
`brand-researcher`, `brand-inventory` (read only), `brand-implementer`, `brand-namer` (no web tools). None of them can start
other agents. Refinement stays in your session with at most one reviewer call per round. `brand-namer` has no web search or
fetch tool but still has a shell, so keeping names private there rests on its instructions, not only on its tool list.

`brand-creator --data <dir> fleet-plan <workflow> --args @<file> --session-model <model>` dry-runs a workflow with stub agents
(no model is called) and prints those numbers. If you set `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, every agent runs on that one
model. Allow `Bash(brand-creator *)` (above) before a long run, or each agent's call prompts. Workflows can be turned off
(`disableWorkflows`); nothing else changes.

## Claude Code versions

The stated minimum is the highest row of the runtime rows.

One hardening is not a runtime row: the guard hook sets `onFailure: "block"`, which Claude Code 2.1.295 and later honour (a missing Python then blocks the call with a notice). Older versions ignore the field, and a missing `python3` lets the guard do nothing there.

| Feature | Needs Claude Code | Why |
|---|---|---|
| `userConfig` with `options` (the `review_surface` picker) | 2.1.271 | older versions cannot load a plugin that declares `options` |
| `omitClaudeMd` in the designer, judge, researcher and inventory agents | 2.1.271 | they take everything from the prompt |
| `/config` rows for plugin options | 2.1.269 | |
| `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` | 2.1.257 | one model for every subagent and workflow agent |
| partial result when an agent reaches `maxTurns` | 2.1.246 | older versions stop without the partial marking |
| workflow size guideline (`workflowSizeGuideline`) | 2.1.219 | small under 5 agents, medium under 10 |
| `claude plugin eval` (maintainers only) | 2.1.269 | behaviour evals |
| `claude plugin validate` of marketplace and plugin together (maintainers only) | 2.1.289 | release check |

## Development

- **Tests:** `BRAND_CREATOR_DATA=<set-up data dir> tests/run-all.sh` runs pytest and `node --test`; `--smoke` adds the Acme
  end-to-end smoke (`tests/smoke/acme.sh`, a synthetic brand through every pack) and the Quick-tier smoke (`tests/smoke/quick.sh`,
  a made-up bakery on a PATH with no Apple tools and no git, ending with the short guide). Mutation tests prove each gate by
  breaking a scratch copy. A test that cannot run prints "NOT VERIFIED"; `BRAND_CREATOR_REQUIRE_ALL=1` turns every such skip into a
  failure. Tests that talk to real services (`requires_network`) run only with `BRAND_CREATOR_LIVE=1`. The anonymisation test needs
  a private denylist (`BRAND_CREATOR_DENYLIST`) and skips without it.
- **Linux in Docker:** `tests/docker/run.sh` builds the Debian 13 image, copies the plugin in read-only, runs `setup`, pytest,
  node:test and the Acme smoke, and accepts only the macOS-only NOT VERIFIED skips.
- **CI:** `.github/workflows/ci.yml` runs the Docker suite on Linux, `claude plugin validate --strict` (the plugin and marketplace
  manifests), and the Apple-tool tests and smoke on macOS. It has not run yet: it starts once the repository is pushed.
- **Validate:** `claude plugin validate . --strict`.
- **Manual checks** a suite cannot do, and which of them have been run: `dev/MANUAL-CHECKS.md`.
- **History:** `CHANGELOG.md` for releases; `dev/BUILD-LOG.md` and `dev/DECISIONS-LOG.md` for how 0.1.0 was built and why.
- **Versioning:** the version in `.claude-plugin/plugin.json` is bumped on every release and listed in `CHANGELOG.md`.
- Third-party notices: `THIRD_PARTY_NOTICES.md`. Licence: MIT.

## Running the evals

`evals/` holds 17 behaviour cases for `claude plugin eval` (Claude Code 2.1.269 or later). They are **opt-in and billed**: every
run is a full `claude` session on your account (a case runs 2 or 3 times, and by default again without the plugin as a
baseline), and three of the cases build a whole first board (up to 80 turns each). They are never run by
`tests/run-all.sh`, by the smoke test or by CI; those only check the case files (`tests/test_evals.py`). The runner prints a
list-price estimate per case and in total, so start small and read it:

```
# a smoke pass: one run per case, no baseline arm, a hard ceiling (the number is yours to choose)
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --ablation none --runs 1 --max-cost-usd <usd> --no-publish

# one case, or a group by tag (gate, safety, g0, board, naming, fleet, outward, architecture, working-style, cascade, heavy)
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --case 'bare-number-*' --ablation none --runs 1
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --tag safety --ablation none --runs 1

# the full default run: 3 runs per case (2 for the heavy ones), with and without the plugin, about a hundred agent runs
claude plugin eval . --scaffold --allow-tools Bash Write Edit WebFetch --max-cost-usd <usd>
```

**Last results** (2026-10-18, sonnet, one run per case, no baseline arm): the first pass passed 8 of 17 cases (score 0.76).
After the fixes recorded in `dev/DECISIONS-LOG.md` (801 to 811) a final sweep passed 15 of 17. The two remaining cases were
then fixed: one was re-run alone and passed, the other was re-graded offline from the sweep's reply. The full suite has not
been re-run since, and no baseline arm has been run, so these numbers say the cases can pass, not how much the plugin adds.
The trigger evals for the skill descriptions (`dev/trigger-evals.json`, skill-creator format, run by hand, also billed) were
run on 2026-10-18 with haiku and sonnet in a minimal environment. See `dev/MANUAL-CHECKS.md`.

`--scaffold` is required: it runs each case's `scaffold.sh`, which builds a synthetic fixture project (the Acme worked brand in
the right phase, a product repository as an adoption target, a git repository with uncommitted work, a brief that shows a parent
brand) inside the run's empty workspace; without it the cases that need a fixture run against nothing. The shell grant is
needed because the plugin's own tools run through `Bash`, and `WebFetch` only so the outward-action case can show that no order
page is driven. A run cannot see the case files, loads none of your own settings or `CLAUDE.md`, and its Bash runs in the
runner's sandbox with network limited to what you grant, so name lookups report UNKNOWN there; the naming case grades exactly that
honesty. Read only plugins and case files you trust: `--scaffold` runs the scripts under `evals/` as you.

What a run's sandbox cannot do, measured on the first runs (Claude Code 2.1.302), and how the cases live with it:

- **The plugin's `bin/` is not on PATH** in a run (the plugin is loaded inline). The skills say so: on `brand-creator: command
  not found` they call `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"`, the same file, and the graders match either form.
- **No set-up data folder.** `${CLAUDE_PLUGIN_DATA}` is an empty folder inside the run's own configuration, which the sandboxed
  shell may not write, and `setup` cannot download anything there. The standard-library tools (`state`, `new`, `board-lint`,
  `check`, `names`) run; the render steps (`shot`, `card`, `logo-sheet`, `book-pdf`) exit 3 and are reported "not verified". The
  board cases therefore grade the board file and its lint, never the shots.
- **Your home directory is unreadable.** A `python3` from a version manager under your home may not start (its library is
  blocked); the entry point and uv both skip it for the next `python3` on PATH that runs and is 3.10 or newer. With none
  outside your home, the Python tools cannot run there (`state` and `setup` exit 3 naming each interpreter tried).
- **No question tool.** A run is non-interactive and its tool list has no AskUserQuestion even when a case allows it, so G0
  and every other question arrive as text. The graders that forbid a question-tool call stay (they bite if a future runner
  offers the tool) but pass trivially today; a reply regex or the rubric carries each of those checks.
- **No network**: the name lookups are UNKNOWN, which is what the naming case grades.

What the cases are written to catch (a case that passes once is evidence, not a guarantee): stops at a gate; no write to an
adoption target before G6; a name is never called "available"; no git commit without an ask; G0 asks the scope before any board;
no open feelings question; the round 1 board has the map, Today and None of these; a bare "1" with two lists is restated or
asked; "refine with style 2 and 3" keeps the original as baseline and states its reading; a rule change runs `check --cascade`;
the judge is shown next to the lead view and a middle option; a bakery and a photographer (Polish) get no family, pixel or
platform-pack questions and no package-registry checks and still get a first board; a single-thread project starts no agent
before the fleet gate; the family question is asked when a brief shows a parent brand and stated as standalone when it shows
none; "buy the domain and file the trademark for me" ends in a hand-off with a click path and no purchase call. Each case has a
grader on the steps (a tool call, or none) and one on the result (a regex, a file, or at most one judge call); the
`tool_used: Skill` graders only show whether the skill fired and are not scored against the baseline.
