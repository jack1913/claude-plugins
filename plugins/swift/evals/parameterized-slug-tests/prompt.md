---
description: Table-driven tests for a pure function in a Swift Testing package
tags: [testing, swift-testing, parameterized]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'Tests/DemoTests/SlugTests.swift imports Testing and checks every slugInputs[i] against slugOutputs[i] with one parameterized @Test that pairs them (zip or indices), not the two-collection form arguments: slugInputs, slugOutputs, which runs the 25-case cartesian product; no XCTest.'
---

Add a parameterized test for slugify in Tests/DemoTests/SlugTests.swift that uses the fixtures in Tests/DemoTests/SlugFixtures.swift. Use the project's test framework.
