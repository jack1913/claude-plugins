---
type: regex
pattern: 'XCTestCase|XCTAssert'
match: not_contains
target: { source: file, path: Tests/DemoTests/SlugTests.swift }
---
