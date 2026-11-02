---
# The package targets iOS 26 and macOS 15, so the gate must name iOS 27.1 and macOS 27.1,
# in either order; #unavailable with both and the SDK's anyAppleOS form also count.
type: regex
pattern: '#available\((?=[^)]*\biOS\s+27\.1\b)(?=[^)]*\bmacOS\s+27\.1\b)[^)]*\*\s*\)|#unavailable\((?=[^)]*\biOS\s+27\.1\b)(?=[^)]*\bmacOS\s+27\.1\b)[^)]*\)|#available\(\s*anyAppleOS\s+27\.1\b'
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---
