---
name: review
description: >-
  Reviews a SwiftUI screen against Apple's Human Interface Guidelines, from its code and/or screenshots, and
  reports findings with the HIG source and a fix. Checks hierarchy, typography, colour, SF Symbols, controls
  and hit targets, platform idioms, Liquid Glass placement, motion and accessibility. Runs only when typed
  as /swift:review.
argument-hint: "<view files or screenshot paths>"
disable-model-invocation: true
disallowed-tools: Write, Edit, NotebookEdit
---

# SwiftUI Design Review

This skill reviews a screen someone already built and reports what departs from Apple's Human Interface Guidelines, with the guideline and a fix for each finding. It judges against `swift:design`'s Decision Rules and area references, which sit next to this skill in `../design/`; it never restates them, so read them rather than working from memory.

## Inputs

Review what `$ARGUMENTS` names: SwiftUI view files, screenshot image paths, or both. Images pasted into the conversation count as screenshots. With no files and no images, ask which screen to review and stop.

## Operating Rules

- If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict
- For a review that means a value the project's layer sanctions is not a finding: a token, a colour set or a project-skill rule is the project's decision, even where it differs from a system default
- Missing Liquid Glass is never a finding; glass stays opt-in. Glass on content (lists, tables, cards, backgrounds) is a finding
- Report only: never edit, create or delete a file, and never offer a patch as a file change. Fixes are described in the finding
- Review for the platforms the project targets: read `Package.swift`, the Xcode project or the file's `#if os(...)` branches; a rule for another platform is not a finding
- Load `swift:design` and apply its Decision Rules; when a check needs code detail (availability, accessibility modifiers), `swift:swiftui` has it
- A finding needs a HIG basis. Taste without one is not a finding

## Method

1. **Project layer.** Look for token types (a `DesignTokens`-style enum, spacing or radius constants), colour sets beyond the template's AccentColor and a project design skill. Note what they cover, so their values are not reported.
2. **Code pass.** Walk `references/checklist.md` area by area against each view file. Cite `file:line` for every finding.
3. **Screenshot pass.** Follow `references/screenshot-review.md`: judge only what the image shows, state the scale you assume, and mark any measurement taken from pixels `(estimated)`.
4. **Merge.** When code and screenshot show the same issue, report it once with both locations.
5. **Report** in the `references/findings-format.md` shape, most severe first, and end with `## Not checked`: what the inputs could not show and the capture or file that would.

## Scope

In scope: hierarchy and grouping, typography and Dynamic Type, colour and contrast, SF Symbols, controls and hit targets, toolbars, tabs and navigation, sheets and modality, platform idioms, Liquid Glass placement, motion and Reduce Motion, accessibility labels and reading order.

Out of scope: API correctness, concurrency, performance and tests. Mention an obvious one in a single line after the findings and name the skill that covers it (`swift:swiftui`, `swift:concurrency`, `swift:testing`).

## References

| Topic | Reference |
|-------|-----------|
| The checks, per HIG area, each pointing at its rule and page | `references/checklist.md` |
| What a screenshot can and cannot show; estimating hit targets | `references/screenshot-review.md` |
| Finding line shape, severity, what is not a finding | `references/findings-format.md` |
| The Decision Rules the checks come from | `../design/SKILL.md` |
| Area detail: hierarchy, type, colour, symbols, glass, idioms, motion, tokens | `../design/references/` |
| Accessibility code patterns | `../swiftui/references/accessibility-patterns.md` |
