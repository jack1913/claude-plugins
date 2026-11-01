---
# The two peer regions belong in an ArrangementView with a split style, which places
# them on either side of an active fold. Any initializer form and either order.
type: regex
pattern: '^(?=[\s\S]*\bArrangementView\s*[({])(?=[\s\S]*\.arrangementViewStyle\(\s*(?:\.split\b|SplitArrangementViewStyle\b))'
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---
