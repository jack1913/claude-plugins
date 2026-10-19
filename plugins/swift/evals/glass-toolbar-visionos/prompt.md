---
description: Floating glass controls in an app that also ships on visionOS
tags: [swiftui, liquid-glass, visionos]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'An #if os(visionOS) branch uses glassBackgroundEffect (or an ornament); GlassEffectContainer and glass styles appear only in the non-visionOS branch.'
---

Add a floating glass toolbar with Play, Pause and Stop buttons over the content of Sources/Demo/ContentView.swift.
