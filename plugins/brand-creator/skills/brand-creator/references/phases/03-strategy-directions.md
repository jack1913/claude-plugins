# P3 Strategy core and divergent directions (round 1)

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)
- [Fleet option: the directions workflow](#fleet-option-the-directions-workflow)

## Goal

Three to five directions that differ in **strategy**, not three looks of one idea, shown on one round page the owner
can react to in a minute. The owner reacts to boards, not to questions.

## Inputs

- `brief/BRIEF.md`, `FACTS.md`, the architecture line and never-borrow list.
- Research when it exists (Standard and Full): `research/cliches.md`, the category's competitive alternatives, the
  5-competitor lineup. In Quick, do a short category scan yourself (a handful of searches) before drawing.
- Real content: the owner's own copy, product names, offers. Never lorem ipsum.

## Outputs and paths

| Output | Path |
|---|---|
| Round page (the board the owner sees) | `rounds/r1/board.html`, from `templates/round-page.html` |
| Optional deep board per direction (Standard, Full) | `rounds/r1/<direction>/board.html`, from `templates/board.html` |
| Strategy core | on the round page (`data-section="strategy-core"`); fields in [strategy-core.md](../strategy-core.md) |
| Directions table | `BRAND-STATE.md` → Directions (name, letter, register, status) |
| Review page | `review/index.html`, published to the review surface |

## Techniques

1. **Draft the strategy core first** (7 fields, [strategy-core.md](../strategy-core.md)) from research and the brief,
   and show it on the board for reaction. Never interview for it.
2. **Build the positioning map.** Two axes taken from the category's clichés (for example "institutional ↔ personal",
   "cold ↔ warm"). Mark where the category norm sits. Place every direction; at least one sits far from the norm.
3. **Generate territories with these prompts** (details in [board-contract.md](../board-contract.md)):
   - one territory rooted in place, heritage or craft (the brand's own city, material, trade or history);
   - one direction per emotional register (for example trust, noble, friendly, bold); one adjective from the owner
     can open a new territory;
   - each direction states a **named visual philosophy** in one line before anything is drawn;
   - each is placed on named spectrums with a visual gesture and a verbal one (a sample line).
4. **Reflex test.** Check each direction against [ai-defaults.json](../ai-defaults.json). A hit is allowed only with
   an argument written on the board (`data-field="reflex"`). If every direction shares one archetype, they are not
   divergent; replace one.
5. **Design systems, not marks.** Each direction shows mark, wordmark, type, colour and a real hero together; the cell
   list is in [board-contract.md](../board-contract.md).
6. **Hardest surface.** Show every direction on the one surface from BRIEF (or from INVENTORY.md when it exists).
7. **Family modes.** Each direction states what it keeps from the family layer and what it owns; check family fit
   before polish, and show "why this is not <sibling>".
8. **Single thread works.** One pass per direction in sequence, each with its own "YOUR DIRECTION" paragraph over
   the same brief (skeleton in [prompt-fragments.md](../prompt-fragments.md)). A fleet of designers is optional,
   only after the fleet gate.
9. **Test loop.** Lint, shoot, Read every slice, fix, repeat at least twice before showing.

## Gate

None by itself: the round ends at G2 (see [04-selection.md](04-selection.md)). The page ends with My call and an
instruction to reply with a direction name, or question number plus option (1a), and one sentence. Direction letters stay off unless the owner asks. Combinable picks are allowed
("Compass with Lantern's dot"); whatever the owner picks is developed to equal depth.

## Pitfalls

- Three options sitting in the same safe middle of the category: all rejected. Research first, map against the norm,
  keep one far from it.
- All directions leaving a family's shared grammar: the owner did not want that. Know the architecture before round 1.
- Category clichés (navy and gold for trust, scales and columns for law, a leaf for eco): fine only when argued.
- Placeholder copy hides whether a direction works; use the real offer and real names.
- A board that only shows the mark: the owner cannot judge the system.

## Enforcement

- `board-lint` (round 1): strategy core, positioning map with every direction placed and one `data-far="true"`,
  at least 3 directions with word names and one register each, an idea and a reflex result per direction, hardest
  surface, None of these, My call with recommendation and critique, numbered questions with lettered options, reply.
- `shot`: four views with no overflow, console errors or network requests; forbidden-string counts from BRIEF and
  `research/cliches.md`.
- Behaviour eval `evals/r1-board-map-today-none`: the r1 board has the map, Today (when an incumbent exists) and None of these.

## Fleet option: the directions workflow

With the owner's yes at the fleet gate, round 1 (or a reset round) can run as the `directions` workflow: one
`brand-creator:brand-designer` per direction writing only `rounds/r<N>/<direction>/`, then one advisory
`brand-creator:brand-judge`; `inventory: true` runs the P1c survey first with `brand-creator:brand-inventory`. Default
3 designers and the judge, 4 agents. You still write the strategy core, the territories and the round page, and stop at
G2. Arguments, models and the gate: [fleet.md](../fleet.md).
