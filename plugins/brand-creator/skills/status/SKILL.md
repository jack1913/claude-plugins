---
name: status
description: Shows where the current brand project stands (tier, phase, recorded gates, directions, review page) and the next gate.
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Brand project status

Current state, read by the plugin from the nearest BRAND-STATE.md at or above the current folder:

!`brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`

Using only the output above (and BRAND-STATE.md when you need detail), reply in at most eight lines:

1. Brand, tier, phase.
2. Gates recorded, and the next gate with what it needs from the owner.
3. Directions: the canonical one and the status of the others.
4. Review page (`review_url`) and anything listed under Still open.

If the output says no brand project was found, say that in one line and offer `/brand-creator:new`, or ask for the
project folder. Do not start any work from this command.
