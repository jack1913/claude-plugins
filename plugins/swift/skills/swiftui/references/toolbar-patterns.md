# SwiftUI Toolbar Patterns

## Customizable toolbars (iOS 26+, macOS 26+, tvOS 26+, watchOS 26+, visionOS 26+)

Use `.toolbar(id:)` when people should be able to add, remove, or rearrange toolbar content. Every customizable `ToolbarItem` needs a stable, unique string ID. Keep IDs tied to the meaning of the action rather than to a changing array position.

```swift
.toolbar(id: "main-toolbar") {
    ToolbarItem(id: "tag") {
        TagButton()
    }
    ToolbarItem(id: "share") {
        ShareButton()
    }
    ToolbarSpacer(.fixed)
    ToolbarItem(id: "more") {
        MoreButton()
    }
}
```

`ToolbarItem(id:placement:content:)` is available on iOS 14+, macOS 11+, tvOS 14+, and watchOS 7+ (visionOS 1+). The `showsByDefault:` overload is soft-deprecated in the SDK 27 toolchain; use `defaultCustomization(_:options:)` instead.

`ToolbarSpacer` separates groups of toolbar content. `ToolbarSpacer(.fixed)` creates a fixed-width gap; `ToolbarSpacer(.flexible)` expands to push content apart. The initializer also accepts a placement. `ToolbarSpacer` is available on iOS 26+ and macOS 26+; it is unavailable on tvOS, watchOS, and visionOS.

## System-defined toolbar content

`DefaultToolbarItem` places a system-defined item, such as search or the sidebar toggle, at a chosen placement. It is available on iOS 26+, macOS 26+, tvOS 26+, watchOS 26+, and visionOS 26+.

```swift
.toolbar {
    DefaultToolbarItem(kind: .search, placement: .bottomBar)
    DefaultToolbarItem(kind: .sidebarToggle, placement: .navigationBarLeading)
}
```

The `.search` kind is available on iOS, macOS, and visionOS 26+; it is unavailable on tvOS and watchOS. The `.sidebarToggle` kind is available on every platform supported by `DefaultToolbarItem`.

The `.largeSubtitle` placement supplies content in the large navigation-title subtitle area. It takes precedence over the value supplied by `navigationSubtitle(_:)`. It is available on iOS 26+ only.

On iOS 26+ and macOS 26+, use `sharedBackgroundVisibility(.hidden)` on the `ToolbarItem` when one item should not participate in the shared Liquid Glass background. It is unavailable on tvOS, watchOS, and visionOS. Apply `badge(_:)` to the item's view to show an indicator:

```swift
.toolbar {
    ToolbarItem(placement: .topBarTrailing) {
        Button("Notifications", systemImage: "bell") { }
            .badge(unreadCount)
    }
    ToolbarItem(placement: .topBarTrailing) {
        ProfileButton()
    }
    .sharedBackgroundVisibility(.hidden)
}
```

## Search

Use `.searchToolbarBehavior(.minimize)` to opt into a compact, button-like search control that expands when selected. The modifier is available on all aligned 26 releases, but `.minimize` is available only on iOS and visionOS; use `.automatic` elsewhere.

## Transitioning from toolbar controls

Attach `matchedTransitionSource(id:in:)` to toolbar content that presents another view, then use a zoom navigation transition with the same ID and namespace in the destination.

```swift
@Namespace private var namespace

.toolbar {
    ToolbarItem(placement: .topBarTrailing) {
        Button("Show details", systemImage: "info") {
            isPresented = true
        }
    }
    .matchedTransitionSource(id: "details", in: namespace)
}
.sheet(isPresented: $isPresented) {
    DetailsView()
        .navigationTransition(.zoom(sourceID: "details", in: namespace))
}
```

The view `matchedTransitionSource(id:in:)` is available on iOS 18+, macOS 15+, tvOS 18+, watchOS 11+, and visionOS 2+. Its toolbar-content form is available on iOS 26+ and is unavailable on macOS, tvOS, watchOS, and visionOS. The zoom transition, `zoom(sourceID:in:)`, is available on iOS, iPadOS, and Mac Catalyst 18+, tvOS 18+, watchOS 11+, and visionOS 2+, and is unavailable on macOS; `navigationTransition(_:)` itself is available on macOS 15+.

## Adaptive vertical bars (27.1+)

Build with the 27.1 SDK and attach `.toolbar` content to a system `NavigationStack`, `NavigationSplitView`, or `TabView`. Those containers can move eligible controls between horizontal and vertical bars as available space and context change; a hand-built bar does not gain this behavior.

Describe every action with both a title and icon, even when the visible representation is symbol-only. The system needs the title for accessibility, expanded representations, and overflow:

```swift
NavigationStack {
    ContentView()
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Close", systemImage: "xmark") { close() }
            }
            ToolbarItem(placement: .topBarPinnedTrailing) {
                Button("Share", systemImage: "square.and.arrow.up") { share() }
            }
        }
}
```

Keep semantic placements so ordering remains meaningful on either axis: navigation and cancellation actions lead, prominent actions use `.topBarPinnedTrailing`, and bottom-bar actions remain grouped as bottom actions. Do not position items by reading a physical edge.

SwiftUI infers axis eligibility from the item. Symbol-capable items can move vertically, while title-only and complex custom views generally remain horizontal. Override that inference only when needed:

```swift
ToolbarItem {
    SelectOrDoneButton()
}
#if os(iOS)
.axisBehavior(.horizontalOnly)
#endif

ToolbarItem {
    CompactCompassControl()
}
#if os(iOS)
.axisBehavior(.verticalPreferred)
#endif
```

Use `.horizontalOnly` when related states must stay together and one representation cannot fit a fixed-width vertical bar. Use `.verticalPreferred` only when a custom view has a compact vertical representation. Otherwise keep `.automatic`. `axisBehavior(_:)` and `.automatic` exist on every platform, but `.horizontalOnly` and `.verticalPreferred` exist only on iOS, iPadOS and Mac Catalyst: the SDK marks them unavailable on macOS, tvOS, visionOS and watchOS, so they sit inside `#if os(iOS)`, which also covers Mac Catalyst. No availability check can admit them on the other platforms.

For a custom item's presentation details, a view built for the 27.1 SDK can read `@Environment(\.toolbarVerticalEdge)`. A non-`nil` value means the environment supports a vertical bar on that directional edge; use it to select a compact representation, not to add safe-area spacing. Keep the property declaration in a type marked `@available(iOS 27.1, macOS 27.1, macCatalyst 27.1, tvOS 27.1, visionOS 27.1, watchOS 27.1, *)` and selected behind `#available` with the same platforms. Name 27.1 for each platform the target builds for: the `*` admits unnamed platforms at their deployment target. `toolbarVerticalEdge` and the vertical-bar modifiers in this section (`axisBehavior(_:)`, `toolbarVerticalCompressionBehavior(_:)`, `toolbarVerticalBehavior(_:)`) are introduced in 27.1 on every platform, Mac Catalyst included, so they need only the availability check; the four iOS-only values in this section (`.horizontalOnly`, `.verticalPreferred`, `.prefersToolbarItems` and `.prefersTabBar`) are the exception.

When a view combines a toolbar and tab bar, `.toolbarVerticalCompressionBehavior(.prefersToolbarItems)` keeps toolbar actions visible longer, while `.prefersTabBar` favors destinations. The default `.automatic` compresses toolbar items first. Like the axis values above, `.prefersToolbarItems` and `.prefersTabBar` exist only on iOS, iPadOS and Mac Catalyst, so put the modifier call inside `#if os(iOS)`:

```swift
@available(iOS 27.1, macOS 27.1, macCatalyst 27.1, tvOS 27.1, visionOS 27.1, watchOS 27.1, *)
struct CompressedToolbarTabs: View {
    var body: some View {
        TabView {
            // tabs
        }
        #if os(iOS)
        .toolbarVerticalCompressionBehavior(.prefersToolbarItems)
        #endif
    }
}
```

Select this view behind `#available` with the same platforms; inside `#if os(iOS)` the modifier still needs iOS 27.1.

Choose based on the experience's primary task, then use the existing SDK 27 [overflow and visibility](#sdk-27-overflow-and-visibility) APIs to prioritize individual actions rather than duplicating overflow controls.

Most interfaces should keep automatic vertical behavior. Use `.toolbarVerticalBehavior(.disabled)` only for a narrow exception, such as a bottom-heavy single-page interface or a sheet whose lone toolbar item would cost more space than it saves. All of these vertical-bar APIs require 27.1 on every platform (iOS, iPadOS, Mac Catalyst, macOS, tvOS, visionOS and watchOS), `.disabled` included; only `.horizontalOnly`, `.verticalPreferred`, `.prefersToolbarItems` and `.prefersTabBar` are iOS-only. The first example's `.topBarPinnedTrailing` requires iOS 27 or visionOS 27 and has no macOS, tvOS or watchOS release; gate it as in [SDK 27 overflow and visibility](#sdk-27-overflow-and-visibility), and preserve the ordinary system toolbar as the earlier-OS fallback.

## SDK 27 overflow and visibility

When toolbar content does not fit, the system can move lower-priority items into an overflow menu. `visibilityPriority(_:)` is available on iOS 27+, macOS 26.1+, watchOS 27+, tvOS 27+, and visionOS 27+. `.automatic` is available on every supported platform. `.low` and `.high` are available only on iOS and macOS. `ToolbarItemVisibilityPriority(higherThan:)` and `(lowerThan:)` are available on iOS 27+ and macOS 27+. When the target also builds for tvOS, visionOS or watchOS, put `.low`, `.high` and the `higherThan:` / `lowerThan:` initializers inside `#if os(iOS) || os(macOS)`: those platforms have none of them, so no availability check admits them there.

```swift
.toolbar {
    ToolbarItemGroup {
        UndoButton()
        RedoButton()
    }
    #if os(iOS) || os(macOS)
    .visibilityPriority(.high)
    #endif
}
```

`ToolbarOverflowMenu` is toolbar content whose children always appear in the overflow menu. The `View.toolbarOverflowMenu { ... }` modifier provides the same behavior outside a toolbar builder. Both are available on iOS 27+ and visionOS 27+ only, with no macOS, tvOS or watchOS release. The type and modifier have different syntaxes:

```swift
.toolbar {
    ToolbarOverflowMenu {
        ExportButton()
        ClearButton()
    }
}

content
    .toolbarOverflowMenu {
        ExportButton()
        ClearButton()
    }
```

`.topBarPinnedTrailing` keeps a `ToolbarItem` at the trailing edge and prevents it from moving into overflow. It is available on iOS 27+ and visionOS 27+ only, with no macOS, tvOS or watchOS release.

For deployment targets below SDK 27, prefer one availability check around the toolbar content when using these APIs. Name visionOS in the check too, and keep it inside `#if os(iOS) || os(visionOS)` when the target also builds for macOS, tvOS or watchOS: none of them has either API, so no `#available` version admits them there, and the `#else` branch gives them the plain item:

```swift
.toolbar {
    #if os(iOS) || os(visionOS)
    if #available(iOS 27, visionOS 27, *) {
        ToolbarItem(placement: .topBarPinnedTrailing) {
            ShareButton()
        }
        ToolbarOverflowMenu {
            ExportButton()
        }
    } else {
        ToolbarItem {
            ShareButton()
        }
    }
    #else
    ToolbarItem {
        ShareButton()
    }
    #endif
}
```

## Minimization, margins, and status bar

`toolbarMinimizationBehavior(_:for:)`, `toolbarMinimizationSafeAreaAdjustment(_:for:)`, and `toolbarMinimizationRestoration(_:for:)` are available on all Apple platforms in SDK 27, and so is each one's `.automatic` value. The behavior cases `.onScrollDown`, `.onScrollUp` and `.never`, the safe-area cases `.enabled` and `.disabled`, and the restoration case `.atScrollEdge` exist only on iOS, iPadOS and Mac Catalyst: the SDK marks them unavailable on macOS, tvOS, visionOS and watchOS, so no availability check admits them there. Use `.automatic` for cross-platform code and put the iOS-only cases inside `#if os(iOS)`, which also covers the `.navigationBar` placement that macOS lacks:

```swift
ScrollView {
    Content()
}
#if os(iOS)
.toolbarMinimizationBehavior(.onScrollDown, for: .navigationBar)
.toolbarMinimizationSafeAreaAdjustment(.automatic, for: .navigationBar)
#endif
```

`contentMarginsRemoved(_:)` removes the system margins around toolbar content. It is available on iOS 27+, macOS 27+, tvOS 27+, watchOS 27+, and visionOS 27+.

On iOS 27+, `ToolbarPlacement.statusBar` can be passed to `toolbarVisibility(_:for:)` to control status-bar visibility. It is iOS-only; keep `statusBarHidden(_:)` in an earlier deployment fallback and do not suggest a replacement on visionOS, where there is no status bar.

```swift
.toolbarVisibility(.hidden, for: .statusBar)
```

## Navigation title alignment (27.2+)

`toolbarTitleAlignment(_:)` overrides the alignment the navigation bar picks for its title: `.automatic`, `.leading` or `.center`. Leave the system choice in place unless the design needs a fixed alignment. The modifier exists only on iOS, iPadOS and Mac Catalyst 27.2+; on macOS, tvOS, visionOS and watchOS the SDK marks it unavailable, so no availability check admits it there. Wrap it in `#if os(iOS)` and `#available(iOS 27.2, *)`, with the unmodified view as the fallback:

```swift
extension View {
    @ViewBuilder
    func centeredNavigationTitle() -> some View {
        #if os(iOS)
        if #available(iOS 27.2, *) {
            toolbarTitleAlignment(.center)
        } else {
            self
        }
        #else
        self
        #endif
    }
}

NavigationStack {
    Content()
        .navigationTitle("Library")
        .centeredNavigationTitle()
}
```

`@Environment(\.toolbarTitleAlignment)` reports the alignment the bar resolved: `.leading` or `.center` once the system has chosen one, `.automatic` before. Read it in a custom title view (a `ToolbarItem` with the `.title` placement) to align that view's content to match, not to decide its size. Unlike the modifier, the environment value and `ToolbarTitleAlignment` itself are available on every platform from 27.2:

```swift
@available(iOS 27.2, macOS 27.2, tvOS 27.2, watchOS 27.2, visionOS 27.2, *)
struct TitleLabel: View {
    @Environment(\.toolbarTitleAlignment) private var alignment

    var body: some View {
        Text("Library")
            .frame(maxWidth: .infinity, alignment: alignment == .center ? .center : .leading)
    }
}
```

## Dynamic toolbar content

`ForEach` conforms to `ToolbarContent` when built with the SDK 27 toolchain and back-deploys to iOS 16+, macOS 13+, watchOS 9+, tvOS 16+, and visionOS 1+. Give the collection elements stable identity. `EmptyView` as toolbar content requires iOS 27+, macOS 27+, tvOS 27+, watchOS 27+, and visionOS 27+.

```swift
.toolbar {
    ForEach(actions) { action in
        ToolbarItem {
            Button(action.title) {
                action.perform()
            }
        }
    }
}
```

To show or hide one toolbar item from state, use `ToolbarContent.hidden(_:)` (also on `CustomizableToolbarContent`). It is available on iOS 26.4+, macOS 15+, visionOS 26.4+, tvOS 27.2+ and watchOS 27.2+. Below those versions, fall back to an `if` inside the `.toolbar` builder:

```swift
.toolbar {
    if #available(iOS 26.4, macOS 15.0, visionOS 26.4, tvOS 27.2, watchOS 27.2, *) {
        ToolbarItem(placement: .primaryAction) { Button("Go") { } }
            .hidden(isEmpty)
    } else if !isEmpty {
        ToolbarItem(placement: .primaryAction) { Button("Go") { } }
    }
}
```

For broader Liquid Glass styling, see [liquid-glass.md](liquid-glass.md). For macOS window and toolbar concerns, keep platform-specific guidance in the macOS references.
