---
type: regex
pattern: 'ADOPTION-TARGET=UNCHANGED'
target: { source: file, path: verify-result.txt }
weight: 1
---
cmp of every file against the pristine copy, plus git state of the target.
