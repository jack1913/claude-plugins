# P10 Brand book

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Method: generated mark source](#method-generated-mark-source)
- [Method: authored-vector mark source](#method-authored-vector-mark-source)
- [Self-review before G5](#self-review-before-g5)
- [Collapse, edition and approval](#collapse-edition-and-approval)
- [Adapters and the applied skill (opt-in at G5)](#adapters-and-the-applied-skill-opt-in-at-g5)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

One self-contained document that says what the brand is, shows it at the sizes it will be used at, and proves what was measured. Quick: a short
guide (the Quick chapters: idea, mark, colour, files, changing, plus wordmark when there is one), built by `book` like any book, and the Quick
path ends with it and G5. Standard and Full: the whole book. The book is a view of the project's data, not a second copy
of it: tokens, the manifest, BRAND-STATE.md, FACTS.md and the check reports are read, never retyped.
The order of work, and the self-review as a checklist, are in [the brand-book skill](../../../brand-book/SKILL.md); `/brand-creator:review`
runs the same self-review.

## Inputs

- Built tokens (`brand-creator tokens`), the mark SVGs, `assets/manifest.json` from the emitters, the contrast and downscale reports.
- BRAND-STATE.md: tier, architecture, `mark_source`, `content_languages`, `edition`, the Directions table, the Rules section, gates.
- FACTS.md: every claim in the book's own words is a row there, or it is not written.
- `book/chapters/*.md` (generated mode) or `book.html` (authored-vector mode).

## Outputs and paths

- `book.html`: fonts and images inline as data URIs, no script, no network, light and dark through `prefers-color-scheme` and the tokens.
- `book.pdf`: an RGB proof labelled "RGB, not print-ready" in its metadata and on its cover; never offered as a print file.
- `assets/_checks/book.json`, `book-lint.json`, `book-pdf.json`; `removed-<date>/` after a collapse.
- Which chapters appear: the tier, the architecture and the project decide (`scripts/CONTRACT.md`, "Brand book").
- The last chapter, "Changing the brand", ends with **Governance**: who approves a change, the naming rule (and the regulator's,
  where one applies), the claim rule (FACTS.md rows only) and the accessibility commitments. BRAND.md carries the same section when the
  adapters are on.

## Method: generated mark source

`mark_source: generated` and `existing`: the book is generated and never hand-edited.

1. `brand-creator book --init` writes a skeleton for each chapter this book needs into `book/chapters/` (never overwrites). Set
   `content_languages` and `edition` in BRAND-STATE.md first (`state --set`); with several languages every chapter is written in each.
2. Fill every `[[fill: ...]]` marker, one chapter at a time. Computed blocks (`{{marks}}`, `{{mark-sizes}}`, `{{contrast}}`, `{{files}}`,
   `{{checks}}`, `{{donts}}` ...) and counts (`{{count:files}}`) come from data: never type a number, a colour value or a file list. A claim about
   the brand is `{{fact:label}}` or words that restate a FACTS.md row. Status words ("available", "launching", "in development") need a row.
3. `brand-creator book`. It lints the page and writes it only when it lints clean. Read the 1440 and 390 px shots
   (`brand-creator shot book.html`) before any visual claim, in light and dark.
4. `brand-creator book-lint --self-consistency`, then `brand-creator check`. `check` fails a book.html that is not the bytes `book` wrote.

## Method: authored-vector mark source

The book is hand-authored HTML (the chapters of a drawn identity are drawings the generator cannot know). `book` refuses.

- The only edit path is `brand-creator patch book.html --old ... --new ... --count N`: it refuses unless the text occurs N times and writes
  one line to the Edition log in BRAND-STATE.md. Read where the text occurs before choosing N.
- Mark every embedded mark (`data-mark`), keep text out of marks (outline it: `outline-glyphs`), keep diagrams that carry labels in
  `<svg data-diagram>`, give each file row `data-path` and `data-sha`, and each chapter `<section data-chapter="id">`.
- `brand-creator book-lint --self-consistency` is the gate, with the same rules as the generated book.

## Self-review before G5

Run the lint, then read the book as a stranger would. Each item has a check or a named human step:

| Item | How |
|---|---|
| No mark depends on an installed font | `book-lint` `marks:lint`; outline text with `outline-glyphs` |
| Formal and short names are used consistently (and per the regulator's rule where one applies) | read the book; judgement |
| The book obeys its own rules (motion durations, smallest label, palette) | `book-lint --self-consistency` |
| Legal and regulatory statements match a dated source | FACTS.md `legal:` rows (verbatim) and the owner's source; judgement |
| The system has not drifted back into a rejected direction | read the history chapter against the Directions table; judgement |
| Required chapters are present for the tier | `book-lint` `chapters:required` |
| Components show their focus state | read the components chapter; judgement |
| No label is under the minimum size | `book-lint --self-consistency` `self:font-size` |
| The book reads at 390 px | `brand-creator shot book.html`, read the 390 slices |
| Counts and file rows agree with the data | `counts:data`, `counts:typed`, `files:accounting` |

## Collapse, edition and approval

While a choice is open, options live in the book sources and tokens as `::: variant GROUP NAME` blocks, `::: switcher GROUP` fences, and
tokens or elements marked `variant`. After the owner decides: `brand-creator collapse --group G --keep NAME` (show the plan; `--apply` writes
it after the owner has seen it). The losing options and every switcher leave the sources; a dated copy of each changed file goes to
`removed-<date>/`; the decision is recorded under Collapsed in BRAND-STATE.md. Rebuild the tokens and the book afterwards. Variants live only
while undecided: `book-lint` fails any left in the book, and `book --allow-variants` exists only for a review build.

The cover shows the edition and APPROVED (or the word `labels.<language>.APPROVED` gives in `book/book.json`, for the book's first
content language) only when G5 is recorded for that edition (`state --record G5` writes `approved_edition`). A generated book follows
BRAND-STATE.md when rebuilt. A hand-authored book is patched to show the stamp before G5 is recorded. After approval an edition is not
edited in place: `patch --new-edition` or `collapse --new-edition` opens the next one, which needs its own G5.

## Adapters and the applied skill (opt-in at G5)

Ask once, at G5, whether the owner wants either. Nothing below is written without the owner's yes, and each needs G5 recorded.

- `brand-creator adapters --brand-md --design-md [--primary <role>]`: `BRAND.md` (Strategy, Voice, Visual, Governance; `type` and `architecture` frontmatter
  from BRAND-STATE's architecture, overridable with `--bm-type` and `--bm-architecture`) and `DESIGN.md` (YAML tokens: colours with `-dark` variants,
  type families, spacing, a component per text pair; then the section prose), both generated from the built tokens, BRAND-STATE.md and FACTS.md. Sections
  with no source say so ("no voice facts are recorded"); contact facts stay out. DTCG stays the truth. `DESIGN.md` is linted by the pinned
  `@google/design.md` when `setup` installed it, else the result is "not verified" (exit 3), never a pass. An error, or a contrast-ratio finding, fails;
  other findings (`missing-primary`, `orphaned-tokens`) are warnings.
- `brand-creator applied-skill --yes`: a small skill in the project's own `.claude/skills/<slug>-brand/SKILL.md` (colours and ratios, type, mark files and
  the small-size rule, what is never done, the G4 rules, the facts that may be claimed). Without `--yes` it prints the plan and exits 2.
- Both are generated files: `check` fails a hand edit, treats a changed source as not verified, and `check --cascade` searches them. `staleness` reads
  both as inputs of the pack. `--replace` moves a hand-edited file to `removed-<date>/` before writing a new one.

## Gate

**G5** (every tier; in Quick it closes the project after the short guide): the edition is approved, the collapse step is done, `check`
exits 0 with the book's reports current. BRAND.md and DESIGN.md adapters
and an applied brand skill are written only on the owner's explicit yes at this gate.

## Pitfalls

- Typing a count or a status into prose. The lint catches a number that disagrees, not one that happens to agree today: use `{{count:...}}`.
- Round, version and decision wording outside the history chapter ("Round 2", "v3", "item a", "Decision 4").
- Leaving choice scaffolding (variants, switchers) in the book after the decision.
- Editing the generated `book.html`: the next build overwrites it and `check` fails it meanwhile.
- Calling the PDF print-ready. It is an RGB proof; a printer's own proof and a print profile come from the owner.
- A book approved with a stale proof table: rebuild after every change to a report's inputs; `check` says which report is stale.

## Enforcement

`book-lint` (every row in `scripts/CONTRACT.md`, "Brand book", each proven by a test in `09-qa.md`), `check` (report currency, generated bytes,
state view), `patch` (counted edits, edition log, approved edition), `collapse` (dated copy, record), `book-pdf` (label in metadata, XMP and
page 1; RGB only).
