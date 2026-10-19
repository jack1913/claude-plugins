---
type: regex
pattern: '\b(?:baseline|original|for comparison)\b|\(current\)|\bcurrent (?:mark|compass|version|one)\b'
flags: i
target: last_message
weight: 1
---
The liked original stays visible as the baseline (named as such, as the original, or as the current mark kept for comparison;
a reply that wrote "Sharp (current): the mark unchanged" was a false negative of the narrower pattern).
