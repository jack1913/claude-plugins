"""emit profiles: the circle-safe avatar, the six profile images, the safe-area proof images, the gate before anything ships, the
"UNVERIFIED, recheck" label (every row is status U), the tier gate, retirement, determinism and `check`.

Expected values are worked out by hand from the rows' numbers (400 and 800 px avatars, 1584x396 LinkedIn, 1500x500 X, 2560x1440 YouTube, 820x312
Facebook, 1080x1350 Instagram feed, 1080x1920 story) or are properties of the output (colour type, where the ink is, what the proof shows that the
shipped file does not). Safe areas are read from platform-specs.json through `specs`, the one table the emitters read.

A Standard-tier run renders twelve cards and takes about 16 s, so the tests share one (`pack`, only read), ask one run for several faults when each is
told apart by its own row, and use the Quick tier (the avatars only, about 1 s) wherever the banners are not what is tested."""
import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest
from helpers import FIXTURES, ROOT, bc, failing, make_project, install_fixture, mutate, mutate_json, report

import _emit
import determinism
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


RED = re.compile(rb"(?=[\xc9-\xff][\x00-\x4f][\x00-\x4f])")    # the proof's red (R > 200, G < 80, B < 80), looked for at every byte: it counts where a pixel starts


class Ink(NamedTuple):
    far: float                       # the farthest ink pixel from the centre (px)
    box: tuple | None                # (l, t, r, b) of the ink, right and bottom exclusive; None when there is none
    red: bool                        # some pixel of the file is the proof's red


def ink(path: Path) -> Ink:
    """Where the ink of a PNG is: the pixels unlike the ground (the corner pixel) by more than 8 in any channel. Measured here, not by the emitter. A banner is
    millions of pixels, so: a row equal to the ground row has no ink and no red and is skipped with one comparison; in any other row one XOR of it and the
    ground row, as integers, says where the first and the last differing pixel are, and the ink is looked for from each end inwards (the pixel of a row that
    is farthest from the centre is one of its two ends)."""
    w, h, px = read_png(path.read_bytes())
    n, g = 4 * w, bytes(px[:4])
    ground, ground_int = g * w, int.from_bytes(g * w, "big")

    def unlike(row, i):
        return abs(row[4 * i] - g[0]) > 8 or abs(row[4 * i + 1] - g[1]) > 8 or abs(row[4 * i + 2] - g[2]) > 8

    far2, left, right, top, bottom, red = 0.0, w, 0, h, -1, g[0] > 200 and g[1] < 80 and g[2] < 80
    for y in range(h):
        row = px[y * n:(y + 1) * n]
        if row == ground:
            continue
        diff = int.from_bytes(row, "big") ^ ground_int
        first = (n - (diff.bit_length() + 7) // 8) // 4                  # the first pixel that differs at all: the highest set bit of the XOR is in its first byte
        last = (n - 1 - ((diff & -diff).bit_length() - 1) // 8) // 4     # and the last: the lowest set bit is in its last byte
        red = red or any(m.start() % 4 == 0 for m in RED.finditer(row, first * 4, last * 4 + 4))
        while first <= last and not unlike(row, first):
            first += 1
        if first > last:
            continue                 # a row of noise within the tolerance: no ink
        while not unlike(row, last):
            last -= 1
        left, right, top, bottom = min(left, first), max(right, last + 1), min(top, y), y + 1
        dy2 = (y + 0.5 - h / 2) ** 2
        far2 = max(far2, (first + 0.5 - w / 2) ** 2 + dy2, (last + 0.5 - w / 2) ** 2 + dy2)
    return Ink(far2 ** 0.5, (left, top, right, bottom) if bottom >= 0 else None, red)


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


def test_the_quick_tier_writes_the_avatar_only_and_says_why(acme):
    """PF-1: every business on a network needs the circle-safe picture; the banners stay Standard."""
    assert (acme / "BRAND-STATE.md").read_text().count("tier: quick") == 1
    r = profiles(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    files = sorted(f.name for f in (acme / OUT).glob("*.png"))
    assert files == ["avatar-400.png", "avatar-800.png"], files
    rows = {x["id"]: x for x in report(acme, "emit-profiles")["results"]}
    assert rows["note:banners"]["status"] == "info" and "state --set tier=standard" in rows["note:banners"]["detail"]
    out = bc("check", project=acme).stdout
    assert "[FAIL] tierb:profiles" not in out, out
    assert bc("state", "--set", "tier=standard", project=acme).returncode == 0
    out = bc("check", project=acme).stdout
    assert "[FAIL] tierb:profiles" in out and "linkedin-banner" in out, out   # the full set is expected again once the tier is raised
    assert profiles(acme).returncode == 0 and (acme / OUT / "linkedin-banner-1584x396.png").is_file()


# No Full-tier test here: the gate takes quick, standard and full, and the one run of `emit profiles` in the Full tier is in tests/test_marks.py
# (the accent-line test; tests/mutation_ledger.py, profiles/full-tier-refused, proves it still catches a refusal).


# ================================================================ the avatar

def test_avatars_are_opaque_squares_with_the_mark_centred_inside_the_circle(pack):
    sc = specs.sizes("profile-avatar")["safe_circle"]
    for n in (400, 800):
        f = pack / OUT / f"avatar-{n}.png"
        data = f.read_bytes()
        assert png_size(data) == (n, n) and png_color_type(data) == 2          # RGB, no alpha channel
        far, bb, _red = ink(f)
        assert far <= sc * n / 2 + 1.5, (n, far)                                # inside the safe circle (measured here)
        assert far > 0.3 * n / 2, "the mark is tiny: the automatic size should fill the circle margin as far as the cap allows"
        assert abs((bb[0] + bb[2]) / 2 - n / 2) <= 2 and abs((bb[1] + bb[3]) / 2 - n / 2) <= n / 20   # centred sideways; the triangle's centre of mass sits low
    assert [x["detail"] for x in report(pack, "emit-profiles")["results"] if x["id"] == "check:avatar-400 circle"][0].startswith("farthest ink pixel")


def test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why(std):
    """One run with both faults (the Standard tier, so the banners are rendered): a mark too big for the circle (--content-fraction 1.0) and a name too long
    for the banners (--name). Each is a row of its own and is counted in the message, so neither hides the other."""
    r = profiles(std, "--content-fraction", "1.0", "--name", "W" * 50)
    assert r.returncode == 1 and "an image does not fit its safe area" in r.stderr, r.stdout + r.stderr
    assert all(k in r.stderr for k in ("avatar-400", "avatar-800", "linkedin-banner")), r.stderr     # the message lists the first four that fail
    rep = report(std, "emit-profiles")
    assert {"check:avatar-400 circle", "check:avatar-800 circle", "check:linkedin-banner safe area"} <= set(failing(rep))
    assert not (std / "assets/manifest.json").is_file() or not [a for a in manifest(std)["artefacts"] if a["emitter"] == "profiles"]   # no manifest row either
    assert not list((std / OUT).glob("*.png"))                                       # nothing shipped
    assert (std / OUT / "_proof/avatar-400.png").is_file() and (std / OUT / "_proof/linkedin-banner.png").is_file()   # the proofs are there to look at
    assert bc("state", "--set", "tier=quick", project=std).returncode == 0           # the same project passes with a smaller mark: the avatars are what the fraction is about
    r = profiles(std, "--content-fraction", "0.5")
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(f.name for f in (std / OUT).glob("*.png")) == ["avatar-400.png", "avatar-800.png"]


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
    _far, bb, red = ink(f)
    assert bb is not None and bb[0] >= s["x"] - 1 and bb[1] >= s["y"] - 1 and bb[2] <= s["x"] + s["width"] + 1 and bb[3] <= s["y"] + s["height"] + 1, (fname, bb, s)
    assert (bb[2] - bb[0]) > 0.2 * s["width"], "the mark and the name fill a fair part of the safe rectangle"
    assert not red, "the shipped file has no overlay: nothing in it is the proof's red"


def page(p: Path, fname: str) -> str:
    """A banner's filled HTML without its comments (the template's comment lists the placeholders, and they are filled too)."""
    return re.sub(r"<!--.*?-->", "", (p / OUT / f"_build/{fname}.html").read_text(), flags=re.S)


def lettering_of(html: str) -> str:
    """The SVG a banner or card shows as its drawn lettering (decoded from the <img> data URI)."""
    m = re.search(r'<img class="lettering" alt="[^"]*" width="\d+" height="\d+" src="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)">', html)
    assert m, "no drawn lettering on the page"
    return base64.b64decode(m.group(1)).decode("utf-8")


def test_the_drawn_wordmark_and_the_real_tagline_are_drawn_and_nothing_else(pack):
    """Acme has a wordmark and no lockup: the banners set the mark and the drawn wordmark, never the name as live text."""
    html = page(pack, "linkedin-banner")
    assert '<body class="wordmark">' in html and TAG in html and "<h1>" not in html
    assert re.search(r'<div class="mark">\s*<svg', html)                           # the mark stays next to a wordmark
    assert lettering_of(html) == (pack / "assets/logo/wordmark.svg").read_text()
    assert "{{" not in html and "<script" not in html
    rows = {x["id"]: x for x in report(pack, "emit-profiles")["results"]}
    assert rows["note:lettering"]["status"] == "info" and rows["note:lettering"]["detail"] == "assets/logo/wordmark.svg (by its file name)"


def test_a_lockup_stands_alone_with_no_second_mark_and_stays_inside_the_safe_rectangle(std):
    shutil.copy2(std / "assets/logo/wordmark.svg", std / "assets/logo/lockup.svg")    # any pure-vector art named lockup stands alone
    assert profiles(std).returncode == 0
    for fname, (w, h) in BANNERS.items():
        html = page(std, fname)
        assert '<body class="lockup">' in html and '<div class="mark"></div>' in html and "<h1>" not in html
        assert lettering_of(html) == (std / "assets/logo/lockup.svg").read_text()
        s = specs.sizes(ROWS[fname])["safe"]
        bb = ink(std / OUT / f"{fname}-{w}x{h}.png").box
        assert bb[0] >= s["x"] - 1 and bb[2] <= s["x"] + s["width"] + 1 and (bb[2] - bb[0]) > 0.3 * s["width"], (fname, bb, s)


def test_without_a_lockup_or_wordmark_the_name_is_text_and_the_report_warns(std):
    for f in (std / "assets/logo").glob("wordmark*.svg"):
        f.rename(std / f.name)
    assert profiles(std).returncode == 0
    html = page(std, "linkedin-banner")
    assert '<body class="type">' in html and "<h1>Acme</h1>" in html and 'class="lettering"' not in html
    row = next(x for x in report(std, "emit-profiles")["results"] if x["id"] == "note:lettering")
    assert row["status"] == "warn" and "no assets/logo/lockup.svg or wordmark.svg" in row["detail"]


def test_a_name_given_is_set_as_text_and_a_template_from_before_the_lettering_still_works(std, tmp_path):
    assert profiles(std, "--name", "Acme Tools").returncode == 0
    assert "<h1>Acme Tools</h1>" in page(std, "linkedin-banner")
    row = next(x for x in report(std, "emit-profiles")["results"] if x["id"] == "note:lettering")
    assert row["status"] == "info" and "--name" in row["detail"]
    t = tmp_path / "banner.html"
    shutil.copy2(ROOT / "templates/profile/banner.html", t)
    mutate(t, '<div class="text">{{lettering}}', '<div class="text"><h1>{{name}}</h1>')    # a template written before 0.3.1
    assert profiles(std, "--template", str(t)).returncode == 0
    assert "<h1>Acme</h1>" in page(std, "linkedin-banner")
    row = next(x for x in report(std, "emit-profiles")["results"] if x["id"] == "note:lettering")
    assert row["status"] == "warn" and "no {{lettering}} placeholder" in row["detail"]


def test_a_template_that_draws_its_own_name_is_an_info_row(std, tmp_path):
    """No {{lettering}} and no {{name}} outside the comments and the <title>: the template draws the name itself (outlined paths, for example), so
    nothing is wrong and the row is info, with or without a lockup or wordmark file (no such file is read). A template that types {{name}} without
    {{lettering}} keeps its warning (the test above holds that on a run, tests/test_emitters.py on each case)."""
    t = tmp_path / "banner.html"
    shutil.copy2(ROOT / "templates/profile/banner.html", t)
    assert "{{name}}" in t.read_text()      # the <title> and the comment name it: neither counts
    mutate(t, '<div class="text">{{lettering}}', '<div class="text"><svg class="own-name" viewBox="0 0 40 8" width="320" height="64"><path d="M0 0h40v8h-40z"/></svg>')
    assert profiles(std, "--template", str(t)).returncode == 0       # Acme's wordmark.svg is there and is not placed
    row = next(x for x in report(std, "emit-profiles")["results"] if x["id"] == "note:lettering")
    assert row["status"] == "info" and row["label"] == "the template draws its own name" and "no {{lettering}} and no {{name}}" in row["detail"], row
    html = page(std, "linkedin-banner")
    assert 'class="own-name"' in html and "<h1>" not in html and 'class="lettering"' not in html


def test_lockup_or_wordmark_comes_from_lettering_or_the_file_name_and_is_never_guessed(std):
    """A --logo-svg whose name says wordmark is a wordmark, wherever the word stands in the name (the pack's page shows the mark next to it); a name that
    says neither stops the run (exit 2) until --lettering says."""
    logo = std / "assets/logo"
    shutil.copy2(logo / "wordmark.svg", logo / "acme-wordmark.svg")
    assert _emit.lettering_kind("assets/logo/acme-wordmark.svg", None) == "wordmark"
    shutil.copy2(logo / "wordmark.svg", logo / "logotype.svg")
    r = profiles(std, "--logo-svg", "assets/logo/logotype.svg")
    assert r.returncode == 2 and "--lettering lockup or --lettering wordmark" in r.stderr
    assert profiles(std, "--logo-svg", "assets/logo/logotype.svg", "--lettering", "lockup").returncode == 0
    assert '<body class="lockup">' in page(std, "linkedin-banner")
    row = next(x for x in report(std, "emit-profiles")["results"] if x["id"] == "note:lettering")
    assert row["detail"] == "assets/logo/logotype.svg (--lettering)"
    # --name types the name, so drawn lettering next to it would go unused: refused, never dropped in silence
    r = profiles(std, "--name", "Acme Tools", "--logo-svg", "assets/logo/acme-wordmark.svg")
    assert r.returncode == 2 and "not both" in r.stderr
    r = profiles(std, "--lettering", "wordmark")
    assert r.returncode == 2 and "together with --logo-svg" in r.stderr


def test_the_quick_tier_reads_no_lettering_so_a_lockup_it_never_uses_cannot_stop_it(acme):
    """The Quick tier writes no banners: no lettering row, no lettering input, and a lockup that is not pure vector does not stop the avatars."""
    (acme / "assets/logo/lockup.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 10"><text x="1" y="9">Acme</text></svg>')
    r = profiles(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(acme, "emit-profiles")
    assert "note:lettering" not in {x["id"] for x in rep["results"]} and "lockup.svg" not in json.dumps(rep)
    assert sorted(f.name for f in (acme / OUT).glob("*.png")) == ["avatar-400.png", "avatar-800.png"]


def test_a_tagline_that_is_not_a_facts_value_is_refused(std):
    r = profiles(std, "--tagline", "the best repair tools anywhere")
    assert r.returncode == 1 and "not a value in FACTS.md" in r.stderr
    assert not (std / OUT).exists() or not list((std / OUT).glob("*.png"))


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

def assets_tree(p: Path) -> dict[str, str]:
    """Every file under assets/ by its hash, except what sits in a folder named _* (the scratch, the proofs, the reports): the rule of `verify-idempotent`."""
    root = p / "assets"
    return {f.relative_to(root).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(root.rglob("*"))
            if f.is_file() and not any(part.startswith("_") for part in f.relative_to(root).parts)}


def test_proof_images_draw_the_safe_areas_are_never_shipped_or_in_the_manifest_and_a_second_run_writes_nothing(pack, tmp_path):
    proof = pack / OUT / "_proof"
    names = sorted(f.name for f in proof.glob("*.png"))
    assert names == sorted(["avatar-400.png", "avatar-800.png", *[f"{k}.png" for k in BANNERS]])
    for fname, (w, h) in BANNERS.items():
        data = (proof / f"{fname}.png").read_bytes()
        assert png_size(data) == (w, h)
        assert ink(proof / f"{fname}.png").red, f"{fname}: the dashed safe rectangle is not drawn"
        assert data != (pack / OUT / f"{fname}-{w}x{h}.png").read_bytes()
    assert not [a for a in manifest(pack)["artefacts"] if "_proof" in a["path"]]
    # a second run on a copy of the pack: it says it wrote nothing, no file outside the _* folders differs by a byte from the first build, and none carries a date
    again = tmp_path / "again"
    shutil.copytree(pack, again)
    first = assets_tree(again)
    r = profiles(again, "--tagline", TAG)
    assert r.returncode == 0 and " 0 written" in r.stdout, r.stdout + r.stderr
    assert assets_tree(again) == first
    dated = {f: determinism.lint_file(again / "assets" / f) for f in first}
    assert not any(dated.values()), dated        # the lint `verify-idempotent` runs over its tree: no tIME or date chunk in a PNG


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
    # five faults in that one copy, each told by its own words: one note loses the label; the recorded safe circle shrinks below where the ink is and so does a
    # banner's safe rectangle (the gate re-measures both from the pixels); a banner's recorded size is not the file's; a banner file disappears (moved, not deleted)
    path, banner, cover = f"{OUT}/avatar-400.png", f"{OUT}/linkedin-banner-1584x396.png", f"{OUT}/facebook-cover-820x312.png"
    fix = {path: dict(note="profile photo", safe_radius_px=10), banner: dict(safe={"x": 0, "y": 0, "width": 10, "height": 10}), cover: dict(size="820x311")}

    def break_rows(d):
        for a in d["artefacts"]:
            a.update(fix.get(a["path"], {}))
    mutate_json(c / "assets/manifest.json", break_rows)
    moved = c / OUT / "x-header-1500x500.png"
    shutil.move(str(moved), str(tmp_path / "moved.png"))
    assert not moved.exists()
    r = bc("check", project=c)
    failed = {ln.split(" ")[1]: ln for ln in r.stdout.splitlines() if ln.startswith("[FAIL] ")}      # row id -> its line
    assert r.returncode == 1 and "tierb:labels" in failed and "tierb:profiles" in failed, r.stdout
    assert path in failed["tierb:labels"], failed["tierb:labels"]
    prof = failed["tierb:profiles"]
    assert "outside the safe circle of 10 px" in prof and "x-header: x-header-1500x500.png is not written" in prof, prof
    assert re.search(rf"{re.escape(banner)}: ink box \(\d+, \d+, \d+, \d+\) is outside the safe rectangle", prof), prof
    assert f"{cover}: the file is 820x312, the manifest says 820x311" in prof, prof


def test_bands_are_recorded_for_the_marks_size_and_sizes_are_in_the_manifest(pack):
    a = row(pack, f"{OUT}/avatar-800.png")
    assert a["size"] == "800x800" and a["slot"] == "profile-avatar" and a["band"] and a["specs"] == ["profile-avatar"] and a["safe_radius_px"] > 0
    b = row(pack, f"{OUT}/instagram-story-1080x1920.png")
    assert b["size"] == "1080x1920" and b["resampled_by"] == "PAGE" and b["safe"] == {"x": 60, "y": 260, "width": 960, "height": 1400}


def test_a_size_the_spec_row_drops_is_retired_moved_never_deleted(acme, plugin_copy):
    """On the Quick tier (acme): the files that retire are avatars, and no card is rendered."""
    assert profiles(acme).returncode == 0
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate(f, '"sizes": { "px": [400, 800], "safe_circle": 0.72 }', '"sizes": { "px": [800], "safe_circle": 0.72 }')
    r = profiles(acme, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (acme / OUT / "avatar-400.png").exists() and (acme / OUT / "avatar-800.png").is_file()
    assert (acme / "removed-2026-10-17" / OUT / "avatar-400.png").is_file()
    assert f"{OUT}/avatar-400.png" in report(acme, "emit-profiles")["retired"]
    assert not [a for a in manifest(acme)["artefacts"] if a["path"] == f"{OUT}/avatar-400.png"]


def test_the_entry_point_dispatches_profiles_and_check_names_the_report():
    entry = (ROOT / "bin/brand-creator").read_text()
    assert "presskit|profiles) py" in entry and "emit profiles " in entry
    assert '"profiles"' in (ROOT / "scripts/check.py").read_text()
    r = bc("emit", "profiles", "--help")
    assert r.returncode == 0 and "usage:" in r.stdout and "emit profiles" in r.stdout
