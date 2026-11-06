# ADR-0013: Old rounds leave through `brand-creator cleanup`

- **Status:** accepted
- **Date:** 2026-11-05
- **Source:** "Cleanup" in the [script contract](../../scripts/CONTRACT.md) (the rules, the order of refusals, the plan hash, the stated
  limits); "Hook guard" in the same contract; the [history phase](../../skills/brand-creator/references/phases/12-history.md) ("Method:
  cleaning old rounds"); the [changelog](../../CHANGELOG.md); a client project whose old rounds piled up and whose first answer was a
  line the owner had to type.

## Context

Rounds pile up in `rounds/`. Before a project is pushed to a shared repository, the owner wants the old ones gone. The guard stops
the agent from deleting in a brand project, because a round may hold work that is not committed and the guard cannot see the file
list. So the first answer was a procedure that ended in a line the owner typed, and that line, a `git rm` by a list of files,
failed in the owner's shell.

Removing a round is also not harmless in itself. A kept page can point at a file in an old round, the lint of a kept board reads
earlier rounds (the first motion board, the first board of a site stage, the references board, the hero board), and a decision
record may name a round.

## Decision

- **A command removes whole round folders, after a recorded yes tied to the exact plan.** `brand-creator cleanup` shows a plan
  first (a dry run is the default), the owner says yes, `--record-yes` writes it into `DECISIONS.md` with the plan hash, and `--yes`
  runs `git rm` itself. A plan that changed since the yes needs a new yes; each recorded yes is used once.
- **Only committed, unchanged files go, and only through git.** It refuses while any file of a round to remove is modified,
  staged, deleted, untracked, ignored (but for `.DS_Store`) or hidden from `git status`, or a round holds a link, a special file or
  a nested repository. The removal is staged and never committed, and the record names the line that restores it.
- **What stays is decided by rules, and the rules are the risky part.** The latest round of each stage and the latest pick board, any
  round something kept refers to (text, URLs, links, report inputs, state keys), every earlier round the lint of a kept board
  reads, every round it cannot place, and any `--keep`. A check computes board-lint's questions again on the kept rounds and stops
  the run when an answer would change.
- **The only thing outside `rounds/` it removes** is the `assets/_checks` report whose subject is in a removed round.
- **The guard does not change.** It does not inspect `brand-creator` commands, so the command runs; every git deletion form and
  every `xargs` deleter stays blocked for the agent.
- Rejected: the owner's `!` line (it failed in the owner's shell, and the agent cannot see what it removes); removing files inside
  rounds (a kept round must stay whole); moving rounds to `removed-<date>/` (it keeps the bytes, so it fixes nothing for a shared
  repository).

## Consequences

- The command was not run against a real brand project. A reference it does not read (a path a script builds from parts, one inside
  a binary file, one outside the project that nothing lists) lets a round that is still used be proposed for removal. Git keeps it
  recoverable, but the break may go unnoticed until the page or the book is opened. The owner compares the dry run with what they
  would keep by hand before the first real run.
- The recorded yes ties a plan to a decision entry; it cannot prove who wrote the entry. What makes a wrong run harmless is that only
  committed, unchanged files go, the removal is staged, and the undo is one line.
- Recording the yes touches `DECISIONS.md`, which the lint of a pages board reads, so a `check --refresh` follows the removal.
- Not built: `--json`, an undo command, a `check` row about the size of `rounds/`.
