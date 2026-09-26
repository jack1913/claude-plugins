---
description: Fix a MainActor isolation error without moving heavy work onto the main actor
tags: [concurrency, mainactor, swift6]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'The heavy synchronous computeScore() stays off the main actor (the task remains detached or otherwise nonisolated) while the score/badge mutations hop back to the main actor (MainActor.run or assumeIsolated), and the file passes Swift 6 strict concurrency checking.'
---

Sources/Demo/PlayerModel.swift fails Swift 6 strict concurrency checking inside load() with: "main actor-isolated property 'score' can not be mutated from a nonisolated context". Fix the isolation error properly, with both constraints: the heavy synchronous computeScore() must not run on the main actor, and the score/badge mutations must stay main-actor-isolated. Keep load() non-async. Do not suppress checking (no nonisolated(unsafe), no @preconcurrency, no @unchecked).
