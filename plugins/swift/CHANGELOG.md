# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-09-28

The code skills now follow a project's own rules. `swift:swiftui`, `swift:concurrency` and `swift:testing` look for the project's AGENTS.md and CLAUDE.md before writing code, and follow them where they conflict with the skill's defaults. Two flaky eval graders are fixed, and every eval case now passes at 1.00 with the plugin.

### Fixed

- `swift:swiftui`, `swift:concurrency` and `swift:testing` now look for the project's own rules (AGENTS.md, CLAUDE.md, project skills) and follow them where they conflict with the skill's defaults, saying which rule they followed. Before, a project that forbids `async let` still got it from `swift:concurrency` whenever its rule wasn't already in context (ADR-0013).
- Two eval graders that failed correct answers now and then:
  - `glass-toolbar-visionos` demanded a `GlassEffectContainer` even when the bar had a single glass surface, which needs none;
  - `mainactor-detached-task` missed a main-actor task that awaits a detached task's `.value` before mutating.

  Both misses showed up in 0.2.0 as well.

### Added

- Eval case `project-rule-over-skill`: a project's AGENTS.md forbids the `async let` that `swift:concurrency` recommends. With the plugin it went from 0/3 to 6/6; without the plugin it scores 0/3.

### Changed

- The manual's move from `swift-plugin` to `jack1913-plugins` has now been run: in a scratch repo, then in a second repo. It now says that `marketplace remove` uninstalls the old plugin in every repo, and that in the repos moved after the first, the old settings entries have to be deleted by hand. This closes the known gap listed for 0.2.0.
- Known gap: with the fixed grader, `mainactor-detached-task` also scores 1.00 without the plugin. Like `parameterized-slug-tests` and `sendable-shared-cache`, it now guards against regressions rather than showing the plugin's value.

## [0.2.0] - 2026-09-28

**Breaking:** the marketplace is renamed from `swift-plugin` to `jack1913-plugins`, so the install ID changes from `swift@swift-plugin` to `swift@jack1913-plugins`. Claude Code can't migrate a marketplace name, so move each older install by hand:
- uninstall `swift@swift-plugin`;
- `claude plugin marketplace remove swift-plugin`;
- add `jack1913/swift-plugin` again;
- install `swift@jack1913-plugins`, all at `--scope project`;
- commit the repo's changed `.claude/settings.json`.

The manual's "Move an install from swift-plugin" section lists the exact commands. The skills and the GitHub repo are unchanged.

### Changed

- The marketplace is named `jack1913-plugins`, and the manifests are signed "Jacek Pytlik" with a link to github.com/jack1913 (ADR-0012). The name avoids `claude` and `anthropic`, which Claude Code reserves and re-checks on every load.
- The manual's headless note for `swift:review` is now tested against an installed copy: it reads its reference files without `--add-dir`, which only a `--plugin-dir` checkout needs. This closes the known gap listed for 0.1.7.
- Known gap: the move commands follow Claude Code's documentation and haven't yet been run on an older install.

## [0.1.7] - 2026-09-28

A maintenance release: no skills were added.
- `swift:review` now judges Mac controls by Mac sizes.
- Five course callouts in `swift:concurrency` were stuck inside code blocks, so they rendered as code. They're fixed.
- `check-apis` stops reading prose as Swift, which shrinks its ignore list from 317 names to 231.
- `swift:review`'s verification was re-run with a stricter scorer.

### Fixed

- `swift:review`:
  - it judges a Mac control against the Mac sizes (20×20 pt minimum, 28×28 pt default) instead of the 44×44 pt touch target, so standard Mac controls are no longer reported;
  - a hit region a screenshot can't show goes under "Not checked" instead of becoming a finding.
- `swift:concurrency`: five "Course Deep Dive" callouts sat inside `swift` code blocks and rendered as code, two of them splitting an example in half. Each now follows its block.
- `swift:concurrency` and `swift:swiftui`: twelve decision trees, build-setting lists and tool-output blocks are marked as text, not Swift.
- `check-apis` no longer reads Markdown headings, shell variables, command-line flags, file paths or name globs inside code spans as Swift names. No real API name dropped out of the check.

### Changed

- The `check-apis` ignore list drops 86 names that no longer need ignoring, and every remaining group's reason now fits its names. 14 names had been filed under the wrong reason.
- The `swift:review` verification scorer:
  - matches a finding by its violation, not its fix;
  - reads `:41–72`-style line continuations;
  - checks each pixel measurement for its own "estimated" mark.
- `docs/internals/review-verification.md` gains a re-run on the new key: 8/8, 2/2 and 4/4, with no false positives and no file edits. It also records that `swift:review` stays out of the model's context.
- The marketplace has a top-level description, so `claude plugin validate .` passes with no warnings.
- `UPSTREAM.md` maps the two concurrency Deviations rows that landed one commit early.
- Known gap: the headless `--add-dir` note for `swift:review` is tested with `--plugin-dir`, not yet with an installed copy.

## [0.1.6] - 2026-09-27

Adds `swift:review`, the plugin's fifth skill. It is our own text, not a fork: an on-demand HIG review of a SwiftUI screen from its code and/or screenshots, run only as `/swift:review`. It judges against `swift:design`'s rules and carries the same project-layer rule. `swift:review` has no eval case: slash-only skills can't be driven by the eval harness, so it ships with a recorded end-to-end verification instead. This release also closes a gap in `swift:testing` that made `callback-confirmation-test` flaky.

### Added

- `swift:review` (`/swift:review <view files or screenshots>`):
  - it reports findings as violation · location · HIG page · fix, most severe first, then what the inputs couldn't show;
  - it never fires on its own and adds nothing to the model's always-loaded context;
  - values sanctioned by a project's design layer aren't findings, and neither is missing Liquid Glass;
  - a screenshot finding marks sizes measured from pixels as estimates.
- A recorded verification for it in `docs/internals/review-verification.md`:
  - planted-violations, project-token and screenshot fixtures in `maintenance/review-fixtures/`;
  - a scorer with unit tests, and an answer key committed before the first run.

### Fixed

- `swift:testing` now explains that a `confirmation` counts only calls made before its closure returns. It shows how to keep the closure waiting for a callback delivered later on another queue, and says not to reach for sleep windows. `callback-confirmation-test` went from 3 of 6 passing runs to 6 of 6.

### Changed

- ADR-0011 records `swift:review`'s design, and ADR-0007's project-layer rule now also binds `swift:review`.
- The registry surfaces name the fifth skill: AGENTS.md, the README, the manual and both manifest descriptions.
- Known gaps:
  - `claude plugin details` counts about 120 always-on tokens for `swift:review`, but the skill stays out of the model's context until it is invoked;
  - "report-only" is enforced for Write and Edit only during the turn that runs the review. Beyond that it rests on the skill's own rule;
  - a headless `claude -p "/swift:review …"` needs `--add-dir <plugin dir>` so the skill can read its reference files.

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
