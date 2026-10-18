---
name: r1-board-map-today-none
description: 'A Standard project with an incumbent wordmark and no round yet: the first board carries the map, Today and None of these.'
tags: [board, heavy]
max_turns: 80
timeout_seconds: 2400
runs: 2
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit, Agent]
expected_outcome: 'rounds/r1/board.html exists, passes the plugin''s lint, has the three sections; no agent was started.'
---

G0 is done (see BRAND-STATE.md and brief/BRIEF.md). Build the round 1 pick board for Acme in rounds/r1/board.html: the directions and the page. Lint it, then stop for my pick.
