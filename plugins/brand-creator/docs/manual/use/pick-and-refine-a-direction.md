# Pick and refine a direction

Choose a style, then one of three different looks for your brand, then refine it until it's right. Your pick is then locked.

## Before you start

- You have a brand project. See [Start a brand](start-a-brand.md).

## Pick a style first

Nothing is drawn until you have seen how brands like yours look and picked the styles you like.

1. Open the style board. It shows who will see your logo, where, what the category usually looks like, and four to six
   styles. Each style comes with real brands you can open and look at, and what to take from each and what to avoid.
   Where Claude could fetch a brand's logo, a small picture of it sits next to the brand, marked as shown for private
   research.
2. Tick the styles you like (one or more) or `none: research again`, or just answer with the style names. If you are
   making several things (a family of marks), you also say whether they share one style or each gets its own.
3. Want to go straight to drawing? Say "skip the research". Claude records that you skipped and never skips it for you.
   You can skip only before the first board of directions. If you later reject every direction, the style board comes back
   and you pick again.

Looking up real brands needs web access. If Claude has none, it tells you so and waits. It never makes up brands. Send
links or screenshots of brands you like. Before your first board of directions you can also skip the step.

## Pick a direction

1. Open the board. It is one page with three clearly different directions, plus "None of these". It may open as a
   private claude.ai page or a local file, depending on [your setting](../reference/settings.md). The marks on it are
   drawn on a design tool first: see [Get your marks drawn](get-your-marks-drawn.md).
2. Answer by name, or by question and option, like `1a 2b`. `ok` accepts every suggestion.
3. Claude restates your choice before it builds, in the form "You picked <direction> and <anything you asked to borrow>;
   building that now." Correct it if it's wrong.

If none of them fit, say so. Claude researches again, shows a new style board so you can pick the styles again (this one
can't be skipped), and then shows new directions, including at least one far from what the category usually does.

## Refine it

1. Run the next round:

   > /brand-creator:round refine

2. Read the new board. It lists what changed and the weak points.
3. Answer, or ask for another round. Refining deepens your pick. It doesn't blend in the others.
4. When you approve a board, Claude locks it: the round is saved in `history/` with a checksum, and nothing can quietly
   change it afterwards.

You can combine picks ("refine with style 2 and 3"). Claude states how it reads that before it builds.

## Try a motion round (Standard and Full)

After you approve the refined board, Claude asks one question, once: does your logo move? A shop or a practice that lives
on paper and in a window rarely needs to. A logo seen in an app or on a site often does. Claude tells you which it
recommends, and why.

1. Say that nothing moves, with a short reason in your own words, and Claude records it. Or say yes to a motion round.
2. For a motion round, Claude builds a board of three variants of your logo's one move, each on a page where you would
   really see it. You can also ask for it yourself:

   > /brand-creator:round motion

3. Read the board. Each variant shows a strip of stills, so you can read the move frame by frame, the still you get when
   reduced motion is on, a link to the live page, what the proof found, what the move is, what it costs and what is left
   with no script.
4. Answer by name, or by question and option like `1a`. You can ask to combine two variants ("Settle, with Glide's
   curve"), or say that none of them fits and what was missing.
5. Claude refines your pick in further rounds, like any other board, and shows what changed and the weak points.
6. When you approve a variant, Claude keeps it as your brand's approved move, with its proof and its stills (the brand
   book replays them), and locks the round.

Either answer is asked once. To change your mind later, ask Claude: it changes `motion/motion.json` and searches the
project for places that still say the old thing.

## Check it worked

- The finished round is in `history/`, and `/brand-creator:status` shows your pick.
- `/brand-creator:check` verifies the locked rounds against their checksums.

## If something goes wrong

| You see | Do this |
| --- | --- |
| A write to an earlier round is blocked | That's the lock on finished rounds. Work in the latest round, or start a new one |
| Shots "not verified" | Chromium is missing. Run `/brand-creator:setup`. The board is still written |
| The first board of directions does not appear | It waits for your style pick. Answer the style board, or say "skip the research" |
| Claude says the style research needs web access | Allow web access, or send links or screenshots of brands you like. Before your first board of directions you can also say "skip the research" |
| You started the brand before the style step existed | Either have Claude run the style research now (`/brand-creator:round style`), or tell it your first board was drawn before that step. Both are fine |
| A bare "1" when two lists are on the board | Claude asks which list you mean, or says what it assumed |
| A motion round is refused before you approved the design | The motion round comes after you approve the refined board. Approve it first |
| A motion round is refused because nothing moves is recorded | The two contradict each other. To try motion after all, ask Claude to change `motion/motion.json`, so it can search the project for places that still say nothing moves |

## Related

- [Name your brand](name-your-brand.md)
- [Check your project](check-your-project.md)
- [Glossary](../reference/glossary.md)
