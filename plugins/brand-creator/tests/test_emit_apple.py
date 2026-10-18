"""emit apple: the .icon document and its validation, actool as a hard gate per platform, the Assets.car compare, the legacy sets,
the visionOS stack, the marketing icon, the menu-bar template, DMG background, store frames and ictool previews.

Everything here needs macOS with Xcode (actool, iconutil, assetutil, ictool): on another machine these tests are skipped with the loud
NOT VERIFIED banner, and `emit apple` itself exits 3 there (tested in test_emit_platforms.py). Expected values are properties of the output
(dimensions, colour type, alpha, file names that carry their own size) or worked by hand; the vendored validator and Apple's own tools are
the independent oracles."""
import json
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, downscale_report, failing, mutate, mutate_json, report

import determinism
import specs
from pxio import png_color_type, png_size, read_png

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg, pytest.mark.requires_macos, pytest.mark.requires_actool]

TAG = "a repair guide is in every box"
VALIDATOR = ROOT / "scripts/vendor/giginet-icon-composer/validate_icon.py"


def apple(p, *extra, **kw):
    return bc("emit", "apple", *extra, project=p, **kw)


def manifest(p):
    return json.loads((p / "assets" / "manifest.json").read_text())


def row(p, path):
    return next(a for a in manifest(p)["artefacts"] if a["path"] == path)


def validate(path: Path) -> subprocess.CompletedProcess:
    """The vendored validator run as its own program (jsonschema comes from uv), not through the emitter."""
    return subprocess.run(["uv", "run", "--no-project", "--with", "jsonschema==4.26.0", "python", str(VALIDATOR), str(path)], capture_output=True, text=True)


@pytest.fixture(scope="module")
def pack(tmp_path_factory, golden):
    """One full emit (cards and legacy sets included); the tests below only read it."""
    p = tmp_path_factory.mktemp("apple") / "acme"
    shutil.copytree(golden, p)
    shutil.copy2(FIXTURES / "FACTS.md", p / "FACTS.md")
    (p / "INVENTORY.md").write_text("# Acme: surface inventory\n\n## Deployment targets\n\n- iOS: 17.0\n- macOS: 14.0\n- visionOS: 2.0\n")
    r = apple(p, "--tagline", TAG)
    assert r.returncode == 0, r.stdout + r.stderr
    return p


def files(root: Path) -> list[str]:
    return sorted(str(f.relative_to(root)) for f in root.rglob("*") if f.is_file() and not any(part.startswith("_") for part in f.relative_to(root).parts))


# ================================================================ the .icon document

def test_icon_package_is_valid_and_carries_default_dark_and_tinted_artwork(pack):
    pkg = pack / "assets/apple/AppIcon.icon"
    assert files(pkg) == ["Assets/mark-dark.svg", "Assets/mark-tinted.svg", "Assets/mark.svg", "icon.json"]
    r = validate(pkg)
    assert r.returncode == 0 and r.stdout.startswith("VALID:") and "warning" not in r.stdout, r.stdout + r.stderr   # no orphan assets either
    doc = json.loads((pkg / "icon.json").read_text())
    fills = {s.get("appearance"): s["value"]["solid"] for s in doc["fill-specializations"]}
    assert set(fills) == {None, "dark", "tinted"} and fills[None] == "srgb:0.97647,0.96863,0.93333,1.00000"   # #f9f7ee, the light color.bg
    assert fills["dark"] == "srgb:0.05490,0.07843,0.11373,1.00000" and fills["tinted"].startswith("gray:")      # #0e141d
    layer = doc["groups"][0]["layers"][0]
    assert {s.get("appearance"): s["value"] for s in layer["image-name-specializations"]} == {None: "mark.svg", "dark": "mark-dark.svg", "tinted": "mark-tinted.svg"}
    assert layer["glass"] is False and doc["supported-platforms"] == {"circles": ["watchOS"], "squares": "shared"}
    # the artwork: the light drawing keeps the light colours, dark the dark ones, tinted only greys
    svg = lambda n: (pkg / "Assets" / n).read_text()  # noqa: E731
    assert "#0d1b2d" in svg("mark.svg") and "#007d71" in svg("mark.svg") and "#f0eee7" in svg("mark-dark.svg") and "#4cd7c8" in svg("mark-dark.svg")
    grey = set(re.findall(r'fill="(#[0-9a-f]{6})"', svg("mark-tinted.svg")))
    assert len(grey) == 2 and all(h[1:3] == h[3:5] == h[5:7] for h in grey)
    for n in ("mark.svg", "mark-dark.svg", "mark-tinted.svg"):
        assert "<text" not in svg(n) and 'viewBox="0 0 1024 1024"' in svg(n)
    rep = report(pack, "emit-apple")
    assert rep["status"] == "pass" and any(x["id"] == "icon:schema" and x["status"] == "pass" for x in rep["results"])


def test_the_vendored_validator_accepts_documents_icon_composer_wrote_and_rejects_a_broken_one(tmp_path):
    for name in ("version2-complex.icon.json", "scaled-layer.icon.json"):
        f = tmp_path / name.replace(".icon.json", "") / "icon.json"
        f.parent.mkdir()
        shutil.copy2(ROOT / "tests/fixtures/giginet" / name, f)
        r = validate(f)
        assert r.returncode == 0 and "VALID" in r.stdout, (name, r.stdout, r.stderr)
    bad = tmp_path / "bad" / "icon.json"
    bad.parent.mkdir()
    shutil.copy2(ROOT / "tests/fixtures/giginet/scaled-layer.icon.json", bad)
    mutate_json(bad, lambda d: d["groups"][0]["layers"][0].__setitem__("fil", "x"))   # a typo'd key
    r = validate(bad)
    assert r.returncode == 1 and "INVALID" in r.stdout and "fil" in r.stdout


def test_the_vendored_files_carry_the_licence_and_the_notices_record_the_pinned_commit():
    v = ROOT / "scripts/vendor/giginet-icon-composer"
    assert sorted(f.name for f in v.iterdir()) == ["LICENSE", "icon-schema.json", "validate_icon.py"]
    lic = (v / "LICENSE").read_text()
    assert "Apache License" in lic and "Version 2.0, January 2004" in lic
    notes = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    assert re.search(r"commit `[0-9a-f]{40}`", notes) and "Apache-2.0" in notes and "github.com/giginet/apple-icon-composer-skill" in notes
    import hashlib
    for f in v.iterdir():
        assert hashlib.sha256(f.read_bytes()).hexdigest() in notes, f"the notices do not record the sha256 of {f.name}"
    assert json.loads((v / "icon-schema.json").read_text())["title"] == "Apple Icon Composer Icon"


def test_a_document_the_schema_rejects_stops_the_emit_before_any_compile(acme, plugin_copy):
    schema = plugin_copy / "scripts/vendor/giginet-icon-composer/icon-schema.json"
    mutate_json(schema, lambda d: d["$defs"]["layer"]["properties"].pop("glass"))   # the layer's `glass` key is now an unknown property
    r = apple(acme, "--no-cards", plugin=plugin_copy)
    assert r.returncode == 1, r.stdout + r.stderr
    rep = report(acme, "emit-apple")
    assert "icon:schema" in failing(rep)
    assert not (acme / "assets/apple/compiled").exists()
    assert any("glass" in x.get("detail", "") for x in rep["results"] if x["id"] == "icon:schema:detail")


# ================================================================ actool per platform, a hard gate

def test_actool_compiles_each_platform_and_the_fallbacks_ship(pack):
    base = pack / "assets/apple/compiled"
    assert files(base) == ["ios.renditions.json", "ios/AppIcon60x60@2x.png", "ios/AppIcon76x76@2x~ipad.png", "ios/Info-icons.plist", "macos.renditions.json",
                           "macos/AppIcon.icns", "visionos.renditions.json", "watchos.renditions.json"]
    for f in (base / "ios").glob("*.png"):   # the file name carries its own size: <pt>x<pt>@<scale>x
        m = re.match(r"AppIcon(\d+)x\1@(\d)x", f.name)
        assert png_size(f.read_bytes()) == (int(m.group(1)) * int(m.group(2)),) * 2, f.name
    plist = plistlib.loads((base / "ios/Info-icons.plist").read_bytes())
    assert plist["CFBundleIcons"]["CFBundlePrimaryIcon"]["CFBundleIconName"] == "AppIcon"
    icns = (base / "macos/AppIcon.icns").read_bytes()
    assert icns[:4] == b"icns" and int.from_bytes(icns[4:8], "big") == len(icns)
    assert not list((pack / "assets/apple").rglob("*.car")), "the Assets.car is compared by its renditions and is not shipped"


def test_compiled_rendition_lists_describe_what_the_system_will_show(pack):
    base = pack / "assets/apple/compiled"
    ios = json.loads((base / "ios.renditions.json").read_text())
    icons = [r for r in ios if r["AssetType"] == "Icon Image" and r["PixelWidth"] == 1024]
    assert {r.get("Appearance") for r in icons} == {None, "UIAppearanceDark", "ISAppearanceTintable"} and {r["Idiom"] for r in icons} == {"phone", "pad"}
    assert all(not re.search(r"[0-9A-F]{8}-[0-9A-F]{4}-", r.get("RenditionName", "")) for r in ios), "the volatile UUID is not part of the list"
    assert not any(k in r for r in ios for k in determinism.CAR_VOLATILE_KEYS)
    mac = json.loads((base / "macos.renditions.json").read_text())
    assert {r["PixelWidth"] for r in mac if r["AssetType"] == "Icon Image"} == {32, 64, 128, 256, 512, 1024}
    watch = json.loads((base / "watchos.renditions.json").read_text())
    assert any(r["AssetType"] == "Icon Image" and r["Idiom"] == "watch" for r in watch)
    vis = json.loads((base / "visionos.renditions.json").read_text())
    assert any(r["AssetType"] == "SolidImageStack" for r in vis) and len([r for r in vis if r["AssetType"] == "Image" and r["PixelWidth"] == 1024]) >= 2


def test_a_compile_that_fails_is_exit_1_with_actools_own_words(acme, plugin_copy):
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate(f, '"ios": "iphoneos"', '"ios": "nosuchos"')
    r = apple(acme, "--no-cards", plugin=plugin_copy)
    assert r.returncode == 1 and "actool failed compiling AppIcon.icon for nosuchos" in r.stderr, r.stderr
    assert not (acme / "assets/apple/compiled").exists()


def test_the_car_compare_ignores_what_changes_between_compiles_and_sees_what_matters(pack, tmp_path):
    pkg = pack / "assets/apple/AppIcon.icon"

    def compile_to(src: Path, name: str) -> Path:
        out = tmp_path / name
        out.mkdir()
        cp = subprocess.run(["xcrun", "actool", str(src), "--compile", str(out), "--platform", "iphoneos", "--minimum-deployment-target", "26.0", "--app-icon", "AppIcon",
                             "--output-partial-info-plist", str(out / "p.plist"), "--output-format", "xml1"], capture_output=True, text=True)
        assert cp.returncode == 0, cp.stdout + cp.stderr
        return out / "Assets.car"

    a, b = compile_to(pkg, "a"), compile_to(pkg, "b")
    assert a.read_bytes() != b.read_bytes()                                      # the bytes differ between two compiles of one input ...
    assert determinism.car_renditions(a) == determinism.car_renditions(b)        # ... the rendition lists do not
    other = tmp_path / "other" / "AppIcon.icon"   # actool wants the icon's name (the folder name) to match --app-icon
    shutil.copytree(pkg, other)
    mutate(other / "icon.json", "srgb:0.97647,0.96863,0.93333,1.00000", "srgb:0.10000,0.20000,0.30000,1.00000")   # another ground colour
    c = compile_to(other, "c")
    assert determinism.car_renditions(a) != determinism.car_renditions(c)        # a real change shows


def test_verify_idempotent_compares_a_real_assets_car_by_its_renditions_not_its_bytes(pack, acme):
    shutil.copytree(pack / "assets/apple/AppIcon.icon", acme / "AppIcon.icon")
    chain = ["--cmd", "bash -c 'mkdir -p {project}/assets/car && xcrun actool {project}/AppIcon.icon --compile {project}/assets/car --platform iphoneos "
                     "--minimum-deployment-target 26.0 --app-icon AppIcon --output-partial-info-plist {project}/assets/car/p.plist > /dev/null'",
             "--root", "assets/car"]
    r = bc("verify-idempotent", *chain, project=acme)
    assert r.returncode == 1 and "bytes differ between two runs" in r.stdout and "assets/car/Assets.car" in r.stdout   # the bytes of a compiled catalogue never repeat
    (acme / "qa").mkdir(exist_ok=True)
    (acme / "qa/idempotence.json").write_text(json.dumps({"schema": 1, "entries": [{"path": "assets/car/Assets.car", "reason": "actool writes a timestamp and a UUID into every catalogue",
                                                                                    "substitute": {"check": "assetutil"}}]}))
    r = bc("verify-idempotent", *chain, project=acme)
    assert r.returncode == 0, r.stdout + r.stderr   # the substitute check (equal assetutil --info rendition lists) holds on a real catalogue


def test_verify_idempotent_accepts_the_apple_chain_and_lints_what_it_wrote(pack):
    r = bc("verify-idempotent", "--cmd", "{bc} emit apple --project {project} --no-cards", "--root", "assets/apple", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(pack, "idempotence")
    assert rep["status"] == "pass" and any(x["id"] == "determinism:rules" and x["status"] == "pass" for x in rep["results"])


def test_second_emit_writes_nothing_not_even_the_compiled_outputs_or_the_cards(pack):
    before = {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in sorted((pack / "assets/apple").rglob("*")) if f.is_file() and "_" != f.parent.name[:1]}
    r = apple(pack, "--tagline", TAG)
    assert r.returncode == 0 and " 0 written" in r.stdout
    assert before == {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in before}


# ================================================================ marketing icon, visionOS stack, menu bar

def test_marketing_icon_is_flattened_rgb_with_no_alpha_channel(pack):
    f = pack / "assets/apple/marketing/AppStore-1024.png"
    data = f.read_bytes()
    assert png_size(data) == (1024, 1024) and png_color_type(data) == 2          # colour type 2 = RGB, no alpha channel at all
    w, h, px = read_png(data)
    assert tuple(px[:4]) == (0xf9, 0xf7, 0xee, 255) and all(px[i] == 255 for i in range(3, len(px), 4))   # the light ground, in every corner and everywhere
    a = row(pack, "assets/apple/marketing/AppStore-1024.png")
    assert a["qa"] == ["downscale"] and a["slot"] == "apple-marketing-icon" and a["size"] == "1024x1024"


def test_visionos_stack_has_four_levels_inside_the_safe_circle(pack):
    s = pack / "assets/apple/Assets.xcassets/AppIconVision.solidimagestack"
    assert files(s) == ["Back.solidimagestacklayer/Content.imageset/Contents.json", "Back.solidimagestacklayer/Content.imageset/back.png",
                        "Back.solidimagestacklayer/Contents.json", "Contents.json", "Front.solidimagestacklayer/Content.imageset/Contents.json",
                        "Front.solidimagestacklayer/Content.imageset/front.png", "Front.solidimagestacklayer/Contents.json"]
    stack = json.loads((s / "Contents.json").read_text())
    assert [x["filename"] for x in stack["layers"]] == ["Front.solidimagestacklayer", "Back.solidimagestacklayer"]
    img = json.loads((s / "Front.solidimagestacklayer/Content.imageset/Contents.json").read_text())["images"][0]
    assert img == {"filename": "front.png", "idiom": "vision", "scale": "2x"}
    back = (s / "Back.solidimagestacklayer/Content.imageset/back.png").read_bytes()
    front = (s / "Front.solidimagestacklayer/Content.imageset/front.png").read_bytes()
    assert png_size(back) == png_size(front) == (1024, 1024) and png_color_type(back) == 2 and png_color_type(front) == 6
    w, h, px = read_png(front)
    far = max(((i % w + 0.5 - 512) ** 2 + (i // w + 0.5 - 512) ** 2) ** 0.5 for i in range(w * h) if px[i * 4 + 3])
    assert 0 < far <= 0.9 * 512 and px[3] == 0
    assert specs.sizes("apple-visionos-stack")["layers_max"] == 3 and len(stack["layers"]) <= 3


def test_visionos_artwork_outside_the_safe_circle_fails_the_emit(acme):
    r = apple(acme, "--no-cards", "--visionos-content-fraction", "1.4")
    assert r.returncode == 1, r.stdout + r.stderr
    gate = next(x for x in report(acme, "emit-apple")["results"] if x["id"] == "check:visionOS safe circle")
    assert gate["status"] == "fail" and "lower --visionos-content-fraction" in gate["detail"]
    # the same icon with a mark that fills the square passes once the visionOS layer is drawn smaller (the circle is smaller than the square)
    why = "the system shrinks this master to 16 px"
    r = apple(acme, "--no-cards", "--master-band", "small", "--exemption", why, "--content-fraction", "0.8")
    assert r.returncode == 1 and "check:visionOS safe circle" in failing(report(acme, "emit-apple"))   # the grid mark's corners reach the circle edge at 0.8
    r = apple(acme, "--no-cards", "--master-band", "small", "--exemption", why, "--content-fraction", "0.8", "--visionos-content-fraction", "0.6")
    assert r.returncode == 0, r.stdout + r.stderr


def test_menu_bar_template_is_black_plus_alpha_at_the_spec_size(pack):
    d = pack / "assets/apple/Assets.xcassets/MenuBarTemplate.imageset"
    assert files(d) == ["Contents.json", "menubar@2x.png"]
    w, h, px = read_png((d / "menubar@2x.png").read_bytes())
    assert (w, h) == (32, 36) and px[3] == 0
    ink = [i for i in range(w * h) if px[i * 4 + 3]]
    assert ink and all(tuple(px[i * 4:i * 4 + 3]) == (0, 0, 0) for i in ink)
    assert json.loads((d / "Contents.json").read_text())["properties"] == {"template-rendering-intent": "template"}


def test_colour_sets_are_byte_copies_of_what_build_tokens_wrote(pack):
    src = pack / "assets/tokens/Colors.xcassets"
    for f in src.rglob("*"):
        if f.is_file():
            assert (pack / "assets/apple/Colors.xcassets" / f.relative_to(src)).read_bytes() == f.read_bytes()
    assert (pack / "assets/apple/Assets.xcassets/AccentColor.colorset/Contents.json").read_bytes() == (src / "accent.colorset/Contents.json").read_bytes()


# ================================================================ legacy sets, only when a target is below 26

def test_legacy_sets_are_written_for_targets_below_26(pack):
    s = pack / "assets/apple/Assets.xcassets/AppIcon.appiconset"
    doc = json.loads((s / "Contents.json").read_text())
    ios = [i for i in doc["images"] if i.get("platform") == "ios"]
    mac = [i for i in doc["images"] if i.get("idiom") == "mac"]
    assert [i["filename"] for i in ios] == ["AppIcon-iOS-light-1024.png", "AppIcon-iOS-dark-1024.png", "AppIcon-iOS-tinted-1024.png"]
    assert [i.get("appearances", [{}])[0].get("value") for i in ios] == [None, "dark", "tinted"]
    mp = specs.sizes("apple-macos-iconset")
    assert sorted((i["size"], i["scale"]) for i in mac) == sorted((f"{pt}x{pt}", f"{sc}x") for pt in mp["points"] for sc in mp["scales"]) and len(mac) == 10
    for i in mac:   # pt x scale = px
        pt, sc = int(i["size"].split("x")[0]), int(i["scale"][0])
        assert png_size((s / i["filename"]).read_bytes()) == (pt * sc,) * 2
    light = (s / "AppIcon-iOS-light-1024.png").read_bytes()
    assert png_color_type(light) == 2 and png_size(light) == (1024, 1024)                                  # opaque, no alpha
    dw, dh, dp = read_png((s / "AppIcon-iOS-dark-1024.png").read_bytes())
    assert dp[3] == 0                                                                                       # the dark variant has a transparent ground
    tw, th, tp = read_png((s / "AppIcon-iOS-tinted-1024.png").read_bytes())
    assert all(tp[i] == tp[i + 1] == tp[i + 2] for i in range(0, len(tp), 4))                               # the tinted variant is greyscale
    icns = pack / "assets/apple/legacy/AppIcon.icns"
    assert icns.read_bytes()[:4] == b"icns"
    rep = report(pack, "emit-apple")
    got = {x["id"]: x["status"] for x in rep["results"]}
    assert got["actool:legacy-iphoneos"] == "pass" and got["actool:legacy-macosx"] == "pass" and got["check:legacy icns"] == "pass"


def test_no_legacy_assets_without_a_target_or_when_every_target_is_26_or_later(acme):
    r = apple(acme, "--no-cards")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (acme / "assets/apple/Assets.xcassets/AppIcon.appiconset").exists() and not (acme / "assets/apple/legacy").exists()
    info = next(x for x in report(acme, "emit-apple")["results"] if x["id"] == "legacy")
    assert "lists no deployment targets" in info["detail"]
    r = apple(acme, "--no-cards", "--target", "iOS=26.0", "--target", "macOS=27.0")
    assert r.returncode == 0
    assert not (acme / "assets/apple/Assets.xcassets/AppIcon.appiconset").exists()
    assert "every target is 26 or later" in next(x for x in report(acme, "emit-apple")["results"] if x["id"] == "legacy")["detail"]


def test_one_legacy_platform_does_not_write_the_other(acme):
    assert apple(acme, "--no-cards", "--target", "iOS=17.0").returncode == 0
    names = [f.name for f in (acme / "assets/apple/Assets.xcassets/AppIcon.appiconset").iterdir()]
    assert "AppIcon-iOS-light-1024.png" in names and not any(n.startswith("AppIcon-mac-") for n in names)
    assert not (acme / "assets/apple/legacy").exists()


def test_a_target_flag_wins_over_the_inventory_and_a_bad_one_is_a_usage_error(acme):
    (acme / "INVENTORY.md").write_text("## Deployment targets\n\n- iOS: 17.0\n")
    assert apple(acme, "--no-cards", "--target", "iOS=26.0").returncode == 0
    assert not (acme / "assets/apple/Assets.xcassets/AppIcon.appiconset").exists()
    r = apple(acme, "--no-cards", "--target", "Android=14")
    assert r.returncode == 2 and "--target" in r.stderr


# ================================================================ DMG background and store frames

def test_dmg_background_and_layout(pack):
    d = pack / "assets/apple/dmg"
    assert files(d) == ["background.png", "background@2x.png", "layout.json"]
    assert png_size((d / "background.png").read_bytes()) == (660, 400) and png_size((d / "background@2x.png").read_bytes()) == (1320, 800)
    assert json.loads((d / "layout.json").read_text()) == {"window": [660, 400], "app": [165, 188], "applications": [495, 188]}   # 25 % and 75 % of 660, 47 % of 400
    # the ground is the brand's light ground, and the window carries only the name, the mark and the arrow (a quiet image, not a poster)
    w, h, px = read_png((d / "background.png").read_bytes())
    assert tuple(px[:3]) == (0xf9, 0xf7, 0xee)


def test_store_frames_have_the_spec_sizes_an_empty_screenshot_area_and_only_real_copy(pack):
    d = pack / "assets/apple/store"
    frames = specs.sizes("apple-store-frames")["frames"]
    assert files(d) == sorted([f"frame-{f['name']}.png" for f in frames] + ["frames.json"])
    doc = json.loads((d / "frames.json").read_text())
    for fr in frames:
        assert png_size((d / f"frame-{fr['name']}.png").read_bytes()) == (fr["width"], fr["height"])
        rect = doc[fr["name"]]["screenshot_area"]
        assert doc[fr["name"]]["size"] == [fr["width"], fr["height"]]
        assert 0 < rect["x"] and 0 < rect["y"] and rect["x"] + rect["w"] < fr["width"] and rect["y"] + rect["h"] < fr["height"]
        w, h, px = read_png((d / f"frame-{fr['name']}.png").read_bytes())
        cx, cy = rect["x"] + rect["w"] // 2, rect["y"] + rect["h"] // 2
        inside = tuple(px[(cy * w + cx) * 4:(cy * w + cx) * 4 + 3])
        assert inside == (0xf9, 0xf7, 0xee), f"{fr['name']}: the screenshot area is not empty ground"   # no invented interface inside it
    html = re.sub(r"<!--.*?-->", "", (pack / "assets/apple/_build/frame-iphone.html").read_text(), flags=re.S)   # the template's own comment explains what it never draws
    assert TAG in html and "Acme" in html and "★" not in html and "rating" not in html.lower() and html.count("<p>") == 1


def test_store_frame_copy_must_be_a_facts_value_and_none_is_invented(acme):
    r = apple(acme, "--tagline", "the best tools in the world")
    assert r.returncode == 1 and "not a value in FACTS.md" in r.stderr
    r = apple(acme)   # no tagline: no copy, and the report says nothing was invented
    assert r.returncode == 0, r.stdout + r.stderr
    assert "<p></p>" in (acme / "assets/apple/_build/frame-iphone.html").read_text()
    assert any(x["id"] == "frames:copy" for x in report(acme, "emit-apple")["results"])


def test_no_cards_skips_the_chromium_outputs_and_says_so(acme):
    r = apple(acme, "--no-cards")
    assert r.returncode == 0
    assert not (acme / "assets/apple/dmg").exists() and not (acme / "assets/apple/store").exists()
    assert any(x["id"] == "cards" and "--no-cards" in x["detail"] for x in report(acme, "emit-apple")["results"])


# ================================================================ bands, downscale, previews

def test_a_coarse_grid_master_needs_an_exemption_and_is_recorded(acme):
    r = apple(acme, "--no-cards", "--master-band", "small")
    assert r.returncode == 1 and "--exemption" in r.stderr and not (acme / "assets/apple").exists()
    why = "the system shrinks this one master to 16 px; the coarse-grid drawing keeps the accent"
    r = apple(acme, "--no-cards", "--master-band", "small", "--exemption", why)
    assert r.returncode == 0, r.stdout + r.stderr
    for path in ("assets/apple/AppIcon.icon/Assets/mark.svg", "assets/apple/marketing/AppStore-1024.png", "assets/apple/compiled/ios/AppIcon60x60@2x.png"):
        a = row(acme, path)
        assert a["band"] == "small" and a["exemption"] == why, path
    assert "#007d71" in (acme / "assets/apple/AppIcon.icon/Assets/mark.svg").read_text()
    assert "[PASS] manifest:bands" in bc("check", project=acme).stdout


def test_the_system_downscale_gate_sees_the_difference_between_the_fine_vector_and_the_grid_master(acme):
    # the fine vector drawn at the default 0.62 and the grid master at 0.62: at 16 px the grid master's four accent cells are 3.97 px wide (fails);
    # drawn at 0.8 they are 5.1 px wide (passes): worked by hand from the 10-cell grid, measured by sips -z
    why = "the system shrinks this master to 16 px"
    assert apple(acme, "--no-cards", "--master-band", "small", "--exemption", why, "--content-fraction", "0.62").returncode == 0
    r = bc("downscale", "--source", "assets/apple/marketing/AppStore-1024.png", project=acme)
    assert r.returncode == 1 and "downscale:16px" in failing(downscale_report(acme, "assets/apple/marketing/AppStore-1024.png"))
    assert apple(acme, "--no-cards", "--master-band", "small", "--exemption", why, "--content-fraction", "0.8",
                 "--visionos-content-fraction", "0.6").returncode == 0
    r = bc("downscale", "--source", "assets/apple/marketing/AppStore-1024.png", project=acme)
    assert r.returncode == 0, r.stdout
    rep = downscale_report(acme, "assets/apple/marketing/AppStore-1024.png")
    assert rep["status"] == "pass" and "sips" in rep["renderer"]


def test_a_passing_report_on_another_master_does_not_make_check_green_for_a_failing_apple_master(acme):
    why = "the system shrinks this master to 16 px"
    master = "assets/apple/marketing/AppStore-1024.png"
    assert apple(acme, "--no-cards", "--master-band", "small", "--exemption", why, "--content-fraction", "0.62").returncode == 0
    asking = [a for a in manifest(acme)["artefacts"] if "downscale" in a.get("qa", [])]
    assert asking and {a["downscale_source"] for a in asking} == {master}   # every row that asks names the one master the system shrinks
    assert bc("downscale", "--source", master, project=acme).returncode == 1                       # the shipped master fails at 16 px
    assert bc("downscale", "--source", "assets/logo/grid-mark-master.png", project=acme).returncode == 0   # another file passes
    r = bc("check", project=acme)
    res = report(acme, "check")
    from _common import downscale_report_tool
    assert r.returncode == 1 and f"report:{downscale_report_tool(master)}" in failing(res)


def test_the_deployment_targets_file_is_an_input_of_the_apple_report(acme):
    (acme / "INVENTORY.md").write_text("# Inventory\n\n## Deployment targets\n\n- iOS: 17.0\n")
    why = "the system shrinks this master to 16 px"
    assert apple(acme, "--no-cards", "--master-band", "small", "--exemption", why).returncode == 0
    assert "INVENTORY.md" in [i["path"] for i in report(acme, "emit-apple")["inputs"]]
    assert "qa/rules.json" in [i["path"] for i in report(acme, "emit-apple")["inputs"]]
    paths = [i["path"] for i in report(acme, "emit-apple")["inputs"]]
    assert len(paths) == len(set(paths))


def test_no_cards_keeps_the_cards_and_a_dropped_deployment_target_retires_its_legacy_set(acme):
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    (acme / "INVENTORY.md").write_text("# Inventory\n\n## Deployment targets\n\n- iOS: 17.0\n")
    why = "the system shrinks this master to 16 px"
    args = ("--master-band", "small", "--exemption", why, "--tagline", TAG)
    assert apple(acme, *args).returncode == 0
    cards = [a["path"] for a in manifest(acme)["artefacts"] if a["path"].startswith(("assets/apple/dmg/", "assets/apple/store/"))]
    legacy = [a["path"] for a in manifest(acme)["artefacts"] if "AppIcon.appiconset/AppIcon-iOS" in a["path"]]
    assert cards and legacy
    assert apple(acme, "--no-cards", *args).returncode == 0   # skipped on purpose: the cards of the earlier run stay
    assert all((acme / c).is_file() for c in cards) and not set(report(acme, "emit-apple")["retired"]) & set(cards)
    assert all(any(a["path"] == c for a in manifest(acme)["artefacts"]) for c in cards)
    # the repo's minimum iOS is now 26: no legacy set is a slot any more, so the earlier one is moved out
    (acme / "INVENTORY.md").write_text("# Inventory\n\n## Deployment targets\n\n- iOS: 26.0\n")
    assert apple(acme, "--no-cards", *args).returncode == 0
    assert not [p for p in legacy if (acme / p).exists()] and not [a for a in manifest(acme)["artefacts"] if a["path"] in legacy]
    assert all((acme / "removed-2026-10-17" / p).is_file() for p in legacy)
    assert set(report(acme, "emit-apple")["retired"]) >= set(legacy) and not set(report(acme, "emit-apple")["retired"]) & set(cards)


def test_ictool_previews_are_never_shipped_and_watchos_is_exported_at_its_own_size(acme):
    assert apple(acme, "--no-cards", "--previews").returncode == 0
    pv = acme / "assets/apple/_preview"
    names = sorted(f.name for f in pv.glob("*.png"))
    assert len(names) == 18 and "iOS-Default.png" in names and "watchOS-ClearDark.png" in names
    assert png_size((pv / "iOS-Dark.png").read_bytes()) == (1024, 1024) and png_size((pv / "macOS-TintedLight.png").read_bytes()) == (1024, 1024)
    assert png_size((pv / "watchOS-Default.png").read_bytes()) == (1088, 1088) == (specs.sizes("apple-app-icon")["watchos_px"],) * 2
    assert not [a for a in manifest(acme)["artefacts"] if "_preview" in a["path"]]
    r = apple(acme, "--no-cards")   # without the flag nothing is rendered and nothing is announced
    assert not any(x["id"] == "previews" for x in report(acme, "emit-apple")["results"])


def test_check_gates_the_apple_pack_and_asks_for_the_downscale_report(pack):
    out = bc("check", project=pack).stdout
    assert "[PASS] report:emit-apple" in out and "[PASS] mark_lint:assets/apple/AppIcon.icon/Assets/mark.svg" in out
    assert re.search(r"\[(SKIP|PASS|FAIL)\] report:downscale", out)   # the rows marked qa: downscale ask for it; it is not assumed
