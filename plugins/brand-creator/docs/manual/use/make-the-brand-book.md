# Make the brand book

Get one page of brand rules: your logo at several sizes, colours with their contrast, type, files and proof. It is built
from your project, so it can't drift from your files.

## Before you start

- You have a brand project with an approved logo and colours. A brand that doesn't exist yet starts with
  [Start a brand](start-a-brand.md).

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
