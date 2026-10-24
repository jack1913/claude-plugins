# Board contract

What every round page and direction board must carry, how directions are generated, and how they are scored. The
machine-checked part (the `data-section` and `data-field` vocabulary) is defined once in
`${CLAUDE_PLUGIN_ROOT}/scripts/CONTRACT.md` ("Board contract"); `board-lint` enforces it.

## Contents

- [Two templates](#two-templates)
- [Required sections of a round page](#required-sections-of-a-round-page)
- [Style board (round 0)](#style-board-round-0)
- [Motion board (a round after G3)](#motion-board-a-round-after-g3)
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
| `templates/style-board.html` | `rounds/r0/board.html` (after a full rejection also `rounds/r<N>/board.html` of a reset round) | `style` | the style research page before anything is drawn (P1s, every tier); linted; the owner's pick is gate G1s |
| `templates/motion-board.html` | `rounds/r<N>/board.html` of a motion round | `motion` | the brand's signature move as variants, after G3 (Standard and Full: every brand unless nothing moves; Quick: when something moves); linted; below |
| `templates/board.html` | `rounds/r<N>/<direction>/board.html` | `refine` | one direction in depth (Standard, Full); can serve as the round page of a one-direction refine round |
| `templates/review/index.html` | `review/index.html` | same as the round | the stable review page, regenerated every round, published to one URL; for a style board (round 0) the page is a copy of the style board instead (`cp rounds/r0/board.html review/index.html`, then `board-lint review/index.html --round 0`) |

Fill every `[[fill: ...]]` marker; `board-lint` fails on any that remain (in text or attributes; HTML comments are
ignored). Delete optional blocks you do not use rather than leaving them empty.

## Required sections of a round page

| Section (`data-section`) | When | What it holds |
|---|---|---|
| `what-changed` | round 2+ | "00 What changed since the review": one line per change, owner's numbered items first |
| `today` | an incumbent exists | "0 Today": the current mark or site as variant 0, judged by the same criteria |
| `strategy-core` | round 1 | the 7 fields of [strategy-core.md](strategy-core.md), drafted by you, for reaction |
| `positioning-map` | round 1 and `reset_rounds` | two named axes, the category norm, every direction placed (`data-direction`), at least one far (`data-far="true"` on the direction); in resets also where the failed round sat (`data-field="failed-round"`) |
| `direction` (repeat) | always; 3-5 on pick boards | word name (`data-name`, 3+ letters, identical in chat), no letter by default (an optional `data-letter` only when the owner asks; `board-lint` warns when it equals an option letter of a question that does not list the directions), one emotional register per direction (`data-register`), the idea, the reflex result |
| `hardest-surface` | always | every direction on the one surface most likely to break it (from BRIEF or INVENTORY.md) |
| `weak-points` | round 2+ | honest weak points, measured where possible |
| `losers` | round 2+ | each losing candidate (`data-section="loser"`) with a one-line reason |
| `none-of-these` | pick boards | the explicit way out: say so and what was missing; the next round resets |
| `my-call` | always | your recommendation and an honest critique (of the owner's earlier pick, or of your own pick in round 1); with `data-judge="ran"` also judge view, lead view and a middle option |
| `questions` | always | numbered questions (`data-n`), each with lettered options (`data-option="a"`...), exactly one marked recommended (zero or two fail `board-lint`); the question that lists the directions shows their names |
| `reply` | always | how to answer: "Answer with a direction name, or question number plus option (1a)" and one sentence; batched answers welcome ("1a 2c") |

Also carry, where they apply (not linted): "Decisions for you" from the review pass (as questions), and "why this is not
<sibling>" in family modes. If today's mark still wins, say so on the board.

A keep / drop / unsure vote per card (a direction, a territory or a variant) is optional, and `board-lint` checks it when it is
there (`page:votes`, on every kind of board): the radios of a card are named `vote-<name>`, the name as written in its
`data-vote`, letter case included, a group of their own per card: two cards that share a name are one group, and a vote on one clears the other.
The row fails a board whose cards share a radio name, or whose radios are not named after their card, names the cards and the fix.

## Style board (round 0)

`<body data-round="0" data-board="style">`, written in the owner's language, visual first (colour strips, short lines,
no dense tables). It carries no drawn mark; round 1 starts after the owner's pick (G1s). After a full rejection the style
research runs again: a new style board goes in the next round, which is added to `reset_rounds`, and the pick board of the
new territories follows in the round after it (also listed), once the owner's new pick is recorded. The style board is
required then: "skipped by owner" is for the first pick board only, and `board-lint` fails a reset round's pick board
(`project:style-gate`) that has no newer style board, or no newer pick behind it. The lint accepts a style board in round 0
and in a round listed in `reset_rounds`, and nowhere else; a pick board belongs to round 1 or to a reset round, and later
rounds are refine boards.

| Section (`data-section`) | What it holds |
|---|---|
| `audience` | who sees the mark and what they expect |
| `surfaces` | where it is seen, the hardest one named |
| `norm` | the category norm and what to avoid |
| `territory` (repeat, 4 or more) | `data-name` (a word of 3+ letters, never a label such as "Style 2"), `data-field="idea"`, optional `data-field="per-item"` (a family of marks), and `data-field="references"`: a list of 3+ `li`, each with an `<a href="https://...">` and a `data-field="take"` (what to take, what to avoid), and where an image of the real mark could be fetched a thumbnail (below) |
| `none-of-these` | the way out: research again |
| `my-call` | `data-field="recommendation"` and `data-field="critique"` |
| `questions` | numbered, lettered options, exactly one recommended; question 1 (which territories) is multi-pick with checkboxes and the reply lists every ticked style; with several marks in the brief one question asks shared style or per item |
| `reply` | how to answer |

**Thumbnails.** Visual first means each reference shows its real mark where one can be fetched: from official images (the
reference's own site or press page), from Wikimedia Commons images, or from a screenshot. Save the original under `research/style-thumbs/`, downscale a copy to about
240 px wide and inline it: `<img data-field="thumb" src="data:image/...;base64,..." alt="the mark in words">` in a `<figure>` with a
`<figcaption>` that says whose mark it is, where the image is from and that it is shown for private research (in the owner's
language). `board-lint` fails a thumbnail whose `src` is not an inlined `data:image/` URI, that has a `srcset`, that has no alt
text, or whose `<figure>` has no non-empty `<figcaption>` (it does not look for particular words); on a style board it also fails
any other `<img>` whose `src`, and any `srcset` on an `<img>` or `<source>`, is not an inlined `data:image/` URI. A reference with
no fetchable image simply has none. A thumbnail is for the research page only: never reuse a reference's mark, or a part of it,
in anything you draw.

## Motion board (a round after G3)

`<body data-round="N" data-board="motion">`, from `templates/motion-board.html`, built on the round page's frame (the same
tokens, header, hardest surface, My call, questions and reply). It is a round from 2 on, in any tier, once G3 is recorded:
Standard and Full run one for every brand unless the owner records that nothing moves ([07-tokens](phases/07-tokens.md),
"The motion round"), Quick only when something moves. It is no pick, style, reset or rejected round, so the map, the style
gate and the kept masters do not apply to it.

One folder per variant, `rounds/r<N>/<name>/`, made before the page: `index.html` (the move where it will be seen, the
approved mark in place), `proof.json` (one page case named `<name>`, its page that `index.html`, its `static` an approved
master of `assets/logo/`) and, in `frames/<name>/`, the stills of `frames rounds/r<N>/<name>/proof.json --count 25`; and the
reports of `shot --motion` and of `frames` on that proof.

| Section (`data-section`) | When | What it holds |
|---|---|---|
| `what-changed` | from the second motion board | "What changed since the review", the owner's numbered items first |
| one card per variant | always: exactly 3 on the project's first motion board, 1 or more on a later one | below |
| `hardest-surface` | always | the one place the move is hardest to get right, and what the proof measured there for each variant |
| `weak-points` | from the second motion board | honest weak points, measured where possible |
| `my-call` | always | as on every board |
| `questions` | always | as on every board; question 1 asks which variant goes forward and lists their names, one option combines two, one says none of these |
| `reply` | always | how to answer: a variant name, or question number plus option |

There is no `today`, `strategy-core`, `positioning-map`, `direction`, `losers` or `none-of-these` section.

**The variant card** is an element `data-motion-variant="<name>"` (a word of 3 or more letters, never "Variant 2", unique,
and also the folder name) that holds:

- the strip (`<img data-field="strip">`, `<name>/frames/<name>/strip.png`) and the still under reduced motion
  (`<img data-field="reduced">`, `reduced.png`), by relative path, or as `data:` URIs of the same bytes on the review copy
  (`review/index.html`, linted with `--round N`);
- a link to the live page (`<a data-field="live" href="<name>/index.html">`): the board has no replay;
- the proof line, an element `data-proof="pass"` or `"fail"` with its text, saying what `shot --motion` found. It must say
  what the report says: a failing proof labelled `fail` is honest and passes the lint, labelled `pass` it fails it;
- What it is, Cost and Degrades to (what remains with no script and with reduced motion): `data-field="what-it-is"`,
  `"cost"` and `"degrades-to"`, filled, with no marker left;
- the vote, `<fieldset data-vote="<name>">`, as on the round page (`page:votes` checks it, as on every board).

`board-lint` gives one row per rule, each one result for the whole board that names the variants it fails: `motion:g3` (G3
is recorded), `motion:off` (`motion/motion.json` does not say nothing moves), `motion:variants` (the count, and a word name
each), `motion:files` (each variant's folder, spelt as the card spells it, letter case included, its page and proof: the proof's page is that `index.html`, and a proof copied from
an earlier round and still pointing there fails), `motion:proof` (a current motion report of each proof, and the card's proof
line equals its status; a missing or stale one names `brand-creator shot --motion rounds/r<N>/<name>/proof.json`; a report
that is not a verdict quotes the rows it could not verify, and for a move driven by `requestAnimationFrame`, which
stays not verified, says to write it as CSS animations, transitions or `element.animate()`),
`motion:stills` (a current passing `frames` report of each proof, so the stills are of the page as it is now, and the strip
and the reduced still on the card are the files `frames.json` lists, by sha256) and `motion:fields` (the three fields).
Taking a proof or its stills again after the lint makes the lint report stale: lint again, and shoot the board last.

## Per-direction cells

On the round page, every direction shows at least:

- the idea in one sentence and its **named visual philosophy** (one line, decided before drawing);
- best for / risk;
- mark at real sizes (16, 32, 64, 180) on light and dark, primary and reversed;
- wordmark or lockup;
- palette with role names (not just swatches) and computed contrast for the main pairs;
- type specimen with the audience's diacritics (the glyph set from G0), a pangram;
- two or three sample lines in the brand voice, one of them for a moment when something goes wrong, in the brand's own world:
  an error page for software, "sold out today" or "closed for a holiday" for a shop, "running late" for a practice;
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
