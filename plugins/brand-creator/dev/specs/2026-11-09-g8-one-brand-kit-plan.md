# brand-creator 0.11.0 (group 8): one brand kit, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the generated kit takes over what made Płacuję's hand-made kit work: a short entry page with a map, a review
checklist, recipes for the masters, updates that reach owner files a repository never changed, and an installer the kit
carries.

**Architecture:** the code that judges a repository's copy moves out of `kitlib.py` into a standalone, standard-library
module, `scripts/adaptlib/kitcopy.py`. `kit status` uses it, and the kit ships its bytes as `install.py`, so both give
the same answer by construction. The kit's `SKILL.md` gets its own templates (`kit-SKILL.md`, `kit-brand.md`); the applied
skill of a project without a kit keeps its template and its bytes.

**Tech Stack:** Python 3.10+ (PEP 723 scripts with committed locks; `kitcopy.py` imports the standard library only);
pytest (xdist).

**Spec:** `plugins/brand-creator/dev/specs/2026-11-09-g8-one-brand-kit-design.md`

All paths below are relative to `plugins/brand-creator/`. Test command: `BRAND_CREATOR_DATA=<data dir> uv run --no-project
--with-requirements tests/requirements.txt python -m pytest tests/<file> -q -p no:cacheprovider -n auto`. Work on a branch
`brand-creator-g8`, in the main working tree (no worktree).

## Global Constraints

- The build stays deterministic: no clock and no random numbers in anything `kit build` writes. `install.py` may read the
  date (for `removed-<date>/`), and honours `BRAND_CREATOR_TODAY` as `_common.today()` does.
- `kitcopy.py` imports only modules in `sys.stdlib_module_names`; it never imports a plugin module.
- A kit is never installed globally: the home folder and anything under `~/.claude` are refused (the owner, 2026-10-26).
- `install.py` never commits, never makes a branch and never pushes. The plugin's own scripts still write only inside the
  brand project (ADR-0014 supersedes D10 for `install.py` alone).
- An owner file a repository changed is never overwritten. An owner file is updated only when the repository's bytes are
  the hash its own `kit.json` `owned` recorded (ADR-0014 supersedes D11's "only where the repository has none").
- A project without a kit: `applied-skill` writes the same bytes as 0.10.0.
- No print recipe scaffold (print is 0.20.0). No global install. No agent fleets and no paid calls in tests. No macOS CI.
- Docs follow `docs/internals/docs-standard.md` and the user-facing tone (friendly, short, task-first).

## Review Focus

1. A copy that stops halfway, after the owner files and before `kit.json`: the next run must still update them, never take
   them for the repository's own edits. `kit.json` is the last file of every copy list. Tests in Tasks 2 and 7.
2. A repository whose `kit.json` is unreadable, of another schema or a link: every owner file that differs is the
   repository's own and is never overwritten. Test in Task 2.
3. An owner file at a path the new version generates (`brand.md`, `checklist.md`, `install.py`): in the project, the build
   stops naming it and `--replace` moves it aside; in a repository, `install.py` moves the repository's file to
   `removed-<date>/` before it copies. Tests in Tasks 4 and 7.
4. `install.py` pointed at the repository it sits in, at the brand project, or at a folder outside any git work tree:
   refused with the reason, nothing written. Test in Task 7.
5. A brand name written with Polish letters in decomposed form (NFD) in another skill's `SKILL.md`: still found by the
   second-skill warning. Test in Task 3.

---

### Task 1: the copy judge as a standalone module

**Files:**

- Create: `scripts/adaptlib/kitcopy.py`
- Modify: `scripts/adaptlib/kitlib.py` (the moved names become imports from `kitcopy`), `scripts/kit.py` (`refusal`,
  `left_over_to`, `status_lines`, the JSON shaping move to `kitcopy`)
- Test: `tests/test_kitcopy.py` (new), `tests/test_kit.py` (unchanged, must pass)

**Interfaces:**

- Produces in `kitcopy`: the constants `KIT_FILE`, `SCHEMA`, `SKILL_FILE`, `GENERATED_DIRS`, `FINDER_FILE`, `RULES_JSON`,
  `FACTS_JSON`, `ROOT_FILES`, `OWNED_FILES`, `TOP_KEYS`, `SOURCE_KEYS`, `OPTIONAL_SOURCE_KEYS`, `ALL_SOURCE_KEYS`,
  `FONT_KEYS`, `FONT_COPIED_KEYS`, `FONT_NOT_COPIED_KEYS`, `PAGE_KEYS`, `NOT_INSTALLED`, `CURRENT`, `NOT_CURRENT`,
  `WHY_MISSING`, `WHY_LINK`, `WHY_BYTES`, `STATUS_SHOWN`, and `EXIT_FAIL = 1`, `EXIT_USAGE = 2`, `EXIT_CANNOT = 3`;
  `class KitError(Exception)` with `.code: int` and `.message: str`;
  the functions `is_sha`, `problems`, `is_owner_path`, `owned_problems`, `font_problems`, `reference_page_problems`,
  `paths_in`, `owner_paths`, `owner_sorted`, `recorded_path`, `json_object` (was `kitlib._json_object`), `read_plain`
  (was `_read_plain`), `plain_file` (was `_plain_file`), `generated_files_in`, `installed_version`, `folder_state`,
  `not_current_text`, with today's signatures;
  `compare(kit: Path, installed: Path) -> dict` (today's result; raises `KitError` where it called `fail`);
  `refusal(project_root: Path, real: Path) -> str | None` (today's `kit.refusal`);
  `left_over_to(kd_rel: str) -> str`; `status_lines(res: dict, kd_rel: str) -> list[str]`;
  `result_json(res: dict) -> dict` (one repository's entry of `kit status --json`, as `kit.status` shapes it today).
- `kitlib` keeps every one of these names (imported from `kitcopy`, the old private names kept as aliases), and
  `kitlib.compare(kit, installed)` calls `kitcopy.compare` and turns a `KitError` into `fail(e.code, e.message)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_kitcopy.py`:

```python
def test_kitcopy_imports_only_the_standard_library():
    tree = ast.parse((ROOT / "scripts/adaptlib/kitcopy.py").read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}

def test_the_exit_codes_are_the_plugins():
    assert (kitcopy.EXIT_FAIL, kitcopy.EXIT_USAGE, kitcopy.EXIT_CANNOT) == (_common.EXIT_FAIL, _common.EXIT_USAGE, _common.EXIT_CANNOT)

def test_kitlib_keeps_the_names_it_had():
    for name in ("problems", "is_owner_path", "owner_sorted", "recorded_path", "compare", "not_current_text", "folder_state",
                 "ROOT_FILES", "OWNED_FILES", "CURRENT", "NOT_CURRENT", "NOT_INSTALLED", "_json_object", "_read_plain", "_plain_file"):
        assert hasattr(kitlib, name), name

def test_a_kit_that_is_not_whole_raises_kit_error_with_exit_3(tmp_path):
    # make_fake_kit(...) then corrupt one generated file -> pytest.raises(kitcopy.KitError) with e.code == 3, "not whole" in e.message
```

  Add `make_fake_kit(folder: Path, generated: dict[str, bytes], owner: dict[str, bytes], version: str = "1.1") -> None` to
  `tests/helpers.py`: writes the files and a `kit.json` that passes `kitcopy.problems` (every `TOP_KEYS` key, `owned`
  holding the five `OWNED_FILES` plus `owner`'s paths with their sha256, `sources` with every `SOURCE_KEYS` key `null`,
  `fonts` `{"copied": [], "not_copied": []}`, `reference_pages` `[]`).

- [ ] **Step 2:** run `tests/test_kitcopy.py`: FAIL with `ModuleNotFoundError: kitcopy`.
- [ ] **Step 3:** move the code. No behaviour changes; messages stay word for word.
- [ ] **Step 4:** run `tests/test_kitcopy.py`, `tests/test_kit.py`, `tests/test_adoption.py`: all pass.
- [ ] **Step 5: Commit** `brand-creator: the kit copy judge in its own standard-library module (kitcopy)`.

### Task 2: owner files a repository never changed are updated

**Files:**

- Modify: `scripts/adaptlib/kitcopy.py` (`compare`, `status_lines`, `result_json`)
- Test: `tests/test_kitcopy.py`, `tests/test_kit.py` (the hand-written copy orders at lines 2866, 2871 and 4943 change:
  `kit.json` moves to the end)

**Interfaces:**

- Consumes: Task 1's `compare`, `json_object`, `problems`, `read_plain`.
- Produces: `owner_state(repo: bytes | None, project: bytes, recorded: str | None) -> str`, one of `"copy"` (the
  repository has none), `"same"`, `"update"` (`sha256(repo) == recorded` and the bytes differ from the project's),
  `"own"` (anything else, `recorded` None included);
  `compare` result keys added: `"update_owner": [path]`, `"owner_left_over": [path]` (in the repository's `kit.json`
  `owned`, unchanged there, no longer an owner file of the project's kit), `"other_skills": []` (filled in Task 3);
  `"copy"` order: generated files except `kit.json`, then `copy_owner`, then `update_owner`, then `kit.json` last.
  The recorded hashes are the repository's `kit.json` `owned` when it is a plain file that `problems()` accepts, else
  `{}`. `state` is `NOT_CURRENT` also when `update_owner` or `owner_left_over` is not empty.
- `status_lines` adds "owner files to update (unchanged in the repository since the last copy):" and lists
  `owner_left_over` under the left-over heading; a copy-list line of an update reads `<path> (owner file, an update)`.

- [ ] **Step 1: Write the failing tests** (fake kits from Task 1's helper; the repository copy made with `shutil.copytree`):

```python
def test_owner_state_table():
    p, r = b"new", b"old"
    assert kitcopy.owner_state(None, p, None) == "copy"
    assert kitcopy.owner_state(p, p, sha(r)) == "same"
    assert kitcopy.owner_state(r, p, sha(r)) == "update"
    assert kitcopy.owner_state(b"mine", p, sha(r)) == "own"
    assert kitcopy.owner_state(r, p, None) == "own"

def test_an_owner_file_the_repository_never_changed_is_updated(tmp_path): ...
    # install v1 (recipes/ad.md = b"v1"), project moves to v2 (b"v2"): update_owner == ["recipes/ad.md"], state NOT_CURRENT
def test_an_owner_file_the_repository_changed_is_kept_and_reported(tmp_path): ...
    # repo's recipes/ad.md = b"mine": owner_differ lists it, update_owner == [], not on the copy list
def test_an_owner_file_the_repository_added_is_its_own(tmp_path): ...
def test_an_owner_file_gone_from_the_kit_and_unchanged_is_left_over(tmp_path): ...
    # owner_left_over == ["recipes/old.md"]; changed in the repo instead -> not listed
def test_an_unreadable_installed_kit_json_makes_every_differing_owner_file_the_repositorys_own(tmp_path): ...
    # repo kit.json replaced by b"{" (and, second case, by a link): update_owner == [], owner_differ lists the file
def test_kit_json_is_the_last_file_of_every_copy_list(tmp_path): ...
    # fresh install, an update with copy_owner and update_owner: res["copy"][-1] == "kit.json"
def test_a_copy_stopped_before_kit_json_is_finished_by_the_next_run(tmp_path): ...
    # copy every file of res["copy"] except kit.json, compare again: the owner file is "same", kit.json still differs, nothing is "own"
```

  In `tests/test_kit.py`: `test_kit_status_names_the_owner_files_to_update` (build, copy with the copy list, change
  `voice.md` in the project, build again: text output holds "owner files to update" and `--json` holds
  `"update_owner": ["voice.md"]`).

- [ ] **Step 2:** run: FAIL (`owner_state` missing). **Step 3:** implement. **Step 4:** run `test_kitcopy.py`,
  `test_kit.py`, `test_adoption.py`: pass.
- [ ] **Step 5: Commit** `brand-creator: kit status updates owner files a repository never changed; kit.json is copied last`.

### Task 3: a second skill for the same brand

**Files:**

- Modify: `scripts/adaptlib/kitcopy.py`
- Test: `tests/test_kitcopy.py`

**Interfaces:**

- Produces: `brand_name(kit: Path) -> str | None` (from the kit's `SKILL.md`: the first line `# <brand> brand`);
  `other_brand_skills(skills_dir: Path, kit_name: str, brand: str) -> list[str]` (sorted folder names in `skills_dir`,
  other than `kit_name`, never through a link, whose `SKILL.md` front matter `name:` or `description:` line holds the
  brand: both sides `unicodedata.normalize("NFC", ...).casefold()`); `compare` fills `"other_skills"` from
  `installed.parent`; `status_lines` adds `warning: .claude/skills/<folder>/ is another skill for <brand>: Claude may load
  either; taking it out is yours` per folder. The state and the exit code do not change.

- [ ] **Step 1: Write the failing tests:**

```python
def test_a_hand_made_skill_naming_the_brand_is_found(tmp_path): ...
    # skills/placuje/SKILL.md description "Applies the Płacuję brand" written NFD; brand "Płacuję" NFC -> ["placuje"]
def test_a_skill_that_does_not_name_the_brand_and_the_kit_itself_are_not_listed(tmp_path): ...
def test_a_link_among_the_skills_is_never_read(tmp_path): ...
def test_kit_status_warns_and_still_says_current(tmp_path): ...
```

- [ ] **Steps 2-4:** fail, implement, pass. **Step 5: Commit** `brand-creator: kit status warns about a second skill for the same brand`.

### Task 4: a short entry page and `brand.md`

**Files:**

- Create: `templates/applied-skill/kit-SKILL.md`, `templates/applied-skill/kit-brand.md`
- Modify: `scripts/adaptlib/adapt.py` (`applied_skill_md`: `{{how}}` and `{{map}}` come from the `kit` dict, `""`
  without a kit), `scripts/adaptlib/kitlib.py` (`section`, `plan`, new `how_md`, `map_md`),
  `scripts/adaptlib/kitcopy.py` (`ROOT_FILES` gains `"brand.md"`)
- Test: `tests/test_kit.py` (new tests; the hand-written expectations that read the file list or `## Colour` from the
  kit's `SKILL.md`, and the "fifteen files of a kit" list, are updated)

**Interfaces:**

- `kit-SKILL.md` holds, in this order: the front matter and title of `SKILL.md`, the status line, the "Use this whenever"
  paragraph, `{{how}}`, `{{kit}}`, `## Rules the owner decided` with `{{rules}}`, `## Never` with `{{never}}`, `{{map}}`.
- `kit-brand.md` holds `# {{brand}} brand: values and facts`, one line ("The values and facts behind `SKILL.md`. Generated:
  never edit it here."), then today's sections Colour (with `{{colours}}` and `{{pairs}}`), Type, `{{layout}}`, Mark
  (`{{mark}}`, `{{small}}`), `{{motion}}` and What may be claimed (`{{facts}}`), in today's words.
- `section(version: str) -> str`: `## The kit`, the version line, then: "This folder is a brand kit and this skill is its
  core. `kit.json` lists every file with its hash. Never edit a generated file here: change the brand project and run
  `brand-creator kit build --yes` again. Your own files (`EXTENDING.md` says which) are never overwritten.", then today's
  web-design paragraph.
- `how_md(files: dict[str, bytes]) -> str`: `## How to work` and these numbered steps, the bracketed parts only when the
  plan holds the file named:
  1. Name what you are making and the moment it is for (a page, a post, an ad, a deck; a launch, a reminder, an error).
  2. Read `golden-rules.md`: the rules every piece keeps.
  3. Open the recipe for that material in `recipes/`, one file per kind of material. When none fits, work from `brand.md`
     and say what no recipe covers.
  4. [masters: Ads and decks start from an approved master: `brand/assets/masters/README.md` lists them.]
  5. Take colours, type, spacing and motion from the tokens (`brand/assets/tokens/tokens.css`). A value the tokens lack is
     asked for, never invented.
  6. Take the logo from its files in `brand/assets/logo/` [logo.html: , placed as `snippets/logo.html` does it], as they
     are: never redrawn, recoloured or typed out.
  7. Take every claim (a number, a feature, a price, a client, a date) from `facts.json`. When one is missing, leave a
     visible placeholder and ask the owner.
  8. Anything the brand has not decided (a layout, a use of colour, an animation, a line of copy) is a proposal: label it
     and ask the owner.
  9. Before you hand anything over, go through `checklist.md`.

  Numbering runs on without the step that is left out.
- `map_md(files: dict[str, bytes]) -> str`: `## Map`, a table `| You need | Open |`, one row per line below, each only when
  the plan holds what it names: colours, pairs, type, layout, mark sizes, motion and claims → `brand.md`; the token values →
  `brand/assets/tokens/tokens.css`, `brand/assets/tokens/tokens.json`; the logo files → `brand/assets/logo/` (and
  `snippets/logo.html`); the fonts → `snippets/fonts.css`; the colours text may sit on → `snippets/on-ground.css`; the
  rules and the facts as data → `rules.json`, `facts.json`; approved pages to follow → `reference-pages/`; the approved
  ads and decks → `brand/assets/masters/README.md` (or `brand/assets/masters/` when it has no README); the signature
  move → `brand/motion/SPEC.md`; how to make one kind of material → `recipes/`; the rules every piece keeps →
  `golden-rules.md`; how the brand looks and sounds → `visual.md`, `voice.md`; the check before handing over →
  `checklist.md` (added in Task 5); how to change the kit → `EXTENDING.md`; every file and its hash → `kit.json`.
- `plan()` renders both templates with `kit={"prefix": PREFIX, "section": section(VERSION_PLACEHOLDER), "how":
  how_md(files), "map": map_md(files)}` and returns `SKILL.md` and `brand.md` with the other files.

- [ ] **Step 1: Write the failing tests:**

```python
def test_the_kits_skill_has_steps_rules_never_and_a_map_and_no_file_list(pack): ...
    # after kit build --yes: "## How to work", "## Rules the owner decided", "## Never", "## Map" in that order;
    # "## Colour" not in it; no line starts with "- `brand/"; "Kit version 1.1 (kit.json)." in it
def test_brand_md_holds_colour_type_mark_and_claims_with_kit_paths(pack): ...
    # "## Colour", "## Type", "## Mark", "## What may be claimed"; "`brand/assets/tokens/tokens.json`"; no "../../../"
def test_every_path_the_map_and_the_steps_name_is_in_the_kit(pack): ...
    # every backticked path in "## How to work" and "## Map" exists in the kit folder (a folder path ends with "/")
def test_the_map_names_masters_and_pages_only_when_the_kit_has_them(pack): ...
def test_without_a_kit_the_applied_skill_keeps_its_bytes(pack): ...
    # applied-skill --yes output equals tests/fixtures/applied-skill-acme.md, written before any code of this task changes by running
    # applied-skill --yes on the pack fixture (BRAND_CREATOR_TODAY as the tests set it)
def test_an_owner_file_where_brand_md_now_goes_stops_the_build(pack): ...
    # build; write kit/brand.md with other bytes; build again -> exit 1 naming brand.md; --replace -> moved to removed-<date>/, the new brand.md written
```

- [ ] **Steps 2-4:** fail, implement, pass (`test_kit.py`, `test_adapters.py`, `test_skills.py`).
- [ ] **Step 5: Commit** `brand-creator: the kit's entry page is steps, rules and a map; values and facts move to brand.md`.

### Task 5: a review checklist from the rules

**Files:**

- Modify: `scripts/adaptlib/kitlib.py` (new `checklist_md`, `plan`), `scripts/adaptlib/kitcopy.py` (`ROOT_FILES` gains
  `"checklist.md"`)
- Test: `tests/test_kit.py`

**Interfaces:**

- Produces: `CHECKLIST_MD = "checklist.md"`; `checklist_md(project: Path, rules: dict, files: dict[str, bytes]) -> bytes`,
  where `rules` is `rules_doc(project)`. The file, every item a `- [ ]` line:
  - `# <brand> checklist`, then "Go through it before you hand anything over. A "no" is fixed, or shown to the owner; never
    waved through."
  - `## Logo`: "The logo comes from its files in `brand/assets/logo/`, used as they are."; one line per band: "Up to
    <max_px> px[ the <mark>] <name> uses `<drawing>`." (a band with no `max_px`: "At larger sizes ... uses ..."); the
    downscale line: "At <accent_rule_max_size> px and below the accent holds a solid <accent_min_px> x <accent_min_px> px
    square."
  - `## Colour`: "Every colour is a token role from `brand/assets/tokens/tokens.css`, in both themes where the material has
    them."; one line per distinct (`kind`, `min`) of `pairs`, in first-seen order: "Every <kind> pair reaches at least
    <min>:1 (`brand.md` lists the pairs and their ratios)."
  - `## The owner's rules`: one line per `g4` rule: "<text> (`<id>`)". None recorded: the section is left out.
  - `## Words`: "None of these: <forbidden, joined by ", ">." Only when `forbidden` is not empty.
  - `## Page rules`: one line per `page.rules` entry: "`<id>`: <g4>". Only when `rules` has `page`.
  - `## Claims`: "Every number, feature, price, client and date is in `facts.json`; a missing one is a visible
    placeholder." and "Sample data is labelled as sample data."
  - `## New things`: "Anything the brand has not decided is labelled a proposal and shown to the owner." and "Every rule in
    `golden-rules.md` holds."

- [ ] **Step 1: Write the failing tests:**

```python
def test_the_checklist_lists_every_g4_rule_with_its_id_and_every_band(pack): ...
    # Acme: each g4 rule of rules.json appears as "- [ ] <text> (`<id>`)"; "uses `brand/assets/logo/grid-mark.svg`"
def test_the_checklist_has_no_words_section_without_forbidden_words_and_no_page_section_without_a_page_block(pack): ...
def test_the_checklist_is_a_generated_file_hashed_in_kit_json_and_its_links_resolve(pack): ...
    # kit.json generated has "checklist.md"; kit check passes kit:files and kit:links
def test_every_checklist_line_comes_from_rules_json_or_the_fixed_lines(pack): ...
    # strip the fixed lines (written out in the test); every remaining item names a rule id, a band drawing, a pair kind, a forbidden word or a page rule id
```

- [ ] **Steps 2-4:** fail, implement, pass. **Step 5: Commit** `brand-creator: the kit carries a review checklist built from rules.json`.

### Task 6: recipes for the masters

**Files:**

- Create: `templates/kit/recipes/ad.md`, `templates/kit/recipes/presentation.md`
- Modify: `scripts/adaptlib/kitlib.py` (new `scaffolds`; `owner_plan` and `owned_changes` use it instead of `OWNED_FILES`)
- Test: `tests/test_kit.py`

**Interfaces:**

- Produces: `MASTER_SCAFFOLDS = {"recipes/ad.md": ("ad",), "recipes/presentation.md": ("slide", "deck-html", "deck-pdf",
  "deck-pptx")}`; `scaffolds(project: Path) -> tuple[str, ...]`: `OWNED_FILES`, then each `MASTER_SCAFFOLDS` path whose
  kinds meet an entry of `assets/masters/masters.json` (`mastersdata.load_manifest`). No `masters.json`: `OWNED_FILES`. A
  `masters.json` with problems: exit 1, `assets/masters/masters.json: <first problem>; fix it, or run masters approve again`.
- Each scaffold: `# Ads` / `# Presentations`, "Steps only. The brand's values live in the tokens and rules.json; a line you
  add that pins a value cites a token or a rule, or is tagged `[example]`.", then numbered steps: start from an approved
  master (`../brand/assets/masters/README.md` lists each one, its size and the copy rules); keep its canvas and layout,
  change only the copy and pictures the copy rules allow; take every claim from `../facts.json`; nothing reaches outside
  the canvas and no text is covered by anything; (presentation only) a PowerPoint deck is checked in PowerPoint, never in
  Keynote, which ignores embedded fonts; anything new is a proposal for the owner. Then
  `[[fill: when to use which direction, in one line each]]`. Only `{{brand}}` and `{{skill}}` placeholders.
- `kit.json` `owned` lists every path of `scaffolds(project)`; `owned_problems` still requires only the five.

- [ ] **Step 1: Write the failing tests:**

```python
def test_ad_masters_scaffold_the_ad_recipe_only(pack): ...
    # assets/masters/masters.json with one "ad" entry -> recipes/ad.md written, recipes/presentation.md not
def test_a_deck_scaffolds_the_presentation_recipe(pack): ...
def test_a_master_scaffold_is_never_overwritten_and_comes_back_when_deleted(pack): ...
def test_without_masters_json_no_master_recipe_is_scaffolded(pack): ...
    # assets/masters/ with files and no masters.json (masters placed by hand)
def test_a_masters_json_with_a_problem_stops_the_build_naming_it(pack): ...
def test_the_scaffolds_link_to_files_the_kit_has(pack): ...
    # after the build, kit check: kit:links passes; kit:fill fails naming recipes/ad.md
```

- [ ] **Steps 2-4:** fail, implement, pass. **Step 5: Commit** `brand-creator: approved ad and deck masters scaffold their recipes`.

### Task 7: `install.py`, the installer the kit carries

**Files:**

- Modify: `scripts/adaptlib/kitcopy.py` (a CLI: `main(argv: list[str] | None = None) -> int`, `apply(...)`,
  `repo_root(...)`, `if __name__ == "__main__": sys.exit(main())`), `scripts/adaptlib/kitlib.py` (`plan` adds
  `install.py`), `scripts/adaptlib/kitcopy.py` (`ROOT_FILES` gains `"install.py"`), `skills/brand-adopt/SKILL.md` and
  `agents/brand-implementer.md` (the kit row runs `install.py`)
- Test: `tests/test_kitcopy.py`, `tests/test_kit.py`, `tests/test_skills.py`

**Interfaces:**

- `INSTALL_PY = "install.py"`; the plan's `install.py` is the bytes of `scripts/adaptlib/kitcopy.py`, read at build time.
- `repo_root(folder: Path) -> Path | None`: the nearest folder at or above `folder` holding a `.git` entry (a folder or a
  file), links resolved first.
- `apply(kit: Path, root: Path, res: dict, today: str) -> list[str]`: copies `res["copy"]` in order into
  `root/.claude/skills/<kit name>/` (parents made; each file written to a temporary name beside it, then `os.replace`).
  Before it writes a generated path that the repository's own `kit.json` `owned` records, it moves the repository's file
  to the removed folder. It moves `left_over` and `owner_left_over` there too. The removed folder is
  `root/removed-<today>/` (`-2`, `-3` when taken), and inside it each file keeps its path below `.claude/skills/<kit name>/`.
  Returns the paths moved.
- `main`: `python3 install.py REPO [--yes] [--json]`. The kit is the folder holding the script. Refused, exit 2, nothing
  written: a REPO that is no folder or a URL; one with no git work tree above it; a target for which
  `refusal(kit.parents[2], root)` gives a reason (the brand project or the repository the kit sits in, the home folder,
  `~/.claude`); a `.claude/skills/<kit name>` in the target that is a link. A kit that is not whole: exit 3.
  Without `--yes` it prints `status_lines` and "run again with --yes to copy" (exit 0 when current, 1 otherwise). With
  `--yes` it copies, then compares again: current, with nothing left to copy or update → `installed: <target> (version V)`
  and `next: review and commit it in <root>`, exit 0; otherwise what is left, exit 1. `--json` prints `result_json(res)`
  plus `"applied": true|false` and `"moved": [...]`. `today` is `BRAND_CREATOR_TODAY` when set, else the local date.
- brand-adopt's kit row: "run `python3 <kit folder>/install.py <repository path> --yes` on the owner's branch; then `kit
  status --repo <path>` must say current. Never into `~/.claude/skills` or any global folder. The kit is not committed."
  The implementer's rule "an owner file the repository already has is never overwritten" becomes "install.py updates an
  owner file only when the repository never changed it; one the repository changed is kept".

- [ ] **Step 1: Write the failing tests** (a project kit from `pack` and `kit build --yes`; a scratch repository made with
  `git init`; `install.py` run with `sys.executable -I` from the kit folder):

```python
def test_install_plans_then_copies_then_says_current(pack, tmp_path): ...
    # without --yes: exit 1, nothing written; --yes: exit 0, "installed:", kit status --repo exit 0
def test_install_and_kit_status_give_the_same_answer(pack, tmp_path): ...
    # for a fresh repo, a current one and one with an owner update: install.py --json minus applied/moved
    # == kit status --repo --json repos[0] minus label/path
def test_install_updates_an_unchanged_owner_file_and_keeps_a_changed_one(pack, tmp_path): ...
def test_install_moves_left_over_files_to_removed_and_deletes_nothing(pack, tmp_path): ...
def test_install_moves_a_repository_owner_file_aside_before_a_generated_file_takes_its_path(pack, tmp_path): ...
    # repo kit.json owned records checklist.md (a 0.10-era owner file): after --yes it is in removed-<date>/
def test_install_is_refused_for_its_own_repository_the_project_home_dot_claude_and_no_git(pack, tmp_path): ...
    # each: exit 2, the reason in stderr, folder_state of the target unchanged
def test_an_install_stopped_before_kit_json_is_finished_by_the_next_run(pack, tmp_path): ...
def test_the_kits_install_py_is_kitcopy_byte_for_byte(pack): ...
def test_install_runs_from_a_copy_of_the_kit_with_no_plugin(pack, tmp_path): ...
    # copytree the kit to tmp_path/elsewhere, run its install.py with cwd=tmp_path and PYTHONPATH unset: exit 0
```

- [ ] **Steps 2-4:** fail, implement, pass (`test_kitcopy.py`, `test_kit.py`, `test_skills.py`, `test_adoption.py`).
- [ ] **Step 5: Commit** `brand-creator: the kit carries install.py; brand-adopt's kit row runs it`.

### Task 8: docs, calibration, release

**Files:**

- Create: `docs/adr/ADR-0014-the-kit-installs-itself-and-updates-unchanged-owner-files.md` (from `ADR-TEMPLATE.md`:
  supersedes D10 for `install.py` and D11's "only where the repository has none"; why: the owner's 2026-11-09 answers
  and the spec)
- Modify: `docs/adr/README.md` (row; ADR-0011's status notes ADR-0014 as the docs standard says), `scripts/CONTRACT.md`
  ("kit": `brand.md`, `checklist.md`, `install.py`, the masters scaffolds, the status keys `update_owner`,
  `owner_left_over`, `other_skills`, the copy order), `docs/manual/use/use-your-brand-kit.md` (install with `install.py`,
  updates, the checklist), `templates/kit/EXTENDING.md` (the generated files, the update rule, `install.py`),
  `skills/brand-creator/references/phases/10-book.md` (kit section), `scripts/kit.py` docstring, `CHANGELOG.md` (0.11.0),
  version pins (`.claude-plugin/plugin.json`, `tests/test_static.py`, `scripts/lib/_common.py` USER_AGENT,
  `evals/_shared/fixture.sh`, `evals/_shared/acme-kit/` via `tests/tools/regen_eval_kit.py`),
  `docs/internals/manual-checks.md` (the release run record)
- Test: `tests/test_skills.py`, `tests/test_static.py`, `tests/test_evals.py`, the docs checks

- [ ] **Step 1:** docs edits; `python3 .github/scripts/check-docs-standard.py` and `npx -y markdownlint-cli2@0.18
  "plugins/brand-creator/**/*.md"`: 0 findings. `skills/brand-creator/SKILL.md` stays under its top budget (19,850
  characters).
- [ ] **Step 2: Calibration** on a scratch copy of Płacuję in the scratchpad (never the real project): `kit build --yes`;
  expect `SKILL.md` near 1,500 words and `brand.md` near 2,100 (`wc -w`), `kit check` failing only where 0.10.0 failed.
  Then a scratch `git init` repository: `install.py` plan, `--yes`, current; add `recipes/email.md` in the project, build,
  install again (copied); change `voice.md` in the project, build, install (updated); edit the repository's `voice.md`,
  change the project's again, build, install (kept, reported). Record the numbers in the CHANGELOG entry.
- [ ] **Step 3:** release run: Mac `tests/run-all.sh --smoke`, Linux `BRAND_CREATOR_TEST_PARTS=pytest,node
  tests/docker/run.sh && BRAND_CREATOR_TEST_PARTS=smoke tests/docker/run.sh --no-build`; record in manual-checks.md.
- [ ] **Step 4: Commit** `brand-creator 0.11.0: one brand kit (entry page and brand.md, checklist, master recipes, owner
  updates, install.py)`. Push and tag only on the owner's go, after the push-triggered checks pass.
- [ ] **After the release:** hand Part B of the spec to the Płacuję session.
