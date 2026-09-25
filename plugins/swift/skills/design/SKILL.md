---
name: design
description: Use when designing or restyling SwiftUI screens and components for iOS, iPadOS, macOS or visionOS, including information hierarchy and layout, typography and Dynamic Type, color and dark mode, SF Symbols, when and how to use Liquid Glass, platform idioms (tab bar vs sidebar vs ornaments, toolbars, inspectors, sheets vs windows), motion, and design tokens. Also use when a view looks like a web page, when choosing between native primitives, or when a project has no design tokens yet.
---

# Apple-Native Design

This skill decides *what* to build: which native primitive fits, how a screen ranks and groups its content, how it changes per platform, and *when* Liquid Glass fits. `swift:swiftui` owns API correctness, accessibility code patterns and Liquid Glass mechanics, so link to it rather than repeating it. Its references sit next to this skill in `../swiftui/references/`: `liquid-glass.md` (glass APIs and fallbacks), `platform-availability.md` (where each 26-era API exists), `visionos.md` (glass alternatives, ornaments, windows) and `accessibility-patterns.md` (Dynamic Type, labels, grouping). Each decision rule below cites the Apple page it paraphrases.

## Operating Rules

- If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict
- With no project layer, use system text styles and semantic colours, and suggest the starter token set in `references/tokens.md` instead of scattering literals
- Adopt Liquid Glass where `references/liquid-glass-design.md` says it fits; `swift:swiftui` keeps the API rules

## Design Thinking

Before coding, understand the context and commit to an Apple-native direction:
- **Purpose**: What does this view do? What user problem does it solve?
- **Platform**: Will it differ on iOS vs macOS vs visionOS? Use `#if os(iOS)` / `#if os(macOS)` / `#if os(visionOS)` for platform-specific code.
- **Navigation pattern**: NavigationStack, TabView, sheets, popovers — pick what Apple would use.
- **Information hierarchy**: What's the primary content? What's secondary? What's glanceable?
- **Interaction model**: Touch (iOS) vs pointer (macOS)? Keyboard shortcuts? Drag targets?

**CRITICAL**: This is NOT web design ported to SwiftUI. Do not recreate web patterns. Think in terms of Lists, Forms, NavigationSplitView, toolbars, sheets, and inspectors — the native primitives.

## Apple-Native Means

- **System colors** (`Color.primary`, `.secondary`, `.accentColor`) that adapt to Light/Dark automatically
- **SF Symbols** for all iconography — never custom icon images for standard actions
- **Standard navigation**: NavigationStack with toolbar items, not custom header bars
- **Semantic grouping**: `Form`, `Section`, `GroupBox`, `LabeledContent` — not raw VStacks with dividers
- **Platform idioms**: Sidebars on macOS, tab bars on iOS, sheets for modal input

## What to Avoid

- Custom dark themes or neon accents — the system handles dark mode
- Web-style card layouts with drop shadows — use `Section` or `.listRowBackground()`
- Custom tab bars or navigation bars — use the system ones
- Hardcoded colors, fonts, spacing, or corner radii — use the project's tokens, or the starter set in `references/tokens.md`
- Decorative gradients, noise textures, or background patterns — Apple is clean
- Custom scroll indicators or pull-to-refresh — use system defaults
- Reimplementing system controls (toggles, sliders, pickers) — use SwiftUI's

## Decision Rules

- **Grouped input**: a `Form` with one `Section` per group and `LabeledContent` for each label and value; SwiftUI styles it per platform, as a grouped list on iOS and as aligned rows on macOS ([SwiftUI: Form](https://developer.apple.com/documentation/swiftui/form), [SwiftUI: LabeledContent](https://developer.apple.com/documentation/swiftui/labeledcontent))
- **Settings**: keep them few, with defaults that suit most people; an option that affects one task lives on that task's screen; don't copy system-wide choices into the app; on Mac, a `Settings` scene opened from the app menu (Command-Comma), not from a toolbar button ([HIG: Settings](https://developer.apple.com/design/human-interface-guidelines/settings))
- **Top-level sections**: a `TabView`, shown as a tab bar on iPhone and iPad, whose tabs switch sections and never run actions; `.tabViewStyle(.sidebarAdaptable)` (iOS 18, macOS 15, visionOS 2) lets people turn the iPad tab bar into a sidebar and shows a sidebar on Mac; a sidebar-only app, or a hierarchy deeper than two levels, uses `NavigationSplitView` ([HIG: Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars), [HIG: Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars), [SwiftUI: sidebarAdaptable](https://developer.apple.com/documentation/swiftui/tabviewstyle/sidebaradaptable))
- **visionOS**: system toolbars and tab bars become ornaments on their own; add a custom ornament only for controls people need all the time, no wider than its window; supplementary content goes in a split view or an adjacent window, not an ornament ([HIG: Ornaments](https://developer.apple.com/design/human-interface-guidelines/ornaments), [HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [HIG: Split views](https://developer.apple.com/design/human-interface-guidelines/split-views)); APIs: `visionos.md`
- **Toolbars**: actions on the current view go here; one primary action (Done, Submit), tinted, at the trailing end; items grouped by function and frequency, three groups at most, with text buttons kept apart from symbol buttons; no custom bar backgrounds or borders ([HIG: Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars), [WWDC25 356](https://developer.apple.com/videos/play/wwdc2025/356/))
- **Buttons**: a tappable area no smaller than 44x44 pt, or 60x60 pt on visionOS; the likeliest action gets the prominent style, one or two per view, and alternatives differ by style rather than size; destructive actions take `role: .destructive` and are never the default button ([HIG: Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons))
- **Sheets**: one short, scoped task, and one sheet at a time; Done never stands alone but comes with Cancel, or Back in a multi-step flow (on iOS and iPadOS, Cancel leading, Done trailing); a long or self-contained task gets its own window on Mac or a full-screen presentation on iPhone and iPad ([HIG: Sheets](https://developer.apple.com/design/human-interface-guidelines/sheets))
- **Liquid Glass**: only on bars, sidebars and controls floating above the content; standard components adopt it by themselves, so custom glass is for your own floating controls, used sparingly, and never for content such as lists, tables or backgrounds ([HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials), [WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/)); APIs: `liquid-glass.md`, `platform-availability.md`
- **Colour**: system and semantic colours used for their stated role (no separator colour as text); custom colours as asset colour sets with light, dark and increased-contrast variants; meaning never by colour alone, so a status colour comes with a symbol or a label ([HIG: Color](https://developer.apple.com/design/human-interface-guidelines/color))
- **Type**: built-in text styles rather than point sizes, so Dynamic Type scales them; no Ultralight, Thin or Light weights; at the largest accessibility sizes, stack side-by-side items instead of truncating text ([HIG: Typography](https://developer.apple.com/design/human-interface-guidelines/typography)); code patterns: `accessibility-patterns.md`

## Checklist

**Tokens**
- [ ] No literal spacing, radius, colour, font or animation value: the project's tokens, or system text styles, semantic colours and the `references/tokens.md` set

**Structure**
- [ ] Grouped input uses `Form`, `Section` and `LabeledContent`, not stacks with dividers
- [ ] Settings are few, per-task options sit on their own screen, and Mac settings open from the app menu
- [ ] Tabs switch top-level sections and hold no actions; Mac shows a sidebar; deep hierarchies use `NavigationSplitView`
- [ ] visionOS: system bars appear as ornaments, custom ornaments hold only always-needed controls, and supplementary content is not in an ornament
- [ ] Sheets: one at a time, Done paired with Cancel or Back; long tasks get a window or a full-screen presentation

**Controls**
- [ ] Toolbar: one tinted primary action at the trailing end, three groups at most, no custom bar backgrounds
- [ ] Buttons: tappable area no smaller than 44x44 pt (60x60 pt on visionOS), and one or two prominent buttons per view
- [ ] Destructive actions use `role: .destructive` and are never the default

**Glass, colour and type**
- [ ] Glass only on bars and floating controls, never on content
- [ ] No meaning carried by colour alone; custom colours have light, dark and increased-contrast variants
- [ ] Text uses text styles and still reads at the largest accessibility size

## References

| Topic | Reference |
|-------|-----------|
| Design tokens: using a project's, or introducing a starter set | `references/tokens.md` |
