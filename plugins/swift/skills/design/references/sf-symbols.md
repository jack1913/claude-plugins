# SF Symbols

How to choose a symbol, its variant and rendering mode, size it to the text beside it, and animate it only when the motion means something.

**Sources:** [HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols), [HIG: Icons](https://developer.apple.com/design/human-interface-guidelines/icons), [HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [SwiftUI: SymbolVariants](https://developer.apple.com/documentation/swiftui/symbolvariants), [SwiftUI: symbolVariant(_:)](https://developer.apple.com/documentation/swiftui/view/symbolvariant(_:)), [SwiftUI: symbolRenderingMode(_:)](https://developer.apple.com/documentation/swiftui/view/symbolrenderingmode(_:)), [SwiftUI: palette](https://developer.apple.com/documentation/swiftui/symbolrenderingmode/palette), [SwiftUI: init(systemName:variableValue:)](https://developer.apple.com/documentation/swiftui/image/init(systemname:variablevalue:)), [SwiftUI: imageScale(_:)](https://developer.apple.com/documentation/swiftui/view/imagescale(_:)), [SwiftUI: symbolEffect(_:options:value:)](https://developer.apple.com/documentation/swiftui/view/symboleffect(_:options:value:)), [SwiftUI: symbolEffect(_:options:isActive:)](https://developer.apple.com/documentation/swiftui/view/symboleffect(_:options:isactive:)), [SwiftUI: ContentTransition.symbolEffect(_:options:)](https://developer.apple.com/documentation/swiftui/contenttransition/symboleffect(_:options:)), [SwiftUI: Transition.symbolEffect(_:options:)](https://developer.apple.com/documentation/swiftui/transition/symboleffect(_:options:)), [Symbols: DiscreteSymbolEffect](https://developer.apple.com/documentation/symbols/discretesymboleffect), [Symbols: IndefiniteSymbolEffect](https://developer.apple.com/documentation/symbols/indefinitesymboleffect), [Symbols: BounceSymbolEffect](https://developer.apple.com/documentation/symbols/bouncesymboleffect), [Symbols: WiggleSymbolEffect](https://developer.apple.com/documentation/symbols/wigglesymboleffect), [Symbols: BreatheSymbolEffect](https://developer.apple.com/documentation/symbols/breathesymboleffect), [Symbols: RotateSymbolEffect](https://developer.apple.com/documentation/symbols/rotatesymboleffect), [Symbols: DrawOnSymbolEffect](https://developer.apple.com/documentation/symbols/drawonsymboleffect)

## Choosing a Symbol

- For a common action, use the symbol the HIG lists for it, for example `trash` (Delete), `square.and.pencil` (Compose), `square.and.arrow.up` (Share), `magnifyingglass` (Search) and `ellipsis` (More) ([HIG: Icons](https://developer.apple.com/design/human-interface-guidelines/icons))
- The same action gets the same symbol on every device ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/)). Where a symbol could be misread, as a pencil or a checkmark can be for Edit or Select, use a text label; in a menu of closely related actions, show the symbol once for the group and let the text tell the items apart ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- A symbol exists only from the OS release that introduced it, so check each one's availability in the SF Symbols app against the deployment target ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols))
- A custom symbol starts from an exported template of a similar symbol, so it matches in detail, weight and alignment; it never copies an Apple product, and it gets an accessibility label ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)). Label patterns: `swift:swiftui` → `accessibility-patterns.md`

## Variants

- Outline is the usual form and suits toolbars, lists and symbols set beside text. Fill adds weight and marks selection; slash says something is unavailable; an enclosing circle or square keeps a symbol legible at small sizes ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols))
- Let the container choose where it does: SwiftUI fills the symbols in tab items and swipe actions by itself ([SwiftUI: SymbolVariants](https://developer.apple.com/documentation/swiftui/symbolvariants)), and toolbars use the outline ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)). Write the base name, `Label("Inbox", systemImage: "tray")`, and add `.symbolVariant(.fill)` only for a selected state of your own; a symbol that has no such variant stays as it is ([SwiftUI: symbolVariant(_:)](https://developer.apple.com/documentation/swiftui/view/symbolvariant(_:)))
- Standard toolbars, tab bars and buttons draw the selected state themselves, so they need no separate selected icon ([HIG: Icons](https://developer.apple.com/design/human-interface-guidelines/icons))

## Rendering Modes

| Mode | What it does | Fits |
|---|---|---|
| Monochrome | One colour on every layer | A plain icon where one colour says enough |
| Hierarchical | One colour, at a lower opacity on each lower layer | Depth and emphasis inside one symbol, for example in the accent colour |
| Palette | A separate colour per layer; on a three-layer symbol, two colours leave the second and third layers sharing one | Symbols that must match a particular colour scheme |
| Multicolor | The symbol's own colours, where colour adds meaning (a green `leaf`, a red `trash.slash`) | Symbols whose built-in colours say something |

The modes are from [HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols).

- Set the mode with `.symbolRenderingMode(_:)` ([SwiftUI: symbolRenderingMode(_:)](https://developer.apple.com/documentation/swiftui/view/symbolrenderingmode(_:))). Passing two or three styles to `foregroundStyle` gives the palette colours, and implies palette mode on its own ([SwiftUI: palette](https://developer.apple.com/documentation/swiftui/symbolrenderingmode/palette))
- Whatever the mode, use system colours so the symbol follows dark mode, vibrancy and the accessibility settings ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols), [HIG: Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))
- Check the mode where the symbol is actually used: size and background decide whether its details stay visible, even with the automatic mode ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols))
- Variable colour shows a value that changes over time, such as strength or capacity: `Image(systemName: "speaker.wave.3", variableValue: volume)` colours more of the waves as `volume` rises ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols), [SwiftUI: init(systemName:variableValue:)](https://developer.apple.com/documentation/swiftui/image/init(systemname:variablevalue:))). It shows change, not depth; depth is the hierarchical mode's job ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols))

## Weight and Scale

- Symbols come in the same nine weights as the system font, so a symbol in the same text style as its label matches the label's weight ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)). Size it with a text style through `.font`, not with `resizable()` and a frame, and it also grows with Dynamic Type ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- Icon and text share a weight unless one of them is meant to stand out ([HIG: Icons](https://developer.apple.com/design/human-interface-guidelines/icons))
- For more or less emphasis beside the same text, change the scale rather than the point size: `.imageScale(.small)`, `.medium` (the default) or `.large`, each relative to the font's cap height, keeps the weight match ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols), [SwiftUI: imageScale(_:)](https://developer.apple.com/documentation/swiftui/view/imagescale(_:)))

```swift
// Symbol and text share the style: matching weight, and both scale with Dynamic Type
Label("Attachments", systemImage: "paperclip")
    .font(.headline)

// More emphasis on the symbol, same weight match
HStack {
    Image(systemName: "folder")
        .imageScale(.large)
    Text("Projects")
}
.font(.body)

// Not this: a fixed frame ignores Dynamic Type and the text's weight
Image(systemName: "folder")
    .resizable()
    .frame(width: 24, height: 24)
```

## Symbol Effects

- Animate a symbol only when the motion tells people something: that an action happened, a state changed, or work is going on. Too many effects crowd the interface, and each should suit the app's tone ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols))
- A discrete effect plays once, each time its `value:` changes; an indefinite one runs while `isActive:` is true ([SwiftUI: symbolEffect(_:options:value:)](https://developer.apple.com/documentation/swiftui/view/symboleffect(_:options:value:)), [SwiftUI: symbolEffect(_:options:isActive:)](https://developer.apple.com/documentation/swiftui/view/symboleffect(_:options:isactive:)), [Symbols: DiscreteSymbolEffect](https://developer.apple.com/documentation/symbols/discretesymboleffect), [Symbols: IndefiniteSymbolEffect](https://developer.apple.com/documentation/symbols/indefinitesymboleffect))

| To say | Effect ([HIG: SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)) | In SwiftUI |
|---|---|---|
| An action just happened | Bounce | `.symbolEffect(.bounce, value: addedCount)` |
| Something is ongoing: recording, connecting | Pulse, Breathe, Variable Color | `.symbolEffect(.pulse, isActive: isRecording)` |
| The state changed | Replace; Magic Replace between related symbols | `.contentTransition(.symbolEffect(.replace))` |
| This item is selected | Scale, which lasts until removed | `.symbolEffect(.scale.up, isActive: isSelected)` |
| An easily missed call to action | Wiggle | `.symbolEffect(.wiggle, value: reminderCount)` |
| Work in progress | Rotate | `.symbolEffect(.rotate, isActive: isSyncing)` |
| Progress, or what a symbol stands for | Draw On, Draw Off | `.transition(.symbolEffect(.drawOn))` |

- Availability: `symbolEffect` and Bounce, Pulse, Scale, Variable Color, Replace, Appear and Disappear arrived in iOS 17, macOS 14 and visionOS 1; Wiggle, Breathe and Rotate in iOS 18, macOS 15 and visionOS 2; Draw On and Draw Off in iOS 26, macOS 26 and visionOS 26 ([Symbols: BounceSymbolEffect](https://developer.apple.com/documentation/symbols/bouncesymboleffect), [Symbols: WiggleSymbolEffect](https://developer.apple.com/documentation/symbols/wigglesymboleffect), [Symbols: BreatheSymbolEffect](https://developer.apple.com/documentation/symbols/breathesymboleffect), [Symbols: RotateSymbolEffect](https://developer.apple.com/documentation/symbols/rotatesymboleffect), [Symbols: DrawOnSymbolEffect](https://developer.apple.com/documentation/symbols/drawonsymboleffect)). Below those targets, gate the effect with `if #available` as `swift:swiftui` requires for any newer API
- A repeating effect is automatic, repetitive motion, which HIG Accessibility asks apps to cut back while Reduce Motion is on ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)); the check itself is in `motion.md`
