# Platform Availability of Liquid Glass and 26-era APIs

Where each API exists, generated from Apple's documentation JSON by `maintenance/check-apis.py --write-table` (repository only). Do not edit the table by hand. A cell holds the version the API arrived in; — means the platform lacks it. For what to use instead on visionOS, see `visionos.md`; for fallbacks below 26, see `liquid-glass.md` → Fallback Strategies.

<!-- BEGIN GENERATED: maintenance/check-apis.py --write-table -->
| API | iOS | iPadOS | Mac Catalyst | macOS | visionOS | watchOS | tvOS | Notes |
|---|---|---|---|---|---|---|---|---|
| `glassEffect(_:in:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)> |
| `GlassEffectContainer` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/glasseffectcontainer> |
| `Glass.interactive(_:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/glass/interactive(_:)> |
| `GlassButtonStyle` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/glassbuttonstyle> |
| `glassProminent` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/primitivebuttonstyle/glassprominent> |
| `glassEffectUnion(id:namespace:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/glasseffectunion(id:namespace:)> |
| `glassEffectTransition(_:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/glasseffecttransition(_:)> |
| `glassEffectID(_:in:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/glasseffectid(_:in:)> |
| `scrollEdgeEffectStyle(_:for:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/scrolledgeeffectstyle(_:for:)> |
| `ToolbarSpacer` | 26.0 | 26.0 | 26.0 | 26.0 | — | — | — | <https://developer.apple.com/documentation/swiftui/toolbarspacer> |
| `sharedBackgroundVisibility(_:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | — | — | <https://developer.apple.com/documentation/swiftui/toolbarcontent/sharedbackgroundvisibility(_:)> |
| `tabViewBottomAccessory(content:)` | 26.0 | 26.0 | 26.0 | — | — | — | — | <https://developer.apple.com/documentation/swiftui/view/tabviewbottomaccessory(content:)> |
| `backgroundExtensionEffect()` | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/backgroundextensioneffect()> |
| `tabBarMinimizeBehavior(_:)` | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/tabbarminimizebehavior(_:)> |
| `safeAreaBar(edge:alignment:spacing:content:)` | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/view/safeareabar(edge:alignment:spacing:content:)> |
| `ConcentricRectangle` | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/concentricrectangle> |
| `rect(corners:isUniform:)` | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | 26.0 | <https://developer.apple.com/documentation/swiftui/shape/rect(corners:isuniform:)> |
<!-- END GENERATED -->
