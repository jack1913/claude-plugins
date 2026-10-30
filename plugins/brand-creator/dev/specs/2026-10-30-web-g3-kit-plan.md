# Group 3 plan: the brand kit, its install and the redesign wiring record

Plan date 2026-10-30. The owner approved the roadmap on 2026-10-30. This is group 3 of 3 and covers roadmap steps 3 and 13 to 18.
Group 1 (foundations and the page check) lands first, then group 2 (website references and the site round), then this group. Every
interface taken from an earlier group is named in "Interfaces taken from groups 1 and 2".

This is a working file, not a doc. It lives in `dev/specs/` while the work runs and moves to `docs/archive/` when it ships. The
static tests and the docs checks scan it like a shipped file. So it holds no personal path, no e-mail address and no client name:
the owner's private brand that showed the problem is called "the pilot brand" here, and the owner's site repository "the owner's site".

## Cross-group review (2026-10-30)

The three plans were checked against each other and against the code. What changed here:

- ADR numbers are fixed: ADR-0011 (the kit, G3-02) and ADR-0012 (the wiring record, G3-24). This group starts after G2-19.
- Page-check reports are found with group 1's `pagecheck.report_tool()`; their `samples` and `target` are top-level keys
  (`Report.write` spreads `extra`). Loopback URLs are judged by group 1's `isLoopbackUrl` (`scripts/lib/_common.mjs`).
- G3-01 scores against a scratch copy of the brand project (page-check writes its report into the project it is given).
- G3-08 copies the `page` block only from the project's own `qa/rules.json` file (group 1 adds defaults to `qa_rules.DEFAULTS`).
- G3-11 always writes `snippets/on-ground.css` (group 1 puts the grounds in `tokens.json` only).
- G3-13's static test lives in `tests/test_skills.py` (`tests/test_kit.py` has a module-level `pytestmark`).
- G3-23 adds a `PLAN_BULLETS` entry (`tests/test_evals.py` fails on a case folder without one) and ignores `plugin_version`
  in the snapshot.
- Verify commands set `BRAND_CREATOR_DATA`; the mutation ledger and `BRAND_CREATOR_REQUIRE_ALL=1` need it.

## Goal

Every brand gets a generated, extendable brand kit that a product repository can carry. The kit sits around the per-brand applied
skill, and the applied skill stays its core. The kit holds the brand's own files byte for byte, the rules and facts as data, and
derived snippets, all hash-locked. It also holds the owner's own parts (recipes, voice, visual, golden rules), written once and never
overwritten. `kit check` proves the kit is whole, current and honest: no dead link, no fill marker, one version, and no value that
neither cites a token or a rule nor says it is an example. The kit goes into a product repository through brand-adopt as a byte copy
on the owner's branch, and `kit status --repo` proves the copy is current. A redesign of an existing site records the site's wiring
before and after, and the review fails any loss that is not recorded as dropped with a reason.

## Scope

- In scope: roadmap 3 (the kit test baseline as a manual check), 13 (the kit), 14 (the web-page recipe), 15 (the reference pages in
  the kit), 16 (install through brand-adopt, `kit status --repo`), 17 (the kit test as a standard step and a billed eval) and 18 (the
  wiring record).
- Out of scope: everything of groups 1 and 2, any skill `description` or `when_to_use` text, `evals/trigger-evals.json`, the
  orchestrator's top section (above `## Round mechanics`), and the pilot brand's project, which stays untouched.

## Decisions

### Owner defaults (each is a default the owner may change)

- **D1 Kit around the applied skill.** The kit folder is the applied skill's folder, `.claude/skills/<slug>-brand/`. Its `SKILL.md`
  is still written by the same builder (`adapt.applied_skill_md`), so the applied skill becomes the kit's core. Nothing is replaced. A
  project without a kit keeps the applied skill as it is today: the same bytes, the same command and the same `check` rows.
- **D2 Descriptions change only in group 2.** No task here touches a skill's `description` or `when_to_use`, or the trigger evals.
- **D3 Word lists English and Polish.** This belongs to group 1's page check. The kit's recipe only points at that check.
- **D4 Sample data.** Data labelled `[data-sample]` passes the page check with a before-publishing list, and an unbacked claim with no
  label fails. The recipe's last step builds that list.
- **D5 The social kicker is reported only.** This is group 1's. Nothing here changes `templates/social/`.
- **D6 Fonts.** OFL fonts are copied with their licence text. A font under any other licence is listed and not copied.
- **D7 Agents only after the fleet gate.** The kit test runs in-thread by default. An agent runs only after the fleet gate. No new
  workflow is added.
- **D8 The pilot brand stays untouched.** Its project is read only for the manual baseline, by the owner, from a scratch copy.

### Defaults this plan adds (each is a default the owner may change)

- **D9 One version field.** The version is `kit.json` `version`, written `<edition>.<build>`. The build number starts at 1 and goes up
  by 1 when a build changes any kit content. The SKILL.md kit section prints the version, and no other file carries one.
- **D10 Scripts never write outside the brand project.** The install copy into a product repository is done by the implementer (the
  lead in-thread, or `brand-implementer` after the fleet gate), by the copy list that `kit status` prints. `kit status --repo` and the
  wiring scan only read a repository, and each proves it.
- **D11 An installed kit's owner files are the repository's.** An update copies the generated files. It copies an owner file only
  where the repository has none, and reports owner files that differ.
- **D12 Rule ids.** A G4 rule's id is the ASCII slug of its first six words (`the-mark-keeps-its-clear-space`), with `-2`, `-3` for
  repeats in BRAND-STATE order. Group 1's plan gives G4 lines no ids: its `page` rules carry the G4 text in `g4`. A tag names
  one of three kinds of id:
  - a G4 slug, written bare: `[rule: the-mark-keeps-its-clear-space]`
  - a page rule: `[rule: page:<id>]`
  - a site choice tagged `rule` in `site/site.json`: `[rule: site:<id>]`
- **D13 The kit is offered in every tier, opt-in at G5.** It is recommended when the brief lists a site or INVENTORY lists product
  repositories.
- **D14 The new kit checks fail from the start.** No kit exists yet, so nothing that exists can break. The one-release WARN rule of
  group 1 does not apply.
- **D15 Rendered wiring is read from loopback URLs only** (`127.0.0.1`, `localhost`, `[::1]`): the product's own dev or preview
  server, started by the owner.
- **D16 A font's licence comes from the fontcheck report**, which reads the font's own name table. The OFL text must also sit in
  `assets/fonts/`.

## Interfaces taken from groups 1 and 2

The names below are from the group 1 and group 2 plans written beside this one (`dev/specs/2026-10-30-web-g1-foundations-plan.md`,
`dev/specs/2026-10-30-web-g2-site-round-plan.md`). Before a task that uses one of them starts, read the code that landed. If a name
differs, use the landed name and keep the behaviour. If the behaviour is missing, stop and ask the lead; never build a second
version of it here.

- **ADR numbers (fixed by the cross-group review).** Group 1 takes ADR-0006, ADR-0007 and ADR-0008. Group 2 takes ADR-0009
  (website references) and ADR-0010 (the site round). This group takes ADR-0011 (the kit) and ADR-0012 (the wiring record).
- **Order.** Group 1 ends with G1-25 and group 2 with G2-19; this group starts after G2-19, one implementer at a time in one
  working tree.
- **The handoff fix (group 1).** In `scripts/adaptlib/adapt.py`, `applied_skill_md(project, template)` writes sizes, weights,
  spacing, radius, leading, tracking and an optional `## Layout` section. G3-03 adds one keyword argument on top of that version.
- **Ground roles (group 1, G1-10).** Group 1 writes the grounds into `tokens.json` only; `tokens.css` gets no per-ground
  scope. The built `assets/tokens/tokens.json` holds `grounds`:
  `{named_by_owner, list: [{ground, roles: {text, action, on-action, focus, border}, modes: {light: {...}, dark: {...}}}]}`. It is
  there only when the token sources declare it. `named_by_owner` starts with a `YYYY-MM-DD` date once the owner named the grounds;
  until then the list is a proposal. Used by G3-11.
- **The page check (group 1).**
  - The command: `brand-creator page-check <page> | --from DIR <page> | --url URL [--project DIR]`, exit 0, 1, 2 or 3. `--url` takes
    loopback hosts only.
  - One report per page, tool `page-check/<slug>-<hash6>` from `pagecheck.report_tool("<project-relative path>")` in
    `scripts/pagelib/pagecheck.py` (import it; never rebuild the rule). Rows `page:*` (brand rules), `tell:<id>` (reflex
    warnings) and `page:samples`. `Report.write` puts `extra` at the top level, so the report's top-level `samples`
    (`[{label, text, selector, view}]`) is the before-publishing list and its top-level `target` is
    `{kind, page, from, url}`.
  - The loopback rule: `isLoopbackUrl(url)` exported by `scripts/lib/_common.mjs` (and `pagecheck.is_loopback_url` in
    Python). G3-27 reuses it.
  - Markup: `data-sample="<label>"` and `data-brand-mark`.
  - `qa/rules.json` `page.rules[]`, each with `id`, `kind` and `g4` (the text of the G4 line it is tied to).
  - Measuring lives in `scripts/pagelib/page_measure.mjs`, through `render.mjs page-measure`.
  - Used by G3-13, G3-16, G3-17, G3-22, G3-23 and G3-27.
- **Specimens (group 1).** `specimens/<name>/` in a project, and `shot --out specimens/<name>`.
- **Layout references (group 2).** `skills/brand-creator/references/page-layouts.json`, read by `sitedata.load_layouts()`. The
  recipe's references step points at it.
- **Approved reference pages (group 2).**
  - `site/<id>/index.html`, with its stills from `brand-creator capture` in `site/<id>/shots/` and `capture.json` (with `inputs`).
  - One page-check report per page.
  - `site/site.json` (schema 1): `approved` (the G4p record), `round`, `hero`, `pages: [{id, path, layout, sha256}]`, and
    `choices: [{id, text, tag: rule|example, source, pages}]`.
  - `scripts/boardlib/sitedata.py`: `load_site()`, `validate_site()`, `rewrite_urls()`, `load_layouts()`. `site approve` is
    `scripts/site_pages.py` (subcommand `site`).
  - The home page's id in every shipped example is `start`.
  - `check` rows `site:record`, `site:pages` and `site:stills`.
  - `site approve` already rewrites a page's URLs so they resolve project files from `site/<id>/`. Because the kit's `brand/`
    mirrors project paths, the kit needs no rewriting of its own.
  - Used by G3-16 and G3-17.
- **The cold-review prompt fragment (group 2).** In `skills/brand-creator/references/prompt-fragments.md`, reused by the kit test
  (G3-22).

## Architecture

### The kit folder (in the brand project)

```text
.claude/skills/<slug>-brand/
  SKILL.md               generated: the applied skill (same builder), paths inside the kit, plus a "## The kit" section
  kit.json               generated: schema, version, edition, sources, sha256 of every other generated file, owner files, fonts, pages
  rules.json             generated: G4 rules with ids, the size rule and bands, the contrast pairs with ratios, forbidden words, the page block
  facts.json             generated: the public FACTS rows (contact rows never)
  brand/                 generated: byte copies of the brand's files AT THEIR PROJECT PATHS, so their relative links still resolve:
    assets/tokens/tokens.css, tokens.json
    assets/logo/*.svg, *.png, and every band drawing qa/rules.json names (at its own path)
    assets/fonts/<OFL fonts> and their licence texts
    motion/motion.json, motion/SPEC.md, and the page of each page case of motion/proof.json
    <each approved reference page and every local file it loads>, <its screenshots>
  snippets/              generated: fonts.css, logo.html, on-ground.css (each only when it has content)
  reference-pages/<id>/notes.md   generated: the page's layout reference, approval, screenshots and choices, each tagged
  EXTENDING.md           owner's: written once from templates/kit/, never overwritten
  voice.md  visual.md  golden-rules.md   owner's (scaffolds with [[fill: ...]] markers)
  recipes/web-page.md    owner's: the web-page recipe, steps only
```

`brand/` mirrors project paths, so a demo or reference page that loads `../assets/tokens/tokens.css` still finds it inside the kit.
That is why `kit:links` can demand that every link resolves inside the kit.

### kit.json

```json
{"schema": 1, "kit": "acme-brand", "version": "1.3", "edition": "1", "plugin_version": "<plugin version>",
 "content_sha": "<sha256 over the kit content, version left out>",
 "generated": {"SKILL.md": "<sha256>", "rules.json": "<sha256>", "brand/assets/tokens/tokens.css": "<sha256>"},
 "owned": {"voice.md": "<sha256 at the last build>"},
 "fonts": {"copied": [{"file": "brand/assets/fonts/X.woff2", "licence": "SIL Open Font License (OFL)", "licence_files": ["brand/assets/fonts/OFL.txt"]}],
           "not_copied": [{"file": "assets/fonts/Y.woff2", "reason": "..."}]},
 "sources": {"state_sha": "...", "tokens": "...", "tokens_css": "...", "rules": null, "facts": "...", "motion": null, "logos": "...", "fonts": null, "pages": null},
 "reference_pages": [{"id": "start", "page": "brand/site/start/index.html", "source_sha": "...", "page_check_inputs_sha": "...", "capture_inputs_sha": "..."}]}
```

- `generated` lists every generated file except `kit.json` itself. The `kit` report records `kit.json`'s own sha256 in `outputs`.
- `content_sha` is sha256 over the sorted (path, sha256) pairs of every generated file except `kit.json`, plus the `owned` pairs.
  SKILL.md is hashed as rendered with the literal `<version>` in its version line. The version rule: same edition and same
  `content_sha` keeps the version; same edition and another `content_sha` adds 1 to the build number; a new edition starts at
  `<edition>.1`. No clock, no randomness.
- `kitlib.load()` refuses an unknown key at any level (exit 2, naming it), as `motionspec` does. Each task that adds a key adds it to
  the known set.

### Commands, reports and exit codes

All are written after `brand-creator --data "${CLAUDE_PLUGIN_DATA}"`. Exit codes follow the contract: 0 pass, 1 a gate failed, 2
usage, 3 cannot run or not verified.

- `kit build [--yes] [--plan] [--replace]` writes report `kit`. It needs G5 recorded (exit 1 without) and `--yes` (without it, the
  plan goes to stdout and the message to stderr, exit 2). `--plan` prints the plan and exits 0. A generated file that was edited by
  hand, or a file put into a generated folder, stops it (exit 1) unless `--replace`, which moves it to `removed-<date>[-n]/`. Tokens
  not built: exit 3. A path that would leave the project: exit 2.
- `kit check` writes report `kit-check`. No kit: exit 2. Otherwise exit 0, 1 or 3.
- `kit status [--repo DIR[=LABEL]]... [--json]` writes no report and reads only. Exit 0 when every copy is current. Exit 1 when one is
  not installed or not current. Exit 2 on usage: no kit, a folder that does not exist, the project itself or a folder inside it, the
  user's home or a global skills folder.
- `adoption add --repo LABEL --kit` adds a pinned row of the new category `kit`.
- `adoption wiring --repo LABEL (--before [--again] | --after | --compare | --drop "ITEM::REASON"...) [--page URL]...` writes report
  `adoption-wiring` for `--before` and `--after`. `--compare` writes nothing. The exit codes are in G3-25 to G3-27.

### Report rows

- `kit`: `kit:written`, `kit:fonts`, `kit:owned`, `kit:reference-pages`.
- `kit-check`: `kit:files`, `kit:links`, `kit:fill`, `kit:versions`, `kit:plugin` (warn), `kit:sources`, `kit:owned` (warn),
  `kit:tags`, `kit:numbers`, `kit:reference-page:<id>`.
- `check`: `report:kit`, `report:kit-check` (the generic report gate), `kit:file`, `kit:state`, `adoption:wiring:<label>`.
- `adoption-wiring`: `read-only:<label>`, `wiring:<label>`, `wiring:scope`, `wiring:pages`.

### Code layout

- `scripts/adaptlib/kitlib.py` (new, standard library only). It holds the kit as data: paths, plan, version, sources, rule ids,
  checks. It sits outside `scripts/lib/` for the reason `adapt.py` does: a change there must not make every pack stale (`lib/stale.py`
  hashes `scripts/lib/*.py`).
- `scripts/kit.py` (new uv script: shebang `#!/usr/bin/env -S uv run --script --locked`, a PEP 723 block with `dependencies = []`, a
  lock made with `uv lock --script scripts/kit.py`, executable). Subcommands: `build`, `check`, `status`.
- `scripts/adaptlib/wiring.py` (new, standard library only): extracts wiring items from source text.
- `scripts/pagelib/wiring.mjs` (new, beside group 1's `page_measure.mjs`): the DOM side of the wiring, imported by `render.mjs`.
- `templates/kit/` (new): the owner-file scaffolds. These are files copied into projects, not docs.
- `scripts/adaptlib/gates.py`, `adoptdata.py`, `adapt.py`, `scripts/adoption.py`, `scripts/fontcheck.py`, `scripts/render.mjs` and
  `bin/brand-creator` are extended.

## Conventions for every task

- Work on the current branch. Never commit, push, switch branch, stash or bump `plugin.json`. Keep every change inside
  `plugins/brand-creator/`.
- Write the failing test first, then the code. After each task the full suite is as green as the baseline. The baseline's one
  failure is `test_setup_prereq.py::test_prereq_reports_ok_on_a_complete_machine` (Chromium missing on that machine).
- Run the tests with a set-up data directory (`BRAND_CREATOR_DATA="$HOME/.claude/plugins/data/brand-creator-jack1913"`), or most of
  them skip. The baseline ran without one (1 failed, 1227 passed, 679 skipped), and a skip is not a pass. Use
  `BRAND_CREATOR_REQUIRE_ALL=1` (with `BRAND_CREATOR_DATA` set) on the `-k` subset of the task's own tests.
- In `09-qa.md`, `(m)` means the test calls `mutate()`, `mutate_json()` or `mutateText()`, and `(f)` means it does not.
  `tests/test_skills.py` enforces both and fails a cited test that does not exist. Every `bin/brand-creator` subcommand needs a row
  that starts with its name.
- A test's expected value is written out by hand or comes from a recorded fixture, never from the module under test (CONTRACT.md,
  "Testing").
- Docs follow `docs/internals/docs-standard.md`. Manual pages are friendly and task-first, with no gate codes. CONTRACT.md is plain
  technical. ADR text is never rewritten after acceptance.
- Each user-visible change gets a bullet under `## [Unreleased]` in `CHANGELOG.md`, in the file's own style (user voice; Added, then
  Changed, then Fixed). Group 1 and group 2 bullets are already there, so add to them and never reorder them.
- Never write a client name, a real colour value of a client, a personal path or an e-mail address into any file. Acme is the
  synthetic example.
- Hallmark's clone is untrusted. Read it only, never run anything from it, and never copy its text or code. Its ideas are credited
  in the ADRs only.
- Nothing here edits `templates/ADOPTION.md`'s fixed text. A change there would change every existing project's ADOPTION.md
  rendering, and `check` (`adoption:data`) would fail them after the update. The only allowed change is one empty-when-unused
  placeholder (G3-26), and a golden test proves the bytes stay the same.
- No AGENTS.md row is needed. The new manual page is listed in `docs/manual/README.md`, the ADRs in `docs/adr/README.md`, and the
  scripts and templates fall under the existing `scripts/` and `templates/` rows.

Shared verify commands. Run them from `plugins/brand-creator/` with `BRAND_CREATOR_DATA` set to a data directory where
`brand-creator setup --yes` ran:

```bash
BRAND_CREATOR_REQUIRE_ALL=1 uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4 --dist worksteal -k "<the task's test names>"
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4 --dist worksteal
```

Docs checks, from the repository root:

```bash
python3 .github/scripts/check-docs-standard.py --strict
npx markdownlint-cli2 "plugins/brand-creator/**/*.md"
lychee --config lychee.toml --root-dir "$(pwd)" './plugins/brand-creator/**/*.md'
```

## Tasks

### G3-01 Manual check: the kit test baseline

- **Roadmap:** 3. **Depends on:** none (the scoring line uses group 1's page check once it exists).
- **Files:** `docs/internals/manual-checks.md`.
- **Do:** Add a section, `## Kit test baseline: a hero from the applied skill and from a kit`, and a status-table row for it with
  "never run". The section has the usual "Why manual" and "Steps" parts:
  - Why manual: it needs a real Claude Code session, a web-building skill, and a brand's own files, read only. It is billed.
  - Step 1. In scratch, outside every brand project, copy the brand's applied skill folder, DESIGN.md and `tokens.css` into folder A.
    Copy a brand kit into folder B: the owner's hand-made one before this release, the generated one after it.
  - Step 2. In a fresh session in A, with the owner's web skill (for example frontend-design) and no other plugin, ask for the home
    page hero from the brief line and the facts only. Save the page.
  - Step 3. Do the same in B.
  - Step 4. Score both with `brand-creator page-check`, both tiers, with `--project <a scratch copy of the brand project>` (page-check
    writes its report into the project it is given, so never the brand project itself) and `--from <folder A or B> <page>` or
    `--url`, and with the owner's own checklist if there is one. Count brand-rule failures, reflex warnings and invented values (a colour, size or
    claim that is in no brand file). Before group 1's page check exists, score by hand and say so.
  - Step 5. Record the date, Claude Code version, model, web skill and its version, both scores and the gaps. The gaps feed the kit
    work. Nothing in the brand project changes.
  - Step 6. The same run fills two existing rows. "Applied skill in a real session": was `<slug>-brand` listed by `/skills` and used
    in A? "DESIGN.md and BRAND.md in a real agent": did the agent take colours and dark variants from DESIGN.md?
  - Last run: never.
- **Tests:** none (docs only).
- **Docs:** this page only. No CHANGELOG entry (internals).
- **Verify:** the docs checks.
- **Done when:** the section and its row exist, and markdownlint and lychee pass, including the row's anchor link.
- **Owner checkpoint:** the owner and the lead run it, in-thread, from scratch copies. It is not an implementer task. Ideally it runs
  before G3-04, so its gaps can shape the recipe text in G3-13.

### G3-02 ADR: a generated brand kit around the applied skill

- **Roadmap:** 13 to 17. **Depends on:** G1-01 and G2-01 (ADR-0006 to ADR-0010 exist), G2-19 (group 2 done).
- **Files:** `docs/adr/ADR-0011-a-generated-brand-kit-around-the-applied-skill.md` (new, from `ADR-TEMPLATE.md`),
  `docs/adr/README.md` (a row).
- **Do:** Status `accepted`, Date 2026-10-30. Source: group 1's scope ADR (ADR-0007, "brand-side of the web"), group 2's site round
  ADR (ADR-0010), and CONTRACT.md "Adoption, cascade, adapters, applied skill and launch". Name this plan by its path in a code span, not a
  link (it moves to the archive when shipped, and lychee checks links).
  - Context. The applied skill is one file whose mark paths (`../../../`) do not resolve in a product repository. Hand-built kits
    drift: on the pilot brand, twelve hand version bumps in six days, and two files that each claimed a version and disagreed. A
    recipe that pins undecided defaults is obeyed by web-building skills, because the brief's own words win there. The owner asked
    for an extendable brand skill that installs per product repository.
  - Decision. Every bullet of "Decisions" D1, D6, D9 to D14 and D16. The generated and owner-owned split. The `brand/` mirror of
    project paths. The `kit check` rows. Tagging (`[rule: <id>]`, `[example]`) and numbers that cite a token or a rule. Install as
    adoption category `kit`, copied on the owner's branch, never committed, never global, proven by `kit status --repo`. The site
    round's approved reference pages enter the kit only with a passing page check and go stale on a token or rule change. The kit
    test is an optional step after the kit is written plus a billed eval, in-thread by default.
  - Consequences. A project without a kit is unchanged. `applied-skill` hands over to `kit build` once a kit exists. `check` expects
    the `kit` and `kit-check` reports. A fresh kit fails `kit check` until the owner files are filled. The kit must be rebuilt after
    a brand change, and `kit check` says when. List the defaults the owner may change.
  - Credit (ideas only, reimplemented; no text or code copied): Hallmark (MIT), commit 4f6a46c. Its `references/anatomy.md` (start a
    page from the visitor's job) and its `references/review-hero.md` (build the hero first; a cold review with fixed inputs and the
    verdict first).
- **Tests:** none. `check-docs-standard.py` checks the Status line.
- **Docs:** ADR README row: `| [ADR-<n>](<file>) | A generated brand kit sits around the applied skill | accepted |`.
- **Verify:** the docs checks.
- **Done when:** the ADR and its row exist and the docs checks pass. The ADR names no client and no personal path.

### G3-03 The applied skill builder learns a kit mode

- **Roadmap:** 13. **Depends on:** group 1's handoff fix (the builder as group 1 left it).
- **Files:** `scripts/adaptlib/adapt.py`, `templates/applied-skill/SKILL.md`, `tests/test_kit.py` (new).
- **Do:**
  - Before any edit, run `applied-skill --yes` on an Acme pack (a copy of the test `pack` fixture's steps, in scratch) and note the
    sha256 of the SKILL.md.
  - Change the signature to `applied_skill_md(project, template, *, kit: dict | None = None)`. `kit` is
    `{"prefix": "brand/", "section": "<markdown>"}`.
  - With `kit=None`, the output stays byte for byte what it was. Fill `{{tokens}}` with `../../../assets/tokens/tokens.json`, mark lines
    with ``- `../../../<path>` `` (as now), and band lines with the drawing's raw project path (as now). Drop the `{{kit}}` line and the
    blank line after it, as `{{motion}}` is dropped.
  - With a kit: `{{tokens}}` becomes `brand/assets/tokens/tokens.json`. Mark lines become ``- `brand/<path>` ``, band lines
    `` `brand/<drawing>` ``, and `{{kit}}` becomes `kit["section"]`.
  - In the template, write `{{tokens}}` in place of the literal tokens path. Put `{{kit}}` on its own line between the "Use this
    whenever ..." paragraph and `## Colour`.
  - The placeholder guard stays: an unknown placeholder still exits 2.
- **Tests (in `tests/test_kit.py`):** add `pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_node]` and a `pack` fixture
  that copies `tests/test_adapters.py`'s (acme, FACTS fixture, `content_languages=en`, `edition=1`, G5 recorded).
  - `test_without_a_kit_the_applied_skill_keeps_its_paths_and_has_no_kit_section` (f): runs `applied-skill --yes`. The file holds
    `../../../assets/tokens/tokens.json`, no `## The kit` and no `{{`.
  - `test_in_kit_mode_every_path_points_inside_the_kit` (f): calls `adapt.applied_skill_md` in-process (`tests/helpers.py` already puts
    `scripts/adaptlib` on `sys.path`) with `kit={"prefix": "brand/", "section": "## The kit\n\nx"}`. Asserts no `../../../`,
    `` `brand/assets/logo/mark.svg` `` present, `brand/assets/tokens/tokens.json` present, and `## The kit` placed before `## Colour`.
  - The existing applied-skill tests in `tests/test_adapters.py` stay green, including the placeholder-guard test.
- **Docs:** CONTRACT.md `### applied-skill`: one sentence saying the same builder writes the kit's SKILL.md, with paths inside the kit
  (see `kit`). No CHANGELOG entry (no user-visible change).
- **Verify:** `-k "applied_skill or kit_mode or keeps_its_paths"`; then regenerate the scratch SKILL.md and compare its sha256 with the
  one noted before (it must be equal); then the full suite.
- **Done when:** the no-kit output is byte-identical to before, and both new tests pass.

### G3-04 kitlib and `kit build`: the generated core

- **Roadmap:** 13. **Depends on:** G3-03.
- **Files:** `scripts/adaptlib/kitlib.py` (new), `scripts/kit.py` and `scripts/kit.py.lock` (new; `chmod +x`), `bin/brand-creator`,
  `scripts/CONTRACT.md`, `skills/brand-creator/references/phases/09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - `kitlib.py` holds the constants (`KIT_FILE = "kit.json"`, `SCHEMA = 1`, `GENERATED_DIRS = ("brand", "snippets",
    "reference-pages")`), `kit_dir(project)`, `exists(project)`, `load(project)` (a strict schema; an unknown key exits 2),
    `sources(project)`, `sources_sha(project)`, `plan(project) -> dict[kit_rel, bytes]`, `section(version, rels)`, `content_sha(...)`
    and `next_version(prev, edition, content_sha)`. `kit_dir(project)` is `project / adapt.SKILL_DIR / adapt.skill_name(project)`.
  - The plan, for now:
    - `brand/assets/tokens/tokens.css` and `brand/assets/tokens/tokens.json`. A missing `tokens.json` exits 3 through
      `bookdata.tokens`; a missing `tokens.css` exits 3, naming `brand-creator tokens`.
    - `brand/<path>` for every file of `bookdata.logo_files(project)`.
    - `brand/<drawing>` for every band drawing that `qa_rules.load(project)` names, top-level and per mark. A drawing outside the
      project exits 2 (use `confine`). A missing drawing exits 1, naming it.
    - `SKILL.md`, made by `adapt.applied_skill_md(..., kit={"prefix": "brand/", "section": kitlib.section(...)})`.
    - `kit.json`.
  - The kit section lists only what the plan holds, so later tasks extend it with no edit. It holds a version line written exactly
    `Kit version <version> (kit.json).`, the generated part with the "never edit these here: change the brand project and run `kit
    build` again" rule, and the owner part with "yours to extend; how: `EXTENDING.md`" (the owner part appears once G3-12 adds it).
  - Previous record: the `kit` report's `outputs` map. With no kit report, the `applied-skill` report's `output.sha256` stands in for
    `SKILL.md`.
  - Hand edits. A planned file on disk whose bytes differ from the plan, and whose sha256 is not the recorded one, is a hand edit. A
    file inside a generated folder that is neither planned nor recorded is a foreign file. Either one stops the build with exit 1,
    listing up to 6 paths, unless `--replace` moves each to `removed-<date>[-n]/<its project path>`.
  - A file recorded before and no longer planned (a logo taken away) is moved to `removed-<date>/` and said so. It is never deleted.
  - Version: as in the Architecture section. The edition is BRAND-STATE `approved_edition`. When it is empty, exit 1: "G5 is
    recorded but no edition is approved".
  - Writing: put-on-byte-change (`write_bytes_if_changed`), `kit.json` last.
  - Report `kit`: renderer `n/a (generated files)`. Inputs: `tokens.css`, `tokens.json`, the logo files, the band drawings,
    `qa/rules.json`, `FACTS.md` and `motion/motion.json`, each when present. Row `kit:written` is pass, with detail
    `<n> generated files: <w> written, <u> unchanged, <r> moved to removed-<date>/; version <v>`. Extra: `outputs` (every generated
    rel path with its sha256, `kit.json` included), `version`, `adapter_state_sha` (`adapt.state_sha`), `kit_sources_sha`.
  - `--plan`, or no `--yes`: print `would write <n> generated files into .claude/skills/<name>/ (version <v>)`, then one line per file
    (`generated <rel> (<bytes> bytes)`). Without `--plan`, also stderr `error: the brand kit is written into the project's
    .claude/skills/ and needs the owner's explicit OK at G5: re-run with --yes`, exit 2. With `--plan`, exit 0.
  - `bin/brand-creator`: dispatch `kit) py kit.py "$@" ;;`. Help lines in the "adoption, adapters, launch" group: `kit
    build|check|status` with a two-line description (only `build` exists yet; the help names all three because G3-14 and G3-18 follow).
- **Tests (`tests/test_kit.py`):**
  - `test_the_kit_needs_g5_and_yes_and_writes_nothing_without_them` (f)
  - `test_the_kit_core_is_the_applied_skill_with_paths_inside_the_kit` (f): every `` `brand/...` `` path in SKILL.md exists in the
    kit. `filecmp.cmp(shallow=False)` holds for both token files. The Acme colour constants of `test_adapters.py` are in SKILL.md, and
    so is `Kit version 1.1 (kit.json).`.
  - `test_a_second_build_with_nothing_changed_is_byte_identical_and_keeps_the_version` (f)
  - `test_a_changed_token_rebuilds_the_copy_and_adds_one_to_the_build_number` (m): `mutate_json` a token source, then `tokens`, then
    `kit build`. The version is 1.2.
  - `test_a_hand_edited_kit_file_stops_the_build_and_replace_moves_it_aside` (m): the old file ends up under
    `removed-2026-10-17/.claude/skills/acme-brand/...` (`bc` sets `BRAND_CREATOR_TODAY`).
  - `test_a_file_put_into_a_generated_folder_stops_the_build` (f)
  - `test_a_logo_taken_out_of_the_project_moves_its_kit_copy_to_removed` (f)
  - `test_a_new_edition_starts_the_build_number_again` (f): `state --set edition=2`, `state --record G5 ...`; the version is `2.1`.
  - `test_the_kit_takes_over_a_skill_file_that_applied_skill_wrote` (f)
  - `test_a_hand_edited_applied_skill_stops_the_first_kit_build` (m)
  - `test_every_uv_script_starts_and_shows_help` and the bin, help and contract test in `test_static.py` must stay green.
- **Docs:**
  - CONTRACT.md: add `kit` to the Reports tool names. Add a project-file-conventions line:
    `.claude/skills/<slug>-brand/  the per-brand applied skill, or the brand kit around it (kit.json), written only by applied-skill --yes or kit build --yes`.
    Add a new `### kit` subsection under "Adoption, cascade, adapters, applied skill and launch" with the folder layout, the
    generated and owned split, `kit.json`, the version rule, hand-edit refusal, exit codes and the report.
  - `09-qa.md`: a new row `| \`kit build --yes\` | \`kit\` | ... | ... |` that blocks: no G5 (exit 1); no `--yes` (plan, exit 2, nothing
    written); tokens not built (exit 3); a band drawing missing (exit 1) or outside the project (exit 2); a hand-edited generated kit
    file or a foreign file in a generated folder (exit 1; `--replace` moves it). Cite the tests above with their (m) and (f).
  - CHANGELOG Added: "A brand kit for your product repositories: `brand-creator kit build --yes` writes it around your brand skill,
    with the brand's own files copied in byte for byte and locked (opt-in when you approve the brand)."
- **Verify:** `uv lock --script scripts/kit.py`; `uv run --script --locked scripts/kit.py --help`; `-k "kit and not applied"`;
  `tests/test_static.py` and `tests/test_skills.py`; the full suite.
- **Done when:** every listed test passes, the static and 09-qa tests pass, and the suite is at the baseline.

### G3-05 `check` gates the kit, and `applied-skill` hands over to it

- **Roadmap:** 13. **Depends on:** G3-04.
- **Files:** `scripts/adaptlib/gates.py`, `scripts/applied_skill.py`, `scripts/check.py` (docstring only), `scripts/CONTRACT.md`,
  `09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - `gates.present()` returns `kit` (the kit dir, relative) when `kit.json` exists. In that case `skill` is `None`, so the
    applied-skill rows are not run.
  - `expected_reports()` adds `("kit", "brand-creator kit build --yes")` when a kit exists.
  - `rows()` adds `kit:file`: fail when any path in the `kit` report's `outputs` is missing or has another sha256 (the detail names up
    to 4 and says "edited by hand: change the brand project and run `brand-creator kit build --yes`"); pass otherwise. A kit report
    without `outputs` gives a fail row that says so, never a crash.
  - `rows()` adds `kit:state`: skipped ("not verified") when the kit report passed and its `adapter_state_sha` or `kit_sources_sha`
    differs from now.
  - `applied_skill.py`: when `kit.json` exists in the skill folder, exit 2 before writing, with "this project's brand skill is a kit
    (kit.json): run `brand-creator kit build --yes`".
- **Tests:**
  - `test_check_fails_a_kit_file_edited_after_the_build` (m)
  - `test_check_says_not_verified_when_the_brand_changed_after_the_kit` (m): `mutate` FACTS.md.
  - `test_the_applied_skill_command_hands_over_to_the_kit` (f)
  - `test_the_kit_is_searched_by_the_cascade` (f): `check --cascade "<an Acme token value>"` lists a hit under
    `.claude/skills/acme-brand/brand/`.
  - The existing `test_adapters.py` applied-skill tests stay green.
- **Docs:**
  - CONTRACT.md `### kit`: what `check` gates (`report:kit`, `kit:file`, `kit:state`). `### applied-skill`: the hand-over.
  - `09-qa.md`: extend the `applied-skill --yes` row ("a project whose skill is a kit: exit 2, names `kit build --yes`") and the
    `kit build --yes` row ("`check`: `kit:file`, `kit:state`"). Cite the tests.
  - The `check.py` docstring bullet: "... BRAND.md, DESIGN.md, the applied skill and the brand kit as generated files".
  - CHANGELOG: extend the kit bullet: "`check` fails a kit file edited by hand and says when the brand changed after the kit."
- **Verify:** `-k "kit or applied_skill or cascade"`; `tests/test_skills.py`; the full suite.
- **Done when:** the new rows behave as tested, and every applied-skill and cascade test is green.

### G3-06 fontcheck names each font's family, weight and style

- **Roadmap:** 13 (fonts). **Depends on:** none.
- **Files:** `scripts/fontcheck.py`, `scripts/CONTRACT.md` ("fontcheck, fonts and outline-glyphs"), `tests/test_fontcheck.py`,
  `CHANGELOG.md`.
- **Do:** The `licence:<font>` row gains three fields: `family` (name ID 16, else name ID 1, else the file stem), `weight` (OS/2
  `usWeightClass`, else 400) and `style` (`italic` when OS/2 `fsSelection` bit 0 or `head.macStyle` bit 1 is set, else `normal`). The
  status and detail of the row do not change.
- **Tests:** `test_the_licence_row_names_the_family_weight_and_style_of_the_file` (f). The fixture font is
  `tests/fixtures/fonts/TestFont-subset.ttf`, read by hand: family `Inter`, weight 400, style `normal`.
- **Docs:** one CONTRACT sentence. CHANGELOG Changed: "`fontcheck` names each font's family, weight and style in its licence row."
- **Verify:** `-k licence_row`; `tests/test_fontcheck.py`.
- **Done when:** the test passes and fontcheck's existing tests are green.

### G3-07 Kit fonts: OFL copied with the licence, others listed; snippets/fonts.css

- **Roadmap:** 13. **Depends on:** G3-04, G3-06.
- **Files:** `kitlib.py`, `scripts/kit.py`, CONTRACT.md `### kit`, `09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - For each `.ttf`, `.otf`, `.woff` or `.woff2` in `assets/fonts/`, copy it to `brand/assets/fonts/<file>` only when both of these
    hold:
    - `assets/_checks/fontcheck.json` exists, is current (`_common.stale_inputs` is empty), and has a `licence:assets/fonts/<file>` row
      whose `recognised` is `SIL Open Font License (OFL)` and which carries `family`.
    - A licence text in `assets/fonts/` contains "SIL OPEN FONT LICENSE" (any case). The licence text is a file named `OFL*`,
      `LICENSE*` or `LICENCE*` with no extension or with `.txt` or `.md`. Each such file is copied along, once.
  - Any other font is listed in `kit.json` `fonts.not_copied`, with one of these reasons:
    - "no current fontcheck report: run `brand-creator fontcheck`, then `kit build`"
    - "the fontcheck report reads no licence for it"
    - "licence: <recognised>; only OFL fonts are copied (a default you may change): copy it into a product yourself, under its own licence"
    - "OFL by its name table, but no OFL licence text in assets/fonts/: add the font's OFL.txt"
    - "the fontcheck report has no family name: run `brand-creator fontcheck` again"
  - `snippets/fonts.css` is written when one font or more is copied, and is sorted by path. It opens with the comment
    `/* generated by brand-creator from assets/fonts/ and the fontcheck report; paths are relative to this file */`. Each copied font
    gets an `@font-face` with `font-family: "<family>"`, `src: url("../brand/assets/fonts/<file>") format("<woff2|woff|truetype|opentype>")`,
    `font-weight: <weight>` and `font-style: <style>`. Nothing else is set: no value is invented.
  - Row `kit:fonts`: pass when every font is copied. Warn when one is not copied for its licence. Skipped (the build writes the rest
    and exits 3) when there is no current fontcheck report. No fonts means no row.
  - Report inputs add the font files and the fontcheck report. `sources.fonts` hashes them.
- **Tests** (put `TEST_FONT` and `tests/fixtures/fonts/OFL.txt` into `acme/assets/fonts/`, then `fontcheck --lang en --no-platform`):
  - `test_an_ofl_font_is_copied_with_its_licence_and_gets_a_font_face` (f): the exact `@font-face` text is written out in the test.
  - `test_a_font_whose_licence_is_not_ofl_is_listed_and_not_copied` (m): `mutate_json` the report row's `recognised` to
    `Apache License`.
  - `test_without_a_current_fontcheck_report_no_font_is_copied_and_the_kit_is_not_verified` (f): exit 3, the kit written, no font in
    it.
  - `test_an_ofl_font_without_its_licence_text_is_not_copied` (m): `mutate` every "SIL Open Font License" in the copied OFL.txt.
- **Docs:** CONTRACT `### kit` fonts paragraph. `09-qa.md` kit build row: "a font not copied: warn; no current fontcheck report: not
  verified". CHANGELOG: "Open-licence (OFL) fonts go into the kit with their licence; any other font is listed, never copied."
- **Verify:** `-k "font and kit"`; the full suite.
- **Done when:** the four tests pass.

### G3-08 rules.json and facts.json

- **Roadmap:** 13. **Depends on:** G3-04, and group 1's `qa/rules.json` `page` block.
- **Files:** `kitlib.py` (`rule_id(text)`, `g4_rules(project)`, `known_rule_ids(project)`), `scripts/kit.py`, CONTRACT `### kit`,
  `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - `rule_id`: strip `(rule)`, NFKD-fold to ASCII (`ł` becomes `l`), lower-case, take the first six words, and join with `-`.
    Repeats get `-2`, `-3` in BRAND-STATE order.
  - `known_rule_ids(project)` returns the G4 slugs, `page:<id>` for each `qa/rules.json` `page.rules[].id`, and `site:<id>` for each
    `site/site.json` choice tagged `rule` (only once `sitedata` exists; before that, none).
  - `rules.json`: `{"schema": 1, "edition": ..., "g4": [{"id", "text"}], "downscale": {"accent_min_px", "accent_rule_max_size", "from":
    "qa/rules.json" | "plugin proposal"}, "bands": [{"mark": null | id, "name", "max_px", "drawing": "brand/<path>"}], "pairs": [{"fg",
    "bg", "kind", "min", "light", "dark"}], "forbidden": [...], "page": <the page block of the project's own qa/rules.json file,
    verbatim, only when that file has one>}`. Group 1 adds `page` to `qa_rules.DEFAULTS`, so `qa_rules.load()` always returns
    one: read the file itself (or `rules["_from_file"]`), never the merged defaults.
    The ratios come from `adapt.pairs`, rounded to 2 decimals. The JSON is written with `indent=2`, `ensure_ascii=False` and a trailing
    newline.
  - `facts.json`: `{"schema": 1, "facts": [{"fact", "value", "source", "confirmed"}]}` from `adapt.public_facts`.
  - Both are generated and listed in the kit section.
- **Tests:**
  - `test_rules_json_lists_the_g4_rules_with_ids_and_the_pairs_with_their_ratios` (m): `mutate` two `(rule)` bullets into
    BRAND-STATE's `Rules (G4)` section. The expected ids are written out by hand, for example `the-mark-keeps-its-clear-space`.
  - `test_a_rule_in_polish_gets_an_ascii_id_and_two_alike_get_a_number` (m): use "(rule) Znak zawsze na jasnym tle" for
    `znak-zawsze-na-jasnym-tle`.
  - `test_facts_json_holds_the_public_facts_and_never_a_contact_row` (f).
  - `test_the_page_block_of_qa_rules_reaches_rules_json_unchanged` (m): `mutate_json` a `page` block of group 1's shape into
    `qa/rules.json`.
- **Docs:** CONTRACT `### kit` (both files, the rule-id rule). CHANGELOG: extend the kit bullet ("the rules and facts as data").
- **Verify:** `-k "rules_json or facts_json or ascii_id"`; the full suite.
- **Done when:** the tests pass.

### G3-09 Motion files in the kit

- **Roadmap:** 13. **Depends on:** G3-04.
- **Files:** `kitlib.py`, CONTRACT `### kit`, `09-qa.md`, `tests/test_kit.py`.
- **Do:**
  - When `motion/motion.json` exists, copy it. Copy `motion/SPEC.md` when it exists.
  - When motion is `on` and `motion/proof.json` exists, copy the `page` file of each `"type": "page"` case to `brand/<its path>`. A
    page outside the project exits 2; a missing page exits 1.
  - `sources.motion` hashes these files.
- **Tests:**
  - `test_a_brand_that_moves_gets_its_motion_spec_and_demo_page_in_the_kit` (f): write `motion/motion.json` as `test_adapters.py`'s
    `put_spec(on_spec())` does. Acme already has `motion/demo.html` and `motion/proof.json`.
  - `test_a_brand_where_nothing_moves_gets_only_its_reason` (f).
  - `test_a_proof_page_outside_the_project_stops_the_build` (m): `mutate_json` a page case to `../outside.html`.
- **Docs:** the CONTRACT paragraph. The 09-qa kit build row: "a proof page outside the project (exit 2) or missing (exit 1)". No
  CHANGELOG entry beyond the kit bullet ("and the motion spec and demo").
- **Verify:** `-k "motion and kit"`; the full suite.
- **Done when:** the tests pass.

### G3-10 snippets/logo.html: the logo per theme

- **Roadmap:** 13. **Depends on:** G3-04.
- **Files:** `kitlib.py`, CONTRACT `### kit`, `tests/test_kit.py`.
- **Do:**
  - For every `assets/logo/<name>.svg` that does not end in `-dark` and has a `<name>-dark.svg` twin, write two `<img>` lines with the
    classes `brand-logo brand-logo--light` and `brand-logo brand-logo--dark`. A file with no twin gets one `<img class="brand-logo">`.
    The `alt` is the brand name. Paths are relative to the snippet (`../brand/assets/logo/...`). Files are sorted by name, and a
    `<!-- <name> -->` line goes before each.
  - A `<style>` block mirrors how `tokens.css` switches theme (`scripts/build_tokens.mjs`). Light shows by default.
    `:root[data-theme="dark"]` shows dark. Under `@media (prefers-color-scheme: dark)`, `:root:not([data-theme="light"])` shows dark.
    No size, colour or spacing is set.
  - The first line is `<!-- generated by brand-creator: the logo in light and dark, switched as tokens.css switches them; paths are relative to this file -->`.
- **Tests:**
  - `test_the_logo_snippet_pairs_each_mark_with_its_dark_twin_and_switches_like_tokens_css` (f): the expected `<img>` lines for
    `mark.svg` and `mark-dark.svg` are written out. Both selectors are asserted present in the snippet and in the kit's `tokens.css`.
  - `test_a_mark_without_a_dark_twin_is_shown_in_both_themes` (f): `mark-animated.svg`.
- **Docs:** the CONTRACT sentence. No CHANGELOG entry beyond the kit bullet.
- **Verify:** `-k logo_snippet`; the full suite.
- **Done when:** the tests pass.

### G3-11 snippets/on-ground.css from the declared grounds

- **Roadmap:** 13. **Depends on:** G3-04, and group 1's ground roles (`tokens.json` `grounds`).
- **Files:** `kitlib.py`, CONTRACT `### kit`, `tests/test_kit.py`.
- **Do:**
  - First read how group 1's code landed: CONTRACT "Token sources" (the `grounds` extension) and `build_tokens.mjs`. G1-10 writes
    the grounds into `tokens.json` only (`tokens.css` gets no per-ground scope), so the kit writes the snippet. If the landed code
    does scope grounds in `tokens.css` after all, stop and ask the lead.
  - Write `snippets/on-ground.css`, only when `tokens.json` `grounds.named_by_owner` starts with a `YYYY-MM-DD` date (the
    owner named the grounds). While it is still a proposal, write no snippet. Row `kit:grounds` (info) then says "the grounds are a
    proposal until the owner names them", because the model never guesses.
  - The first listed ground is the page ground, and its five roles are the base variables. Each other listed ground gets one rule:
    `[data-ground="<ground without color.>"] { background-color: var(<ground var>); <base text var>: var(<its text var>); ... }` for
    text, action, on-action, focus and border.
  - Variable names come from how `tokens.css` names tokens (`color.x` becomes `--color-x`; confirm in `build_tokens.mjs`), never made
    up.
  - A ground with a `null` role is left out of the snippet and named in `kit:grounds` (warn). Group 1's contrast rows own
    completeness; this only refuses to write half a scope.
- **Tests:**
  - `test_each_named_ground_gets_a_scope_that_maps_the_page_roles_to_its_own` (m): `mutate_json` a second ground and a dated
    `named_by_owner` into the semantic light source, then `tokens`. The expected CSS is written out by hand.
  - `test_grounds_that_are_still_a_proposal_get_no_snippet` (f).
  - `test_a_ground_with_a_missing_role_is_left_out_and_named` (m).
- **Docs:** the CONTRACT sentence. CHANGELOG: extend the kit bullet ("ready-made snippets: fonts, the logo per theme and text on each
  of your grounds").
- **Verify:** `-k ground`; the full suite.
- **Done when:** the tests pass.

### G3-12 The owner files: scaffolded once, never overwritten

- **Roadmap:** 13. **Depends on:** G3-04.
- **Files:** `templates/kit/EXTENDING.md`, `templates/kit/voice.md`, `templates/kit/visual.md`, `templates/kit/golden-rules.md`,
  `templates/kit/recipes/web-page.md` (a stub `# Web page` here; G3-13 writes the text), `kitlib.py`, `scripts/kit.py`, CONTRACT
  `### kit`, `09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - Each template is written into the kit only when its path is absent. It is never overwritten and never moved.
  - Placeholders `{{brand}}` and `{{skill}}` are filled in one pass. An unknown `{{...}}` exits 2 and writes nothing.
  - `kit.json` `owned` records each owner file's sha256 at build time, and `content_sha` covers them, so an owner edit moves the
    version at the next build. Row `kit:owned` (info): "<k> owner files scaffolded this run, <m> kept as they are".
  - `EXTENDING.md` (complete, no fill markers): what is generated and what is the owner's, and how to extend (new recipes under
    `recipes/`, new folders of your own; never edit a generated file; brand changes go into the brand project, then `kit build`). Also
    how a product repository's copy is updated (`/brand-creator:brand-adopt`, `kit status`), the version, the tags `[rule: <id>]` and
    `[example]`, and the rule that a value cites a token or a rule or is tagged an example.
  - `voice.md`, `visual.md`, `golden-rules.md`: a heading with `{{brand}}`, one sentence on what belongs there, and one
    `[[fill: ...]]` marker. The marker text has no square brackets, for example `[[fill: up to ten rules, each tagged with a rule id
    from rules.json or as an example]]`.
- **Tests:**
  - `test_the_first_build_scaffolds_the_owner_files_once` (f)
  - `test_an_owner_file_is_never_overwritten_and_its_change_moves_the_version` (m)
  - `test_a_deleted_owner_file_is_scaffolded_again` (f)
  - `test_the_kit_scaffolds_keep_their_placeholder_guard` (m): use the `plugin_copy` fixture and `mutate` a template to hold
    `{{nope}}`. Exit 2, nothing written.
- **Docs:** CONTRACT `### kit` (the owned part). 09-qa kit build row: "a scaffold with a placeholder this version does not know (exit 2,
  nothing written)". CHANGELOG: extend the kit bullet ("your own parts: recipes, voice, visual and golden rules, never overwritten").
- **Verify:** `-k "owner or scaffold"`; the full suite.
- **Done when:** the tests pass.

### G3-13 The web-page recipe: steps only

- **Roadmap:** 14. **Depends on:** G3-12, group 1's page check (the command and the sample list), and group 2's
  `page-layouts.json`.
- **Files:** `templates/kit/recipes/web-page.md`, `tests/test_skills.py`.
- **Do:** Write seven numbered steps, with no value in them. Each step is a short paragraph:
  1. The visitor's job: name the one job a visitor comes to this page for, and the material at hand (facts, photos, data). Start
     there, never from a list of sections.
  2. References: the brand's reference pages (`reference-pages/`, when the kit has them) and the layout reference that fits the job
     (brand-creator's `page-layouts.json`; each layout is named after what the visitor came to do). Take structure and rhythm from
     them, never another site's look.
  3. Tokens: colour, type, spacing and motion come from `brand/assets/tokens/tokens.css` (`var(--...)`) and `rules.json`. A value the
     tokens lack is asked for, never invented.
  4. Hero first: build the hero alone, in light and dark, at a phone and a desktop width. Nothing else until it holds.
  5. Page check: run the brand's page check on it, both tiers, from the brand project. For a page in a product repository, use
     `brand-creator page-check --from <the product's folder> <page> --project <the brand project>`, or `--url
     http://localhost:<port>/<path>` for the product's own local server. Fix every brand-rule failure; fix or argue each reflex
     warning.
  6. Cold read: someone who did not build it gets fixed inputs (the page, the brief line, the visitor's job) and answers with a
     verdict first, ship or fix, then the reasons.
  7. Before publishing: mark sample content with `data-sample="<label>"`. The page check lists every sample (its `page:samples`
     row); each needs the fact that must replace it. A claim with no FACTS row stays a sample or goes.

  Then: "The other pages follow the same steps." The file opens with `# Web page` and one line: "Steps only. The brand's values live
  in the tokens and rules.json; a line you add that pins a value cites a token or a rule, or is tagged `[example]`."
- **Tests:** `test_the_web_page_recipe_is_steps_only_with_no_values` (f, static, no data dir needed) in `tests/test_skills.py`:
  `tests/test_kit.py` has a module-level `pytestmark` (requires_setup, requires_node) that a test inside it cannot escape. It checks: seven numbered steps in this order (by their
  keywords), no number with a unit, no hex colour, no ratio, no `[[fill`, and the words `[data-sample]` and `page-check` present.
- **Docs:** none beyond the template. CHANGELOG: extend the kit bullet ("a web-page recipe that starts from the visitor's job, builds
  the hero first and checks it against the brand").
- **Verify:** `-k web_page_recipe`.
- **Done when:** the test passes.

### G3-14 `kit check`, part 1: files, links, fill markers, versions, sources, owner files

- **Roadmap:** 13. **Depends on:** G3-04 to G3-12.
- **Files:** `kitlib.py`, `scripts/kit.py` (subcommand `check`), `scripts/adaptlib/gates.py`, CONTRACT.md (a new `### kit check`
  subsection and `kit-check` in the tool names), `09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:** `kit check` writes report `kit-check`. Its inputs are every file under the kit folder plus the kit's sources, so any change
  makes it stale. No kit exits 2: "no kit in this project: `brand-creator kit build --yes` (opt-in at G5)". The rows:
  - `kit:files` fails when:
    - a path in `kit.json` `generated` is missing or has another sha256;
    - `kit.json` is not the bytes the `kit` report recorded;
    - a file in a generated folder is not listed (the detail says "move it to recipes/ or a folder of your own").
    With no `kit` report: skipped.
  - `kit:links` checks every relative link, so each resolves to an existing file inside the kit: `](target)` in `.md`, `src=`, `href=`
    and `srcset=` in `.html`, `url(...)` in `.css`. Fragments, `?query`, `http:`, `https:`, `mailto:` and `data:` are ignored.
    Failures: "points outside the kit: it will not resolve in a product repository", an absolute path, or a missing file. The first 6
    are listed as `<file>:<line> -> <target>`.
  - `kit:fill` fails on any `[[fill` in a text file, as `<file>:<line>`.
  - `kit:versions` fails unless SKILL.md holds `Kit version <kit.json version> (kit.json).` exactly once, and `kit.json` `edition`
    equals BRAND-STATE `approved_edition` ("the kit is of edition X, the brand is at Y: run `kit build --yes`").
  - `kit:plugin` warns when `plugin_version` differs from the running plugin.
  - `kit:sources` is skipped when `kitlib.sources(project)` differs from `kit.json` `sources`, naming the keys that changed and "run
    `kit build --yes`".
  - `kit:owned` warns when an owner file's sha256 differs from `kit.json` `owned`: "changed since the last build: `kit build --yes`
    records it and moves the version on".
  - `gates.expected_reports()` adds `("kit-check", "brand-creator kit check")` when a kit exists.
- **Tests:** add a helper `fill_owned(kit)` that `mutate`s each `[[fill: ...]]` into tagged plain text.
  - `test_a_fresh_kit_fails_on_its_fill_markers_until_the_owner_files_are_filled` (m)
  - `test_a_link_that_leaves_the_kit_fails` (m): add `[mark](../../../assets/logo/mark.svg)` to `visual.md`.
  - `test_a_generated_file_edited_or_a_file_added_to_a_generated_folder_fails_kit_check` (m)
  - `test_the_version_in_skill_md_must_be_the_one_in_kit_json` (m)
  - `test_a_kit_of_an_older_edition_fails_kit_check` (f)
  - `test_a_brand_change_after_the_build_makes_kit_check_not_verified` (m)
  - `test_check_asks_for_kit_check_once_a_kit_exists` (f)
  - `test_a_demo_page_whose_files_are_in_the_kit_has_no_dead_link` (f): the Acme demo with motion on.
- **Docs:** CONTRACT `### kit check` (every row and the exit codes). A new 09-qa row `| \`kit check\` | \`kit-check\` | ... |`. CHANGELOG
  Added: "`brand-creator kit check` proves the kit is whole: every link resolves inside it, no fill marker is left, the versions
  agree, and it says when the brand changed after the kit was built."
- **Verify:** `-k "kit_check or fill_markers or leaves_the_kit or version"`; `tests/test_skills.py`; the full suite.
- **Done when:** the tests pass and `check` expects `kit-check`.

### G3-15 `kit check`, part 2: tags and values

- **Roadmap:** 13 and 14. **Depends on:** G3-14, G3-08.
- **Files:** `kitlib.py`, `scripts/kit.py`, CONTRACT `### kit check`, `09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - `kit:tags`: every bullet line (`- ` or `* `) outside code fences in `recipes/**/*.md`, and every bullet or numbered line in
    `golden-rules.md` and `visual.md`, carries `[example]` or `[rule: <id>]`. Numbered steps in `recipes/` need no tag. A
    `[rule: <id>]` must be one of `kitlib.known_rule_ids(project)` (D12: a G4 slug, `page:<id>` or `site:<id>`). It fails with
    `<file>:<line>` and "untagged" or "unknown rule id <id>". The generated `reference-pages/*/notes.md` are checked by the same
    rule; their tags come from `site/site.json`, so a failure there means the record and the kit disagree.
  - `kit:numbers`: in the same files, inside code fences too, every value needs a citation on its line. A value is a number followed
    by a unit (`px`, `rem`, `em`, `ms`, `s`, `%`, `vh`, `vw`, `svh`, `dvh`, `ch`, `fr`, `deg` or `pt`), a ratio like `4.5:1`, a hex
    colour, or `rgb(`, `hsl(` or `oklch(`. A citation is `[example]`, a known `[rule: <id>]`, or a token reference that exists:
    `var(--name)` declared in the kit's `tokens.css`, or `{dotted.path}` present in the kit's `tokens.json`. An unknown token
    reference fails too.
- **Tests:**
  - `test_an_untagged_rule_in_golden_rules_fails_and_a_tagged_one_passes` (m)
  - `test_a_rule_tag_must_name_a_rule_the_kit_knows` (m)
  - `test_a_value_in_a_recipe_needs_a_token_a_rule_or_the_example_tag` (m): add "- Hero padding 48px" and get a fail; add
    `[example]` and get a pass.
  - `test_a_token_reference_must_exist_in_the_kit_tokens` (m)
  - `test_numbered_steps_need_no_tag_but_their_values_do` (m)
- **Docs:** the CONTRACT rows. Extend the 09-qa `kit check` row. CHANGELOG: extend the kit check bullet ("and that every value in your
  recipes cites a token or a rule, or says it is an example").
- **Verify:** `-k "tag or value or token_reference or numbered_steps"`; the full suite.
- **Done when:** the tests pass.

### G3-16 The approved reference pages go into the kit

- **Roadmap:** 15. **Depends on:** G3-14, G1-13 (page check, `pagecheck.report_tool`), G2-04 (`capture`), G2-13 (`site
  approve`, `sitedata`).
- **Files:** `kitlib.py` (`reference_pages(project)`), `scripts/kit.py`, CONTRACT `### kit`, `09-qa.md`, `tests/test_kit.py`, a
  fixture `tests/fixtures/kit/site/` (one small approved page `start` and its `site.json`, in group 2's format; use the page id
  `start`, never `home`: a page folder named `home` puts the personal-path needle (slash, home, slash) into a shipped file and fails
  the personal-path test), `CHANGELOG.md`.
- **Do:**
  - When `site/site.json` exists, `sitedata.validate_site(project)` must return no problem. Otherwise `kit build` exits 1 before
    writing anything, quoting the first three problems.
  - Every page in `pages` needs a current, passing page-check report (`assets/_checks/<pagecheck.report_tool("site/<id>/index.html")>.json`,
    imported from `scripts/pagelib/pagecheck.py`; `kit.py` adds `scripts/pagelib` and `scripts/boardlib` to `sys.path`) and a current
    `capture.json` in `site/<id>/shots/` (`stale_inputs` empty). Otherwise `kit build` exits 1 before writing anything, naming the
    page and the command to run (`page-check site/<id>/index.html` or `capture site/<id>/index.html`).
  - Copy into `brand/`, at project paths: `site/<id>/index.html` and every file under `site/<id>/`, `shots/` included (no
    `cold-review.md` or report files are there after `site approve`). Also copy every project file the page loads from outside its
    folder: `src`, `href`, `poster` and `srcset` in the HTML, `url(...)` in `<style>`, `style` attributes and local `.css` files, one
    level deep. Skip `http(s):`, `data:`, `mailto:`, `tel:` and `#...`; `site approve` and the page check already refuse network
    loads. A path outside the project exits 2.
  - Write `reference-pages/<id>/notes.md` (generated) with:
    - the page id as title;
    - the layout (the `page-layouts.json` name for its id, or `own:<word>`), with the words "structure only";
    - `Approved: <site.json approved>`;
    - links to `../../brand/site/<id>/index.html` and to each still;
    - `## Choices`, one bullet per choice whose `pages` names this page (or all), written `- <text> [rule: site:<id>]` for a rule
      (with "decided in <source>") or `- <text> [example]`.
  - `kit.json` `reference_pages` records, per page, the id, the kit path, `source_sha` (from `site.json`), the page-check report's
    `inputs_sha` and `capture.json`'s inputs sha. Row `kit:reference-pages`: pass with the count, or info "no approved reference
    pages".
- **Tests:**
  - `test_an_approved_reference_page_and_what_it_loads_are_copied_with_notes` (f)
  - `test_a_reference_page_without_a_passing_page_check_stops_the_build` (m): `mutate` the page so group 1's check fails it (a colour
    that is not a token), then `page-check`, then `kit build`. Exit 1, nothing written.
  - `test_a_reference_page_that_loads_a_file_outside_the_project_stops_the_build` (m)
  - `test_each_choice_of_a_reference_page_is_tagged_in_its_notes` (f)
  - `test_a_site_record_that_does_not_validate_stops_the_build` (m)
- **Docs:** CONTRACT `### kit`. The 09-qa kit build row. CHANGELOG: extend the kit bullet ("the reference pages you approved, with
  their screenshots and which choices are rules and which are examples").
- **Verify:** `-k reference_page`; the full suite.
- **Done when:** the tests pass.

### G3-17 Reference pages go stale when the tokens or rules change

- **Roadmap:** 15. **Depends on:** G3-16.
- **Files:** `kitlib.py`, `scripts/kit.py` (check), CONTRACT `### kit check`, `09-qa.md`, `tests/test_kit.py`.
- **Do:** `kit check` writes a row `kit:reference-page:<id>` for each page in `kit.json`:
  - Skipped ("not verified: the tokens or rules changed since this page was checked: run `page-check site/<id>/index.html` and
    `capture site/<id>/index.html`, then `kit build --yes`") when the page's page-check report or its `capture.json` is stale, or
    either `inputs_sha` differs from the recorded one.
  - Skipped ("the page changed in the project since the kit was built: `kit build --yes`") when `site/site.json`'s `sha256` for the
    page differs from `source_sha`.
  - Fail when the page-check report is current and failing.
  - Pass otherwise.

  `lib/stale.py` does not change. The kit is downstream of the pack, so the kit records its own sources (say so in CONTRACT). Group
  2's `check` rows (`site:pages`, `site:stills`) keep gating the pages in the project; these rows gate the kit's copies.
- **Tests:**
  - `test_a_token_change_makes_a_reference_page_not_verified` (m)
  - `test_a_reference_page_approved_again_makes_its_kit_copy_not_verified` (m)
  - `test_stills_taken_again_make_the_kit_copy_not_verified` (m)
  - `test_a_failing_page_check_fails_the_reference_page_row` (m)
- **Docs:** CONTRACT. Extend the 09-qa `kit check` row. CHANGELOG: extend the kit check bullet ("and marks a reference page stale when
  the tokens or rules change").
- **Verify:** `-k reference_page`; the full suite.
- **Done when:** the tests pass.

### G3-18 `kit status --repo`: is the copy in a product repository current?

- **Roadmap:** 16. **Depends on:** G3-14.
- **Files:** `kitlib.py` (`compare(kit_dir, installed_dir)`), `scripts/kit.py` (subcommand `status`), CONTRACT (a new
  `### kit status` subsection), `09-qa.md`, `tests/test_kit.py`, `CHANGELOG.md`.
- **Do:**
  - `kit status --repo DIR[=LABEL]... [--json]` reads `<DIR>/.claude/skills/<slug>-brand/` and writes nothing, neither in the
    repository nor in the project.
  - Per repository it prints one of these states:
    - `not installed`
    - `current (version V)`: every generated file and `kit.json` byte-identical
    - `not current`: the installed version and the project version, then the generated files that differ, are missing or are left
      over from an older kit
  - It also prints "owner files that differ (kept on update)" and a copy list. The copy list is every generated file to copy, then
    the owner files the repository lacks, as paths relative to the kit folder.
  - Without `--repo`, it reads every repository that has a `kit` row in `adoption.json` (after G3-19). With none: exit 2, "pass
    --repo".
  - Refusals (exit 2): no kit in the project; a folder that does not exist; the project itself or a folder inside it; the user's home
    folder (`Path.home()`); any path inside `~/.claude` ("the kit goes into one product repository at a time, never into a global
    skills folder").
  - It proves it read only: a list of files, sizes and modification times of the installed folder before and after, as the survey
    does. A difference exits 1.
  - Exit 0 when every repository is current, 1 otherwise.
- **Tests:**
  - `test_kit_status_says_not_installed_and_lists_what_to_copy` (f)
  - `test_a_byte_copy_of_the_kit_is_current` (f): copy the folder with `shutil.copytree`.
  - `test_a_changed_generated_file_in_the_repository_is_not_current_and_owner_changes_are_kept` (m)
  - `test_an_older_installed_version_is_not_current_and_names_both_versions` (m): `mutate_json` the installed `kit.json`.
  - `test_kit_status_refuses_a_global_skills_folder_the_home_folder_and_the_project` (f): set `HOME` to a tmp folder through `bc(...,
    env=)`.
  - `test_kit_status_reads_and_never_writes_the_repository` (f)
- **Docs:** CONTRACT `### kit status`. A new 09-qa row `| \`kit status --repo <dir>\` | none | ... |`. CHANGELOG Added: "`brand-creator
  kit status --repo <folder>` tells whether a product repository's copy of the kit is current, and what to copy."
- **Verify:** `-k kit_status`; `tests/test_skills.py`; the full suite.
- **Done when:** the tests pass.

### G3-19 Adoption category `kit`

- **Roadmap:** 16. **Depends on:** G3-18.
- **Files:** `scripts/adaptlib/adoptdata.py`, `scripts/adoption.py`, a golden fixture `tests/fixtures/adoption/no-kit.json` plus
  `no-kit.ADOPTION.md`, `tests/test_adoption.py`, `tests/test_kit.py`, CONTRACT `### adoption`, `09-qa.md`, `CHANGELOG.md`.
- **Do:**
  - Before editing `adoptdata.py`, record the golden fixture. Survey `tests/fixtures/target-repo` in a scratch project with the
    tests' `NAMES` and `COLOURS`, the project and the repository as siblings, and `BRAND_CREATOR_TODAY=2026-10-17`. Save its
    `adoption.json` and the `ADOPTION.md` that `adoptdata.render(doc, "<name>")` gives. Commit both as test fixtures. They are the
    oracle that later renders stay the same bytes.
  - `CATEGORIES` gains `("kit", "Brand kit")`, placed before `change`. `SURVEYED` leaves out `kit` and `change`.
  - `adoption add --repo LABEL --kit` adds the row `{category: "kit", file: ".claude/skills/<slug>-brand/", find: "kit.json", change:
    "Copy the brand kit: every generated file byte for byte and the owner files the repository does not have, by the list `brand-creator
    kit status --repo <path>` prints; it must then say current. Never into a global skills folder.", lines: []}`. It is pinned like
    any row. `--file`, `--find` and `--change` are refused with `--kit`.
  - Refusals (exit 2): no kit in the project; a repository that already has a kit row; an unknown label.
  - In ADOPTION.md, a kit row's Lines cell reads "the whole folder".
  - `adoption status` prints the `kit status` state of each kit row's repository after the counts. It reads only, and its exit code
    stays 0.
- **Tests:**
  - `test_adoption_md_of_a_list_without_a_kit_row_is_the_bytes_it_was` (f, in `test_adoption.py`): render the golden json and compare
    with the golden md.
  - `test_a_kit_row_is_added_for_a_surveyed_repository_and_a_survey_leaves_it_alone` (f, in `test_kit.py`, markers `requires_setup`
    and `requires_rg`)
  - `test_a_kit_row_needs_a_kit_in_the_project_and_is_one_per_repository` (f)
  - `test_adoption_status_says_whether_each_kit_copy_is_current` (f)
  - The existing pin tests stay green.
- **Docs:** CONTRACT `### adoption`: a `kit` line in the category table and the `--kit` flag. Extend the 09-qa `adoption status / add /
  verify / render` row. CHANGELOG: "The adoption list can hold a brand kit row per repository."
- **Verify:** `-k "adoption or kit_row"`; the full suite.
- **Done when:** the golden test and the new tests pass.

### G3-20 brand-adopt, the agents and the adopt workflow install the kit

- **Roadmap:** 16. **Depends on:** G3-19.
- **Files:** `skills/brand-adopt/SKILL.md`, `skills/brand-creator/references/phases/11-adoption.md`, `agents/brand-implementer.md`,
  `agents/brand-reviewer.md`, `workflows/adopt.js`, `tests/node/workflows.test.mjs`, `CHANGELOG.md`.
- **Do:**
  - Skill §2 (Survey): "When the project has a kit and the owner wants it in a repository: `adoption add --repo <label> --kit`."
  - Skill §3 (Apply): "A Brand kit row: run `kit status --repo <path>` and copy exactly the files of its copy list (`mkdir -p` then
    `cp`, one file at a time; an owner file the repository already has is never overwritten), then `kit status --repo <path>` must say
    current. Never copy into `~/.claude/skills` or any global folder. The kit is not committed."
  - Skill §4 (Review): "`kit status --repo <path>` exit 0 is the byte comparison of a kit row."
  - `11-adoption.md`: the same in Method steps 5 and 6, and an Enforcement bullet.
  - `brand-implementer.md` and `brand-reviewer.md`: one bullet each.
  - `adopt.js`: the implementer prompt gains one line with the kit copy rule (including "never into a global skills folder"). The
    reviewer prompt gains "for a Brand kit row, `brand-creator --data "<data>" kit status --repo <path> --project "<project>"` must exit
    0; quote it". The RULES line does not change.
- **Tests:** a node test, `test("adopt tells the implementer how a kit row is copied and the reviewer how it is checked", ...)`, which
  asserts both prompt lines. `fleet-plan --check` passes. The `tests/test_agents_workflows.py` tests stay green.
- **Docs:** no CONTRACT change. CHANGELOG: "`/brand-creator:brand-adopt` installs the brand kit in a repository you name, on your
  branch, and checks the copy byte for byte."
- **Verify:** `node --test tests/node/workflows.test.mjs`; `bin/brand-creator --data "$BRAND_CREATOR_DATA" fleet-plan --check`;
  `tests/test_agents_workflows.py` and `tests/test_skills.py`.
- **Done when:** the node and static tests pass.

### G3-21 The opt-in at G5, and the manual page for the kit

- **Roadmap:** 13 to 16 (docs). **Depends on:** G3-20.
- **Files:**
  - `skills/brand-book/SKILL.md` ("Approval (G5) and the opt-in files")
  - `skills/brand-creator/references/phases/10-book.md` (a new section, `## The brand kit (opt-in at G5)`, with a Contents entry, and
    the Gate line)
  - `skills/brand-creator/SKILL.md`: only the command-table row "BRAND.md, DESIGN.md and a per-brand skill (opt-in at G5)", which sits
    after `## Round mechanics`
  - `docs/manual/use/use-your-brand-kit.md` (new how-to) and `docs/manual/README.md` (the index)
  - `docs/manual/reference/what-it-makes.md`, `docs/manual/reference/glossary.md` (a "Brand kit" row),
    `docs/manual/use/apply-the-brand-to-your-product.md` (a section, "Put the brand kit in a repository"),
    `docs/manual/reference/what-it-never-does.md` (it never installs the kit globally and never commits it)
  - `docs/internals/manual-checks.md` (a row and section, "The kit in a product repository session", never run)
  - `CHANGELOG.md`
- **Do:**
  - brand-book G5: the one question also offers the brand kit (recommend it when the brief lists a site or product repositories).
    On a yes: `kit build` (the plan), then `kit build --yes`, then fill the owner files with the owner (voice from the tone chapter
    and the FACTS voice rows, visual from the book, golden rules citing rule ids), then `kit check` until it passes. A later brand
    change means `kit build --yes` again.
  - Add a pitfall: "Editing a kit file under `brand/`, `snippets/` or `reference-pages/`: change the brand project, then rebuild."
  - Do not touch the orchestrator's top section. `test_orchestrator_top_holds_the_core_within_the_compaction_budget` must still pass.
  - The manual page is a how-to in the manual's voice, with no gate codes and no maintainer commands:
    - what the kit is, and what is yours to change;
    - how to ask for it ("when you approve your brand files");
    - how to fill your parts;
    - how to put it in a product repository (brand-adopt);
    - how to check a copy is current;
    - what to do when the brand changes;
    - a "If something goes wrong" table.
- **Tests:** existing tests only. Optionally add a needle test that brand-book's G5 section names `kit build --yes`.
- **Docs:** this task is the docs. CHANGELOG: one line pointing at the new manual page.
- **Verify:** `tests/test_skills.py`; the docs checks.
- **Done when:** the docs checks and `tests/test_skills.py` pass.

### G3-22 The kit test as an optional step after the kit is written

- **Roadmap:** 17. **Depends on:** G3-21, group 1's page check, group 2's cold-review prompt fragment.
- **Files:** `skills/brand-creator/references/phases/10-book.md` (a subsection, `### Kit test (optional)`, under the kit section),
  `templates/kit/EXTENDING.md` (one paragraph), `docs/manual/use/use-your-brand-kit.md` (a short "Test your kit" section),
  `CHANGELOG.md`.
- **Do:** The steps, in order:
  1. One builder in scratch, outside the project, makes a hero and one other piece from the kit alone.
  2. `page-check --from <the scratch folder> <page> --project <the brand project>` scores them, both tiers. A cold read with
     group 2's cold-review prompt fragment (`references/prompt-fragments.md`) answers ship or fix first.
  3. Gaps flow back to the tokens, the G4 rules, FACTS and the owner files. A generated kit file is never patched.
  4. Record "kit test <date>: page-check <status>; gaps: ..." in BRAND-STATE.md Notes, and list open gaps in "Still open".

  It runs in-thread by default. One builder agent may run only after the fleet gate (agent count, models, size, cost, a yes). No
  workflow is added.
- **Tests:** none beyond the existing link and structure tests.
- **Docs:** the above. CHANGELOG: "After the kit is written you can ask for a kit test: a hero built from the kit alone and checked
  against the brand."
- **Verify:** the docs checks; `tests/test_skills.py`.
- **Done when:** the checks pass.

### G3-23 A billed eval case for the kit test

- **Roadmap:** 17. **Depends on:** G3-22, group 1's page check (`page-check` must be a real subcommand: `test_evals.py` checks that the subcommands
  graders name exist).
- **Files:** `evals/kit-test-hero/` (new: `prompt.md`, `case.yaml`, `scaffold.sh`, `graders/*.md`), `evals/_shared/fixture.sh`
  (`fx_kit`), `evals/_shared/acme-kit/` (a committed snapshot of the Acme kit), `tests/tools/regen_eval_kit.py` (new),
  `tests/test_kit.py`, `tests/test_evals.py` (a `PLAN_BULLETS` entry: `test_evals.py` asserts the case folders equal its values),
  `docs/internals/evals.md` (the "Last results" paragraph names the cases not yet run).
- **Do:**
  - `fx_kit` copies Acme, writes the state with G5 recorded and the edition approved, and copies `evals/_shared/acme-kit/` into
    `.claude/skills/acme-brand/`. It also copies the kit's `brand/assets/tokens/` into `assets/tokens/`, because the page check needs
    the built tokens. It also writes a pristine copy and `.eval-verify/verify.sh`, which `cmp`s every kit file against the pristine
    copy, as `fx_adoption` does.
  - The prompt asks to build the hero of Acme's home page in `kit-test/hero.html` from the kit alone and to check it. It ends with
    the harness note that asks the run to execute `bash .eval-verify/verify.sh > verify-result.txt`.
  - Graders:
    - a file regex `var\(--` on `kit-test/hero.html`
    - a file regex for the mark file
    - `tool_used` Bash `brand-creator\b.*\bpage-check\b`, min 1
    - a regex over `last_message` for `before publishing|data-sample` (flags i)
    - a regex over `verify-result.txt` that nothing in the kit changed
    - one `llm` grader: PASS when the reply reports the page check's result and the gaps the kit showed; FAIL when it claims a pass
      without running the check, or edits kit files
  - `max_turns` is 40 or more.
  - The snapshot is the output of `kit build --yes` on the Acme golden pack, with the owner files filled by `fill_owned`'s text.
    `tests/tools/regen_eval_kit.py` rebuilds it into the folder. It needs a set-up data dir and is run by hand when the test below
    fails.
- **Tests:** `test_the_eval_kit_snapshot_is_what_kit_build_writes_for_acme` (f, `requires_setup`) compares the trees by bytes. The
  `tests/test_evals.py` static checks must pass for the new case.
- **PLAN_BULLETS** entry: `"kit test: a hero built from the kit alone is page-checked and the kit is left unchanged":
  "kit-test-hero"`.
- **Snapshot and releases:** `kit.json` holds `plugin_version`, which changes at every release; the snapshot test compares
  `kit.json` with `plugin_version` dropped on both sides (and says so), or the next version bump would fail it.
- **Docs:** `docs/internals/evals.md`: add `kit-test-hero` to the cases not yet run. `manual-checks.md` "Behaviour evals": a note that the next run
  covers the new case. No CHANGELOG entry (evals are not user-facing).
- **Verify:** `tests/test_evals.py`; `-k eval_kit_snapshot`; `bash evals/kit-test-hero/scaffold.sh` in a scratch folder (it must
  finish offline).
- **Done when:** the static eval tests and the snapshot test pass. The billed run is a manual check, never claimed here.

### G3-24 ADR: a redesign records the site's wiring

- **Roadmap:** 18. **Depends on:** G3-02 (numbering).
- **Files:** `docs/adr/ADR-0012-a-redesign-records-the-sites-wiring.md`, `docs/adr/README.md`.
- **Do:**
  - Status `accepted`, Date 2026-10-30.
  - Context: a redesign can drop links, form field names, handlers, test hooks, ids and scripts that the product, its tests or its
    analytics depend on, and nothing in the adoption list would notice.
  - Decision:
    - `adoption wiring` records six kinds, from source and from rendered loopback pages, before and after.
    - The record lives in `adoption.json` `wiring`; the key `kept` is taken.
    - A loss is acceptable only as `dropped: <reason>` in the owner's words.
    - The reviewer's live `--compare` fails an unrecorded loss.
    - `check` fails a recorded after-scan that lost wiring nobody dropped.
    - Scripts only read the repository and prove it.
  - Consequences: regex extraction is approximate (dynamic routes, generated ids), so a noisy item is dropped with a reason. It is a
    record, not a proof that the site works; the repository's own tests stay the proof.
  - Credit (idea only, reimplemented; no text or code copied): Hallmark (MIT), commit 4f6a46c, its `references/redesign.md` ("The
    wiring") and its before-and-after record of what a redesign must keep.
- **Tests:** none.
- **Docs:** the ADR README row.
- **Verify:** the docs checks.
- **Done when:** the docs checks pass.

### G3-25 `adoption wiring --before` and `--after`, from source

- **Roadmap:** 18. **Depends on:** G3-24.
- **Files:** `scripts/adaptlib/wiring.py` (new), `scripts/adoption.py`, `scripts/adaptlib/adoptdata.py`, `bin/brand-creator` (the
  adoption help line), CONTRACT (a new `### adoption wiring` subsection and `adoption-wiring` in the tool names), `09-qa.md`,
  `tests/fixtures/target-site/` (new synthetic site), `tests/test_adoption_wiring.py` (new, `requires_rg`), `CHANGELOG.md`.
- **Do:**
  - `wiring.py` (standard library). It reads files whose extension is one of `.html .htm .jsx .tsx .js .ts .mjs .vue .svelte .astro
    .erb .ejs .hbs .handlebars .njk .liquid .twig .php .mdx`. It removes HTML comments first. Values are quoted strings or
    `{...}` expressions, balanced to three levels and whitespace-squashed. Items are `kind:value`, with the value capped at 120
    characters. The six kinds:
    - `link`: the values of `href`, `to`, `action` and `formAction`. Skip an empty value or `#`. Skip the attribute when the tag (the
      name after the last `<` before it) is `link`, `script`, `base`, `use`, `image` or `style`.
    - `field`: `name="..."` on any tag except `meta`, `link`, `a`, `iframe`, `param`, `slot`, `map` and `object`, plus the string
      argument of `register("...")`.
    - `handler`: the attribute names `on[A-Z]\w*` and `on[a-z]+` with `=`, `@<event>=`, `v-on:<event>=` and `on:<event>=`. The item
      is `handler:<attr>=<value>`.
    - `hook`: the values of `data-testid`, `data-test`, `data-cy`, `data-qa`, `data-track*`, `data-analytics*`, `data-event*` and
      `data-gtm*`. The item is `hook:<attr>=<value>`.
    - `id`: a static `id="..."` with no braces or spaces.
    - `script`: the `src` of `<script>`, with the query and a leading `./` taken off.

    Write these patterns fresh; never copy Hallmark's.
  - `adoption.py wiring`:
    - `--repo LABEL` must be surveyed, else exit 2.
    - `--before` or `--after`, one of them.
    - The files are listed with ripgrep as the survey lists them (`.gitignore` honoured, `.git` out), leaving out every path the
      survey's `keep_reason(path, [])` keeps (lock files, history, licences, minified files, dist and build folders, vendor).
    - The read is proven read-only: a file list with sizes and modification times, before and after. A change gives row
      `read-only:<label>` fail and exit 1, and nothing is stored.
    - The store is `doc["wiring"][<repo id>][before|after] = {"date", "head", "files", "items": {item: [up to 5 files]}}`. `--before`
      over an existing before record exits 1 ("the before record is the baseline: pass --again to replace it"). `--after` with no
      before exits 2.
    - It writes both files through `write_both`.
    - Report `adoption-wiring`: `read-only:<label>`, `wiring:<label>` (info: the count per kind) and `wiring:scope` (info: the files
      read, and how many the keep rules left out).
    - No ripgrep exits 3, with the survey's install hint.
  - `adoptdata.py`: `empty()` gains `"wiring": {}`. `TARGET_KEYS` gains `"wiring"`, so the cascade never counts a repository's values
    as leftovers. `verify()` checks that each wiring repository id is a known repository and that items are lists of strings. Render
    does not change yet.
  - The fixture site: `index.html` (links, a form with fields, ids, a `data-testid`, an inline `onclick`, a `<script src>`),
    `src/Header.jsx` (`onClick={...}`, `to="/pricing"`, `data-cy`), `src/Signup.vue` (`@submit`, `v-model`, `name`), `dist/bundle.js`
    (must be kept out), and `package-lock.json`.
- **Tests:**
  - `test_the_wiring_of_a_site_is_read_from_its_source_with_every_kind` (f): the expected item set is written out by hand.
  - `test_the_wiring_scan_never_edits_the_repository_and_proves_it` (f)
  - `test_generated_and_vendored_files_are_not_read_for_wiring` (f)
  - `test_a_before_record_is_kept_unless_asked_again` (f)
  - `test_after_needs_a_before` (f)
  - `test_the_wiring_record_is_not_searched_by_the_cascade` (f)
  - The golden ADOPTION.md test of G3-19 stays green.
- **Docs:** CONTRACT. A new 09-qa row `| \`adoption wiring --repo <label> --before|--after\` | \`adoption-wiring\` | ... |`. Write the
  pipe as `\|` inside the code span, or say "before or after" in words. The bin help gets one line under `adoption survey|status`.
  CHANGELOG Added: "Redesigning a site? `brand-creator adoption wiring --before` records its links, form fields, handlers, test hooks,
  ids and scripts, so nothing is lost by accident."
- **Verify:** `-k wiring`; `tests/test_static.py`; `tests/test_skills.py`; the full suite.
- **Done when:** the tests pass and the golden render is unchanged.

### G3-26 `--compare`, `--drop`, the `check` row and the ADOPTION.md section

- **Roadmap:** 18. **Depends on:** G3-25.
- **Files:** `scripts/adoption.py`, `scripts/adaptlib/adoptdata.py` (render and `PLACEHOLDERS`), `templates/ADOPTION.md` (the
  placeholder only), `scripts/adaptlib/gates.py` (a row), CONTRACT, `09-qa.md`, `tests/test_adoption_wiring.py`, `CHANGELOG.md`.
- **Do:**
  - `--compare` rescans the repository now, plus the recorded pages after G3-27, and writes nothing. It prints the lost items (in
    before, not in the scan, not dropped) with the files they were in, the dropped items with their reasons, and the count of new
    items. Exit 1 when a loss is not recorded, 0 when none is, 2 with no before record.
  - `--drop "ITEM::REASON"` (repeatable). The item must be in the before record and the reason must not be empty; otherwise exit 2.
    It is stored in `wiring[<id>]["dropped"]`.
  - In `gates.rows()` (or the adoption block of `check`), each repository with both records gets `adoption:wiring:<label>`. It fails
    when the after record lost an undropped item, naming up to 5, and passes otherwise. With only a before record it is an info row,
    "record --after when the redesign is applied".
  - `templates/ADOPTION.md`: one line `{{wiring}}` between `{{rows}}` and `## How this list is applied`, with blank lines around it.
    `PLACEHOLDERS` gains `wiring`. With no wiring the fill is empty, and the existing `\n{3,}` collapse gives the old bytes.
  - With wiring, the fill is `## Wiring kept`, then per repository one line of counts per kind (before and after), and one line per
    lost item, `- <item>: dropped, <reason>` or `- <item>: lost, not recorded`. Every line holding a repository value ends with the
    target-repo marker (`adoptdata.MARK`).
- **Tests:**
  - `test_compare_lists_what_a_redesign_lost_and_fails_until_it_is_dropped_with_a_reason` (m)
  - `test_compare_reads_the_repository_now_and_writes_nothing` (f)
  - `test_a_drop_needs_an_item_of_the_before_record_and_a_reason` (f)
  - `test_check_fails_a_recorded_after_that_lost_wiring_nobody_dropped` (m)
  - `test_adoption_md_shows_the_wiring_and_marks_its_lines_as_the_repository` (f)
  - `test_adoption_md_of_a_list_without_a_kit_row_is_the_bytes_it_was` (G3-19) stays green.
- **Docs:** CONTRACT. Extend the 09-qa wiring row, and the `check` row with `adoption:wiring:<label>`. CHANGELOG: extend the wiring
  bullet ("`--compare` says what a redesign lost; a loss is fine only when you record why").
- **Verify:** `-k "wiring or adoption"`; the full suite.
- **Done when:** the tests pass.

### G3-27 Rendered pages in the wiring record

- **Roadmap:** 18. **Depends on:** G3-26, group 1's page check (`render.mjs` with `scripts/pagelib/` and its loopback URL check).
- **Files:** `scripts/pagelib/wiring.mjs` (new), `scripts/render.mjs` (a subcommand `wiring <url>`), `scripts/adoption.py` (`--page`),
  CONTRACT, `09-qa.md`, `tests/node/wiring.test.mjs` (new), `tests/test_adoption_wiring.py`, `CHANGELOG.md`.
- **Do:**
  - `render.mjs wiring <url>` takes loopback only (`http` or `https` on `127.0.0.1`, `localhost` or `[::1]`): call
    `isLoopbackUrl` from `scripts/lib/_common.mjs` (G1-13). Reuse the URL check
    group 1 wrote for `page-check --url`; never write a second one. Anything else exits 2: "the wiring is read from your own local
    server".
  - It launches Chromium as `shot` does (reuse group 1's shared launch if it exists), loads the URL, and waits for load (bounded at
    15 s). It prints JSON `{kind: [values]}` from the DOM, read with `getAttribute` and never with resolved URLs:
    - `link`: `a[href]`, `area[href]`, `form[action]`, `[formaction]`
    - `field`: `[name]` on `input`, `select`, `textarea` and `button`
    - `id`: `[id]`
    - `hook`: the data attributes of G3-25
    - `script`: `script[src]`
    - `handler`: inline `on*` attributes only, as `handler:<attr>=<value>`
  - Missing Chromium or a page that does not load exits 3.
  - `adoption wiring --page <url>` is repeatable, with `--before`, `--after` and `--compare`. Items carry the source
    `rendered:<path of the url>`. The before record stores `pages`, and `--compare` renders them again. A page that cannot be read
    stops the run with exit 3 and stores nothing. Row `wiring:pages`: info, which says that listeners added by script are not
    visible in the DOM and are read only from source.
- **Tests:**
  - Node: `test("wiring: a page on 127.0.0.1 gives its links, fields, ids, hooks, scripts and inline handlers", ...)` (f), served from
    `node:http` on port 0. `test("wiring: a URL that is not loopback is refused with exit 2", ...)` (f).
  - pytest: `test_a_rendered_page_adds_its_wiring_and_a_server_that_is_gone_is_not_verified` (f), with `http.server` on `127.0.0.1`
    port 0 in a thread. Loopback is not the network the suite must avoid; say so in the test's docstring.
- **Docs:** CONTRACT. Extend the 09-qa wiring row. CHANGELOG: extend the wiring bullet ("and from your own local server's pages").
- **Verify:** `node --test tests/node/wiring.test.mjs`; `-k wiring`; the full suite.
- **Done when:** the tests pass.

### G3-28 The wiring in brand-adopt, the agents, the workflow and the manual

- **Roadmap:** 18. **Depends on:** G3-27.
- **Files:** `skills/brand-adopt/SKILL.md`, `skills/brand-creator/references/phases/11-adoption.md`, `agents/brand-implementer.md`,
  `agents/brand-reviewer.md`, `workflows/adopt.js`, `tests/node/workflows.test.mjs`,
  `docs/manual/use/apply-the-brand-to-your-product.md`, `CHANGELOG.md`.
- **Do:**
  - Skill §2: for a redesign of an existing site, run `adoption wiring --repo <label> --before [--page <local URL>]` before any change
    (read only, no gate).
  - Skill §3: the implementer ends with `--after`.
  - Skill §4: the reviewer runs `--compare`, and any unrecorded loss fails the review. A drop is the owner's decision, recorded with
    `--drop "<item>::<the owner's reason>"`.
  - `adopt.js`: the REVIEW schema gains `wiring_losses: string[]`. The reviewer prompt names `adoption wiring --repo <label>
    --compare`. The `next` text says that a review with wiring losses is not ready for a commit ask.
  - Apply the same to `11-adoption.md` (Method and Enforcement) and to the two agents.
  - The manual page gets a short section, "Redesigning a site: keep what it is wired to".
- **Tests:** a node test that the reviewer prompt names `--compare` and the schema has `wiring_losses` (f). `fleet-plan --check`
  passes.
- **Docs:** as listed. CHANGELOG: "A brand-adopt review fails a redesign that lost wiring you did not agree to drop."
- **Verify:** `node --test tests/node/workflows.test.mjs`; `fleet-plan --check`; `tests/test_agents_workflows.py`; the docs checks.
- **Done when:** the tests and the docs checks pass.

### G3-29 Mutation ledger groups and the full run

- **Roadmap:** all. **Depends on:** G3-01 to G3-28.
- **Files:** `tests/mutation_ledger.py`, `docs/internals/development.md` (the ledger's list of groups).
- **Do:** Add the group `kit` with these breaks:
  - hand-edit detection off
  - `[[fill` not looked for
  - a link outside the kit accepted
  - a value accepted with no citation
  - an unknown rule id accepted
  - `kit status` comparing sizes instead of bytes
  - owner files overwritten

  Add the group `wiring` with these breaks:
  - `--compare` ignoring losses
  - `"wiring"` missing from `TARGET_KEYS`
  - the read-only proof skipped
  - a non-loopback URL accepted

  Each break names the tests that must catch it.
- **Tests:** the ledger itself.
- **Docs:** the development page's list of groups.
- **Verify:**
  - `BRAND_CREATOR_DATA=<set-up data dir> uv run --no-project --with-requirements tests/requirements.txt python tests/mutation_ledger.py --group kit`
    (the ledger needs the data directory; its usage line says so)
  - `BRAND_CREATOR_DATA=<set-up data dir> uv run --no-project --with-requirements tests/requirements.txt python tests/mutation_ledger.py --group wiring`
  - the full suite
  - `BRAND_CREATOR_DATA=<set-up data dir> tests/run-all.sh --smoke`
  - the docs checks
  - `claude plugin validate plugins/brand-creator --strict` (from the repository root)
- **Done when:** every break is caught, the suite is at the baseline, the smokes pass and the docs checks pass.

## Owner checkpoints (not implementer tasks)

1. G3-01's baseline run, by the owner with the lead, in-thread and from scratch copies. Best before G3-04.
2. After G3-21: a kit build on a scratch copy of the pilot brand, on the owner's say-so, to compare with the owner's hand-made kit.
   The pilot brand's own project is not written.
3. After G3-28: the first wiring record on the owner's site, `--before`, read only, before any redesign.
4. The billed eval run (G3-23) and the manual-check rows: run and dated by the owner, never claimed by the suite.

## Risks

- The names taken from the group 1 and group 2 plans may change when their code lands: the page-check command and report, the
  `grounds` shape, `site/site.json`, `sitedata`, `capture`, and `scripts/pagelib/`. The affected tasks (G3-08, G3-11, G3-13, G3-16,
  G3-17, G3-22, G3-23, G3-27) start by reading the landed code.
- Group 1 gives G4 lines no ids, so the kit makes its own (D12). If group 1 or 2 later adds ids, two id schemes would exist; the kit
  should then switch to theirs in one change.
- Resolved in the cross-group review: the group 1 and group 2 plan files no longer hold absolute personal paths or client names
  (`dev/specs/` is scanned by `tests/test_static.py::test_no_personal_paths_or_email_addresses_in_shipped_files`), and group 2
  uses the page id `start` in every shipped example, so no shipped path holds a `home` folder.
- The orchestrator's top section is near its 20,000-character budget (19,850 at most after G2-16). This group changes only the
  command-table row after
  `## Round mechanics`.
- `templates/ADOPTION.md` and the applied skill's bytes are what existing projects are checked against. Only empty-when-unused
  placeholders are added, and golden tests hold the old bytes.
- A fresh kit fails `kit check` until the owner files are filled, so `check` fails right after the opt-in. That is intended: the kit is
  not done until its owner parts are.
- The eval's kit snapshot drifts whenever the tokens builder or the applied-skill text changes (group 1 changes both). The snapshot
  test says so, and `tests/tools/regen_eval_kit.py` rebuilds it.
- Regex wiring extraction is approximate. Noise is handled by `--drop` with a reason, and the repository's own tests stay the proof.
- Font licences come from the name table: a hint, not legal advice. Only OFL with its licence text is copied.
- Three groups write the same `## [Unreleased]` section and the same `09-qa.md` table, so merges need care. Add, never reorder.
- This plan file sits in a folder the static tests and docs checks scan: no personal path, no e-mail address, no client name.
- The suite needs a set-up data directory. Without one most kit tests skip, and a skip is not a pass.
- Size: 29 tasks. Most are small, and G3-04, G3-14 and G3-25 are the largest. If time runs short, G3-23 (the billed eval) and G3-27
  (rendered wiring) can follow in a later release without breaking anything before them.
