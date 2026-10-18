---
name: photographer-first-board-pl
description: 'A photographer asks in Polish: no software questions, no registry checks, a first board exists, the chat stays Polish.'
tags: [g0, board, heavy, non-software, pl]
max_turns: 80
timeout_seconds: 2400
runs: 2
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit, Agent]
expected_outcome: 'foto/rounds/r1/board.html exists with None of these; the reply is Polish; no registry check, no agent, no family or platform question.'
---

Potrzebuję logo i identyfikacji wizualnej dla mojej pracowni fotograficznej w Krakowie. Nazwa: Pracownia Kadr, jest ostateczna. Wystarczy wersja Quick, resztę zdecyduj sam. Projekt umieść w ./foto/ (bieżący folder) i pokaż mi pierwszą tablicę z kierunkami.
