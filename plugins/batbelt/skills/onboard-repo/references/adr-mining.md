# Mine ADRs from the repo's history

Section 3.7b of [SKILL.md](../SKILL.md), moved here; only citations of another repository's ADRs were dropped. SKILL.md sends you here at that step.

## 3.7b Mine ADRs from the repo's own history (offer-first)

**Trigger:** after adoption and authoring, `docs/adr/` still holds no real decision
record (only `ADR-TEMPLATE.md` / `README.md`). A brownfield repo's design decisions
usually live in commit messages and design docs rather than decision pages — the
§3.6 rubric can only *file* pages that already exist, so without this pass the ADR
tier scaffolds empty and stays empty. **Offer the pass, report-first; never run it
unasked.** It runs inside the `author` phase (`run_set_phase` enforces the phase
enum — no new phase); register the confirmed candidates as run items with
`--kind adr` so a resumed run picks up mid-list.

The bar every candidate must pass:

- a durable **design choice with rejected alternatives**, still constraining the
  code today — "could this reasonably have been done another way, and does the
  choice still bind?" A feature is not an ADR; a bugfix is not an ADR.
- **product/architecture only** — never documentation layout, repo tooling, or
  this skill's own bookkeeping. An onboarding run's IA conventions are run-record
  material, not an ADR; writing one as the first ADR is the exact failure this bar
  exists to prevent.
- a superseded decision is still recordable (`Status: superseded`, naming what
  replaced it) when it shaped the system.

Mining is a **fan-out** pass (§0.2): shard the repo by subsystem with
non-overlapping briefs; each worker reads that subsystem's design docs plus
targeted `git log` / `git show` and returns **candidates only** — title, decision,
context, consequences, status, decision date, evidence commits, rationale
sources — never file bodies. **Every evidence hash comes from real git output —
cite-or-defer; a hash the worker did not read from `git log` does not go in a
candidate.** Down-tier the workers; the still-in-force judgment and all authoring
stay with the lead.

Then, in the main thread: dedupe, keep the durable ones, and **show the operator
the candidate list for confirmation** before writing anything. Author each
confirmed candidate as `docs/adr/ADR-NNNN-<slug>.md` in the template's shape
(Context / Decision / Consequences, with `Status`, `Date` = the deciding commit's
date, `Source` = the verified commits plus the spec/doc carrying the rationale).
`check-docs`'s `ADR_NAMING` / `ADR_SHAPE` findings are the shape gate — run it
scoped per authored ADR exactly like a §3.7 page, and the close-out unscoped pass
covers the set.

Shape is not truth — a well-formed ADR that misreads history passes the gate
clean. So each authored ADR then gets the same independent revalidation a §3.7
page gets from the reviewer: **one verifier per ADR**, handed only the authored
page and the repo — never the miner's candidate notes — re-reads each `Source`
commit and the code it touched and answers three questions: does the cited
evidence actually support the stated decision, are the rejected alternatives
real rather than invented, and does the choice still bind the code today (or
should `Status` be `superseded`)? A verifier flag is handled exactly like a §3.7
reviewer flag — fix or park; an ADR never counts `done` while a flag stands.
`--no-review` skips this verifier along with the §3.7 reviewer, and the run is
labeled *unreviewed*.
