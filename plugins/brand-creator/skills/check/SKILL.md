---
name: check
description: Runs every check that applies to the current brand project (boards, contrast, logo sheet, files, book, print, adoption and the history record) and, given old names or colours, searches the whole project for leftovers. Reports each failing row with its fix. Runs only when typed as /brand-creator:check.
argument-hint: "[<old value or phrase> ...]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Check

Thin wrapper over `brand-creator check`; what each row means is in
[09-qa](../brand-creator/references/phases/09-qa.md) and the cascade method in
[cascade](../brand-creator/references/cascade.md). Arguments: `$ARGUMENTS` (old values or phrases that must be gone;
empty → the gates only).

1. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. None → say so and offer
   `/brand-creator:new`.
2. Run the gates: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" check --project <dir>`. It covers the history manifest
   (`history/MANIFEST.sha256`), report currency and every gate of the tier.
3. With arguments, run the cascade too, one `--cascade` per old value:
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" check --project <dir> --cascade "<old value>"`. Add `--also <path>`
   for a parent brand's document the owner names. Adoption work-list lines warn; every other hit fails.
4. Reply in this order: the exit code and what it means (0 pass, 1 a gate failed, 2 usage, 3 cannot run); each failing
   row with its file and the fix the message names; warnings; rows "not verified" with the reason. Never report a row
   that did not run as passed.
5. Fix nothing unasked. Offer the fixes as one list: those that need no decision first, then numbered decisions with a
   recommendation. A fix goes into a source (a token, a chapter, a generator), never into an output.
