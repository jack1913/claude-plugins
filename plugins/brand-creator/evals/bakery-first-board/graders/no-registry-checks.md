---
type: tool_used
tool: Bash
input_match: '\bnpm\s+(?:view|info|search|show)\b|\bpip\s+(?:index|download|search)\b|pypi\.org|crates\.io|registry\.npmjs\.org|\bcargo\s+search\b|\bbrew\s+(?:info|search)\b|\bdocker\s+(?:search|pull)\b|formulae\.brew\.sh|names\b.*--profile\s+software'
min: 0
max: 0
weight: 1
---
No package-registry or software-profile name checks for a bakery.
