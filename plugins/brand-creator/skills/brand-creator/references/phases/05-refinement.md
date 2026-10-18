# P5 Refinement

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques)
- [Gate G3](#gate-g3)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)
- [Refine loop with one reviewer call](#refine-loop-with-one-reviewer-call)

## Goal

Turn the chosen direction into a board the owner approves, in two or three rounds, without losing its character.

## Inputs

- The canonical direction (`canonical_direction`) and its last approved state.
- The owner's feedback, often with screenshots: read every image and name what you see before replying.
- The runner-up, for restraint rules.

## Outputs and paths

| Output | Path |
|---|---|
| Change list | BRAND-STATE.md → Notes, numbered, confirmed by the owner before refining |
| Refine round | `rounds/r<N>/board.html` (`data-board="refine"`), copied from the previous round first |
| Losers | on the board (`data-section="losers"`), each with a one-line reason |
| Frozen approval | `history/<date>-approved-board/` via `freeze`, plus `history/MANIFEST.sha256` |

## Techniques

1. **Numbered change list.** Turn feedback into "(1) ... (2) ..." and confirm it ("unless you say otherwise, I build
   these five"). Owner decisions are numbered; your critique items are lettered.
2. **Refine loop.** Designer pass → one independent review pass → fix:
   - the review says done / partly / not done for every change-list item;
   - recomputes contrast on at least six pairs (`contrast`), magnifies the marks (`logo-sheet`), checks the glyph set;
   - splits findings into no-decision fixes (applied by the fix pass) and a numbered "Decisions for you" list with a
     recommendation each (the fix pass never resolves those);
   - high and medium findings are fixed, or argued against in one line.

   In single-thread you run the review yourself, honestly: if something is fine, say so; do not invent problems.
3. **Each round is a copy.** `cp -R rounds/r<N-1> rounds/r<N>`, then edit only the new folder. Earlier rounds stay as
   they were (the hook enforces it).
4. **Board structure from round 2.** Opens with "00 What changed since the review", closes with "Weak points".
   Every losing candidate stays with a one-line reason.
5. **Restraint from the runner-up.** After the pick, borrow restraint rules, not looks: one accent, no decoration that
   carries no information, count the component types, depth or ornament only in named places. Record them as G4
   "(rule)" items with their counts.
6. **Salvage, don't mix.** A loser's best part may come back as a component; never run two rendering styles side by
   side in one system.
7. **Gentle refinement** means geometry and finish only, never character.
8. **G-sys tripwire.** Count incremental fixes per area (`state --bump fixes_per_area.<area>`). The third in one area
   stops the loop: write a numbered-rules system spec, review it adversarially, get a GO.

## Gate G3

The owner approves the refined board. Record and freeze:

```
... state --project <dir> --record G3 "approved r3"
... freeze r3 --name approved-board --project <dir>
```

`freeze` refuses without G3, never overwrites, adds a "kept as written" banner and updates the manifest. Emitters
also require G3.

## Pitfalls

- Heavy display type and decoration diluting the direction; fixed with explicit restraint rules.
- Editing the previous round in place, which destroys the baseline the owner compares against.
- Patching the same lockup three times instead of writing its rules (G-sys).
- Reporting "done" from code without looking at the rendered result.

## Enforcement

- `board-lint` (round 2+): What changed, Weak points, losers with one-line reasons, My call, questions, reply.
- Hook: Edit and overwriting Write on any round that is not the latest are blocked; `history/` only via `freeze`.
- `check`: history manifest intact; contrast and logo-sheet reports current.

## Refine loop with one reviewer call

Refinement is never a workflow. It runs in the main thread; the only optional subagent is **one**
`brand-creator:brand-reviewer` call per round, after the fleet gate (1 agent, the model that will run, a small cost)
and the owner's yes:

1. The owner's numbered change list is confirmed; you build the round (`rounds/r<N>/`, copied first).
2. The reviewer gets the same numbered change list, the round folder, BRAND-STATE.md, FACTS.md and the data folder in
   the prompt skeleton of [prompt-fragments.md](../prompt-fragments.md). It runs the checks (`contrast` on at least six
   pairs, `logo-sheet`, `fontcheck`, `shot`) and reports done / partly / not done per item, no-decision fixes and
   "Decisions for you". It edits nothing.
3. You apply the no-decision fixes (or argue in one line), re-run the checks, and show the board at G3 with the
   decisions. Without the yes, you do step 2 yourself, honestly. Details: [fleet.md](../fleet.md).
