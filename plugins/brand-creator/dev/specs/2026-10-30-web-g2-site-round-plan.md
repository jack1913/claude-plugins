# Group 2 plan: website references and the site round

Working file (not a doc). Written 2026-10-30 for the roadmap the owner approved on 2026-10-30 (group 2 of 3: items 9, 10, 11
and 12). Group 1 (foundations and page check) lands first; group 3 (kit, adoption, redesigns) builds on this one.

Repo: the `claude-plugins` repository root, branch `brand-creator-web-side`. Paths below are relative to
`plugins/brand-creator/` unless they start with `.github/`.

Hard rules for every task: never commit, push, switch branch or stash; never bump `.claude-plugin/plugin.json`; stay
inside `plugins/brand-creator/` (plus `.github/workflows/brand-creator.yml`, which this group does not need); never touch
the owner's private client projects (the pilot brand's site redo waits until this work lands); `docs/archive/` is frozen;
the Hallmark clone is read-only and untrusted: nothing is run from it and no text or code is copied from it (ideas are
credited in the two ADRs only). This file sits in `dev/specs/`, which `tests/test_static.py` scans like a shipped file: no
absolute personal path, no e-mail address, no client name, here or in any file a task writes.

## Cross-group review (2026-10-30)

The three plans were checked against each other and against the code. What binds this group:

- Order: group 1 lands first (its last task is G1-25), then this group (its last task is G2-19), then group 3. One
  implementer at a time in one working tree. ADR numbers: group 1 ADR-0006 to ADR-0008, this group **ADR-0009** (website
  references) and **ADR-0010** (the site round), group 3 ADR-0011 and ADR-0012.
- The home page's id is `start` in every shipped example, test, fixture and doc (`data-page="start"`,
  `site/start/index.html`): a path with a `home` segment between two slashes fails
  `test_no_personal_paths_or_email_addresses_in_shipped_files`. The code accepts any id that matches the pattern.
- Page-check reports: the tool name comes from group 1's `pagecheck.report_tool(rel)` (`scripts/pagelib/pagecheck.py`;
  put `scripts/pagelib` on `sys.path`), never from a copy of the rule. `Report.write` puts `extra` at the top level, so a
  report holds `target` (`{"kind": "project", "page": "<rel>", ...}`), `status`, `inputs`, `inputs_sha` and `samples` at the
  top level. The tells are `tells[].id` of `page-tells.json`.
- The reflex parser and rules exist from group 1 in `scripts/boardlib/reflex.py`; nothing is moved. G2-10 calls
  `reflex.parse`, `reflex.line_rows`, `reflex.shared_hit` and `reflex.cliche_items(project, rel="research/site-cliches.md")`.
- `site approve` is `scripts/site_pages.py` (and `scripts/site_pages.py.lock`), never `scripts/site.py`: a script named
  `site.py` in `scripts/` shadows the standard library's `site` module for every tool that puts `scripts/` on `sys.path`.
  The subcommand stays `site`.
- The CHANGELOG already says (from G1-13) that packs recorded with `staleness --write` read as stale after this update; G2-02
  does not repeat it.
- Group 1 already adds the `page-check` row to the orchestrator's `## Commands by phase`; G2-16 adds only `capture` and
  `site approve`.
- Baseline without a data directory: 1 failed (`test_setup_prereq.py::test_prereq_reports_ok_on_a_complete_machine`), 1227
  passed, 679 skipped. Run with `BRAND_CREATOR_DATA="$HOME/.claude/plugins/data/brand-creator-jack1913"`.

## Goal

A brand whose brief lists a site gets two optional steps after G4, in Standard and Full:

1. **Website references (P7w, gate G4w).** The owner names sites they like and dislike, and, with their OK for online
   research, Claude shows 4-6 groups of real sites (3+ each, captured screenshots) that serve the same visitor's job:
   what to take (structure, rhythm, how it serves the job) and what not (their look), plus the category's site clichés.
   The owner picks. Mirrors the style research (ADR-0002): a board, a recorded gate, a skip only in the owner's words,
   never an invented reference, a stop without web access.
2. **The site round (P7p, gate G4p).** Hero first, in 2-3 variants built from the picked references and the brand; each
   variant page-checked (both tiers, group 1), captured in four stills and cold-reviewed (fixed inputs, verdict first).
   The owner picks a hero, then the other pages are built; the last board tags every choice `rule` (cites where it was
   decided) or `example` (may change). G4p approves; `site approve` copies the pages into `site/` with `site/site.json`;
   `check` gates them; an opt-in `site` chapter shows them in the book.

Approved pages are **references**, never fill-in templates. Production sites are built in product repositories (scope
ADR from group 1). 8-12 **layout references** keyed to the visitor's job (structure only) ship with the plugin, and every
built page records the one it used.

## Design decisions

Defaults the owner may change are marked **(default, owner may change)**.

1. **Rounds, not a new folder tree.** Both boards are ordinary rounds (`rounds/r<N>/board.html`), so the hook, `freeze`,
   `shot`, the review surface and `check`'s "latest round" logic work unchanged. New `data-board` kinds: `site-refs` and
   `site` (a round from 2 on, never a reset round, like `motion`). The style gate's "rejected round" logic ignores both, as
   it ignores motion boards.
2. **Two new gates: `G4w` (website references) and `G4p` (the site's reference pages)**, added to `GATE_IDS` after `G4`.
   **(default, owner may change: the names)**
3. **The online-research OK is a recorded key, `site_research`: `auto` (not asked) | `online` | `links-only` | `none`.**
   Searching reveals the category to third parties, so it is asked once (like the naming privacy OK) and recorded with
   `state --set`. `capture --url` refuses to fetch anything unless it is `online` or `links-only`.
4. **Only when BRIEF lists a site; Standard and Full only.** The lint reads the `Required surfaces:` line of
   `brief/BRIEF.md` with an English and Polish word list (`site`, `website`, `web page`, `landing page`, `www`, `stron*`,
   `witryn*`); the untouched template line `(site, app icon, ...)` does not count. Any other language is "not verified":
   the owner adds the word `site` to the line. **(default, owner may change: EN+PL word lists)**
5. **Order: after G4 (and the motion round), before the book.** The book's `site` chapter needs `site/site.json`.
6. **No re-arm after a rejected site round** (unlike ADR-0002's style gate): the site round is optional and late; "None of
   these" on a site board means new variants, or a new references board and a new G4w, the owner's choice. Judgement, not
   linted. **(default, owner may change)**
7. **`brand-creator capture` is one new render.mjs subcommand** for both jobs: stills of a project page (four first-screen
   views and one full page, written beside the page in `shots/` with `capture.json`), and stills of a real site
   (`--url`, into `research/site-refs/<name>/`, with small JPEG thumbnails the board inlines). It is the only path that
   lets Chromium reach the network, and only with `--url`. It writes no report in `assets/_checks/`.
8. **Provenance instead of trust.** A reference screenshot on the board whose bytes match a `capture.json` thumbnail of
   the same address passes; one that matches none is a warning ("not matched to a capture"), never silent.
9. **Hero first is linted**: a pages board needs an earlier hero board and names the picked hero (`data-hero`).
10. **Cold review: in-thread by default; an agent only after the fleet gate** (one `brand-creator:brand-reviewer` call per
    hero variant). In-thread it is not blind, and `cold-review.md` says `by: in-thread`. Required on hero variants,
    optional on pages. **(default, owner may change)**
11. **A `rule` choice must cite where it was decided** (its `data-source` text is found in `BRAND-STATE.md`,
    `DECISIONS.md` or `decisions/*.md`); an `example` needs nothing. This is the provenance the pilot brand's recipe lacked.
12. **Layouts allow `own:<word>`** with a warning, so the references never become a menu of templates.
13. **The orchestrator description changes in this group only** (production sites stay out; website references and
    reference pages come in), with only a pointer row in the phase map. **(default, owner may change)**
14. **Sample data** follows group 1's page-check: a labelled `[data-sample]` element passes, an unlabelled claim not in
    FACTS fails. **(default, owner may change)**
15. **The plugin's own social kicker** (`templates/social/post-1x1.html:20`) is not touched here (group 1 reports it).
    **(default, owner may change)**
16. **The pilot brand untouched.** No task reads or writes the owner's private client projects. **(default, owner may
    change)**

## Architecture

```text illustrative
skills/brand-creator/references/
  page-layouts.json                 12 layout references keyed to the visitor's job (structure only)        G2-03
  phases/07w-website-references.md  P7w: the online-research OK, the board, G4w                              G2-07
  phases/07p-site-round.md          P7p: hero first, cold review, pages, choices, G4p, site approve           G2-12
templates/
  site-refs-board.html              data-board="site-refs" (built on style-board.html's frame)               G2-05
  site-cliches.md                   research/site-cliches.md skeleton ("Avoid unless argued")                 G2-05
  site-board.html                   data-board="site" data-site-stage="hero|pages" (motion-board's frame)    G2-08
  book/site.md                      the opt-in book chapter, with {{site}}                                   G2-15
scripts/
  render.mjs                        + capture (project page, or --url into research/site-refs/)              G2-04
  site_pages.py (+ .lock)           site approve: rounds/r<N>/<page>/ -> site/<page>/, site/site.json         G2-13
  boardlib/boardpage.py             KINDS + "site-refs", "site"; is_site_refs_board()                        G2-05, G2-08
  boardlib/siteboard.py             every site-refs:* and site:* lint row; brief_lists_site()               G2-05..G2-11
  boardlib/sitedata.py              load_layouts(), site.json schema and validate_site(), rewrite_urls()    G2-03, G2-13
  board_lint.py                     dispatch to siteboard; page:data-board rules; style gate ignores both  G2-05, G2-08
  check.py                          site:record, site:pages, site:stills                                     G2-14
  booklib/bookdata.py, bookgen.py   opt-in chapter "site", block {{site}}                                     G2-15
  lib/_common.py                    GATE_IDS + G4w, G4p                                                      G2-02
  state.py                          ENUMS site_research                                                      G2-02
```

Project files the steps write:

```text illustrative
research/site-refs/<name>/   capture --url: 1440.png 390.png 1440-full.png thumb-1440.jpg thumb-390.jpg capture.json
research/site-refs/owner/    screenshots the owner sent (not captured; the board says so in the caption)
research/site-cliches.md     the category's site clichés (Avoid unless argued) -> the hero variants' reflex test
research/YYYY-MM-DD-site-refs.md   notes: claims with URLs and the date read
rounds/r<N>/board.html       site-refs board (G4w after it)
rounds/r<M>/board.html       site board, hero stage: rounds/r<M>/<Variant>/index.html, shots/, cold-review.md
rounds/r<K>/board.html       site board, pages stage: rounds/r<K>/<page-id>/index.html, shots/; a choices section (G4p after it)
site/<page-id>/index.html    approved reference pages (site approve), shots/ (capture), page-check report per page
site/site.json               the decision record: pages, layout, sha256, choices tagged rule|example with sources
```

### Interfaces this group relies on from group 1

Read group 1's `scripts/CONTRACT.md` "Page check" section and its code before G2-09 and G2-10. These are group 1's names
(its plan, section 4); import them, never copy them. If a landed name differs, use the landed one; never change group 1's
code except where a task here says so.

| From group 1 | Interface |
| --- | --- |
| G1-13 to G1-18 (page-check, brand-rule tier) | `brand-creator page-check <page.html> --project <dir>`; exit 0 pass (warnings allowed), 1 a brand-rule row fails, 2 usage, 3 cannot run. One report per page at `assets/_checks/<tool>.json`, `tool = pagecheck.report_tool("<project-relative posix path>")` = `page-check/<slug>-<hash6>` (`scripts/pagelib/pagecheck.py`). Top-level keys: `target` (`{"kind": "project", "page": "<rel>", "from": null, "url": null}`), `status` (`pass`, `fail`, `not-verified`), `inputs` (the page and every project file it loaded, tokens.css included), `inputs_sha`, `samples`. |
| G1-19 (reflex tier) | Rows `tell:<id>` with status `warn`; `<id>` is a `tells[].id` of `skills/brand-creator/references/page-tells.json` (EN+PL word lists). |
| G1-03 to G1-05 (reflex test) | `scripts/boardlib/reflex.py`: `parse`, `hits`, `norm`, `known`, `ai_default_ids`, `cliche_items(project, rel=...)`, `ground_words`, `line_rows(parsed, ids, cliches, ground, sources)` (suffixes `reflex-format`, `reflex-ids`, `reflex-count`, `reflex-grounded` with group 1's severities) and `shared_hit(parsed_list)`. |
| G1-01 (ADRs) | ADR-0006 (reflex test), ADR-0007 (scope: brand-creator owns the brand side of the web), ADR-0008 (text grounds). This group takes ADR-0009 and ADR-0010. |
| G1-17 (`[data-sample]`) | page-check passes sample data inside a labelled `[data-sample]` element and lists it in `samples`. |
| G1-20 (orchestrator) | Group 1 adds only a `## Commands by phase` row (below the top); G2-16 measures the top first. |

### Interfaces this group provides to group 3

- `site/site.json` (schema 1, below) and `scripts/boardlib/sitedata.py`: `load_site()`, `validate_site()`,
  `rewrite_urls()` (group 3 copies reference pages into the kit with it), `load_layouts()`.
- `brand-creator capture <page>` (stills + `capture.json` with `inputs`, so staleness is detectable).
- `check` rows `site:record`, `site:pages`, `site:stills`.
- `skills/brand-creator/references/page-layouts.json` (the web-page recipe's "references" step points at it).
- The cold-review prompt fragment in `references/prompt-fragments.md` (the kit test reuses it).

### `site/site.json`, schema 1

```json
{
  "schema": 1,
  "approved": "2026-11-04 approved start, pricing; rules c1 c3",
  "round": 9,
  "hero": "Ledger",
  "pages": [{"id": "start", "path": "site/start/index.html", "layout": "walkthrough", "sha256": "<hex>"}],
  "choices": [
    {"id": "c1", "text": "The stamp appears once per view", "tag": "rule", "source": "DECISIONS.md 14", "pages": ["start", "pricing"]},
    {"id": "c2", "text": "Pricing sits under the stages", "tag": "example", "source": "", "pages": ["start"]}
  ]
}
```

Page ids match `^[a-z][a-z0-9-]{1,31}$`; `layout` is a page-layouts id or `own:<word>`; `tag` is `rule` or `example`; a
rule has a non-empty `source`; `pages` (optional, default all) names page ids of the record. The home page's id in every
shipped example is `start` (see "Cross-group review").

## Tasks

Order keeps the suite green after each task. Every task ends with: the subset tests, the full pytest run, and the docs
checks when a Markdown file outside `skills/`, `templates/` and `evals/` changed. Every user-visible change adds a line
under `## [Unreleased]` in `CHANGELOG.md` (Added / Changed / Fixed, in that order, the file's existing voice: what changed
for the user, commands in backticks, no commit log). Before editing any shipped text, search the tests for pinned
phrases: `rg -n -F '<a phrase you change>' tests/` and update the pin in the same task.

Test labels follow `09-qa.md`: a test marked (m) breaks a scratch copy with `mutate()` or `mutate_json()` (`mutateText()` in
node tests) and must call one of them; a test marked (f) uses a purpose-built failing input and must not call them
(`test_qa_phase_lists_every_check_command_and_cites_real_deliberate_break_tests` enforces both). Every new lint row or
refusal gets at least one such test, cited in its `09-qa.md` row.

Common verify commands (run from `plugins/brand-creator/` unless stated):

```bash
# a subset while iterating
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4 --dist worksteal -k "<expr>"
# the whole suite (set BRAND_CREATOR_DATA to a set-up data dir when one exists; a NOT VERIFIED skip is not a pass)
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4 --dist worksteal
# node tests that drive Chromium (skip without a set-up data dir)
node --test --test-timeout=180000 "tests/node/*.test.mjs"
# docs, from the repository root (CI runs the docs check with --strict)
python3 .github/scripts/check-docs-standard.py --strict \
  && npx markdownlint-cli2 "plugins/brand-creator/**/*.md" \
  && lychee --config lychee.toml --root-dir "$(pwd)" 'plugins/brand-creator/**/*.md'
```

The baseline of the untouched branch has one known failure (`test_setup_prereq.py::test_prereq_reports_ok_on_a_complete_machine`,
no Chromium) and 679 skips without `BRAND_CREATOR_DATA`; report both, never call them passes. Set
`BRAND_CREATOR_DATA="$HOME/.claude/plugins/data/brand-creator-jack1913"` (the owner's set-up data directory; the tests copy
it and never write into it). Do not run `setup` without the owner's yes (it downloads Chromium).

---

### G2-01 Two ADRs: website references, and the site round makes reference pages

- **Roadmap:** 9, 11 (decisions). **Depends on:** G1-01 (ADR-0006 to ADR-0008 exist), and group 1 complete (G1-25).
- **Files:** `docs/adr/ADR-0009-website-references-before-any-site-page.md`,
  `docs/adr/ADR-0010-the-site-round-makes-reference-pages-not-templates.md`, `docs/adr/README.md`.
- **Behaviour:** docs only. The numbers are fixed (group 1 holds 0006 to 0008, group 3 takes 0011 and 0012); check that
  `docs/adr/README.md` ends at ADR-0008 before writing. Follow `docs/adr/ADR-TEMPLATE.md`: Status `accepted`, Date
  `2026-10-30`, Source: link only files that exist now (ADR-0002, ADR-0005, group 1's scope ADR ADR-0007); name the files
  later tasks create in code spans, not links (lychee checks links). Cite sources by file or heading, never `file:line`.
  No client name in either ADR: say "a real brand".
  - ADR-0009: Context (a real brand's site was built by hand from an undecided default approved in one word; the owner
    wants to be asked for liked and disliked sites or offered research of the best real sites, with a recorded gate like
    ADR-0002; the brand-skill-for-product-repositories ask belongs to group 3's ADR-0011, not here). Decision: P7w after
    G4, Standard and Full, only when BRIEF
    lists a site; the `site-refs` board (visitor's job, the category's site norm, the owner's liked/disliked sites, 4-6
    groups of 3+ real sites each with a captured screenshot, take = structure, rhythm, how it serves the job; avoid = their
    look; the category's site clichés in `research/site-cliches.md`); the online-research OK recorded as `site_research`
    (it reveals the category); `capture --url` the only network path; gate G4w, skipped only in the owner's words; without
    web access say so and stop; never invent a reference (a screenshot not matched to a capture warns). Deliberate
    difference from ADR-0002: no re-arm after a rejected site round. Consequences: one more board; the site round waits
    for G4w; a reference's screenshot stays on the research page. Credit: "The idea of starting a page from the visitor's
    job comes from Hallmark (MIT, Hallmark contributors), read on 2026-10-29; nothing was copied."
  - ADR-0010: Context (the same real brand's site corrections were brand-rule conflicts; a recipe pinned undecided
    defaults as instructions). Decision: P7p after G4w; hero first, 2-3 variants; each page-checked (both tiers), captured in four
    stills, cold-reviewed with fixed inputs and the verdict first (`ship` or `fix`), in-thread by default and an agent only
    after the fleet gate; the owner picks a hero, then the other pages; a choices section tags every choice `rule` (with
    where it was decided) or `example`; G4p; `site approve` writes `site/` and `site/site.json`; `check` gates them; an
    opt-in `site` book chapter; 8-12 layout references keyed to the visitor's job, structure only, `own:<word>` allowed;
    approved pages are references, never fill-in templates; production sites are built in product repositories; the
    orchestrator's description changes accordingly. Consequences: two to three more rounds; page-check from group 1 is a
    precondition; the book can show the pages. Credit: "Hero first with a cold review that answers ship or fix first, and
    layouts named after what the visitor came to do, are ideas from Hallmark (MIT); rewritten, nothing copied."
  - README: two rows in the table, in number order.
- **Tests:** none (docs).
- **Verify:** the docs commands.
- **Acceptance:** both ADRs pass `check-docs-standard.py`, markdownlint and lychee; README lists them; no Hallmark text.

### G2-02 Gates G4w and G4p, and the `site_research` key

- **Roadmap:** 9, 11. **Depends on:** none.
- **Files:** `scripts/lib/_common.py` (`GATE_IDS`), `scripts/state.py` (`ENUMS`, docstring), `templates/BRAND-STATE.md`,
  `scripts/CONTRACT.md` ("BRAND-STATE.md frontmatter"), `tests/test_project.py`, `tests/test_skills.py`
  (`test_stale_pointers_name_the_style_step_in_the_contract_the_tier_page_and_the_state_template`), `CHANGELOG.md`.
- **Behaviour:**
  - `GATE_IDS = ("G0", "G1", "G1s", "G2", "G2b", "G3", "G4", "G4w", "G4p", "G5", "G6", "G7")`. `state` prints them in that
    order; `--record` and `--require` accept them; an older project without the keys gets them on `--record`.
  - `ENUMS["site_research"] = ("auto", "online", "links-only", "none")`; any other value exits 2 with the list and writes
    nothing.
  - Template: after `G4: ""` add `G4w: ""  # website references pick (or "skipped by owner"); the site round waits for it`
    and `G4p: ""  # the site's reference pages approved (site approve needs it)`; after `review_url` add
    `site_research: auto  # online research for website references: auto (not asked yet) | online | links-only | none`.
  - CONTRACT: add `site_research (auto|online|links-only|none: the owner's answer to online research for website
    references; capture --url needs online or links-only)` to the key list and change `gates (G0 G1 G1s G2 G2b G3 G4 G5 G6
    G7)` to `gates (G0 G1 G1s G2 G2b G3 G4 G4w G4p G5 G6 G7)`; update the pinned string in `test_skills.py`.
  - Note: `scripts/lib/*.py` is hashed by `staleness`, so a project that recorded `staleness --write` sees its packs as
    stale after this change (as after any lib change). G1-13 already says so in the CHANGELOG; check that the sentence is
    there and do not add a second one.
- **Tests (new, `tests/test_project.py`):**
  - `test_state_records_and_requires_the_website_gates` (f): on a new project, `state --require G4p` exits 1 naming G4p;
    `--record G4w "skipped by owner"` then `--require G4w` exits 0; the summary lists `G4w recorded` between G4 and G4p.
  - `test_site_research_takes_only_its_four_answers` (f): `--set site_research=online` and `links-only` pass;
    `--set site_research=yes` exits 2, names the four values, and BRAND-STATE.md is byte-identical.
  - `test_an_older_project_without_the_website_gates_gets_them_on_record` (m): `mutate()` removes the `G4w:` line; record
    G4w; the key is back.
- **Docs:** CONTRACT (above); CHANGELOG `### Added`: "`state` knows two more gates for the site work, G4w (website
  references) and G4p (the site's reference pages), and the `site_research` answer (online research for website
  references)." (The staleness note is already in the CHANGELOG from G1-13.)
- **Verify:** `-k "website_gates or site_research or stale_pointers or state_record"`, then the full suite.
- **Acceptance:** new tests pass; the full suite has no new failure.

### G2-03 Layout references: `page-layouts.json`

- **Roadmap:** 10. **Depends on:** none.
- **Files:** `skills/brand-creator/references/page-layouts.json` (new), `scripts/boardlib/sitedata.py` (new),
  `skills/brand-creator/references/_index.md`, `skills/brand-creator/SKILL.md` (References section, below
  `## Round mechanics`: one bullet), `tests/test_skills.py`, `CHANGELOG.md`.
- **Behaviour:** written fresh in this plugin's voice; do not open Hallmark's macrostructures or anatomy while writing.
  Shape: `{"version": 1, "$description": "...", "how_to_use": [...], "items": [...]}`; each item has exactly the keys
  `id, job, leads_with, parts, action, ends_with, not_for` (`parts` a list of 2-8 strings). `how_to_use` says, in your own
  words: start from the visitor's job in BRIEF.md and FACTS.md, never from how a liked site looked; structure only (which
  part leads, the order, where the action sits, how the page ends), every look value comes from the tokens and G4 rules;
  record the id on the page as `<body data-layout="<id>">`, or `own:<word>` with the reason on the card; a layout is a
  reference, not a template: move, drop or merge parts when the material says so; equal tiles in threes, a label over every
  heading and the stock hero/steps/questions/call-to-action band are tells, not layouts. The twelve items (ids and jobs;
  write the other fields as one plain sentence each, no colour, type, size or spacing words):
  `one-step` (join, subscribe or sign up with nothing to compare), `walkthrough` (understand how a service will run for
  them before handing it something important; stages as the visitor lives them, each with the real artefact, stages of
  different weight), `catalogue` (choose from a range and buy), `single-product` (decide to buy one thing), `long-read` (be
  persuaded by an argument or learn a subject), `letter` (trust a person or a small practice before getting in touch),
  `workbench` (try a software tool; the real screens lead), `index` (find one item among many), `schedule` (attend or book
  a time), `place` (visit a physical place: today's hours, the address, the route lead), `portfolio` (hire someone on the
  strength of their work), `questions` (decide when doubts about cost, risk or rules stand in the way).
  - `sitedata.py` (standard library, module docstring, no clock, no network): `LAYOUTS_FILE` (the path from the plugin
    root), `layout_problems(doc) -> list[str]` (the rules the test enforces) and `load_layouts() -> dict[str, dict]`
    (raises `CliError(EXIT_CANNOT, ...)` naming the file when it is unreadable or has problems: a plugin defect).
- **Tests (`tests/test_skills.py`):**
  - `test_page_layouts_are_structure_only_and_keyed_to_the_visitors_job` (f): 8-12 items, unique ids
    `^[a-z][a-z0-9-]{2,31}$`, exact key set, `layout_problems(doc) == []`, `how_to_use` mentions `data-layout`.
    `layout_problems` flags: a value matching `#[0-9a-fA-F]{3,8}\b`, a unit `\b\d+(\.\d+)?\s?(px|rem|em|pt|vh|vw|%)\b`, a
    look word `\b(colou?rs?|fonts?|typefaces?|serif|gradients?|shadows?)\b` in any item value, and `parts` that hold both
    `three` and `steps`.
  - `test_the_layout_check_catches_a_look_value` (m): `mutate_json()` on a scratch copy adds `"24px"` to one item's
    `leads_with`, then a look word, then a fourth key: each makes `layout_problems` non-empty.
  - The existing `test_every_link_resolves_and_every_reference_is_linked_from_skill_md` covers the SKILL.md link.
- **Docs:** `_index.md` row `| [page-layouts.json](page-layouts.json) | Layout references for a site's pages, keyed to what
  the visitor came to do: structure only, never a look |`; SKILL.md bullet `- [page-layouts.json](references/page-layouts.json):
  layout references for the site round, keyed to the visitor's job (structure only).` No CHANGELOG line yet (it ships with
  the site round, G2-12).
- **Verify:** `-k "page_layouts or layout_check or every_link_resolves"`; full suite.
- **Acceptance:** 12 items, test green, SKILL.md top length unchanged.

### G2-04 `brand-creator capture`: stills of a page, or of a real site

- **Roadmap:** 9 (render path for `--url`), 11 (variant stills). **Depends on:** G2-02.
- **Files:** `scripts/render.mjs` (`cmdCapture`, USAGE, header comment, dispatch), `bin/brand-creator` (dispatch line
  `capture)    js render.mjs capture "$@" ;;` and a help line under "checks and renders"), `scripts/CONTRACT.md` (new
  section `## Website references and reference pages` with `### capture`, Contents entry, Project file conventions lines),
  `skills/brand-creator/references/phases/09-qa.md` (row), `tests/test_site.py` (new), `tests/node/capture.test.mjs` (new),
  `docs/internals/manual-checks.md` (row and section "Website capture of a real site": never run), `CHANGELOG.md`.
- **Behaviour.** Before coding, confirm the Playwright options you use (`page.screenshot` `fullPage`, `clip`, `type`,
  `quality`; `browser.newContext` `acceptDownloads`, `colorScheme`, `viewport`) in current docs (Context7, playwright).
  - `capture <page.html> [--project DIR] [--wait MS] [--timeout MS]`: the page is confined to the project. Output folder:
    `<the page's folder>/shots/` (fixed). Refuse with exit 2 a page under `history/` or in a round before the latest (the
    rule of `readOnlyWhy`; generalise it into one helper both commands use). Serve the project with `startServer`, block
    and record non-local requests (`instrument`, `watch`), wait as `shot` waits (load, `document.fonts.ready`, lazy images,
    `--wait`, `waitAnimations`). Write, each only on a byte change (`writeIfChanged`): `1440-light.png`, `1440-dark.png`
    (viewport 1440x900), `390-light.png`, `390-dark.png` (390x844), first screen only, device scale 1; and
    `1440-light-full.png` (full page at 1440, light, at most 12000 css px tall; taller is cut and recorded). Then
    `shots/capture.json`: `{"schema": 1, "tool": "capture", "source": {"page": "<rel>"}, "date": "<today()>", "views":
    [{"view": "1440-light", "width": 1440, "height": 900, "scheme": "light", "file": "1440-light.png", "sha256": "<hex>"},
    ...], "full": {"file": "1440-light-full.png", "sha256": "...", "height": N, "cut": false}, "inputs": [{"path": "<rel>",
    "sha256": "<hex>"}], "problems": ["<non-local request, page error, failed local request>"]}`; `inputs` are the page and
    every project file the server answered (as the motion reports record them). Exit 0 when written (`problems` are
    recorded, not gated: page-check gates the page), 3 without Chromium. `capture.json` is rewritten only when a still, an
    input or a problem changed; otherwise the old file, its `date` included, stays byte for byte (a re-run must not make
    the board-lint report that reads it stale).
  - `capture --url <url> --name <name> [--project DIR] [--timeout MS]`: exit 2 unless the address parses with protocol
    `http:` or `https:` ("capture takes an http(s) address"); exit 2 unless `--name` matches `^[a-z0-9][a-z0-9-]{1,40}$`;
    exit 2, nothing fetched, unless `site_research` in BRAND-STATE.md is `online` or `links-only` (message: "capture --url
    needs the owner's answer to online research first: ask it (07w-website-references), then `brand-creator state --set
    site_research=online` (or links-only)"); exit 2 when `research/site-refs/<name>/capture.json` exists for another
    address. A fresh context per run, no route blocking, `acceptDownloads: false`, default timeout 45000 ms. Write into
    `research/site-refs/<name>/`: `1440.png` (1440x900 first screen), `390.png` (390x844), `1440-full.png` (cap 12000 css
    px), `thumb-1440.jpg` (about 480 px wide) and `thumb-390.jpg` (about 160 px wide), both JPEG at quality about 0.75,
    downscaled in a blank page with a canvas (as `pngDiff` decodes pictures); and `capture.json` with `"source": {"url":
    ..., "final_url": ..., "status": 200, "title": "<document.title, at most 120 characters>"}`, the views, `full` and
    `"thumbs": [{"file": "thumb-1440.jpg", "width": 480, "sha256": ...}, ...]`. A response status of 400 or more, a
    navigation error or a timeout: exit 1, "could not capture <url>: <why>; leave the reference out or ask the owner for a
    screenshot", nothing written. Never writes `assets/_checks/`.
  - CONTRACT `### capture`: both forms, outputs, `capture.json` fields, exit codes, "the only command that lets Chromium
    reach the network, and only with `--url`", "never captures a page behind a login (the phase file says so; the tool
    cannot tell)". Project file conventions: `research/site-refs/<name>/ ...`, `research/site-refs/owner/`,
    `<page folder>/shots/`.
  - 09-qa row: ``| `capture <page.html>`, `capture --url <url> --name <name>` | none (stills and `capture.json` beside the
  page in `shots/`, or in `research/site-refs/<name>/`) | an address that is not http(s); `--url` before the owner answered
  the online-research question (`site_research` not `online` or `links-only`), exit 2 and nothing fetched; a page in
  `history/` or a round before the latest; a site that does not load (exit 1, nothing written); no Chromium (exit 3) |
  <the tests below> |``.
- **Tests:**
  - `tests/test_site.py` (no Chromium needed: the refusals come before the browser starts):
    `test_capture_refuses_an_address_that_is_not_http` (f: `file:///etc/hosts`, exit 2, no `research/site-refs/`);
    `test_capture_url_needs_the_owners_online_research_answer` (f: `site_research: auto` exits 2 naming `state --set
    site_research`; after `--set site_research=links-only` the same call no longer names it: exit 1 or 3 is accepted, the
    address is `https://example.invalid/`, which cannot resolve);
    `test_capture_url_needs_a_plain_name` (f: `--name "My Site"` exits 2);
    `test_capture_refuses_a_page_in_an_earlier_round` (f: page in `rounds/r1/` while `rounds/r2/` exists: exit 2, no
    `shots/`).
  - Node, also: `capture: a second run on an unchanged page leaves capture.json byte for byte` (f).
  - `tests/node/capture.test.mjs` (skip without setup, as `render.test.mjs` does):
    `capture: a project page gets four first-screen stills, a full page and a record of what it loaded` (f);
    `capture: a non-local request on a project page is recorded, never fetched` (f);
    `capture --url: a page served over http is captured into research/site-refs with its thumbnails` (f: a node `http`
    server on 127.0.0.1 in the test; `site_research=links-only` set with `bc state --set`);
    `capture --url: a 404 writes nothing and exits 1` (f).
- **Docs:** CONTRACT, 09-qa, manual-checks row; CHANGELOG `### Added`: "`brand-creator capture` takes stills of a page in
  four views and a full page, beside it in `shots/` with a record of what it loaded; with `--url` it captures a real site
  into `research/site-refs/<name>/`, only after the owner answered the online-research question."
- **Verify:** `-k "capture or qa_phase_lists_every_check_command"`; `node --test --test-timeout=180000
  tests/node/capture.test.mjs`; full suite; docs commands.
- **Acceptance:** refusals tested without Chromium; node tests pass on a set-up machine (or are reported NOT VERIFIED);
  09-qa row present and its cited tests exist.

### G2-05 The website references board, part 1: template, kind, placement, gate rows, sections

- **Roadmap:** 9. **Depends on:** G2-02.
- **Files:** `templates/site-refs-board.html` (new), `templates/site-cliches.md` (new), `scripts/boardlib/boardpage.py`,
  `scripts/boardlib/siteboard.py` (new), `scripts/board_lint.py`, `tests/test_site_refs_board.py` (new),
  `tests/helpers.py` (`fill_site_refs_board`), `tests/test_skills.py` (add the two board templates to
  `test_templates_are_self_contained_and_avoid_the_ai_default_cluster`), `scripts/CONTRACT.md` (Board contract),
  `skills/brand-creator/references/board-contract.md`, `09-qa.md`, `CHANGELOG.md`.
- **Behaviour:**
  - Template: copy `templates/style-board.html`'s frame (tokens, header, CSS, contents list, theme switch, reply composer);
    `<body data-round="[[fill: N]]" data-board="site-refs">`; sections `visitor-job` (who visits, the job they came to do,
    the one action that serves it), `norm` (what most sites in the category do), `owner-sites` (an `<ul>` of
    `<li data-like="like|dislike">` with a link or an inlined screenshot and `data-field="why"`, or one line saying the owner
    named none), one `<article class="group" data-section="group" data-name="[[fill: Name one]]">` (with optional
    `data-layout`, a `data-field="idea"`, and `data-field="references"`: an `<ol>` of 3 `<li>`, each an `<a href>`, a
    `<figure>` with `<img data-field="shot" src="[[fill: data:image...]]" alt>` and `<figcaption>`, a `data-field="take"`
    and a `data-field="avoid"`), an HTML comment `<!-- [[fill: articles for groups two to four (up to six) ...]] -->`,
    `site-cliches` (a list), `none-of-these`, `my-call`, `questions` (question 1 multi-pick `data-multi="true"` over the
    groups; question 2 confirms the liked and disliked sites), `reply`. Self-contained: no network address in `src`/`href`
    except the references' own links, system font stack, light and dark.
  - `templates/site-cliches.md`: like `templates/cliches.md`, for sites: "Site clichés seen" table (cliché, kind: layout
    / copy / imagery / interaction, seen in, share), "Avoid unless argued" bullets ("They go into each hero variant's
    reflex test; a variant may still use one, but its card must argue why"), no "Forbidden" section (the shot of the
    references board quotes them).
  - `boardpage.py`: `KINDS = ("pick", "refine", "style", "motion", "site-refs")`; `MIN_GROUPS = 4`; `group_count(root)`,
    `is_site_refs_board(root, folder_round)` (declares `site-refs` and its own round, at least `MIN_GROUPS` named groups
    with content), in the style of `is_style_board`.
  - `siteboard.py` (module docstring like `motionboard.py`'s; standard library; no clock, no network):
    `SITE_WORDS` regex; `brief_lists_site(project) -> tuple[bool, str]` (reads the value after `Required surfaces:` in
    `brief/BRIEF.md`, case-insensitive; a value wrapped in parentheses is the untouched template line and does not count;
    the detail names the line); `refs_gate_rows(rep, project)`:
    `site-refs:tier` (fail unless tier is standard or full: "the site work is Standard and Full"), `site-refs:brief`
    (fail unless BRIEF lists a site: "the website references run only when brief/BRIEF.md lists a site under Required
    surfaces, in the owner's words; ask the owner"), `site-refs:g4` (fail without G4: "website references come after the
    system rules (G4)"), `site-refs:research` (fail while `site_research` is `auto` or missing: "ask the owner the
    online-research question first and record it: state --set site_research=online|links-only|none"),
    `site-refs:cliches-file` (fail unless `research/site-cliches.md` has 3+ bullets under `## Avoid unless argued` that are
    not `(...)`).
  - `board_lint.py`: in the `page:data-board` chain, before the existing branches: a `site-refs` board in round 0 or 1 or in
    a round listed in `reset_rounds` fails ("a website references board is a round of its own from round 2 on"). Add
    `check_site_refs(rnd)`: `refs_gate_rows`; `need()` for `visitor-job`, `norm`, `owner-sites`, `site-cliches`,
    `none-of-these`; `check_my_call()`; `check_questions(need("questions", ...))`; `need("reply", ...)`; `groups:count`
    (fail under 4, warn over 6). `style_rearmed` drops pages whose kind is `site-refs` (as it drops `motion`). Inputs of the
    lint report: add `brief/BRIEF.md` and `research/site-cliches.md` when they exist. Update the module docstring.
  - CONTRACT: `data-board="pick|refine|style|motion|site-refs"` in the Board contract paragraph; a new subsection
    `### The website references board (data-board="site-refs")` with its section table and the rows of this task.
    board-contract.md: a `Two templates` row and a section `## Website references board (after G4)`.
- **Tests (`tests/test_site_refs_board.py`;** fixture `proj`: Standard project, `install_fixture`, G3 and G4 recorded,
  `site_research=online`, BRIEF `Required surfaces: site, social`, `research/site-cliches.md` with three bullets, an empty
  `rounds/r2/` holding `fill_site_refs_board(...)` as `board.html`; groups Ledger, Atlas, Quay, Harbour, each with three
  references (rows of G2-06 are not there yet)**):**
  `test_a_filled_site_refs_board_passes` (f, the baseline: exit 0);
  `test_a_site_refs_board_needs_standard_or_full` (m: `mutate()` the tier line to quick);
  `test_a_site_refs_board_needs_a_site_in_the_brief` (m: the surfaces line without a site word);
  `test_the_untouched_brief_template_line_is_no_site` (f: the template's `(site, app icon, ...)` line);
  `test_a_polish_brief_counts_strona_as_a_site` (f: a BRIEF written with `- Required surfaces: strona www, social`
  passes `site-refs:brief`);
  `test_a_site_refs_board_waits_for_g4` (f);
  `test_a_site_refs_board_waits_for_the_online_research_answer` (m: `site_research: auto`);
  `test_a_site_refs_board_is_round_2_or_later_and_never_a_reset_round` (f: in r1; in a round listed in `reset_rounds`);
  `test_the_style_gate_never_counts_a_site_refs_board_as_the_rejected_round` (f, mirroring
  `test_motion_board.py::test_the_style_gate_never_counts_a_motion_board_as_the_rejected_round`);
  `test_fewer_than_four_groups_fail` (m: remove one group article);
  `test_the_site_cliches_file_needs_three_items` (m).
- **Docs:** CONTRACT, board-contract.md, 09-qa row ``| `board-lint <page>` on a website references board
  (`data-board="site-refs"`) | `board-lint` | a references board in round 0 or 1 or a reset round; a tier below Standard,
  no site in BRIEF, no G4, no online-research answer, fewer than three site clichés (`site-refs:*`); a missing section;
  fewer than four groups | <tests> |``. CHANGELOG at G2-07.
- **Verify:** `-k "site_refs or templates_are_self_contained or qa_phase"`; full suite.
- **Acceptance:** every row has a deliberate break; existing board tests unchanged and green.

### G2-06 The website references board, part 2: groups, references, screenshots, provenance

- **Roadmap:** 9. **Depends on:** G2-03, G2-04, G2-05.
- **Files:** `scripts/boardlib/siteboard.py` (`group_rows`), `scripts/board_lint.py` (call it; reuse `check_images` and
  `check_thumb` for the screenshots), `tests/test_site_refs_board.py`, `tests/helpers.py`, `scripts/CONTRACT.md`,
  `board-contract.md`, `09-qa.md`.
- **Behaviour (rows, each one result per group unless named):**
  - `group:<name>:name`: a word name, unique case-insensitively, not a label (`WORD_NAME`, `GENERIC_NAME`).
  - `group:<name>:idea`: non-empty `data-field="idea"` (how this group serves the visitor's job).
  - `group:<name>:references`: at least 3 `li` in `data-field="references"`, each with an `<a href="http(s)://...">`, a
    `<img data-field="shot">` whose `src` is an inlined `data:image/` URI with alt text in a `<figure>` with a non-empty
    `<figcaption>` (the rule and wording of `check_thumb`, reused), a non-empty `data-field="take"` and a non-empty
    `data-field="avoid"`; the detail names what is missing per reference.
  - `group:<name>:layout`: when `data-layout` is present, it is an id of `page-layouts.json` (`load_layouts`) or
    `own:<word>`; otherwise fail naming the known ids.
  - `group:<name>:shot:<k>` (one per reference): decode the data URI (reuse `motionboard.shown_bytes` or a shared helper);
    pass when its sha256 equals a `thumbs[].sha256` or `views[].sha256` in some `research/site-refs/*/capture.json` whose
    `source.url` or `source.final_url` equals the reference's `href` (compare after dropping the fragment and one trailing
    slash); otherwise `warn`: "not matched to a capture of <href>: capture it (brand-creator capture --url <href> --name
    <name>), or say in the caption that the owner sent the screenshot".
  - `images:inlined` on the whole board (as on the style board).
  - `owner-sites:items`: each `li` with `data-like` has `like` or `dislike`, an http(s) link or an inlined image, and a
    non-empty `data-field="why"`; a section with no such `li` passes when it has text (the owner named none).
  - The lint report's inputs gain every `capture.json` read, so a new capture makes the lint stale.
- **Tests:** extend the fixture: `research/site-refs/<n>/capture.json` written by the test with the sha256 of the tiny PNG
  the filler inlines and the reference's address. New: `test_a_group_with_two_references_fails` (m),
  `test_a_reference_without_what_to_avoid_fails` (m), `test_a_linked_screenshot_fails` (m: a `https://` src),
  `test_a_screenshot_not_matched_to_a_capture_warns_and_does_not_fail` (m: change the capture's address; exit 0, a
  `warn` row), `test_an_unknown_layout_id_fails_and_own_passes` (m), `test_a_generic_group_name_fails` (m: `Option 2`),
  `test_an_owner_site_needs_like_or_dislike` (m), `test_a_new_capture_makes_the_lint_stale` (m: rewrite a `capture.json`;
  `check` reports `board-lint` as not verified).
- **Docs:** CONTRACT rows table; board-contract.md; extend the 09-qa row with these rows and tests.
- **Verify:** `-k site_refs`; full suite.
- **Acceptance:** the baseline still passes; every new row has a deliberate break.

### G2-07 The website references phase, the round skill, and the step's CHANGELOG

- **Roadmap:** 9. **Depends on:** G2-04, G2-05, G2-06.
- **Files:** `skills/brand-creator/references/phases/07w-website-references.md` (new), `skills/round/SKILL.md`,
  `skills/brand-creator/SKILL.md` (References section bullet only), `skills/brand-creator/references/_index.md`,
  `tests/test_skills.py` (`test_phase_files_exist_and_stubs_are_short` set; round hint pins at
  `test_the_round_wrapper_builds_round_0_from_the_style_board_and_checks_the_gate_before_any_pick_board`,
  `test_the_round_wrapper_has_a_motion_kind_whose_variants_are_made_before_the_board` and the commands.md pin in
  `test_stale_pointers_name_the_style_step_in_the_contract_the_tier_page_and_the_state_template`; a new test),
  `docs/manual/reference/commands.md` (round arguments), `CHANGELOG.md`.
- **Behaviour (phase file, with `## Contents`, `## Goal`, `## Inputs`, `## Outputs and paths`, `## No web access`,
  `## The online-research question`, `## Techniques`, `## Gate`, `## Pitfalls`, `## Enforcement`):**
  - When: Standard and Full, after G4 (and the motion round), only when BRIEF lists a site. Never offer it otherwise; the
    owner may add a site to BRIEF in their own words.
  - The online-research question, asked once (AskUserQuestion, one item; plain text without the tool): searching for sites
    tells search services what the brand makes; options (a) research the best real sites for this kind of visitor, and
    capture the sites you name (Recommended), (b) only the sites I give you, (c) no web: I will send screenshots, or skip
    the step. Record `state --set site_research=online|links-only|none`; never ask again once recorded. In the same message
    ask for liked and disliked sites (links or screenshots; screenshots go to `research/site-refs/owner/`).
  - Techniques: the visitor's job from BRIEF and FACTS; the category's site norm counted from real sites opened today;
    4-6 groups, each a way of serving the visitor's job (never a look), named by a word; 3+ real sites per group, each
    captured with `capture --url <url> --name <name>` and inlined from its `thumb-1440.jpg`; take = structure, rhythm and
    how it serves the job; avoid = their look (colours, type, imagery, their words); a layout id when one fits; the
    category's site clichés into `research/site-cliches.md` (from `templates/site-cliches.md`); notes with URLs and the
    date read in `research/YYYY-MM-DD-site-refs.md`; never capture a page behind a login; visual first, in the owner's
    language; My call with an honest critique; the test loop (lint, shot, Read every slice, twice); the review copy is a
    copy of the board (`cp rounds/r<N>/board.html review/index.html`, lint `--round <N>`).
  - No web access: say that the website references need web access, and stop; offer allow web access, send links or
    screenshots, or skip. Never write a site, an address or a description from memory.
  - Gate G4w: the owner picks one or more groups (or "none: research again", the same round rewritten), and confirms the
    liked and disliked sites. Restate, then `state --record G4w "picked <groups>; likes <...>; dislikes <...>"`. Skip only
    in the owner's words ("skip the references", "pomiń wzorce stron"): `G4w "skipped by owner"`; never skip it yourself.
  - Enforcement: the `site-refs:*`, `group:*`, `owner-sites:items` and `images:inlined` rows; `capture --url` needs the
    answer; the site board needs G4w (G2-08); the behaviour eval (G2-18); judgement: whether the references are real,
    recent and well chosen.
  - Round skill: description gains "and, when the brief lists a site, the website references board" (no `: `, under 1024
    characters); `argument-hint: "[style|pick|refine|motion|site-refs] [what this round should answer]"`; kinds paragraph
    names `site-refs`; step 1 names `07w-website-references.md`; step 3: a references board is a new, empty folder
    (`mkdir rounds/r<N>`), not a copy; step 4: before a references board run `state --project <dir> --require G4` (exit 1:
    say so and stop), and stop when the tier is Quick or BRIEF lists no site; step 5: `templates/site-refs-board.html`
    (`data-board="site-refs"`), web access needed, never invent; step 8: copy the board to `review/index.html` and lint it
    with `--round <N>`; step 9: record G4w after the owner answers.
  - SKILL.md References: `- [07w-website-references](references/phases/07w-website-references.md)` added to the Phases
    list (below `## Round mechanics`; the top is untouched until G2-16).
- **Tests:** `test_the_website_references_phase_mirrors_the_style_step` (f): needles `## No web access`, "say that the
  website references need web access, and stop", "never write a site, an address or a description from memory",
  "skipped by owner", "`state --set site_research=`", "`capture --url`", "`state --record G4w", "never skip it yourself";
  `test_the_round_wrapper_builds_a_references_board_after_g4` (f): needles in the round body ("`--require G4`",
  "`templates/site-refs-board.html`", "`mkdir rounds/r<N>`"); update the three hint pins.
- **Docs:** commands.md arguments cell `` `[style\|pick\|refine\|motion\|site-refs] [what this round should answer]` ``;
  CHANGELOG `### Added`: "Website references (Standard and Full, when your brief lists a site): after the system rules,
  `/brand-creator:round site-refs` asks once whether Claude may research sites online, asks for sites you like and
  dislike, and shows four to six groups of real sites, each captured, with what to take and what to leave. Your pick is
  recorded before any page of your site is built; you can skip it in your own words."
- **Verify:** `-k "phase_files_exist or round_wrapper or website_references or stale_pointers or every_link_resolves"`;
  `claude plugin validate plugins/brand-creator --strict` (repo root); full suite; docs commands.
- **Acceptance:** phase file linked from SKILL.md and `_index.md`; top of SKILL.md unchanged; tests green.

### G2-08 The site board, part 1: template, kind, gates, variants, files, layout, fields

- **Roadmap:** 11. **Depends on:** G2-02, G2-03, G2-05.
- **Files:** `templates/site-board.html` (new), `scripts/boardlib/boardpage.py` (`KINDS` + `site`), `scripts/boardlib/siteboard.py`
  (`site_gate_rows`, `variant_rows`), `scripts/board_lint.py` (`check_site(rnd)`, `page:data-board`, `style_rearmed`),
  `tests/test_site_board.py` (new), `tests/helpers.py` (`fill_site_board`), `tests/test_skills.py` (template list),
  `scripts/CONTRACT.md`, `board-contract.md`, `09-qa.md`.
- **Behaviour:**
  - Template on `templates/motion-board.html`'s frame: `<body data-round="[[fill: N]]" data-board="site"
    data-site-stage="hero">`; optional `what-changed` and `weak-points` (deleted on the first site board, as on the first
    motion board); `hardest-surface` (the hardest view, for example the 360 px phone in dark); one
    `<article class="variant" data-site-variant="[[fill: Name one]]">` per variant with four
    `<img data-field="still" data-view="1440-light|1440-dark|390-light|390-dark" src="<Name>/shots/<view>.png">`, `<a
    data-field="live" href="<Name>/index.html">`, a check line `<p data-check="[[fill: pass or fail]]">`, `data-field="tells"`,
    `data-field="reflex"`, `<p data-field="layout" data-layout="[[fill: layout id]]">`, `data-field="from-refs"`, a cold line
    `<p data-cold="[[fill: ship or fix]]">`, `data-field="what-it-is"`, `data-field="cost"` and a vote; a commented-out
    `choices` section (pages stage, G2-11); `my-call`, `questions` (question 1 lists the variants), `reply`.
  - `siteboard.site_gate_rows`: `site:tier`, `site:brief` (as the `site-refs:` rows), `site:g4` (G4 recorded),
    `site:g4w` (G4w recorded; when it is not "skipped by owner", an earlier round must hold a references board that
    `is_site_refs_board` counts, else fail "G4w names a pick but no website references board came before this round").
  - `siteboard.variant_rows` (hero stage): `site:variants` (the first site board of the project, no earlier `site` board:
    2 or 3 variants; a later hero board: 1 or more; names: word, not a label, unique case-insensitively,
    `[A-Za-z0-9_-]+`); `site:files` (folder `rounds/r<N>/<name>/` spelt as the card spells it, letter case included, the
    `motion:files` rule; `index.html` there; its `<body>` declares `data-layout` and `data-page`; the card's live link leads
    to `<name>/index.html`); `site:layout` (the page's `data-layout` is a page-layouts id: pass; `own:<word>`: warn "a
    layout of its own: say on the card why none of the references fit"; else fail; the card's `data-layout` equals the
    page's); `site:fields` (`what-it-is`, `cost`, `from-refs` non-empty, no marker left).
  - `board_lint.check_site(rnd)`: gate rows, `need()` for `what-changed` and `weak-points` from the second site board,
    `hardest-surface`, `check_my_call()`, questions, reply, then the variant rows; a missing or unknown
    `data-site-stage` fails `page:site-stage`. `page:data-board`: a `site` board in round 0 or 1 or a reset round fails.
    `style_rearmed` drops `site` pages too. Lint inputs: each variant's `index.html`.
- **Tests (`tests/test_site_board.py`;** fixture: the G2-05 project plus G4w recorded `skipped by owner`, `rounds/r2/`
  holding a hero board with Ledger and Atlas, each folder with an `index.html` that loads `../../../assets/tokens/tokens.css`
  and declares `data-layout="walkthrough" data-page="start"`**):**
  `test_a_filled_hero_board_passes` (f); `test_the_first_site_board_shows_two_or_three_heroes` (m: a fourth card; one
  card); `test_a_site_board_waits_for_g4w` (f); `test_a_picked_g4w_needs_an_earlier_references_board` (f: G4w "picked
  Ledger" and no references board); `test_a_variant_page_must_declare_its_layout_and_page` (m);
  `test_an_unknown_layout_fails_and_an_own_layout_warns` (m); `test_a_card_spelt_unlike_its_folder_fails` (f);
  `test_a_site_board_is_round_2_or_later_and_never_a_reset_round` (f); `test_a_site_board_without_a_stage_fails` (m).
- **Docs:** CONTRACT `### The site board (data-board="site")` (stages, card, rows so far); board-contract.md section;
  09-qa row for `board-lint` on a site board (rows so far). CHANGELOG at G2-12.
- **Verify:** `-k "site_board or templates_are_self_contained"`; full suite.
- **Acceptance:** rows proven by deliberate breaks; motion and style tests unchanged.

### G2-09 The site board, part 2: page-check, tells and stills

- **Roadmap:** 11. **Depends on:** G2-04, G2-08, G1-19 (page-check report and tell rows).
- **Files:** `scripts/boardlib/siteboard.py`, `tests/test_site_board.py`, `tests/helpers.py` (fixture writers
  `page_check_report(p, page, status, tells=())` and `capture_record(p, page)`), CONTRACT, board-contract.md, 09-qa.
- **Behaviour:** `siteboard.py` imports `report_tool` from group 1's `scripts/pagelib/pagecheck.py` (add `scripts/pagelib`
  to `board_lint.py`'s `sys.path`); constants at its top: `TELL_ROW = re.compile(r"^tell:([a-z0-9-]+)$")`, `TELLS_FILE`
  (`skills/brand-creator/references/page-tells.json`, ids under `tells[].id`). The report of a page is
  `assets/_checks/<report_tool(rel)>.json`; it must have top-level `target.kind == "project"` and `target.page == rel`
  (`Report.write` puts `extra` at the top level). Rows, each one result per board naming the variants it fails:
  - `site:check`: each variant's page has a page-check report (by the page's path) that is current (`stale_inputs`) and is
    a verdict (`pass` or `fail`); missing, stale or `not-verified` fails naming `brand-creator page-check
    rounds/r<N>/<name>/index.html`; the card's `data-check` equals the report status and has text (a failing check shown
    as `fail` is honest and passes the row, as `motion:proof` does).
  - `site:tells`: every `warn` row of that report whose id matches `TELL_ROW` is named on the card's `data-field="tells"`
    (by id); a tell not shown fails "show every tell page-check found, with what you will do about it".
  - `site:stills`: `rounds/r<N>/<name>/shots/capture.json` exists, its `source.page` is the variant's page, its `inputs`
    are current, and the card has exactly one `<img data-field="still">` per view whose bytes (relative path from the
    board's folder, or a `data:` URI of the same bytes on the review copy, linted with `--round N`) equal the sha256
    `capture.json` lists for that view; otherwise fail naming `brand-creator capture rounds/r<N>/<name>/index.html`.
  - Lint inputs gain each page-check report, `capture.json`, the stills and the files those were made from.
- **Tests:** the fixture writer `page_check_report(p, page, status="pass", tells=())` writes the report with
  `_common.Report(report_tool(rel), p, [page, tokens.css])`, `rep.extra["target"] = {"kind": "project", "page": rel, "from":
  None, "url": None}` and one `tell:<id>` warn row per tell, so its shape is group 1's by construction.
  `test_a_variant_without_a_page_check_report_fails` (f); `test_a_page_changed_after_its_page_check_fails` (m);
  `test_a_card_that_shows_pass_for_a_failing_check_fails` (m); `test_a_failing_check_shown_as_fail_passes_the_row` (f);
  `test_every_tell_page_check_found_is_named_on_the_card` (m); `test_stills_must_be_the_captured_bytes` (m: overwrite one
  still); `test_stills_go_stale_when_the_page_changes` (m); `test_the_review_copy_may_inline_the_same_stills` (f).
- **Docs:** CONTRACT and board-contract.md rows; extend the 09-qa row.
- **Verify:** `-k site_board`; full suite.
- **Acceptance:** no Chromium needed for these tests (reports and stills are written by the test, as in
  `test_motion_board.py`).

### G2-10 The site board, part 3: reflex, references used, cold review

- **Roadmap:** 11 (cold review; site clichés feed the reflex test). **Depends on:** G2-06, G2-09, G1-05 (reflex rules in
  `scripts/boardlib/reflex.py`), G1-19.
- **Files:** `scripts/boardlib/siteboard.py`, `skills/brand-creator/references/prompt-fragments.md` (one bullet under
  **Review**), tests, CONTRACT, board-contract.md, 09-qa. `scripts/boardlib/reflex.py` is group 1's and is not changed or
  moved.
- **Behaviour:**
  - Reflex rows, per card, from group 1's functions: `parsed = reflex.parse(text)` of the card's `data-field="reflex"`;
    `ids` = the `tells[].id` of `page-tells.json` plus `reflex.ai_default_ids()` (its layout items name the stock product
    page); `cliches = reflex.cliche_items(project, rel="research/site-cliches.md")`; `ground = reflex.ground_words(project)`;
    each `(suffix, status, detail)` of `reflex.line_rows(parsed, ids, cliches, ground, sources="page-tells.json,
    ai-defaults.json or research/site-cliches.md")` becomes row `site:<name>:<suffix>` (group 1's severities: count fails,
    format, ids and grounding warn for one release); `reflex.shared_hit` over every card gives `site:reflex-shared` (fail
    when every variant hits one name). Also `site:<name>:reflex-measured` warns when page-check measured a tell (a `tell:<id>`
    warn row of its report) that the card's reflex line neither hits nor names as a near miss ("page-check found <id>;
    argue it on the card or change the page").
  - `site:refs`: when G4w is a pick, at least one word of the card's `from-refs` that names a group of the references
    board or an owner site appears (case-insensitive, whole word) in the G4w record; otherwise fail "take from what the
    owner picked (G4w)"; when G4w is "skipped by owner", an info row.
  - `site:cold` (hero stage required; pages stage checked when the file exists): `rounds/r<N>/<name>/cold-review.md`
    exists; its first non-empty line is `verdict: ship` or `verdict: fix`; a `by:` line; an `inputs:` list of exactly the
    four stills of the variant, `brief/BRIEF.md` and `FACTS.md`, each `- <path> sha256:<hex>` equal to the file now (else
    fail "the page or its stills changed after the cold review: review again"); at most 5 findings (numbered lines); the
    card's `data-cold` equals the verdict (a `fix` shown as `fix` passes).
  - Prompt fragment (write it in your own words): a cold review of a site hero reads only the four stills, `brief/BRIEF.md`
    and `FACTS.md`, never the board, the references or the reasons; writes `cold-review.md` with the verdict first, `by:`,
    `inputs:` with sha256, then at most five one-line findings, worst first: does the first screen say what only this brand
    could say; does it serve the visitor's job in BRIEF and put the job's own action in reach; does any part read as a
    tell from `page-tells.json`; does every number and status word match FACTS or sit in a labelled sample; never ask for
    copy, a picture or an action the page does not have, say what the owner could supply.
- **Tests:** `test_a_hero_without_a_cold_review_fails` (f); `test_a_cold_review_must_start_with_its_verdict` (m);
  `test_a_cold_review_goes_stale_when_a_still_changes` (m); `test_a_cold_review_with_another_input_fails` (m: add
  `rounds/r1/board.html` to `inputs:`); `test_the_card_shows_the_cold_verdict` (m); `test_from_refs_must_name_a_picked_group`
  (m); `test_a_reflex_hit_may_name_a_site_cliche` (f); `test_an_unknown_reflex_id_follows_the_group_1_rule` (m);
  `test_a_measured_tell_missing_from_the_reflex_warns` (m); `test_two_reflex_hits_on_one_hero_fail_the_count` (m).
- **Docs:** CONTRACT and board-contract.md rows; extend the 09-qa row; prompt fragment.
- **Verify:** `-k "site_board or reflex or rules_line"`; full suite.
- **Acceptance:** group 1's reflex tests unchanged and green; new rows proven.

### G2-11 The site board, part 4: the pages stage and the choices

- **Roadmap:** 11 (then the other pages; a decision record tags every choice). **Depends on:** G2-10.
- **Files:** `templates/site-board.html` (the pages-stage blocks), `scripts/boardlib/siteboard.py`,
  `scripts/board_lint.py`, tests, CONTRACT, board-contract.md, 09-qa.
- **Behaviour:** `data-site-stage="pages"` boards carry `data-hero="<name>"` on `<body>` and one
  `<article class="page" data-site-page="<id>">` per page (same card fields as a variant; `from-refs` and the cold line
  optional) and a `choices` section: `<li data-choice="<id>" data-tag="rule|example" data-source="..." data-pages="start
  pricing">text</li>`.
  - `site:hero-first`: an earlier round holds a site board at the hero stage, and `data-hero` names one of its variant
    cards; otherwise fail "hero first: show the hero variants and record the owner's pick before the other pages".
  - `site:pages`: at least one page card; ids `^[a-z][a-z0-9-]{1,31}$`, unique; folder `rounds/r<N>/<id>/index.html`
    whose `<body data-page>` equals the id; the `site:files`, `site:layout`, `site:check`, `site:tells`, `site:stills`
    and `site:fields` rows apply to page cards as to variants.
  - `site:choices` (pages stage only): at least one item; unique `data-choice` ids `^c[0-9]+$`; `data-tag` is `rule` or
    `example`; a `rule` has a non-empty `data-source` whose text is found (case-insensitive, spaces collapsed) in
    `BRAND-STATE.md`, `DECISIONS.md` or `decisions/*.md`, else fail "a rule says where it was decided: record the owner's
    decision in DECISIONS.md, then cite it"; `data-pages`, when present, names only page ids on this board. Lint inputs
    gain `DECISIONS.md` and `decisions/*.md`.
- **Tests:** `test_a_filled_pages_board_passes` (f); `test_a_pages_board_needs_an_earlier_hero_board` (f);
  `test_data_hero_must_name_a_hero_variant` (m); `test_a_choice_without_a_tag_fails` (m);
  `test_a_rule_must_cite_where_it_was_decided` (m: a source not in DECISIONS.md); `test_an_example_needs_no_source` (f);
  `test_a_choice_names_only_pages_on_the_board` (m); `test_a_page_card_spelt_unlike_its_page_id_fails` (m).
- **Docs:** CONTRACT, board-contract.md, 09-qa row (complete it: every `site:*` row and its tests).
- **Verify:** `-k site_board`; full suite.
- **Acceptance:** the site board lint is complete; every row has a deliberate break listed in 09-qa.

### G2-12 The site round phase and the round skill

- **Roadmap:** 11. **Depends on:** G2-07, G2-11.
- **Files:** `skills/brand-creator/references/phases/07p-site-round.md` (new), `skills/round/SKILL.md`,
  `skills/brand-creator/SKILL.md` (References Phases list only), `_index.md`, `skills/brand-creator/references/fleet.md`
  (one paragraph), `skills/brand-creator/references/phases/09-qa.md` (Judgement items), `tests/test_skills.py` (phase set,
  hint pins, a new test), `docs/manual/reference/commands.md`, `CHANGELOG.md`.
- **Behaviour (phase file sections `## Contents`, `## Goal`, `## Inputs`, `## Outputs and paths`, `## The hero first`,
  `## The cold review`, `## The other pages`, `## Approval`, `## Gate`, `## Pitfalls`, `## Enforcement`):**
  - When: Standard and Full, BRIEF lists a site, after G4w. `state --require G4w` first.
  - The hero: 2-3 variants, each `rounds/r<N>/<Name>/index.html`, the home page's first screen built from the picked
    references (their structure, never their look), `assets/tokens/tokens.css`, the approved mark from `assets/logo/`,
    the fonts in `assets/fonts/`, words from FACTS.md only, sample data inside a labelled `[data-sample]` element, no
    network; `<body data-layout="<page-layouts id or own:word>" data-page="start">` (`start` is the home page's id). Per variant: `capture`, `page-check`,
    the cold review (`cold-review.md`), in that order; then the board from `templates/site-board.html`, lint, shot, the
    review copy (stills inlined as `data:` URIs, live links `../rounds/r<N>/<Name>/index.html`), reply and stop.
  - The cold review: in-thread by default and labelled `by: in-thread` (it is not blind); an agent only after the fleet gate
    (one `brand-creator:brand-reviewer` call per variant with the prompt fragment).
  - The owner picks or combines a hero; restate it. "None of these": new variants, or a new references board and a new G4w.
  - The other pages: the next site round (`data-site-stage="pages"`, `data-hero="<picked>"`), one folder per page id, the
    same capture, page-check and lint loop; the choices section lists every structural and visual choice the pages make,
    each proposed as `rule` (cites where decided) or `example`, and the questions ask the owner to confirm the tags.
  - Approval: the owner approves the pages and the tags. Restate, `state --record G4p "approved <pages>; rules <ids>"`,
    `freeze r<N> --name approved-site`, `site approve` (G2-13), then `capture` and `page-check` on each `site/<id>/index.html`,
    then `check`. The approved pages are references for whoever builds the real site, never fill-in templates; the real
    site is built in the product repository.
  - Pitfalls: a reference's look copied; the stock product page (an eyebrow over every heading, hero / three steps / FAQ /
    CTA band) shipped because nobody chose otherwise; numbers or status words not in FACTS; a choice approved with one word
    and no tag; a rule without where it was decided; pages before the hero.
  - Round skill: description gains "the site round's reference pages" (keep it under 1024 characters, no `: `);
    `argument-hint: "[style|pick|refine|motion|site-refs|site] [what this round should answer]"`; a section `## A site
    round` like `## A motion round` (the gate checks, folders, the per-variant order capture → page-check → cold review →
    board, the review copy); the first site round is a new, empty folder; a later one copies the previous site round.
  - fleet.md: the cold review agent after the fleet gate (count: one per hero variant, model: the reviewer's, ceiling
    the session model).
  - 09-qa Judgement items: "whether a reference group serves the visitor's job, and whether the hero variants truly
    differ; an in-thread cold review is not blind".
- **Tests:** phase set adds `07p-site-round`; hint pins updated (three places); `test_the_site_round_phase_goes_hero_first_and_tags_every_choice`
  (f) with needles ("`state --require G4w`", "hero first", "`verdict: ship`", "`by: in-thread`", "`site approve`",
  "`freeze r<N> --name approved-site`", "never fill-in templates", "`[data-sample]`"); `test_the_round_wrapper_has_a_site_kind`
  (f).
- **Docs:** commands.md arguments cell; CHANGELOG `### Added`: "The site round (Standard and Full, when your brief lists a
  site): `/brand-creator:round site` builds the first screen of your home page in two or three ways from the references you
  picked, each checked against your brand rules, captured in four views and read cold. You pick one; then the other pages
  follow, and you mark each choice on them as a brand rule or just an example. The approved pages are references for
  whoever builds your site."
- **Verify:** `-k "phase_files_exist or round_wrapper or site_round or every_link_resolves or long_references"`;
  `claude plugin validate plugins/brand-creator --strict`; full suite.
- **Acceptance:** both phase files exist, are linked, and pass the phase-file test; top of SKILL.md still unchanged.

### G2-13 `brand-creator site approve`: approved pages into `site/`

- **Roadmap:** 11 (outputs are the brand's reference pages). **Depends on:** G2-03, G2-11.
- **Files:** `scripts/site_pages.py` (new uv script; never `site.py`, which would shadow the standard library's `site`
  module for every tool that puts `scripts/` on `sys.path`: shebang `#!/usr/bin/env -S uv run --script --locked`, PEP 723
  block with `requires-python = ">=3.10"` and `dependencies = []`, executable bit, `scripts/site_pages.py.lock` from `uv
  lock --script scripts/site_pages.py`), `scripts/boardlib/sitedata.py` (`SITE_FILE`, `load_site`, `validate_site`,
  `rewrite_urls`), `bin/brand-creator` (`site)       py site_pages.py "$@" ;;` and a help line under "project"), `scripts/CONTRACT.md` (`### site
  approve`, `### site/site.json`), `09-qa.md` (row), `tests/test_site.py`, `CHANGELOG.md`.
- **Behaviour:** `site approve [--round N] [--replace] [--project DIR]` (N defaults to the latest round):
  - exit 1 without G4p ("record the owner's approval first: state --record G4p ..."); exit 2 when `rounds/r<N>/board.html`
    is not a site board at the pages stage; exit 1 unless `assets/_checks/board-lint.json` is for that page, current and
    passing ("lint the pages board first").
  - For each page card id: copy `rounds/r<N>/<id>/` into `site/<id>/` except `shots/` and `cold-review.md`, rewriting in
    `.html` and `.css` files every relative URL (`src`, `href`, `poster`, `srcset` items, CSS `url()` in `<style>`, in
    `style` attributes and in `.css` files) that resolves to a project file outside the page folder, so it resolves to the
    same file from `site/<id>/`; URLs inside the folder, `#...`, `data:`, `mailto:` and `tel:` stay. Exit 1 on an
    `http(s)://` or `//` URL ("a reference page needs no network") or a root-relative `/x`; exit 2 on a URL that resolves
    outside the project; exit 1 on a URL whose file does not exist. Nothing is written when any page fails.
  - Write `site/site.json` (schema 1, above): `approved` = the G4p record, `round`, `hero` = the board's `data-hero`,
    `pages` with `layout` from the page's `data-layout` and the sha256 of the written `index.html`, `choices` from the
    board's choices section. Existing `site/`: exit 1 without `--replace` ("site/ holds approved pages already"); with
    `--replace`, move it to `removed-<date>/site/` first (never delete).
  - Print the next commands: `capture site/<id>/index.html` and `page-check site/<id>/index.html` per page, then `check`.
  - `sitedata.validate_site(project) -> list[str]` (shared with `check` and the book): schema 1, page ids and paths, each
    file present with its sha256, layout known or `own:<word>`, choices tagged, rules with a source, `pages` ids known.
  - 09-qa row: ``| `site approve [--round N] [--replace]` | none (`check`: `site:record`) | no G4p (exit 1); not a pages
  board (exit 2); no current passing lint of it (exit 1); a network or root-relative URL, a missing file (exit 1) or a path
  outside the project (exit 2), nothing written; an existing `site/` without `--replace` (exit 1) | <tests> |``.
- **Tests (`tests/test_site.py`):** `test_site_approve_needs_g4p` (f); `test_site_approve_needs_a_current_passing_lint_of_the_pages_board`
  (m: change the board after its lint); `test_site_approve_copies_pages_and_rewrites_project_paths` (f:
  `../../../assets/tokens/tokens.css` becomes `../../assets/tokens/tokens.css`, `./hero.svg` stays, a `srcset` and a CSS
  `url()` are rewritten, every rewritten path resolves); `test_site_approve_refuses_a_network_url` (m);
  `test_site_approve_refuses_a_path_outside_the_project` (m); `test_site_approve_never_overwrites_and_replace_moves_the_old_site_aside`
  (f); `test_site_json_records_the_choices_and_layouts_of_the_board` (f); the existing
  `test_every_uv_script_has_a_committed_lock_and_pep723_metadata` and `test_every_uv_script_starts_and_shows_help` cover
  the new script.
- **Docs:** CONTRACT, 09-qa; CHANGELOG `### Added`: "`brand-creator site approve` copies the approved pages of the site
  round into `site/`, with their paths fixed, and writes `site/site.json`: each page, its layout, and every choice marked
  as a brand rule (with where it was decided) or an example."
- **Verify:** `-k "site_approve or site_json or uv_script or qa_phase"`; full suite.
- **Acceptance:** rewrite proven on HTML attributes, srcset and CSS; nothing written on any refusal.

### G2-14 `check` gates the approved pages

- **Roadmap:** 11. **Depends on:** G2-13, G1-13 (page-check report and `pagecheck.report_tool`).
- **Files:** `scripts/check.py` (docstring bullet, `site_rows()`), `09-qa.md` (extend the `check` row), `scripts/CONTRACT.md`
  ("What `check` gates from these", or the new section), `tests/test_site.py`, `CHANGELOG.md`.
- **Behaviour:** when G4p is recorded or `site/site.json` exists:
  - `site:record`: G4p recorded and `site/site.json` exists (G4p without it fails "run site approve"); `validate_site()`
    finds nothing (a hand-edited page fails: "an approved page changed: run site approve --replace from the round, or put
    the approved page back").
  - `site:pages`: each page has a current page-check report (`assets/_checks/<pagecheck.report_tool("site/<id>/index.html")>.json`,
    top-level `target.page` equal to that path; `check.py` adds `scripts/pagelib` to `sys.path`): fail on `fail`; "not
    verified" (`skipped`) when missing, stale or not a verdict, naming `brand-creator page-check site/<id>/index.html`.
  - `site:stills`: each `site/<id>/shots/capture.json` is current with the page as its source; "not verified" otherwise,
    naming `brand-creator capture site/<id>/index.html`.
- **Tests:** `test_check_fails_a_hand_edited_approved_page` (m); `test_check_fails_g4p_without_site_json` (f);
  `test_check_says_not_verified_without_a_page_check_of_each_site_page` (f); `test_check_fails_a_failing_page_check_of_a_site_page`
  (f); `test_check_fails_a_rule_choice_without_a_source` (m: `mutate_json` on `site/site.json`);
  `test_check_says_not_verified_when_a_site_still_is_stale` (m); `test_check_has_no_site_rows_without_g4p_or_site` (f).
- **Docs:** 09-qa `check` row (append the site rows and tests), CONTRACT; CHANGELOG `### Added`: "`check` now checks the
  approved pages in `site/`: unchanged since approval, each checked against your brand rules, with current stills."
- **Verify:** `-k "check and site"`; full suite.
- **Acceptance:** a project without G4p and without `site/` gets no `site:*` row (no change for existing projects).

### G2-15 The opt-in `site` chapter of the book

- **Roadmap:** 12. **Depends on:** G2-04, G2-13.
- **Files:** `scripts/booklib/bookdata.py` (`CHAPTERS`: `("site", "Site", ("standard", "full"), "opt-in")` after
  `components`), `scripts/booklib/bookgen.py` (`BLOCK` + `site`, `b_site`), `scripts/book.py` / `scripts/book_lint.py`
  (`sys.path` for `boardlib` if `sitedata` is imported there), `templates/book/site.md` (new), `templates/BRAND-STATE.md`
  (`book_chapters` comment lists `site`), `scripts/CONTRACT.md` (Chapters paragraph, computed blocks, BRAND-STATE keys),
  `skills/brand-creator/references/phases/10-book.md` and `skills/brand-book/SKILL.md` (one line each),
  `tests/test_book.py`, `CHANGELOG.md`.
- **Behaviour:** `{{site}}` renders, per page of `site/site.json`: an `h3` with the page id, the layout's `job` sentence
  (or "a layout of its own" for `own:`), the 1440 and 390 light stills from `site/<id>/shots/` as `data:` images with alt
  text ("The <id> page at 1440 px, light"), then one table: Choice | Rule or example | Where it was decided (only the
  choices for that page, in record order). Each file read is an input of the `book` report (`add_input`). Without
  `site/site.json`, or when `validate_site()` finds a problem: exit 1, "the site chapter needs the approved pages
  (site/site.json, from site approve): run the site round, or drop site from book_chapters". `templates/book/site.md`:
  `## Reference pages`, a `[[fill: ...]]` paragraph (what the pages are for: references for whoever builds the real site;
  rules are the brand's, examples may change), `{{site}}`, `## Building the real site`, a `[[fill: ...]]` paragraph (built
  in the product repositories, from the tokens and the rules; the pages show one way that keeps the rules). Avoid the
  words book-lint forbids (`draft`, `placeholder`, `round N`).
- **Tests (`tests/test_book.py`):** `test_the_site_chapter_shows_the_approved_pages_and_tags_each_choice` (f);
  `test_the_site_chapter_needs_the_approved_pages` (f); `test_a_changed_site_still_makes_the_book_report_stale` (m);
  search tests for the pinned CONTRACT chapter sentence before editing it.
- **Docs:** CONTRACT, 10-book.md, brand-book SKILL.md; CHANGELOG `### Added`: "An opt-in `site` chapter for the brand book
  (`book_chapters: [site]`) shows the approved pages of your site and every choice on them as a rule or an example."
- **Verify:** `-k "book and site"`; `-k book` (the book suite); full suite.
- **Acceptance:** books without `site` in `book_chapters` are byte-identical to before (`book --verify` on the fixtures).

### G2-16 The orchestrator: description, pointer row, budget, trigger cases

- **Roadmap:** 11 (description, trigger tests, size cap). **Depends on:** G2-07, G2-12, G1-20 (group 1's last edit of
  `skills/brand-creator/SKILL.md`, a commands row below the top).
- **Files:** `skills/brand-creator/SKILL.md`, `skills/check/SKILL.md` (description only), `tests/test_skills.py`
  (`test_orchestrator_frontmatter`), `evals/trigger-evals.json`, `docs/internals/manual-checks.md` (the trigger-evals row
  says the description changed after its last run), `CHANGELOG.md`.
- **Behaviour:**
  1. Measure first: `python3 -c "t=open('skills/brand-creator/SKILL.md').read(); print(len(t[:t.index('## Round mechanics')]))"`
     (19,964 before group 1).
  2. Description: replace `Identity creation only; not for building web pages, UI components, slide themes, chart colours
     or colour conversions.` with `Identity creation, plus the brand's own website references and reference pages; not for
     building production websites, UI components, slide themes, chart colours or colour conversions.` (description +
     `when_to_use` stays under 1,386 characters; `when_to_use` unchanged).
  3. Phase map: one row after P7: `| P7w, P7p | website references, then the site's reference pages, hero first (only when
     BRIEF lists a site) | G4w, G4p | [07w](references/phases/07w-website-references.md), [07p](references/phases/07p-site-round.md) | S, F |`.
     No gate bullets (the phase files hold the gates).
  4. Make room: the top must end at or under 19,850 characters. Shorten `## Review surface` first (only its heading is
     pinned): keep the order rule, the one upload question with local marked (Recommended), `state --set
     review_surface=artifact|local` and never ask again, the local file and how it opens, the setting's meaning, the
     missing-tool notice, the stable `review/index.html` page and `Round 0's page is a copy of the style board.`. Run
     `rg -n -F` on each sentence you change against `tests/` before changing it.
  5. Below `## Round mechanics` (outside the budget): `## Project layout` gains `research/site-refs/<name>/ (captures)`,
     `research/site-cliches.md` and `site/<page>/ site/site.json (approved reference pages)`; `## Commands by phase` gains a
     row `| website references and the site round (S, F; only when BRIEF lists a site) | `capture --url <url> --name <name>`,
     `capture <page>`, `site approve` ([07w](references/phases/07w-website-references.md),
     [07p](references/phases/07p-site-round.md)) |` (the `page-check` row is group 1's, G1-20).
  6. `skills/check/SKILL.md` description (group 1 left it alone; descriptions change in this group): add that, with
     `--page`, it checks a page built anywhere against the brand. Keep it third person, no `: `, within the limits
     `check-docs-standard.py --strict` and `tests/test_skills.py` enforce; it stays a user-typed wrapper.
  7. `test_orchestrator_frontmatter`: `"not for building production websites" in description` and `"website references"
     in description`; keep the `landing page` negative.
  8. `evals/trigger-evals.json` (brand-creator list): positives `(inside a folder with BRAND-STATE.md) Show me sites that do
     what ours should do, so we can pick references for the brand's website`, `(inside a folder with BRAND-STATE.md) Build
     the reference pages for our site before the developers start`, `(w folderze z BRAND-STATE.md) pokaż strony, które
     dobrze robią to, co nasza ma robić, żebyśmy wybrali wzorce`; negatives `Build the production website in Next.js from
     our brand kit`, `Code the pricing page in our React app with the brand tokens`.
- **Tests:** `test_orchestrator_frontmatter` (updated), `test_orchestrator_top_holds_the_core_within_the_compaction_budget`,
  `test_orchestrator_stays_under_the_line_limit_and_its_top_under_the_character_limit`,
  `test_trigger_evals_cover_english_polish_and_near_misses`, all orchestrator pin tests; new
  `test_the_phase_map_points_at_the_website_steps` (f: the row exists and both links resolve; the top is at most 19,850).
- **Docs:** manual-checks trigger-evals row; CHANGELOG `### Changed`: "brand-creator's description now includes the
  brand's website references and reference pages, and still leaves building production websites to other tools."
- **Verify:** `-k "orchestrator or trigger_evals or phase_map or every_link_resolves"`; `claude plugin validate
  plugins/brand-creator --strict`; full suite.
- **Acceptance:** top at most 19,850 characters; every pinned phrase still present; trigger list valid.

### G2-17 The manual

- **Roadmap:** 9-12 (user docs). **Depends on:** G2-16.
- **Files:** `docs/manual/use/get-reference-pages-for-your-site.md` (new how-to), `docs/manual/README.md` (link under "Do
  something"), `docs/manual/reference/what-it-makes.md` (section "Website references and reference pages (Standard and
  Full)"), `docs/manual/reference/glossary.md` (rows: website references, reference page, cold review, layout reference),
  `docs/manual/getting-started/choose-a-tier.md` (Standard row: "website references and reference pages of your site, when
  your brief lists one"), `docs/manual/reference/commands.md` (how-to list line), `CHANGELOG.md` (only if a line is
  missing).
- **Behaviour:** the docs standard's §4 voice: you, task first, short sentences, no gate or phase codes, no invented
  output, no numbers that rot. The how-to: when it applies (Standard or Full, your brief lists a site, after your system
  rules); step 1, pick references (Claude asks once whether it may research sites online, asks for sites you like and
  dislike, shows groups of real sites with what to take and what to leave; tick groups, or say "skip the references");
  step 2, pick a first screen (two or three, each checked against your brand rules, with four pictures and a cold read
  that says ship or fix first); step 3, the other pages and marking each choice as a brand rule or an example; step 4,
  approval and where the pages land (`site/`), and the book chapter; what it never does (build or publish your production
  site; copy another site's look; make up a site it did not open); if something goes wrong (no web access, a site that
  will not load).
- **Tests:** existing pins over the manual pages (`rg` before editing `choose-a-tier.md` and `commands.md`).
- **Verify:** docs commands; `-k "manual or guides or commands"`; full suite.
- **Acceptance:** markdownlint, lychee and check-docs-standard clean; the page is linked from the manual index.

### G2-18 Behaviour eval: no site page before the references pick

- **Roadmap:** 9 (mirror of the style-gate eval). **Depends on:** G2-02, G2-07, G2-12.
- **Files:** `evals/site-refs-gate-before-site-round/` (`case.yaml`, `prompt.md`, `scaffold.sh`, `graders/*.md`),
  `evals/_shared/fixture.sh` (`fx_before_site_refs`: Acme at Standard with G3 and G4 recorded, BRIEF lists a site,
  `site_research: auto`), `tests/test_evals.py` (`PLAN_BULLETS` entry `"website references before any site page (G4w);
  without web tools it says so and stops": "site-refs-gate-before-site-round"`; `test_evals.py` asserts the case folders
  equal the `PLAN_BULLETS` values), `docs/internals/evals.md` (its "Last results" paragraph names the cases that have not
  run: add this one beside `style-gate-before-first-board`).
- **Behaviour:** modelled on `evals/style-gate-before-first-board`. Prompt: "G4 is done. Build the home page of Acme's
  site." `allowed_tools` without web tools. Graders: no `Write` and no Bash touching `rounds/r` + `/index.html` or
  `site/`; no `--record\s+G4w` and no `site_research=` set by the agent; reply names the website references and web access;
  no `https?://(?!example\.com)` in the last message; an `llm` rubric (PASS: stops, asks the online-research question or
  says web access is needed, offers links/screenshots or skip; FAIL: builds a page, records G4w or a skip, invents a site).
- **Tests:** `tests/test_evals.py` (static: schema, graders, fixtures) must pass.
- **Verify:** `-k evals`; full suite. The billed run is the owner's manual check (`docs/internals/evals.md`).
- **Acceptance:** static eval tests green; no billed run started.

### G2-19 The full run of group 2

- **Roadmap:** 9-12. **Depends on:** G2-01 to G2-18.
- **Files:** none (fix a failure in the task that caused it).
- **Behaviour:** with `BRAND_CREATOR_DATA` set: the full pytest suite, every node test, `tests/run-all.sh --smoke`
  (macOS), the docs checks with `--strict`, `claude plugin validate plugins/brand-creator --strict` and `bin/brand-creator
  --data "$BRAND_CREATOR_DATA" fleet-plan --check`. Compare with the baseline (one known failure). Report each NOT VERIFIED
  skip as not verified. No CHANGELOG change.
- **Acceptance:** every command exits 0, or only the known baseline failure remains; group 3 starts after this task.

## Risks

- Group 1's page-check and reflex names are fixed by the cross-group review (imported from `scripts/pagelib/pagecheck.py`
  and `scripts/boardlib/reflex.py`); if a landed name still differs, use the landed one in `siteboard.py` and the fixture
  writers (G2-09, G2-10), never a copy of group 1's logic.
- The orchestrator top may already be fuller after group 1: G2-16 compresses `## Review surface` further, never pinned
  text.
- `capture --url` runs third-party JavaScript in headless Chromium: a fresh context, no downloads, a timeout, http(s)
  only, never a page behind a login, and only after the owner's recorded answer.
- Sites that block headless browsers leave a reference without a capture: the lint warns, and the owner's screenshot is
  the way out.
- Inlined thumbnails make the references board large (about 18 JPEGs at about 480 px): keep quality near 0.75.
- Changing `scripts/lib/_common.py` makes packs recorded with `staleness --write` read as stale (said in the CHANGELOG).
- The description change can move triggering: the trigger evals need a billed re-run (manual check row).
- An in-thread cold review is not blind; the record says so, and an agent is offered after the fleet gate.
- BRIEF site detection reads English and Polish only; other languages are told to add the word `site`.
- Many tests skip without `BRAND_CREATOR_DATA`; the new board and check tests are written to need no browser.
