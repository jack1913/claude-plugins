# ADR-0016: The kit records the brand's sort of its rules, and `kit status` names what a repository sorts differently

- **Status:** accepted
- **Date:** 2026-11-20
- **Source:** [ADR-0015](ADR-0015-the-kit-states-three-weights.md), its consequence on a rule that changes weight unseen and
  its "left for later" list (rules and their weights as structured data); [ADR-0014](ADR-0014-the-kit-installs-itself-and-updates-unchanged-owner-files.md)
  (an owner file a repository changed is kept); the code review of the kit weights before 0.13.0, which left this open for
  the owner; the owner's choice of 2026-11-20 between two answers (record the sort and name each line, or only flag the file);
  `scripts/adaptlib/kitcopy.py` (`sort_of`, `sort_differ`); the "kit status" section of the
  [script contract](../../scripts/CONTRACT.md).

## Context

ADR-0015 gave every line of a kit one of three weights and put the sort of the brand's rules in `golden-rules.md`. That
file is an owner file. ADR-0014 lets a product repository keep an owner file it changed: an update never copies over it,
and `kit status` still calls the copy current.

Together the two leave a hole. A product can move a rule from Fixed to Defaults, or delete it, and nothing says so.
`kit status` lists `golden-rules.md` among the owner files that differ, as it lists a recipe the product reworded, and
does not say that what changed is what binds every product.

Two answers were weighed. One only flags the file, which `kit status` already does. The other records the sort as data
and names each line.

## Decision

- **The build records the sort.** `kit.json` gets the key `sort`: three lists, `fixed`, `default` and `example`, holding
  the bullets and numbered lines of `golden-rules.md` without their list marker. The heading a line stands under is its
  weight; where no heading says it, the tag decides, as ADR-0015 set it. A line nobody sorted or tagged is fixed.
- **`kit status` names what a repository sorts differently.** It compares the record with the `golden-rules.md` the
  repository holds, and prints each line of the brand's sort that has another weight there or is no longer there, with
  both weights. `--json` holds the same as `sort_differ`. The kit's `install.py` is the same code and says the same when
  it runs.
- **The file stays the repository's.** It is not copied over, the copy stays current and the exit code does not change.
  The section names the difference; whoever maintains the brand decides what follows.
- **Lines are compared as text.** A reworded line reads as gone. A line the repository added is its own and is not named.
- **The key is optional when a `kit.json` is read.** A kit built before it has none, and then nothing is compared.

Rejected:

- Calling such a copy not current: an update keeps the file, so the copy could never become current again.
- Generating `golden-rules.md`: the sort is the owner's own words and decision, written line by line.
- Only flagging the file: the list of owner files that differ already does, and it does not say which rule changed.

## Consequences

- Whoever maintains the brand sees, at every `kit status` and every install, which rules a product re-sorted or dropped.
- `kitcopy.py` changes, and every kit carries it as `install.py`: the next build raises the version of every kit by one,
  and a product's copy reads as behind until it is updated.
- A version of the plugin from before this record refuses a `kit.json` that has the key. Update the plugin wherever kits
  are built or compared.
- Only the sort of `golden-rules.md` is recorded. The Fixed sections of the recipes and of `visual.md` are not.
- Nothing inside a product reads the record by itself: a product that never meets `kit status` or `install.py` again is
  not told. A check that ships inside the kit is still left for later; this record is the data it would read.
- The helpers that read the lines of an owner file (code fences, bullets, tags) moved into `kitcopy.py`, so `kit check`
  and the sort read a line by the same code.
