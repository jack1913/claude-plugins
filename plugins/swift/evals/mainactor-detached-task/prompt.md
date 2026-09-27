---
description: Fix a MainActor isolation error without moving heavy work onto the main actor
tags: [concurrency, mainactor, swift6]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'The heavy synchronous computeScore() stays off the main actor (the task stays detached or @concurrent) while the score/badge mutations hop back with MainActor.run, and the file passes Swift 6 strict concurrency checking without MainActor.assumeIsolated (which traps from a detached task) or any checking opt-out.'
---

Sources/Demo/PlayerModel.swift fails Swift 6 strict concurrency checking inside load() with: "main actor-isolated property 'score' can not be mutated from a nonisolated context". Fix the isolation error properly, with both constraints: the heavy synchronous computeScore() must not run on the main actor, and the score/badge mutations must stay main-actor-isolated. Keep load() non-async. Do not suppress checking (no nonisolated(unsafe), no @preconcurrency, no @unchecked).
