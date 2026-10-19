---
name: architecture-asked-when-parent-shown
description: 'The brief shows a parent brand and sister products: the family question is asked before round 1.'
tags: [g0, architecture]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'A question about family-member, product-in-family or standalone; no board.'
---

My brief is in brief.md. Scope: Quick tier, generated mark, the name Fieldnote is final. Start the project.
