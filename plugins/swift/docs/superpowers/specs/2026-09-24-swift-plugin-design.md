# swift-plugin — design spec

- **Date:** 2026-09-24
- **Status:** design approved in conversation (parts 1–4); written spec reviewed 2026-09-24 in the swift-plugin session, review changes applied
- **Origin:** research + brainstorming session in `~/Dev/projects/example-app` (session `example-app-5e`). Implementation happens in this repo's own session.
- **Companion spec (consumer side):** `~/Dev/projects/example-app/docs/superpowers/specs/2026-09-24-example-app-design-layer-design.md`

## 1. Goal

A private Claude Code plugin, owned outright, that makes an agent write correct, current, Apple-native SwiftUI — and that is **active only in the Swift repos that opt in**.

Success means:

1. In any Swift repo that enables it, the agent uses APIs that exist on the project's target platforms (including visionOS and deployment targets below 26), guards `#Preview` with `#if DEBUG`, and produces Apple-native layouts rather than web patterns.
2. In a repo with its own design layer (ExampleApp's `example-app-design`), every example literal is translated into that layer's tokens.
3. Every API the skills name is checkable against Apple's documentation by one command.
4. No runtime or update dependency on any third-party repo. Upstream is read, never tracked.
5. In repos that have not enabled it, none of its skills appear.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Base | Clean import of AvdLee/SwiftUI-Agent-Skill `skills/swiftui-expert-skill/` at tag `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`) | Best candidate found (see §8); MIT; accurate on every spot-checked claim |
| Relationship to upstream | Own copy; no `npx skills`, no marketplace subscription, no git fork | User: "not dependent in any way"; upstream changes are ported by hand after reading a diff |
| Packaging | Claude Code plugin in a single-plugin marketplace | Only mechanism that enables a skill per project (`--scope project`); a user-level skill would load everywhere |
| Location | `~/Dev/claude_skills/swift-plugin/` → private GitHub `jack1913/swift-plugin` | `~/Dev/claude_skills/` is the user's home for skill repos; GitHub is the backup copy |
| Names | marketplace `swift-plugin`, plugin `swift`, skills `swift:swiftui`, `swift:design` | Plugin name is the namespace for every skill; `swift` leaves room for non-UI skills (`swift:concurrency`, `swift:testing`) |
| Scope of the fork | Keep **all** upstream references and the Instruments scripts (incl. iPhone Duo, WebKit, Charts, document apps) | User will need them |
| Improvements | Coverage fixes, API self-check script, a separate design-quality skill | User-selected |
| Design guidance | A separate `swift:design` skill, not edits scattered through `swift:swiftui` | Keeps `swift:swiftui` close to upstream so upstream diffs stay readable |
| Versioning | Explicit SemVer in `plugins/swift/.claude-plugin/plugin.json`, released with the `changelog-release` skill stamped by `/onboard-repo` and tagged with `claude plugin tag` (§6) | User wants versions; with `version` set, installs refresh only when it is bumped |
| API check | Names resolved automatically against Apple's per-framework doc indexes; the manifest holds only claims and overrides (§6) | Upstream's snippets name ~1,300 identifiers; a hand-written manifest would not pass `--strict` |
| Scenario tests | A `claude plugin eval` suite with its built-in no-plugin baseline (§7) | Repeatable RED/GREEN instead of hand-run prompts |

## 3. Repo layout (part 1)

```
~/Dev/claude_skills/swift-plugin/          private GitHub: jack1913/swift-plugin
  .claude-plugin/marketplace.json          marketplace "swift-plugin" → one plugin, source ./plugins/swift
  plugins/swift/                           the only directory copied into an install
    .claude-plugin/plugin.json             name "swift", version (SemVer) — the only version home (§6)
    NOTICE.md                              attributions + full MIT texts, travels with every install
    skills/
      swiftui/                             swift:swiftui — upstream fork + our fixes
        SKILL.md
        references/                        33 upstream files + ours (§4)
        scripts/                           upstream xctrace tooling (record_trace.py, analyze_trace.py, instruments_parser/)
        LICENSE-upstream                   upstream MIT text, travels with every install
      design/                              swift:design — ours (§5)
        SKILL.md
        references/
    evals/                                 claude plugin eval suite (§7); results/ gitignored
  maintenance/                             never shipped (outside plugins/swift)
    check-apis.py                          CLI shim
    apicheck/                              its package: apple, extract, manifest, fetch, table, cli
    apis.json
    upstream-diff.sh
    tests/                                 check-apis tests + upstream tests/test_record_trace.py
    .cache/                                gitignored
  docs/superpowers/                        specs/ (this file), plans/ — skipped by /onboard-repo's docs walk
  CHANGELOG.md                             Keep a Changelog, written by changelog-release (§6)
  UPSTREAM.md
  README.md
  .gitignore
```

`/onboard-repo` (full default pass, §6) adds its own files on top: stamped skills under `.claude/skills/` (`changelog-release`, `update-docs`, `update-rules`), agent config, the four-tier docs IA and a consumer manual. None of it is part of the plugin.

- **Commit 1** is upstream's skill folder byte-for-byte at `5.1.0` (including `agents/openai.yaml` and `assets/`), placed at `plugins/swift/skills/swiftui/`, tagged `upstream-5.1.0`. **Commit 2** deletes `agents/` and `assets/` (logos, ~430 KB) as the first deviation. Every later change is its own commit, so `git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` always shows exactly what we changed.
- **Not imported** (repo level, outside the skill folder): `.codex-plugin/`, `.cursor-plugin/`, `.github/`, `.agents/` (their Sosumi-based maintenance skill — replaced by §6), root `plugin.json` / `.claude-plugin/`, `package.json`, their README/INSTALLATION/CONTRIBUTING/AGENTS.md.
- **Frontmatter:** upstream `name: swiftui-expert-skill` becomes `name: swiftui`. This is required: in a plugin skill the frontmatter `name` sets the command, so upstream's name would give `/swift:swiftui-expert-skill`. The `description` (upstream: "for iOS or macOS") gains visionOS so the skill also triggers on visionOS work. Both are recorded deviations in `UPSTREAM.md`.
- **License:** upstream MIT text in `skills/swiftui/LICENSE-upstream`; `plugins/swift/NOTICE.md` lists every file or passage taken from AvdLee (MIT), twostraws/SwiftUI-Agent-Skill (MIT) and Dimillian/Skills (MIT), with each one's copyright line and MIT permission notice, so the notices ship with every install. Nothing is taken from dickwu/apple-design-skill (no license) or dpearson2699/swift-ios-skills (PolyForm).

**Install in a Swift repo** (run inside that repo):

```bash
claude plugin marketplace add jack1913/swift-plugin --scope project   # or declare it via extraKnownMarketplaces
claude plugin install swift@swift-plugin --scope project
```

`--scope project` writes to the repo's committed `.claude/settings.json`; `--scope local` writes to the gitignored `.claude/settings.local.json`. A repo without either entry never sees the plugin.

**Edit loop:** edit here → try with `claude --plugin-dir ~/Dev/claude_skills/swift-plugin/plugins/swift` → commit → release (§6: bump + changelog, commit, `claude plugin tag`) → push → `claude plugin marketplace update swift-plugin` + `claude plugin update swift@swift-plugin` in consumer repos. Installs are copies in `~/.claude/plugins/cache/`, so an edit reaches consumers only through a version bump and that update.

## 4. `swift:swiftui` — changes on top of upstream (part 2)

Each item is a separate commit and a row in `UPSTREAM.md` → Deviations.

1. **`references/visionos.md` (new).** Which glass APIs do not exist on visionOS (`glassEffect(_:in:)`, `GlassEffectContainer`, `Glass.interactive(_:)`, `.buttonStyle(.glass)` / `.glassProminent`, `glassEffectUnion`, `glassEffectTransition`, `scrollEdgeEffectStyle`, `ToolbarSpacer`, `sharedBackgroundVisibility`) and what to use there (`glassBackgroundEffect`, ornaments); windows, volumes, `ImmersiveSpace`; `SpatialEventGesture`; hover effects; the `#if os(visionOS)` branch pattern. Every platform statement comes from Apple's doc JSON (§6), not memory.
2. **`references/platform-availability.md` (new, generated).** Table of every Liquid-Glass / 26-era API × iOS / iPadOS / Mac Catalyst / macOS / visionOS / watchOS / tvOS with introduced version, deprecation and beta flags. Body between markers is written by `check-apis.py --write-table`; never hand-edited.
3. **`references/previews.md`.** Add the rule and a checklist item: wrap every `#Preview` in `#if DEBUG` — `#Preview` compiles into Release, so any DEBUG-only helper it references breaks archiving.
4. **Deployment targets below 26.** Upstream `liquid-glass.md` already has material fallbacks; add to the SKILL.md correctness checklist: every 26-only API sits behind `if #available(…)` with a fallback when the deployment target is lower.
5. **Borrowed rules.** twostraws `swiftui-pro` deprecated-API entries that `latest-apis.md` lacks; Dimillian view-ordering and subview-extraction rules into `view-structure.md` where upstream does not already cover them. Each attributed in `NOTICE.md`. Dimillian's "no view models by default" and `scrollExtensionMode(.underSidebar)` (not an Apple API) are **not** taken.
6. **SKILL.md.** Router rows for the new files, and one operating rule: *if the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict.*
7. **Script paths.** Upstream runs its tooling as `python3 "${SKILL_DIR}/scripts/…"`, 18 times across `SKILL.md`, `references/trace-analysis.md` and `references/trace-recording.md`. Claude Code documents `${CLAUDE_SKILL_DIR}`, not `${SKILL_DIR}`, so the commands would point at `/scripts/…`. Switch every occurrence to `${CLAUDE_SKILL_DIR}`.
8. **Upstream test path.** `tests/test_record_trace.py` hard-codes `skills/swiftui-expert-skill/scripts/record_trace.py` relative to the repo root; moving it to `maintenance/tests/` means pointing it at `plugins/swift/skills/swiftui/scripts/`. The file sits outside the tagged folder, so this deviation lives only in `UPSTREAM.md`.

Unchanged on purpose: upstream's "adopt Liquid Glass only when explicitly requested" stays — `swift:swiftui` is the correctness layer. When glass fits is `swift:design`'s job; a project layer may override both.

## 5. `swift:design` — new, ours (part 3)

```
skills/design/
  SKILL.md                 ~120 lines: design thinking (purpose, platform, hierarchy, interaction),
                           native primitives not web patterns, decision rules, checklist, router
  references/
    hierarchy-layout.md    content vs navigation layer, grouping (Form / Section / LabeledContent),
                           spacing rhythm, alignment
    typography.md          text styles, Dynamic Type, weights, when monospaced
    color.md               system and semantic colours, accent, dark mode, contrast, status colours
    sf-symbols.md          rendering modes, variants, matching weight and scale to adjacent text, symbol effects
    liquid-glass-design.md when glass fits: navigation layer only, regular vs clear, tint only primary
                           actions, avoid glass on glass (Apple's reason: clutter), concentric corners
    platform-idioms.md     iPhone / iPad / Mac / Vision Pro: tab bar vs sidebar vs ornaments, toolbars,
                           inspectors, sheets vs windows, pointer and keyboard, hit targets
    motion.md              springs, meaningful motion, Reduce Motion
    tokens.md              project has tokens → use them, never literals; project has none →
                           a recommended starter token set and how to introduce it
```

- **Sources:** Apple Human Interface Guidelines and WWDC25 sessions 219 (Meet Liquid Glass), 356 (Get to know the new design system), 323 (Build a SwiftUI app with the new design), fetched while writing. Every rule cites its source and is paraphrased, not copied (Apple's text is copyrighted). Seeded with the generic sections of ExampleApp's current `swiftui-design` skill ("Design Thinking", "Apple-Native Aesthetics", "What to AVOID"), which are the user's own text.
- **No duplication:** accessibility code patterns and Liquid Glass API mechanics stay in `swift:swiftui`; `design` links to them.
- **Numbers** (hit-target sizes per platform, etc.) are taken from the HIG at write time, with the page cited — not from memory.
- **Context cost:** in a repo with a project layer, "build a view" loads three SKILL.md files (~370 lines at the time of writing); references load on demand. Re-recorded 2026-09-26 (part-2 spec §8): the plugin's own bodies are now swiftui 161 + design 93 + concurrency 211 = 465 lines, and grow to ≈660 when `swift:testing` and `swift:review` land; always-loaded cost is the skill descriptions only (≈500 tokens for four; `swift:review` is slash-only and costs nothing), and a view task loads only the SKILL.md files it triggers.

## 6. Maintenance (part 4)

**`maintenance/check-apis.py`** — Python 3 stdlib only; network only to `developer.apple.com`.

1. **Resolve:** download Apple's per-framework doc indexes (`https://developer.apple.com/tutorials/data/index/<framework>`; the `swiftui` index held 8,418 entries on 2026-09-24, each with a title and a doc path such as `/documentation/swiftui/view/glasseffect(_:in:)`) and map every API name to its doc path automatically. The framework list lives in the manifest (SwiftUI plus whatever the skills use: Charts, WebKit, Observation, …).
2. **Manifest** `maintenance/apis.json` holds only what cannot be derived: recorded claims (e.g. `{"visionOS": false}` for "not on visionOS"), the page to use where a name has several overloads, which APIs go into `platform-availability.md`, and an ignore list for non-Apple names the snippet rules below miss.
3. **Check:** fetch `https://developer.apple.com/tutorials/data/documentation/<path>.json` for every resolved name; fail on 404, on deprecated/beta where the skill says otherwise, or when a recorded claim contradicts `metadata.platforms`.
4. **Coverage:** scan every `.md` under `plugins/swift/skills/` for API-shaped names in code spans and blocks (`.modifier(`, type names, `@Attribute`). Skip names the same snippet declares (`struct`/`class`/`enum`/`protocol`/`func`/`let`/`var`) and names on the ignore list; report any name no index resolves. Warn by default, fail with `--strict`. Scale on 2026-09-24: upstream's snippets hold ~290 `.name(` calls and ~1,030 capitalised identifiers, many of them example names (`AccountView`, `AppModel`, `Alice`).
5. **Generate:** `--write-table` rewrites the marked block in `platform-availability.md`.
6. **Cache:** `maintenance/.cache/` (gitignored); `--refresh` to bypass.
7. **Tests:** stdlib `unittest` with saved Apple JSON fixtures (doc pages and an index excerpt) for index lookup, parsing, claim checking, API-name extraction and the declared-name skip.

**`maintenance/upstream-diff.sh [ref]`** — temporary clone of `https://github.com/AvdLee/SwiftUI-Agent-Skill`, prints `git diff --stat` and the diff of `skills/swiftui-expert-skill/` between the baseline in `UPSTREAM.md` and `ref` (default: latest tag). Read-only: never writes to this repo. Porting is manual; after porting, bump the baseline and log it.

**`UPSTREAM.md`** — upstream URL, baseline tag + SHA, a Deviations table (file → what we changed → why), a Ported log (upstream ref → what we took).

**When to run:** by hand before pushing a new plugin version and when Apple ships a new SDK. Not in a git hook (network).

**Versioning.** SemVer in `plugins/swift/.claude-plugin/plugin.json`, starting at `0.1.0`. That is the only version home: the marketplace entry carries no `version` (Claude Code reads `plugin.json` first anyway, and two homes drift). Claude Code uses the version as the cache key: a push without a bump never reaches installs, and `plugin update` reports "already at the latest version" (docs, plugins-reference → Version management).

Release flow:

1. `changelog-release` (stamped into this repo by `/onboard-repo`) infers the bump from the commits since the last release, updates `plugin.json` and `CHANGELOG.md` and stages both. It never commits.
2. The user commits.
3. `claude plugin tag plugins/swift` creates the tag `swift--v<version>` after checking that `plugin.json` and the marketplace entry agree (`--dry-run` first).
4. Push the commit and the tag.

`/onboard-repo` is slash-only (`disable-model-invocation`), so the user runs it — the full default pass, as in the user's other repos. It needs the git repo, so it is a plan step after the scaffold and the upstream import. Its detection already lists `.claude-plugin/plugin.json` as a version home, and its docs walk skips `docs/superpowers/`.

## 7. Testing and verification

1. `claude plugin validate .` (marketplace) and `claude plugin validate plugins/swift` (manifest, skills) pass; `python3 maintenance/check-apis.py --strict` passes; `python3 -m unittest discover maintenance/tests` passes.
2. **Scenario tests (RED/GREEN)** as a `claude plugin eval` suite in `plugins/swift/evals/`: one case per scenario, graders for its criteria. `plugin eval` adds a no-plugin baseline run by itself (`--ablation with-without`), which is the RED run. `evals/results/` is gitignored. Every run costs model calls (agent runs plus an LLM judge, haiku by default). Scenarios:
   - scratch project, iOS 17.5 deployment target: "add a glass button" → `if #available(iOS 26, *)` with a material fallback;
   - scratch project, iOS + visionOS: "floating glass toolbar" → `#if os(visionOS)` branch with `glassBackgroundEffect`, `GlassEffectContainer` elsewhere;
   - "add a preview for this view" → `#Preview` inside `#if DEBUG`;
   - "build a settings screen" in a project without tokens → system text styles and semantic colours, `Form`/`Section`, `tokens.md` starter set suggested rather than literals scattered.
   The ExampleApp-specific scenarios live in the companion spec.
3. **Scoping.** After a `--scope project` install in a scratch Swift repo, `swift:swiftui` and `swift:design` are listed there and absent in a non-Swift repo (e.g. `~/Dev/claude-configs`). example-app's own install is the example-app session's step (companion spec §3), so this session doesn't edit example-app's settings.

## 8. Research record (2026-09-24)

Candidates deep-read (GitHub API metadata checked on 2026-09-24):

| Candidate | License | Last push | Verdict |
|---|---|---|---|
| AvdLee/SwiftUI-Agent-Skill `swiftui-expert-skill` (3,610★) | MIT | 2026-09-18 (tag 5.1.0) | **Base.** 6/6 Liquid Glass claims matched Apple JSON (incl. `Glass` has only `.regular`/`.clear`/`.identity`; `glassEffectUnion` not on visionOS). Gaps: no visionOS, no `#if DEBUG` preview rule, hard-coded example literals, `glassBackgroundEffect` absent. Scripts: stdlib Python wrapping local `xctrace`, no network. |
| twostraws/SwiftUI-Agent-Skill `swiftui-pro` (4,840★) | MIT | 2026-04-20 | Accurate (7/7), barely covers Liquid Glass. Borrow deprecated-API entries only. |
| Dimillian/Skills (3,980★) | MIT | 2026-03-29 | `liquid-glass.md:225` recommends `.scrollExtensionMode(.underSidebar)`, which has no Apple doc page; misses `backgroundExtensionEffect()`. Borrow view-ordering / subview-extraction rules only. |
| dickwu/apple-design-skill (791★) | none | 2026-09-22 | Accurate HIG review skill, 30–70K tokens per run. Cannot copy text (no license). |

Listed, not deep-read: rshankras/claude-code-apple-skills (MIT, design bundle incl. visionOS), CharlesWiltgen/Axiom, dpearson2699/swift-ios-skills (PolyForm), wshobson `mobile-ios-design`, wondelai `ios-hig-design`, Wholiver, heyimjames, haider-nawaz, 2dubu, Prisma-Labs-Dev, JordanCoin.

Apple platform data (doc JSON, `metadata.platforms`, checked 2026-09-24):

| API | visionOS | Notes |
|---|---|---|
| `glassEffect(_:in:)`, `GlassEffectContainer`, `Glass.interactive(_:)`, `GlassButtonStyle` / `.glassProminent` | **no** | iOS, iPadOS, Mac Catalyst, macOS, tvOS, watchOS 26.0 |
| `glassEffectUnion(id:namespace:)`, `glassEffectTransition(_:)`, `scrollEdgeEffectStyle(_:for:)` | no | same six platforms |
| `ToolbarSpacer`, `sharedBackgroundVisibility(_:)` | no | iOS, iPadOS, Mac Catalyst, macOS only |
| `tabViewBottomAccessory` | no | iOS, iPadOS, Mac Catalyst only |
| `backgroundExtensionEffect()`, `tabBarMinimizeBehavior(_:)`, `safeAreaBar(edge:alignment:spacing:content:)` | **yes** | all seven platforms |

Also named in Apple's "Adopting Liquid Glass": `rect(corners:isUniform:)`, `ConcentricRectangle` — verify slugs with `check-apis.py` before citing.

iOS/macOS 27 (WWDC26): Apple's WWDC26 SwiftUI guide lists toolbar-overflow APIs, `@State` as a macro, document-API changes and more, but reference pages for guessed slugs returned 404 on 2026-09-24. Upstream `latest-apis.md` already tracks 27.1 beta with `#available` gating. Add no 27-era API to our own files until `check-apis.py` resolves it.

Upstream at `5.1.0` (clone checked 2026-09-24, spec review): 33 reference files (10,113 lines), SKILL.md 154 lines; the skill folder also holds `agents/openai.yaml` and `assets/` (428 KB); scripts are called through `${SKILL_DIR}` in three files; `tests/test_record_trace.py` sits at the repo root.

`check-apis` prototype run against upstream 5.1.0 and 20 Apple framework indexes (2026-09-24, during planning):
- It found 877 API names; 165 don't resolve. Most are example types (`ContentView`, `AppModel`), trace symbols, Info.plist keys or prose words.
- Apple's index lacks five names upstream uses: `AXDateDataAxisDescriptor`, `VerticalTabViewStyle`, `navigationTransitionSource`, `navigationTransitionDestination` and `sliderNeutralValue`.
- The five were recorded as findings to decide on, not fixed.

Claude Code (docs and CLI 2.1.282, checked 2026-09-24):

- **Version.** The update cache key is, in order of precedence: `plugin.json` `version`, the marketplace-entry `version`, then the git commit SHA. With an explicit version, only a bump reaches installs.
- **Skill command name.** A plugin skill's frontmatter `name` replaces the folder name in the command: `/<plugin>:<name>`.
- **Skill directory.** Skill content references its own folder as `${CLAUDE_SKILL_DIR}`.
- **CLI.** `claude plugin validate`, `claude plugin eval` (cases + graders, no-plugin baseline) and `claude plugin tag` (`{name}--v{version}`) all exist, and `marketplace add` and `install` accept `--scope project`.

## 9. Verify during implementation

- Marketplace and plugin naming rules accept `swift-plugin` and `swift` (`claude plugin validate`); no clash with installed plugins (`swift-lsp` is distinct). Confirmed 2026-09-25, first release (0.1.0, `swift--v0.1.0`): `claude plugin validate` accepts the names (one warning: no marketplace description); `claude plugin list` shows `swift-lsp@claude-plugins-official` installed, but it is a different plugin name shipping an LSP server and no skills, so it neither clashes with `swift` nor with the `swift:swiftui` / `swift:design` skill commands.
- Private GitHub marketplace resolves with the existing `gh`/git credentials. Confirmed 2026-09-25: the private GitHub marketplace resolved with the existing credentials (`marketplace add` + `install --scope project` in a scratch repo).
- `claude plugin tag` accepts a marketplace entry without a `version` (`--dry-run`). Confirmed 2026-09-25: `claude plugin tag` accepted the marketplace entry without a `version`.
- `claude plugin eval` finds the suite in `plugins/swift/evals/` and runs the baseline arm against a `--plugin-dir`-style path target. Confirmed 2026-09-25: `claude plugin eval` found the suite in `plugins/swift/evals/`, and its `with-without` ablation ran the baseline (`without`) arm against the plugin's path target — e.g. `glass-button-ios17` WITH 1.00 vs W/OUT 0.67, `preview-debug-guard` WITH 1.00 vs W/OUT 0.50 (`plugins/swift/evals/results/2026-09-25T09-03-55-011Z/aggregate-result.json`, gitignored).
- Resolved in the spec review (§8): a `version` bump is required to refresh an install; `name: swiftui` yields `/swift:swiftui`. The `name: swiftui` → `/swift:swiftui` mapping was confirmed live 2026-09-25 (the live install listed `swift:swiftui` and `swift:design` in a scratch repo, and neither in `~/Dev/claude-configs`). The version-bump rule was confirmed live 2026-09-25: after the bump to 0.1.1 (`swift--v0.1.1`), a project-scope install updated from 0.1.0 to 0.1.1 (`claude plugin update` printed `updated from 0.1.0 to 0.1.1`).

## 10. Out of scope / later

- `swift:review` — on-demand HIG review of a screen (own text, run by hand).
- `swift:concurrency`, `swift:testing`.
- An optional claude-configs entry that registers the `swift-plugin` marketplace on a new machine without enabling it anywhere.

## 11. Working rules

- No commits, no push, no GitHub repo creation without the user's explicit OK at that step (user's global CLAUDE.md).
- `/onboard-repo` and every commit, tag and push in the release flow are run or approved by the user.
- Plan before building: this spec → `superpowers:writing-plans` → user picks the execution method.
