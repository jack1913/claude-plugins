# brand-creator 0.10.0 (group 7): masters and a smaller freeze, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a masters round with its checks and approval, and a freeze that keeps only what its boards show, plus slimming of
existing freezes through cleanup.

**Architecture:** one shared closure module (`scripts/lib/closure.py`, static references) plus a browser pass in
`render.mjs` (`page-requests`) feed both `freeze` and `cleanup --history`. Masters get a manifest reader
(`scripts/boardlib/mastersdata.py`), a measuring command in `render.mjs` (`masters-measure`), and one Python entry point
(`scripts/masters.py`: `check`, `approve`, `embed-fonts`); `pdf normalise` wraps the existing `determinism.normalise_pdf`.

**Tech Stack:** Python 3.10+ PEP 723 scripts with committed `uv lock --script` locks; Node 22+ `render.mjs` with
playwright-core from the data directory; pytest (xdist); pptxgenjs (new, MIT, installed by `setup`).

**Spec:** `plugins/brand-creator/dev/specs/2026-11-07-g7-masters-and-freeze-design.md`

All paths below are relative to `plugins/brand-creator/`. Test command: `BRAND_CREATOR_DATA=<data dir> uv run --no-project
--with-requirements tests/requirements.txt python -m pytest tests/<file> -q -p no:cacheprovider -n auto`.

## Global Constraints

- `history/` is written only by `freeze`, and changed only by `cleanup --history` after the owner's recorded yes; the guard
  rules do not loosen.
- Every PDF the plugin writes goes through `normalise_pdf()`; same input, same bytes.
- No Office app, LibreOffice or Keynote is driven by the plugin. PPTX rendering is a manual check, PowerPoint preferred,
  recorded with G4m.
- No paid API and no agent fleet in any test; tests that need Chromium are marked `requires_setup` and `requires_node`.
- A missing browser or data directory is reported (exit 3 or NOT VERIFIED), never skipped silently; `freeze` without a
  browser stops and names `--static`.
- New Python scripts carry PEP 723 metadata and a committed lock (`uv lock --script scripts/<file>.py`).
- Print (business cards, letterhead) is out of scope (0.20.0).
- Docs follow `docs/internals/docs-standard.md` and the user-facing tone (friendly, short, task-first).

## Review Focus

1. A board whose pictures are added by a script (paths built in JS): the frozen copy must still show them. Test in Task 3.
2. A round with a file name holding spaces or Polish letters (`ż`, NFD on disk): closure, freeze and cleanup must treat it
   as the same file. Test in Task 1.
3. A master whose HTML loads a font or picture from outside its folder (`../fonts/`): `masters approve` must copy it or refuse
   by name, never leave a broken master. Test in Task 8.
4. `cleanup --history` on a freeze whose files were edited by hand: refused with the files named. Test in Task 4.
5. A text drawn over other text on purpose (the stamp) with no `data-masters-overlay`: a warning naming both elements, not a
   crash and not a silent pass. Test in Task 6.

---

### Task 1: the static closure of a round

**Files:**

- Create: `scripts/lib/closure.py`
- Test: `tests/test_closure.py`

**Interfaces:**

- Produces: `START_NAMES = ("board.html", "index.html", "preview.html", "review.html")`;
  `starting_pages(root: Path) -> list[Path]` (those names anywhere under root, plus `*.md` directly in root, sorted);
  `static_closure(root: Path, starts: list[Path]) -> tuple[set[Path], list[str]]` (files reached through `src`, `href`,
  `poster`, `data-src`, `xlink:href`, `srcset`, CSS `url()`, JS `import` in HTML/CSS/SVG/JS files, followed recursively,
  only inside root; second item: references that point at no file, as `"<page>: <ref>"`);
  `builders(root: Path) -> set[Path]` (`*.py`, `*.mjs`, `*.js`, `*.sh`, never under `__pycache__` or `node_modules`).
- URLs with a scheme (`data:`, `http(s):`, `mailto:`, `//`) are ignored; `%xx` is unquoted; `?query` and `#frag` dropped;
  paths compared after `unicodedata.normalize("NFC")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_closure_follows_html_css_and_svg_references_and_stays_inside_the_round(tmp_path): ...
    # board.html -> a.png, style.css -> url(bg.png), pic.svg -> href="inner.png"; ../outside.png not in the set
def test_srcset_and_a_js_import_are_followed(tmp_path): ...
def test_a_reference_to_no_file_is_listed_not_dropped(tmp_path): ...
    # assert missing == ["board.html: gone.png"]
def test_a_polish_name_decomposed_on_disk_is_the_same_file(tmp_path): ...
    # file written as NFD "ża.png", referenced NFC in board.html -> in the closure
def test_builders_skip_pycache_and_node_modules(tmp_path): ...
```

- [ ] **Step 2:** run, expect ImportError. **Step 3:** implement with the stdlib `html.parser` (the regex from the
  design's measurement is the fallback for CSS and JS text). **Step 4:** run, expect pass.
- [ ] **Step 5: Commit** `brand-creator: the static closure of a round (lib/closure.py)`.

### Task 2: the browser pass (`render.mjs page-requests`)

**Files:**

- Modify: `scripts/render.mjs` (new `cmdPageRequests`, case `page-requests`, a line in `USAGE` and `helpOf`)
- Modify: `scripts/lib/closure.py` (add `browser_closure`)
- Test: `tests/test_closure.py`, `tests/node/page-requests.test.mjs`

**Interfaces:**

- `node render.mjs page-requests --root DIR --page REL [--page REL ...] --out FILE.json`: serves root on 127.0.0.1 with
  the existing `startServer`, loads each page with `CAPTURE_FRAMES_SETTLE_MS` settle and `--reveal`'s walk, aborts every
  request to another origin, writes `{"pages": {rel: {"requested": [rel...], "missing": [rel...]}}}`.
- `browser_closure(project: Path, root: Path, starts: list[Path]) -> tuple[set[Path], list[str]]` raises
  `CliError(EXIT_CANNOT, ...)` when node, the data directory or Chromium is missing.

- [ ] **Step 1:** tests: `test_a_picture_a_script_adds_is_in_the_browser_closure` (board.html adds `<img src="shots/"+n+".png">`
  in a script; `static_closure` misses it, `browser_closure` has it; marks `requires_setup`, `requires_node`);
  `test_without_a_data_directory_the_browser_pass_says_it_cannot_run` (exit 3 text names `brand-creator setup`).
- [ ] **Steps 2-4:** fail, implement, pass. **Step 5: Commit** `brand-creator: render.mjs page-requests`.

### Task 3: `freeze` keeps what the boards show

**Files:**

- Modify: `scripts/freeze.py`, `scripts/CONTRACT.md` (freeze section), `docs/manual/reference/commands.md`
- Test: `tests/test_freeze.py` (new; move the freeze tests from `tests/test_project.py` that cover copying here only if
  they need the new modes)

**Interfaces:**

- Consumes: Task 1 and Task 2.
- CLI: `brand-creator freeze <round> --name N [--date D] [--whole | --static]`.
- Kept set = `static_closure ∪ browser_closure ∪ builders ∪ starting_pages`; with `--static`, no browser pass; with
  `--whole`, today's copy.
- After copying to `.tmp-freeze-<pid>`, the browser pass runs again on the copy (not with `--static` or `--whole`); any
  missing request fails the freeze before the rename, naming the page and the file.
- FROZEN.md gains `mode: closure|static|whole` and `left out: <n> files, <MB> (top folders: <name> <MB>, ...)`.

- [ ] **Step 1: tests**

```python
def test_freeze_keeps_the_boards_what_they_show_and_the_builders_and_leaves_the_rest(tmp_path): ...
    # round with board.html -> shots/a.png, _lead/shots/big.png (not referenced), build.py
    # frozen: board.html, shots/a.png, build.py; not _lead/shots/big.png; FROZEN.md says "left out: 1 files"
def test_freeze_whole_copies_everything_as_before(tmp_path): ...
def test_a_frozen_board_that_would_miss_a_picture_fails_before_anything_is_written(tmp_path, monkeypatch): ...
    # browser pass on the copy reports a missing file -> exit 1, no history/<date>-<name>, no .tmp left
def test_without_a_browser_freeze_stops_and_names_static(tmp_path): ...
def test_freeze_static_records_static_in_frozen_md(tmp_path): ...
def test_a_script_added_picture_is_frozen(tmp_path): ...   # requires_setup, requires_node (Review Focus 1)
```

- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: freeze keeps what the boards show (--whole, --static)`.

### Task 4: `cleanup --history`

**Files:**

- Modify: `scripts/cleanup.py` (a history mode beside the rounds mode), `scripts/lib/_common.py`
  (`write_history_manifest` already exists; add `drop_from_history_manifest(history: Path, rels: set[str]) -> None`)
- Modify: `docs/manual/reference/commands.md`, `scripts/CONTRACT.md`, `docs/adr/` (append an "Update 2026-11-07" to
  ADR-0013: history may be slimmed through this flow)
- Test: `tests/test_cleanup.py`

**Interfaces:**

- CLI: `brand-creator cleanup --history [--record-yes CODE --said "..." | --yes CODE]`; `--history` and `--keep` refuse
  each other (exit 2).
- Plan file `qa/<date>-cleanup-history-plan.txt`: per freeze, `stays` (its Task 1+2 closure, computed on the frozen copy;
  banner comments are ignored when parsing) and `goes` with sizes, and the code (same digest scheme as the rounds plan).
- `--yes`: `git rm` in chunks only for committed, unchanged files; rewrites `history/MANIFEST.sha256` without them; writes
  `qa/<date>-cleanup-history-removed.txt` with `head before:`, `removed from history: <freeze> ...` and a restore line
  `git -C <project> --literal-pathspecs checkout <head> -- history/<freeze>... history/MANIFEST.sha256`.
- `check_no_failed_removal` reads both record kinds.

- [ ] **Step 1: tests**

```python
def test_history_plan_lists_what_each_freeze_keeps_and_what_goes_with_sizes(tmp_path): ...
def test_history_yes_removes_only_what_the_plan_listed_and_rewrites_the_manifest(tmp_path): ...
    # afterwards `brand-creator check` history:manifest passes
def test_history_refuses_a_freeze_whose_files_do_not_match_the_manifest(tmp_path): ...   # Review Focus 4
def test_history_record_restores_the_freeze_and_the_manifest(tmp_path): ...
    # run the printed restore line; check passes; files back byte for byte
def test_history_and_keep_refuse_each_other(tmp_path): ...
```

- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: cleanup --history slims frozen rounds to what their boards show`.

### Task 5: the masters board, its manifest and G4m

**Files:**

- Create: `scripts/boardlib/mastersdata.py`, `templates/masters-board.html`
- Modify: `scripts/lib/_common.py` (`GATE_IDS` gains `"G4m"` after `"G4p"`), `scripts/state.py` (gate text),
  `scripts/boardlib/boardpage.py` (`KINDS` gains `"masters"`), `scripts/board_lint.py` (masters rows)
- Test: `tests/test_masters.py` (new)

**Interfaces:**

- `MASTERS_FILE = "masters.json"`; `KINDS = ("ad", "slide", "deck-html", "deck-pdf", "deck-pptx", "image", "font")`.
- `load_manifest(path: Path) -> Manifest`, a NamedTuple `Manifest(entries: list[Entry], copy_rules: list[str],
  builder: str | None, problems: list[str])`; `Entry(file: str, kind: str, canvas: tuple[int, int] | None,
  direction: str | None, note: str | None)`. `canvas` is required for `ad` and `slide`, refused for the others.
- board-lint rows on a `data-board="masters"` page: `masters:manifest` (present, parses, no problems), `masters:files`
  (every entry's file exists inside the round), `masters:canvas-size` (an `ad`/`slide` HTML declares
  `<meta name="masters-canvas" content="WxH">` equal to its entry), `masters:directions` (at least two directions on the
  first masters board of the project, the r19 lesson; later boards may have one).

- [ ] **Step 1: tests:** `test_a_manifest_with_a_bad_kind_or_a_missing_canvas_lists_each_problem`,
  `test_board_lint_fails_a_masters_board_whose_file_is_missing`, `test_the_first_masters_board_needs_two_directions`,
  `test_g4m_is_a_gate_state_can_record`.
- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: the masters board, masters.json and G4m`.

### Task 6: `masters check` (`render.mjs masters-measure` and `scripts/masters.py check`)

**Files:**

- Create: `scripts/masters.py` (+ `.lock`), `scripts/masterslib/pptx.py`
- Modify: `scripts/render.mjs` (`cmdMastersMeasure`), `bin/brand-creator` (`masters) py masters.py "$@" ;;`, usage lines)
- Test: `tests/test_masters.py`, fixtures under `tests/fixtures/masters/` (a two-direction round: two ads, a 3-slide deck,
  a PPTX made in the test with pptxgenjs via node)

**Interfaces:**

- `node render.mjs masters-measure --round DIR --request FILE.json --out FILE.json --png-dir DIR`: per HTML master, a
  viewport of its canvas, fonts ready, the wait = the longest `motion.reveal` duration from the built motion tokens plus
  200 ms (no tokens: 0 ms plus fonts ready), then: boxes outside the canvas; painted text boxes (range rects) that overlap
  another element painted above them, by `elementsFromPoint` sampling on a 4 px grid inside each text box, ignoring
  ancestors and elements with `data-masters-overlay`; PNG written.
- `brand-creator masters check [--round N]` writes the report `masters` with rows `masters:canvas`, `masters:covered`,
  `masters:pdf`, `masters:pptx`, `masters:pptx-render` (NOT VERIFIED until G4m's record contains the PowerPoint answer;
  the detail tells the owner to open it in PowerPoint), and `masters:overlays` (info: each `data-masters-overlay` element).
- `masterslib.pptx.inspect(path: Path) -> dict` reads `ppt/presentation.xml` (`p:sldSz`), every `ppt/slides/slideN.xml`
  shape `a:off`/`a:ext` in EMU, fonts named by `a:latin/@typeface`, `ppt/fonts/` and `p:embeddedFontLst`, picture
  relationships; returns `{"slide_size", "outside", "fonts_named", "fonts_embedded", "missing_pictures"}`.

- [ ] **Step 1: tests**

```python
def test_an_element_outside_the_canvas_fails_masters_canvas(tmp_path): ...
def test_a_number_running_into_another_fails_masters_covered_and_names_both(tmp_path): ...   # slide 9
def test_an_overlay_marked_on_purpose_passes_and_is_listed(tmp_path): ...
def test_an_unmarked_stamp_over_text_warns_naming_both_elements(tmp_path): ...   # Review Focus 5
def test_a_deck_pdf_with_the_wrong_page_count_or_unnormalised_dates_fails(tmp_path): ...
def test_pptx_shape_outside_the_slide_and_an_unembedded_font_fail(tmp_path): ...
def test_pptx_render_is_not_verified_until_the_powerpoint_answer_is_recorded(tmp_path): ...
```

- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: masters check (canvas, covered text, PDF, PPTX structure)`.

### Task 7: `pdf normalise`, `masters embed-fonts`, pptxgenjs

**Files:**

- Modify: `scripts/masters.py` (`embed-fonts`), `scripts/package.json` and `package-lock.json` (`"pptxgenjs": "<pinned
  latest 3.x>"`, via `npm install --save-exact pptxgenjs` in `scripts/`), `scripts/setup.py` (size line if it lists packages),
  `bin/brand-creator` (`pdf) py masters.py pdf "$@" ;;` routed to a `pdf normalise` subcommand)
- Test: `tests/test_masters.py`, `tests/test_setup_prereq.py`

**Interfaces:**

- `brand-creator pdf normalise <file.pdf> [--out FILE]`: in place by default; exit 1 when pdfinfo afterwards shows
  other dates (when pdfinfo is present; NOT VERIFIED otherwise).
- `brand-creator masters embed-fonts <deck.pptx> --font FILE.ttf [--font ...] [--out FILE]`: a port of Pilot's
  `rounds/r32/wzory/pptx/embed.py` (read it, never edit it; it is the proven method: PowerPoint rendered its output with the
  fonts not installed), generalised to any typeface (names from the font's `name` table); refuses a font whose `OS/2 fsType`
  forbids embedding, by name.

- [ ] **Step 1: tests:** `test_pdf_normalise_makes_two_runs_byte_identical`, `test_embed_fonts_adds_the_font_and_masters_check_sees_it_embedded`,
  `test_embed_fonts_refuses_a_restricted_licence_font`, `test_setup_installs_pptxgenjs`.
- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: pdf normalise, masters embed-fonts, pptxgenjs in setup`.

### Task 8: `masters approve`, the README, the book block and the kit

**Files:**

- Modify: `scripts/masters.py` (`approve`), `scripts/booklib/bookgen.py` and `bookdata.py` (block `masters`),
  `scripts/kit.py` (kit:behind trigger)
- Test: `tests/test_masters.py`, `tests/test_book.py`, `tests/test_kit.py`

**Interfaces:**

- `brand-creator masters approve [--round N]`: needs G4m (message names `state --record G4m "<choices>; PowerPoint: <answer>"`),
  a passing current `masters` report and a passing `board-lint` of the round; copies every entry byte for byte into
  `assets/masters/<file>` and every file the HTML masters reach (Task 1 closure, inside the round) along with them;
  refuses, by name, a master that reaches a file outside the round (Review Focus 3); moves files it replaces to
  `removed-<date>/assets-masters-r<N>/`; writes `assets/masters/masters.json` (manifest + `"round"`, `"approved"`) and
  `assets/masters/README.md` (table: path, what, size; copy rules; rebuild command; the font note: PowerPoint uses the
  embedded fonts, Keynote and Google Slides need the font files installed).
- Book block `masters`: previews by direction (`png/`), sizes, copy rules, file list; offered in Standard and Full, never
  replacing a hand-written chapter with the id `masters`.
- `kit:behind` also fires when `assets/masters/masters.json` is newer than the last build and an owner file names a master
  (default `recipes/ad.md`, `recipes/presentation.md`).

- [ ] **Step 1: tests:** `test_approve_needs_g4m_and_a_passing_masters_report`,
  `test_approve_copies_the_masters_and_what_they_reach_and_writes_the_readme`,
  `test_approve_refuses_a_master_that_reaches_outside_the_round`, `test_replaced_masters_go_to_removed`,
  `test_the_book_masters_block_shows_each_direction`, `test_kit_behind_names_the_ad_recipe_after_new_masters`.
- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: masters approve, the README, the book block, kit:behind`.

### Task 9: masters behind the site

**Files:** Modify `scripts/check.py`; Test `tests/test_masters.py`.

**Interfaces:** row `masters:behind-site`, info, only when G4p's date is later than the last G4m's (or G4p is recorded and
`assets/masters/masters.json` exists without G4m): detail "the masters were approved before the site; a masters round would
bring them to the site's language". Also listed by `status` among next steps.

- [ ] **Step 1: tests:** `test_masters_older_than_the_site_get_an_info_row`, `test_no_row_when_the_masters_are_newer`.
- [ ] **Steps 2-4.** **Step 5: Commit** `brand-creator: check says when the masters are older than the site`.

### Task 10: the round skill, docs, release

**Files:**

- Create: `skills/brand-creator/references/phases/07m-masters-round.md` (inputs: `site/`, `assets/masters/`, motion tokens,
  FACTS.md; two or three directions on the first board; `masters.json`; `masters check`; the owner opens the PPTX in
  PowerPoint; G4m; `masters approve`; then `kit build` and the book)
- Modify: `skills/round/SKILL.md` (kind `masters` in the argument hint and the kinds list), `skills/brand-creator/SKILL.md`
  (pointer), `references/phases/09-qa.md` (test rows), `07p-site-round.md` step 6 (masters as the next step),
  `docs/manual/` (a "Make your ads and decks" use page; commands reference; cleanup page: history mode), `scripts/CONTRACT.md`,
  `CHANGELOG.md` (0.10.0), version pins (`plugin.json`, `test_static.py`, `_common.py` USER_AGENT, evals `fixture.sh`,
  `regen_eval_kit`), `docs/internals/manual-checks.md` (Release run record)
- Test: `tests/test_skills.py`, `tests/test_static.py`, docs checks

- [ ] **Step 1:** skill and docs edits; `python3 .github/scripts/check-docs-standard.py` and markdownlint: 0 findings.
- [ ] **Step 2:** calibration on a scratch copy of Pilot: r32's masters as a masters round (`masters.json` written for
  it), `masters check` (expect the canvas rows to pass and the covered row to list the stamp), `cleanup --history`
  plan (expect about 17 MB to stay of 291 MB). Record the numbers in the CHANGELOG entry.
- [ ] **Step 3:** full release run: Mac `tests/run-all.sh --smoke`, Linux Docker pytest/node and smoke, record in
  manual-checks.md.
- [ ] **Step 4: Commit** `brand-creator 0.10.0: masters and a smaller freeze`. Push and tag only on the owner's go
  (tag only after push-triggered checks pass).
- [ ] **After the release (owner's yes):** `cleanup --history` on the real Pilot project.
