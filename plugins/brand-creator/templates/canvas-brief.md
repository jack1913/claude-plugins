# Round [[fill: N]] drawing brief: [[fill: the items to draw, for example "the three marks of the family" or "the one mark"]]

For the session that draws round [[fill: N]] on [[fill: the engine: the use-llm design canvas | Claude Code /design | Claude-drawn SVG, with the owner's yes of YYYY-MM-DD]]. Read `BRAND-STATE.md` first, then `brief/BRIEF.md` and `FACTS.md`.

<!-- Authoring note, delete it before handing the brief over: save this file as brief/canvas-round-<N>.md in the brand project, fill every marker, delete a line that does not apply, and take nothing from another project. The drawing-engines reference of the brand-creator skill says what the brief must carry. -->

## Where to start and where to write

- [[fill: the use-llm design canvas only, else delete this line: start this session in the brand project folder. The canvas is written to `<cwd>/.design/<slug>/`, and a session started in another repository puts it there, untracked.]]
- [[fill: from round 2, else delete this line: the round folder starts as a copy of the previous round. If `rounds/r<N>/` is not there yet, run `cp -R rounds/r<N-1> rounds/r<N>` first, with the two round numbers, and write into that copy. A direction's new `SOURCE.md` replaces the copied one, and the previous round itself is never written to.]]
- Write the round's files only inside `rounds/r[[fill: N]]/`, one folder per direction: `rounds/r[[fill: N]]/[[fill: direction folder]]/` for each of [[fill: the direction folders]]. The canvas keeps its own files in `.design/`. Touch nothing else in the project: not `assets/`, not an earlier round, not `history/`, not `BRAND-STATE.md`.
- Drafts, and every file you hand over, go in the project, never in your session's scratch folder: `rounds/r[[fill: N]]/drafts/` while this round is open, `assets/logo/drafts/` once it is approved (G3) and frozen.
- Use the engine named above and no other. If it fails, or cannot do something this brief asks, say so and stop; do not draw another way.

## The owner's picks ([[fill: date]])

- Styles: [[fill: the territories picked on the style board, and the path of that board]].
- [[fill: one shared style for all the items (same hand, line weight and palette rules, each item with its own subject and colour) | one style per item]].
- [[fill: what the owner rejected, in their words, and what not to draw again]].

## Round [[fill: N]]: [[fill: a pick board with K directions | a refine round that answers ...]]

[[fill: say in one line whether this is a reset round (listed in reset_rounds) and what the round answers]] Direction names are fixed; use them on the canvas, on the board and in chat.

| Direction | What it is | [[fill: item 1]] | [[fill: item 2]] | [[fill: item 3]] |
|---|---|---|---|---|
| **[[fill: direction word name]]** | [[fill: the style in one line]] | [[fill: the subject]] | [[fill: the subject]] | [[fill: the subject]] |

Watch out:

- [[fill: one line per direction: how it usually goes wrong, and what to draw instead]]

## Rules for every direction

- Draw at real size first: [[fill: the items side by side at 16 px on the grounds that matter, with their colours]]. Then 32, 128 and 512.
- Footprint at 16 px: [[fill: the target footprint, for example fill about 14-16 px wide and 12 px or more tall on a 16 grid]]. A mark that fills less is redrawn, not shipped small.
- Each mark needs one clear silhouette at 16 px, and the [[fill: items]] must be told apart there. Look for readings you did not mean: a symmetric shape with flared ends can read as wings, and tabs along the top as a crown.
- Colours: [[fill: which colour goes to which item, and the colours each direction may use, each with its hex value]].
- On a dark background: [[fill: the rule for the mark: invert | a 1 px keyline in the light colour | a separate dark version]]. Look at the 16 px mark on the dark ground before you keep it: inverting a black-and-cream mark once turned a thin strap into a cream slab, and a 1 px cream ring fixed it.
- Larger grids: [[fill: pixel marks only, else delete this line: redraw the 32 grid, never upscale the 16 grid]].
- Screen before drawing: [[fill: the references that need screening before drawing starts: other companies' marks, platform marks, characters]]. Screening, not clearance: say what you found and what you changed, and the owner decides.
- Avoid: [[fill: the FORBIDDEN items of brief/BRIEF.md, the never-borrow list, and what the owner asked you to avoid]].

## How to draw

- Engine: [[fill: the engine, and in one line how this session reaches it]].
- Method: [[fill: one line per direction: for hand-placed pixels, place the pixels by hand on a visible grid at 16 x 16 and 32 x 32; for a cut or drawn style, explore with generated images, then redraw the kept ones as clean one-ink vectors]].
- Options: [[fill: how many options per item, for example three]]. The owner looks at [[fill: the canvas | the artboard]] and comments there, or sends screenshots in chat. Then keep one option per item per direction, and say which you would pick and why.
- Option IDs: give every option an ID that names its board, the item and the number (for example `family1-bc-3`: board family1, brand-creator, option 3), and use it on the canvas, in chat and in `SOURCE.md`. A bare "the 3" means two different options once there are two boards.
- Gate answers belong to the lead session: when the owner picks, approves or rejects something here, say so and ask them to give that answer in the lead session. Never record a gate yourself.
- Tracing a generated image: threshold, trim and pad it to a square first (a paper or mat edge becomes a speck), then `magick in.png -colorspace Gray -threshold 50% pbm:- | potrace -s -o out.svg -`. Add `-t 60` to drop specks (turdsize 60 worked). Then fix the curves by hand. Never ship a raw generated image or an untraced bitmap as the mark.
- Image budget: [[fill: only on an engine that generates images, such as the use-llm design canvas, else delete this line: at most N images and $X in all]], in batches of at most 9. Generate none until the owner has agreed to this budget. Say the cost in each reply and keep your own running tally: the canvas reports the cost per call only. At the cap, stop and ask.
- Agent budget: [[fill: only when agents draw, else delete this line: at most N agents and about T tokens per run]]. Ask before going over it, and write each run's agents, models and tokens in `SOURCE.md`.

## What lands in the brand project

`.design/` keeps the canvas. The round itself goes in `rounds/r[[fill: N]]/`:

- `rounds/r[[fill: N]]/<direction>/<item>.svg`: the master, pure vector, with a square viewBox and no live text. A pixel mark is crisp rects with `shape-rendering="crispEdges"`. Next to it, `<item>-16.png`, `<item>-32.png` and `<item>-128.png`, exported from the SVG (a pixel mark only at whole-number scales).
- `rounds/r[[fill: N]]/<direction>/SOURCE.md`: the engine, where the canvas or artboard is, the prompts, the image model, the image count and cost, the trace settings, what was fixed by hand, the lineage of each kept mark (option ID, redraws, fixes, file), the agents and tokens of each run, the date.
- Raw generated images stay on the canvas or in the round as exploration, never as the mark.

You draw; you do not build the board. [[fill: who builds rounds/rN/board.html from your files, lints it, shoots it and reads every slice: the brand-creator lead session, or this session when it runs brand-creator]].

Finish with: the files you wrote, the number of images and the total cost, which option you would pick for each item and why, and anything you could not do.

## Rules

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.
