---
description: Table-driven tests for a pure function in a Swift Testing package
tags: [testing, swift-testing, parameterized]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'Tests/DemoTests/SlugTests.swift imports Testing and covers all five cases with one parameterized @Test (arguments:), not five copies or a loop inside one test, and no XCTest.'
---

Add tests for slugify in Tests/DemoTests/SlugTests.swift covering these cases: "Hello World" → "hello-world", "  Trim  me  " → "trim-me", "Swift & SwiftUI!" → "swift-swiftui", "already-slug" → "already-slug", "" → "". Use the project's test framework.
