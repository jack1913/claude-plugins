# jack1913 — Claude Code plugins

One catalogue for every plugin I maintain. Each plugin lives in its own repository (or under `plugins/` here) and is listed in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json); install and update everything from this one marketplace.

```
/plugin marketplace add jack1913/claude-plugins
/plugin install <plugin>@jack1913
```

The repositories are private: installing needs read access to them with your git credentials, and background auto-updates
need `GITHUB_TOKEN` set.

## Plugins

| Plugin | What it is | Source |
|---|---|---|
| `brand-creator` | Gated brand-identity process: boards, mark system, tokens, platform assets, brand book, launch | [jack1913/brand-creator](https://github.com/jack1913/brand-creator) |
| `swift` | Correct, current, Apple-native Swift (SwiftUI, design, concurrency, testing, review) | [jack1913/swift-plugin](https://github.com/jack1913/swift-plugin), `plugins/swift` |

## Naming

- **Domain plugins** get descriptive names (`brand-creator`, `swift`): the name says what you install.
- **Kits** (cross-cutting collections of abilities, like `superpowers`) get short DC names (`batbelt`, `brainiac`).

## Adding a plugin

1. Give the plugin its own repository with `.claude-plugin/plugin.json` (or put it under `plugins/<name>/` here).
2. Add an entry to `.claude-plugin/marketplace.json`:
   - own repository: `"source": {"source": "url", "url": "https://github.com/jack1913/<repo>.git"}`
   - a folder in another repository: `"source": {"source": "git-subdir", "url": "...", "path": "plugins/<name>"}`
   - a folder here: `"source": "./plugins/<name>"`
3. `claude plugin validate . --strict`, commit, push. Installed users get it with `/plugin marketplace update jack1913`.
