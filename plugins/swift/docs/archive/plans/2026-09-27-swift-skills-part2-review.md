# Part 2, Plan 3: `swift:review` (0.1.6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `swift:review`, an on-demand HIG review of a SwiftUI screen from its code and/or screenshots, verified by a recorded end-to-end run, released as 0.1.6.

**Architecture:** `swift:review` is our own authored skill, like `swift:design` and unlike the forks. It is slash-only and report-only. Its checks point into `swift:design`'s Decision Rules and references instead of restating them. The spec (§6) replaces the automated eval with a recorded end-to-end verification: a planted-violations fixture, a project-layer variant and a rendered screenshot are reviewed through headless `claude -p "/swift:review …"`, scored against a key committed before the first run, and kept in `docs/internals/review-verification.md`. ADR-0011 records the design and extends ADR-0007's project-layer rule to a third skill.

**Tech Stack:** Markdown skill files, `claude -p` with `--plugin-dir`, a stdlib Python scorer, `swiftc` plus `ImageRenderer` for the screenshot fixture (render verified at planning: a 780×600 PNG from a CLI binary), `maintenance/check-apis.py`. Toolchain at planning: Xcode 27.0, Swift 6.4.

**Spec:** `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md` §2 (the review rows), §6, §8 and §9; ADR-0007, ADR-0008.

## Global Constraints

- **Names are fixed.** After Task 7 the skills are `swift:swiftui`, `swift:design`, `swift:concurrency`, `swift:testing`, `swift:review` (AGENTS.md §4; spec §8 says additive). `swift:review` is not a fork: it gets no `UPSTREAM.md` row and is not added to AGENTS §4's forked-skill list.
- **Invocation.**
  - `disable-model-invocation: true`, so it runs only as `/swift:review`, and the spec (§6) wants zero always-loaded cost.
  - Read-only is enforced with `disallowed-tools: Write, Edit, NotebookEdit`, because `allowed-tools` only pre-approves tools (Claude Code docs, "Pre-Approve Tools").
  - Both behaviours are proven in Task 1 against a positive control.
- **Project-layer rule.** It is carried **byte-identical** to `swift:design` (SKILL.md:13) and `swift:swiftui` (SKILL.md:18): *If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict*. For a reviewer this means a literal the project's layer sanctions is not a finding (ADR-0007, extended by ADR-0011).
- **Glass.** Missing Liquid Glass is never a finding; glass on content can be (ADR-0008).
- **HIG text** is paraphrased with page URLs cited, never copied (parent spec §5). Every cited page is checked to answer 200 at `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<page>.json`. `dickwu/apple-design-skill` stays off-limits (ADR-0005).
- **No restating `swift:design`.** `swift:review` names a Decision Rule by its bold label (**Grouped input**, **Settings**, **Top-level sections**, **visionOS**, **Toolbars**, **Buttons**, **Sheets**, **Liquid Glass**, **Colour**, **Type**) and links the area reference.
- **Cross-skill links** are written relative to the file that contains them, the way `swift:design` does. From `review/SKILL.md` a link is `../design/references/<file>.md`; from `review/references/*.md` it is `../../design/references/<file>.md`.
- **`check-apis --strict`** (`python3 maintenance/check-apis.py --strict`) is green at every commit. Any `apis.json` change lands in the commit that needs it (Plan 2 lesson).
- **Verification integrity.**
  - The answer key is committed in Task 5, before the first review run. It is never edited after Task 6 starts.
  - Fixture sources carry no comments that hint at a violation.
  - Each run's working directory holds only what that run is allowed to see.
- **Commits and release.**
  - Accepting this plan authorizes local commits. **Pushes are not authorized:** ask the user at Task 9.
  - Release order: `changelog-release` → commit → `claude plugin tag plugins/swift --dry-run` → the tag itself → push, only with the user's OK.

## Review Focus

1. **The skill must never fire unasked.** A normal "review this screen" prompt with the plugin loaded must not invoke `swift:review`, and always-loaded context must not grow. Pinned by Task 1's auto-invocation probe, with a control that proves the prompt would fire a model-invocable twin, and by Task 8's `plugin details` check.
2. **A repo's sanctioned deviations must not be reported.** In a project with its own tokens, token-based spacing, colours and radii produce no "hardcoded literal" finding. Pinned by Task 6 Run B's per-run false-positive rule.
3. **Missing glass must never be reported.** Pinned by the key's `N1` entry, which applies to every run.
4. **A screenshot review must not claim what an image cannot show:** exact point sizes, Dynamic Type, dark mode, toolbars or sheets that aren't in the image. Pixel-derived measurements are marked `(estimated)`. Pinned by Task 6 Run C's rules and a Run C working directory that holds only the PNG.
5. **The review must be report-only.** The working tree is unchanged after every run, even with edits permitted. Pinned by Task 1's write probe and control, and by Task 6's runs under `--permission-mode acceptEdits` with a `git status` check.

---

### Task 1: Invocation mechanics probe

**Files:** none in the repo. Two scratch plugins, `$TMPDIR/probe-on/` and `$TMPDIR/probe-off/`.

**Interfaces:**
- Produces: confirmed frontmatter for Task 3, recorded as ledger evidence for ADR-0011:
  - `disable-model-invocation: true` blocks auto-invocation and adds ~0 always-on tokens;
  - `disallowed-tools` blocks Write while the skill runs, even when edits are permitted;
  - `$ARGUMENTS` expands under `claude -p`;
  - `claude plugin validate` accepts both keys.

- [ ] **Step 1: Two probe plugins.** Both get a `.claude-plugin/plugin.json` (`{"name":"probe-on","version":"0.0.1","description":"probe"}`, and the same with `probe-off`) and a `skills/rv/SKILL.md`. `probe-on`'s skill:

```markdown
---
name: rv
description: Use when the user asks to review a probe screen.
disable-model-invocation: true
disallowed-tools: Write, Edit, NotebookEdit
---

Print exactly: PROBE-ARGS=[$ARGUMENTS]. Then use the Write tool to create written.txt containing "x", and report whether the Write tool was available.
```

  `probe-off` is identical except that it has neither `disable-model-invocation` nor `disallowed-tools`. It is the positive control.

- [ ] **Step 2: Measure.** Run each command from a fresh scratch dir; `ls written.txt` after every run.

| # | Command | Expected |
| --- | --- | --- |
| a | `claude plugin validate $TMPDIR/probe-on` | passes; no unknown-key error |
| b | `claude --plugin-dir $TMPDIR/probe-on plugin details probe-on` vs the same for `probe-off` | `probe-on` always-on ~0; `probe-off` > 0 |
| c | `claude -p --permission-mode acceptEdits --plugin-dir $TMPDIR/probe-off "/probe-off:rv hello.swift"` | prints `PROBE-ARGS=[hello.swift]`; `written.txt` **exists** (proves the probe detects writes) |
| d | same with `probe-on` | `PROBE-ARGS=[hello.swift]`; `written.txt` **absent** |
| e | `claude -p --plugin-dir $TMPDIR/probe-off "Please review the probe screen"` | `PROBE-ARGS` printed (proves the prompt triggers) |
| f | same with `probe-on` | no `PROBE-ARGS` |

- [ ] **Step 3: Rule on any failure, then record.** If any row fails its expectation, rule in the ledger before Task 3.
  - If the control (c or e) fails, the probe is broken: fix the probe, not the conclusion.
  - If d fails, report-only rests on the skill text alone. The ruling says so, ADR-0011 records it, and Task 6's acceptEdits runs become the sole gate.
  - If b shows a non-zero cost, record the figure.

  Record all six outputs in the ledger.

### Task 2: ADR-0011 and the ADR-0007 pointer

**Files:**
- Create: `docs/adr/ADR-0011-swift-review-skill.md`, in the `docs/adr/ADR-TEMPLATE.md` shape.
- Modify: `docs/adr/ADR-0007-project-design-layer-wins.md`, status line only. There is no ADR index to update.

- [ ] **Step 1: Write ADR-0011.**
  - **Title:** "`swift:review` is an authored, slash-only, report-only review skill that points into `swift:design`".
  - **Status and date:** `accepted`, dated the execution date.
  - **Source:** spec §2/§6/§8, Task 1 evidence, and the commit SHAs, filled at commit.
  - **Context:** parent spec §10's "on-demand HIG review, run by hand".
  - **Decision:**
    - slash-only via `disable-model-invocation`;
    - report-only via `disallowed-tools` (or as Task 1 ruled);
    - inputs are view files and/or screenshots;
    - checks point into `swift:design` rather than restating it;
    - it carries the project-layer rule byte-identical, extending ADR-0007 to a third skill;
    - ADR-0008 applies, so missing glass is never a finding;
    - no automated eval, because the harness fires skills through the Skill tool, which slash-only skills block; a recorded end-to-end verification replaces it.
  - **Rejected:** a model-invocable skill with a narrow description (spec §2, since a review must never fire mid-build); restating design's rules.
  - **Consequences:**
    - design-rule changes flow to review automatically;
    - the verification is re-run when review's method changes, as a new dated section;
    - three skills carry the project-layer rule, so a change to it touches three files.
- [ ] **Step 2: Point ADR-0007 at it.** `- **Status:** accepted` becomes `- **Status:** accepted; amended by ADR-0011 (the rule also binds swift:review)`. The body stays frozen.
  - Run check-docs. Expected: exit 0.
  - Commit `docs(adr): record swift:review's design in ADR-0011 and point ADR-0007 at it`.

### Task 3: Author the skill

**Files:** Create `plugins/swift/skills/review/SKILL.md` and `plugins/swift/skills/review/references/{checklist.md,screenshot-review.md,findings-format.md}`.

**Interfaces:**
- Consumes:
  - Task 1's frontmatter;
  - `swift:design`'s Decision Rule labels (Global Constraints) and its eight references: `color`, `hierarchy-layout`, `liquid-glass-design`, `motion`, `platform-idioms`, `sf-symbols`, `tokens`, `typography`;
  - `swift:swiftui`'s `references/accessibility-patterns.md`.
- Produces the findings format Task 5's scorer parses:
  - one line per finding: `- [<severity>] <violation> — <location> — HIG: <page URL> — Fix: <fix>`;
  - `<severity>` is `high`, `medium` or `low`;
  - `<location>` is `<file>:<line>` or `screenshot: <region>`;
  - a pixel-derived measurement carries `(estimated)`;
  - the report ends with a `## Not checked` section.

- [ ] **Step 1: SKILL.md** (≤ 120 lines).

```markdown
---
name: review
description: 'On-demand HIG review of a SwiftUI screen from its code and/or screenshots: hierarchy, typography, colour, SF Symbols, controls and hit targets, platform idioms, Liquid Glass placement, motion and accessibility, reported as findings with the HIG source and a fix. Run as /swift:review <view files or screenshot paths>.'
disable-model-invocation: true
disallowed-tools: Write, Edit, NotebookEdit
---
```

  Sections:
  - **Purpose:** two sentences.
  - **Inputs:** `$ARGUMENTS` names Swift view files and/or image paths. Images pasted into the conversation count too. With neither, ask which screen.
  - **Operating Rules:**
    - the byte-identical project-layer rule, then its reviewer consequence: a literal the project's layer sanctions is not a finding;
    - missing glass is never a finding (ADR-0008); glass on content is;
    - report only, never edit;
    - review against the platform(s) the project targets, read from `Package.swift` or the Xcode project;
    - use `swift:design`'s Decision Rules rather than re-deriving them.
  - **Method:**
    1. Detect the project layer: token types, colour sets, a project design skill.
    2. Code pass per `references/checklist.md`.
    3. Screenshot pass per `references/screenshot-review.md`.
    4. Merge code and screenshot findings for the same issue.
    5. Report in the `references/findings-format.md` shape, most severe first, ending with `## Not checked`.
  - **Router:** a table covering the three references, `../design/SKILL.md` and `../design/references/<file>.md`.
- [ ] **Step 2: `references/checklist.md`.**
  - One section per area:
    - hierarchy and grouping;
    - typography;
    - colour and contrast;
    - SF Symbols;
    - controls and hit targets;
    - toolbars, tabs and navigation;
    - sheets and modality;
    - platform idioms;
    - Liquid Glass placement;
    - motion and Reduce Motion;
    - accessibility (labels, Dynamic Type, VoiceOver order).
  - Each check is a question naming its source rule, its reference (`../../design/references/<file>.md`, or `../../swiftui/references/accessibility-patterns.md`) and its HIG page (`https://developer.apple.com/design/human-interface-guidelines/<page>`). Example: "Is grouped input a `Form` with `Section`s and `LabeledContent`? — **Grouped input** · `../../design/references/hierarchy-layout.md` · HIG lists-and-tables".
  - No rule text is restated.
  - Pages come from those `swift:design` already cites: accessibility, buttons, color, dark-mode, layout, lists-and-tables, materials, modality, motion, ornaments, settings, sf-symbols, sheets, sidebars, split-views, tab-bars, toolbars, typography, windows. Any other page is checked for 200 first.
- [ ] **Step 3: `references/screenshot-review.md`.**
  - What one image can show: hierarchy, grouping, alignment, apparent contrast, symbol and label use, glass placement, and the number of prominent actions, but only for what is visible.
  - What it cannot show, and the extra capture to ask for:
    - exact point sizes (the image's scale is needed);
    - Dynamic Type (an accessibility-size capture);
    - dark mode and increased contrast;
    - motion;
    - VoiceOver order;
    - toolbars, sheets or menus that aren't in the frame.
  - Hit targets from pixels: points = pixels ÷ scale. State the assumed scale and mark the result `(estimated)`.
  - Anything the image can't support goes under `## Not checked`, never in findings.
- [ ] **Step 4: `references/findings-format.md`.**
  - The entry shape from **Interfaces**, with two filled examples: one code, one screenshot.
  - Severity:
    - **high:** breaks a HIG requirement a person hits, such as a hit region under 44×44 pt (60×60 on visionOS) or meaning carried by colour alone;
    - **medium:** against HIG guidance, with a clear fix;
    - **low:** polish.
  - The "not a finding" list: project-layer-sanctioned literals; missing glass; taste with no HIG basis.
  - The closing `## Not checked` section.
- [ ] **Step 5: Gates.**
  - `check-apis --strict` → 0 warnings. Any unresolved name is an example type or prose word, justified in `apis.json` in this commit.
  - Link check, resolving each link against the directory of the file it appears in. Expected: no output.

```sh
rg -o --with-filename -N '\.\./[^ )`]*\.md' plugins/swift/skills/review | while IFS=: read -r f l; do test -f "$(dirname "$f")/$l" || echo "BROKEN $f -> $l"; done
```

  - Every cited HIG page answers 200 at its JSON path.
  - `claude plugin validate plugins/swift` passes.
  - `wc -l plugins/swift/skills/review/SKILL.md` ≤ 120.
  - Byte check: `diff <(grep -h 'translate every literal' plugins/swift/skills/review/SKILL.md) <(grep -h 'translate every literal' plugins/swift/skills/design/SKILL.md)` shows no difference.
- [ ] **Step 6: Commit** `feat(review): add swift:review, a slash-only HIG review of SwiftUI code and screenshots`.

### Task 4: Cross-surface integrity for review's links

**Files:** `.claude/skills/update-docs/SKILL.md`, the REPO SPECIFICS "cross-surface reference integrity" row (currently line 357).

- [ ] **Step 1: RED.** Copy `plugins/swift/skills/review` to `$TMPDIR/rv-copy/review`. Add `../../design/references/nope.md` to its `checklist.md` and run the Task 3 link check on the copy. Expected: `BROKEN …checklist.md -> ../../design/references/nope.md`. Run it on the real tree: no output.
- [ ] **Step 2: Extend the row.** Add to it: "every `../`-relative `.md` link in `plugins/swift/skills/review/` must resolve against the directory of the file that contains it". This is the spec §8 "review→`../design/references/` link resolution" item.
  - Run check-instructions. Expected: exit 0.
  - Commit `docs: extend update-docs' cross-surface check to swift:review's links`.

### Task 5: Verification fixtures and scorer

**Files:**
- Create:
  - `maintenance/review-fixtures/planted/` (a Swift package);
  - `maintenance/review-fixtures/tokened/` (a Swift package);
  - `maintenance/review-fixtures/render/render.swift`;
  - `maintenance/review-fixtures/screenshot.png`;
  - `maintenance/review-fixtures/key.json`;
  - `maintenance/review-fixtures/score.py` (stdlib only);
  - `maintenance/tests/test_review_score.py`.

**Interfaces:**
- Produces `key.json`:

```json
{
  "runs": {
    "code":       {"planted": ["P1","P2","P3","P4","P5","P6","P7","P8"], "min": 7, "must_not_report": ["N1"]},
    "tokened":    {"planted": ["P3","P4"], "min": 2, "must_not_report": ["N1","N2"]},
    "screenshot": {"planted": ["<set in Step 4 from the inspected PNG>"], "min": "<len - 1>", "must_not_report": ["N1","N3"]}
  },
  "violations": {"P1": {"area": "grouping", "must_match": ["Form|LabeledContent"], "line": 0}},
  "never": {"N1": {"pattern": "(add|adopt|missing|consider)\\b.{0,40}(Liquid )?[Gg]lass", "why": "ADR-0008"}}
}
```

  - `line` is the fixture line of the violation, filled in Step 1.
  - `N2` is the tokened run's rule: no finding that calls a `DesignTokens` value a hard-coded literal.
  - `N3` is the screenshot run's rule: no exact `\d+ ?pt` measurement without `(estimated)`, and no Dynamic Type or dark-mode finding.
- Scorer: `python3 maintenance/review-fixtures/score.py <key.json> <review.md> --run code|tokened|screenshot`.
  - It splits `<review.md>` into finding lines (`^- \[(high|medium|low)\]`); text under `## Not checked` is not findings.
  - A planted violation counts as detected when one finding line matches a `must_match` pattern. For code runs, that line's `<file>:<line>` must also be within ±3 lines of the key's `line`.
  - A `never` pattern matching any finding line is a false positive.
  - Output: `detected N/M, missed [...], false positives [...], unscored K`. Exit 0 only when detected ≥ `min` and there are no false positives.

- [ ] **Step 1: `planted/`.**
  - `Package.swift` declares `platforms: [.iOS(.v26), .macOS(.v26)]`, because `.glassEffect` is OS 26.
  - `Sources/Demo/SettingsView.swift` is one settings screen with eight violations. No comment in it names or hints at them.

| ID | Planted violation | Design rule / HIG page |
| --- | --- | --- |
| P1 | Labelled values in a `VStack` with `Divider`s instead of `Form` / `Section` / `LabeledContent` | **Grouped input** / lists-and-tables |
| P2 | `.font(.system(size: 13, weight: .ultraLight))` | **Type** / typography |
| P3 | An icon `Button` whose whole tappable area is `.frame(width: 28, height: 28)` | **Buttons** (44×44 pt) / buttons |
| P4 | A status shown only by a red or green `Circle` | **Colour** / color |
| P5 | A toolbar with three `.borderedProminent` actions | **Toolbars** / toolbars |
| P6 | "Delete account" with no `role: .destructive`, styled prominent | **Buttons** / buttons |
| P7 | A sheet whose only action is "Done" | **Sheets** / sheets |
| P8 | `.glassEffect()` on a content card inside the list | **Liquid Glass** / materials |

  - No glass anywhere else, so `N1` has nothing legitimate to say.
  - Gate: `swift build` exits 0. Fill each `line` in `key.json` from `rg -n`.
- [ ] **Step 2: `tokened/`.**
  - The same screen, with every spacing, colour and radius coming from a `DesignTokens.swift` enum plus asset colours.
  - P1, P2 and P5–P8 are fixed; P3 and P4 stay planted, their `line` values in a separate `tokened` block of `violations` (as `P3t`, `P4t`, with the run's `planted` list updated to match).
  - Gate: `swift build` exits 0.
- [ ] **Step 3: Render.** `render.swift` renders the planted view with `ImageRenderer` at scale 2 to `screenshot.png`, using the planning approach: `swiftc -parse-as-library -swift-version 6`, with the target set to the fixture's macOS floor. The render wraps the content in a phone-sized frame. `ImageRenderer` draws view content only, not window toolbars or presented sheets, and may not draw glass or list-backed views.
- [ ] **Step 4: Inspect, then set the screenshot key.** Read `screenshot.png` and list which of P1–P8 are actually visible. Only those go into `runs.screenshot.planted`, with `min` = count − 1. Toolbar P5 and sheet P7 are expected to be absent. Ledger the list with the reason for each exclusion. If fewer than four are visible, restructure the render (inline the action row and card in the content) and re-inspect. Do not fall back to trusting the code.
- [ ] **Step 5: TDD the scorer.** `maintenance/tests/test_review_score.py` builds synthetic reviews and asserts:
  - all eight findings at the right lines pass `--run code`;
  - missing two fails;
  - a finding at the wrong line (±10) is not detected;
  - a line reading "consider adding Liquid Glass to the toolbar" fails on `N1`;
  - a matching phrase that appears only under `## Not checked` is not detected;
  - a tokened review that calls `DesignTokens.spacingM` hard-coded fails on `N2`;
  - a screenshot review with `28 pt` and no `(estimated)` fails on `N3`.

  Run `python3 -m unittest maintenance.tests.test_review_score -v`. Expected: RED, because `score.py` doesn't exist. Implement it, then expect GREEN. Then run the full suite: 105 + new tests, all passing.
- [ ] **Step 6: Commit** `test(maintenance): add swift:review verification fixtures, answer key and scorer`. The key is frozen from here.

### Task 6: Recorded end-to-end verification

**Files:**
- Create: `docs/internals/review-verification.md`.
- Modify: `docs/internals/README.md`. It has no page list yet, so start one with `agent-instructions.md` and this page.

- [ ] **Step 1: Prepare three isolated working dirs** under `$TMPDIR/rv/`. Each one runs `git init && git add -A && git commit -qm base`.
  - `A/`: a copy of `planted/` with no key and no scorer.
  - `B/`: a copy of `tokened/`.
  - `C/`: `screenshot.png` only.
- [ ] **Step 2: Run each from its dir**, recording `claude --version` first.

```sh
claude -p --permission-mode acceptEdits --plugin-dir "$REPO/plugins/swift" "/swift:review Sources/Demo/SettingsView.swift" > ../A.md   # in A/
claude -p --permission-mode acceptEdits --plugin-dir "$REPO/plugins/swift" "/swift:review Sources/Demo/SettingsView.swift" > ../B.md   # in B/
claude -p --permission-mode acceptEdits --plugin-dir "$REPO/plugins/swift" "/swift:review screenshot.png" > ../C.md                    # in C/
```

  After each run, `git status --porcelain` must print nothing (Review Focus 5). `acceptEdits` makes that check meaningful: without it, `-p` denies writes anyway.
- [ ] **Step 3: Score.** Run `score.py … --run code|tokened|screenshot` on `A.md`, `B.md` and `C.md`. Accept when all three exit 0 and every tree is clean.
  - Findings the key doesn't list are recorded as `unscored`. Each one is judged in the record as real or wrong. A wrong one in the "not a finding" class is a skill-text defect.
  - If a run fails, fix the **skill text** (never the key or the fixtures), commit the fix, re-create the dirs and re-run all three. At most two iterations, all recorded. If it is still failing after two, stop and report to the user.
- [ ] **Step 4: Record.** `docs/internals/review-verification.md` (dated) holds:
  - the commands;
  - the `claude --version` output and the model;
  - each run's raw output, fenced;
  - the scorer lines;
  - the unscored-findings judgement;
  - the iteration history;
  - the `git status` evidence.

  It is frozen after this task: a later method change appends a new dated section and never edits an old one. Index it in `docs/internals/README.md`. Run check-docs. Expected: exit 0. Commit `docs(internals): record swift:review's end-to-end verification`.

### Task 7: Registry surfaces

**Files:**
- `AGENTS.md`:
  - §1: the skill list and summary;
  - §2: the `maintenance/` row gains "review verification fixtures";
  - §3: rows for `swift:review` → `plugins/swift/skills/review/SKILL.md` and for "Review verification record" → `docs/internals/review-verification.md`;
  - §4: the fixed-names sentence gains `swift:review`; the forked list is unchanged.
- `README.md`: the skill table, with a note that it runs as `/swift:review`.
- `docs/manual/getting-started/enable-in-a-swift-repo.md`: five skills, the "From …SKILL.md" line, and a row saying it runs only when invoked.
- Both manifest descriptions.
- The parent spec `docs/superpowers/specs/2026-09-24-swift-plugin-design.md`:
  - §10 marks `swift:review`, `swift:concurrency` and `swift:testing` done. The last two were missed by Plans 1–2; this is a ledgered catch-up.
  - §5's context-cost line is re-recorded with the measured `wc -l` of all five SKILL.md bodies and the `plugin details` always-on figure (spec §8).

- [ ] **Step 1: Apply with the Edit tool.** Manifest description: `"Correct, current, Apple-native Swift: swift:swiftui (APIs and correctness, visionOS, previews), swift:design (Apple-native design), swift:concurrency (Swift 6 concurrency), swift:testing (Swift Testing and XCTest migration) and swift:review (on-demand HIG review, /swift:review)."`
- [ ] **Step 2: Check and commit.** `rg -n 'four skills|Skills \(4\)' docs/manual README.md AGENTS.md` finds nothing stale. The capture itself refreshes in Task 9. Both validates, check-docs and check-instructions pass. Commit `docs: register swift:review across AGENTS, README, the manual, the manifests and the parent spec`.

### Task 8: Gate battery and final review

- [ ] **Step 1: Run the gates.**
  - The unit tests, including the scorer tests.
  - `check-apis --strict`.
  - Both validates.
  - check-docs and check-instructions.
  - `claude --plugin-dir plugins/swift plugin details swift`. Expected: `Skills (5)` and an always-on figure within noise of 0.1.5's ~1,001 tokens (Review Focus 1).
- [ ] **Step 2: Run the full eval suite.** Expected: 8 cases loaded and 8 passing. `swift:review` has no case, by design, and no existing case's `skill-fired` regresses.
- [ ] **Step 3: Final review.** One fresh whole-branch reviewer, on opus, before the release commit. It gets this plan's Review Focus verbatim and the ledger's `Ruling:` lines. Name these lessons:
  - review is not a fork, so no UPSTREAM rows;
  - strict must be green at every commit;
  - behavioural claims get runtime checks;
  - the key must not be tuned to the output (compare `key.json`'s commit against Task 6's run timestamps).

  Then a fix pass per executing-plans. A fix that touches the skill text re-runs Task 6 and appends to the record.

### Task 9: Release 0.1.6

- [ ] **Step 1: `changelog-release`.** A feature, so z bumps: 0.1.5 → 0.1.6. The narrative covers `swift:review`: slash-only, report-only, and how it's verified. Add the known gap: no automated eval by design; the verification record is the gate.
- [ ] **Step 2: Refresh the captures:** plugin-details (`Skills (5)`), unit-tests and check-apis-strict. Redact per the house pattern, with `--extra "<realpath tmpdir>,$TMPDIR"`. Then update the page blocks, scan for secrets, and run check-docs. Expected: exit 0.
- [ ] **Step 3: Commit and tag.**
  - Commit `chore(release): v0.1.6`.
  - `claude plugin tag plugins/swift --dry-run`, then refresh the tag capture and its work-on-it block, and `--amend`.
  - `claude plugin tag plugins/swift`.
- [ ] **Step 4: Ask the user before pushing:** `git push origin main`, then `git push origin swift--v0.1.6`.

---

## Self-review record

- **Spec coverage:**

| Spec requirement | Task |
| --- | --- |
| §6 invocation | 1, 3 |
| §6 shape | 3 |
| §6 inputs, including pasted images | 3, 5, 6 |
| §6 rules | 3; Global Constraints |
| §6 quality gate | 5, 6 |
| §8 ADR-0011 and ADR-0007 pointer | 2 |
| §8 cross-surface row | 4 |
| §8 AGENTS §2/§3/§4 | 7 |
| §8 manifests, README, manual, capture | 7, 9 |
| §8 parent spec §10 and §5 re-record | 7 |
| §8 changelog-release scopes | already contains `review`; no change |
| §9 release | 9 |

- **Deviation from the spec, stated:** the spec says report-only but names no mechanism. `allowed-tools` only pre-approves, so the plan uses `disallowed-tools` and proves it against a control in Task 1.
- **Revalidation (2026-09-27) corrected the first draft:**
  - Cross-skill links from `references/` need `../../`, and the link check now resolves per file.
  - The write and auto-invoke probes had no positive control. `-p` denies writes anyway, so runs use `acceptEdits`.
  - The screenshot run's dir held the source code, so the reviewer could read it.
  - `ImageRenderer` doesn't draw toolbars or sheets, so the screenshot key is set from the inspected PNG.
  - The fixture needs OS 26 platforms for `.glassEffect`.
  - The scorer matched the whole output, including "Not checked"; it now scores per finding line with location tolerance and per-run false-positive rules.
  - Spec §8's parent-spec §5 re-record and AGENTS §2 row were missing.
  - No ADR index exists.
- **Placeholder scan:** conditional branches (the Task 1 rulings, Task 5 Step 4's screenshot set, Task 6's iterations) have explicit outcomes. Values filled at execution: dates, `claude --version`, SHAs, fixture line numbers.
- **Consistency:** `/swift:review`, `plugins/swift/skills/review/`, `maintenance/review-fixtures/`, `score.py --run code|tokened|screenshot`, P1–P8, `N1`–`N3` and the finding-line shape are used identically in Tasks 3, 5 and 6.
