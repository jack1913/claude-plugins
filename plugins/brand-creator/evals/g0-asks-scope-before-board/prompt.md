---
name: g0-asks-scope-before-board
description: 'A one-line bakery request: G0 asks the scope (tier) before any board exists.'
tags: [g0, gate]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'A tier question with a recommendation; no project scaffold, no board file.'
---

I want a logo and a whole look for my bakery. Where do we start?
