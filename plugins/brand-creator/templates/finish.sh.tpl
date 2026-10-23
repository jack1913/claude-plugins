#!/usr/bin/env bash
# finish.sh: the ordered chain that rebuilds every generated pack of this brand and proves it. Copy to <project>/tools/finish.sh
# (phase P8) and edit the three marked blocks. One command regenerates everything, in this order, and stops at the first failure:
#
#   1 the project's own generators (tools/*.py built with scripts/lib/px_lib.py)
#   2 tokens, contrast
#   3 the emitters for the targets this brand has (apple needs macOS with Xcode; android, chrome-ext and msix need the Full tier; profiles, print and
#     the social posts need Standard or Full), then print-check when print was emitted. With several marks (qa/rules.json marks) each emitter runs
#     once per mark (--mark <id>), and emit social once more without --mark for the images that show every mark side by side
#   4 the gates (downscale on every master a manifest row names, states-check). Off macOS there is no sips and no iconutil: set ICNS_RENDERER=pillow
#     (emit tauri) and DOWNSCALE_RENDERER=pillow or resvg (the downscale gates) in block 2, the explicit opt-ins; without them those two steps exit 3
#   5 verify-idempotent: the whole emit chain run twice must give byte-identical files
#   6 the brand book when book/chapters/ exists (frames first, Standard and Full, when the brand moves: motion/motion.json says on and motion/proof.json has a page case,
#     so that the Motion chapter replays fresh stills, with FRAMES_ARGS of block 2; a failure that writes a failing report (exit 1) does not stop the chain, exit 2 or 3 does; then book, book-pdf: they read the reports of steps 4
#     and 5), then the press kit (Standard and Full): the kit holds book.pdf
#   7 staleness --write (records the inputs, the plugin version and the emitter code the pack was built from), then check
#
# The chain sets BRAND_CREATOR_CHAIN=1. A generator that clears or rewrites a whole output folder calls
# `require_chain()` (scripts/lib/_common.py) and refuses to run without it: run alone it would wipe files that later steps refill.
# Needs the plugin's bin/ on PATH (Claude Code does that) and BRAND_CREATOR_DATA or CLAUDE_PLUGIN_DATA set.
# Option values live in the variables of block 2 (an environment variable of the same name overrides them), and reach each emitter
# as separate, quoted arguments: a tagline or an exemption with spaces in it is one argument, here and in the idempotence run.
# The print, press-kit and post steps follow the CLI's own tiers: `emit print` (and the e-mail signature), `emit presskit` and `emit social --posts` are Standard and Full tier;
# print is also opt-in (the owner decides): it runs only when PRINT_REGION is set. A value set for a step the tier does not allow stops the chain (exit 2)
# instead of being ignored. The chain never writes or fills book/chapters/: no folder, no book step, and the log says so.
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
[ "$("${BC[@]}" state --get tier)" = full ] && TARGETS+=(android chrome-ext msix)   # Tier B packs are Full tier only; delete the ones this brand does not ship to
TIER="$("${BC[@]}" state --get tier)"
TARGETS+=(profiles)   # every tier: Quick writes the avatar only; Standard and Full add the banners and the Instagram images
PRINT_REGION="${PRINT_REGION:-}"  # EU, US or JP: print stationery is opt-in with the owner (ask before the packs); empty = not opted in, nothing is printed
PRINT_ICC="${PRINT_ICC:-}"        # YOUR printer's CMYK profile (.icc): with it the PDFs are "PDF/X-4 candidate", without it "RGB proof, not print-ready"
PRINT_BLEED="${PRINT_BLEED:-}"    # bleed in mm; empty = the region's default (printer-specific: ask your printer)
IMAGE_BASE_URL="${IMAGE_BASE_URL:-}"   # https URL where the e-mail signature's PNGs will be hosted (print); empty = a placeholder, warned
FRAMES_ARGS="${FRAMES_ARGS:---count 25}"   # the stills of the Motion chapter (Standard and Full, when the brand moves): --count N or --at 0,25,50,75,100; a wide mark may need fewer (frames says how many fit)
POST_FACTS="${POST_FACTS:-}"      # labels of FACTS.md rows, one per post line, separated by semicolons, for example "spare parts;repair guide"; empty = no social posts
POST_LABELS=(); [ -z "$POST_FACTS" ] || IFS=';' read -r -a POST_LABELS <<< "$POST_FACTS"
case "$TIER" in
  standard|full) [ -z "$PRINT_REGION" ] || TARGETS+=(print) ;;
  *) [ -z "$PRINT_REGION" ] && [ -z "$POST_FACTS" ] || { echo "finish.sh: print and social posts are Standard and Full tier; this project's tier is '$TIER'. Raise it with the owner's agreement: brand-creator state --set tier=standard" >&2; exit 2; } ;;
esac
ICNS_RENDERER="${ICNS_RENDERER:-}"           # off macOS: pillow, the explicit opt-in for the Tauri .icns (no iconutil there; no 16 px entry). Empty on macOS.
DOWNSCALE_RENDERER="${DOWNSCALE_RENDERER:-}" # off macOS: pillow (PNG masters) or resvg (SVG masters), the explicit opt-in for the downscale gates (no sips there). Empty on macOS.
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
    social)    [ -z "$TAGLINE" ] || EMIT_ARGS+=(--tagline "$TAGLINE")
               if [ ${#POST_LABELS[@]} -gt 0 ]; then EMIT_ARGS+=(--posts); for f in "${POST_LABELS[@]}"; do EMIT_ARGS+=(--post-fact "$f"); done; fi ;;
    profiles)  [ -z "$TAGLINE" ] || EMIT_ARGS+=(--tagline "$TAGLINE") ;;
    print)     EMIT_ARGS+=(--region "$PRINT_REGION")
               [ -z "$TAGLINE" ] || EMIT_ARGS+=(--tagline "$TAGLINE")
               [ -z "$PRINT_BLEED" ] || EMIT_ARGS+=(--bleed "$PRINT_BLEED")
               [ -z "$PRINT_ICC" ] || EMIT_ARGS+=(--icc "$PRINT_ICC")
               [ -z "$IMAGE_BASE_URL" ] || EMIT_ARGS+=(--image-base-url "$IMAGE_BASE_URL") ;;
    linux)     [ -z "$APP_ID" ] || EMIT_ARGS+=(--app-id "$APP_ID") ;;
    tauri)     [ -z "$ICNS_RENDERER" ] || EMIT_ARGS+=(--renderer "$ICNS_RENDERER") ;;
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

# a session that still runs an older copy of the plugin than the one installed stops here (start a new session); a checkout says "not checked"
step "plugin version"; "${BC[@]}" version --check
for g in ${GENERATORS[@]+"${GENERATORS[@]}"}; do step "generator $g"; python3 "$g"; done
step "tokens";   "${BC[@]}" tokens
# a project whose qa/rules.json sets a colour-vision threshold (cvd) keeps its colour-vision rows: without --cvd the report would lose them, and check
# says so ("not verified")
CONTRAST_ARGS=()
python3 -c 'import json, os, sys; sys.exit(0 if os.path.isfile("qa/rules.json") and json.load(open("qa/rules.json")).get("cvd") else 1)' && CONTRAST_ARGS+=(--cvd)
step "contrast ${CONTRAST_ARGS[*]-}"; "${BC[@]}" contrast ${CONTRAST_ARGS[@]+"${CONTRAST_ARGS[@]}"}

# the marks of a project with several of them (qa/rules.json marks), in the file's order; none for a one-mark project
MARKS=()
while IFS= read -r m; do [ -z "$m" ] || MARKS+=("$m"); done <<< "$(python3 -c '
import json, os
print("\n".join(json.load(open("qa/rules.json")).get("marks", {}) if os.path.isfile("qa/rules.json") else []))
')"

cmds=()
emit_run() {   # emit_run <target> [<mark>]: run it, and add it to the idempotence run
  local t="$1" m="${2:-}"
  step "emit $t${m:+ --mark $m}"
  emit_args "$t"
  [ -z "$m" ] || EMIT_ARGS+=(--mark "$m")
  "${BC[@]}" emit "$t" ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}
  # the idempotence run takes each command as one shell-quoted string: printf %q keeps every argument whole
  local q="" w; for w in "$t" --project '{project}' ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}; do q+="$(printf '%q ' "$w")"; done
  cmds+=(--cmd "{bc} emit $q")
}
emit_one() {   # emit_one <target>: once, or once per mark (and emit social once more without one: every mark side by side)
  local t="$1" m
  if [ ${#MARKS[@]} -eq 0 ]; then emit_run "$t"; return; fi
  for m in "${MARKS[@]}"; do emit_run "$t" "$m"; done
  [ "$t" != social ] || emit_run social
}
for t in "${TARGETS[@]}"; do emit_one "$t"; done
case " ${TARGETS[*]} " in *" print "*) step "print-check"; "${BC[@]}" print-check ${PRINT_ICC:+--icc "$PRINT_ICC"} ;; esac

# ---- block 3: the gates. Every master a manifest row asks to be downscale-checked (`downscale_source`) needs its own passing
# report; `check` ties each row to the report of its own master, so one passing file cannot vouch for another.
step "gates"
SOURCES="$(python3 -c '
import json
doc = json.load(open("assets/manifest.json"))
print("\n".join(sorted({a.get("downscale_source") or a["path"] for a in doc.get("artefacts", []) if "downscale" in a.get("qa", [])})))
')"
while IFS= read -r src; do
  [ -z "$src" ] || { step "downscale $src"; "${BC[@]}" downscale --source "$src" ${DOWNSCALE_RENDERER:+--renderer "$DOWNSCALE_RENDERER"}; }
done <<< "$SOURCES"
[ -f qa/states.json ] && "${BC[@]}" states-check
"${BC[@]}" verify-idempotent "${cmds[@]}"
# ---- block 4: the brand book and the press kit. They come after the gates because the book reads the downscale and idempotence reports (a book built before
# them is stale the moment they are rewritten), and the kit holds book.pdf, so it follows the book (the book's file list leaves the kit out).
# The kit is deterministic (tested with `emit presskit` run twice); it is not in the idempotence run, which has to finish before the book is built.
HAVE_BOOK=no
if [ -d book/chapters ]; then
  # a brand that moves has stills of its motion in the book (the Motion chapter, Standard and Full tier, replays them): take them again first, so that they are the page as it is
  # now. `frames` writes only motion/frames/ (and its report); a rerun with nothing changed writes nothing. A page it cannot step through (motion driven by requestAnimationFrame,
  # a scroll timeline) exits 1 and writes a failing report: that is said and the chain goes on, the book keeps the stills of the last run that worked, if any, and `check` fails
  # the report and says why. Any other non-zero exit (2: a strip too wide, a case folder that holds another proof's stills; 3: it could not run) leaves no failing report for `check` to gate: the chain stops with that exit code
  case "$TIER" in
    standard|full)
      if python3 -c 'import json, sys; ok = json.load(open("motion/motion.json")).get("motion") == "on" and any(c.get("type") == "page" for c in json.load(open("motion/proof.json")).get("cases", [])); sys.exit(0 if ok else 1)' 2>/dev/null; then
        read -r -a FRAMES_OPTS <<< "$FRAMES_ARGS"
        step "frames motion/proof.json $FRAMES_ARGS"
        rc=0; "${BC[@]}" frames motion/proof.json "${FRAMES_OPTS[@]}" || rc=$?
        if [ "$rc" -eq 1 ]; then echo "finish.sh: frames could not take the stills (see above); the book keeps the stills of the last run that worked, if any, and check says why" >&2
        elif [ "$rc" -ne 0 ]; then echo "finish.sh: frames stopped with exit $rc (see above); check has no failing report to gate, so the chain stops here (the number of stills is FRAMES_ARGS in block 2)" >&2; exit "$rc"; fi
      fi ;;
  esac
  step "book";     "${BC[@]}" book
  step "book-pdf"; "${BC[@]}" book-pdf
  HAVE_BOOK=yes
else
  step "book: skipped (no book/chapters/: start one with brand-creator book --init and fill it)"
fi
case "$TIER" in
  standard|full)
    EMIT_ARGS=(); [ "$HAVE_BOOK" = yes ] || EMIT_ARGS+=(--no-book)
    if [ ${#MARKS[@]} -eq 0 ]; then
      step "emit presskit"
      "${BC[@]}" emit presskit ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}
    else
      for m in "${MARKS[@]}"; do step "emit presskit --mark $m"; "${BC[@]}" emit presskit --mark "$m" ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}; done
    fi ;;
esac
"${BC[@]}" staleness --write
"${BC[@]}" check
