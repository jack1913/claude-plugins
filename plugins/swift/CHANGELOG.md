# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.5] - 2026-09-27

Adds `swift:testing`, the plugin's fourth skill: an own-copy fork of AvdLee's Swift-Testing-Agent-Skill 1.2.0 covering Swift Testing (`@Test`, `#expect`/`#require`, traits, parameterized tests, parallel execution, `confirmation`) and XCTest migration. Before release its text went through a claim-by-claim audit, with compiler checks under full SIL diagnostics and behaviour claims run with `swift test`; every confirmed defect is fixed.

### Added

- `swift:testing` (`/swift:testing`), for writing, migrating and reviewing Swift tests.
- Two testing eval cases: testing a callback delivered later on another queue with `confirmation`, and a parameterized test over two parallel fixture arrays.

### Fixed

- Swift Testing snippets that did not compile or did not pass:
  - `.timeLimit(.seconds(10))`: time limits take whole minutes only (`.minutes(1)`);
  - a `URLSessionConfiguration` equality check that fails at runtime, since configurations compare by identity;
  - the fixed-size `InlineArray` zip helper, which now compiles and is gated on OS 26 on every platform;
  - four snippets missing `import Foundation` (`Testing` does not re-export it).
- Two shared-state anti-patterns now compile in Swift 6 mode (`nonisolated(unsafe)`), so they show the flakiness they describe.
- The skill's resources pointer links Apple's Swift Testing documentation instead of a README the skill does not ship.

### Changed

- The concurrency and testing skills now split the work: writing and migrating tests goes to `swift:testing`, and hanging, flaky or data-racing async tests go to `swift:concurrency`.
- The `apis.json` frameworks now include `xcuiautomation`, where `XCUIApplication` lives.
- The registry surfaces now name the fourth skill: AGENTS.md, the README, the manual and both manifest descriptions.
- Known gap: `parameterized-slug-tests` also passes without the plugin on current models, even in its harder paired-fixtures form, so it guards against regressions rather than showing the skill's value. `callback-confirmation-test` shows the skill's value: without it, agents sleep or skip `confirmation`.

## [0.1.4] - 2026-09-27

Adds `swift:concurrency`, the plugin's third skill: an own-copy fork of AvdLee's Swift-Concurrency-Agent-Skill 2.3.0 covering async/await, tasks, actors, `Sendable`, isolation and Swift 6 migration. Before release its text went through a claim-by-claim audit against Apple's doc JSON, the 27.0 SDK interfaces and the Swift 6.4 compiler, and every confirmed defect is fixed. The upstream tooling now tracks one baseline per forked skill.

### Added

- `swift:concurrency` (`/swift:concurrency`), triggered by Swift 6 concurrency work and the compiler's isolation and data-race diagnostics.
- Two concurrency eval cases: removing `nonisolated(unsafe)` from a shared cache, and fixing a `@MainActor` isolation error without moving heavy work onto the main actor.
- ADR-0010, extending the own-copy fork model to the concurrency and testing upstreams.

### Fixed

- Concurrency snippets that did not compile in Swift 6 language mode:
  - an unconstrained `withTimeout<T>`;
  - `Thread.current` used in async contexts;
  - a Void-returning Core Data `perform` helper;
  - `@Observable` classes isolating a single property to `@MainActor`;
  - `try` inside non-throwing functions and a wrong argument label.
- Data races in examples that Swift 6 rejects (a class-based download manager, observation tracking reading `@MainActor` state from a nonisolated closure), now actor- or MainActor-isolated.
- APIs that do not exist, replaced with real ones:
  - swift-async-algorithms ships throttle only as the underscored `_throttle` in every 1.x release;
  - `AsyncStream` has no `continuation` property;
  - `AsyncTimerSequence` needs a clock or `repeating(every:)`;
  - Combine has no `CombineLatest2`;
  - Swift 6.4 has no unused-`@preconcurrency` warning.
- Stale Swift 6.2 claims: `Observations` has shipped (OS 26), `Task` takes a `sending` closure rather than a `@Sendable` one, and default actor isolation is `MainActor` or `nonisolated`.
- Quoted compiler diagnostics now match the messages Swift 6.4 actually emits, so they can be searched for.
- The SwiftLint rule table says which rules are opt-in.

### Changed

- `maintenance/upstream-diff.sh` takes a required `<swiftui|concurrency|testing>` argument and reads that upstream's baseline from its own `UPSTREAM.md` section. New unit tests cover it offline.
- `UPSTREAM.md` is split into one section per upstream; the plugin and marketplace descriptions, README, AGENTS.md and the manual name the new skill.
- The `apis.json` frameworks now include `coredata`, `xctest` and `testing`.
- Known gap: with graders that accept every correct fix, both concurrency eval cases also pass without the plugin on current models, so they guard against regressions rather than show the skill's value. The eval harness has no build grader, so call-site consistency in `sendable-shared-cache` is judged from the agent's reply.

## [0.1.3] - 2026-09-26

A claim-by-claim audit of all ~10,600 lines of `swift:swiftui`'s reference text against Apple's doc JSON, the 27.0 SDK interfaces and `swiftc -typecheck` found 19 confirmed defects; all are fixed. Seven were high severity: snippets that don't compile or name APIs that don't exist.

### Fixed

- Nonexistent or misused APIs in `swift:swiftui` references:
  - `CopyButton` doesn't exist; `macos-views.md` now points to `.copyable(_:)` and `NSPasteboard.general`, and the stale ignore entry that hid the name from `check-apis --strict` is gone;
  - `windowIdealPlacement` gets its real two-parameter closure and `visibleRect`;
  - `DocumentGroupLaunchScene`'s `background:` returns a `View`, and the snippet defines the `.list` source it uses;
  - WebKit back navigation reads `backForwardList.backList.last`, not the nonexistent `backItem`;
  - concentric corners use `.rect(corners: .concentric)`, not a `.concentric` corner style that `RoundedCornerStyle` doesn't have.
- Wrong availability claims:
  - the `alert`/`confirmationDialog` `item:` overloads require OS 27 on every platform — they do not back-deploy to iOS 15 as Apple's doc page still claims;
  - `ForEach` over `.enumerated()` directly needs an OS 26 deployment target, not just a Swift 6.1 toolchain;
  - `@Previewable` is iOS 17+ / macOS 14+, not iOS 18+ (both mentions, in `previews.md` and `latest-apis.md`);
  - the `@Animatable` macro needs the SDK 26 toolchain but works at any deployment target — only hand-written `AnimatableValues` needs iOS 26+;
  - `onDeleteCommand` is macOS-only and is now gated in the cross-platform snippet;
  - the file-dialog modifiers are macOS 14+ and also on iOS 17+ / visionOS 1+, not macOS 13+-only;
  - `Table`'s availability names Mac Catalyst and macOS and excludes tvOS and watchOS; the `NavigationSplitView` example notes its `ContentUnavailableView` placeholder needs iOS 17.
- Swift 6 strict concurrency: the four `ViewModifier` + `Animatable` snippets in the animation references mark `animatableData` and their animated stored properties `nonisolated`, so they compile in Swift 6 mode.

### Changed

- `check-apis` grows to 111 pinned APIs; every new platform statement from this release is pinned, and the docs gate captures are refreshed.
- The toolbar `if #available`-inside-`.toolbar` crash concern from 0.1.2 is resolved as safe: the compiler picks the erasing `buildLimitedAvailability` overload and the pre-17.5 path falls back to `TupleToolbarContent(())` (SILGen and IR verified); no change was needed.

## [0.1.2] - 2026-09-25

Upstream bugs in `swift:swiftui`'s references are fixed. Availability gates in the other references now compile on every platform a package targets, and the six API names Apple doesn't have are replaced with the real APIs.

### Fixed

- `swift:swiftui` availability gates outside the Liquid Glass reference:
  - Charts gates name macOS, and visionOS where Apple ships the API later; the advice gives the tvOS and watchOS releases too;
  - `chart3DCameraProjection` is kept off visionOS, and `Chart3D` off tvOS and watchOS;
  - SDK 27 toolbar APIs (`topBarPinnedTrailing`, `ToolbarOverflowMenu`) are gated so macOS builds;
  - iOS 27.1-only APIs (`ArrangementView`, reserved regions, vertical toolbar bars, `onHingeChange`) sit behind a compile-time iOS check, since no `#available` version admits them on macOS, Mac Catalyst or visionOS.
- API names that don't exist in Apple's SDKs are replaced with the real APIs:
  - a numeric axis replaces `AXDateDataAxisDescriptor`;
  - `VerticalPageTabViewStyle` replaces `VerticalTabViewStyle`;
  - `matchedTransitionSource` and a zoom transition replace `navigationTransitionSource`/`Destination`;
  - `Slider`'s `neutralValue:` parameter replaces `sliderNeutralValue`;
  - the `inspector(isPresented:content:)` modifier replaces an `Inspector` type.
- The zoom navigation transition is no longer claimed on macOS.
- The view-structure example uses `foregroundStyle` instead of `foregroundColor`.

### Changed

- `UPSTREAM.md` Findings gains a Status column; all six rows are marked fixed.
- The docs are updated:
  - spec §9 records the version-bump update as confirmed live;
  - the `check-apis`, unit-test and plugin-details outputs are re-captured.

## [0.1.1] - 2026-09-25

Fixes from a full code review. The Liquid Glass fallback examples in `swift:swiftui` now compile below 26, `swift:design` no longer applies its starter tokens unasked, and `check-apis` catches more mistakes.

### Fixed

- `swift:swiftui` Liquid Glass fallbacks:
  - the `glassEffectWithFallback` helper and the toolbar example compile below 26 again;
  - availability gates name macOS as well as iOS, so a package that targets macOS 14 builds;
  - visionOS is kept out of availability gates and uses its `#if os(visionOS)` branch instead;
  - a fallback for glass button styles is added.
- The Text interpolation entry gives its real availability (iOS 14, not 26). It also notes that `Text.foregroundStyle` only interpolates from iOS 17, and that `foregroundColor` is the one exception below that.
- `swift:swiftui`'s checklist names `GlassEffectContainer` for several glass elements shown together.
- The trace recorder clears a leftover stop-file, so a new recording no longer stops at once.
- `swift:design` offers the `tokens.md` starter set but never applies it unasked. Until the user accepts it, it builds with system defaults: default padding and spacing, standard control shapes, and `.smooth`.
- `check-apis`:
  - scans code blocks indented inside lists;
  - rejects a malformed `apis.json` with a clear error instead of a traceback;
  - warns (and fails under `--strict`) when its cached Apple data is more than 30 days old.
- `upstream-diff.sh` picks upstream's newest plain release tag, and says so when upstream has none.

### Changed

- The eval graders are stricter: every `#Preview` must sit inside `#if DEBUG`, and the glass gate must also name macOS 26.
- The docs are updated:
  - `--plugin-dir` is back as the fallback when `marketplace add` fails;
  - the `check-apis` outputs are re-captured;
  - spec §9 records what the live install confirmed;
  - the rules skeleton file is retired.

## [0.1.0] - 2026-09-25

First release of the private `swift` plugin: `swift:swiftui` (SwiftUI correctness, forked from AvdLee/SwiftUI-Agent-Skill 5.1.0) and a new `swift:design` (Apple-native design). The repo also has tooling that checks every API the skills name against Apple's documentation.

### Added

- `swift:swiftui`, a fork of AvdLee/SwiftUI-Agent-Skill 5.1.0: invoked as `/swift:swiftui`, triggers on visionOS work too, and runs its Instruments scripts through `${CLAUDE_SKILL_DIR}`.
- visionOS guidance: which Liquid Glass APIs visionOS lacks, the `#if os(visionOS)` branch with `glassBackgroundEffect`, ornaments, windows, volumes and immersive spaces.
- A per-platform availability table for Liquid Glass and other 26-era APIs, generated from Apple's documentation.
- Correctness rules:
  - wrap every `#Preview` in `#if DEBUG`;
  - below a 26 deployment target, gate 26-only APIs with `#available` and fall back to a material (glass button styles included);
  - keep glass APIs that visionOS lacks out of the visionOS branch.
- A project's own design layer (tokens, a project design skill) overrides the skills' example literals.
- Deprecation entries for `overlay(_:alignment:)` and `Text + Text`, and guidance on view ordering, keeping side effects out of `body` and splitting large view files.
- `swift:design`: hierarchy and layout, typography, colour, SF Symbols, when Liquid Glass fits, platform idioms, motion, and a starter token set for projects without tokens. It triggers on new screens, loads `swift:swiftui` before writing code, and adopts Liquid Glass only once glass is in scope.
- An eval suite of four scenarios that compares runs with and without the plugin.
- Upstream's MIT license and a `NOTICE.md` crediting AvdLee, twostraws and Dimillian, both shipped with every install.
- Repo-only maintenance tooling, never shipped:
  - `check-apis.py` checks every API name against Apple's documentation indexes and verifies recorded platform claims;
  - `upstream-diff.sh` shows what changed upstream;
  - unit tests.
- Repo docs: an operator manual, ADR-0001 to ADR-0009, and the `changelog-release`, `update-docs` and `update-rules` skills.
