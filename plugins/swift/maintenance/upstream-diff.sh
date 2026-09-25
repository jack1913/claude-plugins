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
