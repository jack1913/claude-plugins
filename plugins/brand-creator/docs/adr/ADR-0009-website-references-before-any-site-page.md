# ADR-0009: Website references come before any site page

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** [ADR-0002](ADR-0002-style-research-before-the-first-drawing.md) and the
  [style research phase](../../skills/brand-creator/references/phases/01s-style-research.md); [ADR-0005](ADR-0005-motion-is-part-of-standard-and-full.md)
  (the motion round is a board of its own kind); [ADR-0007](ADR-0007-brand-side-of-the-web.md) (website references are
  part of the brand side of the web); "Board contract (data attributes)" in the [script contract](../../scripts/CONTRACT.md)
  (a motion board is a round from 2 on); "Privacy of candidate names" in the
  [fleet reference](../../skills/brand-creator/references/fleet.md); the [changelog](../../CHANGELOG.md). Files this decision adds, named here and not linked because they do not exist yet:
  `skills/brand-creator/references/phases/07w-website-references.md`, `templates/site-refs-board.html`,
  `templates/site-cliches.md`, `scripts/boardlib/siteboard.py`, and the `capture` command in `scripts/render.mjs`.

## Context

A real brand's site was built by hand. Nothing in the project had decided how the site should be laid out, so the build
started from a default, and the owner approved that default in one word. The corrections that followed were about the
structure of the site, not about the brand's marks or colours.

The owner then asked for the step that was missing: to be asked which sites they like and dislike, or to be offered
research into the best real sites for the same kind of visitor, with a gate that is recorded the way G1s records the style
pick ([ADR-0002](ADR-0002-style-research-before-the-first-drawing.md)).

Searching for sites tells search services what the brand makes. The naming step already asks the owner before it does that
for candidate names, so this step has to ask too.

## Decision

- **A new phase, P7w, after G4.** Website references run in Standard and Full, after G4 and the motion round, only when the
  brief lists a site. They are never offered otherwise; the owner may add a site to the brief in their own words. The
  `Required surfaces:` line of `brief/BRIEF.md` is read with an English and a Polish word list; a brief in another
  language is reported as not verified, and the owner adds the word `site` to the line.
- **A board of its own kind.** `data-board="site-refs"` is an ordinary round (`rounds/r<N>/board.html`, a round from 2 on,
  never a reset round, like the motion board), so the hook, `freeze`, `shot` and the review surface work unchanged. It
  shows:
  - the visitor's job, taken from the brief and `FACTS.md`;
  - the category's site norm, counted from real sites opened that day;
  - the sites the owner likes and dislikes;
  - four to six groups, each a way of serving the visitor's job and never a look, with three or more real sites each and a
    captured screenshot of every one.
  For each group, **take** is structure, rhythm and how the site serves the job; **avoid** is its look: colours, type,
  imagery and wording.
- **The category's site clichés** go in `research/site-cliches.md`, under "Avoid unless argued". The hero variants of the
  site round use them in their reflex test ([ADR-0006](ADR-0006-reflex-test-checked-beyond-presence.md)).
- **The online-research OK is a recorded key.** `site_research` is `auto` (not asked), `online`, `links-only` or `none`.
  It is asked once, with the owner's answer recorded by `state --set`, and never asked again.
- **`brand-creator capture --url` is the only path that lets Chromium reach the network.** It refuses to fetch anything
  unless `site_research` is `online` or `links-only`. It writes the screenshots, small thumbnails the board inlines, and a
  `capture.json` beside them, in `research/site-refs/<name>/`. Claude never captures a page behind a login; the command
  cannot tell.
- **Gate G4w.** The owner picks one or more groups, or "none: research again", and confirms the liked and disliked sites.
  Claude records it with `state --record G4w`. The owner may skip the step, only in their own words, and Claude records
  "skipped by owner"; Claude never skips for them. The site round waits for G4w.
- **No invented reference.** Without web access Claude says the step needs it and stops. It never writes a site, an
  address or a description from memory. A screenshot on the board is matched to a `capture.json` thumbnail of the same
  address by its bytes; a screenshot that matches none is a warning ("not matched to a capture"), never silent. The
  screenshots the owner sent are kept apart, in `research/site-refs/owner/`, and the board says so in the caption.
- **A deliberate difference from ADR-0002: no re-arm.** After a full rejection ADR-0002 arms G1s again, so that the first
  pick cannot stand in for a new style pick. The site round is optional and late, so a full rejection of the site round's
  hero variants ("None of these" on a `data-board="site"` board) does not arm G4w again. The owner chooses new variants,
  or a new references board and a new G4w. The "none: research again" answer on the references board itself is a different
  case, covered by the G4w bullet. This is judgement, not a lint row.

## Consequences

- The owner answers one more board, and one more question before it.
- The step needs web access for the research. With only the owner's links, or only their screenshots, it still runs.
- A reference's screenshot stays on the research page, for private research. It is never reused in a page the plugin draws.
- The site round waits for G4w. A project that has no site in its brief is not asked.
- `capture` is the one command that reaches the network, so it is the one place to audit for what leaves the machine.
- Credit. The idea of starting a page from the visitor's job comes from Hallmark (MIT, Hallmark contributors), read on
  2026-10-29; nothing was copied.
