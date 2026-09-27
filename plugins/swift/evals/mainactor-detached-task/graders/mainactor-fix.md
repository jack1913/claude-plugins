---
# The score/badge mutation must hop back to the main actor explicitly.
# (MainActor.assumeIsolated is not a hop: from the detached task it traps at
# runtime, so it is rejected by no-assume-or-optout.md.)
type: regex
pattern: 'MainActor\.run'
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
