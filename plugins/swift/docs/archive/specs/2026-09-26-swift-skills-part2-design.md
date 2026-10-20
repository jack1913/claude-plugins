# swift-plugin part 2 — `swift:concurrency`, `swift:testing`, `swift:review`

- **Date:** 2026-09-26
- **Status:** design approved in conversation (fork both AvdLee upstreams; review = code + screenshots; one spec, sequential releases; audit-first content additions; review slash-only with a recorded end-to-end verification run). Written-spec review pending.
- **Origin:** swift-plugin session; discharges the parent spec's §10 "Out of scope / later".
- **Parent spec:** `2026-09-24-swift-plugin-design.md` (its decisions, working rules and quality bar carry over unchanged unless this file says otherwise).

## 1. Goal

Extend the `swift` plugin from two skills to five, at the same bar as the parent spec: every API name checkable by one command, every claim verified against Apple's data or the compiler, every release eval-green where evals apply.

Success means:

1. `swift:concurrency` and `swift:testing` are own-copy forks of AvdLee's skills with the same discipline as `swift:swiftui` (byte-for-byte import tag, per-change Deviations rows, claim audit before release).
2. `swift:review` audits a screen's SwiftUI code and/or screenshots against the HIG and `swift:design`'s rules, on demand only, without duplicating them.
3. Releases ship one skill at a time: **0.1.4** (concurrency), **0.1.5** (testing), **0.1.6** (review) — the `changelog-release` pre-1.0 rule bumps `z` for features.
4. All repo surfaces that name skills, counts or upstream facts stay in step (§8).

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Base for `swift:concurrency` | Clean import of AvdLee/Swift-Concurrency-Agent-Skill `skills/swift-concurrency/` at tag `2.3.0` (SHA pinned at import) | Same author and shape as the swiftui upstream; MIT; already ships Swift 6 mode detection, Sendable guardrails and a migration quick guide (verified 2026-09-26) |
| Base for `swift:testing` | Clean import of AvdLee/Swift-Testing-Agent-Skill `swift-testing-expert/` at tag `1.2.0` (SHA pinned at import) | MIT; already ships `migration-from-xctest.md` with coexistence and assertion mapping (verified 2026-09-26) |
| Relationship to both upstreams | Own copy, manual porting — ADR-0004's model, recorded as extended by ADR-0010 | Parent spec: "not dependent in any way" |
| Authored additions | **Audit-first:** additions land only where the pre-release audit finds a gap, as deviations inside the upstream files, never as parallel sections | Upstream already covers the planned additions (§4, §5); parallel text creates two truths and rots upstream-diff readability |
| `swift:review` | Ours, like `swift:design`; slash-only (`disable-model-invocation: true`); inputs are view files and/or pasted screenshots | Parent spec §10 "own text, run by hand"; a review must never fire unasked mid-build; slash-only costs zero always-loaded context |
| `swift:review` quality gate | No automated eval; one recorded end-to-end verification run (planted-violations screen + one screenshot) before release; revisit only if `claude plugin eval` proves it can drive slash-only skills | The eval harness fires skills via the Skill tool, which Claude Code blocks for `disable-model-invocation` skills |
| Release slicing | One spec, three sequential releases, each alone when green | Usable skills early; a defect in one doesn't hold the others |
| Build order | Multi-upstream machinery (§3) → concurrency → testing → review | The machinery must exist before the first new import commit; review depends only on `swift:design`, which exists |

## 3. Multi-upstream machinery (one atomic change, before any import)

- **`UPSTREAM.md`** restructures into one section per upstream — SwiftUI, Concurrency, Testing — each with its own Upstream URL, Baseline tag (+ pinned SHA), Local import tag, and Deviations / Ported / Findings tables. The existing content moves under the SwiftUI section unchanged.
- **`maintenance/upstream-diff.sh`** takes a skill argument (`swiftui|concurrency|testing`) plus an optional ref; no argument is an error listing the choices, not a silent default. The baseline parse becomes per-section. `UPSTREAM_DIFF_URL` keeps working as the test seam for the selected skill.
- **New unit tests** (stdlib-only, `maintenance/tests/`): a scratch git repo in a tmpdir driven through `UPSTREAM_DIFF_URL`, covering per-section baseline parse, skill-argument mapping, the no-arg error, and the no-plain-tag error. None exist today; these are new, not "extended".
- **ADR-0009's Findings pointer:** when the ignore group "upstream names not in Apple's index" is re-created, its reason text names the upstream section the finding lives in.
- **Same change refreshes:** `work-on-it.md`'s upstream-diff usage text and capture, update-docs REPO SPECIFICS (§8), and anything else that parses or quotes the old single-baseline shape.

## 4. `swift:concurrency` (0.1.4)

- **Import:** byte-for-byte `skills/swift-concurrency/` at `2.3.0`, local tag `upstream-concurrency-2.3.0`; `NOTICE.md` entry pinning tag + SHA; `LICENSE-upstream` inside the skill folder.
- **Day-one deviations** (the known swiftui patterns): frontmatter `name: concurrency`; description rewritten to the house trigger-worded style; `${SKILL_DIR}` → `${CLAUDE_SKILL_DIR}` wherever it occurs (count verified at import); `agents/` and `assets/` deleted.
- **Verification:** `apis.json` frameworks already cover it (`swift`, `dispatch`, `os`, `foundation`, `combine`); names that don't resolve get ignore entries with reasons per ADR-0009; platform claims pinned; `check-apis --strict` green before release.
- **Audit:** the report-only claim-by-claim workflow (≈4 sonnet auditors + opus verifier, the 0.1.3 shape; 16 reference files) runs after import and before release. Confirmed findings become individual fix commits with Deviations rows marked "upstream bug, worth reporting upstream" where applicable.
- **Gap-filling (only if the audit finds gaps):** Swift 6 strict-concurrency additions land inside upstream's own files (`sendable.md`, `migration.md`, `threading.md`), as deviations.
- **Routing:** its upstream `references/testing.md` (async testing) stays for fork fidelity, gaining a router cross-reference to `swift:testing` as a deviation; the two skills' descriptions route async-test *diagnosis* to concurrency and test *authoring/migration* to testing.
- **Evals:** 2–3 cases (e.g. make a racy type Sendable-safe; diagnose an actor-isolation error), WITH-arm threshold 0.67 — the semantics the 0.1.2/0.1.3 runs proved (suites passed with WITHOUT arms at 0.50).

## 5. `swift:testing` (0.1.5)

- **Import:** byte-for-byte `swift-testing-expert/` at `1.2.0`, local tag `upstream-testing-1.2.0`; NOTICE + `LICENSE-upstream`. No `agents/`/`assets/` in this repo — that deletion deviation applies to concurrency only.
- **Day-one deviations:** frontmatter `name: testing`; description rewritten to house style (upstream's targets "Apple-platform or Swift server projects"); `${SKILL_DIR}` fix if present.
- **Verification:** `apis.json` frameworks grow by `testing` and `xctest` — both indexes verified live 2026-09-26 (`testing`: 332 symbols incl. `Test`, `expect`, `Suite`, and Apple's own "Migrating a test from XCTest"). Audit + gates as §4 (10 reference files, ≈3 auditors).
- **XCTest bridge:** upstream's `migration-from-xctest.md` is audited first; only genuinely missing guidance (notably *when to stay on XCTest* — UI tests, suite continuity) is added **into that file**, as a deviation. No parallel authored section.
- **Evals:** 2–3 cases scaffolded as greenfield packages with no existing tests, so "new tests come out in Swift Testing syntax" cannot contradict the bridge rule; prompts chosen so the WITHOUT arm is genuinely red (modern models often write Swift Testing unaided — the suite's value is the delta).

## 6. `swift:review` (0.1.6)

- **Invocation:** `disable-model-invocation: true`; runs only as `/swift:review`. Zero always-loaded context cost.
- **Shape:** ~120-line SKILL.md + references: a per-HIG-area checklist that **points into** `swift:design`'s Decision Rules and area references (never restating them), a screenshot-review method, and the findings format: *violation · HIG source · fix*. Output is a findings report in chat.
- **Inputs:** SwiftUI view file(s) and/or pasted screenshot images; both first-class.
- **Rules:** carries the project-layer Operating Rule byte-identical (ADR-0011 records the scope extension; ADR-0007's body stays untouched and only gains an "Amended by ADR-0011" status pointer); a repo's deliberate, project-layer-sanctioned deviations are not findings; per ADR-0008, *missing* glass is never a finding (glass-on-content conflicting with the project layer can be). HIG text is paraphrased with page URLs cited, never copied (parent spec §5). `dickwu/apple-design-skill` stays off-limits (no license; ADR-0005).
- **Quality gate:** before release, one recorded end-to-end run against a screen with planted violations **and** one screenshot run; both outputs kept as evidence at `docs/internals/review-verification.md` (dated, frozen after the run). ADR-0011 records this design.

## 7. Verification summary

Per release: unit tests, `check-apis --strict`, `claude plugin validate` (plugin + marketplace), check-docs, check-instructions, `git diff <import-tag>` fully covered by Deviations rows, eval suite green (except review, §6), audit workflow run and findings closed. The 0.1.3 audit is the quality precedent for forks.

## 8. Surfaces to update (complete list)

- `AGENTS.md`: §4's per-commit Deviations constraint generalizes from `plugins/swift/skills/swiftui/` to every forked skill dir; §2/§3 rows for the new skills and files; the fixed-names sentence grows to five skills (additive — example-app depends only on the existing names).
- `changelog-release` REPO SPECIFICS: commit scopes gain `concurrency`, `testing`, `review`.
- `update-docs` REPO SPECIFICS: the UPSTREAM.md section→source row becomes the three per-upstream diff commands; the cross-surface integrity row gains review→`../design/references/` link resolution.
- `plugins/swift/.claude-plugin/plugin.json` **and** `.claude-plugin/marketplace.json` descriptions extended at each release (they already differ slightly; both get the five-skill text by 0.1.6).
- `README.md` skill table; `enable-in-a-swift-repo.md` skill table and the `plugin-details` capture ("Skills (5) …" at the end).
- `work-on-it.md`: the "Change swift:swiftui" section generalizes to any fork; upstream-diff usage + capture; unit-tests and check-apis count captures and their page blocks.
- Parent spec: §10 items marked done incrementally; §5's "three SKILL.md files (~370 lines)" context-cost figure re-recorded (five skills ≈ 660 lines worst case; always-loaded cost ≈ four descriptions ≈ 500 tokens, review costs none).
- ADRs: **0010** (own-copy fork model extended to the two new upstreams), **0011** (`swift:review`: authored, slash-only, relationship to `swift:design`, project-layer-rule scope extension); ADR-0007's body stays frozen and gains only an "Amended by ADR-0011" status pointer.

## 9. Versioning and release

Each skill ships through the unchanged flow: `changelog-release` → commit → `claude plugin tag plugins/swift` (dry run first) → push **with the user's OK at that step**. The §3 machinery lands inside the 0.1.4 range (it may be committed before the concurrency import, but it releases together with it).

## 10. Verify during implementation

- At import time: each upstream's newest plain tag (repos were pushed to as recently as 2026-09-14; if a newer plain tag exists, import that and record it) and its SHA.
- `${SKILL_DIR}` occurrence counts in both upstreams.
- Apple's index coverage for the exact Swift Testing / XCTest symbol paths the testing fork names; ignore entries per ADR-0009 for what doesn't resolve.
- WITH-arm threshold semantics re-confirmed on the first new eval case.
- Whether `claude plugin eval` prompt.md text is processed as a user turn (the §6 revisit clause depends on it; do not assume).

## 11. Working rules

The parent spec's §11 carries over: no commits, pushes or repo changes without the user's explicit OK at that step; this spec → `superpowers:writing-plans` → the user picks the execution method. Fleet sizes are stated before launch (audits: ≤4 auditors + 1 verifier per skill); audits are report-only; fixes are main-thread, one commit per finding group with its Deviations row.
