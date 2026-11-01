---
# The two peer regions belong in an ArrangementView with a split style, which places
# them on either side of an active fold.
type: regex
pattern: 'ArrangementView\s*\{[\s\S]*\.arrangementViewStyle\(\s*\.split'
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---
