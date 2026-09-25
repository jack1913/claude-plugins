# Hierarchy and Layout

How a screen ranks, groups, spaces and aligns its content, and how controls sit apart from that content.

**Sources:** [HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [HIG: Designing for iOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ios), [HIG: Designing for iPadOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ipados), [HIG: Designing for macOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-macos), [HIG: Boxes](https://developer.apple.com/design/human-interface-guidelines/boxes), [HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/), [WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [SwiftUI: Form](https://developer.apple.com/documentation/swiftui/form), [SwiftUI: grouped form style](https://developer.apple.com/documentation/swiftui/formstyle/grouped), [SwiftUI: LabeledContent](https://developer.apple.com/documentation/swiftui/labeledcontent), [SwiftUI: GroupBox](https://developer.apple.com/documentation/swiftui/groupbox), [SwiftUI: padding(_:_:)](https://developer.apple.com/documentation/swiftui/view/padding(_:_:)), [SwiftUI: VStack init](https://developer.apple.com/documentation/swiftui/vstack/init(alignment:spacing:content:)), [SwiftUI: scenePadding(_:)](https://developer.apple.com/documentation/swiftui/view/scenepadding(_:))

## Content Layer and Navigation Layer

- A screen has two layers. The content layer holds what people came for: lists, tables, text, media. Bars, tab bars, sidebars and floating controls form a functional layer on top of it that gives structure and stays out of the way until needed ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/))
- Content stays in the content layer. Turning a table or list into glass makes it compete with the bars and blurs the hierarchy ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). When glass fits: `liquid-glass-design.md`; the APIs: `swift:swiftui` → `liquid-glass.md`
- Set controls apart from content with the system material and the scroll edge effect, not with a solid or semi-transparent fill painted behind the bar. A full-screen background runs on under the sidebar, toolbar and tab bar; where a sidebar or inspector would cover part of an image, `backgroundExtensionEffect()` mirrors and blurs it underneath them ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))
- Each control lives in the layer it serves. A tab bar accessory holds features that persist across the app, such as playback controls; an action that belongs to one screen, such as checkout, sits with that screen's content ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- Rank comes from layout and grouping, not decoration: the extra backgrounds and borders that bar items used to carry are no longer needed ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))

## Rank and Reading Order

- People read from the top and from the leading side, so the most important content goes there. Standard components mirror themselves for right-to-left languages, which is one more reason to prefer them over hand-placed views ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))
- Show less up front. Disclosure groups, menus and pushed detail views keep a screen scannable, and the rest is one step away ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). On iPhone, keep the number of on-screen controls low and let secondary details and actions stay discoverable ([HIG: Designing for iOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ios))
- Match density to the device. On iPad, give the large display to content and avoid modal and full-screen transitions where you can ([HIG: Designing for iPadOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ipados)); on Mac, use the big screen to show more at once, with shallower navigation and fewer modal steps, while keeping the density comfortable ([HIG: Designing for macOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-macos))
- Choose the layout from the space the view gets (size classes), never from device type or orientation. Every size keeps the same features; only how much of them is visible changes, as when a tab bar gives way to a sidebar in a wide window ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). SwiftUI mechanics: `swift:swiftui` → `layout-best-practices.md` (Adaptive and Resizable Interfaces)

## Grouping

Related items belong together, and the grouping shows through space, a container shape or a separator ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). SwiftUI's containers draw that grouping for each platform:

| Content | Container |
|---|---|
| Settings, data entry, an inspector | `Form`, one `Section` per group; a header names the group, a footer explains it |
| A label with a value, read-only or editable | `LabeledContent` inside the form or list |
| Rows of text to scan or pick from | `List` |
| A small titled cluster inside a larger view | `GroupBox` |

- `Form` groups data-entry controls and styles them per platform: a grouped list on iOS, aligned stacks on macOS ([SwiftUI: Form](https://developer.apple.com/documentation/swiftui/form)). `.formStyle(.grouped)` gives leading labels and trailing controls in grouped sections, on macOS too ([SwiftUI: grouped form style](https://developer.apple.com/documentation/swiftui/formstyle/grouped))
- `LabeledContent` lays out a label and its value the way the framework's own controls do, and adapts to the container it sits in ([SwiftUI: LabeledContent](https://developer.apple.com/documentation/swiftui/labeledcontent))
- Text reads best in rows; a grid of mixed-size items or many images suits a collection instead ([HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables)). Keep row text short so it doesn't wrap or truncate, and move long text to a detail view ([HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables))
- Pick the list style that suits the data and the platform: on iOS the grouped style sets groups apart with headers, footers and extra space, so there's no need to draw cards ([HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables))
- A `GroupBox` stays small next to the view around it; one that nearly fills the window no longer reads as a group. Don't nest boxes: inside one, show subgroups with padding and alignment. Add a short sentence-case title only when the grouping needs explaining ([HIG: Boxes](https://developer.apple.com/design/human-interface-guidelines/boxes)). `GroupBox` doesn't exist on tvOS or watchOS ([HIG: Boxes](https://developer.apple.com/design/human-interface-guidelines/boxes), [SwiftUI: GroupBox](https://developer.apple.com/documentation/swiftui/groupbox))

## Spacing

- The HIG sets no spacing scale for iOS, iPadOS or macOS. It asks for negative space that shows what belongs together ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). Keeping the gap inside a group smaller than the gap between groups is a convention, not an Apple rule
- Start from the system's spacing. `Form` applies platform styling to everything inside it ([SwiftUI: Form](https://developer.apple.com/documentation/swiftui/form)); a stack with no `spacing:` picks a default distance for each pair of subviews ([SwiftUI: VStack init](https://developer.apple.com/documentation/swiftui/vstack/init(alignment:spacing:content:))); `.padding()` with no length uses a default suited to the platform and context ([SwiftUI: padding(_:_:)](https://developer.apple.com/documentation/swiftui/view/padding(_:_:))); on macOS, `scenePadding()` gives the recommended margin around a window's root view ([SwiftUI: scenePadding(_:)](https://developer.apple.com/documentation/swiftui/view/scenepadding(_:)))
- A value beyond the defaults comes from the project's tokens or the starter set in `tokens.md`, reused across screens so the rhythm holds. That scale is a convention, not an Apple rule
- Space around a control counts as much as its size: about 12 pt around a control with a bezel, about 24 pt around the visible edges of one without ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)). On visionOS, keep button centres at least 60 pt apart so the hover effect doesn't cover a neighbour ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))

## Alignment

- Line items up on shared edges so the eye reads them as related, and indent an item to show it belongs under the one before it ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))
- Give each group one alignment edge. A text stack is `VStack(alignment: .leading)`, not a mix of centred and leading lines ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). The system's own text moved to bolder, leading-aligned type in places such as alerts and onboarding for readability ([WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- Let `LabeledContent` and grouped forms line labels and values up, rather than aligning them by hand with fixed-width frames ([SwiftUI: LabeledContent](https://developer.apple.com/documentation/swiftui/labeledcontent), [SwiftUI: grouped form style](https://developer.apple.com/documentation/swiftui/formstyle/grouped))

## Margins and Safe Areas

- Content and controls stay inside the safe area and the system margins, so the Dynamic Island, the status bar and the bars never cover them; only backgrounds extend past. System layout guides also cap the width of text so long lines stay readable ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). Which modifier to use (`safeAreaBar`, `safeAreaInset`, `safeAreaPadding`, `ignoresSafeArea`): `swift:swiftui` → `layout-best-practices.md` (Adaptive Safe Areas)
- Mac: keep controls and critical information away from a window's bottom edge, since people often drag windows partly off the screen, and keep content clear of the camera housing along the top edge ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))
- visionOS: windows resize, so the layout has to follow; at very large sizes keep content centred horizontally. Minimum and maximum sizes are there to prevent overlap, not to stop resizing ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). APIs: `swift:swiftui` → `visionos.md`
- Test the extremes first: the largest and smallest layouts, then other size classes, localisations and text sizes ([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))

## Example: a Settings Form

Nothing below sets a font, colour or spacing value; the form supplies them on each platform.

```swift
import SwiftUI

struct NotificationSettingsView: View {
    @State private var allowsNotifications = true
    @State private var showsPreviews = true
    @State private var summaryHour = 8

    var body: some View {
        Form {
            Section {
                Toggle("Allow Notifications", isOn: $allowsNotifications)
                Toggle("Show Previews", isOn: $showsPreviews)
                    .disabled(!allowsNotifications)
            } footer: {
                Text("Previews show the first line of each message.")
            }

            Section("Daily Summary") {
                Picker("Delivery Time", selection: $summaryHour) {
                    Text("Morning").tag(8)
                    Text("Evening").tag(18)
                }
                LabeledContent("Next Summary", value: "Tomorrow")
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Notifications")
    }
}
```
