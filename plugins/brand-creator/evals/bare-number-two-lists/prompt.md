---
name: bare-number-two-lists
description: 'The owner replies with a bare ''1'' while a direction list and a question list are both numbered.'
tags: [g2, working-style]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'The reply restates its reading or asks which list is meant.'
---

Your last message ended with two numbered lists.

The directions on the board: 1 Compass, 2 Lantern, 3 Keystone.
Your questions for me: 1 Is the strategy core right as written? 2 Is the tagline line fine? 3 Where should the dot sit?

My whole reply to that message is: 1
