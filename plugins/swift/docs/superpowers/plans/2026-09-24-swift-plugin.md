# swift-plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the private `swift` Claude Code plugin (`swift:swiftui`, `swift:design`) in `~/Dev/claude_skills/swift-plugin`, with its Apple API checker, upstream-diff script and eval suite, and release it as `0.1.0` to the private GitHub repo `jack1913/swift-plugin`.

**Architecture:** One repo holds a single-plugin marketplace. Only `plugins/swift/` ships. It contains the upstream AvdLee skill (imported byte-for-byte, then patched in logged commits), our design skill and an eval suite. `maintenance/` never ships: a stdlib-Python checker (`check-apis.py` + the `apicheck` package) that resolves every API name in the skills against Apple's documentation JSON, a read-only upstream diff script and unit tests. Releases bump SemVer in `plugin.json` through the `changelog-release` skill and are tagged with `claude plugin tag`.

**Tech Stack:** Claude Code 2.1.282 (plugins, skills, `claude plugin validate|eval|tag`), Markdown, Python 3.13 stdlib (`unittest`, `urllib`), Bash, git, `gh`.

**Spec:** `docs/superpowers/specs/2026-09-24-swift-plugin-design.md`. Read it before starting; this plan argues from it.

## Global Constraints

- Repo `~/Dev/claude_skills/swift-plugin`; only `plugins/swift/` ships; GitHub `jack1913/swift-plugin`, private.
- Names, fixed (the example-app layer depends on them): marketplace `swift-plugin`, plugin `swift`, skills `swift:swiftui` and `swift:design`.
- Upstream: `https://github.com/AvdLee/SwiftUI-Agent-Skill`, folder `skills/swiftui-expert-skill/`, tag `5.1.0` = `b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`; local tag `upstream-5.1.0`.
- Borrowed text, pinned: twostraws/SwiftUI-Agent-Skill `be297ff80dddec529af1f9b1f1f114aab6c9d11c` ("Copyright (c) 2026 Paul Hudson.", MIT); Dimillian/Skills `05ba982bfeb0d77d3c97d4542b0ee15034d05f84` ("Copyright (c) 2026 Thomas Ricouard", MIT). Nothing from dickwu/apple-design-skill (no license) or dpearson2699/swift-ios-skills (PolyForm). Not taken from Dimillian: "no view models by default", `scrollExtensionMode(.underSidebar)`.
- The project-layer rule, word for word, in both skills: *If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict.*
- `swift:swiftui` keeps upstream's "Only adopt Liquid Glass when explicitly requested by the user"; when glass fits is `swift:design`'s job.
- Sources: every platform statement comes from Apple's doc JSON (checked by `check-apis.py`); every design rule cites its source and is paraphrased, never copied; numbers come from the HIG with the page cited; no 27-era API goes into our own files until `check-apis.py` resolves it.
- Maintenance code: Python 3 stdlib only. `check-apis.py` talks only to `developer.apple.com`; `upstream-diff.sh` only clones upstream into a temp dir.
- Versioning: SemVer only in `plugins/swift/.claude-plugin/plugin.json`; the marketplace entry has no `version`; `0.0.0` until the first release, which is `0.1.0`.
- Every change to `swift:swiftui` after the import is its own commit and a row in `UPSTREAM.md` → Deviations.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`); `changelog-release` infers the bump from them.
- Git: at the start of execution, ask the user once to approve the local commits and tags this plan lists. Pushing, `gh repo create` and installing into any repo each need their own OK at that step. Never `--no-verify`.
- Evals spend model calls. Before the first `claude plugin eval` run, ask the user for a `--max-cost-usd` ceiling and pass it on every run.
- Shell state does not persist between commands: every command below spells out its paths. `UP` always means `"${TMPDIR:-/tmp}/swift-plugin-upstream"`.

## Review Focus

1. **Apple answers 5xx, times out or the machine is offline.** `check-apis.py` must stop with exit 2 and name the URL. It must never report such a failure as a missing page, and never cache it. Pinned in Task 6 (`test_server_error_and_network_error_are_fetch_errors_not_404s`).
2. **Doc paths with operator characters or disambiguation suffixes** (`text/+(_:_:)`, `webview-swift.struct`). They must fetch the right URL and resolve to the right name. Pinned in Task 4 (`test_key_drops_arguments_and_disambiguation_suffix`) and Task 6 (`test_url_keeps_symbol_punctuation`).
3. **`platform-availability.md` with missing, duplicated or out-of-order markers, or a run with failing checks.** `--write-table` must refuse and leave the file untouched; it never appends a second block. Pinned in Task 6 (`test_missing_duplicate_or_reversed_markers_are_refused`) and Task 7 (`test_write_table_refuses_while_checks_fail`).
4. **A snippet that conforms to or extends an Apple type** (`struct CardView: View`, `extension Text`). The Apple type must still be checked, not skipped as "declared by the snippet". Pinned in Task 5 (`test_conformances_and_extensions_are_not_declarations`).
5. **Ignore-list rot.** An ignored name that no longer appears in any skill file, or that now resolves, must be reported, and it fails `--strict`. Pinned in Task 7 (`test_ignored_name_is_quiet_until_it_goes_stale`, `test_ignored_name_that_now_resolves_is_flagged`).

## File Structure

```
.claude-plugin/marketplace.json            marketplace "swift-plugin" → ./plugins/swift            (Task 1)
plugins/swift/.claude-plugin/plugin.json   name "swift", version                                    (Task 1)
plugins/swift/NOTICE.md                    third-party attributions + MIT texts                      (Task 2, 12)
plugins/swift/skills/swiftui/              upstream 5.1.0 + deviations                              (Task 1, 2, 10–12)
  LICENSE-upstream                         upstream MIT text                                         (Task 2)
  references/visionos.md                   ours                                                      (Task 10)
  references/platform-availability.md      ours; table generated by check-apis.py --write-table     (Task 10)
plugins/swift/skills/design/               swift:design, ours                                        (Task 13–15)
plugins/swift/evals/<case>/                claude plugin eval suite                                  (Task 9)
maintenance/check-apis.py                  CLI shim → apicheck.cli.main                              (Task 7)
maintenance/apicheck/apple.py              parse Apple index + symbol JSON, resolve names, check claims (Task 4)
maintenance/apicheck/extract.py            find API-shaped names in Markdown                         (Task 5)
maintenance/apicheck/manifest.py           load + validate apis.json                                 (Task 6)
maintenance/apicheck/fetch.py              cached HTTPS fetch from developer.apple.com               (Task 6)
maintenance/apicheck/table.py              render + splice the platform table                        (Task 6)
maintenance/apicheck/cli.py                argument parsing and the check run                        (Task 7)
maintenance/apis.json                      frameworks, APIs with claims, ignore list                 (Task 8, 10–15)
maintenance/upstream-diff.sh               read-only upstream diff                                   (Task 3)
maintenance/tests/                         unittest suites + fixtures + upstream test_record_trace.py (Task 2, 4–7)
UPSTREAM.md  README.md  .gitignore  CHANGELOG.md (from /onboard-repo, Task 17)
```

`apicheck/` is a package so the tests can import it; `check-apis.py` (the name the spec uses) is a 6-line shim.

---

### Task 1: Repository, upstream import and plugin manifests

**Files:**
- Create: git repo (`main`); `plugins/swift/skills/swiftui/**` (upstream copy); `.claude-plugin/marketplace.json`; `plugins/swift/.claude-plugin/plugin.json`; `.gitignore`; `README.md`; `UPSTREAM.md`
- Delete (commit 2): `plugins/swift/skills/swiftui/agents/`, `plugins/swift/skills/swiftui/assets/`
- Commit as-is: `docs/superpowers/specs/2026-09-24-swift-plugin-design.md`, `docs/superpowers/plans/2026-09-24-swift-plugin.md`

**Interfaces:**
- Produces: tag `upstream-5.1.0`; the `UPSTREAM.md` "Baseline tag" line (exact format in Step 7), which `upstream-diff.sh` (Task 3) parses; the Deviations table that every later swiftui task appends to; the upstream clone at `UP` (Tasks 2 and 12 read `UP/LICENSE` and `UP/tests/`).

- [ ] **Step 1: Confirm nothing exists yet**

Run: `git -C ~/Dev/claude_skills/swift-plugin rev-parse --show-toplevel; gh repo view jack1913/swift-plugin --json name`
Expected: `fatal: not a git repository` and a GitHub "Could not resolve to a Repository" error. If either exists, stop and ask the user.

- [ ] **Step 2: Clone upstream at the baseline and verify the SHA**

```bash
rm -rf "${TMPDIR:-/tmp}/swift-plugin-upstream"
git clone --quiet https://github.com/AvdLee/SwiftUI-Agent-Skill "${TMPDIR:-/tmp}/swift-plugin-upstream"
git -C "${TMPDIR:-/tmp}/swift-plugin-upstream" checkout --quiet 5.1.0
test "$(git -C "${TMPDIR:-/tmp}/swift-plugin-upstream" rev-parse HEAD)" = b24e68a965dc4b5bd2cc41dc60c094a26a9379ce && echo SHA-OK
```
Expected: `SHA-OK`.

- [ ] **Step 3: Commit 1 — the byte-for-byte import, tagged**

```bash
cd ~/Dev/claude_skills/swift-plugin
git init -b main
mkdir -p plugins/swift/skills
cp -R "${TMPDIR:-/tmp}/swift-plugin-upstream/skills/swiftui-expert-skill" plugins/swift/skills/swiftui
diff -r "${TMPDIR:-/tmp}/swift-plugin-upstream/skills/swiftui-expert-skill" plugins/swift/skills/swiftui && echo IDENTICAL
git add plugins/swift/skills/swiftui
git commit -m "chore: import AvdLee/SwiftUI-Agent-Skill skills/swiftui-expert-skill at 5.1.0" -m "Byte-for-byte copy of upstream b24e68a965dc4b5bd2cc41dc60c094a26a9379ce."
git tag -a upstream-5.1.0 -m "AvdLee/SwiftUI-Agent-Skill 5.1.0 (b24e68a) skills/swiftui-expert-skill"
git ls-files | wc -l
```
Expected: `IDENTICAL`; the file count equals `find "${TMPDIR:-/tmp}/swift-plugin-upstream/skills/swiftui-expert-skill" -type f | wc -l`.

- [ ] **Step 4: Commit 2 — drop Codex agent config and logos**

```bash
cd ~/Dev/claude_skills/swift-plugin
git rm -r --quiet plugins/swift/skills/swiftui/agents plugins/swift/skills/swiftui/assets
git commit -m "chore(swiftui): drop upstream agents/ and assets/" -m "Codex agent config and logos (~430 KB); Claude Code uses neither."
git diff --stat upstream-5.1.0 -- plugins/swift/skills/swiftui
```
Expected: the diffstat lists only `agents/openai.yaml`, `assets/logo-small.png`, `assets/logo.png`, `assets/logo.svg` as deleted.

- [ ] **Step 5: Write the manifests**

`.claude-plugin/marketplace.json`:

```json
{
  "name": "swift-plugin",
  "owner": { "name": "jack1913" },
  "plugins": [
    {
      "name": "swift",
      "source": "./plugins/swift",
      "description": "Correct, current, Apple-native SwiftUI: swift:swiftui (APIs and correctness) and swift:design (Apple-native design)."
    }
  ]
}
```

`plugins/swift/.claude-plugin/plugin.json` (`0.0.0` = unreleased; Task 18 makes it `0.1.0`):

```json
{
  "name": "swift",
  "version": "0.0.0",
  "description": "Correct, current, Apple-native SwiftUI: swift:swiftui (APIs and correctness, visionOS, previews) and swift:design (Apple-native design).",
  "author": { "name": "jack1913" },
  "repository": "https://github.com/jack1913/swift-plugin"
}
```

`.gitignore`:

```
.DS_Store
__pycache__/
maintenance/.cache/
plugins/swift/evals/results/
```

- [ ] **Step 6: Write `README.md`**

````markdown
# swift-plugin

Private Claude Code marketplace with one plugin, `swift`: skills that make an agent write correct, current, Apple-native SwiftUI.

| Skill | Covers |
|---|---|
| `swift:swiftui` | SwiftUI correctness and current APIs. A fork of [AvdLee/SwiftUI-Agent-Skill](https://github.com/AvdLee/SwiftUI-Agent-Skill) with visionOS, preview and platform-availability fixes (`UPSTREAM.md`) |
| `swift:design` | Apple-native design: hierarchy, typography, color, SF Symbols, Liquid Glass, platform idioms, motion, tokens |

## Enable it in a Swift repo

Run inside that repo. `--scope project` writes its committed `.claude/settings.json`; `--scope local` writes the gitignored `.claude/settings.local.json`.

```bash
claude plugin marketplace add jack1913/swift-plugin --scope project
claude plugin install swift@swift-plugin --scope project
```

A repo without these entries never sees the plugin. Installs are copies: a repo picks up a new release with `claude plugin marketplace update swift-plugin` and `claude plugin update swift@swift-plugin`.

## Work on it

| Task | Command |
|---|---|
| Try a change | `claude --plugin-dir ~/Dev/claude_skills/swift-plugin/plugins/swift` |
| Check APIs against Apple | `python3 maintenance/check-apis.py --strict` |
| Unit tests | `python3 -m unittest discover maintenance/tests` |
| Evals | `claude plugin eval plugins/swift --scaffold --trust-plugin --max-cost-usd <budget> --allow-tools Write Edit` |
| Upstream changes | `maintenance/upstream-diff.sh [ref]` |
| Validate manifests | `claude plugin validate . && claude plugin validate plugins/swift` |

Release flow and design: `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §6.

## Licenses

Third-party text and its MIT notices: `plugins/swift/NOTICE.md`. Upstream's license: `plugins/swift/skills/swiftui/LICENSE-upstream`.
````

- [ ] **Step 7: Write `UPSTREAM.md`**

```markdown
# Upstream

- **Upstream:** https://github.com/AvdLee/SwiftUI-Agent-Skill, folder `skills/swiftui-expert-skill/`, MIT
- **Baseline tag:** `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`)
- **Local import tag:** `upstream-5.1.0`, this repo's first commit: the folder byte-for-byte at the baseline

`git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows every change listed under Deviations. `maintenance/upstream-diff.sh [ref]` shows what upstream changed after the baseline. Porting is manual: read the diff, port what fits, bump the baseline above, add a Ported row.

## Deviations

| File | Change | Why |
|---|---|---|
| `agents/`, `assets/` | Deleted | Codex agent config and logos (~430 KB); Claude Code uses neither |

## Ported

| Upstream ref | What we took | Date |
|---|---|---|
| `5.1.0` | Initial import | 2026-09-24 |
```

- [ ] **Step 8: Validate**

Run: `cd ~/Dev/claude_skills/swift-plugin && claude plugin validate . ; echo "exit $?"; claude plugin validate plugins/swift ; echo "exit $?"`
Expected: both `exit 0`. Copy any warnings into the task report. The skill still carries `name: swiftui-expert-skill` until Task 2.

- [ ] **Step 9: Commit 3**

```bash
cd ~/Dev/claude_skills/swift-plugin
git add .claude-plugin plugins/swift/.claude-plugin .gitignore README.md UPSTREAM.md docs
git commit -m "chore: scaffold the swift-plugin marketplace and the swift plugin"
git status --short
```
Expected: `git status --short` prints nothing.

---

### Task 2: Mechanical `swift:swiftui` deviations

Four commits: the skill name and description, the script-path variable, license files, and the upstream test.

**Files:**
- Modify: `plugins/swift/skills/swiftui/SKILL.md:2-3` (frontmatter)
- Modify: every file containing `${SKILL_DIR}`: `SKILL.md` (5), `references/trace-analysis.md` (4), `references/trace-recording.md` (9)
- Create: `plugins/swift/skills/swiftui/LICENSE-upstream`, `plugins/swift/NOTICE.md`
- Create: `maintenance/tests/test_record_trace.py` (from `UP/tests/test_record_trace.py`)
- Modify: `UPSTREAM.md` (one Deviations row per commit)

**Interfaces:**
- Consumes: `UP` clone (Task 1).
- Produces: `/swift:swiftui` as the command name; `NOTICE.md` with an `## AvdLee/SwiftUI-Agent-Skill` section that Task 12 appends to.

- [ ] **Step 1: Rename the skill and widen its description**

In `plugins/swift/skills/swiftui/SKILL.md`, make three edits to the frontmatter.

1. Line 2: `name: swiftui-expert-skill` becomes `name: swiftui`.
2. In line 3, `for iOS or macOS` becomes `for iOS, iPadOS, macOS or visionOS`.
3. At the end of line 3, this text:

   ```text
   and Instruments `.trace` capture or analysis.
   ```

   becomes:

   ```text
   Instruments `.trace` capture or analysis, and visionOS glass alternatives (`glassBackgroundEffect`, ornaments), windows, volumes and immersive spaces.
   ```

Check: `sed -n 1,4p plugins/swift/skills/swiftui/SKILL.md`. Expected: `name: swiftui`; the description starts `Use when writing, reviewing, or refactoring SwiftUI code for iOS, iPadOS, macOS or visionOS,` and ends `windows, volumes and immersive spaces.`

- [ ] **Step 2: Verify the command name, then commit**

Run: `cd ~/Dev/claude_skills/swift-plugin && claude plugin validate plugins/swift; claude -p --plugin-dir plugins/swift --model haiku "Reply with only the names of the skills available to you that start with 'swift:', comma-separated, nothing else."`
Expected: validate exits 0; the reply contains `swift:swiftui`.

Append to `UPSTREAM.md` → Deviations:

```markdown
| `SKILL.md` frontmatter | `name: swiftui`; description names iOS, iPadOS, macOS, visionOS and the visionOS topics | Plugin skill command is `/swift:<name>`; visionOS work must trigger the skill |
```

```bash
git add plugins/swift/skills/swiftui/SKILL.md UPSTREAM.md
git commit -m "fix(swiftui): name the skill swiftui and cover visionOS in its description"
```

- [ ] **Step 3: Switch `${SKILL_DIR}` to `${CLAUDE_SKILL_DIR}` in every file**

```bash
cd ~/Dev/claude_skills/swift-plugin
rg -l '\$\{SKILL_DIR\}' plugins/swift/skills/swiftui | xargs sed -i '' 's/\${SKILL_DIR}/${CLAUDE_SKILL_DIR}/g'
rg -c '\$\{SKILL_DIR\}' plugins/swift/skills/swiftui; echo "old left: $?"
rg -c '\$\{CLAUDE_SKILL_DIR\}' plugins/swift/skills/swiftui
```
Expected: `old left: 1` (rg found nothing); counts `SKILL.md:5`, `references/trace-analysis.md:4`, `references/trace-recording.md:9`.

Append to Deviations:

```markdown
| `SKILL.md`, `references/trace-analysis.md`, `references/trace-recording.md` | `${SKILL_DIR}` → `${CLAUDE_SKILL_DIR}` (18 places) | Claude Code substitutes `${CLAUDE_SKILL_DIR}`; `${SKILL_DIR}` would leave commands pointing at `/scripts/…` |
```

```bash
git add plugins/swift/skills/swiftui UPSTREAM.md
git commit -m "fix(swiftui): run bundled scripts through \${CLAUDE_SKILL_DIR}"
```

- [ ] **Step 4: Ship upstream's license and a NOTICE with the plugin**

~~~bash
cd ~/Dev/claude_skills/swift-plugin
cp "${TMPDIR:-/tmp}/swift-plugin-upstream/LICENSE" plugins/swift/skills/swiftui/LICENSE-upstream
cat > plugins/swift/NOTICE.md <<'EOF'
# Third-party notices

The `swift` plugin contains text from the projects below, each under the MIT License. Each section says what was taken and carries that project's copyright and permission notice.

## AvdLee/SwiftUI-Agent-Skill

- Source: https://github.com/AvdLee/SwiftUI-Agent-Skill at `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`)
- Taken: `skills/swiftui/`, which is upstream's `skills/swiftui-expert-skill/` with the changes the repository's `UPSTREAM.md` lists. Files marked "New" there are this project's own.

```text
EOF
cat "${TMPDIR:-/tmp}/swift-plugin-upstream/LICENSE" >> plugins/swift/NOTICE.md
printf '```\n' >> plugins/swift/NOTICE.md
cmp plugins/swift/skills/swiftui/LICENSE-upstream "${TMPDIR:-/tmp}/swift-plugin-upstream/LICENSE" && rg -c 'Copyright \(c\) 2026 Antoine van der Lee' plugins/swift/NOTICE.md
~~~
Expected: `1`.

Append to Deviations:

```markdown
| `LICENSE-upstream` | New: upstream's MIT license text | Travels with every install (the plugin cache copies only `plugins/swift/`) |
```

```bash
git add plugins/swift/skills/swiftui/LICENSE-upstream plugins/swift/NOTICE.md UPSTREAM.md
git commit -m "docs: ship upstream's MIT license and a NOTICE with the plugin"
```

- [ ] **Step 5: Move upstream's recorder test into `maintenance/tests/`**

```bash
cd ~/Dev/claude_skills/swift-plugin
mkdir -p maintenance/tests
cp "${TMPDIR:-/tmp}/swift-plugin-upstream/tests/test_record_trace.py" maintenance/tests/test_record_trace.py
```

In `maintenance/tests/test_record_trace.py`, replace the `SCRIPT = (...)` block (upstream lines 12–18) with:

```python
SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "swift"
    / "skills"
    / "swiftui"
    / "scripts"
    / "record_trace.py"
)
```

Run: `python3 -m unittest discover maintenance/tests -v 2>&1 | tail -4`
Expected: `Ran 3 tests` … `OK`.

Append to Deviations:

```markdown
| (repo) `tests/test_record_trace.py` → `maintenance/tests/` | Path to `record_trace.py` now `plugins/swift/skills/swiftui/scripts/` | Outside the tagged folder; the test keeps covering the shipped script |
```

```bash
git add maintenance/tests/test_record_trace.py UPSTREAM.md
git commit -m "test: carry upstream's record_trace tests in maintenance/tests"
```

---

### Task 3: `maintenance/upstream-diff.sh`

**Files:**
- Create: `maintenance/upstream-diff.sh` (executable)

**Interfaces:**
- Consumes: the "Baseline tag" line in `UPSTREAM.md` (Task 1 Step 7).
- Produces: `maintenance/upstream-diff.sh [ref]`: exit 0 with a diff or "no upstream changes"; exit 2 on a missing baseline line or an unknown ref.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Show what upstream changed in skills/swiftui-expert-skill/ between our baseline (UPSTREAM.md) and a ref.
# Usage: maintenance/upstream-diff.sh [ref]   (default ref: upstream's newest tag)
# Read-only: clones into a temp dir and never writes to this repo. Porting is manual.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream_url="https://github.com/AvdLee/SwiftUI-Agent-Skill"
skill_path="skills/swiftui-expert-skill"

baseline="$(sed -n 's/^- \*\*Baseline tag:\*\* `\([^`]*\)`.*/\1/p' "$repo_root/UPSTREAM.md")"
if [[ -z "$baseline" ]]; then
  echo "error: UPSTREAM.md has no line like: - **Baseline tag:** \`5.1.0\` (...)" >&2
  exit 2
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone --quiet "$upstream_url" "$tmp/upstream"
cd "$tmp/upstream"

ref="${1:-$(git tag --sort=-v:refname | head -n 1)}"
for r in "$baseline" "$ref"; do
  if ! git rev-parse --verify --quiet "$r^{commit}" >/dev/null; then
    echo "error: upstream has no ref '$r'" >&2
    exit 2
  fi
done

echo "upstream: $upstream_url ($skill_path)"
echo "baseline: $baseline -> ref: $ref"
if [[ "$(git rev-parse "$baseline^{commit}")" == "$(git rev-parse "$ref^{commit}")" ]]; then
  echo "no upstream changes: $ref is the baseline"
  exit 0
fi
git --no-pager diff --stat "$baseline" "$ref" -- "$skill_path"
echo
git --no-pager diff "$baseline" "$ref" -- "$skill_path"
```

Run: `chmod +x ~/Dev/claude_skills/swift-plugin/maintenance/upstream-diff.sh`

- [ ] **Step 2: Exercise every path, from another directory, and confirm it wrote nothing**

```bash
cd "${TMPDIR:-/tmp}"
S=~/Dev/claude_skills/swift-plugin/maintenance/upstream-diff.sh
"$S"; echo "exit $?"
"$S" 5.0.0 > "${TMPDIR:-/tmp}/ud.out"; echo "exit $?"; head -4 "${TMPDIR:-/tmp}/ud.out"; rg -c '^diff --git' "${TMPDIR:-/tmp}/ud.out"
"$S" no-such-ref; echo "exit $?"
git -C ~/Dev/claude_skills/swift-plugin status --short
```
Expected:
- no ref: `baseline: 5.1.0 -> ref: 5.1.0`, `no upstream changes`, `exit 0` (while 5.1.0 is upstream's newest tag; if a newer tag exists, a real diff prints instead, which is also correct);
- `5.0.0`: `exit 0`, a diffstat, and a non-zero count of `diff --git` lines;
- `no-such-ref`: `error: upstream has no ref 'no-such-ref'`, `exit 2`;
- `git status --short`: only `?? maintenance/upstream-diff.sh`.

- [ ] **Step 3: Commit**

```bash
cd ~/Dev/claude_skills/swift-plugin
git add maintenance/upstream-diff.sh
git commit -m "feat(maintenance): add read-only upstream-diff.sh"
```

---

### Task 4: `apicheck` — Apple documentation JSON

**Files:**
- Create: `maintenance/apicheck/__init__.py` (empty), `maintenance/apicheck/apple.py`
- Create: `maintenance/tests/fixtures/index-swiftui.json`, `glasseffect.json`, `glassbackgroundeffect.json`, `cornerradius.json`
- Test: `maintenance/tests/test_apple.py`

**Interfaces:**
- Produces (used by Tasks 6 and 7):
  - `PLATFORMS: tuple[str, ...]` = `("iOS", "iPadOS", "Mac Catalyst", "macOS", "visionOS", "watchOS", "tvOS")`
  - `IndexEntry(path: str, kind: str, deprecated: bool, beta: bool)` with `.key -> str`
  - `Availability(introduced: str | None, deprecated_at: str | None, beta: bool, unavailable: bool)`
  - `parse_index(data: dict) -> list[IndexEntry]` (raises `ValueError`)
  - `build_lookup(entries) -> dict[str, list[IndexEntry]]`
  - `resolve(text: str, kind: str, lookup) -> list[IndexEntry]`; `kind` ∈ `"member" | "type" | "attribute"`
  - `parse_platforms(page: dict) -> dict[str, Availability]` (raises `ValueError`)
  - `check_claims(name: str, claims: dict, platforms) -> list[str]` (raises `ValueError` on an unknown claim key)

Facts behind the fixtures (checked 2026-09-24): an index is `{"interfaceLanguages": {"swift": [module node]}}`. Nodes carry `title`, `path` (`/documentation/…`, or null for group markers), `type`, `children`, and optionally `deprecated` / `beta`. A symbol can be listed under several topics. A symbol page has `metadata.platforms[]` with `name`, `introducedAt`, `deprecated`, `deprecatedAt`, `beta`, `unavailable`, and Apple marks upcoming deprecations with `deprecatedAt` while `deprecated` is still `false` (`cornerRadius(_:antialiased:)`: `deprecatedAt: "27.2"`). Paths carry disambiguation suffixes such as `webkit/webview-swift.struct`.

- [ ] **Step 1: Write the fixtures** (trimmed real data)

`maintenance/tests/fixtures/index-swiftui.json`:

```json
{
  "interfaceLanguages": {
    "swift": [
      {
        "title": "SwiftUI",
        "path": "/documentation/swiftui",
        "type": "module",
        "children": [
          {"title": "Essentials", "path": null, "type": "groupMarker"},
          {"title": "Adopting Liquid Glass", "path": "/documentation/technologyoverviews/adopting-liquid-glass", "type": "article"},
          {"title": "GlassEffectContainer", "path": "/documentation/swiftui/glasseffectcontainer", "type": "struct"},
          {"title": "View", "path": "/documentation/swiftui/view", "type": "protocol", "children": [
            {"title": "func glassEffect(Glass, in: some Shape) -> some View", "path": "/documentation/swiftui/view/glasseffect(_:in:)", "type": "method"},
            {"title": "func glassBackgroundEffect<S>(in: S, displayMode: GlassBackgroundDisplayMode) -> some View", "path": "/documentation/swiftui/view/glassbackgroundeffect(in:displaymode:)", "type": "method"},
            {"title": "func cornerRadius(CGFloat, antialiased: Bool) -> some View", "path": "/documentation/swiftui/view/cornerradius(_:antialiased:)", "type": "method", "deprecated": true}
          ]},
          {"title": "Text", "path": "/documentation/swiftui/text", "type": "struct", "children": [
            {"title": "func bold() -> Text", "path": "/documentation/swiftui/text/bold()", "type": "method"}
          ]},
          {"title": "macro Previewable()", "path": "/documentation/swiftui/previewable()", "type": "macro"},
          {"title": "WebView", "path": "/documentation/webkit/webview-swift.struct", "type": "struct"}
        ]
      }
    ]
  }
}
```

`maintenance/tests/fixtures/glasseffect.json`:

```json
{"metadata":{"title":"glassEffect(_:in:)","platforms":[{"beta":false,"deprecated":false,"introducedAt":"26.0","name":"iOS","unavailable":false},{"beta":false,"deprecated":false,"introducedAt":"26.0","name":"iPadOS","unavailable":false},{"beta":false,"deprecated":false,"introducedAt":"26.0","name":"Mac Catalyst","unavailable":false},{"beta":false,"deprecated":false,"introducedAt":"26.0","name":"macOS","unavailable":false},{"beta":false,"deprecated":false,"introducedAt":"26.0","name":"tvOS","unavailable":false},{"beta":false,"deprecated":false,"introducedAt":"26.0","name":"watchOS","unavailable":false}]}}
```

`maintenance/tests/fixtures/glassbackgroundeffect.json`:

```json
{"metadata":{"title":"glassBackgroundEffect(in:displayMode:)","platforms":[{"beta":false,"deprecated":false,"introducedAt":"1.0","name":"visionOS","unavailable":false}]}}
```

`maintenance/tests/fixtures/cornerradius.json`:

```json
{"metadata":{"title":"cornerRadius(_:antialiased:)","platforms":[{"beta":false,"deprecated":false,"deprecatedAt":"27.2","introducedAt":"13.0","message":"Use `clipShape` or `fill` instead.","name":"iOS","unavailable":false},{"beta":false,"deprecated":false,"deprecatedAt":"27.2","introducedAt":"10.15","message":"Use `clipShape` or `fill` instead.","name":"macOS","unavailable":false},{"beta":false,"deprecated":false,"deprecatedAt":"27.2","introducedAt":"1.0","message":"Use `clipShape` or `fill` instead.","name":"visionOS","unavailable":false}]}}
```

- [ ] **Step 2: Write the failing test** — `maintenance/tests/test_apple.py`

```python
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck import apple  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ParseIndexTests(unittest.TestCase):
    def setUp(self):
        self.entries = apple.parse_index(fixture("index-swiftui.json"))
        self.lookup = apple.build_lookup(self.entries)

    def test_flattens_nested_children_and_skips_nodes_without_a_path(self):
        paths = {e.path for e in self.entries}
        self.assertIn("swiftui/view/glasseffect(_:in:)", paths)
        self.assertIn("swiftui/text/bold()", paths)
        self.assertNotIn(None, paths)
        self.assertEqual(len(self.entries), 11)

    def test_key_drops_arguments_and_disambiguation_suffix(self):
        keys = {e.path: e.key for e in self.entries}
        self.assertEqual(keys["swiftui/view/glasseffect(_:in:)"], "glasseffect")
        self.assertEqual(keys["webkit/webview-swift.struct"], "webview")

    def test_reads_deprecated_flag(self):
        (entry,) = self.lookup["cornerradius"]
        self.assertTrue(entry.deprecated)

    def test_symbol_listed_under_two_topics_appears_once(self):
        node = {"title": "Text", "path": "/documentation/swiftui/text", "type": "struct"}
        data = {"interfaceLanguages": {"swift": [{"title": "A", "path": None, "children": [node]}, node]}}
        self.assertEqual(len(apple.parse_index(data)), 1)

    def test_rejects_data_that_is_not_an_index(self):
        with self.assertRaises(ValueError):
            apple.parse_index({"metadata": {}})


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.lookup = apple.build_lookup(apple.parse_index(fixture("index-swiftui.json")))

    def test_member_resolves_to_method(self):
        self.assertEqual(apple.resolve("glassEffect", "member", self.lookup)[0].path, "swiftui/view/glasseffect(_:in:)")

    def test_type_resolves_through_disambiguated_path(self):
        self.assertEqual(apple.resolve("WebView", "type", self.lookup)[0].kind, "struct")

    def test_attribute_resolves_to_macro(self):
        self.assertEqual(apple.resolve("Previewable", "attribute", self.lookup)[0].kind, "macro")

    def test_kind_must_match(self):
        self.assertEqual(apple.resolve("text", "member", self.lookup), [])  # Text is a struct, not a .text( member
        self.assertEqual(apple.resolve("Missing", "type", self.lookup), [])


class ParsePlatformsTests(unittest.TestCase):
    def test_platforms_without_visionos(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        self.assertNotIn("visionOS", platforms)
        self.assertEqual(platforms["iOS"].introduced, "26.0")
        self.assertIsNone(platforms["iOS"].deprecated_at)

    def test_deprecated_at_version(self):
        platforms = apple.parse_platforms(fixture("cornerradius.json"))
        self.assertEqual(platforms["macOS"].deprecated_at, "27.2")

    def test_deprecated_flag_without_version(self):
        page = {"metadata": {"platforms": [{"name": "iOS", "introducedAt": "13.0", "deprecated": True}]}}
        self.assertEqual(apple.parse_platforms(page)["iOS"].deprecated_at, "?")

    def test_page_without_platforms_is_an_error(self):
        with self.assertRaises(ValueError):
            apple.parse_platforms({"metadata": {"title": "An article"}})


class CheckClaimsTests(unittest.TestCase):
    def test_matching_claims_pass(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        claims = {"visionOS": False, "iOS": "26.0", "macOS": True, "deprecated": False, "beta": False}
        self.assertEqual(apple.check_claims("glassEffect(_:in:)", claims, platforms), [])

    def test_wrong_platform_claim_is_reported(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        (problem,) = apple.check_claims("glassEffect(_:in:)", {"visionOS": True}, platforms)
        self.assertIn("visionOS=True", problem)
        self.assertIn("Apple says False", problem)

    def test_wrong_version_claim_is_reported(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        (problem,) = apple.check_claims("glassEffect(_:in:)", {"iOS": "18.0"}, platforms)
        self.assertIn("Apple says '26.0'", problem)

    def test_deprecation_claim_is_checked(self):
        platforms = apple.parse_platforms(fixture("cornerradius.json"))
        self.assertEqual(len(apple.check_claims("cornerRadius(_:antialiased:)", {"deprecated": False}, platforms)), 1)

    def test_unknown_claim_key_raises(self):
        with self.assertRaises(ValueError):
            apple.check_claims("x", {"visionos": False}, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it to see it fail**

Run: `cd ~/Dev/claude_skills/swift-plugin && python3 -m unittest maintenance/tests/test_apple.py 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'apicheck'`.

- [ ] **Step 4: Implement** — `maintenance/apicheck/__init__.py` (empty) and `maintenance/apicheck/apple.py`:

```python
"""Parse Apple's documentation JSON: framework navigator indexes and symbol pages."""
from __future__ import annotations

from dataclasses import dataclass

PLATFORMS = ("iOS", "iPadOS", "Mac Catalyst", "macOS", "visionOS", "watchOS", "tvOS")

TYPE_KINDS = frozenset({"struct", "class", "enum", "protocol", "typealias", "associatedtype", "actor", "module"})
MEMBER_KINDS = frozenset({"method", "property", "init", "case", "func", "subscript", "op"})
ATTRIBUTE_KINDS = TYPE_KINDS | {"macro"}
# Capitalised names can also be C-style global functions (NSLocalizedString, CGImageSourceCreateWithData).
KINDS_FOR = {"member": MEMBER_KINDS, "type": TYPE_KINDS | {"func"}, "attribute": ATTRIBUTE_KINDS}

DOC_PREFIX = "/documentation/"


@dataclass(frozen=True)
class IndexEntry:
    path: str  # below /documentation/, e.g. "swiftui/view/glasseffect(_:in:)"
    kind: str  # Apple's node type: "method", "struct", "macro", ...
    deprecated: bool
    beta: bool

    @property
    def key(self) -> str:
        """Lower-cased name without arguments or disambiguation: glasseffect(_:in:) → glasseffect, webview-swift.struct → webview."""
        return self.path.rsplit("/", 1)[-1].split("(", 1)[0].split("-", 1)[0]


@dataclass(frozen=True)
class Availability:
    introduced: str | None
    deprecated_at: str | None  # a version, or "?" when Apple flags it deprecated without one
    beta: bool
    unavailable: bool


def parse_index(data: dict) -> list[IndexEntry]:
    """Flatten a navigator index (tutorials/data/index/<framework>) into symbol entries."""
    try:
        stack = list(data["interfaceLanguages"]["swift"])
    except (KeyError, TypeError) as exc:
        raise ValueError("not an Apple navigator index: no interfaceLanguages.swift") from exc
    entries, seen = [], set()
    while stack:
        node = stack.pop()
        stack.extend(node.get("children") or ())
        path = node.get("path")
        if not path or not path.startswith(DOC_PREFIX) or path in seen:
            continue  # group markers have no path; a symbol listed under several topics appears once
        seen.add(path)
        entries.append(IndexEntry(
            path=path[len(DOC_PREFIX):],
            kind=node.get("type", ""),
            deprecated=bool(node.get("deprecated")),
            beta=bool(node.get("beta")),
        ))
    return entries


def build_lookup(entries: list[IndexEntry]) -> dict[str, list[IndexEntry]]:
    lookup: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        lookup.setdefault(entry.key, []).append(entry)
    return lookup


def resolve(text: str, kind: str, lookup: dict[str, list[IndexEntry]]) -> list[IndexEntry]:
    """Index entries a name can refer to: .name( calls → members, Capitalised → types, @Name → types and macros."""
    allowed = KINDS_FOR[kind]
    return [e for e in lookup.get(text.lower(), ()) if e.kind in allowed]


def parse_platforms(page: dict) -> dict[str, Availability]:
    """Read metadata.platforms from a symbol page (tutorials/data/documentation/<path>.json)."""
    try:
        platforms = page["metadata"]["platforms"]
    except (KeyError, TypeError) as exc:
        raise ValueError("symbol page has no metadata.platforms") from exc
    result = {}
    for p in platforms:
        result[p["name"]] = Availability(
            introduced=p.get("introducedAt"),
            deprecated_at=p.get("deprecatedAt") or ("?" if p.get("deprecated") else None),
            beta=bool(p.get("beta")),
            unavailable=bool(p.get("unavailable")),
        )
    return result


def check_claims(name: str, claims: dict, platforms: dict[str, Availability]) -> list[str]:
    """Compare a manifest entry's recorded claims with Apple's platform data; return one line per mismatch."""
    problems = []
    for key, expected in claims.items():
        if key == "deprecated":
            actual = any(a.deprecated_at for a in platforms.values())
        elif key == "beta":
            actual = any(a.beta for a in platforms.values())
        elif key in PLATFORMS:
            a = platforms.get(key)
            if a is None or a.unavailable:
                actual = False
            elif isinstance(expected, str):
                actual = a.introduced
            else:
                actual = True
        else:
            raise ValueError(f"{name}: unknown claim {key!r}")
        if actual != expected:
            problems.append(f"{name}: skill says {key}={expected!r}, Apple says {actual!r}")
    return problems
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `python3 -m unittest maintenance/tests/test_apple.py 2>&1 | tail -3`
Expected: `Ran 18 tests` … `OK`.

- [ ] **Step 6: Commit**

```bash
git add maintenance/apicheck/__init__.py maintenance/apicheck/apple.py maintenance/tests/test_apple.py maintenance/tests/fixtures
git commit -m "feat(maintenance): parse Apple doc indexes and symbol pages"
```

---

### Task 5: `apicheck` — API-shaped names in Markdown

**Files:**
- Create: `maintenance/apicheck/extract.py`
- Test: `maintenance/tests/test_extract.py`

**Interfaces:**
- Produces (used by Task 7):
  - `Name(text: str, kind: str)`, frozen; `kind` ∈ `"member" | "type" | "attribute"` (matches `apple.resolve`)
  - `code_fragments(markdown: str) -> list[str]`
  - `names_in(fragment: str) -> set[Name]`
  - `declared_names(fragments: list[str]) -> set[str]`
  - `scan(root: Path) -> dict[Name, list[Path]]`

Rules (the spec's §6 "API-shaped names", made precise):
- Code means fenced blocks whose info string is empty or starts with `swift` (``` or ~~~), plus inline spans. String literals, comments, `#if`/`#else`/`#endif` lines and `import` lines are stripped first.
- Member: `.name(`, unless the receiver is a lower-case identifier (`model.load(`, a call on a variable). Chains (`).bold(`), implicit members (`(.system(`) and static calls (`Font.system(`) count. An inline span that is a whole symbol signature (`scrollEdgeEffectStyle(_:for:)`) counts as that member.
- Type: a Capitalised identifier of two or more characters that doesn't follow `@`. Attribute: `@Name`.
- A name the same file declares (`struct`/`class`/`enum`/`protocol`/`actor`/`typealias`/`associatedtype`/`func`/`var`/`let`/`case`, or a generic parameter of a declaration) is skipped for that file. Conformances and extensions declare nothing.

On upstream 5.1.0 these rules find 877 names, and 165 of them don't resolve (checked 2026-09-24). Task 8 handles them.

- [ ] **Step 1: Write the failing test** — `maintenance/tests/test_extract.py`

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck.extract import Name, code_fragments, declared_names, names_in, scan  # noqa: E402


def names(markdown: str) -> set[tuple[str, str]]:
    found = set()
    for fragment in code_fragments(markdown):
        found |= {(n.text, n.kind) for n in names_in(fragment)}
    return found


class FragmentTests(unittest.TestCase):
    def test_swift_and_unlabelled_fences_are_code_other_languages_are_not(self):
        md = "```swift\nGlassEffectContainer {}\n```\n```\nForEach {}\n```\n```bash\nPythonThing --x\n```\n"
        found = names(md)
        self.assertIn(("GlassEffectContainer", "type"), found)
        self.assertIn(("ForEach", "type"), found)
        self.assertNotIn(("PythonThing", "type"), found)

    def test_tilde_fence_and_info_string_extras(self):
        self.assertIn(("Toggle", "type"), names("~~~swift title=\"x\"\nToggle()\n~~~\n"))

    def test_inline_spans_are_code(self):
        self.assertIn(("glassEffect", "member"), names("Use `.glassEffect()` here."))

    def test_signature_span_counts_as_member(self):
        self.assertIn(("scrollEdgeEffectStyle", "member"), names("See `scrollEdgeEffectStyle(_:for:)`."))

    def test_strings_comments_directives_and_imports_are_dropped(self):
        md = '```swift\nimport SwiftUI\n#if DEBUG\nText("NotAType") // CommentType\n/* BlockType */\n#endif\n```\n'
        found = names(md)
        self.assertIn(("Text", "type"), found)
        for gone in ("NotAType", "CommentType", "BlockType", "DEBUG", "SwiftUI"):
            self.assertNotIn((gone, "type"), found)


class NamesInTests(unittest.TestCase):
    def test_modifier_chain_and_implicit_members(self):
        found = {(n.text, n.kind) for n in names_in('Text("x")\n    .bold()\n    .font(.system(size: 12))')}
        self.assertTrue({("bold", "member"), ("font", "member"), ("system", "member")} <= found)

    def test_calls_on_variables_are_skipped_but_static_calls_are_kept(self):
        found = {n.text for n in names_in("model.load()\nself.reload()\nFont.system(size: 1)")}
        self.assertNotIn("load", found)
        self.assertNotIn("reload", found)
        self.assertIn("system", found)

    def test_attribute_is_not_also_a_type(self):
        found = names_in("@State private var x = 0")
        self.assertIn(Name("State", "attribute"), found)
        self.assertNotIn(Name("State", "type"), found)

    def test_single_letters_are_generic_parameters(self):
        self.assertNotIn(Name("T", "type"), names_in("func f<T>(_ x: T) {}"))


class DeclaredNamesTests(unittest.TestCase):
    def test_declarations_and_generic_parameters(self):
        code = "struct CardView<Content: View>: View {\n  let title: String\n  func load() {}\n}\nenum Phase { case idle }"
        declared = declared_names([code])
        self.assertTrue({"CardView", "Content", "title", "load", "Phase", "idle"} <= declared)

    def test_conformances_and_extensions_are_not_declarations(self):
        declared = declared_names(["struct CardView: View {}\nextension Text {}"])
        self.assertNotIn("View", declared)
        self.assertNotIn("Text", declared)


class ScanTests(unittest.TestCase):
    def test_maps_names_to_files_and_skips_names_a_file_declares(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            (root / "a" / "one.md").write_text("```swift\nstruct CardView: View { var body: some View { Text(\"\") } }\n```\n")
            (root / "two.md").write_text("Use `CardView` and `.glassEffect()`.\n")
            found = scan(root)
            self.assertEqual(found[Name("Text", "type")], [root / "a" / "one.md"])
            self.assertEqual(found[Name("CardView", "type")], [root / "two.md"])  # declared only in one.md
            self.assertIn(Name("glassEffect", "member"), found)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest maintenance/tests/test_extract.py 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'apicheck.extract'`.

- [ ] **Step 3: Implement** — `maintenance/apicheck/extract.py`

```python
"""Find API-shaped names in the skills' Markdown: .name( calls, Capitalised identifiers, @Attributes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SWIFT_FENCES = frozenset({"", "swift"})
BUILTIN_IGNORES = frozenset({"Self", "Type", "Protocol", "Any"})

_FENCE = re.compile(r"^(```|~~~)[ \t]*([^\n]*)\n(.*?)^\1[ \t]*$", re.M | re.S)
_INLINE = re.compile(r"`([^`\n]+)`")
_TRIPLE_STRING = re.compile(r'"""(?:.|\n)*?"""')
_STRING = re.compile(r'"(?:\\.|[^"\\\n])*"')
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_DIRECTIVE = re.compile(r"^[ \t]*#(?:if|elseif|else|endif)\b[^\n]*", re.M)
_IMPORT = re.compile(r"^[ \t]*(?:@testable[ \t]+)?import[ \t]+[^\n]*", re.M)
_MEMBER = re.compile(r"\.([a-z]\w*)\(")
_RECEIVER = re.compile(r"(\w+)[?!]*$")
_SIGNATURE = re.compile(r"\.?([a-z]\w*)\((?:\w*:)*\)")
_TYPE = re.compile(r"(?<![@\w])([A-Z][A-Za-z0-9_]*)\b")
_ATTRIBUTE = re.compile(r"@([A-Z]\w*)")
_DECL = re.compile(r"\b(?:struct|class|enum|protocol|actor|typealias|associatedtype|func|var|let|case)\s+([A-Za-z_]\w*)")
_GENERIC_DECL = re.compile(r"\b(?:struct|class|enum|actor|protocol|func|init|typealias)\b[^<{(\n]*<([^<>]*)>")


@dataclass(frozen=True)
class Name:
    text: str
    kind: str  # "member" (.name( call or name(_:) span), "type" (Capitalised) or "attribute" (@Name)


def strip_code(code: str) -> str:
    """Drop string literals, comments, #if lines and import lines so only code remains."""
    code = _TRIPLE_STRING.sub('""', code)
    code = _STRING.sub('""', code)
    code = _BLOCK_COMMENT.sub(" ", code)
    code = _LINE_COMMENT.sub("", code)
    code = _DIRECTIVE.sub("", code)
    return _IMPORT.sub("", code)


def code_fragments(markdown: str) -> list[str]:
    """Swift code from fenced blocks (info string empty or starting with "swift") and from inline spans."""
    fragments = []

    def take_fence(match: re.Match) -> str:
        info = match.group(2).split()
        if (info[0].lower() if info else "") in SWIFT_FENCES:
            fragments.append(strip_code(match.group(3)))
        return "\n"

    prose = _FENCE.sub(take_fence, markdown)
    fragments.extend(strip_code(span) for span in _INLINE.findall(prose))
    return fragments


def _members(code: str):
    for match in _MEMBER.finditer(code):
        receiver = _RECEIVER.search(code, max(0, match.start() - 80), match.start())
        if receiver and not receiver.group(1)[0].isupper():
            continue  # a call on a variable, e.g. model.load(
        yield match.group(1)


def names_in(fragment: str) -> set[Name]:
    found = {Name(n, "member") for n in _members(fragment)}
    signature = _SIGNATURE.fullmatch(fragment.strip())
    if signature:
        found.add(Name(signature.group(1), "member"))
    found |= {Name(n, "attribute") for n in _ATTRIBUTE.findall(fragment)}
    found |= {Name(n, "type") for n in _TYPE.findall(fragment) if len(n) > 1}
    return found


def declared_names(fragments: list[str]) -> set[str]:
    """Names the snippets themselves declare: types, functions, properties, cases, generic parameters."""
    declared = set()
    for code in fragments:
        declared.update(_DECL.findall(code))
        for params in _GENERIC_DECL.findall(code):
            for part in params.split(","):
                ident = part.split(":")[0].strip()
                if ident.isidentifier():
                    declared.add(ident)
    return declared


def scan(root: Path) -> dict[Name, list[Path]]:
    """Every API-shaped name in root/**/*.md → the files that use it, minus names a file declares itself."""
    found: dict[Name, list[Path]] = {}
    for md in sorted(root.rglob("*.md")):
        fragments = code_fragments(md.read_text(encoding="utf-8"))
        declared = declared_names(fragments)
        names = set().union(*(names_in(f) for f in fragments))
        for name in sorted(names, key=lambda n: (n.text, n.kind)):
            if name.text not in declared and name.text not in BUILTIN_IGNORES:
                found.setdefault(name, []).append(md)
    return found
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m unittest maintenance/tests/test_extract.py 2>&1 | tail -3`
Expected: `Ran 12 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add maintenance/apicheck/extract.py maintenance/tests/test_extract.py
git commit -m "feat(maintenance): extract API-shaped names from skill Markdown"
```

---

### Task 6: `apicheck` — manifest, cached fetch and platform table

**Files:**
- Create: `maintenance/apicheck/manifest.py`, `maintenance/apicheck/fetch.py`, `maintenance/apicheck/table.py`
- Test: `maintenance/tests/test_manifest.py`, `maintenance/tests/test_fetch.py`, `maintenance/tests/test_table.py`

**Interfaces:**
- Consumes: `apple.PLATFORMS`, `apple.Availability`, `apple.parse_platforms` (Task 4).
- Produces (used by Task 7):
  - `manifest.ManifestError(ValueError)`; `ApiEntry(name, path, claims: dict, table: bool)`; `Manifest(frameworks: tuple[str, ...], apis: tuple[ApiEntry, ...], ignore: dict[str, str])`; `load_manifest(path: Path) -> Manifest`
  - `fetch.NotFound`, `fetch.FetchError`; `url_for(rel: str) -> str`; `Fetcher(cache_dir: Path, refresh: bool = False, opener=urlopen)` with `.index(framework) -> dict` and `.page(doc_path) -> dict`
  - `table.BEGIN`, `table.END`; `render_table(rows: list[tuple[str, str, dict[str, Availability]]]) -> str`; `replace_block(text: str, table: str) -> str` (raises `ValueError`)

`apis.json` format (the spec's §6 "Manifest"):

```json
{
  "frameworks": ["swiftui", "swift"],
  "apis": [
    {"name": "glassEffect(_:in:)", "path": "swiftui/view/glasseffect(_:in:)", "claims": {"visionOS": false, "iOS": "26.0"}, "table": true}
  ],
  "ignore": {"reason for a group of names": ["ContentView", "CardView"]}
}
```

Claims: `deprecated` / `beta` take `true`/`false`. Each platform in `PLATFORMS` takes `true`/`false` (available) or an introduced version string. `table: true` puts the row into `platform-availability.md`.

- [ ] **Step 1: Write the failing tests**

`maintenance/tests/test_manifest.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck.manifest import ManifestError, load_manifest  # noqa: E402

VALID = {
    "frameworks": ["swiftui"],
    "apis": [
        {"name": "glassEffect(_:in:)", "path": "swiftui/view/glasseffect(_:in:)", "claims": {"visionOS": False, "iOS": "26.0"}, "table": True},
        {"name": "GlassEffectContainer", "path": "swiftui/glasseffectcontainer"},
    ],
    "ignore": {"example views": ["CardView", "ContentView"]},
}


class LoadManifestTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apis.json"
            path.write_text(json.dumps(data))
            return load_manifest(path)

    def test_valid_manifest(self):
        m = self.load(VALID)
        self.assertEqual(m.frameworks, ("swiftui",))
        self.assertEqual(m.apis[0].claims, {"visionOS": False, "iOS": "26.0"})
        self.assertTrue(m.apis[0].table)
        self.assertFalse(m.apis[1].table)
        self.assertEqual(m.ignore["CardView"], "example views")

    def assertRejected(self, data, fragment):
        with self.assertRaises(ManifestError) as ctx:
            self.load(data)
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_top_level_key(self):
        self.assertRejected({**VALID, "extra": 1}, "unknown keys")

    def test_frameworks_required(self):
        self.assertRejected({**VALID, "frameworks": []}, "frameworks")

    def test_misspelled_platform_claim(self):
        bad = {**VALID, "apis": [{"name": "x", "path": "swiftui/x", "claims": {"visionos": False}}]}
        self.assertRejected(bad, "bad claim 'visionos'")

    def test_deprecated_claim_must_be_bool(self):
        bad = {**VALID, "apis": [{"name": "x", "path": "swiftui/x", "claims": {"deprecated": "27.2"}}]}
        self.assertRejected(bad, "bad claim 'deprecated'")

    def test_duplicate_api_name(self):
        entry = {"name": "x", "path": "swiftui/x"}
        self.assertRejected({**VALID, "apis": [entry, entry]}, "duplicate name")

    def test_path_must_be_relative_without_json(self):
        self.assertRejected({**VALID, "apis": [{"name": "x", "path": "/documentation/swiftui/x"}]}, "relative")
        self.assertRejected({**VALID, "apis": [{"name": "x", "path": "swiftui/x.json"}]}, "relative")

    def test_name_ignored_twice(self):
        self.assertRejected({**VALID, "ignore": {"a": ["CardView"], "b": ["CardView"]}}, "ignored twice")

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apis.json"
            path.write_text("{")
            with self.assertRaises(ManifestError):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
```

`maintenance/tests/test_fetch.py`:

```python
import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck.fetch import Fetcher, FetchError, NotFound, url_for  # noqa: E402


class FakeOpener:
    """Stands in for urlopen: answers from a dict of url → bytes, or raises the given exception."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(answer)


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "error", {}, None)


class FetcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.url = url_for("index/swiftui")

    def tearDown(self):
        self.tmp.cleanup()

    def test_url_keeps_symbol_punctuation(self):
        self.assertEqual(
            url_for("documentation/swiftui/view/glasseffect(_:in:).json"),
            "https://developer.apple.com/tutorials/data/documentation/swiftui/view/glasseffect(_:in:).json",
        )
        self.assertTrue(url_for("documentation/swiftui/text/+(_:_:).json").endswith("/text/+(_:_:).json"))

    def test_second_fetch_comes_from_the_cache(self):
        opener = FakeOpener({self.url: b'{"a": 1}'})
        fetcher = Fetcher(self.cache, opener=opener)
        self.assertEqual(fetcher.index("swiftui"), {"a": 1})
        self.assertEqual(fetcher.index("swiftui"), {"a": 1})
        self.assertEqual(len(opener.calls), 1)

    def test_refresh_bypasses_the_cache(self):
        opener = FakeOpener({self.url: b'{"a": 1}'})
        Fetcher(self.cache, opener=opener).index("swiftui")
        Fetcher(self.cache, refresh=True, opener=opener).index("swiftui")
        self.assertEqual(len(opener.calls), 2)

    def test_404_raises_not_found_and_caches_nothing(self):
        opener = FakeOpener({self.url: http_error(self.url, 404)})
        with self.assertRaises(NotFound):
            Fetcher(self.cache, opener=opener).index("swiftui")
        self.assertFalse(self.cache.exists())

    def test_server_error_and_network_error_are_fetch_errors_not_404s(self):
        for failure in (http_error(self.url, 503), urllib.error.URLError("offline"), TimeoutError()):
            with self.subTest(failure=failure):
                with self.assertRaises(FetchError):
                    Fetcher(self.cache, opener=FakeOpener({self.url: failure})).index("swiftui")
        self.assertFalse(self.cache.exists())

    def test_non_json_answer_is_a_fetch_error(self):
        with self.assertRaises(FetchError):
            Fetcher(self.cache, opener=FakeOpener({self.url: b"<html>"})).index("swiftui")

    def test_corrupt_cache_file_names_the_fix(self):
        fetcher = Fetcher(self.cache, opener=FakeOpener({self.url: b'{"a": 1}'}))
        fetcher.index("swiftui")
        (cached,) = self.cache.glob("*.json")
        cached.write_text('{"a": ')
        with self.assertRaises(FetchError) as ctx:
            fetcher.index("swiftui")
        self.assertIn("--refresh", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

`maintenance/tests/test_table.py`:

```python
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck import apple  # noqa: E402
from apicheck.table import BEGIN, END, render_table, replace_block  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def platforms(name):
    return apple.parse_platforms(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


class RenderTableTests(unittest.TestCase):
    def test_row_shows_versions_dashes_and_doc_link(self):
        table = render_table([("glassEffect(_:in:)", "swiftui/view/glasseffect(_:in:)", platforms("glasseffect.json"))])
        header, rule, row = table.splitlines()
        self.assertEqual(header, "| API | iOS | iPadOS | Mac Catalyst | macOS | visionOS | watchOS | tvOS | Notes |")
        self.assertEqual(row.count("|"), len(header.split("|")) - 1)
        self.assertIn("| `glassEffect(_:in:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 |", row)
        self.assertIn("<https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)>", row)

    def test_deprecations_are_grouped_by_version(self):
        table = render_table([("cornerRadius(_:antialiased:)", "swiftui/view/cornerradius(_:antialiased:)", platforms("cornerradius.json"))])
        self.assertIn("deprecated 27.2: iOS, macOS, visionOS", table)


class ReplaceBlockTests(unittest.TestCase):
    def test_replaces_only_the_marked_block(self):
        text = f"intro\n{BEGIN}\nold table\n{END}\noutro\n"
        self.assertEqual(replace_block(text, "NEW"), f"intro\n{BEGIN}\nNEW\n{END}\noutro\n")

    def test_missing_duplicate_or_reversed_markers_are_refused(self):
        for text in ("no markers", f"{BEGIN}\n{END}\n{BEGIN}\n{END}", f"{END}\n{BEGIN}"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    replace_block(text, "NEW")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest maintenance/tests/test_manifest.py maintenance/tests/test_fetch.py maintenance/tests/test_table.py 2>&1 | tail -3`
Expected: `ModuleNotFoundError` for `apicheck.manifest` (and the other two).

- [ ] **Step 3: Implement** `maintenance/apicheck/manifest.py`:

```python
"""Load maintenance/apis.json: frameworks to index, APIs with recorded claims, names to ignore."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .apple import PLATFORMS

_TOP_KEYS = {"frameworks", "apis", "ignore"}
_API_KEYS = {"name", "path", "claims", "table"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ApiEntry:
    name: str  # as the skills write it, e.g. "glassEffect(_:in:)"
    path: str  # Apple doc path below /documentation/, e.g. "swiftui/view/glasseffect(_:in:)"
    claims: dict  # e.g. {"visionOS": False, "iOS": "26.0", "deprecated": False}
    table: bool  # include in platform-availability.md


@dataclass(frozen=True)
class Manifest:
    frameworks: tuple[str, ...]
    apis: tuple[ApiEntry, ...]
    ignore: dict[str, str]  # name → reason


def _valid_claim(key: str, value) -> bool:
    if key in ("deprecated", "beta"):
        return isinstance(value, bool)
    return key in PLATFORMS and isinstance(value, (bool, str))


def load_manifest(path: Path) -> Manifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path}: invalid JSON: {exc}") from exc
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise ManifestError(f"{path}: unknown keys {sorted(unknown)}")
    frameworks = data.get("frameworks")
    if not frameworks or not all(isinstance(f, str) for f in frameworks):
        raise ManifestError(f"{path}: 'frameworks' must be a non-empty list of Apple framework slugs")

    apis, seen = [], set()
    for i, raw in enumerate(data.get("apis", [])):
        where = f"{path}: apis[{i}]"
        if not isinstance(raw, dict) or set(raw) - _API_KEYS or not {"name", "path"} <= set(raw):
            raise ManifestError(f"{where}: needs 'name' and 'path'; allowed keys are {sorted(_API_KEYS)}")
        if raw["name"] in seen:
            raise ManifestError(f"{where}: duplicate name {raw['name']!r}")
        seen.add(raw["name"])
        if raw["path"].startswith("/") or raw["path"].endswith(".json"):
            raise ManifestError(f"{where}: path is relative to /documentation/ without .json, e.g. swiftui/view/glasseffect(_:in:)")
        claims = raw.get("claims", {})
        for key, value in claims.items():
            if not _valid_claim(key, value):
                raise ManifestError(
                    f"{where}: bad claim {key!r}: {value!r} (deprecated/beta take true/false; "
                    f"platforms {', '.join(PLATFORMS)} take true/false or an introduced version like \"26.0\")"
                )
        apis.append(ApiEntry(raw["name"], raw["path"], dict(claims), bool(raw.get("table", False))))

    ignore: dict[str, str] = {}
    for reason, names in data.get("ignore", {}).items():
        for name in names:
            if name in ignore:
                raise ManifestError(f"{path}: {name!r} is ignored twice")
            ignore[name] = reason
    return Manifest(tuple(frameworks), tuple(apis), ignore)
```

`maintenance/apicheck/fetch.py`:

```python
"""Fetch Apple documentation JSON through an on-disk cache. Network goes only to developer.apple.com."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://developer.apple.com/tutorials/data/"
_SAFE = "/():_.,-+~!*=<>&|^"


class NotFound(Exception):
    """Apple answered 404 for this documentation path."""


class FetchError(Exception):
    """A network failure, a non-404 HTTP error, a non-JSON answer or a corrupt cache file."""


def url_for(rel: str) -> str:
    return BASE + urllib.parse.quote(rel, safe=_SAFE)


def _urlopen(url: str):
    return urllib.request.urlopen(url, timeout=30)


class Fetcher:
    def __init__(self, cache_dir: Path, refresh: bool = False, opener=_urlopen):
        self.cache_dir = cache_dir
        self.refresh = refresh
        self._open = opener

    def index(self, framework: str) -> dict:
        return self._get(f"index/{framework}")

    def page(self, doc_path: str) -> dict:
        return self._get(f"documentation/{doc_path}.json")

    def _get(self, rel: str) -> dict:
        cached = self.cache_dir / (hashlib.sha256(rel.encode()).hexdigest()[:32] + ".json")
        if cached.exists() and not self.refresh:
            try:
                return json.loads(cached.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise FetchError(f"corrupt cache file {cached} for {rel}; rerun with --refresh") from exc
        url = url_for(rel)
        try:
            with self._open(url) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(url) from exc
            raise FetchError(f"{url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise FetchError(f"{url}: {exc}") from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise FetchError(f"{url}: answer is not JSON") from exc
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".partial")
        partial.write_bytes(body)
        os.replace(partial, cached)
        return data
```

`maintenance/apicheck/table.py`:

```python
"""Render the generated platform table in references/platform-availability.md."""
from __future__ import annotations

from .apple import PLATFORMS, Availability

BEGIN = "<!-- BEGIN GENERATED: maintenance/check-apis.py --write-table -->"
END = "<!-- END GENERATED -->"
DOC_URL = "https://developer.apple.com/documentation/"


def render_table(rows: list[tuple[str, str, dict[str, Availability]]]) -> str:
    """rows: (name, doc path, platforms). A cell holds the introduced version, or — where the API is missing."""
    lines = [
        "| API | " + " | ".join(PLATFORMS) + " | Notes |",
        "|---|" + "---|" * len(PLATFORMS) + "---|",
    ]
    for name, path, platforms in rows:
        cells, beta, deprecated = [], [], {}
        for platform in PLATFORMS:
            a = platforms.get(platform)
            if a is None or a.unavailable:
                cells.append("—")
                continue
            cells.append(a.introduced or "?")
            if a.beta:
                beta.append(platform)
            if a.deprecated_at:
                deprecated.setdefault(a.deprecated_at, []).append(platform)
        notes = [f"beta: {', '.join(beta)}"] if beta else []
        notes += [f"deprecated {version}: {', '.join(names)}" for version, names in deprecated.items()]
        notes.append(f"<{DOC_URL}{path}>")
        lines.append(f"| `{name}` | " + " | ".join(cells) + " | " + "; ".join(notes) + " |")
    return "\n".join(lines)


def replace_block(text: str, table: str) -> str:
    """Swap the text between the BEGIN/END markers for the table; refuse unless there is exactly one pair, in order."""
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        raise ValueError(f"need exactly one {BEGIN!r} followed by one {END!r}")
    head, rest = text.split(BEGIN)
    _, tail = rest.split(END)
    return f"{head}{BEGIN}\n{table}\n{END}{tail}"
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m unittest maintenance/tests/test_manifest.py maintenance/tests/test_fetch.py maintenance/tests/test_table.py 2>&1 | tail -3`
Expected: `Ran 20 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add maintenance/apicheck/manifest.py maintenance/apicheck/fetch.py maintenance/apicheck/table.py maintenance/tests/test_manifest.py maintenance/tests/test_fetch.py maintenance/tests/test_table.py
git commit -m "feat(maintenance): load the API manifest, fetch Apple JSON with a cache, render the platform table"
```

---

### Task 7: `check-apis.py` command line

**Files:**
- Create: `maintenance/apicheck/cli.py`, `maintenance/check-apis.py` (executable)
- Test: `maintenance/tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 4–6.
- Produces: `python3 maintenance/check-apis.py [--strict] [--refresh] [--write-table] [--find NAME] [--manifest F] [--cache D] [--skills D] [--table-file F]`. Exit 0 = clean (warnings allowed without `--strict`); 1 = failures (or warnings under `--strict`, or `--find` found nothing); 2 = manifest, file, network or cache error. Output lines are `FAIL …`, `WARN …` and a summary: `<n> manifest APIs, <f> failures, <w> warnings`.
- `cli.run(args, fetcher, out) -> int` is what the tests drive; `fetcher` needs `.index(framework)` and `.page(doc_path)`.

- [ ] **Step 1: Write the failing test** — `maintenance/tests/test_cli.py`

```python
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck import cli  # noqa: E402
from apicheck.fetch import NotFound  # noqa: E402
from apicheck.table import BEGIN, END  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = {
    "swiftui/view/glasseffect(_:in:)": "glasseffect.json",
    "swiftui/view/glassbackgroundeffect(in:displaymode:)": "glassbackgroundeffect.json",
}


class FakeFetcher:
    def index(self, framework):
        if framework != "swiftui":
            raise NotFound(framework)
        return json.loads((FIXTURES / "index-swiftui.json").read_text(encoding="utf-8"))

    def page(self, doc_path):
        if doc_path not in PAGES:
            raise NotFound(doc_path)
        return json.loads((FIXTURES / PAGES[doc_path]).read_text(encoding="utf-8"))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.skills = root / "skills"
        (self.skills / "swiftui" / "references").mkdir(parents=True)
        (self.skills / "swiftui" / "SKILL.md").write_text(
            "```swift\nstruct CardView: View {\n  var body: some View {\n"
            "    Text(\"\").bold().glassEffect()\n  }\n}\n```\nOn visionOS use `glassBackgroundEffect(in:displayMode:)`.\n"
        )
        self.table_file = self.skills / "swiftui" / "references" / "platform-availability.md"
        self.table_file.write_text(f"# Platforms\n{BEGIN}\n{END}\n")
        self.manifest_path = root / "apis.json"
        self.manifest = {
            "frameworks": ["swiftui"],
            "apis": [
                {"name": "glassEffect(_:in:)", "path": "swiftui/view/glasseffect(_:in:)", "claims": {"visionOS": False}, "table": True},
                {"name": "glassBackgroundEffect(in:displayMode:)", "path": "swiftui/view/glassbackgroundeffect(in:displaymode:)", "claims": {"visionOS": True, "iOS": False}},
            ],
            "ignore": {},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *flags):
        self.manifest_path.write_text(json.dumps(self.manifest))
        argv = ["--manifest", str(self.manifest_path), "--skills", str(self.skills), "--table-file", str(self.table_file), *flags]
        out = io.StringIO()
        code = cli.run(cli.parse_args(argv), FakeFetcher(), out=out)
        return code, out.getvalue()

    def test_clean_tree_passes_strict(self):
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("2 manifest APIs, 0 failures, 0 warnings", out)

    def test_unresolved_name_warns_and_fails_only_under_strict(self):
        (self.skills / "swiftui" / "extra.md").write_text("Use `.glassMagic()`.\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("WARN unresolved member 'glassMagic' in swiftui/extra.md", out)
        self.assertEqual(self.run_cli("--strict")[0], 1)

    def test_ignored_name_is_quiet_until_it_goes_stale(self):
        (self.skills / "swiftui" / "extra.md").write_text("Use `ExampleView`.\n")
        self.manifest["ignore"] = {"example views": ["ExampleView"]}
        self.assertEqual(self.run_cli("--strict")[0], 0)
        (self.skills / "swiftui" / "extra.md").write_text("nothing here\n")
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 1)
        self.assertIn("'ExampleView' appears in no skill file", out)

    def test_ignored_name_that_now_resolves_is_flagged(self):
        self.manifest["ignore"] = {"oops": ["Text"]}
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 1)
        self.assertIn("'Text' now resolves", out)

    def test_missing_apple_page_fails(self):
        self.manifest["apis"].append({"name": "scrollExtensionMode(_:)", "path": "swiftui/view/scrollextensionmode(_:)"})
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAIL scrollExtensionMode(_:): Apple has no page", out)

    def test_contradicted_claim_fails(self):
        self.manifest["apis"][0]["claims"] = {"visionOS": True}
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("skill says visionOS=True, Apple says False", out)

    def test_write_table_fills_the_block(self):
        code, out = self.run_cli("--write-table")
        self.assertEqual(code, 0, out)
        text = self.table_file.read_text()
        self.assertIn("| `glassEffect(_:in:)` | 26.0", text)
        self.assertNotIn("glassBackgroundEffect", text)  # table: false

    def test_write_table_refuses_while_checks_fail(self):
        self.manifest["apis"][0]["claims"] = {"visionOS": True}
        code, out = self.run_cli("--write-table")
        self.assertEqual(code, 1)
        self.assertIn("platform table not written", out)
        self.assertEqual(self.table_file.read_text(), f"# Platforms\n{BEGIN}\n{END}\n")

    def test_find_prints_index_entries(self):
        code, out = self.run_cli("--find", "glassEffect")
        self.assertEqual(code, 0)
        self.assertIn("swiftui/view/glasseffect(_:in:)", out)
        self.assertEqual(self.run_cli("--find", "nothingLikeThis")[0], 1)

    def test_missing_manifest_exits_2_before_any_network(self):
        err = io.StringIO()
        missing = Path(self.tmp.name) / "missing.json"
        with contextlib.redirect_stderr(err):
            code = cli.main(["--manifest", str(missing), "--cache", str(Path(self.tmp.name) / "cache")])
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertFalse((Path(self.tmp.name) / "cache").exists())

    def test_unknown_framework_is_an_error(self):
        self.manifest["frameworks"] = ["swiftui", "nosuchkit"]
        with self.assertRaises(cli.ManifestError):
            self.run_cli()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest maintenance/tests/test_cli.py 2>&1 | tail -3`
Expected: `ImportError: cannot import name 'cli'` (or `ModuleNotFoundError`).

- [ ] **Step 3: Implement** `maintenance/apicheck/cli.py`:

```python
"""Check every API the swift plugin's skills name against Apple's documentation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import apple, extract, table
from .fetch import Fetcher, FetchError, NotFound
from .manifest import ManifestError, load_manifest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "plugins" / "swift" / "skills"


def parse_args(argv):
    p = argparse.ArgumentParser(prog="check-apis.py", description=__doc__)
    p.add_argument("--strict", action="store_true", help="also fail on unresolved names and stale ignore entries")
    p.add_argument("--refresh", action="store_true", help="bypass the cache")
    p.add_argument("--write-table", action="store_true", help="rewrite the generated block in platform-availability.md")
    p.add_argument("--find", metavar="NAME", help="print the index entries for NAME and exit")
    p.add_argument("--manifest", type=Path, default=REPO / "maintenance" / "apis.json")
    p.add_argument("--cache", type=Path, default=REPO / "maintenance" / ".cache")
    p.add_argument("--skills", type=Path, default=SKILLS)
    p.add_argument("--table-file", type=Path, default=SKILLS / "swiftui" / "references" / "platform-availability.md")
    return p.parse_args(argv)


def _load_lookup(manifest, fetcher):
    entries = []
    for framework in manifest.frameworks:
        try:
            entries += apple.parse_index(fetcher.index(framework))
        except NotFound:
            raise ManifestError(f"Apple has no index for framework {framework!r}") from None
    return apple.build_lookup(entries)


def _check_manifest(manifest, fetcher):
    failures, rows = [], []
    for api in manifest.apis:
        try:
            platforms = apple.parse_platforms(fetcher.page(api.path))
        except NotFound:
            failures.append(f"{api.name}: Apple has no page at {api.path}")
            continue
        except ValueError as exc:
            failures.append(f"{api.name}: {exc}")
            continue
        failures += apple.check_claims(api.name, api.claims, platforms)
        if api.table:
            rows.append((api.name, api.path, platforms))
    return failures, rows


def _check_coverage(manifest, lookup, skills):
    warnings, seen = [], set()
    for name, files in sorted(extract.scan(skills).items(), key=lambda kv: (kv[0].text, kv[0].kind)):
        seen.add(name.text)
        resolved = apple.resolve(name.text, name.kind, lookup)
        if name.text in manifest.ignore:
            if resolved:
                warnings.append(f"ignored {name.text!r} now resolves to {resolved[0].path}; drop it from 'ignore'")
            continue
        if not resolved:
            where = ", ".join(str(f.relative_to(skills)) for f in files[:3])
            more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
            warnings.append(f"unresolved {name.kind} {name.text!r} in {where}{more}")
    warnings += [f"ignored {n!r} appears in no skill file; drop it from 'ignore'" for n in sorted(set(manifest.ignore) - seen)]
    return warnings


def run(args, fetcher, out=sys.stdout) -> int:
    manifest = load_manifest(args.manifest)
    lookup = _load_lookup(manifest, fetcher)

    if args.find:
        matches = lookup.get(args.find.lower(), [])
        for e in matches:
            flags = "".join(f" ({flag})" for flag, on in (("deprecated", e.deprecated), ("beta", e.beta)) if on)
            print(f"{e.kind:14} {e.path}{flags}", file=out)
        return 0 if matches else 1

    failures, rows = _check_manifest(manifest, fetcher)
    warnings = _check_coverage(manifest, lookup, args.skills)

    if args.write_table:
        if failures:
            failures.append("platform table not written: fix the failures above first")
        else:
            text = args.table_file.read_text(encoding="utf-8")
            args.table_file.write_text(table.replace_block(text, table.render_table(rows)), encoding="utf-8")
            print(f"wrote {len(rows)} rows to {args.table_file}", file=out)

    for line in failures:
        print(f"FAIL {line}", file=out)
    for line in warnings:
        print(f"WARN {line}", file=out)
    print(f"{len(manifest.apis)} manifest APIs, {len(failures)} failures, {len(warnings)} warnings", file=out)
    return 1 if failures or (args.strict and warnings) else 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return run(args, Fetcher(args.cache, refresh=args.refresh))
    except (ManifestError, FetchError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
```

`maintenance/check-apis.py`:

```python
#!/usr/bin/env python3
"""Check every API the swift plugin's skills name against Apple's documentation (see apicheck/cli.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apicheck.cli import main  # noqa: E402

sys.exit(main())
```

Run: `chmod +x maintenance/check-apis.py`

- [ ] **Step 4: Run the whole suite**

Run: `python3 -m unittest discover maintenance/tests 2>&1 | tail -3`
Expected: `Ran 64 tests` … `OK` (3 upstream + 18 + 12 + 20 + 11).

- [ ] **Step 5: Check the error path by hand**

Run: `python3 maintenance/check-apis.py --manifest /nonexistent.json; echo "exit $?"`
Expected: `error: [Errno 2] No such file or directory: '/nonexistent.json'` and `exit 2`, with no traceback.

- [ ] **Step 6: Commit**

```bash
git add maintenance/apicheck/cli.py maintenance/check-apis.py maintenance/tests/test_cli.py
git commit -m "feat(maintenance): add check-apis.py"
```

---

### Task 8: Seed `apis.json` until `--strict` passes on the imported skill

**Files:**
- Create: `maintenance/apis.json`
- Modify: `UPSTREAM.md` (new `## Findings` section)

**Interfaces:**
- Consumes: `check-apis.py` (Task 7).
- Produces: a manifest that later tasks extend. Tasks 10–15 add an `apis` entry for every API their text makes a platform or deprecation claim about, and add ignore entries only with a reason.

- [ ] **Step 1: Write the starting manifest**

`observation` is left out on purpose: Apple serves Observation inside the `swift` index.

```json
{
  "frameworks": ["swiftui", "swift", "foundation", "uikit", "appkit", "charts", "webkit", "swiftdata", "coregraphics", "corefoundation", "combine", "accessibility", "os", "dispatch", "objectivec", "mapkit", "corelocation", "uniformtypeidentifiers", "imageio", "developertoolssupport"],
  "apis": [
    {"name": "glassEffect(_:in:)", "path": "swiftui/view/glasseffect(_:in:)", "claims": {"visionOS": false, "iOS": "26.0"}, "table": true},
    {"name": "GlassEffectContainer", "path": "swiftui/glasseffectcontainer", "claims": {"visionOS": false}, "table": true},
    {"name": "Glass.interactive(_:)", "path": "swiftui/glass/interactive(_:)", "claims": {"visionOS": false, "macOS": true}, "table": true},
    {"name": "GlassButtonStyle", "path": "swiftui/glassbuttonstyle", "claims": {"visionOS": false}, "table": true},
    {"name": "glassProminent", "path": "swiftui/primitivebuttonstyle/glassprominent", "claims": {"visionOS": false}, "table": true},
    {"name": "glassEffectUnion(id:namespace:)", "path": "swiftui/view/glasseffectunion(id:namespace:)", "claims": {"visionOS": false}, "table": true},
    {"name": "glassEffectTransition(_:)", "path": "swiftui/view/glasseffecttransition(_:)", "claims": {"visionOS": false}, "table": true},
    {"name": "glassEffectID(_:in:)", "path": "swiftui/view/glasseffectid(_:in:)", "claims": {"visionOS": false}, "table": true},
    {"name": "scrollEdgeEffectStyle(_:for:)", "path": "swiftui/view/scrolledgeeffectstyle(_:for:)", "claims": {"visionOS": false}, "table": true},
    {"name": "ToolbarSpacer", "path": "swiftui/toolbarspacer", "claims": {"visionOS": false, "watchOS": false, "tvOS": false}, "table": true},
    {"name": "sharedBackgroundVisibility(_:)", "path": "swiftui/toolbarcontent/sharedbackgroundvisibility(_:)", "claims": {"visionOS": false}, "table": true},
    {"name": "tabViewBottomAccessory(content:)", "path": "swiftui/view/tabviewbottomaccessory(content:)", "claims": {"visionOS": false, "macOS": false}, "table": true},
    {"name": "backgroundExtensionEffect()", "path": "swiftui/view/backgroundextensioneffect()", "claims": {"visionOS": true}, "table": true},
    {"name": "tabBarMinimizeBehavior(_:)", "path": "swiftui/view/tabbarminimizebehavior(_:)", "claims": {"visionOS": true}, "table": true},
    {"name": "safeAreaBar(edge:alignment:spacing:content:)", "path": "swiftui/view/safeareabar(edge:alignment:spacing:content:)", "claims": {"visionOS": true}, "table": true},
    {"name": "ConcentricRectangle", "path": "swiftui/concentricrectangle", "table": true},
    {"name": "rect(corners:isUniform:)", "path": "swiftui/shape/rect(corners:isuniform:)", "table": true}
  ],
  "ignore": {}
}
```

- [ ] **Step 2: Run the check and fix any manifest FAIL**

Run: `python3 maintenance/check-apis.py > "${TMPDIR:-/tmp}/ca.out"; echo "exit $?"; rg '^FAIL|manifest APIs' "${TMPDIR:-/tmp}/ca.out"`
Expected: `17 manifest APIs, 0 failures, ~165 warnings`, and `exit 0`. Any `FAIL` means a claim from the spec's §8 no longer matches Apple. Stop and report it to the user; never edit a claim just to make the check pass.

- [ ] **Step 3: Triage every `WARN unresolved` line into the ignore list, by reason**

For each name, run `python3 maintenance/check-apis.py --find <name>` and read the snippet it comes from. Put each name in exactly one group:

| Group key in `ignore` | Put here |
|---|---|
| `"example types in upstream snippets (declared elsewhere or implied)"` | app-level names such as `ContentView`, `CardView`, `AppModel`, `Product`, `ItemRow`, `SettingsView` |
| `"SwiftUI runtime symbols named in Instruments output"` | `UserDefaultObserver`, `EnvironmentWriter`, `GraphAttribute`, `LogForEachSlowPath` and similar trace names |
| `"Info.plist keys"` | `CFBundleTypeRole`, `LSUIElement`, `UISupportsDocumentBrowser` |
| `"placeholders and prose words inside code spans or unlabelled blocks"` | `START`, `END`, `START_MS`, `END_MS`, `YES`, `NO`, `Does`, `Is`, `Use`, `Legacy`, `BINDINGS`, `MODIFY`, `SKILL`, `Bash`, `Time`, `Profiler`, `Hitches`, `Creation`, `Reuse`, `Callback`, `Target`, `CA`, `CF`, `NS` |
| `"named on purpose as the wrong spelling"` | `textFormattingDefinition` (`styled-text-editing.md` says "not `textFormattingDefinition(_:)`") |
| `"upstream names not in Apple's index (see UPSTREAM.md Findings)"` | names that look like Apple APIs but no index has them. Expected, as of 2026-09-24: `AXDateDataAxisDescriptor`, `VerticalTabViewStyle`, `navigationTransitionSource`, `navigationTransitionDestination`, `sliderNeutralValue` |

Rerun until `python3 maintenance/check-apis.py --strict; echo "exit $?"` prints `0 warnings` and `exit 0`.

- [ ] **Step 4: Record the findings in `UPSTREAM.md`**

Append this, with one row per name from the last group. The "Apple has" column comes from `--find` on related names; for example, `--find AXNumericDataAxisDescriptor` and `--find VerticalPageTabViewStyle` both resolve.

```markdown
## Findings

Names upstream uses that Apple's documentation index did not have on 2026-09-24. `check-apis.py` ignores them for this reason; each still needs a decision: fix as a deviation, or wait for Apple's docs.

| Name | Upstream file | Nearest Apple API |
|---|---|---|
| `AXDateDataAxisDescriptor` | `references/charts-accessibility.md` | `AXNumericDataAxisDescriptor`, `AXCategoricalDataAxisDescriptor` |
```

- [ ] **Step 5: Run the whole gate and commit**

Run: `python3 -m unittest discover maintenance/tests 2>&1 | tail -1; python3 maintenance/check-apis.py --strict | tail -1`
Expected: `OK`; `17 manifest APIs, 0 failures, 0 warnings`.

```bash
git add maintenance/apis.json UPSTREAM.md
git commit -m "chore(maintenance): seed apis.json; check-apis --strict passes on upstream 5.1.0"
```

Report the Findings table to the user in the task summary.

---

### Task 9: Eval suite and the RED baseline

**Files:**
- Create: `plugins/swift/evals/{glass-button-ios17,glass-toolbar-visionos,preview-debug-guard,settings-screen-no-tokens}/` with `prompt.md`, `case.yaml`, `scaffold.sh`, `graders/*.md`

**Interfaces:**
- Produces: the suite Task 16 reruns for GREEN. Case names and grader file names are fixed.

Format facts (docs `plugin-evals`, CLI 2.1.282):
- Every run starts in an empty workspace; `case.yaml` `context.scaffold_script` runs only with `--scaffold`.
- `regex` graders take `target: { source: file, path: … }`.
- A `tool_used: Skill` grader is an indicator only (excluded from the score) in a with/without run.
- `Write`/`Edit` must be listed in `allowed_tools` **and** granted with `--allow-tools`. The target comes before `--allow-tools`.

- [ ] **Step 1: Case `glass-button-ios17`** (spec §7.2, first scenario)

`plugins/swift/evals/glass-button-ios17/case.yaml`:

```yaml
schema_version: "1.1"
name: glass-button-ios17
context:
  scaffold_script: scaffold.sh
```

`plugins/swift/evals/glass-button-ios17/scaffold.sh`:

```bash
#!/usr/bin/env bash
# Workspace: a Swift package targeting iOS 17.5 / macOS 14, so any 26-only API needs a gate.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("17.5"), .macOS("14.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/ContentView.swift <<'SWIFT'
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Text("Welcome")
                .font(.largeTitle)
        }
    }
}
SWIFT
```

`plugins/swift/evals/glass-button-ios17/prompt.md`:

```markdown
---
description: Glass button in a package whose deployment target is below 26
tags: [swiftui, liquid-glass, availability]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: The glass button sits behind if #available(iOS 26, *) with a material fallback, because Package.swift targets iOS 17.5.
---

Add a glass button labelled "Continue" at the bottom of the view in Sources/Demo/ContentView.swift.
```

`graders/availability-gate.md`:

```markdown
---
type: regex
pattern: '#available\(\s*iOS\s+26'
target: { source: file, path: Sources/Demo/ContentView.swift }
---
```

`graders/material-fallback.md`:

```markdown
---
type: regex
pattern: '(ultraThin|thin|regular|thick|ultraThick)Material|\.bar\b'
target: { source: file, path: Sources/Demo/ContentView.swift }
---
```

`graders/skill-fired.md`:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:swift:)?swiftui"'
---
```

- [ ] **Step 2: Case `glass-toolbar-visionos`** (second scenario)

`plugins/swift/evals/glass-toolbar-visionos/case.yaml`:

```yaml
schema_version: "1.1"
name: glass-toolbar-visionos
context:
  scaffold_script: scaffold.sh
```

`plugins/swift/evals/glass-toolbar-visionos/scaffold.sh`:

```bash
#!/usr/bin/env bash
# Workspace: a Swift package for iOS 26 and visionOS 26, so glass needs a visionOS branch.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("26.0"), .visionOS("26.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/ContentView.swift <<'SWIFT'
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Text("Welcome")
                .font(.largeTitle)
        }
    }
}
SWIFT
```

`prompt.md`:

```markdown
---
description: Floating glass controls in an app that also ships on visionOS
tags: [swiftui, liquid-glass, visionos]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: An #if os(visionOS) branch uses glassBackgroundEffect (or an ornament); GlassEffectContainer and glass styles appear only in the non-visionOS branch.
---

Add a floating glass toolbar with Play, Pause and Stop buttons over the content of Sources/Demo/ContentView.swift.
```

`graders/visionos-branch.md`:

```markdown
---
type: regex
pattern: '#if\s+!?os\(visionOS\)'
target: { source: file, path: Sources/Demo/ContentView.swift }
---
```

`graders/glass-background.md`:

```markdown
---
type: regex
pattern: 'glassBackgroundEffect'
target: { source: file, path: Sources/Demo/ContentView.swift }
---
```

`graders/container.md`:

```markdown
---
type: regex
pattern: 'GlassEffectContainer'
target: { source: file, path: Sources/Demo/ContentView.swift }
---
```

`graders/guarded.md`:

```markdown
---
type: llm
focus: { source: file, path: Sources/Demo/ContentView.swift }
---

PASS if every use of glassEffect, GlassEffectContainer, .glass or .glassProminent in the file compiles only for non-visionOS platforms (inside the #else of an #if os(visionOS) block, or inside #if !os(visionOS)), and the visionOS branch uses glassBackgroundEffect or an ornament instead.
FAIL if any of those glass APIs would compile for visionOS, or if there is no visionOS branch.
```

`graders/skill-fired.md`:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:swift:)?swiftui"'
---
```

- [ ] **Step 3: Case `preview-debug-guard`** (third scenario)

`plugins/swift/evals/preview-debug-guard/case.yaml`:

```yaml
schema_version: "1.1"
name: preview-debug-guard
context:
  scaffold_script: scaffold.sh
```

`scaffold.sh`:

```bash
#!/usr/bin/env bash
# Workspace: an iOS 26 package with a view that has no preview yet.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("26.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/InboxView.swift <<'SWIFT'
import SwiftUI

struct Message: Identifiable {
    let id = UUID()
    let sender: String
    let subject: String
}

struct InboxView: View {
    let messages: [Message]

    var body: some View {
        List(messages) { message in
            VStack(alignment: .leading) {
                Text(message.sender).font(.headline)
                Text(message.subject)
            }
        }
    }
}
SWIFT
```

`prompt.md`:

```markdown
---
description: Adding a preview must guard it with #if DEBUG
tags: [swiftui, previews]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: The new #Preview sits inside #if DEBUG … #endif.
---

Add an Xcode preview for InboxView in Sources/Demo/InboxView.swift that shows three sample messages.
```

`graders/has-preview.md`:

```markdown
---
type: regex
pattern: '#Preview'
target: { source: file, path: Sources/Demo/InboxView.swift }
---
```

`graders/debug-guard.md`:

```markdown
---
type: regex
pattern: '#if DEBUG[\s\S]*?#Preview[\s\S]*?#endif'
target: { source: file, path: Sources/Demo/InboxView.swift }
---
```

`graders/skill-fired.md`:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:swift:)?swiftui"'
---
```

- [ ] **Step 4: Case `settings-screen-no-tokens`** (fourth scenario)

`plugins/swift/evals/settings-screen-no-tokens/case.yaml`:

```yaml
schema_version: "1.1"
name: settings-screen-no-tokens
context:
  scaffold_script: scaffold.sh
```

`plugins/swift/evals/settings-screen-no-tokens/scaffold.sh` (no design-token files, on purpose):

```bash
#!/usr/bin/env bash
# Workspace: an iOS 26 package with no design tokens.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("26.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/ContentView.swift <<'SWIFT'
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Text("Welcome")
                .font(.largeTitle)
        }
    }
}
SWIFT
```

`prompt.md`:

```markdown
---
description: A settings screen in a project without design tokens
tags: [design, swiftui]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: Form/Section with system text styles and semantic colours, a destructive Sign Out, no literal colours or font sizes, and a suggestion to introduce a starter token set.
---

Build a settings screen in Sources/Demo/SettingsView.swift: account name and email, a notifications toggle, an appearance picker (System, Light, Dark) and a Sign Out button.
```

Graders, all in `plugins/swift/evals/settings-screen-no-tokens/graders/`:

`graders/form.md`:

```markdown
---
type: regex
pattern: 'Form\s*\{'
target: { source: file, path: Sources/Demo/SettingsView.swift }
---
```

`graders/section.md`:

```markdown
---
type: regex
pattern: 'Section'
target: { source: file, path: Sources/Demo/SettingsView.swift }
---
```

`graders/destructive.md`:

```markdown
---
type: regex
pattern: 'role:\s*\.destructive'
target: { source: file, path: Sources/Demo/SettingsView.swift }
---
```

`graders/no-literal-colours.md`:

```markdown
---
type: regex
pattern: 'Color\(\s*(red|hex|\.sRGB)|UIColor\(\s*red|#[0-9A-Fa-f]{6}'
match: not_contains
target: { source: file, path: Sources/Demo/SettingsView.swift }
---
```

`graders/no-fixed-font-sizes.md`:

```markdown
---
type: regex
pattern: '\.font\(\.system\(size:'
match: not_contains
target: { source: file, path: Sources/Demo/SettingsView.swift }
---
```

`graders/tokens-advice.md` (judges the final reply, `last_message`, which is the default focus):

```markdown
---
type: llm
---

PASS if the reply notes that the project has no design tokens and suggests introducing a small named set (spacing, colour, typography or similar) instead of scattering literal values, or says it used system styles for that reason.
FAIL if the reply says nothing about design tokens or shared design constants.
```

`graders/skill-fired.md`:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:swift:)?design"'
---
```

- [ ] **Step 5: Check that each case loads**

Ask the user for the `--max-cost-usd` ceiling now (Global Constraints). Then:

Run: `cd ~/Dev/claude_skills/swift-plugin && chmod +x plugins/swift/evals/*/scaffold.sh && claude plugin eval plugins/swift --scaffold --trust-plugin --runs 1 --ablation none --case preview-debug-guard --max-cost-usd <ceiling> --allow-tools Write Edit`
Expected: the case runs; no "No eval cases found" and no frontmatter error. An `unknown key` error means a field name is wrong: fix it and rerun.

- [ ] **Step 6: Run RED (upstream-only skill, before any content change)**

Run: `claude plugin eval plugins/swift --scaffold --trust-plugin --runs 1 --threshold 0 --max-cost-usd <ceiling> --json "${TMPDIR:-/tmp}/red.json" --allow-tools Write Edit`
Expected: the run completes (exit 0 with `--threshold 0`). Record each case's `WITH`, `W/OUT` and `Δ`, plus which graders failed, in the task report. Likely RED:
- `preview-debug-guard` fails `debug-guard` (upstream has no such rule);
- `glass-toolbar-visionos` fails `glass-background` and/or `guarded`;
- the `settings-screen-no-tokens` `swift:design` indicator fails (the skill doesn't exist yet).

Don't change skill text in this task.

- [ ] **Step 7: Commit**

```bash
git add plugins/swift/evals
git commit -m "test(evals): add scenario suite for swift:swiftui and swift:design"
```

---

### Task 10: `swift:swiftui` — `visionos.md` and the generated platform table

Two commits, one per new file (§4 items 1 and 2).

**Files:**
- Create: `plugins/swift/skills/swiftui/references/platform-availability.md`, `plugins/swift/skills/swiftui/references/visionos.md`
- Modify: `plugins/swift/skills/swiftui/SKILL.md` (Topic Router), `maintenance/apis.json`, `UPSTREAM.md`

**Interfaces:**
- Consumes: `check-apis.py --write-table` and `--find` (Task 7); manifest rows with `"table": true` (Task 8).
- Produces: `references/visionos.md` and `references/platform-availability.md`, which Task 11's checklist lines and the design skill link to.

- [ ] **Step 1: Create `platform-availability.md` and generate its table**

```markdown
# Platform Availability of Liquid Glass and 26-era APIs

Where each API exists, generated from Apple's documentation JSON by `maintenance/check-apis.py --write-table` (repository only). Do not edit the table by hand. A cell holds the version the API arrived in; — means the platform lacks it. For what to use instead on visionOS, see `visionos.md`; for fallbacks below 26, see `liquid-glass.md` → Fallback Strategies.

<!-- BEGIN GENERATED: maintenance/check-apis.py --write-table -->
<!-- END GENERATED -->
```

Run: `python3 maintenance/check-apis.py --write-table --strict; echo "exit $?"; rg -c '^\| `' plugins/swift/skills/swiftui/references/platform-availability.md`
Expected: `wrote 17 rows`, `exit 0`, count `17`.

- [ ] **Step 2: Add the router row, log the deviation, commit**

In `SKILL.md` → Topic Router, after the "Liquid Glass (iOS 26+)" row, add:

```markdown
| Where Liquid Glass and 26-era APIs exist, per platform | `references/platform-availability.md` |
```

Deviations row:

```markdown
| `references/platform-availability.md` | New, table generated by `check-apis.py --write-table` | Platform facts from Apple's JSON, not memory |
```

Run: `python3 maintenance/check-apis.py --strict | tail -1` → `0 failures, 0 warnings`.

```bash
git add plugins/swift/skills/swiftui UPSTREAM.md
git commit -m "feat(swiftui): add generated platform-availability table"
```

- [ ] **Step 3: Collect Apple's facts for `visionos.md`**

For each API below, run `--find` and confirm the path. Then fetch the page and read `abstract` and `metadata.platforms`:

```bash
curl -s "https://developer.apple.com/tutorials/data/documentation/<path>.json" | jq '{abstract: [.abstract[]?.text] | join(""), platforms: .metadata.platforms}'
```

| API | Expected path (verify) |
|---|---|
| `glassBackgroundEffect(in:displayMode:)` | `swiftui/view/glassbackgroundeffect(in:displaymode:)` |
| `glassBackgroundEffect(displayMode:)` | `swiftui/view/glassbackgroundeffect(displaymode:)` |
| `ornament(visibility:attachmentAnchor:contentAlignment:ornament:)` | `swiftui/view/ornament(visibility:attachmentanchor:contentalignment:ornament:)` |
| `ImmersiveSpace` | `swiftui/immersivespace` |
| `windowStyle(_:)` | `swiftui/scene/windowstyle(_:)` (then `--find volumetric` for the style) |
| `SpatialEventGesture` | `swiftui/spatialeventgesture` |
| `hoverEffect(_:isEnabled:)` | `--find hoverEffect`, pick the `swiftui/view/…` entry |
| `openImmersiveSpace` / `dismissImmersiveSpace` | `--find openImmersiveSpace` |

Also read Apple's HIG JSON for `designing-for-visionos`, `ornaments` and `windows` (`https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<page>.json`) for the *when to use* sentences, and cite each page.

Add each API to `maintenance/apis.json` with the claims `visionos.md` will make, for example `{"visionOS": true, "iOS": false}` for `glassBackgroundEffect(in:displayMode:)` (Apple lists visionOS only).

- [ ] **Step 4: Write `visionos.md`**

Required sections, in this order: title, source note, table of contents, then:

1. **`## Glass on visionOS`.**
   - Name the glass APIs visionOS lacks (every row with — in the visionOS column of `platform-availability.md`) and link that file rather than copying the table.
   - Say what visionOS uses instead: windows already have a glass background, and `glassBackgroundEffect(in:displayMode:)` gives custom content the same material.
   - Include the branch pattern below, verbatim.
2. **`## Floating controls: ornaments`.** When to use an ornament rather than an in-window toolbar (from the HIG page), and a code example with `.ornament(attachmentAnchor: .scene(.bottom)) { … }` whose content uses `.glassBackgroundEffect()`.
3. **`## Windows, volumes and immersive spaces`.** `WindowGroup`, `.windowStyle(.volumetric)`, `ImmersiveSpace`, and opening and dismissing it through the environment actions, each with its doc link.
4. **`## Input and hover`.** Look-and-pinch taps come from standard gestures; `SpatialEventGesture` handles multi-touch spatial input; `hoverEffect` gives gaze feedback.
5. **`## Checklist`.** Checkbox items for each rule above, including: "Every glass API missing on visionOS sits in the non-visionOS branch of `#if os(visionOS)`".

The branch pattern, verbatim (it assumes a 26 deployment target on the other platforms; below 26, add the `if #available` fallback from `liquid-glass.md`):

```swift
struct PlaybackBar: View {
    var body: some View {
        #if os(visionOS)
        PlaybackControls()
            .padding()
            .glassBackgroundEffect()
        #else
        GlassEffectContainer {
            PlaybackControls()
                .buttonStyle(.glass)
        }
        #endif
    }
}

struct PlaybackControls: View {
    var body: some View {
        HStack {
            Button("Play", systemImage: "play.fill") {}
            Button("Pause", systemImage: "pause.fill") {}
            Button("Stop", systemImage: "stop.fill") {}
        }
    }
}
```

Rules for this file: every platform statement matches a manifest claim; no API that `check-apis.py` can't resolve; literals in examples are allowed (the project-layer rule in SKILL.md, Task 11, covers translating them).

- [ ] **Step 5: Router row, check, commit**

Topic Router row, after the platform-availability row:

```markdown
| visionOS: glass alternatives, ornaments, windows, volumes, immersive spaces | `references/visionos.md` |
```

Deviations row:

```markdown
| `references/visionos.md` | New | Upstream has no visionOS coverage; glass APIs missing there need a branch |
```

Run: `python3 maintenance/check-apis.py --strict | tail -1` → `0 failures, 0 warnings`.

```bash
git add plugins/swift/skills/swiftui maintenance/apis.json UPSTREAM.md
git commit -m "feat(swiftui): add visionOS reference"
```

---

### Task 11: `swift:swiftui` — previews, deployment targets below 26, the project-layer rule

Three commits (§4 items 3, 4 and 6).

**Files:**
- Modify: `plugins/swift/skills/swiftui/references/previews.md` (TOC line 7-ish, new section before `## Common Diagnostics`, Summary Checklist at the end)
- Modify: `plugins/swift/skills/swiftui/SKILL.md` (Operating Rules, Correctness Checklist)
- Modify: `UPSTREAM.md`

**Interfaces:**
- Consumes: `references/platform-availability.md`, `references/visionos.md` (Task 10).
- Produces: the project-layer rule text the example-app layer relies on (Global Constraints).

- [ ] **Step 1: `previews.md` — the `#if DEBUG` rule**

In the Table of Contents, between the `@Previewable Property Wrappers` and `Common Diagnostics` entries, add:

```markdown
- [Guard Previews with `#if DEBUG`](#guard-previews-with-if-debug)
```

Insert before `## Common Diagnostics`, keeping the file's existing spacing between sections:

````markdown
## Guard Previews with `#if DEBUG`

`#Preview` is a macro whose expansion compiles in every build configuration, Release included. A preview that references anything compiled only in Debug (mock services, sample data, helpers behind `#if DEBUG`) breaks the Release build, and that only shows up when you archive. Wrap every preview in `#if DEBUG`, and keep preview-only helpers behind the same condition:

```swift
#if DEBUG
#Preview("Three messages") {
    InboxView(messages: Message.samples)
}

extension Message {
    static let samples: [Message] = [
        Message(sender: "Ana", subject: "Lunch?"),
        Message(sender: "Ben", subject: "Build is green"),
        Message(sender: "Chen", subject: "Slides attached"),
    ]
}
#endif
```
````

At the end of `## Summary Checklist`, add:

```markdown
- [ ] Every `#Preview`, and every preview-only helper, sits inside `#if DEBUG` … `#endif`
```

In `SKILL.md` → Correctness Checklist, after the line "Previews use self-contained mock data; no dependency on live services or network", add:

```markdown
- [ ] Every `#Preview` sits inside `#if DEBUG` … `#endif` (see `references/previews.md`)
```

Deviations row:

```markdown
| `references/previews.md`, `SKILL.md` checklist | New section and checklist items: wrap every `#Preview` in `#if DEBUG` | `#Preview` compiles into Release; DEBUG-only helpers it references break archiving |
```

Run: `python3 maintenance/check-apis.py --strict | tail -1`. Expect it to warn about `InboxView` and `Message`, the snippet's example types. Add both to the "example types in upstream snippets (declared elsewhere or implied)" group, then rerun and expect `0 failures, 0 warnings`.

```bash
git add plugins/swift/skills/swiftui maintenance/apis.json UPSTREAM.md
git commit -m "feat(swiftui): guard previews with #if DEBUG"
```

- [ ] **Step 2: `SKILL.md` — deployment targets below 26**

In the Correctness Checklist, after the line "Version-specific APIs are gated with `#available` and have sensible fallbacks", add:

```markdown
- [ ] When the deployment target is below 26, every 26-only API (see `references/platform-availability.md`) sits behind `if #available(iOS 26, macOS 26, *)` naming the project's platforms, with a fallback such as a material (`references/liquid-glass.md` → Fallback Strategies)
- [ ] Glass APIs that visionOS lacks sit in the non-visionOS branch of `#if os(visionOS)`; visionOS uses `glassBackgroundEffect` (see `references/visionos.md`)
```

Deviations row:

```markdown
| `SKILL.md` checklist | Items for deployment targets below 26 and for the visionOS glass branch | Upstream's generic `#available` item doesn't name the 26 boundary or visionOS |
```

```bash
git add plugins/swift/skills/swiftui/SKILL.md UPSTREAM.md
git commit -m "feat(swiftui): check 26-only APIs against lower deployment targets and visionOS"
```

- [ ] **Step 3: `SKILL.md` — the project-layer rule**

In Operating Rules, after the line "Only adopt Liquid Glass when explicitly requested by the user", add exactly:

```markdown
- If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict
```

(Upstream's bullets have no final period; the wording is otherwise the Global Constraints text.)

Deviations row:

```markdown
| `SKILL.md` Operating Rules | Project-layer rule | A repo's own tokens and design skill override example literals (example-app-design depends on this) |
```

Run: `rg -n 'translate every literal in these examples into it; the project layer wins on conflict' plugins/swift/skills/swiftui/SKILL.md` → one line.

```bash
git add plugins/swift/skills/swiftui/SKILL.md UPSTREAM.md
git commit -m "feat(swiftui): let a project's design layer override example literals"
```

---

### Task 12: `swift:swiftui` — borrowed rules

Two commits (§4 item 5), each with a NOTICE section.

**Files:**
- Modify: `plugins/swift/skills/swiftui/references/latest-apis.md`, `plugins/swift/skills/swiftui/references/view-structure.md`
- Modify: `plugins/swift/NOTICE.md`, `maintenance/apis.json`, `UPSTREAM.md`

**Interfaces:**
- Consumes: `NOTICE.md` layout (Task 2).

- [ ] **Step 1: Fetch the pinned sources**

```bash
T="${TMPDIR:-/tmp}/swift-plugin-borrow"; rm -rf "$T"; mkdir -p "$T"
git clone --quiet https://github.com/twostraws/SwiftUI-Agent-Skill "$T/twostraws" && git -C "$T/twostraws" checkout --quiet be297ff80dddec529af1f9b1f1f114aab6c9d11c
git clone --quiet https://github.com/Dimillian/Skills "$T/dimillian" && git -C "$T/dimillian" checkout --quiet 05ba982bfeb0d77d3c97d4542b0ee15034d05f84
head -3 "$T/twostraws/LICENSE" "$T/dimillian/LICENSE"
```
Expected: both are MIT, with "Copyright (c) 2026 Paul Hudson." and "Copyright (c) 2026 Thomas Ricouard".

- [ ] **Step 2: twostraws → `latest-apis.md`**

The candidates are the deprecation entries in `${TMPDIR:-/tmp}/swift-plugin-borrow/twostraws/swiftui-pro/references/api.md` that upstream lacks; on 2026-09-24 there were two. For each one, first confirm the gap with `rg` in `latest-apis.md` and the deprecation in Apple's JSON (`curl … | jq '.metadata.platforms'`). Then write the entry in upstream's voice; don't paste twostraws' sentences.

**a. `overlay(_:alignment:)` → `overlay(alignment:content:)`.**
- Apple (2026-09-24): `swiftui/view/overlay(_:alignment:)` has `deprecatedAt: "27.2"`, with the message to use `overlay(alignment:content:)` instead.
- Add one sentence in upstream's style under `## When Targeting iOS 27+`, and this row to the summary table (the `| Deprecated | Recommended | Since |` table near the end):

  ```markdown
  | `overlay(_:alignment:)` | `overlay(alignment:content:)` | iOS 15+; old form deprecated in SDK 27.2 |
  ```

**b. `Text + Text` → `Text` interpolation.**
- Apple (2026-09-24): `swiftui/text/+(_:_:)` has `deprecatedAt: "26.0"`, with the message to use string interpolation on `Text` instead.
- Add a short `### Text` subsection under `## When Targeting iOS 26+` with this before/after snippet:

  ```swift
  // Deprecated in SDK 26
  Text("Hello").foregroundStyle(.red) + Text(" world")

  // Use interpolation
  let hello = Text("Hello").foregroundStyle(.red)
  Text("\(hello) world")
  ```

- And this row in the summary table:

  ```markdown
  | `Text + Text` | `Text` interpolation: `Text("\(a)\(b)")` | iOS 26+ |
  ```

Add both to `maintenance/apis.json` → `apis`:

```json
{"name": "overlay(_:alignment:)", "path": "swiftui/view/overlay(_:alignment:)", "claims": {"deprecated": true}},
{"name": "Text + Text", "path": "swiftui/text/+(_:_:)", "claims": {"deprecated": true}}
```

Append to `NOTICE.md`:

~~~bash
T="${TMPDIR:-/tmp}/swift-plugin-borrow"
cat >> plugins/swift/NOTICE.md <<'EOF'

## twostraws/SwiftUI-Agent-Skill

- Source: https://github.com/twostraws/SwiftUI-Agent-Skill at `be297ff80dddec529af1f9b1f1f114aab6c9d11c`, `swiftui-pro/references/api.md`
- Taken: the `overlay(_:alignment:)` and `Text + Text` deprecation entries in `skills/swiftui/references/latest-apis.md`, reworded

```text
EOF
cat "$T/twostraws/LICENSE" >> plugins/swift/NOTICE.md
printf '```\n' >> plugins/swift/NOTICE.md
~~~

Deviations row:

```markdown
| `references/latest-apis.md` | `overlay(_:alignment:)` and `Text + Text` deprecation entries (from twostraws, see NOTICE.md) | Apple deprecates both (27.2, 26.0); upstream had neither |
```

Run: `python3 maintenance/check-apis.py --strict | tail -1` → `0 failures, 0 warnings`.

```bash
git add plugins/swift/skills/swiftui/references/latest-apis.md plugins/swift/NOTICE.md maintenance/apis.json UPSTREAM.md
git commit -m "feat(swiftui): add overlay and Text concatenation deprecations"
```

- [ ] **Step 3: Dimillian → `view-structure.md`**

Source: `${TMPDIR:-/tmp}/swift-plugin-borrow/dimillian/swiftui-view-refactor/SKILL.md` → "1) View ordering", "3b) Extract actions and side effects out of `body`", "Large-view handling". Upstream already covers subview extraction (`## Extract Subviews, Not Computed Properties`, `## When to Extract Subviews`) and gives ordering as an *optional* suggestion (`## View File Structure (optional readability suggestion)`). Add only what's missing, in upstream's voice:

1. In `## View File Structure`, one sentence extending the suggested order: non-view computed properties go before `init`; view helpers after `body`; helper and async functions last. The section stays optional; don't make ordering a rule.
2. A new section `## Keep Actions and Side Effects Out of body`, after `## Keep View Body Simple and Avoid High-Cost Operations`:
   - non-trivial button actions and `.task`/`.onChange` bodies become small private methods;
   - business logic moves to models or services;
   - a short snippet (`Button("Save", action: save)`, `.task(id: query) { await reload(for: query) }`, and the two private methods).
3. In `## When to Extract Subviews`, one bullet: a view file past roughly 300 lines should be split into dedicated view types; `// MARK: -` extensions are no substitute; move reused subviews into their own files.

Don't take "Default to MV, not MVVM" or anything about view models.

Append to `NOTICE.md`:

~~~bash
T="${TMPDIR:-/tmp}/swift-plugin-borrow"
cat >> plugins/swift/NOTICE.md <<'EOF'

## Dimillian/Skills

- Source: https://github.com/Dimillian/Skills at `05ba982bfeb0d77d3c97d4542b0ee15034d05f84`, `swiftui-view-refactor/SKILL.md`
- Taken: the view-ordering detail, the actions-out-of-body section and the 300-line split rule in `skills/swiftui/references/view-structure.md`, reworded

```text
EOF
cat "$T/dimillian/LICENSE" >> plugins/swift/NOTICE.md
printf '```\n' >> plugins/swift/NOTICE.md
rg -c '^## ' plugins/swift/NOTICE.md
~~~
Expected: `3` (AvdLee, twostraws, Dimillian).

Deviations row:

```markdown
| `references/view-structure.md` | Ordering detail, actions-out-of-body section, 300-line split rule (from Dimillian, see NOTICE.md) | Gaps in upstream's view-structure guidance |
```

Run: `python3 maintenance/check-apis.py --strict | tail -1` → `0 failures, 0 warnings`. `save` and `reload` are declared by the snippet (`private func`), so they don't appear.

```bash
git add plugins/swift/skills/swiftui/references/view-structure.md plugins/swift/NOTICE.md maintenance/apis.json UPSTREAM.md
git commit -m "feat(swiftui): add view ordering, side-effect and file-size guidance"
```

---

### Task 13: `swift:design` — `SKILL.md` and `tokens.md`

**Files:**
- Create: `plugins/swift/skills/design/SKILL.md`, `plugins/swift/skills/design/references/tokens.md`
- Modify: `maintenance/apis.json` (entries for any API these files make claims about)

**Interfaces:**
- Consumes: `swift:swiftui` references to link to (`accessibility-patterns.md`, `liquid-glass.md`, `visionos.md`, `platform-availability.md`).
- Produces: the `swift:design` skill (`/swift:design`) with its router. Tasks 14–15 add a router row per reference file they create.

Sources to fetch while writing, and to cite per rule (paraphrase; never copy Apple's text):
- HIG JSON `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<page>.json` for `layout`, `typography`, `color`, `sf-symbols`, `materials`, `motion`, `accessibility`, `designing-for-ios`, `designing-for-ipados`, `designing-for-macos`, `designing-for-visionos`.
- WWDC25 219, 356 and 323 at `https://developer.apple.com/videos/play/wwdc2025/<n>/` (the pages carry transcripts).

Cite as `([HIG: Layout](https://developer.apple.com/design/human-interface-guidelines/layout))` or `([WWDC25 219](https://developer.apple.com/videos/play/wwdc2025/219/))`.

- [ ] **Step 1: Write `SKILL.md` (~120 lines)**

Frontmatter, exactly:

```yaml
---
name: design
description: Use when designing or restyling SwiftUI screens and components for iOS, iPadOS, macOS or visionOS, including information hierarchy and layout, typography and Dynamic Type, color and dark mode, SF Symbols, when and how to use Liquid Glass, platform idioms (tab bar vs sidebar vs ornaments, toolbars, inspectors, sheets vs windows), motion, and design tokens. Also use when a view looks like a web page, when choosing between native primitives, or when a project has no design tokens yet.
---
```

Body sections, in order:
1. `# Apple-Native Design`: one paragraph on scope. This skill decides *what* to build and *when* glass fits; `swift:swiftui` owns API correctness, accessibility code patterns and Liquid Glass mechanics, so link to it and don't repeat it.
2. `## Operating Rules`, exactly these three bullets (the first is the Global Constraints rule, word for word):

   ```markdown
   - If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict
   - With no project layer, use system text styles and semantic colours, and suggest the starter token set in `references/tokens.md` instead of scattering literals
   - Adopt Liquid Glass where `references/liquid-glass-design.md` says it fits; `swift:swiftui` keeps the API rules
   ```
3. `## Design Thinking`: the user's own text from `~/Dev/projects/example-app/.claude/skills/swiftui-design/SKILL.md` lines 12–19 (Purpose, Platform, Navigation pattern, Information hierarchy, Interaction model, and the **CRITICAL** "not web design" paragraph). Copy it verbatim, except add visionOS to "Platform" (`#if os(visionOS)`).
4. `## Apple-Native Means`: the same file's lines 24–28 (the bullets under "What Apple-native means"), verbatim.
5. `## What to Avoid`: the same file's lines 31–37 (the bullets under "What to AVOID"), verbatim, except replace "Hardcoded colors, fonts, spacing, or corner radii — always use tokens" with "Hardcoded colors, fonts, spacing, or corner radii — use the project's tokens, or the starter set in `references/tokens.md`".
6. `## Decision Rules`: 6–10 one-line rules, each cited. For example: grouped settings → `Form` + `Section` + `LabeledContent`; a destructive action takes `role: .destructive`; iPad and Mac lead with a sidebar, iPhone with a tab bar (HIG); visionOS puts persistent controls in ornaments (HIG: Ornaments). Write them from the fetched pages; drop any rule you can't cite.
7. `## Checklist`: checkboxes mirroring the rules.
8. `## References`: a router table (`| Topic | Reference |`) with, for now, one row:

   ```markdown
   | Design tokens: using a project's, or introducing a starter set | `references/tokens.md` |
   ```

- [ ] **Step 2: Write `references/tokens.md`**

Sections:
1. **Project has tokens.** Find them (grep for `enum Spacing`, `AppColor`, `Theme`, asset-catalog colour sets), use them, never add a literal; a genuinely new value becomes a new token.
2. **Project has none.** Suggest this starter set. Label it as a convention, not an Apple rule: the HIG sets no spacing scale, so cite HIG Layout only for "consistent spacing" and "respect safe areas and margins". Fonts stay on text styles (Dynamic Type, HIG Typography), and colours stay semantic (HIG Color).

   ```swift
   import SwiftUI

   enum Spacing {
       static let xs: CGFloat = 4
       static let sm: CGFloat = 8
       static let md: CGFloat = 16
       static let lg: CGFloat = 24
       static let xl: CGFloat = 32
   }

   enum Radius {
       static let sm: CGFloat = 8
       static let md: CGFloat = 12
       static let lg: CGFloat = 20
   }

   enum Motion {
       static let standard: Animation = .smooth
       static let quick: Animation = .snappy
   }
   ```

   Also: colours are asset-catalog colour sets with light and dark variants, or semantic system colours (`.primary`, `.secondary`, `Color.accentColor`, `.tint`); roles map to text styles (`.headline`, `.body`, `.caption`) rather than fixed sizes.
3. **How to introduce it.** One file (`DesignTokens.swift`); replace literals as files are touched, not in one sweep; mention it in the project's instructions file.

Add manifest entries for `smooth` / `snappy` if you state their availability. Run `python3 maintenance/check-apis.py --find smooth` to confirm they are `Animation` members.

- [ ] **Step 3: Check and commit**

Run: `claude plugin validate plugins/swift; python3 maintenance/check-apis.py --strict | tail -1`
Expected: exit 0; `0 failures, 0 warnings`. Example names such as `Spacing` and `Radius` are declared by the snippet and won't appear.

Run: `claude -p --plugin-dir plugins/swift --model haiku "Reply with only the names of the skills available to you that start with 'swift:', comma-separated."`
Expected: contains `swift:swiftui` and `swift:design`.

```bash
git add plugins/swift/skills/design maintenance/apis.json
git commit -m "feat(design): add swift:design skill with token guidance"
```

---

### Task 14: `swift:design` — hierarchy, typography, color, SF Symbols

**Files:**
- Create: `plugins/swift/skills/design/references/hierarchy-layout.md`, `typography.md`, `color.md`, `sf-symbols.md`
- Modify: `plugins/swift/skills/design/SKILL.md` (router rows), `maintenance/apis.json`

**Interfaces:**
- Consumes: SKILL.md router (Task 13).

Every file opens with a one-line scope sentence and a "Sources" list of the pages it cites. Every rule ends with its citation. Code examples use system styles and semantic colours. Accessibility code patterns are not repeated; link `swift:swiftui`'s `references/accessibility-patterns.md`.

- [ ] **Step 1: `hierarchy-layout.md`** (HIG Layout, HIG Designing for iOS/iPadOS/macOS)

Cover:
- content layer vs navigation layer (WWDC25 219/356);
- grouping with `Form`, `Section`, `LabeledContent`, `GroupBox`;
- spacing rhythm: consistent steps, grouping by proximity;
- alignment: leading-aligned text and one alignment edge per group;
- margins and safe areas;
- an example settings `Form`.

- [ ] **Step 2: `typography.md`** (HIG Typography)

Cover:
- text styles over fixed sizes;
- Dynamic Type, including testing at accessibility sizes;
- weights for emphasis (`bold()` lets the system pick the weight);
- `monospacedDigit()` for changing numbers and when to use `.monospaced` at all;
- line limits and truncation.

- [ ] **Step 3: `color.md`** (HIG Color, HIG Dark Mode, HIG Accessibility → contrast)

Cover:
- semantic and system colours;
- the accent/tint colour and its limited use;
- dark mode via asset variants;
- contrast minimums, with the numbers the HIG page gives, cited;
- status colours paired with a symbol or text, never colour alone.

- [ ] **Step 4: `sf-symbols.md`** (HIG SF Symbols)

Cover:
- rendering modes (monochrome, hierarchical, palette, multicolor) and when each fits;
- variants (`.fill` and similar);
- matching a symbol's weight and scale to adjacent text (`imageScale`, `font` on the symbol);
- symbol effects (`symbolEffect`) used for meaning, not decoration.

Add manifest entries for the APIs these rules name (`symbolRenderingMode(_:)`, `symbolEffect(_:options:value:)` and so on) after `--find`.

- [ ] **Step 5: Router rows, check, commit**

Add four rows to SKILL.md → References:

```markdown
| Hierarchy, grouping, spacing and alignment | `references/hierarchy-layout.md` |
| Text styles, Dynamic Type, weights | `references/typography.md` |
| System and semantic colour, dark mode, contrast | `references/color.md` |
| SF Symbols: rendering modes, variants, effects | `references/sf-symbols.md` |
```

Run: `python3 maintenance/check-apis.py --strict | tail -1` → `0 failures, 0 warnings`.

```bash
git add plugins/swift/skills/design maintenance/apis.json
git commit -m "feat(design): add hierarchy, typography, colour and SF Symbols references"
```

---

### Task 15: `swift:design` — Liquid Glass design, platform idioms, motion

**Files:**
- Create: `plugins/swift/skills/design/references/liquid-glass-design.md`, `platform-idioms.md`, `motion.md`
- Modify: `plugins/swift/skills/design/SKILL.md` (router rows), `maintenance/apis.json`

**Interfaces:**
- Consumes: `swift:swiftui` `references/liquid-glass.md`, `visionos.md`, `platform-availability.md` (link, don't repeat).

- [ ] **Step 1: `liquid-glass-design.md`** (WWDC25 219, 356, 323; Apple's "Adopting Liquid Glass" JSON at `https://developer.apple.com/tutorials/data/documentation/technologyoverviews/adopting-liquid-glass.json`)

Cover:
- glass belongs to the navigation layer (toolbars, tab bars, floating controls), not to content;
- standard components adopt it automatically, so custom glass is for custom floating controls only;
- regular vs clear, and when clear needs a dimming layer;
- tint only the primary action;
- avoid glass on glass (Apple's stated reason: clutter);
- concentric corners (`ConcentricRectangle`, `rect(corners:isUniform:)`, both in the manifest since Task 8).

Link `swift:swiftui`'s `liquid-glass.md` for the API, `platform-availability.md` for where each API exists, and `visionos.md` for the visionOS branch.

- [ ] **Step 2: `platform-idioms.md`** (HIG Designing for iOS/iPadOS/macOS/visionOS, Tab bars, Sidebars, Toolbars, Ornaments, Windows, Sheets, Inspectors, Pointing devices, Keyboards; HIG Accessibility for hit targets)

A section per platform: iPhone, iPad, Mac, Vision Pro. Cover:
- the primary navigation choice (tab bar vs sidebar vs ornaments);
- toolbars and inspectors;
- sheets vs windows;
- pointer and keyboard support.

Hit-target minimums are quoted from HIG Accessibility with the page cited. On 2026-09-24 the page listed 44x44 pt, 28x28 pt and 60x60 pt; state which platform each belongs to from the page itself.

- [ ] **Step 3: `motion.md`** (HIG Motion, HIG Accessibility → Reduce Motion)

Cover:
- springs as the default (`.smooth`, `.snappy`, `.bouncy` and when each fits);
- motion that explains a change, never decoration;
- honouring Reduce Motion via `@Environment(\.accessibilityReduceMotion)`;
- durations kept short.

Add manifest entries after `--find`.

- [ ] **Step 4: Router rows, check, commit**

Add three rows to SKILL.md → References:

```markdown
| When Liquid Glass fits, regular vs clear, tinting, concentric corners | `references/liquid-glass-design.md` |
| iPhone, iPad, Mac, Vision Pro idioms and hit targets | `references/platform-idioms.md` |
| Springs, meaningful motion, Reduce Motion | `references/motion.md` |
```

Run: `wc -l plugins/swift/skills/design/SKILL.md; python3 maintenance/check-apis.py --strict | tail -1`
Expected: SKILL.md is about 120 lines (spec §5; no more than 150); `0 failures, 0 warnings`.

```bash
git add plugins/swift/skills/design maintenance/apis.json
git commit -m "feat(design): add Liquid Glass, platform idiom and motion references"
```

---

### Task 16: GREEN — full verification

**Files:** none new; fixes go to skill text only, never to graders.

- [ ] **Step 1: Static gates**

Run:

```bash
cd ~/Dev/claude_skills/swift-plugin
claude plugin validate . ; echo "validate marketplace: $?"
claude plugin validate plugins/swift ; echo "validate plugin: $?"
python3 -m unittest discover maintenance/tests 2>&1 | tail -1
python3 maintenance/check-apis.py --strict --refresh | tail -1
git diff --stat upstream-5.1.0 -- plugins/swift/skills/swiftui
```
Expected:
- both validations `0`;
- unit tests `OK`;
- `0 failures, 0 warnings` against fresh Apple data (`--refresh`);
- a diffstat whose every file appears in `UPSTREAM.md` → Deviations. Check each one.

- [ ] **Step 2: Eval GREEN**

Run: `claude plugin eval plugins/swift --scaffold --trust-plugin --threshold 0.67 --max-cost-usd <ceiling> --json "${TMPDIR:-/tmp}/green.json" --allow-tools Write Edit`

Expected:
- exit 0: every case's WITH score ≥ 0.67 over the default 3 runs;
- the `skill-fired` indicators pass in the with-arm: `swift:swiftui` for the first three cases, `swift:design` for the fourth.

Report a table of RED (Task 9) vs GREEN `WITH` / `W/OUT` / `Δ` per case.

If a case fails, apply the superpowers:writing-skills REFACTOR loop to the **skill text**:
- read the failing run's transcript in `plugins/swift/evals/results/<timestamp>/`;
- find why the agent didn't follow the rule (the skill didn't fire, or the rule was unclear);
- tighten the description or the rule;
- rerun only that case with `--case <name>`.

A `Δ` near zero with a passing WITH is a finding to report, not a failure.

- [ ] **Step 3: Commit any fixes**

```bash
git add plugins/swift/skills maintenance/apis.json UPSTREAM.md
git commit -m "fix: tighten skill wording after eval GREEN run"
```
(Skip if nothing changed.)

---

### Task 17: `/onboard-repo` (the user runs it)

**Files:** whatever `/onboard-repo` stamps: `.claude/skills/changelog-release`, `update-docs`, `update-rules`, agent config, the docs IA, a consumer manual, and `CHANGELOG.md`.

- [ ] **Step 1: Hand over to the user**

Tell the user: "Run `/onboard-repo` in `~/Dev/claude_skills/swift-plugin` now (the full default pass). It's slash-only, so I can't start it." Wait until they report it finished. Its docs walk skips `docs/superpowers/`.

- [ ] **Step 2: Review its changes and rerun the gates**

Run: `git status --short; git diff --stat; python3 -m unittest discover maintenance/tests 2>&1 | tail -1; python3 maintenance/check-apis.py --strict | tail -1; claude plugin validate plugins/swift`
Expected:
- nothing under `plugins/swift/` changed, except what the user approved;
- gates as in Task 16 Step 1;
- `CHANGELOG.md` exists with an `## [Unreleased]` heading;
- `.claude/skills/changelog-release/SKILL.md` exists, and its REPO SPECIFICS name `plugins/swift/.claude-plugin/plugin.json` as the version home.

If the version home is wrong or missing, stop and ask the user.

- [ ] **Step 3: Commit (with the user's OK)**

```bash
git add -A
git status --short
git commit -m "chore: onboard repo (changelog-release, update-docs, update-rules, docs IA)"
```
Before committing, show the user the `git status --short` list.

---

### Task 18: Release 0.1.0

**Files:**
- Modify: `plugins/swift/.claude-plugin/plugin.json` (`version`), `CHANGELOG.md`

- [ ] **Step 1: Run `changelog-release`**

Invoke the stamped `changelog-release` skill. If this session doesn't list it, ask the user to restart the session in the repo first. It stages `plugin.json` and `CHANGELOG.md` and never commits.

Expected: `plugin.json` `"version": "0.1.0"` (0.0.0 + `feat:` commits → minor) and `## [0.1.0] - 2026-…` in `CHANGELOG.md`. If it proposes anything other than `0.1.0`, set `0.1.0` (the spec's first version) and tell the user.

Run: `jq -r .version plugins/swift/.claude-plugin/plugin.json; jq '.plugins[0] | has("version")' .claude-plugin/marketplace.json`
Expected: `0.1.0`; `false`.

- [ ] **Step 2: Commit and tag (with the user's OK)**

```bash
git commit -m "chore(release): v0.1.0"
claude plugin tag plugins/swift --dry-run
```
Expected: the dry run reports the tag `swift--v0.1.0` and no disagreement between `plugin.json` and the marketplace entry. This is spec §9's open check: "`claude plugin tag` accepts a marketplace entry without a `version`". If it refuses, stop and report to the user; don't add a `version` to the marketplace entry without their decision.

Run: `claude plugin tag plugins/swift -m "swift %s"; git tag -l`
Expected: tags `swift--v0.1.0` and `upstream-5.1.0`.

---

### Task 19: Publish and check scoping

Each step here is outward-facing. Ask the user before each one.

- [ ] **Step 1: Create the private GitHub repo (OK required)**

Run: `gh repo create jack1913/swift-plugin --private --source ~/Dev/claude_skills/swift-plugin --remote origin`
Expected: the repo is created and `origin` is set. Nothing is pushed yet.

- [ ] **Step 2: Push (OK required; commit and push are separate steps)**

Run: `git -C ~/Dev/claude_skills/swift-plugin push -u origin main && git -C ~/Dev/claude_skills/swift-plugin push origin upstream-5.1.0 swift--v0.1.0`
Expected: `main` and both tags are on GitHub; `gh repo view jack1913/swift-plugin --json visibility` → `PRIVATE`.

- [ ] **Step 3: Install into a scratch Swift repo at project scope (OK required)**

This covers spec §7.3. example-app's own install is the example-app session's step (example-app spec §3), so a scratch repo stands in here.

```bash
S="${TMPDIR:-/tmp}/swift-scope-check"; rm -rf "$S"; mkdir -p "$S"; git -C "$S" init -q
cd "$S" && claude plugin marketplace add jack1913/swift-plugin --scope project && claude plugin install swift@swift-plugin --scope project
jq '{extraKnownMarketplaces, enabledPlugins}' "$S/.claude/settings.json"
claude plugin details swift
```
Expected:
- `settings.json` lists the `swift-plugin` marketplace (github `jack1913/swift-plugin`) and `"swift@swift-plugin": true`;
- `details` shows the skills `swiftui` and `design`, with the projected token cost. Report that cost against spec §5's "~370 lines" note.

If `marketplace add` fails on authentication, stop and show the user the error (spec §9: private GitHub marketplace with the existing credentials). Don't change git or `gh` configuration yourself.

- [ ] **Step 4: Check that it's enabled only there**

```bash
Q="Reply with only the names of the skills available to you that start with 'swift:', comma-separated, or NONE."
(cd "${TMPDIR:-/tmp}/swift-scope-check" && claude -p --model haiku "$Q")
(cd ~/Dev/claude-configs && claude -p --model haiku "$Q")
```
Expected: `swift:swiftui, swift:design` in the scratch repo; `NONE` in `~/Dev/claude-configs`.

- [ ] **Step 5: Confirm an update reaches the install** (spec §9: version bump)

In the scratch repo, run: `claude plugin marketplace update swift-plugin && claude plugin update swift@swift-plugin --scope project`
Expected: "already at the latest version" (0.1.0 installed, nothing newer). This confirms the documented version-keyed behaviour; the next release proves the bump path.

- [ ] **Step 6: Clean up the scratch install**

Run: `cd "${TMPDIR:-/tmp}/swift-scope-check" && claude plugin uninstall swift@swift-plugin --scope project; rm -rf "${TMPDIR:-/tmp}/swift-scope-check"`
Expected: uninstalled; the directory is gone. The marketplace entry stays registered at user level, which is harmless because nothing is enabled.

- [ ] **Step 7: Tell example-app-5e**

Send the example-app session a message that:
- `swift@swift-plugin` 0.1.0 is on `jack1913/swift-plugin` (private);
- `swift:swiftui` and `swift:design` exist under exactly those names;
- the project-layer rule is in both skills, word for word;
- the install command is `claude plugin install swift@swift-plugin --scope project`.
