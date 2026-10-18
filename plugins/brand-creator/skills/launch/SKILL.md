---
name: launch
description: Writes the owner's launch checklist (LAUNCH.md, trademark first, then domains, handles, e-mail, deploy, renames and the print hand-off) from local files and hands it over one action at a time, with the reason and the click path. The owner acts; nothing outward is ever done for them.
argument-hint: "[--name <candidate>]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Launch

Thin wrapper over `brand-creator launch-todo`; the method is [13-launch](../brand-creator/references/phases/13-launch.md).
Arguments: `$ARGUMENTS` (the candidate name when the names run screened several).

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

1. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. None → say so and stop.
2. No name screening on file (`assets/_checks/names.json`) → say that the domain and handle rows will be UNKNOWN, and
   offer the names run first (it needs the owner's privacy OK; see the brand-naming skill).
3. `brand-creator --data "${CLAUDE_PLUGIN_DATA}" launch-todo --project <dir> $ARGUMENTS`, then read LAUNCH.md fully.
4. Hand over **one action**: the first unticked box in file order (trademark comes first; nothing is bought before its
   answer). Give the reason in one sentence, the exact click path (the page to open, what to type, which button), what
   it costs when that is known, and what to tell you afterwards. Then stop and wait.
5. When the owner reports back, record it: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project <dir> --record G7 "<what the owner did, and when>"`.
   The owner ticks the box (ticks survive a regeneration), then the next action.
6. "Buy it for me", "file it", "register the handle", "send the e-mail": answer with the hand-off, never the act. You
   never open a registrar's checkout, a filing form or a sign-up page on the owner's behalf.
7. Every state in the file is a reading of one source on one day (REGISTERED, NOT-FOUND or UNKNOWN). Never say a name
   is available, free or clear. Older than a few days before a purchase or a filing → say "recheck first" and offer to
   run the screening again.
