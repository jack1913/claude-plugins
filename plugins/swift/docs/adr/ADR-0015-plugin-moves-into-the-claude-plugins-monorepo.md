# ADR-0015: The plugin moves into `jack1913/claude-plugins` as `plugins/swift/`

- **Status:** accepted; supersedes the `git-subdir` source and the separate plugin repo of ADR-0014
- **Date:** 2026-10-19
- **Source:** the owner's decision (2026-10-19) to make `jack1913/claude-plugins` the single source of truth for all three plugins (`batbelt`, `brand-creator`, `swift`) and to publish it; ADR-0014 (the catalogue); [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) (relative-path sources)

## Context

ADR-0014 kept this plugin in its own repo, `jack1913/swift-plugin`, and listed it in the catalogue with a `git-subdir` source. Each plugin then lived in a different repo from the marketplace that lists it, with its own CI, so a change touching a plugin and the catalogue was two commits in two repos. The owner decided to keep all three plugins in the catalogue repo and make it public.

## Decision

- The repo `jack1913/swift-plugin` is merged, with its full history, into `jack1913/claude-plugins`. The old `plugins/swift/` folder and the old repo-level files (`AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`, `README.md`, `UPSTREAM.md`, `docs/`, `maintenance/`, `.claude/`) became one folder, `plugins/swift/`, which is the plugin root.
- The catalogue lists `swift` with the source `./plugins/swift`. The entry still carries no `version`; `plugins/swift/.claude-plugin/plugin.json` stays the only version home (ADR-0003).
- Everything the install copies is now the whole `plugins/swift/` folder, contributor files included. That is accepted: it is a few hundred kilobytes of Markdown and scripts that nothing loads, and a plugin must be one folder for a relative-path source.
- Paths inside the plugin's docs, scripts and tests are relative to `plugins/swift/`. `maintenance/apicheck/cli.py` finds the skills at `skills/`, and the recorder tests find `skills/swiftui/scripts/record_trace.py` the same way. Commands run from `plugins/swift/`, except `claude plugin tag plugins/swift`, which runs from the monorepo root where the marketplace file is.
- Release tags keep the form `swift--v<version>` and the history keeps its tags (`swift--v0.1.0` to `swift--v0.2.3`, `upstream-5.1.0`, `upstream-concurrency-2.3.0`, `upstream-testing-1.2.0`). `git diff upstream-5.1.0 -- skills/swiftui`, run from `plugins/swift/`, still shows the forked skill's deviations.
- CI for the plugin is `.github/workflows/swift.yml` at the monorepo root, filtered to `plugins/swift/**`.
- The `CLAUDE.md` bridge moved to `.claude/CLAUDE.md` (`@../AGENTS.md`): the plugin root is now this whole folder, and `claude plugin validate --strict` rejects a `CLAUDE.md` there.
- `.claude/rules/` and `.claude/skills/` stay inside `plugins/swift/`. Claude Code loads them for a session started in `plugins/swift/`; a session started at the monorepo root does not see them as project-level instructions.
- The history was scrubbed on import: a private app name became `ExampleApp` / `example-app`, and a home path became `<home>`. Keep it that way.

Rejected:
- Keeping `swift-plugin` as the source of truth and mirroring it: two copies, and a mirror drifts.
- Moving the contributor files to the monorepo root: the plugin would not be self-contained, and `UPSTREAM.md`, `maintenance/` and the ADRs belong to this plugin only.

## Consequences

- The install ID `swift@jack1913` does not change, so installed copies keep working; `marketplace update jack1913` picks the move up. Installing no longer needs read access to anything private.
- `jack1913/swift-plugin` is archived; its README points here.
- Records written before the move keep their old paths and repo names (the changelog's past entries, ADRs 0001 to 0014, `docs/superpowers/`, `docs/archive/`, `docs/.onboard-captures/`), because they describe what was run then.
- `maintenance/check-apis.py --strict` needs the network and compares the skills with Apple's current data, which drifts, so it is a manual gate and is not in CI. The unit tests are.
