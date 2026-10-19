---
# The heavy synchronous computeScore() must stay off the main actor: a plain
# `Task {}` inside the @MainActor class inherits MainActor and would run it on
# main, which the prompt forbids.
type: regex
pattern: 'Task\.detached|@concurrent'
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
