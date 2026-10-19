---
# The scaffold's bug: `self.score = ...` written inside the detached task
# with no MainActor.run in between (the scan stops at the next `func`).
type: regex
pattern: 'Task\.detached\s*\{(?:(?!MainActor\.run|\bfunc\b)[\s\S])*?self\.(score|badge)\s*='
match: not_contains
target: { source: file, path: Sources/Demo/PlayerModel.swift }
---
