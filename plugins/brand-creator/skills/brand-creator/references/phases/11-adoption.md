# P11 Adoption

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Method](#method)
- [A parent site that shows the product](#a-parent-site-that-shows-the-product)
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

Every place a product repository shows the old brand is a numbered row, or is listed as kept with its reason, so adoption has no unlisted
corner. The agent surveys read only, lists, and changes nothing until the owner asks (G6).

## Inputs

- The approved pack (`assets/manifest.json`), the book, `INVENTORY.md` (the slots, the deployment targets, the incumbent), G5 recorded.
- The target repositories, read only. Before G6 nothing in them is edited, whatever the owner says in passing.
- The old names (a name, its short form, its slug) and the old colours (hex), from the incumbent in BRAND-STATE.md and INVENTORY.md.

## Outputs and paths

| Output | Path |
|---|---|
| The rows, progress, pins, kept list, identifiers | `adoption.json` |
| The document the owner reads, rendered from it | `ADOPTION.md` (never edited by hand) |
| The survey's report | `assets/_checks/adoption.json` |
| Changes in the product repositories | on a branch of each repository, after G6 only |

## Method

1. `brand-creator adoption survey --repo <dir>=<label> [--repo ...] --old-name "<Old Name>" --old-colour "#rrggbb" [--keep "<glob>::<reason>"]`.
   It reads each repository with ripgrep (respecting `.gitignore`) for old names (with their hyphen, underscore and joined forms, any case), old
   colours (hex, `rgb()`), icon and logo files (grouped by folder), package and platform metadata (package.json, Cargo.toml, plists, Tauri,
   AppStream, web manifests, Android, .desktop), and README badges. Lock files, change history, licence text, minified output and generated folders
   go on "Kept, not counted" with the reason; `--keep` adds the owner's own exceptions. A match is a row or kept: the report's `accounting` row
   fails otherwise.
2. Read `ADOPTION.md`. Rows are numbered, in a group, with the file, the lines and a **Find** excerpt: **line numbers drift, so find the place by
   its content**. The counts in the status sentence are computed, never typed.
3. Add what no search finds, one row at a time: `adoption add --repo <label> --file <path> --find "<text>" --change "<sentence>"` (a tray rule
   the repository gets wrong, a platform size it states wrongly: the pack follows the platform's page, and the drift becomes a row).
   For a redesign of an existing site, record what it is wired to before any change: `adoption wiring --repo <label> --before [--page <local URL>]`
   (links, form field names, handlers, test hooks, ids and scripts, from the source and from pages of the owner's own local server; read only, no
   gate). The record is the baseline: it is replaced only with `--again`, on the owner's word.
4. Show the owner the list and the counts. Record G6 only on the owner's explicit ask: `state --record G6 "<what was asked>"`.
5. After G6, apply with [the brand-adopt skill](../../../brand-adopt/SKILL.md) (`/brand-creator:brand-adopt apply`), on a branch
   **the owner names**, one repository at a time: one implementer per repository (single-thread by default; a subagent per
   repository only after the fleet gate, never two in one working tree), then an independent review, then a fix pass for the
   findings that need no decision, then the owner's decisions. Mark progress as it happens: `adoption status --set 1-5=doing`,
   then `done` when committed (the owner's call; `doing` is made in the working tree and not committed). Survey again from time
   to time: a row marked done that still matches is flagged.
   A Brand kit row (added when the project has a kit and the owner wants it in a repository: `adoption add --repo <label> --kit`):
   run `kit status --repo <path>` and copy exactly the files of its copy list (`mkdir -p` then `cp`, one file at a time; an owner
   file the repository already has is never overwritten), then `kit status --repo <path>` must say current. Never copy into
   `~/.claude/skills` or any global folder. The kit is not committed.
   A redesign of an existing site: the implementer ends with `adoption wiring --repo <label> --after` (the same `--page` URLs, or none to
   read the pages of the before record again; the owner's local server must be running, and a page that cannot be read is reported, never
   skipped). It never records a before or a drop.
6. The review proves the work: lockups and files copied from the pack are byte-compared with the pack (`cmp`) and size-checked
   in the target; the repository's own build and tests run, and their commands and exit codes are quoted; the product is built
   and run to see the real icon where the platform allows it. A check that needs a real device is listed "not verified". Never
   skip a repository's own hooks (`--no-verify`): an unrelated failing hook is reported, and fixed as a separate change only if
   the owner agrees.
   For a Brand kit row, `kit status --repo <path>` exit 0 is the byte comparison.
   For a redesign, `adoption wiring --repo <label> --compare` reads the repository now and writes nothing: an item of the before record that is
   gone and not recorded as dropped fails the review. The item is put back, or the owner decides it goes and says why; the lead records that with
   `adoption wiring --repo <label> --drop "<item>::<the owner's reason>"`, in the owner's words. Neither the implementer nor the reviewer records a drop.
7. Commit, merge and push are three separate asks, each answered by the owner. Before a push, read the target's CI, deploy and
   publish configuration and say what the push triggers and what cannot be undone. Rows that act on a live service (renaming a
   repository, a hosted service or an app id, an upload, a DNS change, a store listing) need their own OK, apart from the apply
   ask; most are owner steps in LAUNCH.md.
8. When a product's pages are built, run the page check on them: `page-check <page>`, `page-check --from <dir> <page>` or
   `page-check --url http://localhost:<port>/<path>` (see [09-qa](09-qa.md)). It reports colours, type, the mark, motion and claims against
   the brand, and warns about generic patterns; it changes nothing in the product.

### A parent site that shows the product

The parent brand's site uses the product's own pack files, byte for byte; a product without a pack gets no placeholder, it is
listed as missing. Preview the variants in a scratch copy of the site (copy, build, shoot, read the shots) before its source is
touched, and let the owner pick. Propose a build check in the site that fails on a missing lockup, a size mismatch, a wrong embed
or a lockup that is never shown; it is added only if the owner agrees.

## Gate

**G6 Adoption.** An explicit ask; work on a branch; `adoption status --set ... doing|done` needs G6 recorded (exit 1 without it); commit, merge and
push are separate asks. The survey and `adoption add` do not touch a repository and need no gate.

## Pitfalls

- Treating the survey as the whole job: it finds slots by search. Behaviour a search cannot find (a tray that picks its icon at runtime, a size a
  platform wants) is a hand-written row.
- Editing `ADOPTION.md` or `adoption.json` by hand: `check` fails a document that is not what the data renders, and a row inserted, moved or removed
  fails the pins.
- Counting a row done because the work was started: `doing` is the working tree, `done` is committed.
- Renaming identifiers (a bundle id, a package name, a repository) as if they were copy: they are outward steps, listed in LAUNCH.md.

## Enforcement

- The survey proves it wrote nothing in a repository (`read-only:<label>`: the list of files, sizes and times before and after).
- `adoption verify` and `check` (`adoption:data`): the pins, the numbering, the accounting and that ADOPTION.md is what adoption.json renders.
- `check --cascade "<old name>"` treats the adoption rows as the work list (a warning), not as a leftover.
- A Brand kit row is proved by `kit status --repo <path>` (read only, writes nothing in the repository): exit 0 means every
  generated file of the copy is the project's bytes; the owner files are the repository's and are never overwritten.
- A redesign's wiring is recorded by `adoption wiring` (read only, and it proves it: `read-only:<label>`). `--compare` exits 1 on a loss nobody
  dropped with a reason, a review with such a loss fails, and `check` fails a recorded `--after` that lost wiring nobody dropped
  (`adoption:wiring:<label>`). The record is not proof that the site works: the repository's own build and tests stay the proof.
- Proven by `test_adoption.py` (see the table in [09-qa](09-qa.md)).
