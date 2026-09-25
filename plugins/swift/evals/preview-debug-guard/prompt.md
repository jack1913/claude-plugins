---
description: Adding a preview must guard it with #if DEBUG
tags: [swiftui, previews]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: The new #Preview sits inside #if DEBUG … #endif.
---

Add an Xcode preview for InboxView in Sources/Demo/InboxView.swift that shows three sample messages.
