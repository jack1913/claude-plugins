"""fontcheck (cmap per language set, licence hint, Chromium platform-font report with a control) and render.mjs fonts.

The font is the OFL test subset: Basic Latin, the Polish letters and the German letters. What it lacks is worked out by hand
from the language data files (the expected sets below are written out, never read from the code under test)."""
import json
import unicodedata
from pathlib import Path

import pytest
from helpers import ROOT, TEST_FONT, bc, failing, font_variant, make_project, mutate, report

LANG_DIR = ROOT / "scripts" / "data" / "languages"

# Czech letters the subset lacks: the 15 Czech capitals ÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ minus Ó (a Polish letter, present), and their lower case
CS_MISSING = set("ÁČĎÉĚÍŇŘŠŤÚŮÝŽáčďéěíňřšťúůýž")
# Turkish: ÇĞİÖŞÜ çğıöşü minus Ö Ü ö ü (German letters, present): Ç Ğ İ Ş ç ğ ı ş
TR_MISSING = set("ÇĞİŞ") | set("çğış")


@pytest.fixture
def proj(tmp_path):
    return make_project(tmp_path)


def fc(proj, *extra, font=TEST_FONT, platform=False):
    args = ["fontcheck", "--font", str(font), *extra] + ([] if platform else ["--no-platform"])
    return bc(*args, project=proj)


def results(proj):
    return {r["id"]: r for r in report(proj, "fontcheck")["results"]}


# ---------------------------------------------------------------- the language data files

def test_language_files_are_well_formed_and_nfc():
    files = sorted(LANG_DIR.glob("*.json"))
    assert {f.stem for f in files} >= {"en", "pl", "de", "cs", "fr", "es", "tr"}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d["schema"] == 1 and d["code"] == f.stem and d["name"] and isinstance(d["basic_latin"], bool)
        for key in ("letters", "symbols", "extras"):
            assert isinstance(d[key], str) and unicodedata.normalize("NFC", d[key]) == d[key], (f.name, key)
        assert len(set(d["letters"])) == len(d["letters"]), f.name
        assert all(r["id"] and r["text"] for r in d["rules"]), f.name


def test_polish_is_one_set_among_others_with_its_eighteen_letters():
    pl = json.loads((LANG_DIR / "pl.json").read_text(encoding="utf-8"))
    assert set(pl["letters"]) == set("ĄĆĘŁŃÓŚŹŻąćęłńóśźż") and len(pl["letters"]) == 18  # nine letters, two cases (worked out by hand)
    en = json.loads((LANG_DIR / "en.json").read_text(encoding="utf-8"))
    assert en["letters"] == "" and en["basic_latin"] is True  # the plugin has no default language, English adds no letters


# ---------------------------------------------------------------- coverage

def test_polish_and_german_are_covered_czech_and_turkish_are_not(proj):
    r = fc(proj, "--lang", "pl,de,cs,tr")
    assert r.returncode == 1, r.stdout
    res = results(proj)
    f = TEST_FONT.name
    assert res[f"cmap:{f}:pl"]["status"] == "pass" and res[f"cmap:{f}:de"]["status"] == "pass"
    assert res[f"cmap:{f}:cs"]["status"] == "fail" and set(res[f"cmap:{f}:cs"]["missing"]) == CS_MISSING
    assert res[f"cmap:{f}:tr"]["status"] == "fail" and set(res[f"cmap:{f}:tr"]["missing"]) == TR_MISSING
    assert len(TR_MISSING) == 8
    assert "pl,de,cs,tr" == ",".join(report(proj, "fontcheck")["languages"])


def test_typographic_extras_warn_but_do_not_fail(proj):
    r = fc(proj, "--lang", "pl")
    assert r.returncode == 0, r.stdout
    ex = results(proj)[f"extras:{TEST_FONT.name}:pl"]
    assert ex["status"] == "warn" and set(ex["missing"]) == set("„”«»–—…")  # the subset holds none of them


def test_extra_text_is_checked_as_required(proj):
    assert fc(proj, "--lang", "pl", "--text", "Zażółć").returncode == 0
    r = fc(proj, "--lang", "pl", "--text", "Čech")
    assert r.returncode == 1 and failing(report(proj, "fontcheck")) == [f"cmap:{TEST_FONT.name}:pl"]
    assert results(proj)[f"cmap:{TEST_FONT.name}:pl"]["missing"] == ["Č"]


def test_no_default_language_and_the_chat_language_is_not_used(proj):
    r = fc(proj)
    assert r.returncode == 2 and "no language set" in r.stderr and "content_languages" in r.stderr
    assert "pl" in r.stderr and "cs" in r.stderr  # the available sets are listed
    assert bc("state", "--set", "language=pl", project=proj).returncode == 0  # chat language is not the brand's text language
    assert fc(proj).returncode == 2
    assert bc("state", "--set", "content_languages=pl,de", project=proj).returncode == 0
    r = fc(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert report(proj, "fontcheck")["languages"] == ["pl", "de"]


def test_unknown_language_and_bad_fonts_exit_2(proj, tmp_path):
    r = fc(proj, "--lang", "xx")
    assert r.returncode == 2 and "no language set for xx" in r.stderr
    r = bc("fontcheck", "--lang", "pl", "--no-platform", project=proj)
    assert r.returncode == 2 and "no fonts to check" in r.stderr
    junk = tmp_path / "x.ttf"
    junk.write_bytes(b"nope")
    r = fc(proj, "--lang", "pl", font=junk)
    assert r.returncode == 1 and "cannot read" in report(proj, "fontcheck")["results"][0]["detail"]
    txt = tmp_path / "x.txt"
    txt.write_text("x")
    assert fc(proj, "--lang", "pl", font=txt).returncode == 2


def test_fonts_under_assets_fonts_are_found_without_a_flag(proj):
    d = proj / "assets" / "fonts"
    d.mkdir(parents=True)
    font_variant(d / "a.ttf", static=True)
    r = bc("fontcheck", "--lang", "pl", "--no-platform", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert report(proj, "fontcheck")["fonts"] == ["assets/fonts/a.ttf"]


def test_a_named_font_is_checked_together_with_the_fonts_under_assets_fonts(proj):
    # naming a font outside assets/fonts/ (a master's or a page's) used to narrow the one fontcheck report to it, so the next
    # kit build found no licence row for the brand's own fonts and left them out of the kit
    d = proj / "assets" / "fonts"
    d.mkdir(parents=True)
    font_variant(d / "a.ttf", static=True)
    extra = proj / "assets" / "masters" / "deck"
    extra.mkdir(parents=True)
    font_variant(extra / "b.ttf", static=True)
    r = bc("fontcheck", "--lang", "pl", "--no-platform", "--font", str(extra / "b.ttf"), "--font", str(d / "a.ttf"), project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert report(proj, "fontcheck")["fonts"] == ["assets/fonts/a.ttf", "assets/masters/deck/b.ttf"]   # each once, assets/fonts/ first
    assert {"licence:assets/fonts/a.ttf", "licence:assets/masters/deck/b.ttf"} <= set(results(proj))


# ---------------------------------------------------------------- a run that drops a font an earlier run checked

ADVICE = "name every font in one run, or kit build leaves it out"


def run_named(proj, *fonts):
    """fontcheck with each of `fonts` named by --font (and the fonts under assets/fonts/ as always); the run must end 0."""
    args = ["fontcheck", "--lang", "pl", "--no-platform"]
    for f in fonts:
        args += ["--font", str(f)]
    r = bc(*args, project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def test_a_run_that_leaves_out_a_font_an_earlier_run_checked_warns_naming_it(proj):
    # the per-font trap: each run rewrites the one report, so the font of the run before drops out of it and kit build leaves it out
    deck = proj / "assets" / "masters" / "deck"
    deck.mkdir(parents=True)
    a, b = font_variant(deck / "a.ttf", static=True), font_variant(deck / "b.ttf", static=True)
    run_named(proj, a)
    assert "fonts:dropped" not in results(proj)   # the first run has no earlier report to compare with
    r = run_named(proj, b)
    row = results(proj)["fonts:dropped"]
    assert row["status"] == "warn" and row["dropped"] == ["assets/masters/deck/a.ttf"]
    assert "assets/masters/deck/a.ttf" in row["detail"] and ADVICE in row["detail"] and "b.ttf" not in row["detail"]
    assert "[WARN] fonts:dropped" in r.stdout
    assert report(proj, "fontcheck")["fonts"] == ["assets/masters/deck/b.ttf"]   # no merge: the report holds this run's fonts only
    assert report(proj, "fontcheck")["status"] == "pass"                          # a warning, never a failure
    # a run that names both is silent, and so is the one that follows it with the same two
    run_named(proj, a, b)
    assert "fonts:dropped" not in results(proj)
    assert report(proj, "fontcheck")["fonts"] == ["assets/masters/deck/a.ttf", "assets/masters/deck/b.ttf"]
    run_named(proj, b, a)
    assert "fonts:dropped" not in results(proj)
    # a font taken away since is not dropped, it is gone
    a.unlink()
    run_named(proj, b)
    assert "fonts:dropped" not in results(proj)


def test_a_font_of_a_master_left_out_of_the_next_run_warns_and_the_fonts_under_assets_fonts_never_do(proj):
    brand = proj / "assets" / "fonts"
    brand.mkdir(parents=True)
    font_variant(brand / "a.ttf", static=True)
    deck = proj / "assets" / "masters" / "deck"
    deck.mkdir(parents=True)
    b = font_variant(deck / "b.ttf", static=True)
    run_named(proj, b)
    assert report(proj, "fontcheck")["fonts"] == ["assets/fonts/a.ttf", "assets/masters/deck/b.ttf"]
    run_named(proj)   # no --font: assets/fonts/ again, the master's font left out
    assert results(proj)["fonts:dropped"]["dropped"] == ["assets/masters/deck/b.ttf"]
    assert report(proj, "fontcheck")["fonts"] == ["assets/fonts/a.ttf"]
    run_named(proj)   # the run after it has nothing left to drop
    assert "fonts:dropped" not in results(proj)


def test_a_font_outside_the_project_is_recorded_by_name_and_never_counted_as_dropped(proj, tmp_path):
    # the report keeps only the file name of a font outside the project, which the kit never holds: there is nothing to compare
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    x, y = font_variant(outside / "x.ttf", static=True), font_variant(outside / "y.ttf", static=True)
    run_named(proj, x)
    assert report(proj, "fontcheck")["fonts"] == ["x.ttf"]
    run_named(proj, y)
    assert "fonts:dropped" not in results(proj)


def test_an_earlier_report_that_cannot_be_read_is_said_and_the_run_goes_on(proj):
    run_named(proj, TEST_FONT)
    path = proj / "assets" / "_checks" / "fontcheck.json"
    path.write_text("{ not json", encoding="utf-8")
    run_named(proj, TEST_FONT)
    row = results(proj)["fonts:earlier"]
    assert row["status"] == "info" and "not compared" in row["detail"] and "fonts:dropped" not in results(proj)
    run_named(proj, TEST_FONT)   # the report just written reads fine, so the row is gone
    assert "fonts:earlier" not in results(proj)
    path.write_text(json.dumps({"tool": "fontcheck", "fonts": "assets/fonts/a.ttf"}), encoding="utf-8")   # `fonts` that is no list
    run_named(proj, TEST_FONT)
    assert "not compared" in results(proj)["fonts:earlier"]["detail"]


# ---------------------------------------------------------------- licence hint and budget

def test_licence_hint_reads_the_name_table(proj, tmp_path):
    fc(proj, "--lang", "pl")
    lic = results(proj)[f"licence:{TEST_FONT.name}"]
    assert lic["status"] == "info" and lic["recognised"] == "SIL Open Font License (OFL)" and "not legal advice" in lic["detail"]
    nolic = font_variant(tmp_path / "nolic.ttf", no_licence=True)
    assert fc(proj, "--lang", "pl", font=nolic).returncode == 0  # a warning, not a failure
    lic = results(proj)["licence:nolic.ttf"]
    assert lic["status"] == "warn" and lic["recognised"] is None and "no recognisable licence" in lic["detail"]


def test_the_licence_row_names_the_family_weight_and_style_of_the_file(proj):
    # The fixture read by hand with fontTools: name ID 16 absent, name ID 1 "Inter", OS/2 usWeightClass 400, fsSelection bit 0 clear, macStyle 0.
    r = fc(proj, "--lang", "pl")
    assert r.returncode == 0, r.stdout + r.stderr
    lic = results(proj)[f"licence:{TEST_FONT.name}"]
    assert (lic["family"], lic["weight"], lic["style"]) == ("Inter", 400, "normal")
    assert lic["status"] == "info" and lic["recognised"] == "SIL Open Font License (OFL)"  # the status and the facts are as before


FACE_VARIANTS = """
import sys
from fontTools.ttLib import TTFont
out, src = sys.argv[1], sys.argv[2]

def make(name, change):
    f = TTFont(src)
    change(f)
    f.save(f"{out}/{name}.ttf")

def by_fsselection(f):  # weight 700; italic by OS/2 fsSelection bit 0 alone
    f["OS/2"].usWeightClass = 700
    f["OS/2"].fsSelection |= 1
    f["head"].macStyle &= ~2

def by_macstyle(f):  # italic by head.macStyle bit 1 alone
    f["OS/2"].fsSelection &= ~1
    f["head"].macStyle |= 2

def typographic_family(f):  # name ID 16 beats name ID 1
    f["name"].setName("Inter Display", 16, 3, 1, 0x409)

def no_os2(f):  # no OS/2 table: weight 400, style from head.macStyle
    del f["OS/2"]
    f["head"].macStyle |= 2

def no_family(f):  # neither name ID 16 nor name ID 1: the file stem
    f["name"].names = [n for n in f["name"].names if n.nameID not in (1, 16)]

make("by-fsselection", by_fsselection)
make("by-macstyle", by_macstyle)
make("typographic-family", typographic_family)
make("no-os2", no_os2)
make("Brand-Sans", no_family)
"""


def test_the_licence_row_takes_the_family_weight_and_style_from_the_next_table_when_one_is_missing(proj, tmp_path):
    from helpers import fonttools
    made = fonttools(FACE_VARIANTS, str(tmp_path), str(TEST_FONT))
    assert made.returncode == 0, made.stderr
    names = ["by-fsselection", "by-macstyle", "typographic-family", "no-os2", "Brand-Sans"]
    args = ["fontcheck", "--lang", "pl", "--no-platform"]
    for n in names:
        args += ["--font", str(tmp_path / f"{n}.ttf")]
    r = bc(*args, project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    res = results(proj)
    got = {n: (res[f"licence:{n}.ttf"]["family"], res[f"licence:{n}.ttf"]["weight"], res[f"licence:{n}.ttf"]["style"]) for n in names}
    assert got == {
        "by-fsselection": ("Inter", 700, "italic"),
        "by-macstyle": ("Inter", 400, "italic"),
        "typographic-family": ("Inter Display", 400, "normal"),
        "no-os2": ("Inter", 400, "italic"),
        "Brand-Sans": ("Brand-Sans", 400, "normal"),
    }


WEIGHT_VARIANTS = """
import sys
from fontTools.ttLib import TTFont
out, src = sys.argv[1], sys.argv[2]
for name, stored in (("w-zero", 0), ("w-over", 1001), ("w-max", 1000), ("w-min", 1), ("w-huge", 65535)):
    f = TTFont(src)
    f["OS/2"].usWeightClass = stored
    f.save(f"{out}/{name}.ttf")
"""


def test_an_invalid_weight_class_is_taken_as_400_and_the_detail_says_the_stored_value_was_invalid(proj, tmp_path):
    from helpers import fonttools
    made = fonttools(WEIGHT_VARIANTS, str(tmp_path), str(TEST_FONT))
    assert made.returncode == 0, made.stderr
    names = ["w-zero", "w-over", "w-max", "w-min", "w-huge"]
    args = ["fontcheck", "--lang", "pl", "--no-platform"]
    for n in names:
        args += ["--font", str(tmp_path / f"{n}.ttf")]
    r = bc(*args, project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    res = results(proj)
    assert {n: res[f"licence:{n}.ttf"]["weight"] for n in names} == {"w-zero": 400, "w-over": 400, "w-max": 1000, "w-min": 1, "w-huge": 400}      # 1 to 1000 is a weight
    for n, stored in (("w-zero", 0), ("w-over", 1001), ("w-huge", 65535)):
        lic = res[f"licence:{n}.ttf"]
        assert f"OS/2 usWeightClass {stored} is not a valid weight (1 to 1000): taken as 400" in lic["detail"], lic["detail"]
        assert lic["status"] == "info" and lic["recognised"] == "SIL Open Font License (OFL)" and "not legal advice" in lic["detail"]      # nothing else about the row changed
    for n in ("w-max", "w-min"):
        assert "usWeightClass" not in res[f"licence:{n}.ttf"]["detail"]
    ok = fc(proj, "--lang", "pl")                                                  # the fixture's own 400 is valid and says nothing
    assert ok.returncode == 0 and "usWeightClass" not in results(proj)[f"licence:{TEST_FONT.name}"]["detail"]


def test_a_restricted_embedding_flag_fails_the_licence_hint(proj, tmp_path):
    restricted = font_variant(tmp_path / "restricted.ttf", fs_type=2)
    r = fc(proj, "--lang", "pl", font=restricted)
    assert r.returncode == 1
    assert failing(report(proj, "fontcheck")) == ["licence:restricted.ttf"]
    preview = font_variant(tmp_path / "preview.ttf", fs_type=4)
    assert fc(proj, "--lang", "pl", font=preview).returncode == 0
    assert results(proj)["licence:preview.ttf"]["status"] == "warn"


def test_font_budget_warns_beyond_two_families(proj, tmp_path):
    fonts = [font_variant(tmp_path / f"{n}.ttf", static=True, family=f"Test Family {n}") for n in ("a", "b", "c")]
    args = ["fontcheck", "--lang", "pl", "--no-platform"]
    for f in fonts:
        args += ["--font", str(f)]
    r = bc(*args, project=proj)
    assert r.returncode == 0, r.stdout
    b = results(proj)["budget:families"]
    assert b["status"] == "warn" and "3 families" in b["detail"]
    two = bc("fontcheck", "--lang", "pl", "--no-platform", "--font", str(fonts[0]), "--font", str(fonts[1]), project=proj)
    assert "budget:families" not in results(proj) and two.returncode == 0


# ---------------------------------------------------------------- the platform report (Chromium)

@pytest.mark.requires_setup
def test_platform_report_agrees_with_the_cmap_and_passes_its_control(proj):
    r = fc(proj, "--lang", "pl,de", platform=True)
    assert r.returncode == 0, r.stdout + r.stderr
    p = results(proj)[f"platform:{TEST_FONT.name}"]
    assert p["status"] == "pass" and p["fallback"] == [] and p["control"]["ok"] is True
    assert "control" in p["label"]


@pytest.mark.requires_setup
def test_platform_report_names_the_characters_chromium_replaced(proj):
    r = fc(proj, "--lang", "cs", platform=True)
    assert r.returncode == 1
    p = results(proj)[f"platform:{TEST_FONT.name}"]
    assert p["status"] == "fail" and set(p["fallback"]) == CS_MISSING  # Chromium and the cmap say the same thing
    assert p["control"]["ok"] is True


@pytest.mark.requires_setup
def test_fonts_command_prints_json_with_a_control(tmp_path):
    r = bc("fonts", "--font-file", str(TEST_FONT), "--text", "Zażółć", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["fallback"] == [] and out["control"]["ok"] is True and out["mode"] == "font-file"
    assert {c["char"] for c in out["chars"]} == set("Zażółć")
    r = bc("fonts", "--font-file", str(TEST_FONT), "--text", "Č", "--json")
    assert r.returncode == 1 and json.loads(r.stdout.strip().splitlines()[-1])["fallback"] == ["Č"]
    assert bc("fonts", "--text", "A").returncode == 2  # needs a font file or a family
    assert bc("fonts", "--font-file", str(TEST_FONT), "--family", "X", "--text", "A").returncode == 2


CATCH_ALL = """
import sys
from fontTools.ttLib import TTFont
f = TTFont(sys.argv[2]); cmap = f.getBestCmap()
for t in f["cmap"].tables:
    if t.isUnicode():
        for ch in sys.argv[3]:
            t.cmap[ord(ch)] = cmap[ord("A")]
f.save(sys.argv[1])
"""


@pytest.mark.requires_setup
def test_a_control_that_cannot_fail_makes_the_report_not_verified(proj, tmp_path):
    """A 'font' that holds every control character (a stand-in for a catch-all font) must not pass as a verified report."""
    out = tmp_path / "ctl.ttf"
    from helpers import fonttools
    r = fonttools(CATCH_ALL, str(out), str(TEST_FONT), "あ中กאअαжع")   # all eight candidates of render.mjs
    assert r.returncode == 0, r.stderr
    rc = fc(proj, "--lang", "pl", font=out, platform=True)
    p = results(proj)[f"platform:ctl.ttf"]
    assert p["status"] == "skipped" and "control failed" in p["detail"]
    assert rc.returncode == 3  # not verified, never a pass


@pytest.mark.requires_setup
def test_the_control_moves_on_when_no_system_font_holds_the_first_candidates(proj, tmp_path):
    """A machine with no CJK, Thai, Hebrew or Devanagari font (a bare Linux container) cannot make Chromium fall back for the first five
    candidates: it paints the requested font's .notdef. Simulated here by a font that holds those five, so the requested font is used for
    them; the control must then be Greek, Cyrillic or Arabic (which any desktop or container font set covers) and the report is verified.
    Before, the control was the first candidate only and fontcheck was 'not verified' on such a machine forever."""
    out = tmp_path / "nocjk.ttf"
    from helpers import fonttools
    r = fonttools(CATCH_ALL, str(out), str(TEST_FONT), "あ中กאअ")
    assert r.returncode == 0, r.stderr
    rc = fc(proj, "--lang", "pl", font=out, platform=True)
    p = results(proj)[f"platform:nocjk.ttf"]
    assert p["status"] == "pass" and p["control"]["ok"] is True and p["control"]["char"] in "αжع", p
    assert rc.returncode == 0, rc.stdout
