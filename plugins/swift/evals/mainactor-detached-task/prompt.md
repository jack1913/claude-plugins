---
description: Fix a MainActor isolation error caused by Task.detached
tags: [concurrency, mainactor, swift6]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'The detached task is replaced with a MainActor-inheriting Task (or an equivalent assumeIsolated form), so the score mutation stays main-actor-isolated and the file passes Swift 6 strict concurrency checking.'
---

Sources/Demo/PlayerModel.swift fails Swift 6 strict concurrency checking inside load() with: "main actor-isolated property 'score' can not be mutated from a nonisolated context". Fix the isolation error properly — keep load() non-async and keep score updates on the main actor. Do not suppress checking (no nonisolated(unsafe), no @preconcurrency, no @unchecked).
