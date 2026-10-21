"""emit windows, linux, tray, tauri, wallet, developer: structure (sizes, layers, bit depth, alpha), spec-driven sizes, band choice,
facts-only text, the states gate, no silent fallbacks, idempotence and mutation tests.

Expected values are worked out by hand (the Acme wordmark is 282.17 x 77.82, so 3.626:1; the accent #007d71 is 5.03:1 on white and
4.17:1 on black) or are properties of the output (dimensions, alpha, header fields). Sizes come from platform-specs.json through
`specs`, the one table the emitters read: a test that read them from the emitter would prove nothing."""
import json
import os
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from helpers import FIXTURES, OFF_MAC_TAURI, ROOT, bc, downscale_report, failing, make_project, mutate, mutate_json, report

import specs
from px_lib import from_png
from pxio import png_color_type, png_size, read_ico_sizes, read_png

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]
macos = pytest.mark.requires_macos


def emit(p, target, *extra, **kw):
    return bc("emit", target, *extra, project=p, **kw)


def manifest(p):
    return json.loads((p / "assets" / "manifest.json").read_text())


def row(p, path):
    return next(a for a in manifest(p)["artefacts"] if a["path"] == path)


def with_facts(p):
    shutil.copy2(FIXTURES / "FACTS.md", p / "FACTS.md")


def bare_path(tmp_path, *, without: tuple[str, ...] = ()) -> dict:
    """A PATH with the tools the emitters need as symlinks, minus the ones named in `without`."""
    d = tmp_path / "bare"
    d.mkdir(exist_ok=True)
    for tool in ("uv", "node", "python3", "bash", "env", "dirname", "readlink", "mkdir", "cat", "resvg", "magick", "iconutil", "xcrun", "sips", "assetutil"):
        found = shutil.which(tool)
        if found and tool not in without and not (d / tool).exists():
            (d / tool).symlink_to(found)
    return {"PATH": str(d)}


def pixels(path: Path):
    return read_png(path.read_bytes())


# ================================================================ spec rows

def test_every_row_the_new_emitters_use_exists_with_a_source_and_a_status():
    rows = specs.load()["rows"]
    used = ["apple-app-icon", "apple-icon-composer", "apple-marketing-icon", "apple-macos-iconset", "apple-visionos-stack", "apple-menubar-template",
            "apple-dmg-background", "apple-store-frames", "windows-ico", "windows-nsis", "windows-tray", "tauri-icons", "linux-hicolor", "linux-tray",
            "linux-appstream", "apple-wallet", "google-wallet", "email-logo", "nuget-icon", "github-org-avatar", "cli-identity"]
    assert set(used) <= set(rows)
    for rid in used:
        r = rows[rid]
        assert r["source_url"].startswith("https://") and r["status"] in "VRU" and r["checked"] >= "2026-10-01", rid
        assert r["notes"], f"{rid} has no notes (what the row means and what is unverified)"
    # rows whose number nobody read at the platform's own page must not claim V
    assert {rid for rid in used if rows[rid]["status"] == "V"} == {"apple-app-icon", "windows-ico", "apple-wallet", "google-wallet"}


def test_a_unverified_or_stale_row_is_warned_in_the_report_and_stamped_in_the_manifest(acme, plugin_copy):
    r = emit(acme, "windows")
    assert r.returncode == 0, r.stdout + r.stderr
    warns = [x["detail"] for x in report(acme, "emit-windows")["results"] if x["id"] == "spec"]
    assert any("windows-nsis" in w and "UNVERIFIED" in w for w in warns)
    stamped = manifest(acme)["specs"]
    assert stamped["windows-nsis"]["status"] == "U" and stamped["windows-ico"]["status"] == "V" and stamped["windows-ico"]["stale"] is False
    # make the V row stale in a copy of the plugin: the report and the manifest say so
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate(f, '"checked": "2026-10-17",\n      "status": "V",\n      "notes": "Bare minimum layers', '"checked": "2025-01-02",\n      "status": "V",\n      "notes": "Bare minimum layers')
    r = emit(acme, "windows", plugin=plugin_copy)
    assert r.returncode == 0
    assert any("windows-ico" in x["detail"] and "stale" in x["detail"] for x in report(acme, "emit-windows")["results"] if x["id"] == "spec")
    assert manifest(acme)["specs"]["windows-ico"]["stale"] is True
    assert bc("check", project=acme).returncode != 2  # check reads the stamp; it warns, it does not crash


def test_platform_specs_markdown_is_generated_from_the_json_and_current():
    shipped = (ROOT / "skills/brand-creator/references/platform-specs.md").read_text()
    assert shipped == specs.markdown(), "references/platform-specs.md is stale: run `brand-creator specs-due --write-markdown skills/brand-creator/references/platform-specs.md`"
    assert shipped.startswith("# Platform specs") and specs.GENERATED_MARK in shipped and "## Contents" in shipped
    doc = specs.load()
    for rid, r in doc["rows"].items():
        assert f"## {rid}\n" in shipped and r["source_url"] in shipped
    # mutation: a size changed in the JSON makes the committed file differ (so the lint can fail)
    changed = json.loads(json.dumps(doc))
    changed["rows"]["windows-ico"]["sizes"]["layers"] = [16, 24, 32, 48, 128]
    assert specs.markdown(changed) != shipped


def test_specs_due_markdown_flag_prints_the_same_document(tmp_path):
    r = bc("specs-due", "--markdown")
    assert r.returncode == 0 and r.stdout == specs.markdown()
    out = tmp_path / "ref.md"
    assert bc("specs-due", "--write-markdown", str(out)).returncode == 0 and out.read_text() == specs.markdown()


# ================================================================ windows

def bmp_header(path: Path):
    d = path.read_bytes()
    magic, _size = struct.unpack("<2sI", d[:6])
    w, h, planes, bits, comp = struct.unpack("<iiHHI", d[18:34])
    return magic, w, abs(h), planes, bits, comp


def test_windows_ico_layers_and_nsis_bitmaps_follow_the_spec(acme):
    r = emit(acme, "windows")
    assert r.returncode == 0, r.stdout + r.stderr
    base = acme / "assets/windows"
    assert sorted(str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()) == ["app.ico", "nsis/header.bmp", "nsis/sidebar.bmp"]
    ico, nsis = specs.sizes("windows-ico"), specs.sizes("windows-nsis")
    assert ico["layers"] == [16, 24, 32, 48, 256]
    assert read_ico_sizes((base / "app.ico").read_bytes()) == [(s, s) for s in ico["layers"]]
    for fname, key in (("header.bmp", "header"), ("sidebar.bmp", "sidebar")):
        magic, w, h, planes, bits, comp = bmp_header(base / "nsis" / fname)
        assert (magic, w, h, planes, bits, comp) == (b"BM", nsis[key]["width"], nsis[key]["height"], 1, 24, 0), fname
    assert (nsis["header"]["width"], nsis["header"]["height"]) == (150, 57) and (nsis["sidebar"]["width"], nsis["sidebar"]["height"]) == (164, 314)
    assert report(acme, "emit-windows")["status"] == "pass"


def test_each_ico_layer_is_drawn_by_the_band_rule_for_its_size(acme):
    assert emit(acme, "windows").returncode == 0
    a = row(acme, "assets/windows/app.ico")
    # Acme's bands (qa/rules.json): small up to 32 px, large above; the layer list is the spec row's
    assert a["layer_bands"] == {"16": "small", "24": "small", "32": "small", "48": "large", "256": "large"}
    assert a["resampled_by"] == "OURS" and a["slot"] == "windows-ico"
    # and the 16 px layer is the coarse-grid drawing, not the fine vector: its accent is a solid block of at least 4 x 4 px
    d = (acme / "assets/windows/app.ico").read_bytes()
    n = struct.unpack("<H", d[4:6])[0]
    ents = [struct.unpack("<BBBBHHII", d[6 + 16 * i:22 + 16 * i]) for i in range(n)]
    w, h, px = read_png(d[ents[0][7]:ents[0][7] + ents[0][6]])
    assert (w, h) == (16, 16)
    teal = [(i % w, i // w) for i in range(w * h) if px[i * 4 + 3] == 255 and abs(px[i * 4] - 0) < 40 and abs(px[i * 4 + 1] - 125) < 40 and abs(px[i * 4 + 2] - 113) < 40]
    xs, ys = {x for x, _ in teal}, {y for _, y in teal}
    assert len(teal) >= 12 and max(xs) - min(xs) >= 3 and max(ys) - min(ys) >= 3


def test_nsis_bit_depth_gate_fails_when_the_spec_asks_for_another_depth(acme, plugin_copy):
    f = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate(f, '"bit_depth": 24', '"bit_depth": 32')
    r = emit(acme, "windows", plugin=plugin_copy)
    assert r.returncode == 1
    rep = report(acme, "emit-windows")
    assert "check:header.bmp bit depth" in failing(rep) and "check:sidebar.bmp bit depth" in failing(rep)


def test_windows_second_run_writes_nothing(acme):
    assert emit(acme, "windows").returncode == 0
    files = sorted(p for p in (acme / "assets/windows").rglob("*") if p.is_file())
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    r = emit(acme, "windows")
    assert r.returncode == 0 and "0 written, 3 unchanged" in r.stdout
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}


def test_windows_without_imagemagick_is_exit_3_with_the_install_hint(acme, tmp_path):
    r = emit(acme, "windows", env=bare_path(tmp_path, without=("magick",)))
    assert r.returncode == 3 and "ImageMagick" in r.stderr


def test_every_emitter_needs_gate_g3(tmp_path):
    from helpers import make_project, install_fixture
    p = make_project(tmp_path)
    install_fixture(p)
    assert bc("tokens", project=p).returncode == 0
    for target in ("windows", "linux", "tray", "tauri", "wallet", "developer"):
        r = emit(p, target)
        assert r.returncode == 1 and "G3" in r.stderr, target


# ================================================================ linux

def test_linux_hicolor_tree_sizes_and_scalable_svg(acme):
    r = emit(acme, "linux", "--app-id", "org.example.Acme")
    assert r.returncode == 0, r.stdout + r.stderr
    hic = specs.sizes("linux-hicolor")
    base = acme / "assets/linux/usr/share/icons/hicolor"
    for s in hic["px"]:
        assert png_size((base / f"{s}x{s}/apps/acme.png").read_bytes()) == (s, s)
    dirs = sorted(d.name for d in base.iterdir())
    assert dirs == sorted([f"{s}x{s}" for s in hic["px"]] + ["scalable"])
    svg = (base / "scalable/apps/acme.svg").read_text()
    assert svg.startswith("<svg") and "<text" not in svg and "font-family" not in svg
    assert row(acme, "assets/linux/usr/share/icons/hicolor/16x16/apps/acme.png")["band"] == "small"
    assert row(acme, "assets/linux/usr/share/icons/hicolor/512x512/apps/acme.png")["band"] == "large"
    assert report(acme, "emit-linux")["status"] == "pass"


def test_metainfo_text_fields_come_from_facts_only_and_gaps_are_reported(acme):
    # the scaffolded FACTS.md holds only its example row: every text field is empty and says so
    assert emit(acme, "linux", "--app-id", "org.example.Acme").returncode == 0
    f = acme / "assets/linux/usr/share/metainfo/org.example.Acme.metainfo.xml"
    root = ET.parse(f).getroot()
    assert root.tag == "component" and root.findtext("id") == "org.example.Acme" and root.findtext("name") == "Acme"
    for tag in ("summary", "metadata_license", "project_license"):
        assert (root.findtext(tag) or "") == "", tag
    warns = {x["id"] for x in report(acme, "emit-linux")["results"] if x["status"] == "warn" and x["id"].startswith("metainfo:")}
    assert warns == {"metainfo:appstream summary", "metainfo:appstream description", "metainfo:project license", "metainfo:metadata license"}
    # with FACTS.md filled, the elements carry exactly those values (and nothing else is invented)
    with_facts(acme)
    assert emit(acme, "linux", "--app-id", "org.example.Acme").returncode == 0
    root = ET.parse(f).getroot()
    assert root.findtext("summary") == "Hand tools with a published spare-parts list"
    assert root.findtext("project_license") == "MIT" and root.findtext("metadata_license") == "CC0-1.0"
    assert root.findtext("description/p").startswith("Acme makes small-batch hand tools.")
    assert root.find("url") is None  # no homepage fact, no URL
    assert not [x for x in report(acme, "emit-linux")["results"] if x["id"].startswith("metainfo:") and x["status"] == "warn"]
    # mutation: change a fact and the metainfo follows it
    mutate(acme / "FACTS.md", "| project license | MIT |", "| project license | Apache-2.0 |")
    assert emit(acme, "linux", "--app-id", "org.example.Acme").returncode == 0
    assert ET.parse(f).getroot().findtext("project_license") == "Apache-2.0"


def test_metainfo_without_an_app_id_is_a_flagged_stub(acme):
    assert emit(acme, "linux").returncode == 0
    f = acme / "assets/linux/usr/share/metainfo/acme.metainfo.xml"
    assert (ET.parse(f).getroot().findtext("id") or "") == ""
    assert any(x["id"] == "metainfo:--app-id" for x in report(acme, "emit-linux")["results"])


# ================================================================ tray

STATES = ("idle", "active", "error")


def tray(p, *extra, **kw):
    return emit(p, "tray", *extra, **kw)


def test_tray_writes_every_size_for_every_state_and_runs_the_states_gate(acme):
    r = tray(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    win, lin, mac = specs.sizes("windows-tray"), specs.sizes("linux-tray"), specs.sizes("apple-menubar-template")
    base = acme / "assets/tray"
    for mode in ("light", "dark"):
        for s in win["px"]:
            for st in STATES:
                assert png_size((base / f"windows/{mode}/{st}-{s}.png").read_bytes()) == (s, s)
    for s in lin["px"]:
        for st in STATES:
            assert png_size((base / f"linux/{st}-{s}.png").read_bytes()) == (s, s)
    for st in STATES:
        assert png_size((base / f"macos/{st}Template@{mac['scale']}x.png").read_bytes()) == (mac["width"], mac["height"]) == (32, 36)
    assert len([p for p in base.rglob("*.png")]) == 2 * len(win["px"]) * 3 + len(lin["px"]) * 3 + 3
    rep = report(acme, "emit-tray")
    assert rep["status"] == "pass" and any(x["id"] == "gate:states-check" and x["status"] == "pass" for x in rep["results"])
    states = report(acme, "states")
    assert states["status"] == "pass" and states["states_files"] == ["qa/states.json", "qa/states.tray.json"]
    assert len({x["set"] for x in states["results"] if x["id"].startswith("states:tray-")}) == 2 * len(win["px"]) + len(lin["px"]) + 1
    assert all(a["qa"] == ["states"] for a in manifest(acme)["artefacts"] if a["path"].startswith("assets/tray/"))


def test_dark_taskbar_set_is_the_light_set_recoloured_exactly_through_the_token_roles(acme):
    assert tray(acme).returncode == 0
    lw, lh, lp = pixels(acme / "assets/tray/windows/light/idle-16.png")
    dw, dh, dp = pixels(acme / "assets/tray/windows/dark/idle-16.png")
    assert (lw, lh) == (dw, dh) == (16, 16)
    ink_l = {tuple(lp[i * 4:i * 4 + 3]) for i in range(256) if lp[i * 4 + 3] == 255}
    ink_d = {tuple(dp[i * 4:i * 4 + 3]) for i in range(256) if dp[i * 4 + 3] == 255}
    assert ink_l == {(0x0d, 0x1b, 0x2d)}          # the ring is the light ink #0d1b2d
    assert ink_d == {(0xf0, 0xee, 0xe7)}          # recoloured to the dark ink #f0eee7 (color.mark light -> dark)
    assert [lp[i * 4 + 3] for i in range(256)] == [dp[i * 4 + 3] for i in range(256)]  # the same shape


def test_macos_template_is_black_plus_alpha_with_the_glyph_centred(acme):
    assert tray(acme).returncode == 0
    w, h, px = pixels(acme / "assets/tray/macos/activeTemplate@2x.png")
    assert (w, h) == (32, 36)
    ink = [(i % w, i // w) for i in range(w * h) if px[i * 4 + 3]]
    assert ink and all(tuple(px[i * 4:i * 4 + 3]) == (0, 0, 0) for i in range(w * h) if px[i * 4 + 3])
    assert min(y for _, y in ink) >= 2 and max(y for _, y in ink) <= 33  # a 32 px glyph centred on 36 rows leaves 2 px above and below
    assert all(px[i * 4 + 3] == 0 for i in range(w * 2))                  # the top two rows are empty


def test_a_size_without_a_fitting_master_is_an_error_not_a_blurry_resample(acme):
    mutate_json(acme / "tray/tray.json", lambda d: d["states"]["idle"].pop("24"))
    r = tray(acme)
    assert r.returncode == 2 and "no master fits 24 px" in r.stderr and "'idle'" in r.stderr


def test_two_states_that_look_alike_fail_the_gate(acme):
    # point `error` at the idle masters: identical shapes, so states-check must fail and the emit exits 1
    mutate_json(acme / "tray/tray.json", lambda d: d["states"].__setitem__("error", dict(d["states"]["idle"])))
    r = tray(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    rep = report(acme, "emit-tray")
    gate = next(x for x in rep["results"] if x["id"] == "gate:states-check")
    assert gate["status"] == "fail" and "idle" in gate["detail"] and "error" in gate["detail"]
    assert report(acme, "states")["status"] == "fail"
    assert bc("check", project=acme).returncode == 1  # check reads the failing states report too


def test_a_colour_the_tokens_do_not_map_stops_the_dark_set(acme):
    from px_lib import Img
    odd = Img(16, 16)
    odd.rect(4, 4, 8, 8, "#c0392b")   # not a token colour
    (acme / "assets/tray-src/idle-16.png").write_bytes(odd.png())
    r = tray(acme)
    assert r.returncode == 2 and "#c0392b" in r.stderr and "not mapped light to dark" in r.stderr


def test_explicit_dark_artwork_is_used_as_given(acme):
    # the owner's own dark masters (a ring in a colour no token maps to) win over the recolour, so nothing is rewritten
    cfg = json.loads((acme / "tray/tray.json").read_text())
    idle = cfg["states"]["idle"]
    dark = {}
    for n, rel in idle.items():
        w, h, px = pixels(acme / rel)
        im = from_png((acme / rel).read_bytes())
        for i in range(0, len(im.p), 4):
            if im.p[i + 3]:
                im.p[i:i + 3] = bytes((0xff, 0xd4, 0x00))
        dark[n] = rel.replace("idle-", "idle-dark-")
        (acme / dark[n]).write_bytes(im.png())
    cfg["states"]["idle"] = {"light": idle, "dark": dark}
    (acme / "tray/tray.json").write_text(json.dumps(cfg))
    assert tray(acme).returncode == 0
    _w, _h, px = pixels(acme / "assets/tray/windows/dark/idle-16.png")
    assert {tuple(px[i * 4:i * 4 + 3]) for i in range(256) if px[i * 4 + 3] == 255} == {(0xff, 0xd4, 0x00)}
    _w, _h, px = pixels(acme / "assets/tray/windows/light/idle-16.png")
    assert {tuple(px[i * 4:i * 4 + 3]) for i in range(256) if px[i * 4 + 3] == 255} == {(0x0d, 0x1b, 0x2d)}


def test_tray_config_errors_are_usage_errors(acme):
    (acme / "tray/tray.json").write_text(json.dumps({"schema": 1, "states": {"idle": "assets/tray-src/idle-16.png"}}))
    r = tray(acme)
    assert r.returncode == 2 and "at least two states" in r.stderr
    (acme / "tray/tray.json").unlink()
    r = tray(acme)
    assert r.returncode == 2 and "no tray config" in r.stderr


def test_tray_second_run_writes_nothing(acme):
    assert tray(acme).returncode == 0
    r = tray(acme)
    assert r.returncode == 0 and " 0 written" in r.stdout


# ================================================================ tauri

def test_tauri_icons_folder_follows_the_spec(acme):
    r = emit(acme, "tauri", *OFF_MAC_TAURI)   # off macOS there is no iconutil: the Pillow .icns writer is the explicit opt-in
    assert r.returncode == 0, r.stdout + r.stderr
    spec = specs.sizes("tauri-icons")
    base = acme / "assets/tauri/src-tauri/icons"
    assert sorted(f.name for f in base.iterdir()) == sorted(list(spec["png"]) + ["icon.ico", "icon.icns"])
    for name, px in spec["png"].items():
        assert png_size((base / name).read_bytes()) == (px, px)
    assert [w for w, _ in read_ico_sizes((base / "icon.ico").read_bytes())] == spec["ico_order"] and spec["ico_order"][0] == 32
    icns = (base / "icon.icns").read_bytes()
    assert icns[:4] == b"icns" and int.from_bytes(icns[4:8], "big") == len(icns)
    assert report(acme, "emit-tauri")["status"] == "pass"


@macos
def test_tauri_icns_by_iconutil_holds_every_rendition(acme, tmp_path):
    assert emit(acme, "tauri").returncode == 0
    out = tmp_path / "x.iconset"
    cp = subprocess.run(["iconutil", "-c", "iconset", str(acme / "assets/tauri/src-tauri/icons/icon.icns"), "-o", str(out)], capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr
    mac = specs.sizes("apple-macos-iconset")
    want = {f"icon_{pt}x{pt}{'@2x' if sc == 2 else ''}.png": pt * sc for pt in mac["points"] for sc in mac["scales"]}
    assert len(want) == 10
    got = {f.name: png_size(f.read_bytes()) for f in out.glob("*.png")}
    assert got == {n: (s, s) for n, s in want.items()}
    # the legacy body is 824 of 1024 px: the 512 px rendition keeps a transparent margin of (1 - 824/1024) / 2 each side
    w, h, px = read_png((out / "icon_256x256@2x.png").read_bytes())
    assert (w, h) == (512, 512) and px[3] == 0 and px[(256 * 512 + 256) * 4 + 3] == 255
    xs = [i % w for i in range(w * h) if px[i * 4 + 3] == 255]
    assert min(xs) >= round(512 * (1 - 824 / 1024) / 2) - 1


def test_tauri_pillow_is_an_explicit_opt_in_and_says_so(acme):
    r = emit(acme, "tauri", "--renderer", "pillow")
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(acme, "emit-tauri")
    assert "Pillow (.icns, explicit --renderer pillow)" in rep["renderer"]
    icns = (acme / "assets/tauri/src-tauri/icons/icon.icns").read_bytes()
    assert icns[:4] == b"icns"
    sizes = {a for a in (b"ic07", b"ic08", b"ic09", b"ic10", b"ic11", b"ic12", b"ic13", b"ic14") if a in icns}
    assert len(sizes) == 8  # Pillow's writer entries; it has no 16 px entry, and the report says that
    assert "no 16 px entry" in row(acme, "assets/tauri/src-tauri/icons/icon.icns")["note"]


def test_tauri_without_iconutil_and_without_the_opt_in_is_exit_3(acme, tmp_path):
    r = emit(acme, "tauri", env=bare_path(tmp_path, without=("iconutil",)))
    assert r.returncode == 3 and "--renderer pillow" in r.stderr
    # the opt-in works on the same PATH
    assert emit(acme, "tauri", "--renderer", "pillow", env=bare_path(tmp_path, without=("iconutil",))).returncode == 0


# ================================================================ wallet

def test_apple_wallet_images_are_point_sizes_times_the_scale(acme):
    r = emit(acme, "wallet")
    assert r.returncode == 0, r.stdout + r.stderr
    base = acme / "assets/wallet/apple"
    # worked by hand for the Acme wordmark (282.17 x 77.82 = 3.626:1): logo 50 pt high would be 181 pt wide (max 160), so it is 160 x 44.1 pt;
    # primaryLogo 30 pt high is 108.8 pt wide; secondaryLogo 12 pt high is 43.5 pt wide (centred on the 12 pt minimum width if narrower)
    want = {"icon@2x.png": (76, 76), "icon@3x.png": (114, 114), "logo@2x.png": (320, 88), "logo@3x.png": (480, 132),
            "primaryLogo@2x.png": (218, 60), "primaryLogo@3x.png": (326, 90), "secondaryLogo@2x.png": (87, 24), "secondaryLogo@3x.png": (131, 36),
            "order-logo.png": (300, 300)}
    assert sorted(f.name for f in base.iterdir()) == sorted(want)
    for name, size in want.items():
        assert png_size((base / name).read_bytes()) == size, name
    spec = specs.sizes("apple-wallet")
    assert spec["scales"] == [2, 3] and spec["icon"] == {"width": 38, "height": 38} and spec["order_logo_px"] == 300
    # the order-tracking logo is opaque
    _w, _h, px = pixels(base / "order-logo.png")
    assert all(px[i] == 255 for i in range(3, len(px), 4))
    # the pass logos stay inside the HIG widths
    for key in ("logo", "primaryLogo", "secondaryLogo"):
        for sc in (2, 3):
            w, h = png_size((base / f"{key}@{sc}x.png").read_bytes())
            assert spec[key]["min_width"] * sc <= w <= spec[key]["max_width"] * sc and h <= spec[key]["height"] * sc, (key, sc)


def test_google_wallet_logo_is_circle_safe_and_the_wide_logo_is_transparent(acme):
    assert emit(acme, "wallet").returncode == 0
    g = acme / "assets/wallet/google"
    assert sorted(f.name for f in g.iterdir()) == ["logo-660.png", "wide-logo-1280x400.png"]
    w, h, px = pixels(g / "logo-660.png")
    assert (w, h) == (660, 660) and all(px[i] == 255 for i in range(3, len(px), 4))   # opaque, full bleed
    bg = tuple(px[:3])
    far = max(((i % w + 0.5 - w / 2) ** 2 + (i // w + 0.5 - h / 2) ** 2) ** 0.5 for i in range(w * h) if max(abs(px[i * 4 + c] - bg[c]) for c in range(3)) > 24)
    assert far <= (0.5 - 0.15) * 660 + 1.5   # every mark pixel inside the circle that keeps a 15 percent margin
    ww, wh, wp = pixels(g / "wide-logo-1280x400.png")
    assert (ww, wh) == (1280, 400) and wp[3] == 0 and wp[(ww * wh - 1) * 4 + 3] == 0
    ink = [(i % ww, i // ww) for i in range(ww * wh) if wp[i * 4 + 3]]
    assert min(y for _, y in ink) >= 400 * 0.15 - 2 and max(y for _, y in ink) <= 400 * 0.85 + 2


def test_a_logo_art_that_is_not_pure_vector_is_refused(acme):
    (acme / "assets/logo/lockup.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 20"><text x="0" y="15">Acme</text></svg>')
    r = emit(acme, "wallet")
    assert r.returncode == 1 and "not pure vector" in r.stderr


def test_wallet_second_run_writes_nothing(acme):
    assert emit(acme, "wallet").returncode == 0
    assert " 0 written" in emit(acme, "wallet").stdout


# ================================================================ developer

TAG = "a repair guide is in every box"


def developer(p, *extra, **kw):
    return emit(p, "developer", *extra, **kw)


def test_developer_pack_sizes_and_alpha(acme):
    r = developer(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    base = acme / "assets/developer"
    em, ng, av = specs.sizes("email-logo"), specs.sizes("nuget-icon"), specs.sizes("github-org-avatar")
    # the wordmark is 3.626:1 and shown 24 px high: 87 x 24 at 1x, then 174 x 48 and 261 x 72
    for name, size in (("acme-email-logo.png", (87, 24)), ("acme-email-logo@2x.png", (174, 48)), ("acme-email-logo@3x.png", (261, 72))):
        assert png_size((base / "email" / name).read_bytes()) == size, name
    _w, _h, px = pixels(base / "email/acme-email-logo.png")
    assert px[3] == 0  # transparent
    assert png_size((base / f"nuget/acme-nuget-{ng['px']}.png").read_bytes()) == (128, 128)
    assert (base / f"nuget/acme-nuget-{ng['px']}.png").stat().st_size <= ng["max_bytes"]
    assert png_size((base / f"avatar/acme-avatar-{av['px']}.png").read_bytes()) == (1024, 1024)
    for f in (base / "nuget", base / "avatar"):
        _w, _h, px = pixels(next(f.glob("*.png")))
        assert all(px[i] == 255 for i in range(3, len(px), 4))   # an opaque ground, whatever page it lands on
    assert report(acme, "emit-developer")["status"] == "pass"


def test_cli_identity_uses_the_named_ansi_colour_when_the_brand_colour_fails_a_ground(acme):
    assert developer(acme, "--tagline", TAG).returncode != 0   # FACTS.md has no such row yet
    with_facts(acme)
    assert developer(acme, "--tagline", TAG).returncode == 0
    d = acme / "assets/developer/cli"
    colour = (d / "identity.txt").read_text()
    # the light accent #007d71 is 5.03:1 on white but 4.17:1 on black, the dark accent #4cd7c8 is 1.77:1 on white: neither reaches 4.5 on both,
    # and teal is nearest to cyan (SGR 36), so the named colour is used and no 24-bit sequence appears
    assert colour == f"\x1b[1m\x1b[36mAcme\x1b[0m\n{TAG}\n"
    assert "38;2" not in colour
    assert (d / "identity.plain.txt").read_text() == f"Acme\n{TAG}\n" and "\x1b" not in (d / "identity.plain.txt").read_text()
    info = next(x for x in report(acme, "emit-developer")["results"] if x["id"] == "cli:color.accent")
    assert "ANSI 36 (cyan)" in info["detail"] and "5.03:1 on light" in info["detail"] and "4.17:1 on dark" in info["detail"]


def test_cli_identity_uses_24_bit_only_when_both_grounds_pass(acme):
    with_facts(acme)
    mutate_json(acme / "assets/tokens/tokens.json", lambda d: d["modes"]["light"]["color.accent"].__setitem__("hex", "#767676"))   # 4.54:1 on white, 4.62:1 on black
    assert developer(acme, "--tagline", TAG).returncode == 0
    text = (acme / "assets/developer/cli/identity.txt").read_text()
    assert text.startswith("\x1b[1m\x1b[38;2;118;118;118mAcme\x1b[0m")
    # a grey that fails a ground and has no hue to name falls back to the terminal's own text colour, never to a guessed ANSI colour
    mutate_json(acme / "assets/tokens/tokens.json", lambda d: (d["modes"]["light"]["color.accent"].__setitem__("hex", "#aaaaaa"),
                                                              d["modes"]["dark"]["color.accent"].__setitem__("hex", "#555555")))
    assert developer(acme, "--tagline", TAG).returncode == 0
    text = (acme / "assets/developer/cli/identity.txt").read_text()
    assert text.startswith("\x1b[1mAcme\x1b[0m") and "38;2" not in text and "\x1b[3" not in text


def test_the_tagline_must_be_a_facts_value(acme):
    r = developer(acme, "--tagline", "the best tools in the world")
    assert r.returncode == 1 and "not a value in FACTS.md" in r.stderr


def test_a_shrunk_master_from_another_band_needs_a_stated_exemption(acme):
    r = developer(acme, "--master-band", "small")
    assert r.returncode == 1 and "--exemption" in r.stderr
    assert not (acme / "assets/developer").exists()   # refused before anything was written
    r = developer(acme, "--master-band", "small", "--exemption", "the host shrinks this one file to 16 px")
    assert r.returncode == 0, r.stdout + r.stderr
    a = row(acme, "assets/developer/avatar/acme-avatar-1024.png")
    assert a["band"] == "small" and a["exemption"] == "the host shrinks this one file to 16 px" and a["resampled_by"] == "SYS" and a["qa"] == ["downscale"]
    assert developer(acme, "--exemption", "x").returncode == 2


def test_developer_second_run_writes_nothing(acme):
    assert developer(acme).returncode == 0
    assert " 0 written" in developer(acme).stdout


# ================================================================ the whole chain and check

def test_check_reads_the_new_emit_reports_and_every_pack_survives_it(acme):
    with_facts(acme)
    for target, extra in (("windows", ()), ("linux", ("--app-id", "org.example.Acme")), ("tray", ()), ("tauri", tuple(OFF_MAC_TAURI)), ("wallet", ()), ("developer", ())):
        assert emit(acme, target, *extra).returncode == 0, target
    assert bc("logo-sheet", project=acme).returncode == 0
    r = bc("check", project=acme)
    out = r.stdout
    for tool in ("emit-windows", "emit-linux", "emit-tray", "emit-tauri", "emit-wallet", "emit-developer"):
        assert f"[PASS] report:{tool}" in out, tool
    # the downscale rows (avatar, nuget) ask for a downscale report that does not exist yet: not verified, never a pass
    assert "[SKIP] report:downscale" in out and r.returncode == 3
    # mutation: delete an emitted file and the manifest check fails
    f = acme / "assets/windows/app.ico"
    before = f.read_bytes()
    f.write_bytes(before[:-1] + bytes([before[-1] ^ 1]))
    assert f.read_bytes() != before
    r = bc("check", project=acme)
    assert r.returncode == 1 and "changed since emitted: assets/windows/app.ico" in r.stdout


def test_finish_chain_template_lists_every_emit_target_and_the_chain_guard():
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    dispatch = (ROOT / "bin/brand-creator").read_text()
    targets = [t for t in ("web", "social", "apple", "windows", "linux", "tray", "tauri", "wallet", "developer")]
    for t in targets:
        assert t in dispatch and (f" {t} " in tpl or f"{t})" in tpl or f"({t} " in tpl or f" {t})" in tpl), t
    assert "BRAND_CREATOR_CHAIN=1" in tpl and "verify-idempotent" in tpl and "staleness --write" in tpl and tpl.rstrip().endswith('"${BC[@]}" check')
    assert subprocess.run(["bash", "-n", str(ROOT / "templates/finish.sh.tpl")]).returncode == 0
    r = bc("root")
    assert r.returncode == 0 and r.stdout.strip() == str(ROOT) and '"${BC[@]}" root' in tpl
    assert "$(emit_args" not in tpl   # arguments live in arrays; an unquoted command substitution splits every multi-word value
    # the chain order: generators, tokens, contrast, emitters, gates, idempotence, staleness, check
    body = "\n".join(ln for ln in tpl.splitlines() if not ln.lstrip().startswith("#"))
    order = [body.index(s) for s in ('"${BC[@]}" tokens', '"${BC[@]}" contrast', '"${BC[@]}" emit "$t"', 'step "gates"', "verify-idempotent", "staleness --write", '"${BC[@]}" check')]
    assert order == sorted(order)


def test_a_generator_that_wipes_its_folder_refuses_to_run_outside_the_chain(tmp_path):
    gen = tmp_path / "wipe.py"
    gen.write_text(f"import sys\nsys.path.insert(0, {str(ROOT / 'scripts/lib')!r})\nfrom _common import require_chain, main_guard\n"
                   "def main():\n    require_chain('wipe.py')\n    print('wiped')\n    return 0\nmain_guard(main)\n")
    env = {k: v for k, v in os.environ.items() if k != "BRAND_CREATOR_CHAIN"}
    r = subprocess.run(["python3", str(gen)], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "run the whole chain" in r.stderr and "wiped" not in r.stdout
    r = subprocess.run(["python3", str(gen)], capture_output=True, text=True, env={**env, "BRAND_CREATOR_CHAIN": "1"})
    assert r.returncode == 0 and "wiped" in r.stdout


# ================================================================ web: the band rule (R3-02)

def ico_layers(path: Path) -> dict[int, tuple]:
    d = path.read_bytes()
    n = struct.unpack("<H", d[4:6])[0]
    out = {}
    for i in range(n):
        w, _h, _c, _r, _pl, _bpp, size, off = struct.unpack("<BBBBHHII", d[6 + 16 * i:22 + 16 * i])
        out[w or 256] = read_png(d[off:off + size])
    return out


def render_at(acme, drawing: str, n: int):
    import svgtools
    from _common import rasterise_svg
    svg = svgtools.fit((acme / drawing).read_text(encoding="utf-8"), n, n)
    return read_png(rasterise_svg(svg, n, n, renderer="resvg"))


def test_web_draws_every_favicon_layer_and_png_icon_by_the_band_rule(acme):
    assert emit(acme, "web").returncode == 0
    a = row(acme, "assets/web/favicon.ico")
    assert a["layer_bands"] == {"16": "small", "32": "small", "48": "large"} and a["slot"] == "favicon-ico" and a["band"] == "large"
    layers = ico_layers(acme / "assets/web/favicon.ico")
    # the 16 and 32 px layers are the coarse-grid drawing rendered at that size, the 48 px layer is the fine vector
    for n, drawing in ((16, "assets/logo/grid-mark.svg"), (32, "assets/logo/grid-mark.svg"), (48, "assets/logo/mark.svg")):
        assert layers[n][:2] == (n, n) and layers[n][2] == render_at(acme, drawing, n)[2], n
    assert layers[16][2] != render_at(acme, "assets/logo/mark.svg", 16)[2]   # not the fine vector at 16 px
    # every PNG icon records its band, and the rule's pick for its own size is the one recorded
    for path, size, band in (("apple-touch-icon.png", 180, "large"), ("icons/icon-192.png", 192, "large"), ("icons/icon-512.png", 512, "large"),
                             ("icons/maskable-512.png", 512, "large"), ("icons/monochrome-512.png", 512, "large")):
        r = row(acme, f"assets/web/{path}")
        assert r["band"] == band and r["size"] == f"{size}x{size}" and r["slot"].startswith(("pwa-icon", "apple-touch")), path
    assert "[PASS] manifest:bands" in bc("check", project=acme).stdout
    assert "rules_source" in report(acme, "emit-web") and report(acme, "emit-web")["status"] == "pass"


def test_icon_svg_is_the_drawing_a_tab_shows_by_the_band_rule_or_the_owners_favicon_drawing(acme):
    """Browsers that read icon.svg show it in the tab, at the smallest favicon layer's size: the small band's drawing, never the fine
    vector shrunk. favicon.drawing in qa/rules.json overrides it and is recorded, so a rerun keeps it."""
    logo = acme / "assets/logo"
    assert emit(acme, "web").returncode == 0
    svg = (acme / "assets/web/icon.svg").read_text()
    grid = (logo / "grid-mark.svg").read_text()
    assert 'shape-rendering="crispEdges"' in svg and "M4 0h2v1h-2z" in grid and "M4 0h2v1h-2z" in svg   # the coarse grid, not mark.svg
    assert "prefers-color-scheme:dark" in svg                                                          # with grid-mark-dark.svg
    assert row(acme, "assets/web/icon.svg")["drawing_file"] == "assets/logo/grid-mark.svg"
    rows = {x["id"]: x for x in report(acme, "emit-web")["results"]}
    assert "band rule's drawing for a 16 px tab" in rows["note:icon.svg drawing"]["detail"] and "note:icon.svg" not in rows
    # the owner names a drawing: it is used, and a second run without any flag keeps it
    mutate_json(acme / "qa/rules.json", lambda d: d.__setitem__("favicon", {"drawing": "assets/logo/mark.svg"}))
    for _ in range(2):
        assert emit(acme, "web").returncode == 0
        assert row(acme, "assets/web/icon.svg")["drawing_file"] == "assets/logo/mark.svg"
        assert "M4 0h2v1h-2z" not in (acme / "assets/web/icon.svg").read_text()
    assert "favicon.drawing in qa/rules.json" in next(x for x in report(acme, "emit-web")["results"] if x["id"] == "note:icon.svg drawing")["detail"]
    # a drawing with no dark file next to it: no switch, and the report says which file is missing
    shutil.copy2(logo / "mark.svg", logo / "tab.svg")
    mutate_json(acme / "qa/rules.json", lambda d: d.__setitem__("favicon", {"drawing": "assets/logo/tab.svg"}))
    assert emit(acme, "web").returncode == 0
    assert "prefers-color-scheme" not in (acme / "assets/web/icon.svg").read_text()
    warn = next(x for x in report(acme, "emit-web")["results"] if x["id"] == "note:icon.svg")
    assert warn["status"] == "warn" and "assets/logo/tab.svg" in warn["detail"]
    # its dark file is held to the drawing's rule: pure vector, or the emit stops (exit 1) instead of writing it into icon.svg
    (logo / "tab-dark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text x="1" y="9">A</text></svg>')
    r = emit(acme, "web")
    assert r.returncode == 1 and "mark_lint: assets/logo/tab-dark.svg is not pure vector" in r.stderr
    (logo / "tab-dark.svg").rename(acme / "tab-dark.svg")
    # a drawing that does not exist, or a key the rules do not know, is a usage error, never a silent default
    mutate_json(acme / "qa/rules.json", lambda d: d.__setitem__("favicon", {"drawing": "assets/logo/missing.svg"}))
    r = emit(acme, "web")
    assert r.returncode == 2 and "assets/logo/missing.svg must be an existing .svg file" in r.stderr
    mutate_json(acme / "qa/rules.json", lambda d: d.__setitem__("favicon", {"svg": "assets/logo/mark.svg"}))
    r = emit(acme, "web")
    assert r.returncode == 2 and "unknown key favicon.svg" in r.stderr


def test_the_band_rule_decides_the_web_layers_and_a_favicon_off_the_rule_fails_check(acme):
    # the owner moves the small band's limit up to 48 px: the 48 px layer is now the coarse drawing
    mutate_json(acme / "qa/rules.json", lambda d: d["bands"][0].__setitem__("max_px", 48))
    assert emit(acme, "web").returncode == 0
    assert row(acme, "assets/web/favicon.ico")["layer_bands"] == {"16": "small", "32": "small", "48": "small"}
    assert ico_layers(acme / "assets/web/favicon.ico")[48][2] == render_at(acme, "assets/logo/grid-mark.svg", 48)[2]
    assert "[PASS] manifest:bands" in bc("check", project=acme).stdout
    # a favicon whose 16 px layer was drawn from the fine vector is off the rule: check fails and names the layer
    def tamper(d):
        for a in d["artefacts"]:
            if a["path"] == "assets/web/favicon.ico":
                a["layer_bands"]["16"] = "large"
    mutate_json(acme / "assets/manifest.json", tamper)
    assert row(acme, "assets/web/favicon.ico")["layer_bands"]["16"] == "large"   # the mutation applied
    r = bc("check", project=acme)
    detail = next(x for x in report(acme, "check")["results"] if x["id"] == "manifest:bands")["detail"]
    assert r.returncode == 1 and "assets/web/favicon.ico layer 16 px" in detail and "no exemption" in detail
    # and so does a PNG icon recorded with the wrong band
    assert emit(acme, "web").returncode == 0
    mutate_json(acme / "assets/manifest.json", lambda d: [a.__setitem__("band", "small") for a in d["artefacts"] if a["path"] == "assets/web/icons/icon-512.png"])
    r = bc("check", project=acme)
    assert r.returncode == 1 and "icons/icon-512.png" in next(x for x in report(acme, "check")["results"] if x["id"] == "manifest:bands")["detail"]


# ================================================================ report inputs and staleness (R3-05)

def report_row(p, tool):
    bc("check", project=p)
    return next(x for x in report(p, "check")["results"] if x["id"] == f"report:{tool}")


def test_emitter_reports_record_every_file_the_emitter_read_once(acme):
    with_facts(acme)
    (acme / "INVENTORY.md").write_text("# Inventory\n\n## Deployment targets\n\n- iOS: 17.0\n")
    assert emit(acme, "linux", "--app-id", "org.example.Acme").returncode == 0
    assert emit(acme, "developer", "--tagline", "a repair guide is in every box").returncode == 0
    assert tray(acme).returncode == 0
    assert emit(acme, "web").returncode == 0
    for tool, must in (("emit-linux", {"FACTS.md", "qa/rules.json"}), ("emit-developer", {"FACTS.md", "qa/rules.json"}),
                       ("emit-tray", {"tray/tray.json", "qa/rules.json"}), ("emit-web", {"qa/rules.json"})):
        paths = [i["path"] for i in report(acme, tool)["inputs"]]
        assert must <= set(paths), (tool, paths)
        assert len(paths) == len(set(paths)), f"{tool} lists an input twice: {paths}"
    assert "mark.svg" in " ".join(i["path"] for i in report(acme, "emit-web")["inputs"])


def test_editing_a_file_an_emitter_read_makes_its_report_stale(acme):
    with_facts(acme)
    assert emit(acme, "developer", "--tagline", "a repair guide is in every box").returncode == 0
    assert tray(acme).returncode == 0
    assert report_row(acme, "emit-developer")["status"] == "pass" and report_row(acme, "emit-tray")["status"] == "pass"
    mutate(acme / "FACTS.md", "a repair guide is in every box", "a repair guide is in every crate")
    row_ = report_row(acme, "emit-developer")
    assert row_["status"] == "skipped" and "FACTS.md changed" in row_["detail"]
    assert report_row(acme, "emit-tray")["status"] == "pass"   # the tray emitter never read FACTS.md
    mutate_json(acme / "tray/tray.json", lambda d: d["states"].pop("error"))
    row_ = report_row(acme, "emit-tray")
    assert row_["status"] == "skipped" and "tray/tray.json changed" in row_["detail"]
    mutate_json(acme / "qa/rules.json", lambda d: d["bands"][0].__setitem__("max_px", 40))
    assert "qa/rules.json changed" in report_row(acme, "emit-developer")["detail"]


def test_staleness_covers_facts_inventory_and_the_tray_config(acme):
    import stale
    assert {"FACTS.md", "INVENTORY.md", "tray/*.json"} <= set(stale.DEFAULT_GLOBS)
    with_facts(acme)
    (acme / "INVENTORY.md").write_text("# Inventory\n\n## Deployment targets\n\n- iOS: 17.0\n")
    assert tray(acme).returncode == 0
    assert bc("staleness", "--write", project=acme).returncode == 0
    recorded = {i["path"] for i in json.loads((acme / "tools/inputs.json").read_text())["inputs"]}
    assert {"FACTS.md", "INVENTORY.md", "tray/tray.json"} <= recorded
    for f, old, new in (("FACTS.md", "a repair guide is in every box", "a repair guide is in every crate"),
                        ("INVENTORY.md", "iOS: 17.0", "iOS: 18.0")):
        mutate(acme / f, old, new)
        r = bc("check", project=acme)
        res = report(acme, "check")
        assert r.returncode == 1 and f"staleness:input:{f}" in failing(res), f
        mutate(acme / f, new, old)
    mutate_json(acme / "tray/tray.json", lambda d: d["states"].pop("error"))
    assert bc("check", project=acme).returncode == 1 and "staleness:input:tray/tray.json" in failing(report(acme, "check"))


# ================================================================ slots that no longer exist (R3-06)

def test_a_tray_state_that_was_removed_is_moved_out_and_its_rows_are_dropped(acme):
    assert tray(acme).returncode == 0
    gone = sorted(p.relative_to(acme).as_posix() for pat in ("error-*.png", "errorTemplate@*.png") for p in (acme / "assets/tray").rglob(pat))
    assert len(gone) == 15 and any("Template" in g for g in gone) and all(any(a["path"] == g for a in manifest(acme)["artefacts"]) for g in gone)
    original = (acme / "tray/tray.json").read_text()
    mutate_json(acme / "tray/tray.json", lambda d: d["states"].pop("error"))
    r = tray(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not [g for g in gone if (acme / g).exists()]                                   # no longer shipped
    assert not [a for a in manifest(acme)["artefacts"] if a["path"] in gone]               # no manifest row for them
    moved = sorted(p.relative_to(acme).as_posix() for p in acme.glob("removed-*/assets/tray/**/*.png"))
    assert moved == sorted(f"removed-2026-10-17/{g}" for g in gone)                          # moved, never deleted
    rep = report(acme, "emit-tray")
    assert sorted(x["id"].removeprefix("retired:") for x in rep["results"] if x["id"].startswith("retired:")) == gone and rep["retired"] == gone
    assert all(x["status"] == "warn" for x in rep["results"] if x["id"].startswith("retired:"))
    assert "idle-16.png" in " ".join(a["path"] for a in manifest(acme)["artefacts"])      # the states that remain are untouched
    assert sorted(report(acme, "states")["states_files"]) == ["qa/states.json", "qa/states.tray.json"]
    assert "error" not in (acme / "qa/states.tray.json").read_text()
    assert all("moved to removed-2026-10-17/" in x["detail"] for x in rep["results"] if x["id"].startswith("retired:"))
    # a run that removes nothing says nothing
    assert tray(acme).returncode == 0 and report(acme, "emit-tray")["retired"] == []
    # a second retirement the same day goes to removed-<date>-2/ and the report names that folder
    (acme / "tray/tray.json").write_text(original)
    r = tray(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    mutate_json(acme / "tray/tray.json", lambda d: d["states"].pop("error"))
    assert tray(acme).returncode == 0
    rep2 = [x for x in report(acme, "emit-tray")["results"] if x["id"].startswith("retired:")]
    assert rep2 and all("moved to removed-2026-10-17-2/" in x["detail"] for x in rep2)


def test_a_slot_dropped_by_an_option_is_retired_and_other_emitters_rows_stay(acme):
    assert emit(acme, "web").returncode == 0 and emit(acme, "social").returncode == 0
    assert emit(acme, "social", "--site-url", "https://example.invalid").returncode == 0
    assert row(acme, "assets/social/og-meta.html")
    web_before = [a["path"] for a in manifest(acme)["artefacts"] if a["emitter"] == "web"]
    r = emit(acme, "social")   # no --site-url this time: og-meta.html no longer exists as a slot
    assert r.returncode == 0
    assert not (acme / "assets/social/og-meta.html").exists() and (acme / "removed-2026-10-17/assets/social/og-meta.html").is_file()
    paths = [a["path"] for a in manifest(acme)["artefacts"]]
    assert "assets/social/og-meta.html" not in paths and [p for p in web_before if p not in paths] == []
    # the fingerprinted Open Graph file of an earlier card stays (its URL may be in cached previews) and is warned about
    assert emit(acme, "social", "--name", "Acme Tools").returncode == 0
    assert len(list((acme / "assets/social").glob("og-*.png"))) == 2


# ================================================================ a failed run does not leave the old pass standing (R3-07)

def test_a_run_that_fails_rewrites_its_report_as_failed(acme):
    with_facts(acme)
    assert emit(acme, "developer", "--tagline", "a repair guide is in every box").returncode == 0
    assert report(acme, "emit-developer")["status"] == "pass"
    r = emit(acme, "developer", "--tagline", "the best tools in the world")
    assert r.returncode == 1 and "not a value in FACTS.md" in r.stderr
    rep = report(acme, "emit-developer")
    err = next(x for x in rep["results"] if x["id"] == "error")
    assert rep["status"] == "fail" and err["status"] == "fail" and "not a value in FACTS.md" in err["detail"] and err["exit_code"] == 1
    # the inputs did not change, so before this the old passing report would still have been current: check must now say fail
    assert report_row(acme, "emit-developer")["status"] == "fail"
    # the next good run passes again
    assert emit(acme, "developer", "--tagline", "a repair guide is in every box").returncode == 0
    assert report_row(acme, "emit-developer")["status"] == "pass"


def test_every_report_based_tool_records_a_cannot_run_exit_too(tmp_path):
    """main_guard persists the failure of any open Report for exit 1 and exit 3 alike (checked on the shared code, not one tool)."""
    proj = make_project(tmp_path)
    script = tmp_path / "boom.py"
    script.write_text(f"import sys\nsys.path.insert(0, {str(ROOT / 'scripts/lib')!r})\n"
                      "from pathlib import Path\nfrom _common import Report, fail, main_guard\n"
                      "def main():\n    code = int(sys.argv[2])\n    Report('probe', Path(sys.argv[1])).add('a', 'pass')\n"
                      "    rep = Report('probe2', Path(sys.argv[1]))\n    rep.add('b', 'pass')\n    rep.finish()\n"
                      "    fail(code, 'the platform cannot do this')\nmain_guard(main)\n")
    for code in (1, 3):
        r = subprocess.run(["python3", "-I", str(script), str(proj), str(code)], capture_output=True, text=True)
        assert r.returncode == code and "the platform cannot do this" in r.stderr
        doc = json.loads((proj / "assets/_checks/probe.json").read_text())
        assert doc["status"] == "fail" and doc["results"][-1]["id"] == "error" and doc["results"][-1]["exit_code"] == code
        assert json.loads((proj / "assets/_checks/probe2.json").read_text())["status"] == "pass"   # a finished report is left alone


def test_a_crash_records_a_failure_and_never_leaves_a_passing_report(tmp_path):
    """An unexpected exception (e.g. a RuntimeError from a failing assetutil) is a failure: traceback shown, exit 1, the open report
    rewritten as fail. Before this only CliError was recorded and the previous passing report stayed current."""
    proj = make_project(tmp_path)
    (proj / "assets/_checks").mkdir(parents=True, exist_ok=True)
    (proj / "assets/_checks/probe.json").write_text(json.dumps({"tool": "probe", "status": "pass", "results": []}))
    script = tmp_path / "crash.py"
    script.write_text(f"import sys\nsys.path.insert(0, {str(ROOT / 'scripts/lib')!r})\n"
                      "from pathlib import Path\nfrom _common import Report, main_guard\n"
                      "def main():\n    Report('probe', Path(sys.argv[1])).add('a', 'pass')\n"
                      "    raise RuntimeError('assetutil failed')\nmain_guard(main)\n")
    r = subprocess.run(["python3", "-I", str(script), str(proj)], capture_output=True, text=True)
    assert r.returncode == 1 and "Traceback" in r.stderr and "assetutil failed" in r.stderr
    doc = json.loads((proj / "assets/_checks/probe.json").read_text())
    err = doc["results"][-1]
    assert doc["status"] == "fail" and err["id"] == "error" and "RuntimeError: assetutil failed" in err["detail"] and err["exit_code"] == 1


# ================================================================ finish.sh runs end to end (R3-03)

def test_the_filled_finish_chain_runs_through_to_check(acme, tmp_path):
    """The template with the Acme values: a tagline and an exemption with spaces in them, a generator that needs BRAND_CREATOR_ROOT, the
    gates for every downscale master the manifest names, the idempotence run and check. bash -n alone proved none of that."""
    with_facts(acme)
    shutil.copytree(FIXTURES / "tools", acme / "tools", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    for g in ("grid_mark.py", "state_icons.py"):
        assert f"  # tools/{g}\n" in tpl
        tpl = tpl.replace(f"  # tools/{g}\n", f"  tools/{g}\n")
    fin = acme / "tools" / "finish.sh"
    fin.write_text(tpl)
    fin.chmod(0o755)
    probe = acme / "tools" / "root_probe.py"
    probe.write_text("import os, sys\nsys.path.insert(0, os.path.join(os.environ['BRAND_CREATOR_ROOT'], 'scripts', 'lib'))\nimport px_lib\n"
                     "print('generator saw the plugin root')\n")
    fin.write_text(tpl.replace("  tools/grid_mark.py\n", "  tools/grid_mark.py\n  tools/root_probe.py\n"))
    assert "root_probe.py" in fin.read_text()
    # the round-level gates are outside the chain (they judge the board, not a pack); `check` wants them current
    for cmd in (("logo-sheet",), ("board-lint", "rounds/r1/board.html"), ("shot", "rounds/r1/board.html")):
        assert bc(*cmd, project=acme).returncode == 0, cmd
    exemption = "the system shrinks this one master to 16 px; the coarse-grid drawing keeps the accent"
    env = {**os.environ, "PATH": f"{ROOT / 'bin'}:{os.environ['PATH']}", "BRAND_CREATOR_TODAY": "2026-10-17", "BRAND_CREATOR_DATA": os.environ.get("BRAND_CREATOR_DATA", ""),
           "TAGLINE": "a repair guide is in every box", "APP_ID": "org.example.Acme", "MASTER_BAND": "small", "EXEMPTION": exemption,
           "ICON_CONTENT": "0.8", "VISIONOS_CONTENT": "0.6"}
    if sys.platform != "darwin":   # no iconutil, no sips: the chain names its two explicit opt-ins (README, "Linux")
        env.update({"ICNS_RENDERER": "pillow", "DOWNSCALE_RENDERER": "pillow"})
    env.pop("BRAND_CREATOR_ROOT", None)   # the script must derive it, not inherit it
    r = subprocess.run(["bash", str(fin)], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=900)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    assert "generator saw the plugin root" in out and "unrecognized arguments" not in out
    assert "emit developer" in out and "== downscale assets/developer/" in out and "check: PASS" in out
    # the multi-word values arrived whole, as one argument each
    assert row(acme, "assets/developer/avatar/acme-avatar-1024.png")["exemption"] == exemption
    assert "a repair guide is in every box" in (acme / "assets/developer/cli/identity.plain.txt").read_text()
    # every downscale row has its own passing report: check ties each row to the report of its master
    for a in manifest(acme)["artefacts"]:
        if "downscale" in a.get("qa", []):
            assert downscale_report(acme, a["downscale_source"])["status"] == "pass", a["path"]
    assert report(acme, "check")["status"] == "pass"


# ================================================================ apple: where it cannot run

def test_emit_apple_off_macos_is_exit_3_with_a_clear_message_and_no_fallback(acme):
    """The program itself, started the way uv starts it but with sys.platform set to linux: no file is written, nothing falls back."""
    code = ("import runpy, sys\nsys.platform = 'linux'\nscript, project = sys.argv[1], sys.argv[2]\n"
            "sys.argv = ['apple.py', '--project', project]\nrunpy.run_path(script, run_name='__main__')\n")
    env = {**os.environ, "BRAND_CREATOR_DATA": os.environ.get("BRAND_CREATOR_DATA", ""), "BRAND_CREATOR_ROOT": str(ROOT)}
    r = subprocess.run(["uv", "run", "--no-project", "--with", "jsonschema==4.26.0", "python", "-c", code, str(ROOT / "scripts/emitters/apple.py"), str(acme)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "needs macOS with Xcode" in r.stderr and "no fallback" in r.stderr
    assert not (acme / "assets/apple").exists() and not (acme / "assets/_checks/emit-apple.json").exists()


@macos
def test_emit_apple_without_xcode_on_a_mac_is_exit_3_naming_the_fix(acme, tmp_path):
    r = emit(acme, "apple", env=bare_path(tmp_path, without=("xcrun",)))
    assert r.returncode == 3 and "actool not found" in r.stderr and "prereq --for apple" in r.stderr
    assert not (acme / "assets/apple").exists()
