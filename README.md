# jack1913 plugins

Claude Code plugins by Jacek Pytlik, and the marketplace `jack1913` that lists them.

```
/plugin marketplace add jack1913/claude-plugins
/plugin install <plugin>@jack1913
```

## Plugins

| Plugin | Description | Install | Folder |
|---|---|---|---|
| `brand-creator` | Brand identity from brief to platform assets, brand book and launch | `/plugin install brand-creator@jack1913` | [`plugins/brand-creator`](plugins/brand-creator) |
| `swift` | Current, Apple-native Swift: SwiftUI, design, concurrency, testing, review | `/plugin install swift@jack1913` | [`plugins/swift`](plugins/swift) |
| `batbelt` | Plan interviews, claim verification against primary sources, and repository onboarding | `/plugin install batbelt@jack1913` | [`plugins/batbelt`](plugins/batbelt) |

From a shell: `claude plugin marketplace add jack1913/claude-plugins`, then `claude plugin install <plugin>@jack1913`.
Installed copies pick up a release with `/plugin marketplace update jack1913`.

## Layout

```
.claude-plugin/marketplace.json   the marketplace; every source is ./plugins/<name>
.github/workflows/                one workflow per plugin, plus marketplace.yml (GitHub reads only this folder)
.github/scripts/                  helpers the workflows call
plugins/<name>/                   one plugin, self-contained
tests/                            batbelt's tests (the other plugins keep theirs in their own folder)
```

Each folder under `plugins/` is a complete plugin: its `.claude-plugin/plugin.json`, its own docs, tests and `CHANGELOG.md`
(batbelt has no changelog yet), and its own version. Releases are tagged per plugin, `<plugin>--vX.Y.Z`, for example
`swift--v0.3.0`. A plugin's own `AGENTS.md`, `CLAUDE.md` or `README.md` has the rules for working on it.

## Tests

Each plugin has its own checks, run from the folder shown. CI runs them per plugin, and only when that plugin's folder (or the
marketplace) changes: `.github/workflows/<plugin>.yml`.

| Plugin | Run from | Command |
|---|---|---|
| `batbelt` | repository root | `uv run --no-project --with pytest --with pyyaml python -m pytest tests -q` |
| `brand-creator` | `plugins/brand-creator` | `BRAND_CREATOR_DATA=<set-up data dir> tests/run-all.sh --smoke` (setup, data dir and Docker run: its README, "Tests") |
| `swift` | `plugins/swift` | `python3 -m unittest discover maintenance/tests` (more checks: its `AGENTS.md`) |
| marketplace | repository root | `python3 .github/scripts/check-marketplace.py` |

Manifests, from the repository root (needs the Claude Code CLI; CI does not run the CLI for batbelt or swift):

```
claude plugin validate . --strict
claude plugin validate plugins/<name> --strict
```

## Adding a plugin

1. Create `plugins/<name>/` with `.claude-plugin/plugin.json` (name equal to the folder name), its docs and its tests.
2. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.
3. Add `.github/workflows/<name>.yml` that runs the plugin's tests, with a `paths:` filter on `plugins/<name>/**` and the workflow file.
4. Run `python3 .github/scripts/check-marketplace.py` and `claude plugin validate . --strict`, commit and push.
5. Tag releases from the repository root with `claude plugin tag plugins/<name>`.

## License

MIT, see [LICENSE](LICENSE). A plugin's own `LICENSE` and notices cover third-party material in that plugin.
