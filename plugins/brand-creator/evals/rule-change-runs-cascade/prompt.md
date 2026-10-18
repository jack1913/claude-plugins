---
name: rule-change-runs-cascade
description: 'A rule change with the rule written in several places: the cascade check runs before the agent says done.'
tags: [cascade, heavy]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: '`brand-creator check --cascade "4×4"` ran; the README and book chapter carry the new value; leftovers are reported.'
---

Change the accent minimum rule from 4×4 px to 3×3 px. I checked it at 32 px and it holds. Update everything that has to follow.
