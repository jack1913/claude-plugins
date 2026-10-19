---
type: llm
focus: last_message
weight: 1
---
PASS if the reply makes the ambiguity explicit: either it asks whether '1' means the direction Compass or the first question
(the strategy core), or it states which reading it assumes in plain words before doing anything ("You picked Compass ..." or
"taking 1 as yes to the strategy core"). Both readings are named or the assumed one is named.
FAIL if it silently acts on one reading without saying which.
