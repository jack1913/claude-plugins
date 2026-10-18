---
type: regex
pattern: '(?=[\s\S]*\b(?:recommend|suggest))[\s\S]*\bquick\b[\s\S]*\bstandard\b[\s\S]*\bfull\b'
flags: i
target: last_message
weight: 1
---
The three tiers are put to the owner with a recommendation. A `claude plugin eval` run is non-interactive and has no
AskUserQuestion tool (the session's tool list leaves it out even when `allowed_tools` names it), so the question can only
arrive as text; in an interactive session the skill asks it through the question tool.
