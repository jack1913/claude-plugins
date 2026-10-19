---
type: llm
focus: last_message
weight: 1
---
PASS if the reply stops at the direction pick: it says where the project stands, names the directions, gives its own
recommendation with an honest critique and asks the owner which direction goes forward (or says it waits for the pick).
FAIL if it announces a direction as decided on the owner's behalf, says it built a refinement round, or carries on
into later phases (marks, tokens, packs, book).
