# onboard-repo references

Files that [SKILL.md](../SKILL.md) sends Claude to, one level deep. The first three are read while
detecting and stamping. The rest are sections of the procedure that moved out of SKILL.md to keep it short; each
opens with the section number it came from.

| File | Use it for |
| --- | --- |
| [detection.md](detection.md) | What to detect before stamping: version homes, release scripts, doc layout, consumer surfaces |
| [rubric.md](rubric.md) | Classifying an existing docs page into one of the four tiers |
| [stamping.md](stamping.md) | How a stamped skill is laid out, and what goes in each REPO SPECIFICS block |
| [agent-config.md](agent-config.md) | Section 3.4: permissions in `.claude/settings.json`, `.gitignore`, the rules folder, grounding existing rules and skills |
| [rule-mining.md](rule-mining.md) | Section 3.4c: offering to mine rules from the codebase, with validation |
| [adopt-docs.md](adopt-docs.md) | Section 3.6: moving existing docs into the four tiers and fixing their links |
| [author-manual.md](author-manual.md) | Section 3.7: writing the consumer manual, grounding each output block, the review pass |
| [manual-page-how-to.md](manual-page-how-to.md) | Section 3.7: the shape of a how-to or getting-started page |
| [manual-page-reference.md](manual-page-reference.md) | Section 3.7: the shape of a reference page |
| [adr-mining.md](adr-mining.md) | Section 3.7b: offering to mine decision records from git history |
| [check-mode.md](check-mode.md) | Section 6: what `--check` reports |
