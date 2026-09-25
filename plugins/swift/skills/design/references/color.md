# Colour

Which colours text, backgrounds, accents and status indicators use, and how they hold up in dark mode and at higher contrast.

**Sources:** [HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/), [WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [SwiftUI: foregroundStyle(_:)](https://developer.apple.com/documentation/swiftui/view/foregroundstyle(_:)), [SwiftUI: accentColor](https://developer.apple.com/documentation/swiftui/color/accentcolor), [SwiftUI: tint(_:)](https://developer.apple.com/documentation/swiftui/view/tint(_:)), [SwiftUI: Color init(_:bundle:)](https://developer.apple.com/documentation/swiftui/color/init(_:bundle:)), [SwiftUI: Form](https://developer.apple.com/documentation/swiftui/form)

## System and Semantic Colours

- Use the system colours. They already have light, dark and increased-contrast variants and adjust to vibrancy by themselves ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color)). Never copy their published values into code: Apple changes them between releases ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color)), and retuned the whole family across Light, Dark and Increased Contrast in 2025 ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- Choose a colour by its role, not its look. For text, the hierarchical styles `.primary`, `.secondary`, `.tertiary` and `.quaternary` derive from the current foreground style ([SwiftUI: foregroundStyle(_:)](https://developer.apple.com/documentation/swiftui/view/foregroundstyle(_:))), and iOS defines label colours for the same four levels of content ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Don't give a semantic colour a different job: the separator colour is not a text colour, and the secondary label colour is not a background ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- One colour, one meaning. If a colour marks what is interactive, don't also use it for static text ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Backgrounds: iOS has a plain set and a grouped set, each with primary, secondary and tertiary levels for nesting, and grouped tables use the grouped set ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color)). A `Form` appears as a grouped list on iOS ([SwiftUI: Form](https://developer.apple.com/documentation/swiftui/form)), so leave its background to the system. A custom background also hides the base-to-elevated shift that dark mode uses to lift sheets and popovers ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))
- When people pick a colour, give them the system picker (`ColorPicker`) ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))

```swift
VStack(alignment: .leading) {
    Text(title)
        .font(.headline)
    Text(subtitle)
        .font(.subheadline)
        .foregroundStyle(.secondary)
}

// Not this: a fixed grey that doesn't adapt to dark mode or Increase Contrast
Text(subtitle)
    .foregroundStyle(Color(red: 0.45, green: 0.45, blue: 0.45))
```

## Accent and Tint

- The accent colour is the app-wide theme for controls. Set it once in the asset catalog and read it as `Color.accentColor` ([SwiftUI: accentColor](https://developer.apple.com/documentation/swiftui/color/accentcolor))
- On macOS, your accent shows only while people keep the system accent setting on multicolor; any other choice replaces it, apart from sidebar icons you gave a fixed colour ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [SwiftUI: accentColor](https://developer.apple.com/documentation/swiftui/color/accentcolor))
- `tint(_:)` overrides the accent for one view, and user settings never override it, so keep it for colour that adds meaning to a control, such as a green Answer beside a red Decline ([SwiftUI: tint(_:)](https://developer.apple.com/documentation/swiftui/view/tint(_:)))
- Spend colour on few elements. On controls and glass, keep it for the primary action and for status; a prominent button carries the colour in its background, not in its label, and several coloured control backgrounds together cancel each other out ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). Colour for brand and mood belongs in the content layer ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/))
- Fit the accent to the content. Over colourful content, keep bars monochrome or choose an accent that stands clearly apart; over mostly neutral content, the brand colour works well as the accent ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Keep the resting state readable. Colourful content may pass under the bars while scrolling, but the top of a screen shouldn't park similar colours under controls ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))

## Dark Mode

- Follow the system appearance and offer no in-app light/dark switch: people expect their system choice to apply, and the Auto setting can change it while the app is open ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)). A permanently dark interface suits only the rare app built around immersive media ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))
- A custom colour is an asset-catalog colour set with a light and a dark variant, and an increased-contrast version of each ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)). `Color("Name")` loads it, and SwiftUI picks the variant from the environment at render time ([SwiftUI: Color init(_:bundle:)](https://developer.apple.com/documentation/swiftui/color/init(_:bundle:))). Supply both variants even for an app that ships in one appearance, because Liquid Glass adapts between them ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- A dark variant is not an inversion of the light one: backgrounds get dimmer and foregrounds brighter ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))
- Images: darken a content image with a white background slightly so it doesn't glow in dark mode, and give an icon that works in only one appearance a second variant in the asset catalog ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))
- visionOS and watchOS have no Dark Mode ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)). On visionOS the room shows through the window's glass and changes how colours read, so use colour sparingly there and put it on heavy text or broad areas, where it stays visible ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))

## Contrast

- The minimum ratios that Accessibility Inspector checks, taken from WCAG level AA ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)):

| Text | Minimum contrast |
|---|---|
| Up to 17 pt, any weight | 4.5:1 |
| 18 pt and larger, any weight | 3:1 |
| Bold, any size | 3:1 |

- Check both appearances. If the default colours fall short, the app has to reach these ratios at least while Increase Contrast is on ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))
- For your own foreground and background pairs, aim for 7:1, above all in small text ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))
- In dark mode, test with Reduce Transparency and Increase Contrast turned on, one at a time and together; dark text on a dark background is where contrast tends to drop ([HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))

## Status Colours

- Colour never carries meaning alone. Pair every status colour with a symbol shape or a text label, because people with colour blindness can struggle with pairs such as red and green or blue and orange ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Use the system colours (`.green`, `.orange`, `.red`) for status so they keep their contrast variants ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)), and check what each one means where the app ships: red signals danger in some cultures and something positive in others ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Colour the symbol and leave the words in the primary style, so the text keeps full contrast and the colour only repeats what the words say:

```swift
struct SyncStatusLabel: View {
    let title: String   // "Synced", "Sync Failed"
    let symbol: String  // "checkmark.circle.fill", "exclamationmark.triangle.fill"
    let color: Color    // .green, .red

    var body: some View {
        Label {
            Text(title)
        } icon: {
            Image(systemName: symbol)
                .foregroundStyle(color)
        }
    }
}
```
