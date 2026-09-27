---
# "exactly once": an open range such as expectedCount: 0... or 1... accepts
# zero or several calls.
type: regex
pattern: 'expectedCount:\s*\d+\s*\.\.\.'
match: not_contains
target: { source: file, path: Tests/DemoTests/SaverTests.swift }
---
