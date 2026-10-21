"""emit android, chrome-ext, msix (the Tier B packs): structure at the spec sizes, the Android safe-zone gate, the monochrome layer, the
"UNVERIFIED, recheck" label on files built from U rows, the MSIX unplated trio, retirement, determinism, the tier gate and `check`.

Expected values are worked out by hand from the published numbers (108 dp layers, 66 dp safe zone, density factors 1, 1.5, 2, 3, 4; MSIX scale 100,
200, 400 of 44, 150, 310x150, 310, 71, 50) or are properties of the output (colour type, alpha, ink position). They are not read from the emitters. Sizes
that a test takes from platform-specs.json go through `specs`, the one table the emitters read."""
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, failing, install_fixture, make_project, mutate, mutate_json, report

import specs
from pxio import png_color_type, png_size, read_png

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]
LABEL = "UNVERIFIED, recheck"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}   # worked out by hand: px = dp x factor
MSIX_BASE = {"Square44x44Logo": (44, 44), "Square150x150Logo": (150, 150), "Wide310x150Logo": (310, 150), "Square310x310Logo": (310, 310),
             "Square71x71Logo": (71, 71), "StoreLogo": (50, 50)}
APPLIST = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256]


def emit(p, target, *extra, **kw):
    return bc("emit", target, *extra, project=p, **kw)


def manifest(p):
    return json.loads((p / "assets" / "manifest.json").read_text())


def row(p, path):
    return next(a for a in manifest(p)["artefacts"] if a["path"] == path)


@pytest.fixture
def full(acme) -> Path:
    """Acme at the Full tier with its FACTS.md (the Tier B packs are Full tier only)."""
    assert bc("state", "--set", "tier=full", project=acme).returncode == 0
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    return acme


def ink_stats(path: Path):
    """(farthest ink pixel from the centre in px, bounding box (l, t, r, b), mean luma of ink) of a PNG with alpha."""
    w, h, px = read_png(path.read_bytes())
    far = 0.0
    xs, ys, luma, n = [], [], 0.0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[(y * w + x) * 4:(y * w + x) * 4 + 4]
            if a >= 32:
                far = max(far, ((x + 0.5 - w / 2) ** 2 + (y + 0.5 - h / 2) ** 2) ** 0.5)
                xs.append(x)
                ys.append(y)
                luma += 0.2126 * r + 0.7152 * g + 0.0722 * b
                n += 1
    return far, ((min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None), (luma / n if n else None)


def alpha_at(path: Path, x: int, y: int) -> int:
    w, _h, px = read_png(path.read_bytes())
    return px[(y * w + x) * 4 + 3]


# ================================================================ spec rows

def test_the_tier_b_rows_exist_with_a_source_a_status_and_notes():
    rows = specs.load()["rows"]
    want = {"android-adaptive": "V", "android-densities": "U", "android-legacy-launcher": "U", "android-play-icon": "V", "android-feature-graphic": "R",
            "chrome-ext-icons": "V", "chrome-ext-promo": "V", "msix-assets": "V", "msix-applist": "R"}
    assert set(want) <= set(rows)
    for rid, status in want.items():
        r = rows[rid]
        assert r["status"] == status, rid
        assert r["source_url"].startswith("https://") and r["checked"] == "2026-10-17" and r["notes"], rid
        if status == "U":
            assert LABEL in r["notes"], f"{rid} is U and its notes must say so"
    # numbers worked out from the published pages
    assert specs.sizes("android-adaptive")["layer_dp"] == 108 and specs.sizes("android-adaptive")["safe_dp"] == 66
    assert specs.sizes("chrome-ext-icons")["manifest"] == [16, 32, 48, 128] and specs.sizes("msix-applist")["targetsizes"] == APPLIST


# ================================================================ gates before anything: G3 and the Full tier

def test_every_tier_b_emitter_needs_gate_g3(tmp_path):
    p = make_project(tmp_path)
    install_fixture(p)
    assert bc("tokens", project=p).returncode == 0
    assert bc("state", "--set", "tier=full", project=p).returncode == 0
    for target in ("android", "chrome-ext", "msix"):
        r = emit(p, target)
        assert r.returncode == 1 and "G3" in r.stderr, target


@pytest.mark.parametrize("target", ["android", "chrome-ext", "msix"])
def test_a_tier_below_full_is_refused_with_the_way_up_and_writes_nothing(acme, target):
    assert (acme / "BRAND-STATE.md").read_text().count("tier: quick") == 1   # the fixture is a Quick project
    r = emit(acme, target)
    assert r.returncode == 2 and "full" in r.stderr and "state --set tier=full" in r.stderr, r.stderr
    assert not (acme / "assets" / target).exists()


# ================================================================ android

def test_android_adaptive_icon_layers_density_sizes_and_xml(full):
    r = emit(full, "android")
    assert r.returncode == 0, r.stdout + r.stderr
    base = full / "assets/android/res"
    for dn, k in DENSITIES.items():
        for name, dp in (("ic_launcher_foreground", 108), ("ic_launcher_monochrome", 108), ("ic_launcher", 48), ("ic_launcher_round", 48)):
            f = base / f"mipmap-{dn}" / f"{name}.png"
            assert png_size(f.read_bytes()) == (round(dp * k), round(dp * k)), f
    root = ET.parse(base / "mipmap-anydpi-v26/ic_launcher.xml").getroot()
    assert root.tag == "adaptive-icon"
    assert [c.tag for c in root] == ["background", "foreground", "monochrome"]
    assert root.find("foreground").get(f"{ANDROID_NS}drawable") == "@mipmap/ic_launcher_foreground"
    assert root.find("monochrome").get(f"{ANDROID_NS}drawable") == "@mipmap/ic_launcher_monochrome"
    assert (base / "mipmap-anydpi-v26/ic_launcher_round.xml").read_bytes() == (base / "mipmap-anydpi-v26/ic_launcher.xml").read_bytes()
    bg = ET.parse(base / "values/ic_launcher_background.xml").getroot().find("color")
    tokens = json.loads((full / "assets/tokens/tokens.json").read_text())
    assert bg.get("name") == "ic_launcher_background" and bg.text == tokens["modes"]["light"]["color.bg"]["hex"]
    assert report(full, "emit-android")["status"] == "pass"


def test_android_foreground_and_monochrome_ink_stay_inside_the_66_dp_circle_in_the_logo_range(full):
    assert emit(full, "android").returncode == 0
    base = full / "assets/android/res"
    for dn, k in DENSITIES.items():
        for kind in ("foreground", "monochrome"):
            far, box, _luma = ink_stats(base / f"mipmap-{dn}/ic_launcher_{kind}.png")
            assert far <= 33 * k + 1, (dn, kind, far / k)     # radius of the 66 dp circle, one pixel of anti-aliasing
        w = (box[2] - box[0]) / k
        assert 0 < w <= 66, (dn, w)
    far, box, _l = ink_stats(base / "mipmap-xxxhdpi/ic_launcher_foreground.png")
    content = report(full, "emit-android")["content_dp"]
    assert 48 <= content <= 66
    # the Acme mark's viewBox is 64 square, ink 52 of 64 wide: the ink is about 52/64 of the box
    assert abs((box[2] - box[0]) / 4 - content * 52 / 64) < 1.5


def test_the_monochrome_layer_is_a_black_silhouette_the_background_is_a_colour(full):
    assert emit(full, "android").returncode == 0
    w, h, px = read_png((full / "assets/android/res/mipmap-xxxhdpi/ic_launcher_monochrome.png").read_bytes())
    ink = [px[i:i + 4] for i in range(0, len(px), 4) if px[i + 3] >= 32]
    assert ink and all(p[0] == 0 and p[1] == 0 and p[2] == 0 for p in ink)
    # the foreground is the coloured mark: more than one colour
    _w, _h, fp = read_png((full / "assets/android/res/mipmap-xxxhdpi/ic_launcher_foreground.png").read_bytes())
    assert len({tuple(fp[i:i + 3]) for i in range(0, len(fp), 4) if fp[i + 3] == 255}) >= 2


def test_legacy_icons_are_a_square_and_a_circle(full):
    assert emit(full, "android").returncode == 0
    d = full / "assets/android/res/mipmap-xxxhdpi"
    assert alpha_at(d / "ic_launcher.png", 0, 0) == 255            # the square is full bleed
    assert alpha_at(d / "ic_launcher_round.png", 0, 0) == 0        # the round icon has transparent corners
    assert alpha_at(d / "ic_launcher_round.png", 96, 96) == 255


def test_play_icon_is_a_full_opaque_square_32_bit_with_an_srgb_chunk(full):
    assert emit(full, "android").returncode == 0
    f = full / "assets/android/play/ic_launcher-playstore.png"
    data = f.read_bytes()
    assert png_size(data) == (512, 512) and png_color_type(data) == 6 and len(data) <= 1024 * 1024
    w, h, px = read_png(data)
    assert all(px[i] == 255 for i in range(3, len(px), 4)), "every pixel is opaque: a full square, Play rounds it"
    assert b"sRGB" in data and data.index(b"sRGB") < data.index(b"IDAT")
    # worked out: the mark keeps 66/108 of the square (the adaptive icon's share)
    assert report(full, "emit-android")["status"] == "pass"
    ids = {r["id"]: r["status"] for r in report(full, "emit-android")["results"]}
    assert ids["check:play icon"] == "pass" and ids["check:play icon safe zone"] == "pass"


def test_feature_graphic_is_1024_by_500_and_has_no_alpha_channel(full):
    assert emit(full, "android").returncode == 0
    data = (full / "assets/android/play/feature-graphic.png").read_bytes()
    assert png_size(data) == (1024, 500) and png_color_type(data) == 2   # colour type 2 = RGB, no alpha
    html = (full / "assets/android/_build/feature-graphic.html").read_text()
    assert "Acme" in html and "{{" not in html
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert '<body class="wordmark">' in body and 'class="lettering"' in body and "<h1>" not in body   # the drawn wordmark, not typed text


def test_the_tagline_on_the_feature_graphic_must_be_a_facts_value(full):
    r = emit(full, "android", "--tagline", "an invented line nobody confirmed")
    assert r.returncode == 1 and "FACTS.md" in r.stderr
    assert not (full / "assets/android/res").exists()


def test_android_manifest_rows_bands_and_labels(full):
    assert emit(full, "android").returncode == 0
    fg = row(full, "assets/android/res/mipmap-xxxhdpi/ic_launcher_foreground.png")
    assert fg["slot"] == "android-adaptive-foreground" and fg["size"] == "432x432" and fg["band"] == "large" and fg["resampled_by"] == "OURS"
    assert fg["specs"] == ["android-adaptive", "android-densities"] and LABEL in fg["note"] and "android-densities" in fg["note"]
    leg = row(full, "assets/android/res/mipmap-mdpi/ic_launcher_round.png")
    assert leg["size"] == "48x48" and LABEL in leg["note"] and "android-legacy-launcher" in leg["note"]
    play = row(full, "assets/android/play/ic_launcher-playstore.png")
    assert play["specs"] == ["android-play-icon"] and LABEL not in play["note"]       # a V row carries no label
    xml = row(full, "assets/android/res/mipmap-anydpi-v26/ic_launcher.xml")
    assert xml["slot"] == "android-adaptive-xml" and LABEL not in xml["note"]
    stamped = manifest(full)["specs"]
    assert stamped["android-densities"]["status"] == "U" and stamped["android-adaptive"]["status"] == "V"
    rep = report(full, "emit-android")
    labelled = [r for r in rep["results"] if r["id"].startswith("file:") and LABEL in r["label"]]
    assert len(labelled) == 5 * 4 and all("android-" in r["label"] for r in labelled)   # the layers and the legacy icons of five densities
    assert not any(LABEL in r["label"] for r in rep["results"] if r["id"].startswith("file:play/"))


def test_android_second_run_writes_nothing(full):
    assert emit(full, "android").returncode == 0
    files = sorted(p for p in (full / "assets/android").rglob("*") if p.is_file() and "_build" not in p.parts)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    r = emit(full, "android")
    assert r.returncode == 0 and " 0 written" in r.stdout
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}


def test_a_slot_that_is_no_longer_emitted_is_retired_not_deleted(full):
    assert emit(full, "android").returncode == 0
    stale = full / "assets/android/res/mipmap-ldpi/ic_launcher.png"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old density")

    def add(doc):
        doc["artefacts"].append({"path": "assets/android/res/mipmap-ldpi/ic_launcher.png", "sha256": "0" * 64, "bytes": 11, "emitter": "android", "specs": []})
    mutate_json(full / "assets/manifest.json", add)
    r = emit(full, "android")
    assert r.returncode == 0
    assert not stale.exists() and (full / "removed-2026-10-17/assets/android/res/mipmap-ldpi/ic_launcher.png").read_bytes() == b"old density"
    assert not any(a["path"] == "assets/android/res/mipmap-ldpi/ic_launcher.png" for a in manifest(full)["artefacts"])
    assert "retired:assets/android/res/mipmap-ldpi/ic_launcher.png" in {x["id"] for x in report(full, "emit-android")["results"]}


# ---- mutations: the mark outside the safe zone, a missing monochrome layer

SQUARE = '<rect width="64" height="64" fill="#0d1b2d"/>'


def test_a_mark_outside_the_safe_zone_fails_the_emit_and_writes_nothing(full):
    before = mutate(full / "assets/logo/mark.svg", '<path d="M32 6 58 54H6Z" fill="#0d1b2d"/>', SQUARE)
    assert SQUARE in (full / "assets/logo/mark.svg").read_text() and before != (full / "assets/logo/mark.svg").read_text()
    # by hand at the top of the logo range: a full square's corners are 66 x 0.707 = 46.7 dp from the centre, the circle's radius is 33
    r = emit(full, "android", "--content-dp", "66")
    assert r.returncode == 1 and "outside the 66 dp safe zone" in r.stderr, r.stderr
    assert not (full / "assets/android/res").exists() and not (full / "assets/android/play").exists()
    rep = report(full, "emit-android")
    assert rep["status"] == "fail" and "check:android safe zone" in failing(rep)
    # left to choose its own size the emit still fails: no size in 48 to 66 dp puts a square's corners inside the circle
    r = emit(full, "android")
    assert r.returncode == 1 and "does not fit the 66 dp safe zone" in r.stderr
    assert not (full / "assets/android/res").exists()


def test_content_dp_above_the_logo_range_is_a_usage_error(full):
    r = emit(full, "android", "--content-dp", "80")
    assert r.returncode == 2 and "48 to 66" in r.stderr


def test_a_mark_that_cannot_be_reduced_to_a_silhouette_needs_an_authored_monochrome_layer(full):
    mutate(full / "assets/logo/mark.svg", '<circle cx="32" cy="41" r="9" fill="#007d71"/>',
           '<defs><linearGradient id="g"><stop offset="0" stop-color="#007d71"/><stop offset="1" stop-color="#0d1b2d"/></linearGradient></defs>'
           '<circle cx="32" cy="41" r="9" fill="url(#g)"/>')
    r = emit(full, "android")
    assert r.returncode == 1 and "monochrome" in r.stderr and "--svg-mono" in r.stderr, r.stderr
    assert not (full / "assets/android/res").exists()
    # with an authored silhouette the layer is written
    sil = full / "assets/logo/mark-mono.svg"
    sil.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M32 6 58 54H6Z" fill="#000000"/></svg>')
    r = emit(full, "android", "--svg-mono", "assets/logo/mark-mono.svg")
    assert r.returncode == 0, r.stderr
    assert ink_stats(full / "assets/android/res/mipmap-xxxhdpi/ic_launcher_monochrome.png")[1] is not None


def _rewrite_manifest_hash(p: Path, rel: str) -> None:
    import hashlib
    data = (p / rel).read_bytes()

    def fix(doc):
        for a in doc["artefacts"]:
            if a["path"] == rel:
                a["sha256"], a["bytes"] = hashlib.sha256(data).hexdigest(), len(data)
    mutate_json(p / "assets/manifest.json", fix)


def test_check_fails_an_adaptive_icon_without_its_monochrome_layer(full):
    assert emit(full, "android").returncode == 0
    xml_rel = "assets/android/res/mipmap-anydpi-v26/ic_launcher.xml"
    before = mutate(full / xml_rel, '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>\n', "")
    assert "monochrome" not in (full / xml_rel).read_text() and "monochrome" in before
    _rewrite_manifest_hash(full, xml_rel)          # the file and the manifest agree: only the structural gate can see it
    r = bc("check", project=full)
    assert "[FAIL] tierb:android" in r.stdout and "no <monochrome> layer" in r.stdout and r.returncode == 1
    # the unmutated pack passes the same gate
    assert emit(full, "android").returncode == 0
    assert "[PASS] tierb:android" in bc("check", project=full).stdout


def test_check_fails_a_monochrome_layer_that_is_missing_at_one_density(full):
    assert emit(full, "android").returncode == 0
    rel = "assets/android/res/mipmap-hdpi/ic_launcher_monochrome.png"
    (full / rel).unlink()
    mutate_json(full / "assets/manifest.json", lambda d: d.update(artefacts=[a for a in d["artefacts"] if a["path"] != rel]))
    assert not (full / rel).exists()
    r = bc("check", project=full)
    assert r.returncode == 1 and "[FAIL] tierb:android" in r.stdout and rel in r.stdout


# ================================================================ the U label

@pytest.mark.parametrize("target,flipped,extra", [("android", "android-play-icon", ()), ("chrome-ext", "chrome-ext-icons", ()), ("msix", "msix-assets", ())])
def test_a_file_built_from_a_u_row_is_labelled_and_one_built_from_verified_rows_is_not(full, plugin_copy, target, flipped, extra):
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate_json(f, lambda d: d["rows"][flipped].update(status="U"))
    assert json.loads(f.read_text())["rows"][flipped]["status"] == "U"
    r = emit(full, target, *extra, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    arts = [a for a in manifest(full)["artefacts"] if a["emitter"] == target]
    on_u = [a for a in arts if flipped in a["specs"]]
    assert on_u
    for a in arts:
        u_rows = [s for s in a["specs"] if specs.row(s)["status"] == "U" or s == flipped]
        assert (LABEL in a["note"]) == bool(u_rows), (a["path"], a["specs"], a["note"])
    assert all(LABEL in a["note"] and flipped in a["note"] for a in on_u)
    rep = report(full, f"emit-{target}")
    assert any(r_["id"].startswith("file:") and LABEL in r_["label"] for r_ in rep["results"])
    assert manifest(full)["specs"][flipped]["status"] == "U"
    # and `check` reads the stamped status from the manifest and agrees
    assert "[PASS] tierb:labels" in bc("check", project=full).stdout


def test_check_fails_a_u_row_file_whose_note_lost_the_label(full):
    assert emit(full, "android").returncode == 0
    rel = "assets/android/res/mipmap-mdpi/ic_launcher_foreground.png"
    assert LABEL in row(full, rel)["note"]
    assert "[PASS] tierb:labels" in bc("check", project=full).stdout

    def drop(doc):
        for a in doc["artefacts"]:
            if a["path"] == rel:
                a["note"] = a["note"].replace(LABEL, "checked")
    mutate_json(full / "assets/manifest.json", drop)
    assert LABEL not in row(full, rel)["note"]
    r = bc("check", project=full)
    assert r.returncode == 1 and "[FAIL] tierb:labels" in r.stdout and rel in r.stdout


# ================================================================ chrome extension

def test_chrome_ext_icons_store_icon_and_promo_tiles(full):
    r = emit(full, "chrome-ext")
    assert r.returncode == 0, r.stdout + r.stderr
    base = full / "assets/chrome-ext"
    for s in (16, 32, 48, 128):
        data = (base / f"icons/icon-{s}.png").read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n" and png_size(data) == (s, s)
    # the Web Store rule, by hand: 96 px of artwork in 128, 16 px of transparent padding on every side
    _far, box, _l = ink_stats(base / "icons/icon-128.png")
    assert box[0] >= 15 and box[1] >= 15 and box[2] <= 113 and box[3] <= 113
    assert (base / "store/store-icon-128.png").read_bytes() == (base / "icons/icon-128.png").read_bytes()
    # the smaller icons use the whole canvas (no padding rule): the 48 px ink reaches its edges
    _f, box48, _l = ink_stats(base / "icons/icon-48.png")
    assert box48[0] <= 6 and box48[2] >= 42
    for name, size in (("promo-small-440x280", (440, 280)), ("promo-marquee-1400x560", (1400, 560))):
        data = (base / f"store/{name}.png").read_bytes()
        assert png_size(data) == size and png_color_type(data) == 2
    for key in ("small", "marquee"):
        body = re.sub(r"<!--.*?-->", "", (base / f"_build/promo-{key}.html").read_text(), flags=re.S)
        assert '<body class="wordmark">' in body and 'class="lettering"' in body and "<h1>" not in body, key
    doc = json.loads((base / "manifest.icons.json").read_text())
    assert doc == {"icons": {"16": "icons/icon-16.png", "32": "icons/icon-32.png", "48": "icons/icon-48.png", "128": "icons/icon-128.png"}}
    assert sorted(p.name for p in (base / "icons").iterdir()) == ["icon-128.png", "icon-16.png", "icon-32.png", "icon-48.png"]   # PNG only
    assert report(full, "emit-chrome-ext")["status"] == "pass"


def test_chrome_ext_draws_each_size_from_its_band_and_records_it(full):
    assert emit(full, "chrome-ext").returncode == 0
    assert row(full, "assets/chrome-ext/icons/icon-16.png")["band"] == "small"
    assert row(full, "assets/chrome-ext/icons/icon-48.png")["band"] == "large"
    a = row(full, "assets/chrome-ext/store/promo-small-440x280.png")
    assert a["slot"] == "chrome-web-store-promo-small" and a["size"] == "440x280" and "required" in a["note"] and a["resampled_by"] == "PAGE"
    assert all(LABEL not in x["note"] for x in manifest(full)["artefacts"] if x["emitter"] == "chrome-ext")   # every Chrome row is V


def test_chrome_ext_second_run_writes_nothing(full):
    assert emit(full, "chrome-ext").returncode == 0
    r = emit(full, "chrome-ext")
    assert r.returncode == 0 and " 0 written" in r.stdout


def test_chrome_ext_refuses_a_spec_row_that_allows_another_format(full, plugin_copy):
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate_json(f, lambda d: d["rows"]["chrome-ext-icons"]["sizes"].update(formats=["png", "webp"]))
    r = emit(full, "chrome-ext", plugin=plugin_copy)
    assert r.returncode == 1 and "PNG only" in r.stderr


# ================================================================ msix

def test_msix_base_assets_at_every_scale(full):
    r = emit(full, "msix")
    assert r.returncode == 0, r.stdout + r.stderr
    base = full / "assets/msix/Assets"
    for name, (w, h) in MSIX_BASE.items():
        for sc in (1, 2, 4):
            f = base / f"{name}.scale-{sc * 100}.png"
            assert png_size(f.read_bytes()) == (w * sc, h * sc), f
    assert report(full, "emit-msix")["status"] == "pass"


def test_msix_app_list_has_the_plain_unplated_and_lightunplated_file_for_every_size(full):
    assert emit(full, "msix").returncode == 0
    base = full / "assets/msix/Assets"
    for s in APPLIST:
        trio = [base / f"Square44x44Logo.targetsize-{s}{alt}.png" for alt in ("", "_altform-unplated", "_altform-lightunplated")]
        for f in trio:
            assert png_size(f.read_bytes()) == (s, s), f
        for f in trio[1:]:
            assert alpha_at(f, 0, 0) == 0, f"{f.name}: an unplated file must not paint its own ground"
    assert len(list(base.glob("Square44x44Logo.targetsize-*"))) == 3 * len(APPLIST)
    # the dark-theme file carries the artwork for dark grounds (lighter), the light-theme file the artwork for light grounds (darker)
    dark = ink_stats(base / "Square44x44Logo.targetsize-256_altform-unplated.png")[2]
    light = ink_stats(base / "Square44x44Logo.targetsize-256_altform-lightunplated.png")[2]
    assert dark > light + 40, (dark, light)
    assert (base / "Square44x44Logo.targetsize-256.png").read_bytes() == (base / "Square44x44Logo.targetsize-256_altform-lightunplated.png").read_bytes()


def test_msix_app_list_sizes_follow_the_band_rule(full):
    assert emit(full, "msix").returncode == 0
    assert row(full, "assets/msix/Assets/Square44x44Logo.targetsize-16_altform-unplated.png")["band"] == "small"
    assert row(full, "assets/msix/Assets/Square44x44Logo.targetsize-32_altform-lightunplated.png")["band"] == "small"
    assert row(full, "assets/msix/Assets/Square44x44Logo.targetsize-36.png")["band"] == "large"
    # the 16 px file is drawn from the coarse-grid drawing, not the fine mark shrunk
    small = (full / "assets/msix/Assets/Square44x44Logo.targetsize-16_altform-lightunplated.png").read_bytes()
    from px_lib import from_png
    from _common import rasterise_svg
    import svgtools
    grid = (full / "assets/logo/grid-mark.svg").read_text()
    want = rasterise_svg(svgtools.fit(grid, 16, 16), 16, 16)
    assert read_png(small)[2] == read_png(want)[2]


def test_the_appx_manifest_snippet_names_every_image_and_uses_the_light_ground(full):
    assert emit(full, "msix").returncode == 0
    text = (full / "assets/msix/AppxManifest.visual-elements.xml").read_text()
    root = ET.fromstring('<Package xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">' + text + "</Package>")
    assert root.find("Properties/Logo").text == "Assets\\StoreLogo.png"
    ve = root.find("{http://schemas.microsoft.com/appx/manifest/uap/windows10}VisualElements")
    tokens = json.loads((full / "assets/tokens/tokens.json").read_text())
    assert ve.get("BackgroundColor") == tokens["modes"]["light"]["color.bg"]["hex"] and ve.get("DisplayName") == "Acme"
    assert ve.get("Square44x44Logo") == "Assets\\Square44x44Logo.png" and ve.get("Square150x150Logo") == "Assets\\Square150x150Logo.png"
    tile = ve.find("{http://schemas.microsoft.com/appx/manifest/uap/windows10}DefaultTile")
    assert {k: v for k, v in tile.attrib.items()} == {"Wide310x150Logo": "Assets\\Wide310x150Logo.png", "Square71x71Logo": "Assets\\Square71x71Logo.png",
                                                      "Square310x310Logo": "Assets\\Square310x310Logo.png"}
    # the Acme FACTS.md has no description or summary row: the attribute is left out and the report says so
    assert ve.get("Description") is None
    assert "note:description" in {x["id"] for x in report(full, "emit-msix")["results"] if x["status"] == "warn"}


def test_the_appx_manifest_description_is_a_facts_value_when_there_is_one(full):
    with open(full / "FACTS.md", "a", encoding="utf-8") as fh:
        fh.write("\n| description | Acme makes dependable widgets | the owner's own words | 2026-10-17 | yes |\n")
    assert emit(full, "msix").returncode == 0
    text = (full / "assets/msix/AppxManifest.visual-elements.xml").read_text()
    assert 'Description="Acme makes dependable widgets"' in text


def test_msix_labels_follow_the_row_status(full):
    assert emit(full, "msix").returncode == 0
    arts = [a for a in manifest(full)["artefacts"] if a["emitter"] == "msix"]
    assert len(arts) == 6 * 3 + 3 * 14 + 1
    assert all(LABEL not in a["note"] for a in arts)       # msix-assets is V and msix-applist is R: nothing here is U
    assert manifest(full)["specs"]["msix-applist"]["status"] == "R"


def test_check_fails_an_app_list_size_without_its_lightunplated_file(full):
    assert emit(full, "msix").returncode == 0
    assert "[PASS] tierb:msix" in bc("check", project=full).stdout
    rel = "assets/msix/Assets/Square44x44Logo.targetsize-24_altform-lightunplated.png"
    (full / rel).unlink()
    mutate_json(full / "assets/manifest.json", lambda d: d.update(artefacts=[a for a in d["artefacts"] if a["path"] != rel]))
    assert not (full / rel).exists()
    r = bc("check", project=full)
    assert r.returncode == 1 and "[FAIL] tierb:msix" in r.stdout and "targetsize-24_altform-lightunplated.png is missing" in r.stdout and "backplate" in r.stdout


def test_check_fails_an_unplated_file_that_paints_its_own_ground(full):
    assert emit(full, "msix").returncode == 0
    rel = "assets/msix/Assets/Square44x44Logo.targetsize-48_altform-unplated.png"
    from px_lib import Img
    (full / rel).write_bytes(Img(48, 48, "#ffffff").png())
    assert alpha_at(full / rel, 0, 0) == 255
    _rewrite_manifest_hash(full, rel)
    r = bc("check", project=full)
    assert r.returncode == 1 and "[FAIL] tierb:msix" in r.stdout and "corner pixel is not transparent" in r.stdout and rel in r.stdout


def test_msix_second_run_writes_nothing(full):
    assert emit(full, "msix").returncode == 0
    r = emit(full, "msix")
    assert r.returncode == 0 and " 0 written" in r.stdout


# ================================================================ the three together, check, the chain

def test_check_reads_the_tier_b_reports_and_a_changed_mark_makes_them_stale(full):
    for target in ("android", "chrome-ext", "msix"):
        assert emit(full, target).returncode == 0, target
    r = bc("check", project=full)
    for tool in ("emit-android", "emit-chrome-ext", "emit-msix"):
        assert f"[PASS] report:{tool}" in r.stdout, tool
    for gate in ("tierb:labels", "tierb:android", "tierb:msix"):
        assert f"[PASS] {gate}" in r.stdout, gate
    spec_warns = [ln for ln in r.stdout.splitlines() if ln.startswith("[WARN] specs:")]
    assert any("android-densities" in ln and "UNVERIFIED" in ln for ln in spec_warns)
    # a mark edit makes every Tier B report stale: not verified, never a pass
    mutate(full / "assets/logo/mark.svg", 'r="9"', 'r="10"')
    r = bc("check", project=full)
    assert "[PASS] report:emit-android" not in r.stdout and r.returncode != 0


def test_the_entry_point_dispatches_the_three_targets_and_the_chain_template_lists_them():
    entry = (ROOT / "bin/brand-creator").read_text()
    assert "android|msix" in entry and "chrome-ext) py emitters/chrome_ext.py" in entry
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    assert "TARGETS+=(android chrome-ext msix)" in tpl and 'state --get tier)" = full' in tpl
    assert subprocess.run(["bash", "-n", str(ROOT / "templates/finish.sh.tpl")]).returncode == 0
    for t in ("android", "chrome-ext", "msix"):
        r = bc("emit", t, "--help")
        assert r.returncode == 0 and "usage:" in r.stdout and f"emit {t}" in r.stdout


def test_a_tier_b_emitter_is_in_check_and_the_report_names(full):
    src = (ROOT / "scripts/check.py").read_text()
    assert '"android", "chrome-ext", "msix"' in src
    assert re.search(r"emit-chrome-ext", (ROOT / "scripts/CONTRACT.md").read_text())
