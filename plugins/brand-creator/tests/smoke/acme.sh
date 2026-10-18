#!/usr/bin/env bash
# Acme smoke test: the whole Quick-tier path on a synthetic brand, end to end. Exits non-zero on any failure.
#
#   BRAND_CREATOR_DATA=<set-up data dir> tests/smoke/acme.sh
#   brand-creator --data <dir> smoke
#
# new -> r1 round page -> tokens -> mark SVG -> contrast -> logo sheet -> emit web -> emit social -> 4-view shots
# -> board-lint -> QA and mark tooling (px_lib marks, outlined wordmark, downscale, states, colour-vision, guides, fonts, motion)
# -> platform packs (windows, linux, tray, tauri, wallet, developer; on macOS also apple: .icon, actool per platform, legacy sets, visionOS,
# DMG, store frames, watchOS and tvOS packs for the targets INVENTORY.md lists; elsewhere `emit apple` must exit 3) -> Tier B packs (tier raised to full: android, chrome-ext, msix,
# profiles; the safe-zone gates on mutated marks and an overflowing name) -> snapshot, idempotence over the whole emit chain, staleness, specs -> check -> freeze -> check again -> guard hook on the frozen history.
# -> brand book (generated: skeletons, build, lint, byte-identical rebuild, check, labelled RGB PDF; six mutations; patch and collapse on a hand-authored copy)
# -> print and press (print PDFs trim + 2 x bleed, boxes, outlined text, RGB proof label, print-check with four mutations, a PDF/X-4 candidate only with --icc, press kit, social posts)
# -> adoption (a synthetic target repository surveyed read only, pins, progress), check --cascade, BRAND.md and DESIGN.md (linted), the applied skill, LAUNCH.md
# -> names (offline replay) -> brand-assets standalone entry (existing mark into ./brand-assets/: srgb tokens, audit, owner decisions, web +
# windows packs, check) -> fleets (fleet-plan dry runs of the opt-in workflows, the designers' snapshot guard; no model is called)
# -> evals (every behaviour case's scaffold builds a valid fixture project; the real `claude plugin eval` loader accepts every case; nothing is run or billed).
# The r1 page is the worked example filled from templates/round-page.html (three directions). A previous smoke folder
# is moved aside (to <parent>/removed/), never deleted.
set -euo pipefail

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -P "$HERE/../.." && pwd)"
FIX="$ROOT/skills/brand-creator/references/examples/acme"   # the synthetic worked brand
: "${BRAND_CREATOR_DATA:?set BRAND_CREATOR_DATA to a data directory prepared by: brand-creator --data <dir> setup --yes}"
BC=("$ROOT/bin/brand-creator" --data "$BRAND_CREATOR_DATA")
SMOKE="${ACME_SMOKE_DIR:-${TMPDIR:-/tmp}/brand-creator-acme-smoke}"
export BRAND_CREATOR_TODAY="${BRAND_CREATOR_TODAY:-2026-10-17}"

step() { printf '\n== %s\n' "$*"; }
ok()   { printf '   ok: %s\n' "$*"; }
die()  { printf 'SMOKE FAILED: %s\n' "$*" >&2; exit 1; }
png_size() { python3 -c "import struct,sys;d=open(sys.argv[1],'rb').read(24);assert d[:8]==b'\x89PNG\r\n\x1a\n';print(*struct.unpack('>II',d[16:24]))" "$1"; }
expect_size() { local got; got="$(png_size "$1")"; [ "$got" = "$2 $3" ] || die "$1 is $got, expected $2 $3"; ok "$(basename "$1") is $2x$3"; }
expect_file() { [ -s "$1" ] || die "missing or empty: $1"; ok "$1"; }

step "tools"
"${BC[@]}" prereq --for quick >/dev/null || die "prerequisites are missing (run: brand-creator prereq --for quick)"
ok "prereq --for quick"

step "scaffold Acme in $SMOKE"
if [ -e "$SMOKE" ]; then
  mkdir -p "$(dirname "$SMOKE")/removed"
  mv "$SMOKE" "$(dirname "$SMOKE")/removed/$(basename "$SMOKE")-$(date +%Y%m%d%H%M%S)-$$"
  ok "previous run moved aside"
fi
mkdir -p "$SMOKE"
"${BC[@]}" new acme --name Acme --tier quick --root "$SMOKE" >/dev/null
P="$SMOKE/acme"
expect_file "$P/BRAND-STATE.md"; expect_file "$P/FACTS.md"; expect_file "$P/brief/BRIEF.md"
"${BC[@]}" state --project "$P" --record G0 "quick tier, generated mark" >/dev/null

step "r1 round page (from templates/round-page.html), token sources and the mark"
mkdir -p "$P/rounds/r1" "$P/tokens" "$P/assets/logo"
cp "$FIX/rounds/r1/board.html" "$P/rounds/r1/board.html"
cp "$FIX"/tokens/*.tokens.json "$P/tokens/"
cp "$FIX"/tokens/exceptions.json "$P/tokens/"
cp "$FIX"/assets/logo/*.svg "$P/assets/logo/"
"${BC[@]}" state --project "$P" --record G2 "picked Compass" >/dev/null
"${BC[@]}" state --project "$P" --record G3 "approved r1 (smoke)" >/dev/null

step "tokens: DTCG sources to css, json, swift, android, colorsets"
"${BC[@]}" tokens --project "$P"
for f in tokens.css tokens.json swift/BrandColors.swift android/values/colors.xml android/values-night/colors.xml Colors.xcassets/Contents.json; do
  expect_file "$P/assets/tokens/$f"
done
"${BC[@]}" tokens --project "$P" --check >/dev/null || die "tokens output is stale right after a build"

step "contrast (WCAG 2.2 AA, brand rules, touching pairs found in the logo raster, APCA advisory)"
"${BC[@]}" contrast --project "$P"
expect_file "$P/assets/_checks/contrast.json"
python3 - "$P/assets/_checks/contrast.json" <<'PY' || die "contrast.json has no touching pairs (the raster check did not run)"
import json, sys
rows = [r for r in json.load(open(sys.argv[1]))["results"] if r.get("section") == "touching-pairs"]
ids = {r["id"] for r in rows}
assert {"touch:light:mark:#0d1b2d|ground", "touch:dark:mark:#f0eee7|ground"} <= ids, ids
assert any(r["status"] == "warn" and r.get("exception") for r in rows), "the recorded exception was not applied"
print(f"   touching pairs found in the raster: {len(rows)}")
PY
ok "touching pairs enumerated from the raster; the accepted exception carries its reason"

step "logo sheet"
"${BC[@]}" logo-sheet --project "$P"
expect_file "$P/assets/_checks/logo-sheet.png"

step "emit web"
"${BC[@]}" emit web --project "$P"
expect_size "$P/assets/web/apple-touch-icon.png" 180 180
expect_size "$P/assets/web/icons/icon-192.png" 192 192
expect_size "$P/assets/web/icons/icon-512.png" 512 512
expect_size "$P/assets/web/icons/maskable-512.png" 512 512
expect_file "$P/assets/web/favicon.ico"; expect_file "$P/assets/web/icon.svg"; expect_file "$P/assets/web/site.webmanifest"; expect_file "$P/assets/web/head.html"
grep -q '<link rel="icon" href="/favicon.ico"' "$P/assets/web/head.html" || die "head.html does not reference the stable /favicon.ico"
step "emit web again: nothing may change"
"${BC[@]}" emit web --project "$P" | grep -q "0 written" || die "second emit web wrote files"

step "emit social"
"${BC[@]}" emit social --project "$P" --tagline "Dependable small-batch tools"
expect_size "$P/assets/social/github-social-1280x640.png" 1280 640
OG="$(ls "$P"/assets/social/og-1200x630-*.png | head -n 1)"
expect_size "$OG" 1200 630
expect_size "$P/assets/social/readme-header-light.png" 1280 320
expect_size "$P/assets/social/readme-header-dark.png" 1280 320

step "board lint and four-view shots"
"${BC[@]}" board-lint rounds/r1/board.html --project "$P"
"${BC[@]}" shot rounds/r1/board.html --project "$P"
python3 - "$P/assets/_checks/shot.json" <<'PY'
import json, sys
rep = json.load(open(sys.argv[1]))
assert rep["status"] == "pass", rep["status"]
assert [r["id"] for r in rep["results"]] == ["view:1440-light", "view:1440-dark", "view:390-light", "view:390-dark"]
for r in rep["results"]:
    assert r["slices"], r["id"]
print("   ok: 4 views, slices written")
PY

step "mark tooling: the grid mark and the status glyphs are rebuilt byte for byte by the example's own px_lib tools"
mkdir -p "$P/tools" "$P/qa" "$P/motion" "$P/assets/states"
cp "$FIX"/tools/*.py "$P/tools/"; cp "$FIX"/qa/*.json "$P/qa/"; cp "$FIX"/motion/* "$P/motion/"
( cd "$P" && BRAND_CREATOR_ROOT="$ROOT" python3 tools/grid_mark.py >/dev/null && BRAND_CREATOR_ROOT="$ROOT" python3 tools/state_icons.py >/dev/null ) || die "the px_lib tools failed"
for f in assets/logo/grid-mark.svg assets/logo/grid-mark-dark.svg assets/logo/grid-mark-master.png assets/states/idle.png assets/states/active.png assets/states/error.png; do
  cmp -s "$P/$f" "$FIX/$f" || die "$f is not byte-identical to the example's committed file (px_lib output changed)"
done
ok "grid mark, master and three status glyphs rebuilt identically"

step "outline-glyphs: a wordmark with no live text, then the guide overlay measures its baseline, cap line and x-height"
FONT="$ROOT/tests/fixtures/fonts/TestFont-subset.ttf"
"${BC[@]}" outline-glyphs --font "$FONT" --text "Acme" --axis wght=700 --fill "#0d1b2d" --out assets/logo/wordmark-outlined.svg --project "$P"
grep -q "<text" "$P/assets/logo/wordmark-outlined.svg" && die "the outlined wordmark contains live text"
# a 278 x 74 wordmark is not a 16 px mark: the sheet's own 16 px tile may fail, so only the guide rows are asserted here
"${BC[@]}" logo-sheet --guides --svg assets/logo/wordmark-outlined.svg --project "$P" >/dev/null || true
python3 - "$P/assets/_checks/logo-sheet.json" <<'PY' || die "guide results missing"
import json, sys
ids = {r["id"]: r["status"] for r in json.load(open(sys.argv[1]))["results"]}
assert [ids.get(f"guide:{k}") for k in ("baseline", "cap", "x-height")] == ["pass"] * 3, ids
PY
ok "baseline, cap and x-height guides sit on the ink edges"
"${BC[@]}" logo-sheet --guides --grid 8 --project "$P" >/dev/null
expect_file "$P/assets/_checks/logo-guides.png"; expect_size "$P/assets/_checks/logo-guides.png" 512 512

step "downscale: the fine vector fails the 4 x 4 accent rule at 16 px, the coarse-grid master passes (real system downscale on macOS)"
set +e
"${BC[@]}" downscale --source assets/logo/mark.svg --renderer=resvg --sizes 32,16 --project "$P" >/dev/null; rc_fine=$?
set -e
[ "$rc_fine" = 1 ] || die "the fine vector should fail the accent rule at 16 px (exit $rc_fine)"
# Each master has its own report now, and a failing report that exists fails `check` (the fine vector is a demonstration, not a shipped
# file): move it aside, never delete it.
mkdir -p "$SMOKE/removed"
mv "$P"/assets/_checks/downscale/mark-*.json "$SMOKE/removed/fine-vector-downscale-$$.json"
DS=(); [ "$(uname)" = Darwin ] || DS=(--renderer=pillow)       # off macOS there is no sips: Pillow is the explicit opt-in for a PNG master
ICNS=(); [ "$(uname)" = Darwin ] || ICNS=(--renderer pillow)   # ... and no iconutil: Pillow writes the Tauri .icns, said in the report
FIN_OPT=(); [ "$(uname)" = Darwin ] || FIN_OPT=(ICNS_RENDERER=pillow DOWNSCALE_RENDERER=pillow)   # the same two opt-ins for tools/finish.sh
"${BC[@]}" downscale --source assets/logo/grid-mark-master.png ${DS[@]+"${DS[@]}"} --project "$P" >/dev/null || die "the grid master failed the downscale check"
python3 - "$P/assets/_checks/downscale" <<'PY' || die "downscale report is wrong"
import glob, json, sys
# one report per measured source: the grid master's own (the fine vector's failing one was moved aside above)
(f,) = glob.glob(sys.argv[1] + "/grid-mark-master-*.json")
rep = json.load(open(f))
assert rep["source"] == "assets/logo/grid-mark-master.png" and len(glob.glob(sys.argv[1] + "/*.json")) == 1
want = [180, 120, 87, 58, 48, 40, 32, 29, 20, 16]
assert rep["status"] == "pass" and rep["sizes"] == want, rep["sizes"]
assert all(r["accent_square"] >= 4 for r in rep["results"] if r["id"] in ("downscale:32px", "downscale:20px", "downscale:16px"))
print("   method:", rep["renderer"])
PY
ok "accent holds a solid square at every rule size"

step "states-check, contrast --cvd, fontcheck (cmap + licence + Chromium platform report), motion proof"
"${BC[@]}" states-check --project "$P" >/dev/null || die "states-check failed"
"${BC[@]}" contrast --cvd --project "$P" >/dev/null || die "contrast --cvd failed"
python3 - "$P/assets/_checks/contrast.json" <<'PY' || die "no cvd results"
import json, sys
rows = [r for r in json.load(open(sys.argv[1]))["results"] if r.get("section") == "cvd" and r["id"] != "cvd:threshold"]
assert rows and all(r["status"] in ("pass", "warn") for r in rows) and any(r["status"] == "warn" and r.get("exception") for r in rows)
print(f"   {len(rows)} colour-vision pair results (the accepted exception carries its reason)")
PY
"${BC[@]}" fontcheck --font "$FONT" --lang pl,de --project "$P" >/dev/null || die "fontcheck failed"
python3 - "$P/assets/_checks/fontcheck.json" <<'PY' || die "fontcheck report is wrong"
import json, sys
ids = {r["id"]: r["status"] for r in json.load(open(sys.argv[1]))["results"]}
assert ids["cmap:TestFont-subset.ttf:pl"] == "pass" and ids["platform:TestFont-subset.ttf"] == "pass", ids
PY
"${BC[@]}" shot --motion motion/proof.json --project "$P" >/dev/null || die "the motion proof failed"
python3 - "$P/assets/_checks/motion.json" <<'PY' || die "motion report is wrong"
import json, sys
rep = json.load(open(sys.argv[1]))
ids = [r["id"] for r in rep["results"]]
assert rep["status"] == "pass" and "motion:dot-press:2x:control:rest!=pressed" in ids and "motion:demo-page:reduced:animations" in ids, ids
PY
ok "states differ, colours survive colour-vision simulation, font covers pl and de, motion proof passes at 1x and 2x with a control"

step "platform packs: the Acme tray masters are rebuilt byte for byte, then windows, linux, tray, tauri, wallet and developer are emitted"
cp "$FIX/FACTS.md" "$P/FACTS.md"
mkdir -p "$P/tray" "$P/assets/tray-src"
cp "$FIX/tray/tray.json" "$P/tray/tray.json"
( cd "$P" && BRAND_CREATOR_ROOT="$ROOT" python3 tools/tray_masters.py >/dev/null ) || die "tools/tray_masters.py failed"
for f in "$FIX"/assets/tray-src/*.png; do cmp -s "$P/assets/tray-src/$(basename "$f")" "$f" || die "$(basename "$f") is not byte-identical to the example's committed master"; done
ok "12 tray masters rebuilt identically"
"${BC[@]}" emit windows --project "$P" >/dev/null || die "emit windows failed"
python3 - "$P/assets/windows" <<'PY' || die "the Windows pack is wrong"
import struct, sys
from pathlib import Path
d = Path(sys.argv[1])
ico = (d / "app.ico").read_bytes()
n = struct.unpack("<H", ico[4:6])[0]
layers = [(e[0] or 256, e[1] or 256) for e in (struct.unpack("<BBBBHHII", ico[6 + 16 * i:22 + 16 * i]) for i in range(n))]
assert layers == [(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)], layers
for name, size in (("header.bmp", (150, 57)), ("sidebar.bmp", (164, 314))):
    b = (d / "nsis" / name).read_bytes()
    w, h, planes, bits, comp = struct.unpack("<iiHHI", b[18:34])
    assert b[:2] == b"BM" and (w, abs(h)) == size and bits == 24 and comp == 0, (name, w, h, bits, comp)
print("   ok: app.ico layers 16 24 32 48 256; NSIS header 150x57 and sidebar 164x314, 24-bit")
PY
"${BC[@]}" emit linux --project "$P" --app-id org.example.Acme >/dev/null || die "emit linux failed"
for s in 16 22 24 32 48 64 128 256 512; do expect_size "$P/assets/linux/usr/share/icons/hicolor/${s}x${s}/apps/acme.png" "$s" "$s"; done
expect_file "$P/assets/linux/usr/share/icons/hicolor/scalable/apps/acme.svg"
python3 - "$P/assets/linux/usr/share/metainfo/org.example.Acme.metainfo.xml" "$P/FACTS.md" <<'PY' || die "the metainfo text is not the FACTS.md text"
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
facts = open(sys.argv[2]).read()
for tag in ("summary", "project_license", "metadata_license"):
    assert root.findtext(tag) and f"| {root.findtext(tag)} |" in facts, tag
print("   ok: AppStream summary and licences are FACTS.md values")
PY
"${BC[@]}" emit tray --project "$P" >/dev/null || die "emit tray failed (the states gate may have failed)"
python3 - "$P" <<'PY' || die "tray outputs or the states gate are wrong"
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
pngs = list((p / "assets/tray").rglob("*.png"))
assert len(pngs) == 2 * 6 * 3 + 2 * 3 + 3, len(pngs)
rep = json.load(open(p / "assets/_checks/states.json"))
assert rep["status"] == "pass" and rep["states_files"] == ["qa/states.json", "qa/states.tray.json"], rep["states_files"]
print(f"   ok: {len(pngs)} tray PNGs, {len({r['set'] for r in rep['results'] if r['id'].startswith('states:')})} state sets pass greyscale and silhouette")
PY
"${BC[@]}" emit tauri ${ICNS[@]+"${ICNS[@]}"} --project "$P" >/dev/null || die "emit tauri failed"
for f in 32x32.png 128x128.png 128x128@2x.png icon.png icon.ico icon.icns; do expect_file "$P/assets/tauri/src-tauri/icons/$f"; done
expect_size "$P/assets/tauri/src-tauri/icons/128x128@2x.png" 256 256
"${BC[@]}" emit wallet --project "$P" >/dev/null || die "emit wallet failed"
expect_size "$P/assets/wallet/apple/icon@3x.png" 114 114; expect_size "$P/assets/wallet/apple/logo@2x.png" 320 88
expect_size "$P/assets/wallet/apple/order-logo.png" 300 300; expect_size "$P/assets/wallet/google/logo-660.png" 660 660
expect_size "$P/assets/wallet/google/wide-logo-1280x400.png" 1280 400
DEV_EXEMPTION="the host shrinks the registry icon and the avatar to 16 px; the coarse-grid drawing keeps the accent"
"${BC[@]}" emit developer --project "$P" --tagline "a repair guide is in every box" --master-band small --content-fraction 0.8 --exemption "$DEV_EXEMPTION" >/dev/null || die "emit developer failed"
expect_size "$P/assets/developer/email/acme-email-logo@2x.png" 174 48; expect_size "$P/assets/developer/avatar/acme-avatar-1024.png" 1024 1024
expect_size "$P/assets/developer/nuget/acme-nuget-128.png" 128 128
for f in assets/developer/avatar/acme-avatar-1024.png assets/developer/nuget/acme-nuget-128.png; do
  "${BC[@]}" downscale --source "$f" ${DS[@]+"${DS[@]}"} --project "$P" >/dev/null || die "$f fails the accent rule at a size the host shows"
done
ok "downscale passes on each master the host shrinks (each manifest row is tied to the report of its own master)"
grep -q $'\x1b\[36mAcme' "$P/assets/developer/cli/identity.txt" || die "the CLI identity did not fall back to ANSI 36 (the accent fails 4.5:1 on a black ground)"
ok "windows, linux, tray, tauri, wallet and developer packs written at the spec sizes"

step "emit apple: the .icon, actool per platform (hard gate), legacy sets, visionOS stack, watchOS and tvOS packs for the listed targets, DMG and store frames (macOS); exit 3 elsewhere"
APPLE_ARGS=(--tagline "a repair guide is in every box" --master-band small --content-fraction 0.8 --visionos-content-fraction 0.6
            --exemption "the system shrinks this one master to 16 px; the coarse-grid drawing keeps the accent")
if [ "$(uname)" = Darwin ]; then
  printf '# Acme: surface inventory\n\n## Deployment targets\n\n- iOS: 17.0\n- macOS: 14.0\n- watchOS: 10.0\n- tvOS: 17.0\n' > "$P/INVENTORY.md"
  "${BC[@]}" emit apple --project "$P" "${APPLE_ARGS[@]}" || die "emit apple failed"
  python3 - "$P/assets/apple" <<'PY' || die "the Apple pack is wrong"
import json, struct, sys
from pathlib import Path
a = Path(sys.argv[1])
def size(f):
    d = Path(f).read_bytes()
    assert d[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", d[16:24]), d[25]
doc = json.load(open(a / "AppIcon.icon/icon.json"))
assert {s.get("appearance") for s in doc["fill-specializations"]} == {None, "dark", "tinted"}
assert size(a / "marketing/AppStore-1024.png") == ((1024, 1024), 2), "the marketing icon must be RGB with no alpha channel"
assert size(a / "compiled/ios/AppIcon60x60@2x.png")[0] == (120, 120) and size(a / "compiled/ios/AppIcon76x76@2x~ipad.png")[0] == (152, 152)
assert (a / "compiled/macos/AppIcon.icns").read_bytes()[:4] == b"icns"
for plat, want in (("ios", "Icon Image"), ("macos", "Icon Image"), ("watchos", "Icon Image"), ("visionos", "SolidImageStack")):
    kinds = {r["AssetType"] for r in json.load(open(a / f"compiled/{plat}.renditions.json"))}
    assert want in kinds, (plat, kinds)
assert size(a / "Assets.xcassets/AppIconVision.solidimagestack/Front.solidimagestacklayer/Content.imageset/front.png") == ((1024, 1024), 6)
assert size(a / "dmg/background@2x.png")[0] == (1320, 800) and size(a / "store/frame-iphone.png")[0] == (1206, 2622)
assert size(a / "Assets.xcassets/AppIcon.appiconset/AppIcon-iOS-light-1024.png") == ((1024, 1024), 2)
assert (a / "legacy/AppIcon.icns").read_bytes()[:4] == b"icns"
# watchOS (listed in INVENTORY.md): one opaque square at its own (U) spec size, compiled by actool for watchos; tvOS: a two-layer stack at 800 x 480, compiled for appletvos
assert size(a / "watchos/Assets.xcassets/AppIcon.appiconset/AppIcon-watchOS-1024.png") == ((1024, 1024), 2)
tv = a / "tvos/Assets.xcassets/AppIconTV.brandassets/Small.imagestack"
assert size(tv / "Back.imagestacklayer/Content.imageset/back.png") == ((800, 480), 2) and size(tv / "Front.imagestacklayer/Content.imageset/front.png") == ((800, 480), 6)
for f, want in (("watchos-appiconset", "Icon Image"), ("tvos", "ImageStack")):
    assert want in {r["AssetType"] for r in json.load(open(a / f"compiled/{f}.renditions.json"))}, f
mf = {x["path"]: x for x in json.load(open(a.parent / "manifest.json"))["artefacts"]}
assert mf["assets/apple/watchos/Assets.xcassets/AppIcon.appiconset/AppIcon-watchOS-1024.png"]["note"].startswith("UNVERIFIED, recheck (")
print("   ok: .icon valid, compiled for ios, macos, watchos and visionos; fallbacks, .icns, marketing icon (no alpha), legacy sets, watchOS appiconset and tvOS stack (labelled), DMG, frames")
PY
  "${BC[@]}" downscale --source assets/apple/marketing/AppStore-1024.png --project "$P" >/dev/null || die "the Apple master fails the accent rule at a size the system shows"
  ok "downscale (sips) passes on the Apple master: the accent keeps a solid 4 x 4 square down to 16 px"
  "${BC[@]}" emit apple --project "$P" "${APPLE_ARGS[@]}" | grep -q " 0 written" || die "a second emit apple wrote files"
  ok "second emit apple writes nothing"
else
  set +e; "${BC[@]}" emit apple --project "$P" >/dev/null 2>"$SMOKE/apple.err"; rc_apple=$?; set -e
  [ "$rc_apple" = 3 ] || die "emit apple off macOS must exit 3 (exit $rc_apple)"
  grep -q "needs macOS with Xcode" "$SMOKE/apple.err" || die "the exit 3 message does not say why"
  ok "emit apple exits 3 with a clear message (Apple emitters are macOS only)"
fi

step "Tier B packs (Full tier): emit android, chrome-ext and msix; the safe-zone gate, the monochrome layer and the unverified label"
set +e; "${BC[@]}" emit android --project "$P" >/dev/null 2>"$SMOKE/tierb.err"; rc_tb=$?; set -e
[ "$rc_tb" = 2 ] && grep -q "state --set tier=full" "$SMOKE/tierb.err" || die "emit android in the Quick tier must exit 2 and name the way up (exit $rc_tb)"
ok "emit android exits 2 below the Full tier and says how to raise it"
"${BC[@]}" state --project "$P" --set tier=full >/dev/null
for t in android chrome-ext msix; do "${BC[@]}" emit "$t" --project "$P" >/dev/null || die "emit $t failed"; done
python3 - "$P" <<'PY' || die "the Tier B packs are wrong"
import json, struct, sys, xml.etree.ElementTree as ET
from pathlib import Path
p = Path(sys.argv[1])
def size(f):
    d = Path(f).read_bytes()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", f
    return struct.unpack(">II", d[16:24]), d[25]
a = p / "assets/android"
for dn, px in (("mdpi", 108), ("hdpi", 162), ("xhdpi", 216), ("xxhdpi", 324), ("xxxhdpi", 432)):
    assert size(a / f"res/mipmap-{dn}/ic_launcher_foreground.png")[0] == (px, px) and size(a / f"res/mipmap-{dn}/ic_launcher_monochrome.png")[0] == (px, px), dn
assert size(a / "res/mipmap-xxxhdpi/ic_launcher_round.png")[0] == (192, 192)
root = ET.parse(a / "res/mipmap-anydpi-v26/ic_launcher.xml").getroot()
assert [c.tag for c in root] == ["background", "foreground", "monochrome"], [c.tag for c in root]
assert size(a / "play/ic_launcher-playstore.png") == ((512, 512), 6) and size(a / "play/feature-graphic.png") == ((1024, 500), 2)
mf = {x["path"]: x for x in json.load(open(p / "assets/manifest.json"))["artefacts"]}
assert "UNVERIFIED, recheck" in mf["assets/android/res/mipmap-hdpi/ic_launcher_foreground.png"]["note"]
assert "UNVERIFIED" not in mf["assets/android/play/ic_launcher-playstore.png"]["note"]
c = p / "assets/chrome-ext"
assert [size(c / f"icons/icon-{s}.png")[0] for s in (16, 32, 48, 128)] == [(16, 16), (32, 32), (48, 48), (128, 128)]
assert size(c / "store/promo-small-440x280.png") == ((440, 280), 2) and size(c / "store/promo-marquee-1400x560.png") == ((1400, 560), 2)
m = p / "assets/msix/Assets"
for name, (w, h) in (("Square44x44Logo", (44, 44)), ("Square150x150Logo", (150, 150)), ("Wide310x150Logo", (310, 150)), ("Square310x310Logo", (310, 310)), ("Square71x71Logo", (71, 71)), ("StoreLogo", (50, 50))):
    for sc in (1, 2, 4):
        assert size(m / f"{name}.scale-{sc * 100}.png")[0] == (w * sc, h * sc), (name, sc)
for s in (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256):
    for alt in ("", "_altform-unplated", "_altform-lightunplated"):
        assert size(m / f"Square44x44Logo.targetsize-{s}{alt}.png")[0] == (s, s), (s, alt)
print("   ok: adaptive layers at 5 densities with a monochrome layer, Play icon 512 RGBA, feature graphic 1024x500 RGB, Chrome icons and promo tiles, MSIX scales and 14 app-list sizes x 3 files")
PY
"${BC[@]}" emit android --project "$P" | grep -q " 0 written" || die "a second emit android wrote files"
"${BC[@]}" emit msix --project "$P" | grep -q " 0 written" || die "a second emit msix wrote files"
ok "second emit android and msix write nothing"
TB="$SMOKE/guard-tierb"; cp -R "$P" "$TB"
python3 - "$TB/assets/logo/mark.svg" <<'PY'
import sys
f = sys.argv[1]
s = open(f).read()
old = '<path d="M32 6 58 54H6Z" fill="#0d1b2d"/>'
assert old in s, "mutation did not apply"
open(f, "w").write(s.replace(old, '<rect width="64" height="64" fill="#0d1b2d"/>'))
PY
grep -q '<rect width="64" height="64"' "$TB/assets/logo/mark.svg" || die "the safe-zone mutation did not apply"
set +e; "${BC[@]}" emit android --project "$TB" --content-dp 66 --out-dir assets/android-square >/dev/null 2>"$SMOKE/tierb.err"; rc_tb=$?; set -e
[ "$rc_tb" = 1 ] && grep -q "outside the 66 dp safe zone" "$SMOKE/tierb.err" || die "a square mark at 66 dp must fail the safe-zone gate (exit $rc_tb)"
[ ! -e "$TB/assets/android-square/res" ] || die "the failed safe-zone gate wrote files"
ok "a full-bleed square mark at 66 dp fails the Android safe-zone gate (exit 1) and nothing is written"

step "profiles (Standard and Full tier): circle-safe avatar, six platform images inside their safe areas, proof images; the gate on an overflowing name; the Quick tier is refused"
"${BC[@]}" emit profiles --project "$P" --tagline "a repair guide is in every box" >/dev/null || die "emit profiles failed"
expect_size "$P/assets/profiles/avatar-400.png" 400 400; expect_size "$P/assets/profiles/avatar-800.png" 800 800
expect_size "$P/assets/profiles/linkedin-banner-1584x396.png" 1584 396; expect_size "$P/assets/profiles/x-header-1500x500.png" 1500 500
expect_size "$P/assets/profiles/youtube-banner-2560x1440.png" 2560 1440; expect_size "$P/assets/profiles/facebook-cover-820x312.png" 820 312
expect_size "$P/assets/profiles/instagram-feed-1080x1350.png" 1080 1350; expect_size "$P/assets/profiles/instagram-story-1080x1920.png" 1080 1920
python3 - "$P" "$ROOT" <<'PY' || die "the profile pack is wrong"
import json, sys
from pathlib import Path
p, root = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root / "scripts/lib"))
from pxio import png_color_type, read_png
rows = json.load(open(root / "scripts/emitters/platform-specs.json"))["rows"]
def ink(f):
    """(farthest ink from the centre, bounding box) of the pixels unlike the corner pixel."""
    d = Path(f).read_bytes()
    assert png_color_type(d) == 2, (f, "an avatar and a banner are RGB with no alpha channel")
    w, h, px = read_png(d)
    g = px[:3]
    far, xs, ys = 0.0, [], []
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            if max(abs(px[i + k] - g[k]) for k in range(3)) > 8:
                far = max(far, ((x + .5 - w / 2) ** 2 + (y + .5 - h / 2) ** 2) ** .5); xs.append(x); ys.append(y)
    return far, (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
circle = rows["profile-avatar"]["sizes"]["safe_circle"]
for n in (400, 800):
    far, _bb = ink(p / f"assets/profiles/avatar-{n}.png")
    assert 0 < far <= circle * n / 2 + 1.5, (n, far)           # the mark stays inside the safe circle of the profile-avatar row
s = rows["profile-youtube-banner"]["sizes"]["safe"]
far, bb = ink(p / "assets/profiles/youtube-banner-2560x1440.png")
assert bb[0] >= s["x"] - 1 and bb[2] <= s["x"] + s["width"] + 1 and bb[1] >= s["y"] - 1 and bb[3] <= s["y"] + s["height"] + 1, bb      # inside the central 1546 x 423 area
assert all((p / f"assets/profiles/_proof/{n}.png").is_file() for n in ("avatar-400", "linkedin-banner", "instagram-story"))
mf = json.load(open(p / "assets/manifest.json"))["artefacts"]
mine = [a for a in mf if a["emitter"] == "profiles"]
assert len(mine) == 8 and all(a["note"].startswith("UNVERIFIED, recheck (") for a in mine) and not [a for a in mf if "_proof" in a["path"]]
print("   ok: avatars inside the safe circle, YouTube ink inside its central area, proofs written and not in the manifest, 8 files all labelled UNVERIFIED")
PY
"${BC[@]}" emit profiles --project "$P" --tagline "a repair guide is in every box" | grep -q " 0 written" || die "a second emit profiles wrote files"
PG="$SMOKE/guard-profiles"; cp -R "$P" "$PG"
set +e; "${BC[@]}" emit profiles --project "$PG" --name "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW" --out-dir assets/profiles-long >/dev/null 2>"$SMOKE/profiles.err"; rc_pf=$?; set -e
[ "$rc_pf" = 1 ] && grep -q "does not fit its safe area" "$SMOKE/profiles.err" || die "a name wider than the LinkedIn safe rectangle must fail the gate (exit $rc_pf)"
[ -z "$(ls "$PG"/assets/profiles-long/*.png 2>/dev/null)" ] && [ -s "$PG/assets/profiles-long/_proof/linkedin-banner.png" ] || die "the failed gate shipped an image, or left no proof image"
ok "an overflowing name fails the safe-area gate (exit 1), nothing ships, the proof image shows where the ink went"
"${BC[@]}" state --project "$PG" --set tier=quick >/dev/null
set +e; "${BC[@]}" emit profiles --project "$PG" >/dev/null 2>"$SMOKE/profiles.err"; rc_pf=$?; set -e
[ "$rc_pf" = 2 ] && grep -q "state --set tier=standard" "$SMOKE/profiles.err" || die "emit profiles in the Quick tier must exit 2 and name the way up (exit $rc_pf)"
ok "emit profiles exits 2 in the Quick tier and says how to raise it"

step "snapshot, verify-idempotent (emit chain twice), staleness record, specs-due"
# qa/rules.json (the size bands) arrived after the first emit web: re-emit once so the favicon follows the band rule, then it must be stable
"${BC[@]}" emit web --project "$P" >/dev/null
"${BC[@]}" snapshot take assets --name before-emit --out snaps/before.json --project "$P" >/dev/null
"${BC[@]}" emit web --project "$P" >/dev/null
"${BC[@]}" snapshot take assets --name after-emit --out snaps/after.json --project "$P" >/dev/null
"${BC[@]}" snapshot diff snaps/before.json snaps/after.json --ignore "assets/_checks/*" --project "$P" >/dev/null || die "emit web changed files that were already current"
CHAIN=(--cmd "{bc} emit web --project {project}" --cmd "{bc} emit social --tagline Dependable --project {project}" --cmd "{bc} emit windows --project {project}"
       --cmd "{bc} emit linux --app-id org.example.Acme --project {project}" --cmd "{bc} emit tray --project {project}" --cmd "{bc} emit tauri ${ICNS[*]:-} --project {project}"
       --cmd "{bc} emit wallet --project {project}" --cmd "{bc} emit android --project {project}" --cmd "{bc} emit chrome-ext --project {project}" --cmd "{bc} emit msix --project {project}" --cmd "{bc} emit profiles --tagline 'a repair guide is in every box' --project {project}" --cmd "{bc} emit developer --tagline 'a repair guide is in every box' --master-band small --content-fraction 0.8 --exemption '$DEV_EXEMPTION' --project {project}")
[ "$(uname)" = Darwin ] && CHAIN+=(--cmd "{bc} emit apple --tagline 'a repair guide is in every box' --master-band small --content-fraction 0.8 --visionos-content-fraction 0.6 --exemption 'the system shrinks this one master to 16 px; the coarse-grid drawing keeps the accent' --project {project}")
"${BC[@]}" verify-idempotent "${CHAIN[@]}" --project "$P" >/dev/null \
  || die "the emit chain is not byte-identical when run twice"
ok "the whole emit chain (web, social and every platform pack) is byte-identical across two runs and passes the determinism rules"
"${BC[@]}" staleness --write --project "$P" >/dev/null
"${BC[@]}" staleness --project "$P" >/dev/null || die "a pack recorded a moment ago is already stale"
"${BC[@]}" specs-due >/dev/null || die "specs-due failed"
ok "staleness recorded and current; specs-due lists the rows to recheck"

step "check (every gate for the artefacts that exist)"
"${BC[@]}" check --project "$P"

step "freeze the approved round, then check again"
"${BC[@]}" freeze r1 --name approved-board --project "$P"
expect_file "$P/history/MANIFEST.sha256"
"${BC[@]}" check --project "$P"

step "guards on a copy of the finished pack: a failing master, a favicon off the band rule, an edited fact, a removed tray state"
G="$SMOKE/guard"; cp -R "$P" "$G"
failing_ids() { python3 -c "import json,sys;print(' '.join(r['id'] for r in json.load(open(sys.argv[1]))['results'] if r['status']==sys.argv[2]))" "$G/assets/_checks/check.json" "$1"; }
python3 - "$G" <<'PY' || die "the favicon layers are not drawn by the band rule"
import json, sys
a = next(x for x in json.load(open(sys.argv[1] + "/assets/manifest.json"))["artefacts"] if x["path"] == "assets/web/favicon.ico")
assert a["layer_bands"]["16"] == "small" and a["layer_bands"]["48"] == "large", a["layer_bands"]
PY
ok "emit web drew the 16 px favicon layer from the small band"
python3 - "$G" <<'PY'
import json, sys
f = sys.argv[1] + "/assets/manifest.json"
d = json.load(open(f))
for a in d["artefacts"]:
    if a["path"] == "assets/web/favicon.ico":
        a["layer_bands"]["16"] = "large"
json.dump(d, open(f, "w"), indent=2)
PY
set +e; "${BC[@]}" check --project "$G" >/dev/null; rc=$?; set -e
[ "$rc" = 1 ] && case " $(failing_ids fail) " in *" manifest:bands "*) true ;; *) false ;; esac || die "a favicon whose 16 px layer is off the band rule must fail check (exit $rc)"
ok "check fails a favicon layer drawn off the band rule"
G2="$SMOKE/guard-facts"; cp -R "$P" "$G2"
python3 - "$G2" <<'PY'
import sys
f = sys.argv[1] + "/FACTS.md"
t = open(f).read()
assert "a repair guide is in every box" in t
open(f, "w").write(t.replace("a repair guide is in every box", "a repair guide is in every crate", 1))
PY
set +e; "${BC[@]}" check --project "$G2" >/dev/null; rc=$?; set -e
python3 - "$G2/assets/_checks/check.json" "$rc" <<'PY' || die "editing FACTS.md must make the packs that quote it stale"
import json, sys
res = json.load(open(sys.argv[1]))["results"]
dev = next(r for r in res if r["id"] == "report:emit-developer")
assert dev["status"] == "skipped" and "FACTS.md changed" in dev["detail"], dev
assert any(r["id"] == "staleness:input:FACTS.md" and r["status"] == "fail" for r in res)
assert sys.argv[2] == "1", sys.argv[2]
PY
ok "check notices an edited FACTS.md (emit report stale, staleness input changed)"
python3 - "$G" <<'PY'
import json, sys
f = sys.argv[1] + "/tray/tray.json"
d = json.load(open(f))
d["states"].pop("error")
json.dump(d, open(f, "w"), indent=2)
PY
"${BC[@]}" emit tray --project "$G" >/dev/null || die "emit tray failed after a state was removed"
python3 - "$G" <<'PY' || die "a removed tray state is still shipped"
import glob, json, sys
g = sys.argv[1]
assert not glob.glob(g + "/assets/tray/**/error*", recursive=True), "error icons are still under assets/tray"
paths = [a["path"] for a in json.load(open(g + "/assets/manifest.json"))["artefacts"]]
assert not [p for p in paths if "/error" in p and p.startswith("assets/tray/")], "manifest rows remain"
moved = glob.glob(g + "/removed-*/assets/tray/**/error*", recursive=True)
assert len(moved) == 15, len(moved)
PY
ok "a removed tray state is moved to removed-<date>/ with its manifest rows dropped"
if [ "$(uname)" = Darwin ]; then
  G3="$SMOKE/guard-apple"; cp -R "$P" "$G3"
  "${BC[@]}" emit apple --project "$G3" --tagline "a repair guide is in every box" --master-band small --content-fraction 0.62 \
    --exemption "the system shrinks this one master to 16 px; the coarse-grid drawing keeps the accent" >/dev/null || die "emit apple (content 0.62) failed"
  set +e; "${BC[@]}" downscale --source assets/apple/marketing/AppStore-1024.png --project "$G3" >/dev/null; rc=$?; set -e
  [ "$rc" = 1 ] || die "the Apple master at content 0.62 should fail the accent rule at 16 px (exit $rc)"
  "${BC[@]}" downscale --source assets/logo/grid-mark-master.png --project "$G3" >/dev/null || die "the grid master should pass on its own"
  set +e; "${BC[@]}" check --project "$G3" >/dev/null; rc=$?; set -e
  python3 - "$G3/assets/_checks/check.json" "$rc" <<'PY' || die "check must stay red while the Apple master fails, whatever else passes"
import json, sys
res = json.load(open(sys.argv[1]))["results"]
bad = [r["id"] for r in res if r["status"] == "fail" and r["id"].startswith("report:downscale/appstore-1024")]
assert bad and sys.argv[2] == "1", (bad, sys.argv[2])
assert any(r["id"].startswith("report:downscale/grid-mark-master") and r["status"] == "pass" for r in res)
PY
  ok "a passing downscale report on the grid master does not vouch for the Apple master that fails at 16 px"
fi

step "tools/finish.sh from the template: the whole chain (every emitter that applies at the Full tier, print, posts, book, press kit) with multi-word options, a generator and every gate, then check"
G4="$SMOKE/guard-finish"; cp -R "$P" "$G4"
python3 - "$ROOT/templates/finish.sh.tpl" "$G4/tools/finish.sh" <<'PY'
import sys
t = open(sys.argv[1]).read()
for g in ("grid_mark.py", "state_icons.py"):
    assert f"  # tools/{g}\n" in t
    t = t.replace(f"  # tools/{g}\n", f"  tools/{g}\n")
open(sys.argv[2], "w").write(t)
PY
chmod +x "$G4/tools/finish.sh"
# the book's chapters are the owner's text: the chain never writes them, so the smoke starts and fills them here (the way the book step does below)
"${BC[@]}" state --project "$G4" --set content_languages=en --set book_chapters=tone >/dev/null
"${BC[@]}" book --init --project "$G4" >/dev/null || die "book --init failed in the finish copy"
python3 - "$G4" <<'PY' || die "the finish copy's chapters could not be filled"
import glob, re, sys
n = 0
for f in glob.glob(sys.argv[1] + "/book/chapters/*.md"):
    t = open(f).read()
    t, k = re.subn(r"\[\[fill:.*?\]\](?!\])", "Acme sample text for this slot.", t, flags=re.S)
    n += k
    open(f, "w").write(t)
assert n > 10, n
f = sys.argv[1] + "/BRAND-STATE.md"
t = open(f).read()
assert "- (rule) (...)" in t
open(f, "w").write(t.replace("- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)", 1))
PY
# a set PRINT_REGION in the Quick tier stops the chain at once (exit 2), before any step runs: a value is never silently ignored
QF="$SMOKE/guard-finish-quick"; cp -R "$G4" "$QF"; "${BC[@]}" state --project "$QF" --set tier=quick >/dev/null
set +e; ( cd "$QF" && env -u BRAND_CREATOR_ROOT PATH="$ROOT/bin:$PATH" PRINT_REGION=EU bash tools/finish.sh > "$SMOKE/finish-quick.log" 2>&1 ); rc_q=$?; set -e
[ "$rc_q" = 2 ] && grep -q "Standard and Full tier" "$SMOKE/finish-quick.log" && ! grep -q "^== tokens" "$SMOKE/finish-quick.log" || die "PRINT_REGION in the Quick tier must stop the chain with exit 2 before any step (exit $rc_q)"
ok "finish.sh: PRINT_REGION in the Quick tier stops the chain (exit 2) before any step runs"
( cd "$G4" && env -u BRAND_CREATOR_ROOT ${FIN_OPT[@]+"${FIN_OPT[@]}"} PATH="$ROOT/bin:$PATH" TAGLINE="a repair guide is in every box" APP_ID=org.example.Acme MASTER_BAND=small \
    EXEMPTION="the system shrinks this one master to 16 px; the coarse-grid drawing keeps the accent" ICON_CONTENT=0.8 VISIONOS_CONTENT=0.6 \
    PRINT_REGION=EU IMAGE_BASE_URL=https://img.example.com/brand POST_FACTS="spare parts;repair guide;batch size" \
    bash tools/finish.sh > "$SMOKE/finish.log" 2>&1 ) || { tail -30 "$SMOKE/finish.log" >&2; die "tools/finish.sh did not run through (log: $SMOKE/finish.log)"; }
grep -q "^check: PASS" "$SMOKE/finish.log" || die "finish.sh ended without a passing check"
python3 - "$SMOKE/finish.log" "$G4" <<'PY' || die "the finish chain did not run every step that applies at the Full tier, in order"
import re, sys
from pathlib import Path
log = Path(sys.argv[1]).read_text()
steps = re.findall(r"^== (.+)$", log, re.M)
def at(name):
    i = [k for k, s in enumerate(steps) if s == name or s.startswith(name + " ")]
    assert i, (name, steps)
    return i[0]
want = ["emit web", "emit social", "emit android", "emit chrome-ext", "emit msix", "emit profiles", "emit print", "print-check", "gates", "book", "book-pdf", "emit presskit"]
if sys.platform == "darwin":
    want.insert(want.index("emit android"), "emit apple")
order = [at(n) for n in want]
assert order == sorted(order), dict(zip(want, order))
p = Path(sys.argv[2])
for f in ("book.html", "book.pdf", "assets/presskit/acme-press-kit.zip", "assets/social/posts/carousel-4x5-01.png", "assets/print/letterhead.rgb-proof.pdf",
          "assets/profiles/avatar-400.png", "assets/android/res/mipmap-hdpi/ic_launcher_foreground.png", "assets/chrome-ext/icons/icon-128.png", "assets/msix/Assets/StoreLogo.scale-100.png"):
    assert (p / f).is_file(), f
if sys.platform == "darwin":
    assert (p / "assets/apple/watchos/Assets.xcassets/AppIcon.appiconset/AppIcon-watchOS-1024.png").is_file() and (p / "assets/apple/tvos/Assets.xcassets/Contents.json").is_file()
print("   ok:", ", ".join(want))
PY
ok "finish.sh: generators, tokens, every emitter that applies (Tier B, profiles, print, posts), book, book-pdf, press kit, downscale gates, idempotence, staleness and check all ran from the template"

step "guard hook: frozen history is protected, unrelated paths are not"
payload() { python3 -c "import json,sys;print(json.dumps({'tool_name':sys.argv[1],'tool_input':{sys.argv[2]:sys.argv[3]},'cwd':sys.argv[4]}))" "$@"; }
FROZEN="$(ls "$P"/history/*/board.html | head -n 1)"
set +e
payload Edit file_path "$FROZEN" "$P" | python3 "$ROOT/scripts/guard.py" 2>/dev/null; rc_frozen=$?
payload Write file_path "$P/notes.md" "$P" | python3 "$ROOT/scripts/guard.py" 2>/dev/null; rc_notes=$?
set -e
[ "$rc_frozen" = 2 ] || die "the guard did not block an edit of frozen history (exit $rc_frozen)"
[ "$rc_notes" = 0 ] || die "the guard blocked an unrelated write (exit $rc_notes)"
ok "edit of history/ blocked, write of notes.md allowed"

step "names: offline replay of the recorded fixtures (no network; the live path is the manual requires_network test)"
"${BC[@]}" names granite zqxvkrmpl --tlds com,io --offline "$ROOT/tests/fixtures/names/software" --project "$P" >/dev/null || die "names replay failed"
expect_file "$P/assets/_checks/names.json"; expect_file "$P/research/names/2026-10-17-check.md"
python3 - "$P/assets/_checks/names.json" <<'PY' || die "names report has the wrong states"
import json, sys
c = {r["id"]: r["state"] for r in json.load(open(sys.argv[1]))["results"]}
assert c["granite:.com"] == "REGISTERED" and c["zqxvkrmpl:.com"] == "NOT-FOUND" and len(c) == 20, c
PY
ok "names report: REGISTERED / NOT-FOUND as recorded, 20 cells"
"${BC[@]}" check --project "$P" >/dev/null || die "check no longer passes after names wrote its report"

step "brand-assets standalone entry: an existing mark and a target list into ./brand-assets/ (the skill's commands, in its order)"
SA="$SMOKE/standalone"
mkdir -p "$SA"
"${BC[@]}" new brand-assets --name Acme --tier quick --root "$SA" >/dev/null
A="$SA/brand-assets"
"${BC[@]}" state --project "$A" --set mark_source=existing >/dev/null
"${BC[@]}" state --project "$A" --record G0 "standalone brand-assets: existing mark; targets web, windows" >/dev/null
"${BC[@]}" state --project "$A" --record G3 "owner's existing mark, used as supplied" >/dev/null
[ "$("${BC[@]}" state --project "$A" --get mark_source)" = existing ] || die "mark_source was not recorded as existing"
mkdir -p "$A/assets/logo" "$A/tokens"
cp "$FIX/assets/logo/mark.svg" "$FIX/assets/logo/mark-dark.svg" "$A/assets/logo/"
cp "$ROOT"/templates/tokens/*.json "$A/tokens/"
python3 - "$A/tokens/primitives.tokens.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
def srgb(h):  # the mark's own colours, exact (step 5 of the skill)
    return {"colorSpace": "srgb", "components": [round(int(h[i:i + 2], 16) / 255, 6) for i in (1, 3, 5)], "alpha": 1, "hex": h}
for role, h in {"ink": "#0d1b2d", "signal": "#007d71", "chalk": "#f0eee7", "signal-bright": "#4cd7c8"}.items():
    d["color"][role]["$value"] = srgb(h)
json.dump(d, open(p, "w"), indent=2)
PY
"${BC[@]}" tokens --project "$A" >/dev/null || die "tokens from srgb primitives failed"
set +e
"${BC[@]}" contrast --project "$A" >/dev/null; rc_contrast=$?
set -e
[ "$rc_contrast" = 1 ] || die "the audit should find the dark accent touching the dark mark colour (contrast exit $rc_contrast)"
python3 - "$A/assets/_checks/contrast.json" "$A/tokens/exceptions.json" <<'PY'
import json, sys
bad = [r["id"] for r in json.load(open(sys.argv[1]))["results"] if r["status"] == "fail"]
assert bad == ["touch:dark:mark:#4cd7c8|#f0eee7"], bad
e = json.load(open(sys.argv[2]))
e["exceptions"].append({"a": "color.accent", "b": "color.mark", "mode": "dark",
                        "reason": "owner accepts the dot on the light triangle in dark mode; it is a fill with an edge, never text"})
json.dump(e, open(sys.argv[2], "w"), indent=2)
PY
"${BC[@]}" contrast --project "$A" >/dev/null || die "contrast still fails after the owner's exception"
"${BC[@]}" logo-sheet --project "$A" >/dev/null
expect_file "$A/assets/_checks/logo-sheet.png"
set +e
"${BC[@]}" downscale --source assets/logo/mark.svg --renderer=resvg --sizes 32,16 --project "$A" >/dev/null; rc_ds=$?
set -e
[ "$rc_ds" = 1 ] || die "the 16 px accent of the fine mark should fail the default 4 x 4 rule (downscale exit $rc_ds)"
"${BC[@]}" emit web --project "$A" >/dev/null
"${BC[@]}" emit windows --project "$A" >/dev/null
expect_file "$A/assets/web/favicon.ico"; expect_file "$A/assets/windows/app.ico"; expect_file "$A/assets/manifest.json"
set +e
"${BC[@]}" check --project "$A" >/dev/null; rc_check=$?
set -e
[ "$rc_check" = 1 ] || die "check must fail while a failing downscale report exists (exit $rc_check)"
mkdir -p "$A/qa"
printf '{"schema": 1, "downscale": {"accent_min_px": 2}}\n' > "$A/qa/rules.json"
printf '\n- %s: the 16 px accent keeps a 2 px solid square (measured); the owner set the accent minimum to 2 px rather than redraw.\n' "$BRAND_CREATOR_TODAY" >> "$A/DECISIONS.md"
"${BC[@]}" downscale --source assets/logo/mark.svg --renderer=resvg --sizes 32,16 --project "$A" >/dev/null || die "downscale fails under the owner's rule"
"${BC[@]}" emit web --project "$A" >/dev/null
"${BC[@]}" emit windows --project "$A" >/dev/null
"${BC[@]}" check --project "$A" >/dev/null || die "check fails on the standalone brand-assets project"
ok "standalone: srgb tokens from the mark, audit found two weaknesses, each resolved by a recorded owner decision, check passes"

step "brand book: chapter skeletons, filled, built, linted, rebuilt byte for byte, exported as a labelled RGB PDF (on a copy of the finished pack)"
BK="$SMOKE/book"; cp -R "$P" "$BK"
"${BC[@]}" state --project "$BK" --set tier=standard --set content_languages=en --set book_chapters=tone >/dev/null
mut() { python3 - "$@" <<'PY'
import sys
f, old, new = sys.argv[1:4]
t = open(f).read()
assert old in t, f"the mutation did not apply: {old!r} not found in {f}"
open(f, "w").write(t.replace(old, new, 1))
PY
}
mut "$BK/BRAND-STATE.md" "- (rule) (...)" "- (rule) the accent is a fill, never text (proposal)"
"${BC[@]}" book --init --project "$BK" >/dev/null || die "book --init failed"
python3 - "$BK" <<'PY'
import glob, re, sys
n = 0
for f in glob.glob(sys.argv[1] + "/book/chapters/*.md"):
    t = open(f).read()
    t, k = re.subn(r"\[\[fill:.*?\]\](?!\])", "Acme sample text for this slot.", t, flags=re.S)
    n += k
    open(f, "w").write(t)
assert n > 10, n
PY
"${BC[@]}" book --project "$BK" | tail -n 1
expect_file "$BK/book.html"
python3 - "$BK" <<'PY' || die "the generated book is wrong"
import json, re, sys
from html.parser import HTMLParser
p = sys.argv[1]
html = open(p + "/book.html").read()
manifest = json.load(open(p + "/assets/manifest.json"))["artefacts"]
class P(HTMLParser):
    def __init__(s): super().__init__(); s.sections = []; s.paths = set(); s.counts = {}; s.last = None; s.imgs = []
    def handle_starttag(s, tag, attrs):
        a = dict(attrs)
        if tag == "section" and "data-chapter" in a: s.sections.append(a["data-chapter"])
        if "data-path" in a: s.paths.add(a["data-path"])
        if "data-count" in a: s.last = a["data-count"]
        if tag == "img": s.imgs.append(a.get("src", ""))
    def handle_data(s, d):
        if s.last: s.counts[s.last] = d; s.last = None
q = P(); q.feed(html)
assert q.sections == ["idea", "mark", "motion", "wordmark", "colour", "type", "tone", "use", "files", "proof", "donts", "changing", "history"], q.sections
assert q.counts["files"] == str(len(manifest)) and {m["path"] for m in manifest} <= q.paths, (q.counts, len(manifest))
assert "<script" not in html and not re.search(r"(?:src|href)=[\"']https?:", html) and all(s.startswith("data:") for s in q.imgs)
assert "prefers-color-scheme:dark" in html and "16.15:1" in html      # contrast computed from the tokens (Acme text on its ground)
assert re.search(r"<h3[^>]*>Governance</h3>", html), "the changing chapter lost the Governance section of its skeleton"
print(f"   ok: {len(q.sections)} chapters, {q.counts['files']} files computed from the manifest, {len(q.imgs)} embedded images, light and dark")
PY
cp "$BK/book.html" "$SMOKE/book.first.html"
"${BC[@]}" book --project "$BK" | grep -q "unchanged" || die "a second book build changed the file"
cmp -s "$BK/book.html" "$SMOKE/book.first.html" || die "the book is not byte-identical on rebuild"
"${BC[@]}" book --verify --project "$BK" >/dev/null || die "book --verify failed on a fresh build"
"${BC[@]}" book-lint --self-consistency --project "$BK" >/dev/null || die "book-lint --self-consistency failed on the generated book"
ok "book built from tokens, manifest, state, facts and reports; lint and self-consistency pass; the rebuild is byte-identical"
BS="$SMOKE/book-shot"; cp -R "$BK" "$BS"      # a copy: shot rewrites assets/_checks/shot.json
"${BC[@]}" shot book.html --project "$BS" --out "$SMOKE/book-shots" --dsf 1 >/dev/null || die "the book's four-view shot failed"
python3 - "$BS/assets/_checks/shot.json" <<'PY' || die "the book lost its side gutter"
import json, sys
res = {r["id"]: r for r in json.load(open(sys.argv[1]))["results"]}
for v in ("view:390-light", "view:390-dark"):
    r = res[v]
    assert r["gutter_left"] is not None and r["gutter_left"] >= 16 and r["gutter_right"] >= 16, (v, r["gutter_left"], r["gutter_right"])
print("   ok: at 390 px the cover, text and colophon keep a 16 px side gutter (left %s, right %s)" % (res["view:390-light"]["gutter_left"], res["view:390-light"]["gutter_right"]))
PY
"${BC[@]}" check --project "$BK" >/dev/null 2>&1; python3 - "$BK/assets/_checks/check.json" <<'PY' || die "check does not gate the book"
import json, sys
ids = {r["id"]: r["status"] for r in json.load(open(sys.argv[1]))["results"]}
assert ids["report:book-lint"] == "pass" and ids["report:book"] == "pass" and ids["book:generated"] == "pass", ids
PY
ok "check gates the book (lint report, build report, and that book.html is still the generated bytes)"
command -v pdfinfo >/dev/null && command -v pdftotext >/dev/null || die "pdfinfo and pdftotext (poppler) are needed for the book-pdf step: install poppler, then re-run (brand-creator prereq --for print)"
"${BC[@]}" book-pdf --project "$BK" >/dev/null || die "book-pdf failed"
pdfinfo "$BK/book.pdf" | grep -q "Subject:         RGB, not print-ready" || die "book.pdf metadata does not carry the RGB label"
pdftotext -f 1 -l 1 "$BK/book.pdf" - | tr '\n' ' ' | grep -q "RGB, not print-ready" || die "the first page of book.pdf does not carry the RGB label"
cp "$BK/book.pdf" "$SMOKE/book.first.pdf"; "${BC[@]}" book-pdf --project "$BK" | grep -q unchanged || die "a second book-pdf changed the file"
cmp -s "$BK/book.pdf" "$SMOKE/book.first.pdf" || die "book.pdf is not byte-identical on a second export"
ok "book.pdf: RGB proof labelled in the metadata and on the cover, identical on a second export"

step "brand book mutations: each broken copy of the book must fail with a clear message"
brk() { # brk <name> <expected message fragment> <command...>: run on a fresh copy; the command mutates it first
  local name="$1" frag="$2"; shift 2
  local d="$SMOKE/book-m-$name"; cp -R "$BK" "$d"
  "$@" "$d"
  set +e; out="$("${BC[@]}" ${BRK_CMD:-book} --project "$d" 2>&1)"; rc=$?; set -e
  [ "$rc" = 1 ] || die "mutation $name: expected exit 1, got $rc"
  printf '%s' "$out" | grep -qF -- "$frag" || die "mutation $name: the message does not say '$frag': $(printf '%s' "$out" | tail -n 3)"
  ok "mutation $name fails: $frag"
}
files_n="$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['artefacts']))" "$BK/assets/manifest.json")"
m_count()  { mut "$1/book/chapters/files.md" "The pack holds" "There are $((files_n + 40)) files here. The pack holds"; }
m_round()  { mut "$1/book/chapters/mark.md" "## By size" "## By size

This came out of Round 2."; }
m_net()    { mut "$1/book/chapters/use.md" "## In use" "## In use

See [the site](https://example.com/brand)."; }
m_status() { mut "$1/book/chapters/idea.md" "## The idea" "## The idea

The shop is coming soon."; }
m_text()   { mut "$1/assets/logo/mark.svg" "</svg>" "<text x='1' y='9'>A</text></svg>"; }
m_dur()    { mut "$1/book.html" "</style>" "a{transition:color 900ms}</style>"; }
brk count  "but the data say $files_n files" m_count
brk round  "'Round 2'" m_round
brk net    "network address in a link" m_net
brk status "'coming soon'" m_status
brk text   "<text> element" m_text
BRK_CMD="book-lint --self-consistency" brk duration "900ms" m_dur
BRK_CMD=check brk handedit "differs from what \`book\` wrote" m_dur

step "print and press: stationery as honest print PDFs, print-check with four mutations, a PDF/X-4 candidate only with --icc, press kit, social posts (on a copy of the pack that has the book)"
command -v gs >/dev/null && command -v pdftoppm >/dev/null && command -v pdffonts >/dev/null || die "gs and poppler (pdfinfo, pdftoppm, pdffonts) are needed for the print step: brand-creator prereq --for print"
PR="$SMOKE/print"; cp -R "$BK" "$PR"
set +e; "${BC[@]}" emit print --project "$PR" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 2 ] || die "emit print must ask for --region when the brief names none (exit $rc)"
"${BC[@]}" emit print --project "$PR" --region EU --tagline "a repair guide is in every box" --image-base-url https://img.example.com/brand | tail -n 1
python3 - "$PR" <<'PY' || die "the print pieces are wrong"
import json, re, subprocess, sys
from pathlib import Path
p = Path(sys.argv[1]) / "assets/print"
MM = 72 / 25.4     # 25.4 mm to the inch, 72 pt to the inch
want = {"business-card-front": (85, 55), "business-card-back": (85, 55), "letterhead": (210, 297), "envelope": (220, 110)}
for piece, (w, h) in want.items():
    pdf = p / f"{piece}.rgb-proof.pdf"
    out = subprocess.run(["pdfinfo", "-box", str(pdf)], capture_output=True, text=True, check=True).stdout
    box = lambda n: [float(v) for v in re.search(rf"^{n}:\s+(.*)$", out, re.M).group(1).split()]
    m, tr, bl = box("MediaBox"), box("TrimBox"), box("BleedBox")
    assert abs((m[2] - m[0]) - (w + 6) * MM) < 0.02 and abs((m[3] - m[1]) - (h + 6) * MM) < 0.02, (piece, m)      # trim + 2 x 3 mm
    assert abs((tr[2] - tr[0]) - w * MM) < 0.02 and abs((tr[3] - tr[1]) - h * MM) < 0.02, (piece, tr)
    assert all(abs(a - b) < 0.01 for a, b in zip(bl, m)), (piece, bl, m)
    assert "Subject:         RGB proof, not print-ready" in out and "Pages:           1" in out
    fonts = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    assert not [f for f in fonts if f.strip()], (piece, fonts)       # text is outlines
    raw = pdf.read_bytes()
    assert b"/OutputIntents" not in raw and b"PDF/X" not in raw and b"/DeviceCMYK" not in raw
sig = (p / "email-signature/email-signature.html").read_text()
assert "<table" in sig and "<style" not in sig.lower() and "https://img.example.com/brand/logo@2x.png" in sig and 'href="tel:+00000000000"' in sig
print("   ok: four print PDFs, each trim + 2 x 3 mm, TrimBox and BleedBox set, one page, no fonts, labelled RGB proof; e-mail signature is a table with inline styles")
PY
"${BC[@]}" print-check --project "$PR" | tail -n 2 | head -n 1 | grep -q "print-check: PASS" || die "print-check did not pass on the clean pieces"
"${BC[@]}" emit print --project "$PR" --region EU --tagline "a repair guide is in every box" --image-base-url https://img.example.com/brand | grep -q " 0 written" || die "a second emit print wrote files"
ok "print-check passes on the clean pieces; a second emit print writes nothing"

pbrk() { # pbrk <name> <template> <old> <new> <row id> <detail fragment>: a broken copy of one template must fail print-check on exactly that rule
  local name="$1" tpl="$2" old="$3" new="$4" row="$5" frag="$6"
  local d="$SMOKE/print-m-$name"; cp -R "$PR" "$d"; mkdir -p "$d/tpl"; cp "$ROOT"/templates/print/*.html "$d/tpl/"
  mut "$d/tpl/$tpl.html" "$old" "$new"
  "${BC[@]}" emit print --project "$d" --region EU --template-dir "$d/tpl" --only "$tpl" >/dev/null || die "mutation $name: the broken template did not render"
  set +e; out="$("${BC[@]}" print-check --project "$d" 2>&1)"; rc=$?; set -e
  [ "$rc" = 1 ] || die "mutation $name: print-check should exit 1, got $rc"
  printf '%s' "$out" | grep -F "$row" | grep -qF -- "$frag" || die "mutation $name: row $row does not say '$frag': $(printf '%s' "$out" | grep -F "$row")"
  ok "mutation $name fails: $row"
}
pbrk safezone business-card-back ".trim{display:flex;flex-direction:column;justify-content:space-between;padding:{{margin}}mm}" ".trim{display:flex;flex-direction:column;justify-content:space-between;padding:1mm}" "business-card-back.rgb-proof:safe-zone" "mm from the left trim edge"
pbrk bleed business-card-back ".ground{background:{{ink}};color:{{paper}}}" ".ground{background:{{ink}};color:{{paper}};left:{{bleed}}mm;top:{{bleed}}mm;width:{{trim_w}}mm;height:{{trim_h}}mm}" "business-card-back.rgb-proof:bleed:ring" "artwork stops at the trim"
pbrk opacity letterhead ".contact{font-size:8pt;line-height:1.45;text-align:right;color:{{muted}}}" ".contact{font-size:8pt;line-height:1.45;text-align:right;color:{{muted}};opacity:.5}" "letterhead.rgb-proof:transparency" "ca 0.5"
d="$SMOKE/print-m-pdfx"; cp -R "$PR" "$d"
"$ROOT/tests/tools/pdfmut.py" claim-pdfx "$PR/assets/print/letterhead.rgb-proof.pdf" "$d/assets/print/letterhead.rgb-proof.pdf" || die "the PDF/X claim mutation did not apply"
cmp -s "$PR/assets/print/letterhead.rgb-proof.pdf" "$d/assets/print/letterhead.rgb-proof.pdf" && die "the PDF/X claim mutation did not change the file"
set +e; out="$("${BC[@]}" print-check --project "$d" assets/print/letterhead.rgb-proof.pdf 2>&1)"; rc=$?; set -e
[ "$rc" = 1 ] || die "a PDF/X claim without --icc must fail print-check (exit $rc)"
printf '%s' "$out" | grep -F "label:claims" | grep -qF "needs --icc" || die "the PDF/X claim was not named: $(printf '%s' "$out" | grep -F 'label:')"
ok "mutation pdfx-claim-without-icc fails: letterhead.rgb-proof:label:claims"

ICC="$(python3 - <<'PY'
import shutil, sys
from pathlib import Path
gs = Path(shutil.which("gs")).resolve()
# Homebrew: <prefix>/share/ghostscript/<version>/iccprofiles; Debian and Ubuntu: /usr/share/color/icc/ghostscript
for root in (gs.parents[1] / "share" / "ghostscript", gs.parents[2] / "share" / "ghostscript", gs.parents[1] / "share" / "color" / "icc" / "ghostscript"):
    hits = sorted(root.rglob("default_cmyk.icc")) if root.is_dir() else []
    if hits:
        print(hits[0]); break
PY
)"
[ -n "$ICC" ] || die "no CMYK ICC profile found next to Ghostscript to stand in for a printer's profile: pass one by hand to test the --icc path (brand-creator bundles none)"
IC="$SMOKE/print-icc"; cp -R "$PR" "$IC"
"${BC[@]}" emit print --project "$IC" --region EU --icc "$ICC" >/dev/null || die "emit print --icc failed"
for n in business-card-front business-card-back letterhead envelope; do
  f="$IC/assets/print/$n.pdfx4-candidate.pdf"; expect_file "$f"
  pdfinfo "$f" | grep -q "Subject:         PDF/X-4 candidate (preflight with your printer)" || die "$n: the label is wrong"
  [ -z "$(pdffonts "$f" | tail -n +3)" ] || die "$n: text is not outlined"
  grep -aq "/OutputIntents" "$f" && grep -aq "GTS_PDFXVersion" "$f" || die "$n: no PDF/X-4 output intent in the candidate"
  grep -aqi "conform\|compliant" "$f" && die "$n: the file claims conformance"
done
[ -z "$(ls "$IC/assets/print/"*.rgb-proof.pdf 2>/dev/null)" ] || die "the RGB proofs were not retired when the candidates were written"
"${BC[@]}" print-check --project "$IC" --icc "$ICC" | tail -n 2 | head -n 1 | grep -q "print-check: PASS" || die "print-check failed on the PDF/X-4 candidates"
ok "with --icc: PDF/X-4 candidates (label, output intent, CMYK, no fonts), the RGB proofs retired, print-check --icc passes; nothing says it conforms"

"${BC[@]}" emit presskit --project "$PR" >/dev/null || die "emit presskit failed"
cp "$PR/assets/presskit/acme-press-kit.zip" "$SMOKE/kit.first.zip"
"${BC[@]}" emit presskit --project "$PR" | grep -q " 0 written" || die "a second emit presskit wrote files"
cmp -s "$PR/assets/presskit/acme-press-kit.zip" "$SMOKE/kit.first.zip" || die "the press kit is not byte-identical on a second run"
python3 - "$PR/assets/presskit/acme-press-kit.zip" <<'PY' || die "the press kit is wrong"
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = [i.filename for i in z.infolist()]
assert names == sorted(names) and all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in z.infolist())
for want in ("logos/mark.svg", "logos/wordmark.svg", "tokens/tokens.css", "tokens/tokens.json", "book/book.pdf", "README.txt"):
    assert f"acme-press-kit/{want}" in names, (want, names)
print(f"   ok: press kit of {len(names)} entries, sorted, fixed mtime, with logos, tokens and the book PDF")
PY
"${BC[@]}" emit social --project "$PR" --posts --post-fact "spare parts" --post-fact "repair guide" --post-fact "batch size" --tagline "Dependable small-batch tools" >/dev/null || die "emit social --posts failed"
for i in 01 02 03 04 05; do expect_size "$PR/assets/social/posts/carousel-4x5-$i.png" 1080 1350; done
expect_size "$PR/assets/social/posts/educational-4x5.png" 1080 1350; expect_size "$PR/assets/social/posts/post-1x1.png" 1080 1080
grep -q "a repair guide is in every box" "$PR/assets/social/_build/posts/carousel-4x5-03.html" || die "the post text is not the FACTS.md value"
set +e; "${BC[@]}" emit social --project "$PR" --posts --post-fact "an unconfirmed claim" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "a post fact that is not in FACTS.md must fail (exit $rc)"
ok "social posts: a 5-slide 4:5 carousel, an educational 4:5 post and a 1:1 post from FACTS.md values; an unconfirmed label is refused"
"${BC[@]}" verify-idempotent --project "$PR" --cmd "{bc} emit print --region EU --tagline 'a repair guide is in every box' --image-base-url https://img.example.com/brand --project {project}" \
  --cmd "{bc} emit presskit --project {project}" \
  --cmd "{bc} emit social --posts --post-fact 'spare parts' --post-fact 'repair guide' --post-fact 'batch size' --tagline 'Dependable small-batch tools' --project {project}" >/dev/null \
  || die "the print, press kit and social chain is not byte-identical when run twice"
"${BC[@]}" book --project "$PR" >/dev/null || die "the book does not rebuild with the print rows in the manifest"
"${BC[@]}" book-lint --self-consistency --project "$PR" >/dev/null || die "the rebuilt book does not lint (files accounting must cover the print rows)"
"${BC[@]}" book-pdf --project "$PR" >/dev/null || die "book-pdf failed after the rebuild"
"${BC[@]}" emit presskit --project "$PR" >/dev/null
"${BC[@]}" print-check --project "$PR" >/dev/null || die "print-check failed after the rebuild"
"${BC[@]}" check --project "$PR" >/dev/null 2>&1 || die "check does not pass on the pack with print, press kit and posts (the press kit must not make the book reports stale)"
python3 - "$PR/assets/_checks/check.json" <<'PY' || die "check does not gate the print pack"
import json, sys
ids = {r["id"]: r["status"] for r in json.load(open(sys.argv[1]))["results"]}
for k in ("report:print-check", "report:emit-print", "report:emit-presskit", "report:emit-social", "report:book", "report:book-lint", "report:book-pdf"):
    assert ids[k] == "pass", (k, ids.get(k))
PY
ok "idempotent chain; the book accounts for the print rows and leaves the press kit out; check passes and gates print-check, emit-print, emit-presskit and emit-social"

step "hand-authored books: patch refuses a wrong count, applies the right one and logs the edition; collapse closes a choice and backs up"
AV="$SMOKE/book-authored"; cp -R "$BK" "$AV"
"${BC[@]}" state --project "$AV" --set mark_source=authored-vector >/dev/null
set +e; "${BC[@]}" book --project "$AV" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 2 ] || die "book must refuse an authored-vector brand (exit $rc)"
n_hits="$(grep -o 'Acme sample text for this slot' "$AV/book.html" | wc -l | tr -d ' ')"
set +e; "${BC[@]}" patch book.html --old "Acme sample text for this slot." --new "Real text." --count $((n_hits + 1)) --project "$AV" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "patch must refuse a wrong count (exit $rc)"
grep -q "Acme sample text for this slot" "$AV/book.html" || die "a refused patch changed the book"
"${BC[@]}" patch book.html --old "Acme sample text for this slot." --new "Real text." --count "$n_hits" --note "smoke" --project "$AV" >/dev/null || die "patch with the right count failed"
grep -q "edition 1: patched book.html ($n_hits replacements): smoke" "$AV/BRAND-STATE.md" || die "patch did not log the edition"
"${BC[@]}" book-lint --self-consistency --project "$AV" >/dev/null || die "the patched hand-authored book does not lint"
mut "$AV/book/chapters/idea.md" "## The idea" "## The idea

::: variant nav a
Option A.
:::

::: variant nav b
Option B.
:::
"
"${BC[@]}" collapse --group nav --keep a --apply --project "$AV" >/dev/null || die "collapse failed"
[ -f "$AV/removed-$BRAND_CREATOR_TODAY/book/chapters/idea.md" ] || die "collapse kept no dated copy"
grep -q "Option B" "$AV/book/chapters/idea.md" && die "the losing variant is still in the chapter"
grep -q "nav decided, kept a" "$AV/BRAND-STATE.md" || die "collapse did not record the decision"
ok "patch asserts the count and logs the edition; collapse removes the losing variant, keeps a dated copy and records it"

step "adoption, cascade, adapters, applied skill and launch: a synthetic target repository surveyed read only, check --cascade, BRAND.md and DESIGN.md (linted), the applied skill, LAUNCH.md"
command -v rg >/dev/null || die "ripgrep (rg) is needed for the adoption step: brand-creator prereq --for adoption"
AD="$SMOKE/adopt"; cp -R "$BK" "$AD"
"${BC[@]}" state --project "$AD" --record G5 "approved (smoke)" >/dev/null     # G5 and G6 are in the book's state view: record them, then rebuild the book once
"${BC[@]}" state --project "$AD" --record G6 "go (smoke)" >/dev/null
"${BC[@]}" book --project "$AD" >/dev/null && "${BC[@]}" book-lint --self-consistency --project "$AD" >/dev/null && "${BC[@]}" book-pdf --project "$AD" >/dev/null || die "the book does not rebuild after G5 and G6"
TR="$SMOKE/target-repo"; cp -R "$ROOT/tests/fixtures/target-repo" "$TR"; mkdir -p "$TR/ignored"; echo "Oldco ignored by .gitignore" > "$TR/ignored/n.txt"
tree_sha() { python3 - "$1" <<'PY'
import hashlib, sys
from pathlib import Path
r = Path(sys.argv[1]); h = hashlib.sha256()
for p in sorted(r.rglob("*")):
    if p.is_file():
        h.update(p.relative_to(r).as_posix().encode() + b"\0" + p.read_bytes())
print(h.hexdigest())
PY
}
before="$(tree_sha "$TR")"
set +e; "${BC[@]}" adoption status --project "$AD" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 2 ] || die "adoption status before any survey must be a usage error (exit $rc)"
"${BC[@]}" adoption survey --project "$AD" --repo "$TR=shop" --old-name Oldco --old-name "Old Co" --old-colour "#123456" --old-colour "#0a0a0a" >/dev/null || die "adoption survey failed"
[ "$(tree_sha "$TR")" = "$before" ] || die "the survey changed the target repository"
python3 - "$AD" <<'PY' || die "the survey result is wrong"
import json, re, sys
from pathlib import Path
p = Path(sys.argv[1]); d = json.loads((p / "adoption.json").read_text())
names = {r["file"]: r["lines"] for r in d["rows"] if r["category"] == "name"}
assert names["README.md"] == [1, 4, 6] and names["package.json"] == [2, 4, 6] and "ignored/n.txt" not in json.dumps(d), names     # counted by hand in the fixture
assert {k["file"] for k in d["kept"]} == {"CHANGELOG.md", "LICENSE", "dist/bundle.js", "package-lock.json"}
a = d["accounting"]; assert a["hits"] == a["in_rows"] + a["kept"] and a["kept"] == 4, a
assert [r["n"] for r in d["rows"]] == list(range(1, len(d["rows"]) + 1)) and len(d["pins"]) == len(d["rows"]) == d["nrows"]
md = (p / "ADOPTION.md").read_text()
assert "find the place by its content" in md and f"0 of {len(d['rows'])} rows done" in md and "## Kept, not counted" in md
assert re.findall(r"^## (.+)$", md, re.M) == ["How this list is applied", "Kept, not counted"] and "branch the owner names" in md and md.index("| # |") < md.index("## How this")
rep = json.loads((p / "assets/_checks/adoption.json").read_text())
assert [r["status"] for r in rep["results"] if r["id"] == "read-only:shop"] == ["pass"]
acc = next(r for r in rep["results"] if r["id"] == "accounting")
assert acc["status"] == "pass" and "counted again by a second ripgrep run and agree" in acc["detail"], acc
print(f"   ok: {len(d['rows'])} rows, {len(d['kept'])} kept entries, every match accounted for and name and colour lines recounted; the repository is byte-identical after the survey")
PY
NG="$SMOKE/adopt-no-g6"; cp -R "$AD" "$NG"; python3 - "$NG/BRAND-STATE.md" <<'PY'
import re, sys
f = sys.argv[1]; t = open(f).read(); n = re.sub(r'(?m)^(  G6:) .*?(\s+#.*)$', r'\1 ""\2', t); assert n != t; open(f, "w").write(n)
PY
set +e; "${BC[@]}" adoption status --project "$NG" --set 1=done >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "marking a row done must need G6 (exit $rc)"
"${BC[@]}" adoption status --project "$AD" --set 1-3=done >/dev/null || die "adoption status --set failed"
grep -q "Status: \*\*in progress\*\*. 3 of " "$AD/ADOPTION.md" || die "the status sentence does not carry the computed counts"
"${BC[@]}" adoption verify --project "$AD" >/dev/null || die "adoption verify failed on a consistent list"
ok "status needs G6, progress is stored apart from the rows, the sentence is built from the counts, verify passes"
"${BC[@]}" book --verify --project "$AD" >/dev/null 2>&1 && die "a changed adoption progress must make the built book stale"
"${BC[@]}" book --project "$AD" >/dev/null && "${BC[@]}" book-lint --self-consistency --project "$AD" >/dev/null && "${BC[@]}" book-pdf --project "$AD" >/dev/null || die "the book does not rebuild after the adoption progress changed"
python3 - "$AD" <<'PY' || die "the cover does not state adoption as far as the data back it"
import json, re, sys
p = sys.argv[1]
n = len(json.load(open(p + "/adoption.json"))["rows"])
m = re.search(r"<dt>Adoption</dt><dd>(.*?)</dd>", open(p + "/book.html").read())
assert m and m.group(1) == f"Adoption approved 2026-10-17; 3 of {n} rows done", m and m.group(1)
assert "Applied to products" not in open(p + "/book.html").read()
print(f"   ok: the cover says {m.group(1)!r}")
PY
m_pin() { python3 - "$1/adoption.json" <<'PY'
import json, sys
f = sys.argv[1]; d = json.load(open(f)); before = json.dumps(d, sort_keys=True)
d["rows"].insert(1, dict(d["rows"][0])); [r.__setitem__("n", i) for i, r in enumerate(d["rows"], 1)]
assert json.dumps(d, sort_keys=True) != before
json.dump(d, open(f, "w"), indent=2)
PY
}
m_adoc() { mut "$1/ADOPTION.md" "| 1 | done |" "| 1 | to do |"; }
for m in pin adoc; do
  d="$SMOKE/adopt-m-$m"; cp -R "$AD" "$d"; "m_$m" "$d"
  set +e; out="$("${BC[@]}" adoption verify --project "$d" 2>&1)"; rc=$?; set -e
  [ "$rc" = 1 ] || die "mutation $m: adoption verify should exit 1, got $rc"
  if [ "$m" = pin ]; then printf '%s' "$out" | grep -q "pinned" || die "mutation pin: the pins did not say so: $out"; else printf '%s' "$out" | grep -q "edited by hand" || die "mutation adoc: $out"; fi
  set +e; "${BC[@]}" check --project "$d" >/dev/null 2>&1; rc=$?; set -e
  [ "$rc" = 1 ] || die "mutation $m: check should exit 1, got $rc"
  ok "mutation $m fails adoption verify and check"
done
"${BC[@]}" check --project "$AD" --cascade Oldco >/dev/null 2>&1 || die "an old name that only the adoption records hold must warn, not fail"
python3 - "$AD/assets/_checks/check.json" <<'PY' || die "the cascade did not treat the adoption records as the work list"
import json, sys
c = next(r for r in json.load(open(sys.argv[1]))["results"] if r["id"] == "cascade:Oldco")
assert c["status"] == "warn" and c["hits"] == [] and c["recorded"] > 0, c
PY
mkdir -p "$SMOKE/parent"; echo "The family still says Oldco." > "$SMOKE/parent/README.md"
mkdir -p "$AD/qa"; printf '{"schema": 1, "also": ["../parent/README.md"]}\n' > "$AD/tools/cascade.json"
mut "$AD/book/chapters/idea.md" "## The idea" "## The idea

The old name Oldco is still here."
set +e; out="$("${BC[@]}" check --project "$AD" --cascade Oldco 2>&1)"; rc=$?; set -e
[ "$rc" = 1 ] || die "the cascade must fail when a book chapter and a parent document hold the old name (exit $rc)"
printf '%s' "$out" | grep -F "cascade:Oldco" | grep -q "book/chapters/idea.md:" || die "the cascade did not name the book chapter: $out"
printf '%s' "$out" | grep -F "cascade:Oldco" | grep -q "also:../parent/README.md:1" || die "the cascade did not name the parent document"
python3 - "$AD/book/chapters/idea.md" <<'PY'
import sys
f = sys.argv[1]; t = open(f).read(); n = t.replace("\n\nThe old name Oldco is still here.", ""); assert n != t; open(f, "w").write(n)
PY
mkdir -p "$SMOKE/removed"; mv "$AD/tools/cascade.json" "$SMOKE/removed/cascade-$$.json"
"${BC[@]}" check --project "$AD" --cascade Oldco >/dev/null 2>&1 || die "the cascade still fails after the old name was removed from the sources"
ok "check --cascade finds the old value in a book source and in a configured parent document, and passes when the sources are clean (adoption records only warn)"
mkdir -p "$AD/decisions"; python3 - "$ROOT/templates/ADR.md" "$AD/decisions/ADR-0001-name.md" <<'PY'
import sys
t = open(sys.argv[1]).read()
for old, new in (("# ADR-NNNN: (the decision in one line)", "# ADR-0001: the brand is renamed"), ("(Proposed | Accepted | Superseded by ADR-NNNN)", "Accepted"),
                 ("(Each alternative that was considered, one line each, with the reason it lost.)", "Keeping the old name Oldco: it collided in the names run.")):
    assert old in t, old; t = t.replace(old, new)
open(sys.argv[2], "w").write(t)
PY
"${BC[@]}" check --project "$AD" --cascade Oldco >/dev/null 2>&1 || die "an ADR that records the old name must not fail the cascade (decisions/ is history)"
python3 - "$AD/assets/_checks/check.json" <<'PY' || die "the cascade scope does not say it skipped decisions/"
import json, sys
res = json.load(open(sys.argv[1]))["results"]
s = next(r for r in res if r["id"] == "cascade:scope")
c = next(r for r in res if r["id"] == "cascade:Oldco")
assert "decisions," in s["detail"] and not any("decisions/" in str(h) for h in c.get("hits", [])), (s, c)
PY
ok "an ADR written from templates/ADR.md keeps the old name as a record: the cascade skips decisions/ and says so"
CB="$SMOKE/adopt-m-build"; cp -R "$AD" "$CB"
[ -f "$CB/assets/social/_build/github-social.html" ] || die "emit social left no _build html to plant a value in"
"${BC[@]}" check --project "$CB" --cascade Quxold >/dev/null 2>&1 || die "the baseline must pass before the plant (Quxold is nowhere yet)"
printf '<p>Quxold</p>\n' >> "$CB/assets/social/_build/github-social.html"
grep -q Quxold "$CB/assets/social/_build/github-social.html" || die "the plant did not apply"
set +e; out="$("${BC[@]}" check --project "$CB" --cascade Quxold 2>&1)"; rc=$?; set -e
[ "$rc" = 1 ] || die "a value left in the _build html of a social image must fail the cascade (exit $rc)"
printf '%s' "$out" | grep -F "cascade:Quxold" | grep -q "assets/social/_build/github-social.html:" || die "the cascade did not name the _build file: $out"
ok "the cascade searches _build/ html, the only text layer of a social image"
set +e; "${BC[@]}" adapters --project "$AD" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 2 ] || die "adapters without a flag must exit 2 (exit $rc)"
"${BC[@]}" staleness --write --project "$AD" >/dev/null
set +e; "${BC[@]}" adapters --project "$AD" --brand-md --design-md --primary accent >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 0 ] || die "adapters failed (exit $rc); exit 3 means @google/design.md is not installed in the data directory: run brand-creator --data <dir> setup --yes"
python3 - "$AD" <<'PY' || die "BRAND.md or DESIGN.md is wrong"
import json, re, sys
from pathlib import Path
p = Path(sys.argv[1]); b = (p / "BRAND.md").read_text(); d = (p / "DESIGN.md").read_text()
assert re.findall(r"^## (.+)$", b, re.M) == ["Strategy", "Voice", "Visual", "Governance"] and "type: master" in b and "architecture: independent" in b
assert "Sample Person" not in b and "every tool has a published spare-parts list" in b
assert '  bg: "#f9f7ee"' in d and '  bg-dark: "#0e141d"' in d and '  primary: "#007d71"' in d and "version: alpha" in d
rep = json.loads((p / "assets/_checks/adapters.json").read_text())
assert rep["status"] == "pass" and [r["status"] for r in rep["results"] if r["id"] == "design-md:lint"] == ["pass"], rep["results"]
inp = json.loads((p / "tools/inputs.json").read_text()); assert "BRAND.md" in inp["globs"] and "DESIGN.md" in inp["globs"]
PY
set +e; "${BC[@]}" staleness --project "$AD" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "the pack recorded before the adapters existed must read as stale once they do (exit $rc)"
"${BC[@]}" staleness --write --project "$AD" >/dev/null && "${BC[@]}" staleness --project "$AD" >/dev/null || die "staleness does not accept the recorded adapters"
ok "BRAND.md (four layers) and DESIGN.md (token values, linted by the pinned @google/design.md) generated; both are staleness inputs"
"${BC[@]}" book --project "$AD" >/dev/null && "${BC[@]}" book-lint --self-consistency --project "$AD" >/dev/null && "${BC[@]}" book-pdf --project "$AD" >/dev/null || die "the book does not rebuild (its proof table reads the staleness report, which the runs above rewrote)"
set +e; "${BC[@]}" applied-skill --project "$AD" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 2 ] && [ ! -e "$AD/.claude" ] || die "applied-skill without --yes must exit 2 and write nothing (exit $rc)"
"${BC[@]}" applied-skill --yes --project "$AD" >/dev/null || die "applied-skill --yes failed"
grep -q "^name: acme-brand$" "$AD/.claude/skills/acme-brand/SKILL.md" && grep -q "#007d71" "$AD/.claude/skills/acme-brand/SKILL.md" || die "the applied skill is wrong"
"${BC[@]}" check --project "$AD" >/dev/null 2>&1 || { "${BC[@]}" check --project "$AD" | grep -v PASS | tail -n 8; die "check does not pass with the adoption list, the adapters and the applied skill"; }
python3 - "$AD/assets/_checks/check.json" <<'PY' || die "check does not gate the stage-4c artefacts"
import json, sys
ids = {r["id"]: r["status"] for r in json.load(open(sys.argv[1]))["results"]}
for k in ("adoption:data", "report:adapters", "adapters:BRAND.md", "adapters:DESIGN.md", "report:applied-skill", "applied-skill:file"):
    assert ids[k] == "pass", (k, ids.get(k))
PY
d="$SMOKE/adopt-m-design"; cp -R "$AD" "$d"; mut "$d/DESIGN.md" "version: alpha" "version: alpha
# edited by hand"
set +e; "${BC[@]}" check --project "$d" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "a hand-edited DESIGN.md must fail check (exit $rc)"
ok "applied skill written only with --yes; check gates the adoption list, both adapters and the skill; a hand-edited DESIGN.md fails"
"${BC[@]}" names zqxvkrmpl granite --tlds com,io --region PL --offline "$ROOT/tests/fixtures/names/software" --project "$AD" >/dev/null || die "the offline names replay failed"
"${BC[@]}" launch-todo --project "$AD" --name zqxvkrmpl >/dev/null || die "launch-todo failed"
cp "$AD/LAUNCH.md" "$SMOKE/launch.first.md"; "${BC[@]}" launch-todo --project "$AD" --name zqxvkrmpl >/dev/null
cmp -s "$AD/LAUNCH.md" "$SMOKE/launch.first.md" || die "LAUNCH.md is not byte-identical on a second run"
python3 - "$AD/LAUNCH.md" <<'PY' || die "LAUNCH.md is wrong"
import re, sys
t = open(sys.argv[1]).read()
assert re.findall(r"^## (.+)$", t, re.M) == ["Trademark first", "Domains", "Handles and registries", "E-mail", "Deploy", "Repositories, packages and app ids", "Decisions for you"]
assert "Checked 2026-10-17, recheck before buying" in t and "| zqxvkrmpl.com | NOT-FOUND |" in t and "tmdn.org/tmview" in t
assert not re.search(r"(?i)\b(available|free|clear|cleared)\b", t) and "granite" not in t
assert len([ln for ln in t.splitlines() if ln.startswith("| shop | `")]) == 5 and "`oldco-app`" in t     # the rename list is the survey's identifiers
PY
ok "LAUNCH.md: trademark first, dated domains and handles, the survey's renames; never 'available'; byte-identical on a second run; nothing outward executed"

step "fleets (opt-in): agent and workflow lint, the fleet plan of every workflow (dry run, no model is called), the designers' snapshot guard"
"${BC[@]}" fleet-plan --check >/dev/null || { "${BC[@]}" fleet-plan --check | tail -n 8; die "fleet-plan --check failed"; }
FL="$SMOKE/fleet"; mkdir -p "$FL/repos/shop"
for w in directions review-panel naming adopt; do
  python3 - "$ROOT/tests/fixtures/fleet/$w.json" "$FL/$w.json" "$P" "$ROOT" "$BRAND_CREATOR_DATA" "$FL/repos" <<'PY'
import sys
src, out, project, plugin, data, repos = sys.argv[1:]
t = open(src).read().replace("/PROJECT", project).replace("/PLUGIN", plugin).replace("/DATA", data).replace("/REPOS", repos)
open(out, "w").write(t)
PY
  "${BC[@]}" fleet-plan "$w" --args "@$FL/$w.json" --json > "$FL/$w.plan.json" || die "fleet-plan $w refused the fixture arguments"
done
python3 - "$FL" <<'PY' || die "a fleet plan is wrong"
import json, sys
want = {"directions": 4, "review-panel": 4, "naming": 4, "adopt": 2}
for w, n in want.items():
    p = json.load(open(f"{sys.argv[1]}/{w}.plan.json"))
    assert p["agents"] == n and p["guideline"] == "small (under 5)" and not p["refused"] and not p["above_session"], (w, p)
    assert all(c["agent"].startswith("brand-creator:brand-") for c in p["calls"]), w
PY
ok "fleet-plan: directions 4, review-panel 4, naming 4, adopt 2 agents (size guideline small); every agent type exists"
set +e; "${BC[@]}" fleet-plan directions --args "@$FL/directions.json" --session-model sonnet >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "opus designers in a sonnet session must fail the plan unless args.ceiling caps them (exit $rc)"
python3 -c "import json,sys;a=json.load(open(sys.argv[1]));a['inventory']={'repos':[{'label':'shop','path':sys.argv[2]}]};json.dump(a,open(sys.argv[3],'w'))" "$FL/directions.json" "$FL/repos/shop" "$FL/directions-inv.json"
set +e; out="$("${BC[@]}" fleet-plan directions --args "@$FL/directions-inv.json" 2>&1)"; rc=$?; set -e
[ "$rc" = 1 ] && grep -q "plans 5 agents but args.approved_agents is 4" <<<"$out" || die "inventory on with 4 approved agents must be refused before any agent starts (exit $rc)"
ok "the session model is a ceiling (sonnet session: plan fails until capped); a 5-agent run with 4 approved is refused"
G="$SMOKE/fleet-guard"; cp -R "$P" "$G"
node --input-type=module - "$ROOT/scripts/fleet_plan.mjs" "$ROOT/workflows/directions.js" "$FL/directions.json" "$G" "$P" > "$FL/guard.cmds" <<'JS' || die "cannot read the designer prompt"
import { pathToFileURL } from "node:url";
import fs from "node:fs";
const [mod, wf, argsFile, guard, project] = process.argv.slice(2);
const F = await import(pathToFileURL(mod).href);
const r = await F.dryRun(wf, JSON.parse(fs.readFileSync(argsFile, "utf8")));
const p = r.calls.find((c) => c.label === "Compass").prompt;
const take = /first run (brand-creator .+?--project "[^"]+")/.exec(p)[1].split(project).join(guard);
console.log(take);
JS
take="$(head -n 1 "$FL/guard.cmds")"
grep -q -- "--ignore '\*rounds/r1/\*'" <<<"$take" || die "the designer's snapshot command has no round ignore: $take"
grep -q -- "--ignore '\*assets/_checks/\*'" <<<"$take" || die "the designer's snapshot command does not ignore the shot report (assets/_checks/): $take"
IGN=(--ignore '*rounds/r1/*' --ignore '*assets/_checks/*')   # the verify takes the same two options the prompt tells the designer to repeat
snap="$(PATH="$ROOT/bin:$PATH" bash -c "$take" | sed -n 's/.* -> //p')"; [ -s "$snap" ] || die "the designer's snapshot command wrote nothing ($take)"
mkdir -p "$G/rounds/r1/compass"; cp "$P/rounds/r1/board.html" "$G/rounds/r1/compass/board.html"
# the prompt's own TEST step: shot rewrites assets/_checks/shot.json, which must not trip the verify
"${BC[@]}" shot rounds/r1/compass/board.html --project "$G" --out "$SMOKE/fleet-guard-shots" --dsf 1 >/dev/null || die "the designer's own shot step failed on its board"
[ -s "$G/assets/_checks/shot.json" ] || die "shot wrote no report, so the guard step proves nothing"
"${BC[@]}" snapshot verify "$snap" "${IGN[@]}" --project "$G" >/dev/null || die "a board inside the designer's round plus the shot report must pass the snapshot verify"
set +e; "${BC[@]}" snapshot verify "$snap" --ignore '*rounds/r1/*' --project "$G" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "mutation check: without the _checks ignore the shot report must show as a change (exit $rc)"
printf '\n- added by a stray agent\n' >> "$G/FACTS.md"
set +e; "${BC[@]}" snapshot verify "$snap" "${IGN[@]}" --project "$G" >/dev/null 2>&1; rc=$?; set -e
[ "$rc" = 1 ] || die "a write outside the round (FACTS.md) must fail the designer's snapshot verify (exit $rc)"
ok "the designer prompt's own snapshot command: a board plus its shot report pass, an edited FACTS.md fails (and the shot report alone trips the verify without the _checks ignore)"

step "evals (opt-in behaviour cases): every scaffold builds its fixture, the verify scripts see the untouched state, the real loader reads every case; no case is run"
EV="$SMOKE/evals"; mkdir -p "$EV"; n_cases=0
for c in "$ROOT"/evals/*/; do
  name="$(basename "$c")"; case "$name" in _*|results) continue;; esac
  n_cases=$((n_cases+1)); [ -s "$c/prompt.md" ] && [ -d "$c/graders" ] || die "evals/$name: prompt.md or graders/ missing"
  if [ -f "$c/case.yaml" ]; then
    w="$EV/$name"; mkdir -p "$w"; (cd "$w" && bash "$c/scaffold.sh") || die "evals/$name: the scaffold failed"
    if [ -f "$w/BRAND-STATE.md" ]; then "${BC[@]}" state --project "$w" >/dev/null || die "evals/$name: the fixture is not a brand project"; fi
    if [ -f "$w/.eval-verify/verify.sh" ]; then
      out="$(bash "$w/.eval-verify/verify.sh")"; grep -Eq '^(ADOPTION-TARGET=UNCHANGED|GIT-STATE: COMMITS=1 STASHES=0 WORKTREES=1 BRANCHES=1)$' <<<"$out" || die "evals/$name: the verify script says '$out' on the untouched fixture"
    fi
  fi
done
[ "$n_cases" = 17 ] || die "expected 17 eval cases, found $n_cases"
ok "$n_cases cases: scaffolds ran, fixtures are brand projects, verify scripts pass on the untouched fixtures"
if command -v claude >/dev/null; then
  python3 - "$ROOT" "$EV" <<'PY' || die "the real eval loader rejected a case"
import pathlib, re, shutil, subprocess, sys
root, ev = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
plug = ev / "loader"
if plug.exists(): sys.exit("loader scratch folder exists; move it aside: " + str(plug))
(plug / ".claude-plugin").mkdir(parents=True); shutil.copy(root / ".claude-plugin/plugin.json", plug / ".claude-plugin/plugin.json")
shutil.copytree(root / "evals", plug / "evals", ignore=shutil.ignore_patterns("results"))
cases = [c for c in (plug / "evals").iterdir() if c.is_dir() and not c.name.startswith("_")]
for c in cases:   # one invalid grader per case: every case is loaded, none can run
    (c / "graders" / "zz-injected.md").write_text("---\ntype: zzz\n---\n")
r = subprocess.run(["claude", "plugin", "eval", ".", "--trust-plugin", "--ablation", "none", "--runs", "1", "--no-publish", "--max-cost-usd", "0.01", "-j", "1", "--output-dir", str(ev / "loader-out")],
                   cwd=plug, capture_output=True, text=True, timeout=180)
errs = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("\u2717")]
assert len(errs) == len(cases) and all(l.count("Invalid") == 1 for l in errs), (r.stdout + r.stderr)[-1500:]
assert "0 case(s)" in r.stdout, r.stdout[-500:]
assert re.search(r"0 case\(s\) .*\$0\.00\b", r.stdout), "the loader check must bill nothing: " + r.stdout[-300:]
PY
  ok "claude plugin eval loads every case (checked with one injected invalid grader per case, so nothing ran)"
else
  printf '   NOT VERIFIED: the claude CLI is not on PATH; the real eval loader was not run\n'
  [ "${BRAND_CREATOR_REQUIRE_ALL:-}" = 1 ] && die "claude is missing and BRAND_CREATOR_REQUIRE_ALL=1"
fi

step "state"
"${BC[@]}" state --project "$P" --require G3 >/dev/null
"${BC[@]}" state --project "$P"

printf '\nSMOKE PASSED: Acme at %s\n' "$P"
