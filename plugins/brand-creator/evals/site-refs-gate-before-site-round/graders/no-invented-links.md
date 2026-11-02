---
type: regex
pattern: 'https?://(?!example\.com)'
flags: i
match: not_contains
target: last_message
weight: 1
---
No link is offered as a researched reference (the only address in the fixture is example.com).
