# AGENTS.md — swift-plugin (single source of truth)

## 1. Project identity
A private Claude Code plugin marketplace with one plugin, `swift`, whose skills (`swift:swiftui`, `swift:design`, `swift:concurrency`, `swift:testing`) make an agent write correct, current, Apple-native Swift: SwiftUI, design, Swift 6 concurrency and tests; `swift:review` (slash-only) reviews a built screen against the HIG. Design: `docs/superpowers/specs/2026-09-24-swift-plugin-design.md`; part 2: `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md`.

## 2. Repo layout
| Path | Purpose |
| --- | --- |
| `plugins/swift/` | The only directory an install copies: manifest, skills, NOTICE, eval suite |
| `maintenance/` | Never shipped: API checker, upstream diff, unit tests, `swift:review` verification fixtures |
| `docs/manual/` | Consumer documentation — commands-first, one concept per page |
| `docs/internals/` | Technical mechanics — contributors only |
| `docs/adr/` | Architecture Decision Records |
| `docs/archive/` | Frozen point-in-time records |
| `docs/superpowers/` | Specs and plans (agent working directory, not a docs tier) |
| `.claude/rules/` | Path-scoped constraints, auto-loaded when a matching file is read |
| `.claude/skills/` | Invoked procedures and reference packs |

## 3. Pointer index (source-of-truth → path)
| Topic | Path |
| --- | --- |
| Marketplace manifest | `.claude-plugin/marketplace.json` |
| Plugin manifest, the only version home | `plugins/swift/.claude-plugin/plugin.json` |
| `swift:swiftui` (upstream fork) | `plugins/swift/skills/swiftui/SKILL.md` |
| `swift:design` | `plugins/swift/skills/design/SKILL.md` |
| `swift:concurrency` (upstream fork) | `plugins/swift/skills/concurrency/SKILL.md` |
| `swift:testing` (upstream fork) | `plugins/swift/skills/testing/SKILL.md` |
| `swift:review` (ours, slash-only) | `plugins/swift/skills/review/SKILL.md` |
| Generated platform table | `plugins/swift/skills/swiftui/references/platform-availability.md` |
| Upstream baselines, Deviations, Ported, Findings (one section per upstream) | `UPSTREAM.md` |
| License (MIT), one copy at the root and one in the shipped folder | `LICENSE.md`, `plugins/swift/LICENSE.md` |
| Third-party notices | `plugins/swift/NOTICE.md` |
| API checker CLI | `maintenance/check-apis.py` → `maintenance/apicheck/cli.py` |
| API manifest: frameworks, claims, ignore list | `maintenance/apis.json` |
| Upstream diff | `maintenance/upstream-diff.sh` |
| Unit tests | `maintenance/tests/` |
| `swift:review` verification fixtures, answer key, scorer | `maintenance/review-fixtures/` |
| `swift:review` verification record (dated, frozen sections) | `docs/internals/review-verification.md` |
| Eval suite | `plugins/swift/evals/` |
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
| `changelog-release` | Cut a release: bump `plugins/swift/.claude-plugin/plugin.json`, write `CHANGELOG.md`; stages, never commits |
| `update-docs` | Bring docs back in line with the code after a change |
| `update-rules` | Re-ground the claims inside `.claude/rules/` and `.claude/skills/` |

The plugin's own skills live in `plugins/swift/skills/`, not in `.claude/skills/`.

## 4. Project constraints
- Docs describe implemented state.
- `docs/archive/**` is frozen — never edited.
- A stale pointer is worse than no pointer: moving or renaming a **doc, rule or
  skill** means fixing its row above in the same change. Nothing fails a build when
  these tables drift.
- Names are fixed: marketplace `jack1913-plugins` (named `swift-plugin` before 0.2.0; ADR-0012), plugin `swift`, skills `swift:swiftui`, `swift:design`, `swift:concurrency`, `swift:testing` and `swift:review`; the example-app layer depends on the first two (spec §1 goal 2; ExampleApp companion spec named in the spec header; part-2 spec §2).
- A change under a forked skill (`plugins/swift/skills/swiftui/`, `plugins/swift/skills/concurrency/`, `plugins/swift/skills/testing/`) is its own commit, with its `UPSTREAM.md` → Deviations row — in that upstream's section — in that commit (spec §4; part-2 spec §3). This applies while writing, when no `paths:` rule has loaded.
- Never hand-edit the block between the `BEGIN GENERATED` / `END GENERATED` markers in `platform-availability.md`; run `python3 maintenance/check-apis.py --write-table`.
- New code in `maintenance/apicheck/` or `maintenance/check-apis.py` stays standard-library-only, including while a file is being created (`.claude/rules/apicheck-stdlib-only.md` only loads on read); see `docs/internals/agent-instructions.md`.
- Release through `changelog-release`, then `claude plugin tag plugins/swift`; see `docs/manual/work-on-it.md#release`.

## 5. Documentation map
`docs/manual/` (consumer) · `docs/internals/` (technical) · `docs/adr/` (decisions) · `docs/archive/` (frozen).
