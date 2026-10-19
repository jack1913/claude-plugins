# Review a screen

`/swift:review` checks a SwiftUI screen against Apple's Human Interface Guidelines, from its code, a screenshot, or both. It runs only when you type it, and it reports without editing anything ([ADR-0011](../../adr/ADR-0011-swift-review-skill.md)).

## Review the code

In Claude Code, type:

> /swift:review Sources/Demo/SettingsView.swift

A real run on a settings screen with planted problems. The findings come most severe first: what's wrong, where, the HIG page, and a fix. This shows 6 of its 10 findings, including all 4 high ones; `…` marks the rest:

```text capture=review-2026-09-28-a
Found 10 issues in `SettingsView.swift`, 4 of them high severity. I reviewed against iOS 26 and macOS 26, the platforms in `Package.swift`. The project has no design tokens, colour sets or design skill of its own, so system defaults are the baseline.
## Findings
- [high] The Sync status is only a red or green `Circle`, with no symbol or text. The state depends on colour alone, and VoiceOver reads nothing for it — `Sources/Demo/SettingsView.swift:68` — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: put a `Label` inside `LabeledContent("Sync")`. Its text says "Synced" or "Not Synced", and only its icon (`checkmark.circle.fill` or `exclamationmark.triangle.fill`) takes `.green` or `.red`. The text stays primary.
- [high] The pencil edit button's tap area is under 44×44 pt. The 28×28 frame is already too small, and because it sits outside a `.plain` button it adds no tappable area. Only the pencil glyph (about body-text size) responds, which is likely also under the Mac minimum of 20×20 pt — `Sources/Demo/SettingsView.swift:49` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: make the whole Name row the control (a `Button` or `NavigationLink` row). If the inline button stays, put `.frame(minWidth: 44, minHeight: 44)` and `.contentShape(.rect)` on its label.
- [high] Delete Account has no `role: .destructive`. It is `.borderedProminent` with a red tint, which makes it the most prominent control in the content — `Sources/Demo/SettingsView.swift:83` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: use `Button("Delete Account", role: .destructive) { … }` with the default style, in its own last `Section`. The role supplies the red.
- [high] The "Account" heading uses `.system(size: 13, weight: .ultraLight)`. The fixed size ignores Dynamic Type, and the HIG rules out Ultralight — `Sources/Demo/SettingsView.swift:43` — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: make it a `Section("Account")` header, which the form styles and marks as a heading for VoiceOver. If it stays standalone, give it a text style such as `.headline` at Regular weight or heavier.
…
- [medium] The Storage card has `.glassEffect(.regular, in: .rect(cornerRadius: 16))`, which puts glass on content — `Sources/Demo/SettingsView.swift:82` — HIG: https://developer.apple.com/design/human-interface-guidelines/materials — Fix: remove the glass and the hand-picked radius, and make Storage a `Section` of the Form.
- [medium] The Edit Name sheet has Done but no Cancel. The field is bound directly to `name`, so edits apply as you type and can't be abandoned — `Sources/Demo/SettingsView.swift:101`, `:97` — HIG: https://developer.apple.com/design/human-interface-guidelines/sheets — Fix: edit a local `@State` draft and add `ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }`. Done writes the draft back to `name`, then dismisses.
…
```

Every one of the eight planted problems was found, with no false alarms ([verification record](../../internals/review-verification.md)).

## Review a screenshot

In Claude Code, type:

> /swift:review screenshot.png

From an image alone, the review judges only what's visible. Any size read from pixels is marked as an estimate, and anything the image can't show is listed under **Not checked**, together with what would settle it:

```text capture=review-2026-09-28-c
I assumed a scale of @2x: the image is 780×594 px, so the screen is about 390×297 pt. The image doesn't show which platform this is: there's no status bar, bar or window frame. 390 pt is the width of an iPhone.
## Findings
- [high] The Sync state is shown only by a red dot, with no symbol or words, so colour alone carries the meaning — screenshot: Sync row, trailing edge — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: say the state in words and put the colour on a symbol, e.g. `LabeledContent("Sync") { Label { Text("Sync Failed") } icon: { Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.red) } }`, keeping the text in the primary style. If Sync is an on/off setting rather than a status, use `Toggle("Sync", isOn: $isSyncOn)` instead.
- [medium] "Delete Account" is the only filled button on the screen, so the destructive action looks like the main action — screenshot: bottom-left button — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: drop the prominent style and use `Button("Delete Account", role: .destructive) { … }` in its own last `Section` of the form. iOS draws it as a red text row.
…
## Not checked
…
- **Hit targets:**
  - The Delete Account button is about 117×24 pt (estimated, @2x). On iPhone or iPad that is below the 44 pt minimum, which would be a high finding. On Mac it is above the 20 pt minimum.
  - The pencil glyph is about 10×10 pt (estimated, @2x), but the image can't show how large its tappable area is. The code (its frame or `contentShape`) would settle it.
…
- **Dynamic Type:** point sizes and text styles can't be measured from the image. A capture at an accessibility text size would show whether "Email … jordan@example.com" stacks or truncates.
…
```

Pass the view file and the screenshot together to get both: the code settles what the image only suggests.

## What it won't report

- A value your project's design layer sanctions: its tokens, colour sets or design skill.
- Missing Liquid Glass. Glass stays opt-in ([ADR-0008](../../adr/ADR-0008-liquid-glass-stays-opt-in.md)); glass on content is reported.
- A rule for a platform your project doesn't target.
- Taste with no HIG basis.

## Run it headless

An installed copy reads its reference files without extra flags. A checkout loaded with `--plugin-dir` also needs `--add-dir` with the same directory ([enable the plugin](../getting-started/enable-in-a-swift-repo.md#what-each-skill-covers)). `<checkout>` is your clone of `jack1913/swift-plugin`.

```bash
claude -p "/swift:review Sources/Demo/SettingsView.swift" --plugin-dir <checkout>/plugins/swift --add-dir <checkout>/plugins/swift
```
