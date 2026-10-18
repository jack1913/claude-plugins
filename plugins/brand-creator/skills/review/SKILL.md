---
name: review
description: Runs the self-review of the current brand project's latest work (the round board, the book or the packs) against its own rules and checks, and presents the findings as one approvable list. Offers an optional lens panel (design, content, technical and, when they apply, legal, platform and accessibility) behind the fleet gate.
argument-hint: "[board|book|pack|all] [panel]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Review

Thin wrapper. Arguments: `$ARGUMENTS` (what to review; empty → the latest work the phase in BRAND-STATE.md points at;
`panel` → offer the lens panel).

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

## Self-review (always)

1. `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`; read BRAND-STATE.md, brief/BRIEF.md and FACTS.md.
2. Run the checks first and quote their results: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" check --project <dir>`,
   plus `board-lint` for a board and `book-lint --self-consistency` for the book. Then `shot` the page and Read every
   slice (1440 and 390, light and dark).
3. Read the work against its list:
   - a board: [board-contract](../brand-creator/references/board-contract.md), the reflex list
     ([ai-defaults](../brand-creator/references/ai-defaults.json)) and [anti-patterns](../brand-creator/references/anti-patterns.md);
   - the book: the self-review table of the [brand-book skill](../brand-book/SKILL.md#self-review);
   - packs: [09-qa](../brand-creator/references/phases/09-qa.md) and the downscale proof.
4. Challenge every finding before listing it: verify it yourself, and drop anything wrong, cosmetic without benefit, or
   against an owner decision or the approved rules. Measured numbers instead of adjectives; judgement said as such.
5. Present one list: fixes that need no decision (with the file), numbered "Decisions for you" each with a
   recommendation, and up to five strengths that must not change. The owner approves the list; nothing is fixed before.

## Lens panel (optional)

Each lens reads the same work for one concern and returns findings as `{id, severity, where, evidence, why for this
brand, change, effort S/M/L}`: design, content (FACTS.md only, the tone rules), technical (files, sizes, checks) and,
when they apply, legal or regulatory, platform, accessibility. A judge pass then challenges every finding and sorts the
survivors into A (before launch), B (soon) and C (optional), plus the owner-only decisions with a recommendation.
Lenses read; they never edit.

- Default: single-thread. You run each lens in turn, then the judge pass, in this session.
- A fleet (one read-only subagent per lens, then one judge) only after the fleet gate of the
  [orchestrator](../brand-creator/SKILL.md): state the agent count, the models that will actually run (the session model
  is a ceiling), the size guideline (a cross-check is 2 to 4 agents) and a rough cost, and launch only after an explicit
  yes. Every prompt carries the RULES line and the CONTEXT paths of
  [prompt-fragments](../brand-creator/references/prompt-fragments.md).
- Panels advise. Show the judge's view, your own view and a middle option where they differ; the owner decides.
