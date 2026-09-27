# Findings Format

Put each finding on its own line, most severe first:

```text
- [<severity>] <violation> — <location> — HIG: <page URL> — Fix: <fix>
```

- **severity:** `high`, `medium` or `low` (see below).
- **violation:** what is wrong, in one clause, naming the view or control.
- **location:** `<file>:<line>` for code; `screenshot: <region>` for an image, such as `screenshot: top-right toolbar`. Give both when both show it.
- **HIG:** the page the finding rests on, `https://developer.apple.com/design/human-interface-guidelines/<page>`.
- **Fix:** the change, described in words and the SwiftUI to use. It is not applied, because the review is report-only.

Examples:

```text
- [high] Track titles use .lineLimit(1) and truncate at accessibility text sizes — LibraryRow.swift:18 — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: drop the line limit, or switch to a vertical layout when dynamicTypeSize.isAccessibilitySize
- [medium] The share button is a custom image instead of the Share symbol — screenshot: top-right toolbar — HIG: https://developer.apple.com/design/human-interface-guidelines/icons — Fix: Image(systemName: "square.and.arrow.up"), or ShareLink
```

## Severity

- **high:** breaks a HIG requirement a person runs into. Examples: a hit region under 44×44 pt (60×60 pt on visionOS); meaning carried by colour alone; a destructive action that is the default or unmarked; text that can't scale with Dynamic Type.
- **medium:** goes against HIG guidance and has a clear fix. Examples: stacks with dividers instead of a `Form`; more than one tinted primary action; Done without Cancel; glass on content.
- **low:** polish. Examples: symbol weight not matching its label; a toolbar group that could merge.

## Not a Finding

- A value the project's design layer sanctions: its tokens, colour sets or project design skill rules
- Missing Liquid Glass
- A rule for a platform the project doesn't target
- Taste with no HIG basis
- Anything the inputs can't show: it goes under `## Not checked`

## Report Shape

```text
## Findings
- [high] …
- [medium] …

## Not checked
- Dynamic Type: no accessibility-size capture; send one to check truncation.
```

With no findings, say so under `## Findings` and still list `## Not checked`.
