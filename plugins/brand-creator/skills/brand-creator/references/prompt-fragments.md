# Prompt fragments

The skeleton every designer, judge or reviewer pass uses: in single-thread as your own checklist, in a fleet as the
agent prompt. Fill the angle brackets; keep the RULES and TEST lines verbatim.

## Contents

- [Skeleton](#skeleton)
- [Fragments by purpose](#fragments-by-purpose)

## Skeleton

```
CONTEXT: <absolute paths to READ FULLY: BRAND-STATE.md, brief/BRIEF.md, FACTS.md, the approved board, history/>
DECISIONS ALREADY MADE BY THE OWNER: (1) ... (2) ...        ← numbered, the owner's words paraphrased closely
CRITIQUE ITEMS (fix these): (a) ... (b) ...                 ← lettered, from the last review
FAMILY LAYER (keep) / COMPANY LAYER (own) / FORBIDDEN: ...  ← FORBIDDEN = research/cliches.md + BRIEF Forbidden + never-borrow
VERIFIED FACTS YOU MAY USE: <FACTS.md rows>                 ← nothing else may be claimed
HARD CONSTRAINTS: static first; reduced motion = nothing moves; nothing loops forever; light and dark via tokens;
  at most 2 self-hostable fonts with a licence that allows embedding; the audience's glyph set verified (say how);
  real content only; the gating goal from BRIEF.
YOUR DIRECTION: <one paragraph: the territory, its register, its named visual philosophy>
DELIVERABLE: one self-contained board.html from <template path> (fonts inline, ?v=N, ?t=light|dark, replay control
  when anything moves); per variant: what it is, its cost, its degrade path; Weak points; an honest ranked
  recommendation that includes "keep today's" when an incumbent exists.
TEST: screenshot 1440×900 light+dark and 390×844, Read every tile, iterate at least twice; print one-line check (overflow, errors, requests, non-whole images).
RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.
OUTPUT: <schema or file list>. Aim to finish within <time box>; keep turns short; tail-limit command output.
```

In this plugin the TEST line runs as `brand-creator shot <page> --project <dir>` followed by reading every slice the
report lists.

## Fragments by purpose

Generalised from prompts that worked; use them as written or close to it.

**Research**

- Cite primary sources; write UNVERIFIED next to any claim whose primary source you could not find.
- Re-fetch the cited primary source and try to refute the claim; drop or correct claims that fail.
- Read only: do not register, buy, contact anyone or create accounts.

**Design**

- Judge the mark at 16 px first; iterate at least three times.
- The icon must survive the platform's own downscale: design the large master, then show real downscales at the
  sizes the platform uses.
- Avoid patchwork: if two visual languages appear together, say exactly what role each plays and why they read as
  one system.
- Include "0 Today" and say honestly whether today's mark is still better; include a "None of these" option.

**Judge**

- Rank the directions, say which one you would take forward and what you would graft from the others.
- Score this round against the previous round and the best so far on the same rubric; return a numbered MUST-FIX
  list and an optional NICE list.
- Be honest: if something is fine, say so; do not invent problems to fill the list.

**Review**

- Say plainly whether each numbered change is done, partly done or not done.
- If you disagree with a point, say why instead of applying it.
- Challenge each finding: verify the important ones yourself; reject anything wrong, cosmetic without real benefit,
  or in conflict with the approved guide or the owner's decisions.
- Split findings into fixes that need no decision and a numbered "Decisions for you" list with a recommendation each.

**Implementation and safety**

- The output must not change unless asked: record a hash of every shipped file before; after the change, rebuild
  and prove every hash is identical.
- Line numbers from an earlier read may have drifted: find each spot by its content; if a row's text is not there,
  do not guess, report it as not done.
- Prove a new check with mutations in scratch copies: each mutation must apply and then fail the gate with a clear
  message; the clean project passes.
- Resuming after an interruption: do not start over blindly and do not assume the previous work is right; read it,
  verify it, keep what is correct, finish the rest.

**Copy**

- Offer 2-4 concrete text options with a Recommended one; never ask an open question about wording.
- Only facts from VERIFIED FACTS; never invent clients, team size, years of experience, awards, numbers, dates,
  release dates or features.
