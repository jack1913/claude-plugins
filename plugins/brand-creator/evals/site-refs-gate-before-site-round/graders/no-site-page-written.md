---
type: tool_used
tool: Write
input_match: '"file_path"\s*:\s*"(?:[^"]*[^\w"-])?(?:site/|rounds/r\d+/(?:[^"/]+/)*index\.html)'
min: 0
max: 0
weight: 1
---
No page of the site is written before the website references are picked (G4w): not into a round, not into site/.
