# swift-plugin

The `swift` plugin gives Claude Code five skills for writing correct, current, Apple-native Swift: SwiftUI, Apple design, Swift 6 concurrency, Swift Testing, and an on-demand Human Interface Guidelines review.

[Changelog](CHANGELOG.md) (current version and every release) · [Manual](docs/manual/README.md) · Marketplace `jack1913-plugins` · Private

- [Requirements](#requirements)
- [Enable it in a Swift repo](#enable-it-in-a-swift-repo)
- [Usage](#usage)
- [What it covers](#what-it-covers)
- [Versioning](#versioning)
- [Work on it](#work-on-it)
- [Licenses](#licenses)

## Requirements

- Claude Code. The runs in the manual used 2.1.283.
- Read access to the private repo `jack1913/swift-plugin`, through your git or `gh` credentials.
- A Swift package or Xcode project to use it in.

## Enable it in a Swift repo

Run inside that repo. `--scope project` writes its committed `.claude/settings.json`; `--scope local` writes the gitignored `.claude/settings.local.json`.

```bash
claude plugin marketplace add jack1913/swift-plugin --scope project
claude plugin install swift@jack1913-plugins --scope project
```

A repo without these entries never sees the plugin. Before 0.2.0 the marketplace was named `swift-plugin`. To move an older install, see [the manual](docs/manual/getting-started/enable-in-a-swift-repo.md#move-an-install-from-swift-plugin).

## Usage

Ask in plain words. The right skills load on their own:

> Add a settings screen in Sources/App/SettingsView.swift: show the account's name and email, a notifications toggle, and a Sign Out button.

One real run wrote a native settings form, and `swift build` passed:

```text capture=use-swiftui-plain-code
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

More, each built around a real run:

| Task | Page |
| --- | --- |
| Build a SwiftUI screen, with or without your design tokens | [Build a SwiftUI screen](docs/manual/use/build-a-swiftui-screen.md) |
| Fix a Swift 6 concurrency error, following your repo's own rules | [Fix a concurrency error](docs/manual/use/fix-a-concurrency-error.md) |
| Test async callbacks, migrate XCTest to Swift Testing | [Write tests](docs/manual/use/write-tests.md) |
| Review a built screen from its code or a screenshot | [Review a screen](docs/manual/use/review-a-screen.md) |

## What it covers

| Skill | Loads | Covers |
| --- | --- | --- |
| `swift:swiftui` | Automatically | SwiftUI APIs and correctness, previews, availability gates below 26, visionOS, Liquid Glass APIs, accessibility code, Instruments traces |
| `swift:design` | Automatically | Hierarchy, typography, colour, SF Symbols, when Liquid Glass fits, platform idioms, motion, design tokens |
| `swift:concurrency` | Automatically | async/await, actors, `Sendable`, isolation errors, Swift 6 migration |
| `swift:testing` | Automatically | Swift Testing, parameterized tests, `confirmation`, XCTest migration |
| `swift:review` | Only as `/swift:review` | An HIG review of a screen from its code or a screenshot; reports, never edits |

The skills follow your repo's own rules first:
- `swiftui`, `design` and `review` use your design tokens ([ADR-0007](docs/adr/ADR-0007-project-design-layer-wins.md));
- `swiftui`, `concurrency` and `testing` follow your AGENTS.md and CLAUDE.md over their own defaults ([ADR-0013](docs/adr/ADR-0013-project-rules-win-over-skill-defaults.md)).

Nine eval cases check the skills' behaviour, and `project-rule-over-skill` is the one that checks the AGENTS.md rule. The full matrix of topics, shared rules and eval results is in [What the plugin covers](docs/manual/reference/capabilities.md).

## Versioning

- SemVer. The version lives only in `plugins/swift/.claude-plugin/plugin.json` ([ADR-0003](docs/adr/ADR-0003-explicit-semver-one-version-home.md)), and each release is tagged `swift--v<version>`.
- Before 1.0, a breaking change bumps the minor version (0.2.0 renamed the marketplace), and anything else bumps the patch.
- Installs are copies, so a repo picks up a release with `claude plugin marketplace update jack1913-plugins` and `claude plugin update swift@jack1913-plugins`, then a new session.
- Every release is listed in the [Changelog](CHANGELOG.md).

## Work on it

| Task | Command |
|---|---|
| Try a change | `claude --plugin-dir ~/Dev/claude_skills/swift-plugin/plugins/swift` |
| Check APIs against Apple | `python3 maintenance/check-apis.py --strict` |
| Unit tests | `python3 -m unittest discover maintenance/tests` |
| Evals | `claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --max-cost-usd <budget> --allow-tools Write Edit` |
| Upstream changes | `maintenance/upstream-diff.sh <swiftui\|concurrency\|testing> [ref]` |
| Validate manifests | `claude plugin validate . && claude plugin validate plugins/swift` |

The full workflow, releases included: [Work on the plugin](docs/manual/work-on-it.md). Decisions: [`docs/adr/`](docs/adr/).

## Licenses

Third-party text and its MIT notices: `plugins/swift/NOTICE.md`. Upstreams' licenses: `plugins/swift/skills/swiftui/LICENSE-upstream`, `plugins/swift/skills/concurrency/LICENSE-upstream`, `plugins/swift/skills/testing/LICENSE-upstream`.
