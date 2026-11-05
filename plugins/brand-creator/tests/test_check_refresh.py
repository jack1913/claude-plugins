"""brand-creator check --refresh: a stale report that is a pure re-run of a check is run again before check judges; any other stale report is named and left alone.

The page-check runs in a real browser, so these tests need the set-up data folder, like tests/test_page_check.py."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from helpers import FIXTURES, bc, mutate, report

from test_book import built  # noqa: F401  (the built-book fixture)
from test_page_check import PAGE

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_node]
BOARD = "rounds/r1/board.html"


def row(p: Path, rid: str) -> dict:
    return next(r for r in report(p, "check")["results"] if r["id"] == rid)


def page_tool(p: Path) -> str:
    return next(f.stem for f in (p / "assets" / "_checks" / "page-check").glob("*.json"))


@pytest.fixture
def stale(acme):
    """A project whose page-check and board-lint reports were made, and then FACTS.md changed: both are stale."""
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    (acme / "pages").mkdir()
    (acme / "pages" / "index.html").write_text(PAGE, encoding="utf-8")
    r = bc("page-check", "pages/index.html", "--widths", "390", "--schemes", "light", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    r = bc("board-lint", BOARD, project=acme)
    assert r.returncode in (0, 1, 3), r.stdout + r.stderr
    for cmd in (("contrast",), ("logo-sheet",), ("shot", BOARD)):   # the gate reports a clean project has, so that only the FACTS.md edit stands between it and a pass
        r = bc(*cmd, project=acme)
        assert r.returncode == 0, (cmd, r.stdout + r.stderr)
    with (acme / "FACTS.md").open("a", encoding="utf-8") as f:
        f.write("\n<!-- edited after the reports -->\n")
    return acme


def test_check_without_refresh_says_not_verified_and_names_the_command(stale):
    r = bc("check", project=stale)
    assert r.returncode == 3 and report(stale, "check")["status"] == "not-verified", r.stdout + r.stderr
    lint = row(stale, "report:board-lint")
    assert lint["status"] == "skipped" and "stale" in lint["detail"] and f"brand-creator board-lint {BOARD}" in lint["detail"], lint


def test_refresh_runs_the_stale_page_check_then_board_lint_and_both_are_current_after(stale):
    before = {f: f.read_bytes() for f in (stale / "assets" / "_checks").rglob("*.json")}
    r = bc("check", "--refresh", project=stale)
    out = r.stdout + r.stderr
    lines = [ln for ln in out.splitlines() if ln.startswith("refresh: ")]
    assert any("brand-creator page-check pages/index.html --widths 390 --schemes light -> exit 0" in ln for ln in lines), out   # the options the report records are passed on
    assert any(f"brand-creator board-lint {BOARD} ->" in ln for ln in lines), out
    assert [i for i, ln in enumerate(lines) if "page-check" in ln][0] < [i for i, ln in enumerate(lines) if "board-lint" in ln][0]   # the page-checks first
    for f, old in before.items():
        if f.parent.name == "page-check" or f.name == "board-lint.json":
            assert f.read_bytes() != old, f"{f.name} was not made again"
        elif f.name != "check.json":
            assert f.read_bytes() == old, f"{f.name} was touched"
    rows = {x["id"]: x for x in report(stale, "check")["results"]}
    assert not any("stale" in x.get("detail", "") for x in rows.values() if x["id"].startswith("report:")), [(k, x["detail"]) for k, x in rows.items() if "stale" in x.get("detail", "")]
    assert report(stale, "check")["status"] == "pass" and r.returncode == 0, out


def test_widths_from_the_rules_are_read_again_and_widths_given_on_the_command_line_are_kept(stale):
    """An edit of qa/rules.json page.widths makes the page-check stale: a check made with the rules' widths is re-run at the new ones, one made with --widths keeps them."""
    pc = report(stale, f"page-check/{page_tool(stale)}")
    assert pc["widths_from"] == "flag" and pc["schemes_from"] == "flag", pc   # the fixture ran --widths 390 --schemes light
    rules_file = stale / "qa" / "rules.json"
    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    rules.setdefault("page", {})["widths"] = [390, 1440]
    rules_file.write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")
    out = bc("check", "--refresh", project=stale).stdout
    assert "brand-creator page-check pages/index.html --widths 390 --schemes light -> exit 0" in out, out
    assert bc("page-check", "pages/index.html", "--schemes", "light", project=stale).returncode == 0   # now from the rules
    assert report(stale, f"page-check/{page_tool(stale)}")["widths_from"] == "rules"
    rules["page"]["widths"] = [1440]
    rules_file.write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")
    out = bc("check", "--refresh", project=stale).stdout
    assert "brand-creator page-check pages/index.html --schemes light -> exit 0" in out, out
    assert report(stale, f"page-check/{page_tool(stale)}")["widths"] == [1440]


def test_a_stale_report_that_is_not_a_pure_re_run_is_named_and_never_run(stale):
    assert bc("state", "--record", "G5", "approved (test)", project=stale).returncode == 0
    for kv in ("content_languages=en", "edition=1"):
        assert bc("state", "--set", kv, project=stale).returncode == 0
    assert bc("adapters", "--brand-md", project=stale).returncode == 0
    brand_md = (stale / "BRAND.md").read_bytes()
    adapters_report = stale / "assets" / "_checks" / "adapters.json"
    old = adapters_report.read_bytes()
    with (stale / "BRAND-STATE.md").open("a", encoding="utf-8") as f:
        f.write("\n")
    mutate(stale / "FACTS.md", "<!-- edited after the reports -->", "<!-- edited again -->")
    r = bc("check", "--refresh", project=stale)
    out = r.stdout + r.stderr
    assert "refresh: adapters is stale and is not re-run" in out, out
    assert "brand-creator adapters" not in "\n".join(ln for ln in out.splitlines() if ln.startswith("refresh: ") and "is not re-run" not in ln), out
    assert (stale / "BRAND.md").read_bytes() == brand_md and adapters_report.read_bytes() == old


def test_a_re_run_that_fails_is_said_so_and_check_still_runs(stale):
    (stale / "pages" / "index.html").write_text(PAGE, encoding="utf-8")
    tokens_css = stale / "assets" / "tokens" / "tokens.css"
    tokens_css.write_text(tokens_css.read_text(encoding="utf-8") + "\n/* changed */\n", encoding="utf-8")   # stale, and the page can be checked again
    shutil.move(str(stale / "assets" / "tokens" / "tokens.json"), str(stale / "tokens.json.away"))     # but the built tokens are gone: page-check cannot run (exit 3)
    r = bc("check", "--refresh", project=stale)
    out = r.stdout + r.stderr
    assert "FAILED: no report was written" in out and "check:" in out and r.returncode != 0, out


def test_refresh_with_nothing_stale_runs_nothing(acme):
    r = bc("check", "--refresh", project=acme)
    assert "refresh: no stale report" in r.stdout and "refresh: brand-creator" not in r.stdout


def test_contrast_is_re_run_with_cvd_when_its_report_has_the_cvd_block(acme):
    assert bc("contrast", "--cvd", project=acme).returncode == 0
    assert "cvd" in report(acme, "contrast")
    with (acme / "qa" / "rules.json").open("a", encoding="utf-8") as f:
        f.write("\n")
    r = bc("check", "--refresh", project=acme)
    out = r.stdout + r.stderr
    assert "refresh: brand-creator contrast --cvd -> exit 0" in out, out
    assert "cvd" in report(acme, "contrast")


def test_contrast_is_held_back_while_the_built_tokens_are_stale(acme):
    assert bc("contrast", project=acme).returncode == 0
    for f in (acme / "tokens" / "primitives.tokens.json", acme / "qa" / "rules.json"):
        with f.open("a", encoding="utf-8") as h:
            h.write("\n")
    r = bc("check", "--refresh", project=acme)
    out = r.stdout + r.stderr
    assert "refresh: contrast is stale and is not re-run: the built tokens are stale too" in out, out
    assert "refresh: brand-creator contrast" not in out


def test_book_lint_is_re_run_with_self_consistency_and_the_book_is_named(built, tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(built, proj)
    assert bc("book-lint", "book.html", "--self-consistency", project=proj).returncode == 0
    with (proj / "FACTS.md").open("a", encoding="utf-8") as f:
        f.write("\n<!-- edited -->\n")
    r = bc("check", "--refresh", project=proj)
    out = r.stdout + r.stderr
    assert "refresh: brand-creator book-lint book.html --self-consistency -> exit 0" in out, out
    assert "refresh: book is stale and is not re-run" in out, out
    assert not any(x["id"] == "report:book-lint" and "stale" in x.get("detail", "") for x in report(proj, "check")["results"])


def test_a_board_lint_that_only_the_page_check_re_run_made_stale_is_re_run_after_it(stale):
    """The board-lint report lists the page-check report as its only input: current before the refresh, stale once the page-check ran again."""
    pc = f"assets/_checks/page-check/{page_tool(stale)}.json"
    path = stale / "assets" / "_checks" / "board-lint.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["inputs"] = [{"path": pc, "sha256": hashlib.sha256((stale / pc).read_bytes()).hexdigest()}]
    path.write_text(json.dumps(doc), encoding="utf-8")
    r = bc("check", "--refresh", project=stale)
    out = r.stdout + r.stderr
    assert f"brand-creator board-lint {BOARD} ->" in out, out
    assert out.index("brand-creator page-check") < out.index("brand-creator board-lint"), out


# ---------------------------------------------------------------- the paths no project reaches easily: a recorded failure, a timeout, the recorded options

import subprocess  # noqa: E402
import types  # noqa: E402

from helpers import ROOT  # noqa: E402


def _load_check() -> types.ModuleType:
    """scripts/check.py as a module, without its last line (`main_guard(main)`, which would run the command on import)."""
    f = ROOT / "scripts" / "check.py"
    src = f.read_text(encoding="utf-8").rstrip()
    assert src.endswith("main_guard(main)")
    mod = types.ModuleType("check_under_test")
    mod.__file__ = str(f)
    exec(compile(src[: -len("main_guard(main)")], str(f), "exec"), mod.__dict__)
    return mod


check = _load_check()


def test_a_re_run_that_records_its_failure_is_said_so_and_a_timeout_is_said_so(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "error: the tokens are unreadable\nfailure recorded in assets/_checks/contrast.json\n"))
    assert check.run_refresh(tmp_path, ["contrast"]) is False
    out = capsys.readouterr()
    assert "refresh: brand-creator contrast -> exit 1: error: the tokens are unreadable  [FAILED: the report records the failure]" in out.out, out
    def too_slow(*a, **k):
        raise subprocess.TimeoutExpired(a, 1800)
    monkeypatch.setattr(check.subprocess, "run", too_slow)
    assert check.run_refresh(tmp_path, ["board-lint", BOARD]) is False
    out = capsys.readouterr()
    assert f"refresh: brand-creator board-lint {BOARD} -> timed out after 1800 s  [FAILED]" in out.out and "run `brand-creator board-lint" in out.err, out


def test_the_book_lint_re_run_keeps_allow_variants_and_a_removed_book_is_not_promised_to_check(built, tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(built, proj)
    assert bc("book-lint", "book.html", "--allow-variants", project=proj).returncode in (0, 1)
    assert report(proj, "book-lint").get("allow_variants") is True, "book-lint records --allow-variants"
    words, _ = check.refresh_command(proj, "book-lint", report(proj, "book-lint"))
    assert words == ["book-lint", "book.html", "--allow-variants"], words
    (proj / "book.html").unlink()
    words, why = check.refresh_command(proj, "book-lint", report(proj, "book-lint"))
    assert words is None and why.endswith(check.GONE), why


def test_contrast_keeps_skip_marks_and_kit_check_is_a_pure_re_run(tmp_path):
    doc = {"results": [{"id": "touching:skipped-on-purpose", "status": "info"}], "cvd": {}}
    assert check.refresh_command(tmp_path, "contrast", doc)[0] == ["contrast", "--cvd", "--skip-marks"]
    assert check.refresh_command(tmp_path, "contrast", {"results": []})[0] == ["contrast"]
    assert check.refresh_command(tmp_path, "kit-check", {})[0] == ["kit", "check"]
