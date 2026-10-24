# P7 Tokens and system rules

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques)
- [The motion round (Standard and Full)](#the-motion-round-standard-and-full)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

Brand values live once, in DTCG 2025.10 sources, and every consumer reads them: the site, the apps, the emitters and the
book. The rules that hold the system together (contrast, colour-vision distance, theme behaviour, motion) are written as
one-line "(rule)" items that the owner approves at G4.

## Inputs

- The approved direction (G3) and the mark's colours from P6, with the signature move P6 named and the approved still
  (`assets/logo/mark.svg`) that a motion round starts from.
- `templates/tokens/*.tokens.json` copied to `<project>/tokens/` (neutral placeholders; replace every value).
- INVENTORY.md and BRIEF.md: the surfaces that carry state colours, charts or dark mode.
- `qa/rules.json` for owner thresholds (proposals apply without it, printed as proposals).

## Outputs and paths

| Output | Path |
|---|---|
| Token sources (the truth) | `tokens/primitives.tokens.json`, `tokens/semantic.light.tokens.json`, `tokens/semantic.dark.tokens.json` |
| Built tokens | `assets/tokens/` (`tokens.css`, `tokens.json`, Swift, Android XML, `Colors.xcassets`; Swift and Android also carry the durations and the curves) |
| Accepted misses | `tokens/exceptions.json` (one reason per entry) |
| Reports | `assets/_checks/tokens.json`, `assets/_checks/contrast.json` |
| Thresholds | `qa/rules.json` (`cvd`, and the P6 sections) |
| Motion hand-off | `motion/SPEC.md` from `templates/MOTION-SPEC.md` (when the brand moves) |
| Motion spec as data | `motion/motion.json`: motion on or off, the signature move, the parts, the timeline in tokens, the rules (schema in `scripts/CONTRACT.md`; `check` validates it). It is also the one record of the decision: absent means not decided |
| The motion round (Standard and Full) | `rounds/r<N>/board.html` (`data-board="motion"`) and one folder per variant, `rounds/r<N>/<variant>/`; once approved: `motion/proof.json`, `motion/frames/` and `history/<date>-approved-motion/` |
| Rules | BRAND-STATE.md Notes as "(rule)" lines, then G4 |

## Techniques

1. **Two tiers, DTCG 2025.10.** DTCG 2025.10 is a Final Community Group Report: stable, but not a W3C Standard and not
   on the Standards Track, and no project file may say otherwise. *Primitives* hold the palette ladders, type scale, units
   (hairline, frame, focus ring), named durations and named curves. *Semantic* light and dark files hold the roles (`color.bg`,
   `color.text`, `color.muted`, `color.accent`, `color.mark`, `color.border` ...) as aliases (`"{color.paper}"`). Family
   members swap primitives only; the roles stay. Token names never contain `.`, `{`, `}` or start with `$`. The 2025.10
   resolver module exists, but the pinned Style Dictionary does not read it, so light and dark stay two files.
2. **OKLCH ladder with gamut mapping.** For each role pick a hue, then a lightness ladder (for example L 0.97 down to
   0.20) with a chroma curve that peaks in the middle steps. Map out-of-gamut steps into sRGB by reducing chroma at
   constant L and H (CSS Color 4 gamut mapping). Never clip channel by channel. The 6-digit `hex` beside each oklch value is
   the sRGB fallback and must equal the gamut-mapped conversion. `brand-creator tokens --fix-hex` computes it; never type
   it by hand. Colours that already exist (an owner's mark) go in as `srgb` components, which is exact.
3. **Three kinds of contrast, never mixed up.**
   - *UI gate, WCAG 2.2 AA:* text 4.5:1, large text 3:1, UI components and focus indicators 3:1, in light **and** dark.
     A pair's `min` can be raised, never lowered.
   - *Brand-rule targets for marks and lockups:* WCAG 2.2 says text that is part of a logo or brand name has no contrast
     requirement, and the 1.4.11 guidance exempts logos. So mark targets are the owner's rules, labelled "brand rule
     (logos WCAG-exempt)", never "WCAG". The colours that touch in the artwork are found in the raster, not declared by
     hand, and each pair is held to a target. A miss the owner accepts goes in `tokens/exceptions.json` with a reason.
   - *APCA, advisory only:* an Lc column (APCA 0.0.98G through colorjs.io) to inform type choices. WCAG 3 is a Working
     Draft whose contrast method is still to be determined, and APCA is not in it. APCA never gates, and nothing here
     claims WCAG 3.
4. **Colour vision.** `contrast --cvd` simulates protanopia, deuteranopia and tritanopia at full severity with
   ColorAide (Viénot/Brettel for protan and deutan, Brettel 1997 for tritan; Machado has no tritan model). It requires a
   minimum ΔE2000 between every contrast pair and every `distinct` pair (for example the brand accent and the danger
   colour, or two state colours). The proposal is ΔE2000 ≥ 10. That number is a heuristic, not a standard; the owner sets
   it in `qa/rules.json` `cvd`. A state is never told apart by hue alone: add shape (P6, `states-check`).
5. **Theme behaviour is a rule.** The default is "follow the system": `tokens.css` applies dark under
   `prefers-color-scheme: dark` unless `[data-theme="light"]` pins light, and `[data-theme="dark"]` pins dark. The
   alternatives are always light, always dark, or follow the system with a toggle. Dark is designed, not inverted: the
   semantic dark file is checked pair by pair like light.
6. **Motion rules (a brand that moves: Standard and Full from the approved move, Quick only when something moves).**
   - Static first: the still is complete without motion.
   - Reduced motion means nothing moves and no motion listener is registered.
   - Every motion ends on the rest frame, and the rest frame equals the still pixel for pixel.
   - Nothing loops forever.
   - Movement is in whole pixels and causes no layout shift.
   - Touch never blocks scrolling.
   - No audio before a gesture, and a sound-off control also stops key listening.
   - Keyboard-driven pieces listen only while in view, ignore modifier keys and form fields, and release on blur; say
     what a single-key shortcut costs.
   - Animated text keeps its full text available to assistive technology, and in-page navigation never replays motion
     already shown.
   - A stated script budget for interactive pieces, in kB gzipped (proposal: 6 kB).
   - Delight (interaction, sound, a seamless loop that ends) is welcome only when it says something about the brand and
     obeys every rule above.
   Durations and curves are named tokens. Durations: `motion.quick`, `base`, `slow`, `stagger`. Curves: `easing.standard`,
   `easing.enter`, `easing.exit`, each `$type` `cubicBezier` with `[x1, y1, x2, y2]` (x between 0 and 1, y free); the
   starter's three are proposals until G4. The build writes them to CSS, Swift and Android. Write the hand-off from
   `templates/MOTION-SPEC.md`: selectors, units, timeline, the rest frame and the reduced behaviour. Write the same
   facts as data in `motion/motion.json` (the signature move, the parts, the timeline as references to these tokens, the
   rules; or `"motion": "off"` with the owner's reason), which the adapters read. In Standard and Full that file is written
   when the motion round is approved, or by `brand-creator motion --off`, before G4; in Quick, at G4.
7. **Type and units.** A type scale in px or rem as DTCG dimensions (`{value, unit}`). A minimum label size the book
   will hold itself to. Hairline and frame units for strokes and padding. A focus ring that passes the UI gate on both
   grounds.

## The motion round (Standard and Full)

Standard and Full decide motion for every brand before G4: a motion round (the default), or the owner records that nothing
moves. `motion/motion.json` is the one record of it: absent means not decided (schema and commands:
`scripts/CONTRACT.md`, "The motion decision"). Quick keeps its own rule: motion is decided at G4, and only when something
moves; a Quick brand that moves may run a motion round too.

1. **When.** After G3 and the P6 masters, before G4. From G3 on, `brand-creator motion` and the `motion:` line of the state
   summary say `not decided` and what is due before G4; `check` shows it as an info row until G4 is recorded, then fails
   `motion:decided`.
2. **The question, at G3, asked once.** One question, two options, your pick marked (Recommended): try the signature move
   in a motion round, or nothing moves. Recommend nothing moves for a brand with no screen presence (a bakery, a practice,
   a photographer, a shop that sells on paper) and the motion round for a brand whose mark is seen on a screen (an app, a
   site, a product), with the reason in one line. Nothing moves: `brand-creator motion --off "<the owner's reason, in the
   owner's words>"` writes `motion/motion.json` once and never over an answer; changing it later is an edit of that file,
   then `check --cascade`. Never run it on a reason of your own, and never ask again once the state summary shows an answer.
3. **The round.** `/brand-creator:round motion` ([the round skill](../../../round/SKILL.md)): 3 variants of the signature
   move P6 named, three readings of one idea, each a page of its own in the place the move is really seen with the approved
   mark in place, its proof and its 25 stills, shown on a motion board as a strip, the still under reduced motion, a link to
   the live page, the proof line, What it is, Cost and Degrades to ([board-contract](../board-contract.md)).
4. **The owner picks or combines.** A pick or a combination ("Settle, with Glide's curve") goes into the next motion round,
   which shows 1 or more variants and needs What changed and Weak points. "None of these", with what was missing, gives a
   new motion round (three new variants are fine), or the owner says nothing moves.
5. **The refine loop** is [05-refinement](05-refinement.md)'s: a designer pass, at most one `brand-creator:brand-reviewer`
   call per round (it runs `shot --motion` on each variant's proof and reads each strip), the fix pass. A round copied from
   the previous one keeps its stills in its own folder; `frames` takes them again in place.
6. **On approval.** The timeline of `motion/motion.json` names its durations and curves as tokens, and the variants' pages
   load `tokens.css`, so build the tokens first: copy `templates/tokens/*.tokens.json` to `tokens/` if that is not done yet
   (Inputs above; the starter already holds `motion.quick`, `base`, `slow`, `stagger` and `easing.standard`, `enter`, `exit`),
   add to `tokens/primitives.tokens.json` a duration or a curve the move needs that is not there, and run
   `brand-creator tokens`, which writes `assets/tokens/`. Building them changes `tokens.css`, a file the variants' pages load,
   so the variants' reports and the lint of the round are stale, and `check` says "not verified" for a round the owner
   approved: run `shot --motion` and `frames` on each variant's proof again, then `board-lint rounds/r<N>/board.html`, then
   `shot rounds/r<N>/board.html` (the board last), so that the record of the round is current. A later change to a file the
   variants load (a token, a master) makes that lint stale again until they are run again, as for any proof. Then freeze the round:
   `... freeze r<N> --name approved-motion` (take every still first: `frames` refuses a proof inside `history/` and one in a
   round before the latest, both read-only). Copy the approved variant's page into `motion/` and its `proof.json` to
   `motion/proof.json`, with every path that moved rewritten (the case's `page`, any link in the page). Then write
   `motion/motion.json` with `"motion": "on"` and `motion/SPEC.md` (technique 6); written before the tokens are built it would
   still be the answer: until the tokens are built `motion` and `state` still show the answer, and `check` says `motion:spec`
   is not verified. Run `shot --motion motion/proof.json` and `frames motion/proof.json --count 25` (the stills the book
   replays go in `motion/frames/`). Then G4, with the motion rules.

## Gate

**G4 System rules.** A written plan, then an explicit GO. Every threshold is your proposal, written as one revertable
"(rule)" line in BRAND-STATE.md Notes. Pitch the list at the owner. In Quick, and for any brand without a product UI (a
bakery, a practice, a photographer), show the rules as plain-language defaults "unless you say otherwise" ("text is
easy to read on every colour we use, in light and dark"; "the logo stands out from whatever it sits on"; "the colours
stay tellable apart for people with colour-blindness") and keep the numbers in the Notes line, not in the message.
Standard and Full decided motion before this gate: offer the motion rules from the approved move, and none when nothing
moves. In Quick offer them only when something in the brand moves. Offer the script-budget rule only when the brand ships
code. For example:

- (rule) UI text at least 4.5:1, large text and UI components at least 3:1, light and dark (WCAG 2.2 AA; cannot be lowered)
- (rule) mark on its ground at least 3:1 (brand rule; logos are WCAG-exempt)
- (rule) colours that touch in the mark at least 3:1, except the pairs listed in tokens/exceptions.json with a reason
- (rule) colour-vision distance ΔE2000 at least 10 between role pairs, for protan, deutan and tritan (proposal)
- (rule) theme follows the system; `data-theme` pins light or dark (when the brand has a site or an app)
- (rule) reduced motion: nothing moves; durations `motion.quick` 160 / `base` 320 / `slow` 640 ms, `stagger` 120 ms; curves `easing.standard`, `enter` and `exit` (when `motion/motion.json` says on; in Quick, only when something moves)
- (rule) interactive brand pieces stay within 6 kB of script, gzipped (proposal; only when the brand ships code)
- (rule) accent and danger stay distinct (a `distinct` pair)

In Quick, record the motion answer, on or off, in `motion/motion.json` now (off needs the owner's reason, in the owner's
words: `brand-creator motion --off "<reason>"` writes it). In Standard and Full it is there already, and `check` fails
`motion:decided` once G4 is recorded without it. Then record the G4 plan with
`... state --project <dir> --record G4 "<plan> GO"`. Any later change to a rule or token follows the cascade (`check --cascade "<old value>"`).

## Pitfalls

- Presenting DTCG as a standard of the W3C, or WCAG 3 as the current rule.
- Clipping out-of-gamut channels, or typing hex fallbacks by hand. The two drift apart.
- Labelling a mark target "WCAG", or gating on APCA.
- A dark theme made by inverting the light one. The touching pairs and the mark on its dark ground fail.
- Simulating tritan with a model that does not cover it. Check that the report names the method.
- State colours that differ only in hue.
- A colour value written into code, CSS or a generator instead of read from `assets/tokens/`.
- An animation that never stops, or a reduced-motion mode that only shortens durations.
- Asking the motion question again when the state summary already shows an answer, or answering it for the owner: a
  motion round or nothing moves is the owner's call, and `motion --off` takes the owner's reason, never yours.
- A copied motion round whose proofs still point into the old round (`board-lint` fails `motion:files`), and an approved
  `motion/proof.json` that still names the page inside a round: the proof of the approved move must not lean on a try-out folder.

## Enforcement

- `tokens` (script): Style Dictionary 5.7.0 is the only producer of colour values for code. Every emitted artefact is
  parsed back and compared with the source hex (a round trip per transform). A stored hex that is not the gamut-mapped
  oklch fails, and `--check` fails when the outputs are stale. A curve that is not four finite numbers with x1 and x2
  between 0 and 1, and a duration that is not whole milliseconds, fail it too, named by token path; the Swift and Android
  motion files are parsed back like the rest.
- `check` (script): `motion/motion.json` is validated when it exists: its schema, and every duration and curve it names
  must be a built token of that kind. With the tier Standard or Full and G4 recorded, `motion:decided` fails without the
  file (on or off), and a brand that moves needs a current passing report of `motion/proof.json`, the proof of the
  approved move, `motion:proof` (the report of any other proof never counts, a try-out's included, and a failing one fails
  the row); from G3 to G4 an undecided motion is an info row. Quick has neither row.
- `motion` (script): prints the decision (`on`, `off` or `not decided`, with what is due before G4), and `--off "<reason>"`
  records that nothing moves once, never over an answer. `state` prints the same line.
- `board-lint` on a motion board (script): `motion:g3`, `motion:off`, `motion:variants`, `motion:files`, `motion:proof`,
  `motion:stills` and `motion:fields`: each variant's folder, page, proof, report and stills, and that the strip on its card
  is the file `frames.json` lists ([board-contract](../board-contract.md)).
- `contrast` (script): the UI pairs gate on WCAG 2.2 AA; the brand-rule pairs and the touching pairs from the raster gate
  on the owner's targets; an exception needs a reason and is reported when it matches nothing. Artwork with gradients is
  "not verified", never a pass.
- `contrast --cvd` (script): ΔE2000 under each deficiency, the threshold from `qa/rules.json`, the method named per row.
- `shot --motion` (script): a page's motion is seeked, not waited for: no infinite animation, layout shift 0 and no animated
  layout property (move the mark with `transform` and `opacity`), whole pixels for a pixel mark (a vector mark may ease), at
  360 and 390 px nothing past an edge and no sideways scroll, the rest frame equal to the still in the page itself (a
  named-state file: at device scale 1 and 2, control pairs must differ), and a reduced pass with no running animation and no
  motion listener. Motion driven by `requestAnimationFrame` cannot be seeked: its edges and whole pixels are "not verified",
  so write the motion as CSS animations, transitions or `element.animate()`. One report per proof file. `frames` writes
  stills of the motion into `motion/frames/` for the book, whose Motion chapter replays them (`frames motion/proof.json
  --count 25` before `book`: fewer than 9 stills jump); the variants of a motion round keep theirs beside each proof, in
  `rounds/r<N>/<variant>/frames/<variant>/` (`frames` refuses a proof inside `history/` or in a round before the latest).
- `check --cascade` (script): no current file still holds an old value.
- Prose: this file and the G4 "(rule)" list. Touch scrolling, audio and the script budget are not measured; they are
  listed in [09-qa](09-qa.md) as judgement items.
