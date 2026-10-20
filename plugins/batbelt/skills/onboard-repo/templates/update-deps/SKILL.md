---
name: update-deps
description: Safely update project dependencies across js/ts, php, python, rust, swift, and .net with risk-tiered execution and a verify gate per tier. /update-deps --dry-run for report only.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Bash(git status:*), Bash(git diff:*), Bash(git checkout:*), Bash(git restore:*), Bash(npm:*), Bash(yarn:*), Bash(pnpm:*), Bash(cargo:*), Bash(swift:*), Bash(dotnet:*), Bash(composer:*), Bash(uv:*), Bash(pip:*), Bash(poetry:*), Bash(npx:*), WebFetch
argument-hint: "[--dry-run] [--ecosystem <js|php|python|rust|swift|dotnet>] [--tier <0|1|2|3>]"
---

# update-deps

Safely update project dependencies across js/ts, php, python, rust, swift, and .net.
**Applies changes by default** (the `--dry-run` flag runs discovery + baseline
only). The pipeline is ecosystem-agnostic; per-ecosystem mechanics live in the
adapter sections below. Per-repo facts (ecosystems, workspaces, verify commands,
Tier-0 rule, rollback recipe) come from the **REPO SPECIFICS** block at the
bottom of this file.

## 1. Universal pipeline

1. **Baseline capture** -- run `verify_fast` before any change; record stderr.
2. **Tiered bumps** -- per the tier table (§2); never bulk across tiers.
3. **Per-tier verify** -- `verify_fast` after each tier; only NEW stderr blocks.
4. **Rollback** -- `git checkout` manifests + lockfiles + the stamped cache step.
5. **Final verify** -- `verify_full` after all tiers complete.

The pipeline is per-ecosystem when more than one is present; the ordering is
Tier 0, then Tiers 1-3 by ecosystem (js first, then php, then python, then rust,
then swift, then dotnet -- ecosystem ordering is cosmetic; the verify gate already enforces
correctness).

## 2. Tier model

| Tier | Risk    | Meaning                                                | Gate                          |
|------|---------|--------------------------------------------------------|-------------------------------|
| 0    | None    | vendor/framework lockfile bumped via the group's own tool only. Conditionally populated; empty for php/python/rust/swift/dotnet. | `verify_fast`                 |
| 1    | Low     | patch (semver x.y.Z)                                   | `verify_fast`                 |
| 2    | Low-Med | minor (x.Y.z); pre-1.0 patch goes here                 | `verify_fast`                 |
| 3    | Medium  | major (X.y.z); pre-1.0 minor goes here                 | `verify_fast` + operator confirm |
| SKIP | High    | pinned beyond a group constraint / needs platform or SDK upgrade / **private-registry or private-git (needs auth / operator-managed)** | do not update                 |

**RESOLVE (SPM only).** An ecosystem with no per-package specific-version
primitive (SPM) has no T1/T2 "install @ version" move -- its within-range
updates are a single **resolve** step (`swift package update <pkg>` / `swift
package resolve --version <ver> <pkg>`), semantically "move to latest/specific
within range," not a specific-target pin. The T1 (patch) / T2 (minor) risk band
still applies; only the mechanics differ. See §3.

Carry-over rules: never `@latest` for T1/T2 (always the specific target, where
the ecosystem provides a per-package pin primitive -- npm `pkg@ver`, cargo
`--precise`, the .NET `<PackageVersion Version>` line; **SPM has none** -- its
within-range moves use the RESOLVE tier above); never the ecosystem's bulk
primitive across tiers (no `npm update` / `ncu -u` / `cargo upgrade`-all /
`--refresh-dependencies`); **workspace exception** -- one shared-dep manifest
line (`[workspace.dependencies]`, npm workspace root, `Directory.Packages.props`)
is one logical bump, not a bulk update, and the verify gate covers all affected
members.

## 3. Per-package-pin carve-out (SPM)

The "always specific version" rule holds where the ecosystem provides the
primitive (npm `pkg@ver`, cargo `--precise`, the .NET CPM `<PackageVersion
Version>` line). **SPM has no such primitive** -- `swift package update <pkg>`
takes a name only (latest-in-range); `swift package resolve --version` pins the
lockfile only and is non-durable and absent for Xcode-project deps. So for SPM,
within-range moves collapse to a single **RESOLVE** tier and out-of-range moves
are a manifest edit + resolve. The tier model labels "move to latest within
range" as semantically distinct from "install a specific version."

## 4. Safety model

- **Baseline-first:** capture the repo's verify-command errors before any
  change; only NEW errors block.
- **Two verify tiers (not one):** `verify_fast` (per-tier, read-only, seconds
  to low-minutes) and `verify_full` (final, the repo's full pipeline). REPO
  SPECIFICS declares both. A per-tier *full* gate (e.g. `just ci`, a release
  build) is infeasible for compiled languages.
- **Read-only verify gates (the formatter trap):** every gate must be
  source-read-only. `cargo fmt`, `swiftformat`, `dotnet format`, and biome's
  *format* all **rewrite** source mid-run and break baseline purity. Use the
  `--check` / `--lint` / `--verify-no-changes` / `check` (not `format`) forms.
- **No bulk updates** (with the workspace exception in §2).
- **Pinned-group respect:** never bump a Tier-0 member outside its group tool.
- **Major = operator-in-the-loop:** research breaking changes, grep usage,
  confirm each (Tier 3).
- **Rollback per tier, with cache invalidation:** a `git checkout` of
  manifests/lockfiles does not invalidate compiled-ecosystem build caches
  (rust fingerprints, DerivedData, NuGet obj/). The stamped recipe (REPO
  SPECIFICS) includes the cache step (rust `cargo check` reconciles / `cargo
  clean -p`; js `npm install` rebuilds node_modules).
- **Private-registry / auth (first-class):** classify each dependency's source
  at detect time (public-registry / private-registry / git / path); default
  private-registry and private-git to **SKIP** -- never plumb credentials.
- **Cross-compile verify is operator-opt-in, pre-merge only** (not per-tier):
  native verify does not exercise platform-gated code paths; detection flags
  `[target.'cfg(...)']` / multi-platform deps and records the cross gate
  in REPO SPECIFICS.
- **`--dry-run` everywhere; never auto-commit** (offer only).

## 5. Adapters

### js/ts (npm)

**List outdated:** `npm outdated --json` (or `npx npm-check-updates --dep prod,dev` where available).

**Install @ version:** `npm install <pkg>@<ver>` -- always the specific target version for T1/T2.

**Audit:** `npm audit --json`.

**Verify:** `verify_fast` from REPO SPECIFICS (typically `npm run typecheck && npm test`); `verify_full` from REPO SPECIFICS.

**Tier 0 (Expo):** `bundledNativeModules.json` bumped via `npx expo install --fix` only. Never hand-edit a Tier-0 member.

**SKIP:** private-registry packages ("needs auth"), git/github dependencies, path-linked local packages.

### php (composer)

**List outdated:** `composer outdated --direct --format=json` (drop `--direct` to include transitives). `composer show --latest` is the same data in table form.

**Install @ version:** `composer require <vendor/pkg>:<ver> --no-scripts` for a T1/T2 bump -- always the specific target version. `--no-scripts` keeps a post-update hook from running arbitrary code before the verify gate has been reached; drop it only when the repo's own scripts are the thing being verified.

**Audit:** `composer audit --format=json` (first-party since Composer 2.4).

**Verify:** `verify_fast` from REPO SPECIFICS (typically `composer validate --strict && vendor/bin/phpunit` or `php artisan test`); `verify_full` from REPO SPECIFICS. Read-only: use `vendor/bin/pint --test` and `vendor/bin/phpstan analyse`, never `vendor/bin/pint` bare (it rewrites).

**Rollback:** restore `composer.json` + `composer.lock`, then `composer install` to rebuild `vendor/` from the lockfile -- the cache-invalidation step, since `vendor/` still holds the new code until it is re-resolved.

**Tier 0:** none. A framework's pinned group (Laravel's own constraint set) is bumped as ordinary T1-T3; `tier0_rule: laravel` records the framework for the verify command, not a pinned-group tool.

**SKIP:** private-registry packages (`composer config repositories` naming an authed VCS/Satis host -- "needs auth"), `dev-*` branch constraints, path repositories, and any package whose constraint is an exact `1.2.3` pin.

### python (uv / poetry / pdm / pipenv / pip)

**Source of truth:** `pyproject.toml` (PEP 621 `[project].dependencies`, or the manager's own table). The manager comes from the lockfile beside it -- `deps-detect` reports which; do not assume pip.

**List outdated:** `uv pip list --outdated` / `poetry show --outdated` / `pdm outdated` / `pip list --outdated --format=json`.

**Install @ version:** `uv add '<pkg>==<ver>'` / `poetry add '<pkg>==<ver>'` / `pdm add '<pkg>==<ver>'`. For a pip/requirements repo, edit the pin then `pip install -r requirements.txt`. Bare `uv sync` after a manual `pyproject.toml` edit re-locks; that is the intended T1/T2 path when the constraint, not the pin, is what moves.

**Audit:** `pip-audit` where available (`uv run pip-audit`), else `safety check`. Neither is first-party -- report the gap rather than blocking if the repo has neither.

**Verify:** `verify_fast` from REPO SPECIFICS (typically `ruff check && pytest -q`, prefixed with the manager's runner where one is in use, e.g. `uv run pytest -q`); `verify_full` from REPO SPECIFICS. Read-only: use `ruff format --check`, never `ruff format`.

**Rollback:** restore `pyproject.toml` + the lockfile, then `uv sync` (or `poetry install` / `pip install -r`) to rebuild the environment -- the cache-invalidation step, since the virtualenv still holds the new versions until re-synced.

**Tier 0:** none.

**SKIP:** private-index packages (`[tool.uv.index]` / `--index-url` naming an authed host -- "needs auth"), VCS and local-path requirements (`@ git+…`, `@ file://`, `-e .`), and `==`-exact pins that a comment marks as deliberate.

### rust (cargo)

**List outdated:** `cargo update --dry-run` shows within-range moves. Major discovery (Tier 3) is operator-driven in v1: the operator names package + target version (`--package <name>@<ver>`). `cargo-outdated` is third-party and not assumed installed.

**Install @ version:** `cargo update -p <pkg> --precise <ver>` -- the `--precise` flag is load-bearing (omitting it silently jumps to latest-in-range). Tier 3 = edit `[workspace.dependencies]` then `cargo update -p <pkg>`.

**Audit:** `cargo deny check` (honors `deny.toml`; `cargo audit` is opt-in third-party).

**Verify:** `verify_fast` from REPO SPECIFICS (typically `cargo check --workspace && cargo test --workspace`); `verify_full` from REPO SPECIFICS. Read-only: use `cargo fmt -- --check`, never `cargo fmt`.

**Workspace roots:** detection enumerates **every** workspace root via `cargo metadata`. A shared path-dep bump edits both `Cargo.toml`s and re-resolves both lockfiles.

**SKIP:** git dependencies, path dependencies, `=`-exact pins.

**Tier 3 (major) operator-driven:** `cargo update --dry-run` surfaces only within-range moves. `/update-deps --ecosystem rust --tier 3 --package <name>@<ver>` requires the operator to name the package and target version, then performs the `[workspace.dependencies]` edit + `cargo update -p <pkg>` + verify.

### swift (SPM + Xcode)

Two shapes:
- **Pure-SPM:** `Package.swift` is the source of truth; use `swift package` subcommands.
- **XcodeGen:** `project.yml` is the source of truth (the `.xcodeproj` is generated). Edit `project.yml`, run `xcodegen generate`, then `xcodebuild -resolvePackageDependencies`. Never hand-edit the pbxproj.

**List outdated:** `swift package show-dependencies` (within-range); no built-in cross-major discovery.

**Resolve:** `swift package update <pkg>` (latest-in-range) / `swift package resolve --version <ver> <pkg>`. No per-package pin primitive -- within-range moves collapse to the RESOLVE tier (§2-§3).

**Audit:** No first-party audit. Report the gap, rely on Dependabot; do not block the run.

**Verify:** `verify_fast` from REPO SPECIFICS (typically `swift build && swift test`); `verify_full` from REPO SPECIFICS. Read-only: use `swiftformat --lint`, never `swiftformat`.

**Package.resolved:** lives in multiple locations; some are gitignored (drift hazard). Two-file pin hazard: a dep pinned in both `project.yml` and a local `Package.swift` must move together.

**SKIP classification (stdlib-only):** `Package.resolved` (JSON v3) `state.branch`/`state.revision` expose branch/revision pins. `.package(path:)`, `.exact`/`exactVersion`, `.revision`, `.branch` in the manifest (`project.yml`/`Package.swift`) are classified by the literal pin-kind tokens; these go to SKIP. `.from:` ranges are NOT SKIP -- they are the within-range RESOLVE tier.

### .NET (dotnet / Central Package Management)

**Source of truth:** `Directory.Packages.props` (version-less `<PackageReference>` in csproj). Every bump (T1/T2/T3) is the same step -- edit the one `<PackageVersion Version>` line + `dotnet restore`.

**List outdated:** `dotnet list package --outdated --include-transitive`.

**Restore-fails fallback:** `dotnet list package --outdated` requires a prior successful `dotnet restore`. When `TreatWarningsAsErrors` + NuGetAudit (NU1901-1904) hard-fails restore on a pre-existing vulnerability, retry with NuGetAudit temporarily suppressed: `dotnet restore -p:NuGetAudit=false`. Report that a pre-existing vuln was bypassed for discovery only and must still be addressed.

**Audit:** `dotnet list package --vulnerable`.

**Verify:** `verify_fast` from REPO SPECIFICS (typically `dotnet build`); `verify_full` from REPO SPECIFICS (typically `dotnet test`). Read-only: use `dotnet format --verify-no-changes`, never `dotnet format`.

**SDK/TFM detection gate:** the repo targets a specific .NET version; a mismatched local SDK makes `dotnet` hard-fail. Detection reports the required SDK band (REPO SPECIFICS).

## 6. Verify-command discovery ladder

Fed into REPO SPECIFICS at stamp time. In order:

1. **justfile recipes** (`check` / `lint` / `ci` / `deny`)
2. **CI workflow files** (`.github/workflows/*.yml` -- mine the build/test jobs)
3. **Repo-local scripts** (`scripts/*.sh`)
4. **Manifest scripts** (`package.json` / `composer.json` `scripts`)
5. **Ecosystem default** (rust `cargo check`/`cargo test`; .NET `dotnet build`/`dotnet test`; swift `swift build`/`swift test`; js `npm run typecheck`/`npm test`; php `composer validate`/`composer run test`; python `ruff check`/`pytest` -- prefixed with the manager's runner where one is in use, e.g. `uv run pytest`)

`verify_fast` prefers the fast read-only rungs; `verify_full` prefers the full
gate. Missing `verify_fast` at stamp time prompts the operator; still none aborts
non-zero. Missing `verify_full` warns and degrades to `verify_fast`-only; does
not abort.

## 7. Invocation

```
/update-deps --dry-run                       # report only: all discovery + baseline, no mutations
/update-deps --ecosystem js --tier 1          # patch js deps only
/update-deps --ecosystem rust --tier 3 --package serde@2.0.0  # rust major, operator-driven
/update-deps --tier 0                         # Tier-0 for all ecosystems (Expo only in v1)
```

- `--dry-run`: run all read-only discovery + ONE baseline capture; print planned
  per-tier bumps and proposed manifest diffs (unified diffs for
  `Cargo.toml`/`Directory.Packages.props`/`project.yml`/`Package.swift`); SKIP
  all mutations and the per-tier verify gates (meaningful only after a real
  bump); baseline runs to report pre-existing errors but does not gate; exit 0.
- `--ecosystem {js|rust|swift|dotnet}`: scope to one ecosystem. On a repo with N
  disjoint workspaces (rust) loop every workspace root.
- `--tier {0|1|2|3}`: stop after a tier. `--tier 0` iterates all detected
  ecosystems, applies Tier-0 where a pinned group exists (js/Expo only in v1),
  reports "Tier 0 empty" per ecosystem without one, exits 0.

<!-- stamped by onboard-repo v4 from batbelt on <date>. The template region is regenerated on /batbelt:onboard-repo --sync (backup + diff shown first); the REPO SPECIFICS block is preserved. -->

<!-- BEGIN REPO SPECIFICS (preserved on --sync) -->
<!-- onboard-repo fills this in per repo; see references/stamping.md -->
<!-- END REPO SPECIFICS -->
