# ADR-0001: Ship as a private single-plugin marketplace, enabled per project

- **Status:** superseded by ADR-0014
- **Date:** 2026-09-25
- **Source:** commit `e23aa05` (scaffold the marketplace and plugin); `docs/archive/specs/2026-09-24-swift-plugin-design.md` §1 goal 5, §2 "Packaging" and "Location" rows, §3 install commands, §9 (private GitHub marketplace); `claude plugin install --help` and `claude plugin marketplace add --help` (default scope)

## Context

The skills must be active only in the Swift repos that opt in: a repo that hasn't enabled them must not see them at all (spec §1, goal 5). A skill in the user's own skills directory loads in every repo that user opens.

## Decision

Package the skills as a Claude Code plugin, `swift`, listed in a marketplace, `swift-plugin`, that holds that one plugin (`source: ./plugins/swift`). The marketplace is meant to live in the private GitHub repo `jack1913/swift-plugin` (spec §2, "Location"). A repo enables it with `claude plugin marketplace add jack1913/swift-plugin` and `claude plugin install swift@swift-plugin`, each with `--scope project` (committed) or `--scope local` (per checkout).

Rejected: a user-level skill, which would load in every repo (spec §2, "Packaging": "a user-level skill would load everywhere").

## Consequences

- The repo carries two manifests: `.claude-plugin/marketplace.json` at the root and `plugins/swift/.claude-plugin/plugin.json` in the shipped folder. Only `plugins/swift/` is copied into an install.
- Every consuming repo passes an explicit `--scope`, because both commands default to user scope. A user-scope `install` enables the plugin in every repo; a user-scope `marketplace add` registers the marketplace for every repo.
- Once the marketplace is pushed to the private `jack1913/swift-plugin`, only people who can read that repo get the plugin from a repo's committed settings.

## Update 2026-10-19

The Status line used to read, before it was reduced to the one-status grammar of the docs standard: "superseded by ADR-0014 (the catalogue is `jack1913/claude-plugins`, marketplace `jack1913`; amended earlier by ADR-0012)". ADR-0012 amended this record's marketplace name before ADR-0014 superseded it.
