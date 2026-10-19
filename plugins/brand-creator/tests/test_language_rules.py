"""The `rules` of scripts/data/languages/<code>.json reach the work: book-lint checks the book text in each content language (warnings with
line and offset), and the prompt fragments name the rules (`fontcheck --print-rules`)."""
import json
import shutil
from pathlib import Path

import pytest
from helpers import ROOT, bc, report

import booklint

LANG_DIR = ROOT / "scripts" / "data" / "languages"


def rules(text, langs):
    return {r["id"]: r for r in booklint._language_rules(text, {"content_languages": langs})}


PL = '<html lang="pl"><body>\n<p>Idę w świat. "Cytat" i tak.</p>\n<p>Idę&nbsp;w świat, a potem „cytat”.</p></body></html>'


def test_polish_single_letter_words_and_quotes_warn_with_line_and_offset():
    r = rules(PL, ["pl"])
    nb, q = r["lang:pl:nbsp-single-letter"], r["lang:pl:low-opening-quote"]
    assert nb["status"] == "warn" and "line 2, offset" in nb["detail"] and "w świat" in nb["detail"] and "i tak" in nb["detail"]
    assert "line 3" not in nb["detail"]          # the no-break spaces on line 3 are fine
    assert q["status"] == "warn" and "line 2, offset" in q["detail"] and "line 3" not in q["detail"]


def test_clean_polish_text_passes():
    clean = '<html lang="pl"><body><p>Idę w&nbsp;świat i wracam z&nbsp;domu, „cytat”.</p></body></html>'
    r = rules(clean, ["pl"])
    assert r["lang:pl:nbsp-single-letter"]["status"] == "pass" and r["lang:pl:low-opening-quote"]["status"] == "pass"


def test_offsets_are_offsets_in_the_file_and_code_style_and_svg_are_ignored():
    t = '<html lang="pl"><style>p{content:"a b"}</style><svg><text>w x "y"</text></svg><pre>w x "y"</pre><body><p>o dom</p></body></html>'
    r = rules(t, ["pl"])
    d = r["lang:pl:nbsp-single-letter"]["detail"]
    assert r["lang:pl:low-opening-quote"]["status"] == "pass"
    assert f"offset {t.index('o dom')}" in d and d.count("offset") == 1


def test_with_several_content_languages_only_the_elements_in_that_language_are_checked():
    t = ('<html lang="en"><body><p lang="en" data-key="a">Go to "work" a b</p><p lang="pl" data-key="a">Idę w świat</p></body></html>')
    r = rules(t, ["en", "pl"])
    d = r["lang:pl:nbsp-single-letter"]["detail"]
    assert r["lang:pl:nbsp-single-letter"]["status"] == "warn" and d.count("offset") == 1 and "w świat" in d
    assert r["lang:pl:low-opening-quote"]["status"] == "pass"     # the straight quotes are English text
    assert "lang:en:typographic-quotes" not in r                   # a rule with no machine check adds no row


def test_a_language_with_no_checked_rule_or_no_text_adds_no_row():
    assert rules("<html><body><p>Hello w x</p></body></html>", ["en"]) == {}
    assert rules('<html><body><p lang="en">w x</p></body></html>', ["en", "pl"]) == {}


def test_czech_and_german_rules_use_their_own_data():
    cs = rules('<html lang="cs"><body><p>Jdu k lesu a pak s ním.</p></body></html>', ["cs"])["lang:cs:nbsp-single-letter"]
    assert cs["status"] == "warn" and cs["detail"].count("offset") == 3
    de = rules('<html lang="de"><body><p>Er sagte "ja".</p></body></html>', ["de"])["lang:de:low-opening-quote"]
    assert de["status"] == "warn"


def test_mutation_a_rule_without_its_check_stops_producing_rows(tmp_path, monkeypatch):
    d = tmp_path / "languages"
    shutil.copytree(LANG_DIR, d)
    f = d / "pl.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    for r in doc["rules"]:
        r.pop("check", None)
    f.write_text(json.dumps(doc), encoding="utf-8")
    assert "lang:pl:nbsp-single-letter" in rules(PL, ["pl"])
    monkeypatch.setattr(booklint, "LANG_DIR", d)
    assert rules(PL, ["pl"]) == {}


def test_every_check_in_the_data_is_one_the_lint_knows():
    for f in LANG_DIR.glob("*.json"):
        for r in json.loads(f.read_text(encoding="utf-8"))["rules"]:
            if "check" in r:
                assert r["check"]["kind"] in ("single-letter-nbsp", "low-opening-quote"), (f.name, r["id"])


def test_print_rules_names_the_rules_of_the_content_languages(tmp_path):
    from helpers import make_project
    p = make_project(tmp_path)
    assert bc("state", "--set", "content_languages=pl,en", project=p).returncode == 0
    r = bc("fontcheck", "--print-rules", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "pl: nbsp-single-letter" in r.stdout and "pl: low-opening-quote" in r.stdout and "en: typographic-quotes" in r.stdout
    assert "de:" not in r.stdout
    r = bc("fontcheck", "--print-rules", "--lang", "fr", project=p)
    assert "fr: nbsp-before-high-punctuation" in r.stdout


def test_the_designer_and_copy_fragments_name_the_rules():
    frag = (ROOT / "skills/brand-creator/references/prompt-fragments.md").read_text(encoding="utf-8")
    assert "LANGUAGE RULES" in frag and "fontcheck --print-rules" in frag
    copy = frag[frag.index("**Copy**"):]
    assert "fontcheck --print-rules" in copy
    assert "LANGUAGE RULES" in (ROOT / "agents/brand-designer.md").read_text(encoding="utf-8")
