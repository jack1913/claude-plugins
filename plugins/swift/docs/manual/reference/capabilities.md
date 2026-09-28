# What the plugin covers

Five skills, the rules they share, and the eval cases behind them.

## Skills

| Skill | Loads | Covers | Built from |
| --- | --- | --- | --- |
| `swift:swiftui` | Automatically, when you write, review or refactor SwiftUI | Correct, current SwiftUI APIs: state and `@Observable`, view structure, layout, lists, previews in `#if DEBUG`, `#available` gates below 26, visionOS, Liquid Glass APIs, accessibility code, Instruments traces | A fork of AvdLee/SwiftUI-Agent-Skill 5.1.0 (`UPSTREAM.md`) |
| `swift:design` | Automatically, when you build or restyle a screen | Apple-native design: hierarchy and grouping, typography and Dynamic Type, colour and dark mode, SF Symbols, when Liquid Glass fits, platform idioms, motion, design tokens | Our own text |
| `swift:concurrency` | Automatically, for concurrency code, concurrency errors and Swift 6 migration | async/await, tasks and task groups, actors and `@MainActor`, `Sendable`, isolation diagnostics, Swift 5 → 6 migration, hanging or flaky async tests | A fork of AvdLee/Swift-Concurrency-Agent-Skill 2.3.0 (`UPSTREAM.md`) |
| `swift:testing` | Automatically, when you write, migrate or review tests | Swift Testing: `@Test`, `#expect`/`#require`, traits, parameterized tests, `confirmation`, parallel execution, XCTest migration and what stays on XCTest | A fork of AvdLee/Swift-Testing-Agent-Skill 1.2.0 (`UPSTREAM.md`) |
| `swift:review` | Only when you type `/swift:review <files or screenshots>` | An HIG review of a built screen from code and/or screenshots, reported as violation · location · HIG page · fix; it never edits files | Our own text ([ADR-0011](../../adr/ADR-0011-swift-review-skill.md)) |

## Topics by skill

● owns the topic · ○ also applies it.

| Topic | `swiftui` | `design` | `concurrency` | `testing` | `review` |
| --- | :-: | :-: | :-: | :-: | :-: |
| SwiftUI API correctness and deprecations | ● | | | | |
| State, `@Observable`, data flow | ● | | ○ | | |
| Previews in `#if DEBUG` | ● | | | | |
| Availability gates below OS 26 | ● | | | | |
| visionOS | ● | ○ | | | ○ |
| Liquid Glass | ● APIs | ● when it fits | | | ○ placement |
| Hierarchy, grouping, layout | ○ | ● | | | ○ |
| Typography and Dynamic Type | ○ | ● | | | ○ |
| Colour and dark mode | | ● | | | ○ |
| SF Symbols | | ● | | | ○ |
| Motion and Reduce Motion | ○ | ● | | | ○ |
| Design tokens | ○ | ● | | | ○ |
| Accessibility | ● code | ○ | | | ○ |
| Performance and Instruments | ● | | ○ | | |
| async/await, actors, `Sendable` | | | ● | | |
| Swift 6 migration and diagnostics | | | ● | | |
| Swift Testing | | | | ● | |
| XCTest migration | | | | ● | |
| Async and callback tests | | | ○ hangs, races | ● | |
| HIG review of a built screen | | | | | ● |

## Rules the skills share

| Rule | Skills | Decision |
| --- | --- | --- |
| Your design layer (tokens, colour sets, a design skill) wins over example literals | `swiftui`, `design`, `review` | [ADR-0007](../../adr/ADR-0007-project-design-layer-wins.md) |
| Your AGENTS.md and CLAUDE.md rules win over a skill's defaults, and the skill says which rule it followed | `swiftui`, `concurrency`, `testing` | [ADR-0013](../../adr/ADR-0013-project-rules-win-over-skill-defaults.md) |
| Liquid Glass stays opt-in; missing glass is never a finding | `swiftui`, `design`, `review` | [ADR-0008](../../adr/ADR-0008-liquid-glass-stays-opt-in.md) |
| Every API name a skill uses is checked against Apple's documentation before a release | all | [ADR-0009](../../adr/ADR-0009-check-apis-resolves-against-apple-indexes.md) |

## Eval cases

Each case runs a prompt in a scratch project, with the plugin and without it, and grades the result. `swift:review` is checked by a recorded end-to-end run instead, because slash-only skills can't run in the eval harness ([verification record](../../internals/review-verification.md)).

| Case | Skill | Checks |
| --- | --- | --- |
| `callback-confirmation-test` | `testing` | A callback that arrives later, tested with `confirmation` and no sleeps |
| `glass-button-ios17` | `swiftui` | A glass button gated for a deployment target below 26 |
| `glass-toolbar-visionos` | `swiftui` | Floating glass controls with a visionOS branch |
| `mainactor-detached-task` | `concurrency` | A MainActor isolation fix that keeps heavy work off the main actor |
| `parameterized-slug-tests` | `testing` | Table-driven tests with `@Test(arguments:)` |
| `preview-debug-guard` | `swiftui` | A new preview wrapped in `#if DEBUG` |
| `project-rule-over-skill` | `concurrency` | The repo's AGENTS.md rule followed over the skill's default |
| `sendable-shared-cache` | `concurrency` | `nonisolated(unsafe)` opt-outs removed from a shared cache |
| `settings-screen-no-tokens` | `design` | A native settings form, plus an offer of design tokens when the project has none |

The 0.2.1 release run: WITH is the score with the plugin, W/OUT without it, and Δ the difference.

```text capture=eval-suite
CASE                        WITH  W/OUT Δ      RUNS COST    NOTES
callback-confirmation-test  1.00  0.73  +0.27  6    $0.72   
glass-button-ios17          1.00  0.50  +0.50  6    $0.67   
glass-toolbar-visionos      1.00  0.92  +0.08  6    $1.06   
mainactor-detached-task     1.00  1.00  0.00   6    $0.67   
parameterized-slug-tests    1.00  1.00  0.00   6    $0.58   
preview-debug-guard         1.00  0.50  +0.50  6    $0.64   
project-rule-over-skill     1.00  0.00  +1.00  6    $0.69   
sendable-shared-cache       1.00  1.00  0.00   6    $0.73   
settings-screen-no-tokens   1.00  0.83  +0.17  6    $0.87   

9 case(s) · mean Δ +0.28 · 2333s · $6.63
```

A Δ of 0.00 means today's models pass that case without the plugin too, so it guards against regressions rather than showing the plugin's value. How to run the suite: [Work on the plugin](../work-on-it.md#run-the-evals).
