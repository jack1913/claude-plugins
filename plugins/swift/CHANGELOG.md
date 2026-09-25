# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
