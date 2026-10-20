# onboard-repo: agent configuration

How onboard-repo provisions a repository's own agent setup. The steps are in [agent-config.md](../../skills/onboard-repo/references/agent-config.md). Back to [onboard-repo](onboard-repo.md).

## Permissions in `.claude/settings.json`

- `settings-plan` proposes a permissions block from the detected ecosystems. It writes nothing, so it is safe to run before you confirm.
- An existing file is diffed and merged additively. It is never overwritten.
- `--explain` shows what an `ask` rule costs: a human-only prompt that the auto-mode classifier cannot clear. It also gives one reason for each proposed `ask` or `deny` rule, taken from `_RULE_REASONS`. A test requires that table to cover every rule the planner can emit.
- `npx:*` is opt-in through `--ask-npx`. It is never proposed by default, because it fires on every Node lint and test run. The reasoning is in [the npx question](../../skills/onboard-repo/references/agent-config.md).

## Credential paths

- Credential paths are a single `**/.env*` in `ask`, never a list in `deny`.
- Environment names are an open set, so a list cannot stay ahead of them.
- Gitignore patterns have no negation, so a wildcard in `deny` would wall off `.env.example` for good.
- The full invariants are in [agent-config.md](../../skills/onboard-repo/references/agent-config.md).

## Auditing an already-onboarded file

- `settings-audit` is read-only and exits `1` on a defect.
- It names deny `Read()` rules anchored inside the repository. On Claude Code 2.1.259 every path-less `rg` there was a human-only prompt.
- It also names home-directory globs that cover nothing in project scope, and allow shapes that `test_payload.py` refuses.
- `settings-migrate --apply --stamp S` re-anchors those deny rules at `//**/<path>`. That is a strict superset of what they covered, the tier is kept, and a backup goes under `.onboard-repo-retired/<stamp>/`.
- `--check` runs the audit and `--sync` offers the migration. A repository onboarded with the older credential rules is the usual case.

## Rules and the ban on authoring them

- onboard-repo scaffolds `.claude/rules/EXAMPLE.md` from `templates/docs-ia/rules-EXAMPLE.md`.
- It does not write repo-specific rules on its own. A real rule needs measured counts and verified symbols that only a reader of the codebase can supply.
- The one exception is rule mining, below.

## Rule mining

- When `.claude/rules/` holds only `EXAMPLE.md`, the skill offers to mine the codebase for rule candidates. It never runs unasked.
- Workers split by subsystem and return candidates only.
- Each survivor passes three checks. A mechanical check re-runs every count and resolves every symbol and glob. A truth verifier tries to refute the rule by sampling real sites. A worth verifier asks whether a linter or test already covers it, and whether the rule is procedural, too broad or not worth its per-read cost.
- Both verifiers must pass. The loop is bounded at two rounds, and a candidate that does not converge is dropped to the report, never written to disk.
- You confirm the list of evidence and verdicts before anything is written, and `check-instructions` must come back clean on the new files.
- `--no-review` turns the pass off, because validation cannot be separated from it.
- The procedure is in [rule-mining.md](../../skills/onboard-repo/references/rule-mining.md).

## Grounding existing instruction files

- `check-instructions` runs read-only once during onboarding, before the docs work, and again under `--check`.
- It is skipped when both `.claude/rules` and `.claude/skills` are empty or absent.
- It has six finding codes. Four are errors: `INVALID_FRONTMATTER`, `DEAD_GLOB`, `UNDEFINED_SCRIPT` and `UNRESOLVED_CITATION`. Two are warnings: `MISSING_PATHS` and `UNGROUNDED_COUNT`.
- `--repo-root` is repeatable, so a file that cites against both a repository root and a source root resolves under either.
- `UNDEFINED_SCRIPT` covers `composer run` as well as `npm run`, each against its own manifest. A runner whose manifest is absent is skipped.

## The Copilot port

- `convert-copilot` ports `.github/instructions/*.instructions.md` to `.claude/rules/`. `applyTo:` becomes `paths:`.
- It ports `.github/prompts/*.prompt.md` to `.claude/skills/<name>/SKILL.md`. `${input:Name}` becomes `$Name`.
- It is offered and confirmed, never run unasked.
- Converted text goes to stdout and notes go to stderr.
- A placeholder glued to an identifier character, such as `${input:Name}Props`, is left alone and reported rather than silently renamed.
