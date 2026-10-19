---
description: Follow the project's own concurrency rule when it conflicts with the skill's default
tags: [concurrency, project-rules, swift6]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'DashboardLoader.load() fetches the profile and the settings in parallel with a task group, as the project AGENTS.md requires, with no async let (the skill default for fixed parallel work), and the reply says it followed the project rule.'
---

Implement DashboardLoader.load() in Sources/Demo/DashboardLoader.swift so it fetches the profile and the settings in parallel through the client and returns both.
