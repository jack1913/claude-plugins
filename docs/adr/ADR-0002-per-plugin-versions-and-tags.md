# ADR-0002: A plugin's version lives only in its plugin.json; releases are tagged per plugin

- **Status:** accepted
- **Date:** 2026-10-19
- **Source:** commits b343cbb (jack1913 marketplace: brand-creator and swift), e55457d (the marketplace moves to
  `jack1913/claude-plugins`), 9f6a1b7 (one workflow per plugin, root README);
  `plugins/swift/docs/adr/ADR-0003-explicit-semver-one-version-home.md` (the rule for swift, before the monorepo);
  `README.md` ("Layout", "Adding a plugin" step 5)

## Context

Claude Code reads a plugin's version from its `plugin.json`, then from the marketplace entry, and otherwise falls back
to the commit SHA. An explicit version means installed copies update only when it is bumped. Three plugins in one repo
release on their own schedules.

## Decision

- Each plugin's SemVer version lives only in `plugins/<name>/.claude-plugin/plugin.json`. Marketplace entries in
  `.claude-plugin/marketplace.json` carry no `version`.
- A release is tagged per plugin as `<name>--vX.Y.Z`, created from the repo root with `claude plugin tag plugins/<name>`,
  which checks `plugin.json` against the marketplace entry before tagging.
- There is no repo-wide version, tag or changelog; each plugin keeps its own `CHANGELOG.md` (batbelt has none yet).

Rejected:
- A second `version` on each marketplace entry: two homes that drift.
- No version at all: every push would count as an update.
- One repo-wide version or tag (not recorded as weighed; implied by the per-plugin tags since 9f6a1b7): the plugins
  release independently.

## Consequences

- A push that does not bump a plugin's version never reaches installed copies; `claude plugin update <plugin>@jack1913`
  (or `/plugin` → Marketplaces → `jack1913` → Update marketplace) picks up a bump
  ([Claude Code docs, "Keep plugins updated"](https://code.claude.com/docs/en/discover-plugins#keep-plugins-updated)).
- Tags are namespaced per plugin (`git tag -l 'swift--v*'`); swift's tags came with its history.
- Untagged releases exist: batbelt and brand-creator have no tags, and swift 0.3.0 (88f4acb) and 0.3.1 (99095cb) are
  untagged (the newest tag is `swift--v0.2.3`). `claude plugin tag` tags `HEAD`, so the current version can be tagged
  with the same command; an older release only from a checkout of its release commit.
