# Make the brand book

Get one page of brand rules: your logo at several sizes, colours with their contrast, type, files and proof. It is built
from your project, so it can't drift from your files.

## Before you start

- You have a brand project with an approved logo and colours. A brand that doesn't exist yet starts with
  [Start a brand](start-a-brand.md).
- In Standard and Full, motion is settled first: you tried a motion round, or you said that nothing moves. See
  [Pick and refine a direction](pick-and-refine-a-direction.md).

## Build it

1. Ask in your own words, such as "generate the brand book", or type the command:

   > /brand-creator:brand-book

2. Claude builds `book.html`, one self-contained page with no script and no network, in light and dark. The cover shows
   your name as you drew it, with your wordmark. In Quick it is a short guide: idea, mark, colour, files and changing the
   brand. Standard and Full add the full chapters.
3. Claude reviews the book against its own checklist and shows you the findings.
4. Read it and approve it, or ask for a change.

## Change it later

Ask for the change: "update the guidelines after the colour change". Claude changes the source and rebuilds. It never
edits `book.html` by hand. A hand-drawn logo has a hand-written book instead, which Claude edits through counted patches
that open a new edition.

## If your brand moves

In Standard and Full the book always has a Motion chapter once motion is settled. When nothing moves, it says so and gives
your reason, and there is nothing to replay. When your brand moves, read on.

The Motion chapter can replay your brand's motion, with no script. Before you build the book, ask Claude for "stills of
the motion", or run `brand-creator frames motion/proof.json --count 25`. The chapter then plays the mark's movement on
its own page, with a "Replay" box and a "4× slower" box you can click or reach with the keyboard. With reduced motion
switched on, it shows the still and nothing moves. If the stills are missing or older than the page, the build tells you
which command to run, and `check` tells you when you took them after the book was built, or when the page (or a stylesheet
it loads) changed since you took them, or when a later run for one case (`--case`) left the other cases' stills without a
check: run `frames`, then `book`. The `tools/finish.sh` of a new Standard or Full project takes fresh stills for you; an
older one needs the `frames` step added before `book`.

## A book in another language

The approval stamp says `APPROVED` until you give it the word in your language. For a Polish book, add this to
`book/book.json`, and the cover says `ZATWIERDZONO` and the date:

```json
{"schema": 1, "labels": {"pl": {"APPROVED": "ZATWIERDZONO"}}}
```

## Export a PDF

Ask for "the brand book as a PDF". It is an RGB proof labelled "RGB, not print-ready": good for checking on screen, not
for a printer.

## Optional extras

When you approve the book, you may opt into `BRAND.md` and `DESIGN.md` files for other agents, and a small per-brand
skill in your project's `.claude/skills/`. Without a yes, Claude writes neither.

## Check it worked

- `book.html` exists in your project and opens in a browser.
- `/brand-creator:check` passes its book rows, or says "not verified" and why.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude says something is missing | It names the step that builds it: the logo, the colours or the files. Finish that first |
| The PDF step stops | The PDF checks need poppler. `brand-creator prereq --for standard` lists what's missing and how to install it |

## Related

- [Check your project](check-your-project.md)
- [What it makes](../reference/what-it-makes.md)
