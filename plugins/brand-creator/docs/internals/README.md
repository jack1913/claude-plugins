# brand-creator internals

Notes for people who change brand-creator. For using it, read the [manual](../manual/README.md).

| Page | What it covers |
| --- | --- |
| [development.md](development.md) | Load a checkout, run the tests, what CI runs, validate |
| [evals.md](evals.md) | Run the billed behaviour and trigger evals, and what they show |
| [manual-checks.md](manual-checks.md) | Checks no suite can do, and when each was last run |

## Where things are

Paths are from `plugins/brand-creator/`.

| What | Where |
| --- | --- |
| The script contract: entry point, reports, exit codes, every tool's rules | [`scripts/CONTRACT.md`](../../scripts/CONTRACT.md) |
| Decision records | [`docs/adr/`](../adr/README.md) |
| Frozen build history | [`docs/archive/`](../archive/README.md) |
| Skills, and the phase files they read | `skills/`, `skills/brand-creator/references/phases/` |
| Files copied into brand projects (do not edit them as docs) | `templates/` |

The script contract stays in `scripts/` because the skills, tests and scripts read it by that path.

## Ground rules

- Docs for users go in [`../manual/`](../manual/README.md). Docs for contributors go here.
- The rules for every page are in the marketplace [docs standard](../../../../docs/internals/docs-standard.md).
