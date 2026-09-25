# Typography

Which text style each role gets, how text behaves as Dynamic Type grows, and when weight, monospaced digits and line limits are the right tool.

**Sources:** [HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables), [SwiftUI: DynamicTypeSize](https://developer.apple.com/documentation/swiftui/dynamictypesize), [SwiftUI: extraLargeTitle](https://developer.apple.com/documentation/swiftui/font/extralargetitle), [SwiftUI: Font.leading(_:)](https://developer.apple.com/documentation/swiftui/font/leading(_:)), [SwiftUI: monospacedDigit()](https://developer.apple.com/documentation/swiftui/view/monospaceddigit()), [SwiftUI: monospaced(_:)](https://developer.apple.com/documentation/swiftui/view/monospaced(_:)), [SwiftUI: multilineTextAlignment(_:)](https://developer.apple.com/documentation/swiftui/view/multilinetextalignment(_:)), [SwiftUI: lineLimit(_:reservesSpace:)](https://developer.apple.com/documentation/swiftui/view/linelimit(_:reservesspace:)), [SwiftUI: truncationMode(_:)](https://developer.apple.com/documentation/swiftui/view/truncationmode(_:))

## Text Styles, Not Point Sizes

- Give every piece of text a built-in text style. A style carries its own weight, size and leading at each Dynamic Type setting; the styles together make up the hierarchy, and with the system fonts they follow Dynamic Type up to the larger accessibility sizes ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)). Custom fonts that still scale, and `@ScaledMetric` for non-text values: `swift:swiftui` → `accessibility-patterns.md`
- A starting map from role to style (a convention; the sizes are the HIG's iOS and iPadOS values at the default Large setting, [HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)):

| Role | Style | iOS size at Large |
|---|---|---|
| Screen title | `.largeTitle` | 34 pt |
| Section title | `.title2`, `.title3` | 22 pt, 20 pt |
| Row title, emphasis | `.headline` | 17 pt Semibold |
| Content | `.body` | 17 pt |
| Supporting text | `.callout`, `.subheadline` | 16 pt, 15 pt |
| Metadata, timestamps | `.footnote`, `.caption`, `.caption2` | 13 pt, 12 pt, 11 pt |

- Where a custom size is unavoidable, give running text the platform's default size and never go below its minimum (default / minimum): iOS and iPadOS 17 / 11 pt, macOS 13 / 10 pt, visionOS 17 / 12 pt, watchOS 16 / 12 pt, tvOS 29 / 23 pt. A thin custom face needs more than that ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- Use as few typefaces as possible; each extra one muddies the hierarchy and makes the interface look inconsistent ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)). Reach SF and New York through `Font.Design` (`.default`, `.serif`, `.rounded`, `.monospaced`) and never bundle them in the app ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))

## Dynamic Type

- Every screen has to work at every text size, the accessibility sizes included. Test on a device with Larger Accessibility Text Sizes turned on (Settings > Accessibility > Display & Text Size > Larger Text) ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)); in a preview, `.dynamicTypeSize(.accessibility5)` shows the largest one (previews go inside `#if DEBUG`: `swift:swiftui` → `previews.md`)
- Aim to let people enlarge text to at least 200 percent, or 140 percent on watchOS ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))
- At large sizes, change the layout instead of truncating: stack side-by-side items with the text above the secondary item, let rows grow taller, and use fewer columns ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)). `isAccessibilitySize` is true for the five accessibility sizes, which makes it the switch for that change ([SwiftUI: DynamicTypeSize](https://developer.apple.com/documentation/swiftui/dynamictypesize)):

```swift
struct MailboxRow: View {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    let name: String
    let unreadCount: Int

    var body: some View {
        let layout = dynamicTypeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading))
            : AnyLayout(HStackLayout(alignment: .firstTextBaseline))
        layout {
            Text(name)
                .font(.body)
            Text(unreadCount, format: .number)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .monospacedDigit()
        }
    }
}
```

- Not everything needs to grow. People enlarge text to read the content they care about; controls such as tab titles can stay put ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- Keep the hierarchy at every size: primary elements stay near the top even when the text is very large ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- Icons that carry meaning grow with the text; SF Symbols do so when they take the text's style (`sf-symbols.md`) ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- macOS has no Dynamic Type, and its styles are smaller (body 13 pt) ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- visionOS uses heavier body and title styles, and has two more title sizes for wide, editorial layouts: `.extraLargeTitle` and `.extraLargeTitle2`, which exist only on visionOS ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [SwiftUI: extraLargeTitle](https://developer.apple.com/documentation/swiftui/font/extralargetitle))

## Weight and Emphasis

- Weight, size and colour together express importance, and their relative order has to survive a change in text size ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- To emphasise text, apply `.bold()` to its text style and let the system choose the weight: each style has its own emphasised weight, from Medium to Heavy; on iOS, Body becomes Semibold and Title 1 becomes Bold ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)). Keep `.fontWeight(_:)` for the rare case where one specific weight is the point
- Stay with Regular, Medium, Semibold and Bold. Ultralight, Thin and Light are hard to see, most of all at small sizes ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)); a secondary line gets a smaller style or `.foregroundStyle(.secondary)` (`color.md`), not a lighter weight
- The system fonts react to the Bold Text setting by themselves; a custom font must do the same ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- Leading: `.leading(.tight)` on a font helps two lines fit a height-constrained row, `.leading(.loose)` helps long passages and wide columns, and text of three or more lines shouldn't be tightened ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [SwiftUI: Font.leading(_:)](https://developer.apple.com/documentation/swiftui/font/leading(_:)))

## Numbers and Monospaced Text

- Numbers that change in place (timers, counters, prices, progress) or sit in columns get `.monospacedDigit()`. Only the digits become fixed-width, the rest of the text stays proportional and keeps its style, and numbers line up ([SwiftUI: monospacedDigit()](https://developer.apple.com/documentation/swiftui/view/monospaceddigit())); a value that counts up then holds its width instead of shifting its neighbours
- `.monospaced()` makes the whole font fixed-width ([SwiftUI: monospaced(_:)](https://developer.apple.com/documentation/swiftui/view/monospaced(_:))). Keep it for text where every character has to line up or be told apart: code, terminal output, hashes and similar identifiers. For plain numbers it only adds a typeface ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))

```swift
Text(downloadCount, format: .number)
    .font(.body)
    .monospacedDigit()

Text(commitHash)
    .font(.caption)
    .monospaced()

// Not this: a fixed size ignores Dynamic Type, and a monospaced face for a plain count
Text(downloadCount, format: .number)
    .font(.system(size: 11, design: .monospaced))
```

## Line Limits and Truncation

- Truncate as little as you can, and less as text grows: at the largest accessibility size, show as much useful text as at the largest standard size. In a scrolling view, don't truncate unless people can open the full text somewhere else ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography))
- A `Text` wraps onto more lines by default ([SwiftUI: multilineTextAlignment(_:)](https://developer.apple.com/documentation/swiftui/view/multilinetextalignment(_:))), so a `lineLimit` is a design decision: a one-line row title or a two-line summary, with the full text a tap away. `lineLimit(2, reservesSpace: true)` keeps rows the same height when some summaries are shorter ([SwiftUI: lineLimit(_:reservesSpace:)](https://developer.apple.com/documentation/swiftui/view/linelimit(_:reservesspace:)))
- Where both ends of a string matter, such as a file name, `truncationMode(.middle)` keeps the start and the end ([HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables), [SwiftUI: truncationMode(_:)](https://developer.apple.com/documentation/swiftui/view/truncationmode(_:)))
- Keep row text short so it neither wraps nor truncates, and put long text in a detail view ([HIG: Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables))
