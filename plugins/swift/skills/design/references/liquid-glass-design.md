# Liquid Glass Design

When a design uses Liquid Glass, which variant it takes, where colour goes on it, and how its shapes nest; the APIs, their fallbacks and where each one exists are in `swift:swiftui`.

**Sources:** [HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials), [HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars), [HIG: Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass), [Applying Liquid Glass to custom views](https://developer.apple.com/documentation/swiftui/applying-liquid-glass-to-custom-views), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/), [WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/), [SwiftUI: Glass.clear](https://developer.apple.com/documentation/swiftui/glass/clear), [SwiftUI: ConcentricRectangle](https://developer.apple.com/documentation/swiftui/concentricrectangle), [SwiftUI: rect(corners:isUniform:)](https://developer.apple.com/documentation/swiftui/shape/rect(corners:isuniform:))

The APIs live in `swift:swiftui`: `liquid-glass.md` (modifiers, containers, morphing, material fallbacks below 26), `platform-availability.md` (where each API exists) and `visionos.md` (visionOS has no glass modifiers and neither `Glass` variant; its windows are glass already, and custom pieces use `glassBackgroundEffect`).

## Glass Is the Navigation Layer

- Glass makes up one functional layer for navigation and controls, such as toolbars, tab bars, sidebars and controls that float over content, and content scrolls beneath it ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass))
- Keep glass out of the content layer. A list or table turned into glass competes with the bars and blurs which layer is which ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)); to separate things inside the content, such as an app background, use the standard materials ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials)). Sliders and toggles are the exception, and the system handles it: their knob turns to glass only while someone is using it ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/))
- At rest, for example when the app opens, content and glass shouldn't overlap: move or scale the content so the two stay apart ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). Colourful content may pass under the bars while people scroll, but the resting state has to read clearly ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Controls sit on the system material, never straight on content. The scroll edge effect marks where floating controls meet scrolling content; it isn't decoration or a dimming overlay, so leave it out where nothing floats. Use one per view, and don't mix or stack its two styles: soft, the default and the usual pick on iOS and iPadOS, and hard, mostly on macOS, where pinned headers and controls without a background need a firmer edge ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/)). The API is `scrollEdgeEffectStyle(_:for:)`

## Standard Components First

- Bars, tab bars, sidebars, sheets, popovers, menus and controls built from standard SwiftUI components take on glass by themselves when the app is built with the current SDK, and they adapt to overlap and focus without extra code ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/))
- Remove what covers the material: custom backgrounds on navigation stacks, split views, toolbars and tab bars, a `presentationBackground(_:)` on a sheet, and darkening layers behind bar items all sit over the glass or fight the scroll edge effect ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/))
- For a glass button, use a glass button style instead of building the effect by hand ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass)). The prominent style fills the button's background with the accent colour, which is how the system marks a primary action such as Done ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color)), so `.glassProminent` goes on the one primary action and `.glass` on the others; see `liquid-glass.md` → Glass Button Styles
- Custom glass is for your own controls that float above content, like the map controls in Maps ([WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/)), and only for the most important of them. Each extra glass control draws attention away from the content ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass)), and many effects on screen at once cost rendering time ([Applying Liquid Glass to custom views](https://developer.apple.com/documentation/swiftui/applying-liquid-glass-to-custom-views))
- Put the material on the control itself, not on the views inside it ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))

## Regular or Clear

| Variant | Behaviour | Use it for |
|---|---|---|
| Regular | Adapts to what's behind it and stays legible over any content, at any size, with anything on top | Almost everything, as most system components do, and always for text-heavy components such as alerts, sidebars and popovers |
| Clear | Stays more transparent and has none of the adaptive behaviour | Controls floating over photos, video and other rich media |

The variants are described in [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/) and [HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials).

- Clear takes all three conditions: the element floats over media-rich content, that content can take a dimming layer without harm, and whatever sits on the glass is bold and bright ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). If one fails, use regular
- Over bright content, clear glass usually needs a dark dimming layer behind it; the HIG suggests 35% opacity. Content that is already dark, or AVKit's standard playback controls, which bring their own dimming, needs none ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials)). For small glass elements, dim only the area around them so the rest of the content keeps its colour ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). The `Glass.clear` page shows a dimming layer in code ([SwiftUI: Glass.clear](https://developer.apple.com/documentation/swiftui/glass/clear))
- Never mix the two variants; each has its own character and its own job ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/))
- People can choose a preferred glass look in Settings, and Reduce Transparency and Increase Contrast change both variants ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials)); test custom glass with those settings on ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass))

## No Glass on Glass

- Don't stack glass on glass: layered glass elements quickly make the interface look cluttered and confusing ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). Anything placed on glass, such as a badge, a label or a nested button, uses fills, transparency and vibrancy, so it reads as a thin layer of the same material ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/))
- Keep the standard spacing between glass controls instead of crowding or overlapping them ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass))
- Glass can't sample other glass, so custom glass elements near each other share one `GlassEffectContainer`, which also lets them blend and morph into each other ([WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/), [Applying Liquid Glass to custom views](https://developer.apple.com/documentation/swiftui/applying-liquid-glass-to-custom-views)). Mechanics: `liquid-glass.md` → GlassEffectContainer

## Tint and Colour

- Glass has no colour of its own; it takes on the colours of the content behind it ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Tint only what must stand out: the primary action or element, and status indicators. When everything is tinted, nothing stands out; a brand colour belongs in the content layer ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/), [HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- To emphasise a primary action, colour its background rather than its symbol or label, and don't colour the backgrounds of several controls ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- Tint with the material itself (`Glass.tint(_:)`, or the prominent button style), never with an opaque fill. A solid fill loses the glass character; tinted glass shifts with what's behind it and stays legible ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/))
- Toolbar icons are monochrome by default. Tint one only when the colour means something, such as a call to action or the next step, and never for looks ([WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/), [HIG: Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars))
- Over colourful content, keep toolbars and tab bars monochrome or pick an accent that clearly differs from the content, and don't give labels colours close to the content's ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color), [HIG: Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars), [HIG: Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars))
- A custom colour on a control is a system colour, or a colour set with light, dark and increased-contrast variants ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass)); more in `color.md`

## Concentric Corners

- The hardware sets the curve: its corners guide the radius of controls, sheets and windows, and nested shapes share a centre with the shape around them ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass))
- Three kinds of shape build this: a fixed radius, a capsule (radius half the height), and a concentric shape, whose radius is the parent's radius minus the padding between them ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- Corners that look pinched or flared usually sit on a nested shape, such as artwork in a card; make the inner shape concentric and let the system work out its radius ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- Near the screen edge on iPhone, set a capsule further in from the edge; on iPad and Mac, follow the window's corner with a concentric shape ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/)). A button placed low in a sheet shares the sheet's corner centre ([WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/))
- A component that sometimes sits in a container and sometimes stands alone takes a concentric shape that falls back to a fixed radius ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/)). In SwiftUI that is `ConcentricRectangle` with `.concentric(minimum:)` corners: where a corner is far from the container's corners, or the device's corners are square, the minimum keeps it rounded ([SwiftUI: ConcentricRectangle](https://developer.apple.com/documentation/swiftui/concentricrectangle)). `rect(corners:isUniform:)` with `isUniform: true` gives all four corners the largest radius it computes, for a symmetric shape ([SwiftUI: rect(corners:isUniform:)](https://developer.apple.com/documentation/swiftui/shape/rect(corners:isuniform:)))
- System views provide the container shape; a custom container declares its own with `containerShape(_:)` ([SwiftUI: ConcentricRectangle](https://developer.apple.com/documentation/swiftui/concentricrectangle)). Standard toolbar items are already concentric with the bar, and a custom item in a toolbar has to be as well ([HIG: Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars))
- Capsules suit touch layouts; on the desktop, save them for actions that must stand out. On macOS, controls at the mini, small and medium sizes keep rounded rectangles, which suit dense areas such as inspectors, while large controls become capsules ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [WWDC25 323](https://developer.apple.com/videos/play/wwdc2025/323/))

The radii below are literals only to keep the example short; take them from the project's tokens or `tokens.md`. Below the deployment target that `platform-availability.md` gives for `ConcentricRectangle`, gate it with `if #available` and fall back to a fixed radius, as `swift:swiftui` requires.

```swift
struct AlbumTile: View {
    let title: String

    var body: some View {
        VStack(alignment: .leading) {
            // Stands in for the artwork: its corners follow the tile's, less the padding
            Rectangle()
                .fill(.tint)
                .aspectRatio(1, contentMode: .fit)
                .clipShape(ConcentricRectangle(corners: .concentric(minimum: 8), isUniform: true))
            Text(title)
                .font(.headline)
        }
        .padding()
        .background(.quaternary, in: .rect(cornerRadius: 24))
        .containerShape(.rect(cornerRadius: 24))
    }
}
```
