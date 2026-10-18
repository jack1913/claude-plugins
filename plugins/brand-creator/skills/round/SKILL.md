---
name: round
description: Builds the next board round of the current brand project. Copies the previous round, fills the round page, lints it, shoots it in four views, publishes the stable review page and stops at the gate.
argument-hint: "[pick|refine] [what this round should answer]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Next round

Thin wrapper over the orchestrator's "Round mechanics". Arguments: `$ARGUMENTS` (board kind and the question this
round answers; infer both from BRAND-STATE.md when empty).

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/SKILL.md` (Round mechanics, Gates, Response template) and
   `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/board-contract.md`. Then the phase file for where the
   project is: `references/phases/03-strategy-directions.md` (round 1 or a reset), `04-selection.md`, or
   `05-refinement.md`.
2. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`.
   Read BRAND-STATE.md, brief/BRIEF.md and FACTS.md fully. No project → say so and offer `/brand-creator:new`.
3. Next round number N = highest `rounds/rK/` + 1. From round 2: `cp -R rounds/r<N-1> rounds/r<N>` first; never edit
   an earlier round.
4. Build `rounds/r<N>/board.html` from `${CLAUDE_PLUGIN_ROOT}/templates/round-page.html` (`data-board="pick"` in
   round 1 and after a full rejection, else `refine`); deep boards per direction from `templates/board.html`.
   Delete optional blocks that do not apply; fill every `[[fill: ...]]`.
5. Lint until exit 0: `... board-lint rounds/r<N>/board.html --project <dir>`.
6. Shoot: `... shot rounds/r<N>/board.html --project <dir>`; Read every slice listed in `assets/_checks/shot.json`
   and fix what you see. Iterate at least twice. Exit 3 (no Chromium yet): carry on, and say the shots are not verified.
7. Regenerate `review/index.html` from `${CLAUDE_PLUGIN_ROOT}/templates/review/index.html` with this round's
   sections, lint it (`board-lint review/index.html --round <N>`), and publish it on the review surface (same
   Artifact URL as `review_url`, or open the local file). Record `review_url` with `state --set`.
8. Update BRAND-STATE.md (phase, Directions table, Still open), then reply with the response template and stop at the
   gate. Do not start the next round in the same turn.
