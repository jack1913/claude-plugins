---
type: regex
pattern: 'KIT=UNCHANGED'
target: { source: file, path: verify-result.txt }
weight: 1
---
cmp of every file of the kit against the pristine copy, and no file added to the kit folder.
