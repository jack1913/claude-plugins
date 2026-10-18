---
type: llm
focus: trace
weight: 1
---
PASS if the reply asks the owner to choose the scope (a Quick, Standard or Full tier) with a recommended option, with at most
four concrete questions and any facts it cannot find batched into one plain message, and builds nothing yet.
FAIL if it starts building a board or project without asking, or asks more than a handful of questions, or asks what the
brand should feel like.
