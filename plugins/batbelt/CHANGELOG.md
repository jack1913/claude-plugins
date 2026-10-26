# Changelog

All notable changes to batbelt are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A `puppet-master` skill: one Claude session starts background worker sessions, one job each, relays their questions to you one at a time, compacts a worker only between tasks once it is measured at 30% of its context or more, and closes it when its job is done. It needs Node.js 20 or newer and a setting of your own first. See [Run background workers](docs/manual/use/run-background-workers.md).

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
