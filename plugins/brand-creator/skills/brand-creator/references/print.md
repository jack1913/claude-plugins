# Print, press kit and social posts

How to produce stationery, a press kit and social posts honestly. The rules and the checks are in `scripts/CONTRACT.md` ("Print, press kit and social
posts"); this file is the method and the owner's hand-off. Standard and Full tier; print is opt-in with the owner (intake question 7).

## Contents

- [The commands](#the-commands)
- [What a print file is, and is not](#what-a-print-file-is-and-is-not)
- [Facts the pieces read](#facts-the-pieces-read)
- [Hand-off to the owner](#hand-off-to-the-owner)
- [Pitfalls](#pitfalls)

## The commands

1. `prereq --for print` (Ghostscript and poppler). Set `content_languages` in BRAND-STATE.md and answer the brief's "Region and language" and
   "Regulated profession" lines.
2. `emit print --region EU|US|JP [--bleed <mm>] [--font-file <brand font>] [--icc <the printer's CMYK profile>]`, then `print-check`. Read the
   rendered pages (`pdftoppm -r 150 -png`) and look at the bleed, the logo and the contact lines before showing them.
3. `emit presskit` after `book` and `book-pdf` (or `--no-book`, said aloud). `emit social --posts --post-fact "<FACTS label>" ...`.

## What a print file is, and is not

Without `--icc` the PDFs are an **RGB proof, not print-ready**. With the owner's own CMYK profile they are a **PDF/X-4 candidate (preflight with
your printer)**. Neither is a printer's acceptance: nothing here can check PDF/X conformance, no profile is bundled, spot colours are not produced.
Never write "print-ready", "conforms" or "compliant" about a file of ours, in chat, in the book or in LAUNCH. The 3 mm (0.125 in) bleed is a default
that is the printer's to confirm.

## Facts the pieces read

`contact name`, `contact role`, `contact email`, `contact phone`, `postal address`, `website` (or `homepage`) and rows starting `legal` in FACTS.md.
A missing row is left out and reported; ask the owner for it, never invent it. `--tagline` and every `--post-fact` are FACTS.md values.

## Hand-off to the owner

For LAUNCH (the owner acts, never the agent):

- [ ] ask the printer for its own template and bleed; re-run `emit print --bleed <mm>`;
- [ ] ask for the printer's CMYK output profile; re-run with `--icc <file>`;
- [ ] run the printer's preflight (Acrobat Preflight, callas or PitStop) on the candidate: conformance cannot be checked here;
- [ ] order a contract proof on the real stock and check the brand colours against it under daylight. Spot colours are recorded as a name plus a
      Lab target, never "this hex equals the spot"; spot-library licensing is not assumed;
- [ ] compare `qa/print.json` thresholds (safe zone, thinnest line, smallest reversed text) with what the printer says, and record any change as a decision;
- [ ] offer a few card fronts on one shared back, with a recommendation, rather than many unrelated cards;
- [ ] for a regulated profession, tick `assets/social/posts/PRE-PUBLICATION.md` before any post goes out.

## Pitfalls

- Calling a pass of `print-check` "print-ready". It reads boxes and physical rules; the printer's preflight and proof decide.
- Running `emit print` before the contact rows are in FACTS.md: the card back refuses, the letterhead and envelope go out thin.
- A system font on stationery: pass `--font-file` and check its licence allows outlining (`fontcheck`).
- Checking the e-mail signature only in a browser: send it to the main mail clients, light and dark (a manual check).
