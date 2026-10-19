---
type: regex
pattern: 'pixel[- ]?art|platform packs?|app store icons?|package registr|pakiet(?:y|ów|ach)? (?:na )?platform|ikon(?:y|a)? aplikacji|rejestr(?:y|ach|ów)? pakietów'
flags: i
match: not_contains
target: last_message
weight: 1
---
The reply does not push software-only topics on a photographer (the question tool is not in a non-interactive run, so
the reply is where such a question would show).
