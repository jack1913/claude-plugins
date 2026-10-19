# onboard-repo — detection guidance

What `onboard-repo` detects before stamping. Everything here is **reported to
the operator and confirmed** — never baked silently. Detection results become
the REPO SPECIFICS bakes described in `stamping.md`.

## Version homes (for `changelog-release`)

Find the authoritative files that carry a real `version`:
- Common homes: `package.json`, `.claude-plugin/plugin.json`, `pyproject.toml`,
  `Cargo.toml`, `VERSION`, `*.gemspec`.
- **Exclude** `node_modules/`, `vendor/`, `dist/`, `build/`, and workspace
  mirrors — a `version` there is not authoritative.
- Require a plausible version — SemVer, or date-shaped (evidence for the
  versioning scheme below); ignore files where `version` is absent or a range.
- Confirm the final list with the operator.

**Monorepo mode:** decide how versions move together and bake it:
- `independent` — each package versions on its own;
- `linked` — packages share a version but are released together;
- `fixed` — one version across the repo.

## Versioning scheme (for `changelog-release`)

Default to `semver`. Propose `calver` only on evidence — date-shaped versions in
the version homes, date-shaped `CHANGELOG.md` headings or tags — or when the
operator asks for it, and then confirm the exact format, the timezone that decides
the date, and the tag pattern. Check the proposed format against each version
home's own rules before baking it. Where npm, Cargo or another SemVer-only manager
reads it, a rendered version must match the SemVer core grammar (CalVer uses no
pre-release or build part). Render it for a date with a single-digit month and day
(e.g. 2026-01-05), where a padded part shows; the check prints `False` for a
two-part version or a leading-zero part, which would break installs:

```bash
python3 -c "import re,sys; print(bool(re.fullmatch(r'(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}', sys.argv[1])))" <v>
```

PEP 440 (`pyproject.toml`) accepts two-part versions but drops leading zeros
(`2026.09` reads back as `2026.9`); a plain `VERSION` file has no parser. On
`False` for a SemVer-only home, offer a valid format (e.g. `YYYYMM.D.N`) or a
separate manifest form (e.g. `YYYYMMDD.N.0` beside `YYYYMMDD.N` headings and tags)
before the plan is confirmed. A new format must sort above the last release, part
by part numerically (`202609.29.1` sorts below `20260929.0`); when it would not,
offer only the manifest form. Write the format in the template's token notation
(§4b: `YYYY`/`YY` year, `MM`/`DD` zero-padded, `M`/`D` unpadded, `N` the counter),
not calver.org's.

## GitHub Release (for `changelog-release`)

Propose `ci` when a workflow already publishes releases
(`rg -n 'gh release create|action-gh-release' .github/workflows`), naming its file,
job and trigger condition; otherwise bake `none`. Offer `manual` only when the
operator asks for releases without a workflow.

## Release script + version-sync test

Look for `scripts/release.*` (shell/JS/etc.) and any test that asserts the
manifests stay in sync (e.g. a "versions match" test). If both exist, bake a
note so `changelog-release` **suggests then delegates** to the script rather than
editing manifests directly.

## Doc layout + extractors (for `update-docs`)

- Note which of `README.md`, `CLAUDE.md`, `docs/**` exist.
- **IA shape** — note which IA dirs already exist (`docs/manual/`, `docs/internals/`,
  `docs/adr/`, `docs/archive/`) and whether `AGENTS.md` is the index. If the repo
  has existing docs pages, classify each with `references/rubric.md` (four tiers →
  the four dirs) so the scaffold + adoption steps know what to create vs. move.
- **Index doc** — detect which file is the repo's always-loaded thin index; it is
  **not always `CLAUDE.md`**. A repo following the AGENTS.md convention keeps the
  index in `AGENTS.md`, with `CLAUDE.md` a one-line `@AGENTS.md` import (or
  `GEMINI.md`, etc.). Rule: if `CLAUDE.md` is only an `@import` of another file,
  the **imported** file is the index; otherwise `CLAUDE.md` itself. Bake the
  resolved path as the `index doc` (see `stamping.md`) — the K-pointer baseline,
  the section→source seed, and the pointer bootstrap all target it, never a literal
  `CLAUDE.md`. **Never bootstrap a pointer index into an `@import`-only stub.**
- Infer a **route/CLI extraction command** only when there's a generic one to
  infer (e.g. a framework's route-list command). If none is obvious, leave it
  unset — route/CLI drift then stays in the report-only tier (do not guess an
  extractor). Note any caveat (needs a build; has a side-effect such as a
  `prebuild` hook that rewrites a generated file) so the bake records it.
- Seed the section→source SET map from the **index doc**'s existing pointers
  (cite-or-defer: only where the source verifies).

## Consumer surfaces (for the manual)

What §3.7 authors against — a **surface** is one topic the operator manual
must eventually cover.

- **Enumerate.** Walk `README.md`'s H2/H3 headings (`heading_slugs` gives each
  one's slug); each heading is one candidate surface, keyed by its slug.
- **Classify principal vs. niche by keyword rule**, mirroring `rubric.md`:
  - **principal** — the heading text matches
    `install|setup|quickstart|getting-started|usage|command|option|flag|config|safety|security|permission`,
    plus the repo's own primary workflow verbs (the actions a user actually
    runs day to day).
  - **niche** — the heading text matches
    `contributing|sponsor|license|changelog|badge|acknowledg|faq|roadmap|development`.
  - Anything unmatched defaults to principal (better to over-cover than
    silently drop a real workflow). **Operator override** is always
    allowed — show the proposed split and let the operator move a surface
    between tiers before it's confirmed.
- **Persist the confirmed split** to the committed coverage record,
  `docs/.onboard-coverage.json` — a JSON array of objects shaped
  `{surface, slug, tier, page, status}`, where `tier` is `principal` or
  `niche`, `page` is the authored page's path (or `null` before it's
  written), and `status` is `covered` or `deferred`. §3.7 reads and updates
  this file across authoring rounds; `check-docs --coverage` reads it too.

## Predecessor artifacts (by content, not name)

Run the helper and treat its JSON as candidates:

```
python3 "$SKILL_DIR/scripts/onboard.py" find-predecessors .claude
```

It scans `.claude/skills/*/SKILL.md` and `.claude/commands/*.md`, classifies
each by **content** (changelog vs docs-sync work), and excludes the canonical
names (`changelog-release`, `update-docs`). A bare `docs`/`changelog` artifact
whose body is unrelated is **not** returned. Show each `excerpt` to the operator
before proposing retirement (see `SKILL.md` step 4).

## Dependency ecosystem detection (for the `update-deps` question)

Run `deps-detect` on every default run (unless `--without update-deps`). Its
output serves two purposes: it tells the operator what was detected when
`SKILL.md` asks whether to stamp `update-deps`, and — if they accept — it
supplies the facts the model-in-the-loop needs to author that skill's REPO
SPECIFICS block:

```
python3 "$SKILL_DIR/scripts/onboard.py" deps-detect .
```

The verb scans the repo root for supported ecosystem manifests (stdlib-only;
no ecosystem CLIs required). Each detected ecosystem surfaces:

- **js/ts** — `package.json` (any root-level or workspace member). Manager:
  decided by the lockfile CLOSEST TO THE REPO ROOT — `package-lock.json` → `npm`,
  `pnpm-lock.yaml` → `pnpm`, `yarn.lock` → `yarn`; `npm` when none is present
  (bun stubbed). Root-closest on purpose: one legacy `package-lock.json` in a
  workspace member must not name the manager for a pnpm monorepo. Only lockfiles
  that EXIST are reported; workspace roots are every directory with a
  `package.json`.
- **php** — `composer.json` (any root-level or monorepo member). Manager:
  `composer`. Lockfiles: `composer.lock` siblings that exist. `tier0_rule` is
  `laravel` when an `artisan` file sits beside a manifest — the same shape as
  `expo` for js.
- **python** — a PEP 621 `pyproject.toml`, or a legacy `setup.py` / `setup.cfg`.
  Manager: decided by the root-closest lockfile — `uv.lock` → `uv`,
  `poetry.lock` → `poetry`, `pdm.lock` → `pdm`, `Pipfile.lock` → `pipenv`,
  `requirements.txt` → `pip`; `pip` when none is present. `tier0_rule` is
  `django` when a `manage.py` sits beside a manifest.
- **rust** — `Cargo.toml` whose `[workspace]` section declares `members`.
  Every workspace root is a separate ecosystem entry (a repo with two disjoint
  cargo workspaces yields two `rust` entries). Manager: `cargo`. Lockfiles:
  `Cargo.lock` next to each workspace root.
- **.NET** — `*.sln` or `Directory.Packages.props` (Central Package
  Management). Manager: `dotnet`. Lockfiles: none emitted by the verb in v1
  (the operator may record `packages.lock.json` paths when
  `RestorePackagesLockFile` is enabled).
- **swift** — `Package.swift` (pure-SPM) or `*.xcodeproj` (Xcode-SPM).
  Manager: `swift-package` (the verb emits this for both pure-SPM and Xcode-SPM;
  an XcodeGen app is operator-confirmed at stamp time). Lockfiles: `Package.resolved`
  (v3 JSON; may exist in multiple locations, some gitignored).

Every manifest walk applies a two-tier rule, tested relative to the repo root:

- **DEPENDENCY trees never supply a manifest** — `node_modules/`, `vendor/`,
  `.venv`/`venv`, `.tox`, `site-packages`. Those hold manifests belonging to other
  projects.
- **Build OUTPUT (`build/`, `dist/`, `target/`) supplies one only as a last
  resort** — consulted when the pattern matched nothing outside it. A manifest
  there is a *copy* of this repo's own, so counting it as a peer double-reports
  workspace roots (`cargo package` leaves a full crate, `[workspace]` section and
  all, under `target/package/`; a publishable subpackage ships a
  `dist/package.json`). But it is still this repo's manifest, so a repo whose
  **only** manifest lives there must not be reported as having no ecosystem.

If no supported ecosystem manifest is found, `deps-detect` exits non-zero — in
that case **don't ask the question at all** and don't stamp; report the skip
("no supported ecosystem found") so the operator knows why. Never silently stamp
a no-op skill.

### Verify-command discovery ladder (§8.2)

The model-in-the-loop assigns `verify_fast` and `verify_full` per ecosystem by
walking this ladder (in order; `verify_fast` prefers the fast read-only rungs,
`verify_full` prefers the full gate):

1. **justfile recipes** — `check` / `lint` / `ci` / `deny`
2. **CI workflow files** — `.github/workflows/*.yml` build/test jobs
3. **repo-local scripts** — `scripts/*.sh` (e.g. `xcbuild.sh` / `xctest.sh`)
4. **`package.json` scripts** — `"typecheck"` / `"test"` / `"lint"`
5. **ecosystem default** — `cargo check` / `cargo test`; `dotnet build` /
   `dotnet test`; `swift build` / `swift test`; `npm run typecheck` / `npm test`

Every verify gate must be **source-read-only**: use `--check` / `--lint` /
`--verify-no-changes` forms (never a format/rewrite command, which would break
baseline purity). Missing `verify_fast` at stamp time → prompt the operator;
still none → abort the stamp for that ecosystem. Missing `verify_full` → warn
and degrade to `verify_fast`-only for the final gate; do not abort.
