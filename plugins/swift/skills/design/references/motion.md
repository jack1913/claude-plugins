# Motion

When to animate, which spring to choose, how long motion should take, and what changes when people turn on Reduce Motion.

**Sources:** [HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion), [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/) (Animate with springs), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass), [SwiftUI: smooth](https://developer.apple.com/documentation/swiftui/animation/smooth), [SwiftUI: snappy](https://developer.apple.com/documentation/swiftui/animation/snappy), [SwiftUI: bouncy](https://developer.apple.com/documentation/swiftui/animation/bouncy), [SwiftUI: default](https://developer.apple.com/documentation/swiftui/animation/default), [SwiftUI: accessibilityReduceMotion](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityreducemotion)

The mechanics (implicit and explicit animation, transitions, completion handlers, performance) are in `swift:swiftui` → `animation-basics.md`, `animation-transitions.md` and `animation-advanced.md`; symbol animation is in `sf-symbols.md` → Symbol Effects.

## Motion Explains a Change

- Animate to show status, give feedback or show how something works, never for its own sake; gratuitous or excessive motion distracts and can make people physically uncomfortable ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion))
- System components already move, and adjust to the input method and to accessibility settings (Liquid Glass reacts more strongly to a finger than to a trackpad), so custom motion is only for custom elements ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion))
- Motion follows the gesture and what people expect from it: a view that slid down to appear doesn't leave by sliding sideways ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion))
- On custom elements, leave interactions that happen all the time unanimated; the system already gives standard ones subtle motion ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion))
- Never block input until an animation ends, above all for one people see again and again ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion)). Springs cope with interruption: a spring sent to a new target mid-flight keeps its velocity and changes course smoothly ([WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/))
- Motion is never the only carrier of information; back it with text, haptics or sound ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion))

## Springs by Default

- Springs keep both position and velocity continuous, take over a gesture's speed as it ends, and come to rest gradually, so they read as physical motion; an eased curve can't start from a gesture's velocity ([WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/))
- SwiftUI's `default` animation, which `withAnimation` uses when you pass none, is a spring; before iOS 17 and macOS 14 it is ease-in-out ([SwiftUI: default](https://developer.apple.com/documentation/swiftui/animation/default), [WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/))

| Preset | What it is | Fits |
|---|---|---|
| `.smooth` | A spring with no bounce | The general-purpose choice, and the one to take when unsure |
| `.snappy` | A spring with a little bounce | Changes that should feel brisk without looking bouncy |
| `.bouncy` | A spring with more bounce | Playful moments, and motion that should feel physical, such as the end of a drag |

What each preset is comes from [SwiftUI: smooth](https://developer.apple.com/documentation/swiftui/animation/smooth), [SwiftUI: snappy](https://developer.apple.com/documentation/swiftui/animation/snappy) and [SwiftUI: bouncy](https://developer.apple.com/documentation/swiftui/animation/bouncy); when each fits, from [WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/).

- Tune a preset instead of inventing a curve: set the duration first for pacing, then the bounce for character, for example with `.smooth(duration:extraBounce:)` or `.spring(duration:bounce:)`. A lot of bounce looks exaggerated on interface elements ([WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/))
- Choose springs that match the app's character, serious or playful, calm or quick, and reuse them everywhere ([WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/)); where the project has motion tokens, they name them once (`tokens.md`)

## Keep It Short

- Feedback animation is brief and precise: it feels light and gets its message across better than a large animation ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion))
- A spring's `duration` is the perceived length you pick for pacing. The time it takes to settle completely is longer and hard to predict, so don't hold back a UI change until a spring settles; use an animation completion instead ([WWDC23 10158](https://developer.apple.com/videos/play/wwdc2023/10158/)), as in `animation-advanced.md` → Animation Completion Handlers
- visionOS asks for more restraint ([HIG: Motion](https://developer.apple.com/design/human-interface-guidelines/motion)):
  - no motion at the edges of the field of view;
  - large moving objects made more translucent or lower in contrast;
  - a fade out and back in, rather than a visible move, when the path means nothing;
  - no rotating the virtual world, and a stationary frame of reference where possible;
  - no sustained oscillation, above all near 0.2 Hz.

  Slow and soften animated objects, especially in peripheral vision ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))

## Reduce Motion

With Reduce Motion on, HIG Accessibility asks apps to ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)):
- cut back automatic and repeating animation, including zooming, scaling and motion in the periphery;
- tighten springs so they bounce less;
- let motion track people's gestures directly;
- stop animating depth changes along the z-axis;
- use fades in place of transitions that slide or zoom.

- Read the setting with `@Environment(\.accessibilityReduceMotion)`; when it is true, avoid large animations, above all ones that simulate a third dimension ([SwiftUI: accessibilityReduceMotion](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityreducemotion))
- Liquid Glass and standard components adapt by themselves: with Reduce Motion on, the material tones down some effects and loses its elastic behaviour ([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)). Your own elements, colours and animations need testing with the setting on ([Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass))
- An indefinite symbol effect is repeating motion, so switch it off while the setting is on ([HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))

The example keeps the change visible under Reduce Motion but swaps the slide for a fade, the bouncier spring for one without bounce, and stops the repeating symbol effect:

```swift
struct NowPlayingBanner: View {
    let isPlaying: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack {
            Spacer()
            if isPlaying {
                Label("Now Playing", systemImage: "waveform")
                    .symbolEffect(.variableColor, isActive: !reduceMotion)
                    .padding()
                    .transition(reduceMotion ? .opacity : .move(edge: .bottom))
            }
        }
        .animation(reduceMotion ? .smooth : .snappy, value: isPlaying)
    }
}
```
