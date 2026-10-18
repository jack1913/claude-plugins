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


# ---------------------------------------------------------------- licence hint and budget

def test_licence_hint_reads_the_name_table(proj, tmp_path):
    fc(proj, "--lang", "pl")
    lic = results(proj)[f"licence:{TEST_FONT.name}"]
    assert lic["status"] == "info" and lic["recognised"] == "SIL Open Font License (OFL)" and "not legal advice" in lic["detail"]
    nolic = font_variant(tmp_path / "nolic.ttf", no_licence=True)
    assert fc(proj, "--lang", "pl", font=nolic).returncode == 0  # a warning, not a failure
    lic = results(proj)["licence:nolic.ttf"]
    assert lic["status"] == "warn" and lic["recognised"] is None and "no recognisable licence" in lic["detail"]


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
