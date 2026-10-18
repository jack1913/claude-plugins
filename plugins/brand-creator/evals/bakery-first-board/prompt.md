---
name: bakery-first-board
description: 'A bakery asks for a logo: no software questions, no registry checks, and a first board exists.'
tags: [g0, board, heavy, non-software]
max_turns: 80
timeout_seconds: 2400
runs: 2
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit, Agent]
expected_outcome: 'bakery/rounds/r1/board.html exists with None of these; no registry check, no agent, no family or platform question.'
---

I'm opening a bakery called Brightloaf in Gdańsk, Poland. I need a logo and a look for the shop sign and Instagram. Quick tier is fine and the name is final; you decide the rest. Put the project in ./bakery/ (current folder) and show me a first board of directions.
