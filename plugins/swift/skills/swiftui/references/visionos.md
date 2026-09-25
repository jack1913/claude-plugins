# SwiftUI visionOS Reference

> Sources, read 2026-09-25: Apple's SwiftUI documentation for every API named here (the platform claims are recorded in `maintenance/apis.json` and checked by `maintenance/check-apis.py`, repository only); the Human Interface Guidelines pages [Designing for visionOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-visionos), [Windows](https://developer.apple.com/design/human-interface-guidelines/windows), [Ornaments](https://developer.apple.com/design/human-interface-guidelines/ornaments), [Eyes](https://developer.apple.com/design/human-interface-guidelines/eyes) and [Gestures](https://developer.apple.com/design/human-interface-guidelines/gestures); and the WWDC23 sessions [Meet SwiftUI for spatial computing](https://developer.apple.com/videos/play/wwdc2023/10109/) (10109) and [Elevate your windowed app for spatial computing](https://developer.apple.com/videos/play/wwdc2023/10110/) (10110). The guidance is paraphrased, and each rule names its source.

## Table of Contents

- [Glass on visionOS](#glass-on-visionos)
- [Floating controls: ornaments](#floating-controls-ornaments)
- [Windows, volumes and immersive spaces](#windows-volumes-and-immersive-spaces)
- [Input and hover](#input-and-hover)
- [Checklist](#checklist)

## Glass on visionOS

visionOS lacks SwiftUI's Liquid Glass modifiers and styles, and some 26-era toolbar and tab APIs. Apple's documentation lists none of these for visionOS, so code that calls them does not build there:

- `glassEffect(_:in:)`, `glassEffectID(_:in:)`, `glassEffectUnion(id:namespace:)` and `glassEffectTransition(_:)`
- `GlassEffectContainer` and `Glass.interactive(_:)`
- `GlassButtonStyle`: `.buttonStyle(.glass)` and `.buttonStyle(.glassProminent)`
- `scrollEdgeEffectStyle(_:for:)`
- `ToolbarSpacer`, `sharedBackgroundVisibility(_:)` and `tabViewBottomAccessory(content:)`

`platform-availability.md` has the per-platform table, including the 26-era APIs that visionOS does have, such as `backgroundExtensionEffect()` and `safeAreaBar(edge:alignment:spacing:content:)`.

What visionOS uses instead:

- **Window content already sits on glass.** A default visionOS window is an upright plane with a glass background that apps can't change. The HIG asks you to keep it: without the glass, text and controls get harder to read, and an opaque fill hides the person's surroundings ([Windows](https://developer.apple.com/design/human-interface-guidelines/windows) → visionOS windows).
- **Content outside the window's glass gets `glassBackgroundEffect`.** Custom ornaments and controls floating in a volume have no background of their own (WWDC23 10109, 10110). `glassBackgroundEffect(displayMode:)` puts glass behind a view in a container-relative rounded rectangle; `glassBackgroundEffect(in:displayMode:)` takes the shape, as in `.glassBackgroundEffect(in: .capsule)`. Both exist only on visionOS. The material is three-dimensional, with thickness, specular highlights, blur and shadows, so it takes part in z-axis layout. In a `ZStack`, apply it to the stack rather than to one of its children; inside an `overlay` or `background` closure, wrap the content in an explicit `ZStack` and apply it there ([`glassBackgroundEffect(in:displayMode:)`](<https://developer.apple.com/documentation/swiftui/view/glassbackgroundeffect(in:displaymode:)>)).

### Branching a multiplatform view

In a target that builds for visionOS and other platforms, keep every glass API that visionOS lacks in the non-visionOS branch of `#if os(visionOS)`, and give the visionOS branch `glassBackgroundEffect`. The pattern assumes a 26 deployment target on the other platforms; below 26, add the `if #available` fallback from `liquid-glass.md` → Fallback Strategies.

```swift
struct PlaybackBar: View {
    var body: some View {
        #if os(visionOS)
        PlaybackControls()
            .padding()
            .glassBackgroundEffect()
        #else
        GlassEffectContainer {
            PlaybackControls()
                .buttonStyle(.glass)
        }
        #endif
    }
}

struct PlaybackControls: View {
    var body: some View {
        HStack {
            Button("Play", systemImage: "play.fill") {}
            Button("Pause", systemImage: "pause.fill") {}
            Button("Stop", systemImage: "stop.fill") {}
        }
    }
}
```

## Floating controls: ornaments

An ornament shows controls or information for a window in a plane just in front of it. It moves with the window, and it stays put when the window's content scrolls ([Ornaments](https://developer.apple.com/design/human-interface-guidelines/ornaments)).

When to use one, and how (HIG [Ornaments](https://developer.apple.com/design/human-interface-guidelines/ornaments) → Best practices, unless noted):

- **Toolbars and tab bars first.** On visionOS, toolbars and `TabView` already appear as ornaments, so use them rather than building your own; `ToolbarItem(placement: .bottomOrnament)` puts a toolbar item below the window (`.bottomOrnament` exists only on visionOS). Toolbar ornaments get a glass capsule background from the system (WWDC23 10110).
- **A custom ornament is for controls people need often**, in one place they can rely on, without crowding the window. Apple's example is the Now Playing controls in Music.
- **Keep it visible** in most cases. Hiding it makes sense only while people are absorbed in the content, such as watching a video.
- **Keep it no wider than its window**, and add few ornaments: each adds visual weight. In a volume, keep a custom ornament off the edge a toolbar or tab bar uses ([Windows](https://developer.apple.com/design/human-interface-guidelines/windows) → visionOS volumes).
- **Give a custom ornament glass yourself.** SwiftUI gives custom ornaments no glass background; add `.glassBackgroundEffect()` to the ornament's content (WWDC23 10110). On that glass, buttons can be borderless: the system adds the hover effect when people look at them (HIG Ornaments).

`ornament(visibility:attachmentAnchor:contentAlignment:ornament:)` exists only on visionOS. `.scene(.bottom)` anchors the ornament to a `UnitPoint` of the scene, here its bottom edge (`OrnamentAttachmentAnchor.scene(_:)`). In a multiplatform view, wrap the modifier in `#if os(visionOS)`; Swift accepts `#if` around a postfix modifier:

```swift
struct LibraryView: View {
    var body: some View {
        NavigationStack {
            List(1...20, id: \.self) { number in
                Text("Track \(number)")
            }
            .navigationTitle("Library")
        }
        #if os(visionOS)
        .ornament(attachmentAnchor: .scene(.bottom)) {
            PlaybackControls()
                .padding()
                .glassBackgroundEffect()
        }
        #endif
    }
}
```

## Windows, volumes and immersive spaces

visionOS offers three kinds of scene, from contained to unbounded. Give each part of the app the lowest level of immersion that works for it; not every moment needs a full space ([Designing for visionOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-visionos) → Best practices).

- **Window:** [`WindowGroup`](https://developer.apple.com/documentation/swiftui/windowgroup). A glass plane with the standard window controls. Use it for familiar, UI-centric tasks ([Windows](https://developer.apple.com/design/human-interface-guidelines/windows) → visionOS windows).
- **Volume:** a `WindowGroup` with [`.windowStyle(.volumetric)`](https://developer.apple.com/documentation/swiftui/windowstyle/volumetric), set through the scene modifier [`windowStyle(_:)`](<https://developer.apple.com/documentation/swiftui/scene/windowstyle(_:)>). A bounded 3D region that people can view from any angle; use it for rich 3D content such as a game board ([Windows](https://developer.apple.com/design/human-interface-guidelines/windows) → visionOS volumes). Give it a size in physical units with `defaultSize(width:height:depth:in:)`. `.volumetric` exists only on visionOS.
- **Immersive space:** [`ImmersiveSpace`](https://developer.apple.com/documentation/swiftui/immersivespace), visionOS only. Content without bounds, placed in the person's surroundings (the default `.mixed` style) or replacing them; `immersionStyle(selection:in:)` sets the style. Opening one hides the other apps, and only one can be open at a time.

Open and dismiss an immersive space with the environment actions [`openImmersiveSpace`](https://developer.apple.com/documentation/swiftui/environmentvalues/openimmersivespace) and [`dismissImmersiveSpace`](https://developer.apple.com/documentation/swiftui/environmentvalues/dismissimmersivespace). Both are `async`. Opening takes the space's `id`, a value, or both, and returns an `OpenImmersiveSpaceAction.Result`; it fails while another space is open, so check the result. Dismissing takes no argument, because at most one space is open.

This app is visionOS only. In a multiplatform app, put the volume and the immersive space inside `#if os(visionOS)` in the scene body:

```swift
@main
struct PlayerApp: App {
    var body: some Scene {
        WindowGroup {
            LibraryView()
        }

        WindowGroup(id: "stage") {
            StageView()
        }
        .windowStyle(.volumetric)
        .defaultSize(width: 0.6, height: 0.4, depth: 0.4, in: .meters)

        ImmersiveSpace(id: "concert") {
            ConcertView()
        }
    }
}

struct ConcertButton: View {
    @Environment(\.openImmersiveSpace) private var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) private var dismissImmersiveSpace
    @State private var isConcertOpen = false

    var body: some View {
        Button(isConcertOpen ? "Leave Concert" : "Enter Concert") {
            Task {
                if isConcertOpen {
                    await dismissImmersiveSpace()
                    isConcertOpen = false
                } else {
                    isConcertOpen = await openImmersiveSpace(id: "concert") == .opened
                }
            }
        }
    }
}
```

## Input and hover

- **Look and pinch arrives as a tap.** People look at an element and tap a finger and thumb together, or touch it directly. Standard controls and gestures (`Button`, `onTapGesture`, `SpatialTapGesture`, `DragGesture`, `MagnifyGesture`) handle both without visionOS-specific code. Prefer these for UI, and keep direct and custom gestures for objects made for close-up interaction ([Gestures](https://developer.apple.com/design/human-interface-guidelines/gestures) → visionOS, Specifications).
- **`SpatialEventGesture` is for low-level multi-touch.** It reports every ongoing spatial event, each with a stable identifier, location, phase and input-device pose. An event can end or be cancelled while the gesture continues, so track state per event in `onChanged` and clear all of it in `onEnded`. Apple recommends it only when you need that detail; otherwise use `SpatialTapGesture`, `MagnifyGesture` or `DragGesture` ([`SpatialEventGesture`](https://developer.apple.com/documentation/swiftui/spatialeventgesture)).
- **Hover is gaze feedback.** visionOS highlights the interactive element a person looks at, which tells them they can tap it; standard controls do this by themselves ([Eyes](https://developer.apple.com/design/human-interface-guidelines/eyes)). Anything that acts on a tap should be a `Button`; a `.plain` button keeps the standard hover effect, but a custom `ButtonStyle` has to add its own with `hoverEffect(_:isEnabled:)` (WWDC23 10109, 10110). `.hoverEffect()` uses `.automatic`; `.highlight` and `.lift` are the alternatives.
- **Shape the hover.** `hoverEffect` reads the content shape of the view it modifies, so set `.contentShape(.hoverEffect, …)` before it (WWDC23 10110). Give an element made of several parts, such as an image with a label, one shape that covers all of it, and round its corners: rounded shapes are easier to look at ([Eyes](https://developer.apple.com/design/human-interface-guidelines/eyes) → Encouraging interaction).
- **Space targets apart:** at least 16 pt of clear space around each interactive item, or centers at least 60 pt apart ([Eyes](https://developer.apple.com/design/human-interface-guidelines/eyes) → Making items easy to see).
- `hoverEffect(_:isEnabled:)` and the `.hoverEffect` content-shape kind exist on iOS, iPadOS, Mac Catalyst, tvOS and visionOS, but not on macOS or watchOS. Keep them out of those branches.

```swift
struct TileButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding()
            .contentShape(.hoverEffect, .rect(cornerRadius: 16))
            .hoverEffect()
            .scaleEffect(configuration.isPressed ? 0.95 : 1)
    }
}
```

## Checklist

- [ ] Every glass API missing on visionOS sits in the non-visionOS branch of `#if os(visionOS)`
- [ ] In a multiplatform target, visionOS-only APIs (`glassBackgroundEffect`, `ornament`, `.bottomOrnament`, `.windowStyle(.volumetric)`, `ImmersiveSpace`) sit in the visionOS branch
- [ ] Windows keep their default glass background; no opaque fill replaces it
- [ ] Custom content outside a window's glass (custom ornaments, controls in a volume) uses `glassBackgroundEffect`, applied to the whole stack
- [ ] Toolbars and tab bars use `.toolbar` and `TabView`; a custom `ornament` holds only frequently needed controls, stays visible and is no wider than its window
- [ ] Bounded 3D content uses a volume; an `ImmersiveSpace` appears only where the moment needs it, at the least immersion that suits it
- [ ] The result of `openImmersiveSpace` is checked; `dismissImmersiveSpace` closes the one open space
- [ ] Taps come from standard controls and gestures; `SpatialEventGesture` only for low-level multi-touch
- [ ] Tappable elements are `Button`s; a custom `ButtonStyle` adds `hoverEffect`, with a rounded `.hoverEffect` content shape that covers the whole element
- [ ] Interactive items have at least 16 pt of clear space around them, or centers at least 60 pt apart
- [ ] `hoverEffect` and the `.hoverEffect` content-shape kind stay out of macOS and watchOS branches
