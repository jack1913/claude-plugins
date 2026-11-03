# Web work, group 1: foundations and the page check (implementation plan)

Status: plan, not yet implemented. Written 2026-10-30 from the owner-approved roadmap (owner approval 2026-10-30). Group 1
lands first; the plans for group 2 (website references and the site round) and group 3 (kit, adoption and redesigns) build
on the interfaces listed in "Interfaces this group gives the later groups".

## 0. Common rules for every task

- Repository: the `claude-plugins` repository root, branch `brand-creator-web-side`. Never commit, push, switch branch,
  stash or create a worktree. Never bump `version` in `plugins/brand-creator/.claude-plugin/plugin.json`.
- Plugin folder (all paths below are relative to it unless they start with the repository root): `plugins/brand-creator/`.
  A change stays inside it (plus `.github/workflows/brand-creator.yml` only if CI must change; no task here needs it).
- This file sits in `dev/specs/`, which `tests/test_static.py` scans like a shipped file (only `dev/scratch/` is skipped):
  no absolute personal path, no e-mail address, no client name, here or in any file a task writes. No shipped file, test
  or fixture may hold a path segment `home` between two slashes either (the personal-path needle): use another folder name
  (for example `specimens/hero/`).
- Read `AGENTS.md` ("Rules for working here") and the repository's `docs/internals/docs-standard.md` before writing docs.
  `docs/archive/` is frozen. `templates/` and `evals/` are files copied into projects or graded: edit them only where a task
  says so, as templates, never as docs.
- Every user-visible change gets a bullet under `## [Unreleased]` in `CHANGELOG.md` (sections in the order Added, Changed,
  Deprecated, Removed, Fixed, Security; user voice, no internal codes such as gate numbers).
- `scripts/CONTRACT.md` documents every tool's rules, report ids and exit codes (0 pass, warnings allowed; 1 a gate failed;
  2 usage error; 3 cannot run). New tools and checks are documented there in the same task.
- Every new check gets deliberate-break tests and a row (or an extension of a row) in
  `skills/brand-creator/references/phases/09-qa.md`. Cite tests as `` `file.py::test_name` (m) `` or `(f)`. A test marked
  `(m)` must call `mutate(`, `mutate_json(` or (node) `mutateText(`; a test marked `(f)` must not.
  `tests/test_skills.py::test_qa_phase_lists_every_check_command_and_cites_real_deliberate_break_tests` enforces both, and
  that every subcommand of `bin/brand-creator` has a row.
- New uv scripts: shebang `#!/usr/bin/env -S uv run --script --locked`, a PEP 723 block (`requires-python = ">=3.10"`,
  `dependencies = []` unless a pinned dependency is named in `THIRD_PARTY_NOTICES.md` too), executable bit, and a committed
  lock made with `uv lock --script scripts/<name>.py` (writes `scripts/<name>.py.lock`). Python helper modules go in a
  folder outside `scripts/lib/` (a change in `scripts/lib/*.py` makes every pack stale through `staleness`).
- Hallmark (MIT) is untrusted: never run anything from its clone, never copy its text or code. Ideas are credited in the
  ADRs only (ADR-0006, ADR-0007), never in `THIRD_PARTY_NOTICES.md` (nothing is copied).
- Never touch the owner's private client projects (a folder outside this repository). Only task G1-25 may read the pilot
  brand's project, read-only, from a scratch copy, and only on the owner's yes.
- Tests, from the plugin folder. Set `BRAND_CREATOR_DATA` to the owner's set-up data directory, so the Chromium tests run
  instead of skipping (the tests give the tools a copy of their own and never write into it):

  ```bash
  cd plugins/brand-creator
  export BRAND_CREATOR_DATA="$HOME/.claude/plugins/data/brand-creator-jack1913"
  uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4 --dist worksteal
  node --test --test-timeout=180000 "tests/node/*.test.mjs"
  ```

  A skip with NOT VERIFIED is not a pass. The baseline run without the data directory (1 failed, 1227 passed, 679 skipped)
  had one pre-existing failure, `tests/test_setup_prereq.py::test_prereq_reports_ok_on_a_complete_machine` (Chromium missing
  for `prereq` without a data directory); it is not caused by this work.
- Docs checks, from the repository root (CI runs the docs check with `--strict`):

  ```bash
  python3 .github/scripts/check-docs-standard.py --strict
  npx markdownlint-cli2 "plugins/brand-creator/**/*.md"
  lychee --config lychee.toml --root-dir "$(pwd)" './plugins/brand-creator/**/*.md'
  claude plugin validate plugins/brand-creator --strict
  ```

## 0a. Cross-group review (2026-10-30)

The three plans were checked against each other and against the code. What binds this group:

- Groups run in order, one implementer at a time in one working tree: group 1 (this plan, ends with G1-25), then group 2
  (ends with G2-19), then group 3. ADR numbers: group 1 ADR-0006 to ADR-0008, group 2 ADR-0009 and ADR-0010, group 3
  ADR-0011 and ADR-0012.
- `Report.write` (scripts/lib/_common.py) spreads `extra` at the top level of the report JSON: a page-check report holds
  top-level `target`, `widths`, `schemes`, `measures` and `samples` keys, never an `extra` object. Groups 2 and 3 read them so.
- `scripts/pagelib/pagecheck.py` is importable by other tools (standard library plus `scripts/lib` only) and exports
  `report_tool(ident)` (a project page: `ident` is its project-relative posix path) and `is_loopback_url(url)`.
  `scripts/lib/_common.mjs` exports `isLoopbackUrl(url)`, used by `render.mjs page-measure` and later by group 3's
  `render.mjs wiring`. Groups 2 and 3 import these; they never write a second version.
- `scripts/boardlib/reflex.py` takes the cliché file as a parameter (`cliche_items(project, rel="research/cliches.md")`) and
  holds the per-line rules as functions (`line_rows`, `shared_hit`), so group 2's site board reuses them for
  `research/site-cliches.md` without changing this group's code.
- `page-tells.json` keeps its tells under `tells` (`tells[].id`), and is linked from `skills/brand-creator/SKILL.md`'s
  References list: `test_every_link_resolves_and_every_reference_is_linked_from_skill_md` fails on any file of
  `references/` that SKILL.md does not link.
- No skill `description` changes in this group (owner default: descriptions change only in group 2); G1-20 changes the
  check wrapper's `argument-hint` and body only.
- Example and test pages for the page check live in `pages/`, never in `site/`: group 2 reserves `site/<id>/` and
  `site/site.json` for approved reference pages.
- Changing `scripts/lib/*.py` (G1-13 and G1-18 change `qa_rules.py`) makes packs recorded with `staleness --write` read as
  stale. G1-13 says so once in the CHANGELOG; group 2 (which changes `_common.py`) does not repeat it.

## 1. Goal

Make the brand side of the web real in brand-creator, without building production sites:

1. The reflex test on pick boards is checked, not only present, and a judge cross-check makes "no hits" an answer that can
   be challenged. The reflex list gains the patterns that shipped unnoticed in a real brand's site.
2. The scope is written down: brand-creator owns website references, an optional site round, a generated brand kit and a
   page check for pages built anywhere; production sites are built in product repositories.
3. The handoff tells the truth: DESIGN.md, BRAND.md and the applied skill read sizes, weights, spacing and radius wherever
   the tokens hold them, and never invent a value.
4. Every ground that carries text has complete roles (text, action, on-action, focus, border) in both themes, checked by
   contrast and colour-vision distance; the owner names the grounds.
5. The starter tokens carry layout slots as proposals, and `check` warns at G4 about starter values still in place.
6. `brand-creator page-check` measures any rendered page against the brand: brand rules fail, generic tells warn and can be
   adopted as brand rules.
7. Small fixes: shots into a project `specimens/` folder, a colour-divergence warning between directions, a timeline
   comparison between motion variants, and component motion proofs (hover and press).

## 2. Design decisions

Defaults marked "default, owner may change" come from the roadmap's open owner questions or are this plan's proposals.

- Reflex format. One parseable line per hit: `hit: <id> | <argument>`. `no hits` stands alone. `near miss: <id> (<why>)` is
  recorded and never counted. A hit names an id of `skills/brand-creator/references/ai-defaults.json` or an item of the
  project's `research/cliches.md` section "Avoid unless argued". An optional leading `Reflex test:` label is allowed.
- Reflex rules that fail now: two or more hits in one direction; one hit shared by every direction. They are the two rules
  `ai-defaults.json` already states, and no shipped board breaks on them.
- Reflex rules that warn for one release, then fail (the CHANGELOG says so): a line not in the format; a hit naming no
  known pattern; an argument that shares no content word with FACTS.md or brief/BRIEF.md; a missing judge list when the
  judge ran; a pattern the judge saw that the reflex line neither hits nor names as a near miss.
- Grounding words (language-neutral floor, not a quality judgement): Unicode letters only (`[^\W\d_]+`, casefolded),
  4 letters or more, taken from the lines of `FACTS.md` and `brief/BRIEF.md` that are not verbatim lines of the plugin's
  `templates/FACTS.md` and `templates/BRIEF.md`, minus the words of the templates' non-table lines (their boilerplate).
  No English stop list is ported. Default, owner may change.
- The judge lists what it sees (`JUDGE_SCHEMA.reflex_seen`); the lead puts the list next to the declared reflex line
  (`data-field="reflex-seen"`). The judge judges layout patterns on each direction's own homepage frame of the deep board,
  never on the board's chrome. Agents only after the fleet gate, in-thread by default (default, owner may change).
- ADR numbers: this group takes ADR-0006 (reflex test checked beyond presence; extends archived decision 37), ADR-0007
  (brand-creator owns the brand side of the web) and ADR-0008 (text grounds carry complete roles). Groups 2 and 3 start at
  ADR-0009.
- The orchestrator description and its trigger tests do not change in this group ("description changes only in group 2";
  default, owner may change). Nothing is added to the top of `skills/brand-creator/SKILL.md` (19,964 of 20,000 characters).
- The applied skill stays and is extended; the kit of group 3 is built around it (default, owner may change).
- Grounds: `$extensions["brand-creator"].grounds` in `tokens/semantic.light.tokens.json` holds `named_by_owner` (the date
  and the owner's words) and `list` (one entry per ground with its five roles). The starter carries a proposal for
  `color.bg` with `named_by_owner` empty; contrast warns until the owner names the grounds. The model never guesses.
- Starter layout slots (proposals until G4; default, owner may change): `space.1`..`space.8` = 4, 8, 12, 16, 24, 32, 48,
  64 px; `radius.sm`/`md`/`lg`/`pill` = 4, 8, 16, 999 px; `layout.container` 1200 px, `layout.gutter` 24 px;
  `breakpoint.sm`/`md`/`lg`/`xl` = 640, 768, 1024, 1280 px; `leading.display` 1.1, `leading.body` 1.5 (`$type`
  `number`); `tracking.display` -0.01, `tracking.body` 0 (`$type` `number`, in em: DTCG 2025.10 dimensions are px or rem
  only).
- `tokens:starter` warns at G4 when a primitive still holds the starter's value (motion values included) and never fails.
  The owner keeps a value by listing it in `$extensions["brand-creator"]["starter-kept"]` of
  `tokens/primitives.tokens.json` with the date and their words.
- Page check: brand rules fail, reflex tells warn. A tell becomes a brand rule only through `qa/rules.json` `page.rules`
  with a `g4` line, and a typed rule fails only once that line is a recorded "(rule)" line of G4; before, it warns.
- Page check widths: 360, 390, 768, 1024, 1440 and 1920, light and dark (`qa/rules.json` `page.widths` or `--widths`
  override). Proposals until G4 (default, owner may change): display face minimum 20 px (`page.display_min_px`), clear space
  0.25 of the mark's rendered height (`page.clear_space`), hero text budget 45 words (in `page-tells.json`).
- Page check targets: a page in the project; `--from DIR` (a built site anywhere, copied to the data folder's scratch area
  and served from there, read only); `--url` for a page on this machine only (`localhost`, `127.0.0.1`, `[::1]`). A remote
  URL is a usage error in this group (group 2 adds remote shots for research). Default, owner may change.
- Claims: numbers and status words must match a FACTS.md value or sit inside a labelled `data-sample` element; labelled
  samples pass and are listed as the before-publishing list (`page:samples`); unlabelled unbacked claims fail (default,
  owner may change). A bare single digit (a step label) is not a claim.
- Word lists in English and Polish; every other page language is reported "NOT verified" in a warning row (default, owner
  may change).
- The plugin's own social post kicker (`templates/social/post-1x1.html`, `.kicker`: small, uppercase, tracked, above the
  headline) is an eyebrow by the new tell. It is reported, not changed (default, owner may change).
- `check` does not gate page-check reports in this group; group 2 decides how reference pages are gated.
- The pilot brand's project stays untouched (default, owner may change): calibration on its pages (G1-25) is read-only,
  from a scratch copy, and only on the owner's yes at that time.

## 3. Architecture

```text
board-lint (scripts/board_lint.py)
  └─ scripts/boardlib/reflex.py        parse reflex lines, known ids, grounding words, judge list   (stdlib, outside lib/)
  └─ scripts/boardlib/divergence.py    OKLab distance of --d-paper/--d-ink/--d-accent per direction
  └─ scripts/boardlib/motionboard.py   + motion:timelines (variants' length and animation count)

workflows/directions.js               JUDGE_SCHEMA.reflex_seen; the judge prompt names ai-defaults.json and cliches.md

tokens (scripts/build_tokens.mjs)     resolves $extensions.grounds into tokens.json "grounds" (only when present)
contrast (scripts/contrast.py)        grounds:* rows and cvd:*:grounds:* rows (warnings in this release)
check (scripts/check.py)              tokens:starter (warning at G4)
adapters / applied-skill (scripts/adaptlib/adapt.py)
                                      sizes, weights, spacing, radius, leading, tracking, layout, grounds

page-check (scripts/page_check.py, uv, stdlib)
  ├─ scripts/pagelib/pagecheck.py     judging: rows, tokens, FACTS, qa/rules.json page block, page-tells.json
  ├─ writes a request JSON into <data>/scratch/<project>/page-check/<slug>-<hash6>/
  ├─ runs: node scripts/render.mjs page-measure --request <req.json> --out <measures.json> --project <dir>
  │        render.mjs (the only Chromium driver) imports scripts/pagelib/page_measure.mjs (in-page collectors)
  └─ report: <project>/assets/_checks/page-check/<slug>-<hash6>.json  (tool "page-check/<slug>-<hash6>")

skills/brand-creator/references/page-tells.json   the generic tells (reflex tier), EN and PL word lists
```

Measuring happens in the browser (`page_measure.mjs` returns raw facts: colours, text pairs, fonts, marks, motion
declarations, controls, tell candidates); judging happens in Python against the brand (`pagecheck.py`). One Chromium driver.

## 4. Interfaces this group gives the later groups

- ADR numbers 0006 to 0008 are taken; group 2 takes ADR-0009 and ADR-0010, group 3 ADR-0011 and ADR-0012.
- `brand-creator page-check <page> | --from DIR <page> | --url URL [--project DIR] [--widths ...] [--schemes ...]`, exit
  codes 0, 1, 2, 3; report tool `page-check/<slug>-<hash6>` from `pagecheck.report_tool(ident)` (import it; for a project
  page the ident is its project-relative posix path); row ids `page:load:<width>-<scheme>`, `page:colours:<scheme>`,
  `page:pairs:<scheme>`, `page:fonts`, `page:display-size`, `page:mark-file`, `page:mark-band`, `page:mark-clear-space`,
  `page:motion`, `page:claims`, `page:samples`, `page:rule:<id>`, `tell:<id>`, `note:stock-anatomy`. `rep.extra` is written
  at the top level of the report: `target` (`{kind, page, from, url}`), `widths`, `schemes`, `measures` (path) and
  `samples` (`[{label, text, selector, view}]`: the before-publishing list group 3's recipe reads). The report's `inputs`
  hold the page and every project file it loaded (tokens.css included), so a token change makes it stale.
- `pagecheck.is_loopback_url(url)` (Python) and `isLoopbackUrl(url)` exported by `scripts/lib/_common.mjs`: the one
  loopback rule (`http` or `https` on `localhost`, `127.0.0.1` or `[::1]`).
- `data-sample="<label>"` marks sample content on any page; `data-brand-mark` (optionally with the file it shows) marks the
  brand mark.
- `qa/rules.json` `page` block: `widths`, `display_min_px`, `clear_space`, `rules[]` (`id`, `kind` in
  `max-marks-per-view`, `max-words-per-control`, `words-under-accent`, `tell`; `g4`; kind keys).
- `skills/brand-creator/references/page-tells.json` (tells under the key `tells`; ids: `eyebrow`, `arrow-glued`,
  `middot-run`, `stock-second-action`, `hero-text-budget`, `styled-div-mock`, `three-equal-tiles`; note `stock-anatomy`).
  Group 2 feeds the category's site clichés (`research/site-cliches.md`) into the hero variants' reflex lines on its site
  board; it does not change `pagecheck.py`.
- `scripts/render.mjs page-measure --request FILE --out FILE [--project DIR]` and `scripts/pagelib/page_measure.mjs`
  (`collect(page, request)`); group 2 adds its own `render.mjs capture` subcommand (stills, and real sites with `--url`).
- `specimens/<name>/` in a project and `shot --out specimens/<name>`.
- Starter token names (section 2) and the adapter output: DESIGN.md `typography` (`<family>`, `text-<step>`,
  `weight-<name>`), `spacing` (`space-<step>`), `rounded`; the applied skill's optional `## Layout` section; tokens.json
  `grounds`. Group 3's kit core is built from `adapt.py`.
- `scripts/boardlib/reflex.py` (`parse`, `hits`, `norm`, `known`, `ai_default_ids`, `cliche_items(project, rel=...)`,
  `content_words`, `ground_words`, `parse_seen`, `line_rows`, `shared_hit`): group 2 calls `line_rows` and `shared_hit`
  for the hero variants of its site board, with `research/site-cliches.md` and the `page-tells.json` ids.
- Motion proof case `type: "component"` (`page`, `selector`, `states`, `rule`).

## 5. Tasks

Order keeps the suite green after each task. Dependencies are listed per task; tasks run one after another.

### G1-01 ADRs 0006, 0007 and 0008

Roadmap steps: 1 (ADR part), 2, 5 (ADR part). Depends on: none.

Files: `docs/adr/ADR-0006-reflex-test-checked-beyond-presence.md`, `docs/adr/ADR-0007-brand-side-of-the-web.md`,
`docs/adr/ADR-0008-text-grounds-carry-complete-roles.md`, `docs/adr/README.md`.

Write three ADRs from `docs/adr/ADR-TEMPLATE.md` (Status `accepted`, Date `2026-10-30`, Source naming files and headings,
never `file:line`; cite the archived decisions log by decision number and title). Plain technical voice.

- ADR-0006. Context: archived decision 37 "Reflex test linted" stopped at presence ("the argument's quality stays a
  judgement"); `ai-defaults.json` states two count rules nobody enforces; nothing detects an undeclared hit. Decision: the
  format, the two fail rules, the four warn-then-fail rules, the grounding floor and the judge list (section 2 of this
  plan). It extends decision 37. Consequences: boards keep passing this release; the next release turns the warnings into
  failures; the grounding rule is a floor, lenient for languages whose function words are long; credit: the idea that an
  exception's argument must share a word with the page's own material comes from Hallmark (MIT, "Hallmark contributors");
  no code or text was copied, and its ASCII-only word matching was not ported.
- ADR-0007. Context: the orchestrator's description excludes web pages, yet the deep board draws a homepage and the applied
  skill names pages; a real brand built six page templates, a site chapter and a hand-made kit; its site corrections were
  brand-rule breaks a script can catch. Decision: brand-creator owns the brand side of the web (website references, an
  optional site round producing reference pages, a generated brand kit around the applied skill, a page check for pages
  built anywhere); production sites are built in product repositories; the page check has two tiers (brand rules fail,
  generic tells warn and are adoptable as brand rules tied to a G4 line); word lists English and Polish; the handoff tells
  the truth (sizes, weights, spacing, radius wherever they live; layout slots in the starter as proposals; a starter warning
  at G4); the description and trigger tests change only with the site round. Consequences: the social post kicker of
  `templates/social/post-1x1.html` is an eyebrow by the new tell and stays as it is; approved pages are references (each
  choice tagged rule or example), never fill-in templates. Credits (ideas only, rewritten): Hallmark's split between rules
  that fail and tells that warn, starting from the visitor's job, hero first with a cold review, and a record of what an
  existing site must keep. Hallmark is not installed, bundled, forked or bridged.
- ADR-0008. Context: a real brand's dark theme put a butter button on a butter hero with an invisible focus ring.
  Decision: every ground that carries text has text, action, on-action, focus and border roles in light and dark, checked
  by contrast and colour-vision distance; the owner names the grounds (recorded in `grounds.named_by_owner`), never the
  model; warnings for one release, then failures; the starter carries a proposal for `color.bg`. Consequences: existing
  projects see warnings until the owner names their grounds.
- `docs/adr/README.md`: three rows in the table, in order.

Tests: none (docs only). Acceptance: the docs checks pass; the three files follow the template.

Verify:

```bash
# from the repository root
python3 .github/scripts/check-docs-standard.py --strict
npx markdownlint-cli2 "plugins/brand-creator/docs/adr/*.md"
lychee --config lychee.toml --root-dir "$(pwd)" './plugins/brand-creator/docs/adr/*.md'
```

### G1-02 ai-defaults.json version 2

Roadmap steps: 1. Depends on: none.

Files: `skills/brand-creator/references/ai-defaults.json`, `tests/test_skills.py`, `CHANGELOG.md`.

- Set `"version": 2`. Keep exactly the five keys per item (`id`, `kind`, `pattern`, `why_reflex`, `argue_with`); no colour
  values (a test forbids `#hex`).
- Rewrite `how_to_use` (five lines): the line format (`no hits`, or one `hit: <id> | <argument>` per hit, where `<id>` is
  an id below or an item of `research/cliches.md` "Avoid unless argued"; `near miss: <id> (<why>)` is not a hit); each
  argument names something of this brand from FACTS.md or brief/BRIEF.md and shares a word with them; two or more hits in
  one direction: replace a part (board-lint fails it); every direction hitting one id: not divergent (board-lint fails it);
  layout items are judged on the direction's own homepage frame of the deep board, never on the board's chrome.
- Add four items, written fresh in plain words:
  - `palette-pale-ground-timid-accent` (palette): a near-white or pale grey ground with one low-chroma accent used only on
    links or one small detail, so the identity reads as no colour at all.
  - `type-first-answer-display-face` (type): the display faces a generator names first, "as of 2026-10" for example
    Fraunces, Playfair Display, DM Serif Display or Space Grotesk, used with no reason of the brand's own (the date is in the
    pattern text, not a new key).
  - `device-texture-as-identity` (device): a texture standing in for the idea: film grain, a rubber stamp or badge, an
    engraving or a halftone screen.
  - `layout-stock-product-page` (layout): a small label over every heading (an eyebrow) and the stock section order: a hero
    with two buttons, three equal steps or feature tiles, an FAQ, a closing call-to-action band.
- `tests/test_skills.py::test_ai_defaults_is_a_generic_reflex_list`: also assert `d["version"] >= 2`, the four ids, `"as of
  2026-10"` in the `type-first-answer-display-face` pattern, and `"hit: <id> | <argument>"` in `how_to_use`.
- CHANGELOG Changed: the reflex list has four new patterns (name them in words).

Tests: the extended test; break check: remove one new id locally and see the test fail, then restore.

Verify: `pytest -k "ai_defaults or templates_are_self_contained"` (with the common command prefix).

### G1-03 Reflex line parser (scripts/boardlib/reflex.py)

Roadmap steps: 1. Depends on: G1-02.

Files: `scripts/boardlib/reflex.py` (new, stdlib only), `tests/test_reflex.py` (new).

API (pure functions, no I/O except the named file reads):

- `Entry(kind: "hit" | "near-miss", name: str, argument: str)`; `Parsed(no_hits: bool, entries: list[Entry], problems:
  list[str])`; `hits(parsed) -> list[Entry]`.
- `parse(text)`: collapse white space; drop a leading `Reflex test:` (any case). Markers are `hit:` and `near miss:` (also
  `near-miss:`), any case, not preceded by a letter or `-`. No marker: `no hits` (optionally followed by any text) is
  `no_hits=True`; anything else is one problem ("free text: write 'no hits', or one 'hit: <id> | <argument>' per hit").
  With markers: text before the first marker must be empty or start with `no hits`; each `hit:` body splits at the first
  `|` into name and argument (no `|`, or an empty name or argument, is a problem naming the entry); a `near miss:` name runs
  to the first `(` or the end; `no hits` together with a hit is a problem.
- `norm(name)`: casefold, collapse spaces, drop one trailing parenthetical.
- `ai_default_ids(path=None)`: ids of `skills/brand-creator/references/ai-defaults.json` (the plugin root from
  `Path(__file__).resolve().parents[2]`).
- `cliche_items(project, rel="research/cliches.md")`: bullets under the heading "Avoid unless argued" of that file
  (placeholders such as `(...)` and HTML comments dropped); `[]` when the file is missing. Group 2 passes
  `rel="research/site-cliches.md"`.
- `known(name, ids, cliches) -> "ai-defaults" | "cliches" | None` (compares `norm` forms).
- `content_words(text) -> set[str]`: `re.findall(r"[^\W\d_]+", text.casefold())`, length 4 or more.
- `ground_words(project) -> set[str]`: content words of the lines of `FACTS.md` and `brief/BRIEF.md` that are not
  verbatim (stripped) lines of the plugin's `templates/FACTS.md` and `templates/BRIEF.md`, minus the content words of those
  templates' lines that do not start with `|`.
- `parse_seen(node_texts: list[str]) -> list[str]`: the judge list: the texts of `li` items when given, else one text that
  is `none seen` (empty list) or items split at `;` after an optional `judge saw:` / `seen:` label.

Tests (`tests/test_reflex.py`, no setup markers; import the module by putting `scripts/boardlib` on `sys.path` as other
unit tests do): the three new Acme lines parse (one near miss, one hit with its argument, one near miss); legacy free
text gives a problem; `hit: x` without `|` gives a problem; `no hits` plus a hit gives a problem; a near miss is not a hit;
Polish words with diacritics (`łódź`, `żółć`) survive `content_words`; `ground_words` drops the template boilerplate line
words and keeps a project fact; `known` matches a cliché bullet with a trailing parenthetical.

Acceptance: `pytest tests/test_reflex.py` passes; the module is not under `scripts/lib/`.

### G1-04 board-lint: reflex count and shared hit (fail), format and ids (warn)

Roadmap steps: 1. Depends on: G1-03.

Files: `scripts/board_lint.py`, `skills/brand-creator/references/examples/acme/rounds/r1/board.html`,
`tests/smoke/quick-bakery/board.html`, `tests/smoke/quick-bakery/research/cliches.md` (new), `tests/smoke/quick.sh`,
`tests/test_board_lint.py`, `tests/test_quick_tier.py`, `templates/round-page.html`, `templates/review/index.html`,
`skills/brand-creator/references/board-contract.md`, `skills/brand-creator/references/phases/03-strategy-directions.md`,
`scripts/CONTRACT.md`, `skills/brand-creator/references/phases/09-qa.md`, `CHANGELOG.md`.

Behaviour (pick boards only; after the existing `field(d, "reflex", True, ...)` call near the end of the direction loop):

| row | status | when |
| --- | --- | --- |
| `direction:<name>:reflex-format` | warn (pass otherwise) | the reflex line has parse problems; the detail quotes them and the format |
| `direction:<name>:reflex-ids` | warn (pass otherwise) | a hit names neither an `ai-defaults.json` id nor an item of `research/cliches.md` "Avoid unless argued"; the detail says when the project has no `research/cliches.md` |
| `direction:<name>:reflex-count` | fail (pass otherwise) | two or more hits in one direction ("replace a part before showing it") |
| `directions:reflex-shared` | fail (pass; info with fewer than 2 parsed directions) | every direction hits one same name (`norm`); names it |

Warn rows say "a failure from the next release". Add `research/cliches.md` to the report's inputs when it exists (a
changed cliché list makes the lint stale).

Put the rules in `scripts/boardlib/reflex.py`, not in `board_lint.py`, so group 2's site board reuses them unchanged:
`line_rows(parsed, ids, cliches, ground=None, sources="ai-defaults.json or research/cliches.md") -> list[tuple[suffix,
status, detail]]` (suffixes `reflex-format`, `reflex-ids`, `reflex-count`, and from G1-05 `reflex-grounded`; `ground=None`
skips the grounding row) and `shared_hit(parsed_list) -> str | None` (the `norm` name every parsed line hits, when there are
two or more). `board_lint.py` adds each suffix under `direction:<name>:` and the shared row as `directions:reflex-shared`.

Fixtures and anchors:

- Acme r1 board: Compass `no hits. near miss: device-product-silhouette (it is not a tool outline)`; Lantern
  `hit: type-geometric-rounded-friendly | <an argument that shares a word with Acme's FACTS.md or BRIEF.md, for example
  "small workshops">`; Keystone `no hits. near miss: palette-navy-gold-trust (cobalt is not navy and there is no gold)`.
- Bakery board (third direction): `hit: wheat-adjacent shape | <argument sharing "sourdough" or "morning" with its facts>`;
  add `tests/smoke/quick-bakery/research/cliches.md` (from `templates/cliches.md` shape: Category, Clichés seen, Map axes,
  "Avoid unless argued" with `- wheat-adjacent shape (an ear, a sheaf, chevrons that read as grain)`, an empty Forbidden);
  `tests/smoke/quick.sh` copies it to `$P/research/cliches.md` next to the brief and facts copies;
  `tests/test_quick_tier.py`: add the file to the list in `test_quick_smoke_reads_only_files_that_exist`, and in
  `test_the_bakery_board_passes_board_lint` copy it too and assert no `direction:*:reflex-ids` row warns.
- `tests/test_board_lint.py::test_pick_board_directions_need_a_reflex_result`: update the mutation anchor to the new
  Lantern text.
- Template fill markers (`templates/round-page.html` and `templates/review/index.html`, the `data-field="reflex"` line):
  `[[fill: reflex test against ai-defaults.json and research/cliches.md: "no hits", or one "hit: <id> | <argument from
  FACTS.md or the brief>" per hit; "near miss: <id> (why)" is not a hit]]`.

Tests (new, in `tests/test_board_lint.py`, using the `proj` fixture):

- `test_two_reflex_hits_in_one_direction_fail_the_count` (m): mutate Lantern's line to two hits; exit 1,
  `direction:Lantern:reflex-count` fails.
- `test_one_hit_in_every_direction_fails_as_not_divergent` (m): mutate all three lines to hit one id; exit 1,
  `directions:reflex-shared` fails.
- `test_a_free_text_reflex_line_warns_and_the_board_still_passes` (m): mutate to the old free text; exit 0, the format row
  warns.
- `test_a_hit_that_names_no_known_pattern_warns_until_cliches_lists_it` (m): mutate the id to `wheat-sheaf`; warn; write
  `research/cliches.md` with that item under "Avoid unless argued"; pass.
- `test_a_near_miss_is_not_counted_as_a_hit` (f): a direction with one hit and one near miss passes the count.

Docs: `scripts/CONTRACT.md` Board contract: the `direction` row's reflex note and a short "Reflex test (pick boards)"
paragraph with the format and the four rows; `board-contract.md` (the direction row and the per-direction cells bullet);
`03-strategy-directions.md` step 4 (format, near miss, the two failures); `09-qa.md` board-lint row: append the two
failures and the two warnings to "Blocks" and cite the five tests; CHANGELOG Changed (board-lint checks the reflex line:
two failures now, two warnings that become failures in the next release).

Acceptance: the Acme and bakery boards pass with no reflex warning in a project that has the matching cliché file; the
suite is green.

Verify: `pytest -k "board_lint or quick_tier or reflex or skills"`; the docs checks.

### G1-05 board-lint: grounded arguments and the judge cross-check (warn)

Roadmap steps: 1. Depends on: G1-04.

Files: `scripts/board_lint.py`, `templates/round-page.html`, `templates/review/index.html`, `tests/test_board_lint.py`,
`scripts/CONTRACT.md`, `skills/brand-creator/references/board-contract.md`, `skills/brand-creator/references/phases/09-qa.md`,
`CHANGELOG.md`.

Behaviour (pick boards):

| row | status | when |
| --- | --- | --- |
| `direction:<name>:reflex-grounded` | warn (pass otherwise) | a hit's argument shares no word with `reflex.ground_words(project)`; the pass detail names the shared words; with neither FACTS.md nor brief/BRIEF.md: warn "NOT verified" |
| `direction:<name>:reflex-seen` | warn (pass) | only when `my-call` has `data-judge="ran"`: the direction has no non-empty `data-field="reflex-seen"` |
| `direction:<name>:reflex-unargued` | warn (pass) | an item of the judge list is neither a hit nor a near miss of the reflex line (compare `norm`); names it and says "argue it as a hit, or say why it is a near miss" |

The grounding rule lives in `reflex.line_rows` (its `ground` argument), the judge rows in `board_lint.py`.
Add `FACTS.md` and `brief/BRIEF.md` (when they exist) to the report's inputs. Templates: after the reflex line of each
direction add an HTML comment block `<!-- when the judge ran: <p class="reflex-seen" data-field="reflex-seen">judge saw:
[[fill: the ai-defaults ids and research/cliches.md items the judge listed for this direction, or "none seen"]]</p> -->`
(comments are not linted; no `--` inside).

Tests (copy `FIXTURES / "FACTS.md"` and `FIXTURES / "brief" / "BRIEF.md"` into the project where grounding must pass):

- `test_an_argument_that_shares_no_word_with_the_facts_or_the_brief_warns` (m).
- `test_a_polish_argument_is_grounded_on_a_polish_fact` (f): a project whose FACTS.md row and argument are Polish words
  with diacritics.
- `test_with_the_judge_a_direction_needs_the_judge_list_and_an_unargued_pattern_warns` (m): set `data-judge="ran"` (with
  its three panels), add a `reflex-seen` list naming an id the line does not mention; both warnings; adding it as a near
  miss clears `reflex-unargued`.

Docs: CONTRACT Board contract (the two judge rows, the grounding rule in one paragraph); `board-contract.md` judge
paragraph (put the judge list next to the reflex line); 09-qa Warnings section bullet and board-lint row citations;
CHANGELOG Added.

Verify: `pytest -k "board_lint or reflex"`; the docs checks.

### G1-06 The judge lists the reflex patterns it sees

Roadmap steps: 1. Depends on: G1-02.

Files: `workflows/directions.js`, `agents/brand-judge.md`, `tests/node/workflows.test.mjs`, `CHANGELOG.md`.

- `JUDGE_SCHEMA`: add required `reflex_seen`: array of `{key: string, items: array of {id: string, source: "ai-defaults" |
  "cliches", where: string}}` (`required: ["key", "items"]` and `["id", "source", "where"]`).
- Judge prompt: one new line before RULES: "REFLEX LIST: for each direction, before you read any argument, list every
  pattern of `<plugin_root>/skills/brand-creator/references/ai-defaults.json` and every 'Avoid unless argued' item of
  research/cliches.md (when the project has it) that you see in its board: the id or the cliché's words, its source and
  where you saw it. Judge layout patterns on the direction's own homepage frame, never on the board's chrome. An empty
  list is an answer."
- The returned `next` string: add "put judge.reflex_seen beside each direction's reflex line (data-field="reflex-seen")".
- `agents/brand-judge.md` "How you judge": one bullet "Reflex list" with the same rule.

Tests: new node test `the judge lists the reflex patterns it sees per direction, and the lead is told where they go` (f):
the dry run's judge call has `reflex_seen` in `schema.required`, its prompt names `ai-defaults.json` and `cliches.md`, and
`result.next` names `reflex-seen`. The existing tests (agent count, RULES line, static checks) still pass; `brand-creator
fleet-plan --check` exits 0.

Docs: CHANGELOG Changed (the judge of a direction round lists the reflex patterns it sees). No 09-qa row (not a check).

Verify: `node --test tests/node/workflows.test.mjs`; `bin/brand-creator --data "$BRAND_CREATOR_DATA" fleet-plan --check`.

### G1-07 Layout token slots in the starter

Roadmap steps: 6. Depends on: none.

Files: `templates/tokens/primitives.tokens.json`, `tests/test_skills.py`, `tests/test_contrast_tokens.py`,
`skills/brand-creator/references/phases/07-tokens.md`, `scripts/CONTRACT.md`, `CHANGELOG.md`.

- Add groups `space`, `radius`, `layout`, `breakpoint` (`$type` `dimension`, `{value, unit: "px"}`), `leading` and
  `tracking` (`$type` `number`), with the values of section 2; each group's `$description` says "proposals until G4"
  (tracking also says "in em: letter-spacing: calc(var(--tracking-display) * 1em)").
- `07-tokens.md` technique 7 "Type and units": the layout slots and that they are proposals until G4; Gate: one example
  rule line "(rule) layout: space steps `space.1`-`space.8`, radius `radius.*`, container `layout.container`, gutter
  `layout.gutter`, breakpoints `breakpoint.*`, display line height `leading.display` and tracking `tracking.display`
  (proposal; when the brand has a site or an app)". Do not change the sentence the test at `test_skills.py` pins about the
  motion starter values.
- CONTRACT Token sources: one bullet listing the starter's layout groups and that `number` tokens reach `tokens.css` and
  `tokens.json` only.

Tests: `tests/test_skills.py::test_token_templates_carry_both_schemes_and_computed_hex`: the six groups exist and each
`$description` holds "proposals until G4". New `tests/test_contrast_tokens.py::test_the_starter_tokens_build_with_their_layout_slots`
(f, requires_setup): a project gets the three starter files copied into `tokens/`, `brand-creator tokens` exits 0,
`tokens.css` holds `--space-1: 4px`, `--leading-display: 1.1` and `--tracking-display: -0.01`, and `tokens.json` `other`
holds them.

Docs: CHANGELOG Added (the starter tokens carry spacing, radius, container, gutter, breakpoints, line height and tracking
as proposals).

Verify: `pytest -k "token_templates or starter_tokens"`.

### G1-08 `tokens:starter` warning in check at G4

Roadmap steps: 6. Depends on: G1-07.

Files: `scripts/check.py` (or a helper in `scripts/adaptlib/gates.py`), `tests/test_qa_infra.py`, `scripts/CONTRACT.md`,
`skills/brand-creator/references/phases/09-qa.md`, `skills/brand-creator/references/phases/07-tokens.md`, `CHANGELOG.md`.

Behaviour: with G4 recorded and `tokens/primitives.tokens.json` present, compare every leaf token (`$value`, compared as
canonical JSON) with the same path in the plugin's `templates/tokens/primitives.tokens.json`. Paths listed in
`$extensions["brand-creator"]["starter-kept"]` (`{"decided": "<YYYY-MM-DD> <owner's words>", "paths": [...]}`) of the
project's primitives are kept. Rows:

- `tokens:starter` warn: "still the starter's proposal: <paths> (N); ask the owner to keep them (list them in starter-kept
  with the date and their words) or change them". Pass when none is left ("kept by the owner: ..." when some are kept).
- A `starter-kept` without a dated `decided` or a list `paths`: the same row warns and says what is wrong.
- Before G4: no row. Never a failure, never exit 2.

Make sure `brand-creator tokens` still builds a file with that `$extensions` entry (test it).

Tests (`tests/test_qa_infra.py`):

- `test_at_g4_check_warns_about_starter_values_still_in_place` (f): starter primitives copied, G4 recorded, `check`; the
  row warns and names `motion.base`; no row before G4.
- `test_a_changed_or_kept_starter_value_is_no_longer_listed` (m): `mutate_json` changes `motion.base`; it is gone from the
  list; a `starter-kept` entry for `motion.quick` moves it to the kept list.

Docs: CONTRACT "What `check` gates from these" (one paragraph); 09-qa: the `check` row says it warns about starter values
at G4 and cites both tests; Warnings section bullet; 07-tokens.md Gate (one sentence); CHANGELOG Added.

Verify: `pytest -k "starter"`.

### G1-09 The handoff tells the truth (adapters and applied skill)

Roadmap steps: 4. Depends on: G1-07.

Files: `scripts/adaptlib/adapt.py`, `templates/applied-skill/SKILL.md`, `tests/test_adapters.py`, `scripts/CONTRACT.md`,
`CHANGELOG.md`.

Behaviour (read only what `assets/tokens/tokens.json` holds; never invent a value):

- New `layout_tokens(doc)`: classify the keys of `doc["other"]` by name, where the name is the key with a leading
  `dimension.` dropped: first segment (or the part before the first `-` of a one-segment name) `space`/`spacing` →
  spacing; `radius`/`rounded` → rounded; `weight` → weights; a segment starting `text-` (for example `size.text-sm`) →
  sizes; `leading`/`line-height` → leading; `tracking`/`letter-spacing` → tracking; `layout`, `container`, `gutter`,
  `breakpoint` → layout. Order by name.
- DESIGN.md frontmatter: `typography` keeps one entry per `font.*` family; a `leading.<n>`/`tracking.<n>` joins the
  family entry of the same name (`lineHeight`, `letterSpacing: <n>em`), or makes its own entry `<n>` when no family has that
  name; one entry per size `text-<step>: {fontSize: <value>}`; one per weight `weight-<name>: {fontWeight: <n>}`.
  `spacing` entries are named `space-<rest>` (`space.1` → `space-1`, `dimension.space-1` → `space-1`, as today); `rounded`
  entries are named after radius/rounded (`radius.sm` → `sm`, `dimension.radius-card` → `card`).
- DESIGN.md prose: `## Typography` lists families, then sizes, weights, line height and tracking that exist; the
  unconditional "Families only: the tokens define no sizes or weights." goes; when neither sizes nor weights exist the
  sentence "The tokens define no sizes or weights." stays (true). `## Layout` names the groups the spacing came from and
  lists radius, container, gutter and breakpoints that exist.
- BRAND.md `### Type`: sizes and weights lines when they exist; a `### Layout` block when layout values exist.
- Applied skill: `{{type}}` adds sizes, weights, line height and tracking; a new optional `{{layout}}` placeholder on its
  own line after `## Type` in `templates/applied-skill/SKILL.md` is a whole `## Layout` section or nothing (drop
  `{{layout}}\n\n` when empty, as `{{motion}}` is dropped); add `layout` to the fill map so the placeholder guard knows it.

Tests (`tests/test_adapters.py`, module marks already require setup):

- `test_typography_carries_sizes_and_weights_wherever_they_live` (m): `mutate_json` Acme primitives to add `size.text-sm`
  14 px, `size.text-lg` 20 px, `weight.regular` 400, `weight.bold` 700, `radius.sm` 4 px and `space.3` 12 px; rebuild;
  DESIGN.md has `text-sm` with `fontSize: 14px`, `weight-bold` with `fontWeight: 700`, `space-3: 12px` and `sm: 4px` under
  `rounded`, no "Families only"; BRAND.md and the applied skill list the sizes and weights.
- `test_no_size_weight_or_layout_value_is_invented` (f): Acme as built: no `fontSize`, no `fontWeight`, the sentence "The
  tokens define no sizes or weights." present.
- `test_the_pinned_design_md_format_accepts_sizes_and_weights` (m, `requires_design_lint`): the mutated project's DESIGN.md
  passes the pinned lint with no error.
- Keep `test_design_md_carries_the_token_values_in_the_canonical_order` and the motion block test green (adjust only if the
  new Layout lines move what they compare, and say why in the test).

Docs: CONTRACT adapters (DESIGN.md `typography` now: families, sizes, weights, line height, tracking; spacing and rounded
read wherever the tokens hold them) and applied-skill (the optional Layout section); CHANGELOG Fixed (DESIGN.md and the
applied skill now carry the type sizes, weights, spacing and radius the tokens define, and no longer say there are none).

Verify: `pytest tests/test_adapters.py`.

### G1-10 Ground roles: starter and the token build

Roadmap steps: 5. Depends on: G1-07.

Files: `templates/tokens/semantic.light.tokens.json`, `templates/tokens/semantic.dark.tokens.json`,
`scripts/build_tokens.mjs`, `tests/node/tokens.test.mjs`, `tests/test_skills.py`, `scripts/CONTRACT.md`, `CHANGELOG.md`.

- Starter semantic files: roles `on-accent` (light `{color.paper}`, dark `{color.night}`) and `focus` (light
  `{color.signal}`, dark `{color.signal-bright}`); pairs `color.on-accent`/`color.accent` (`ui-text`, 4.5) and
  `color.focus`/`color.bg` (`ui-component`, 3); `grounds`: `{"named_by_owner": "", "list": [{"ground": "color.bg", "text":
  "color.text", "action": "color.accent", "on-action": "color.on-accent", "focus": "color.focus", "border":
  "color.border"}]}`. Confirm the starter still passes `contrast` (build a project from the starter in the test of G1-07).
- `build_tokens.mjs`, after the `distinct` block: when `$extensions["brand-creator"].grounds` exists, check its shape (an
  object with a string `named_by_owner` and a `list` of objects with a string `ground`); a wrong shape is a `grounds` fail
  row and nothing is written (as for pairs). Resolve each listed role in light and dark; a role name that is not a semantic
  colour token is a `grounds` warn row naming it, resolved as `null`. Write `grounds` into `tokens.json`: `{named_by_owner,
  list: [{ground, roles: {text, action, "on-action", focus, border}, modes: {light: {ground, text, action, "on-action",
  focus, border}, dark: {...}}}]}` (hex or `null`). Without the block, `tokens.json` is byte for byte what it was.

Tests (node, `tests/node/tokens.test.mjs`): `build: grounds resolve into tokens.json in both modes, an unknown role warns
and a project without them is unchanged` (f); `build: a grounds block of the wrong shape fails the build and writes
nothing` (f). `tests/test_skills.py` template test: `on-accent` and `focus` in both starter files, `grounds.list[0].ground ==
"color.bg"`, `named_by_owner == ""`.

Docs: CONTRACT Token sources (the `grounds` extension and its `tokens.json` form); CHANGELOG Added (starter roles for text
on the accent and the focus ring).

Verify: `node --test tests/node/tokens.test.mjs`; `pytest -k "token_templates"`.

### G1-11 contrast: complete roles on every text ground (warnings, colour vision included)

Roadmap steps: 5. Depends on: G1-10.

Files: `scripts/contrast.py`, `tests/test_contrast_tokens.py`, `tests/test_cvd.py`, `scripts/CONTRACT.md`,
`skills/brand-creator/references/phases/09-qa.md`, `skills/brand-creator/references/phases/07-tokens.md`, `CHANGELOG.md`.

Rows (section `grounds`; every one a warning in this release, saying "a failure from the next release"):

| row | warns when |
| --- | --- |
| `grounds:named` | `tokens.json` has no `grounds` ("ask the owner which colours text sits on; record them in grounds with the date and their words; never guess"), or `named_by_owner` does not start with a `YYYY-MM-DD` date ("a proposal, not named by the owner"); pass names the owner's words |
| `grounds:<mode>:<ground>:roles` | one of text, action, on-action, focus, border is missing or `null` |
| `grounds:<mode>:<ground>:text` | text on the ground under 4.5:1 |
| `grounds:<mode>:<ground>:action` | action against the ground under 3:1 |
| `grounds:<mode>:<ground>:on-action` | on-action on the action under 4.5:1 |
| `grounds:<mode>:<ground>:focus` | focus against the ground under 3:1 |
| `grounds:<mode>:<ground>:border` | border against the ground under 3:1 |
| `cvd:<mode>:grounds:<ground>:<role>` (with `--cvd`) | action or focus against the ground closer than the colour-vision threshold |

The report status and exit code do not change because of these rows.

Tests:

- `test_contrast_tokens.py::test_without_named_grounds_contrast_warns_and_still_passes` (f).
- `test_contrast_tokens.py::test_a_button_that_vanishes_into_its_dark_ground_warns_by_role` (m): `mutate_json` adds a
  `grounds` block for `color.bg` whose dark action equals the dark ground; `grounds:dark:color.bg:action` warns; exit 0.
- `test_contrast_tokens.py::test_a_ground_missing_a_role_warns_and_named_grounds_pass` (m).
- `test_cvd.py::test_a_ground_action_that_collapses_for_some_viewers_warns` (m).

Docs: CONTRACT (the grounds rows in the contrast part of Token sources or QA gates); 09-qa: the `contrast` and `contrast
--cvd` rows name the new warnings and cite the tests; Warnings section bullet; 07-tokens.md: a technique bullet "Text
grounds" and, at G4, the plain question "Which colours does text sit on?" recorded in the owner's words; CHANGELOG Added.

Verify: `pytest -k "contrast or cvd"`.

### G1-12 Ground roles reach DESIGN.md, BRAND.md and the applied skill

Roadmap steps: 5, 4. Depends on: G1-09, G1-11.

Files: `scripts/adaptlib/adapt.py`, `tests/test_adapters.py`, `scripts/CONTRACT.md`, `CHANGELOG.md`.

- With `tokens.json` `grounds`: DESIGN.md `components` gains `action-on-<ground>` (`backgroundColor: "{colors.<action>}"`,
  `textColor: "{colors.<on-action>}"`) and its `-dark` twin when both roles exist in dark; `<ground>` is the role name
  without `color.`. A role that is `null` is left out (never invented) and the prose says which ground lacks it.
- BRAND.md Visual: a `### Grounds` table (ground, text, action, on-action, focus, border; light and dark hex; "missing: ask
  the owner" for a `null`). The applied skill: the same table appended to the `{{colours}}` fill (no new placeholder).
- Without `grounds` the three files are byte for byte what they were.

Tests: `test_grounds_give_each_text_ground_its_action_component_and_table` (m, plus a `requires_design_lint` assertion that
the lint passes); `test_without_grounds_the_adapter_files_do_not_change` (f).

Docs: CONTRACT adapters and applied-skill; CHANGELOG Added.

Verify: `pytest tests/test_adapters.py`.

### G1-13 page-check skeleton: command, targets, measure path and report

Roadmap steps: 7. Depends on: none (run after G1-12 to keep one concern per task).

Files: `scripts/page_check.py` (new uv script), `scripts/page_check.py.lock` (`uv lock --script scripts/page_check.py`),
`scripts/pagelib/pagecheck.py` (new), `scripts/pagelib/page_measure.mjs` (new), `scripts/render.mjs`,
`scripts/lib/_common.mjs` (`isLoopbackUrl`), `scripts/lib/qa_rules.py`, `bin/brand-creator`, `tests/test_static.py`,
`tests/test_page_check.py` (new), `scripts/CONTRACT.md`, `skills/brand-creator/references/phases/09-qa.md`, `CHANGELOG.md`.

Shared helpers other groups import (never duplicated): `scripts/pagelib/pagecheck.py` imports only the standard library and
`scripts/lib` (`_common`, `_color`, `qa_rules`), so `board_lint.py`, `check.py` and later `kit.py` can put `scripts/pagelib`
on `sys.path` and call `report_tool(ident)` and `is_loopback_url(url)`. `scripts/lib/_common.mjs` exports
`isLoopbackUrl(url)` (true only for `http:`/`https:` on `localhost`, `127.0.0.1` or `[::1]`); `render.mjs page-measure`
refuses any other `url` with exit 2 (defence in depth behind `page_check.py`'s own check).

Command:

```text
brand-creator page-check <page.html> [--project DIR] [--widths 360,390,...] [--schemes light,dark]
brand-creator page-check --from DIR <page.html> [--project DIR] ...
brand-creator page-check --url http://localhost:<port>/<path> [--project DIR] ...
```

- Exit 2 (nothing written): no target, two target forms, a page that does not exist, `--from` that is not a folder or holds
  more than 5000 files or 200 MB (copying skips `.git`, `node_modules` and symlinks), a `--url` whose host is not
  `localhost`, `127.0.0.1` or `[::1]` or whose scheme is not http or https, a width that is not a whole number from 200 to
  4000, a scheme other than light or dark, a bad `qa/rules.json` `page` block.
- Exit 3: `assets/tokens/tokens.json` missing ("run brand-creator tokens"), `node` missing, or `render.mjs` exiting 3
  (setup missing); the message names the fix.
- `--from`: copy the folder into a new run folder `<data>/scratch/<project>/page-check/<hash6>/<n>/` (`scratch_dir`; `n` is
  one more than the folders already there) and serve that copy. The source is only read.
- `qa/rules.json` gets a `page` section in `scripts/lib/qa_rules.py` DEFAULTS: `widths` `[360, 390, 768, 1024, 1440,
  1920]`, `display_min_px` 20, `clear_space` 0.25, `rules` `[]` (validated as a list here; its entries in G1-18). The
  docstring example shows it. Unknown keys exit 2 as for every section.
- Request JSON written to `<scratch>/page-check/<slug>-<hash6>/request.json`: `{schema: 1, root, page, url, widths,
  schemes, selectors: [], dsf: 1}`; then `node <root>/scripts/render.mjs page-measure --request <req> --out
  <measures.json> --project <project>`.
- `render.mjs page-measure` (new subcommand, also in its USAGE text): serves `root` with the existing local server
  (`root` must be the project or a folder inside `<data>/scratch/`), or opens `url`; one browser context per width and
  scheme (viewport height 800 at 360, 844 at 390, 1024 at 768, 768 at 1024, 900 at 1440, 1080 at 1920, else 900;
  `colorScheme` as the scheme); requests to other origins are recorded and aborted; it waits for load, `fonts.ready` and
  lazy images as `shot` does, then calls `collect(page, request)` from `scripts/pagelib/page_measure.mjs` and writes
  `{schema: 1, chromium, target, views: [{width, scheme, viewport, lang, height, errors, non_local, failed_local,
  resources: {<url>: {sha256, content_type}}, served: [<abs path>], ...collectors}]}` to `--out` (outside the project).
  Image and SVG response bodies are hashed (`response.body()`), so a mark can be compared byte for byte later.
- Report: tool `page-check/<slug>-<hash6>` (`pagecheck.report_tool(ident)`: slug from the page's file stem, or the URL
  path's last segment, else `page`; hash = first six hex of sha256 of the ident: the project-relative posix path, or
  `from:<real DIR>/<page>`, or `url:<URL>`). Inputs: `assets/tokens/tokens.json`, `qa/rules.json`, `FACTS.md`,
  `BRAND-STATE.md` (when they exist), the page (project target) and every served project file. `extra`: `target` (`kind`
  project, from or url, with `page`, `from`, `url`), `widths`, `schemes`, `measures`.
- Rows in this task: `page:target` (info), `page:load:<width>-<scheme>`: fail on page or console errors, failed local
  requests or (project and `--from`) requests to other origins; with `--url`, other-origin requests are a warning
  ("aborted: page-check runs offline"). A view that cannot be rendered fails its row. No view measured: `skipped` (exit
  3).
- `tests/test_static.py::test_every_uv_script_has_a_committed_lock_and_pep723_metadata`: add `"pagelib"` to the set of
  folders skipped (helper modules, not scripts).
- `bin/brand-creator`: dispatch `page-check) py page_check.py "$@" ;;` and a usage line under "checks and renders".

Tests (`tests/test_page_check.py`; mark only the Chromium tests `requires_setup` and `requires_node`):

- `test_page_check_refuses_a_remote_url_two_targets_and_a_missing_page` (f): exit 2 each, no report written.
- `test_page_check_needs_built_tokens` (f): exit 3.
- `test_a_clean_page_passes_and_its_report_is_named_after_the_page` (f): the `acme` fixture plus `pages/index.html` (links
  `../assets/tokens/tokens.css`, uses only `var(--color-*)`, no digits; never `site/`, which group 2 reserves for approved
  pages), `--widths 390,1440`; exit 0, report `assets/_checks/page-check/index-<hash6>.json` (the name
  `pagecheck.report_tool("pages/index.html")` gives), its top-level `target` is `{"kind": "project", "page":
  "pages/index.html", ...}`, rows `page:load:390-light` ... pass.
- `test_a_page_that_asks_the_network_fails_its_load_row` (m).
- `test_from_checks_a_copy_and_never_writes_where_the_site_is` (f): `snapshot` (or a sha256 walk) of the source folder is
  unchanged; the project gains only the report.

Docs: CONTRACT: new section "Page check" (after "QA gates and mark tooling"; add it to Contents), the tool name in
"Reports", `qa/rules.json` `page` keys; 09-qa: a new table row whose Command cell is `page-check <page>` in backticks and
whose Report cell is `page-check/<slug>-<hash6>`, citing the tests (the subcommand test needs the row); CHANGELOG Added
(one line; G1-20 writes the user docs) plus, once for the whole web work, the note "A pack recorded with `staleness
--write` reads as stale after this update (the scripts it hashes changed); rebuild it." (`scripts/lib/qa_rules.py` is in
`lib/stale.py` `EMITTER_GLOBS`). Also a test that `pagecheck.is_loopback_url` accepts `http://localhost:8000/x`,
`http://127.0.0.1/` and `http://[::1]:3000/` and refuses `https://example.com/`, `file:///x` and `http://localhost.evil.test/`
(f, no browser).

Verify: `uv lock --script scripts/page_check.py`; `pytest -k "page_check or static or skills"`.

### G1-14 page-check: colours per theme and declared pairs

Roadmap steps: 7. Depends on: G1-13.

Files: `scripts/pagelib/page_measure.mjs`, `scripts/pagelib/pagecheck.py`, `tests/test_page_check.py`, `scripts/CONTRACT.md`,
`skills/brand-creator/references/phases/09-qa.md`.

- Collect per view (visible elements only): `colours` (`{sel, prop, hex, alpha}` for `color` of elements with own text,
  `background-color` with alpha above 0, each border colour with a width above 0 and a style other than none,
  `outline-color` when the outline style is neither none nor auto, `text-decoration-color` when a line is drawn, and SVG
  `fill` and `stroke` of inline SVG shapes); `texts` (`{sel, text (200 characters), fg, ground, ground_kind ("colour" or
  "image"), font_size_px, font_weight, font_family, rect, sample_label, lang}`; the ground is the first ancestor-or-self
  with a background colour of alpha above 0; a background image on the way makes it "image").
- `page:colours:<scheme>` fail: an opaque colour that is not the hex of a semantic role of that scheme in `tokens.json`, or
  a see-through colour that is not a see-through role; names up to six (selector, property, colour, nearest role and its
  OKLab distance, the width). Pass: the count.
- `page:pairs:<scheme>`: a text whose fg and ground map to a declared `pairs` entry passes; an undeclared pair under 4.5:1
  (3:1 for 24 px and up, or 18.66 px and up at weight 700 or more) fails; an undeclared pair that passes warns ("declare it
  in pairs"); text over an image warns "NOT verified: text over an image".

Tests: `test_a_colour_that_is_not_a_token_fails_and_is_named` (m); `test_a_light_ground_left_in_the_dark_theme_fails_the_dark_row`
(m); `test_an_undeclared_pair_under_the_wcag_floor_fails_and_one_above_it_warns` (m); the clean page still passes.

Docs: CONTRACT rows; 09-qa row citations.

Verify: `pytest tests/test_page_check.py`.

### G1-15 page-check: fonts loaded and the display face's minimum size

Roadmap steps: 7. Depends on: G1-14.

Files: as G1-14.

- Collect `font_faces` (`document.fonts`: family, weight, style, status) and, for one element per distinct computed first
  family and weight, the platform font Chromium used (CDP `CSS.getPlatformFontsForNode`, as `render.mjs fonts` does).
- `page:fonts` fail: a text whose first family is not named in any `font.*` token stack (quotes stripped, case-insensitive;
  generic and system families allowed only when a token's stack names them); a named non-system family that is not loaded,
  or for which Chromium used another font. A CDP error is a warning "NOT verified".
- `page:display-size`: with a `font.display` token, any text set in its first family under `page.display_min_px` (proposal
  printed as a proposal until `qa/rules.json` sets it) fails; without `font.display`: info.

Tests: `test_a_family_the_tokens_do_not_name_fails` (m); `test_a_token_family_whose_file_does_not_load_fails` (m);
`test_display_text_under_the_minimum_fails_and_a_brand_with_no_display_face_gets_an_info_row` (m).

Docs: CONTRACT rows; 09-qa citations.

Verify: `pytest tests/test_page_check.py`.

### G1-16 page-check: the mark (same file, right band, clear space)

Roadmap steps: 7. Depends on: G1-14.

Files: as G1-14.

- Collect `marks`: elements with `data-brand-mark`, and `img`, `picture source`, `image` and CSS `background-image` whose
  URL's file name holds `logo`, `mark`, `favicon`, `wordmark` or `lockup` or whose bytes equal a project logo file; each
  with `{sel, kind, url, sha256 (from resources), svg_markup (inline svg with data-brand-mark), declared, rect, visible,
  nearest_px, nearest_sel}` where `nearest_px` is the gap to the nearest other visible text, image or svg box that is
  neither an ancestor nor a descendant.
- `page:mark-file` fail: a mark whose bytes equal no file of `assets/logo/` and no drawing named by `qa/rules.json` bands or
  marks; an inline SVG is compared after canonicalisation (attributes sorted, white space collapsed) and the detail says
  so.
- `page:mark-band` fail: the file is not the drawing `qa_rules.pick_band` names for the mark's rendered height (its
  `-dark.svg` twin counts in the dark scheme).
- `page:mark-clear-space` fail: `nearest_px` under `page.clear_space` x the mark's rendered height (proposal until set).

Tests: `test_a_mark_that_is_not_a_master_byte_for_byte_fails` (m: one byte changed in a copy the page uses);
`test_the_mark_at_24_px_must_be_the_small_band_drawing` (f, Acme bands: 32 px and below is `grid-mark.svg`);
`test_text_inside_the_clear_space_fails` (m); `test_an_inline_svg_mark_is_compared_after_canonicalisation` (f).

Docs: CONTRACT rows and the `data-brand-mark` convention; 09-qa citations.

Verify: `pytest tests/test_page_check.py`.

### G1-17 page-check: motion tokens, claims and the before-publishing list

Roadmap steps: 7. Depends on: G1-14.

Files: as G1-14, plus `scripts/pagelib/pagecheck.py` word lists.

- Collect `motion_decls` (computed `transition-duration`, `transition-timing-function`, `animation-duration`,
  `animation-timing-function` of every element with a non-zero duration, and `document.getAnimations()` timing) and
  `samples` (`[data-sample]` elements: label, text excerpt, selector).
- `page:motion` fail: a non-zero duration that is not a duration token (`tokens.json` `motion.durations_ms`), or an easing
  that is not a curve token (keywords such as `ease` count only when a token equals their curve); a page that moves while
  the brand has no motion tokens fails and says so.
- `page:claims` fail: outside an element with a non-empty `data-sample`, a number (a digit run of two or more, or any digit
  run next to `%`, a currency sign or a unit such as zł, PLN, €, $, k, mln, tys.) that no FACTS.md value contains, or a
  status word no FACTS.md value contains. Status words: English from `bookdata.LINT_DEFAULTS["status_words"]`; Polish in
  `pagecheck.py` (for example "wkrótce", "dostępne", "dostępny", "w przygotowaniu", "w budowie", "premiera",
  "przedsprzedaż", "nowość"). A page in another language: the row also warns "status words NOT verified for <lang>".
- `data-sample=""` (empty label) fails `page:claims` ("label the sample"). `page:samples` info: each labelled sample
  (label, excerpt, selector, first view); the same list goes to the report's `extra.samples`.

Tests: `test_a_duration_that_is_not_a_token_fails_and_a_token_duration_passes` (m);
`test_an_unbacked_number_fails_and_the_same_number_in_a_labelled_sample_is_listed_before_publishing` (m);
`test_an_empty_sample_label_fails` (m); `test_a_number_backed_by_facts_passes` (f);
`test_status_words_in_another_language_are_not_verified` (f).

Docs: CONTRACT rows and the `data-sample` convention; 09-qa citations.

Verify: `pytest tests/test_page_check.py`.

### G1-18 page-check: typed brand rules from `qa/rules.json` `page.rules`

Roadmap steps: 7. Depends on: G1-16, G1-17.

Files: `scripts/lib/qa_rules.py`, `scripts/pagelib/pagecheck.py`, `scripts/pagelib/page_measure.mjs`,
`tests/test_page_check.py`, `scripts/CONTRACT.md`, `skills/brand-creator/references/phases/09-qa.md`,
`skills/brand-creator/references/phases/07-tokens.md`, `CHANGELOG.md`.

- `qa_rules.py` validates each `page.rules` entry (exit 2 otherwise): `id` (lower-case slug, unique), `kind` in
  `max-marks-per-view`, `max-words-per-control`, `words-under-accent`, `tell`, `g4` (non-empty string), and the kind's keys:
  `max` (whole number, 0 or more) for the first two; `selector` (optional for controls, required for accents); `min` and/or
  `max` for accents; `tell` (string) for `tell`. Unknown keys exit 2.
- Measure: `max-marks-per-view`: windows one viewport high stepped by half a viewport down the page; the most identified
  marks in one window. `max-words-per-control`: `button`, `[role=button]`, `input[type=submit|button|reset]` and the rule's
  `selector`; words are Unicode word runs of the visible text (or the accessible name). `words-under-accent`: for each
  element the `selector` matches, the words of its parent's visible text minus its own. Selectors reach the browser in the
  request's `selectors`.
- Row `page:rule:<id>`: fail when broken and the `g4` text matches (white space collapsed, case-insensitive substring) a
  recorded "(rule)" line of BRAND-STATE "Rules (G4)" with G4 recorded (reuse `adapt.view(project)["rules"]`); warn when
  broken and not yet tied ("not a recorded G4 rule line yet"); pass otherwise. A `tell` rule naming an unknown tell exits
  2 (checked after G1-19 exists; until then `tell` rules are info "available once the tells exist").

Tests: `test_two_marks_in_one_screen_fail_once_the_g4_line_is_recorded` (m); `test_an_untied_rule_only_warns` (f);
`test_a_four_word_button_fails_a_three_word_rule` (m); `test_words_under_an_accent_are_counted` (f);
`test_an_unknown_rule_kind_or_key_is_a_usage_error` (f).

Docs: CONTRACT `qa/rules.json` (the `page` block) and the Page check rows; 07-tokens.md Gate: example G4 lines with their
typed rules ("(rule) one mark per screen", "(rule) a button says at most three words"); 09-qa citations; CHANGELOG
Added (brand rules for pages, tied to the system rules).

Verify: `pytest tests/test_page_check.py -k rule`; `pytest -k "qa_infra or skills"`.

### G1-19 page-check: the reflex tier (generic tells, warnings)

Roadmap steps: 8. Depends on: G1-18.

Files: `skills/brand-creator/references/page-tells.json` (new), `skills/brand-creator/references/_index.md`,
`skills/brand-creator/SKILL.md` (one bullet in the References list, below `## Round mechanics`, never the top:
`- [page-tells.json](references/page-tells.json): the generic page tells the page check warns about (English and Polish).`;
`test_every_link_resolves_and_every_reference_is_linked_from_skill_md` fails on any file of `references/` SKILL.md does not
link), `scripts/pagelib/page_measure.mjs`, `scripts/pagelib/pagecheck.py`, `tests/test_page_check.py`, `tests/test_skills.py`,
`scripts/CONTRACT.md`, `skills/brand-creator/references/phases/09-qa.md`, `CHANGELOG.md`.

- `page-tells.json`: `{"$description", "version": 1, "languages": ["en", "pl"], "tells": [{id, name, what, why, measure,
  threshold?, words?: {en: [...], pl: [...]}}], "notes": [{id: "stock-anatomy", what}]}`, written fresh. Tells and how they
  are found (JavaScript collects candidates; Python applies the thresholds):
  - `eyebrow`: a text element of at most 4 words, uppercase or letter-spacing of 0.05 em or more, smaller than the heading,
    directly before an `h1`-`h3`.
  - `arrow-glued`: a link or button whose label starts or ends with an arrow glyph (→, ←, ↗, ›, », ⟶, ➔ and similar) with
    no gap or one space.
  - `middot-run`: an element whose own text holds two or more middle dots or bullets used as separators.
  - `stock-second-action`: the hero's second action has a stock label (English and Polish lists, for example "Learn more",
    "How it works", "Dowiedz się więcej", "Jak to działa").
  - `hero-text-budget`: the hero (the first section, header or block holding the `h1`) shows more than 45 words in the first
    viewport.
  - `styled-div-mock`: a box of 240 x 160 css px or more holding 8 or more descendants with a background or border, no
    `img`, `svg`, `canvas` or `video`, and no `data-sample` label on it or an ancestor.
  - `three-equal-tiles`: at 1024 px and wider, a row of exactly three siblings of equal width (2 px) and similar height,
    each with a heading.
  - Note `stock-anatomy`: hero, three tiles, an FAQ (`details`/`summary` or a heading "FAQ", "Pytania"), a closing
    call-to-action band, in that order: an info row only.
- Rows: `tell:<id>` warn listing up to six hits with selector and width (pass "none found"); for a page language other
  than en or pl, `tell:stock-second-action` warns "NOT verified: no word list for <lang>"; `note:stock-anatomy` info. A
  `page.rules` entry of kind `tell` turns its tell into `page:rule:<id>` as in G1-18 (enable the unknown-tell exit 2 now).
- The plugin's own social post: a test renders `templates/social/post-1x1.html` with its `{{...}}` placeholders filled
  (token colours, a sample headline) into a project page and asserts `tell:eyebrow` names `.kicker`. The template is not
  changed (owner default).

Tests: `test_an_eyebrow_over_a_heading_warns_and_an_adopted_eyebrow_rule_fails` (m); `test_each_tell_is_found_on_a_page_built_to_show_it`
(f, one fixture page per tell or one page with all seven, at 1440 and 390); `test_a_page_in_german_says_its_stock_labels_are_not_verified`
(f); `test_the_social_post_kicker_is_reported_as_an_eyebrow` (f); `tests/test_skills.py`: every tell has the keys above and
both word lists where `words` is present.

Docs: `references/_index.md` row; CONTRACT tells and rows; 09-qa: page-check row (warnings) and Warnings section;
CHANGELOG Added (the page check warns about generic patterns, English and Polish).

Verify: `pytest tests/test_page_check.py`; `pytest -k skills`.

### G1-20 page-check: user docs and entry points

Roadmap steps: 7, 8. Depends on: G1-19.

Files: `docs/manual/use/check-a-page.md` (new how-to), `docs/manual/README.md`, `docs/manual/use/check-your-project.md`,
`docs/manual/reference/commands.md`, `docs/manual/reference/troubleshooting.md`, `skills/check/SKILL.md`, `AGENTS.md`,
`skills/brand-creator/SKILL.md` (one row in `## Commands by phase`, below `## Round mechanics`),
`skills/brand-creator/references/phases/11-adoption.md`, `CHANGELOG.md`.

- How-to "Check a page against your brand" (task-first, §4 voice, no internal codes): what it checks (colours, contrast,
  type, the logo, motion, claims, your page rules; generic patterns as warnings), how to ask
  (`/brand-creator:check --page pages/index.html`, a built folder, or a page your computer serves), what you see, the
  before-publishing list, adopting a warning as a brand rule, and "If something goes wrong".
- `skills/check/SKILL.md`: `argument-hint: "[--page <file-or-folder-page-or-localhost-url>] [<old value or phrase> ...]"`
  and a step: with `--page`, run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" page-check ...` (with `--from` or `--url` as
  fits) and report rows as for `check`. Do not change the `description` (owner default: descriptions change only in
  group 2; G2-16 updates it).
- `skills/brand-creator/SKILL.md` `## Commands by phase` (below `## Round mechanics`, outside the top budget): a row "a
  page built anywhere, against the brand | `page-check <page>`, `page-check --from <dir> <page>`, `page-check --url
  http://localhost:<port>/<path>`". Group 2's site row does not repeat it.
- `commands.md` check section: the `--page` argument row. `check-your-project.md`: one short section linking the new page.
  `troubleshooting.md`: rows for a non-token colour, a remote URL refused, "NOT verified" fonts.
- `AGENTS.md` pointer row: "The page check (brand rules, generic tells)" → `scripts/page_check.py`, `scripts/pagelib/`,
  `skills/brand-creator/references/page-tells.json`. `11-adoption.md`: one line: when a product's pages are built, run the
  page check on them.
- `docs/manual/README.md`: the new page under "Do something".

Tests: the docs checks; `pytest -k skills` (frontmatter limits).

Verify: the docs checks; `pytest -k skills`; `claude plugin validate plugins/brand-creator --strict`.

### G1-21 shot `--out` into the project's `specimens/` folder

Roadmap steps: 20. Depends on: G1-13.

Files: `scripts/render.mjs`, `scripts/lib/_common.mjs` (if a helper is added), `bin/brand-creator`,
`tests/node/render.test.mjs`, `scripts/CONTRACT.md`, `CHANGELOG.md`.

- `shot --out DIR`: allowed outside the project (as now) or inside `<project>/specimens/` (any depth). Anywhere else inside
  the project: exit 2 "--out must be outside the project, or under specimens/". The report's `out_dir` records it.
- CONTRACT Project discovery (the `--out` sentence) and Project file conventions (`specimens/<name>/   page shots kept as
  specimens (shot --out specimens/<name>)`); bin usage line for `shot` mentions it.

Tests: `shot: --out may point into the project's specimens folder and nowhere else in it` (f, node; requires setup): exit 0
and slices under `specimens/hero/` (never a folder named `home`: the personal-path test rejects a `home` segment between
slashes in a shipped file); `--out <project>/assets/x` exits 2.

Docs: CHANGELOG Added. No 09-qa change (not a gate).

Verify: `node --test tests/node/render.test.mjs`.

### G1-22 Colour divergence between directions (warning)

Roadmap steps: 20. Depends on: G1-05.

Files: `scripts/boardlib/divergence.py` (new, stdlib: sRGB to OKLab), `scripts/board_lint.py`, `tests/test_board_lint.py`,
`scripts/CONTRACT.md`, `skills/brand-creator/references/phases/09-qa.md`, `CHANGELOG.md`.

- On pick boards read each direction's `style` attribute for `--d-paper`, `--d-ink` and `--d-accent` (`#rgb` or
  `#rrggbb`). Row `directions:divergence`: warn naming each pair of directions whose paper and ink are both within 0.04 and
  accents within 0.06 OKLab distance ("they look alike in colour"); pass with the smallest distances; info "not measured"
  when fewer than two directions carry all three. Thresholds are a practice proposal, said in the row.

Tests: `test_two_directions_with_the_same_colours_warn_as_alike` (m); the Acme board passes the row (extend the fixture
pass test).

Docs: CONTRACT board-lint rows; 09-qa Warnings and board-lint citations; CHANGELOG Added.

Verify: `pytest -k board_lint`.

### G1-23 Motion variants' timelines compared (warning)

Roadmap steps: 20. Depends on: none.

Files: `scripts/boardlib/motionboard.py`, `tests/test_motion_board.py`, `scripts/CONTRACT.md`,
`skills/brand-creator/references/phases/09-qa.md`, `CHANGELOG.md`.

- On a motion board, after the variant rows: from each variant's current motion report, the `sampling` row's `length_ms` and
  `animations`. Row `motion:timelines`: warn naming each pair of variants whose lengths differ by 5 % or less (or 20 ms) and
  whose animation counts are equal ("three variants should try three moves"); pass otherwise; info when a report is
  missing (the `motion:proof` row already says so).

Tests: `test_two_variants_with_one_timeline_warn` (m: `mutate_json` sets variant B's `length_ms` and `animations` to A's
in its report); the existing passing motion-board test sees `motion:timelines` pass.

Docs: CONTRACT motion board rows table; 09-qa motion-board row (a warning) and Warnings; CHANGELOG Added.

Verify: `pytest tests/test_motion_board.py`.

### G1-24 Component motion proofs (hover, press, focus)

Roadmap steps: 20. Depends on: G1-21.

Files: `scripts/render.mjs`, `tests/node/motion.test.mjs`, `scripts/CONTRACT.md`,
`skills/brand-creator/references/phases/09-qa.md`, `skills/brand-creator/references/phases/07-tokens.md`, `CHANGELOG.md`.

- Motion proof case `type: "component"`: keys `page`, `selector`, `rule` (non-empty: the G4 line it proves), optional
  `states` (subset of `hover`, `active`, `focus-visible`; default `["hover", "active"]`), `widths` (default `[390, 1440]`),
  `settle_ms`. A bad value exits 2 before a browser starts.
- For each width and state: record the element's box and the boxes of its following siblings; enter the state (hover:
  `page.hover`; active: hover then `mouse.down`; focus-visible: keyboard focus); step the element's and its descendants'
  transitions and animations through their sample points as `pageCase` does; then leave the state and finish.
- Rows: `<case>:shift:<state>:<width>` fail when the element or a following sibling moves or resizes by more than 0.5 css
  px at any point, or a layout property animates; `<case>:tokens:<state>` fail when a duration or easing is not a motion
  token of `assets/tokens/tokens.json`; `<case>:reduced:<state>` fail when an animation runs on the state change under
  reduced motion; `<case>:rest:<state>` fail when the box after leaving the state differs from the box before.

Tests (node): `a button whose padding grows on hover fails the shift row` (f); `a press that scales with a token duration
passes` (f); `a hover transition of 200 ms that is not a token fails the tokens row` (f); `a component that still animates
under reduced motion fails` (f); `a component case without its rule is a usage error` (f).

Docs: CONTRACT Motion proof (the `component` case and its rows); 09-qa `shot --motion` row; 07-tokens.md Enforcement;
CHANGELOG Added.

Verify: `node --test tests/node/motion.test.mjs`.

### G1-25 Calibration, owner report and the final full run

Roadmap steps: 8 (calibration), all. Depends on: G1-01 to G1-24.

Files: `CHANGELOG.md` (lead paragraph only); no other file is written.

1. Run `page-check` (both tiers, default widths) on the Acme page fixture and on the filled social post page.
2. Only if the owner says yes at this point: read-only calibration on the pilot brand's built site pages (its latest
   site round; the lead names the folder in the hand-off, never in a file). Copy the pilot brand's project into a scratch
   folder outside it (`cp -R`, read only on the source), list the built HTML with `ls`, and run `page-check --from <the
   built folder> <page> --project <the scratch copy>`, so the brand-rule rows measure against the pilot brand's own tokens
   and every report lands in the scratch copy. Nothing is written in the pilot brand's project. Without the yes, skip and
   say so.
3. Report to the owner in the hand-off message (not a file): the hits per tell and per brand-rule row, each with "adopt as a
   brand rule (`page.rules` + a G4 line) or drop"; the social kicker finding; the warnings that become failures next
   release.
4. CHANGELOG: a lead paragraph under `## [Unreleased]` saying what may now warn on an existing project (reflex lines,
   grounds, starter values) and that these warnings become failures in the next release.
5. Full runs: pytest (with `BRAND_CREATOR_DATA`), node tests, `tests/run-all.sh --smoke` on macOS, the docs checks and
   `claude plugin validate plugins/brand-creator --strict`. Compare failures with the baseline; any new failure is fixed in
   the task that caused it.

Acceptance: every command exits 0 (or only the baseline's pre-existing failure remains, explained); the owner has the
calibration list.

## 6. Risks

- New warning rows may show up in places that print report rows (the book, smoke assertions on exact output). Run
  `test_book*.py` and the smokes after G1-04, G1-05, G1-11 and G1-08.
- The pinned `@google/design.md` may reject a typography entry without `fontFamily`; the lint test in G1-09 decides. If it
  fails, keep sizes and weights in prose only and say so in the CHANGELOG.
- Style Dictionary 5.7.0 handling of `number` groups with negative values and of a root `$extensions` in primitives is
  assumed; G1-07 and G1-08 test both builds.
- The page check's colour rule is strict: unstyled links and form controls (browser defaults) fail. That is intended; the
  how-to says so.
- Twelve views per page and a CDP font probe make page-check slow; tests pass `--widths 390,1440`.
- The grounding rule is a floor: long function words in Polish or German can match by chance. ADR-0006 says so; the judge
  list is the real guard.
- ADR numbers are fixed across the groups (section 0a): 0006 to 0008 here, 0009 and 0010 in group 2, 0011 and 0012 in
  group 3.
- The warn-then-fail switch is a follow-up for the next release and is not part of this group.
- Reading the pilot brand's pages touches a private client project; it is optional, from a scratch copy, and needs the
  owner's yes at run time.
- This plan file lives in `dev/specs/` and is checked by markdownlint and lychee in the docs job; keep it lint-clean.
