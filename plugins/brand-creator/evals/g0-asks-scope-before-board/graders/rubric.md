---
type: llm
focus: trace
weight: 1
---
PASS if the reply asks the owner to choose the scope (a Quick, Standard or Full tier) with a recommended option, with at most
three concrete scope questions (plus, only when boards could be uploaded to claude.ai, one question about that) and any facts
it cannot find batched into one plain message, and builds nothing yet. Stating how the mark will be made as a default is fine.
FAIL if it starts building a board or project without asking, or asks more than a handful of questions, or asks what the
brand should feel like, or asks the owner to choose how the mark is produced (generated, vector or similar).
