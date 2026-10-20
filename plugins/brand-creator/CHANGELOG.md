# Changelog

All notable changes are listed here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[SemVer](https://semver.org/). The plugin version is in `.claude-plugin/plugin.json`. How 0.1.0 was built, stage by
stage, and why, is in the [archive](docs/archive/README.md).

## [Unreleased]

## [0.2.2] - 2026-10-20

### Added

- A commands reference page in the manual lists every command, workflow and agent, who can start each one, and its
  arguments.
- An index of the reference files the `brand-creator` skill reads
  (`skills/brand-creator/references/_index.md`), linked from the skill.

### Changed

- The README is now a short storefront. Everything else moved into a manual under `docs/manual/`: a first-brand
  walk-through, one how-to page per task, and reference pages for commands, settings, permissions, costs, agents and
  workflows, platform support, Claude Code versions and troubleshooting.
- The README's reference and development halves moved: contributor notes are in `docs/internals/`, and the build log
  and decisions log are archived in `docs/archive/`. New decisions are recorded as ADRs in `docs/adr/`.
- The plugin description is now one plain sentence: "Make a logo, colours and every brand file your product needs, step
  by step, with you deciding at each step."
- `CONNECTORS.md` uses plain words instead of internal step codes: writes to a design tool happen only after you approve
  the finished files.
- The listing text of the `brand-creator`, `brand-assets`, `brand-book` and `brand-naming` skills is shorter and in plainer
  words. When they start is unchanged, but the trigger evals have not been re-run for the new wording.
- The `/` menu descriptions of the typed-only commands (`new`, `round`, `status`, `check`, `review`, `launch`, `setup`
  and `brand-adopt`) now say in plain words what each does and end with "Runs only when typed as
  /brand-creator:<name>." `brand-adopt` also says how it differs from the adopt workflow.
- The agent descriptions keep the "Only for brand-creator workflows or an approved fleet; do not auto-delegate." opener,
  then say in one plain sentence what the agent does. The model and tools are set in each agent's own fields.
- The author in `plugin.json` is now Jacek Pytlik, and the marketplace entry carries only the name, source, category and
  tags; the description and links live in `plugin.json`.
- The trigger-eval list moved from `dev/trigger-evals.json` to `evals/trigger-evals.json`.

## [0.2.1] - 2026-10-19

### Changed

- The descriptions in Claude Code's `/` menu, skill list and agent list now say in plain words what each command, workflow
  and agent does and when it may run, instead of internal gate codes such as "G0" or "after G6". What each one does, and
  when it is allowed to run, is unchanged.

## [0.2.0] - 2026-10-19

**Breaking:** brand-creator is now listed in the `jack1913` marketplace, in `plugins/brand-creator/` of
[jack1913/claude-plugins](https://github.com/jack1913/claude-plugins). The install ID changes from
`brand-creator@brand-creator` to `brand-creator@jack1913`. Claude Code can't move an install between marketplaces, so
move it by hand:

- `claude plugin uninstall brand-creator@brand-creator`;
- `claude plugin marketplace remove brand-creator`;
- `claude plugin marketplace add jack1913/claude-plugins`;
- `claude plugin install brand-creator@jack1913`.

If you wrote a permission rule with the plugin's full path, its folder changed from `cache/brand-creator/brand-creator/`
to `cache/jack1913/brand-creator/`. The `Bash(brand-creator *)` rule needs no change.

### Fixed

- The safety hook is stricter about archives: it blocks an extract into a round, a project folder or a folder above one,
  refuses an extract it can't see into, and reads tar, unzip and 7z options the way those tools do.
- The safety hook treats `git stash push -u` or `-a` without a precise path as covering the whole working tree, so it
  can't sweep up locked rounds.

### Changed

- The README is rewritten for users: what to say, what you get, and a troubleshooting table near the top. The reference
  half is unchanged.

## [0.1.0] - 2026-10-18

The first release.

### Added

**The process.**

- The `brand-creator` skill runs a brand-identity project as phases with owner gates (G0 scope to G7 outward hand-offs, plus
  the G-sys tripwire after a third patch in one area), in three tiers: Quick, Standard and Full. It resumes from the
  project's `BRAND-STATE.md`, works for any kind of business or person, and also fires for work on a brand project's files
  and for a brand's launch steps (handed to the owner, never done for them).
- G0 asks at most three concrete scope questions (tier; architecture only when a parent brand or siblings show; the name only
  when it is open), each with a recommended answer, and states the rest as defaults. It asks once before boards are uploaded
  to claude.ai. Without a question tool, the same questions come as one plain-text message.
- Round 1 shows three divergent directions with a strategy core, a positioning map, the hardest surface, "Today" when a mark
  exists, "None of these" and numbered questions with lettered options. Directions keep stable word names; a choice is
  restated before an expensive build; the liked direction is deepened, never hybridised after the pick.
- User skills: `/brand-creator:new`, `round`, `status`, `setup` (a consented install into the plugin's data folder),
  `check` (every gate, plus `--cascade` for old values), `review` (the self-review as one approvable list), `brand-adopt`
  and `launch`. Model-invocable skills: `brand-naming`, `brand-assets` and `brand-book`.
- Phase references 00 to 13, a board contract, working-style defaults, anti-pattern case cards, a strategy core,
  architecture modes (standalone, family-member, product-in-family), a cascade checklist, regulated-industries rules and
  a synthetic worked brand (Acme).

**Checks** (each writes a report; a check that cannot run is "not verified", never a pass).

- `board-lint`, `shot` (1440 and 390 px, light and dark), `contrast` (text, UI and the colours that touch in the mark) and
  `contrast --cvd`, `logo-sheet` and `logo-sheet --guides`, `downscale` (one report per master), `states-check`,
  `family-check`, `fontcheck` with the platform-font report, `outline-glyphs`, `shot --motion`, `snapshot`,
  `verify-idempotent`, `staleness`, `specs-due`, `book-lint`, `print-check`, and `check`, which gates them all and verifies
  the frozen history's checksum manifest.
- Owner thresholds in `qa/rules.json` and size bands; the plugin's numbers are proposals.

**Tokens and assets.**

- Design tokens from DTCG 2025.10 sources to CSS, JSON, Swift, Android XML and colour sets.
- `emit web` (favicons drawn per size band, PWA icons, head snippet), `emit social` (social card, GitHub and README header
  images; `--posts` for carousel, square and educational posts), `emit profiles` (circle-safe avatar and banner images inside
  each platform's safe area).
- Platform packs for the Full tier, every size read from `scripts/emitters/platform-specs.json` with its source, date and
  status: Apple (an Icon Composer `.icon` compiled by actool per platform, legacy sets, visionOS, watchOS and tvOS; macOS with
  Xcode only), Windows, Linux, tray, Tauri, Wallet, developer, Android (adaptive icon with a monochrome layer and a 66 dp
  safe-zone gate), Chrome extension and MSIX. Files built from a size not yet read at the platform's own page are labelled
  `UNVERIFIED, recheck`, and `check` fails a file that lost the label.
- `templates/finish.sh.tpl`: the whole build chain in order, each step gated by the tier.

**Brand book, print and press.**

- `book` builds one self-contained `book.html` (a short guide in Quick, the whole book in Standard and Full), byte-identical
  on rebuild, with computed counts and ratios; `book-pdf` exports an RGB proof; `patch` edits a hand-authored book with counted
  replacements; `collapse` removes losing variants with a dated copy.
- `emit print`: business card, letterhead and envelope (EU, US or JP sizes, bleed, crop marks, outlined text, boxes set) and an
  HTML e-mail signature. Without the printer's profile a file is an "RGB proof, not print-ready", with it only a "PDF/X-4
  candidate". `emit presskit` writes a deterministic zip.

**Naming.**

- `brand-creator names` screens names against domain registries and, for software brands, package registries, and reports
  REGISTERED, NOT-FOUND or UNKNOWN, never "available". It asks before sending names anywhere, saves raw responses for
  replay and links trademark searches for the owner to run. The `brand-naming` skill writes a go / go-with-conditions / no
  verdict memo.

**Adoption and launch.**

- `adoption survey` reads product repositories read-only and writes `ADOPTION.md` as numbered, append-only rows;
  `check --cascade` finds leftovers of an old value across every project file; opt-in `BRAND.md` and `DESIGN.md` adapters and
  a per-brand applied skill; `launch-todo` writes `LAUNCH.md` from local files only.

**Agents and workflows (opt-in).**

- Seven agents (`brand-designer`, `brand-judge`, `brand-reviewer`, `brand-researcher`, `brand-inventory`,
  `brand-implementer`, `brand-namer`), none of which can start other agents or is delegated to automatically, and four
  workflows (`directions`, `review-panel`, `naming`, `adopt`), each ending before an owner gate. A fleet runs only after the
  owner has been told the agent count, models, size and rough cost and said yes; `fleet-plan` dry-runs one with stub agents.

**Safety.**

- A hook keeps `history/` and earlier rounds read-only and stops a brand project folder from being deleted or moved (shell writes,
  deleters, destructive git, and archive extracts it cannot see into are blocked, failing closed when unsure); the RULES
  line in every skill, agent and workflow forbids commits, pushes, deletes and outward actions unless asked.

**Platforms and tests.**

- Tested on macOS; the suite and the end-to-end smoke also run on Linux in a container (`tests/docker/`). Windows is untested.
- pytest and node:test suites with mutation tests for each gate, the Acme end-to-end smoke, a Quick-tier smoke on a PATH with no
  Apple tools and no git, 17 behaviour evals (`evals/`, billed, run by hand) and trigger evals (`dev/trigger-evals.json`),
  and a CI workflow (Linux, `claude plugin validate --strict`, macOS) that runs once the repository is pushed.

Known limits at 0.1.0:

- Windows has never been run. On Windows the safety hook needs `python3` on PATH.
- The behaviour evals were run once (2026-10-18); see [Evals](docs/internals/evals.md) for the results.
- Some platform sizes are unverified and labelled so; recheck them with `brand-creator specs-due`.
- In Quick, `emit social` also writes GitHub and README header images, and profile images need Standard.
