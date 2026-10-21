# Get your marks drawn

Your marks are drawn on a design tool, not typed up as code. Claude uses the first tool your session has, and you see and
comment on the drawings before they go on a board.

## Before you start

- You have picked your styles on the style board. See [Pick and refine a direction](pick-and-refine-a-direction.md).
- One of these, best first:
  - a design canvas: start Claude Code with `use-claude` in your brand project's folder. `use-claude` comes from use-llm,
    a separate tool that starts Claude Code with a design canvas;
  - Claude Code's own `/design`: a Claude Code version that has it ([which one](../reference/claude-code-versions.md)),
    signed in to claude.ai on a Pro, Max, Team or Enterprise plan.

## Get the marks drawn

1. Claude writes a drawing brief into your project, such as `brief/canvas-round-1.md`: what to draw, the colours, the
   sizes that must work and how many pictures it may generate.
2. On the design canvas, Claude starts drawing and shows you the canvas, but it generates no pictures until you agree to
   the limit in the brief. Comment on the canvas, or send screenshots in the chat. Each option has an ID that names its
   board, such as `family1-bc-3`: use it when you pick, so a choice can't be read two ways.
3. With `/design`: Claude can't start `/design` for you, so it tells you the exact line to type, for example:

   > /design Read brief/canvas-round-1.md and draw what it asks.

4. Tell Claude which drawings to keep. They come into the round's folder as vector files, and Claude builds the board
   from them. Give board answers, such as an approval, in your brand-creator session, not the drawing one.

Already picked on the canvas? Say so. Claude notes your pick in your own words and still files the board, as a record of
what you saw.

## If neither tool is there

Claude tells you what's missing and how to get it. It can also draw the marks as SVG code itself, but only if you say
yes, and it tells you first that marks drawn this way tend to look generic. A plain "ok" never counts as that yes: the
suggested answer is to wait while you set up a tool. A yes is noted in `BRAND-STATE.md`.

## What it costs

On the design canvas, Claude can generate pictures to explore ideas, and each picture costs money: they run through
OpenRouter. Claude proposes a limit in the brief, generates nothing until you agree, and says the cost in each reply. See
[Costs](../reference/costs.md).

## Check it worked

- Each kept mark is an SVG file in `rounds/r<N>/<direction>/`, with PNG copies at 16, 32 and 128 px.
- Each direction folder has a `SOURCE.md` that says how its marks were made: the tool, the prompts, the cost and what was
  fixed by hand.
- The canvas keeps its own files in a `.design/` folder in your project.

## If something goes wrong

| You see | Do this |
| --- | --- |
| The canvas files landed in another repository's `.design/` | Ask Claude to move the canvas folder, name unchanged, into your brand project's `.design/` folder, and start `use-claude` in your brand project's folder next time |
| `/design` isn't there | Update Claude Code (`claude update`) and sign in to claude.ai on a Pro, Max, Team or Enterprise plan |
| A drawing looks fine large but not at 16 px | Say so. Claude redraws the small size instead of shrinking the big one |

## Related

- [Pick and refine a direction](pick-and-refine-a-direction.md)
- [Costs](../reference/costs.md)
- [What it never does](../reference/what-it-never-does.md)
