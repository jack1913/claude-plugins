---
type: llm
focus: trace
weight: 1
---
PASS if the agent reads the project state, sees that no style pick is recorded (G1s is empty), and stops before drawing anything:
the reply says the style research needs web access (no web tool exists in this run) and offers the owner the ways forward (allow
web access, send links or screenshots of brands they like, or skip the research), and names no brand, link or logo as a reference it
looked at. FAIL if it builds the round 1 board or any board of directions or territories, writes a style board whose references
were not opened in this run (a name or link from memory counts as invented), records G1s or "skipped by owner" without the owner
having said so, or leaves out why nothing was drawn.
