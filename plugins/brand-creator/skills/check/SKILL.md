---
name: check
description: Runs every check that applies to the current brand project (boards, contrast, logo sheet, files, book, print, adoption and the history record) and, given old names or colours, searches the whole project for leftovers. With --page, checks a page built anywhere against the brand instead. Reports each failing row with its fix. Runs only when typed as /brand-creator:check.
argument-hint: "[--page <file-or-folder-page-or-localhost-url>] [--review [board|book|pack|all] [panel]] [--panel] [<old value or phrase> ...]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Check

Thin wrapper over `brand-creator check` and `brand-creator page-check`; what each row means is in
[09-qa](../brand-creator/references/phases/09-qa.md) and the cascade method in
[cascade](../brand-creator/references/cascade.md). Arguments: `$ARGUMENTS` (`--page` and the page to check; `--review`
and what to review, or `--panel`, which is `--review panel`; then old values or phrases that must be gone; empty → the
gates only). `--review` is the judgement review of the latest work, below.

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

1. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. None → say so and offer to
   start one (the owner says what the brand is for, in words).
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

## Review (`--review`)

`--review [board|book|pack|all]`: what to review (empty → the latest work the phase in BRAND-STATE.md points at).
`panel` after it, or `--panel` alone, also offers the lens panel. The review runs the gates itself (Self-review, step 2)
and presents the findings as one list; it is not the gates-only report of steps 2 to 6 above.

### Self-review (always)

1. `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`; read BRAND-STATE.md, brief/BRIEF.md and FACTS.md.
2. Run the checks first and quote their results: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" check --project <dir>`,
   plus `board-lint` for a board and `book-lint --self-consistency` for the book. Then `shot` the page and Read every
   slice (1440 and 390, light and dark).
3. Read the work against its list:
   - a board: [board-contract](../brand-creator/references/board-contract.md), the reflex list
     ([ai-defaults](../brand-creator/references/ai-defaults.json)) and [anti-patterns](../brand-creator/references/anti-patterns.md);
   - the book: the self-review table of the [brand-book skill](../brand-book/SKILL.md#self-review);
   - packs: [09-qa](../brand-creator/references/phases/09-qa.md) and the downscale proof.
4. Challenge every finding before listing it: verify it yourself, and drop anything wrong, cosmetic without benefit, or
   against an owner decision or the approved rules. Measured numbers instead of adjectives; judgement said as such.
5. Present one list: fixes that need no decision (with the file), numbered "Decisions for you" each with a
   recommendation, and up to five strengths that must not change. The owner approves the list; nothing is fixed before.

### Lens panel (optional)

Each lens reads the same work for one concern and returns findings as `{id, severity, where, evidence, why for this
brand, change, effort S/M/L}`: design, content (FACTS.md only, the tone rules), technical (files, sizes, checks) and,
when they apply, legal or regulatory, platform, accessibility. A judge pass then challenges every finding and sorts the
survivors into A (before launch), B (soon) and C (optional), plus the owner-only decisions with a recommendation.
Lenses read; they never edit.

- Default: single-thread. You run each lens in turn, then the judge pass, in this session.
- A fleet (one read-only subagent per lens, then one judge) only after the fleet gate of the
  [orchestrator](../brand-creator/SKILL.md): state the agent count, the models that will actually run (the session model
  is a ceiling), the size guideline (a cross-check is 2 to 4 agents) and a rough cost, and launch only after an explicit
  yes. Every prompt carries the RULES line and the CONTEXT paths of
  [prompt-fragments](../brand-creator/references/prompt-fragments.md).
- Panels advise. Show the judge's view, your own view and a middle option where they differ; the owner decides.

### Lens panel as a workflow

With the fleet's yes, the panel runs as the `review-panel` workflow: one `brand-creator:brand-reviewer` per lens (they
run checks and never edit), then one `brand-creator:brand-judge`; default design, content and technical plus the judge,
4 agents. Before proposing it, run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" fleet-plan review-panel --args @<file>
--session-model <your model>` and state its numbers. Do not edit the work under review while the panel runs. The
result is advice: show it as the one approvable list above. Details: [fleet.md](../brand-creator/references/fleet.md).
