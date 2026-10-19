# (Brand name): motion hand-off spec

Written only when something moves. Copy to `motion/SPEC.md`. Every value comes from the tokens (`motion.*`) or from
this file; an implementer never guesses a timing. The proof is `brand-creator shot --motion motion/proof.json`.

## Rules (the G4 "(rule)" lines this spec follows)

- Static first: the still (`assets/logo/mark.svg`) is complete without motion.
- Reduced motion (`prefers-reduced-motion: reduce`): nothing moves, no motion listener is registered, the still shows.
- Every motion ends on the rest frame; the rest frame equals the still pixel for pixel.
- Nothing loops forever. Whole pixels only. No layout shift.
- Touch never blocks scrolling. No audio before a gesture; a sound-off control also stops key listening.

## Moving parts

| Part | Selector | Element in the artwork | Units | Rest state |
|---|---|---|---|---|
| (the dot) | (`.mark [data-motion]`) | (`<g data-motion>` in `assets/logo/mark-animated.svg`) | (px at 1x) | (`rest`) |

## Timeline

| Step | Trigger | State from → to | Duration token | Curve (named) | Delay or stagger |
|---|---|---|---|---|---|
| (1) | (load / hover / press / scroll into view) | (`rest` → `press`) | (`motion.quick`) | (name) | (`motion.stagger`) |

## Reduced behaviour

(What shows instead, per part. "The still, nothing else" is the default.)

## Proof

- `motion/proof.json` cases: (one `states` case per animated file, one `page` case per page that animates the mark).
- Control pairs: (two states that must differ, so the comparison can see a difference).

## Out of scope

(What this spec does not cover, for example scroll-linked effects or sound.)
