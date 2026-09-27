# ADR-0011: `swift:review` is an authored, slash-only, report-only review skill that points into `swift:design`

- **Status:** accepted
- **Date:** 2026-09-27
- **Source:** `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md` §2 (the `swift:review` rows), §6, §8; `docs/superpowers/plans/2026-09-27-swift-skills-part2-review.md` Task 1 (frontmatter probe, 2026-09-27); ADR-0007 (the rule this extends); ADR-0008 (glass stays opt-in)

## Context

The parent spec (§10) deferred an on-demand HIG review of a screen, "own text, run by hand". `swift:design` already holds the decision rules and area references a review would judge against, and `swift:swiftui` holds the accessibility code patterns. A review that auto-fired mid-build would interrupt the work it reviews, and every model-invocable skill adds its description to every session.

A probe on two scratch plugins, identical except for the frontmatter, settled the mechanics:
- With `disable-model-invocation: true`, the skill ran only as `/<plugin>:<skill>`. A matching plain prompt fired the control twin but not this one, and the model's own skill list did not contain it. `claude plugin details` still estimates ~30 tokens for it; the estimator ignores the key.
- `disallowed-tools: Write, Edit, NotebookEdit` blocked the Write tool while the skill ran, even under `--permission-mode acceptEdits`, where the control wrote the file.
- `$ARGUMENTS` expanded under `claude -p`.

## Decision

- **Shape.** `swift:review` is our own text, like `swift:design`, not a fork. It gets no `UPSTREAM.md` section.
- **Slash-only.** `disable-model-invocation: true` means it runs only as `/swift:review` and adds nothing to the model's context until invoked.
- **Report-only.** `disallowed-tools: Write, Edit, NotebookEdit`. `allowed-tools` only pre-approves tools and cannot restrict them. The output is a findings report in chat: violation · location · HIG source · fix.
- **Inputs.** SwiftUI view files and/or screenshots, both first-class. A screenshot finding marks pixel-derived measurements as estimates, and anything an image cannot show goes under "Not checked".
- **Points into `swift:design`.** Its checklist names `swift:design`'s Decision Rules by label and links the area references and HIG pages. It never restates their text, so a design-rule change reaches review without an edit.
- **Carries the project-layer rule byte-identical.** This extends ADR-0007 to a third skill. For a reviewer, a literal the project's layer sanctions is not a finding.
- **Follows ADR-0008.** Missing Liquid Glass is never a finding; glass on content is.
- **Quality gate.** No automated eval: the eval harness fires skills through the Skill tool, which slash-only skills block. Instead, a recorded end-to-end run reviews a planted-violations screen, a project-token variant and a rendered screenshot through `claude -p "/swift:review …"`. The runs are scored against an answer key committed before the first run, and kept in `docs/internals/review-verification.md`.

Rejected:
- **A model-invocable skill with a narrow description:** it can still fire mid-build, and it pays an always-loaded description in every session.
- **Restating `swift:design`'s rules in the review checklist:** two copies drift.

## Consequences

- A change to `swift:review`'s method re-runs the verification, which appends a new dated section to the record; the old sections stay as they are.
- Three skills now carry the project-layer rule word for word (`swift:swiftui`, `swift:design`, `swift:review`), so changing it is a three-file edit.
- `claude plugin details` over-reports `swift:review`'s always-on cost. The probe above is the evidence that the real cost is zero.
