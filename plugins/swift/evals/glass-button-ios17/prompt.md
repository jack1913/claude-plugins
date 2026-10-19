---
description: Glass button in a package whose deployment target is below 26
tags: [swiftui, liquid-glass, availability]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'The glass button sits behind if #available(iOS 26, macOS 26, *) with a material fallback, because Package.swift targets iOS 17.5 and macOS 14.'
---

Add a glass button labelled "Continue" at the bottom of the view in Sources/Demo/ContentView.swift.
