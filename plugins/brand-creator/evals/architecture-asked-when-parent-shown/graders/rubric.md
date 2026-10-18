---
type: llm
focus: trace
weight: 1
---
The brief names a parent company and sister products. PASS if, before building any board, the agent asks the owner about the
relationship to those brands (a family member sharing a family layer, a product inside the family, or a standalone brand),
via a question tool call or a plain question, ideally with a recommended option.
FAIL if it states 'standalone' without asking, or silently builds a board, or never raises the relationship at all.
