# iPhone Duo SwiftUI Guidance

> iPhone Duo support needs the 27.1 SDK or later (Xcode 27.1 or later), and iOS 27.1 or later at runtime.

## Displays and Continuity

iPhone Duo has an outer display and a larger inner display. The outer display uses the familiar compact-horizontal, regular-vertical iPhone context in portrait and compact in both dimensions in landscape; full screen, the inner display provides regular width and height in both orientations, open or partially folded, including sidebar and multi-column presentations. Split View and other resizing can still make it compact. Use the current proposal and size classes, not a device check, orientation, fixed breakpoint, or global screen.

Opening, closing, rotating, partially folding, Split View multitasking, and pinned video all resize the same app experience. Preserve navigation state, content hierarchy, and functionality across those transitions. Do not make a feature available only in one pose or prescribe a bespoke layout for every pose. Generic resizability, safe-area, and display-scale rules remain canonical in [layout-best-practices.md](layout-best-practices.md) and [image-optimization.md](image-optimization.md).

Hardware placement is asymmetric. The outer and inner cameras occupy different positions, and system controls can use a vertical bar on a hardware-aligned side. Never assume opposite safe-area or margin values are equal. Let standard SwiftUI containers and directional safe areas place foreground controls; full-bleed visual backgrounds can extend behind them. See [toolbar-patterns.md](toolbar-patterns.md) for vertical-bar APIs.

## Choose the Technique by Screen Structure

Classify the screen by structure before choosing a fold technique; starting from `ArrangementView` or `reservedRegions` tends to misread the screen. Check in this order:

1. **Rows push further screens** (settings, mailboxes, folders, even a short list): `NavigationSplitView` needs no Duo-specific code; it collapses on compact width and scales to iPad and resizable windows. See [sheet-navigation-patterns.md](sheet-navigation-patterns.md#large-displays).
2. **Cards or a feed in one `ScrollView`** (dashboards, collection grids): [reflow into two columns](layout-best-practices.md#two-column-reflow-for-card-screens) with the gutter over a vertical fold; don't split at a horizontal fold.
3. **Two peer regions without navigation** (media and controls, visual and copy): `ArrangementView` with `.split`, outside any scroll view.
4. **Content plus a supplementary queue or panel**: consider keeping the compact pattern, a persistent bar that pushes the full view (like the Music mini player). If you use `.inspector`, attach it around the `NavigationStack`, not on a pushed screen; in Xcode 27.1 that broke pushes and put full-bleed content under the inspector column.
5. **Custom edge-to-edge chrome only**: read `reservedRegions` directly.

In a portrait-only iPhone app, regular width effectively means the inner display, which ignores supported orientations and can still be landscape.

## Fold and Camera Regions

The outer camera always shapes the outer-display area; standard safe areas and bars account for it, and the outer display reports it, with the system status area beside it, as active `.occlusion` regions. On the inner display, the fold is a `.division` reserved region because it separates the available area: a band 40 points wide across the middle of the display, with 20-point margins on each side, vertical in the book pose and horizontal in the table-top pose. It is active when the device is partially folded and inactive, with the same frame, when it is fully open; read `isActive` rather than inferring it from the hinge status, which can report `.partiallyOpen` before the division becomes active. The FaceTime camera is an `.occlusion` region because it covers a smaller frame; while the camera is not in use it is reported only with `.includeInactive`. The system status area in the inner display's top corner is also an active `.occlusion` region, so a default occlusion query is not empty while the camera is off. Inner regions change activity as the device pose and camera use change.

System components (`NavigationStack`, `NavigationSplitView`, `TabView`, sheets, alerts, menus, `List`, `ScrollView`) already adapt around the fold and system UI. Do not displace continuously scrolling articles, feeds, documents, or lists merely because a fold exists. Pick the technique with the list above, then see [`ArrangementView`](layout-best-practices.md#two-region-arrangements-271) and [reserved regions](layout-best-practices.md#reserved-regions-271).

## Duo Displacement Heuristics

Displacement means moving or resizing the same element around a reserved region, not creating a pose-specific feature. Keep related elements together, move the smallest coherent group, and avoid large jumps that weaken their visual relationship.

When a partially folded book-like pose requires displacement, a trailing region supports continuity as the device closes toward the outer display. In a table-like pose, the upper region suits content viewed at a distance and the lower stable region suits touch controls. Treat these as heuristics after purpose, reachability, and context, not as pose detection rules. Keep the same controls and general hierarchy everywhere.

## Hinge Effects, Not Layout

`onHingeChange` provides live hinge state and angle for optional interactions or effects. The status is `.closed`, `.partiallyOpen` or `.fullyOpen`, and the angle lies between 0 and 180 degrees (180 at `.fullyOpen`). Read the status rather than deriving it from the angle: the simulator reported `.closed` at about 62 degrees while closing and `.partiallyOpen` at about 25 degrees while opening. A pose change delivers a handful of intermediate updates, some repeating the previous value. Do not use it to drive layout; use size classes, `ArrangementView`, and reserved regions instead. `DeviceHingeContext.hinge` is optional, so reset effect state when there is no hinge or when the relevant hinge status ends.

```swift
@available(iOS 27.1, macOS 27.1, macCatalyst 27.1, tvOS 27.1, visionOS 27.1, watchOS 27.1, *)
struct HingeReactiveArtwork: View {
    @State private var foldEffect = 0.0

    var body: some View {
        Artwork()
            .scaleEffect(1 + foldEffect * 0.04)
            .onHingeChange { _, context in
                if let hinge = context.hinge,
                   hinge.status == .partiallyOpen {
                    foldEffect = min(max(hinge.angle.degrees / 180, 0), 1)
                } else {
                    foldEffect = 0
                }
            }
    }
}
```

Select this view behind `#available(iOS 27.1, macOS 27.1, macCatalyst 27.1, tvOS 27.1, visionOS 27.1, watchOS 27.1, *)`; the fallback omits the optional effect. Apple lists `onHingeChange` and `DeviceHingeContext` as introduced in 27.1 on every platform, so the check needs the version for each platform your target builds for.

## Scene Accessories

Scene accessories can pair supplementary content with the main scene on another display, but the system controls their availability and it can change at runtime. Keep enablement state synchronized with `onAvailabilityChange`, disable unavailable controls, and handle failed scene requests rather than inferring availability from pose. For camera accessories, register the accessory with the relevant camera view, but defer capture session, camera selection, preview, and rotation behavior to AVFoundation guidance.

## Verifying Layouts

Before claiming a fold or landscape layout works, check whether your environment can pose the iPhone Duo simulator. `simctl` cannot fold or rotate it. Xcode's Device Hub can: its device toolbar has Closed, Partially Open and Open pose buttons and a Rotate Right button, and they are reachable through macOS accessibility scripting when the tool running them has Accessibility permission. Without such access, ask the developer to confirm the closed, partially folded (book and table-top) and fully open poses, in portrait and landscape. Xcode Previews are another way to iterate on layout.

Resizing is continuous, so also check the extremes, not just named poses: narrowest, widest, shortest, tallest, and roughly square. Look for clipped content, overlapping controls, and text that sprawls at wide sizes. If the root is a `TabView`, see [Tab Bar and Sidebar](sheet-navigation-patterns.md#tab-bar-and-sidebar-sdk-27) for the iPhone sidebar presentation.

## Official Sources

- [Get ready for iPhone Duo](https://developer.apple.com/iphone-duo/)
- [Preparing your app for iPhone Duo](https://developer.apple.com/documentation/technologyoverviews/preparing-your-app-for-iphone-duo)
- [Designing for iPhone Duo](https://developer.apple.com/design/human-interface-guidelines/designing-for-iphone-duo)
- Apple Tech Talks 111461–111466, especially [Prepare your app](https://developer.apple.com/videos/play/tech-talks/111461/), [Raise the bar](https://developer.apple.com/videos/play/tech-talks/111462/), [Strike a pose](https://developer.apple.com/videos/play/tech-talks/111463/), and [Leverage multiple displays and scenes](https://developer.apple.com/videos/play/tech-talks/111464/)
