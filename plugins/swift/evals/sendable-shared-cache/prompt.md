---
description: Remove nonisolated(unsafe) opt-outs from a shared cache under Swift 6
tags: [concurrency, sendable, swift6]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'ImageCache becomes an actor (or an explicitly lock-protected Sendable type) with no nonisolated(unsafe) or @unchecked opt-out, and Downloader.swift keeps compiling with await at the call sites.'
---

The team enabled Swift 6 language mode. Sources/Demo/Cache.swift silences the data-race diagnostics with nonisolated(unsafe). Remove those opt-outs and make ImageCache safe to share across tasks, keeping Sources/Demo/Downloader.swift compiling. Do not suppress checking (no @unchecked Sendable, no @preconcurrency, no nonisolated(unsafe)).
