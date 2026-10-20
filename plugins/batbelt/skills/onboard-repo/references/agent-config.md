# Provision agent configuration

Section 3.4 of [SKILL.md](../SKILL.md), moved here; only citations of another repository's ADRs were dropped. SKILL.md sends you here at that step.

## 3.4 Provision agent configuration (report-first, create-only-missing)

Skills tell an agent what it *can* do; this section decides what it may **run**,
and what the repo keeps out of git. Both are the repo's own committed files.

### `.claude/settings.json`

Propose a permissions block from the detected ecosystems — the verb reads nothing
and writes nothing, so it is safe to run before the operator confirms:

```bash
python3 "$SKILL_DIR/scripts/onboard.py" settings-plan . --ecosystem <names>
python3 "$SKILL_DIR/scripts/onboard.py" settings-plan . --ecosystem <names> --explain
```

Omit `--ecosystem` to let it detect. With no supported ecosystem it still emits the
baseline (git and credential guards), because those are worth having regardless.

**Show the `--explain` output to the operator before asking for confirmation.** It
prints what an `ask` rule costs, then every proposed `ask`/`deny` rule with one
line on why it is there. The cost is the point: an `ask` rule is a **human-only
prompt** — it fires in every permission mode, and under auto mode the classifier
cannot clear it, so the operator clicks or the turn stops. Every rule in that tier
trades a prompt for a guard, and the planner only proposes rules whose action is
rare and expensive to get wrong (a dependency added, a schema migrated, a tracked
file removed). A rule that would fire on the hot path of ordinary work is the wrong
tier however good its intent.

**On a js/ts repo, ask one extra question: gate `npx` too?** Default **no**.
`npx:*` used to be proposed unconditionally and was the textbook hot-path rule:
`npx` is how `tsc`, `vitest`, `prettier` and `markdownlint` run, so it prompted on
every lint and test loop. What it guards — `npx <package>` fetching and executing an
arbitrary registry package — is a real supply-chain posture some teams want, so it
stays available as an **opt-in**: pass `--ask-npx` only when the operator says yes,
and say plainly that it will prompt on every `npx` invocation. Non-interactive runs
leave it out.

Invariants the planner enforces — do not hand-edit them back out:

- **Build, test and lint allows are exact commands, never a wildcard tail.** A tail
  lets an agent append any flag, and these runners take flags that run a program or
  load code (`npm --script-shell`, `cargo --config target.<triple>.runner`,
  `dotnet -p:PreBuildEvent`, `mypy --python-executable`, `git fetch --upload-pack`),
  which turns the rule into an unprompted shell grant. A run with extra flags prompts.
  `settings-audit` reports a wildcard on these commands under `broad_allows`.
- **No `Bash(<read-only git>)` allow entries.** Claude Code already runs `git log`,
  `git show`, `git status` and friends unprompted via a built-in read-only set, so
  such an entry allows something that never prompts.
- **`PowerShell(<read-only git>)` entries are kept.** That tool has no equivalent
  carve-out and genuinely needs them.
- **Every `ask`/`deny` appears in both `Bash(...)` and `PowerShell(...)` forms**,
  because permission rules are matched per tool — `Bash(git reset:*)` does not block
  `PowerShell(git reset …)`.
- **Credential paths are `ask`, never `deny`, and are one wildcard rather than a
  list.** Both halves are load-bearing and they depend on each other. Environment
  names are an open set, so an enumeration leaks (`.env.uat`, `.env.preview`); but
  gitignore patterns carry no negation, so a wildcard in `deny` would permanently
  wall off `.env.example`, the committed template an agent reads to document setup.
  `ask` also keeps a *shared* project file from overriding the operator's own
  choice — `deny` outranks `ask` across settings scopes, so a project deny silently
  converts their global "ask me" into "never", with no prompt to override.

- **No deny `Read()`/`Edit()` rule anchors inside the repo.** A rule written
  `**/x`, `x`, `./x` or `/x` has its static prefix in the working directory. On
  Claude Code 2.1.259 that made every path-less `rg`, `grep -r`, `git`, `cp` or
  `mv` there a human-only prompt, because each counts as a read of the directory
  it scans. 2.1.260 reverted that check, so the prompt is gone — but `//**/x`
  stays the correct form: it protects the same files plus every path outside the
  repo, and it is immune if the check returns. The planner's credential rules
  are `ask` (not consulted by that guard); anything it ever puts in `deny` is a
  shell rule.

**If `.claude/settings.json` already exists, never `Write` over it.** Audit it
first — the verb reads only and exits `1` when a deny `Read()` rule anchors inside
the repo (with `dead_home_denies` and `broad_allows` reported alongside):

```bash
python3 "$SKILL_DIR/scripts/onboard.py" settings-audit .claude/settings.json
```

A repo onboarded with the old enumerated credential denies carries them and
fails this. Offer the migration: it re-anchors every inside-repo deny rule at
`//**/<path>` — the same files under this repo *and* everywhere else, a strict
superset, so nothing is less protected — keeps the tier, touches nothing else, and
is a dry run until `--apply`, which backs the file up under
`.onboard-repo-retired/<stamp>/` first:

```bash
python3 "$SKILL_DIR/scripts/onboard.py" settings-migrate .claude/settings.json                       # dry run: the rewrites
python3 "$SKILL_DIR/scripts/onboard.py" settings-migrate .claude/settings.json --apply --stamp <stamp>
```

Moving a credential rule from `deny` to `ask` (the tier the planner now uses) is a policy
change, not a migration: re-run `settings-plan` and merge on confirm. Then show
the proposed block as a `diff` against the current file, merge additively on
confirm, and leave any key the operator already set alone. The repo's file is
not the operator's global `~/.claude/settings.json`; do not reconcile the two.

### `.gitignore`

`settings.local.json` is per-developer and must not be committed:

```bash
python3 "$SKILL_DIR/scripts/onboard.py" gitignore-ensure .gitignore \
  '.claude/settings.local.json' '.onboard-repo-retired/' > <tmp> && mv <tmp> .gitignore
```

Capture-then-`mv`, never redirect onto the same path. The verb is idempotent, so
re-running it on an already-correct file is a no-op.

If the file is **already tracked**, ignoring it changes nothing on its own. Print
the untrack command for the **operator** to run — onboard-repo carries no
git-mutation grant, the same reason rollback is operator-run:

> `git rm --cached .claude/settings.local.json`

### `.claude/rules/`

Create the directory if absent and copy `templates/docs-ia/rules-EXAMPLE.md` into it
as `.claude/rules/EXAMPLE.md` — a commented skeleton carrying the four tests a rule
must pass (mandatory `paths:`, declarative not procedural, expensive to violate,
every claim re-derivable) and the Read-not-Write trap. Its own `paths:` is a
placeholder glob, so it matches nothing and costs no context until it is filled in;
tell the operator to delete it once a real rule exists.

**Do not author repo-specific rules here.** A grounded rule needs measured counts
and verified symbols that only a reader of this codebase can supply, and an
invented one is worse than none. Scaffold the mechanism, point at
`docs/internals/agent-instructions.md` for the decision rule, and leave the
content to the operator — or to §3.4c, the **one** authoring path:
mined candidates, three validation passes, operator confirmation. The stamped
`update-rules` skill keeps the full ban: it repairs the claims inside rules that
exist and reports a convention that lacks one, but it never writes the rule.

### Ground whatever instruction files already exist

A repo being onboarded often arrives with rules and skills of its own, and those are
exactly where stale claims hide. Run the grounding pass **once here**, before the
docs work, so a broken citation is reported while the operator is still looking at
their instruction files:

```bash
python3 "$SKILL_DIR/scripts/check.py" check-instructions .claude/rules .claude/skills \
  --repo-root . --repo-root <source-root-if-any>
```

Skip it when both directories are empty or absent — a freshly scaffolded repo has
nothing to ground, and a clean run there proves nothing. Report the findings with
the §6 severity split (errors are real, counts are advisory); **do not fix them
here**. On a repo with many rules/skills this is one of the two passes §0.2 says to
**fan out** — shard the files, each worker returning findings only, never file bodies. Editing a repo's existing rules is outside what onboarding was asked to do,
and a count is not wrong merely because no command sits next to it. The stamped
**`update-rules`** skill owns that repair loop from here on — name it in the report, so
the operator sees the findings have a home rather than a dead end.

The pass answers three questions, in order of how expensive a "no" is:

| Code                  | Sev   | Question |
| --------------------- | ----- | -------- |
| `INVALID_FRONTMATTER` | error | Does the file **load at all**? |
| `DEAD_GLOB`           | error | Can it ever **fire**? |
| `UNDEFINED_SCRIPT`    | error | Does a command it tells you to run **exist**? |
| `UNRESOLVED_CITATION` | error | Does a path it points at exist? |
| `MISSING_PATHS`       | warn  | Is it unscoped — loading every session? |
| `UNGROUNDED_COUNT`    | warn  | Is a number re-derivable? |

`INVALID_FRONTMATTER` leads because it is the quietest failure in the set: a rule
whose YAML does not parse is simply absent, with no error surfaced anywhere, and
every other check passes it clean because there is nothing left to check. The
usual cause is an unquoted value containing a colon-space
(`description: Observers: side-effect containers`), which YAML reads as a nested
mapping — one migration lost 17 of 21 rules to exactly that.

`MISSING_PATHS` stays advisory: a rule about *when* to reach for a tool has no file
shape to scope to, so always-on is sometimes correct.
