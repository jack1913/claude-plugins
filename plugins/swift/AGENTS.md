# AGENTS.md — swift-plugin (single source of truth)

## 1. Project identity
A private Claude Code plugin marketplace with one plugin, `swift`, whose skills (`swift:swiftui`, `swift:design`) make an agent write correct, current, Apple-native SwiftUI. Design: `docs/superpowers/specs/2026-09-24-swift-plugin-design.md`.

## 2. Repo layout
| Path | Purpose |
| --- | --- |
| `plugins/swift/` | The only directory an install copies: manifest, skills, NOTICE, eval suite |
| `maintenance/` | Never shipped: API checker, upstream diff, unit tests |
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
| Generated platform table | `plugins/swift/skills/swiftui/references/platform-availability.md` |
| Upstream baseline, Deviations, Ported, Findings | `UPSTREAM.md` |
| Third-party notices | `plugins/swift/NOTICE.md` |
| API checker CLI | `maintenance/check-apis.py` → `maintenance/apicheck/cli.py` |
| API manifest: frameworks, claims, ignore list | `maintenance/apis.json` |
| Upstream diff | `maintenance/upstream-diff.sh` |
| Unit tests | `maintenance/tests/` |
| Eval suite | `plugins/swift/evals/` |
| Design spec | `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-24-swift-plugin.md` |
| Operator manual | `docs/manual/README.md` |
| Changelog | `CHANGELOG.md` |

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

| Agent instruction layout, rule-vs-skill decision rule | `docs/internals/agent-instructions.md` |

## 4. Project constraints
- Docs describe implemented state.
- `docs/archive/**` is frozen — never edited.
- A stale pointer is worse than no pointer: moving or renaming a **doc, rule or
  skill** means fixing its row above in the same change. Nothing fails a build when
  these tables drift.
- Names are fixed: marketplace `swift-plugin`, plugin `swift`, skills `swift:swiftui` and `swift:design`; the example-app layer depends on them (spec §1 goal 2; ExampleApp companion spec named in the spec header).
- A change under `plugins/swift/skills/swiftui/` is its own commit, with its `UPSTREAM.md` → Deviations row in that commit (spec §4). This applies while writing, when no `paths:` rule has loaded.
- Never hand-edit the block between the `BEGIN GENERATED` / `END GENERATED` markers in `platform-availability.md`; run `python3 maintenance/check-apis.py --write-table`.
- Release through `changelog-release`, then `claude plugin tag plugins/swift`; see `docs/manual/work-on-it.md#release`.

## 5. Documentation map
`docs/manual/` (consumer) · `docs/internals/` (technical) · `docs/adr/` (decisions) · `docs/archive/` (frozen).
