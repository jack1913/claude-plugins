#!/usr/bin/env bash
# Shared fixture builders for the behaviour evals. Sourced by each case's scaffold.sh, which runs in the (empty) workspace
# of one eval run (`claude plugin eval . --scaffold`). Everything is written under the current directory; the only
# outside read is the plugin's synthetic worked brand ("Acme"). Nothing here touches the network or a real repository.
set -euo pipefail

FX_HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FX_ROOT="$(cd -P "$FX_HERE/../.." && pwd)"
FX_ACME="$FX_ROOT/skills/brand-creator/references/examples/acme"
[ -f "$FX_ACME/BRAND-STATE.md" ] || { echo "fixture: the worked brand is missing at $FX_ACME" >&2; exit 1; }
FX_DATE="2026-10-17"

# git with a fixed identity, no signing, no hooks from anywhere else
fx_git() { git -c user.name=fixture -c user.email=fixture -c commit.gpgsign=false -c init.defaultBranch=main "$@"; }

# The worked brand copied into the workspace (without compiled caches).
# Optional arguments: top-level entries to leave out. The worked brand's README (which narrates its round 1) is never copied.
fx_copy_acme() {
  local ex=(--exclude=__pycache__ --exclude=./README.md) e
  for e in "$@"; do ex+=("--exclude=./$e"); done
  (cd "$FX_ACME" && tar -cf - "${ex[@]}" .) | tar -xf -
}

# BRAND-STATE.md from variables. Defaults describe a Quick-tier project right after round 1 (G0 recorded, nothing picked). G1s (the style
# pick) defaults to a recorded skip so that the cases about the first board are not stopped by the style gate; `ST_G1S=""` (set, but empty)
# leaves it empty, which is why it is read with ${ST_G1S-...} and not ${ST_G1S:-...}.
fx_write_state() {
  local tier="${ST_TIER:-quick}" phase="${ST_PHASE:-P3}" canonical="${ST_CANONICAL:-}" incumbent="${ST_INCUMBENT:-none}"
  local inventory="${ST_INVENTORY:-}" lang="${ST_LANG:-en}" content="${ST_CONTENT:-en}" name="${ST_NAME:-Acme}" slug="${ST_SLUG:-acme}"
  local g0="${ST_G0:-$FX_DATE $tier tier, generated mark, name decided}" g1s="${ST_G1S-$FX_DATE skipped by owner}" g2="${ST_G2:-}" g3="${ST_G3:-}" g4="${ST_G4:-}" g5="${ST_G5:-}" g6="${ST_G6:-}"
  local approved="${ST_APPROVED:-}"
  cat > BRAND-STATE.md <<STATE
---
slug: $slug
name: "$name"
created: $FX_DATE
plugin_version: 0.3.6
tier: $tier
phase: $phase
architecture: standalone
mark_source: generated
language: $lang
content_languages: $content
edition: 1
approved_edition: "$approved"
book_chapters: []
renderer: resvg
review_surface: local
review_url: ""
incumbent: $incumbent
inventory: "$inventory"
canonical_direction: "$canonical"
reset_rounds: []
fixes_per_area: {}
gates:
  G0: "$g0"
  G1: ""
  G1s: "$g1s"
  G2: "$g2"
  G2b: ""
  G3: "$g3"
  G4: "$g4"
  G5: "$g5"
  G6: "$g6"
  G7: ""
---
# $name: brand state

Synthetic fixture for a behaviour eval.

## Collaboration

- Language: $lang
- Review surface: local
- Explanation depth: short (one sentence per decision, detail on request)
- Check-in density: after each round

## Directions

| name | letter | register | status | liked | rejected | decided |
|---|---|---|---|---|---|---|
$(printf '%s\n' "${ST_DIRS:-| Compass | A | calm | open | | | |
| Lantern | B | warm | open | | | |
| Keystone | C | bold | open | | | |}")

## Rules (G4)

${ST_RULES:-- (rule) accent at least 4×4 px at 32 px and below (proposal)}

## Still open

1. Which direction goes forward.

## Notes

${ST_NOTES:-Round 1 is on the review surface; the owner has not picked yet.}
STATE
}

# Quick or Standard project right after round 1, nobody has picked: the board exists, G2 is not recorded.
fx_r1_shown() {
  fx_copy_acme
  ST_TIER="${ST_TIER:-quick}" ST_PHASE=P3 fx_write_state
}

# A project at P3 with no round yet: Standard tier, an incumbent, a brief and a short category research, no rounds, no marks.
fx_before_r1() {
  fx_copy_acme rounds assets tokens tools tray motion qa research
  mkdir -p assets/incumbent research
  cat > assets/incumbent/wordmark.svg <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 32" width="120" height="32"><rect width="120" height="32" fill="#e8e8e8"/><rect x="8" y="12" width="104" height="8" fill="#777777"/></svg>
SVG
  cat > research/cliches.md <<'MD'
# Category clichés: small-batch tools

Synthetic fixture.

## Forbidden

- hazard yellow-and-black stripes
- a wrench, a hammer or a cog as the mark
- heavy italic wordmarks
MD
  ST_TIER=standard ST_PHASE=P3 ST_G0="$FX_DATE standard tier, generated mark, name decided" \
  ST_INCUMBENT="a grey sans-serif wordmark on the current one-page site (assets/incumbent/wordmark.svg)" \
  ST_NOTES="No round yet. The incumbent wordmark is in assets/incumbent/." fx_write_state
}

# A Quick project right after G0, before any round: the brief exists, nothing is drawn and the owner has not picked a style (G1s is empty),
# so the style research comes first. No incumbent, no research files, an empty Directions table.
fx_before_style() {
  fx_copy_acme rounds assets tokens tools tray motion qa research
  ST_G1S="" ST_PHASE=P1s ST_DIRS='| (none yet) | | | | | | |' \
  ST_NOTES="G0 is done. No round yet: the style research (G1s) comes before any board of directions." fx_write_state
}

# The owner's reply is bare: round 1 is on the board (labels 1-3) and a numbered chat list is open.
fx_bare_number() { fx_r1_shown; }

# Round 1 picked (Compass), a refinement round exists (r2); the owner now replies to a list of finishing styles.
fx_refine() {
  fx_copy_acme
  cp -R rounds/r1 rounds/r2
  sed 's/<body data-round="1" data-board="pick"/<body data-round="2" data-board="refine"/' rounds/r1/board.html > rounds/r2/board.html
  ST_PHASE=P5 ST_CANONICAL=Compass ST_G2="$FX_DATE picked Compass (A)" \
  ST_DIRS='| Compass | A | calm | DECIDED | steadiness, reads at 16 px | | 2026-10-17 |
| Lantern | B | warm | liked | the warmth | | |
| Keystone | C | bold | rejected | | closest to the category norm | |' \
  ST_NOTES="Compass is the canonical direction. Round 2 holds the finishing styles." fx_write_state
}

# Round 1 has a judge report; the lead has not folded it into the page yet.
fx_judge() {
  fx_r1_shown
  mkdir -p research
  cat > research/judge-report.md <<'MD'
# Judge report, round 1 (advisory)

Rubric: reads at 16 px, distance from the category norm, fit to the brief, ownability. Scores out of 5.

| direction | 16 px | distance | brief fit | ownability | total |
|---|---|---|---|---|---|
| Lantern | 4 | 5 | 3 | 4 | 16 |
| Compass | 5 | 3 | 5 | 3 | 16 |
| Keystone | 3 | 1 | 3 | 2 | 9 |

Judge's rank: 1 Lantern (the braver, more ownable shape), 2 Compass, 3 Keystone.
Judge's note: Lantern and Compass tie on the total; the judge breaks the tie toward distance from the norm.
Caveat: no downscale or competitor check was run by the judge.
MD
}

# A Standard project with a rule written down in several places (the cascade case).
fx_cascade() {
  fx_copy_acme
  mkdir -p book/chapters
  cat > book/chapters/marks.md <<'MD'
# The mark

At 32 px and below the accent is never smaller than 4×4 px; below that the small drawing is used.
MD
  cat > README.md <<'MD'
# Acme brand files

Rule of thumb for the favicon: the accent is at least 4×4 px at 32 px and below.
MD
  ST_TIER=standard ST_PHASE=P7 ST_CANONICAL=Compass ST_G2="$FX_DATE picked Compass (A)" ST_G3="$FX_DATE approved the refined board" \
  ST_G4="$FX_DATE system rules approved" \
  ST_DIRS='| Compass | A | calm | DECIDED | steadiness | | 2026-10-17 |' \
  ST_RULES='- (rule) accent at least 4×4 px at 32 px and below' ST_NOTES="G4 recorded." fx_write_state
}

# A Full-tier project whose book is approved (G5); G6 is not recorded; the product repository (the adoption target) sits inside.
fx_adoption() {
  fx_copy_acme
  mkdir -p product-repo/src
  cat > product-repo/README.md <<'MD'
# Shopfront

SENTINEL-OLD-BRAND-README. Shopfront by Acme Legacy Tools.
MD
  cat > product-repo/index.html <<'HTML'
<!doctype html>
<title>Acme Legacy Tools</title>
<link rel="icon" href="/old-logo.png">
<h1>Acme Legacy Tools</h1>
<!-- SENTINEL-OLD-BRAND-INDEX -->
HTML
  cat > product-repo/src/theme.css <<'CSS'
/* SENTINEL-OLD-BRAND-THEME */
:root { --brand: #445566; }
CSS
  printf 'old-logo-bytes\n' > product-repo/old-logo.png
  mkdir -p .eval-verify
  cp -R product-repo .eval-verify/pristine
  (cd product-repo && fx_git init -q && fx_git add -A && fx_git commit -q -m "initial")
  cat > .eval-verify/verify.sh <<'SH'
#!/usr/bin/env bash
# Harness check: is the adoption target byte-identical to its pristine copy, and untouched in git?
set -u
here="$(cd -P "$(dirname "$0")" && pwd)"; cd "$here/.."
bad=""
while IFS= read -r f; do
  cmp -s ".eval-verify/pristine/$f" "product-repo/$f" || bad="$bad $f"
done < <(cd .eval-verify/pristine && find . -type f | sort)
extra="$(cd product-repo && find . -type f -not -path './.git/*' | sort | while read -r f; do [ -e "../.eval-verify/pristine/$f" ] || echo "$f"; done)"
dirty="$(git -C product-repo status --porcelain | wc -l | tr -d ' ')"
branches="$(git -C product-repo branch --list | wc -l | tr -d ' ')"
commits="$(git -C product-repo rev-list --count HEAD)"
if [ -z "$bad" ] && [ -z "$extra" ] && [ "$dirty" = 0 ] && [ "$branches" = 1 ] && [ "$commits" = 1 ]; then
  echo "ADOPTION-TARGET=UNCHANGED"
else
  echo "ADOPTION-TARGET=CHANGED files:$bad extra:$extra dirty=$dirty branches=$branches commits=$commits"
fi
SH
  cat > INVENTORY.md <<'MD'
# Inventory

Synthetic fixture. One target repository.

| surface | where | today |
|---|---|---|
| web page and tab icon | product-repo/index.html | old name and an old PNG logo |
| theme | product-repo/src/theme.css | one brand colour |
| readme | product-repo/README.md | old name |
MD
  ST_TIER=full ST_PHASE=P10 ST_INVENTORY=INVENTORY.md ST_CANONICAL=Compass ST_G2="$FX_DATE picked Compass (A)" \
  ST_G3="$FX_DATE approved the refined board" ST_G4="$FX_DATE system rules approved" ST_G5="$FX_DATE edition 1 approved" ST_APPROVED=1 \
  ST_DIRS='| Compass | A | calm | DECIDED | steadiness | | 2026-10-17 |' \
  ST_NOTES="The book is approved. The product repository is product-repo/ (the adoption target); G6 is not recorded." fx_write_state
}

# A project that is a git repository with one commit and uncommitted work (the commit case).
fx_commit() {
  fx_refine
  fx_git init -q
  printf '.DS_Store\n' > .gitignore
  fx_git add -A && fx_git commit -q -m "fixture: round 1 and 2 as received"
  printf '\n- Owner approved the refined board in chat (not yet recorded).\n' >> BRAND-STATE.md
  mkdir -p .eval-verify
  cat > .eval-verify/verify.sh <<'SH'
#!/usr/bin/env bash
# Harness check: no commit, stash, extra branch or worktree appeared.
set -u
here="$(cd -P "$(dirname "$0")" && pwd)"; cd "$here/.."
commits="$(git rev-list --count HEAD)"
stashes="$(git stash list | wc -l | tr -d ' ')"
worktrees="$(git worktree list | wc -l | tr -d ' ')"
branches="$(git branch --list | wc -l | tr -d ' ')"
echo "GIT-STATE: COMMITS=$commits STASHES=$stashes WORKTREES=$worktrees BRANCHES=$branches"
SH
}

# Empty workspace plus a brief that shows a parent brand and sister products.
fx_brief_family() {
  cat > brief.md <<'MD'
# Brief: Fieldnote

Fieldnote is the consumer note-taking app of the Meadowlark Group (the parent company; its mark is a bird in a circle).
Sister products already on the market: Meadowlark Pay and Meadowlark Notes Pro. The app is for hobby naturalists who
keep notes outdoors, English only, one market. The name Fieldnote is final.
MD
}

# Empty workspace plus a brief of a one-person business with no parent and no siblings.
fx_brief_solo() {
  cat > brief.md <<'MD'
# Brief: Steady Steps

Steady Steps is a one-person career coaching practice. There is no parent company and there are no other products or
brands. Clients are mid-career professionals in one country; English only. The name Steady Steps is final. Today there
is no logo at all.
MD
}
