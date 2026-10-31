---
name: site-refs-gate-before-site-round
description: 'A Standard project with the system rules approved (G4) and a brief that lists a site, no website references picked: a request for the home page writes no page of the site, and without web tools the skill says the website references need web access and stops.'
tags: [gate, site]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'No page of the site is written (no rounds/r*/**/index.html, nothing under site/), neither G4w nor a skip is recorded and site_research is not set by the agent; the reply names the website references and web access (this run has no web tools) and stops, with no site, link or brand named as researched.'
---

G4 is done. Build the home page of Acme's site.
