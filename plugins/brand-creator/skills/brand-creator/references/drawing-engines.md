# Drawing engines

Where a round's marks are drawn and shown to the owner. Use the first engine that is there: the canvas, else /design,
else Claude-drawn SVG. The canvas is the use-llm design canvas, /design is Claude Code's own, and Claude-drawn SVG is an
explicit, weaker choice that needs the owner's yes. Never switch engines silently. The style board (round 0) needs no
engine: it shows references, not drawn marks.

## Contents

- [When a round needs marks drawn](#when-a-round-needs-marks-drawn)
- [Which engine this session has](#which-engine-this-session-has)
- [The order, and the explicit yes](#the-order-and-the-explicit-yes)
- [Write the brief](#write-the-brief)
- [What lands in the round](#what-lands-in-the-round)
- [Warnings for the drawing step](#warnings-for-the-drawing-step)
- [Known quirks of the use-llm design canvas (as of 2026-10-20)](#known-quirks-of-the-use-llm-design-canvas-as-of-2026-10-20)

## When a round needs marks drawn

- The pick board of round 1 and of a reset round: one mark per direction.
- A refine round that redraws a mark instead of editing its SVG ([05-refinement](phases/05-refinement.md)).
- The mark phase, when a small size needs its own drawing ([06-mark](phases/06-mark.md)).

Not needed: the style board, a wordmark that is only type set in a font and outlined (`outline-glyphs`), the owner's
existing mark (audit it), or an edit of an SVG master (edit the SVG).

The mark source (`generated`, `authored-vector`, `existing`) says how the master is made and kept; it does not choose the
engine. A mark drawn as code geometry is Claude-drawn SVG too, and a real round 1 drawn that way was rejected outright.
Placing pixels by hand on a grid is drawing too: the engine is where the drawing is made and shown, not who places the
pixels.

## Which engine this session has

Look at the session before anything is drawn, and tell the owner the result in one line.

1. **The use-llm design canvas.** Available only in a Claude Code session launched through use-llm (for example
   `use-claude`). Such a session has the design MCP tools: `design_guide`, `design_seed`, `dc_write`, `generate_image`,
   `show_to_user`, `save_screenshot` and related. Test: look for `design_guide` among your tools, or search for
   `design_guide` with ToolSearch when tools are deferred; found means this session has the canvas.
   - Canvases are written to `<cwd>/.design/<slug>/`, so the drawing session must start in the brand project folder. A
     session started in another repo put the canvas there, untracked. Check the working folder before the first canvas
     write; if it is not the project folder, stop and tell the owner. A canvas that landed elsewhere moves, with the owner's
     OK, as the whole `.design/<slug>/` folder, name unchanged, into the brand project's `.design/`: the canvas tool works
     from `<cwd>/.design/`, and a canvas moved anywhere else (a first move into `research/` was one) is out of its reach.
   - Generated images run through OpenRouter and cost money. One measured run on 2026-10-20 with Gemini 3 Pro Image cost
     about $0.135 per image (9 images $1.21).
   - The owner looks at the canvas. Feedback may come as screenshots in chat rather than canvas comments: read each one
     and name what you see first.
2. **Claude Code's /design.** Built into Claude Code 2.1.234 and later, for a claude.ai login on a Pro, Max, Team or
   Enterprise plan. It brings Claude Design's artboard workflow into the CLI and publishes an editable artboard as a
   claude.ai artifact. Claude cannot start /design: the owner types `/design` followed by the brief. Write the brief file
   and tell the owner the exact line to type. Its docs do not mention image generation: do not claim it generates images.
   Read the Claude Code version with `claude --version` and the sign-in with `claude auth status`; ask the owner for the
   plan when it does not show.
3. **Claude-drawn SVG.** The marks drawn as SVG by hand, by you. Not an engine to reach for: see the next section.

A session without the design tools can still reach the canvas: the owner starts a use-llm session in the brand project
folder (the canvas, in another session). So when this session has neither tool, offer that and /design (when the version
has it) before the weaker choice, and hand over the brief for the one the owner picks (see Write the brief).

## The order, and the explicit yes

Use the first one that is there: 1, else 2, else 3. If the owner names an engine, use that one. The first time an engine
is used, write it on the `Drawing engine:` line of the Collaboration block in BRAND-STATE.md.

Claude-drawn SVG is an explicit, weaker choice, and only on the owner's yes:

1. Only when neither engine above is available, say what is missing and how to get each: the canvas needs a Claude Code
   session launched through use-llm and started in the brand project folder; /design needs Claude Code 2.1.234 or later
   and a claude.ai login on a Pro, Max, Team or Enterprise plan, and the owner types it.
2. Then offer drawing the marks as SVG by hand, as a weaker choice: marks drawn this way tend to look generic, and a real
   round 1 drawn as code geometry was rejected outright. Say it in words like these, in the usual "Your call" form, with
   setting up an engine marked (Recommended) so a bare "ok" never counts as the yes:

   > I can't draw these marks on a design engine from here. Missing: a Claude Code session launched through use-llm in
   > this folder (it gives me the design canvas), or Claude Code 2.1.234 or later with a claude.ai login on a Pro, Max,
   > Team or Enterprise plan (you type /design; I can't). The weaker choice is that I draw the marks as SVG myself. They
   > tend to look generic, and a round drawn as code geometry was rejected outright before. Do you want me to draw them
   > as SVG? (a) No, I wait while you set up an engine (Recommended). (b) Yes, draw them as SVG.

3. Only on the owner's yes, record it as a line in BRAND-STATE.md's Collaboration block:
   `- Drawing engine: Claude-drawn SVG (owner's yes, <date>)`. Without a yes, draw nothing; the line stays `not chosen yet`.
4. Never switch engines silently. If the engine in use fails mid-round (the canvas session ends, /design is not
   available), say so and ask again.

An owner who asks for Claude-drawn SVG up front still hears the warning once; the answer after it is the yes.

## Write the brief

Copy `${CLAUDE_PLUGIN_ROOT}/templates/canvas-brief.md` to `brief/canvas-round-<N>.md` in the project and fill every
`[[fill: ...]]` from BRAND-STATE.md, `brief/BRIEF.md`, FACTS.md, the style pick and the question of the round. Leave none,
and delete a line that does not apply. Take nothing from another project.

The brief must say, and the template has a slot for each:

1. the exact round folder to write to (`rounds/r<N>/<direction>/`), which from round 2 starts as a copy of the previous round
   (`cp -R rounds/r<N-1> rounds/r<N>` first when the folder is not there yet; a round drawn without the copy started with
   none of the previous round's files);
2. which colour goes to which item;
3. a target footprint at 16 px (for example fill about 14-16 px wide and 12 px or more tall on a 16 grid);
4. the dark-background rule for the mark: invert, a 1 px keyline in the light colour, or a separate dark version
   (inverting black and cream once turned a strap into a cream slab; a 1 px cream ring fixed it);
5. whether larger grids are redrawn or upscaled: redraw the 32 grid, never upscale;
6. references that need screening before drawing starts (other companies' marks, platform marks, characters): screening,
   not clearance;
7. the image budget: the most images and the most money, in batches of at most 9;
8. the agent budget, when agents draw: the most agents and tokens per run.

The template also carries fixed rules: option IDs that name their board (`family1-bc-3`, not "the 3"), gate answers given
only in the lead session, and drafts kept in the project (`rounds/r<N>/drafts/`, after G3 `assets/logo/drafts/`), never in
a session's scratch folder.

Then hand over, by engine:

- **The canvas, in this session.** Draw here, after the working-folder check above. Pixels and vector can start at once;
  generate no image until the owner agrees to the image budget (the count and the dollars).
- **The canvas, in another session.** The owner starts a Claude Code session through use-llm in the brand project folder
  and tells it: "Read brief/canvas-round-<N>.md first, then draw."
- **/design.** Tell the owner the exact line to type: `/design` followed by one sentence that names the brief, for example
  `/design Read brief/canvas-round-<N>.md and draw what it asks.` The owner can paste the brief's text after `/design`
  instead.

State the image budget (images and dollars) when you hand the brief over; it is a proposal until the owner agrees. Reply
in the response template and stop: the round waits for the drawing.

## What lands in the round

The marks the owner keeps come into `rounds/r<N>/<direction>/` as vector, and nothing else becomes a mark:

- `rounds/r<N>/<direction>/<item>.svg`: the pure-vector SVG master (traced with potrace or redrawn, curves fixed by hand;
  a pixel mark as SVG rects with `shape-rendering="crispEdges"`), with a square viewBox and no live text.
- `<item>-16.png`, `<item>-32.png` and `<item>-128.png`, exported from the SVG with resvg; a pixel mark only at
  whole-number scales.
- one `SOURCE.md` per direction, from `templates/SOURCE.md`: the engine, where the canvas or artboard is, the prompts, the
  image model, the image count and cost, the trace settings, what was fixed by hand, the lineage of each kept mark (option
  ID, redraws, fixes, file), the agents and tokens of each run, the date.

Raw generated images stay on the canvas or in the round as exploration, never as the mark. When the owner picks a
direction drawn this way, the mark source is `authored-vector`: drawn or traced, not generated by code.

Then the lead session builds the board from the masters (`templates/round-page.html`), runs `board-lint` and `shot`, and
reads every slice, as in the round mechanics of the orchestrator skill.

If the owner picks on the canvas before the board exists, record the pick in the owner's own words (G2 on a pick round),
then build the board anyway as the record of what was shown, saying on the page that it was filed after the pick. It goes
through `board-lint` and `shot` like any other board.

## Warnings for the drawing step

- Wide subjects (a belt with tools) become a thin bar at 16 px after tracing: crop or redraw for small sizes.
- At 16 px a symmetric subject with flared ends reads as wings or a bat, and tabs along the top read as a crown: look for
  readings you did not mean.
- A drawing fleet on the canvas (2 to 3 artist agents plus a judge, run by a drawing session; brand-creator has no such
  workflow) used 156k to 307k agent tokens per run, 1.2M over the five runs of one project. The brief sets an agent budget.
  If you propose a fleet, say so at the fleet gate, with the agent count, the models and the size.
- Render and look before accepting any judge's pixel fix. One applied literally made the mark worse.

## Known quirks of the use-llm design canvas (as of 2026-10-20)

Field notes from the session that drew a real round on the canvas. The tools change; where one of these no longer holds,
say so and follow the tool.

- `design_system extract` fails with `E_DESIGN_NO_ADAPTER` in a repo without a CSS `@theme`, which is every brand
  project. That is expected: use the brief's colours.
- `generate_image` takes at most 16 requests per call (prompts x count). Send batches of 9.
- Cost is reported per call only, with no running total. Keep your own tally and an image cap, and say the cost in each
  reply.
- Generated images are PNGs of up to about 1.6 MB, mostly 1024 x 1024 (one of 18 came back 1408 x 768). Some come back
  non-square, or with a paper or mat edge that becomes a speck after tracing: threshold, trim and pad to a square before
  potrace (turdsize 60 worked).
- Artboard file names cannot contain spaces (a name such as "My Board.dc.html" was refused).
- Files in a subfolder of the canvas (`traced/`, `thumbs/`) are served as they are: reference them with a relative
  `src=`, and do not list them in `design_seed`'s images.
- After adding an artboard, pass the artboards list and the title to `design_seed` explicitly; the title is required
  whenever artboards is given. Seeding by the slug alone missed artboard files written to disk.
- `dc_write` needs the whole template inline, which is impractical for pixel art (hundreds of rects). Write the
  `.dc.html` from a generator script, then run `design_seed`; `design_status` shows such files as stale until they are
  seeded again.
- `eval_js` and `snapshot` act on the artboard last shown: call `show_to_user` first.
- `ready_for_verification` gives the exact content size. Copy it into `canvas.json` w/h, or the board scrolls, and keep
  80 px between artboards.
- `save_screenshot` captures a whole artboard at natural size, which is good for reading slices.
- No canvas tool exports a mark (`design_export` ports UI to code). SVG and PNG come from brand-creator's own pipeline
  (resvg, whole-number scales for pixel marks).
- The canvas guide says to avoid drawing imagery in SVG and to use placeholders. That does not apply to marks: the mark
  is the SVG.
