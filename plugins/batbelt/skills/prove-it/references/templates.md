# Artifact Templates

The two artifact skeletons. Copy the structure, fill the placeholders, keep the
section order. Headings below are shown in English; per SKILL.md Rule 10 the
artifact is written in the conversation language, so translate headings and
labels, but keep the field set and the IDs exactly as specified.

## Template: Assumption Register

```markdown
# Assumption Register: {topic}

| | |
|---|---|
| Run date | {YYYY-MM-DD} |
| Reference date | {YYYY-MM-DD}: {what it means, e.g. "legal state as of"} |
| Domain(s) | {domain} |
| Mode | VALIDATE / SPEC |
| Research status | NOT STARTED / IN PROGRESS / COMPLETE / BLOCKED: {missing or failed capability; first unfinished assumption; how to resume} |
| Approved source hierarchy | 1. {level 1} / 2. {...} / 3. {...} / 4. {...} {plus any user correction, verbatim} |
| Source register | {name and date of the attached register, or "none: built-in profiles"} |

## Summary

| ID | Assumption | Load | Resolvability | Verdict | Confidence | Source (level) |
|---|---|---|---|---|---|---|
| A-01 | {one sentence} | LOAD-BEARING | SOURCE-CHECKABLE | CONFIRMED | HIGH | P-001 (L1) |

## Validated assumptions

### A-01: {claim}

- Origin: {quote of where it appeared in the input, or "stated by user"}
- Verdict: {verdict} ({confidence}: {one-line reason})
- Evidence:
  - id: P-001
  - citation: {precise identifier}
  - source_url: {url}
  - hierarchy_level: {1-4}
  - verbatim: "{original language quote}"
  - translation: "{conversation language}"
  - fetched: {YYYY-MM-DD}
  - note: {optional}
- Would be refuted by: {one sentence}

## Deferred

| ID | Assumption | Marker | Take it to | Cheapest way to settle |
|---|---|---|---|---|
| A-07 | {claim} | BUSINESS-DECISION | {who} | {experiment or decision} |

## Divergences

| # | What diverges | Details |
|---|---|---|
| D-01 | {arithmetic / source contradiction} | {computed vs claimed, or both verbatims + currency note} |
```

## Template: Change Spec

Second artifact, SPEC mode only. Evidence lives in the register; the spec
references records by ID instead of duplicating them.

```markdown
# Change Spec: {topic}

| | |
|---|---|
| Date | {YYYY-MM-DD} |
| Register | {artifact name of the companion register} |
| Effective from | {YYYY-MM-DD or "on delivery"} |

## Trigger

{1-2 sentences: what event makes this change necessary.}

## Sources

{Bulleted list of register record IDs with one-line descriptions. New
sources found during spec drafting get full provenance records appended to
the register, then referenced here.}

## Inputs

| ID | Input | Type | Boundary | Note |
|---|---|---|---|---|
| IN-01 | {name} | {number/date/flag/...} | OURS / UPSTREAM / EXTERNAL_EXPERTISE: {who} | {} |

## Outputs

| ID | Output | Consumed by | Boundary |
|---|---|---|---|
| OUT-01 | {name} | {downstream consumer} | OURS |

## Calculation

{Pseudocode, not implementation code. Every step that embodies a rule cites
a register record inline:}

    step 1: base = IN-01 * rate        [P-003]
    step 2: if IN-02 then cap at X     [P-004]

## Golden example

{One representative input, expected output derived step by step from the
cited sources, intermediate values shown. Per SKILL.md Rule 11 this is
derived from sources, never copied from the user's materials.}

## Upstream

{One subsection per UPSTREAM-tagged row: what the other team or system must
deliver, phrased in their language, and why it is theirs to deliver.}

## Open items

{EXTERNAL_EXPERTISE markers from the boundary pass (the row, the question,
the named specialist), and any blocking delta from an unverifiable trigger:
what must arrive before the formula can change.}
```

## Self-review checklist (SPEC mode, run before the final checkpoint)

Every line must pass; a failure is a blocker fixed inline.

- [ ] No placeholder text remains: no `{...}`, `TBD`, `TODO`, or `???`
- [ ] Every IN and OUT row referenced in Calculation is declared in its table
- [ ] Every OUT row is produced by at least one calculation step and names a
      consumer
- [ ] Every calculation step embodying a rule cites a register record that
      exists
- [ ] Every number in the spec traces to a provenance record or is computed
      in the golden example
- [ ] Golden example arithmetic re-verified line by line
- [ ] Every IN and OUT row carries a Boundary tag
- [ ] Every UPSTREAM row has its Upstream subsection
- [ ] Every EXTERNAL_EXPERTISE marker appears under Open items with a named
      specialist
- [ ] When the triggering assumption was UNVERIFIABLE, its blocked delta is
      recorded under Open items as blocking
- [ ] Register header carries run date, reference date, and the approved
      hierarchy
