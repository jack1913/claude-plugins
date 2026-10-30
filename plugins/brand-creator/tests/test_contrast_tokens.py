"""build_tokens (DTCG to css/json/swift/android/colorset) and contrast, with mutation tests."""
import json
import re
import shutil
import subprocess
import sys

import pytest
from helpers import ROOT, android_sdk, bc, failing, make_project, install_fixture, mutate, mutate_json, report

pytestmark = pytest.mark.requires_setup


@pytest.fixture
def proj(tmp_path):
    p = make_project(tmp_path)
    install_fixture(p, logo=True, board=False)
    return p


def tokens(p, *extra):
    return bc("tokens", *extra, project=p)


def contrast(p, *extra):
    return bc("contrast", *extra, project=p)


def hexes(text):
    return re.findall(r"#[0-9a-fA-F]{6}", text)


# ---------------------------------------------------------------- tokens

def test_tokens_build_all_outputs_and_pass(proj):
    r = tokens(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    out = proj / "assets" / "tokens"
    for f in ("tokens.css", "tokens.json", "swift/BrandColors.swift", "android/values/colors.xml",
              "android/values-night/colors.xml", "Colors.xcassets/Contents.json", "Colors.xcassets/bg.colorset/Contents.json"):
        assert (out / f).is_file(), f
    rep = report(proj, "tokens")
    assert rep["status"] == "pass"
    assert {r["id"] for r in rep["results"]} >= {"hex-equals-oklch", "style-dictionary", "modes-parity", "pairs", "round-trip"}


def test_independent_round_trip_of_every_output(proj):
    """Parse the emitted files with code that shares nothing with build_tokens and compare with tokens.json."""
    assert tokens(proj).returncode == 0
    out = proj / "assets" / "tokens"
    tj = json.loads((out / "tokens.json").read_text())
    prim = {k: v["hex"] for k, v in tj["primitives"].items()}
    # CSS: primitives as hex, semantic through var()
    css = (out / "tokens.css").read_text()
    for k, h in prim.items():
        assert re.search(rf"--{k.replace('.', '-')}: {h};", css), k
    assert "var(--color-paper)" in css and 'data-theme="dark"' in css and "prefers-color-scheme: dark" in css
    assert "@supports (color: oklch(0 0 0))" in css and "oklch(0.975 0.012 95)" in css
    # Android
    for folder, mode in (("values", "light"), ("values-night", "dark")):
        xml = (out / "android" / folder / "colors.xml").read_text()
        got = dict(re.findall(r'<color name="(\w+)">(#[0-9A-F]{6})</color>', xml))
        for k, v in tj["modes"][mode].items():
            assert got["brand_" + k.split(".", 1)[1].replace("-", "_")].lower() == v["hex"], (mode, k)
    # colorsets
    for k, v in tj["modes"]["light"].items():
        name = k.split(".", 1)[1]
        cs = json.loads((out / "Colors.xcassets" / f"{name}.colorset" / "Contents.json").read_text())
        light, dark = cs["colors"][0], cs["colors"][1]
        assert "appearances" not in light and dark["appearances"] == [{"appearance": "luminosity", "value": "dark"}]
        as_hex = lambda c: "#" + "".join(f"{int(c['color']['components'][ch], 16):02x}" for ch in ("red", "green", "blue"))  # noqa: E731
        assert as_hex(light) == v["hex"] and as_hex(dark) == tj["modes"]["dark"][k]["hex"]
    # Swift
    swift = (out / "swift" / "BrandColors.swift").read_text()
    m = re.search(r"static let paper = Color\(\.sRGB, red: ([\d.]+), green: ([\d.]+), blue: ([\d.]+)", swift)
    assert "#" + "".join(f"{round(float(x) * 255):02x}" for x in m.groups()) == prim["color.paper"]
    assert 'public static let textMuted' not in swift and 'public static let muted = Color("muted")' in swift


def test_pairs_and_apca_are_in_tokens_json(proj):
    assert tokens(proj).returncode == 0
    tj = json.loads((proj / "assets" / "tokens" / "tokens.json").read_text())
    assert len(tj["pairs"]) == 6
    p0 = tj["pairs"][0]
    assert p0["modes"]["light"]["apca_lc"] > 90 and p0["modes"]["dark"]["apca_lc"] < -90  # APCA is polarity aware
    assert "not a W3C Standard" in tj["$format"]


def test_stored_hex_must_equal_the_gamut_mapped_oklch(proj):
    p = proj / "tokens" / "primitives.tokens.json"
    doc = json.loads(p.read_text())
    original = doc["color"]["ink"]["$value"]["hex"]
    mutate(p, f'"hex": "{original}"', '"hex": "#123456"')
    r = tokens(proj)
    assert r.returncode == 1 and "hex-equals-oklch" in failing(report(proj, "tokens"))
    assert "--fix-hex" in r.stdout
    assert not (proj / "assets" / "tokens" / "tokens.css").exists()  # nothing is emitted from invalid sources
    # the explicit opt-in repairs it, and only then
    r = tokens(proj, "--fix-hex")
    assert r.returncode == 0, r.stdout
    assert json.loads(p.read_text())["color"]["ink"]["$value"]["hex"] == original


def test_missing_hex_is_an_error_not_a_silent_default(proj):
    p = proj / "tokens" / "primitives.tokens.json"
    doc = json.loads(p.read_text())
    original = doc["color"]["paper"]["$value"]["hex"]
    mutate(p, f'"hex": "{original}"', '"hex": ""')
    r = tokens(proj)
    assert r.returncode == 1 and "hex is missing" in r.stdout


def test_light_and_dark_must_define_the_same_tokens(proj):
    mutate_json(proj / "tokens" / "semantic.dark.tokens.json", lambda d: d["color"].pop("line"))
    r = tokens(proj)
    assert r.returncode == 1 and "modes-parity" in failing(report(proj, "tokens"))
    assert "line missing in dark" in r.stdout


def test_broken_reference_fails_loudly(proj):
    mutate(proj / "tokens" / "semantic.light.tokens.json", "{color.paper}", "{color.nope}")
    r = tokens(proj)
    assert r.returncode == 1 and "style-dictionary" in failing(report(proj, "tokens"))


def test_missing_source_file_is_a_gate_failure(proj):
    (proj / "tokens" / "semantic.dark.tokens.json").rename(proj / "tokens" / "gone.bak")
    r = tokens(proj)
    assert r.returncode == 1 and "semantic.dark.tokens.json" in r.stderr


def test_check_mode_detects_stale_outputs(proj):
    assert tokens(proj).returncode == 0
    assert tokens(proj, "--check").returncode == 0
    css = proj / "assets" / "tokens" / "tokens.css"
    mutate(css, "--color-ink:", "--color-ink-edited:")
    r = tokens(proj, "--check")
    assert r.returncode == 1 and "outputs-current" in failing(report(proj, "tokens"))
    assert tokens(proj).returncode == 0  # regenerating repairs it
    assert tokens(proj, "--check").returncode == 0


def test_build_is_put_on_byte_change(proj):
    assert tokens(proj).returncode == 0
    f = proj / "assets" / "tokens" / "tokens.css"
    m1 = f.stat().st_mtime_ns
    assert tokens(proj).returncode == 0
    assert f.stat().st_mtime_ns == m1


def test_out_of_gamut_oklch_gets_a_valid_in_gamut_hex(proj):
    p = proj / "tokens" / "primitives.tokens.json"
    mutate_json(p, lambda d: d["color"]["teal"]["$value"].__setitem__("components", [0.9, 0.4, 30]))
    r = tokens(proj)
    assert r.returncode == 1  # stored hex no longer matches
    assert tokens(proj, "--fix-hex").returncode == 0
    h = json.loads(p.read_text())["color"]["teal"]["$value"]["hex"]
    assert re.fullmatch(r"#[0-9a-f]{6}", h)


MOTION_CURVES = {"standard": [0.2, 0, 0, 1], "bounce": [0.34, 1.56, 0.64, 1]}   # the second overshoots: y above 1
MOTION_DURATIONS = {"base": (320, "ms"), "slow": (0.64, "s")}                    # a duration in each unit DTCG allows


def add_motion(p):
    def groups(d):
        d["motion"] = {"$type": "duration", **{k: {"$value": {"value": v, "unit": u}} for k, (v, u) in MOTION_DURATIONS.items()}}
        d["easing"] = {"$type": "cubicBezier", **{k: {"$value": c} for k, c in MOTION_CURVES.items()}}
    mutate_json(p / "tokens" / "primitives.tokens.json", groups)


def test_independent_round_trip_of_the_motion_outputs(proj):
    """Read the CSS, Swift and Android motion files with code that shares nothing with build_tokens (regular expressions here, an XML parser for
    Android) and compare them with the numbers written in the DTCG sources."""
    import xml.etree.ElementTree as ET
    add_motion(proj)
    assert tokens(proj).returncode == 0
    out = proj / "assets" / "tokens"
    css = (out / "tokens.css").read_text()
    for k, (value, unit) in MOTION_DURATIONS.items():
        assert f"--motion-{k}: {value}{unit};" in css, k
    for k, c in MOTION_CURVES.items():
        m = re.search(rf"--easing-{k}: cubic-bezier\(([^)]*)\);", css)
        assert m and [float(x) for x in m.group(1).split(",")] == c, k
    swift = (out / "swift" / "BrandMotion.swift").read_text()
    for k, (value, unit) in MOTION_DURATIONS.items():
        m = re.search(rf"static let {k}: Double = ([\d.]+)\n", swift)
        assert m and round(float(m.group(1)) * 1000, 6) == value * (1000 if unit == "s" else 1), k
    for k, c in MOTION_CURVES.items():
        m = re.search(rf"static func {k}\(duration: Double\) -> Animation \{{ Animation\.timingCurve\(([^)]*), duration: duration\) \}}", swift)
        assert m and [float(x) for x in m.group(1).split(",")] == c, k
    ints = {e.get("name"): e.text for e in ET.parse(out / "android" / "values" / "motion.xml").getroot().iter("integer")}
    assert ints["brand_motion_base"] == "320" and ints["brand_motion_slow"] == "640" and ints["brand_duration_fast"] == "150"
    ns = "{http://schemas.android.com/apk/res/android}"
    for k, c in MOTION_CURVES.items():
        root = ET.parse(out / "android" / "interpolator" / f"brand_easing_{k}.xml").getroot()
        assert root.tag == "pathInterpolator", k
        assert [float(root.get(ns + a)) for a in ("controlX1", "controlY1", "controlX2", "controlY2")] == c, k
    tj = json.loads((out / "tokens.json").read_text())
    assert tj["motion"]["curves"] == {f"easing.{k}": c for k, c in MOTION_CURVES.items()}
    assert tj["motion"]["durations_ms"] == {"duration.fast": 150, "motion.base": 320, "motion.slow": 640}


def test_the_starter_tokens_build_with_their_layout_slots(tmp_path):
    """The three starter files, copied as they are, build: the layout slots (spacing, radius, container, gutter, breakpoints, line height,
    tracking) reach tokens.css and tokens.json (`other`) and no other output; tracking is a number in em."""
    p = make_project(tmp_path)
    (p / "tokens").mkdir(exist_ok=True)
    for f in (ROOT / "templates" / "tokens").glob("*.tokens.json"):
        shutil.copy2(f, p / "tokens" / f.name)
    assert len(list((p / "tokens").glob("*.tokens.json"))) == 3
    r = tokens(p)
    assert r.returncode == 0, r.stdout + r.stderr
    out = p / "assets" / "tokens"
    css = (out / "tokens.css").read_text()
    for decl in ("--space-1: 4px;", "--space-8: 64px;", "--radius-pill: 999px;", "--layout-container: 1200px;", "--layout-gutter: 24px;",
                 "--breakpoint-sm: 640px;", "--breakpoint-xl: 1280px;", "--leading-display: 1.1;", "--leading-body: 1.5;",
                 "--tracking-display: -0.01;", "--tracking-body: 0;"):
        assert decl in css, decl
    other = json.loads((out / "tokens.json").read_text())["other"]
    assert {k: other[k] for k in ("space.1", "radius.md", "layout.container", "breakpoint.lg", "leading.display", "tracking.display")} == {
        "space.1": "4px", "radius.md": "8px", "layout.container": "1200px", "breakpoint.lg": "1024px", "leading.display": "1.1",
        "tracking.display": "-0.01"}
    assert not any(k.split(".")[0] in ("space", "radius", "layout", "breakpoint", "leading", "tracking")
                   for k in json.loads((out / "tokens.json").read_text())["motion"]["durations_ms"])     # none of them is a duration
    for f in (out / "swift").glob("*.swift"):       # a dimension or number token reaches CSS and tokens.json only
        assert not any(w in f.read_text().lower() for w in ("breakpoint", "leading", "tracking", "radius")), f
    for f in (out / "android" / "values").glob("*.xml"):
        assert not any(w in f.read_text() for w in ("brand_space", "brand_radius", "brand_leading", "brand_tracking")), f


def test_the_starter_tokens_pass_contrast_with_the_text_on_accent_and_focus_pairs(tmp_path):
    """The three starter files, copied as they are, pass `contrast` in both schemes, and that includes the two pairs for text on the accent
    and for the focus ring; the tokens report carries the starter's proposal for the text grounds (named by nobody yet)."""
    p = make_project(tmp_path)
    (p / "tokens").mkdir(exist_ok=True)
    for f in (ROOT / "templates" / "tokens").glob("*.tokens.json"):
        shutil.copy2(f, p / "tokens" / f.name)
    assert tokens(p).returncode == 0
    r = contrast(p, "--skip-marks")                       # the starter has no logo artwork to check
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(p, "contrast")
    rows = {x["id"]: x for x in rep["results"]}
    for mode in ("light", "dark"):
        for pair in ("color.on-accent/color.accent", "color.focus/color.bg"):
            assert rows[f"{mode}:{pair}"]["status"] == "pass", (mode, pair)
    assert [x["id"] for x in rep["results"] if x["status"] in ("fail", "warn")] == ["grounds:named"]   # the proposal for the grounds is the one thing to say
    assert all(x["status"] == "pass" for x in rep["results"] if x["id"].startswith("grounds:") and x["id"] != "grounds:named")
    grounds = json.loads((p / "assets" / "tokens" / "tokens.json").read_text())["grounds"]
    assert grounds["named_by_owner"] == "" and grounds["list"][0]["ground"] == "color.bg"


def test_a_starter_kept_entry_in_the_primitives_changes_no_output(tmp_path):
    """The owner's record of the starter values they kept (`check` reads it from G4 on) sits in $extensions of the primitives: the build skips it, and every output is
    byte for byte what it was."""
    p = make_project(tmp_path)
    (p / "tokens").mkdir(exist_ok=True)
    for f in (ROOT / "templates" / "tokens").glob("*.tokens.json"):
        shutil.copy2(f, p / "tokens" / f.name)
    assert tokens(p).returncode == 0
    out = p / "assets" / "tokens"
    before = {f.relative_to(out): f.read_bytes() for f in out.rglob("*") if f.is_file()}
    kept = {"decided": "2026-10-30 keep the quick duration as it is", "paths": ["motion.quick"]}
    mutate_json(p / "tokens" / "primitives.tokens.json", lambda d: d.__setitem__("$extensions", {"brand-creator": {"starter-kept": kept}}))
    r = tokens(p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert {f.relative_to(out): f.read_bytes() for f in out.rglob("*") if f.is_file()} == before and "--tracking-display: -0.01;" in (out / "tokens.css").read_text()


@pytest.mark.requires_aapt2
def test_aapt2_compiles_and_links_the_android_motion_files(proj, tmp_path):
    """The XML parser above reads the values back; aapt2, the Android build's own resource compiler, says they are valid resources for minSdk 21 (an
    <integer> that does not fit 32 bits, or an attribute pathInterpolator does not have, fails here and nowhere else)."""
    add_motion(proj)
    assert tokens(proj).returncode == 0
    aapt2, jar = android_sdk()
    manifest = tmp_path / "AndroidManifest.xml"
    manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.brand">'
                        '<uses-sdk android:minSdkVersion="21"/></manifest>\n')

    def build(res, name):
        flat, gen = tmp_path / f"{name}.zip", tmp_path / f"{name}-gen"
        r = subprocess.run([str(aapt2), "compile", "--dir", str(res), "-o", str(flat)], capture_output=True, text=True)
        if r.returncode == 0:
            r = subprocess.run([str(aapt2), "link", "-I", str(jar), "--manifest", str(manifest), "-o", str(tmp_path / f"{name}.apk"), "--java", str(gen), str(flat)],
                               capture_output=True, text=True)
        return r, gen

    res = proj / "assets" / "tokens" / "android"
    r, gen = build(res, "ok")
    assert r.returncode == 0, r.stdout + r.stderr
    rjava = next(gen.rglob("R.java")).read_text()
    for name in ("brand_motion_base", "brand_motion_slow", "brand_duration_fast", "brand_easing_standard", "brand_easing_bounce"):
        assert re.search(rf"\b{name}\s*=", rjava), name                    # R.integer.* and R.interpolator.* exist for every token
    bad = tmp_path / "bad"
    shutil.copytree(res, bad)
    mutate(bad / "values" / "motion.xml", ">320<", ">3000000000<")      # the same commands refuse an integer that does not fit: the check can fail
    r, _ = build(bad, "bad")
    assert r.returncode != 0 and "integer" in r.stderr.lower(), r.stdout + r.stderr


@pytest.mark.requires_macos
@pytest.mark.requires_actool
def test_the_generated_motion_swift_typechecks_for_macos_and_ios_13(proj):
    """Animation.timingCurve(_:_:_:_:duration:) with the duration in seconds is what the Swift file calls; the compiler, not the round trip, says it is valid."""
    add_motion(proj)
    assert tokens(proj).returncode == 0
    swift = proj / "assets" / "tokens" / "swift" / "BrandMotion.swift"
    paths = {}
    for sdk in ("macosx", "iphoneos"):
        found = subprocess.run(["xcrun", "--sdk", sdk, "--show-sdk-path"], capture_output=True, text=True)
        assert found.returncode == 0, f"the {sdk} SDK is not installed: {found.stderr}"
        paths[sdk] = found.stdout.strip()

    def typecheck(sdk, *extra):
        return subprocess.run(["xcrun", "swiftc", "-typecheck", "-sdk", paths[sdk], *extra, str(swift)], capture_output=True, text=True)

    for sdk, extra in (("macosx", []), ("iphoneos", ["-target", "arm64-apple-ios13.0"])):
        r = typecheck(sdk, *extra)
        assert r.returncode == 0, f"{sdk}: {r.stderr}"
    def keywords(d):   # names that are Swift keywords are escaped, so they compile too
        d["motion"]["Self"] = {"$value": {"value": 50, "unit": "ms"}}
        d["easing"]["repeat"] = {"$value": [0.1, 0, 1, 1]}
    mutate_json(proj / "tokens" / "primitives.tokens.json", keywords)
    assert tokens(proj).returncode == 0 and "`Self`" in swift.read_text() and "`repeat`" in swift.read_text()
    r = typecheck("macosx")
    assert r.returncode == 0, r.stderr
    mutate(swift, "timingCurve", "timingCurveX")        # the same command refuses a call that does not exist: the check can fail
    r = typecheck("macosx")
    assert r.returncode != 0 and "timingCurveX" in r.stderr


@pytest.mark.requires_macos
@pytest.mark.requires_actool
def test_swift_typechecks_and_actool_compiles_the_colorsets(proj, tmp_path):
    assert tokens(proj).returncode == 0
    out = proj / "assets" / "tokens"
    sdk = subprocess.run(["xcrun", "--sdk", "macosx", "--show-sdk-path"], capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["xcrun", "swiftc", "-typecheck", "-sdk", sdk, str(out / "swift" / "BrandColors.swift")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    dest = tmp_path / "compiled"
    dest.mkdir()
    r = subprocess.run(["xcrun", "actool", str(out / "Colors.xcassets"), "--compile", str(dest), "--platform", "macosx",
                        "--minimum-deployment-target", "13.0", "--output-format", "human-readable-text"], capture_output=True, text=True)
    assert r.returncode == 0 and "error" not in (r.stdout + r.stderr).lower(), r.stdout + r.stderr
    assert (dest / "Assets.car").is_file()


# ---------------------------------------------------------------- contrast

def test_contrast_passes_and_reports_four_kinds_of_result(proj):
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 0, r.stdout
    rep = report(proj, "contrast")
    sections = {x["section"] for x in rep["results"]}
    assert sections == {"wcag-ui", "brand-rule", "touching-pairs", "grounds"}      # the fixture names no grounds: the one grounds row is a warning, below
    assert [(x["id"], x["status"]) for x in rep["results"] if x["section"] == "grounds"] == [("grounds:named", "warn")]
    labels = {x["label"] for x in rep["results"] if x["section"] == "brand-rule"}
    assert all("brand rule (logos WCAG-exempt)" in lab for lab in labels)
    pair_rows = [x for x in rep["results"] if x["section"] in ("wcag-ui", "brand-rule")]
    assert all(x["apca_lc"] is not None and x["apca_advisory"] for x in pair_rows)
    assert any("WCAG 3" in n for n in rep["notes"]) and "advisory" in " ".join(rep["notes"])
    assert {x["id"].split(":")[0] for x in pair_rows} == {"light", "dark"}


def test_low_contrast_ui_pair_fails_the_gate(proj):
    mutate_json(proj / "tokens" / "semantic.light.tokens.json", lambda d: d["color"]["muted"].__setitem__("$value", "{color.mist}"))
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1, r.stdout
    bad = failing(report(proj, "contrast"))
    assert bad == ["light:color.muted/color.bg"]
    assert "WCAG 2.2 AA" in r.stdout


def _pairs(d):
    return d["$extensions"]["brand-creator"]["pairs"]


def test_brand_rule_failure_is_labelled_a_brand_rule(proj):
    def raise_min(d):
        for pr in _pairs(d):
            if pr["kind"] == "brand-rule":
                pr["min"] = 30.0
    mutate_json(proj / "tokens" / "semantic.light.tokens.json", raise_min)
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1
    fails = [x for x in report(proj, "contrast")["results"] if x["status"] == "fail"]
    assert fails and all("brand rule (logos WCAG-exempt)" in x["label"] for x in fails)


def test_a_wcag_pair_cannot_be_weakened_below_the_wcag_floor(proj):
    def weaken(d):
        for pr in _pairs(d):
            if pr["kind"] == "ui-text":
                pr["min"] = 2.0
    mutate_json(proj / "tokens" / "semantic.light.tokens.json", weaken)
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1 and "below the WCAG 2.2 AA floor" in r.stdout


def test_contrast_without_built_tokens_cannot_run(proj):
    r = contrast(proj)
    assert r.returncode == 3 and "brand-creator tokens" in r.stderr


def test_dark_mode_is_checked_too(proj):
    mutate_json(proj / "tokens" / "semantic.dark.tokens.json", lambda d: d["color"]["text"].__setitem__("$value", "{color.night}"))
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1
    assert "dark:color.text/color.bg" in failing(report(proj, "contrast"))


# ---------------------------------------------------------------- text grounds (warnings in this release)

def starter_project(tmp_path):
    """A project with the three starter token files, as they are shipped (they carry a proposal for the text grounds, named by nobody)."""
    tmp_path.mkdir(exist_ok=True)
    p = make_project(tmp_path)
    (p / "tokens").mkdir(exist_ok=True)
    for f in (ROOT / "templates" / "tokens").glob("*.tokens.json"):
        shutil.copy2(f, p / "tokens" / f.name)
    return p


def grounds_rows(p):
    return {x["id"]: x for x in report(p, "contrast")["results"] if x["id"].startswith("grounds:")}


def set_grounds(d, **change):
    """Change the keys of the starter's grounds block (or of its one ground, with `ground_`-less names), for mutate_json."""
    ext = d["$extensions"]["brand-creator"]["grounds"]
    for key, value in change.items():
        if key == "named_by_owner":
            ext[key] = value
        elif value is None:
            ext["list"][0].pop(key.replace("_", "-"), None)
        else:
            ext["list"][0][key.replace("_", "-")] = value


def test_without_named_grounds_contrast_warns_and_still_passes(proj, tmp_path):
    """A project that lists no grounds gets one warning that says what to ask; the starter's proposal, as shipped, is judged but warns that nobody named it. Neither
    changes the status or the exit code. (What counts as naming is the next test, which breaks the starter on purpose.)"""
    assert tokens(proj).returncode == 0
    assert "grounds" not in json.loads((proj / "assets" / "tokens" / "tokens.json").read_text())
    r = contrast(proj)
    assert r.returncode == 0, r.stdout
    rows = grounds_rows(proj)
    assert list(rows) == ["grounds:named"] and rows["grounds:named"]["status"] == "warn"
    detail = rows["grounds:named"]["detail"]
    assert "which colours text sits on" in detail and "never guess" in detail and "failure from the next release" in detail
    assert report(proj, "contrast")["status"] == "pass"

    starter = starter_project(tmp_path / "starter")
    assert tokens(starter).returncode == 0
    r = contrast(starter, "--skip-marks")
    assert r.returncode == 0, r.stdout
    rows = grounds_rows(starter)
    assert rows["grounds:named"]["status"] == "warn" and "a proposal, not named by the owner" in rows["grounds:named"]["detail"]
    assert "[WARN] grounds:named" in r.stdout
    assert {k: v["status"] for k, v in rows.items() if k != "grounds:named"} == {
        f"grounds:{mode}:color.bg:{role}": "pass" for mode in ("light", "dark") for role in ("roles", "text", "action", "on-action", "focus", "border")}
    assert report(starter, "contrast")["status"] == "pass"


def test_a_date_with_no_words_or_words_with_no_date_or_a_list_of_no_ground_is_not_naming(tmp_path):
    """Each way the owner's naming can be wrong, written into the starter on purpose: the words with no date, a date with no words, a date that is no calendar day, a date
    in the wrong shape, and a naming that lists no ground. `grounds:named` warns every time and `contrast` still exits 0."""
    starter = starter_project(tmp_path)
    sem = starter / "tokens" / "semantic.light.tokens.json"
    for words in ("the page colour, as the owner said", "2026-10-30", "2026-13-45 the page colour", "20261030 the page colour"):
        mutate_json(sem, lambda d: set_grounds(d, named_by_owner=words))
        assert tokens(starter).returncode == 0
        assert contrast(starter, "--skip-marks").returncode == 0
        assert grounds_rows(starter)["grounds:named"]["status"] == "warn", words
    mutate_json(sem, lambda d: d["$extensions"]["brand-creator"].__setitem__("grounds", {"named_by_owner": "2026-10-30 text sits on the page colour", "list": []}))
    assert tokens(starter).returncode == 0
    assert contrast(starter, "--skip-marks").returncode == 0
    rows = grounds_rows(starter)
    assert list(rows) == ["grounds:named"] and rows["grounds:named"]["status"] == "warn" and "grounds.list holds none" in rows["grounds:named"]["detail"]


def test_a_button_that_vanishes_into_its_dark_ground_warns_by_role(tmp_path):
    """The action of a ground has the ground's own colour in dark: that role warns in dark, not in light, and `contrast` still exits 0."""
    p = starter_project(tmp_path)
    mutate_json(p / "tokens" / "semantic.light.tokens.json", lambda d: (
        d["color"].__setitem__("button", {"$value": "{color.signal}"}),
        set_grounds(d, named_by_owner="2026-10-30 text sits on the page", action="color.button")))
    mutate_json(p / "tokens" / "semantic.dark.tokens.json", lambda d: d["color"].__setitem__("button", {"$value": "{color.night}"}))   # = the dark color.bg
    assert tokens(p).returncode == 0
    r = contrast(p, "--skip-marks")
    assert r.returncode == 0, r.stdout
    rows = grounds_rows(p)
    row = rows["grounds:dark:color.bg:action"]
    assert row["status"] == "warn" and row["ratio"] == 1.0 and row["required"] == 3.0 and row["fg"] == row["bg"]
    assert "failure from the next release" in row["detail"] and "[WARN] grounds:dark:color.bg:action" in r.stdout
    assert rows["grounds:light:color.bg:action"]["status"] == "pass"
    assert rows["grounds:named"]["status"] == "pass" and report(p, "contrast")["status"] == "pass"
    assert "grounds:dark:color.bg:action" not in failing(report(p, "contrast"))


def test_a_ground_missing_a_role_warns_and_named_grounds_pass(tmp_path):
    """A role left out, or one that names no colour token, makes the roles row of that ground warn and names it (the rows that need it are not
    invented); with all five and the owner's words recorded, every grounds row passes."""
    p = starter_project(tmp_path)
    mutate_json(p / "tokens" / "semantic.light.tokens.json", lambda d: set_grounds(d, named_by_owner="2026-10-30 text sits on the page colour", focus=None))
    assert tokens(p).returncode == 0
    assert contrast(p, "--skip-marks").returncode == 0
    rows = grounds_rows(p)
    for mode in ("light", "dark"):
        row = rows[f"grounds:{mode}:color.bg:roles"]
        assert row["status"] == "warn" and row["missing"] == ["focus"] and "focus" in row["detail"] and "never guess" in row["detail"]
        assert f"grounds:{mode}:color.bg:focus" not in rows          # nothing to judge, and nothing invented
        assert rows[f"grounds:{mode}:color.bg:text"]["status"] == "pass"
    assert rows["grounds:named"]["status"] == "pass" and "2026-10-30 text sits on the page colour" in rows["grounds:named"]["detail"]

    mutate_json(p / "tokens" / "semantic.light.tokens.json", lambda d: set_grounds(d, focus="color.nope"))        # a name that is no token: null too
    assert tokens(p).returncode == 0
    assert contrast(p, "--skip-marks").returncode == 0
    assert grounds_rows(p)["grounds:light:color.bg:roles"]["missing"] == ["focus"]

    mutate_json(p / "tokens" / "semantic.light.tokens.json", lambda d: set_grounds(d, focus="color.focus"))
    assert tokens(p).returncode == 0
    r = contrast(p, "--skip-marks")
    assert r.returncode == 0, r.stdout
    rows = grounds_rows(p)
    assert len(rows) == 1 + 2 * 6 and {x["status"] for x in rows.values()} == {"pass"}
    assert not [x for x in report(p, "contrast")["results"] if x["status"] in ("warn", "fail")]


def test_every_role_is_held_to_its_floor_and_a_ground_listed_twice_keeps_its_rows_apart(tmp_path):
    """Text and on-action text at 4.5:1, action, focus and border at 3:1, each warning on its own row; two entries for one ground do not share ids."""
    p = starter_project(tmp_path)

    def weak(d):
        set_grounds(d, named_by_owner="2026-10-30 text sits on the page colour", text="color.line", focus="color.line", border="color.line")
        d["$extensions"]["brand-creator"]["grounds"]["list"].append({**d["$extensions"]["brand-creator"]["grounds"]["list"][0], "text": "color.text"})
    mutate_json(p / "tokens" / "semantic.light.tokens.json", weak)
    assert tokens(p).returncode == 0
    r = contrast(p, "--skip-marks")
    assert r.returncode == 0, r.stdout
    rows = grounds_rows(p)
    assert {role: rows[f"grounds:light:color.bg:{role}"]["status"] for role in ("text", "action", "on-action", "focus", "border")} == {
        "text": "warn", "action": "pass", "on-action": "pass", "focus": "warn", "border": "warn"}
    assert rows["grounds:light:color.bg:text"]["required"] == 4.5 and rows["grounds:light:color.bg:border"]["required"] == 3.0
    assert rows["grounds:light:color.bg#2:text"]["status"] == "pass" and rows["grounds:dark:color.bg#2:roles"]["status"] == "pass"
    ids = [x["id"] for x in report(p, "contrast")["results"]]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------- touching pairs (review finding M1)
#
# The Acme mark is an ink triangle with a teal dot, and a chalk triangle with a bright teal dot on the dark ground. The
# dot touches the body; both touch the ground. None of these pairs is declared by hand: they are found in the raster.

LOGO = "assets/logo/mark.svg"
LOGO_DARK = "assets/logo/mark-dark.svg"


def touch_rows(p):
    return [x for x in report(p, "contrast")["results"] if x["section"] == "touching-pairs"]


def test_touching_pairs_are_found_in_the_pixels_and_mapped_to_roles(proj):
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 0, r.stdout
    rows = {x["id"]: x for x in touch_rows(proj)}
    dot_light = rows["touch:light:mark:#007d71|#0d1b2d"]
    assert dot_light["status"] == "pass" and sorted(dot_light["roles"]) == ["color.accent", "color.mark"]
    assert dot_light["required"] == 2.0 and 3.4 < dot_light["ratio"] < 3.5 and dot_light["contact_px"] > 50
    assert rows["touch:light:mark:#0d1b2d|ground"]["roles"] == ["color.mark", "color.bg"]
    assert rows["touch:dark:mark:#f0eee7|ground"]["status"] == "pass"
    # the dark pair misses its 2:1 target and is carried by the recorded exception: a warning with the reason, not a pass
    dot_dark = rows["touch:dark:mark:#4cd7c8|#f0eee7"]
    assert dot_dark["status"] == "warn" and dot_dark["ratio"] < 2.0 and "shape, not the colour" in dot_dark["exception"]
    # the dot does not touch the ground, and nothing else exists
    assert not [k for k in rows if "#007d71|ground" in k or "#4cd7c8|ground" in k]
    # mark: dot-on-body and body-on-ground, light and dark (4); the example's wordmark is one flat colour on the ground, light and dark (2)
    assert len(rows) == 6 and len([k for k in rows if ":wordmark:" in k]) == 2
    assert rep_inputs(proj) >= {LOGO, LOGO_DARK, "tokens/exceptions.json"}


def rep_inputs(p):
    return {i["path"] for i in report(p, "contrast")["inputs"]}


def test_a_touching_pair_that_nobody_declared_fails_the_gate(proj):
    """Mutation: make the dot nearly the colour of the body. $extensions.pairs knows nothing about this."""
    mutate(proj / LOGO, 'fill="#007d71"', 'fill="#102338"')
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1, r.stdout
    bad = failing(report(proj, "contrast"))
    assert bad == ["touch:light:mark:#0d1b2d|#102338"], bad
    assert "not a colour token in light mode" in r.stdout  # the new colour is also reported as off-system


def test_the_same_dot_far_from_the_body_does_not_touch_and_is_not_reported(proj):
    mutate(proj / LOGO, 'fill="#007d71"', 'fill="#102338"')
    mutate(proj / LOGO, '<circle cx="32" cy="41" r="9"', '<circle cx="8" cy="8" r="3"')  # outside the triangle, on the ground
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 0, r.stdout
    assert not [x for x in touch_rows(proj) if "#102338" in x["id"] and x["id"].endswith("|#0d1b2d")]


def test_a_colour_that_vanishes_into_the_ground_fails(proj):
    mutate(proj / LOGO, 'fill="#0d1b2d"', 'fill="#efeee5"')  # the body now matches the paper ground
    assert tokens(proj).returncode == 0
    assert contrast(proj).returncode == 1
    assert "touch:light:mark:#efeee5|ground" in failing(report(proj, "contrast"))


def test_the_dark_artwork_is_checked_against_the_dark_ground(proj):
    mutate(proj / LOGO_DARK, 'fill="#f0eee7"', 'fill="#1a222d"')
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1
    bad = failing(report(proj, "contrast"))
    assert "touch:dark:mark:#1a222d|ground" in bad, bad


def test_without_a_dark_artwork_the_light_one_is_checked_on_both_grounds(proj):
    (proj / LOGO_DARK).unlink()
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 1, r.stdout  # the ink body vanishes on the dark ground
    bad = failing(report(proj, "contrast"))
    assert "touch:dark:mark:#0d1b2d|ground" in bad, bad
    assert any(x["id"] == "touching:mark:dark-artwork" and x["status"] == "info" for x in report(proj, "contrast")["results"])


def test_an_exception_needs_a_reason_and_turns_a_miss_into_a_warning(proj):
    exc = proj / "tokens" / "exceptions.json"
    mutate(proj / LOGO, 'fill="#007d71"', 'fill="#102338"')
    assert tokens(proj).returncode == 0
    assert contrast(proj).returncode == 1
    mutate_json(exc, lambda d: d["exceptions"].append({"a": "#0d1b2d", "b": "#102338", "mode": "light", "reason": "tonal dot by design"}))
    r = contrast(proj)
    assert r.returncode == 0, r.stdout
    row = next(x for x in touch_rows(proj) if x["id"] == "touch:light:mark:#0d1b2d|#102338")
    assert row["status"] == "warn" and row["exception"] == "tonal dot by design"
    mutate(exc, '"reason": "tonal dot by design"', '"reason": "  "')
    r = contrast(proj)
    assert r.returncode == 2 and "needs a, b and a non-empty reason" in r.stderr


def test_a_stale_exception_is_reported(proj):
    exc = proj / "tokens" / "exceptions.json"
    mutate_json(exc, lambda d: d["exceptions"].append({"a": "color.text", "b": "color.line", "reason": "nothing touches these"}))
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 0
    stale = [x for x in report(proj, "contrast")["results"] if x["id"].startswith("exception:color.text")]
    assert stale and stale[0]["status"] == "warn" and "stale" in stale[0]["detail"]


def test_an_exception_for_a_pair_that_passes_is_reported(proj):
    mutate_json(proj / "tokens" / "exceptions.json", lambda d: d["exceptions"].append(
        {"a": "color.mark", "b": "color.accent", "mode": "light", "reason": "was needed once"}))
    assert tokens(proj).returncode == 0
    contrast(proj)
    msgs = [x["detail"] for x in report(proj, "contrast")["results"] if x["id"].startswith("exception:")]
    assert any("passes its target now" in m for m in msgs), msgs


def test_touching_targets_are_set_in_the_tokens(proj):
    def stricter(d):
        d["$extensions"]["brand-creator"]["touching"]["pairs"][0]["min"] = 4.0
    mutate_json(proj / "tokens" / "semantic.light.tokens.json", stricter)
    assert tokens(proj).returncode == 0
    assert contrast(proj).returncode == 1
    assert failing(report(proj, "contrast")) == ["touch:light:mark:#007d71|#0d1b2d"]
    # a bad target is a usage error, not a silent default
    mutate_json(proj / "tokens" / "semantic.light.tokens.json", lambda d: d["$extensions"]["brand-creator"]["touching"].__setitem__("default", "high"))
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 2 and "touching.default" in r.stderr


def test_without_a_mark_the_check_is_not_verified_never_a_pass(proj):
    (proj / LOGO).unlink()
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 3 and "NOT checked" in r.stdout, r.stdout
    assert report(proj, "contrast")["status"] == "not-verified"
    r = contrast(proj, "--skip-marks")  # explicit and printed
    assert r.returncode == 0 and "--skip-marks" in r.stdout
    assert any(x["status"] == "info" and "skipped-on-purpose" in x["id"] for x in report(proj, "contrast")["results"])


def test_only_flat_fills_are_analysed_a_gradient_is_not_verified(proj):
    svg = proj / LOGO
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="g"><stop offset="0" '
                   'stop-color="#0d1b2d"/><stop offset="1" stop-color="#4b596c"/></linearGradient></defs>'
                   '<rect x="6" y="6" width="52" height="52" fill="url(#g)"/></svg>', encoding="utf-8")
    assert tokens(proj).returncode == 0
    r = contrast(proj)
    assert r.returncode == 3 and "uses <linearGradient>, which is not a flat fill" in r.stdout


def test_touching_analysis_unit(tmp_path):
    """The raster step on its own: two squares that touch, one that does not, and an anti-aliased seam."""
    from touching import analyse
    import subprocess as sp
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
           '<rect x="5" y="5" width="40" height="40" fill="#112233"/><rect x="44.6" y="5" width="30" height="40" fill="#ddeeff"/>'
           '<rect x="5" y="70" width="20" height="20" fill="#cc9900"/></svg>')
    f, o = tmp_path / "a.svg", tmp_path / "a.png"
    f.write_text(svg)
    sp.run(["resvg", "-w", "400", "-h", "400", str(f), str(o)], check=True)
    res = analyse(o.read_bytes())
    assert set(res["colours"]) == {"#112233", "#ddeeff", "#cc9900"}
    assert list(res["contacts"]) == [("#112233", "#ddeeff")]  # the anti-aliased seam counts; the far square does not
    assert set(res["ground"]) == {"#112233", "#ddeeff", "#cc9900"}
