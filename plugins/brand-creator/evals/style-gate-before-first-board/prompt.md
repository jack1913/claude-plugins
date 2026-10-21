---
name: style-gate-before-first-board
description: 'A fresh project after G0 with no style pick: the first turn draws no board of directions, and without web tools the skill says the style research needs web access and stops.'
tags: [gate, board, style]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'No rounds/r1 board is written and no G1s is recorded; the reply says the style research needs web access (this run has no web tools) and stops, with no reference, link or brand named as researched.'
---

G0 is done (see BRAND-STATE.md and brief/BRIEF.md). Show me the first board of directions for Acme.
