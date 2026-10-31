---
type: tool_used
tool: Bash
input_match: 'rounds/r\d+/[^;&|]*index\.html|[^\w-]site/|\bsite\s+approve'
min: 0
max: 0
weight: 1
---
No page of the site is made, captured or checked through the shell either: nothing touches a round's index.html or site/, and `site approve` is not run.
