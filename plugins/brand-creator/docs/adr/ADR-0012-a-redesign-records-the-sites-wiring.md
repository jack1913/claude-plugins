# ADR-0012: A redesign records the site's wiring

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** [ADR-0007](ADR-0007-brand-side-of-the-web.md) (the record a redesign keeps is left to its own ADR, and the page
  check's loopback rule); "adoption" under "Adoption, cascade, adapters, applied skill and launch" in the
  [script contract](../../scripts/CONTRACT.md) (the survey's read-only proof, the kept list, `adoption.json`); the
  [adoption phase](../../skills/brand-creator/references/phases/11-adoption.md); the
  [brand-adopt skill](../../skills/brand-adopt/SKILL.md); the [changelog](../../CHANGELOG.md). Files this decision adds,
  named here and not linked because they do not exist yet: `scripts/adaptlib/wiring.py`, `scripts/pagelib/wiring.mjs`, the
  `wiring` subcommand of `scripts/adoption.py` and the `wiring` subcommand of `scripts/render.mjs`.

## Context

A product's site depends on things that are not brand: where its links point, the names of its form fields, its event
handlers, the hooks its tests and analytics use, the ids that scripts and anchors reach for, and the scripts it loads. A
redesign rewrites the markup and can drop or rename any of them. A form field that lost its name breaks the back end that
reads it. A test hook that went missing breaks the repository's end-to-end tests. An analytics attribute that was not carried
over ends a measurement without an error.

The adoption list is built from what carries the old brand: names, colours, icon paths, metadata and badges. It says what
must change. Nothing in it says what must stay, and `check --cascade` looks for old values that remain, not for things that
went missing. So a redesign can lose wiring and nothing in the project would notice.

[ADR-0007](ADR-0007-brand-side-of-the-web.md) left the record a redesign keeps to its own decision. This is that record.

## Decision

- **A command that records the wiring.** `brand-creator adoption wiring --repo <label>`, with `--before` or `--after`, reads
  a surveyed repository and records six kinds of item. Each item is `kind:value`, with the value cut at 120 characters, and
  the record keeps up to five files that held it.
  - `link`: where a link, a form or a router link points.
  - `field`: the name of a form field.
  - `handler`: an event-handler attribute and its value.
  - `hook`: a test or analytics hook, such as `data-testid` or a `data-track` attribute.
  - `id`: a fixed element id.
  - `script`: a script file a page loads.
- **Two sources.** The source files of the repository, read with patterns, and the pages the owner serves on their own
  machine, read from the rendered DOM with `--page <url>`. A page URL must be on `127.0.0.1`, `localhost` or `[::1]`, by the
  one loopback rule the page check uses ([ADR-0007](ADR-0007-brand-side-of-the-web.md)); anything else is refused. The
  rendered read is optional.
- **Files are chosen as the survey chooses them.** The scan lists files as the survey does (`.gitignore` honoured, `.git`
  left out) and leaves out what the survey keeps out: lock files, change history, licence text, minified output, `dist` and
  `build` folders, and vendored code. Generated and vendored files are not wiring the redesign owns.
- **Before is the baseline.** `--before` stores the record and refuses to replace one unless `--again` is passed. `--after`
  needs a before record.
- **The record lives in `adoption.json`, under `wiring`.** There is one entry per surveyed repository, holding its before,
  its after and what was dropped. The key `kept` is taken: it is the survey's list of lines left out of the count, with
  reasons. `wiring` joins the keys that hold a repository's own values, so `check --cascade` never counts them as leftovers
  of the old brand, and `verify` checks the shape.
- **A loss is acceptable only as dropped, with a reason.** A loss is an item of the before record that the repository no
  longer has and nobody dropped. `--drop "ITEM::REASON"` records a drop. The item must be in the before record, and the
  reason is the owner's, in their words, and never empty. Claude does not write a reason for the owner.
- **The reviewer's live comparison.** `--compare` reads the repository now, and the recorded pages again, and writes nothing.
  It lists the lost items with the files they were in, the dropped items with their reasons, and the count of new items.
  It exits 1 on a loss that is not recorded as dropped. The brand-adopt reviewer runs it, and an unrecorded loss fails the
  review.
- **`check` gates the stored record.** A repository with both records gets the row `adoption:wiring:<label>`. It fails when
  the recorded after-scan lost an item that nobody dropped, and names some of them. With only a before record it is an info
  row that says to record `--after` when the redesign is applied.
- **`ADOPTION.md` shows it.** A "Wiring kept" section gives the counts per kind, before and after, and one line per lost
  item: dropped with its reason, or lost and not recorded. A line that holds a repository's value carries the target-repo
  marker. The template's fixed text does not change, and an adoption list with no wiring renders the bytes it rendered
  before.
- **Scripts only read the repository, and prove it.** The scan needs no gate, as the survey needs none, because it changes
  nothing outside the project. Like the survey it lists the files with sizes and modification times before and after; a
  difference fails the row `read-only:<label>`, exits 1 and stores nothing. The edits to the repository are the
  implementer's, never a script's.

## Consequences

- Extraction by pattern is approximate. Dynamic routes, generated ids and values built at run time give noisy items or
  none. A noisy item is dropped with a reason, which costs one line and keeps the record honest. Wiring the patterns never
  see is not protected.
- The record is not a proof that the site works. A redesign that keeps every recorded item can still break, and the
  repository's own tests stay the proof.
- The record is only as good as the moment of `--before`: it has to be taken before the first change. A baseline replaced
  with `--again` after edits protects the edited site, not the original.
- Listeners that a script adds at run time are not in the DOM, so they are read from source only. A recorded page that
  cannot be read stops the run as not verified and stores nothing.
- Adoption lists without wiring are unchanged: the same rows, the same `check` results and the same `ADOPTION.md` bytes.
- A redesign adds a step for the reviewer, and each drop is a decision of the owner, recorded with its reason.
- Credit, idea only, rewritten here and not copied: Hallmark (MIT licence, "Hallmark contributors"), commit 4f6a46c, whose
  `references/redesign.md` ("The wiring") keeps a before-and-after record of what a redesign must keep. The six kinds, the
  extraction patterns and the code are written here. Hallmark is not installed, bundled, forked or bridged.
