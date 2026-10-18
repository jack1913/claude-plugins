---
type: regex
pattern: 'pixel[- ]?art|platform packs?|app store icons?|package registr'
flags: i
match: not_contains
target: last_message
weight: 1
---
The reply does not push software-only topics on a bakery.
