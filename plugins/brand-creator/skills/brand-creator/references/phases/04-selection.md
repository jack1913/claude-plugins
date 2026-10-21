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

Converge on one direction the owner chose, with the choice understood exactly as meant. The style pick (G1s) happens
before this step ([01s-style-research](01s-style-research.md)); selection here is among drawn directions.

## Inputs

- The round page and its shots; the owner's reply (often terse: a name, a letter, "GO", a batch like "1 ok 2 b").
- BRAND-STATE.md: Directions table, liked and rejected lines.

## Outputs and paths

| Output | Path |
|---|---|
| G2 record | `BRAND-STATE.md` → `gates.G2` (`state --record G2 "picked <Name> (+ graft)"`) |
| Canonical direction | `canonical_direction` in BRAND-STATE.md |
| Direction statuses | Directions table: liked / rejected / DECIDED |
| Reset rounds | `reset_rounds` in BRAND-STATE.md: the style board of the research run again, and the pick board after it (the map is required again on the pick board) |
| G1s record again | `gates.G1s`, re-recorded with the owner's new style pick after the new style board; `state --record G1s` also rewrites `g1s_round` (the highest round whose board is a style board), which the lint reads |

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
8. **Screening overrides go on record.** When the owner keeps an option that the screening or a judge flagged (a likeness
   to another company's mark, a disqualified option), add a Notes line to BRAND-STATE.md:
   `- Screening override <date>: <item>, <why the owner kept it>, <the extra check it triggered>`, and run that check before G3.

## Gates G2, G2b-a, G2b-b

- **G2 Direction pick.** Board open on the review surface; owner picks; restate; record G2 and `canonical_direction`.
- **G2b-a Reset (nothing liked).** Do not patch the losers. Run P1b research (category, adjacent categories, local
  peers, trend reports, the regulator's guidance when one exists). Then run the style research again
  ([P1s](01s-style-research.md)) before any new territory is drawn: a full rejection is often a style rejection. The style
  board is required here: "skipped by owner" is for the first pick board only. Show a new style board in the next round and
  add that round to `reset_rounds` (the whole list: `state --set reset_rounds=2,3`; the lint accepts a style board there).
  When the owner has picked, restate the pick and re-record G1s (`state --record G1s "<the new pick>"`; the tool also writes
  `g1s_round`). Only then build the pick board in the round after it, also added to `reset_rounds`: a positioning map that
  shows where the failed round sat (`data-field="failed-round"`) and 3-5 new territories drawn inside the new style pick, at
  least one far from the norm, one per emotional register. Record G2b. `board-lint` fails that pick board
  (`project:style-gate`) until a style board in a reset round follows the rejected round and G1s was recorded after it, so the
  old pick cannot stand in.
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
  `reset_rounds`; a style board allowed in a reset round; `project:style-gate` on the pick board of a reset round (G1s recorded,
  a new style board in a reset round after the rejected round, `g1s_round` at least that round);
  My call with judge view, lead view and middle option when `data-judge="ran"`.
- `state --require G2` before refinement work is recorded.
- Behaviour evals: `evals/bare-number-two-lists` (bare "1" with two lists → restate or ask), `evals/refine-style-2-and-3`
  ("refine with style 2 and 3" → original shown as baseline and interpretation stated) and
  `evals/judge-view-lead-view-middle-option` (judge shown with lead view and middle option).
