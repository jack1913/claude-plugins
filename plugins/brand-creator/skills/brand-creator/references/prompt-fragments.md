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
LANGUAGE RULES: <paste the output of `brand-creator fontcheck --print-rules --project <dir>`>  ← the typography rules of every content language
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
- Follow the LANGUAGE RULES of every content language in all text you set (for example Polish: a no-break space after
  a one-letter word, quotation marks that open low); `book-lint` warns when text breaks them.
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
- A motion round (`data-board="motion"`): run `brand-creator shot --motion rounds/r<N>/<variant>/proof.json` on each
  variant's proof and give its exit code and failing rows; Read each variant's `strip.png` and `reduced.png` before saying
  what moves; check that each card's proof line says what its report says and that `board-lint` passes its `motion:*` rows.
- A cold review of a site hero reads only the four stills of the variant, `brief/BRIEF.md` and `FACTS.md`, never the
  board, the references or the reasons. It may also be given the approved G4 rules as text in the prompt (the output of
  `brand-creator state --part g4-rules`: the G4 record and the recorded rule lines, never the rest of `BRAND-STATE.md`);
  its `inputs:` list then ends with `- BRAND-STATE.md#g4-rules sha256:<hex>`, the first line of that output. For a page that
  animates when it loads it may also be given the three key frames of the first screen (`shots/frame-1440-0.png`, `-50` and `-100`:
  the start, the middle and the end of the longest animation that runs on load, each listed in `inputs:`); it reads the motion
  from them (does the entrance carry the idea, does anything stay on screen after it ends) and does not guess it from the end
  stills. It writes
  `rounds/r<N>/<name>/cold-review.md`: `verdict: ship` or `verdict: fix`
  first, a `by:` line (`by: in-thread`; in-thread it is not blind, and an agent only after the fleet gate), an `inputs:`
  list with the sha256 of each file (`- <path> sha256:<hex>`), then up to five numbered findings, the one that costs the
  visitor most first, each short enough to sit on a single line. The findings ask: does the first screen say what only
  this brand could say; does it serve the visitor's job in BRIEF and put the job's own action in reach; does any part
  read as one of the generic tells (an eyebrow over a heading; an arrow glued to a link or button label; a run of middle
  dots between items; a stock label on the hero's second action; a hero that carries too much text; a product mock-up made
  of styled boxes; three equal tiles in a row); does every number and status word match FACTS or sit in a labelled sample.
  With the G4 rules in the prompt it also asks whether anything on the page breaks one, and a page that does what a rule
  says (a dark still that equals the light one, when a rule says so) is right, not a finding.
  A review judges what the page shows: where the page lacks something it would need (wording, a picture, a control), the
  finding notes that the owner would have to supply it, and does not fault the page for leaving it out.

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

- Write in the brand's content languages and keep their LANGUAGE RULES (`brand-creator fontcheck --print-rules --project <dir>`
  prints them); `book-lint` warns, with line and offset, where text breaks one.
- Offer 2-4 concrete text options with a Recommended one; never ask an open question about wording.
- Only facts from VERIFIED FACTS; never invent clients, team size, years of experience, awards, numbers, dates,
  release dates or features.
