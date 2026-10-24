# ADR-0005: Motion is part of Standard and Full

- **Status:** accepted
- **Date:** 2026-10-23
- **Source:** the [changelog](../../CHANGELOG.md) section of the release that made motion part of Standard and Full (0.4.0);
  "The motion round (Standard and Full)" in the [tokens phase](../../skills/brand-creator/references/phases/07-tokens.md);
  "The motion decision" and "The motion board" in the [script contract](../../scripts/CONTRACT.md)

## Context

Motion was optional from the start. Decision 910 of the [archived decisions log](../archive/decisions-log.md), "Board voice
line and G4 examples fit the business", left the motion and script-budget rules out of the system rules unless something
moves or ships code. So nothing asked a brand whether it moves: motion came up at G4, as one rule line among others, and a
brand that never raised it never answered.

Three releases then made motion something the plugin can record, prove and show. 0.3.4 made it data: easing curves became
tokens, and `motion/motion.json` holds the signature move, the parts, the timeline written in tokens and the rules, or
"nothing moves" with the owner's reason. 0.3.5 made the motion proof (`shot --motion`) step through a page instead of
waiting for it, check phone screens and compare the rest frame in place, and added `frames`, which writes stills of the
motion. 0.3.6 built the brand book's Motion chapter from that data and made it replay the stills with no script.

What was still missing was the decision itself, and a way to reach it before the system rules. A Standard or Full project
could reach its book with motion never discussed, and a brand that moves had no step where its move was tried as options.

## Decision

- Standard and Full decide motion for every brand before G4: a motion round after G3 (the default), or the owner records
  that nothing moves, once, with a reason in the owner's words. `motion/motion.json` stays the one record: absent means not
  decided, `off` means nothing moves, `on` is the approved move.
- A motion round is a board of its own kind (`data-board="motion"`). The first one shows three variants of the signature
  move, each with its own page, proof and stills in a folder of its own, `rounds/rN/<name>/`; later ones refine the pick.
  The owner picks or combines. On approval the tokens the move needs are built and the round's proofs, stills and lint are made
  current again, the round is frozen as `approved-motion`, and the approved variant is copied into `motion/`, recorded as `"on"`,
  proved and given its stills. Quick may run one when something moves.
- `brand-creator motion` shows and records the decision, and `state` prints the same line, so the question is asked once.
  `motion --off "<reason>"` writes once and never over an answer; turning off a brand that moves is a rule change: an edit of
  `motion/motion.json`, then `check --cascade`.
- `check` enforces it in Standard and Full once G4 is recorded: `motion:decided` fails without `motion/motion.json`, and for
  a brand that moves `motion:proof` needs a passing proof of the approved move (the proof of a try-out never counts).
  Before G4, an undecided motion is an info row from G3 on.
- Quick keeps the rule of decision 910: motion is decided at G4, and only when something moves. Quick runs a motion round only
  when something moves and has no check row.
- The stills of a try-out proof stay beside it, so the stills in `motion/frames/`, the only ones the book replays, are those
  of the approved move.

## Consequences

- A Standard or Full project that recorded G4 before this change has no `motion/motion.json`, so `check` fails
  `motion:decided` until it decides: a motion round, or `brand-creator motion --off "<reason>"`. The changelog says so first.
- Every Standard and Full brand answers one question, once, with a recommendation. A brand with no screen presence says
  nothing moves in one sentence, and the book's Motion chapter says so, with that reason and no replay.
- A Standard or Full project gains a few boards: the first motion board, then the refinements of the pick.
- The finish chain gains a motion step in Standard and Full. It prints the decision, never skips in silence, and proves the
  approved move before the stills and the book read the report. Quick has none.
- A motion board published on the review surface holds the strips and stills as inlined pictures. The live pages stay in the
  round folder, so they open from the local copy only.
