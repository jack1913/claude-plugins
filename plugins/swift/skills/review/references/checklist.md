# Review Checklist

Each check is a question. When the answer is no, it's a finding. After the question comes the `swift:design` Decision Rule it applies (by its bold label in `../../design/SKILL.md`), the area reference with the detail, and the HIG page the finding cites. Read the rule and the reference; this list only points at them. Page URLs are `https://developer.apple.com/design/human-interface-guidelines/<page>`.

## Hierarchy and Grouping

- Is grouped input or a list of labelled values a `Form` with `Section`s and `LabeledContent`, rather than stacks with dividers? — **Grouped input** · `../../design/references/hierarchy-layout.md` · lists-and-tables
- Does the screen have one clear primary element, with secondary content visibly subordinate? — `../../design/references/hierarchy-layout.md` (Rank and Reading Order) · layout
- Do content and controls sit in the safe area, with system margins rather than custom edge padding? — `../../design/references/hierarchy-layout.md` (Margins and Safe Areas) · layout
- Is a settings screen short, with defaults most people keep, and per-task options on their task's screen? On Mac, is it a `Settings` scene? — **Settings** · settings

## Typography

- Does text use built-in text styles (`.body`, `.headline`, …) rather than `.system(size:)` point sizes? — **Type** · `../../design/references/typography.md` · typography
- Is every weight Regular or heavier (no Ultralight, Thin or Light)? — **Type** · `../../design/references/typography.md` (Weight and Emphasis) · typography
- At the largest accessibility sizes, do side-by-side items stack rather than truncate? — **Type** · `../../design/references/typography.md` (Dynamic Type) · typography

## Colour and Contrast

- Does anything rely on colour alone, such as a status dot or a red or green state with no symbol or label? — **Colour** · `../../design/references/color.md` (Status Colours) · color
- Are system and semantic colours used for their stated role (no separator colour as text, `.secondary` for secondary text)? — **Colour** · `../../design/references/color.md` · color
- Do custom colours come from asset colour sets with dark and increased-contrast variants, rather than `Color(red:green:blue:)`, unless the project's layer defines them? — **Colour** · `../../design/references/color.md` (Dark Mode, Contrast) · dark-mode

## SF Symbols

- Do standard actions use SF Symbols (the HIG's symbol for the action, such as `trash` for Delete) rather than custom images, with a text label where a symbol could be misread? — `../../design/references/sf-symbols.md` (Choosing a Symbol) · icons, sf-symbols
- Is each symbol sized with a text style through `.font` (so it matches its label's weight and grows with Dynamic Type), rather than `resizable()` and a frame? — `../../design/references/sf-symbols.md` (Weight and Scale) · sf-symbols

## Controls and Hit Targets

- On iPhone and iPad, is every tappable area at least 44×44 pt (60×60 pt on visionOS), counting the whole hit region, not only the glyph? On Mac, use the Mac row of the platform table instead (default 28×28 pt, minimum 20×20 pt): a control below the minimum is a finding, and standard system control sizes are not — **Buttons** · `../../design/references/platform-idioms.md` (Hit Targets and Control Size) · buttons, accessibility
- Are there one or two prominent buttons per view at most, with alternatives differing by style rather than size? — **Buttons** · buttons
- Does every destructive action take `role: .destructive`, and is it never the default or the prominent button? — **Buttons** · buttons

## Toolbars, Tabs and Navigation

- Does the toolbar hold one tinted primary action at the trailing end (on an iPhone Duo side bar, below Back/Close at the top), with items in three groups at most and text buttons kept apart from symbol buttons? — **Toolbars** · toolbars
- Does the toolbar use the system bar background, with no custom background or border? — **Toolbars** · toolbars
- Do tabs switch top-level sections and never run actions? Does the Mac show a sidebar, and does a hierarchy deeper than two levels use `NavigationSplitView`? — **Top-level sections** · tab-bars, sidebars
- Is navigation a `NavigationStack` or `NavigationSplitView` with system bars, not a custom header bar? — `../../design/SKILL.md` (Apple-Native Means) · layout

## Sheets and Modality

- Is a sheet one short, scoped task, with only one sheet at a time? — **Sheets** · sheets
- Is Done paired with Cancel (or Back in a multi-step flow), with Cancel leading and Done trailing on iOS and iPadOS? — **Sheets** · sheets
- Does a long or self-contained task get a window on Mac or a full-screen presentation on iPhone and iPad? — **Sheets** · modality

## Platform Idioms

- Does each target platform get its own form (tab bar on iPhone, sidebar on iPad and Mac, ornaments on visionOS), rather than one layout stretched across all? — `../../design/references/platform-idioms.md` (Design Once, Adapt the Form) · layout
- visionOS: do system bars appear as ornaments, does a custom ornament hold only controls people always need, and does supplementary content sit in a split view or window instead of an ornament? — **visionOS** · ornaments, split-views
- Mac: is every command in the menu bar (toolbar items included), with keyboard shortcuts for the most frequent ones, and a sidebar people can show and hide? — `../../design/references/platform-idioms.md` (Mac) · designing-for-macos, keyboards

## iPhone Duo (iPhone targets)

Ask these only when the project targets iPhone. A single screenshot shows one pose, so list the other poses under `## Not checked`. Technique and APIs for the fixes: `swift:swiftui` → `iphone-duo.md`, `toolbar-patterns.md`.

- Does the layout rely on fixed widths, a device or orientation check, or anything tied to one display, instead of size classes, layout margins and safe areas? — **iPhone Duo** · `../../design/references/hierarchy-layout.md` (Rank and Reading Order) · designing-for-iphone-duo
- Is any control or content available only on the inner display or in one pose, rather than the same functionality everywhere (one more hierarchy level on the inner display is fine)? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Does the layout change drastically between sizes or poses (controls vanish or move far, or a pose gets its own screen)? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Is a two-pane screen a system split view or arrangement view, rather than a hand-built stack of panes, and is any tab view or navigation container outside the arrangement view? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Are the bars the system's, with default placement (no hand-built top or bottom bar, no overridden placement), so they can move to the side edge? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Are leading and trailing insets taken from the safe area for each edge, with no symmetric hard-coded padding that a side bar would cover? — **iPhone Duo** · `../../design/references/hierarchy-layout.md` (Margins and Safe Areas) · designing-for-iphone-duo
- In a grid, is the column count even, and is no important content or control placed where the fold will cross it? — **iPhone Duo** · `../../design/references/hierarchy-layout.md` (Margins and Safe Areas) · designing-for-iphone-duo
- In a multi-pane screen, do the controls that affect one pane sit with that pane, rather than in the toolbar that serves the other? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Do the most-used toolbar action and any badged item have a higher visibility priority, so overflow removes less important items first? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Does each toolbar item that is not text-only have a title as well as a symbol (a `Label`, not an icon-only `Image`)? A screenshot cannot show the title; ask for the code — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Are toolbar items grouped with the system group types, with no fixed spacing added by hand? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Does the app use the system overflow menu rather than its own, and is the ellipsis symbol used only for overflow? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- On a screen with both a tab bar and a toolbar, does the compression choice match the screen's job (tab bar kept for browsing, toolbar kept for a task)? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo
- Does an edge-to-edge screen have no bars to lose and keep its content clear of the Dynamic Island and the status bar? — **iPhone Duo** · `../../design/references/platform-idioms.md` (iPhone Duo) · designing-for-iphone-duo

## Liquid Glass Placement

- Is glass only on bars, sidebars and controls floating above content, and never on lists, tables, cards or backgrounds? — **Liquid Glass** · `../../design/references/liquid-glass-design.md` (Glass Is the Navigation Layer) · materials
- Is there no glass on glass, and does tint carry meaning rather than decoration? — `../../design/references/liquid-glass-design.md` (No Glass on Glass, Tint and Colour) · materials
- Missing glass is never a finding (see `../SKILL.md` Operating Rules).

## Motion

- Does each custom animation explain a change or give feedback, stay brief, and never block input or carry information on its own? — `../../design/references/motion.md` (Motion Explains a Change, Keep It Short) · motion
- Is custom motion a spring preset (`.smooth`, `.snappy`, `.bouncy`) or a tuned one, rather than an invented curve? — `../../design/references/motion.md` (Springs by Default) · motion
- Under Reduce Motion, do slides and zooms become fades, and does automatic or repeating motion stop? — `../../design/references/motion.md` (Reduce Motion) · accessibility

## Accessibility

- Does every icon-only control and meaningful image have an accessibility label, and are decorative images hidden from VoiceOver? — `../../swiftui/references/accessibility-patterns.md` · accessibility
- Do grouped elements read as one VoiceOver element where they form one idea, in a sensible reading order? — `../../swiftui/references/accessibility-patterns.md` · accessibility
- Does the layout hold at the largest Dynamic Type size without clipping or overlapping? — `../../swiftui/references/accessibility-patterns.md` · accessibility
