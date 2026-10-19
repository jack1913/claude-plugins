# jack1913 plugins

Claude Code plugin marketplace.

```
/plugin marketplace add jack1913/claude-plugins
/plugin install <plugin>@jack1913
```

The repositories are private: installing needs read access with your git credentials, and background auto-updates need
`GITHUB_TOKEN` set.

## Plugins

| Plugin | Description | Source |
|---|---|---|
| `brand-creator` | Brand identity from brief to platform assets, brand book and launch | [jack1913/brand-creator](https://github.com/jack1913/brand-creator) |
| `swift` | Current, Apple-native Swift: SwiftUI, design, concurrency, testing, review | [jack1913/swift-plugin](https://github.com/jack1913/swift-plugin) (`plugins/swift`) |
| `batbelt` | Plan interviews, claim verification against primary sources, and repository onboarding | this repository (`plugins/batbelt`) |

## Tests

```
uv run --no-project --with pytest --with pyyaml python -m pytest tests -q
claude plugin validate . --strict
claude plugin validate plugins/batbelt --strict
```

The tests check the marketplace entries, the skills' frontmatter and the onboard-repo helper scripts. CI runs the pytest
command on Linux; `claude plugin validate` needs the CLI and is run locally.

## Adding a plugin

1. Put the plugin in its own repository with `.claude-plugin/plugin.json`, or under `plugins/<name>/` here.
2. Add an entry to `.claude-plugin/marketplace.json`:
   - own repository: `"source": {"source": "url", "url": "https://github.com/jack1913/<repo>.git"}`
   - folder in another repository: `"source": {"source": "git-subdir", "url": "...", "path": "plugins/<name>"}`
   - folder here: `"source": "./plugins/<name>"`
3. Run `claude plugin validate . --strict`, commit and push. Installed copies pick it up with `/plugin marketplace update jack1913`.
