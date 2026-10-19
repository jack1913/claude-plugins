---
# One parameterized test; allows traits with up to two levels of parentheses
# before arguments:, e.g. @Test(.timeLimit(.minutes(1)), arguments: ...).
type: regex
pattern: '@Test\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*arguments:'
target: { source: file, path: Tests/DemoTests/SlugTests.swift }
---
