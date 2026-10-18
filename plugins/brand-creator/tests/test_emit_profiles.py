"""emit profiles: the circle-safe avatar, the six profile images, the safe-area proof images, the gate before anything ships, the
"UNVERIFIED, recheck" label (every row is status U), the tier gate, retirement, determinism and `check`.

Expected values are worked out by hand from the rows' numbers (400 and 800 px avatars, 1584x396 LinkedIn, 1500x500 X, 2560x1440 YouTube, 820x312
Facebook, 1080x1350 Instagram feed, 1080x1920 story) or are properties of the output (colour type, where the ink is, what the proof shows that the
shipped file does not). Safe areas are read from platform-specs.json through `specs`, the one table the emitters read."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, failing, make_project, install_fixture, mutate, mutate_json, report

import specs
from pxio import png_color_type, png_size, read_png

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]
LABEL = "UNVERIFIED, recheck"
TAG = "a repair guide is in every box"
BANNERS = {"linkedin-banner": (1584, 396), "x-header": (1500, 500), "youtube-banner": (2560, 1440), "facebook-cover": (820, 312),
           "instagram-feed": (1080, 1350), "instagram-story": (1080, 1920)}
ROWS = {"linkedin-banner": "profile-linkedin-banner", "x-header": "profile-x-banner", "youtube-banner": "profile-youtube-banner", "facebook-cover": "profile-facebook-cover",
        "instagram-feed": "profile-instagram-feed", "instagram-story": "profile-instagram-story"}
OUT = "assets/profiles"


def profiles(p, *extra, **kw):
    return bc("emit", "profiles", *extra, project=p, **kw)


def manifest(p):
    return json.loads((p / "assets" / "manifest.json").read_text())


def row(p, path):
    return next(a for a in manifest(p)["artefacts"] if a["path"] == path)


def standard(acme: Path) -> Path:
    assert bc("state", "--set", "tier=standard", project=acme).returncode == 0
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    return acme


@pytest.fixture
def std(acme) -> Path:
    return standard(acme)


@pytest.fixture(scope="module")
def pack(tmp_path_factory, golden):
    """One emit with a tagline; the tests below only read it."""
    p = tmp_path_factory.mktemp("profiles") / "acme"
    shutil.copytree(golden, p)
    standard(p)
    r = profiles(p, "--tagline", TAG)
    assert r.returncode == 0, r.stdout + r.stderr
    return p


def ink(path: Path):
    """(farthest ink pixel from the centre, bounding box (l, t, r, b)) of the pixels unlike the ground (the corner pixel): measured here, not by the emitter."""
    w, h, px = read_png(path.read_bytes())
    g = tuple(px[:3])
    far, xs, ys = 0.0, [], []
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            if max(abs(px[i + c] - g[c]) for c in range(3)) > 8:
                far = max(far, ((x + 0.5 - w / 2) ** 2 + (y + 0.5 - h / 2) ** 2) ** 0.5)
                xs.append(x)
                ys.append(y)
    return far, ((min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None)


# ================================================================ spec rows

def test_the_profile_rows_exist_are_all_unverified_and_say_so():
    rows = specs.load()["rows"]
    want = ["profile-avatar", *ROWS.values()]
    for rid in want:
        r = rows[rid]
        assert r["status"] == "U" and r["source_url"].startswith("https://") and r["checked"] == "2026-10-17", rid
        assert LABEL in r["notes"], f"{rid} is U and its notes must say so"
    assert specs.sizes("profile-avatar")["px"] == [400, 800]
    for fname, (w, h) in BANNERS.items():
        s = specs.sizes(ROWS[fname])
        assert (s["width"], s["height"]) == (w, h), fname
        sf = s["safe"]
        assert sf["x"] >= 0 and sf["y"] >= 0 and sf["x"] + sf["width"] <= w and sf["y"] + sf["height"] <= h, fname    # a safe rectangle inside its image
    assert specs.sizes("profile-youtube-banner")["safe"] == {"x": 507, "y": 508.5, "width": 1546, "height": 423}   # centred: (2560 - 1546) / 2, (1440 - 423) / 2


# ================================================================ gates before anything: G3 and the tier

def test_gate_g3_comes_first(tmp_path):
    p = make_project(tmp_path)
    install_fixture(p)
    assert bc("tokens", project=p).returncode == 0
    assert bc("state", "--set", "tier=standard", project=p).returncode == 0
    r = profiles(p)
    assert r.returncode == 1 and "G3" in r.stderr


def test_the_quick_tier_is_refused_with_the_way_up_and_writes_nothing(acme):
    assert (acme / "BRAND-STATE.md").read_text().count("tier: quick") == 1
    r = profiles(acme)
    assert r.returncode == 2 and "standard" in r.stderr and "state --set tier=standard" in r.stderr, r.stderr
    assert not (acme / OUT).exists()


def test_the_full_tier_is_accepted_too(acme):
    assert bc("state", "--set", "tier=full", project=acme).returncode == 0
    assert profiles(acme).returncode == 0


# ================================================================ the avatar

def test_avatars_are_opaque_squares_with_the_mark_centred_inside_the_circle(pack):
    sc = specs.sizes("profile-avatar")["safe_circle"]
    for n in (400, 800):
        f = pack / OUT / f"avatar-{n}.png"
        data = f.read_bytes()
        assert png_size(data) == (n, n) and png_color_type(data) == 2          # RGB, no alpha channel
        far, bb = ink(f)
        assert far <= sc * n / 2 + 1.5, (n, far)                                # inside the safe circle (measured here)
        assert far > 0.3 * n / 2, "the mark is tiny: the automatic size should fill the circle margin as far as the cap allows"
        assert abs((bb[0] + bb[2]) / 2 - n / 2) <= 2 and abs((bb[1] + bb[3]) / 2 - n / 2) <= n / 20   # centred sideways; the triangle's centre of mass sits low
    assert [x["detail"] for x in report(pack, "emit-profiles")["results"] if x["id"] == "check:avatar-400 circle"][0].startswith("farthest ink pixel")


def test_a_mark_that_does_not_fit_the_circle_stops_the_emit_before_anything_is_written_and_the_proof_shows_why(std):
    r = profiles(std, "--content-fraction", "1.0")
    assert r.returncode == 1 and "an image does not fit its safe area" in r.stderr, r.stdout + r.stderr
    rep = report(std, "emit-profiles")
    assert "check:avatar-400 circle" in failing(rep) and "check:avatar-800 circle" in failing(rep)
    assert not (std / "assets/manifest.json").is_file() or not [a for a in manifest(std)["artefacts"] if a["emitter"] == "profiles"]   # no manifest row either
    assert not list((std / OUT).glob("*.png"))                                       # nothing shipped
    assert (std / OUT / "_proof/avatar-400.png").is_file()                           # the proof is there to look at
    assert profiles(std, "--content-fraction", "0.5").returncode == 0                # the same project passes with a smaller mark


def test_content_fraction_is_validated(std):
    r = profiles(std, "--content-fraction", "1.5")
    assert r.returncode == 2 and "--content-fraction" in r.stderr


# ================================================================ the banners

@pytest.mark.parametrize("fname", sorted(BANNERS))
def test_each_banner_has_the_spec_size_no_alpha_and_all_its_ink_inside_the_safe_rectangle(pack, fname):
    w, h = BANNERS[fname]
    f = pack / OUT / f"{fname}-{w}x{h}.png"
    data = f.read_bytes()
    assert png_size(data) == (w, h) and png_color_type(data) == 2
    s = specs.sizes(ROWS[fname])["safe"]
    _far, bb = ink(f)
    assert bb is not None and bb[0] >= s["x"] - 1 and bb[1] >= s["y"] - 1 and bb[2] <= s["x"] + s["width"] + 1 and bb[3] <= s["y"] + s["height"] + 1, (fname, bb, s)
    assert (bb[2] - bb[0]) > 0.2 * s["width"], "the mark and the name fill a fair part of the safe rectangle"
    # the shipped file has no overlay: nothing in it is the proof's red
    w_, h_, px = read_png(data)
    assert not any(px[i] > 200 and px[i + 1] < 80 and px[i + 2] < 80 for i in range(0, len(px), 4))


def test_the_name_and_the_real_tagline_are_drawn_and_nothing_else(pack):
    html = (pack / OUT / "_build/linkedin-banner.html").read_text()
    assert "<h1>Acme</h1>" in html and TAG in html
    assert "{{" not in html and "<script" not in html


def test_a_tagline_that_is_not_a_facts_value_is_refused(std):
    r = profiles(std, "--tagline", "the best repair tools anywhere")
    assert r.returncode == 1 and "not a value in FACTS.md" in r.stderr
    assert not (std / OUT).exists() or not list((std / OUT).glob("*.png"))


def test_a_name_that_overflows_the_safe_rectangle_fails_before_anything_ships(std):
    r = profiles(std, "--name", "W" * 50)
    assert r.returncode == 1 and "an image does not fit its safe area" in r.stderr and "linkedin-banner" in r.stderr, r.stdout + r.stderr
    rep = report(std, "emit-profiles")
    assert "check:linkedin-banner safe area" in failing(rep)
    assert not list((std / OUT).glob("*.png")) and (std / OUT / "_proof/linkedin-banner.png").is_file()


def test_a_template_that_draws_outside_the_safe_rectangle_fails_the_gate(std, tmp_path):
    t = tmp_path / "banner.html"
    shutil.copy2(ROOT / "templates/profile/banner.html", t)
    mutate(t, ".safe{position:absolute;left:{{safe_x}}px", ".safe{position:absolute;left:0px")
    r = profiles(std, "--template", str(t))
    assert r.returncode == 1 and "safe area" in r.stderr, r.stdout + r.stderr
    assert "check:linkedin-banner safe area" in failing(report(std, "emit-profiles"))


def test_a_template_with_an_unfilled_placeholder_is_an_error_never_a_blank(std, tmp_path):
    t = tmp_path / "banner.html"
    shutil.copy2(ROOT / "templates/profile/banner.html", t)
    mutate(t, "<p>{{tagline}}</p>", "<p>{{tagline}} {{nope}}</p>")
    r = profiles(std, "--template", str(t))
    assert r.returncode == 1 and "unfilled placeholders" in r.stderr and "nope" in r.stderr


# ================================================================ the proof images

def test_proof_images_draw_the_safe_areas_and_are_never_shipped_or_in_the_manifest(pack):
    proof = pack / OUT / "_proof"
    names = sorted(f.name for f in proof.glob("*.png"))
    assert names == sorted(["avatar-400.png", "avatar-800.png", *[f"{k}.png" for k in BANNERS]])
    for fname, (w, h) in BANNERS.items():
        data = (proof / f"{fname}.png").read_bytes()
        assert png_size(data) == (w, h)
        _w, _h, px = read_png(data)
        assert any(px[i] > 200 and px[i + 1] < 80 and px[i + 2] < 80 for i in range(0, len(px), 4)), f"{fname}: the dashed safe rectangle is not drawn"
        assert data != (pack / OUT / f"{fname}-{w}x{h}.png").read_bytes()
    assert not [a for a in manifest(pack)["artefacts"] if "_proof" in a["path"]]
    r = bc("verify-idempotent", "--project", str(pack), "--cmd", f"{{bc}} emit profiles --tagline '{TAG}' --project {{project}}")
    assert r.returncode == 0, r.stdout + r.stderr          # folders named _* are outside the idempotence tree


# ================================================================ the label and check

def test_every_file_says_unverified_and_check_holds_the_label_and_the_safe_areas(pack, tmp_path):
    arts = [a for a in manifest(pack)["artefacts"] if a["emitter"] == "profiles"]
    assert len(arts) == 8 and all(a["note"].startswith(f"{LABEL} (profile-") for a in arts)
    rows = {x["id"]: x for x in report(pack, "emit-profiles")["results"]}
    assert all(LABEL in x["label"] for k, x in rows.items() if k.startswith("file:"))
    c = tmp_path / "chk"
    shutil.copytree(pack, c)
    out = bc("check", project=c).stdout
    assert "[PASS] report:emit-profiles" in out and "[PASS] tierb:labels" in out and "[PASS] tierb:profiles" in out, out
    # mutation 1: one note loses the label
    path = f"{OUT}/avatar-400.png"
    mutate_json(c / "assets/manifest.json", lambda d: next(a for a in d["artefacts"] if a["path"] == path).update(note="profile photo"))
    r = bc("check", project=c)
    assert r.returncode == 1 and "[FAIL] tierb:labels" in r.stdout and path in r.stdout
    # mutation 2 (a fresh copy): the recorded safe circle shrinks below where the ink is -> the gate re-measured from the pixels fails
    d2 = tmp_path / "chk2"
    shutil.copytree(pack, d2)
    mutate_json(d2 / "assets/manifest.json", lambda d: next(a for a in d["artefacts"] if a["path"] == path).update(safe_radius_px=10))
    r = bc("check", project=d2)
    assert r.returncode == 1 and "[FAIL] tierb:profiles" in r.stdout and "outside the safe circle" in r.stdout, r.stdout
    # mutation 3 (a fresh copy): a banner file disappears (moved, not deleted) -> not written
    d3 = tmp_path / "chk3"
    shutil.copytree(pack, d3)
    moved = d3 / OUT / "x-header-1500x500.png"
    shutil.move(str(moved), str(tmp_path / "moved.png"))
    assert not moved.exists()
    r = bc("check", project=d3)
    assert r.returncode == 1 and "[FAIL] tierb:profiles" in r.stdout and "x-header" in r.stdout


def test_bands_are_recorded_for_the_marks_size_and_sizes_are_in_the_manifest(pack):
    a = row(pack, f"{OUT}/avatar-800.png")
    assert a["size"] == "800x800" and a["slot"] == "profile-avatar" and a["band"] and a["specs"] == ["profile-avatar"] and a["safe_radius_px"] > 0
    b = row(pack, f"{OUT}/instagram-story-1080x1920.png")
    assert b["size"] == "1080x1920" and b["resampled_by"] == "PAGE" and b["safe"] == {"x": 60, "y": 260, "width": 960, "height": 1400}


def test_second_run_writes_nothing(std):
    assert profiles(std).returncode == 0
    r = profiles(std)
    assert r.returncode == 0 and " 0 written" in r.stdout, r.stdout


def test_a_size_the_spec_row_drops_is_retired_moved_never_deleted(std, plugin_copy):
    assert profiles(std).returncode == 0
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate(f, '"sizes": { "px": [400, 800], "safe_circle": 0.72 }', '"sizes": { "px": [800], "safe_circle": 0.72 }')
    r = profiles(std, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (std / OUT / "avatar-400.png").exists() and (std / OUT / "avatar-800.png").is_file()
    assert (std / "removed-2026-10-17" / OUT / "avatar-400.png").is_file()
    assert f"{OUT}/avatar-400.png" in report(std, "emit-profiles")["retired"]
    assert not [a for a in manifest(std)["artefacts"] if a["path"] == f"{OUT}/avatar-400.png"]


def test_the_entry_point_dispatches_profiles_and_check_names_the_report():
    entry = (ROOT / "bin/brand-creator").read_text()
    assert "presskit|profiles) py" in entry and "emit profiles " in entry
    assert '"profiles"' in (ROOT / "scripts/check.py").read_text()
    r = bc("emit", "profiles", "--help")
    assert r.returncode == 0 and "usage:" in r.stdout and "emit profiles" in r.stdout
