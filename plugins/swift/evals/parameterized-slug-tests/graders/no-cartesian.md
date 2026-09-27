---
# @Test(arguments: a, b) with two collections runs every combination (25
# cases here, 20 of them wrong), not the aligned pairs.
type: regex
pattern: 'arguments:\s*slugInputs\s*,\s*slugOutputs'
match: not_contains
target: { source: file, path: Tests/DemoTests/SlugTests.swift }
---
