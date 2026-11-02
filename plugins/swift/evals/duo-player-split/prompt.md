---
description: Two peer regions split around the iPhone Duo fold in a package that also targets macOS
tags: [swiftui, iphone-duo, layout, availability]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'PlayerScreen uses ArrangementView with a split style behind an availability check that names iOS 27.1 and macOS 27.1, keeps the HStack as the fallback, and does not branch on the device, the screen or the orientation.'
---

On iPhone Duo, when the phone is half open like a book, the fold runs through the middle of PlayerScreen in Sources/Demo/PlayerScreen.swift. Make the player and the up-next list sit on either side of the fold, and keep the current layout on older systems.
