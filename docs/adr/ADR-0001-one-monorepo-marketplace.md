# ADR-0001: One monorepo marketplace, each plugin a self-contained folder

- **Status:** accepted
- **Date:** 2026-10-19
- **Source:** commits b343cbb (jack1913 marketplace: brand-creator and swift), e55457d (the marketplace moves to
  `jack1913/claude-plugins` as `jack1913`), f93e0a6 (batbelt added), 3f8b348 (prepared for public: MIT licence),
  093186c and 320b6e3 (brand-creator and swift imported with full history), 9f6a1b7, 6f8f66d and 38d706b (CI and the
  plugins work from their folders; 38d706b adds swift's ADR-0015); `plugins/swift/docs/adr/ADR-0014-catalogue-moves-to-claude-plugins.md` and
  `plugins/swift/docs/adr/ADR-0015-plugin-moves-into-the-claude-plugins-monorepo.md`; claude-configs ADR-0019 (its
  skills component installs `batbelt` from here)

## Context

The owner's plugins started in separate repos: swift as its own repo and marketplace, brand-creator in its own repo,
and the skills that became batbelt inside a configuration repo. One marketplace per repo meant several marketplaces to
add, update and trust, and the marketplace name is part of every install ID and cannot be migrated. An intermediate
step listed swift through a `git-subdir` source pointing at its separate repo, which left plugin and catalogue in
different repos: a change touching both was two commits and two CI runs.

## Decision

- One public repo, `jack1913/claude-plugins` (MIT), is the single marketplace, named `jack1913`. Install IDs are
  `<plugin>@jack1913`.
- Every plugin lives in `plugins/<name>/`, and every marketplace entry's `source` is `./plugins/<name>`
  (`.github/scripts/check-marketplace.py` fails on any other source).
- Each plugin folder is complete on its own: its `.claude-plugin/plugin.json` (name equal to the folder name), docs,
  tests, changelog and version. batbelt is the exception: its tests sit in the root `tests/`, and it has no
  `CHANGELOG.md` yet (`README.md`, "Layout").
- This repo is the source of truth: the plugin repos were merged in with their full history, not mirrored.

Rejected:

- One repo and one marketplace per plugin: several marketplaces to add and trust.
- `url` and `git-subdir` sources pointing at separate plugin repos (b343cbb listed brand-creator by `url` and swift by
  `git-subdir`; swift's ADR-0014, superseded by its ADR-0015): plugin and catalogue in different repos.
- Mirroring the plugin repos into the catalogue: two copies that drift.
- Moving a plugin's contributor files to the repo root: the plugin would no longer be one self-contained folder.

## Consequences

- `/plugin marketplace add jack1913/claude-plugins` gives access to every plugin; swift's install ID `swift@jack1913`
  survived the move.
- An install copies the whole plugin folder, contributor files included.
- Adding a plugin is a folder, a marketplace entry and a workflow (`README.md`, "Adding a plugin").
- A plugin's own `.claude/` (swift has one) applies in full only in a session started in that plugin's folder. A
  session at the repo root uses the root `AGENTS.md` and `.claude/`, gets swift's nested skills and rules only after
  Claude reads or edits a file under `plugins/swift/`
  ([Claude Code docs, "Load skills in monorepos and subdirectories"](https://code.claude.com/docs/en/skills)).

## Update 2026-10-19

batbelt now has its own `CHANGELOG.md` (`plugins/batbelt/CHANGELOG.md`, from batbelt 0.1.2); its tests
still sit in the root `tests/`. The README section cited above is gone: the steps for adding a plugin now live in
[docs/internals/add-a-plugin.md](../internals/add-a-plugin.md), and the layout in [docs/internals/layout.md](../internals/layout.md).
