# ADR-0003: Explicit SemVer in one place, tagged with `claude plugin tag`

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commit `e23aa05` (`plugin.json` with `version`, marketplace entry without one); `docs/archive/specs/2026-09-24-swift-plugin-design.md` §2 "Versioning" row, §6 "Versioning" and release flow, §8 "Version"; `docs/archive/plans/2026-09-24-swift-plugin.md` Global Constraints ("`0.0.0` until the first release, which is `0.1.0`")

## Context

Claude Code decides whether an install needs updating by the plugin's version. It reads `plugin.json` first, then the marketplace entry, then falls back to the git commit SHA; with an explicit version, only a bump reaches installs (spec §8). The owner wanted versions, so that installs refresh only when the version is bumped (spec §2).

## Decision

Keep one SemVer `version`, in `plugins/swift/.claude-plugin/plugin.json`. The marketplace entry in `.claude-plugin/marketplace.json` has no `version` key. A release:

1. The `changelog-release` skill raises the version and writes `CHANGELOG.md`.
2. The owner commits.
3. `claude plugin tag plugins/swift` creates `swift--v<version>` after checking that `plugin.json` and the marketplace entry agree.
4. The commit and tag are pushed.

Rejected:

- a second `version` on the marketplace entry, because two homes drift apart (spec §6);
- no `version` at all. Claude Code would fall back to the git commit SHA, so every pushed commit would be an update (spec §2, §8).

## Consequences

- A push without a version bump never reaches installs.
- `0.0.0` means unreleased; the first release is `0.1.0` (plan, Global Constraints).
- The marketplace entry must stay free of `version`, or the two copies can disagree.
