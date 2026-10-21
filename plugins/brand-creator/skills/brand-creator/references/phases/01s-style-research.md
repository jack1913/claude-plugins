# P1s Style research (before anything is drawn)

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [No web access](#no-web-access)
- [Techniques](#techniques)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

No brand project draws anything before the owner has seen style research and picked styles. Two real projects lost whole
rounds by drawing first: the owner rejected rounds 1 and 2 on style alone (marks, colours, "too technical"), and only a
round of sketches in a style the owner chose worked. P1s puts that choice first, for **every tier**, Quick included.

The deliverable is one visual page, the style board, with 4 to 6 **style territories**. Each territory is grounded in
real, named references the owner can open. The owner picks one or more territories (or "none: research again"), and
round 1 draws inside the pick. After a full rejection (G2b-a) P1s runs again before the new territories are drawn, and
then it cannot be skipped.

## Inputs

- `brief/BRIEF.md`, `FACTS.md`, the architecture line, `incumbent` in BRAND-STATE.md.
- P1b results when they exist (Standard and Full): the five-competitor lineup, `research/cliches.md`. In Quick, do a
  short scan yourself: a handful of searches, enough to name the category norm.
- Any reference the owner named (a site, a sibling brand). If it may be the owner's own brand, say so on the board and
  ask in its questions; a sibling's lettering and fonts are a constraint, not a style option.

## Outputs and paths

| Output | Path |
|---|---|
| Style board (the page the owner sees) | `rounds/r0/board.html`, from `${CLAUDE_PLUGIN_ROOT}/templates/style-board.html` |
| The same page on the review surface | `review/index.html`, a copy of the board (`cp rounds/r0/board.html review/index.html`), linted with `board-lint review/index.html --round 0` |
| Reference marks shown as thumbnails | `research/style-thumbs/` (the originals; the board inlines downscaled copies) |
| Notes behind it (claims with URLs and the date read) | `research/YYYY-MM-DD-style.md` |
| G1s record | `BRAND-STATE.md` → `gates.G1s` (`state --record G1s "<decision>"`; the tool also writes `g1s_round`, the highest round whose board is a style board, or drops it when there is none) |

Set the phase as you go (`... state --project <dir> --set phase=P1s`). The board is round 0, so round 1 stays the first
drawn round. The hook keeps `rounds/r0/` writable while `gates.G1s` is empty; once G1s is recorded and `rounds/r1/` exists
it is read-only like any earlier round.

**A project that is already past round 1** when this step arrived has G1s empty, so `board-lint` fails its round 1 board.
Record it honestly, for example `... --record G1s "n/a: round 1 drawn before the style step"`, or run the style research now
as round 0 (the hook allows it while G1s is empty) and record the owner's pick. An r0 style board drawn after round 1 never
counts for a reset, because a reset needs its style board after the rejected round. So when round 1 was rejected outright, show the
style board as the next reset round instead (round N, listed in `reset_rounds`), record G1s from it, and draw the pick board in
round N+1. For example: r1 rejected, r2 style board, r3 pick board, `reset_rounds` [2, 3]. A later full rejection still shows a new
style board first (below).

**After a full rejection** (G2b-a, see [04-selection](04-selection.md)) the style research runs again before any new
territory is drawn, and it cannot be skipped: "skipped by owner" is for the first pick board only. A new style board goes in
the next round (`rounds/r<N>/board.html` with `data-round` set to N), and N is added to `reset_rounds` (the lint accepts a style
board in round 0 and in a reset round). When the owner has picked, restate the pick and record G1s again; the tool writes
`g1s_round` with it. The pick board of the new territories follows in the round after it, also listed in `reset_rounds`.
Its lint (`project:style-gate`) finds the rejected round (the highest earlier round whose board is not a style board) and
fails until a style board in a reset round lies after it and `g1s_round` is at least that board's round: the pick from before the
rejection cannot stand in for a new one. Two rejections in a row repeat the loop: r1 pick, r2 style, r3 pick, r4 style, r5 pick.

## No web access

The research needs web access: reading the category's real sites, opening each reference, fetching its mark. Check that the
session has web tools (WebSearch, WebFetch or a browser) before you start.

When it has none, or the network is blocked, **say that the style research needs web access, and stop.** Name what you would
have looked at (the category, the competitors, the references the owner named), and offer the three ways forward: allow web
access, send links or screenshots of brands the owner likes (you can read an image you were given), or, before the first
pick board only, skip the research ("skip the research", which you then record as `skipped by owner`; after a full rejection
the style board is required, so the choice is web access or links). Never write references, URLs, brand names or
descriptions of marks from memory, never fill a style board with guesses, and never draw a direction instead. A board whose
references were not opened is worse than no board.

## Techniques

1. **Who sees the mark and where.** The people, what they expect from a brand like this, and the surfaces where the
   mark is seen (the hardest one named). This is the `audience` and `surfaces` sections.
2. **The category norm.** What most competitors share (colour, symbol, type) with 2 named examples, and what to avoid:
   `norm`. Count it from real sites you opened, not from memory.
3. **4 to 6 style territories.** Each is a style, not a logo: one sentence of idea, a palette strip, shape and type in a
   line. They differ from each other the way the owner can see in a second. At least one sits away from the norm. Name each
   with a word (never "Style 2", "Option 3", "Territory 1" or "Look A": the lint rejects a label like those).
4. **Ground every territory in 3 or more named real references**, each with its URL and "what to take / what to avoid".
   Open each page and describe its mark in words (shape, colour, type); link it, and never copy its parts. A reference
   with no link or no "take" does not count.
5. **Show the real mark.** Visual first means each reference shows its real mark as a thumbnail where one can be fetched:
   from official images (the reference's own site or press page), from Wikimedia Commons images, or from a screenshot. Save the original under
   `research/style-thumbs/`, downscale a copy to about 240 px wide and inline it as a `data:` image (`<img data-field="thumb"
   src="data:image/...">`) with alt text, in a `<figure>` whose `<figcaption>` says whose mark it is, where the image is from
   and that it is shown for private research (in the owner's language). A reference with no fetchable image shows none. The
   thumbnail lives on this research page only: never reuse a reference's mark, or a part of it, in a drawing, and never link the
   image from the net (the lint fails it: every `<img src>` and every `srcset` on a style board is an inlined `data:image/`
   URI; a thumbnail also needs alt text and a non-empty caption, and the words of the caption are yours).
6. **A family of marks** (several marks in the brief): put the question to the owner, shared style or a style per item
   or a shared base with a twist each. Add a per-item list to each territory showing how it would flex across the items.
7. **Visual first, in the owner's language.** Thumbnails, short lines, colour strips, chips, no dense tables, no essays,
   no construction detail. Chat language and board language are the owner's; the references keep their own names. The first
   question lets the owner tick one or more styles, and the page composes the reply.
8. **My call.** Say which territory (or two) you would draw first and give the honest critique of your own pick.
9. **Test loop.** Lint, shoot, Read every slice, fix, repeat at least twice before showing, as for any board
   ([board-contract.md](../board-contract.md)).

## Gate

**G1s Style pick.** The board is open on the review surface. The owner picks one or more territories, or "none: research
again" (go back to step 3 with new angles and rewrite the board in the same `rounds/r0/`, which stays writable while G1s is
empty or while it is still the latest round). Restate the pick in one line before drawing ("You picked Harbor and Ember's palette; drawing round 1 inside those.") and
record it: `... state --project <dir> --record G1s "picked Harbor + Ember palette"`.

Before the first pick board the owner may skip it explicitly ("skip the research", in any language, such as "pomiń badanie stylu"). Then record `... --record G1s "skipped by owner"` and go to
round 1. Never skip it on your own: an unanswered style board is not a skip. After a full rejection there is no skip: show the
new style board and record the owner's new pick.

Every pick board waits for G1s: round 1 (P3) with a recorded pick, a skip or an honest "n/a", and the pick board of each reset
round with a new pick recorded after the new style board. Run `... state --project <dir> --require G1s` before building one
(exit 1 means do the style research first; after a full rejection it still exits 0 with the old pick, so keep the order
yourself: new style board, the owner's pick, `--record G1s`, then the pick board); the `/brand-creator:round` skill does it, and
the `directions` workflow refuses to start without the G1s record.

## Pitfalls

- **Drawing first.** A pick board without G1s is the mistake this step exists to prevent; `board-lint` fails it.
- **Invented references.** A URL not opened today, a mark described from memory, or a brand that does not exist. Open it, or
  leave it out. Without web access say so and stop ([No web access](#no-web-access)).
- **Three looks of one idea.** Territories that differ only in hue. Change the shape language, the type and the mood.
- **A sibling brand's style offered as a choice.** If the owner owns the reference, shared grammar is a constraint.
- **A document, not a page.** Tables, contrast grids and English essays on the owner's board; the owner gives up.
- **Skipping on your own** because the brief "seems clear". Only the owner skips, and only before the first pick board.
- **A reference's mark leaving the research page.** A thumbnail linked from the net makes the page depend on it; a mark, or a
  part of it, reused in a drawing copies someone else's identity.
- **Style research forgotten after a full rejection.** New territories drawn straight away repeat the mistake of drawing first.
- **The old pick standing in.** After a full rejection G1s still holds the first pick until the new one is recorded; the lint
  fails the pick board of a reset round until the new style board is there and `g1s_round` is at least its round.

## Enforcement

- `board-lint` on `data-board="style"` (round 0, or a round listed in `reset_rounds`): `audience`, `surfaces`, `norm`, at least
  4 `territory` sections each with a word name (generic labels such as "Style 2", "Option B" or "Territory 1" fail), an idea and 3 or
  more references that carry a link and a "take", every `<img src>` and `srcset` an inlined `data:image/` URI, every thumbnail with
  alt text and a non-empty `<figcaption>` (not particular words), `none-of-these`, `my-call`, numbered questions with lettered
  options and one recommended, `reply`, no unfilled markers.
- `board-lint` on a pick board: round 1 fails with `project:style-gate` while `gates.G1s` is empty (a pick, "skipped by owner" and
  an honest "n/a" all pass). A reset round also fails until a style board in a reset round follows the rejected round (a style
  board with fewer than 4 territories does not count) and `g1s_round` is at least that board's round.
- `scripts/guard.py`: `rounds/r0/` stays writable while G1s is empty, so a project past round 1 can still run the research.
- `workflows/directions.js` requires `args.g1s`; `/brand-creator:round` runs `state --require G1s` before a pick board.
- Behaviour eval `evals/style-gate-before-first-board`: on a fresh project the first turn writes no `rounds/r1` board, and
  without web tools the reply says the research needs web access and stops.
- Prose: whether the references are real, recent and well chosen, and whether the territories truly differ, is judgement
  and is not scripted.
