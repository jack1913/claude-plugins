# Reviewing a Screenshot

A screenshot shows one state of one screen at one size, in one appearance. Judge what it shows, and list the rest under `## Not checked` along with the capture that would show it. Never infer a finding the image can't support. Code you haven't been given is not evidence.

## What One Image Can Show

Check these against `checklist.md`, limited to what is visible in the frame:
- hierarchy and grouping: one primary element, related items grouped, labelled values aligned in rows
- apparent contrast: text that is hard to read against its background
- colour alone carrying meaning: a coloured dot or tint with no symbol or label beside it
- symbol and label use: custom images where SF Symbols fit, and icon-only controls that are hard to read
- how many buttons look prominent (filled or tinted), and whether a destructive action looks like the default
- glass placement: glass on cards, list rows or backgrounds rather than on bars and floating controls
- margins: content running into the screen edges or under the status bar

## What It Cannot Show

| Not visible in one image | Ask for |
|--------------------------|---------|
| Exact point sizes and text styles | The capture's scale (@2x, @3x) or the code |
| Dynamic Type behaviour | A capture at an accessibility text size |
| Dark mode, increased contrast | A capture in each appearance |
| Motion and Reduce Motion | A screen recording, or the code |
| VoiceOver labels and reading order | The code, or an Accessibility Inspector pass |
| Toolbars, tab bars, sheets or menus outside the frame | A capture that includes them |
| Target platform | The platform, if the image doesn't make it plain |

## Estimating Sizes from Pixels

- Points = pixels ÷ scale. State the scale you assume: @2x for most Mac and iPad captures, @3x for most recent iPhones. If the image doesn't pin the scale, say so.
- Measure a control's whole hit region, not only its glyph. A glyph can be small inside a larger tappable area, and an image can't show where the tappable area ends. When the region can't be seen, report the glyph size and say that the hit region is unknown.
- Every size taken from pixels carries `(estimated)` in the finding, for example "the close button is about 28×28 pt (estimated, @2x)". Never state an exact point size from an image.

## Combining with Code

When the view's code is also given, the code settles what the image only suggests: styles, roles, labels and frames. Report an issue once, cite both the `file:line` and the screenshot region, and drop the `(estimated)` mark once the code confirms the value.
