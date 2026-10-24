# P12 History, ADR and governance

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Method: freeze and history](#method-freeze-and-history)
- [Method: decision records](#method-decision-records)
- [Method: rule changes](#method-rule-changes)
- [Method: the project's memory](#method-the-projects-memory)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

What was approved stays as written, why it was decided stays findable, and a rule changed later is changed everywhere at
once. Nobody, including a later session, reopens a rejected direction by accident or rebuilds from memory what a file
already says.

## Inputs

- Approved rounds (G3 recorded), the Directions table (rejected, liked, DECIDED) and the gate records in BRAND-STATE.md.
- The owner's decisions and their reasons, paraphrased, from each gate.
- The "before" icons and marks of the product repositories (from the adoption survey's icon rows, or the owner).

## Outputs and paths

| Output | Path |
|---|---|
| Frozen copy of an approved round, with a "kept as written" banner | `history/<date>-<name>/` (`brand-creator freeze`) |
| Hash of every frozen file | `history/MANIFEST.sha256` |
| Decision log, one entry per owner decision, newest last | `DECISIONS.md` (from `templates/DECISIONS.md`) |
| Architecture-level decision records | `decisions/ADR-0001-<slug>.md` (from `templates/ADR.md`) |
| The project's memory | `BRAND-STATE.md` (Directions, Rules, Still open, Notes, gates) |

## Method: freeze and history

1. After G3: `brand-creator freeze r<N> --name approved-board --project <dir>`. It copies the round, adds the banner and
   updates the manifest. Freeze the round behind each later approval too (a system-rules board at G4, a recovery round,
   the approved motion round: `freeze r<N> --name approved-motion`, with its variants, proofs and stills kept as written)
   with a name that says what was approved. `freeze` copies a round folder only. Take every still before a freeze: `frames`
   refuses a proof inside `history/` and one in a round before the latest (both are read-only), so a frozen round keeps the
   stills it was frozen with.
2. Rejected directions stay in their rounds and in the Directions table, each with the owner's reason in one line. The
   history chapter of the book tells the path from them; it never shows a rejected direction as an option.
3. Keep the "before": copy the old icons and marks the adoption will replace into the current round (`rounds/r<N>/before/`)
   so its freeze keeps them and the book's history can show what changed. A history chapter that refers to an inventory
   keeps its own copy of it, never a link into a product repository that will change.
4. Nothing under `history/` is edited, moved or removed. A correction is a new round and a new freeze.

## Method: decision records

- `DECISIONS.md` takes every owner decision at a gate: the gate, what was decided (stable direction names), the reason
  (paraphrased, or "owner's taste"), what was rejected and the consequences.
- An ADR is for a decision that shapes the system for a long time: the architecture (standalone, family-member,
  product-in-family), the mark source, the endorsement policy, a never-borrow list, the token structure, the adoption
  order. Copy `templates/ADR.md` to `decisions/ADR-<NNNN>-<slug>.md` (numbers in sequence, never reused) and fill every
  field: Status, Date, Source, Context, Decision, Consequences, Rejected.
- **Append, never rewrite.** A change to an accepted ADR is a dated entry under Amendments ("YYYY-MM-DD: what changed,
  why, which gate"). A decision that is replaced gets a new ADR; the old one's Status becomes "Superseded by ADR-NNNN" as
  an amendment, and its text stays.
- Every ADR entry names its source: the gate record, the round, or the owner's message (paraphrased, dated).

## Method: rule changes

A rule, token, lockup or threshold that changes after it was approved is a cascade, not an edit:

1. Write the change once at its source (a token file, the Rules section of BRAND-STATE.md, a generator constant).
2. Record it: a `DECISIONS.md` entry, and an ADR amendment when an ADR covers the rule.
3. Follow [cascade.md](../cascade.md) to the end: regenerate, byte-check, search for the old value with
   `check --cascade`, show the changed section.
4. The book is a new edition when the approved one changes (`patch --new-edition`, `collapse --new-edition`, or the
   `edition` key for a generated book), and that edition needs its own G5.

When the owner asks "should the book (or the parent's book, or the README) change too?", the answer is the cascade list,
run in full, not a guess about which file matters.

## Method: the project's memory

- BRAND-STATE.md is the memory. Each direction is marked rejected, liked or DECIDED; the owner's signals are paraphrased
  lines under Liked and Rejected; Still open is carried until closed; gate records carry their date.
- Re-read BRAND-STATE.md after a compaction or at the start of a session, before doing anything. Never rebuild the state
  from chat recall.
- A note kept outside the project (a personal memory file of the session) may point at the project folder; it never holds
  a second copy of the rules, the palette or the decisions, which would drift.
- Collaboration preferences the owner states (how many options, the review surface, the language) go into the
  Collaboration block of BRAND-STATE.md, so the next session follows them.

## Gate

There is no owner gate in this phase. `freeze` needs G3; the hook blocks every other write into `history/` and into
earlier rounds; `check` verifies `history/MANIFEST.sha256`. A rule change is done only when `check --cascade` exits 0.

## Pitfalls

- Editing an ADR in place to "keep it current": the reason for the original decision is lost. Append an amendment.
- A rejected direction that comes back in a later round under a new name. Name it, and ask before reopening it.
- Fixing an output (a PNG, `book.html`, a built token file) instead of its source: the next build undoes it.
- Updating the book and forgetting the parent's README, the agent pointer files or the social cards: run the whole list.
- Facts kept in memory instead of FACTS.md: the book and the posts can only quote FACTS.md rows.

## Enforcement

- The hook (`hooks/guard.py`) blocks writes, moves and deletes in `history/` and earlier rounds; `check` fails a manifest
  mismatch (`history:manifest`).
- `check --cascade` fails on any leftover of the old value in the project and the named outside documents.
- ADRs and DECISIONS.md are append-only by convention, written from their templates; no check reads them (they hold old
  values on purpose, so the cascade skips them).
