---
name: architecture-standalone-stated
description: 'A one-person practice with no parent or siblings: architecture is stated as standalone, not asked.'
tags: [g0, architecture]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'No family or parent question; the reply says standalone; the project is scaffolded.'
---

My brief is in brief.md. Scope: Quick tier, generated mark, the name Steady Steps is final. Set the project up, tell me in one message what you decided about scope and architecture, and stop before any board.
