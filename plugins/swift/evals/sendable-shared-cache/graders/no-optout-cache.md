---
type: regex
pattern: 'nonisolated\(unsafe\)|@unchecked|@preconcurrency'
match: not_contains
target: { source: file, path: Sources/Demo/Cache.swift }
---
