# Part 2, Plan 1: Multi-upstream machinery + `swift:concurrency` (0.1.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the multi-upstream machinery and the `swift:concurrency` fork, audited and eval-green, released as 0.1.4.

**Architecture:** One atomic machinery change (UPSTREAM.md sections, `upstream-diff.sh` skill argument, new unit tests, config surfaces) lands first; then a byte-for-byte import of AvdLee/Swift-Concurrency-Agent-Skill at tag `2.3.0`, day-one deviations as separate commits, `check-apis --strict` green, a report-only claim audit with fix commits, two eval cases, and the release. Plans 2 (testing → 0.1.5) and 3 (review → 0.1.6) are written after this ships.

**Tech Stack:** bash + stdlib-only Python (unittest), git tags, `maintenance/check-apis.py`, `claude plugin eval`, the Workflow tool for the audit.

**Spec:** `docs/superpowers/specs/2026-09-26-swift-skills-part2-design.md` (§3 machinery, §4 concurrency, §7 verification, §8 surfaces, §9 releases). Read it before executing; this plan argues from it.

## Global Constraints

- Names are fixed: marketplace `swift-plugin`, plugin `swift`; after Task 9 the skills are `swift:swiftui`, `swift:design`, `swift:concurrency` (AGENTS.md §4).
- New code in `maintenance/` is standard-library-only, including while a file is being created (`.claude/rules/apicheck-stdlib-only.md` only loads on read).
- Every change under `plugins/swift/skills/swiftui/` or `plugins/swift/skills/concurrency/` is its own commit with its `UPSTREAM.md` → Deviations row in the same commit.
- Upstream-derived files are edited through the shell (`sed`, `cat`, `cp`), never the Write/Edit tools: the user's PostToolUse formatter would reformat them and break byte-fidelity.
- `apis.json` ignore entries always carry a reason; an upstream API name Apple's index lacks also gets a Findings row in the owning upstream's section.
- Never hand-edit the generated block in `platform-availability.md`; regenerate with `python3 maintenance/check-apis.py --write-table`.
- Local commits are authorized by accepting this plan. **Pushes are not:** ask the user at Task 12.
- Release flow: `changelog-release` skill → commit → `claude plugin tag plugins/swift --dry-run` then without → push only with the user's OK.

## Review Focus

1. `maintenance/upstream-diff.sh` run with no argument must print the usage error naming the three skills and exit 2 — never silently default to swiftui (pinned by `test_no_args_is_usage_error`, Task 1).
2. The per-section baseline parse must read the selected skill's section only — a decoy section with a bogus baseline must not leak in (pinned by `test_baseline_comes_from_the_named_section`, Task 1).
3. The import must stay byte-for-byte: the formatter hook or an editor touching a copied file breaks the `git diff <import-tag>` contract (pinned by the `diff -r` verification step, Task 4).
4. `check-apis --strict` must not be silenced with unjustified ignore entries — every entry needs a reason, and API-name groups need Findings rows (pinned by Task 6's review step).
5. An eval case whose WITHOUT arm passes proves nothing — acceptance requires a positive delta, iterating on scaffold/prompt, never weakening graders (pinned by Task 10's acceptance rule).

---

### Task 1: `upstream-diff.sh` multi-upstream + test seam

**Files:**
- Modify: `maintenance/upstream-diff.sh` (whole file)
- Create: `maintenance/tests/test_upstream_diff.py`

**Interfaces:**
- Produces: CLI contract `maintenance/upstream-diff.sh <swiftui|concurrency|testing> [ref]`; env seams `UPSTREAM_DIFF_URL` (overrides the selected skill's upstream URL) and `UPSTREAM_MD` (overrides the UPSTREAM.md path, tests only); exit 2 + usage on missing/unknown skill; per-section baseline parse of `## SwiftUI` / `## Concurrency` / `## Testing` headings. Tasks 2, 4, 12 rely on this contract.

- [ ] **Step 1: Write the failing tests**

Create `maintenance/tests/test_upstream_diff.py` (stdlib-only, matches house test style):

```python
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "upstream-diff.sh"


def run(args, **env_extra):
    env = dict(os.environ, **env_extra)
    return subprocess.run(
        [str(SCRIPT), *args], capture_output=True, text=True, env=env
    )


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def make_upstream(root: Path, skill_path: str, tags):
    """Scratch repo: commit+tag per entry; file in skill_path changes each time."""
    repo = root / "upstream"
    (repo / skill_path).mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for i, tag in enumerate(tags, start=1):
        (repo / skill_path / "SKILL.md").write_text(f"v{i}\n")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", f"v{i}")
        git(repo, "tag", tag)
    return repo


def make_upstream_md(root: Path, section: str, baseline: str):
    md = root / "UPSTREAM.md"
    md.write_text(
        "# Upstream\n\n"
        f"## {section}\n\n"
        f"- **Baseline tag:** `{baseline}` (`0000000`)\n\n"
        "### Deviations\n\n"
        "## Decoy\n\n"
        "- **Baseline tag:** `99.99.99` (`1111111`)\n"
    )
    return md


class UpstreamDiffTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_no_args_is_usage_error(self):
        r = run([])
        self.assertEqual(r.returncode, 2)
        self.assertIn("swiftui|concurrency|testing", r.stderr)

    def test_unknown_skill_is_usage_error(self):
        r = run(["nope"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("swiftui|concurrency|testing", r.stderr)

    def test_diff_between_baseline_and_newest_tag(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0", "1.1.0"])
        md = make_upstream_md(self.root, "Concurrency", "1.0.0")
        r = run(
            ["concurrency"],
            UPSTREAM_DIFF_URL=str(repo),
            UPSTREAM_MD=str(md),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("baseline: 1.0.0 -> ref: 1.1.0", r.stdout)
        self.assertIn("SKILL.md", r.stdout)

    def test_baseline_comes_from_the_named_section(self):
        # Decoy section says 99.99.99; the SwiftUI section says 1.0.0, which
        # the scratch repo has. If the parse were global or picked the wrong
        # section, the run would fail on a missing ref instead.
        repo = make_upstream(self.root, "skills/swiftui-expert-skill", ["1.0.0", "1.1.0"])
        md = make_upstream_md(self.root, "SwiftUI", "1.0.0")
        r = run(["swiftui"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("baseline: 1.0.0", r.stdout)

    def test_wrong_section_baseline_is_a_clear_error(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0"])
        md = make_upstream_md(self.root, "Concurrency", "1.0.0")
        # asking for swiftui reads the Decoy baseline (99.99.99): missing ref
        r = run(["swiftui"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 2)
        self.assertIn("99.99.99", r.stderr)

    def test_no_plain_tag_error(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0-beta.1"])
        md = make_upstream_md(self.root, "Concurrency", "1.0.0-beta.1")
        r = run(["concurrency"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        # baseline == ref == the only tag: no-changes path, proving beta tags
        # are accepted when named explicitly by the baseline
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no upstream changes", r.stdout)

    def test_ref_equal_to_baseline_reports_no_changes(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0", "1.1.0"])
        md = make_upstream_md(self.root, "Concurrency", "1.1.0")
        r = run(["concurrency"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no upstream changes", r.stdout)


if __name__ == "__main__":
    unittest.main()
```

Note: `test_no_plain_tag_error` needs a repo whose **newest-plain-tag lookup** fails while an explicit baseline exists — the scratch repo above has only `1.0.0-beta.1`, so the default-ref path errors. Adjust the assertion after Step 2 shows the real behavior: if the baseline check runs before ref resolution the exit is 0 with "no upstream changes"; if after, exit 2 with "no plain X.Y.Z tag". Keep whichever the correct ordering produces and name the test for it (the ordering in the current script resolves `ref` after `baseline`, so expect exit 2 and rename to `test_no_plain_tag_errors` asserting `assertIn("no plain X.Y.Z tag", r.stderr)`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest maintenance.tests.test_upstream_diff -v` (from the repo root; if the module path doesn't resolve, `python3 -m unittest discover maintenance/tests -p 'test_upstream_diff.py' -v`)
Expected: FAIL — `test_no_args_is_usage_error` and friends exit 0 or with the wrong stderr, because today's script takes `[ref]` as `$1` and treats `concurrency` as a ref.

- [ ] **Step 3: Rewrite the script**

Replace `maintenance/upstream-diff.sh` with (keeps every existing comment that still applies):

```bash
#!/usr/bin/env bash
# Show what an upstream changed in its skill folder between our baseline (UPSTREAM.md) and a ref.
# Usage: maintenance/upstream-diff.sh <swiftui|concurrency|testing> [ref]
#   (default ref: that upstream's newest plain X.Y.Z tag, pre-releases skipped)
# Read-only: clones into a temp dir and never writes to this repo. Porting is manual.
# UPSTREAM_DIFF_URL overrides the upstream URL for the selected skill (e.g. for tests).
# UPSTREAM_MD overrides the UPSTREAM.md path (tests only).
set -euo pipefail

skill="${1:-}"
case "$skill" in
  swiftui)
    upstream_url="${UPSTREAM_DIFF_URL:-https://github.com/AvdLee/SwiftUI-Agent-Skill}"
    skill_path="skills/swiftui-expert-skill"
    section="SwiftUI"
    ;;
  concurrency)
    upstream_url="${UPSTREAM_DIFF_URL:-https://github.com/AvdLee/Swift-Concurrency-Agent-Skill}"
    skill_path="skills/swift-concurrency"
    section="Concurrency"
    ;;
  testing)
    upstream_url="${UPSTREAM_DIFF_URL:-https://github.com/AvdLee/Swift-Testing-Agent-Skill}"
    skill_path="swift-testing-expert"
    section="Testing"
    ;;
  *)
    echo "usage: maintenance/upstream-diff.sh <swiftui|concurrency|testing> [ref]" >&2
    exit 2
    ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream_md="${UPSTREAM_MD:-$repo_root/UPSTREAM.md}"

# Per-section baseline parse: print the section, stop at the next '## ' heading.
# ('### Deviations' does not match '^## ' — its third character is '#', not ' '.)
baseline="$(
  sed -n "/^## ${section}$/,/^## /p" "$upstream_md" \
    | sed -n 's/^- \*\*Baseline tag:\*\* `\([^`]*\)`.*/\1/p' \
    | head -n 1
)"
if [[ -z "$baseline" ]]; then
  echo "error: $upstream_md has no '## $section' section with a line like: - **Baseline tag:** \`5.1.0\` (...)" >&2
  exit 2
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone --quiet "$upstream_url" "$tmp/upstream"
cd "$tmp/upstream"

# `git tag --sort=-v:refname | head -n 1` would also pick a pre-release tag
# (e.g. 5.2.0-beta.1) if upstream cut one after the last plain release; filter
# to plain X.Y.Z tags (an optional leading "v") before taking the newest.
# Under `pipefail`, a `grep` that matches nothing exits 1, which becomes the
# whole pipeline's status even though every later stage exits 0 on empty
# input -- and with `set -e` that aborted the script right there, silently.
# `|| true` defers that to the explicit -z check below.
# "v1.10.0" sorts wrong against "2.0.0" under plain `sort -V` (the leading
# "v" makes it compare as text), so tags are sorted on a tab-separated key
# with the "v" stripped, then the matching original tag is printed and used.
if [[ -n "${2:-}" ]]; then
  ref="$2"
else
  ref="$(
    git tag --list \
      | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' \
      | while IFS= read -r t; do printf '%s\t%s\n' "${t#v}" "$t"; done \
      | sort -t "$(printf '\t')" -k1,1 -V \
      | tail -n 1 \
      | cut -f2 \
      || true
  )"
  if [[ -z "$ref" ]]; then
    echo "error: upstream has no plain X.Y.Z tag (optionally v-prefixed); pass a ref explicitly" >&2
    exit 2
  fi
fi
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

- [ ] **Step 4: Run the full test suite**

Run: `python3 -m unittest discover maintenance/tests -v 2>&1 | tail -3`
Expected: PASS, count = 96 + the new tests (~103). The new script is exercised only through `UPSTREAM_DIFF_URL`/`UPSTREAM_MD`; no test touches the network.

- [ ] **Step 5: Commit**

```bash
git add maintenance/upstream-diff.sh maintenance/tests/test_upstream_diff.py
git commit -m "feat(maintenance): upstream-diff.sh takes a skill argument and parses per-section baselines"
```

### Task 2: UPSTREAM.md restructure + docs that quote it

**Files:**
- Modify: `UPSTREAM.md` (header + section headings only; table contents untouched)
- Modify: `docs/manual/work-on-it.md` (the "Check upstream for changes" section, ~line 93-107)
- Modify: `docs/.onboard-captures/upstream-diff.txt` (re-capture)

**Interfaces:**
- Consumes: Task 1's script contract.
- Produces: `## SwiftUI` / `## Concurrency` / `## Testing` section shape with per-section `- **Baseline tag:**` lines and `### Deviations` / `### Ported` / `### Findings` subsections. Task 4 writes into the Concurrency section.

- [ ] **Step 1: Restructure with a shell script (UPSTREAM.md is upstream-adjacent record; keep edits mechanical)**

```bash
cd <home>/Dev/claude_skills/swift-plugin && python3 - <<'PYEOF'
p = 'UPSTREAM.md'; t = open(p).read()
old_head = """# Upstream

- **Upstream:** https://github.com/AvdLee/SwiftUI-Agent-Skill, folder `skills/swiftui-expert-skill/`, MIT
- **Baseline tag:** `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`)
- **Local import tag:** `upstream-5.1.0`, this repo's first commit: the folder byte-for-byte at the baseline

`git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows every change listed under Deviations. `maintenance/upstream-diff.sh [ref]` shows what upstream changed after the baseline. Porting is manual: read the diff, port what fits, bump the baseline above, add a Ported row.

## Deviations"""
new_head = """# Upstream

One section per upstream. Porting is manual: read the diff, port what fits, bump that section's baseline, add a Ported row. `maintenance/upstream-diff.sh <swiftui|concurrency|testing> [ref]` shows what an upstream changed after its baseline.

## SwiftUI

- **Upstream:** https://github.com/AvdLee/SwiftUI-Agent-Skill, folder `skills/swiftui-expert-skill/`, MIT
- **Baseline tag:** `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`)
- **Local import tag:** `upstream-5.1.0`, this repo's first commit: the folder byte-for-byte at the baseline

`git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows every change listed under Deviations.

### Deviations"""
assert t.count(old_head) == 1
t = t.replace(old_head, new_head)
assert t.count("\n## Ported\n") == 1 and t.count("\n## Findings\n") == 1
t = t.replace("\n## Ported\n", "\n### Ported\n").replace("\n## Findings\n", "\n### Findings\n")
# Findings intro: the ignore-group pointer names the section (ADR-0009 wording)
a = "While a row is open, `check-apis.py` ignores its name under the group that points here."
b = "While a row is open, `check-apis.py` ignores its name in the `apis.json` ignore group \"upstream names not in Apple's index\", whose reason text names this section."
assert t.count(a) == 1
t = t.replace(a, b)
open(p, 'w').write(t)
PYEOF
```

If any `assert` fires, stop and reconcile by hand — the file changed since planning.

- [ ] **Step 2: Update work-on-it.md's usage text**

In `docs/manual/work-on-it.md`, section `## Check upstream for changes`: replace the command line `maintenance/upstream-diff.sh [ref]` with `maintenance/upstream-diff.sh <swiftui|concurrency|testing> [ref]` and adjust the surrounding sentence to say the first argument picks the upstream. Keep the `capture=upstream-diff` block for Step 3.

- [ ] **Step 3: Re-capture upstream-diff**

```bash
cd <home>/Dev/claude_skills/swift-plugin
maintenance/upstream-diff.sh swiftui > "$TMPDIR/ud.raw" 2>&1 || true
python3 .claude/skills/update-docs/scripts/check.py redact "$TMPDIR/ud.raw" --home "$HOME" --user "$USER" --stamp 20260925-114824 > "$TMPDIR/ud.red" && mv "$TMPDIR/ud.red" docs/.onboard-captures/upstream-diff.txt
```

Then make the page's `capture=upstream-diff` block quote the first lines of the new capture (the `upstream:`/`baseline:` lines), and confirm the gate: `python3 .claude/skills/update-docs/scripts/check.py check-docs docs README.md AGENTS.md --captures docs/.onboard-captures --coverage docs/.onboard-coverage.json` → exit 0. Review the redacted capture for secrets before committing (it is network output).

- [ ] **Step 4: Verify the script against the real files**

Run: `maintenance/upstream-diff.sh swiftui | head -3` → prints `upstream: https://github.com/AvdLee/SwiftUI-Agent-Skill ...`, `baseline: 5.1.0 -> ref: <newest>`. Run `maintenance/upstream-diff.sh` with no args → exit 2, usage on stderr.

- [ ] **Step 5: Commit**

```bash
git add UPSTREAM.md docs/manual/work-on-it.md docs/.onboard-captures/upstream-diff.txt
git commit -m "docs(upstream): restructure UPSTREAM.md into per-upstream sections"
```

### Task 3: Config surfaces (scopes, constraints, update-docs rows)

**Files:**
- Modify: `AGENTS.md` (§4 constraint bullet)
- Modify: `.claude/skills/changelog-release/SKILL.md` (REPO SPECIFICS commit-convention line only)
- Modify: `.claude/skills/update-docs/SKILL.md` (REPO SPECIFICS section→source map: the UPSTREAM.md row)
- Modify: `docs/manual/work-on-it.md` (`## Change swift:swiftui` section)

**Interfaces:**
- Produces: generalized fork discipline used by Tasks 4–8 commit messages and by Plans 2–3.

- [ ] **Step 1: Generalize the AGENTS.md §4 constraint**

Replace the bullet

> A change under `plugins/swift/skills/swiftui/` is its own commit, with its `UPSTREAM.md` → Deviations row in that commit (spec §4). This applies while writing, when no `paths:` rule has loaded.

with

> A change under a forked skill (`plugins/swift/skills/swiftui/`, `plugins/swift/skills/concurrency/`) is its own commit, with its `UPSTREAM.md` → Deviations row — in that upstream's section — in that commit (part-2 spec §3). This applies while writing, when no `paths:` rule has loaded.

- [ ] **Step 2: Extend the commit scopes**

In `.claude/skills/changelog-release/SKILL.md` REPO SPECIFICS, change "with scopes `swiftui`, `design`, `maintenance`, `evals`, `plan`" to "with scopes `swiftui`, `design`, `concurrency`, `testing`, `review`, `maintenance`, `evals`, `plan`". Touch nothing outside the REPO SPECIFICS block.

- [ ] **Step 3: Extend the update-docs source map**

In `.claude/skills/update-docs/SKILL.md` REPO SPECIFICS, replace the row

> `UPSTREAM.md` → `git diff upstream-5.1.0 -- plugins/swift/skills/swiftui`, `maintenance/upstream-diff.sh`

with

> `UPSTREAM.md` → per section: `git diff upstream-5.1.0 -- plugins/swift/skills/swiftui`, `git diff upstream-concurrency-2.3.0 -- plugins/swift/skills/concurrency` (added at its import), `maintenance/upstream-diff.sh <skill>`

(the concurrency diff command joins the row at Task 4's commit — add it there, not now; this step only generalizes the row's shape and the script usage).

- [ ] **Step 4: Generalize the work-on-it section**

Rename `## Change swift:swiftui` to `## Change a forked skill` and rewrite its body:

> Every change under a forked skill's folder (`plugins/swift/skills/swiftui/`, `plugins/swift/skills/concurrency/`) is its own commit, with a row in that upstream's `UPSTREAM.md` section → Deviations in the same commit. `git diff <local-import-tag> -- <skill-folder>` then shows exactly what differs from upstream.

Re-run the docs gate (Task 2 Step 3 command) → exit 0.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md .claude/skills/changelog-release/SKILL.md .claude/skills/update-docs/SKILL.md docs/manual/work-on-it.md
git commit -m "docs: generalize the fork discipline and commit scopes for the new upstreams"
```

### Task 4: Byte-for-byte import + local tag + UPSTREAM.md Concurrency section + NOTICE

**Files:**
- Create: `plugins/swift/skills/concurrency/**` (copied, never hand-written)
- Modify: `UPSTREAM.md` (new `## Concurrency` section)
- Modify: `plugins/swift/NOTICE.md` (new entry)

**Interfaces:**
- Consumes: Task 2's section shape.
- Produces: local tag `upstream-concurrency-<tag>`; folder `plugins/swift/skills/concurrency/`; the Concurrency section that Tasks 5–8 write Deviations rows into.

- [ ] **Step 1: Verify the newest plain tag (spec §10)**

```bash
git clone --quiet https://github.com/AvdLee/Swift-Concurrency-Agent-Skill "$TMPDIR/conc-upstream"
git -C "$TMPDIR/conc-upstream" tag --list | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1
```

Expected: `2.3.0`. If it prints something newer, use that tag everywhere below and record the change in the section's Baseline row. Pin the SHA: `git -C "$TMPDIR/conc-upstream" rev-parse <tag>^{commit}` (planning-time value for 2.3.0: `45fa49e4e0b2af4d43b1cb458903f8030ac993bd`; re-verify, don't trust). Check out the tag: `git -C "$TMPDIR/conc-upstream" checkout --quiet <tag>`.

- [ ] **Step 2: Copy the folder and verify byte-fidelity**

```bash
cd <home>/Dev/claude_skills/swift-plugin
cp -R "$TMPDIR/conc-upstream/skills/swift-concurrency" plugins/swift/skills/concurrency
diff -r "$TMPDIR/conc-upstream/skills/swift-concurrency" plugins/swift/skills/concurrency && echo BYTE-FOR-BYTE
```

Expected: `BYTE-FOR-BYTE`. From here on, every edit inside `plugins/swift/skills/concurrency/` goes through shell tools (Global Constraints).

- [ ] **Step 3: Add the UPSTREAM.md Concurrency section**

Insert before the line `## Concurrency` does not yet exist — append at end of file, or after the SwiftUI section's `### Findings` table (keep sections in spec order: SwiftUI, Concurrency; Testing arrives in Plan 2):

```markdown
## Concurrency

- **Upstream:** https://github.com/AvdLee/Swift-Concurrency-Agent-Skill, folder `skills/swift-concurrency/`, MIT
- **Baseline tag:** `2.3.0` (`45fa49e4e0b2af4d43b1cb458903f8030ac993bd`)
- **Local import tag:** `upstream-concurrency-2.3.0`, the import commit: the folder byte-for-byte at the baseline

`git diff upstream-concurrency-2.3.0 -- plugins/swift/skills/concurrency` shows every change listed under Deviations.

### Deviations

| File | Change | Why |
|---|---|---|

### Ported

(none yet)

### Findings

Names upstream uses that Apple's documentation index did not have at import time. While a row is open, `check-apis.py` ignores its name in the `apis.json` ignore group "upstream names not in Apple's index", whose reason text names this section. Status says what was decided: **Fixed**, **Resolved** or **Open** (with the reason it stays).

| Name | Upstream file | Nearest Apple API | Status |
|---|---|---|---|
```

Replace the SHA and tag with Step 1's verified values.

- [ ] **Step 4: Add the NOTICE.md entry**

Append after the existing AvdLee section, following its exact shape (fetch the license text from the clone, not memory):

```markdown
## AvdLee/Swift-Concurrency-Agent-Skill

- Source: https://github.com/AvdLee/Swift-Concurrency-Agent-Skill at `2.3.0` (`45fa49e4e0b2af4d43b1cb458903f8030ac993bd`)
- Taken: `plugins/swift/skills/concurrency/`, which is upstream's `skills/swift-concurrency/` with the changes the repository's `UPSTREAM.md` lists. Files marked "New" there are this project's own.
```

plus the fenced MIT text: `cat "$TMPDIR/conc-upstream/LICENSE"` → paste verbatim into the code fence like the existing entry (verify the copyright line; expected "Copyright (c) 2025 Antoine van der Lee" or similar — copy what the file says).

- [ ] **Step 5: Commit, then tag the import commit**

```bash
git add plugins/swift/skills/concurrency UPSTREAM.md plugins/swift/NOTICE.md
git commit -m "feat(concurrency): import AvdLee Swift-Concurrency-Agent-Skill 2.3.0 byte-for-byte"
git tag upstream-concurrency-2.3.0
git diff upstream-concurrency-2.3.0 -- plugins/swift/skills/concurrency | wc -l   # → 0
```

Also add the Task 3 update-docs row's concurrency diff command now (the tag exists): edit `.claude/skills/update-docs/SKILL.md` REPO SPECIFICS row and include it in this commit.

### Task 5: Day-one deviations (four commits)

**Files:**
- Modify: `plugins/swift/skills/concurrency/SKILL.md` (frontmatter; `${SKILL_DIR}` if present)
- Delete: `plugins/swift/skills/concurrency/agents/`, `plugins/swift/skills/concurrency/assets/`
- Create: `plugins/swift/skills/concurrency/LICENSE-upstream`
- Modify: `UPSTREAM.md` (a Deviations row per commit)

**Interfaces:**
- Consumes: Task 4's import + section.
- Produces: skill named `concurrency` (command `/swift:concurrency`), Claude Code script paths, no dead weight, license traveling with the install.

Each deviation below is **its own commit with its own row** (Global Constraints). Row template: `| <files> | <change> | <why> |`.

- [ ] **Step 1: Frontmatter name**

```bash
cd <home>/Dev/claude_skills/swift-plugin
sed -i '' 's/^name: swift-concurrency$/name: concurrency/' plugins/swift/skills/concurrency/SKILL.md
head -4 plugins/swift/skills/concurrency/SKILL.md
```

Upstream's description is already trigger-worded house style — keep it verbatim. Row: `| SKILL.md frontmatter | name: concurrency | Plugin skill command is /swift:<name> |`. Commit: `git commit -m "feat(concurrency): rename the skill to concurrency for the swift namespace"`.

- [ ] **Step 2: `${SKILL_DIR}` → `${CLAUDE_SKILL_DIR}` (if any)**

```bash
grep -rn 'SKILL_DIR' plugins/swift/skills/concurrency | grep -v CLAUDE_SKILL_DIR | wc -l
```

If the count is > 0: `grep -rl '${SKILL_DIR}' plugins/swift/skills/concurrency | xargs sed -i '' 's/\${SKILL_DIR}/${CLAUDE_SKILL_DIR}/g'` (single-quoted sed pattern; verify with the grep again → 0), row `| <files> | ${SKILL_DIR} → ${CLAUDE_SKILL_DIR} (N places) | Claude Code substitutes ${CLAUDE_SKILL_DIR} |`, commit `fix(concurrency): point script paths at CLAUDE_SKILL_DIR`. If the count is 0, skip this step and record "no ${SKILL_DIR} occurrences" in the plan's execution notes — no commit, no row.

- [ ] **Step 3: Delete `agents/` and `assets/`**

```bash
git rm -r -q plugins/swift/skills/concurrency/agents plugins/swift/skills/concurrency/assets
```

Row: `| agents/, assets/ | Deleted | Codex agent config and logos; Claude Code uses neither |`. Commit: `chore(concurrency): drop upstream's agent config and logos`.

- [ ] **Step 4: LICENSE-upstream**

```bash
cp "$TMPDIR/conc-upstream/LICENSE" plugins/swift/skills/concurrency/LICENSE-upstream
```

Row: `| LICENSE-upstream | New: upstream's MIT license text | Travels with every install (the plugin cache copies only plugins/swift/) |`. Commit: `docs(concurrency): carry upstream's MIT license inside the skill`.

- [ ] **Step 5: Verify the diff is exactly the four deviations**

Run: `git diff upstream-concurrency-2.3.0 --stat -- plugins/swift/skills/concurrency`
Expected: SKILL.md (1–2 lines), deleted agents/assets files, added LICENSE-upstream — nothing else.

### Task 6: `check-apis --strict` green for concurrency

**Files:**
- Modify: `maintenance/apis.json` (frameworks list if needed; ignore entries; pinned claims)
- Modify: `UPSTREAM.md` (Findings rows for API-name groups)

**Interfaces:**
- Consumes: the imported skill text (the scanner already covers `plugins/swift/skills/**/*.md`, `maintenance/apicheck/cli.py`).
- Produces: `--strict` exit 0; every new ignore entry justified; every platform statement in concurrency text either pinned or unclaimed.

- [ ] **Step 1: Run strict and triage**

```bash
python3 maintenance/check-apis.py --refresh --strict 2>&1 | tail -30
```

Expect unresolved names from the new skill. For each: classify per ADR-0009 — example types, prose words, generic parameters, Apple names that aren't index entries (e.g. Instruments/runtime symbols), or upstream API names Apple's index lacks.

- [ ] **Step 2: Add frameworks only if names demand them**

If Swift Testing/Observation symbols appear (upstream ships `references/observation.md` and `references/testing.md`), test resolvability by adding `"observation"` (and only what's needed) to `apis.json` `"frameworks"`, then re-run. Every framework addition must reduce the unresolved list — revert any that doesn't.

- [ ] **Step 3: Add ignore entries with reasons, and Findings rows**

Group ignore entries under the existing reason keys (extend lists; never invent a group without a reason sentence). Any name in the "upstream names not in Apple's index" group gets a row in UPSTREAM.md's **Concurrency → Findings** table (name, upstream file, nearest Apple API, Status **Open** with the evidence: doc JSON 404 / index miss / SDK grep). Pin claims for platform statements the text makes (expected: few — concurrency APIs are old and cross-platform; pin only what the text asserts, e.g. a "macOS 10.15+" or "not on Linux" style claim, with the doc path from `--find`).

- [ ] **Step 4: Green + review gate**

Run: `python3 maintenance/check-apis.py --strict` → `0 failures, 0 warnings`; `python3 -m unittest discover maintenance/tests 2>&1 | tail -1` → OK. Then re-read every new ignore entry: does its reason match ADR-0009's groups, and does every API-name-group entry have a Findings row? (Review Focus 4.)

- [ ] **Step 5: Commit**

```bash
git add maintenance/apis.json UPSTREAM.md
git commit -m "feat(maintenance): resolve the concurrency fork's API names against Apple's indexes"
```

(If `--write-table` changed `platform-availability.md` because a pinned claim carries `table: true`, include it; new concurrency claims should omit `table` unless the generated table genuinely gains a row.)

### Task 7: Claim audit (report-only workflow)

**Files:** none (report-only; scratch under `$TMPDIR`)

**Interfaces:**
- Consumes: the imported + strict-green skill.
- Produces: a verified findings list (CONFIRMED / REFUTED / UNVERIFIABLE with evidence) that Task 8 turns into fix commits.

- [ ] **Step 1: Launch the audit workflow (user opted in via spec §4; fleet ≤5: 4 sonnet auditors + 1 opus verifier)**

Shards (~4–5 files each): (a) SKILL.md + `_index.md` + `glossary.md` + `linting.md`; (b) `async-await-basics.md` + `tasks.md` + `threading.md` + `sendable.md`; (c) `actors.md` + `migration.md` + `performance.md` + `memory-management.md`; (d) `async-sequences.md` + `async-algorithms.md` + `testing.md` + `core-data.md` + `observation.md`. Auditor brief = the 0.1.3 audit brief (claim kinds, evidence sources in order: Apple doc JSON → SDK `.swiftinterface` → `swiftc -typecheck -swift-version 6`; report-only; severity scale; honest not_checked). Verifier = the 0.1.3 verifier brief (re-check every finding from primary evidence, try to refute, CONFIRMED only on own evidence). One addition to both briefs: this skill's domain is the Swift standard library / `_Concurrency` / Foundation — `swiftc -typecheck` snippets need `-target arm64-apple-macos13` or newer and `import Foundation`/`_Concurrency` as appropriate; Linux-only or toolchain-version claims are UNVERIFIABLE on this machine, say so.

- [ ] **Step 2: Triage and report to the user**

Summarize confirmed findings by severity with file:line, before Task 8 touches anything. If zero confirmed, skip Task 8 and record the clean audit in the execution notes.

### Task 8: Fix confirmed findings (conditional)

**Files:** whatever the findings name under `plugins/swift/skills/concurrency/`; `UPSTREAM.md` rows; `maintenance/apis.json` pins where a fix makes a platform statement.

**Interfaces:**
- Consumes: Task 7's CONFIRMED list.
- Produces: one commit per finding group, each with its Deviations row (marked "**Upstream bug, worth reporting upstream:**" with the evidence command + decisive output, dated), each fixed snippet re-typechecked (old form fails, fixed form passes) where the finding is compile-class.

- [ ] **Step 1: Fix, evidence, commit — per finding group** (shell edits only; follow the 0.1.3 fix-commit pattern exactly).
- [ ] **Step 2: Re-run gates:** `check-apis --strict`, unit tests, and `git diff upstream-concurrency-2.3.0 -- plugins/swift/skills/concurrency` fully covered by Deviations rows.

### Task 9: ADR-0010 + registry surfaces

**Files:**
- Create: `docs/adr/ADR-0010-own-copy-fork-model-extended.md`
- Modify: `AGENTS.md` (§1 identity sentence if it enumerates skills; §3 pointer index; §4 names sentence)
- Modify: `README.md` (skill table)
- Modify: `plugins/swift/.claude-plugin/plugin.json` (description)
- Modify: `.claude-plugin/marketplace.json` (description)

**Interfaces:**
- Produces: the public surface naming five… three skills (testing/review join in Plans 2–3).

- [ ] **Step 1: ADR-0010** (house template `docs/adr/ADR-TEMPLATE.md`):

Title: "ADR-0010: The own-copy fork model extends to the concurrency and testing upstreams". Status accepted; Date = execution day; Source: part-2 spec §2–§4, the import + deviation commits (SHAs). Context: ADR-0004 decided the swiftui fork; two more AvdLee skills arrive. Decision: same model per upstream — byte-for-byte import tag, per-change Deviations rows in that upstream's UPSTREAM.md section, manual porting via `upstream-diff.sh <skill>`, claim audit before release. Consequences: three baselines to track; `upstream-diff.sh` requires the skill argument; Findings ignore-group reasons name their section; every audit finding is upstream-reportable material.

- [ ] **Step 2: AGENTS.md** — §4 names sentence: "skills `swift:swiftui`, `swift:design` and `swift:concurrency`"; §3 pointer index rows: `swift:concurrency (upstream fork)` → `plugins/swift/skills/concurrency/SKILL.md`; adjust the UPSTREAM.md row's topic to "Upstream baselines, Deviations, Ported, Findings (per upstream)".

- [ ] **Step 3: README + descriptions** — README skill table gains: `| swift:concurrency | Swift 6 concurrency: Sendable, actors, async/await, data-race diagnosis, 5→6 migration. A fork of AvdLee/Swift-Concurrency-Agent-Skill (UPSTREAM.md) |`. `plugin.json` description → "Correct, current, Apple-native Swift: swift:swiftui (APIs and correctness, visionOS, previews), swift:design (Apple-native design), swift:concurrency (Swift 6 concurrency)." `marketplace.json` description → same text (both descriptions converge now; spec §8).

- [ ] **Step 4: Gates + commit**

Run `claude plugin validate plugins/swift` and `claude plugin validate .` (the marketplace warning about its description disappears once its description matches; any remaining warning must be pre-existing), check-docs, check-instructions. Commit: `docs: register swift:concurrency across ADR, AGENTS, README and the manifests`.

### Task 10: Eval cases (2) + iteration

**Files:**
- Create: `plugins/swift/evals/sendable-shared-cache/{case.yaml,prompt.md,scaffold.sh,graders/*.md}`
- Create: `plugins/swift/evals/mainactor-detached-task/{case.yaml,prompt.md,scaffold.sh,graders/*.md}`

**Interfaces:**
- Consumes: the shipped skill; harness shape copied exactly from `plugins/swift/evals/glass-button-ios17/`.
- Produces: two cases passing the acceptance rule below.

- [ ] **Step 1: Case `sendable-shared-cache`**

`scaffold.sh` (executable, `chmod +x`):

```bash
#!/usr/bin/env bash
# Workspace: a Swift 6 package whose cache silences data-race checking with nonisolated(unsafe).
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.macOS("14.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/Cache.swift <<'SWIFT'
import Foundation

public final class ImageCache {
    public static let shared = ImageCache()
    nonisolated(unsafe) private var storage: [String: Data] = [:]

    public func data(forKey key: String) -> Data? { storage[key] }
    public func insert(_ data: Data, forKey key: String) { storage[key] = data }
}
SWIFT
cat > Sources/Demo/Downloader.swift <<'SWIFT'
import Foundation

public func download(_ key: String, from url: URL) async throws -> Data {
    if let cached = ImageCache.shared.data(forKey: key) { return cached }
    let (data, _) = try await URLSession.shared.data(from: url)
    ImageCache.shared.insert(data, forKey: key)
    return data
}
SWIFT
```

`case.yaml`:

```yaml
schema_version: "1.1"
name: sendable-shared-cache
context:
  scaffold_script: scaffold.sh
```

`prompt.md` (frontmatter + body, house shape):

```markdown
---
description: Remove a nonisolated(unsafe) opt-out under Swift 6 strict concurrency
tags: [concurrency, sendable, swift6]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: 'ImageCache becomes an actor (or an explicitly lock-protected Sendable type) with no nonisolated(unsafe) or @unchecked opt-out, and Downloader.swift keeps compiling with await at the call sites.'
---

The team enabled Swift 6 language mode. Sources/Demo/Cache.swift silences the data-race diagnostic with nonisolated(unsafe). Remove that opt-out and make ImageCache safe to share across tasks, keeping Sources/Demo/Downloader.swift compiling. Do not suppress checking (no @unchecked Sendable, no @preconcurrency, no nonisolated(unsafe)).
```

Graders (`graders/race-free-type.md`, `graders/await-call-sites.md`, `graders/skill-fired.md`):

```markdown
---
type: regex
pattern: 'actor ImageCache|Mutex<|OSAllocatedUnfairLock'
target: { source: file, path: Sources/Demo/Cache.swift }
---
```

```markdown
---
type: regex
pattern: 'await\s+ImageCache|await\s+.*\.data\(forKey|await\s+.*\.insert\('
target: { source: file, path: Sources/Demo/Downloader.swift }
---
```

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:swift:)?concurrency"'
---
```

- [ ] **Step 2: Case `mainactor-detached-task`**

`scaffold.sh` writes the same Package.swift plus:

```bash
cat > Sources/Demo/PlayerModel.swift <<'SWIFT'
import Foundation
import Observation

@MainActor
@Observable
final class PlayerModel {
    var score = 0

    func load() {
        Task.detached {
            self.score = await Self.fetchScore()
        }
    }

    static func fetchScore() async -> Int { 42 }
}
SWIFT
```

(Verify before shipping the case: `swiftc -typecheck -swift-version 6 -target arm64-apple-macos14` on the scaffolded file must produce a real Swift 6 isolation diagnostic — if this exact shape compiles clean, adjust it until it doesn't; the case's premise is a genuine error. `@Observable` needs macOS 14; the package platform is 14.)

`prompt.md` body: "Sources/Demo/PlayerModel.swift fails Swift 6 strict concurrency checking inside load(). Fix the isolation error properly — keep load() non-async and keep score updates on the main actor. Do not suppress checking (no nonisolated(unsafe), no @preconcurrency, no @unchecked)." expected_outcome: 'The detached task is replaced with a MainActor-inheriting Task (or an equivalent assumeIsolated form), so the score mutation stays main-actor-isolated.'
Graders: regex `Task\s*\{|MainActor\.assumeIsolated` in PlayerModel.swift; plus the same skill-fired grader.

- [ ] **Step 3: Run and iterate to acceptance**

```bash
claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --threshold 0.67 --max-cost-usd 12 --allow-tools Write Edit --case sendable-shared-cache --case mainactor-detached-task
```

Acceptance (Review Focus 5): each case WITH-arm ≥ 0.67 **and** delta > 0. If a WITHOUT arm passes, strengthen the scaffold's pull toward the wrong fix (e.g. seed a comment hinting at `@unchecked`) or pick a more skill-specific prompt — never weaken a grader or edit expected_outcome to match observed output. Budget: 2–3 iteration runs; if a case can't reach a positive delta after that, report to the user before shipping it.

- [ ] **Step 4: Commit**

```bash
git add plugins/swift/evals
git commit -m "feat(evals): add the concurrency cases sendable-shared-cache and mainactor-detached-task"
```

### Task 11: Full gate battery

- [ ] **Step 1: Run everything**

```bash
python3 -m unittest discover maintenance/tests 2>&1 | tail -1        # OK, new count
python3 maintenance/check-apis.py --strict                            # 0 failures, 0 warnings
claude plugin validate plugins/swift                                  # passed
claude plugin validate .                                              # passed (warnings must be pre-existing only)
python3 .claude/skills/update-docs/scripts/check.py check-docs docs README.md AGENTS.md --captures docs/.onboard-captures --coverage docs/.onboard-coverage.json   # exit 0
python3 .claude/skills/update-rules/scripts/check.py check-instructions .claude/rules .claude/skills --repo-root .                                                  # exit 0
git diff upstream-concurrency-2.3.0 --name-only -- plugins/swift/skills/concurrency   # every file has a Deviations row
```

- [ ] **Step 2: Full eval suite (all cases, old + new)**

```bash
claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --threshold 0.67 --max-cost-usd 30 --json "$TMPDIR/green-014.json" --allow-tools Write Edit
```

Expected: 6 cases pass. Any old-case failure is a regression from the description/surface changes — fix the source, not the grader.

### Task 12: Release 0.1.4

- [ ] **Step 1: Run the `changelog-release` skill** (it stages `plugin.json` 0.1.3→0.1.4 and the CHANGELOG block; feature → z bump per its pre-1.0 rule). Narrative-led block: headline = the new `swift:concurrency` skill (audited fork); Fixed/Changed = machinery + audit findings.

- [ ] **Step 2: Refresh the version-stamped captures into the release commit**

```bash
claude --plugin-dir plugins/swift plugin details swift > "$TMPDIR/pd.raw" 2>&1
python3 .claude/skills/update-docs/scripts/check.py redact "$TMPDIR/pd.raw" --home "$HOME" --user "$USER" --stamp 20260925-114824 > "$TMPDIR/pd.red" && mv "$TMPDIR/pd.red" docs/.onboard-captures/plugin-details.txt
python3 -m unittest discover maintenance/tests 2>&1 | tail -2 > "$TMPDIR/ut.raw"   # follow the existing capture's exact shape; re-capture the same command that produced it
python3 .claude/skills/update-docs/scripts/check.py redact "$TMPDIR/ut.raw" --home "$HOME" --user "$USER" --stamp 20260925-114824 > "$TMPDIR/ut.red" && mv "$TMPDIR/ut.red" docs/.onboard-captures/unit-tests.txt
python3 maintenance/check-apis.py --strict > "$TMPDIR/cas.raw" 2>&1
python3 .claude/skills/update-docs/scripts/check.py redact "$TMPDIR/cas.raw" --home "$HOME" --user "$USER" --stamp 20260925-114824 > "$TMPDIR/cas.red" && mv "$TMPDIR/cas.red" docs/.onboard-captures/check-apis-strict.txt
```

Update the pages that quote them: `enable-in-a-swift-repo.md`'s inventory block becomes `Skills (3)  concurrency, design, swiftui` (match the real output's order and spacing); `work-on-it.md`'s unit-test count line and API-count line. Review each redacted capture for secrets. Run check-docs → exit 0.

- [ ] **Step 3: Commit the release, dry-run, re-capture the tag block, tag**

```bash
git add -A && git commit -m "chore(release): v0.1.4"
claude plugin tag plugins/swift --dry-run | tee "$TMPDIR/td.raw"
```

Redact `td.raw` into `docs/.onboard-captures/tag-dry-run.txt`, update `work-on-it.md`'s "For release 0.1.x" line + `capture=tag-dry-run` block (Version/Tag lines → 0.1.4 / swift--v0.1.4), check-docs → exit 0, `git commit --amend --no-edit -a`, then `claude plugin tag plugins/swift`.

- [ ] **Step 4: Ask the user before pushing** — print, do not run:

```bash
git push origin main
git push origin swift--v0.1.4
```

---

## Self-review record

- **Spec coverage:** §3 → Tasks 1–3 (atomicity: 1–3 land before 4's import); §4 → Tasks 4–8, 10; audit-first ordering enforced (Task 7 before any authored gap-filling — none planned, gaps become Task 8 findings); §7 → Tasks 6, 8.2, 11; §8 surfaces → Tasks 2, 3, 9, 12 (testing/review-specific rows deferred to Plans 2–3 by design); §9 → Task 12; §10 verify-items → Tasks 4.1 (tag/SHA), 5.2 (SKILL_DIR count), 6 (index coverage), 10.3 (threshold semantics re-confirmed on first new case). Spec §4's router cross-reference to `swift:testing` is deliberately deferred to Plan 2 (the target skill doesn't exist yet — a dangling cross-reference would violate the stale-pointer rule).
- **Placeholder scan:** the two conditional steps (Task 5 Step 2 zero-count branch; Task 7→8 zero-findings branch; Task 1 Step 1 note on beta-tag ordering) have explicit both-ways instructions; everything else is concrete.
- **Type/name consistency:** `upstream-concurrency-2.3.0`, `## Concurrency`, `plugins/swift/skills/concurrency`, `/swift:concurrency`, case names `sendable-shared-cache` / `mainactor-detached-task` used identically everywhere.
- **Review Focus:** all five lines are pinned by named tests/steps (see each line's parenthetical).
