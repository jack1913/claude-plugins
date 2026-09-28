# swift-plugin

Private Claude Code marketplace with one plugin, `swift`: skills that make an agent write correct, current, Apple-native Swift — SwiftUI, design, Swift 6 concurrency and tests — plus an on-demand design review.

| Skill | Covers |
|---|---|
| `swift:swiftui` | SwiftUI correctness and current APIs. A fork of [AvdLee/SwiftUI-Agent-Skill](https://github.com/AvdLee/SwiftUI-Agent-Skill) with visionOS, preview and platform-availability fixes (`UPSTREAM.md`) |
| `swift:design` | Apple-native design: hierarchy, typography, color, SF Symbols, Liquid Glass, platform idioms, motion, tokens |
| `swift:concurrency` | Swift 6 concurrency: Sendable, actors, async/await, data-race diagnosis, 5→6 migration. A fork of [AvdLee/Swift-Concurrency-Agent-Skill](https://github.com/AvdLee/Swift-Concurrency-Agent-Skill) (`UPSTREAM.md`) |
| `swift:testing` | Swift Testing: `@Test`, `#expect`/`#require`, traits, parameterized tests, parallel execution, XCTest migration. A fork of [AvdLee/Swift-Testing-Agent-Skill](https://github.com/AvdLee/Swift-Testing-Agent-Skill) (`UPSTREAM.md`) |
| `swift:review` | On-demand HIG review of a SwiftUI screen from its code and/or screenshots, reported as findings with the HIG source and a fix. Runs only when you type `/swift:review <view files or screenshots>`; it reports and doesn't edit (file-editing tools are removed for that turn) |

## Enable it in a Swift repo

Run inside that repo. `--scope project` writes its committed `.claude/settings.json`; `--scope local` writes the gitignored `.claude/settings.local.json`.

```bash
claude plugin marketplace add jack1913/swift-plugin --scope project
claude plugin install swift@jack1913-plugins --scope project
```

A repo without these entries never sees the plugin. Installs are copies: a repo picks up a new release with `claude plugin marketplace update jack1913-plugins` and `claude plugin update swift@jack1913-plugins`. Before 0.2.0 the marketplace was named `swift-plugin`; to move an older install, see [the manual](docs/manual/getting-started/enable-in-a-swift-repo.md#move-an-install-from-swift-plugin).

## Work on it

| Task | Command |
|---|---|
| Try a change | `claude --plugin-dir ~/Dev/claude_skills/swift-plugin/plugins/swift` |
| Check APIs against Apple | `python3 maintenance/check-apis.py --strict` |
| Unit tests | `python3 -m unittest discover maintenance/tests` |
| Evals | `claude plugin eval plugins/swift --scaffold --trust-plugin --max-cost-usd <budget> --allow-tools Write Edit` |
| Upstream changes | `maintenance/upstream-diff.sh <swiftui\|concurrency\|testing> [ref]` |
| Validate manifests | `claude plugin validate . && claude plugin validate plugins/swift` |

Release flow and design: `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §6.

## Licenses

Third-party text and its MIT notices: `plugins/swift/NOTICE.md`. Upstreams' licenses: `plugins/swift/skills/swiftui/LICENSE-upstream`, `plugins/swift/skills/concurrency/LICENSE-upstream`, `plugins/swift/skills/testing/LICENSE-upstream`.
