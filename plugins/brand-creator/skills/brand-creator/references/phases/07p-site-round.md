# P7p The site round (hero first, then the other pages)

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [The hero first](#the-hero-first)
- [The cold review](#the-cold-review)
- [The other pages](#the-other-pages)
- [Approval](#approval)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

A real brand's site was built by hand from a default nobody had chosen, approved in one word, and its corrections were
conflicts with the brand's own rules. The recipe written afterwards then pinned the undecided defaults as instructions.
P7p fixes both: the owner sees the first screen of the home page on its own, in two or three variants, before anything
else is built; every variant is measured against the brand's rules, photographed in four views and read cold; and the
last board says which choices are the brand's rules and which are one example.

The step has two boards, both ordinary rounds (`rounds/r<N>/board.html`, a round from 2 on, `data-board="site"`):

1. **The hero stage** (`data-site-stage="hero"`): 2 or 3 variants of the home page's first screen, built from the
   references the owner picked (their structure, never their look) and from the brand's own tokens. The owner picks or
   combines one.
2. **The pages stage** (`data-site-stage="pages"`, `data-hero="<the picked variant>"`): the other pages, built from that
   hero, and a **choices** section that tags every choice `rule` (it says where the owner decided it) or `example` (it may
   change). The owner approves the pages and the tags.

What comes out are **reference pages**: they show whoever builds the real site what the brand decided and what was one
example. They are never fill-in templates. The real site is built in the product repository, and a page copied from here
into it carries its examples along as if they were rules.

**When:** Standard and Full, after G4w, **only when the brief lists a site** (a site under `Required surfaces:` in
`brief/BRIEF.md`, in the owner's words). Run `state --project <dir> --require G4w` first (exit 1: the website references
come first, [07w-website-references](07w-website-references.md); say so and stop). Quick never runs it.

## Inputs

- G4 and G4w recorded. G4w is either the owner's pick of reference groups and sites, or `skipped by owner`; with a skip the
  heroes are built from the brief and the layout references alone, and each card's Takes from line says so.
- `brief/BRIEF.md` and `FACTS.md`: who visits, the job they came to do, and the only source of the words and numbers on
  a page.
- The references: the board G4w stands on (`rounds/r<N>/board.html`, `data-board="site-refs"`), the thumbnails and records
  in `research/site-refs/<name>/`, and `research/site-cliches.md` (the category's site clichés, which every hero's reflex
  test uses).
- What a page is made of: `assets/tokens/tokens.css` (built from the G4 tokens; every colour, size, space and motion value
  is a token), the approved mark in `assets/logo/`, the brand's fonts in `assets/fonts/`, and the rules of G4: the "(rule)" lines of
  `BRAND-STATE.md` under "Rules (G4)", with the thresholds and the `page.rules` tied to those lines in `qa/rules.json`.
- [page-layouts.json](../page-layouts.json): the layout references, keyed to the visitor's job. [page-tells.json](../page-tells.json)
  and [ai-defaults.json](../ai-defaults.json): the generic patterns the reflex test and `page-check` look for.
- `DECISIONS.md` and `decisions/*.md`: where a rule says it was decided.

## Outputs and paths

Commands are written after `brand-creator --data "${CLAUDE_PLUGIN_DATA}"`.

| Output | Path |
|---|---|
| A hero variant, one folder each, named by a word of 3 or more letters | `rounds/r<N>/<Name>/index.html` (the home page's first screen), `shots/` (from `capture`: `1440-light.png`, `1440-dark.png`, `390-light.png`, `390-dark.png`, `1440-light-full.png`, `capture.json`) and `cold-review.md` |
| A page of the pages stage, one folder each, named by its page id (`start`, `pricing`) | `rounds/r<N>/<id>/index.html`, `shots/`, and `cold-review.md` when the page was read cold |
| The site board (the page the owner sees) | `rounds/r<N>/board.html`, from `${CLAUDE_PLUGIN_ROOT}/templates/site-board.html` (`data-board="site"`) |
| The same page on the review surface | `review/index.html`, a copy of the board with the stills inlined as `data:` URIs and the live links seen from `review/`, linted with `board-lint review/index.html --round <N>` |
| The check of a page | `assets/_checks/page-check/<slug>-<hash6>.json`, one per page (from `page-check`) |
| The owner's decisions behind a rule | `DECISIONS.md` (or `decisions/*.md`): the owner's words and the date |
| G4p record | `BRAND-STATE.md` → `gates.G4p` (`state --record G4p "<decision>"`) |
| The approved pages | `site/<id>/index.html`, their files, and `site/site.json` (from `site approve`) |

A `page-check` report holds `BRAND-STATE.md` by its G4 rules only (the G4 record and the "(rule)" lines under "Rules
(G4)", the two things a page check reads from it). So a later write to the file (the phase, `review_url`, a gate, the
Directions table, Still open) leaves the round's reports and the board's lint current; only a changed G4 record or "(rule)"
line makes them stale, and then `page-check` runs again on each page, then the lint. A report from an older release lists
the whole file and goes stale at any write: run `page-check` on that page once more. A site board is no pick, style or reset
round, so the hook, `freeze`, `shot` and the review surface work unchanged and the style gate ignores it. The first board of each stage
(the first hero board, then the first pages board) is a new, empty folder (`mkdir rounds/r<N>`), never a copy of an
earlier round. A later board of the same stage, the refine loop on the picked or combined variant, starts as
`cp -R rounds/r<N-1> rounds/r<N>` of the previous board of that stage; everything a variant carries is tied to its path,
so its `capture`, `page-check` and cold review are made again in the new round.

## The hero first

Build the pages before the board, in this order, and only then the board. The home page is `start` (`<body
data-page="start">`) in every project.

1. **The variants.** 2 or 3 on the first hero board (1 or more on a later one), each a folder `rounds/r<N>/<Name>/`, named
   by a word of 3 letters or more (letters, digits, `-` and `_`; never "Variant 2" or "Option B"), spelt the same on the
   card and on the disk. They differ in structure, not in colour: where the first screen leads, what the visitor can do from
   it, how it ends. A site cliché or a generic tell that a variant keeps is a hit on its reflex line, argued on its card;
   two hits on one variant fail.
2. **The page.** `rounds/r<N>/<Name>/index.html` is the home page's first screen, built from the picked references
   (their structure and rhythm, never their look) and the brand:
   - `<body data-layout="<id of page-layouts.json, or own:<word>>" data-page="start">`. The layout is the visitor's job in
     the brief, not how a liked site looked. `own:<word>` is allowed with the reason on the card (the lint warns, so the
     references never become a menu of templates).
   - It loads `assets/tokens/tokens.css` (`../../../assets/tokens/tokens.css`), the approved mark from `assets/logo/`
     and the fonts in `assets/fonts/`. Every look value is a token; nothing is copied from a reference.
   - Words and numbers come from `FACTS.md` only. A number, price, date or status word that is not in the facts goes inside
     an element labelled `data-sample="<what it is>"` (`[data-sample]`: a sample, shown as one), never in the open.
   - No network: no web font, script, image or frame from another address.
3. **Per variant, in this order: `capture`, `page-check`, the cold review.**
   - `capture rounds/r<N>/<Name>/index.html --project <dir>` writes the four stills and the full page into `shots/`, with
     `capture.json`. Read all four stills.
   - `page-check rounds/r<N>/<Name>/index.html --project <dir>` measures the page against the brand rules at six widths,
     light and dark (exit 1: a brand-rule row failed; fix the page, or let the card say `fail`, never `pass`), and warns of
     generic tells. Every tell it finds goes on the card, with what you will do about it; change the page where a tell is
     worth removing. Exit 3 for either command (no Chromium yet): say the stills and the check are not verified; the board
     cannot pass its lint without them.
   - [The cold review](#the-cold-review) reads the four stills last, because it records their sha256.
   - A change to the page after any step makes the later ones stale: change the page, then start the variant's three
     steps again.
4. **The board** from `${CLAUDE_PLUGIN_ROOT}/templates/site-board.html`: one card per variant with its four stills, the live
   link, the check line (`data-check="pass"` or `"fail"`, as its report says), what it is, what it takes from the references,
   the tells, the reflex line (`no hits`, or one `hit: <id> | <argument>` per hit, tested against `page-tells.json`,
   `ai-defaults.json` and `research/site-cliches.md`), the cost, the layout line, the cold line and a vote. Hardest
   surface, My call (which hero you would take, with the honest critique of your own pick), questions and reply as on every
   board. A later hero board also has What changed and Weak points.
5. **Lint, shoot, review copy.** `board-lint rounds/r<N>/board.html --project <dir>` until exit 0, then `shot` the board
   last and Read every slice; taking a still, a check or a cold review again after the lint makes its report stale, so lint
   again. The review copy is `cp rounds/r<N>/board.html review/index.html`, with each still given a
   `data:image/png;base64,...` src of the same file and each live link the path seen from `review/`
   (`../rounds/r<N>/<Name>/index.html`; it opens from this machine only), linted with `board-lint review/index.html
   --round <N>`. Recording `review_url` and updating `BRAND-STATE.md` after that write it again, but the `page-check`
   reports hold only its G4 rules, so they stay current: before the reply run `board-lint rounds/r<N>/board.html --project
   <dir>` once more, so that `check` finds the board's lint current (a lint of a board whose rule cites a line only
   `BRAND-STATE.md` holds lists the whole file, so it needs that run).
6. **Reply and stop.** The owner picks or combines a hero, or says none of these. Restate the pick in one line and write it
   into `DECISIONS.md` with the owner's words and the date. "None of these" is new variants (a new hero board; the old
   ones stay in their round) or, when what was missing is the references, a new website references board and a new G4w.
   Do not start the pages in the same turn as the pick.

## The cold review

A hero is read by someone who does not know why it looks the way it does. The verdict comes first, before any reason, and
the review reads fixed inputs only: the variant's four stills, `brief/BRIEF.md` and `FACTS.md`. Never the board, the
references, the cards or your own reasons. The prompt is the cold-review bullet under **Review** in
[prompt-fragments.md](../prompt-fragments.md). It asks whether the first screen says what only this brand could say,
whether it serves the visitor's job and puts the job's own action in reach, whether any part reads as a tell, and whether
every number and status word matches `FACTS.md` or sits in a labelled sample. Where the page lacks something it would need
(wording, a picture, a control), a finding says the owner would have to supply it and does not fault the page for leaving
it out.

The result is `rounds/r<N>/<Name>/cold-review.md`:

```text illustrative
verdict: ship
by: in-thread
inputs:
- rounds/r2/Ledger/shots/1440-light.png sha256:<hex>
- rounds/r2/Ledger/shots/1440-dark.png sha256:<hex>
- rounds/r2/Ledger/shots/390-light.png sha256:<hex>
- rounds/r2/Ledger/shots/390-dark.png sha256:<hex>
- brief/BRIEF.md sha256:<hex>
- FACTS.md sha256:<hex>

1. The finding that costs the visitor most, short enough for one line.
```

- The first non-empty line is `verdict: ship` or `verdict: fix`. Then `by:`, the `inputs:` list with the sha256 of each file
  as it is now (`shasum -a 256 <file>`), then at most five numbered findings, worst first, one line each.
- **In-thread by default**, labelled `by: in-thread`. It is not blind: the same session that built the page reads it. Say
  so to the owner when you show the card, and read as little as the review allows (the six files, nothing else).
- **An agent only after the fleet gate** ([fleet.md](../fleet.md)): one `brand-creator:brand-reviewer` call per hero
  variant, with the prompt fragment and the six paths, after the owner's yes to the count, the model and the cost. The
  reviewer reports and never writes: you write `cold-review.md` from its reply, with `by: agent`.
- The card's cold line (`data-cold`) says the verdict. A `fix` shown as `fix` is honest and passes; act on it, or say on
  the card why not. The review is required on a hero variant and optional on a page.
- The page or a still changed after the review: the hashes no longer match and the lint fails it. Review again.

## The other pages

After the owner's pick of a hero, the next site round shows the other pages. The pick is restated and recorded first, and
the pages start in their own turn.

1. **A new, empty folder** for the first pages board (`mkdir rounds/r<N>`), and one folder per page,
   `rounds/r<N>/<id>/`, named by its page id (lowercase letters, digits and `-`, starting with a letter, 2 to 32
   characters: `start`, `pricing`). The id is the same in three places: the folder, the card's `data-site-page` and
   `<body data-page>`.
2. **The home page is a page like the others.** Begin `rounds/r<N>/start/` from the picked hero's folder (its `index.html`
   and the files it loads, without `shots/` and `cold-review.md`; the depth in the tree is the same, so its relative
   paths still hold) and build the rest of the page below the first screen. Build each other page from the hero's
   structure and the layout reference that fits its job, in the same terms as the hero: tokens, FACTS, `[data-sample]`,
   no network, `<body data-layout=... data-page="<id>">`.
3. **The same loop per page:** `capture`, `page-check` and (optional on a page) the cold review, then the board from the
   same template with its three comments at the end put to use: the pages in place of the variants, the choices section
   and the two questions of the pages. `<body data-round="<N>" data-board="site" data-site-stage="pages"
   data-hero="<the picked variant>">`. The lint fails a pages board without an earlier hero board that holds that variant
   (hero first), and a page card spelt unlike its page id. Lint, shoot and make the review copy as for the hero, and run `page-check` and the lint again after the
   writes to `BRAND-STATE.md`. A later pages board (the refine loop on the pages, started as `cp -R` of the previous pages
   board) also has What changed and Weak points: the lint requires both from the second board of a stage.
4. **The choices.** List every structural and visual choice the pages make (the order of the sections, where the action
   sits, what repeats, how a page ends, the density, the way an image or a figure is shown), one `<li data-choice="c1">`
   each, tagged:
   - `rule`: the owner decided it, and the brand keeps it wherever it shows a site. `data-source` quotes, word for word, the
     line of `BRAND-STATE.md`, `DECISIONS.md` or `decisions/*.md` where they decided it. If it is not written down yet,
     record the owner's decision in `DECISIONS.md` first, then cite it.
   - `example`: a way the pages did it that may change. It needs no source.

   Propose a choice as a rule only when the owner has already decided it (the G4 rules, the hero pick, an answer they gave
   in their own words); everything else is an example. A default you chose is never a rule. `data-pages` names the pages a
   choice applies to; left out, it applies to every page.
5. **The questions** ask the owner to approve the pages (all, some, or change something first) and to confirm the tags.
   When the owner turns an example into a rule, write the decision into `DECISIONS.md` first, then change the tag and the
   source on the board and lint again.

## Approval

The owner approves the pages and the tags, in their words. Then, in this order:

1. **Restate** which pages are approved and which choices are rules (with where each was decided) and which are examples.
2. `state --project <dir> --record G4p "approved <pages>; rules <ids>"`. Never record it on a bare "ok", and never for pages
   the owner did not approve.
3. **Make the proof current again, when it is not.** Recording a gate changes `BRAND-STATE.md`, but the `page-check`
   reports hold only its G4 rules, so the reports of the round's pages and the board's lint stay current. Lint again when
   `site approve` says the lint is stale: it does when a rule of the board cites a line only `BRAND-STATE.md` holds, and
   when a report is from an older release (run `page-check` on each page of the round first, then `board-lint
   rounds/r<N>/board.html --project <dir>`). A changed G4 record or "(rule)" line needs the same two runs.
   `site approve` refuses a lint that is not current and passing.
4. `freeze r<N> --name approved-site --project <dir>` keeps the round in `history/`.
5. `site approve --project <dir>` copies each approved page from `rounds/r<N>/<id>/` into `site/<id>/` (without `shots/` and
   `cold-review.md`, with every relative path made to resolve from there) and writes `site/site.json`: the pages, the layout
   each used, a checksum of each, and the choices with their tags and sources. It refuses without G4p, on a page that
   needs the network, and when `site/` already holds approved pages (`--replace` moves the old ones to
   `removed-<date>/` first, never deletes).
6. **Take the stills again where the pages now live:** `capture site/<id>/index.html` and `page-check
   site/<id>/index.html` for each page, then `check --project <dir>`. `check` gates the record, the pages and their stills.

The approved pages are references for whoever builds the real site, never fill-in templates: the rules go into the
product repository, the examples show one way to follow them. Production sites are built there, not in this project.
The book can show them in an opt-in `site` chapter.

## Gate

**G4p The site's reference pages approved.** The pages board is open on the review surface. The owner approves all of the
pages or some of them, and confirms the tags. Restate, then record it as above (`state --record G4p`). The hero pick has no
gate of its own; it is written into `DECISIONS.md`.

The site round is optional and late, so there is no re-arm as after a rejected style board: after "none of these" on a site
board, the owner chooses between new variants or pages (a new site board) and a new references board with a new G4w.
`site approve` needs G4p and runs only after it.

## Pitfalls

- **A reference's look copied.** What a variant takes from a reference is structure and rhythm. Colours, type, imagery and
  words are the brand's own, from the tokens and the G4 rules.
- **The stock product page shipped because nobody chose otherwise.** A label over every heading, a hero with two buttons,
  three equal tiles, an FAQ and a closing call-to-action band. The reflex test and `page-check` name it; if a variant keeps
  a part, its card argues why.
- **Numbers or status words that are not in FACTS.** A price, a count, a date, "soon". Back it with the facts, or put it in
  a `[data-sample]` element with a label, or leave it out.
- **A choice approved with one word and no tag.** "Fine" is not a decision on each choice. Show the tags and ask.
- **A rule without where it was decided.** If nothing the owner said holds it, it is an example. The lint finds the quoted
  text in the project's decision files.
- **Pages before the hero.** The pages board needs an earlier hero board and names the picked variant.
- **A hero variant that differs only in colour.** Three heroes are three structures. If every one hits the same reflex
  pattern, the lint fails the board.
- **An in-thread cold review presented as blind.** It is not. Say `by: in-thread`, and never write findings from the
  reasons you know.
- **A stale proof.** A page, still, token file, or a changed G4 record or "(rule)" line of `BRAND-STATE.md` after the
  check, the capture or the lint: run them again before showing the board or running `site approve` (`page-check` on each
  page of the round, then `board-lint rounds/r<N>/board.html --project <dir>`). Other writes to `BRAND-STATE.md` (the
  phase, `review_url`, a gate, the Directions table, Still open) leave the `page-check` reports current; they make the
  lint stale only when a rule cites a line that only `BRAND-STATE.md` holds, and then the lint alone runs again.
- **Building the production site here.** The pages are references. The real site is built in the product repository.
- **Capturing in an earlier round.** `capture` refuses a page in `history/` or in a round before the latest; work in the
  latest round.

## Enforcement

- `board-lint` on `data-board="site"`: `page:data-board` (a round from 2 on, never a reset round), `page:site-stage`,
  `site:tier`, `site:brief`, `site:g4`, `site:g4w`; the sections and the questions as on every board; at the hero stage
  `site:variants` (2 or 3 on the first board), `site:files`, `site:layout`, `site:fields`, `site:check`, `site:tells`,
  `site:stills`, `site:<name>:reflex` and its `-format`, `-ids`, `-count`, `-grounded` and `-measured` rows,
  `site:reflex-shared`, `site:refs` and `site:cold`; at the pages stage `site:hero-first`, `site:pages`, the `site:files`
  to `site:stills` rows read for the pages, `site:cold` for a page that has a review, `section:choices` and
  `site:choices` (an id, a tag, a rule's source found in the decision files, `data-pages` naming pages of the board).
- `page-check` on each page: brand rules fail (`page:rule:<id>`, colours, fonts, the mark, claims), tells warn.
- `capture` refuses a page in `history/` or a round before the latest, and `site approve` refuses without G4p, without a
  current passing lint of the pages board, on a network or root-relative address and on a missing file; `check` gates
  `site/site.json`, the pages and their stills (`site:record`, `site:pages`, `site:stills`).
- Behaviour eval `evals/site-refs-gate-before-site-round`, on the way in: on a Standard project with G4 recorded and a
  brief that lists a site, a request to build the home page writes no page of the site and records neither G4w nor a skip.
- Prose: whether the heroes truly differ, whether the references were used for their structure and not their look, and
  whether a choice is a rule or an example is judgement and is not scripted.
