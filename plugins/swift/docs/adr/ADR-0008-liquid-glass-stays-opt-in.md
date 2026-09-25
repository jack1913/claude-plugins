# ADR-0008: Liquid Glass stays opt-in in `swift:swiftui`

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commits `eb43096` (upstream rule imported), `e2b00d9` and `3c33ce5` (`swift:design` and its Liquid Glass reference); `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §4, final paragraph; ExampleApp companion spec `~/Dev/projects/example-app/docs/superpowers/specs/2026-09-24-example-app-design-layer-design.md` (translation table)

## Context

Upstream's operating rule reads "Only adopt Liquid Glass when explicitly requested by the user". Adding `swift:design`, whose job includes deciding where glass fits, raised the question of whether to relax that gate.

## Decision

Keep upstream's rule unchanged in `swift:swiftui`, the correctness layer. It decides whether glass is used at all. `swift:design` judges where and how glass fits (which variant, tint and corner treatment, on the navigation layer only) once glass is in scope. Per spec §4's final paragraph, a project's own layer may override both. The shipped rules reach that override only through the general clause "the project layer wins on conflict" (ADR-0007), which is worded for example literals.

Rejected: removing or relaxing the gate so the plugin proposes glass wherever it judges glass fits.

## Consequences

- The line stays byte-identical to the `upstream-5.1.0` import (`SKILL.md`, Operating Rules), so it never shows up as a deviation.
- A repo that wants glass by default says so in its own design layer. ExampleApp's planned layer does this for floating overlays (companion spec, translation table).
- Known tension: `swift:design`'s operating rule "Adopt Liquid Glass where `references/liquid-glass-design.md` says it fits" has no condition that glass was requested, so read on its own it can conflict with the gate. It should be reworded to apply only once glass is in scope, as a separate `fix(design)` change.
