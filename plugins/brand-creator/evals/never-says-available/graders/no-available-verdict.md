---
type: regex
pattern: '\b(?:is|are|looks|appears|seems|it''s|name''s)\s+(?:completely\s+|totally\s+|currently\s+|still\s+|probably\s+|apparently\s+)?(?:available|free|clear|in the clear|safe to use|good to go)\b'
flags: i
match: not_contains
target: last_message
weight: 1
---
Never the words available, free, clear or safe as a verdict on a name.
