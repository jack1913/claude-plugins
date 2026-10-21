---
name: r1-board-map-today-none
description: 'A Standard project with an incumbent wordmark and no round yet: the first board carries the map, Today and None of these.'
tags: [board, heavy]
max_turns: 80
timeout_seconds: 2400
runs: 2
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit, Agent]
expected_outcome: 'rounds/r1/board.html exists, passes the plugin''s lint, has the three sections; no agent was started (shots are not graded: a run has no set-up data folder, so shot is not verified).'
---

G0 is done and I skipped the style research (G1s is recorded in BRAND-STATE.md; see also brief/BRIEF.md). Build the round 1 pick board for Acme in rounds/r1/board.html: the directions and the page. Lint it, then stop for my pick.
