# Make your first brand

Go from "I need a logo" to a checked logo, colours, favicons, a social card and a short guide. You decide on taste;
Claude does the legwork.

## Before you start

- brand-creator is installed. The [README](../../../README.md#install) has the two install lines.
- You have a business, shop, band, practice or product in mind. It doesn't have to be software.

## Make a brand

1. **Install the tools, once.** Type:

   > /brand-creator:setup

   It shows what it will download and where it goes, then waits for your yes. That is about 200 MB of Node packages and
   a headless Chrome, in the plugin's own data folder. A matching Playwright Chrome you already have is reused.

2. **Say what you want.** For example:

   > A logo and a look for my bakery

   Or type `/brand-creator:new my-bakery`. You get up to three quick questions, each with a suggested answer:
   - how far to go ([Choose a tier](choose-a-tier.md)),
   - how this brand relates to others you run (only if you mention a parent or sister brand),
   - the name (only if it's still open).

   It may also ask once whether boards can be shown as a private claude.ai page. Claude also tells you how it will keep
   the logo: as code (a pixel grid or simple shapes), as vector shapes, or your existing logo. Say so if you want it
   another way.

3. **Pick a style, then a direction.** First a style board shows how brands like yours look, with real examples. You pick
   the styles you like, or say "skip the research" (you can skip only before the first board of directions). Then one
   page, the board, shows three clearly different directions, plus "None of these". Answer by name, or by question and
   option, like `1a 2b`. `ok` accepts every suggestion.

4. **Refine.** Run `/brand-creator:round` for one more round. Your pick is then locked (saved in `history/`).

5. **Build and check.** You get your logo at real sizes, colours, a contrast report, favicons, a social card and a short
   guide. `/brand-creator:check` runs every check, and `/brand-creator:status` shows where you are.

Your project gets its own folder, like `./my-bakery/`, unless you pick another one.

## Check it worked

- The project folder exists and holds `BRAND-STATE.md`.
- `/brand-creator:status` names your tier and the next step.
- `/brand-creator:check` ends with every row passed, or says "not verified" and why.

## If something goes wrong

| You see | Do this |
| --- | --- |
| A tool stops with "cannot run" | Run `/brand-creator:setup` |
| Shots "not verified" | Chromium is missing. Run `/brand-creator:setup` |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Start a brand](../use/start-a-brand.md)
- [Pick and refine a direction](../use/pick-and-refine-a-direction.md)
- [Glossary](../reference/glossary.md)
