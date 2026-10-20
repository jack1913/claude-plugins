# Part 2, Plan 2: `swift:testing` (0.1.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fork AvdLee/Swift-Testing-Agent-Skill as `swift:testing`, audited and eval-covered, released as 0.1.5.

**Architecture:** The Plan 1 machinery already handles a third upstream (`upstream-diff.sh testing`, a `## Testing` section slot, `testing` and `xctest` in `apis.json` frameworks). This plan imports `swift-testing-expert/` byte-for-byte at `1.2.0`, lands day-one deviations as separate commits, gets `check-apis --strict` green, runs the claim audit with the ADR-0010 method (`swiftc -emit-sil`, plus `swift test` in scratch packages for runtime claims), fixes confirmed findings, wires the concurrency ↔ testing routing, adds two eval cases, and releases. Plan 3 (`swift:review` → 0.1.6) is written after this ships.

**Tech Stack:** git tags, `maintenance/check-apis.py`, `swiftc -emit-sil`, `swift test` (SwiftPM, Swift Testing), `claude plugin eval`, the Workflow tool for the audit.

**Spec:** `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md` (§2 decisions, §5 testing, §7 verification, §8 surfaces, §9 releases) and ADR-0010 (the fork model and audit method). Read both before executing.

## Global Constraints

- Names are fixed: marketplace `swift-plugin`, plugin `swift`; after Task 7 the skills are `swift:swiftui`, `swift:design`, `swift:concurrency`, `swift:testing` (AGENTS.md §4).
- Every change under `plugins/swift/skills/testing/` or `plugins/swift/skills/concurrency/` is its own commit with its `UPSTREAM.md` Deviations row, in that upstream's section, **in that commit**. Stage the row edit immediately before its own commit and check `git show --stat HEAD` lists `UPSTREAM.md` (Plan 1 slipped twice).
- Upstream-derived files are edited with shell tools or the Edit tool, never by rewriting whole files with Write; the user's formatter hook reformats Write output.
- Run `python3 maintenance/check-apis.py --strict` **after every commit** that touches a skill or `apis.json` (Plan 1 left it red across several commits). Every ignore entry carries a true reason; API names Apple's index lacks get a Findings row in the Testing section.
- Compiler evidence uses `swiftc -emit-sil -o /dev/null -swift-version 6` (ADR-0010); a Sema error in the same file suppresses the SIL passes, so check each claim in its own file. Behavioural claims about Swift Testing (parallelism, `.serialized`, `confirmation` counts, `#require` flow) are verified with `swift test` in a scratch package.
- A fix to a fix is re-verified at runtime when the defect is behavioural (Plan 1's observation and download-manager fixes were compile-clean and still wrong).
- Local commits are authorized by accepting this plan. **Pushes are not**: ask the user at Task 10.
- Release: `changelog-release` → commit → `claude plugin tag plugins/swift --dry-run` then without → push only with the user's OK.

## Review Focus

1. The import must stay byte-for-byte: `git diff upstream-testing-1.2.0 -- plugins/swift/skills/testing` explained entirely by Deviations rows (pinned by Task 1's `diff -r` step and Task 9's coverage check).
2. The concurrency and testing skills must not both answer the same request: authoring and migrating tests route to `swift:testing`, diagnosing async-test failures to `swift:concurrency` (pinned by Task 6's description and cross-reference steps and Task 8's `skill-fired` graders naming `testing`).
3. An eval case whose graders reject a correct test or accept a broken one misleads every later run: each grader set is checked against a matrix of good and bad sample solutions before the eval runs (pinned by Task 8 Step 3, the Plan 1 lesson).
4. `check-apis --strict` must not be silenced with unjustified ignore entries, and must be green at every commit (pinned by Task 3 and the Global Constraints rule).
5. Runtime claims (for example "tests run in parallel by default", "`.serialized` runs a suite's tests one at a time", "`confirmation` fails when the count is wrong") must be verified by running tests, not by reading prose (pinned by Task 4's audit brief).

---

### Task 1: Byte-for-byte import, local tag, Testing section, NOTICE

**Files:**
- Create: `plugins/swift/skills/testing/**` (copied, never hand-written)
- Modify: `UPSTREAM.md` (new `## Testing` section after `## Concurrency`)
- Modify: `plugins/swift/NOTICE.md` (new entry)
- Modify: `.claude/skills/update-docs/SKILL.md` (REPO SPECIFICS `UPSTREAM.md` row: add the testing diff command)

**Interfaces:**
- Consumes: `maintenance/upstream-diff.sh testing` (arm already maps to `swift-testing-expert`).
- Produces: local tag `upstream-testing-1.2.0`; folder `plugins/swift/skills/testing/`; the Testing section Tasks 2–6 write rows into.

- [ ] **Step 1: Re-verify the tag and SHA**

```bash
rm -rf "$TMPDIR/test-upstream" && git clone --quiet https://github.com/AvdLee/Swift-Testing-Agent-Skill "$TMPDIR/test-upstream"
git -C "$TMPDIR/test-upstream" tag --list | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1   # expect 1.2.0
git -C "$TMPDIR/test-upstream" checkout --quiet 1.2.0 && git -C "$TMPDIR/test-upstream" rev-parse HEAD
```

Expected: `1.2.0` and `798e9b1a2bcac164d4f0c781908199e754f0bab6` (planning-time values, 2026-09-27). If a newer plain tag exists, use it everywhere below.

- [ ] **Step 2: Copy and verify byte-fidelity**

```bash
cd <home>/Dev/claude_skills/swift-plugin
cp -R "$TMPDIR/test-upstream/swift-testing-expert" plugins/swift/skills/testing
diff -r "$TMPDIR/test-upstream/swift-testing-expert" plugins/swift/skills/testing && echo BYTE-FOR-BYTE
```

Expected: `BYTE-FOR-BYTE`.

- [ ] **Step 3: Add the Testing section to UPSTREAM.md** (Edit tool, after the Concurrency section's Findings table):

```markdown
## Testing

- **Upstream:** https://github.com/AvdLee/Swift-Testing-Agent-Skill, folder `swift-testing-expert/`, MIT
- **Baseline tag:** `1.2.0` (`798e9b1a2bcac164d4f0c781908199e754f0bab6`)
- **Local import tag:** `upstream-testing-1.2.0`, the import commit: the folder byte-for-byte at the baseline

`git diff upstream-testing-1.2.0 -- plugins/swift/skills/testing` shows every change listed under Deviations.

### Deviations

| File | Change | Why |
|---|---|---|

### Ported

| Upstream ref | What we took | Date |
|---|---|---|
| `1.2.0` | Initial import | <execution date> |

### Findings

Names upstream uses that Apple's documentation index did not have at import time. While a row is open, `check-apis.py` ignores its name in the `apis.json` ignore group "upstream names not in Apple's index (see UPSTREAM.md Findings — Testing)", re-created when a row needs it. Status says what was decided: **Fixed**, **Resolved** or **Open** (with the reason it stays).

| Name | Upstream file | Nearest Apple API | Status |
|---|---|---|---|
```

- [ ] **Step 4: NOTICE.md entry** after the Swift-Concurrency entry, same shape, license text copied from `$TMPDIR/test-upstream/LICENSE` (planning-time copyright line: `Copyright (c) 2026 Antoine van der Lee`):

```markdown
## AvdLee/Swift-Testing-Agent-Skill

- Source: https://github.com/AvdLee/Swift-Testing-Agent-Skill at `1.2.0` (`798e9b1a2bcac164d4f0c781908199e754f0bab6`)
- Taken: `plugins/swift/skills/testing/`, which is upstream's `swift-testing-expert/` with the changes the repository's `UPSTREAM.md` lists. Files marked "New" there are this project's own.
```

plus the fenced MIT text.

- [ ] **Step 5: update-docs row** — in `.claude/skills/update-docs/SKILL.md` REPO SPECIFICS, extend the `UPSTREAM.md` row with `` `git diff upstream-testing-1.2.0 -- plugins/swift/skills/testing` (Testing section) ``.

- [ ] **Step 6: Verify, commit, tag**

```bash
maintenance/upstream-diff.sh testing | head -3      # baseline: 1.2.0 -> ref: 1.2.0
git add plugins/swift/skills/testing UPSTREAM.md plugins/swift/NOTICE.md .claude/skills/update-docs/SKILL.md
git commit -m "feat(testing): import AvdLee Swift-Testing-Agent-Skill 1.2.0 byte-for-byte"
git tag upstream-testing-1.2.0
git diff upstream-testing-1.2.0 -- plugins/swift/skills/testing | wc -l   # 0
```

### Task 2: Day-one deviations (two commits)

**Files:** `plugins/swift/skills/testing/SKILL.md` (frontmatter), `plugins/swift/skills/testing/LICENSE-upstream` (new), `UPSTREAM.md` (a row per commit).

**Interfaces:**
- Produces: skill named `testing` (`/swift:testing`) with a house-style description; the license travelling with installs.

Not applicable here (verified at planning time): no `${SKILL_DIR}` occurrences, no `agents/` or `assets/`. Record both as "not needed" in the execution notes, not as rows.

- [ ] **Step 1: Frontmatter** — `name: swift-testing-expert` → `name: testing`; replace the description (single-quoted YAML in upstream; keep valid YAML) with:

```yaml
description: 'Use when writing, migrating, or reviewing Swift tests: Swift Testing (@Test, @Suite, #expect, #require, traits, tags, parameterized tests with arguments:, confirmation for events), test plans and parallel execution, and migrating XCTest suites (XCTestCase, XCTAssert, XCTestExpectation) to Swift Testing or deciding what stays on XCTest. Also use for flaky or slow tests and test structure. For diagnosing concurrency errors in async test code, use swift:concurrency.'
```

Row: `| SKILL.md frontmatter | name: testing; description rewritten in the house "Use when …" style, keeping upstream's topics, dropping "Apple-platform or Swift server projects", and routing async-concurrency diagnosis to swift:concurrency | Plugin skill command is /swift:<name>; the concurrency fork under-triggered with upstream's style of description (UPSTREAM.md Concurrency → SKILL.md frontmatter row) |`. Verify: `claude plugin validate plugins/swift` passes and `head -4` shows the new frontmatter. Commit `feat(testing): rename the skill to testing and word its description for triggering`.

- [ ] **Step 2: LICENSE-upstream** — `cp "$TMPDIR/test-upstream/LICENSE" plugins/swift/skills/testing/LICENSE-upstream`; `diff` against upstream (no output). Row: `| LICENSE-upstream | New: upstream's MIT license text, verbatim | Travels with every install (the plugin cache copies only plugins/swift/) |`. Commit `docs(testing): carry upstream's MIT license inside the skill`.

- [ ] **Step 3:** `git diff upstream-testing-1.2.0 --name-only -- plugins/swift/skills/testing` → exactly `SKILL.md` and `LICENSE-upstream`.

### Task 3: `check-apis --strict` green

**Files:** `maintenance/apis.json`; `UPSTREAM.md` (Testing Findings, if any).

- [ ] **Step 1:** `python3 maintenance/check-apis.py --refresh --strict > "$TMPDIR/strict-t.log" 2>&1`; collect the unresolved names: `grep '^WARN' "$TMPDIR/strict-t.log" | sed -E "s/^WARN unresolved [a-z ]+'([^']*)'.*/\1/" | sort -u > "$TMPDIR/unres-t.txt"`.
- [ ] **Step 2:** For each name, check it first: `python3 maintenance/check-apis.py --find <name>`, and for anything that looks like a real API, the doc JSON (`curl -s https://developer.apple.com/tutorials/data/documentation/testing/<path>.json`). Classify per ADR-0009 into the existing groups (example types; prose words; package symbols; Apple names that are not index entries; compiler flags). A **real API name that doesn't resolve** is a Findings row (Status Open, with the 404/index evidence), never a prose word. `Publishers.CombineLatest2` in Plan 1 is the precedent for what goes wrong when a fake API is filed under a generic group.
- [ ] **Step 3:** Write the entries with an exact-coverage assertion (assigned set == unresolved set), as Plan 1 Task 6 did; re-run `--strict` → `0 failures, 0 warnings`; unit tests OK. Commit `feat(maintenance): resolve the testing fork's API names against Apple's indexes`.

### Task 4: Claim audit (report-only workflow)

**Files:** none (report-only; scratch under `$TMPDIR`).

**Interfaces:**
- Produces: CONFIRMED / REFUTED / UNVERIFIABLE findings with evidence, for Task 5.

- [ ] **Step 1: Launch the workflow** — fleet 4 (3 sonnet auditors + 1 opus verifier), stated to the user before launch. Shards: (a) `SKILL.md`, `references/_index.md`, `fundamentals.md`, `expectations.md`; (b) `traits-and-tags.md`, `parameterized-testing.md`, `parallelization-and-isolation.md`; (c) `async-testing-and-waiting.md`, `migration-from-xctest.md`, `performance-and-best-practices.md`, `xcode-workflows.md`. Brief = the Plan 1 audit brief with three changes from its lessons:
  1. compiler checks use `swiftc -emit-sil -o /dev/null -swift-version 6`, one claim per file, never `-typecheck`;
  2. runtime and behaviour claims are verified by running them: a scratch SwiftPM package (`swift package init --type library`, a `testTarget`, `swift test`, and `swift test --parallel` or `--no-parallel` as the claim needs), with the command and the decisive output line as evidence;
  3. Swift Testing APIs come from the `Testing` swiftinterface (`$(xcrun --show-sdk-platform-path)/Developer/usr/lib/swift/...` or the toolchain's `lib/swift/macosx/Testing.swiftmodule`, found with `find` at audit time) and Apple's `documentation/testing` doc JSON.
  The verifier brief also gets these three rules and must re-run every "compiles clean" or "no diagnostic" claim with `-emit-sil`.
- [ ] **Step 2:** If any shard returns no structured output, re-run that shard alone (Plan 1 shard A precedent) before closing the task. Summarize confirmed findings by severity for the user before Task 5.

### Task 5: Fix confirmed findings

**Files:** as the findings name, under `plugins/swift/skills/testing/`; `UPSTREAM.md` rows; `apis.json` pins where a fix makes a platform statement.

- [ ] **Step 1:** Re-verify each finding yourself first (the verifier's "compiles clean" verdicts were wrong four times in Plan 1). Group fixes by file. For each file: write the failing evidence (old snippet fails, or the runtime harness shows the wrong behaviour), apply the fix, show the fixed form passes under `-emit-sil` (or at runtime), add the row (marked "**Upstream bug, worth reporting upstream:**" with command + decisive output + date), stage and commit in one step, then `check-apis --strict`.
- [ ] **Step 2: Gap-filling (audit-first, spec §5)** — upstream's `references/migration-from-xctest.md` → "Coexistence strategy" already lists what stays on XCTest (`XCUIApplication`, `XCTMetric`, Objective-C-only tests). Add guidance only if the audit finds a real gap, as an edit inside that file with its row. Otherwise record "no bridge addition needed: upstream covers it" in the execution notes.

### Task 6: Concurrency ↔ testing routing (deviations in both forks)

**Files:** `plugins/swift/skills/concurrency/SKILL.md` (description, and the `references/testing.md` router line), `plugins/swift/skills/concurrency/references/testing.md` (a cross-reference line at the top), `UPSTREAM.md` (Concurrency rows).

**Interfaces:**
- Consumes: `/swift:testing` existing (Task 2).
- Produces: the routing split spec §4 prescribes: async-test diagnosis → concurrency, test authoring/migration → testing.

- [ ] **Step 1: Cross-reference** — at the top of `concurrency/references/testing.md` (after its H1), add: `> For writing or migrating tests in general (Swift Testing structure, traits, parameterized tests, XCTest migration), see the swift:testing skill. This file covers testing concurrent code: async waiting, confirmations, actor isolation and leak checks.` Row in the Concurrency section. Commit `fix(concurrency): point testing.md at swift:testing for general test authoring`.
- [ ] **Step 2: Description** — in `concurrency/SKILL.md`'s description, replace `, and testing async code.` with `, and diagnosing hanging, flaky or data-racing async tests (for writing or migrating tests, use swift:testing).`. Extend the existing Concurrency `SKILL.md frontmatter` row. Commit `fix(concurrency): route test authoring to swift:testing in the description`. Validate the plugin.

### Task 7: ADR-free registry surfaces

ADR-0010 already covers the testing upstream, so no new ADR.

**Files:** `AGENTS.md` (§1 identity, §3 pointer row, §4 names and forked-skill list), `README.md` (skill table, Licenses line), `plugins/swift/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (description), `docs/manual/getting-started/enable-in-a-swift-repo.md` (prose "three skills" → "four", skill table row, the "From …SKILL.md" line), `docs/manual/work-on-it.md` ("Change a forked skill" list), `.claude/skills/update-docs/SKILL.md` if the cross-surface integrity row needs the new skill.

- [ ] **Step 1:** Apply the edits (Edit tool). Description for both manifests: `"Correct, current, Apple-native Swift: swift:swiftui (APIs and correctness, visionOS, previews), swift:design (Apple-native design), swift:concurrency (Swift 6 concurrency) and swift:testing (Swift Testing and XCTest migration)."` README row: `| swift:testing | Swift Testing: @Test, #expect/#require, traits, parameterized tests, parallel execution, XCTest migration. A fork of [AvdLee/Swift-Testing-Agent-Skill](https://github.com/AvdLee/Swift-Testing-Agent-Skill) (UPSTREAM.md) |`.
- [ ] **Step 2:** `rg -n 'three skills|swift:concurrency\)' docs README.md AGENTS.md` finds no stale "three skills" wording; `claude plugin validate plugins/swift` and `.` pass; check-docs and check-instructions exit 0. Commit `docs: register swift:testing across AGENTS, README, the manual and the manifests`.

### Task 8: Eval cases (2), grader matrix first

**Files:** `plugins/swift/evals/parameterized-slug-tests/**`, `plugins/swift/evals/callback-confirmation-test/**`.

Harness facts, established in Plan 1 (don't re-discover them): `regex` graders read one file (`target: { source: file, path: … }`) and support `match: not_contains`. `target: files` matches changed file **paths**, not contents. `llm` graders take no `target` key (it's rejected at load time, and the case is silently dropped from full runs) and judge only the final reply. There is no build grader. `--case` takes one glob.

- [ ] **Step 1: Case `parameterized-slug-tests`** — scaffold: a Swift 6 package (`// swift-tools-version: 6.0`, `platforms: [.macOS("14.0")]`, target `Demo`, `testTarget(name: "DemoTests", dependencies: ["Demo"])`), `Sources/Demo/Slug.swift` with `public func slugify(_ s: String) -> String` (lowercase, trim, spaces and punctuation → `-`, collapse repeats), and an empty `Tests/DemoTests/.gitkeep`. Prompt: "Add tests for slugify in Tests/DemoTests/SlugTests.swift covering these cases: "Hello World" → "hello-world", "  Trim  me  " → "trim-me", "Swift & SwiftUI!" → "swift-swiftui", "already-slug" → "already-slug", "" → "". Use the project's test framework." Graders:
  - `import Testing`;
  - `@Test\([^)]*arguments:` (one parameterized test, not five copies);
  - not_contains `XCTestCase|XCTAssert`;
  - `skill-fired` with `"(?:swift:)?testing"`.
- [ ] **Step 2: Case `callback-confirmation-test`** — scaffold: the same package, with `Sources/Demo/Saver.swift`: `public final class Saver: Sendable { public init(onSave: @escaping @Sendable (Int) -> Void) {…}; public func save(_ n: Int) { DispatchQueue.global().async { onSave(n) } } }`. Prompt: "In Tests/DemoTests/SaverTests.swift, test that save(3) calls onSave exactly once with 3, using Swift Testing." Graders:
  - `confirmation\(` (Swift Testing's event confirmation);
  - not_contains `Task\.sleep|sleep\(|XCTestExpectation|usleep`;
  - `skill-fired` with `testing`.
- [ ] **Step 3: Grader matrix before any eval run (Review Focus 3).** For each case, write 3–4 sample solutions into `$TMPDIR/gr-t/<sample>/Tests/DemoTests/…`: a correct one, a correct alternative, and 2 wrong ones (XCTest; five copy-pasted `@Test`s; `Task.sleep` waiting; a continuation-based test that doesn't check the count). Run each good sample with `swift test` in a copy of the scaffold (it must pass), and run the grader regexes over every sample (the Plan 1 `grade.py` approach, rewritten into `$TMPDIR`). Good samples must pass every grader and bad ones must fail at least one. Fix the graders until the matrix is right, not the samples.
- [ ] **Step 4: Run and iterate:**

```bash
claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --threshold 0.67 --max-cost-usd 8 --allow-tools Write Edit --case parameterized-slug-tests
claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --threshold 0.67 --max-cost-usd 8 --allow-tools Write Edit --case callback-confirmation-test
```

  Acceptance: WITH ≥ 0.67 and the skill fires in every WITH run. Delta > 0 is the goal. If a WITHOUT arm passes, try one harder prompt variant per case (at most 2 runs each). If the delta is still 0, report to the user, who decides (Plan 1 precedent: option A, keep as regression guards and say so in the changelog). Never loosen a grader that the Step 3 matrix proved correct.

- [ ] **Step 5:** Commit `feat(evals): add the testing cases parameterized-slug-tests and callback-confirmation-test`.

### Task 9: Gate battery and final review

- [ ] **Step 1:** Unit tests; `check-apis --strict`; both validates; check-docs; check-instructions; `git diff upstream-testing-1.2.0 --name-only -- plugins/swift/skills/testing` and the same for concurrency, with every file having a Deviations row. Then check that every fork commit in the range carries its own row: `for c in $(git log --format=%h <plan-base>..HEAD -- plugins/swift/skills/testing plugins/swift/skills/concurrency); do git show --stat $c | rg -q UPSTREAM.md || echo "NO ROW IN $c"; done` (expect no output).
- [ ] **Step 2:** The full eval suite, with 8 cases expected; confirm `jq '.cases|length'` is 8, so no case was dropped at load time.
- [ ] **Step 3:** One fresh whole-branch reviewer on opus, **before** the release commit, with this plan's Review Focus verbatim and the Plan 1 lessons named (`-emit-sil`, runtime re-verification of behavioural fixes, grader matrix, row-per-commit). Fix pass per executing-plans: Critical and Important are each proven failing then passing; Minor goes to the ledger.

### Task 10: Release 0.1.5

- [ ] **Step 1:** `changelog-release`: feature → z bump, 0.1.4 → 0.1.5. The narrative leads with `swift:testing`, and the block has a known-gap line if either eval case shows delta 0.
- [ ] **Step 2:** Refresh the version-stamped captures: plugin-details, unit-tests, check-apis-strict. Redact each with `--extra "$(python3 -c 'import tempfile,os;print(os.path.realpath(tempfile.gettempdir()))'),$TMPDIR"` so no `/var/folders` path lands. Update the page blocks, check them for secrets, and confirm check-docs exits 0.
- [ ] **Step 3:** Commit `chore(release): v0.1.5`, then `claude plugin tag plugins/swift --dry-run`. Refresh the `tag-dry-run` capture and the work-on-it block, `git commit --amend --no-edit -a`, then `claude plugin tag plugins/swift`.
- [ ] **Step 4:** Ask the user before pushing: `git push origin main`, then `git push origin swift--v0.1.5`.

---

## Self-review record

- **Spec coverage:**
  - §5 import and day-one deviations → Tasks 1–2;
  - §5 verification → Tasks 3–5;
  - §5 XCTest bridge, audit-first → Task 5 Step 2 (upstream already covers it; addition only on an audit gap);
  - §5 evals, greenfield and red-without prompts → Task 8;
  - §4 routing cross-reference, deferred from Plan 1 → Task 6;
  - §8 surfaces → Tasks 1, 7 and 10;
  - §9 → Task 10.
- **Placeholder scan:** conditional branches (gap-filling, delta-0 escalation) have explicit both-ways instructions, and every command is concrete. The only execution-time value is the Ported date.
- **Consistency:** tag `upstream-testing-1.2.0`, section `## Testing`, folder `plugins/swift/skills/testing`, command `/swift:testing`, and the case names match everywhere.
- **Review Focus:** all five lines are pinned by named steps.
