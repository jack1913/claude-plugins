---
type: regex
pattern: '(?:what (?:should|do you want) (?:people|your (?:audience|listeners|customers|clients))(?: to)? feel|how should (?:it|the brand|your brand|the identity) feel|what (?:feeling|emotion|mood)s?\b|which (?:feeling|emotion|mood)s?\b|jakie emocje|co (?:ludzie|odbiorcy|słuchacze|klienci) mają czuć)'
flags: i
match: not_contains
target: last_message
weight: 1
---
Nor in the reply.
