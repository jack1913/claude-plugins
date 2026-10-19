# Enable the plugin in a Swift repo

The plugin ships five skills. Loaded straight from this checkout, its inventory reads:

```text capture=plugin-details
Component inventory
  Skills (5)  concurrency, design, review, swiftui, testing
```

That is `claude --plugin-dir . plugin details swift`, run from the plugin folder (`plugins/swift/` in the monorepo checkout).

## Install it into one repo

Run inside the Swift repo:

```bash
claude plugin marketplace add jack1913/claude-plugins --scope project
claude plugin install swift@jack1913 --scope project
```

Always pass `--scope`. Both commands default to user scope, which loads the plugin in every repo (`claude plugin install --help`).

| Scope | Writes | Who gets the plugin |
| --- | --- | --- |
| `--scope project` | the repo's committed `.claude/settings.json` | everyone who clones the repo |
| `--scope local` | the gitignored `.claude/settings.local.json` | only you, only this checkout |

The plugin loads only where `enabledPlugins` lists it. The marketplace and the plugin are both in the public GitHub repo `jack1913/claude-plugins`.

If `marketplace add` fails — for example `git` can't reach GitHub — fall back to loading straight from a checkout: [`claude --plugin-dir`](../work-on-it.md#try-a-change).

## Pick up a new release

Installs are copies, and a third-party marketplace doesn't auto-update unless you turn that on in `/plugin` → Marketplaces ([Install and manage plugins: keep plugins updated](https://code.claude.com/docs/en/discover-plugins#keep-plugins-updated)). A repo keeps the version it installed until you run:

```bash
claude plugin marketplace update jack1913
claude plugin update swift@jack1913
```

Then start a new session or run `/reload-plugins`; the update needs a restart to apply (`claude plugin update --help`). An update only arrives when a release raised `version` in `.claude-plugin/plugin.json`, because Claude Code keys updates on the version ([Plugins reference: version management](https://code.claude.com/docs/en/plugins-reference)). See [Release](../work-on-it.md#release).

## Move an install to the jack1913 marketplace

The plugin used to be listed in a marketplace hosted in its own repo, `jack1913/swift-plugin`: `swift-plugin` until 0.2.0, then `jack1913-plugins`. Both are gone. The plugin is now listed in `jack1913`, the marketplace in the repo `jack1913/claude-plugins`, which now also holds the plugin ([ADR-0014](../../adr/ADR-0014-catalogue-moves-to-claude-plugins.md), [ADR-0015](../../adr/ADR-0015-plugin-moves-into-the-claude-plugins-monorepo.md)). The marketplace name is part of the plugin's ID, and Claude Code's `renames` map covers plugin names only, not marketplace names. So an older install, `swift@swift-plugin` or `swift@jack1913-plugins`, moves by hand.

In the first repo you move, run, with the old marketplace's name in place of `<old>` (`swift-plugin` or `jack1913-plugins`):

```bash
claude plugin uninstall swift@<old> --scope project
claude plugin marketplace remove <old>
claude plugin marketplace add jack1913/claude-plugins --scope project
claude plugin install swift@jack1913 --scope project
```

The repo's `.claude/settings.json` then lists only the new entries: `swift@jack1913` under `enabledPlugins` and `jack1913` under `extraKnownMarketplaces`.

`marketplace remove` also uninstalls `swift@<old>` in every other repo on the machine, because it drops the marketplace from your user plugin data ([Plugin marketplaces: remove](https://code.claude.com/docs/en/plugin-marketplaces)). The plugin stops loading there until you move those repos too. In each of them:
- the first two commands report "not found";
- `.claude/settings.json` keeps the old `swift@<old>` and `<old>` entries, so delete both by hand;
- then run the `marketplace add` and `install` lines. `add` reports the marketplace is "already on disk".

Commit each repo's settings change, so everyone who clones it gets the new ID.

## What each skill covers

From `skills/swiftui/SKILL.md`, `skills/design/SKILL.md`, `skills/concurrency/SKILL.md`, `skills/testing/SKILL.md` and `skills/review/SKILL.md`:

| Skill | Covers |
| --- | --- |
| `swift:swiftui` | SwiftUI correctness and current APIs: state, view structure, deprecations, `#Preview` inside `#if DEBUG`, `#available` gates below 26, the visionOS glass branch, Instruments traces |
| `swift:design` | Apple-native design: hierarchy, typography, colour, SF Symbols, when Liquid Glass fits, platform idioms, motion, design tokens |
| `swift:concurrency` | Swift 6 concurrency: async/await, tasks and task groups, actors and `@MainActor`, `Sendable` and data-race diagnostics, Swift 5 → 6 migration, hanging or flaky async tests |
| `swift:testing` | Swift Testing: `@Test`, `@Suite`, `#expect`/`#require`, traits and tags, parameterized tests, parallel execution, `confirmation`, XCTest migration and what stays on XCTest |
| `swift:review` | On-demand HIG review of a screen from its view files and/or screenshots: findings as violation · location · HIG page · fix, most severe first, then what the inputs could not show. Runs only as `/swift:review <files or screenshots>`, never on its own. It reports and doesn't edit: Write and Edit are removed for the turn that runs it, and after that the skill's own rule holds ([ADR-0011](../../adr/ADR-0011-swift-review-skill.md)) |

If the repo has its own design layer (tokens, a project design skill), `swift:swiftui` and `swift:design` translate their example literals into it, and the project layer wins where they disagree (the Operating Rules of both files). `swift:review` carries the same rule, so it doesn't report values the project layer sanctions ([ADR-0011](../../adr/ADR-0011-swift-review-skill.md)).

The repo's own rules win over the skills' defaults too. Before writing or changing code, `swift:swiftui`, `swift:concurrency` and `swift:testing` look for the repo's AGENTS.md and CLAUDE.md at the repository root, and any project skill, and read them. Where a rule there conflicts with a skill, for example one that forbids `async let`, which `swift:concurrency` would otherwise suggest for fixed parallel work, they follow the repo and say which rule they followed ([ADR-0013](../../adr/ADR-0013-project-rules-win-over-skill-defaults.md)).

`swift:review` reads its own reference files, `swift:design`'s and `swift:swiftui`'s while it runs. An installed copy reads them without prompting, even in a headless `claude -p "/swift:review …"`. A checkout loaded with `--plugin-dir` is different: a headless run couldn't read them until it also got `--add-dir` with the same directory ([verification record](../../internals/review-verification.md)).
