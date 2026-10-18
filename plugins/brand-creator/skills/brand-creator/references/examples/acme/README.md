# Acme: a synthetic worked brand

Acme is fictional. It exists to show a brand-creator project after round 1 and to drive the plugin's end-to-end smoke
test (`tests/smoke/acme.sh`), which copies these files into a fresh project and runs every Quick-tier step on them.

| File | What it shows |
|---|---|
| [BRAND-STATE.md](BRAND-STATE.md) | frontmatter after G0-G2, Collaboration block, Directions table with statuses, change list, rules, still open |
| [DECISIONS.md](DECISIONS.md) | dated owner decisions with reasons and rejected alternatives |
| [FACTS.md](FACTS.md) | owner-confirmed facts, the only claims the board copy uses |
| [brief/BRIEF.md](brief/BRIEF.md) | a filled brief: gating goal, architecture, hardest surface, Forbidden |
| [research/positioning-map.md](research/positioning-map.md) | the map's axes, the category norm and where each direction sits |
| [rounds/r1/board.html](rounds/r1/board.html) | the round 1 pick board filled from `templates/round-page.html` (passes `board-lint` and four-view `shot`) |
| `tokens/*.tokens.json` | DTCG 2025.10 sources for the picked direction (oklch with hex fallback, contrast pairs) |
| `assets/logo/mark.svg`, `mark-dark.svg` | the Compass mark, pure vector (generated mark source: triangle and dot, no text) |
| `assets/logo/grid-mark*.svg`, `grid-mark-master.png`, `tools/grid_mark.py` | the coarse-grid small-size drawing (10 x 10 cells, accent a 4 x 4 block) generated from a text grid with `scripts/lib/px_lib.py`; a test rebuilds the files byte for byte |
| `assets/states/*.png`, `tools/state_icons.py`, `qa/states.json` | three 16 px status glyphs (ring, disc, cross) that differ in shape, and the state set `states-check` reads |
| `qa/rules.json` | the project's QA thresholds: the 4 x 4 accent rule and two size bands (small: grid mark up to 32 px, large: the fine vector) |
| `assets/tray-src/*.png`, `tools/tray_masters.py`, `tray/tray.json` | the three status glyphs drawn at 16, 20, 22 and 24 px (a test rebuilds them byte for byte) and the tray config `emit tray` reads: it enlarges a master by a whole factor and never resamples |
| `FACTS.md` (AppStream rows) | the labelled facts `emit linux` copies into the AppStream stub; with no row the field stays empty and is reported |
| `assets/logo/mark-animated.svg`, `motion/demo.html`, `motion/proof.json` | the dot presses two pixels and returns to rest: a named-state file, a demo page and the proof (`shot --motion`) |

How the round went, in the response-template form:

1. **What changed:** round 1 page with three directions (Compass calm, Lantern warm and far from the norm, Keystone
   bold), strategy core, map, hardest surface (16 px tab).
2. **Honest read:** Compass is the steadiest; Lantern is the braver choice; Keystone sits closest to the category norm.
3. **Your call:** 1a Compass (Recommended) / 1b Lantern / 1c Keystone / 1d None of these; 2 strategy core; 3 line.
4. **Still open:** typeface choice; whether the dot moves in motion.

The owner replied "1a 2a 3a, Lantern unsure, Keystone drop". The restatement before building was: "You picked Compass
(board label A); Lantern stays as runner-up for restraint rules; building Compass now."
