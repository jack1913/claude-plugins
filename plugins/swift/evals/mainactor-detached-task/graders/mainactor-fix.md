---
# The mutation must hop back to the main actor explicitly; a plain `Task {}`
# would inherit MainActor and run the heavy computeScore() on main, which the
# prompt forbids — so the fix needs MainActor.run / assumeIsolated.
type: regex
pattern: 'MainActor\.run|assumeIsolated'
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
