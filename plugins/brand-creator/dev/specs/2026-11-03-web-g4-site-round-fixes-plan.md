# Group 4 plan: the site round, after its first real use

Plan date 2026-11-03. Release target: brand-creator 0.7.0. This is a working file, not a doc: it lives in `dev/specs/` while the
work runs and moves to `docs/archive/` when it ships. The static tests and the docs checks scan it like a shipped file, so it holds no
personal path, no e-mail address and no client name. The private brand whose redo found these problems is "the pilot brand" here.

> **For agentic workers:** run it task by task (subagent-driven: an implementer per task, an independent review between tasks).
> Write the failing test first. Every file you edit is under `plugins/brand-creator/`. Tasks G4-01 to G4-17 and G4-19; G4-18 is the owner's.

**Goal:** a site round that starts from what the brand already approved, reviews what the owner will actually see (motion, the
brand's own rules), stops reviewing when only the owner can decide, catches a page that breaks after its animation, and costs less
per iteration.

**Architecture:** mostly instructions (`07p-site-round.md`, the round skill, the prompt fragment, the manual), plus four code
changes: the cold-review lint (`scripts/boardlib/siteboard.py`), a key-frame option for `capture` and a stray-box tell
(`scripts/render.mjs`, `scripts/pagelib/`), a cost table for `fleet-plan` (`scripts/fleet_plan.mjs`), and three small fixes
(`templates/finish.sh.tpl`, `scripts/fontcheck.py`, `scripts/new.py`).

**Spec:** the site-round retrospective of 2026-11-03 (rounds 24 to 28 of the pilot brand) as the owner approved it: items 1 to 7 and
the small fixes, in the order below. The research behind each task, with file and line evidence, is summarised in the task.

## Why

The owner had to catch at least 19 things in five rounds. The heroes were safe and bare while approved masters and the brand's
signature move sat unused; old site rules from the site the owner had rejected bound the redo; the cold review saw only end frames
(it missed a tear-off animation and a tab switch), did not know the brand's rules, ran 21 times against 3 announced and almost never
said ship; a real bug (sheets left on screen after the animation) passed every check because nothing looks at a page after its
animations end or at a tall window; and every iteration paid the full board ceremony while the owner iterated on the live page.

## Owner decisions this plan assumes (each is a default the owner may change before work starts)

- **O1 (G4-02).** The hero card's new "Idea" line warns for one release, then fails. (Boards from earlier rounds exist.)
- **O2 (G4-04).** Key frames: three stills of the first screen at 1440 light: at the start, the middle and the end of the longest
  animation that runs on load. Only when the page animates on load.
- **O3 (G4-05).** At most two cold reviews per variant per board (the first, and one after the fixes); then a third verdict,
  `owner`, says the rest is the owner's call.
- **O4 (G4-06).** Costs in tokens come from a small table of measured runs, each dated with its source; an agent with no
  measurement says "not measured" instead of a guess.
- **O5 (G4-08, G4-17).** The live try-out is a local page by default (`tryout/<Name>/`, opened in the owner's browser). With the
  same yes the owner gives for boards on claude.ai, Claude may publish a self-contained copy as a private page; the manual's "Claude
  never publishes anything" becomes "nothing is published without your yes, and then only as a private page".
- **O6 (G4-09).** Forbidden words on a page warn; a fact used as a headline needs an approved `copy:` row.
- **O7 (G4-10).** A labelled sample needs no visible badge (the owner did not want one): the docs say so.
- **O8 (G4-13).** New projects ignore the full-page site captures in git (`research/site-refs/*/1440-full.png`); the boards use the
  smaller stills and thumbnails.
- **O9 (G4-14).** A page band is a `<section>` (or `role="region"`) that holds a heading as a direct child or names one with
  `aria-labelledby`; the mock-up warning never judges such a band as a whole (the boxes inside it are still judged).
- **O10 (G4-16).** A code in a title or main heading is an error code only when an error word stands right beside it, with nothing but
  spaces or separators (`-`, `–`, `·`, `|`, `:`) between them.

## Global constraints

- Work on the current branch; never commit, push, switch branch, stash or bump `plugin.json` (the lead commits; the release is cut
  with the changelog-release skill).
- Run commands without `cd`: absolute paths, `git -C`. A script that writes into its current folder runs only inside
  `( cd "$(mktemp -d)" && … )`.
- Tests run with a set-up data directory: `BRAND_CREATOR_DATA=<data dir> uv run --no-project --with-requirements tests/requirements.txt
  python -m pytest tests -q -n 8 --dist worksteal -k "<subset>"`; node tests with `node --test --test-reporter=tap`.
- `09-qa.md` marks: `(m)` a test that calls `mutate()`/`mutate_json()`/`mutateText()`, `(f)` one that does not; every cited test
  exists (`tests/test_skills.py` enforces both).
- The orchestrator's top section (`skills/brand-creator/SKILL.md` above `## Round mechanics`) has a 19,850-character budget pinned by
  `test_skills.py::test_the_phase_map_points_at_the_website_steps`: put new detail in the phase files, not there.
- No skill `description` or `when_to_use` changes (a change needs the owner's billed trigger-eval run).
- A new check that existing boards could fail warns for one release (the group 1 rule), unless the decision above says otherwise.
- Docs follow `docs/internals/docs-standard.md`; the manual stays in its plain, task-first voice. CHANGELOG bullets go under
  `## [Unreleased]` in the file's voice.
- The pilot brand's project is never read or written by an implementer: every test uses the Acme fixtures.

## Review focus (inputs the tasks' own tests may miss)

1. A page whose animation never ends (`infinite`) or starts on scroll: the stray-box tell must say "not verified", never pass or fail
   it (G4-07).
2. A board made before this release (no Idea line, a cold review with six inputs, two `fix` reviews): it must still lint, with warnings
   only (G4-02, G4-03, G4-05).
3. A page with no animation on load: `capture --frames` writes nothing and the review keeps its six inputs (G4-04).
4. A try-out page copied into a round: its relative paths are one level shallower (`tryout/<Name>/` vs `rounds/r<N>/<Name>/`) and must
   be rewritten, or its tokens and fonts do not load (G4-08).
5. `fontcheck` run twice with different `--font` files: the second run warns about the dropped font, and a run that names every font
   is silent (G4-12).

---

## Tasks

### G4-01 A redo asks which earlier site rules still stand

- **Files:** `skills/brand-creator/references/phases/07p-site-round.md` (Inputs, and a new step 0 of "The hero first"),
  `skills/round/SKILL.md` ("A site round"), `docs/manual/use/get-reference-pages-for-your-site.md`, `tests/test_skills.py`.
- **Do:** When `site/site.json` exists, or a `removed-*/site/` folder does, or the brief records an incumbent site, the hero stage
  starts by listing the earlier choices tagged `rule` (id, text, source) and asking the owner once which still stand, in their words.
  The answer goes in `DECISIONS.md` (Gate: G4p, Decided: …); a surviving rule is cited by the new board's `data-source` as today
  (`siteboard.py` `choices_rows`), a dropped one is named as dropped in the same entry. Earlier G4 "(rule)" lines that came from the old
  site are named in the same question. No new gate id.
- **Tests:** extend the needle list of `test_the_site_round_phase_goes_hero_first_and_tags_every_choice` (`tests/test_skills.py`)
  with the step's key sentences; add the same check to `test_the_round_wrapper_has_a_site_kind`.
- **Done when:** the step and its record are in 07p, the round skill and the manual page; the tests pass.

### G4-02 Masters and the signature move are inputs; each hero states its one idea

- **Files:** `07p-site-round.md` (Inputs, hero steps), `skills/round/SKILL.md`, `templates/site-board.html`,
  `scripts/boardlib/siteboard.py` (`FIELDS`, `card_rows`), `scripts/CONTRACT.md` (site board fields), `09-qa.md`, the manual page,
  `tests/test_site_board.py`, `tests/test_skills.py`, `CHANGELOG.md`.
- **Do:** Inputs gain `assets/masters/` (approved templates and pictures, reusable as they are) and `motion/motion.json` (when it says
  the brand moves: the signature move is shown on the first screen, or the card says why it is left out). Before building, each
  variant states its one memorable idea in one line; the card carries it as `data-field="idea"` (label "Idea"). Lint: a hero card
  with no idea line, or an empty one, is `site:fields` WARN in this release (O1), naming the card; the release notes say it fails in
  the next.
- **Tests:** copy `test_a_card_says_what_it_is_what_it_takes_and_what_it_costs` (`tests/test_site_board.py`) for the idea field
  (missing → warn, empty → warn, present → pass); the Acme hero fixture gains an idea line; needles for the two inputs in
  `test_skills.py`.
- **Done when:** a hero board without the line lints with one warning; with it, clean; the inputs and the idea step are in 07p.

### G4-03 The cold review knows the brand's rules

- **Files:** `scripts/boardlib/siteboard.py` (`cold_problems`), `skills/brand-creator/references/prompt-fragments.md` (the cold-review
  bullet), `agents/brand-reviewer.md`, `07p-site-round.md`, `scripts/CONTRACT.md`, `09-qa.md`, `tests/test_site_board.py`,
  `tests/helpers.py` (`cold_review_record`).
- **Interfaces:** consumes the part record of group 1 (`{"path": "BRAND-STATE.md", "part": "g4-rules", "sha256": …}`,
  `_common.stale_inputs`).
- **Do:** The cold review may take a seventh input: the G4 rules part of `BRAND-STATE.md`, recorded as the part record above, so the
  reviewer judges against the approved rules (a dark still that equals the light one is right when a rule says so) without reading the
  rest of the project record. Lint accepts the six inputs alone (older reviews) or the six plus that part; any other input still fails.
  The fragment and the agent's brief say what the part is for. Also fix the mismatch the research found: the fragment asks about
  `page-tells.json`, which the reviewer is not given: name the tells in the fragment itself instead.
- **Tests:** copy `test_a_cold_review_with_another_input_fails` for: six inputs pass; six plus the g4-rules part pass; a whole
  `BRAND-STATE.md` fails; a stale part fails (the rules changed after the review). Copy
  `test_the_prompt_fragment_describes_the_cold_review_of_a_site_hero` for the new wording.
- **Done when:** both record shapes lint; the fragment no longer names a file the reviewer cannot read.

### G4-04 Key frames of the first screen

- **Files:** `scripts/render.mjs` (`capture`), `scripts/CONTRACT.md` (capture), `scripts/boardlib/siteboard.py` (`cold_problems`:
  optional frame inputs), `scripts/site_pages.py` (copy exclusions), the prompt fragment, `07p-site-round.md`,
  `tests/node/capture.test.mjs`, `tests/test_site_board.py`.
- **Do:** `capture <page> --frames` writes, beside the four stills, `shots/frame-1440-0.png`, `-50.png` and `-100.png`: the first
  screen at 1440 light with every finite animation running on load paused at 0 %, 50 % and 100 % of the longest one (the pause-and-seek
  code of the motion proof in `render.mjs` is the model). A page with no finite animation on load writes no frame and says so.
  `capture.json` lists the frames. The cold review may add the three frames as inputs (lint accepts six, six plus the rules part,
  six plus the frames, or all); the fragment tells the reviewer to read motion from them. `site approve` does not copy frames into
  `site/<id>/shots/` unless they were captured there.
- **Tests:** node: a page with a 600 ms entrance animation yields three frames that differ; a static page yields none and a line
  saying so; an infinite animation alone yields none. Python: copy the cold-review input test for the frame inputs.
- **Done when:** the four existing stills and their tests are unchanged; `--frames` works on a page in the project.

### G4-05 A stop rule for the cold review

- **Files:** `07p-site-round.md`, `skills/brand-creator/references/fleet.md`, the prompt fragment, `scripts/boardlib/siteboard.py`
  (verdict values, the `site:cold` row), `scripts/CONTRACT.md`, `09-qa.md`, `templates/site-board.html` (the cold line),
  `tests/test_site_board.py`, `tests/test_skills.py`.
- **Do:** A third verdict, `verdict: owner`: what is left is a choice only the owner can make; its findings are written as questions
  to them. Per variant per board: at most two cold reviews (the first, and one after fixing what it found); the second may say `owner`;
  a third is not run (O3); the board's card shows the last verdict. Lint accepts `ship`, `fix` and `owner`; `site:cold` treats `owner`
  like `ship` for the gate and shows it on the card. The fleet gate message for reviewer calls states the number of calls this rule
  allows.
- **Tests:** lint accepts `owner`; an unknown verdict still fails; the card line shows it; needles for the cap in 07p and fleet.md.
- **Done when:** a board whose second review says `owner` lints clean.

### G4-06 Costs in tokens, from measured runs

- **Files:** `scripts/fleet_plan.mjs` (the "rough cost" line), a new `skills/brand-creator/references/fleet-costs.json`,
  `references/fleet.md`, `skills/brand-creator/SKILL.md` (only the wording below `## Round mechanics`), `skills/check/SKILL.md`,
  `docs/manual/reference/costs.md`, `tests/node/workflows.test.mjs`, `tests/test_agents_workflows.py`.
- **Do:** `fleet-costs.json` (schema 1) lists, per agent type, a measured token range per call with the date and the run it came from
  (for example the cold reviewer: about 29k per review, from 21 reviews of one site round; the research fleet: about 400k per round).
  `fleet-plan` prints "about <low>-<high>k tokens" per agent from it, and "not measured" for an agent with no row (O4); it keeps the
  turn ceiling. The prose stops calling an agent "about one pass" and points at the printed estimate.
- **Tests:** node: an agent with a row prints its range; one without prints "not measured"; a malformed file exits 2 naming it.
- **Done when:** the four workflows' plans print token ranges or "not measured"; no doc says "passes" for cost.

### G4-07 A page checked after its animations, and at a tall window

- **Files:** `scripts/pagelib/page_measure.mjs` (`tellFacts`), `scripts/render.mjs` (`measureView`), `scripts/pagelib/pagecheck.py`
  (`find_tells`, `tell_rows`), `skills/brand-creator/references/page-tells.json`, `scripts/page_check.py` (docstring), `scripts/CONTRACT.md`
  (page check), `09-qa.md`, `docs/manual/reference/page-check.md`, `tests/test_page_check.py`, `CHANGELOG.md`.
- **Do:** A new warning, `tell:stray-box`: after the page settles (`waitAnimations`), an element that is still visible (shown,
  opacity above 0, visibility visible) and lies wholly outside its parent's box on one axis by `min_outside_px` (8) or more, with no
  clipping ancestor and not fixed or sticky, is a hit; so is one left outside the viewport. An element still animating, or a view whose
  animation wait was capped, makes the row "not verified" for it (the first reader of the view's `animations` fact). Each width is also
  measured once more at a tall window (1300 px high) for this tell only (`strays_tall`), so a bug that shows only on a tall screen is
  caught; the views stay keyed by width and scheme. `site:tells` then asks site cards to name it like any tell.
- **Tests:** copy `test_the_tell_thresholds_are_applied_to_what_the_browser_collected` (7 px vs 8 px); copy
  `test_each_tell_is_found_on_a_page_built_to_show_it` with: a card moved out of a short parent by a forwards animation (hit), an
  `opacity: 0` end state (no hit), an `overflow: hidden` parent (no hit), an infinite animation (not verified), a bug visible only at
  1300 px (hit from `strays_tall`); add `stray-box` to `TELL_IDS`; copy the collector-fields test for `strays_tall`.
- **Done when:** the pilot-style bug (sheets left visible after their animation) is reproduced in a fixture and warned.

### G4-08 A live try-out before the hero board

- **Files:** `07p-site-round.md` (a step before "The board", the ordering sentence, a Pitfalls line), `skills/round/SKILL.md`,
  `docs/manual/use/get-reference-pages-for-your-site.md`, `tests/test_skills.py`, `tests/test_site_board.py`.
- **Do:** Between the references pick and the hero board, Claude builds the two or three variants as plain pages in
  `tryout/<Name>/index.html` and the owner opens them in their own browser and iterates on them live (O5); no capture, page check, cold
  review, board or lint runs per iteration (a quick `page-check --widths 390,1440` only when the owner asks). At the stage gate the
  variants are copied into `rounds/r<N>/<Name>/` (relative paths rewritten for the depth) and the full hero board runs as today. No
  card, record or `DECISIONS.md` entry cites a try-out; a choice made there is not the hero pick. Named "try-out" (not "sketch":
  `anti-patterns.md` uses "wide sketches" for logo rounds).
- **Tests:** needles in `test_skills.py` (the step, the copy rule, "no record cites a try-out"); copy
  `test_a_variant_needs_its_folder_and_its_page` (`test_site_board.py`) to show a card pointing into `tryout/` fails `site:files`.
- **Done when:** the step is in 07p, the round skill and the manual; the gates are unchanged (the test proves it).

### G4-09 Approved copy apart from facts; forbidden words on a page

- **Files:** `templates/FACTS.md` (rules text), `scripts/pagelib/pagecheck.py` (`claim_rows` or a sibling), `scripts/CONTRACT.md`,
  `09-qa.md`, `07p-site-round.md`, `docs/manual/use/check-a-page.md`, `docs/manual/reference/page-check.md`, `tests/test_page_check.py`.
- **Do:** `FACTS.md` keeps the fact in `value`; wording the owner approved for use as copy goes in rows labelled `copy: <slot>`
  (`copy: hero headline`). 07p: a headline quotes a `copy:` row or is new wording the owner approves on the board, never a fact's
  `value` as it stands. Page check: a new info-or-warn row `page:words` warns for each forbidden word (`_common.forbidden_terms`, the
  list `book-lint` already applies) found in the page's text (O6).
- **Tests:** copy `test_an_unbacked_number_fails_and_the_same_number_in_a_labelled_sample_is_listed_before_publishing` for a page with a
  forbidden word (warn, names it), a page without (pass), and a `copy:` row backing a number like any fact.
- **Done when:** the FACTS template and 07p state the split; the row warns on the fixture.

### G4-10 Docs: what a labelled sample, a new token and the Full tier really cost

- **Files:** `07p-site-round.md` (lines that say a sample is "shown as one"), `docs/manual/reference/page-check.md`,
  `skills/brand-creator/references/cascade.md` and `phases/10-book.md` (editions), `docs/manual/getting-started/choose-a-tier.md`,
  `docs/manual/use/make-the-brand-book.md`, `tests/test_skills.py`.
- **Do:** (a) A labelled sample passes the claims check and goes on the before-publishing list; no visible badge is required (O7).
  (b) Adding or removing a semantic token or a declared pair changes the book's counts (`roles`, `pairs`), so `book-lint` fails
  `counts:data` until the book is rebuilt, and an approved book then needs a new edition and G5: say so where an edition is explained.
  (c) In the Full tier the book also has the Adoption and Launch checklist chapters, and the book check fails without them.
- **Tests:** needles in `test_skills.py` for (a) and (b); a needle test for (c) on the manual page.
- **Done when:** the three facts are in the docs; nothing contradicts them.

### G4-11 The finish chain refreshes the brand's adapter files after the tokens

- **Files:** `templates/finish.sh.tpl`, `scripts/CONTRACT.md` (finish chain), `09-qa.md`, `tests/test_finish_chain_steps.py`,
  `tests/test_finish_chain.py`.
- **Do:** One guarded step after `tokens` and `contrast` and before `staleness --write`: when `BRAND.md`/`DESIGN.md` exist, run
  `adapters` again with the options a block-2 variable holds (`ADAPTERS_ARGS`, empty means skip with a line saying why); when the
  applied skill exists and there is no kit, run `applied-skill --yes`; with a kit, run `kit build --yes`. A command that refuses (a
  hand-edited file, a missing package) is a failed step with its message, and the chain goes on to `check` (the group 3 rule).
- **Tests:** copy `test_the_board_of_the_latest_round_is_linted_again_after_the_press_kit_and_before_staleness_and_check` for the order;
  a project with no adapter files skips the step; extend the order list in `test_the_template_names_every_step_the_cli_gates_by_tier`.
- **Done when:** a token change followed by `finish.sh` leaves `check` with no stale adapter, applied-skill or kit report.

### G4-12 fontcheck warns when a run drops a font an earlier run checked

- **Files:** `scripts/fontcheck.py`, `scripts/CONTRACT.md` (fontcheck), `tests/test_fontcheck.py`.
- **Do:** Before writing, read the previous report's `fonts`; a font in it that is outside `assets/fonts/`, still exists and is not in
  this run is a `fonts:dropped` WARN row naming it, with "name every font in one run, or kit build leaves it out". No merge.
- **Tests:** copy `test_a_named_font_is_checked_together_with_the_fonts_under_assets_fonts`: run with font A, then with font B → warn
  naming A; run with A and B → no warn; a deleted A → no warn.
- **Done when:** the per-font trap of the pilot run warns.

### G4-13 New projects keep the full-page site captures out of git

- **Files:** a new `templates/gitignore`, `scripts/new.py`, `scripts/CONTRACT.md` (new), `docs/manual/use/get-reference-pages-for-your-site.md`
  (one line: how to add it to an existing project), `tests/test_project.py` (or the test file of `new`).
- **Do:** `new` writes `.gitignore` from the template into the new project folder with `research/site-refs/*/1440-full.png` (O8);
  an existing `.gitignore` is never overwritten. The manual says what to add by hand to an older project.
- **Tests:** a new project has the file with that line; a folder that already has `.gitignore` keeps its bytes.
- **Done when:** both tests pass.

### G4-14 The mock-up warning leaves a page band alone

- **Files:** `scripts/pagelib/page_measure.mjs` (`tellFacts` boxes: a `band` flag), `scripts/pagelib/pagecheck.py` (`find_tells`,
  `styled-div-mock`), `skills/brand-creator/references/page-tells.json` (the measure text), `scripts/CONTRACT.md`, `09-qa.md`,
  `tests/test_page_check.py`, `CHANGELOG.md`.
- **Do:** A box that is a page band (O9) is not judged as a whole; its children still are. The two false warnings of the pilot
  calibration are the fixtures: a band with an `<h2>`, an index table whose cells hold status badges and a legend of three badges
  under it; and a band with an `<h2>` and a list of cards. A drawn app panel (a `<figure>` or `<div>` with a title line that is not a
  heading element) still warns, and so does one placed inside a band.
- **Tests:** copy `test_each_tell_is_found_on_a_page_built_to_show_it` with: the table band (no hit), the cards band (no hit), the app
  panel inside a band (hit on the panel), a `<section>` with no heading (judged as before).
- **Done when:** the two pilot false warnings are gone in the fixtures and every existing styled-div-mock test still passes.

### G4-15 The list share counts overlapping items once

- **Files:** `scripts/pagelib/page_measure.mjs` (`list_area`), `scripts/CONTRACT.md`, `page-tells.json` (measure text),
  `tests/test_page_check.py`.
- **Do:** `list_area` is the area of the union of the item boxes (each clipped to the box, as now), not their sum, so ten items
  stacked in one place (a fade carousel) count as one item. The union of axis-aligned rectangles is computed exactly (a sweep over the
  x edges is enough for the item counts a page has). Fix the overclaiming test comment ("a share of the box is never more than the
  whole") to say what now holds.
- **Tests:** copy the carousel test: ten stacked items with nine at `opacity: 0` and a head and a foot → the share is one item's
  area → warns; ten side by side → unchanged numbers; the exact `list_area` pinned for the drawn app panel.
- **Done when:** the overlap case warns and every existing list-share number is unchanged.

### G4-16 An error code needs its error word right beside it

- **Files:** `scripts/pagelib/pagecheck.py` (`status_codes`), `scripts/CONTRACT.md` (claims), `docs/manual/reference/page-check.md`,
  `09-qa.md`, `tests/test_page_check.py`.
- **Do:** O10. "Error 404", "404 Not Found", "404 · Nie znaleziono", "Błąd 404 – strona nie istnieje" and "Service Unavailable 503"
  stay error pages; "450 tickets, all gone", "Gone in 450 seconds" and "Ponad 400 produktów, żaden niedostępny" are counts (their
  numbers stay claims). The file-name rule (`404.html`) is unchanged.
- **Tests:** the direct `status_codes` (f) test gains those seven cases both ways; the browser (m) test keeps its counts.
- **Done when:** the three counts are claims again and every error page above is still one.

### G4-17 A try-out can be shared as a private page

- **Files:** a new `brand-creator inline <page> --out <file>` (find the inlining the review copy of a board and the book already use,
  in `scripts/board_lint.py`/`scripts/book.py`, and reuse it rather than writing a second one), `bin/brand-creator`,
  `scripts/CONTRACT.md`, `scripts/state.py` (a `tryout_url` key, apart from `review_url`), `templates/BRAND-STATE.md`,
  `07p-site-round.md` (the try-out step of G4-08), `docs/manual/use/get-reference-pages-for-your-site.md` (line 7 and the try-out step),
  `docs/manual/reference/commands.md`, `09-qa.md`, tests in `tests/test_site.py` (or the inline command's own file) and
  `tests/test_project.py`.
- **Do:** `inline` writes one self-contained HTML of a try-out page: its stylesheets inline, fonts, the logo and images as `data:`
  URLs, its scripts inline, no request to anywhere (a page that loads from another website is refused, exit 2, naming the URL); it
  writes only outside the project or under `tryout/`. With the owner's yes for claude.ai pages (the existing review-surface consent;
  do not edit the orchestrator's top section, whose budget is full), Claude publishes that file with the Artifact tool and records
  `tryout_url`; without it, the try-out stays a local page (O5).
- **Tests:** a page with tokens, a font and the logo inlines to one file with no external reference and renders the same first screen
  (compare a 390 still); a page with a remote font exits 2; `state --set tryout_url=...` is accepted and does not touch `review_url`.
- **Done when:** the manual no longer says "never publishes", and the published copy needs the owner's yes.

### G4-18 Owner checkpoint: the trigger evals

- **Not an implementer task.** After the owner says yes to the cost, the lead runs the billed trigger evals for every model-invoked
  skill (the 0.6.0 phrases "help me launch" and "start a brand called", and anything this group changes), as
  `docs/internals/manual-checks.md` describes, and records the result there. A failed trigger blocks the release until it is fixed.

### G4-19 Mutation ledger, release notes, the full run and a calibration on the pilot brand

- **Files:** `tests/mutation_ledger.py` (a `site-round` group: the idea warning off, `owner` refused, the stray-box tell never
  firing, the fontcheck warning off, the finish step skipped), `docs/internals/development.md` (the group list), `CHANGELOG.md`
  (one coherent set of bullets for the release; the idea line's "warns now, fails next release"), the plugin README if its table
  changes.
- **Do:** Each break is caught by a named test (add the G4-14 to G4-17 breaks: the band exemption off, a sum instead of the union,
  an error word anywhere, publishing without the yes). Then the whole suite: macOS (`tests/run-all.sh --smoke`) and Linux
  (`tests/docker/run.sh`, pytest and smoke in two calls with separate data folders), the docs checks and `claude plugin validate --strict`.
  Then the lead (never an implementer) runs `page-check` on a scratch copy of the pilot brand's site pages, as in the group 1
  calibration, and reports what changed against the last run.
- **Done when:** every group of the ledger catches its breaks; both systems end green; the calibration report lists no warning that
  is a known false one.

## Order and parallelism

G4-01 → G4-02 → G4-08 change the same 07p sections: one lane, in that order. G4-03 → G4-04 → G4-05 change the cold review: one lane.
G4-07, G4-14, G4-15 and G4-16 (the page check) are one lane, in that order. G4-06 (costs), G4-09 to G4-13 (copy, docs and small
code) are a fourth lane. G4-17 follows G4-08 in the first lane. G4-18 waits for the owner's yes; G4-19 runs last.

## Out of scope

- Nothing the retrospective raised. Only the pricing-card case of the mock-up warning (a grid of cards with badges inside a band) is
  left for the calibration in G4-19 to show whether it still warns falsely.
