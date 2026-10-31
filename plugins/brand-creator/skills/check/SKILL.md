---
name: check
description: Runs every check that applies to the current brand project (boards, contrast, logo sheet, files, book, print, adoption and the history record) and, given old names or colours, searches the whole project for leftovers. Reports each failing row with its fix. Runs only when typed as /brand-creator:check.
argument-hint: "[--page <file-or-folder-page-or-localhost-url>] [<old value or phrase> ...]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Check

Thin wrapper over `brand-creator check` and `brand-creator page-check`; what each row means is in
[09-qa](../brand-creator/references/phases/09-qa.md) and the cascade method in
[cascade](../brand-creator/references/cascade.md). Arguments: `$ARGUMENTS` (`--page` and the page to check, then old
values or phrases that must be gone; empty → the gates only).

1. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. None → say so and offer
   `/brand-creator:new`.
2. Run the gates: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" check --project <dir>`. It covers the history manifest
   (`history/MANIFEST.sha256`), report currency and every gate of the tier.
3. With arguments, run the cascade too, one `--cascade` per old value:
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" check --project <dir> --cascade "<old value>"`. Add `--also <path>`
   for a parent brand's document the owner names. Adoption work-list lines warn; every other hit fails.
4. With `--page`, run the page check on that page instead of the gates (steps 2 and 3 run only if the owner also asked for
   them or gave old values). The page is one of three things:
   - a page of the project (a path inside it): `brand-creator --data "${CLAUDE_PLUGIN_DATA}" page-check --project <dir> <page>`;
   - a page of a built site outside the project: `... page-check --project <dir> --from <site folder> <page>`, the page
     written relative to the site folder. That is the folder the page's links start from (often `dist` or `build`); ask the
     owner when it is not clear. It is copied and the copy opened, so the site is only read;
   - a page the owner's computer serves: `... page-check --project <dir> --url <address>`. Only `localhost`,
     `127.0.0.1` and `[::1]` are accepted. For any other address, say the page is not checked and offer to build it
     locally and give its folder.

   Add `--widths` or `--schemes` when the owner asks for fewer. Report the rows as in step 5, with the exit code as
   there. Report the `tell:` rows as warnings (generic patterns, never failures) and the `page:samples` row apart, as
   the owner's before-publishing list. Only when the owner asks to hold their pages to a warning, add a `page.rules`
   entry of kind `tell` to `qa/rules.json` (`tell` the tell's id, `g4` the words of a system rule; the kinds are in
   [07-tokens](../brand-creator/references/phases/07-tokens.md)): it fails a page only once that system rule is
   approved.
5. Reply in this order: the exit code and what it means (0 pass, 1 a gate failed, 2 usage, 3 cannot run); each failing
   row with its file and the fix the message names; warnings; rows "not verified" with the reason. Never report a row
   that did not run as passed.
6. Fix nothing unasked. Offer the fixes as one list: those that need no decision first, then numbered decisions with a
   recommendation. A fix goes into a source (a token, a chapter, a generator), never into an output.
