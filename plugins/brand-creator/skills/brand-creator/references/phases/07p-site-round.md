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
- What the brand already approved, which a hero starts from instead of building bare: `assets/masters/` (the approved
  templates and pictures, reusable as they are: a hero loads one by its relative path and never redraws it) and
  `motion/motion.json` (when it says `"motion": "on"` the brand moves: its signature move, `signature.name` and the places
  in `signature.where`, is shown on the first screen of each variant, or the card says why that variant leaves it out; with
  `off` nothing moves and nothing is asked).
- [page-layouts.json](../page-layouts.json): the layout references, keyed to the visitor's job. [page-tells.json](../page-tells.json)
  and [ai-defaults.json](../ai-defaults.json): the generic patterns the reflex test and `page-check` look for.
- `DECISIONS.md` and `decisions/*.md`: where a rule says it was decided.
- An earlier site, when there is one: `site/site.json` (its choices with their tags and sources), a `removed-*/site/` folder
  (an earlier approved site that `site approve --replace` moved aside), or an incumbent site named in the brief (`incumbent`
  in `BRAND-STATE.md`, or a site under Existing assets in `brief/BRIEF.md`). Its rules bind the redo only when the owner says they
  still stand (step 0 of [The hero first](#the-hero-first)).

## Outputs and paths

Commands are written after `brand-creator --data "${CLAUDE_PLUGIN_DATA}"`.

| Output | Path |
|---|---|
| A hero variant, one folder each, named by a word of 3 or more letters | `rounds/r<N>/<Name>/index.html` (the home page's first screen), `shots/` (from `capture`: `1440-light.png`, `1440-dark.png`, `390-light.png`, `390-dark.png`, `1440-light-full.png`, `capture.json`) and `cold-review.md` |
| A page of the pages stage, one folder each, named by its page id (`start`, `pricing`) | `rounds/r<N>/<id>/index.html`, `shots/`, and `cold-review.md` when the page was read cold |
| A try-out of a hero variant (the first hero board only), one folder each, named as its variant | `tryout/<Name>/index.html`: a plain local page the owner opens in their own browser; no `shots/`, no report, no record, and nothing cites it; the whole folder moves to `removed-<date>/tryout/` at the stage gate |
| A shared copy of a try-out (only when the owner asks and said yes to claude.ai pages) | one self-contained `.html` file made by `inline`, outside the project; published as a private Artifact page; its address in `BRAND-STATE.md` → `tryout_url`, cleared at the stage gate |
| The site board (the page the owner sees) | `rounds/r<N>/board.html`, from `${CLAUDE_PLUGIN_ROOT}/templates/site-board.html` (`data-board="site"`) |
| The same page on the review surface | `review/index.html`, a copy of the board with the stills inlined as `data:` URIs and the live links seen from `review/`, linted with `board-lint review/index.html --round <N>` |
| The check of a page | `assets/_checks/page-check/<slug>-<hash6>.json`, one per page (from `page-check`) |
| The owner's decisions behind a rule | `DECISIONS.md` (or `decisions/*.md`): the owner's words and the date |
| G4p record | `BRAND-STATE.md` → `gates.G4p` (`state --record G4p "<decision>"`) |
| The approved pages | `site/<id>/index.html`, their files, and `site/site.json` (from `site approve`) |

A `page-check` report holds `BRAND-STATE.md` by its G4 rules only (the G4 record and the "(rule)" lines under "Rules
(G4)", the two things a page check reads from it). So a later write to the file (the phase, `review_url`, a gate, the
Directions table, Still open) leaves the round's reports and the board's lint current; only a changed G4 record or "(rule)"
line makes them stale, and then `page-check` runs again on each page, then the lint. A site board is no pick, style or reset
round, so the hook, `freeze`, `shot` and the review surface work unchanged and the style gate ignores it. The first board of each stage
(the first hero board, then the first pages board) is a new, empty folder (`mkdir rounds/r<N>`), never a copy of an
earlier round. A later board of the same stage, the refine loop on the picked or combined variant, starts as
`cp -R rounds/r<N-1> rounds/r<N>` of the previous board of that stage; everything a variant carries is tied to its path,
so its `capture`, `page-check` and cold review are made again in the new round.

## The hero first

Build the pages before the board, in this order, and only then the board. On the first hero board the owner tries the
variants live first (step 2a): steps 1 and 2 are built in `tryout/<Name>/`, not in `rounds/r<N>/<Name>/`, no `rounds/r<N>/`
exists until the stage gate, and none of the proofs of step 3 is made until they say the variants are ready. The home page
is `start` (`<body data-page="start">`) in every project.

0. **Which earlier site rules still stand.** Only when `site/site.json` exists, a `removed-*/site/` folder does, or the brief
   records an incumbent site. List the earlier choices tagged `rule` in each `site.json` (id, text, source), and name the
   "(rule)" lines under "Rules (G4)" of `BRAND-STATE.md` that came from the old site. Ask the owner once which still stand,
   in their words, and wait for the answer before any variant is built. A rule of an earlier site binds nothing until the
   owner says it stands: a rule that came from a site they rejected is not a rule of the redo. Write the answer into
   `DECISIONS.md` as one entry (`Gate: G4p`, `Decided: ...`): each rule that stands by id and text, each one dropped named as
   dropped. A G4 line the owner drops is named as dropped too; the line itself changes the way any G4 rule changes. A rule
   that stands is cited by the new board's `data-source` like any rule (the lint finds the quoted text in the decision files,
   `site:choices`); a dropped one is not built in again. There is no new gate id. With no earlier site, skip this step.
1. **The variants.** 2 or 3 on the first hero board (1 or more on a later one), each a folder `rounds/r<N>/<Name>/`, named
   by a word of 3 letters or more (letters, digits, `-` and `_`; never "Variant 2" or "Option B"), spelt the same on the
   card and on the disk. They differ in structure, not in colour: where the first screen leads, what the visitor can do from
   it, how it ends. A site cliché or a generic tell that a variant keeps is a hit on its reflex line, argued on its card;
   two hits on one variant fail. Before any variant is built, each states its **one memorable idea** in one line: what
   a visitor will remember of the first screen and what makes it this brand's, a choice and not a layout ("the price lands
   like a stamp, once", not "headline, picture, button"). Two variants with one idea are one variant. The idea goes on the
   card as the Idea line (`data-field="idea"`); a hero card with no idea line, or an empty one, is a `site:fields` warning in
   this release and a failure in the next.
2. **The page.** `rounds/r<N>/<Name>/index.html` is the home page's first screen, built from the picked references
   (their structure and rhythm, never their look) and the brand:
   - `<body data-layout="<id of page-layouts.json, or own:<word>>" data-page="start">`. The layout is the visitor's job in
     the brief, not how a liked site looked. `own:<word>` is allowed with the reason on the card (the lint warns, so the
     references never become a menu of templates).
   - It loads `assets/tokens/tokens.css` (`../../../assets/tokens/tokens.css`), the approved mark from `assets/logo/`
     and the fonts in `assets/fonts/`. Every look value is a token; nothing is copied from a reference.
   - Words and numbers come from `FACTS.md` only. A number, price, date or status word that is not in the facts goes inside
     an element labelled `data-sample="<what it is>"` (`[data-sample]`: a sample, shown as one), never in the open.
   - A headline is never a fact's `value` as it stands. It quotes a `copy:` row of `FACTS.md` (wording the owner approved for
     use as copy, labelled `copy: <slot>`, such as `copy: hero headline`; the fact stays in its own row), or it is new wording
     the owner approves on the board, which becomes a `copy:` row once they do. `page-check` warns (`page:words`, never a
     failure) for each word the brief or `research/cliches.md` lists under Forbidden that it finds in the text of the page:
     reword it, or tell the owner why the page keeps it.
   - No network: no web font, script, image or frame from another address.
   - It starts from what the brand approved (Inputs): an approved master or picture of `assets/masters/` is used as it stands,
     and when `motion/motion.json` says the brand moves, the signature move shows on the first screen, or the card's What it
     is line says why this variant leaves it out.

2a. **The try-out (the first hero board only).** The owner tries the variants live before any proof is made. Build each one as
   a plain page in `tryout/<Name>/index.html` (a folder of the project, beside `rounds/`, never inside it), to every rule of
   step 2: its `<body>`, the tokens, the approved masters, the signature move, the words of `FACTS.md`, no network. On this
   board steps 1 and 2 are built here and not in `rounds/r<N>/<Name>/`: no `rounds/r<N>/` exists until the stage gate below.
   It loads what it needs from `assets/` by a path seen from `tryout/<Name>/` (`../../assets/tokens/tokens.css`) and from its
   own folder, never from another try-out's. A name already used under `tryout/` is not reused. Then give the owner the paths
   and stop: they open the pages in their own browser (local files; nothing is published) and say what to change, and each
   change is made in the page for them to reload.

   - **Nothing runs per change:** no `capture`, `page-check`, cold review, board, lint, `shot` or review copy. A `page-check
     tryout/<Name>/index.html --project <dir> --widths 390,1440` only when the owner asks for one; its report is not the board's
     proof (that is the report of the page in `rounds/r<N>/<Name>/`).
   - **Nothing cites a try-out.** No card, record, `cold-review.md` or `DECISIONS.md` entry names `tryout/`, and a choice the
     owner makes there ("this one, not that one") is not the hero pick: the pick is made on the board and written down from
     there (step 6). The first hero board still shows 2 or 3 variants: leave out a variant the owner drops, and build another
     when fewer than 2 remain.
   - **Sharing a try-out (only with the owner's yes).** A try-out stays a local page. When the owner asks to show one to someone,
     and has said yes to claude.ai pages (`review_surface` is `artifact`, or they answer yes to the one upload question of the
     orchestrator's Review surface), make one self-contained copy outside the project:
     `brand-creator --data "${CLAUDE_PLUGIN_DATA}" inline tryout/<Name>/index.html --project <dir>
     --out "${CLAUDE_PLUGIN_DATA}/scratch/tryout-<Name>.html"`. Say the size it prints, then publish that file as a private Artifact page
     with the Artifact tool and record its address with `state --set tryout_url=<url>`, never as `review_url` (the page of the
     boards); a changed try-out is published again to the same address. With no yes, or no Artifact tool, nothing is published
     and the try-out stays local: say so once. `inline` refuses a page that loads from another website (exit 2, naming the URL):
     take that out of the try-out, which has no network by step 2 anyway. The copy is for looking at, not a second page: a link
     to another file is dead in it, and a change is made in the try-out and published again. At the stage gate clear the address
     (`state --set tryout_url=`) and tell the owner the private page is theirs to remove on claude.ai.
   - **At the stage gate**, when the owner says in their words that the try-outs are ready for the board (never on your own),
     make `rounds/r<N>/` (a new, empty folder, as for any first board of a stage; never `cp -R` onto a `rounds/r<N>/<Name>/`
     that exists, it nests the copy as `<Name>/<Name>/` and keeps the old page) and copy each variant that stays:
     `cp -R tryout/<Name> rounds/r<N>/<Name>`. The copy sits one level deeper, so every relative path that leaves the variant's
     own folder gets one more `../` (`../../assets/tokens/tokens.css` becomes `../../../assets/tokens/tokens.css`), in the page
     and in each stylesheet or script of the folder (`href`, `src`, `srcset`, `url()`, `@import`); a path inside the folder stays
     as it is. Then check that every relative path of the copy leads to a file: a page with a wrong path still opens, but loads no
     tokens and no fonts. Last, move the whole `tryout/` folder (a variant the owner dropped too) to `removed-<date>/tryout/`
     (`removed-<date>-2/` when that name is taken; never delete): `check --cascade` searches every folder but `history/`,
     `decisions/`, earlier rounds and `removed-*/`, so a try-out left in place would hold the old name, price or wording and fail
     the cascade after the first change, and it is not edited again. From here on every change goes to the page in
     `rounds/r<N>/<Name>/`, and the full hero board runs as today (steps 3 to 6), its gates unchanged.

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
   link, the check line (`data-check="pass"` or `"fail"`, as its report says), its idea, what it is, what it takes from the references,
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
   <dir>` once more, so that `check` finds the board's lint current (every `board-lint` run writes the one report
   `assets/_checks/board-lint.json`, so the lint of the review copy took the place of the board's, and `check` wants the
   report of `rounds/r<N>/board.html`).
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
- **The brand's rules, when the review should judge against them.** Run `brand-creator state --part g4-rules`. Its first line,
  `BRAND-STATE.md#g4-rules sha256:<hex>`, goes into `inputs:` with a dash in front, as the seventh input; its second line (the
  G4 record and the recorded rule lines) you paste into the reviewer's prompt as text. The review then judges the stills against
  the approved rules: a dark still that equals the light one is right when a rule says so, and a page that breaks a rule is a
  finding. It still does not read the rest of `BRAND-STATE.md`, and the whole file is never listed, nor any other part of it.
  Lint accepts the six inputs alone (a review made before this release) or the six plus that line. A rule or the G4 record that
  changes after the review makes it stale (review again); another line of `BRAND-STATE.md` changing does not.
- **In-thread by default**, labelled `by: in-thread`. It is not blind: the same session that built the page reads it. Say
  so to the owner when you show the card, and read as little as the review allows (the six files, and the rules when you give them, nothing else).
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
   (hero first), and a page card spelt unlike its page id. Lint, shoot and make the review copy as for the hero; a write to `BRAND-STATE.md` asks for
   `page-check` and the lint again only when it changes the G4 record or a "(rule)" line. A later pages board (the refine loop on the pages, started as `cp -R` of the previous pages
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
5. **The questions** ask the owner to approve the pages (all of them, or change something first) and to confirm the tags.
   An approval covers the whole pages board: `site approve` copies every page card on it. To leave a page out, remove its
   card (and its id from any choice's `data-pages`) from the pages board and lint it again, then ask for the approval.
   When the owner turns an example into a rule, write the decision into `DECISIONS.md` first, then change the tag and the
   source on the board and lint again.

## Approval

The owner approves the pages and the tags, in their words. The approval covers every page card on the pages board; a page
the owner leaves out has its card removed and the board linted again first (step 5 of "The other pages"). Then, in
this order:

1. **Restate** which pages are approved and which choices are rules (with where each was decided) and which are examples.
2. `state --project <dir> --record G4p "approved <pages>; rules <ids>"`. Never record it on a bare "ok", and never while
   the board still holds a page card the owner did not approve.
3. **Make the proof current again, when it is not.** Recording a gate changes `BRAND-STATE.md`, but the `page-check`
   reports hold only its G4 rules, so the reports of the round's pages and the board's lint stay current. Lint again when
   `site approve` says the lint is stale: it does when a rule of the board cites a line only `BRAND-STATE.md` holds
   (`board-lint rounds/r<N>/board.html --project <dir>`). A changed G4 record or "(rule)" line needs `page-check` on each
   page of the round first, then that lint.
   `site approve` refuses a lint that is not current and passing.
4. `freeze r<N> --name approved-site --project <dir>` keeps the round in `history/`.
5. `site approve --project <dir>` copies every page card of the pages board from `rounds/r<N>/<id>/` into `site/<id>/` (without `shots/` and
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

**G4p The site's reference pages approved.** The pages board is open on the review surface. The owner approves the pages on the
board (all of its page cards) and confirms the tags. Restate, then record it as above (`state --record G4p`). The hero pick has no
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
- **A bare hero while the brand's approved work sits unused.** An approved master or picture left out, or a signature move that
  never shows on the first screen, with nothing on the card saying why. The hero is then safe and generic: start from the
  inputs, and state the one idea before building.
- **A hero variant that differs only in colour.** Three heroes are three structures. If every one hits the same reflex
  pattern, the lint fails the board.
- **An in-thread cold review presented as blind.** It is not. Say `by: in-thread`, and never write findings from the
  reasons you know.
- **A stale proof.** A page, still, token file, or a changed G4 record or "(rule)" line of `BRAND-STATE.md` after the
  check, the capture or the lint: run them again before showing the board or running `site approve` (`page-check` on each
  page of the round, then `board-lint rounds/r<N>/board.html --project <dir>`). Other writes to `BRAND-STATE.md` (the
  phase, `review_url`, a gate, the Directions table, Still open) leave the `page-check` reports current; they make the
  lint stale only when a rule cites a line that only `BRAND-STATE.md` holds, and then the lint alone runs again.
- **A try-out treated as a round.** A `capture`, a `page-check`, a cold review, a board or a lint per change is the ceremony the
  try-out spares the owner; a card, a record or a `DECISIONS.md` entry that cites `tryout/` rests on nothing, because a choice
  made there is not the hero pick; a try-out copied into a round with its paths as they were loads no tokens and no fonts:
  rewrite them for the depth; a variant also built in `rounds/r<N>/` before the gate ends as `<Name>/<Name>/` and puts the page
  from before the owner's live edits on the board (the lint passes, the folder and page exist), so there is no `rounds/r<N>/`
  until the gate; and a `tryout/` left in place after the gate fails `check --cascade` after the first rename, price or
  wording change: move it aside.
- **A try-out published without the owner's yes.** A try-out is a local page. Sharing it as a private Artifact page needs the
  owner's ask and their yes to claude.ai pages (`review_surface` `artifact`, or the one upload question answered yes). A page
  published without them, an address written to `review_url` instead of `tryout_url`, and a `tryout_url` still set after the stage
  gate are wrong.
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
- The Idea line of a hero card (`data-field="idea"`) is read by `site:fields`: missing or empty it warns in this release and
  fails in the next, so a board made before the line existed still lints. A page card has no Idea line.
- No lint row reads a try-out, and none is added: a hero card's folder and live link are `rounds/r<N>/<Name>/`, so on the round's
  board (`rounds/r<N>/board.html`) a card that points into `tryout/` fails `site:files` as any card without its folder does (the
  review copy's live link is checked only for being there). `check --cascade` does search `tryout/`, which is why step 2a moves it
  to `removed-<date>/` at the stage gate. The step itself (2a) is prose: that the pages were really tried live, and that their
  paths were rewritten for the depth, is judgement and is not scripted.
- `inline` reads no gate of the board: it refuses a page that loads from another website (exit 2) and writes only outside the project
  or under `tryout/`. That the owner asked for the copy and said yes to publishing it is judgement and is not scripted.
- `page-check` on each page: brand rules fail (`page:rule:<id>`, colours, fonts, the mark, claims), tells warn.
- `capture` refuses a page in `history/` or a round before the latest, and `site approve` refuses without G4p, without a
  current passing lint of the pages board, on a network or root-relative address and on a missing file; `check` gates
  `site/site.json`, the pages and their stills (`site:record`, `site:pages`, `site:stills`).
- Behaviour eval `evals/site-refs-gate-before-site-round`, on the way in: on a Standard project with G4 recorded and a
  brief that lists a site, a request to build the home page writes no page of the site and records neither G4w nor a skip.
- Prose: whether the heroes truly differ, whether the references were used for their structure and not their look, and
  whether a choice is a rule or an example is judgement and is not scripted.
