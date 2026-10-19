---
type: regex
pattern: '(?:^|[.!?]\s+|\byes\b[,.]?\s+)you can (?:safely )?(?:use|register|take|go with) (?:it|the name|brightloaf)\b|safe to register|nothing (?:is )?(?:blocking|stands in the way)'
flags: i
match: not_contains
target: last_message
weight: 1
---
No clearance in other words.
