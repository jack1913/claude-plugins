---
# computeScore() moved inside MainActor.run runs the heavy work on the main
# actor, which the prompt forbids, even though Task.detached is still present.
type: regex
pattern: 'MainActor\.run\s*\{[^}]*computeScore'
match: not_contains
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
