# AGENTS.md — swift plugin (single source of truth)

## 1. Project identity
A Claude Code plugin, `swift`, kept in `plugins/swift/` of the monorepo `jack1913/claude-plugins`, which is also the marketplace `jack1913` (ADR-0015; ADR-0014 for the catalogue), whose skills (`swift:swiftui`, `swift:design`, `swift:concurrency`, `swift:testing`) make an agent write correct, current, Apple-native Swift: SwiftUI, design, Swift 6 concurrency and tests; `swift:review` (slash-only) reviews a built screen against the HIG. Design: `docs/superpowers/specs/2026-09-24-swift-plugin-design.md`; part 2: `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md`.

## 2. Repo layout
This folder is the plugin root and one plugin of the monorepo `jack1913/claude-plugins`: from the monorepo root it is `plugins/swift/`. Every path in this file is relative to this folder unless it says otherwise. Run the commands from here, except `claude plugin tag`, which runs from the monorepo root.

| Path | Purpose |
| --- | --- |
| `.claude-plugin/`, `skills/`, `evals/`, `LICENSE.md`, `NOTICE.md` | What an install ships. Everything else in this folder (docs, maintenance, `.claude/`, `AGENTS.md`) is for contributors; the whole folder is the plugin root, `plugins/swift/` in the monorepo |
| `maintenance/` | Never shipped: API checker, upstream diff, unit tests, `swift:review` verification fixtures |
| `docs/manual/` | Consumer documentation — commands-first, one concept per page |
| `docs/internals/` | Technical mechanics — contributors only |
| `docs/adr/` | Architecture Decision Records |
| `docs/archive/` | Frozen point-in-time records |
| `docs/superpowers/` | Specs and plans (agent working directory, not a docs tier) |
| `.claude/CLAUDE.md` | Bridge: `@../AGENTS.md` (not at the root: `claude plugin validate --strict` rejects a `CLAUDE.md` at the plugin root) |
| `.claude/rules/` | Path-scoped constraints, auto-loaded when a matching file is read |
| `.claude/skills/` | Invoked procedures and reference packs |

## 3. Pointer index (source-of-truth → path)
| Topic | Path |
| --- | --- |
| Marketplace manifest: the monorepo's `.claude-plugin/marketplace.json` (two levels up; ADR-0014, ADR-0015) | `docs/adr/ADR-0015-plugin-moves-into-the-claude-plugins-monorepo.md` |
| Plugin manifest, the only version home | `.claude-plugin/plugin.json` |
| `swift:swiftui` (upstream fork) | `skills/swiftui/SKILL.md` |
| `swift:design` | `skills/design/SKILL.md` |
| `swift:concurrency` (upstream fork) | `skills/concurrency/SKILL.md` |
| `swift:testing` (upstream fork) | `skills/testing/SKILL.md` |
| `swift:review` (ours, slash-only) | `skills/review/SKILL.md` |
| Generated platform table | `skills/swiftui/references/platform-availability.md` |
| Upstream baselines, Deviations, Ported, Findings (one section per upstream) | `UPSTREAM.md` |
| License (MIT), ships with the plugin | `LICENSE.md` |
| Third-party notices | `NOTICE.md` |
| API checker CLI | `maintenance/check-apis.py` → `maintenance/apicheck/cli.py` |
| API manifest: frameworks, claims, ignore list | `maintenance/apis.json` |
| Upstream diff | `maintenance/upstream-diff.sh` |
| Unit tests | `maintenance/tests/` |
| `swift:review` verification fixtures, answer key, scorer | `maintenance/review-fixtures/` |
| `swift:review` verification record (dated, frozen sections) | `docs/internals/review-verification.md` |
| Eval suite | `evals/` |
| Design spec | `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-24-swift-plugin.md` |
| Operator manual | `docs/manual/README.md` |
| Capability matrix: skills, topics, shared rules, eval cases | `docs/manual/reference/capabilities.md` |
| Changelog | `CHANGELOG.md` |
| Agent instruction layout, rule-vs-skill decision rule | `docs/internals/agent-instructions.md` |

### Auto-loaded rules
Each loads only when Claude reads a file matching its `paths:` frontmatter, so an
unscoped rule taxes every session. Keep this table in step with `.claude/rules/`.

| When you need... | Where to look |
| --- | --- |
| Import rules for the API checker (`maintenance/apicheck/*.py`, `maintenance/check-apis.py`): standard library only | `.claude/rules/apicheck-stdlib-only.md` |

### Skills
Invoked with the `Skill` tool, or by name. A skill's body costs nothing until it is
invoked, so reference material belongs here rather than in a rule.

| Skill | When to use |
| --- | --- |
| `changelog-release` | Cut a release: bump `.claude-plugin/plugin.json`, write `CHANGELOG.md`; stages, never commits |
| `update-docs` | Bring docs back in line with the code after a change |
| `update-rules` | Re-ground the claims inside `.claude/rules/` and `.claude/skills/` |

The plugin's own skills live in `skills/`, not in `.claude/skills/`.

## 4. Project constraints
- Docs describe implemented state.
- `docs/archive/**` is frozen — never edited.
- A stale pointer is worse than no pointer: moving or renaming a **doc, rule or
  skill** means fixing its row above in the same change. Nothing fails a build when
  these tables drift.
- Names are fixed: marketplace `jack1913` (repo `jack1913/claude-plugins`; named `jack1913-plugins` in 0.2.x and `swift-plugin` before 0.2.0; ADR-0012, ADR-0014, ADR-0015), plugin `swift`, skills `swift:swiftui`, `swift:design`, `swift:concurrency`, `swift:testing` and `swift:review`; the example-app layer depends on the first two (spec §1 goal 2; ExampleApp companion spec named in the spec header; part-2 spec §2).
- A change under a forked skill (`skills/swiftui/`, `skills/concurrency/`, `skills/testing/`) is its own commit, with its `UPSTREAM.md` → Deviations row — in that upstream's section — in that commit (spec §4; part-2 spec §3). This applies while writing, when no `paths:` rule has loaded.
- Never hand-edit the block between the `BEGIN GENERATED` / `END GENERATED` markers in `platform-availability.md`; run `python3 maintenance/check-apis.py --write-table`.
- New code in `maintenance/apicheck/` or `maintenance/check-apis.py` stays standard-library-only, including while a file is being created (`.claude/rules/apicheck-stdlib-only.md` only loads on read); see `docs/internals/agent-instructions.md`.
- Release through `changelog-release`, then, from the monorepo root, `claude plugin tag plugins/swift`; see `docs/manual/work-on-it.md#release`.

## 5. Documentation map
`docs/manual/` (consumer) · `docs/internals/` (technical) · `docs/adr/` (decisions) · `docs/archive/` (frozen).
