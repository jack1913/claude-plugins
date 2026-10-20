# onboard-repo: docs and gates

How onboard-repo sets up a repository's docs and checks them. The steps are in [adopt-docs.md](../../skills/onboard-repo/references/adopt-docs.md), [author-manual.md](../../skills/onboard-repo/references/author-manual.md) and [adr-mining.md](../../skills/onboard-repo/references/adr-mining.md). Back to [onboard-repo](onboard-repo.md).

## Authoring is bounded per surface

- Each surface of the repository that users touch gets one manual page.
- The authoring loop has a round budget for each surface, not for the whole tree.
- A surface that will not converge is parked, with its reason, and recorded as `deferred`. The run carries on.
- One page that needs infrastructure you lack no longer throws away the pages that already converged.
- `run-status` names every parked item, and `--check` flags it again as `EMPTY_TIER`.

## `check-docs --only`

- `check-docs --only PATH` limits which files report findings. It still walks the full roots.
- `--no-tier-check` drops the tree-wide `EMPTY_TIER` sweep while pages are being written.
- The per-page loop passes the full roots plus `--only`, never a single-file root. A single-file root would downgrade a real `BROKEN_LINK` to a warning and exit 0 on a broken page.
- The run ends with one unscoped pass, so the tree-wide checks finally speak.

## What `check-docs` adds

- `CAPTURES_NOT_CHECKED` is an error. It means `--captures` was left out, so a `capture=` block went unverified. Fix the command, not the page.
- Warnings cover what grounding cannot see:
  - `NO_SHOWCASE`: a `docs/manual/` page with commands and no output.
  - `LEAKED_PATH`: an absolute home path in a committed doc. Placeholder segments and `illustrative` blocks are exempt.
  - `ADR_NAMING` and `ADR_SHAPE`: a `docs/adr/` page that is a decision record only by its filename.
  - `ADR_INDEX_DRIFT`: a record with no row in the tier's index README.
  - `ADR_DANGLING_SUPERSEDE`: a "superseded by" or "amended by" pointer that resolves to no file.
- The index and the status pointers are the only maintained parts of a frozen record, so that is where drift lands.
- Grounding, showcase and ADR shape checks stop at the frozen `docs/archive/**` tier. Link checks still apply.
- Tier membership is tested relative to the scanned root, so a checkout under a folder named `archive` or `adr` is not misread.

## The coverage record

- `update-docs` maintains the onboarding contract instead of only auditing drift.
- It reads `docs/.onboard-coverage.json` and reports a principal surface with no page, and a row whose page was deleted.
- It restates every parked surface on each run. Before this, only `onboard-repo --check` showed a park, and nobody runs that again after onboarding, so a deliberate deferral quietly became permanent.
- Changing a `status` to silence a finding counts as the same dishonesty as hand-editing a capture.
- A missing surface is a report-only finding. `update-docs` hands it to `/batbelt:onboard-repo`, whose authoring step creates only the missing pages.
- `update-docs` does not author the page itself. A grounded page needs a captured command it has no grant to run, and an ungrounded page claiming an unverified capability is worse than a missing one.
- The same posture covers the ADR tier. The index and status pointers are maintained, bodies stay frozen, and the check that each accepted ADR still binds is offered as a report. A "no longer binds" finding proposes a new superseding ADR. It never edits the accepted one.
- These rules are in the [update-docs template](../../skills/onboard-repo/templates/update-docs/SKILL.md).

## ADR mining

- When `docs/adr/` still holds no real decision record after adoption and authoring, the skill offers to mine git history and design docs for candidates. It never runs unasked.
- Workers split by subsystem and return candidates only: title, decision, context, consequences, status, evidence commits.
- A hash the worker did not read from `git log` never enters a candidate.
- Deduplication, the still-in-force judgement and all writing stay in the main thread, behind one confirmation of the candidate list.
- A candidate must be a lasting design choice with rejected alternatives, about the product or architecture. An onboarding run's own docs conventions are run-record material, not a decision record.
- Confirmed candidates run inside the `author` phase as `--kind adr` run items. The phase list gets no new entry.
- The manual has three folders: `getting-started/`, `use/` and `reference/`. Its index lists pages under Get started, Do a task and Look it up.
- `docs/internals/docs-standard.md` states the page kinds, voice, changelog and ADR rules; the stamped `update-docs` defers to it when it exists.
- Each ADR follows `templates/docs-ia/ADR-TEMPLATE.md` and passes `ADR_NAMING` and `ADR_SHAPE`.
- Shape is not truth, so an independent verifier then rechecks each ADR. It gets the page and the repository, never the miner's notes, and asks three questions: does the cited evidence support the decision, are the rejected alternatives real, and does the choice still bind the code. If not, the status becomes `superseded`.
- A flag is fixed or parked like a reviewer flag. `--no-review` skips this verifier too.
