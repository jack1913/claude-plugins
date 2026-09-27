# Enable the plugin in a Swift repo

The plugin ships three skills. Loaded straight from this checkout, its inventory reads:

```text capture=plugin-details
Component inventory
  Skills (3)  concurrency, design, swiftui
```

That is `claude --plugin-dir plugins/swift plugin details swift`, run from the repo root.

## Install it into one repo

Run inside the Swift repo:

```bash
claude plugin marketplace add jack1913/swift-plugin --scope project
claude plugin install swift@swift-plugin --scope project
```

Always pass `--scope`. Both commands default to user scope, which loads the plugin in every repo (`claude plugin install --help`).

| Scope | Writes | Who gets the plugin |
| --- | --- | --- |
| `--scope project` | the repo's committed `.claude/settings.json` | everyone who clones the repo and can read `jack1913/swift-plugin` |
| `--scope local` | the gitignored `.claude/settings.local.json` | only you, only this checkout |

The plugin loads only where `enabledPlugins` lists it. The marketplace is a private GitHub repo, so `marketplace add` uses your existing git and `gh` credentials.

If `marketplace add` fails — no read access to `jack1913/swift-plugin`, or `gh` isn't authenticated — fall back to loading straight from a checkout: [`claude --plugin-dir`](../work-on-it.md#try-a-change).

## Pick up a new release

Installs are copies, and a third-party marketplace doesn't auto-update unless you turn that on in `/plugin` → Marketplaces ([Install and manage plugins: keep plugins updated](https://code.claude.com/docs/en/discover-plugins#keep-plugins-updated)). A repo keeps the version it installed until you run:

```bash
claude plugin marketplace update swift-plugin
claude plugin update swift@swift-plugin
```

Then start a new session or run `/reload-plugins`; the update needs a restart to apply (`claude plugin update --help`). An update only arrives when a release raised `version` in `plugins/swift/.claude-plugin/plugin.json`, because Claude Code keys updates on the version ([Plugins reference: version management](https://code.claude.com/docs/en/plugins-reference)). See [Release](../work-on-it.md#release).

## What each skill covers

From `plugins/swift/skills/swiftui/SKILL.md`, `plugins/swift/skills/design/SKILL.md` and `plugins/swift/skills/concurrency/SKILL.md`:

| Skill | Covers |
| --- | --- |
| `swift:swiftui` | SwiftUI correctness and current APIs: state, view structure, deprecations, `#Preview` inside `#if DEBUG`, `#available` gates below 26, the visionOS glass branch, Instruments traces |
| `swift:design` | Apple-native design: hierarchy, typography, colour, SF Symbols, when Liquid Glass fits, platform idioms, motion, design tokens |
| `swift:concurrency` | Swift 6 concurrency: async/await, tasks and task groups, actors and `@MainActor`, `Sendable` and data-race diagnostics, Swift 5 → 6 migration, async testing |

If the repo has its own design layer (tokens, a project design skill), `swift:swiftui` and `swift:design` translate their example literals into it, and the project layer wins where they disagree (the Operating Rules of both files).
