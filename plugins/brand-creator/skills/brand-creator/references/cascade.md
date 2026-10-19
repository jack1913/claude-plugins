# Cascade: when a rule, token, lockup or threshold changes

## Contents

- [When it applies](#when-it-applies)
- [The checklist](#the-checklist)
- [Where the old look hides](#where-the-old-look-hides)
- [What the search covers](#what-the-search-covers)
- [Exit](#exit)

## When it applies

A brand rule lives in many places. Any change to one of them, after it was approved, is not done until every consumer
agrees and the old value is gone. Typical triggers: a colour or ratio moves, a lockup or its clear space changes, a size
band or threshold moves, a name or a tagline changes, a direction is renamed, a motion timing changes, the endorsement
policy changes. When the owner asks "should we also update the book (or the parent's book, or the README)?", the
answer is this checklist, run in full.

## The checklist

Copy it into the reply's "What changed" and tick it as you go.

1. [ ] **Write the change once, at its source**: token sources (`tokens/*.tokens.json`), a generator constant, the rule
   line in the Rules section of BRAND-STATE.md, a FACTS.md row (owner-confirmed, with its source), a chapter source.
   Never edit a generated file (`book.html` of a generated book, built tokens, packs, BRAND.md, DESIGN.md, ADOPTION.md,
   the applied skill).
2. [ ] **Record it**: a dated entry in DECISIONS.md; an amendment to the ADR that covers it, appended, never rewritten
   ([12-history](phases/12-history.md)).
3. [ ] **Hash before**: `brand-creator snapshot take assets --name before` (add `book.html` and any other output
   folder the change may touch), so step 6 can prove what did not change.
4. [ ] **Regenerate every consumer, from the sources**: the project's own generators first (a mark drawn by code),
   then `tokens`, `contrast`, `logo-sheet`, `downscale`, each `emit` target the project uses (or the project's
   `tools/finish.sh` chain), `book` (generated) or `patch` (hand-authored, with an edition bump when the edition was
   approved), `book-pdf`, `emit print` and `print-check` when print files exist, `emit presskit`, `adapters` and
   `applied-skill --yes` when they exist, `launch-todo` when LAUNCH.md exists. Then `staleness --write` once the chain
   is rebuilt.
5. [ ] **Text that restates the rule**: the book chapter, the project README, the parent brand's README and book in the
   family modes, the never-borrow lists of FAMILY.md, the copy of social posts, the tone and pre-publication
   checklists. In product repositories (after G6 only): the AGENTS.md or CLAUDE.md pointer files and their READMEs, as
   new adoption rows (`adoption add`).
6. [ ] **Byte-check what must not change**: `snapshot take assets --name after`, then `snapshot diff <before.json>
   <after.json>`: every changed file is one the change should touch, and files outside it keep their hashes.
   `verify-idempotent --cmd "<the chain>"` proves a second run changes nothing; `check` still passes `history:manifest`.
7. [ ] **Search for every old value and phrase**:
   `brand-creator check --project <dir> --cascade "<old value>"`, one `--cascade` per old number, colour, name or
   phrase; `--also <path>` for a document outside the project. Fix every hit in a source, never in an output, and run
   it again until it exits 0.
8. [ ] **Variants that bent the rule** (switchable demos, open choices) are updated or collapsed together with it.
9. [ ] **Show the specific section** that changed: a shot of it at 1440 and 390, read before you describe it.

## Where the old look hides

Search finds text. These surfaces embed the old look as pixels or geometry, so they are rebuilt (step 4) and looked at
(step 9), not only searched:

- headers and footers of the site and of the book, README header images and badges;
- Open Graph and social cards, profile images, post templates, the press kit;
- installer art: DMG backgrounds, NSIS and MSI banners and sidebars, store frames and screenshots;
- platform icon sets (favicons, Apple, Windows, Linux, tray, Tauri, Wallet, developer surfaces);
- print stationery, the e-mail signature;
- the parent site's lockups of this product, and a sibling's endorsement lockups (family modes).

## What the search covers

`check --cascade` searches every text file of the project (book sources and `book.html`, README, token sources and built
tokens, text assets, templates in the project, `ADOPTION.md`, `LAUNCH.md`, `BRAND.md`, `DESIGN.md`, the applied skill
under `.claude/skills/`), PDFs as text (not verified when `pdftotext` is missing), and the documents outside the project
that you name: `tools/cascade.json` (`{"schema": 1, "also": ["../parent/README.md", "../parent/brand"]}`, paths relative
to the project, read only), `--also PATH`, and `parent_docs` in the family-check block of FAMILY.md (relative to
FAMILY.md; the parent's own FAMILY.md goes here). A configured document that does not exist fails.

Skipped on purpose, and printed in `cascade:scope`: history, decisions, BRAND-STATE.md, DECISIONS.md, earlier rounds,
`removed-*` and generated records (they say what was decided, old values included); images, zips and print PDFs
(outlined text), which are rebuilt from the sources that were searched. The HTML in `_build/` folders is searched: it is the only text layer of an OG card, social post or store frame made from a value given on the command line. A line of `ADOPTION.md` or `LAUNCH.md` that
records what a product repository still holds is the adoption work list: it warns, it does not fail. Not searched at
all: zips, images, `.docx` and other binary documents, and product repositories (the adoption survey reads those).

## Exit

`check` exits 0, `check --cascade` exits 0 for every old value, and the reply lists what was regenerated, the byte-check
result, the cascade result per old value and the section shots.
