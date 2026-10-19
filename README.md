<div align="center">

# jack1913 plugins

**Claude Code plugins that build brand identities, write current Swift, and pressure-test your plans.**

By [Jacek Pytlik](https://github.com/jack1913) · marketplace `jack1913`

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![batbelt](https://github.com/jack1913/claude-plugins/actions/workflows/batbelt.yml/badge.svg)](https://github.com/jack1913/claude-plugins/actions/workflows/batbelt.yml)
[![brand-creator](https://github.com/jack1913/claude-plugins/actions/workflows/brand-creator.yml/badge.svg)](https://github.com/jack1913/claude-plugins/actions/workflows/brand-creator.yml)
[![swift](https://github.com/jack1913/claude-plugins/actions/workflows/swift.yml/badge.svg)](https://github.com/jack1913/claude-plugins/actions/workflows/swift.yml)
[![marketplace](https://github.com/jack1913/claude-plugins/actions/workflows/marketplace.yml/badge.svg)](https://github.com/jack1913/claude-plugins/actions/workflows/marketplace.yml)

[The plugins](#-the-plugins) · [Install](#-install) · [See it work](#-see-it-work) · [Updates](#-updates) ·
[Manual](docs/manual/README.md) · [Maintain it](#-maintain-the-marketplace)

</div>

## 🧰 The plugins

Three plugins, one marketplace. Install only the ones you need.

| | Plugin | Use it to | Docs |
| --- | --- | --- | --- |
| 🎨 | **brand-creator** | Get a logo, colours, type and every file your brand needs, or turn a logo you have into favicons and app icons | [guide](docs/manual/use/brand-creator.md) · [README](plugins/brand-creator/README.md) |
| 🐦 | **swift** | Have Claude write current SwiftUI, Swift 6 concurrency and Swift Testing code, and review a screen against Apple's design guidelines | [guide](docs/manual/use/swift.md) · [README](plugins/swift/README.md) |
| 🦇 | **batbelt** | Grill a plan before you build it, check a claim against real sources, or set up a repository for Claude | [guide](docs/manual/use/batbelt.md) · [README](plugins/batbelt/README.md) |

Not sure which one? [Choose a plugin](docs/manual/getting-started/choose-a-plugin.md).

## 🚀 Install

> [!TIP]
> Add the marketplace once. Every plugin in it then installs as `<plugin>@jack1913`.

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install batbelt@jack1913
```

Swap `batbelt` for `brand-creator` to get that one. Claude Code asks where to put it: **user** (you, in every project;
the usual pick), **project** (everyone on this repository) or **local** (just you, just this repository). Commands not
showing when you type `/`? Run `/reload-plugins`.

- **swift** goes in once per Swift project: use the **For your whole team** lines below.
- **brand-creator** needs Claude Code 2.1.271 or newer, then a one-time `/brand-creator:setup` (it shows what it will
  download, about 200 MB, and waits for your yes).

<details>
<summary><b>From a terminal</b></summary>

```bash
claude plugin marketplace add jack1913/claude-plugins
claude plugin install batbelt@jack1913
```

It shows up in your next Claude Code session.

</details>

<details>
<summary><b>For your whole team</b></summary>

```bash
claude plugin marketplace add jack1913/claude-plugins --scope project
claude plugin install swift@jack1913 --scope project
```

This adds the plugin to the repository's `.claude/settings.json`. Commit that file; then each teammate runs the second
line once on their own machine.

</details>

More, including how to remove a plugin: [Install a plugin](docs/manual/getting-started/install-a-plugin.md).

## 👀 See it work

**swift**, from one real run ([its README](plugins/swift/README.md#usage)). You ask in plain words:

> Add a settings screen in Sources/App/SettingsView.swift: show the account's name and email, a notifications toggle,
> and a Sign Out button.

Claude wrote a native settings form, and `swift build` passed:

```swift
        Form {
            Section("Account") {
                LabeledContent("Name", value: account.name)
                LabeledContent("Email", value: account.email)
            }

            Section {
                Toggle("Notifications", isOn: $notificationsEnabled)
            }

            Section {
                Button("Sign Out", role: .destructive, action: onSignOut)
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Settings")
```

**brand-creator**: say "a logo and a look for my bakery". You get a few quick questions, then one page with three
clearly different directions to pick from ([its first ten minutes](plugins/brand-creator/README.md#first-run-your-first-10-minutes)).

## 🔄 Updates

> [!NOTE]
> Auto-update is off by default for a third-party marketplace like `jack1913`, so a new release waits until you
> update.

- **One plugin**, from a terminal: `claude plugin update <plugin>@jack1913`.
- **Everything from this marketplace**: `/plugin` → **Marketplaces** → `jack1913` → **Update marketplace**.
- `/plugin marketplace update jack1913` on its own only refreshes which versions are available; your installed plugins
  stay on their current version until you update them as above.

What changed: [brand-creator](plugins/brand-creator/CHANGELOG.md) and [swift](plugins/swift/CHANGELOG.md) keep
release notes; batbelt has none yet.

## 🚦 Ground rules

Each plugin draws hard lines around what it does on its own:

| Plugin | Never does |
| --- | --- |
| brand-creator | buy a domain, file a trademark, register a handle, upload to a store or contact anyone; commit or push on its own; call a name "available" ([its README](plugins/brand-creator/README.md#what-it-never-does)) |
| swift | edit anything during `/swift:review`, which only reports ([its README](plugins/swift/README.md#what-it-covers)) |
| batbelt | write before you confirm the plan (`onboard-repo`); answer a claim from memory (`prove-it` needs real sources, or it stops) ([its guide](docs/manual/use/batbelt.md)) |

## 🔧 Maintain the marketplace

Each folder under `plugins/` is a plugin with its own manifest, docs and version, and its own tests and changelog
(batbelt: tests in the root `tests/`, no changelog yet). Releases are tagged per plugin as `<plugin>--vX.Y.Z`.

<details>
<summary><b>Layout</b></summary>

```text illustrative
.claude-plugin/marketplace.json   the marketplace; every source is ./plugins/<name>
.github/workflows/                one workflow per plugin, plus marketplace.yml (GitHub reads only this folder)
.github/scripts/                  helpers the workflows call
plugins/<name>/                   one plugin, self-contained
tests/                            batbelt's tests (the other plugins keep theirs in their own folder)
docs/                             the marketplace's manual, internals and decision records
```

Details: [Repository layout](docs/manual/reference/layout.md).

</details>

### Tests

Each plugin has its own checks, run from the folder shown. CI runs a plugin's checks when its folder or its workflow
changes (`.github/workflows/<plugin>.yml`; batbelt also on `tests/**` and `.claude-plugin/**`), or when started by hand.

| Plugin | Run from | Command |
| --- | --- | --- |
| batbelt | repository root | `uv run --no-project --with pytest --with pyyaml python -m pytest tests -q` |
| brand-creator | `plugins/brand-creator` | `BRAND_CREATOR_DATA=<dir> tests/run-all.sh --smoke` (CI runs it inside `tests/docker/run.sh`; data dir setup: [Tests](docs/manual/reference/tests.md#brand-creator)) |
| swift | `plugins/swift` | `python3 -m unittest discover maintenance/tests` (more checks: [Tests](docs/manual/reference/tests.md#swift)) |
| marketplace | repository root | `python3 .github/scripts/check-marketplace.py` |

Validate the manifests from the repository root before a release (needs the Claude Code CLI; CI only validates
brand-creator's):

```bash
claude plugin validate . --strict
claude plugin validate plugins/<name> --strict
```

### Add a plugin

1. Create `plugins/<name>/` with `.claude-plugin/plugin.json` (name equal to the folder name), its docs and its tests.
2. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.
3. Add `.github/workflows/<name>.yml` that runs the plugin's tests: `push`, `pull_request` and `workflow_dispatch`, the
   same `paths:` filter on both (`plugins/<name>/**` and the workflow file), and `permissions: contents: read`.
4. Run `python3 .github/scripts/check-marketplace.py`, `claude plugin validate . --strict` and
   `claude plugin validate plugins/<name> --strict`, commit and push.
5. Tag releases from the repository root with `claude plugin tag plugins/<name>`.

Step by step, with what each check prints: [Add a plugin](docs/manual/getting-started/add-a-plugin.md). Why it works
this way: [ADR-0001](docs/adr/ADR-0001-one-monorepo-marketplace.md), [ADR-0002](docs/adr/ADR-0002-per-plugin-versions-and-tags.md).

## 📜 License

MIT, see [LICENSE](LICENSE). A plugin's own `LICENSE` and notices cover third-party material in that plugin.
