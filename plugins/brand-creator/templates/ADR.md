# ADR-NNNN: (the decision in one line)

Copy to `decisions/ADR-<NNNN>-<slug>.md`, numbers in sequence and never reused. Fill every field, then leave the body as
written: a later change is a dated line under Amendments, and a replaced decision gets a new ADR (this one's Status then
changes by an amendment). Old values stay in this file on purpose; `check --cascade` does not search `decisions/`.

- **Status:** (Proposed | Accepted | Superseded by ADR-NNNN)
- **Date:** (YYYY-MM-DD, the day the owner decided)
- **Source:** (the gate record, for example "G4 2026-01-31", the round, or the owner's message paraphrased with its date)

## Context

(What forced the decision: the constraint, the measurement, the owner's goal. Facts from FACTS.md, research with its
source tier, numbers measured by a check with the report's path.)

## Decision

(What was decided, with the stable names used on the boards and in BRAND-STATE.md. One rule per line when it is a rule set.)

## Consequences

(What this changes and where: tokens, generators, packs, the book chapter, the product repositories. What it rules out.
Which check now enforces it, if any.)

## Rejected

(Each alternative that was considered, one line each, with the reason it lost.)

## Amendments

(Append only, newest last: "YYYY-MM-DD: what changed, why, which gate". Never edit the sections above.)
