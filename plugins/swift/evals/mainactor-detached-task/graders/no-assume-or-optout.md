---
type: regex
pattern: 'assumeIsolated|nonisolated\(unsafe\)|@preconcurrency|@unchecked'
match: not_contains
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
