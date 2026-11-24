# ADR-0010: The site round makes reference pages, not templates

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** [ADR-0007](ADR-0007-brand-side-of-the-web.md) (the brand side of the web, the page check, "approved pages are
  references, never templates", the description that changes with the site round); [ADR-0009](ADR-0009-website-references-before-any-site-page.md)
  (the references the round builds from); [ADR-0005](ADR-0005-motion-is-part-of-standard-and-full.md) (the motion round is
  a board of its own kind); [ADR-0002](ADR-0002-style-research-before-the-first-drawing.md) (a recorded gate, a skip only
  in the owner's words); "Page check" and "Board contract (data attributes)" in the [script contract](../../scripts/CONTRACT.md)
  (the latter says a motion board is a round from 2 on); "The fleet gate" in the
  [fleet reference](../../skills/brand-creator/references/fleet.md); the `description` in
  [the orchestrator skill](../../skills/brand-creator/SKILL.md); the [changelog](../../CHANGELOG.md). Files this decision
  adds, named here and not linked because they do not exist yet: `skills/brand-creator/references/phases/07p-site-round.md`,
  `skills/brand-creator/references/page-layouts.json`, `templates/site-board.html`, `templates/book/site.md`,
  `scripts/site_pages.py` and `scripts/boardlib/siteboard.py`.

## Context

A real brand built its site by hand, and the corrections the site needed were largely conflicts with the brand's own rules,
the kind a script can measure. Nothing measured a page against the project before the owner saw it, and nothing showed the
owner the first screen on its own before the whole site was built on it.

The recipe that came out of that work then pinned undecided defaults as instructions. A default that was never discussed was
written down as a rule, and the next page followed it as if the owner had chosen it. Nothing in the recipe said which lines
were rules and which were one example.

[ADR-0007](ADR-0007-brand-side-of-the-web.md) put the page check and the reference pages on the roadmap and left the site
round to its own record. This is that record.

## Decision

- **A new phase, P7p, after G4w.** The site round runs in Standard and Full, after the website references
  ([ADR-0009](ADR-0009-website-references-before-any-site-page.md)) and before the book, only when the brief lists a site.
  Its boards are ordinary rounds (`rounds/r<N>/board.html`, a round from 2 on, never a reset round) with
  `data-board="site"`, so the hook, `freeze`, `shot` and `check`'s latest-round logic work unchanged.
- **Hero first, in two to three variants.** The first site board shows only the hero, in two or three variants built from
  the picked references and the brand. The layout of each variant names a layout reference or `own:<word>`. A pages board
  needs an earlier hero board and names the hero the owner picked (`data-hero`); the lint enforces that.
- **Each variant is checked three ways.**
  - `brand-creator page-check`, both tiers (brand rules fail, tells warn), as in ADR-0007.
  - Stills: four first-screen views and one full page, written by `brand-creator capture` beside the page.
  - A cold review with fixed inputs and the verdict first, `ship` or `fix`, before any reasons. It runs in the thread by
    default, and `cold-review.md` says `by: in-thread`, because a review in the same thread is not blind. An agent
    (`brand-creator:brand-reviewer`, one call per hero variant) runs only after the fleet gate. The review is required on a
    hero variant and optional on a page.
- **The owner picks a hero, then the other pages are built from it.** A last board of the pages stage carries a choices
  section. Every choice is tagged `rule` or `example`. A `rule` cites where it was decided: its source text is found in
  `BRAND-STATE.md`, `DECISIONS.md` or `decisions/`. An `example` needs no source and may change. This is the provenance the
  hand-built recipe lacked.
- **Gate G4p.** The owner approves the site's reference pages, and Claude records it with `state --record G4p`. `site approve`
  needs it.
- **`site approve` writes the record.** It copies the approved pages from their round into `site/<page-id>/`, leaving out
  the round's stills and cold reviews, and writes `site/site.json`: the pages, the layout each used, a checksum of each, and
  the choices with their tags and sources. The stills are taken again in `site/` with `capture` after approval, so they
  match the approved page. `check` gates the record, the pages and the stills.
- **Layout references, structure only.** Eight to twelve layout references ship with the plugin in
  `skills/brand-creator/references/page-layouts.json`, each keyed to the visitor's job and describing structure only: what a
  page leads with, its parts, the one action and how it ends. A page may name `own:<word>` instead, with a warning, so the
  references never become a menu of templates. Every built page records the layout it used.
- **Approved pages are references, never fill-in templates.** A product repository takes the rules, and the examples show
  one way to meet them. Production sites are built in product repositories ([ADR-0007](ADR-0007-brand-side-of-the-web.md)).
- **An opt-in `site` chapter in the book** shows the approved pages and their choices.
- **The orchestrator's description changes with this record.** Website references and reference pages come in, and
  production sites stay out. The description and its trigger tests change when the plugin can run a site round, as
  ADR-0007 said they would, and the phase map gets one pointer row.

## Consequences

- A site adds two to three rounds: the website references, the hero, and the pages. All of them are optional.
- The page check from [ADR-0007](ADR-0007-brand-side-of-the-web.md) is a precondition: the round cannot run without it.
- A cold review in the thread is not independent. The record says so, and the agent needs the owner's yes at the fleet gate.
- Owners decide twice: the hero, then the pages with their choices. A recorded `rule` can be traced to the line that made it.
- The book can show the pages.
- Credit. Hero first with a cold review that answers ship or fix first, and layouts named after what the visitor came to
  do, are ideas from Hallmark (MIT); rewritten, nothing copied.

## Update 2026-11-03

The cold review answers `ship`, `fix` or `owner`, not only `ship` or `fix` as the bullet "Each variant is checked three ways" and the
Credit line above say. `owner` says that what is left is a choice only the owner can make, and its findings are written as questions to
them. A variant is reviewed at most twice per board (the first, and one after the fixes) and a third review is not run: the second may say
`owner`, and one that still says `fix` is not followed by a change of the page but by what is left going to the owner on the board. The
lint passes `owner` like `ship` and cannot count the reviews, so the cap is a rule of the phase and of the fleet gate. Everything else in
that bullet stands, including that the review runs in the thread by default and an agent only after the fleet gate. The change is
written in the [site round](../../skills/brand-creator/references/phases/07p-site-round.md#the-cold-review), in the
[fleet reference](../../skills/brand-creator/references/fleet.md#the-cold-review-of-a-site-hero-main-thread-one-reviewer-call-per-variant)
and in the [changelog](../../CHANGELOG.md).

Why: the pilot's 21 reviews showed a loop with no end: a review always finds something, so the page was fixed and read again. A verdict
that hands a choice to the owner ends the loop where only the owner can.
