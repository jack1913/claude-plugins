# Board contract

What every round page and direction board must carry, how directions are generated, and how they are scored. The
machine-checked part (the `data-section` and `data-field` vocabulary) is defined once in
`${CLAUDE_PLUGIN_ROOT}/scripts/CONTRACT.md` ("Board contract"); `board-lint` enforces it.

## Contents

- [Two templates](#two-templates)
- [Required sections of a round page](#required-sections-of-a-round-page)
- [Per-direction cells](#per-direction-cells)
- [Territory card (round 2+ and resets)](#territory-card-round-2-and-resets)
- [Generation prompts](#generation-prompts)
- [Scoring: judge rubric and icon matrix](#scoring-judge-rubric-and-icon-matrix)
- [First icon round checklist](#first-icon-round-checklist)
- [Variants, demos and A/B sections](#variants-demos-and-ab-sections)
- [Self-contained pages](#self-contained-pages)

## Two templates

| Template | Copied to | Kind | Use |
|---|---|---|---|
| `templates/round-page.html` | `rounds/r<N>/board.html` | `pick` (round 1, resets) or `refine` | the page the owner reviews; linted |
| `templates/board.html` | `rounds/r<N>/<direction>/board.html` | `refine` | one direction in depth (Standard, Full); can serve as the round page of a one-direction refine round |
| `templates/review/index.html` | `review/index.html` | same as the round | the stable review page, regenerated every round, published to one URL |

Fill every `[[fill: ...]]` marker; `board-lint` fails on any that remain (in text or attributes; HTML comments are
ignored). Delete optional blocks you do not use rather than leaving them empty.

## Required sections of a round page

| Section (`data-section`) | When | What it holds |
|---|---|---|
| `what-changed` | round 2+ | "00 What changed since the review": one line per change, owner's numbered items first |
| `today` | an incumbent exists | "0 Today": the current mark or site as variant 0, judged by the same criteria |
| `strategy-core` | round 1 | the 7 fields of [strategy-core.md](strategy-core.md), drafted by you, for reaction |
| `positioning-map` | round 1 and `reset_rounds` | two named axes, the category norm, every direction placed (`data-direction`), at least one far (`data-far="true"` on the direction); in resets also where the failed round sat (`data-field="failed-round"`) |
| `direction` (repeat) | always; 3-5 on pick boards | word name (`data-name`, 3+ letters, identical in chat), optional letter, one emotional register per direction (`data-register`), the idea, the reflex result |
| `hardest-surface` | always | every direction on the one surface most likely to break it (from BRIEF or INVENTORY.md) |
| `weak-points` | round 2+ | honest weak points, measured where possible |
| `losers` | round 2+ | each losing candidate (`data-section="loser"`) with a one-line reason |
| `none-of-these` | pick boards | the explicit way out: say so and what was missing; the next round resets |
| `my-call` | always | your recommendation and an honest critique (of the owner's earlier pick, or of your own pick in round 1); with `data-judge="ran"` also judge view, lead view and a middle option |
| `questions` | always | numbered questions (`data-n`), each with lettered options (`data-option="a"`...), one marked recommended |
| `reply` | always | how to answer: a name or letter and one sentence; batched answers welcome ("1a 2c") |

Also carry, where they apply (not linted): a keep / drop / unsure vote per territory, "Decisions for you" from the
review pass (as questions), and "why this is not <sibling>" in family modes. If today's mark still wins, say so on
the board.

## Per-direction cells

On the round page, every direction shows at least:

- the idea in one sentence and its **named visual philosophy** (one line, decided before drawing);
- best for / risk;
- mark at real sizes (16, 32, 64, 180) on light and dark, primary and reversed;
- wordmark or lockup;
- palette with role names (not just swatches) and computed contrast for the main pairs;
- type specimen with the audience's diacritics (the glyph set from G0), a pangram;
- two or three sample lines in the brand voice, one of them an error-page line;
- the reflex test result against [ai-defaults.json](ai-defaults.json): "no hits", or each hit with its argument;
- in family modes: what it keeps from the family layer, what it owns, why it is not a sibling.

A deep board (`templates/board.html`) adds: a real hero with the owner's copy, homepage at desktop and mobile width,
components, footer register, a business card, a social post, the product block in family modes, and per variant
what it is, its cost (JS, effort) and its degrade path.

## Territory card (round 2+ and resets)

Idea / Type / Colour / Devices / Sample lines / Built on / Strongest with / Watch out. Place each territory on named
spectrums (for example institutional ↔ personal, quiet ↔ loud) with a visual gesture and a verbal one.

## Generation prompts

- One territory rooted in **place, heritage or craft**: the brand's city, material, trade, history.
- **One direction per emotional register** (for example trust, noble, friendly, bold). A single adjective from the
  owner can open a new territory; take it literally and build it.
- A **named visual philosophy** for each direction before drawing, in one line.
- At least one direction **far from the category norm** on the map.
- **Archetype** is optional, a one-line hint at most. If every direction shares one archetype, they are not divergent.
- Every prompt carries DECISIONS ALREADY MADE, FORBIDDEN (from `research/cliches.md`, BRIEF and the never-borrow
  list) and VERIFIED FACTS (from FACTS.md); see [prompt-fragments.md](prompt-fragments.md).
- Design mark, wordmark, type, colour and hero together: a system, never a lone logo.

## Scoring: judge rubric and icon matrix

The judge (your own comparative read in single-thread, or a judge agent) is **advisory**. The owner's taste decides.

**Rubric per direction:** distinctness, coherence, mark at 16 and at 180, contrast, fit to brief and gating goal,
build effort, biggest weakness and its fix, rank, what to graft from the others. From round 2 the judge also scores
the current round against the previous round and the best so far on the same rubric, and returns a numbered MUST-FIX
list plus an optional NICE list.

**Icon matrix** (when the mark is an app or product icon), 1-5 each, out of 25:

| criterion | question |
|---|---|
| recognisable | still itself at 20 px on a real downscale? |
| unique | distinct from 5 named competitors placed next to it? |
| says the job | does it hint at what the product does? |
| family fit | belongs with the siblings (family modes; else score fit to the brief) |
| pair distinction | distinct from its paired or companion mark, if any |

Score `unique` from a lineup, not from memory: each candidate icon beside the five competitors' icons on a home-screen or
dock mock at real size, light and dark.

When a judge ran, My call shows the judge view, your view and a middle option side by side: set `data-judge="ran"` on the
`my-call` section and fill the template's three panels (`data-field="judge-view"`, `"lead-view"`, `"middle-option"`). The lint
checks the panels only when `data-judge="ran"` is set, so a judge result folded in as a plain paragraph passes it unseen;
never do that.

## First icon round checklist

Real downscale (not a scaled preview), accent minimum met, graphics at least 3:1 against their ground, light and dark
grounds, no accent-coloured text, no invented claims in mock copy, the silhouette readable at 16.

## Variants, demos and A/B sections

- Pages accept `?t=light|dark` (theme) and `?v=N` (variant) and include a replay control when anything moves.
- Per variant: what it is, its cost (JS, effort) and its degrade path (what remains with no JS and with reduced
  motion).
- A deliberate A/B section is allowed for one contested option.
- Interactive options are switchable demos. An option that bends a brand rule is labelled so on the board, and if it
  is picked, the rule change cascades with it ([cascade.md](cascade.md)).

## Self-contained pages

Fonts and images inline, no network requests, no external scripts; light and dark through tokens; works at 390 px
without horizontal scroll. One page may hold several directions. `shot` reports overflow, console errors, requests,
broken images and forbidden-string counts in four views; read the slices before saying anything about the look.
