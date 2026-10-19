# ADR-0004: Own a hand-ported copy of upstream, never a live dependency

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commits `eb43096` (byte-for-byte import at 5.1.0), `199bb75` (first deviation), `69b90a4` (`upstream-diff.sh`); `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §1 goal 4, §2 "Relationship to upstream" row, §3, §6; `UPSTREAM.md`

## Context

`swift:swiftui` builds on AvdLee/SwiftUI-Agent-Skill (MIT). The plugin must not depend on any third-party repo at run time or for updates: upstream is read, never tracked (spec §1, goal 4). The owner's words were "not dependent in any way" (spec §2).

## Decision

Import upstream's `skills/swiftui-expert-skill/` byte-for-byte at tag `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`) as this repo's first commit, and tag it `upstream-5.1.0`. After that:
- Every change is its own commit with a row in `UPSTREAM.md` → Deviations, so `git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows every change inside the skill folder. The one repo-level deviation, the carried record_trace test in `maintenance/tests/`, is recorded only in `UPSTREAM.md` (spec §4 item 8).
- New upstream work arrives only by hand. `maintenance/upstream-diff.sh [ref]` clones upstream into a temp dir and prints the diff between the baseline recorded in `UPSTREAM.md` and `ref` (default: upstream's newest tag); it never writes to this repo. Someone ports what fits, bumps that baseline and adds a row to `UPSTREAM.md` → Ported.

Rejected (spec §2): `npx skills`, subscribing to upstream's own marketplace, and a git fork. Each keeps a runtime or update dependency on upstream, which goal 4 rules out.

## Consequences

- One diff against a fixed tag, plus the Deviations table, audits every change. Upstream's license travels with installs as `plugins/swift/skills/swiftui/LICENSE-upstream` and `plugins/swift/NOTICE.md`. `UPSTREAM.md` stays in this repo.
- After a port, the baseline in `UPSTREAM.md` moves on while the local `upstream-5.1.0` tag stays fixed. The Ported table records what came in between.
- Nothing updates by itself: without a periodic `upstream-diff.sh` run and a hand port, the copy misses upstream's fixes.
