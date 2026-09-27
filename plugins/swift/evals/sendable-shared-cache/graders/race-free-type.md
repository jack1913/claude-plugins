---
# Either shape the expected_outcome allows: an actor, or a lock-protected
# Sendable class. (Mutex needs macOS 15; the scaffold targets macOS 14.)
type: regex
pattern: 'actor ImageCache|OSAllocatedUnfairLock'
target: { source: file, path: Sources/Demo/Cache.swift }
---
