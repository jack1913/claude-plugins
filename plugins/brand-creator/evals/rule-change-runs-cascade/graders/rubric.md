---
type: llm
focus: last_message
weight: 1
---
PASS if the reply says the rule was changed everywhere it was written (BRAND-STATE rule, README, book chapter) and reports the
result of the search for the old value (what it found, what it updated, or that nothing was left).
FAIL if it only edited one file, or claims every place is updated without having searched.
