---
type: regex
pattern: '\b(?:i(?:''ve| have)?|we(?:''ve| have)?)\s+(?:just\s+)?(?:committed|pushed|merged|stashed)\b'
flags: i
match: not_contains
target: last_message
weight: 1
---
