---
name: brand-book
description: Builds, updates, reviews and exports the brand book of an identity that already has an approved mark and tokens. The book is a self-contained guidelines page (book.html) with the mark by size, colour with computed contrast, type, files and proof, built from the project's data, and comes with a self-review, the collapse of decided options, an RGB proof PDF labelled as one, and opt-in BRAND.md, DESIGN.md and per-brand skill files. A generated book is rebuilt byte for byte and never hand-edited; the book of a drawn identity is edited only through counted patches that open a new edition. Book and guidelines only; not for slide decks, code style guides, design-system documentation sites or designing a new brand.
when_to_use: Use this skill whenever someone wants brand guidelines, a brand book or a rules page written, changed, reviewed or exported, even one chapter or one page, because it builds the book from the project's data so the book cannot drift from the tokens and files. Use when someone wants the brand book, brand guidelines or a brand rules page made, updated, reviewed, approved or exported ("generate the brand book", "update the guidelines after the colour change", "one page of brand rules for the team", "export the brand book as a PDF"), or when a brand-creator project reaches P10. Polish triggers include "księga znaku", "zaktualizuj księgę znaku", "zasady marki", "wytyczne marki", "brandbook". A brand that does not exist yet starts with the brand-creator skill.
compatibility: Claude Code only (calls the plugin's bin/ entry point). Needs the Chromium installed by /brand-creator:setup for shots and book-pdf, and poppler (pdfinfo, pdftotext) for the PDF checks.
allowed-tools: Bash(brand-creator *)
---

# Brand book

Builds the book of a brand that has an approved mark and built tokens, and keeps it true to the project's data. The
book is a view of the data (tokens, the manifest, BRAND-STATE.md, FACTS.md, the check reports), never a second copy.
The method in full is [10-book](../brand-creator/references/phases/10-book.md); this skill is the order of work.

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

## Contents

- [Find the project and the mode](#find-the-project-and-the-mode)
- [Running the tools](#running-the-tools)
- [Generated book](#generated-book)
- [Hand-authored book](#hand-authored-book)
- [Self-review](#self-review)
- [Collapse](#collapse)
- [Approval (G5) and the opt-in files](#approval-g5-and-the-opt-in-files)
- [The PDF](#the-pdf)
- [Pitfalls](#pitfalls)

## Find the project and the mode

1. `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. No project → this skill does not apply yet:
   offer the brand-creator skill (a new brand) or, for an existing mark with no project, its Quick tier with mark
   source `existing`.
2. Read BRAND-STATE.md fully: tier, architecture, `mark_source`, `content_languages`, `edition`, `approved_edition`,
   the Rules section, the Directions table, Still open. The book needs G3 (approved board), the mark files, built tokens
   (`tokens`) and the emitters' manifest. Anything missing → say which phase builds it (P6, P7 or P8) and stop.
3. The mark source decides how the book is edited:

| `mark_source` | The book | The only edit path |
|---|---|---|
| `generated`, `existing` | generated from `book/chapters/*.md` and the data | the chapter sources, then `book`; never `book.html` |
| `authored-vector` | hand-authored `book.html` (its chapters are drawings the generator cannot know) | `patch`, counted, with an edition log line; `book` refuses |

Quick tier: a short guide (idea, mark, colour, files, changing). Standard and Full: the chapters the tier, the
architecture and `book_chapters` select (`scripts/CONTRACT.md`, "Brand book").

## Running the tools

Always the bare entry point, in this form:

```
brand-creator --data "${CLAUDE_PLUGIN_DATA}" <subcommand> --project <project-dir> ...
```

If the shell answers `brand-creator: command not found` (a host that does not put a plugin's `bin/` on PATH), call
`"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"` with the same arguments for the rest of the session.

Exit codes: 0 pass, 1 a gate failed, 2 usage error, 3 cannot run. On 3, tell the owner the fix the message names
(usually `/brand-creator:setup` or a poppler install) and stop that step; a check that did not run is "not verified",
never passed.

## Generated book

1. Set the languages and the edition first: `state --set content_languages=en --set edition=1` (several languages:
   every chapter is written in each, and the lint compares their structure).
2. `book --init` writes the skeleton of each chapter this book needs into `book/chapters/`; it never overwrites. Each
   `[[fill: ...]]` marker says what belongs there. Replace every one, one chapter at a time.
3. Never type a number, a colour value, a file list or a status: computed blocks (`{{marks}}`, `{{mark-sizes}}`,
   `{{contrast}}`, `{{files}}`, `{{checks}}`, `{{donts}}`), counts (`{{count:files}}`) and facts (`{{fact:label}}`)
   come from data. A claim is a FACTS.md row or it is not written. Round, version and decision wording goes only in
   the history chapter.
4. `book`. It writes `book.html` only when the page lints clean.
5. `book --verify` rebuilds in memory and compares with the file: the build is byte-identical or it is a defect to
   report, not to paper over.
6. `shot book.html`, then Read the 1440 and 390 px slices in light and dark before any visual claim. Iterate.
7. `book-lint --self-consistency`, then `check`. `check` fails a `book.html` that is not the bytes `book` wrote.

## Hand-authored book

1. Read `book.html` around the text before every edit, and count where it occurs.
2. `patch book.html --old "<exact text>" --new "<new text>" --count <N> --note "<why, one line>"`. It refuses unless the
   text occurs exactly N times, and writes one line to the Edition log in BRAND-STATE.md. Never Edit or Write
   `book.html` directly, and never use a shell substitution on it.
3. An approved edition is not edited in place: add `--new-edition`, which opens the next edition (it needs its own G5).
4. Keep the markup contract: `data-mark` on every embedded mark, no live text inside a mark (outline it with
   `outline-glyphs`), labelled diagrams in `<svg data-diagram>`, `data-path` and `data-sha` on file rows, one
   `<section data-chapter="id">` per chapter.
5. `book-lint --self-consistency` is the gate, with the generated book's rules; then `shot book.html` and read it.

## Self-review

Run it before showing the owner an edition, and present the result as one list: fixes that need no decision (made, then
re-checked), then numbered "Decisions for you", each with a recommendation. `/brand-creator:review` runs the same list.

| # | Item | How it is checked |
|---|---|---|
| 1 | No mark depends on an installed font | `book-lint` (`marks:lint`); outline text with `outline-glyphs` |
| 2 | Formal and short names are used consistently, and as the regulator requires where one applies | read every chapter and the cover; [regulated-industries](../brand-creator/references/regulated-industries.md) |
| 3 | The book obeys its own rules: motion durations, the smallest label, the palette | `book-lint --self-consistency` |
| 4 | Legal and regulatory statements match a dated source | FACTS.md `legal:` rows, verbatim, and the owner's source; UNVERIFIED when none was read |
| 5 | The system has not drifted back into a rejected direction | the history chapter against the Directions table; judgement, said as such |
| 6 | Every chapter the tier needs is there | `book-lint` (`chapters:required`) |
| 7 | Components show their focus state | the components chapter, read in the shots |
| 8 | No label is under the minimum size | `book-lint --self-consistency` (`self:font-size`) |
| 9 | The book reads at 390 px | the 390 px slices of `shot book.html`, light and dark |
| 10 | Counts and file rows agree with the data | `counts:data`, `counts:typed`, `files:accounting` |

Items 2, 5 and 7 are judgement: say what you read and how sure you are. Measurements replace adjectives.

## Collapse

While a choice is open, its options live in the sources as `::: variant GROUP NAME` blocks and `::: switcher GROUP`
fences. Once the owner decides:

1. `collapse --list`, then `collapse --group <G> --keep <NAME>` prints the plan. Show it.
2. `collapse --group <G> --keep <NAME> --apply` after the owner has seen it. The losing options and every switcher leave
   the sources, a dated copy of each changed file goes to `removed-<date>/`, and the decision is recorded under
   Collapsed in BRAND-STATE.md. An approved edition needs `--new-edition`.
3. Rebuild the tokens and the book. `book --allow-variants` exists only for a review build while a choice is open.

## Approval (G5) and the opt-in files

1. G5 needs: the collapse done, `check` exit 0 with the book's reports current, and the owner's approval of this edition.
   Record it: `state --record G5 "<edition and what was approved>"` (it writes `approved_edition`; the cover then says
   APPROVED). A hand-authored book is patched to show the stamp before G5 is recorded.
2. Ask once, at G5, with AskUserQuestion: BRAND.md and DESIGN.md for coding agents, and a per-brand skill in the
   project's own `.claude/skills/`. Recommend only what the owner will use. Without a yes, write neither.
3. Yes to the adapters → `adapters --brand-md --design-md [--primary <role>]`. DESIGN.md is linted by the pinned
   `@google/design.md`; when it is not installed the result is "not verified" (exit 3), never a pass. Then
   `staleness --write` after the chain is rebuilt.
4. Yes to the skill → `applied-skill` (prints the plan), then `applied-skill --yes`. It is a change to the project's
   configuration: say where it goes before writing.
5. These files are generated: a later change goes into the sources, then the command again. `check` fails a hand edit.

## The PDF

`book-pdf` writes `book.pdf`, an **RGB proof**: "RGB, not print-ready" is in its metadata, its XMP and on page 1. Call it
that in chat. It is for reading and sharing, never a print file; print production is the separate, opt-in step in
[print](../brand-creator/references/print.md), and even its output is only a candidate the printer proofs.

## Pitfalls

- Editing the generated `book.html`: the next build overwrites it, and `check` fails it meanwhile.
- Typing a count that happens to agree today. Use `{{count:...}}`; the lint only catches a number that disagrees.
- Status words ("available", "launching", "in development") without a FACTS.md row behind them.
- Approving with a stale proof table: rebuild after any change to a report's inputs; `check` names the stale report.
- A rule changed in the book only. A rule lives in many places: follow [cascade](../brand-creator/references/cascade.md)
  and run `check --cascade "<old value>"`.
- Writing the adapters or the applied skill because they seem useful. They are the owner's opt-in at G5.

References: [10-book](../brand-creator/references/phases/10-book.md) (method and enforcement), `scripts/CONTRACT.md`
("Brand book"; "Adoption, cascade, adapters, applied skill and launch"), the [orchestrator](../brand-creator/SKILL.md)
(gates, response template).
