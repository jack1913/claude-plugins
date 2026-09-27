---
type: regex
pattern: 'Task\.sleep|\bsleep\(|usleep|XCTestExpectation|XCTestCase'
match: not_contains
target: { source: file, path: Tests/DemoTests/SaverTests.swift }
---
