# Pick and refine a direction

Choose one of three different looks for your brand, then refine it until it's right. Your pick is then locked.

## Before you start

- You have a brand project. See [Start a brand](start-a-brand.md).

## Pick a direction

1. Open the board. It is one page with three clearly different directions, plus "None of these". It may open as a
   private claude.ai page or a local file, depending on [your setting](../reference/settings.md).
2. Answer by name, or by question and option, like `1a 2b`. `ok` accepts every suggestion.
3. Claude restates your choice before it builds, in the form "You picked <direction> and <anything you asked to borrow>;
   building that now." Correct it if it's wrong.

If none of them fit, say so. Claude researches again and shows new directions, including at least one far from what the
category usually does.

## Refine it

1. Run the next round:

   > /brand-creator:round refine

2. Read the new board. It lists what changed and the weak points.
3. Answer, or ask for another round. Refining deepens your pick. It doesn't blend in the others.
4. When you approve a board, Claude locks it: the round is saved in `history/` with a checksum, and nothing can quietly
   change it afterwards.

You can combine picks ("refine with style 2 and 3"). Claude states how it reads that before it builds.

## Check it worked

- The finished round is in `history/`, and `/brand-creator:status` shows your pick.
- `/brand-creator:check` verifies the locked rounds against their checksums.

## If something goes wrong

| You see | Do this |
| --- | --- |
| A write to an earlier round is blocked | That's the lock on finished rounds. Work in the latest round, or start a new one |
| Shots "not verified" | Chromium is missing. Run `/brand-creator:setup`. The board is still written |
| A bare "1" when two lists are on the board | Claude asks which list you mean, or says what it assumed |

## Related

- [Name your brand](name-your-brand.md)
- [Check your project](check-your-project.md)
- [Glossary](../reference/glossary.md)
