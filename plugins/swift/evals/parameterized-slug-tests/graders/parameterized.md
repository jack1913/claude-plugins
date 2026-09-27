---
# One parameterized test; allows traits with one level of parentheses before
# arguments:, e.g. @Test("name", .tags(.x), arguments: ...).
type: regex
pattern: '@Test\((?:[^()]|\([^()]*\))*arguments:'
target: { source: file, path: Tests/DemoTests/SlugTests.swift }
---
