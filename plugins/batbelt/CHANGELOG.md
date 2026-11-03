# Changelog

All notable changes to batbelt are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A `puppet-master` skill: one Claude session hands your jobs to the Claude sessions you already have open, and starts a background worker only when none of them is free. Each session gets one job. The master relays their questions to you one at a time, quoting your own words, and gets a session compacted only between tasks once it is measured at 30% of its context or more: a background worker by itself, while your own window is left to auto-compact unless you ask for `/compact` lines to paste. It closes background workers when their jobs are done. It runs only when you type `/batbelt:puppet-master`. It needs Node.js 20 or newer and a setting of your own first. See [Run background workers](docs/manual/use/run-background-workers.md).
- `puppet-master` keeps one session as an analyst. It reads the day's transcripts of the sessions you named, records what went wrong with evidence, with anything that looks like a secret blanked, and at the end of the day proposes changes for you to approve, reject or defer. It never changes the plugin itself.
- A batbelt option, `puppet_logs_dir`: where the analyst keeps its logs. Leave it empty to use the plugin's data folder.
- `puppet-master` shows each session's model and effort, and every job names a tier: `creative` (an Opus model at high effort or more) or `mechanical` (another model at medium effort or less). When a session doesn't match, Claude gives you the `/model` and `/effort` lines to paste. It never changes a session's settings itself. A background worker it starts gets the tier's model and effort from the start.
- `puppet-master` warns before a session auto-compacts: from 80% of the size where it has seen your sessions compact, or the one you set in `PUPPET_COMPACT_AT`.
- `puppet-master` can give a finished session another job while it is under 30% of its context window, add a follow-up to the job a session holds, reopen a job closed too early, and can run two jobs in one repository when each names the folders it writes and only one of them runs git.
- A `puppet-master` worker's brief names the kind of deliverable (code, a document or a browser run), which the worker states back first, the local state it would otherwise stop to ask about, and the writes you can approve in its window up front. It reminds the worker that files its tools write by default count against its write scope, and that after a compaction it takes its place from git, not from the summary. It also reports cache folders a formatter hook leaves behind, runs multi-line scripts from a file instead of heredocs, and, when it may not run git, gets the git facts it needs in the brief.
- `puppet-master` remembers a closed session by name and prints its resume command when you mention it again. It closes a job in the same turn the session reports it done, and marks a session that reported done while its job is still open.
- The analyst's day starts at 05:00, so work past midnight stays with its day (`PUPPET_DAY_START_HOUR` changes the hour). It also records your answers to Claude's question dialogs, and no longer logs an idle notification as an empty message.

## [0.3.0] - 2026-11-01

This release changes how the docs of a repository you set up are kept. While batbelt is `0.y.z`, a minor
release may break things: the stamped `update-docs` and `changelog-release` now do more on their own (see
Changed). Run `/batbelt:onboard-repo --sync` in each repository you set up; it lists what changes before it
writes anything.

### Added

- A Local deviations list in the docs standard. `--sync` fills it from how your docs are already built, so a
  repository's own layout, reading tour and output blocks are kept instead of reported.
- A getting-started page shape, and a how-to shape that shows each command with its PowerShell twin, the real
  output with a note on how it was captured, what it means, a `You see | Do this` table and a Next link.
- `check-docs` checks that the manual's Next links follow the index (`NEXT_CHAIN`), that the index's page count
  matches its list (`TOC_COUNT`), and that every shell command has a PowerShell twin (`PLATFORM_TWIN`, an error
  with `--platform-pairs`).
- `check-docs --forbidden-allow`, to check that a fact another repository owns is linked, not restated.
- `check.py shrink-check`, so the stamped `update-docs` can stop a rewrite that guts a page.
- `/batbelt:onboard-repo` asks which README voice you want before it writes the README, and the README starts
  with an Install section.
- `--sync` adds any section the template gained (such as Local deviations or the README list) to your existing
  docs standard, as a diff for you to confirm, instead of only showing the whole file as changed.
- A deferred row in the coverage record now says why it is deferred.

### Changed

- Your repository's own choices outrank the docs standard: REPO SPECIFICS first, then the Local deviations, then
  the standard, then built-in defaults. The standard no longer sets the README voice.
- The default docs voice is commands-first again: one concept per page, each showing what you'll actually see.
- How-to pages sit directly in `docs/manual/` by default. An existing manual is never moved or regrouped, and one
  that uses `use/` keeps it.
- The README keeps its install command whatever its voice, and every `update-docs` run checks the README's fixed
  rules.
- `update-docs` fixes a claim it can re-derive from the code, such as a count or a flag name, instead of only
  reporting it. New pages, decision records and captures still wait for you.
- `update-docs` checks the claims on the pages a run changed, with one reviewer per angle, at most 8 readers and
  2 rounds, then reports what is left.
- `update-docs` lists stale captures once and re-takes them after one yes, with read-only commands only.
- `update-docs` reports unchanged niche deferrals and known baselines as one line, and offers the decision-record
  check only when a record's sources changed.
- `changelog-release` prints the commit, push and tag commands, then runs them one by one after one yes. Your own
  permission rules still apply to each command.
- Before 1.0, `changelog-release` bumps the minor version for a feature: 0.1.2 becomes 0.2.0.
- With a release script, `changelog-release` stops before the cut when `--suggest` prints a version other than
  the one you approved.
- `changelog-release` asks for an entry, or a reason to skip, for every merge in the release. Both skills commit by
  explicit path and name any unrelated changes they left out.
- `changelog-release` cuts a SemVer version only when you ask for a release; a routine run only updates
  `[Unreleased]`. It tags and pushes the tag only from the release branch.
- The manual index is renumbered one list at a time, unless you numbered on from one group to the next, which is
  kept. Its page count names the tour's last number, and a tour whose numbers skip is reported.
- `PLATFORM_TWIN` accepts only a PowerShell command block as the twin, not captured PowerShell output; twins pair
  in order within a section, with output blocks between them. The tour checks report on the pages `--only` names.
- The tour checks read a list item whose text wraps onto the next line, and a Do a task section with
  subsections, as one tour. A malformed `--forbidden-allow` pattern is refused with a usage error.
- A tour entry's page is the link its line starts with. An index whose only list is plain numbered steps still gets
  its page count fixed, a total is left alone when the index is ambiguous, numbering is judged list by list the way
  `renumber-toc` writes it (an auto-numbered list, 1. 1. 1., is valid), and a bold range in a table cell is no
  longer taken for the count. A renamed Do a task group is found by its links to how-to pages.
- PowerShell twins may come before or after their shell command, and pair by script name. Only a command that runs
  a `.sh` front-end with a `.ps1` sibling (a remote install one-liner for this repo included; a third-party
  installer is not) needs one; a block that runs both scripts is its own twin, names compare without case, and a
  CLI, `git` or `npm` command needs none.
- A numbered list that starts at 0 (an opt-in step 0) keeps its zero start when the index is renumbered.
- Platform pairs come only from a `.sh` the README or the manual names whose `.ps1` sibling exists, the same rule
  the twin check uses; `uninstall.sh` no longer counts as naming `install.sh`.
- `--forbidden-allow` globs are paths from the repo root, a `[...]` class never matches a `/`, and a glob that
  matches no file is reported (`FORBIDDEN_ALLOW_UNUSED`).
- `--sync` asks whether a missing tour feature (no numbered list, no Next links, no New here? pointer) is
  deliberate before recording it, so an unfinished manual is not excused for good.
- `--forbidden-allow` patterns are anchored: `*` stays within one folder, `**` crosses folders, and `README.md`
  matches only the README at that level.
- The README and the manual carry the jack1913 brand header.

## [0.2.1] - 2026-10-20

### Added

- `/batbelt:onboard-repo --check` reports a repository that has the docs folders but no `docs/internals/docs-standard.md`, and says `--sync` creates it.
- The "Set up a repository" page shows what a real `--sync` looks like, and how to keep a repository up to date after a batbelt update.

### Fixed

- The opening of the `onboard-repo` instructions now names every skill it stamps: `changelog-release`, `update-docs`, `update-rules`, and `update-deps` when you agree.

## [0.2.0] - 2026-10-20

While batbelt is `0.y.z`, a minor release may break things. This one removes a command.

### Added

- A docs standard page for repositories you set up with `/batbelt:onboard-repo`: `docs/internals/docs-standard.md` covers page kinds, voice, changelog and decision-record rules. It is listed in the internals README and the `AGENTS.md` index. Already set up? Run `/batbelt:onboard-repo --sync` to add it.
- A `docs/manual/use/` folder for task pages, and page shapes for how-to and reference pages that the manual-writing step follows.
- A `LICENSE` file in the plugin folder, so the MIT licence travels with the install.
- A commands page and a troubleshooting page in the manual, plus one how-to page each for grilling a plan, proving a claim and setting up a repository.
- A short description, display name and keywords for the plugin, so it reads well in the plugin list.

### Changed

- The manual index of a new repository is now grouped as Get started, Do a task and Look it up, instead of a numbered reading order. The stamped `update-docs` skill writes manual pages task-first and follows the docs standard page when the repository has one.
- The decision-record template now has a `Supersedes` line, the full status list and a note on how to add updates after acceptance.
- Stamped skills now say `from batbelt` in their header. Repositories stamped earlier, which say `from claude-configs`, still sync. Run `--check` to see which stamped files are behind.
- `/batbelt:grill-me` now also starts on its own when you say "grill me" or ask to stress-test a plan.
- The `/batbelt:onboard-repo` description says plainly what it sets up and that it runs only when typed. Its argument hint now lists every flag, including `--with update-deps` and `--without update-deps`.
- The docs moved into `docs/manual` (for using batbelt) and `docs/internals` (for contributors). The README is shorter and links to them.
- The `onboard-repo` instructions are split: the long sections moved into files under `skills/onboard-repo/references/`. Their rules did not change; references to design records from another repository were dropped.

### Removed

- `/batbelt:grilling`. Type `/batbelt:grill-me`, or just say "grill me".

## [0.1.2] - 2026-10-19

### Security

- `onboard-repo` no longer proposes allow rules that an appended flag can turn into a shell command. Build, test and
  lint commands are allowed in exact forms only (`npm test`, `cargo test`, `dotnet build`, `pytest`, `uv sync --locked`
  and so on), `git fetch` only as `git fetch` and `git fetch origin`, and `git stash list` and `git stash show` exactly.
  A run with extra flags now prompts, and `npm run` and `pip show` are no longer allowed. Before, a rule such as
  `git fetch:*` let `git fetch --upload-pack=<cmd>` run `<cmd>` unprompted.
- `settings-audit`, and so `/batbelt:onboard-repo --check` and `--sync`, now reports those wildcard rules in an
  existing `.claude/settings.json` under `broad_allows`. Re-run `--sync` in a repo you onboarded before this release.

### Changed

- The README is written for users: install, the four commands, what each one gives you, and troubleshooting. The
  maintainer notes moved, unchanged, to `docs/how-it-works.md`.

## [0.1.1] - 2026-10-19

### Fixed

- `check-docs` now verifies a `capture=` block whatever its fence language; an output-only `console` capture was never
  checked before.

## [0.1.0] - 2026-10-19

### Added

- First release in the `jack1913` marketplace, under the MIT licence: `grilling`, `grill-me`, `prove-it` and
  `onboard-repo`, moved here from the configuration repository they came from.
- `onboard-repo` proposes permissions that allow only non-destructive git, npm and dotnet forms; dependency and
  database changes ask first.
