---
# "with 3": the test must check the value the callback receives.
type: regex
pattern: '==\s*\[?\s*3\b|\b3\s*\]?\s*=='
target: { source: file, path: Tests/DemoTests/SaverTests.swift }
---
