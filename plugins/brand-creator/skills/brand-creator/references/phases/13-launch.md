# P13 Launch and outward actions

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Method](#method)
- [Trademark screening, step by step](#trademark-screening-step-by-step)
- [Print hand-off](#print-hand-off)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

The owner has one checklist for everything outward, in the order that protects them: trademark first, then domains, handles and e-mail, then
deploy, then renames, then print. The agent recommends and records. It never buys, files, registers, creates an account, sends a message or renames a
repository.

## Inputs

- The names screening (`assets/_checks/names.json`, the memo in `research/names/`) and, when one exists, the verdict memo's "Launch TODO" seed.
- `adoption.json` (the identifiers the survey read), FACTS.md (`contact email`), BRAND-STATE.md (Still open), the manifest (print files), the tokens.

## Outputs and paths

`LAUNCH.md` at the project root, from `templates/LAUNCH.md`, and `assets/_checks/launch-todo.json`. The owner ticks the boxes in `LAUNCH.md`;
the ticks survive when it is generated again (each box has an id in a comment).

## Method

1. If no name screening is on file, run `names` first (after the owner's privacy OK; see [02-naming](02-naming.md)). Trademark registers are never queried:
   the file carries owner-run links.
2. `brand-creator launch-todo [--name <candidate>]`. Sections, in order: **Trademark first** (the register links for the region, then the decision),
   **Domains** and **Handles and registries** (each state with its date, "checked <date>, recheck before buying"; REGISTERED, NOT-FOUND or UNKNOWN,
   never "available"), **E-mail** (the `contact email` fact, the mailbox and its SPF, DKIM and DMARC), **Deploy** (what goes live first, the DNS, the pack's web files,
   the adoption list finished first), **Repositories, packages and app ids** (the
   identifiers from the adoption survey, with the new value left for the owner), **Print hand-off** (only when print files exist: the printer's
   requirements, the printer's CMYK profile, preflight, the printer's proof, and spot colours as a name plus a Lab target, never "hex equals spot"),
   and **Decisions for you**.
3. Hand the list over ([the launch skill](../../../launch/SKILL.md), `/brand-creator:launch`) one action at a time, with the reason and the exact click path (the registrar's page, the register's search page). When the
   owner says "buy the domain" or "file it", answer with the hand-off, never a purchase or a filing; record the owner's report afterwards (G7).
4. Re-run `launch-todo` after a new names run or adoption survey. Re-run the screening before the owner buys: every state says when it was read.

### Trademark screening, step by step

The owner (or their attorney) runs these; LAUNCH.md carries the links and a line per step for the date and what was seen.
Each result is "what this register showed on this date for this query", never "clear".

1. **The goods and services.** Write down what the brand sells and where, so the owner or attorney can pick the classes of
   the Nice classification. brand-creator suggests none as final; a class list is the owner's or the attorney's.
2. **Identical names** in the registers for the region (the national office, the regional one such as the EU office, and
   the international register for marks designated there), in those classes. Record each register, the query and the date.
3. **Similar names**: spelling variants, the sound of the name, translations into the audience languages, the short form.
   Record each query and the date.
4. **Figurative marks**: the register's image or design-code search, when it has one, against the mark. Record the date.
5. **Use without registration**: a web search, the app stores, package registries and the company register of the region.
   Record what was searched and the date.
6. **The decision**: the owner's or the attorney's, written into LAUNCH.md with its date. A filing is the owner's act.
7. **Recheck before buying or filing** when the screening is more than a few days old: registers change daily.

Registers are never queried by brand-creator: some have no public interface, and some forbid automated searches.

### Print hand-off

Only when print files exist (print is opt-in). It is the owner's step with the printer:

- **The printer's requirements first**: bleed, safe zone, paper, the finishing (foil, embossing, spot inks), the file format
  they accept, and their CMYK profile. Re-emit with `--icc <their profile>`; brand-creator bundles no profile (they are
  licensed and press-specific). Even then the file is only a "PDF/X-4 candidate (preflight with your printer)".
- **Spot colours** (a Pantone or other ink): record the ink's **name** and a **Lab target** taken from the ink maker's own
  reference or the printer's swatch, in the LAUNCH.md table. Never write that a hex value equals a spot ink: a screen colour
  is an approximation of a physical ink, and the plugin ships no ink library.
- **The printer's proof is required** before the run: a contract or hard proof on the real stock, checked against the swatch
  under the printer's standard light. The colour tolerance is the printer's (often a Delta E 2000 figure) and is written down
  with the date of the proof.
- Nothing here can check PDF/X conformance, ink coverage or overprint. The printer's preflight does.

## Gate

**G7 Outward.** One action at a time, with its reason and the click path. You recommend and record; the owner buys, files, registers and contacts.

## Pitfalls

- Saying a name is available, free or clear: a NOT-FOUND is a record of one source on one day, and says nothing about price, reserved or premium
  names, pending releases or earlier trademarks.
- Domains and handles before the trademark answer: the file puts trademark first and says nothing below is bought until it is in.
- A print file called print-ready: an `rgb-proof` file is a proof, a `pdfx4-candidate` is a candidate, and nothing here can check PDF/X conformance.
- Renaming a repository or a bundle id as copy: a store treats a changed id as a new app, and a host redirects old addresses only for a while.

## Enforcement

- `launch-todo` reads local files and writes `LAUNCH.md` only: its module imports no network or process library, and a test checks the project tree
  before and after.
- No state word outside REGISTERED, NOT-FOUND, UNKNOWN, and none of the words available, free, clear, in the generated file (a test).
- `check --cascade` treats the rename list as a record of another repository (a warning), and every other line of `LAUNCH.md` as searched.
- Proven by `test_launch_cascade.py` (see the table in [09-qa](09-qa.md)).
