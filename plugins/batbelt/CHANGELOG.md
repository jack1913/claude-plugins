# Changelog

All notable changes to batbelt are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
