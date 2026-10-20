# onboard-repo — stamping guidance

How a stamped `.claude/skills/<name>/SKILL.md` is laid out, and what goes in each
REPO SPECIFICS block. `<X>` below is `TEMPLATE_VERSION` from
`scripts/onboard_lib.py`; `<date>` is today's date.

## File layout (two regions)

In order, top to bottom:

1. **Frontmatter** (`---` … `---`) — from the template. Part of the template
   region (regenerated on `--sync`).
2. **Provenance header** — a single HTML comment, verbatim (repos stamped before version 4
   say `from claude-configs`; both forms are accepted, and `--sync` takes the header from the current template):

   ```text
   <!-- stamped by onboard-repo v<X> from batbelt on <date>. The template region is regenerated on /batbelt:onboard-repo --sync (backup + diff shown first); the REPO SPECIFICS block is preserved. -->
   ```

3. **Template region** — the canonical skill body from
   `templates/<name>/SKILL.md`. Owned by the template; **overwritten on `--sync`**.
4. **REPO SPECIFICS block** — the per-repo bakes, between:

   ```text
   <!-- BEGIN REPO SPECIFICS (preserved on --sync) -->
   ... per-repo facts ...
   <!-- END REPO SPECIFICS -->
   ```

   **Carried forward verbatim on `--sync`.** Exactly one well-formed pair per
   file — `--sync` fails closed otherwise (`scripts/onboard.py check-markers`).

## Stamped gate script (`update-docs`, `update-rules`)

Both skills are stamped with a `scripts/` sibling holding **one file** —
`.claude/skills/<name>/scripts/check.py`, a plain copy of this skill's own. Without it
`update-docs` §7.6–§7.8 (coverage record, missing surface, the `check-docs` gate) and
`update-rules` §2 (`check-instructions`) name a tool the repo does not have, and the
gates would exist only in the plugin.

**Never copy `onboard.py`/`onboard_lib.py`.** They hold the one-shot onboarding verbs
(`preserve`, `settings-plan`, `run-*`, `deps-detect`, `convert-copilot`), which a skill
that runs for years must not ship. `check.py` is
stdlib-only and imports no sibling, so a single-file copy is sound; a test pins both
properties, because the copy silently depends on them.

It is copied **per consuming skill**, not shared from one place: a skill
directory that works standalone is the contract the stamped `SKILL.md` already keeps,
and a cross-skill relative path breaks the moment one skill is deleted or moved.

It is a **third category** of stamped file, and the distinction drives `--sync`:

| | Owned by | `--sync` behavior |
| --- | --- | --- |
| `SKILL.md` template region | the template | regenerated |
| `SKILL.md` REPO SPECIFICS | the repo | preserved verbatim |
| `scripts/check.py` | the template, **wholly** | **replaced outright** |

So do **not** run `preserve` on it: it has no markers, so the call fails
closed — correct, but useless. `diff` it, show the diff, replace on confirm. Drift
detection is likewise a plain `diff`, not `check-markers`.

Three consequences worth stating: the copy is **duplicated per onboarded repo**
(~1.9k lines), which is the cost of a repo that works standalone — the same trade the
stamped `SKILL.md` already makes; a repo stamped before it shipped simply has
none, so `--sync` **creates** the directory rather than diffing it; and a repo stamped
**before the split** has the old pair instead, which still works — `--sync` replaces it
with `check.py` and removes the two orphans, shown in the plan like any other change.

## REPO SPECIFICS schema — `changelog-release`

- **versioning scheme:** `semver` (the default — also what an absent field means),
  or `calver` with its exact format, the timezone that decides the date, and the tag
  pattern, plus a manifest form when it differs (e.g. `calver YYYYMM.D.N,
  Europe/Warsaw, tags YYYYMM.D.N` or `calver YYYYMMDD.N, UTC, tags YYYYMMDD.N,
  manifests YYYYMMDD.N.0`), in the template's token notation (`YYYY`/`YY` year,
  `MM`/`DD` zero-padded, `M`/`D` unpadded, `N` the counter — not calver.org's). A CalVer format
  must be valid SemVer wherever a SemVer-only package manager (npm, Cargo) reads it
  (no two-part versions, no leading zeros), or the bake gives the manifest form
  separately — the template's §4b explains the constraint.
- **version homes:** the confirmed authoritative paths (one per line).
- **monorepo mode:** `independent` | `linked` | `fixed`.
- **release-script delegation:** the script path + version-sync test, or `none`.
  When present, note that the script is **authoritative for the bump and the
  `[Unreleased]` entry format it parses** — the skill must read it for its EXACT
  trigger (a keyword substring, a heading, a label, or a conventional-commit
  parse) and write entries in that form, not apply its own §4a rule. Record the
  real trigger, not an assumed one.
- **dash punctuation:** `—` or `-` — mirror the existing top CHANGELOG entry.
- **changeset dir:** `.changeset/` if the repo uses Changesets, else `none`.
- **github release:** `none` (default — the template's §11 stays inert), `ci` naming
  the workflow file, job and condition that publish the tag and GitHub Release (e.g.
  `ci .github/workflows/release.yml job release, on push to main when the version
  has no tag`), or `manual` (the skill prints the `gh release create` command).
- **release announcement:** `none` (default — the template's §10 stays inert),
  or a bake naming the chat target, language(s), audience ordering, the
  upgrade-path line and a worked reference release.

## REPO SPECIFICS schema — `update-docs`

- **index doc:** the repo's always-loaded thin index — usually `CLAUDE.md`, but
  `AGENTS.md` where the repo follows that convention (a `CLAUDE.md` that only
  `@import`s another file resolves to the imported file; see `detection.md`).
  Every "CLAUDE.md" the template names — the §2 cap, §5 pointers, the bootstrap —
  targets THIS file, not a literal `CLAUDE.md`.
- **section→source map:** each doc section → a SET of verified sources
  (`file` + symbol/anchor preferred over a raw line number); seed only what
  verifies, leave the rest un-pointered.
- **surface enumerator:** how §7.7 finds the repo's real consumer surfaces to diff
  against the coverage record — the same source `detection.md` § "Consumer surfaces"
  used at onboarding (the `README.md` H2/H3 walk), plus any repo-specific command that
  lists them (a CLI `--help`, a route table). `readme-headings` when that walk is all
  there is; never invent an enumerator that needs a build this repo cannot run.
- **coverage record:** `docs/.onboard-coverage.json` when §3.7 authored the manual,
  else `none` — §7.6 is skipped entirely when absent (a repo with no contract has
  nothing to maintain). Record `none` honestly rather than naming a file that is not
  there; a stale bake would make every run report a missing contract.
- **route/CLI extractor:** the baked command, or `none` (report-only tier). Record
  any caveat — a command that needs a build, or one with a side-effect (e.g. a
  `prebuild`/`gen-version` hook that rewrites a generated file) — so `update-docs`
  runs it knowingly.
- **cross-surface reference integrity:** for a repo that ships agents/skills/docs
  citing a command surface, the surfaces to cross-check — e.g. "every `<cli>
  <verb>` an agent names must exist in the CLI usage/help; every skill it cites
  must exist under `<skills-dir>`". `none` if the repo has no such surface. (Agents
  have hallucinated non-existent verbs; this bake is what catches it.)
- **generated blocks:** names of `<!-- BEGIN GENERATED: <name> -->` tables.
- **K-pointer baseline:** record the truth — `established at onboard` **only if**
  the index-doc pointer bootstrap actually ran and produced verified pointers;
  otherwise `not established (legacy prose; the update-docs §2 cap stays engaged)`. Never claim
  `established` without having run the bootstrap (update-docs recounts pointers at
  runtime anyway, so a false claim only misleads the operator).
- **capture fence convention:** how a grounded `docs/manual/` page shows a command
  and its output. Recommended: the COMMAND in a ```` ```bash ```` fence with each line
  marked `$`, the OUTPUT in a separate ```` ```console capture=<slug> ```` fence whose
  lines are a verbatim, in-order subsequence of `docs/.onboard-captures/<slug>.txt`.
  Separate fences copy-paste cleanly; note that markdownlint's MD014 cannot model the
  split and is disabled per grounded page. Record the convention the repo actually
  uses — a single `text capture=<slug>` fence holding both is the older shape — so a
  later run converts pages consistently rather than mixing the two.
- **docs voice:** the tone `update-docs` enforces on `docs/manual/` pages —
  default "task-first, one-concept-per-page, scannable, operator-voiced; cite
  ADRs, don't inline rationale", or aligned to the README voice when that voice is
  docs-natural (Field Notes / Lab Notebook / Workshop / The Index). On defer, the
  task-first default is baked. (The README voice, by contrast, has no default —
  a deferred README voice records "no voice" and re-prompts on the first styling run.)

## REPO SPECIFICS schema — `update-rules`

- **instruction roots:** the directories to audit, normally
  `.claude/rules .claude/skills`. Record what actually exists — naming an absent
  directory makes every run report a usage error rather than a clean pass.
- **repo roots for citation resolution:** every base the repo's own files cite
  against, as repeatable `--repo-root` values. `.` alone for a flat repo; a repo whose
  rules cite both `AGENTS.md:21` (repo root) and `Domain/Models/Result.cs:7` (source
  root) needs **both**, or whichever convention loses is reported as unresolved. This
  is the single most common cause of false `UNRESOLVED_CITATION` findings.
- **linter coverage:** what the repo's linters/compiler/tests already enforce (e.g.
  `eslint` + `tsc`, `phpstan`, `ruff` + `mypy`), or `none`. §5 uses it to **reject**
  candidate rules: a constraint a linter already catches must not become a rule, since
  a rule costs context on every matching read and adds nothing.
- **creation-time constraints:** whether any rule's constraint applies while *creating*
  a file rather than reading one. Those need a one-line pointer in the index doc,
  because `paths:` fires on Read and never on Write. `none` if there are none.
- **known baseline (dated):** what `check-instructions` last reported, with the date —
  `clean` with the exact command, or each accepted finding by code and location with the
  command that re-derives it (e.g. an `UNGROUNDED_COUNT` whose number is re-counted by
  `rg -l ... | wc -l`, listing the value per date). A gate that records what it last
  said turns "passes" into "passes, and here is what changed since"; a run reporting
  anything beyond the baseline has found new drift. Update the line on every run,
  never by deleting a finding.

## REPO SPECIFICS schema — `update-deps`

Populated from `deps-detect` output + the model-in-the-loop's verify-ladder
walk. The model authors the prose from the JSON; `--sync` preserves it verbatim
via `preserve_repo_specifics`.

- **ecosystems:** one entry per detected ecosystem (`js`, `php`, `python`, `rust`,
  `dotnet`, `swift`), each with:
  - **manager** — `npm` | `pnpm` | `yarn` | `composer` | `uv` | `poetry` | `pdm` |
    `pipenv` | `pip` | `cargo` | `dotnet` | `swift-package` | `xcodegen`. For js the lockfile present beside the
    manifest decides it, so a pnpm repo is never told to run npm.
  - **workspaces** — `(root, lockfile)` pairs per detected workspace root, plus
    `shared_path_deps` (path-linked members that must be bumped together).
  - **`verify_fast`** — the confirmed fast read-only verify command
    (seconds to low-minutes; `null` until the operator provides one).
  - **`verify_full`** — the confirmed full-gate verify command (the repo's CI
    pipeline; `null` until provided).
  - **`tier0_rule`** — `expo` (js/Expo pinned-group tool), `laravel`
    (php, detected by `artisan` beside `composer.json`), `django` (python, detected by
    `manage.py` beside the manifest), or `none`.
  - **`cross_verify`** — `none` or a cross-compile gate (operator-opt-in,
    pre-merge only).
- **rollback recipe** — per-ecosystem, with the cache-invalidation step
  (rust `cargo check` / `cargo clean -p`; js `npm install` rebuilds
  `node_modules`; .NET `dotnet restore`; php `composer install` rebuilds
  `vendor/`; python `uv sync` (or `pip install -r`) rebuilds the virtualenv; swift DerivedData clean).
- **sources** — `[]` in v1 (per-dep source classification is a runtime adapter
  concern, deferred).

## CHANGELOG.md skeleton (write only if absent)

For a `calver` bake, end the preamble's sentence with the calendar format and a
rendered example instead of the SemVer clause — no calver.org link, whose `MM`
means an unpadded month — e.g. "…, and versions are calendar-based: `YYYYMM.D.N`
(e.g. `202609.29.0`)."

```text
# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
```

## Docs voice (authored pages, §3.7)

**Show-don't-tell:** lead a page with what running the thing actually produces,
not a paragraph asserting it works. Ground every claim — either it's captured
(a real command's output, committed under `docs/.onboard-captures/` and cited)
or it's explicitly labeled `illustrative` (a hand-built mock with no command
behind it) — never invented as if it were real. Every output block carries a
**provenance tag** in its fence info string: `capture=<slug>` pointing at the
committed capture it came from, or the literal word `illustrative`. A block
with neither tag is what the reviewer (`SKILL.md` §3.7) and `check-docs`'s
grounding checks exist to catch.

**Mock tables** carry the same tag as an HTML comment, because a markdown table
has no fence info string to put it in:

```markdown
<!-- illustrative -->
| Thread | Action |
|---|---|
| `file.php:42` | FIXED |
```

The marker scopes to the block directly beneath it and ends at the first blank
line **or the end of the enclosing fence**, so it cannot silence a whole file.
A marker QUOTED inside a fence (as in the example above) scopes to nothing at all —
otherwise this very page would have switched the check off for whatever followed it.
`check-instructions` then skips both `path:line` citations and numeric claims inside
that block — a mock report table is not asserting that `file.php` exists.

What counts as an **output block** is narrower than "any fence", so ordinary
instructions are never asked to prove provenance:

- **Source fences are exempt** — a `csharp`, `python`, `mermaid`, or `hcl` block
  is authored illustration, not something a command printed. Tagging it would
  force a falsehood.
- **A shell fence needs a tag only when it is a transcript** — a prompt line
  *and* a line that is not one, i.e. a command together with what it printed.
  A bare command list (`dotnet build` / `dotnet test`), with or without `#`
  comments, is authored instruction and stays untagged.
- **Known gap:** output pasted with no command and no prompt is exempt too.
  Telling it apart from a command list would need a regex guessing whether a
  line "looks like" a command, which also matches prose — so the reviewer, not
  the checker, catches that case.

## Index-doc pointer bootstrap

Generate a pointer index into the **index doc** (the resolved `CLAUDE.md` /
`AGENTS.md` from detection — never an `@import`-only stub) for existing sections —
**cite-or-defer**: emit a pointer only where the source verifies (a real
file/symbol); leave a section un-pointered rather than fabricate a `file:line`.
Touch surrounding prose minimally. If the index doc is an `@import` stub, **skip**
the bootstrap and record `not established` — the real index lives in the imported
file and is that file's to maintain.

## Restart notice (print after stamping)

```text
Skills stamped into .claude/skills/. Restart Claude Code (e.g. `claude --continue`) to load them.
```
