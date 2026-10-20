# AGENTS.md — <repo> (single source of truth)

## 1. Project identity
{{TODO: one-line: what this repo is}}

## 2. Repo layout
| Path | Purpose |
| --- | --- |
| `docs/manual/` | Consumer documentation — task-first, one task per page |
| `docs/internals/` | Technical mechanics — contributors only |
| `docs/adr/` | Architecture Decision Records |
| `docs/archive/` | Frozen point-in-time records |
| `.claude/rules/` | Path-scoped constraints, auto-loaded when a matching file is read |
| `.claude/skills/` | Invoked procedures and reference packs |

## 3. Pointer index (source-of-truth → path)
| What | Where |
| --- | --- |
| {{TODO: cite-or-defer real file/symbol pointers}} | |
| How docs are written and where they live (page kinds, voice, changelog, ADR rules) | `docs/internals/docs-standard.md` |
| Agent instruction layout, rule-vs-skill decision rule | `docs/internals/agent-instructions.md` |

### Auto-loaded rules
Each loads only when Claude reads a file matching its `paths:` frontmatter, so an
unscoped rule taxes every session. Keep this table in step with `.claude/rules/`.

| When you need... | Where to look |
| --- | --- |
| {{TODO: one row per rule, with its `paths:` scope}} | |

### Skills
Invoked with the `Skill` tool, or by name. A skill's body costs nothing until it is
invoked, so reference material belongs here rather than in a rule.

| Skill | When to use |
| --- | --- |
| {{TODO: one row per skill in `.claude/skills/`}} | |

## 4. Project constraints
- Docs describe implemented state.
- `docs/archive/**` is frozen — never edited.
- A stale pointer is worse than no pointer: moving or renaming a **doc, rule or
  skill** means fixing its row above in the same change. Nothing fails a build when
  these tables drift.

## 5. Documentation map
`docs/manual/` (consumer) · `docs/internals/` (technical) · `docs/adr/` (decisions) · `docs/archive/` (frozen).
