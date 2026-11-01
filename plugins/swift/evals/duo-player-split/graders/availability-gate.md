---
# The package targets iOS 26 and macOS 15, so the gate must name iOS 27.1 and macOS 27.1,
# in either order.
type: regex
pattern: '#available\((?=[^)]*\biOS\s+27\.1\b)(?=[^)]*\bmacOS\s+27\.1\b)[^)]*\*\s*\)'
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---
