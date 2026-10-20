# ADR-0001: New decisions are ADRs; the decisions log is archived

- **Status:** accepted
- **Date:** 2026-10-19
- **Source:** the docs restructure of this plugin that follows [ADR-0003 of the marketplace](../../../../docs/adr/ADR-0003-one-docs-standard.md) and the [docs standard](../../../../docs/internals/docs-standard.md); the old log is [decisions-log.md](../archive/decisions-log.md)

## Context

Until now brand-creator recorded decisions as numbered entries in one long file, `dev/DECISIONS-LOG.md`, grouped by
build stage. It was written while 0.1.0 was built and runs to well over a thousand lines. Finding the reason for one
choice meant searching the whole file, and nothing marked an entry as superseded.

## Decision

From this change on, each new decision is one ADR in this folder, from [ADR-TEMPLATE.md](ADR-TEMPLATE.md), listed in
the [README](README.md). The decisions log is moved to [`docs/archive/decisions-log.md`](../archive/decisions-log.md)
and is frozen: it is not edited again. It keeps its numbers, so a comment or a changelog line that cites "decision 804"
still points at the right entry.

## Consequences

- A reader finds a decision by its title in one list.
- An old decision that is still in force is not copied into an ADR. A later ADR may cite the log entry it builds on.
- The tracked files of `dev/` moved: the build and decisions logs to `docs/archive/`, the manual checks to
  `docs/internals/manual-checks.md`, and `trigger-evals.json` to `evals/`.
