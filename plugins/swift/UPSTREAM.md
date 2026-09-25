# Upstream

- **Upstream:** https://github.com/AvdLee/SwiftUI-Agent-Skill, folder `skills/swiftui-expert-skill/`, MIT
- **Baseline tag:** `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`)
- **Local import tag:** `upstream-5.1.0`, this repo's first commit: the folder byte-for-byte at the baseline

`git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows every change listed under Deviations. `maintenance/upstream-diff.sh [ref]` shows what upstream changed after the baseline. Porting is manual: read the diff, port what fits, bump the baseline above, add a Ported row.

## Deviations

| File | Change | Why |
|---|---|---|
| `agents/`, `assets/` | Deleted | Codex agent config and logos (~430 KB); Claude Code uses neither |
| `SKILL.md` frontmatter | `name: swiftui`; description names iOS, iPadOS, macOS, visionOS and the visionOS topics | Plugin skill command is `/swift:<name>`; visionOS work must trigger the skill |
| `SKILL.md`, `references/trace-analysis.md`, `references/trace-recording.md` | `${SKILL_DIR}` → `${CLAUDE_SKILL_DIR}` (18 places) | Claude Code substitutes `${CLAUDE_SKILL_DIR}`; `${SKILL_DIR}` would leave commands pointing at `/scripts/…` |
| `LICENSE-upstream` | New: upstream's MIT license text | Travels with every install (the plugin cache copies only `plugins/swift/`) |
| (repo) `tests/test_record_trace.py` → `maintenance/tests/` | Path to `record_trace.py` now `plugins/swift/skills/swiftui/scripts/` | Outside the tagged folder; the test keeps covering the shipped script |

## Ported

| Upstream ref | What we took | Date |
|---|---|---|
| `5.1.0` | Initial import | 2026-09-25 |

## Findings

Names upstream uses that Apple's documentation index did not have on 2026-09-25. `check-apis.py` ignores them for this reason; each still needs a decision: fix as a deviation, or wait for Apple's docs.

| Name | Upstream file | Nearest Apple API |
|---|---|---|
| `AXDateDataAxisDescriptor` | `references/charts-accessibility.md` | `AXNumericDataAxisDescriptor`, `AXCategoricalDataAxisDescriptor` |
| `VerticalTabViewStyle` | `references/latest-apis.md` | `VerticalPageTabViewStyle` (Apple's `CarouselTabViewStyle` metadata says renamed: `VerticalTabViewStyle`, but its deprecation text says `VerticalPageTabViewStyle`) |
| `navigationTransitionSource` | `references/latest-apis.md` | `matchedTransitionSource(id:in:)`, `navigationTransition(_:)` |
| `navigationTransitionDestination` | `references/latest-apis.md` | `matchedTransitionSource(id:in:)`, `navigationTransition(_:)` |
| `sliderNeutralValue` | `references/latest-apis.md` | SwiftUI `Slider.init(value:in:neutralValue:enabledBounds:…)`; also `neutralValue` on `UISlider.TrackConfiguration` and `NSSlider` |
| `Inspector` | `references/macos-window-styling.md`, `references/sheet-navigation-patterns.md` | no `Inspector` type; the API is the `inspector(isPresented:content:)` modifier |
