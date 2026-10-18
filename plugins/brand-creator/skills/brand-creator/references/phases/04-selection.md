# P4 Selection, reset and recovery

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques)
- [Gates G2, G2b-a, G2b-b](#gates-g2-g2b-a-g2b-b)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

Converge on one direction the owner chose, with the choice understood exactly as meant.

## Inputs

- The round page and its shots; the owner's reply (often terse: a name, a letter, "GO", a batch like "1 ok 2 b").
- BRAND-STATE.md: Directions table, liked and rejected lines.

## Outputs and paths

| Output | Path |
|---|---|
| G2 record | `BRAND-STATE.md` → `gates.G2` (`state --record G2 "picked <Name> (+ graft)"`) |
| Canonical direction | `canonical_direction` in BRAND-STATE.md |
| Direction statuses | Directions table: liked / rejected / DECIDED |
| Reset rounds | `reset_rounds` in BRAND-STATE.md (the map is required again there) |

## Techniques

1. **Restate before building.** "You picked <Name> (board label X) and <graft>; building that now." Use the word
   names from the board. A bare token that could refer to two lists (board labels and a numbered chat list) → ask,
   or state the assumption in the same message.
2. **Keep / drop / unsure per territory.** The round page offers the micro-vote; an answer like "Compass keep,
   Keystone drop, Lantern unsure" maps straight onto the Directions table.
3. **Judge is advisory.** When a comparative judge ran (your own read in single-thread, or a judge agent), show its
   view, your view and a middle option side by side. Owners override judges often; that is the process working.
   Rubric and icon matrix: [board-contract.md](../board-contract.md).
4. **Incumbent as variant 0.** When there is a mark today, it stays on the board. If it still wins, say so.
5. **Grafting only before the pick.** Combine parts of directions while choosing ("A with C's front door"). After the
   pick, deepen the chosen one.
6. **Interpret combined picks out loud.** "Style 2 and 3" can mean a blend, a choice between, or two directions to
   develop. State your reading and build the narrow one.
7. **Small sizes on real downscales.** When candidates are compared at icon sizes, show and measure each one on the
   system's own downscale (`... downscale --source <candidate master> --project <dir>`; off macOS only with the
   recorded `--renderer` opt-in), never the vector scaled by the browser.

## Gates G2, G2b-a, G2b-b

- **G2 Direction pick.** Board open on the review surface; owner picks; restate; record G2 and `canonical_direction`.
- **G2b-a Reset (nothing liked).** Do not patch the losers. Run P1b research (category, adjacent categories, local
  peers, trend reports, the regulator's guidance when one exists). Build a positioning map that shows where the failed
  round sat (`data-field="failed-round"`). Offer 3-5 new territories: at least one far from the norm, one per
  emotional register. Add the round number to `reset_rounds`; record G2b.
- **G2b-b Recover (the liked direction's refinement was rejected).** In this order:
  1. Ask, or infer from the reply, exactly what was disliked.
  2. Restore the liked original as the visible baseline on the next board.
  3. Deepen it. "Gentle refinement" changes geometry and finish only, never character.
  4. Widen only if the owner asks.

  Do not treat cheap wide sketches after a rejection as a proven recovery; restoring the liked baseline first is what
  worked. Record G2b with the interpretation.

## Pitfalls

- A bare "1" read as the board label when the owner meant the chat list cost a full round. Stable names and a
  restatement prevent it.
- Hybridising the liked direction with other styles after the pick ("warmer" and "stronger" variants) was rejected;
  the owner wanted the original deepened.
- Treating a judge's ranking as a verdict.
- Hiding the incumbent because the new work is more exciting.

## Enforcement

- `board-lint`: None of these on every pick board; Today when an incumbent exists; word names; the map again in
  `reset_rounds`; My call with judge view, lead view and middle option when `data-judge="ran"`.
- `state --require G2` before refinement work is recorded.
- Behaviour evals (stage 6): bare "1" with two lists → restate or ask; "refine with style 2 and 3" → original shown as
  baseline and interpretation stated; judge shown with lead view and middle option.
