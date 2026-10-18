#!/usr/bin/env bash
# finish.sh: the ordered chain that rebuilds every generated pack of this brand and proves it. Copy to <project>/tools/finish.sh
# (phase P8) and edit the three marked blocks. One command regenerates everything, in this order, and stops at the first failure:
#
#   1 the project's own generators (tools/*.py built with scripts/lib/px_lib.py)
#   2 tokens, contrast
#   3 the emitters for the targets this brand has (apple needs macOS with Xcode)
#   4 the gates (downscale on every master a manifest row names, states-check)
#   5 verify-idempotent: the whole emit chain run twice must give byte-identical files
#   6 staleness --write (records the inputs, the plugin version and the emitter code the pack was built from), then check
#
# The chain sets BRAND_CREATOR_CHAIN=1. A generator that clears or rewrites a whole output folder calls
# `require_chain()` (scripts/lib/_common.py) and refuses to run without it: run alone it would wipe files that later steps refill.
# Needs the plugin's bin/ on PATH (Claude Code does that) and BRAND_CREATOR_DATA or CLAUDE_PLUGIN_DATA set.
# Option values live in the variables of block 2 (an environment variable of the same name overrides them), and reach each emitter
# as separate, quoted arguments: a tagline or an exemption with spaces in it is one argument, here and in the idempotence run.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export BRAND_CREATOR_CHAIN=1
DATA="${BRAND_CREATOR_DATA:-${CLAUDE_PLUGIN_DATA:-}}"
[ -n "$DATA" ] || { echo "finish.sh: set BRAND_CREATOR_DATA (or CLAUDE_PLUGIN_DATA) to the data directory" >&2; exit 2; }
BC=(brand-creator --data "$DATA")
BRAND_CREATOR_ROOT="$("${BC[@]}" root)"; export BRAND_CREATOR_ROOT      # the generators of block 1 import scripts/lib from here
step() { printf '\n== %s\n' "$*"; }

# ---- block 1: the project's own generators (one line each; delete what the brand does not have)
GENERATORS=(
  # tools/grid_mark.py
  # tools/state_icons.py
)

# ---- block 2: the targets this brand ships to, and the options of each emitter
TARGETS=(web social windows linux tray tauri wallet developer)
[ "$(uname)" = Darwin ] && TARGETS+=(apple)     # apple is macOS only; on other systems list it in the release notes as "built on a Mac"
TAGLINE="${TAGLINE:-}"          # one line of copy: it must be a value in FACTS.md (social, developer, apple); empty = no line
APP_ID="${APP_ID:-}"            # reverse-DNS app id for emit linux (AppStream); empty = the metainfo stays a stub
MASTER_BAND="${MASTER_BAND:-}"  # band of the master a system shrinks (apple, developer), for example small; empty = the rule's pick
EXEMPTION="${EXEMPTION:-}"      # one line: why MASTER_BAND differs from the band rule's pick (required then, recorded in the manifest)
ICON_CONTENT="${ICON_CONTENT:-}"         # --content-fraction of apple and developer: the share of the master the mark fills. The default can leave the
VISIONOS_CONTENT="${VISIONOS_CONTENT:-}" # 16 px accent under the 4 x 4 rule: read the downscale gate below, then set it (apple: --visionos-content-fraction)
EMIT_ARGS=()
emit_args() {                   # sets EMIT_ARGS (an array, so every value stays one argument) for target $1
  EMIT_ARGS=()
  case "$1" in
    social)    [ -z "$TAGLINE" ] || EMIT_ARGS+=(--tagline "$TAGLINE") ;;
    linux)     [ -z "$APP_ID" ] || EMIT_ARGS+=(--app-id "$APP_ID") ;;
    apple|developer)
      [ -z "$TAGLINE" ] || EMIT_ARGS+=(--tagline "$TAGLINE")
      [ -z "$MASTER_BAND" ] || EMIT_ARGS+=(--master-band "$MASTER_BAND")
      [ -z "$EXEMPTION" ] || EMIT_ARGS+=(--exemption "$EXEMPTION") ;;
  esac
  if [ "$1" = apple ] || [ "$1" = developer ]; then
    [ -z "$ICON_CONTENT" ] || EMIT_ARGS+=(--content-fraction "$ICON_CONTENT")
  fi
  if [ "$1" = apple ]; then
    [ -z "$VISIONOS_CONTENT" ] || EMIT_ARGS+=(--visionos-content-fraction "$VISIONOS_CONTENT")
  fi
  return 0
}

step "plugin version: $("${BC[@]}" version)"
for g in ${GENERATORS[@]+"${GENERATORS[@]}"}; do step "generator $g"; python3 "$g"; done
step "tokens";   "${BC[@]}" tokens
step "contrast"; "${BC[@]}" contrast

cmds=()
for t in "${TARGETS[@]}"; do
  step "emit $t"
  emit_args "$t"
  "${BC[@]}" emit "$t" ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}
  # the idempotence run takes each command as one shell-quoted string: printf %q keeps every argument whole
  q=""; for w in "$t" --project '{project}' ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}; do q+="$(printf '%q ' "$w")"; done
  cmds+=(--cmd "{bc} emit $q")
done

# ---- block 3: the gates. Every master a manifest row asks to be downscale-checked (`downscale_source`) needs its own passing
# report; `check` ties each row to the report of its own master, so one passing file cannot vouch for another.
step "gates"
SOURCES="$(python3 -c '
import json
doc = json.load(open("assets/manifest.json"))
print("\n".join(sorted({a.get("downscale_source") or a["path"] for a in doc.get("artefacts", []) if "downscale" in a.get("qa", [])})))
')"
while IFS= read -r src; do
  [ -z "$src" ] || { step "downscale $src"; "${BC[@]}" downscale --source "$src"; }
done <<< "$SOURCES"
[ -f qa/states.json ] && "${BC[@]}" states-check
"${BC[@]}" verify-idempotent "${cmds[@]}"
"${BC[@]}" staleness --write
"${BC[@]}" check
