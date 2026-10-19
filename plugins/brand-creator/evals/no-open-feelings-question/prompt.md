---
name: no-open-feelings-question
description: 'The owner has no idea what it should look like; the agent must not ask an abstract feelings question.'
tags: [g0, working-style]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'Concrete scope or fact questions only (or a decision with options); no feelings question.'
---

Make a visual identity for my podcast about urban gardening. Surprise me, I honestly have no idea what it should look like.
