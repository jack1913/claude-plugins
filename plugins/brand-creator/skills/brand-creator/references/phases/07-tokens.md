# P7 Tokens and system rules

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

Brand values live once, in DTCG 2025.10 sources, and every consumer reads them: the site, the apps, the emitters and the
book. The rules that hold the system together (contrast, colour-vision distance, theme behaviour, motion) are written as
one-line "(rule)" items that the owner approves at G4.

## Inputs

- The approved direction (G3) and the mark's colours from P6.
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
| Motion hand-off | `motion/SPEC.md` from `templates/MOTION-SPEC.md` (only when something moves) |
| Motion spec as data | `motion/motion.json`: motion on or off, the signature move, the parts, the timeline in tokens, the rules (schema in `scripts/CONTRACT.md`; `check` validates it) |
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
6. **Motion rules (only when something moves).**
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
   rules; or `"motion": "off"` with the owner's reason), which the adapters read.
7. **Type and units.** A type scale in px or rem as DTCG dimensions (`{value, unit}`). A minimum label size the book
   will hold itself to. Hairline and frame units for strokes and padding. A focus ring that passes the UI gate on both
   grounds.

## Gate

**G4 System rules.** A written plan, then an explicit GO. Every threshold is your proposal, written as one revertable
"(rule)" line in BRAND-STATE.md Notes. Pitch the list at the owner. In Quick, and for any brand without a product UI (a
bakery, a practice, a photographer), show the rules as plain-language defaults "unless you say otherwise" ("text is
easy to read on every colour we use, in light and dark"; "the logo stands out from whatever it sits on"; "the colours
stay tellable apart for people with colour-blindness") and keep the numbers in the Notes line, not in the message.
Offer the motion and script-budget rules only when something in the brand moves or ships code. For example:

- (rule) UI text at least 4.5:1, large text and UI components at least 3:1, light and dark (WCAG 2.2 AA; cannot be lowered)
- (rule) mark on its ground at least 3:1 (brand rule; logos are WCAG-exempt)
- (rule) colours that touch in the mark at least 3:1, except the pairs listed in tokens/exceptions.json with a reason
- (rule) colour-vision distance ΔE2000 at least 10 between role pairs, for protan, deutan and tritan (proposal)
- (rule) theme follows the system; `data-theme` pins light or dark (when the brand has a site or an app)
- (rule) reduced motion: nothing moves; durations `motion.quick` 160 / `base` 320 / `slow` 640 ms, `stagger` 120 ms; curves `easing.standard`, `enter` and `exit` (only when something moves)
- (rule) interactive brand pieces stay within 6 kB of script, gzipped (proposal; only when the brand ships code)
- (rule) accent and danger stay distinct (a `distinct` pair)

Record the motion answer, on or off, in `motion/motion.json` (off needs the owner's reason, in the owner's words). Then record the G4 plan with
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

## Enforcement

- `tokens` (script): Style Dictionary 5.7.0 is the only producer of colour values for code. Every emitted artefact is
  parsed back and compared with the source hex (a round trip per transform). A stored hex that is not the gamut-mapped
  oklch fails, and `--check` fails when the outputs are stale. A curve that is not four finite numbers with x1 and x2
  between 0 and 1, and a duration that is not whole milliseconds, fail it too, named by token path; the Swift and Android
  motion files are parsed back like the rest.
- `check` (script): `motion/motion.json` is validated when it exists: its schema, and every duration and curve it names
  must be a built token of that kind.
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
  stills of the motion into `motion/frames/` for the book.
- `check --cascade` (script): no current file still holds an old value.
- Prose: this file and the G4 "(rule)" list. Touch scrolling, audio and the script budget are not measured; they are
  listed in [09-qa](09-qa.md) as judgement items.
