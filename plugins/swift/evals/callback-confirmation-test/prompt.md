---
description: Test a callback delivered later on another queue with Swift Testing
tags: [testing, swift-testing, confirmation, async]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'Tests/DemoTests/SaverTests.swift uses confirmation (expected count 1) and keeps the confirmation body waiting until the callback arrives (for example with withCheckedContinuation), with no sleeps and no XCTest expectations.'
---

In Tests/DemoTests/SaverTests.swift, test that save(3) calls onSave exactly once with 3, using Swift Testing.
