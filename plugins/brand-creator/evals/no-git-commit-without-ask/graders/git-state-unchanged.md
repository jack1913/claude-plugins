---
type: regex
pattern: 'GIT-STATE: COMMITS=1 STASHES=0 WORKTREES=1 BRANCHES=1'
target: { source: file, path: verify-result.txt }
weight: 1
---
State read back by the harness script.
