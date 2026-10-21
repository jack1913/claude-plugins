# Start a brand

Start a brand project for a business, shop, product or person, or pick up one you already began. Claude runs the whole
process one decision at a time, and you decide on taste.

## Before you start

- brand-creator is installed and you have run `/brand-creator:setup` once. See
  [Make your first brand](../getting-started/make-your-first-brand.md).

## Start it

1. Say what you need, such as "a logo and a look for my bakery", or type the command:

   > /brand-creator:new my-bakery

   Claude can start the process itself when you ask for a logo, a look, a visual identity, a rebrand or brand guidelines.
   It works for small, casual asks too, such as "a logo for my band".

2. Answer up to three quick questions. Each has a suggested answer, so `ok` accepts them:
   - how far to go: [Choose a tier](../getting-started/choose-a-tier.md);
   - how this brand relates to others you run, only if you mention a parent or sister brand;
   - the name, only if it's still open.

3. Read how Claude plans to keep the logo: as code (a pixel grid or simple shapes), as vector shapes, or your existing
   logo. Say so if you want it another way. Either way, the logo you get is a vector (SVG) file, drawn on a design tool
   first ([Get your marks drawn](get-your-marks-drawn.md)); generated pictures are only used to explore ideas.

4. Look at the style board. Before anything is drawn, Claude researches how brands like yours look and shows a few
   styles with real examples. You pick; see [Pick and refine a direction](pick-and-refine-a-direction.md).

Your project gets its own folder, like `./my-bakery/`, unless you name another place. Set a default folder in
[Settings](../reference/settings.md).

## Pick up where you left off

Open Claude Code in the project folder, or just ask to go on with your brand. Claude resumes from `BRAND-STATE.md`.

> /brand-creator:status

It shows your brand, tier, where you are, the decisions recorded so far and what comes next. It starts no work.

## Check it worked

- A folder with your brand's name exists, with `BRAND-STATE.md`, `FACTS.md`, `DECISIONS.md` and `brief/BRIEF.md` in it.
- `/brand-creator:status` shows the tier you chose.

## If something goes wrong

| You see | Do this |
| --- | --- |
| "cannot run" | Run `/brand-creator:setup` first |
| "no brand project found" | Open Claude Code inside the project folder, or start one with `/brand-creator:new` |

## Related

- [Pick and refine a direction](pick-and-refine-a-direction.md)
- [Commands](../reference/commands.md)
