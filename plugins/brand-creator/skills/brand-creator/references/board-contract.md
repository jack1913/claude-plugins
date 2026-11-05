# Board contract

What every round page and direction board must carry, how directions are generated, and how they are scored. The
machine-checked part (the `data-section` and `data-field` vocabulary) is defined once in
`${CLAUDE_PLUGIN_ROOT}/scripts/CONTRACT.md` ("Board contract"); `board-lint` enforces it.

## Contents

- [Two templates](#two-templates)
- [Required sections of a round page](#required-sections-of-a-round-page)
- [Style board (round 0)](#style-board-round-0)
- [Motion board (a round after G3)](#motion-board-a-round-after-g3)
- [Website references board (after G4)](#website-references-board-after-g4)
- [Site board (a round after G4w)](#site-board-a-round-after-g4w)
- [Site board, pages stage (after the owner picked a hero)](#site-board-pages-stage-after-the-owner-picked-a-hero)
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
| `templates/site-refs-board.html` | `rounds/r<N>/board.html` of a website references round | `site-refs` | groups of real sites to learn from, after G4 (Standard and Full, when the brief lists a site); linted; below |
| `templates/site-board.html` | `rounds/r<N>/board.html` of a site round | `site` | the site's first screen as two or three variants, then the other pages, after the website references pick G4w (Standard and Full, when the brief lists a site); linted; below |
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
| `direction` (repeat) | always; 3-5 on pick boards | word name (`data-name`, 3+ letters, identical in chat), no letter by default (an optional `data-letter` only when the owner asks; `board-lint` warns when it equals an option letter of a question that does not list the directions), one emotional register per direction (`data-register`), the idea, the reflex result (one line: `no hits`, or one `hit: <id> \| <argument>` per hit) |
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
and the reduced still on the card are the files `frames.json` lists, by sha256), `motion:fields` (the three fields) and
`motion:timelines` (a warning, never a failure: two variants whose current motion reports show one length, within 5 % or 20 ms,
and the same number of animations are one move tried twice, and three variants should try three moves).
Taking a proof or its stills again after the lint makes the lint report stale: lint again, and shoot the board last.

## Website references board (after G4)

`<body data-round="N" data-board="site-refs">`, from `templates/site-refs-board.html`, built on the style board's frame (the same tokens, header, theme switch, questions and reply), written in the owner's language, visual first.
It is a round from 2 on, never a reset round, in the Standard and Full tiers only, after G4, and only when `brief/BRIEF.md` lists a site under `Required surfaces:` in the owner's words (the lint reads that line
against English and Polish words; a brief in another language needs the word `site` on it, and the untouched template line, in parentheses, does not count). The owner's pick is gate G4w. It is no pick, style, reset or rejected round,
so the map, the style gate and the kept masters do not apply to it. Before it, the owner has answered the online-research question (`state --set site_research=online|links-only|none`), and `research/site-cliches.md`
(from `templates/site-cliches.md`) holds at least three site clichés under "Avoid unless argued".

| Section (`data-section`) | What it holds |
|---|---|
| `visitor-job` | who visits, the job they came to do, the one action that serves it |
| `norm` | what most sites in the category do |
| `owner-sites` | the sites the owner likes and dislikes, one `<li data-like="like">` or `"dislike"` each with a link and the owner's reason (`data-field="why"`), or one line saying the owner named none |
| `group` (repeat, 4 to 6) | `data-name` (a word, never a label such as "Group 2"), `data-field="idea"` (how the group serves the visitor's job, not a look) and `data-field="references"`: three or more real sites, each a link, a captured screenshot (`<img data-field="shot">`, inlined, in a `<figure>` whose `<figcaption>` says whose site it is and when it was captured), `data-field="take"` (structure, rhythm, how it serves the job) and `data-field="avoid"` (their look); a vote, `<fieldset data-vote="<name>">` |
| `site-cliches` | the category's site clichés, as listed in `research/site-cliches.md` |
| `none-of-these` | the way out: research again |
| `my-call` | `data-field="recommendation"` and `data-field="critique"` |
| `questions` | numbered, lettered options, exactly one recommended; question 1 (which groups) is multi-pick with checkboxes and the reply lists every ticked group; question 2 confirms the liked and disliked sites |
| `reply` | how to answer |

There is no `hardest-surface`, `today`, `strategy-core`, `positioning-map`, `direction` or `losers` section. A group is real sites opened today: never write a site, an address or a description from memory, and a screenshot is for this
private research page only, never reused in anything you build.

`board-lint` gives these rows: `site-refs:tier` (Standard or Full), `site-refs:brief` (the brief lists a site), `site-refs:g4` (G4 is recorded), `site-refs:research` (the online-research answer is recorded; `none` counts),
`site-refs:cliches-file` (three site clichés or more), the section rows, `groups:count` (4 to 6 groups: fewer fails, more warns) and `page:data-board`, which fails a references board in round 0 or 1 or in a round listed in
`reset_rounds`. The lint report lists `brief/BRIEF.md`, `research/site-cliches.md` and every `research/site-refs/*/capture.json` among its inputs, so a changed brief or cliché list, or a capture made again, makes it stale.

Each group and each reference gets rows of its own:

- `group:<name>:name`: a word of three letters or more, not a label such as "Option 2", "Group B" or "Layout 3", not another group's name in other letters.
- `group:<name>:idea`: how the group serves the visitor's job, not what it looks like.
- `group:<name>:references`: three or more sites; each has a link (the first link of the item, http or https), an inlined screenshot with alt text and a caption (`<figure>` with `<figcaption>`; the template's ` · shown for private research` is not the caption), `data-field="take"` and `data-field="avoid"` with words in them (the `Take:` and `Avoid:` label of the template does not count, with or without its colon). The row names the reference that lacks one.
- `group:<name>:layout`: only when the group has `data-layout`: an id of `page-layouts.json`, or `own:<word>` (a warning: say in the idea why none of the references fits).
- `group:<name>:shot:<k>`, one per screenshot: a warning, never a failure, unless the picture is a thumbnail or a view listed in a `research/site-refs/<name>/capture.json` (written by `brand-creator capture --url <address> --name <name>`) of the address the reference links to.
  A screenshot the owner sent has no capture and warns too; its caption says so.
- `owner-sites:items`: each site the owner named is `like` or `dislike`, has a link or an inlined image, and says why in `data-field="why"`; one line saying the owner named none passes.
- `images:inlined`: no picture on the board comes from the network.

## Site board (a round after G4w)

`<body data-round="N" data-board="site" data-site-stage="hero">`, from `templates/site-board.html`, built on the motion board's frame (the same tokens, header, hardest surface, My call, questions and reply), written in the owner's language.
It is a round from 2 on, never a reset round, in the Standard and Full tiers only, after G4 and after the owner's pick of website references (G4w; or their skip, in their own words), and only when `brief/BRIEF.md` lists a site under
`Required surfaces:`. It is no pick, style, reset or rejected round, so the map, the style gate and the kept masters do not apply to it. `data-site-stage` is `hero` (two or three variants of the home page's first screen) or `pages` (the other
pages, once the owner picked a hero); a page with none, or another value, fails `page:site-stage`. A G4w that names a pick needs the website references board in an earlier round.

One folder per variant of the hero stage, `rounds/r<N>/<name>/`, made before the page: `index.html`, the home page's first screen, built from the picked references and the tokens. Its `<body>` declares `data-layout` (an id of
[page-layouts.json](page-layouts.json), or `own:<word>`) and `data-page` (`start` for the home page).

| Section (`data-section`) | When | What it holds |
|---|---|---|
| `what-changed` | from the second board of a stage | "What changed since the review", the owner's numbered items first |
| one card per variant | always: 2 or 3 on the project's first hero board, 1 or more on a later one | below |
| `hardest-surface` | always | the one view where the page is hardest to get right (for example the 390 px phone in dark), and what the checks show there |
| `weak-points` | from the second board of a stage | honest weak points, with a number where possible |
| `my-call` | always | as on every board |
| `questions` | always | as on every board; question 1 asks which hero goes forward and lists their names, one option combines two, one says none of these |
| `reply` | always | how to answer: a variant name, or question number plus option |

The card, an element with `data-site-variant="<name>"` (a word, never a label such as "Variant 2", also the name of the folder), holds the four stills of the first screen (`<img data-field="still" data-view="1440-light|1440-dark|390-light|390-dark">`),
the live link (`<a data-field="live" href="<name>/index.html">`), a check line (`data-check="pass|fail"` and its text), `data-field="idea"` (the one memorable idea of the hero, in one line), `data-field="what-it-is"`, `"from-refs"` (the group of the references board, or the owner's site, the structure is taken from:
never their look) and `"cost"`, the tells found and the reflex line (`data-field="tells"`, `"reflex"`), the layout line (`data-field="layout"` with the `data-layout` the page declares), a cold line (`data-cold="ship|fix|owner"`) and a vote (`<fieldset data-vote="<name>">`).
There is no `positioning-map`, `strategy-core`, `today`, `losers`, `none-of-these` or `direction` section. The pages stage has its own cards and a `choices` section (see "Site board, pages stage" below).

`board-lint` gives these rows: `site:tier` (Standard or Full), `site:brief` (the brief lists a site), `site:g4` (G4 is recorded), `site:g4w` (the pick, or the skip, is recorded; a pick has its references board), `site:variants` (2 or 3 variants on the
first hero board, a word for each name), `site:files` (each variant's folder, spelt as the card spells it, letter case included; its `index.html`; the `<body>` declaring `data-layout` and `data-page`; the live link), `site:layout` (the page's layout is a
layout reference, or `own:<word>` with a warning, and the card says the same), `site:fields` (What it is, Takes from and Cost are filled in; the Idea line of a hero card is filled in too), the section rows and `page:data-board`, which fails a site board in round 0 or 1 or in a round listed in
`reset_rounds`. The pages stage is read by its own rows (see "Site board, pages stage" below). The lint report lists `brief/BRIEF.md`, the references board G4w stands on and the
`index.html` of each variant among its inputs, so a changed file makes it stale.

Each variant brings its proof before the board is shown. Run `brand-creator page-check rounds/r<N>/<name>/index.html` and `brand-creator capture rounds/r<N>/<name>/index.html` on the page as it is, then write the card from what they found; a change to the page, to `tokens.css` or to a file the page loads makes both stale. A page that shows content only when scrolled to (an `IntersectionObserver`, a class a scroll handler adds, `data-reveal`) is captured with `capture ... --reveal`, so that its stills show the revealed page; the card says so on its check line ("stills taken with --reveal"), and `capture.json` records it (`reveal`; `reveal.capped` true means the page is longer than the walk, so say that too).
`board-lint` gives three more rows for the cards: `site:check` (the page's page-check report is there, is the report of this page, is current and is a verdict, and the card's check line says its status: a failing check shown as `fail` is honest and passes),
`site:tells` (every `tell:<id>` warning of that report is named by its id on the card's tells line, with what you will do about it; a warning with `hits: []` means page-check could not check the page for that tell, and the row says it could not verify it, not that it found it) and `site:stills` (`shots/capture.json` is current and is the capture of this page, and the four stills on the card are the bytes it lists:
the project's files by a relative path, or on a review copy `data:` URIs of the same bytes). A variant with no current report is not judged for its tells: `site:tells` is "not verified" then, and `site:check` says why. The lint report lists the reports, `capture.json`, the stills and the files they were made from among its inputs.

Each hero also answers three more questions, and `board-lint` reads each answer. The reflex line of the card (`data-field="reflex"`) is written as on a style board's direction: `no hits`, or one `hit: <id> | <argument>` per hit, where the id is a tell of
[page-tells.json](page-tells.json), an id of [ai-defaults.json](ai-defaults.json) (its layout items name the stock product page) or an item of `research/site-cliches.md`, and `near miss: <id> (<why>)` for a pattern that looks close and is not one.
A card with no reflex line, or an empty one, fails `site:<name>:reflex` (the line is required, as on a style board's direction): deleting it is no way round the rows below. The rows are `site:<name>:reflex-format`, `site:<name>:reflex-ids` and `site:<name>:reflex-grounded` (warnings for now, "a failure from the next release"), `site:<name>:reflex-count` (two hits on one hero fail: replace a part before showing it) and
`site:reflex-shared` (it fails when every hero hits one pattern, so the heroes are not divergent). `site:<name>:reflex-measured` warns when page-check measured a tell on the page (a `tell:<id>` warning of its report) that the reflex line neither
hits nor names as a near miss: argue it on the card, or change the page (when the warning has `hits: []`, page-check could not verify the tell and the row says so; the ask is the same). `site:refs` holds the Takes from line of each card to what the owner picked: it must name a group of the references board, or a site the owner liked, that the G4w record names too
(a whole word, any letter case; what the record says after `dislikes` is not a pick); a skip in the owner's words makes it an info row. `site:cold` reads `rounds/r<N>/<name>/cold-review.md` of each hero: its first line is `verdict: ship`, `verdict: fix` or `verdict: owner`, it has a `by:` line, its `inputs:` list is exactly the
four stills, `brief/BRIEF.md` and `FACTS.md` with the sha256 each had when the review was made (the page, its stills, the brief or the facts changed since: review again), it has at most five findings, and the card's cold line (`data-cold`) says the same
verdict. A `fix` shown as `fix` is honest and passes, and so does an `owner` shown as `owner` (what is left is a choice only the owner can make, its findings written as questions to them; at most two reviews are run per variant per board, which the lint cannot count). The prompt for the review is in [prompt-fragments.md](prompt-fragments.md) (**Review**). The lint report lists `FACTS.md`, `research/site-cliches.md` and each `cold-review.md` among its inputs.

## Site board, pages stage (after the owner picked a hero)

`<body data-round="N" data-board="site" data-site-stage="pages" data-hero="<name>">`, the same template with the three comments at its end put to use: the pages section in place of the variants, the choices section after Weak points, and two questions in place of "Which hero goes forward?".
`data-hero` is the name of the variant card, on a hero board of an earlier round, that the owner picked (or combined into a new variant): hero first. The gates, the sections and the vote groups are those of the hero stage.

One folder per page, `rounds/r<N>/<id>/`, made before the board, with the files of a variant's folder (`index.html` declaring `data-layout` and `data-page`, `shots/` from `brand-creator capture`, and `cold-review.md` if the page was read cold). The page id is lowercase letters, digits and `-`
(2 to 32 characters, starting with a letter: `start` for the home page, `pricing`), and the same in three places: the folder, the card's `data-site-page` and `<body data-page>`.

| Section or card | When | What it holds |
|---|---|---|
| one card per page (`data-site-page="<id>"`) | always, at least one | the four stills, the live link, the check line, the Idea line (`data-field="idea"`: the page's one idea in the brand's world; a warning when missing in 0.8.0, a failure from the next release), What it is, Cost, the tells line, the layout line and a vote, as a variant's card; Takes from and the cold line are optional; no reflex line |
| `choices` | always | every structural and visual choice the pages make, one `<li data-choice="c1" data-tag="rule\|example" data-source="..." data-pages="start pricing">` each |

Before the page cards the board writes the hero's motifs down as a short system (its own shapes, devices and the move, one line each; prose, not linted), and every page uses at least one of them for its own job. A form stays straight (a tilt or a drawing goes around a form, never on it).

A **rule** is a choice the owner decided and the brand keeps: its `data-source` quotes, word for word, the line of `BRAND-STATE.md`, `DECISIONS.md` or `decisions/*.md` where they decided it, so write the decision down first. An **example** may change and needs no source. The questions ask the owner to approve the pages and to confirm the tags.
`data-pages` names the pages a choice applies to (all of them, when the attribute is left out). The board is written in the owner's language like every board.

`board-lint` gives these rows on top of the gates and the sections: `site:hero-first` (a hero board came before, and `data-hero` names one of its variant cards), `site:pages` (at least one page card; its id is a page id, unique, and the same as the page's `data-page`), the rows of the hero cards that fit a page (`site:files`, `site:layout`, `site:fields` with Takes from only where the card has the line, and a warning for a page card without its Idea line; line,
`site:check`, `site:tells`, `site:stills`; `site:cold` only for a page that has a cold review) and `site:choices` (an id `c1`, `c2` ..., unique; some text; a tag; a rule's source found in `BRAND-STATE.md`, `DECISIONS.md` or `decisions/*.md`; `data-pages` naming only pages of this board), and `section:choices`.
There are no reflex rows and no `site:refs` on a page: the hero carried them. The lint report lists the hero board, `DECISIONS.md`, `decisions/*.md` and each page's `index.html` among its inputs.

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
- the reflex test result against [ai-defaults.json](ai-defaults.json) and the project's `research/cliches.md` ("Avoid
  unless argued"), as one line: `no hits`, or one `hit: <id> | <argument>` per hit, the argument naming something of this
  brand from FACTS.md or the brief. A pattern that looks close and is not one goes in as `near miss: <id> (why)`; it is
  recorded and never counted. `board-lint` fails a direction with two hits and a board whose directions all hit one
  pattern, and warns about a line that is not in this format, a hit that names no known pattern and an argument that
  shares no word with FACTS.md or the brief (warnings that become failures in the next release);
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
never do that. The judge also lists, for each direction, the ai-defaults ids and `research/cliches.md` items it sees:
put that list beside the direction's reflex line as `data-field="reflex-seen"` (`judge saw: <id>; <id>`, or `judge saw:
none seen`; the templates carry the line in a comment to uncomment). With `data-judge="ran"` the lint warns about a
direction with no list (a list that is only its label, with no pattern and no `none seen`, is none), and about a pattern on the list that the reflex line neither hits nor names as a near miss: argue
it as a hit, or say why it is a near miss. Both warnings become failures in the next release.

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
