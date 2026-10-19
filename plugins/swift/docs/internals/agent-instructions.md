# Agent Instruction Layout

How this repo organizes instructions for coding agents, and why.

## Layout

| File | Loads | Contains |
| --- | --- | --- |
| `.claude/CLAUDE.md` | every session | Thin bridge: `@../AGENTS.md` import, plus anything Claude-specific. It lives in `.claude/` because a `CLAUDE.md` at the plugin root makes `claude plugin validate --strict` fail |
| `AGENTS.md` | every session (via the import) | Single source of truth; pointer index to every doc, rule and skill |
| `.claude/rules/*.md` | only when a matching file is **read** | Path-scoped constraints |
| `.claude/skills/*/SKILL.md` | description every request; body only when invoked | Procedures and reference packs |
| `.claude/settings.json` | every session (as configuration, not context) | Permissions: what runs unprompted, what asks, what is denied |
| `docs/internals/*` | on demand | Mechanics and reference, found via the AGENTS.md pointer index |

## Rule, skill, or doc — the decision rule

The split is by **load timing**, not by content type. Both mechanisms are official
and documented; skills also accept `paths:`, so path-scoping does not distinguish
them.

Ask, in order:

1. **Must it hold whenever an agent touches a file of a given shape, whether or not
   anyone asked?** → a **rule**, and it must carry `paths:`. Declarative only
   ("always X / never Y"), never a numbered procedure. It is paid on every matching
   read, so it earns its place only by being a constraint that is expensive to
   violate.
2. **Is it a procedure to run, or a body of reference to consult, for one task?** →
   a **skill**. Its body costs nothing until invoked, so length is cheap here in a
   way it is not in a rule. Keep `SKILL.md` under 500 lines and split bulk reference
   into sibling files.
3. **Otherwise** → a **doc**, reachable through one row of the AGENTS.md pointer
   index.

Two things that are easy to get backwards:

- **Reference material belongs in a skill, not a rule.** Conventions, patterns and
  domain knowledge are a sanctioned skill type. Moving a reference pack into a rule
  converts free-until-invoked content into a per-read tax.
- **`paths:` fires on Read, never on Write.** Authoring a brand-new file loads no
  rule, because nothing matching was read. A constraint that must hold while
  *creating* a file therefore also needs a line in `CLAUDE.md` — the one sanctioned
  duplication, kept to a one-line summary that points at the owning rule.

**One fact, one home.** If a fact already has an owner, another file may point at it
but must not restate it. Contradictions between a rule and a skill are how an agent
ends up picking arbitrarily between two answers.

## Grounding

Every count, symbol and `file:line` in a rule or skill is a claim that rots. Counts
drift with every merge; a cited symbol can be renamed out from under the file. Two
habits keep this honest:

- Write claims so they can be re-derived — state the command, or make the claim
  countable by an obvious one.
- Re-check them periodically. `onboard-repo --check` runs the mechanical pass.

## Permissions: why the Bash and PowerShell lists differ

`.claude/settings.json` deliberately allows fewer `Bash(git …)` entries than
`PowerShell(git …)`. Do not "fix" the asymmetry by padding the Bash list.

Claude Code recognises a **built-in set of read-only Bash commands** and runs them
with no prompt in every mode — `ls`, `cat`, `grep`, `find`, `head`, `tail`, `wc`,
`diff`, `stat` and the **read-only forms of `git`**. That set is not configurable,
so `Bash(git log:*)` and friends are dead weight. Only genuinely mutating or
networked git commands earn a Bash entry.

The `PowerShell` tool has no equivalent carve-out, so its read-only git commands
**do** need explicit allow entries. Hence the longer list.

Permission rules are matched **per tool**: `Bash(git reset:*)` does **not** block
`PowerShell(git reset …)`. Every `deny` and `ask` entry therefore needs both forms.
This matters even on an all-macOS team, because the PowerShell tool is auto-enabled
on Windows without Git Bash and is on a progressive rollout elsewhere — you cannot
predict which teammate has it.

## See also

- `docs/internals/README.md` — internals index
