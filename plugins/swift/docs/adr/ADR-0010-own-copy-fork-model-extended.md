# ADR-0010: The own-copy fork model extends to the concurrency and testing upstreams

- **Status:** accepted
- **Date:** 2026-09-26
- **Source:** `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md` §2–§5; commits `145e4ad` (`upstream-diff.sh` skill argument), `d09e1e4` (per-upstream UPSTREAM.md sections), `a6a6a7f` (concurrency import at `2.3.0`, tag `upstream-concurrency-2.3.0`), `94a2f8c`/`51eccf8`/`754e64e` (day-one deviations), `6cd347e` (name resolution); ADR-0004 (the model this extends)

## Context

ADR-0004 decided `swift:swiftui` is an own copy of AvdLee's SwiftUI skill: byte-for-byte import tag, every change a commit with an `UPSTREAM.md` Deviations row, porting by hand. The same author publishes `Swift-Concurrency-Agent-Skill` (MIT, `2.3.0`) and `Swift-Testing-Agent-Skill` (MIT, `1.2.0`), the bases for `swift:concurrency` (this release) and `swift:testing` (next). The single-upstream machinery — one baseline line in `UPSTREAM.md`, `upstream-diff.sh` with a hard-coded repo and folder — did not survive a second upstream.

## Decision

Run every fork through the ADR-0004 model, per upstream:

- `UPSTREAM.md` carries one section per upstream (`## SwiftUI`, `## Concurrency`, `## Testing`), each with its own Upstream/Baseline/Local-import-tag lines and its own Deviations, Ported and Findings tables.
- `maintenance/upstream-diff.sh` takes a required skill argument (`swiftui|concurrency|testing`) that selects repo URL, skill folder and section; no argument is an error, not a default. `UPSTREAM_DIFF_URL` and a new `UPSTREAM_MD` env seam keep it testable offline (`maintenance/tests/test_upstream_diff.py`).
- The day-one deviation set travels: frontmatter `name:` matching the plugin namespace, `${SKILL_DIR}` → `${CLAUDE_SKILL_DIR}` where present, `agents/`+`assets/` deleted where present, `LICENSE-upstream` inside the skill folder, a NOTICE.md entry pinning tag and SHA.
- Before its release, each fork gets the report-only claim audit (auditors + independent verifier against Apple doc JSON, SDK interfaces and `swiftc -typecheck`), and confirmed findings become fix commits with Deviations rows — the 0.1.3 precedent.
- Authored additions to a fork land only where the audit finds a gap, as deviations inside the upstream files, never as parallel sections (part-2 spec §2 "audit-first").

Rejected: one combined upstream section (loses per-repo baselines), and a tracking fork/subscription (ADR-0004 already rejected the dependency).

## Consequences

- Three baselines to keep straight; each Findings-open ignore group in `apis.json` names its section ("…see UPSTREAM.md Findings — Concurrency"), per ADR-0009's model.
- Adding a fourth upstream later means one more case arm, one more section, one more NOTICE entry — no structural change.
- `swift:concurrency`'s framework coverage widened `apis.json` (`coredata`, `xctest`, `testing`), which also serves the upcoming `swift:testing` fork.
