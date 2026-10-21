"""downscale: what survives when one master is shrunk to the sizes systems show; the accent rule, before/after, the method.

Masters are built with px_lib so their accent geometry is known exactly (a block of known size on a flat ground); the expected
accent counts are worked out by hand, never read from the tool."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import OFF_MAC_DOWNSCALE, ROOT, bc, downscale_report, failing, make_project, mutate_json, report

from px_lib import Img

pytestmark = pytest.mark.requires_setup  # the tokens (accent, ground) come from a built tokens.json

GROUND, ACCENT = "#f9f7ee", "#007d71"  # the Acme light tokens
DARK_GROUND, DARK_ACCENT = "#0e141d", "#4cd7c8"
macos = pytest.mark.requires_macos


def master(path: Path, block: int, *, size: int = 64, ground=GROUND, accent=ACCENT, svg: bool = False, off: int | None = None) -> Path:
    """A size x size master: flat ground, a block x block accent square (centred unless off is given; whole pixels)."""
    im = Img(size, size, ground)
    off = (size - block) // 2 if off is None else off
    if block:
        im.rect(off, off, block, block, accent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(im.png()) if not svg else path.write_text(im.svg())
    return path


def results(proj):
    return {r["id"]: r for r in downscale_report(proj)["results"]}


# Off macOS there is no sips, so a call that is not about the method must name one (pillow: every master here is a PNG). The tests of the
# default method itself (`macos`-marked) and of the opt-in rules call bc() or pass --renderer / --record-renderer themselves.
def run(proj, *extra):
    method = [] if {"--renderer", "--record-renderer"} & set(extra) or any(e.startswith("--renderer=") for e in extra) else OFF_MAC_DOWNSCALE
    return bc("downscale", *method, *extra, project=proj)


@pytest.fixture
def proj(acme):
    return acme


def test_default_sizes_come_from_the_platform_specs_not_from_code(proj):
    r = run(proj, "--source", "assets/logo/grid-mark-master.png")
    assert r.returncode == 0, r.stdout
    specs = json.loads((ROOT / "scripts/emitters/platform-specs.json").read_text())["rows"]
    want = sorted(set(specs["downscale-apple"]["sizes"]["px"]) | set(specs["favicon-set"]["sizes"]["ico_layers"]), reverse=True)
    assert downscale_report(proj)["sizes"] == want == [180, 120, 87, 58, 48, 40, 32, 29, 20, 16]
    assert set(downscale_report(proj)["specs"]) == {"downscale-apple", "favicon-set"}  # the rows used are stamped, with their status


@macos
def test_system_downscale_is_the_default_on_macos_and_is_printed(proj):
    r = run(proj, "--source", "assets/logo/grid-mark-master.png", "--sizes", "16")
    assert r.returncode == 0, r.stdout
    assert r.stdout.startswith("method: sips -z (macOS system downscale, the default)")
    rep = downscale_report(proj)
    assert rep["method"] == "sips" and rep["renderer"].startswith("sips -z") and rep["rule"]["source"] == "qa/rules.json"


def test_the_acme_grid_master_keeps_its_accent_at_every_size_the_fine_vector_does_not(proj):
    """The coarse-grid master passes the 4 x 4 px rule at 16 px; the fine vector does not (the reason bands exist)."""
    ok = run(proj, "--source", "assets/logo/grid-mark-master.png", "--sizes", "32,20,16")
    assert ok.returncode == 0, ok.stdout
    assert all(results(proj)[f"downscale:{s}px"]["accent_square"] >= 4 for s in (32, 20, 16))
    bad = run(proj, "--source", "assets/logo/mark.svg", "--renderer", "resvg", "--sizes", "32,16")
    assert bad.returncode == 1
    assert failing(downscale_report(proj)) == ["downscale:16px"]
    d = results(proj)["downscale:16px"]
    assert d["accent_square"] < 4 and "Redraw the accent" in d["detail"]


def test_exact_accent_geometry_with_the_vector_renderer(proj):
    """A 32 px accent block on a 64 px master is 8 x 8 = 64 px at 16 px (aligned to the pixel grid, so exact)."""
    m = master(proj / "assets/logo/block.svg", 32, svg=True)
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/block.svg", "--sizes", "32,16,8")
    assert r.returncode == 0, r.stdout
    res = results(proj)
    assert (res["downscale:16px"]["accent_px"], res["downscale:16px"]["accent_box"], res["downscale:16px"]["accent_square"]) == (64, "8x8", 8)
    assert (res["downscale:32px"]["accent_px"], res["downscale:32px"]["accent_square"]) == (256, 16)  # 16 x 16 at half size
    assert res["downscale:8px"]["accent_px"] == 16 and res["downscale:8px"]["accent_bbox"] == [2, 2, 5, 5]
    assert downscale_report(proj)["renderer"].startswith("resvg (explicit --renderer)")


@pytest.mark.parametrize("method", ["pillow", pytest.param("sips", marks=macos)])
def test_resampling_methods_keep_a_big_block_big(proj, method):
    master(proj / "assets/logo/block.png", 32)
    extra = ["--renderer", "pillow"] if method == "pillow" else []
    r = run(proj, "--source", "assets/logo/block.png", "--sizes", "16", *extra)
    assert r.returncode == 0, r.stdout
    d = results(proj)["downscale:16px"]
    # 8 x 8 = 64 px expected. Lanczos keeps all but the edge; the system downscale (sips) blends edges wider, so it measures lower:
    # that difference from the vector is exactly why the check samples the real downscaler
    lo, sq = (56, 7) if method == "pillow" else (25, 5)
    assert lo <= d["accent_px"] <= 72 and d["accent_square"] >= sq, d


def test_the_accent_rule_is_a_project_setting_and_fails_a_smudge(proj):
    master(proj / "assets/logo/small.svg", 12, off=24, svg=True)  # 12 px of 64 is 3 px at 16 px (aligned to the pixel grid): below the 4 x 4 default
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16,40")
    assert r.returncode == 1
    res = results(proj)
    assert res["downscale:16px"]["status"] == "fail" and res["downscale:16px"]["accent_square"] == 3
    assert res["downscale:40px"]["status"] == "info"  # above the 32 px rule size: measured, not gated
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"].__setitem__("accent_min_px", 3))  # the owner relaxes the rule
    assert run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16").returncode == 0
    assert "3x3 px at 32 px and below" in run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16").stdout
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"].__setitem__("accent_rule_max_size", 8))
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16")
    assert results(proj)["downscale:16px"]["status"] == "info"  # 16 px is now above the rule size


def test_an_exemption_excuses_a_miss_of_its_own_master_up_to_its_size_and_carries_the_reason(proj):
    """An owner may accept a miss for one master at a size and below (a row of 2 px gold cells that reads as a row, not as an
    accent): the miss becomes a warning that carries the reason. Another master, or a size above max_px, still fails, and an
    exemption that excused nothing is reported, so the register of accepted misses stays honest."""
    master(proj / "assets/logo/small.svg", 12, off=24, svg=True)   # 3 px at 16 px: a miss under the 4 x 4 default
    master(proj / "assets/logo/other.svg", 12, off=24, svg=True)
    why = "the gold reads as a row of capsules"
    ex = {"source": "assets/logo/small.svg", "max_px": 16, "reason": why}
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"].__setitem__("exemptions", [ex]))
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16")
    row = results(proj)["downscale:16px"]
    assert r.returncode == 0, r.stdout
    assert row["status"] == "warn" and row["accent_square"] == 3 and why in row["detail"] and "downscale.exemptions" in row["detail"]
    assert downscale_report(proj)["rule"]["exemptions"] == [ex]
    assert run(proj, "--renderer", "resvg", "--source", "assets/logo/other.svg", "--sizes", "16").returncode == 1   # not its master
    assert results(proj)["downscale:16px"]["status"] == "fail" and downscale_report(proj)["rule"]["exemptions"] == []
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"]["exemptions"][0].__setitem__("max_px", 15))
    assert run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16").returncode == 1   # 16 is above 15
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "40")                     # nothing to excuse
    res = results(proj)
    assert r.returncode == 0 and res["exemption:0"]["status"] == "warn" and "excused no failing row" in res["exemption:0"]["detail"]


def test_an_exemption_path_is_read_as_written_and_one_that_names_no_file_is_reported(proj):
    master(proj / "assets/logo/small.svg", 12, off=24, svg=True)
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"].__setitem__(
        "exemptions", [{"source": "./assets/logo/small.svg", "max_px": 16, "reason": "a row of cells"},
                       {"source": "assets/logo/smal.svg", "max_px": 16, "reason": "a typo"}]))
    r = run(proj, "--renderer", "resvg", "--source", "./assets/logo/small.svg", "--sizes", "16")
    res = results(proj)
    assert r.returncode == 0 and res["downscale:16px"]["status"] == "warn" and "a row of cells" in res["downscale:16px"]["detail"]
    assert res["exemption:1"]["status"] == "warn" and "names assets/logo/smal.svg, which is not a file" in res["exemption:1"]["detail"]


@pytest.mark.parametrize("bad, words", [
    ({"source": "assets/logo/small.svg", "max_px": 16}, "reason must say why"),
    ({"source": "assets/logo/small.svg", "max_px": 0, "reason": "x"}, "max_px must be a whole number above 0"),
    ({"source": "/tmp/small.svg", "max_px": 16, "reason": "x"}, "source must be the master's path inside the project"),
    ({"source": "../small.svg", "max_px": 16, "reason": "x"}, "source must be the master's path inside the project"),
    ({"source": "assets/logo/small.svg", "max_px": 16, "reason": "x", "until": "2027"}, "unknown keys"),
    ("assets/logo/small.svg", "must be an object"),
])
def test_an_exemption_without_its_master_a_size_or_a_reason_is_refused(proj, bad, words):
    master(proj / "assets/logo/small.svg", 12, off=24, svg=True)
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"].__setitem__("exemptions", [bad]))
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/small.svg", "--sizes", "16")
    assert r.returncode == 2 and words in r.stdout + r.stderr, r.stdout + r.stderr


def test_a_master_that_is_one_bands_drawing_says_which_sizes_ship_another(proj):
    """Acme's bands: grid-mark.svg up to 32 px, mark.svg above. Measuring either names its band and the other drawing, and points
    at --png for the sizes drawn per band; the rows themselves are still the one master shrunk, as a system would."""
    run(proj, "--renderer", "resvg", "--source", "assets/logo/grid-mark.svg", "--sizes", "16,64")
    row = results(proj)["bands"]
    assert row["status"] == "info" and "band 'small' (1 to 32 px)" in row["detail"] and "assets/logo/mark.svg (large)" in row["detail"]
    assert "--png" in row["detail"] and "downscale:64px" in results(proj)                 # 64 px is measured from grid-mark.svg anyway
    run(proj, "--renderer", "resvg", "--source", "assets/logo/mark.svg", "--sizes", "16")
    assert "band 'large' (33 px and up)" in results(proj)["bands"]["detail"]
    master(proj / "assets/logo/other.svg", 32, svg=True)
    run(proj, "--renderer", "resvg", "--source", "assets/logo/other.svg", "--sizes", "16")
    assert "bands" not in results(proj)                                                  # not a band's drawing: nothing to say


def test_a_mark_with_its_own_accent_is_measured_on_that_accent(proj):
    """With several marks each may name its accent role (qa/rules.json marks.<id>.accent): a master that is one of its drawings is measured
    on that accent, not on downscale.accent_colour. Precedence: --accent, the mark's accent, downscale.accent_colour. Acme's accent is the
    teal #007d71 (color.accent) and its muted colour the slate #4b596c (color.muted); the blocks below are one or the other."""
    SLATE = "#4b596c"
    master(proj / "assets/logo/tool-a.svg", 32, svg=True, accent=SLATE)   # a's own accent colour
    master(proj / "assets/logo/tool-b.svg", 32, svg=True)                 # b names none: the teal of color.accent

    def several(d):
        del d["bands"]
        d["marks"] = {"tool-a": {"bands": [{"name": "all", "drawing": "assets/logo/tool-a.svg"}], "accent": "color.muted"},
                      "tool-b": {"bands": [{"name": "all", "drawing": "assets/logo/tool-b.svg"}]}}
    mutate_json(proj / "qa/rules.json", several)
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/tool-a.svg", "--sizes", "16")
    assert r.returncode == 0, r.stdout
    acc = downscale_report(proj)["accent"]
    assert (acc["role"], acc["hex"]) == ("color.muted", SLATE) and results(proj)["downscale:16px"]["accent_square"] == 8   # 32 of 64 px is 8 of 16
    # --accent comes first: the teal is not on a's drawing, so the accent vanishes
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/tool-a.svg", "--sizes", "16", "--accent", ACCENT)
    assert r.returncode == 1 and "the accent vanished" in results(proj)["downscale:16px"]["detail"] and downscale_report(proj)["accent"]["role"] == ACCENT
    # a mark that names no accent falls back to downscale.accent_colour, which is color.accent unless the project sets it
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/tool-b.svg", "--sizes", "16")
    assert r.returncode == 0 and (downscale_report(proj)["accent"]["role"], downscale_report(proj)["accent"]["hex"]) == ("color.accent", ACCENT)
    mutate_json(proj / "qa/rules.json", lambda d: d["downscale"].__setitem__("accent_colour", "color.text"))
    assert run(proj, "--renderer", "resvg", "--source", "assets/logo/tool-b.svg", "--sizes", "16").returncode == 1
    assert downscale_report(proj)["accent"]["role"] == "color.text"
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/tool-a.svg", "--sizes", "16")   # the mark's accent still beats the project's default
    assert r.returncode == 0 and downscale_report(proj)["accent"]["role"] == "color.muted"
    # a master that is no mark's drawing keeps the project's default too
    master(proj / "assets/logo/loose.svg", 32, svg=True, accent="#0d1b2d")
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/loose.svg", "--sizes", "16")
    assert r.returncode == 0 and downscale_report(proj)["accent"]["role"] == "color.text"
    # a role the tokens do not define is a usage error that says where it was named, never a guess
    mutate_json(proj / "qa/rules.json", lambda d: d["marks"]["tool-a"].__setitem__("accent", "color.nope"))
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/tool-a.svg", "--sizes", "16")
    assert r.returncode == 2 and "color.nope (marks.tool-a.accent) cannot be resolved" in r.stderr


def test_an_accent_that_vanished_is_named_as_such(proj):
    master(proj / "assets/logo/none.png", 0)
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/none.png", "--sizes", "16")
    assert r.returncode == 1 and "the accent vanished" in results(proj)["downscale:16px"]["detail"]


def test_before_after_against_an_earlier_master_flags_a_regression(proj):
    big, small = master(proj / "assets/logo/big.png", 32), master(proj / "assets/logo/small.png", 16)
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/small.png", "--previous", "assets/logo/big.png", "--sizes", "16")
    c = results(proj)["compare:16px"]
    assert c["status"] == "warn" and "REGRESSION" in c["detail"] and c["before"]["accent_square"] > c["after"]["accent_square"]
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/big.png", "--previous", "assets/logo/small.png", "--sizes", "16")
    c = results(proj)["compare:16px"]
    assert c["status"] == "info" and "REGRESSION" not in c["detail"] and c["after"]["accent_px"] > c["before"]["accent_px"]
    assert downscale_report(proj)["previous"] == "assets/logo/small.png"


def test_before_after_falls_back_to_the_previous_report_of_the_same_source(proj):
    f = master(proj / "assets/logo/a.png", 32)
    run(proj, "--renderer", "pillow", "--source", "assets/logo/a.png", "--sizes", "16")
    first = results(proj)["downscale:16px"]["accent_px"]
    assert "compare:none" in results(proj)   # the first run has nothing to compare with, and says so
    before = f.read_bytes()
    master(f, 16)
    assert f.read_bytes() != before   # the mutation applied: the same source now has a smaller accent
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/a.png", "--sizes", "16")
    c = results(proj)["compare:16px"]
    assert "the previous run's report" in c["detail"] and c["before"]["accent_px"] == first and c["status"] == "warn"
    assert "compare:none" not in results(proj)


def test_before_after_is_not_compared_with_a_report_of_another_source_or_another_measurement(proj):
    master(proj / "assets/logo/a.png", 32)
    master(proj / "assets/logo/b.png", 16)
    run(proj, "--renderer", "pillow", "--source", "assets/logo/a.png", "--sizes", "16")
    run(proj, "--renderer", "pillow", "--source", "assets/logo/b.png", "--sizes", "16")
    res = results(proj)   # b.png has no earlier report of its own: no compare row, no false REGRESSION
    assert "compare:16px" not in res and res["compare:none"]["status"] == "info" and "no earlier report for this source" in res["compare:none"]["detail"]
    # the same source measured differently (master size) is not comparable either
    run(proj, "--renderer", "pillow", "--source", "assets/logo/a.png", "--sizes", "16", "--master-size", "512")
    res = results(proj)
    assert "compare:16px" not in res and "master_size" in res["compare:none"]["detail"]
    # one report per source: both files have their own
    names = sorted(f.name for f in (proj / "assets/_checks/downscale").glob("*.json"))
    assert len(names) == 2 and names[0].startswith("a-") and names[1].startswith("b-")


def test_shipped_pngs_are_measured_as_they_are(proj):
    Img(16, 16, GROUND).png()
    ok, thin = Img(16, 16, GROUND), Img(16, 16, GROUND)
    ok.rect(4, 4, 6, 6, ACCENT)
    thin.rect(4, 4, 3, 5, ACCENT)
    (proj / "assets/web").mkdir(exist_ok=True)
    (proj / "assets/web/ok.png").write_bytes(ok.png())
    (proj / "assets/web/thin.png").write_bytes(thin.png())
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/grid-mark-master.png", "--sizes", "16",
            "--png", "assets/web/ok.png", "--png", "assets/web/thin.png")
    res = results(proj)
    assert res["shipped:assets/web/ok.png"]["status"] == "pass" and res["shipped:assets/web/ok.png"]["accent_px"] == 36
    assert res["shipped:assets/web/thin.png"]["status"] == "fail" and res["shipped:assets/web/thin.png"]["accent_px"] == 15
    assert r.returncode == 1 and "not resampled" in res["shipped:assets/web/ok.png"]["detail"]
    (proj / "assets/web/wide.png").write_bytes(Img(16, 8, GROUND).png())
    assert run(proj, "--renderer", "pillow", "--source", "assets/logo/grid-mark-master.png", "--png", "assets/web/wide.png").returncode == 2


def test_dark_mode_reads_the_dark_accent_and_ground(proj):
    master(proj / "assets/logo/dark.png", 32, ground=DARK_GROUND, accent=DARK_ACCENT)
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/dark.png", "--sizes", "16", "--mode", "dark")
    assert r.returncode == 0, r.stdout
    assert downscale_report(proj)["accent"]["hex"] == DARK_ACCENT and downscale_report(proj)["accent"]["ground"] == DARK_GROUND
    assert run(proj, "--renderer", "pillow", "--source", "assets/logo/dark.png", "--sizes", "16").returncode == 1  # light ground: nothing is the accent


def test_explicit_accent_and_ground_override_the_tokens(proj):
    master(proj / "assets/logo/odd.png", 32, ground="#ffffff", accent="#ff0000")
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/odd.png", "--sizes", "16", "--accent", "#ff0000", "--ground", "#ffffff")
    assert r.returncode == 0 and results(proj)["downscale:16px"]["accent_square"] >= 5
    assert run(proj, "--renderer", "pillow", "--source", "assets/logo/odd.png", "--accent", "red").returncode == 2


def test_errors_are_explicit(proj, tmp_path):
    assert run(proj, "--source", "assets/logo/missing.png").returncode == 2
    r = run(proj, "--renderer", "pillow", "--source", "assets/logo/mark.svg")
    assert r.returncode == 3 and "cannot rasterise SVG" in r.stderr
    r = run(proj, "--renderer", "resvg", "--source", "assets/logo/grid-mark-master.png")
    assert r.returncode == 3 and "needs sips (macOS) or --renderer=pillow" in r.stderr
    assert run(proj, "--sizes", "16,zero", "--source", "assets/logo/grid-mark-master.png").returncode == 2
    assert run(proj, "--sizes", "0", "--source", "assets/logo/grid-mark-master.png").returncode == 2
    outside = tmp_path / "o.png"
    outside.write_bytes(Img(8, 8, GROUND).png())
    r = run(proj, "--source", str(outside))
    assert r.returncode == 2 and "outside the project" in r.stderr
    (proj / "qa/rules.json").write_text('{"schema": 1, "downscale": {"accent_min_pxx": 4}}')
    r = run(proj, "--source", "assets/logo/grid-mark-master.png")
    assert r.returncode == 2 and "unknown key downscale.accent_min_pxx" in r.stderr  # a typo must not fall back to the default
    (proj / "qa/rules.json").write_text('{"schema": 1, "downscale": {"accent_min_px": 0}}')
    assert run(proj, "--source", "assets/logo/grid-mark-master.png").returncode == 2


def test_an_unresolvable_accent_role_stops_the_run_instead_of_guessing(tmp_path):
    p = make_project(tmp_path)  # no tokens built
    (p / "assets/logo").mkdir(parents=True)
    master(p / "assets/logo/m.png", 32)
    r = bc("downscale", "--renderer", "pillow", "--source", "assets/logo/m.png", project=p)
    assert r.returncode == 2 and "cannot be resolved" in r.stderr and "--accent #rrggbb" in r.stderr


def test_record_renderer_needs_an_explicit_off_system_renderer(proj):
    r = run(proj, "--record-renderer", "--source", "assets/logo/grid-mark-master.png")
    assert r.returncode == 2 and ("needs an explicit" in r.stderr or "records an opt-in" in r.stderr)


# ---------------------------------------------------------------- off macOS: no silent fallback

def off_macos(proj, *args, data) -> subprocess.CompletedProcess:
    """Run the script as if on Linux (sys.platform spoofed): there is no sips, so only an explicit opt-in may measure."""
    script = ROOT / "scripts" / "downscale_check.py"
    code = ("import sys, runpy; sys.platform = 'linux'; sys.argv = [sys.argv[1]] + sys.argv[2:]; "
            "runpy.run_path(sys.argv[0], run_name='__main__')")
    env = {**os.environ, "BRAND_CREATOR_ROOT": str(ROOT), "BRAND_CREATOR_DATA": str(data), "BRAND_CREATOR_TODAY": "2026-10-17"}
    return subprocess.run(["uv", "run", "--no-project", "--quiet", "--with", "pillow==11.3.0", "python", "-I", "-c", code, str(script),
                           "--project", str(proj), *args], capture_output=True, text=True, env=env, timeout=300)


def test_off_macos_without_an_opt_in_nothing_is_measured(proj, tmp_path):
    r = off_macos(proj, "--source", "assets/logo/mark.svg", data=tmp_path)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "no system downscaler" in r.stderr and "--renderer=resvg" in r.stderr and "Nothing was measured" in r.stderr
    assert not list((proj / "assets/_checks").glob("downscale*"))


def test_off_macos_the_opt_in_is_recorded_printed_and_reused(proj, tmp_path):
    r = off_macos(proj, "--renderer", "resvg", "--record-renderer", "--source", "assets/logo/grid-mark.svg", "--sizes", "32,16", data=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "renderer: resvg (opted in 2026-10-17)" in (proj / "BRAND-STATE.md").read_text()
    r = off_macos(proj, "--source", "assets/logo/grid-mark.svg", "--sizes", "32,16", data=tmp_path)  # no flag: the recorded opt-in speaks
    assert r.returncode == 0, r.stdout + r.stderr
    rep = downscale_report(proj)
    assert rep["method"] == "resvg" and "opt-in recorded in BRAND-STATE.md on 2026-10-17" in rep["renderer"]
    assert "opt-in recorded in BRAND-STATE.md on 2026-10-17" in r.stdout  # printed on every run
    c = bc("check", project=proj)
    assert "renderer in use: resvg (opted in 2026-10-17)" in c.stdout  # and by check


def test_off_macos_a_png_master_works_with_explicit_pillow(proj, tmp_path):
    r = off_macos(proj, "--renderer", "pillow", "--source", "assets/logo/grid-mark-master.png", "--sizes", "16", data=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "pillow (Lanczos) (explicit --renderer)" in downscale_report(proj)["renderer"]


def test_off_macos_a_usage_error_is_exit_2_not_exit_3(proj, tmp_path):
    """Found by the Linux run: with no renderer named, 'this system cannot measure' (exit 3) was reported before a missing source, bad sizes,
    a path outside the project or `--record-renderer` without a renderer (all exit 2 on a Mac). Usage errors now come first, everywhere."""
    state_before = (proj / "BRAND-STATE.md").read_text()
    for args, what in ((["--source", "assets/logo/missing.png"], "source not found"),
                       (["--sizes", "16,zero", "--source", "assets/logo/grid-mark-master.png"], "size"),
                       (["--record-renderer", "--source", "assets/logo/grid-mark-master.png"], "needs an explicit --renderer"),
                       (["--source", str(tmp_path / "o.png")], "outside the project")):
        r = off_macos(proj, *args, data=tmp_path)
        assert r.returncode == 2 and what in r.stderr, (args, r.returncode, r.stderr)
    assert (proj / "BRAND-STATE.md").read_text() == state_before   # nothing was recorded
