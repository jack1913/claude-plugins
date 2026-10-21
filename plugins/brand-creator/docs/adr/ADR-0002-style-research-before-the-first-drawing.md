# ADR-0002: Style research before the first drawing

- **Status:** accepted
- **Date:** 2026-10-20
- **Source:** the [style research phase](../../skills/brand-creator/references/phases/01s-style-research.md); "Board contract" and "Hook guard" in [CONTRACT.md](../../scripts/CONTRACT.md); the Unreleased entries of the [changelog](../../CHANGELOG.md)

## Context

On 2026-10-20 an owner rejected a whole round of marks drawn by code. Nothing had anchored the owner's taste first, so the
round was drawn in a style nobody had chosen. A field session for another brand hit the same wall.

## Decision

- Every pick board waits for a style research step (P1s) and its gate (G1s), in every tier. Claude researches who sees the
  mark, where, and what the category looks like. It shows a style board of four to six territories, each with three or more
  real references the owner can open. The owner picks.
- The style board is round 0 (`rounds/r0/board.html`). After a full rejection it comes back in a round listed in
  `reset_rounds`.
- `rounds/r0/` stays writable while G1s is empty, so a project already past round 1 can run the research now. Once G1s is
  recorded, round 0 is read-only like any earlier round.
- A full rejection arms the gate again. `state --record G1s` writes `g1s_round`, the highest round whose board is a style
  board. The pick board of a reset round passes `board-lint` only when a new style board lies after the rejected round and
  `g1s_round` is at least that round, so the first pick cannot stand in for a new one.
- The owner may skip the research only on the first pick board, in their own words. Claude records it in G1s as "skipped by
  owner" and never skips for them. After a full rejection there is no skip.
- A reference may show its real mark as a thumbnail. It is an inlined `data:` image with alt text, in a figure whose caption
  names the owner of the mark, for private research. It stays on the research page and is never reused in a drawing.

## Consequences

- The owner answers one more board before anything is drawn.
- The research needs web access. Without it Claude says so and stops; it never invents a reference.
- Projects that drew round 1 before this step record an honest `n/a: round 1 drawn before the style step` in G1s, or run the
  research now as round 0.
- The gate is covered by tests (`board-lint`, `state`, the hook, `patch`) and by the behaviour eval
  `style-gate-before-first-board`.
