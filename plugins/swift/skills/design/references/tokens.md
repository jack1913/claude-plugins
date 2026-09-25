# Design Tokens

How to work with a project's own tokens, and what to suggest when it has none; the starter set below is a convention, not an Apple rule.

**Sources:** [HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode), [HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/), [SwiftUI: smooth](https://developer.apple.com/documentation/swiftui/animation/smooth), [SwiftUI: snappy](https://developer.apple.com/documentation/swiftui/animation/snappy)

## Project Has Tokens

- Look before writing a view: search the code for token types (`enum Spacing`, `AppColor`, `Theme`), look for colour sets in the asset catalogs (`*.colorset` folders), and read the project's instructions file (CLAUDE.md, AGENTS.md) and any project design skill
- Use the tokens for every spacing, radius, colour, font and animation value, and never add a literal beside them
- A value the tokens don't cover yet becomes a new token, named for its role and added where the others live, not a one-off literal in the view
- When the project's layer and this skill disagree, the project wins

## Project Has None

Suggest this starter set rather than adding it unasked, and present it as a convention. The HIG publishes no spacing or radius scale. What HIG Layout does ask for is a consistent layout, related items grouped by the space around them, and content kept inside the safe areas, margins and layout guides the system defines ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). HIG Accessibility does name padding around controls, so that taps land on the intended one: about 12 pt around a control with a bezel, about 24 pt around the visible edges of one without ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)). Steps of 4 and 8 points are a common habit, not a guideline.

```swift
import SwiftUI

enum Spacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
}

enum Radius {
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 20
}

enum Motion {
    static let standard: Animation = .smooth
    static let quick: Animation = .snappy
}
```

In a view:

```swift
// Tokens and text styles
HStack(spacing: Spacing.sm) {
    Image(systemName: "wifi")
    Text(name).font(.body)
}
.padding(.vertical, Spacing.xs)
.animation(Motion.quick, value: isConnected)

// Not this
HStack(spacing: 8) {
    Image(systemName: "wifi")
    Text(name).font(.system(size: 17))
}
```

What stays outside the token file:

- **Fonts** stay on text styles. Map each text role to a style (`.headline` for a row title, `.body` for content, `.caption` for metadata) rather than to a point size; the styles carry Dynamic Type scaling and keep the hierarchy intact as people change text size ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)). A custom value that must grow with text uses `@ScaledMetric`; the pattern is in `swift:swiftui` → `accessibility-patterns.md`.
- **Colours** stay semantic: system colours such as `.primary`, `.secondary`, `Color.accentColor` and `.tint`, or asset-catalog colour sets with light and dark variants, each with an increased-contrast variant as well ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)). Don't copy system colour values into code; Apple may change them between releases ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color)).

Notes on the scales:

- **Radius** tokens are for shapes that stand alone. A shape nested inside another, such as artwork in a card, reads better concentric with its container: its radius is the container's radius minus the padding between them ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/)). SwiftUI's `ConcentricRectangle` keeps a shape concentric with its container for you ([WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/)); where it exists is in `swift:swiftui` → `platform-availability.md`.
- **Motion** tokens name a purpose, not a duration. `.smooth` is a spring without bounce and `.snappy` a spring with a little bounce ([SwiftUI: smooth](https://developer.apple.com/documentation/swiftui/animation/smooth), [SwiftUI: snappy](https://developer.apple.com/documentation/swiftui/animation/snappy)). Animate only with a purpose, such as showing a change of state or giving feedback, and keep feedback animation brief ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion)). The tokens don't replace a Reduce Motion check: with the setting on, cut automatic and repeating motion and prefer fades to slides and zooms ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)).

## How to Introduce It

1. Put the set in one file, `DesignTokens.swift`, in the app target (or in a shared package when several targets use it).
2. Replace literals in the files a change already touches; don't sweep the whole project in one go.
3. Add a line to the project's instructions file saying where the tokens live and that views use them instead of literals, so later sessions find them.
