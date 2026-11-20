# 0.15.0: a parent brand of a family — plan

Asked for by the Batler brand session on 2026-11-20 (owner: "Workaround + report"); owner approved taking it on as 0.15.0
and chose polygon point lists for glyph comparison. Native execution in the main thread, TDD per task.

**Goal:** a brand project can say it is the parent of a family, and the plugin then treats it as one: state, BRAND.md,
the book, FAMILY.md's place and family-check. family-check also compares letters drawn as polygons.

## Decisions (calls marked "my call" are open to the owner's change)

- New `architecture` value `family-parent`. A parent owns the family layer and the family's rules; it is not a member.
- BRAND.md for a parent: `master` / `branded-house` (my call: the parent houses the products under its system;
  `--bm-architecture` still overrides).
- FAMILY.md of a family lives at the parent project's root (`FAMILY.md`, the existing default path). A member or product
  keeps its own FAMILY.md, whose `glyphs.family`, `tiles` and `parent_docs` point into the parent's project (read only).
- The parent's book: `endorsement` and `family` follow the family modes' rule (Standard and Full; Quick through
  `book_chapters`, as for members today), with skeletons worded for the parent (it defines the family layer and the
  policy; members keep it).
- family-check in a parent: `glyphs.own` is optional. Without it, every `shared` glyph must be present and well formed in
  the family source; `tiles` work as today (the parent lists every product's tile).
- Polygon glyphs: a glyph is either cells (unchanged) or a list of closed contours, each a list of `[x, y]` numbers
  (at least 3 points). Sources are still read, never executed (JSON, or a literal in a `.py`). `exact`: the same
  contours in the same order with the same points. `shape` (my call on the numbers): both normalised to their ink box
  (moved to 0,0, scaled so the longer side of the box is 128 px, aspect kept), filled even-odd at 128 px high in pure Python (no renderer),
  equal when at most 1 pixel in 1000 differs; the row names the count. One glyph as cells and the other as polygons
  fails, named. A malformed contour is exit 2, named.

## Tasks

1. **The value.** `scripts/state.py` (allowed values), `_common.needs_inventory` unchanged (a parent needs an inventory
   only in Full). Tests: `state --set architecture=family-parent` accepted and read back; a member value still works.
2. **BRAND.md.** `adaptlib/adapt.py` `BM_MAP["family-parent"]`; the modes table in `references/architecture.md` (a test
   ties the two). Tests: `adapters --brand-md` on a parent writes `master` / `branded-house`; the override still wins.
3. **The book.** `booklib/bookdata.py` family rule covers the parent; `book --init` copies parent-worded skeletons
   (`templates/book/family.parent.md`, `endorsement.parent.md`) for a parent. Tests: a Standard parent's chapters
   include both; a Quick parent's do only with `book_chapters`; `--init` writes the parent wording.
4. **family-check in the parent.** `scripts/family_check.py`: the parent is a family mode; `glyphs.own` optional there.
   Tests: a parent with shared glyphs all defined passes; one missing fails, named; a member without `own` is still a
   usage error; tiles across two products as today.
5. **Polygon glyphs.** `scripts/family_check.py` (kind detection by depth, even-odd fill, compare). Tests: an equal
   polygon glyph passes; a moved and scaled copy passes `shape` and fails `exact`; one point moved fails with a pixel
   count; cells against polygons fails; a contour of 2 points or a non-number is exit 2; a `.py` literal source works.
6. **Docs and release.** `scripts/CONTRACT.md` (state keys, family-check, chapters, BRAND.md pairing),
   `templates/FAMILY.md` (polygons, where it lives, `own` optional in a parent), `references/architecture.md` (the parent
   row, FAMILY.md's place), `references/phases/00-intake.md` and `skills/brand-creator/SKILL.md` (ask for the parent
   when the brief shows products under it), CHANGELOG, version 0.15.0 and its pins, the eval kit regenerated. Release
   by `docs/internals/release.md` (the full run on macOS and Linux before the tag), then the version to the Batler
   session.

## Not in this release

- Executing glyph code (Batler exports its `LETTERS` outlines to a JSON file itself).
- A member reading the parent's FAMILY.md directly instead of its own copy.
