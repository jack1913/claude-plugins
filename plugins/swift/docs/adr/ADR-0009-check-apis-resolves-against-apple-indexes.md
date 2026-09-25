# ADR-0009: check-apis resolves names against Apple's indexes; the manifest holds only what can't be derived

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commits `4287692`, `cc95797`, `de4dce1`, `f5aa263` (the `apicheck` package and `check-apis.py`), `c109762` (manifest seeded) and `3651bfa` (`Inspector` recorded as a finding, `CollectionID` given its own ignore reason); `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §1 goal 3, §2 "API check" row, §6 (`check-apis.py`), §8 (prototype run)

## Context

Every API the skills name must be checkable against Apple's documentation by one command (spec §1, goal 3). Upstream's snippets alone name about 1,300 API-shaped identifiers. A prototype run against Apple's framework indexes found 877 distinct names, of which 165 did not resolve: mostly example types, Instruments symbols, Info.plist keys and prose words, plus a handful of names Apple's index lacks (spec §8).

## Decision

`check-apis.py` looks up every API-shaped name in `plugins/swift/skills/**/*.md` in Apple's per-framework documentation indexes, automatically. `maintenance/apis.json` holds only what can't be derived:
- the frameworks to index;
- `apis` entries, each there for at least one reason: a recorded claim to verify against Apple's platform data (such as "not on visionOS" or "deprecated"), a doc page chosen among overloads, or a row in the generated platform table;
- an ignore list, grouped by reason, for names that don't resolve in Apple's index. These are example types, prose words and deliberate wrong spellings; Apple names that aren't index entries (Instruments runtime symbols, Info.plist keys, generic parameter names); and upstream API names Apple's index lacks. Only that last group is recorded as findings in `UPSTREAM.md`.

Rejected: a hand-written manifest mapping every name to its doc path, which at about 1,300 names would not pass `--strict` (spec §2).

## Consequences

- `load_manifest` rejects any top-level key beyond `frameworks`, `apis` and `ignore` (`maintenance/apicheck/manifest.py`), so a name catalogue could only grow inside `apis`. Review keeps entries there to the three reasons above.
- A new name in a skill that the same file does not declare (`extract.scan` skips declared names and `Self`, `Type`, `Protocol`, `Any`) either resolves in Apple's index or needs an ignore entry with a reason.
- `--strict` also fails on an ignore entry that no skill file uses any more, and on one that now resolves.
- Current sizes (`apis` entries, then ignored names) come from `python3 -c "import json; d=json.load(open('maintenance/apis.json')); print(len(d['apis']), sum(len(v) for v in d['ignore'].values()))"`.
