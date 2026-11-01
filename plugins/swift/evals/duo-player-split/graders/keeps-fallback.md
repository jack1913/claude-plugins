---
# The prompt asks to keep the current layout on older systems: the HStack stays as the
# fallback (alone or inside a ViewThatFits).
type: regex
pattern: '\bHStack\b'
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---
