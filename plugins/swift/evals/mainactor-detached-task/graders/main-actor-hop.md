---
# The score/badge mutation must reach the main actor through a real hop:
# MainActor.run, an awaited call to a main-actor method, or a MainActor-
# inheriting Task that awaits the off-main work: an @concurrent
# computeScore(), or the `.value` of a Task.detached that runs it.
# MainActor.assumeIsolated is not a hop (it traps from a detached task) and is
# rejected by no-assume-or-optout.md.
type: regex
pattern: 'MainActor\.run|await\s+self\??\.\w+\(|await\s+(Self|PlayerModel)\.computeScore\(|await\s+Task\.detached\b[\s\S]*?\}\s*\.value\b'
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
