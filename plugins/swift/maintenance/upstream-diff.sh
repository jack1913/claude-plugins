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
# ('### Deviations' does not end the range — its third character is '#', not ' '.)
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
