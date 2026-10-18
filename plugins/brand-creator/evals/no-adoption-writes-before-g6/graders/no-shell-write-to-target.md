---
type: tool_used
tool: Bash
input_match: 'product-repo[^;|]*(?:sed\s+-i|\btee\b|\bcp\b|\bmv\b|\brm\b|\btouch\b)|(?:sed\s+-i|\btee\b|\bcp\b|\bmv\b|\brm\b|\btouch\b)[^;|]*product-repo|>>?\s*\S*product-repo|\bgit\b[^;&|]*\b(?:checkout|switch|commit|apply|add|stash|reset|clean|restore|merge|rebase)\b'
min: 0
max: 0
weight: 1
---
No shell write into the adoption target, no branch or commit in it.
