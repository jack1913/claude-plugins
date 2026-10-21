---
name: round
description: Builds the next round of boards for the current brand project, starting with the style board before anything is drawn, then the boards of directions and refinements. It checks the board, takes screenshots in four views, publishes the review page and stops for the owner's decision. Runs only when typed as /brand-creator:round.
argument-hint: "[style|pick|refine] [what this round should answer]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Next round

Thin wrapper over the orchestrator's "Round mechanics". Arguments: `$ARGUMENTS` (board kind and the question this
round answers; infer both from BRAND-STATE.md when empty). Kinds: `style` (round 0, the style research before anything
is drawn), `pick` (round 1 and after a full rejection) and `refine`.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/SKILL.md` (Round mechanics, Gates, Response template) and
   `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/board-contract.md`. Then the phase file for where the
   project is: `references/phases/01s-style-research.md` (round 0, the style board),
   `references/phases/03-strategy-directions.md` (round 1 or a reset), `04-selection.md`, or `05-refinement.md`.
2. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`.
   Read BRAND-STATE.md, brief/BRIEF.md and FACTS.md fully. No project → say so and offer `/brand-creator:new`.
3. Pick the round number N. The style board is round 0 (`rounds/r0/`): it comes first, while G1s is not recorded, even in
   a project that already has rounds (the hook keeps `rounds/r0/` writable while G1s is empty). Every other round is the
   highest `rounds/rK/` + 1. From round 2: `cp -R rounds/r<N-1> rounds/r<N>` first; never edit an earlier round.
4. Check the gate before drawing anything. Before a round 1 board, or the pick board of a reset round, run
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project <dir> --require G1s`. Exit 1 means the owner has
   not picked a style yet: build the style board instead (round 0), or after a full rejection a new style board in the next
   round (listed in `reset_rounds`), and stop there. Never draw a direction first. A project that was already past round 1
   when this step arrived records `state --record G1s "n/a: round 1 drawn before the style step"`, or runs the style
   research as round 0 now. After a full rejection the old pick no longer counts, and `--require G1s` still exits 0 with it:
   the pick board of a reset round needs a new style board in an earlier reset round (no skip: "skipped by owner" is for the
   first pick board only) and the owner's new pick recorded after it, or `board-lint` fails the board.
5. Build `rounds/r<N>/board.html`: round 0 (and a reset round's style research) from
   `${CLAUDE_PLUGIN_ROOT}/templates/style-board.html` (`data-board="style"`); otherwise from
   `${CLAUDE_PLUGIN_ROOT}/templates/round-page.html` (`data-board="pick"` in round 1 and after a full rejection, else
   `refine`); deep boards per direction from `templates/board.html`. Delete optional blocks that do not apply; fill every
   `[[fill: ...]]`. The style research needs web access: without web tools say so and stop, and never invent references.
   Marks that need drawing are drawn before the board shows them, on a drawing engine, never silently by you:
   `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/drawing-engines.md` (the style board needs none).
6. Lint until exit 0: `... board-lint rounds/r<N>/board.html --project <dir>`.
7. Shoot: `... shot rounds/r<N>/board.html --project <dir>`; Read every slice listed in `assets/_checks/shot.json`
   and fix what you see. Iterate at least twice. Exit 3 (no Chromium yet): carry on, and say the shots are not verified.
8. Regenerate `review/index.html` and publish it on the review surface (same Artifact URL as `review_url`, or open the
   local file). Rounds 1 and later: from `${CLAUDE_PLUGIN_ROOT}/templates/review/index.html` with this round's sections.
   Round 0, and a reset round's style board: copy the style board (`cp rounds/r<N>/board.html review/index.html`). Lint
   it either way (`board-lint review/index.html --round <N>`). Upload only after the owner's yes: with `review_surface`
   still `auto`, ask the one upload question first and use the local file until it is answered (the orchestrator's
   Review surface). Record `review_url` with `state --set`.
9. Update BRAND-STATE.md (phase, Directions table, Still open), then reply with the response template and stop at the
   gate. Do not start the next round in the same turn. After the owner answers the style board, restate the pick and
   record it with `state --record G1s "<decision>"` before the next pick board (round 1, or the pick board of a reset round).
