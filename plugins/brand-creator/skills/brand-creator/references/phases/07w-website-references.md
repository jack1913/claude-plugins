# P7w Website references (before any page of the site is built)

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [No web access](#no-web-access)
- [The online-research question](#the-online-research-question)
- [Techniques](#techniques)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

A site built by hand from an undecided default, approved in one word, is how a real brand's site went wrong: the
corrections were about the structure of the site, not about the marks or the colours. P7w puts the structure question
first. Before any page of the site is built, the owner says which sites they like and dislike, or lets you research the
best real sites that serve the same visitor's job, and picks the ways of serving that job to build from.

The deliverable is one visual page, the website references board, with 4 to 6 **groups** of real sites. A group is a way
of serving the visitor's job, never a look. Each group holds 3 or more real sites, each with a captured screenshot, what
to **take** (structure, rhythm, how it serves the job) and what to **avoid** (their look: colours, type, imagery, their
words). The owner picks one or more groups, or "none: research again". The step mirrors the style research
([01s-style-research](01s-style-research.md)): a board, a recorded gate, a skip only in the owner's words, no invented
reference, and a stop without web access.

**When:** Standard and Full, after G4 and the motion round, and **only when the brief lists a site** (a site under
`Required surfaces:` in `brief/BRIEF.md`, in the owner's words). Never offer it otherwise. The owner may add a site to
the brief in their own words, and then the step applies. Quick never runs it.

## Inputs

- `brief/BRIEF.md` and `FACTS.md`: who visits, what they come to do, the surfaces (the `Required surfaces:` line is what
  the lint reads), the facts a page may state.
- G4 recorded (`state --project <dir> --require G4`; exit 1: the system rules are not approved yet, say so and stop). The
  tokens and rules of G4 are what the site is built in; this step takes none of its look from a reference.
- The sites the owner named, liked or disliked, as links or screenshots. If a named site may be the owner's own, say so on
  the board and ask in its questions.
- `site_research` in BRAND-STATE.md (`auto`, or not set in an older project, until the owner is asked): the answer decides
  what you may open.
- [page-layouts.json](../page-layouts.json): the layout references keyed to the visitor's job, for a group's
  `data-layout` when one fits.

## Outputs and paths

Commands are written after `brand-creator --data "${CLAUDE_PLUGIN_DATA}"`.

| Output | Path |
|---|---|
| Website references board (the page the owner sees) | `rounds/r<N>/board.html`, from `${CLAUDE_PLUGIN_ROOT}/templates/site-refs-board.html` (`data-board="site-refs"`); N is 2 or more and a new, empty folder, never a copy of an earlier round |
| The same page on the review surface | `review/index.html`, a copy of the board (`cp rounds/r<N>/board.html review/index.html`), linted with `board-lint review/index.html --round <N>` |
| The sites you captured, one folder each | `research/site-refs/<name>/`: `1440.png`, `390.png`, `1440-full.png`, `thumb-1440.jpg`, `thumb-390.jpg`, `capture.json` (from `capture --url`) |
| Screenshots the owner sent (not captured) | `research/site-refs/owner/` |
| The category's site clichés | `research/site-cliches.md`, from `${CLAUDE_PLUGIN_ROOT}/templates/site-cliches.md` |
| Notes behind the board (claims with URLs and the date read) | `research/YYYY-MM-DD-site-refs.md` |
| The online-research answer | `BRAND-STATE.md` → `site_research` (`state --set site_research=online\|links-only\|none`) |
| G4w record | `BRAND-STATE.md` → `gates.G4w` (`state --record G4w "<decision>"`) |

Set the phase as you go (`state --project <dir> --set phase=P7w`). A references board is an ordinary round from 2 on, so
the hook, `freeze`, `shot` and the review surface work unchanged; it is no pick, style or reset round, and the style gate
ignores it.

## No web access

The research needs web access: searching for the category's real sites, opening each one, capturing its first screen.
Check that the session has web tools (WebSearch, WebFetch or a browser) before you start, and that the owner's answer
allows them (below).

When there are none, or the network is blocked, **say that the website references need web access, and stop.** Name what
you would have looked at (the visitor's job, the category, the sites the owner named), and offer the ways forward: allow
web access, send links or screenshots of sites the owner likes (you can read an image you were given), or skip the step
("skip the references", which you then record as `skipped by owner`). Do not guess: never write a site, an address or a
description from memory, never fill the board with guesses, and never start a page of the site instead. A board whose
sites were not opened is worse than no board.

A session with web tools but no Chromium can search and read, but cannot capture: `capture --url` exits 3. Say so and
offer the same ways forward (the owner may run `/brand-creator:setup`; you never run it without their yes). A reference
without a captured or sent screenshot does not count.

## The online-research question

Searching for sites tells search services what the brand makes, and opening a site tells its owner that someone looked.
The naming step already asks before it does that for candidate names; this step asks too. Read
`state --project <dir> --get site_research` first: `auto` or not set (an older project has no such key, and the command
exits 1) means the owner was not asked; any other value is the owner's recorded answer, and you **never ask again**. The
owner may change it in their own words, and then you record the new one.

Ask once, with one AskUserQuestion item (the same question in plain text without the tool), and say what each option lets
you do. Record the answer with `state --set site_research=` and the value of the option the owner chose. Options:

- (a) **Research the best real sites for this kind of visitor, and capture the sites you name** (Recommended).
  Record `state --set site_research=online`. You search and open sites, and capture them with `capture --url`.
- (b) **Only the sites I give you.** Record `state --set site_research=links-only`. You search nothing and capture only
  the addresses the owner gave. The board needs four groups of three sites, so ask for more addresses when the owner
  gave fewer; if they cannot, offer (a) or the skip rather than filling the gap yourself.
- (c) **No web: I will send screenshots, or skip the step.** Record `state --set site_research=none` when the owner will
  send screenshots; you search and capture nothing, and build the groups only from the sites and screenshots they send
  (kept in `research/site-refs/owner/`, with a caption that says the owner sent each one). If they choose the skip,
  record `state --record G4w "skipped by owner"` instead (see [Gate](#gate)).

In the same message ask for the sites the owner likes and dislikes, with a few words on why (links, or screenshots that go
to `research/site-refs/owner/`). "None" is an answer; the board then says so in one line.

`capture --url` refuses to fetch anything (exit 2) until `site_research` is `online` or `links-only`. That refusal is a
backstop; the question is yours to ask first.

## Techniques

1. **The visitor's job.** From `brief/BRIEF.md` and `FACTS.md`: who visits, what they arrive knowing, the job they came
   to do, and the one action that serves it. This is the `visitor-job` section, and everything else on the board is
   measured against it. Start from the job, never from how a liked site looked.
2. **The category's site norm.** What most sites in the category do (how they open, what comes first, where the action
   sits), counted from real sites you opened today, with 2 named examples. Search with the category and the job in
   general words, not with the brand's name or a candidate name. This is the `norm` section.
3. **The owner's sites.** Each liked or disliked site gets its line with the owner's reason in their words
   (`data-like="like"` or `"dislike"`, a link or an inlined screenshot, `data-field="why"`). A site the owner dislikes is
   a source of what to avoid, not a group.
4. **4 to 6 groups, each a way of serving the visitor's job.** A group is a structure and a rhythm (one step with nothing
   to compare, stages as the visitor lives them, a catalogue to choose from), not a look. They differ the way the owner
   can see in a second, and at least one sits away from the norm. Name each with a word of three letters or more (never
   "Group 2", "Option B" or "Layout 3": the lint rejects a label). One sentence of idea each: how it serves the job.
   When one of the [layout references](../page-layouts.json) fits, put its id in the group's `data-layout`; when none does,
   write `own:<word>` and say in the idea why none of the references fits (the lint warns, so the references never become
   a menu of templates).
5. **3 or more real sites per group, from any trade that serves the same job.** A site from another trade can serve the
   visitor's job better than the category's own. Open each page and say what it does in words (what leads, in what
   order, where the action sits, how it ends). Never write a site you did not open today.
6. **Capture each site, then show it.** For every site run `capture --url <url> --name <name> --project <dir>` (`<name>`:
   lower case letters, digits and hyphens, 2 to 41 characters, one per address, never `owner`). It writes the stills and
   `thumb-1440.jpg` into `research/site-refs/<name>/`. Inline the thumbnail on the board **byte for byte**
   (`data:image/jpeg;base64,...` of `thumb-1440.jpg`, never resized or re-encoded: the lint matches the picture's bytes to
   the capture), with alt text and a `<figcaption>` that says whose site it is, the day it was captured and that it is
   shown for private research (in the owner's language). A screenshot the owner sent has no capture, so the lint warns;
   its caption says the owner sent it. A capture that fails (`could not capture <url>`, exit 1) leaves the site out, or you
   ask the owner for a screenshot of it. **Never capture a page behind a login**: the tool cannot tell, so you do not try.
   The screenshot lives on this research page only: never reuse it, or a part of it, in anything you build, and never
   link the image from the net (the lint fails it).
7. **Take and avoid.** For each site, **take** is structure, rhythm and how it serves the job; **avoid** is their look:
   colours, type, imagery and their words. A reference with no take or no avoid does not count. Every look value of the
   site to come is decided by the tokens and the G4 rules, not by a reference.
8. **The category's site clichés.** What sites like these do by reflex, counted from the sites you opened: a layout, a
   copy pattern, an imagery habit, an interaction, seen in at least two of them. Write them into
   `research/site-cliches.md` from the template, with three or more bullets under "Avoid unless argued"; they become the
   board's `site-cliches` section and go into each hero variant's reflex test in the site round. Keep notes with URLs
   and the date read in `research/YYYY-MM-DD-site-refs.md`.
9. **Visual first, in the owner's language.** Thumbnails, short lines, no dense tables, no essays. Chat language and board
   language are the owner's; the sites keep their own names. Question 1 lets the owner tick one or more groups and the
   page composes the reply; question 2 confirms the liked and disliked sites.
10. **My call.** Say which group (or two) the hero should start from, with the honest critique of your own pick and what
    the category norm would say against it.
11. **Test loop.** Lint, shoot, Read every slice, fix, repeat at least twice before showing, as for any board
    ([board-contract.md](../board-contract.md)). The review page is a copy of the board
    (`cp rounds/r<N>/board.html review/index.html`), linted with `board-lint review/index.html --round <N>`.

## Gate

**G4w Website references pick.** The board is open on the review surface. The owner picks one or more groups, or "none:
research again" (go back to technique 4 with new angles and rewrite the board in the same `rounds/r<N>/` while it is still
the latest round; a site already captured stays where it is, and another address needs another `--name`), and confirms the
liked and disliked sites. Restate the pick in one line before anything is built ("You picked Ledger and Atlas, and keep
the two sites you liked and the one you disliked; the hero is built from those.") and record it:
`state --record G4w "picked <groups>; likes <...>; dislikes <...>" --project <dir>`.

The owner may skip the step explicitly ("skip the references", in any language, such as "pomiń wzorce stron"). Then record
`state --record G4w "skipped by owner" --project <dir>` and go on. Only the owner skips; **never skip it yourself**: an
unanswered board, a brief that seems clear and a missing web connection are not a skip. Without web access the way forward is the owner's choice
([No web access](#no-web-access)).

The site round (`data-board="site"`) waits for G4w. Run `state --project <dir> --require G4w` before building one (exit 1:
the references come first). A new references board after the site round has begun is a new round, and the owner's pick is
recorded again. Do not start the site round in the same turn as the pick.

## Pitfalls

- **Searching before the owner answered.** The search tells a third party what the brand makes. Ask once, record it, and
  never ask again.
- **A site written from memory.** A URL not opened today, a layout described without opening the page, or a site that does
  not exist. Open it and capture it, or leave it out.
- **A group that is a look.** "Dark and minimal" is a style, not a way of serving the visitor's job. Change the structure,
  the order and where the action sits.
- **Taking their look.** What goes in **take** is structure and rhythm. Colours, type, imagery and words are the brand's
  own, from the tokens and the G4 rules.
- **A screenshot that leaves the research page.** A thumbnail linked from the net makes the page depend on it; a
  reference's picture reused in a page you build copies someone else's work.
- **Capturing behind a login.** The tool cannot tell. Do not capture an account, a dashboard or a private page.
- **A screenshot nobody can trace.** A thumbnail that matches no capture warns; either capture the address or say in the
  caption that the owner sent the picture.
- **Fewer than four groups of three.** The lint fails it. Research more, or tell the owner which part is missing.
- **Skipping on your own** because the brief "seems clear". Only the owner skips.
- **Offering it when the brief lists no site.** The lint fails the board; the owner may add a site to the brief in their
  own words.
- **Building a page in the same turn as the pick.** The pick is recorded first and the site round starts in its own turn.

## Enforcement

- `board-lint` on `data-board="site-refs"`: `page:data-board` (a round from 2 on, never a reset round), `site-refs:tier`
  (Standard or Full), `site-refs:brief` (the brief lists a site), `site-refs:g4`, `site-refs:research` (the online-research
  answer is recorded; `none` counts) and `site-refs:cliches-file` (three site clichés or more); the sections
  `visitor-job`, `norm`, `owner-sites`, `site-cliches`, `none-of-these`, `my-call`, numbered questions with lettered options
  and one recommended, and `reply`; `groups:count` (4 to 6 groups); per group `group:<name>:name`, `group:<name>:idea`,
  `group:<name>:references` (three sites, each with a link, an inlined screenshot with alt text and a caption, a take and
  an avoid) and `group:<name>:layout`; per screenshot `group:<name>:shot:<k>` (a warning when the picture matches no
  capture of that address);
  `owner-sites:items`; `images:inlined` (no picture from the network); no unfilled markers.
- `capture --url` exits 2 until `site_research` is `online` or `links-only`, for an address that is not http(s), for a bad
  `--name` and for `owner`; the site round's board needs G4w (`site:g4w`).
- Behaviour eval `evals/site-refs-gate-before-site-round`: on a Standard project with G4 recorded and a brief that lists
  a site, a request to build the home page writes no page of the site and records neither G4w nor a skip; without web
  tools the reply names the website references and web access, and stops.
- Prose: whether the sites are real, recent and well chosen, whether the groups truly differ in how they serve the job,
  and whether the clichés are the category's own is judgement and is not scripted.
