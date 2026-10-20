# onboard-repo

[`skills/onboard-repo/SKILL.md`](../../skills/onboard-repo/SKILL.md) is a scaffolder that sets up the repository you run it in. The long sections of its procedure live in [`references/`](../../skills/onboard-repo/references/_index.md).

Related pages: [agent configuration](onboard-repo-agent-config.md) and [docs and gates](onboard-repo-docs.md).

## What it does

- It copies `changelog-release`, `update-docs` and `update-rules` into the current repository's `.claude/skills/`.
- It also copies `update-deps`, but only after asking.
- It provisions the repository's agent configuration.
- It grounds the instruction files the repository already has.
- It offers to port a repository that is moving off GitHub Copilot.
- It scaffolds or adopts the four docs tiers (`docs/manual`, `docs/internals`, `docs/adr`, `docs/archive`) and an `AGENTS.md` index.
- It writes a consumer manual under `docs/manual/` (`getting-started/`, `use/` and `reference/`), shaped by the page templates in `references/manual-page-how-to.md` and `references/manual-page-reference.md`.
- It stamps the docs standard to `docs/internals/docs-standard.md` from `templates/docs-ia/internals-docs-standard.md`, and lists it in the internals README and the `AGENTS.md` pointer index. The standard is create-only-missing, like the other docs seeds.
- The provenance header of a stamped skill says `from batbelt`. The parser also accepts `from claude-configs`, so repositories stamped earlier still sync. `TEMPLATE_VERSION` is 4.

## It runs only when typed

- The skill sets `disable-model-invocation: true`, so it never starts on its own.
- Run it with `/batbelt:onboard-repo`.

## The stamped skills

- The stamped skills live under `skills/onboard-repo/templates/`.
- Claude Code scans skills one level deep, so a nested `templates/<name>/SKILL.md` is invisible until it is stamped out.
- Each stamped copy is self-contained. A collaborator without batbelt still gets the skills from the checkout.
- The set is pinned to `CANONICAL` in `onboard_lib.py`.
- `find_predecessors` uses `CANONICAL` to skip skills that are already stamped. A name missing there makes onboarding report a canonical skill as a predecessor to retire.
- Each stamped skill has a template region and a REPO SPECIFICS block. See [stamping.md](../../skills/onboard-repo/references/stamping.md).

## The gate script

- `update-docs` and `update-rules` each get a `scripts/check.py`, a plain copy of `onboard-repo/scripts/check.py`.
- Their gates, `check-docs` and `check-instructions`, then run in the onboarded repository.
- The file is wholly template-owned and has no REPO SPECIFICS.
- `--sync` replaces it outright and `--check` reports drift as a plain `diff`. It never uses `preserve`, which would fail closed on the missing markers.
- `check.py` uses only the standard library and imports no sibling file. That is what makes a single-file copy sound.
- Two tests pin both properties.
- The cost is one copy of the file per consuming skill.

## The one-shot scripts

- `onboard.py` and `onboard_lib.py` are never stamped.
- They hold the one-shot verbs: `preserve`, `check-markers`, `settings-plan`, `settings-audit`, `settings-migrate`, `gitignore-ensure`, `deps-detect`, `convert-copilot` and the `run-*` verbs.
- A skill that runs for years must not ship them.
- `onboard.py` still answers the three standing-gate verbs by delegating to `check.py`, so an older `onboard.py check-docs` call keeps working.
- `--sync` migrates a repository stamped before the split. It writes `check.py` and removes the two orphans, and shows both in the plan. See [the sync section](../../skills/onboard-repo/SKILL.md#5---sync-preserve-repo-specifics-fail-closed).
- The standing gates `check-docs`, `check-instructions` and `redact` live in `check.py`. Everything else is in `onboard.py` and `onboard_lib.py`.

## update-deps is always asked about

- It is the one stamped skill that changes manifests and lockfiles.
- Every default run asks once, and the default answer is no.
- The question is skipped when `deps-detect` finds no supported ecosystem (JS/TS, PHP, Python, Rust, Swift, .NET). The run reports the skip instead of stamping a skill that does nothing.
- `--with update-deps` and `--without update-deps` pre-answer it.
- A run with no terminal and neither flag declines.

## update-rules owns the agent instructions

- `.claude/rules/` and `.claude/skills/` are a separate surface from docs, with their own owner, the same way `changelog-release` owns `CHANGELOG.md`.
- It runs `check-instructions` from its own stamped `scripts/` folder.
- It fixes only what it can derive: it quotes an unparsed `description` (`INVALID_FRONTMATTER`) and re-derives a drifted count (`UNGROUNDED_COUNT`).
- It reports `DEAD_GLOB`, `UNRESOLVED_CITATION`, `UNDEFINED_SCRIPT` and `MISSING_PATHS`. Choosing what a broken citation meant is a guess, and a rule that points confidently at the wrong file is worse than one that visibly dangles.
- It never writes a rule. A convention that looks important but is not enforced is a finding handed to a person.
- It is expected to reject most candidates. Anything a linter, the compiler or a test already catches must not become a rule, because a rule costs context on every matching read.
- `INVALID_FRONTMATTER` is fixed first. An unparsed rule is an absent rule: every other check passes it clean, so its other findings appear only once it parses.

## Modes

Every mode shows its plan and confirms before it writes.

- **default** is the full pass described above.
- **`--sync`** re-stamps only the template region of stamped skills and preserves each file's REPO SPECIFICS block. It backs up and shows a diff first, and fails closed on malformed markers. It also adds a missing `docs/internals/docs-standard.md`.
- **`--check`** reports an unfinished run, template drift, marker failures, agent-config drift, instruction-file findings and docs drift, without writing. An unfinished run is the most useful thing it can report.
- **`--resume`** continues from the run record. It re-runs no confirmed phase and re-asks no answered question.
- **`--unattended`** runs the capture commands directly once the list is confirmed.
- **`--no-review`** skips the reviewer passes and turns rule mining off.

`--unattended` runs only commands on the confirmed list. A command found mid-run needs its own confirmation. You still review every redacted capture before committing. `redact` strips only the tokens it is given, and is not a secret scanner.

Creating a `.claude/skills/` folder that did not exist at session start needs a restart (`claude --continue`) before Claude watches the new skills. That is a Claude Code limitation, and the skill's last message says so.

## The run record

- A brownfield pass can take hours and several sessions, so every confirmation is saved.
- `run-init`, `run-status`, `run-next` and `run-set` write the phase, your confirmations and one item per unit of work to `.onboard-repo-retired/<stamp>/run.json`.
- That folder is gitignored, because the record holds confirmed plans.
- `run-set --add` is idempotent. Re-running detection after Claude's context is compacted cannot reset a surface that is already `done`.
- A record that does not parse fails closed with `RUN STATE ERROR` (exit 2) and is never replaced. Minting a new one would discard the confirmations it protects.
- Like every verb, the run verbs write to stdout only. Capture the output, then `mv` it into place. See [the run state section](../../skills/onboard-repo/SKILL.md#01-durable-run-state-do-this-first-always).

## Fan-out

- The read-heavy passes are delegated to workers: rubric classification, instruction grounding, rule mining and its verification, capture reading and draft research, and ADR mining.
- Workers return verdicts or candidates, never file bodies.
- Use a `Workflow` with `pipeline()` when available. Otherwise use at most 8 `Agent` calls with briefs that do not overlap.
- Detection, the plan, every confirmation and every write stay in the main thread. The link-fixing order in the adopt step is load-bearing.
- The reviewer stays exactly one agent.
- `allowed-tools` lists `Agent` and `Workflow`. `Task` stays as a live alias.
- The full policy is in [the fan-out section](../../skills/onboard-repo/SKILL.md#02-fan-out-policy--delegate-the-read-heavy-passes-never-the-writes).
