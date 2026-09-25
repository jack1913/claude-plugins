---
# The scaffold targets iOS 17.5 and macOS 14, so one `#available` gate must
# name both iOS 26 and macOS 26, in either order.
type: regex
pattern: '#available\((?=[^)]*\biOS\s+26\b)(?=[^)]*\bmacOS\s+26\b)[^)]*\*\s*\)'
target: { source: file, path: Sources/Demo/ContentView.swift }
---
