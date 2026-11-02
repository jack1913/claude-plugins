---
name: kit-test-hero
description: 'A project whose brand kit is written: a hero built from the kit alone is page-checked, the reply reports the check and the gaps the kit showed, and no kit file changes.'
tags: [kit]
max_turns: 50
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
expected_outcome: 'kit-test/hero.html exists, takes its values from the kit CSS variables and uses a logo file of the kit; the page check ran on it (brand-creator page-check); the reply gives the check outcome (in a run with no set-up data folder the check exits 3, so: not verified, never a pass), names the sample content to replace before publishing and the gaps the kit showed; every file of .claude/skills/acme-brand/ is byte-identical to the pristine copy.'
---

Acme's brand kit is written: it is in .claude/skills/acme-brand/. Using only that kit, build the hero of Acme's home page in kit-test/hero.html. A visitor comes to find out what Acme sells and whether the tools can be repaired. The hero also shows the flagship tool's price and the date the online shop opens; Acme has not given us either yet. Then check the page against the brand. I'm away, so settle anything you would ask me yourself and say so. The kit is read only in this test: change no file in it, and put each gap in your reply instead. Tell me how the check went and what the kit did not give you.

(Eval harness note, not part of the request: when you stop, run `bash .eval-verify/verify.sh > verify-result.txt`.)
