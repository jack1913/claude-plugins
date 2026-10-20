---
name: brand-adopt
description: Finds every place an approved brand belongs in the owner's product repositories (read only) and, only when the owner asks, applies it on a branch the owner names, one repository at a time, with an independent review before any commit. Typing it surveys and applies in this session; the adopt workflow does only the apply step, with one agent per repository, after the owner approves the agent count and cost. Runs only when typed as /brand-creator:brand-adopt.
argument-hint: "[survey|apply|review|status] [repository label]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Brand adoption

Thin wrapper: the method is [11-adoption](../brand-creator/references/phases/11-adoption.md) and the commands are in
`scripts/CONTRACT.md` ("Adoption, cascade, adapters, applied skill and launch"). Arguments: `$ARGUMENTS` (what to do and
for which repository; with none, show the status and the next step).

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

## 1. Before anything

1. Read [11-adoption](../brand-creator/references/phases/11-adoption.md) and the G5, G6 and Fleet gate lines of the
   [orchestrator](../brand-creator/SKILL.md) fully.
2. `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. No project → say so and stop. G5 not recorded →
   the pack is not approved: say so and stop.
3. The repositories come from `INVENTORY.md` (deployment targets) or the owner. Ask for the paths you cannot find; never
   search the disk for them.

## 2. Survey (read only, no gate)

1. `brand-creator --data "${CLAUDE_PLUGIN_DATA}" adoption survey --project <dir> --repo <path>=<label> --old-name "<Old>" --old-colour "#rrggbb"`
   for every repository at once. The survey reads the whole repository; every match becomes a row or goes on "Kept,
   not counted" with its reason, and the report proves nothing in the repository changed.
2. Add what no search finds, one row each: `adoption add --repo <label> --file <path> --find "<text>" --change "<sentence>"`
   (a platform rule the repository gets wrong, an icon picked at runtime, a size that drifted from the platform's page:
   the pack follows the platform, the drift becomes a row).
3. Show ADOPTION.md's counts and groups, and the rows that act on live services (step 5). Stop. Nothing is applied
   because a list exists.

## 3. Apply (only after the owner's explicit ask)

1. The owner asks for a named repository (or all) to be applied. Ask which branch: the owner names it. Suggest one
   (`brand/<slug>-<date>`) and wait; never work on the default branch or on a branch you picked silently.
2. Record the ask: `state --record G6 "<what the owner asked, which repositories, which branch>"`.
3. One implementer per repository, in sequence: you, single-thread, by default. A subagent per repository only after the
   fleet gate (agent count, the models that will run, a rough cost, an explicit yes); never two implementers in one
   working tree. Every prompt carries the RULES line verbatim.
4. The implementer: create the owner's branch; work row by row, finding each place **by its content** (the Find
   column), never by the line number; a row whose text is gone is reported "not done", never guessed. Files from the
   pack are copied, never redrawn or re-exported. `adoption status --set <rows>=doing` as rows are made.
5. Never pass `--no-verify` or any other hook skip. A hook that fails for an unrelated reason is reported; fixing it is a
   separate change, made only if the owner agrees.

## 4. Independent review (before any commit)

A fresh pass that did not do the implementation (you after re-reading the diff, or a separate reviewer after the fleet
gate). It writes nothing; it reports.

- `cmp` every file copied from the pack against the pack's file; any difference fails the row.
- Size-check the copied lockups and icons in the target (dimensions, the platform's slot).
- Run the repository's own build and tests (from its README, package scripts, Makefile or CI config), and quote the
  commands and their exit codes. Build and run the product to see the real icon where the platform allows it; read the
  shot. A check that needs a real device is listed "not verified".
- Every row: done, partly done or not done, with the evidence.

Then a fix pass for the findings that need no decision, the review again, and only then the numbered "Decisions for
you", each with a recommendation.

## 5. Commit, merge, push, live services

- Commit, merge and push are three separate asks. After a commit the owner asked for, `adoption status --set <rows>=done`.
- Before a push the owner asked for, read the target's CI, deploy and publish configuration and say what the push
  triggers (CI, a deploy, a package or store publish) and anything irreversible. Never call a push safe without having
  read that configuration.
- Rows that act on a live service (renaming a repository, a hosted service or an app id, an upload, a DNS change, a store
  listing) each need their own OK, separate from the apply ask. Most are owner steps listed in LAUNCH.md
  (`/brand-creator:launch`).

## 6. A parent site that shows the product

- Lockups and icons are the product's own pack files, copied byte for byte (`cmp`). A product without a pack gets no
  placeholder: it is listed as missing.
- Preview the variants in a scratch copy of the site first (copy it to scratch, build, shoot, read the shots) and show
  them; the site's source is touched only after the owner picks.
- Propose, do not add unasked, a build check in the site that fails on a missing lockup, a size mismatch, a wrong embed
  or a lockup that is never shown.

Reply with the [response template](../brand-creator/SKILL.md#response-template-every-reply-at-a-gate-or-after-a-round).
After the work, `check --cascade "<old name>"` says what is left.

## The adopt workflow (opt-in, after G6)

With the fleet's yes, the apply and the independent review can run as the `adopt` workflow: per repository one
`brand-creator:brand-implementer` on the owner's branch, then one `brand-creator:brand-reviewer` (`cmp` against the
pack, the repository's own build and tests). Repositories go one at a time unless `parallel_repos: true` and each is
its own working tree; 2 agents per repository. It needs the G6 record in its arguments, never commits, and returns the
rows with evidence; a second run with `mode: "fix"` takes only the no-decision findings. State the numbers from
`brand-creator --data "${CLAUDE_PLUGIN_DATA}" fleet-plan adopt --args @<file> --session-model <your model>` first.
Details: [fleet.md](../brand-creator/references/fleet.md).
