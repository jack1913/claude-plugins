---
name: judge-view-lead-view-middle-option
description: 'A judge report exists: My call shows the judge view, the lead view and a middle option.'
tags: [board, judge]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'board.html carries data-judge=ran with judge-view, lead-view and middle-option, and passes the lint.'
---

A comparative judge ran over round 1; its report is research/judge-report.md. Fold the result into the My call section of rounds/r1/board.html (round 1 is still the latest round), lint the page, and tell me what changed.
