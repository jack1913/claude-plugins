"""The website references and the site round: `capture` (stills of a page, or of a real site). These tests need no Chromium: every refusal comes before the browser starts."""
import json
from pathlib import Path

from helpers import bc, make_project

PAGE = "<!doctype html><html><head><meta charset=utf-8><title>t</title></head><body><h1>A page</h1></body></html>"


def _page(p: Path, rel: str) -> str:
    f = p / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(PAGE, encoding="utf-8")
    return rel


def _files(p: Path) -> list[str]:
    return sorted(str(f.relative_to(p)) for f in p.rglob("*") if f.is_file())


def test_capture_refuses_an_address_that_is_not_http(tmp_path):
    p = make_project(tmp_path)
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0     # the owner's answer is not what stops these
    before = _files(p)
    with_password = "@".join(["https://user:secret", "example.invalid/"])                     # joined: the static scan reads a literal one as an e-mail address
    for bad in ("file:///etc/hosts", "ftp://example.invalid/", "javascript:alert(1)", "example.invalid", with_password):
        r = bc("capture", "--url", bad, "--name", "a-site", project=p)
        assert r.returncode == 2, (bad, r.stdout, r.stderr)
        assert "capture takes an http(s) address" in r.stderr or "without a user name or password" in r.stderr, (bad, r.stderr)
        assert "secret" not in r.stdout + r.stderr, "a password in the address is never echoed"
    assert not (p / "research" / "site-refs").exists()
    assert _files(p) == before                                                              # nothing was written, nothing was fetched
    # --url takes no page, --wait belongs to the page form, --name to --url, and a page form needs its page
    page = _page(p, "rounds/r1/a/index.html")
    for args in (("--url", "https://example.invalid/", "--name", "a-site", page), ("--url", "https://example.invalid/", "--name", "a-site", "--wait", "10"),
                 (page, "--name", "a-site"), ()):
        r = bc("capture", *args, project=p)
        assert r.returncode == 2, (args, r.stdout, r.stderr)


def test_capture_url_needs_the_owners_online_research_answer(tmp_path):
    p = make_project(tmp_path)
    assert bc("state", "--get", "site_research", project=p).stdout.strip() == "auto"
    # a loopback address with nothing listening: it cannot be reached, and no name is looked up
    address = "http://127.0.0.1:1/"
    for answer in ("auto", "none"):
        assert bc("state", "--set", f"site_research={answer}", project=p).returncode == 0
        r = bc("capture", "--url", address, "--name", "a-site", project=p)
        assert r.returncode == 2, (answer, r.stdout, r.stderr)
        assert "state --set site_research" in r.stderr and "07w-website-references" in r.stderr, r.stderr
        assert not (p / "research").exists(), "nothing is written before the owner has answered"
    assert bc("state", "--set", "site_research=links-only", project=p).returncode == 0
    r = bc("capture", "--url", address, "--name", "a-site", project=p)
    assert r.returncode in (1, 3), (r.stdout, r.stderr)                                    # 1: the site did not load; 3: no Chromium here
    assert "state --set site_research" not in r.stderr, r.stderr                           # the answer is accepted now
    assert not (p / "research").exists(), "a capture that failed leaves nothing behind"


def test_capture_url_needs_a_plain_name(tmp_path):
    p = make_project(tmp_path)
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0
    for name in ("My Site", "x", "-site", "Site", "a_b", "../escape", "a/b", "a" * 42):
        r = bc("capture", "--url", "https://example.invalid/", "--name", name, project=p)
        assert r.returncode == 2, (name, r.stdout, r.stderr)
        assert "--name" in r.stderr, (name, r.stderr)
    r = bc("capture", "--url", "https://example.invalid/", project=p)                      # no name at all
    assert r.returncode == 2 and "--name" in r.stderr, r.stderr
    assert not (p / "research").exists()


def test_capture_url_will_not_take_another_site_into_a_name_in_use(tmp_path):
    p = make_project(tmp_path)
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0
    held = p / "research" / "site-refs" / "taken-name"
    held.mkdir(parents=True)
    (held / "capture.json").write_text(json.dumps({"schema": 1, "tool": "capture", "source": {"url": "https://example.invalid/one"}}), encoding="utf-8")
    before = _files(p)
    r = bc("capture", "--url", "https://example.invalid/two", "--name", "taken-name", project=p)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "research/site-refs/taken-name/ already holds a capture of https://example.invalid/one" in r.stderr and "use another --name" in r.stderr, r.stderr
    (held / "capture.json").write_text("{not json", encoding="utf-8")                      # a record that cannot be read is not overwritten either
    r = bc("capture", "--url", "https://example.invalid/two", "--name", "taken-name", project=p)
    assert r.returncode == 2 and "cannot be read" in r.stderr, r.stderr
    assert (held / "capture.json").read_text(encoding="utf-8") == "{not json"
    assert len(_files(p)) == len(before)


def test_capture_url_will_not_write_into_the_owners_folder(tmp_path):
    p = make_project(tmp_path)
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0
    owners = p / "research" / "site-refs" / "owner"                                         # the screenshots the owner sent, named like the files a capture writes
    owners.mkdir(parents=True)
    (owners / "1440.png").write_bytes(b"the owner's own screenshot")
    before = _files(p)
    r = bc("capture", "--url", "http://127.0.0.1:1/", "--name", "owner", project=p)
    assert r.returncode == 2, (r.stdout, r.stderr)                                          # exit 2 and not 1: it never tried to load the address
    assert "--name owner is reserved" in r.stderr and "use another --name" in r.stderr, r.stderr
    assert (owners / "1440.png").read_bytes() == b"the owner's own screenshot"
    assert _files(p) == before, "no capture.json, no picture: nothing was written"
    # the name stays reserved with no folder yet, and before the owner's answer is looked at
    (tmp_path / "other").mkdir()
    other = make_project(tmp_path / "other")
    r = bc("capture", "--url", "http://127.0.0.1:1/", "--name", "owner", project=other)
    assert r.returncode == 2 and "--name owner is reserved" in r.stderr, (r.stdout, r.stderr)
    assert not (other / "research").exists()


def test_capture_url_will_not_write_into_a_folder_that_holds_no_capture(tmp_path):
    p = make_project(tmp_path)
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0
    address = "http://127.0.0.1:1/"                                                         # nothing listens there: a refusal that does not fire ends in exit 1 (3 without Chromium)
    mine = p / "research" / "site-refs" / "their-site"
    mine.mkdir(parents=True)
    (mine / "390.png").write_bytes(b"not a capture")
    before = _files(p)
    r = bc("capture", "--url", address, "--name", "their-site", project=p)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "research/site-refs/their-site exists and holds no capture.json" in r.stderr and "use another --name" in r.stderr, r.stderr
    assert (mine / "390.png").read_bytes() == b"not a capture"
    assert _files(p) == before
    # something that is not even a folder is in the way: the same refusal
    (p / "research" / "site-refs" / "a-file").write_text("x", encoding="utf-8")
    r = bc("capture", "--url", address, "--name", "a-file", project=p)
    assert r.returncode == 2 and "holds no capture.json" in r.stderr, (r.stdout, r.stderr)
    # an empty folder holds nothing to overwrite: it is taken (here the address does not answer, and the folder stays empty)
    (p / "research" / "site-refs" / "empty-one").mkdir()
    r = bc("capture", "--url", address, "--name", "empty-one", project=p)
    assert r.returncode in (1, 3), (r.stdout, r.stderr)
    assert "holds no capture.json" not in r.stderr, r.stderr
    assert list((p / "research" / "site-refs" / "empty-one").iterdir()) == []


def test_capture_refuses_a_page_in_an_earlier_round(tmp_path):
    p = make_project(tmp_path)
    old = _page(p, "rounds/r1/Ledger/index.html")
    (p / "rounds" / "r2").mkdir()
    r = bc("capture", old, project=p)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "rounds/r1/Ledger/index.html is inside rounds/r1/, and every round before the latest (rounds/r2/) is read-only" in r.stderr, r.stderr
    assert "copy the page into the latest round and capture it there" in r.stderr, r.stderr
    assert not (p / "rounds" / "r1" / "Ledger" / "shots").exists()
    # history/ is frozen the same way
    frozen = _page(p, "history/2026-10-23-approved/Ledger/index.html")
    r = bc("capture", frozen, project=p)
    assert r.returncode == 2 and "is inside history/, which is read-only" in r.stderr, (r.stdout, r.stderr)
    assert not (p / "history" / "2026-10-23-approved" / "Ledger" / "shots").exists()
    # a page outside the project, and a page that is not there, are usage errors too
    outside = tmp_path / "x.html"                                                          # the project is tmp_path/acme
    outside.write_text(PAGE, encoding="utf-8")
    assert bc("capture", str(outside), project=p).returncode == 2
    assert bc("capture", "rounds/r2/missing.html", project=p).returncode == 2


# ---------------------------------------------------------------- site approve: the approved pages of the site round go into site/
# The pages board, its pages, their page-check reports and stills are the ones of test_site_board.py (made by hand in the shape of group 1's tools), so these tests need no browser.

import hashlib
import re
from urllib.parse import unquote

import pytest
from helpers import mutate, mutate_json, page_check_report, symlink_or_skip
from test_site_board import PAGES, lint, lint3, pages_project, settle

import sitedata
from _common import CliError, gate_recorded

G4P = "approved start, pricing; rules c1"

RICH_START = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>start</title>
<!-- a comment may name https://comment.invalid/x.png: it loads nothing -->
<link rel="stylesheet" href="../../../assets/tokens/tokens.css">
<link rel="stylesheet" href="./site.css">
<link rel="stylesheet" href="css/nested.css">
<style>.hero{background:url("../../../assets/logo/mark.svg")} @import "../../../assets/tokens/tokens.css";</style>
<script>var elsewhere = "https://script.invalid/not-read.js";</script>
</head>
<body data-layout="walkthrough" data-page="start" style="background-image:url('../../../assets/logo/mark.svg')">
<h1>start</h1>
<img src="./hero.svg" srcset="./hero.svg 1x, ../../../assets/logo/mark.svg 2x" alt="">
<picture><source srcset="../../../assets/logo/mark.svg 480w, ./hero.svg 960w"><img src="img/bg.png" alt=""></picture>
<video poster="../../../assets/logo/mark.svg"></video>
<img src="data:image/png;base64,AAAA,BBBB" alt="">
<a href="../pricing/index.html#plans">Pricing</a> <a href="#top">Top</a> <a href="mailto:?subject=hi">Write</a> <a href="tel:+000">Call</a>
</body></html>
"""


def richen(p: Path) -> None:
    """Give the start page of the pages round the paths a real page has, and settle its report and stills again (it is a new page to the checks)."""
    (p / "assets" / "logo").mkdir(parents=True, exist_ok=True)
    (p / "assets" / "logo" / "mark.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (p / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    (p / "assets" / "fonts" / "Test.woff2").write_bytes(b"not really a font")
    folder = p / "rounds" / "r3" / "start"
    (folder / "img").mkdir()
    (folder / "css").mkdir()
    (folder / "img" / "bg.png").write_bytes(b"not really a picture")
    (folder / "hero.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (folder / "site.css").write_text('@font-face{font-family:T;src:url("../../../assets/fonts/Test.woff2")}\n.a{background:url(img/bg.png)}\n', encoding="utf-8")
    (folder / "css" / "nested.css").write_text(".n{background:url(../../../../assets/logo/mark.svg)}\n.m{background:url(../img/bg.png)}\n", encoding="utf-8")
    (folder / "index.html").write_text(RICH_START, encoding="utf-8")
    settle(p, 3, "start")


def ready(tmp_path: Path, *, g4p: bool = True, rich: bool = False, colds: dict | None = None) -> Path:
    """The pages board of round 3 (start and pricing, built from the hero Ledger of round 2), linted and passing, and G4p recorded: what `site approve` waits for."""
    p = pages_project(tmp_path, colds=colds)
    if rich:
        richen(p)
    r = lint3(p)
    assert r.returncode == 0, r.stdout
    if g4p:
        assert bc("state", "--record", "G4p", G4P, project=p).returncode == 0
    return p


def approve(p: Path, *extra: str):
    return bc("site", "approve", *extra, project=p)


def untouched(p: Path, before: list[str]) -> None:
    """A refusal writes nothing: no site/, no staging folder, no other file."""
    assert not (p / "site").exists()
    assert not [d for d in p.iterdir() if d.name.startswith("site-new")]
    assert _files(p) == before


def resolving(p: Path, f: Path) -> list[str]:
    """The relative paths of an .html or .css file that do not lead to a file (#..., data:, mailto: and tel: are not paths)."""
    text = f.read_text(encoding="utf-8")
    urls = re.findall(r'(?:src|href|poster)="([^"]*)"', text) if f.suffix == ".html" else []
    urls += [u for s in re.findall(r'srcset="([^"]*)"', text) for u in (x.split()[0] for x in s.split(",") if x.strip())]
    urls += [a or b or c for a, b, c in re.findall(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)"'\s]+))\s*\)""", text)] + re.findall(r'@import\s+"([^"]*)"', text)
    bad = []
    for u in urls:
        if not u or u.startswith(("#", "data:", "mailto:", "tel:")):
            continue
        if not (f.parent / unquote(re.split(r"[?#]", u)[0])).resolve().exists():
            bad.append(u)
    return bad


def test_site_approve_needs_g4p(tmp_path):
    p = ready(tmp_path, g4p=False)
    before = _files(p)
    r = approve(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "G4p" in r.stderr and "brand-creator state --record G4p" in r.stderr, r.stderr
    untouched(p, before)


def test_site_approve_needs_a_current_passing_lint_of_the_pages_board(tmp_path):
    p = ready(tmp_path)
    lint_json, board = p / "assets" / "_checks" / "board-lint.json", p / "rounds" / "r3" / "board.html"
    before = _files(p)
    lint_json.unlink()                                                                       # never linted
    r = approve(p)
    assert r.returncode == 1 and "there is no board-lint report" in r.stderr and "lint the pages board first: brand-creator board-lint rounds/r3/board.html" in r.stderr, (r.stdout, r.stderr)
    untouched(p, [x for x in before if not x.endswith("board-lint.json")])
    assert lint3(p).returncode == 0
    mutate(board, "</body>", "<!-- changed after the lint --></body>")                       # linted, then changed
    r = approve(p)
    assert r.returncode == 1 and "the board-lint report is stale" in r.stderr and "rounds/r3/board.html changed" in r.stderr, (r.stdout, r.stderr)
    assert not (p / "site").exists()
    assert lint(p, "rounds/r2/board.html").returncode == 0                                   # the lint of another board is no lint of this one
    r = approve(p)
    assert r.returncode == 1 and "the board-lint report is for rounds/r2/board.html, not rounds/r3/board.html" in r.stderr, (r.stdout, r.stderr)
    mutate(board, 'data-section="reply"', 'data-section="reply-x"')                          # a lint that failed
    assert lint3(p).returncode == 1
    r = approve(p)
    assert r.returncode == 1 and "is 'fail', not pass" in r.stderr and "brand-creator board-lint rounds/r3/board.html" in r.stderr, (r.stdout, r.stderr)
    assert not (p / "site").exists()


def test_recording_g4p_after_the_lint_makes_it_stale_when_a_page_check_read_brand_state(tmp_path):
    p = pages_project(tmp_path)
    for pid in PAGES:                                                                        # an older page-check report lists the whole of BRAND-STATE.md among the files it was made from
        page_check_report(p, f"rounds/r3/{pid}/index.html", "pass", also=("BRAND-STATE.md",))
    assert lint3(p).returncode == 0
    assert bc("state", "--record", "G4p", G4P, project=p).returncode == 0
    r = approve(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "BRAND-STATE.md changed" in r.stderr and "check each page again" in r.stderr, r.stderr
    assert "brand-creator page-check rounds/r3/start/index.html" in r.stderr and "brand-creator page-check rounds/r3/pricing/index.html" in r.stderr, r.stderr
    assert "then lint the board" in r.stderr and "brand-creator board-lint rounds/r3/board.html" in r.stderr, r.stderr
    assert not (p / "site").exists()
    for pid in PAGES:                                                                        # the pages checked again after the record, then the board linted again: it goes through
        page_check_report(p, f"rounds/r3/{pid}/index.html", "pass", also=("BRAND-STATE.md",))
    assert lint3(p).returncode == 0
    r = approve(p)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert sitedata.validate_site(p) == []


def check_rows(p: Path) -> dict:
    """The rows of `check` about the site proof: id -> (status, detail). The exit code has other reasons in a synthetic project; the rows are what counts."""
    from helpers import report
    bc("check", project=p)
    return {x["id"]: (x["status"], x.get("detail", "")) for x in report(p, "check")["results"] if x["id"].startswith(("site:", "report:board-lint"))}


def test_a_changed_g4_rule_after_the_lint_names_the_g4_rules_and_asks_for_the_pages_again(tmp_path):
    """(m) The page-check reports of the pages hold BRAND-STATE.md by its G4 rules: a "(rule)" line that changes after the lint makes the lint stale with a message that says so (`the G4 rules changed`, not
    `recording a gate`), names `page-check` for each page and then the lint; the pages checked again and the board linted again go through."""
    p = pages_project(tmp_path)
    mine = ("BRAND-STATE.md#g4-rules", "FACTS.md")
    assert bc("state", "--record", "G4p", G4P, project=p).returncode == 0
    for pid in PAGES:
        page_check_report(p, f"rounds/r3/{pid}/index.html", "pass", also=mine)
    assert lint3(p).returncode == 0
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule) one mark per screen")
    r = approve(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "the board-lint report is stale (BRAND-STATE.md (the G4 rules) changed)" in r.stderr, r.stderr
    assert "the G4 rules changed, which the page-check reports of the pages were made from: check each page again" in r.stderr and "recording a gate" not in r.stderr, r.stderr
    assert "brand-creator page-check rounds/r3/start/index.html" in r.stderr and "brand-creator page-check rounds/r3/pricing/index.html" in r.stderr, r.stderr
    assert "then lint the board" in r.stderr and "brand-creator board-lint rounds/r3/board.html" in r.stderr, r.stderr
    assert not (p / "site").exists()
    for pid in PAGES:
        page_check_report(p, f"rounds/r3/{pid}/index.html", "pass", also=mine)
    assert lint3(p).returncode == 0
    r = approve(p)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_a_gate_recorded_after_the_lint_asks_for_the_lint_only_when_a_rule_cites_brand_state(tmp_path):
    """(m) A rule whose source only BRAND-STATE.md holds puts the whole file among the inputs of the lint (siteboard.choices_rows), so recording G4p after the lint makes it stale. The page-check reports are
    current (they hold the G4 rules only), so the message asks for the lint again and not for a page check; the board linted again goes through. After the approval, G5 recorded makes the lint stale and only the lint:
    the site rows stay current, and the lint run again (the finish chain does) settles it."""
    cited = "the stamp sits alone on the left edge"
    p = pages_project(tmp_path)
    state = p / "BRAND-STATE.md"
    state.write_text(state.read_text(encoding="utf-8") + f"\n## Notes\n\n- {cited}\n", encoding="utf-8")
    mutate(p / "rounds" / "r3" / "board.html", 'data-source="the stamp appears once per view"', f'data-source="{cited}"')
    for pid in PAGES:
        page_check_report(p, f"rounds/r3/{pid}/index.html", "pass", also=("BRAND-STATE.md#g4-rules", "FACTS.md"))
    assert lint3(p).returncode == 0, lint3(p).stdout
    assert bc("state", "--record", "G4p", G4P, project=p).returncode == 0
    r = approve(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "the board-lint report is stale (BRAND-STATE.md changed)" in r.stderr, r.stderr
    assert "which a rule of the board cites as its source: lint the board again" in r.stderr and "check each page again" not in r.stderr and "brand-creator page-check" not in r.stderr, r.stderr
    assert not (p / "site").exists()
    assert lint3(p).returncode == 0
    r = approve(p)
    assert r.returncode == 0, (r.stdout, r.stderr)
    from helpers import capture_record
    for pid in PAGES:
        page_check_report(p, f"site/{pid}/index.html", "pass", also=("BRAND-STATE.md#g4-rules", "FACTS.md"))
        capture_record(p, f"site/{pid}/index.html")
    assert {k: v[0] for k, v in check_rows(p).items()} == {"report:board-lint": "pass", "site:record": "pass", "site:pages": "pass", "site:stills": "pass"}
    assert bc("state", "--record", "G5", "book approved", project=p).returncode == 0
    stale = check_rows(p)                                                                    # the lint read the file for a source: it is stale, the page checks are not
    assert stale["report:board-lint"][0] == "skipped" and "BRAND-STATE.md changed" in stale["report:board-lint"][1], stale
    assert stale["site:pages"][0] == stale["site:stills"][0] == "pass", stale
    assert lint3(p).returncode == 0                                                          # the finish chain lints the board of the latest round again
    assert {k: v[0] for k, v in check_rows(p).items()} == {"report:board-lint": "pass", "site:record": "pass", "site:pages": "pass", "site:stills": "pass"}


def test_a_gate_recorded_after_the_pages_are_approved_leaves_the_proof_of_the_site_current(tmp_path):
    """(m) Finishing a site project: a page-check report holds BRAND-STATE.md by its G4 rules only, so recording G4p, approving, then recording G5 and G6, setting the phase and linting the pages board again
    (the finish chain does) leaves `report:board-lint` and the site rows of `check` current; a changed "(rule)" line does not. Synthetic project; the reports are written by hand in the shape page-check gives them."""
    from _common import stale_inputs
    from helpers import capture_record, report
    p = pages_project(tmp_path)
    mine = ("BRAND-STATE.md#g4-rules", "FACTS.md")
    for pid in PAGES:
        page_check_report(p, f"rounds/r3/{pid}/index.html", "pass", also=mine)
    assert lint3(p).returncode == 0
    lint = report(p, "board-lint")
    held = [i for i in lint["inputs"] if i["path"] == "BRAND-STATE.md"]
    assert len(held) == 1 and held[0]["part"] == "g4-rules", "the lint follows the page-check reports: the same part, listed once"
    assert bc("state", "--record", "G4p", G4P, project=p).returncode == 0
    assert stale_inputs(p, lint) == [], "recording G4p changes BRAND-STATE.md and not its G4 rules"
    r = approve(p)                                                                           # no page checked again, no lint again in between
    assert r.returncode == 0, (r.stdout, r.stderr)
    for pid in PAGES:
        page_check_report(p, f"site/{pid}/index.html", "pass", also=mine)
        capture_record(p, f"site/{pid}/index.html")

    def rows() -> dict:
        return check_rows(p)
    before = rows()
    assert {k: v[0] for k, v in before.items()} == {"report:board-lint": "pass", "site:record": "pass", "site:pages": "pass", "site:stills": "pass"}, before
    assert bc("state", "--set", "phase=P12", project=p).returncode == 0
    assert bc("state", "--record", "G5", "book approved", project=p).returncode == 0
    assert bc("state", "--record", "G6", "adoption go", project=p).returncode == 0
    assert {k: v[0] for k, v in rows().items()} == {k: "pass" for k in before}, rows()
    assert lint3(p).returncode == 0                                                          # the finish chain lints the board of the latest round again
    after = rows()
    assert {k: v[0] for k, v in after.items()} == {k: "pass" for k in before}, after
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule) one mark per screen")          # a G4 rule is a change the proof stands on
    changed = rows()
    assert changed["report:board-lint"][0] == "skipped" and "BRAND-STATE.md (the G4 rules) changed" in changed["report:board-lint"][1], changed
    assert changed["site:pages"][0] == "skipped" and "BRAND-STATE.md (the G4 rules) changed" in changed["site:pages"][1], changed


def test_site_approve_takes_only_a_site_board_at_the_pages_stage(tmp_path):
    p = ready(tmp_path)
    before = _files(p)
    r = approve(p, "--round", "2")                                                           # the hero board
    assert r.returncode == 2 and "rounds/r2/board.html is not a site board at the pages stage" in r.stderr and "data-site-stage='hero'" in r.stderr, (r.stdout, r.stderr)
    r = approve(p, "--round", "9")
    assert r.returncode == 2 and "rounds/r9/board.html does not exist" in r.stderr, (r.stdout, r.stderr)
    r = approve(p, "--round", "1")                                                           # round 1 is no board here
    assert r.returncode == 2, (r.stdout, r.stderr)
    untouched(p, before)
    (tmp_path / "other").mkdir()
    empty = make_project(tmp_path / "other")
    assert bc("state", "--record", "G4p", G4P, project=empty).returncode == 0
    r = approve(empty)                                                                       # no round at all
    assert r.returncode == 2 and "there is no round yet" in r.stderr, (r.stdout, r.stderr)
    assert not (empty / "site").exists()


def test_site_approve_takes_a_known_action_only(tmp_path):
    p = ready(tmp_path)
    for args in ((), ("publish",), ("approve", "--round", "x")):
        r = bc("site", *args, project=p)
        assert r.returncode == 2, (args, r.stdout, r.stderr)
    assert not (p / "site").exists()


def test_site_approve_copies_pages_and_rewrites_project_paths(tmp_path):
    p = ready(tmp_path, rich=True, colds={"start": "ship"})
    source = {f: (p / f).read_bytes() for f in _files(p) if f.startswith("rounds/")}
    assert (p / "rounds/r3/start/cold-review.md").is_file() and (p / "rounds/r3/start/shots/capture.json").is_file()
    r = approve(p)
    assert r.returncode == 0, (r.stdout, r.stderr)
    site = p / "site"
    # what was copied: the page folder without its stills and its cold review, and the record
    assert sorted(str(f.relative_to(site)) for f in site.rglob("*") if f.is_file()) == sorted(
        ["site.json", "start/index.html", "start/hero.svg", "start/site.css", "start/css/nested.css", "start/img/bg.png", "pricing/index.html"])
    # the paths: a file outside the page's folder is reached from site/start/ now; the page's own files and the rest stay as written
    html = (site / "start" / "index.html").read_text(encoding="utf-8")
    assert html.count('href="../../assets/tokens/tokens.css"') == 1 and 'href="../../../assets/tokens/tokens.css"' not in html
    assert 'href="./site.css"' in html and 'href="css/nested.css"' in html and 'src="./hero.svg"' in html and 'src="img/bg.png"' in html
    assert '.hero{background:url("../../assets/logo/mark.svg")} @import "../../assets/tokens/tokens.css";' in html
    assert """style="background-image:url('../../assets/logo/mark.svg')">""" in html
    assert 'srcset="./hero.svg 1x, ../../assets/logo/mark.svg 2x"' in html
    assert 'srcset="../../assets/logo/mark.svg 480w, ./hero.svg 960w"' in html
    assert 'poster="../../assets/logo/mark.svg"' in html
    assert 'href="../pricing/index.html#plans"' in html, "a link to a sibling page leads to the approved sibling"
    assert 'href="#top"' in html and 'href="mailto:?subject=hi"' in html and 'href="tel:+000"' in html and 'src="data:image/png;base64,AAAA,BBBB"' in html
    assert "https://comment.invalid/x.png" in html and "https://script.invalid/not-read.js" in html, "a comment and a script are not read"
    assert (site / "start" / "site.css").read_text(encoding="utf-8") == '@font-face{font-family:T;src:url("../../assets/fonts/Test.woff2")}\n.a{background:url(img/bg.png)}\n'
    assert (site / "start" / "css" / "nested.css").read_text(encoding="utf-8") == ".n{background:url(../../../assets/logo/mark.svg)}\n.m{background:url(../img/bg.png)}\n"
    for f in site.rglob("*"):
        if f.suffix in (".html", ".css"):
            assert resolving(p, f) == [], (f, resolving(p, f))
    assert (site / "start" / "hero.svg").read_bytes() == (p / "rounds/r3/start/hero.svg").read_bytes()
    # the round is left as it was
    assert {f: (p / f).read_bytes() for f in _files(p) if f.startswith("rounds/")} == source
    # what it says to do next, and the record the book and `check` read
    for pid in ("start", "pricing"):
        assert f"brand-creator capture site/{pid}/index.html" in r.stdout and f"brand-creator page-check site/{pid}/index.html" in r.stdout
    assert "brand-creator check" in r.stdout
    assert sitedata.validate_site(p) == []


def test_site_approve_leaves_the_key_frames_in_the_round(tmp_path):
    """G4-04: the key frames `capture --frames` writes are in shots/, which is not copied: the approved page has none until a capture is run on it, and a frame is never copied into site/<id>/shots/."""
    p = ready(tmp_path, colds={"start": "ship"})
    shots = p / "rounds/r3/start/shots"
    for n in (0, 50, 100):
        (shots / f"frame-1440-{n}.png").write_bytes(b"a key frame of the first screen")
    r = approve(p)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert not (p / "site" / "start" / "shots").exists()
    assert [f for f in (p / "site").rglob("*") if "frame-1440" in f.name] == []
    assert all((shots / f"frame-1440-{n}.png").read_bytes() == b"a key frame of the first screen" for n in (0, 50, 100)), "the round is left as it was"


def test_site_json_records_the_choices_and_layouts_of_the_board(tmp_path):
    p = ready(tmp_path)
    assert approve(p).returncode == 0
    doc = json.loads((p / "site" / "site.json").read_text(encoding="utf-8"))
    assert list(doc) == ["schema", "approved", "round", "hero", "pages", "choices"]
    assert doc["schema"] == 1 and doc["round"] == 3 and doc["hero"] == "Ledger"
    assert doc["approved"] == gate_recorded(p, "G4p") and doc["approved"].endswith(G4P)
    assert doc["pages"] == [{"id": pid, "path": f"site/{pid}/index.html", "layout": "walkthrough", "sha256": hashlib.sha256((p / "site" / pid / "index.html").read_bytes()).hexdigest()} for pid in PAGES]
    assert doc["choices"] == [{"id": "c1", "text": "The stamp appears once per view", "tag": "rule", "source": "the stamp appears once per view", "pages": ["start", "pricing"]},
                              {"id": "c2", "text": "Pricing sits under the stages", "tag": "example", "source": "", "pages": ["start"]}]
    assert (p / "site" / "site.json").read_text(encoding="utf-8").endswith("}\n")
    assert sitedata.load_site(p) == doc and sitedata.validate_site(p) == []
    # a choice with no data-pages is a choice of every page
    assert sitedata.record_problems(doc) == []


def test_site_approve_refuses_a_network_url(tmp_path):
    p = ready(tmp_path)
    page = p / "rounds" / "r3" / "start" / "index.html"
    plain = "<h1>start</h1>"
    cases = (('<img src="https://example.invalid/x.png">', "https://example.invalid/x.png is an address on the network: a reference page needs no network"),
             ('<link rel="stylesheet" href="//cdn.invalid/x.css">', "//cdn.invalid/x.css is an address on the network"),
             ('<style>.a{background:url(http://example.invalid/x.png)}</style>', "http://example.invalid/x.png is an address on the network"),
             ('<img src="/assets/x.png">', "/assets/x.png starts with / and leads to a place on a web server"),
             ('<img src="./missing.png">', "./missing.png leads to rounds/r3/start/missing.png, which does not exist"))
    for added, needle in cases:
        before_text = mutate(page, plain, plain + added)
        settle(p, 3, "start")
        assert lint3(p).returncode == 0
        before = _files(p)
        r = approve(p)
        assert r.returncode == 1, (added, r.stdout, r.stderr)
        assert needle in r.stderr and "rounds/r3/start/index.html line" in r.stderr and "nothing was written" in r.stderr, (added, r.stderr)
        untouched(p, before)
        page.write_text(before_text, encoding="utf-8")
    # one bad page stops them all: the good page is not written alone
    pricing = p / "rounds" / "r3" / "pricing" / "index.html"
    mutate(pricing, plain.replace("start", "pricing"), plain.replace("start", "pricing") + '<img src="https://example.invalid/y.png">')
    settle(p, 3, "start")
    settle(p, 3, "pricing")
    assert lint3(p).returncode == 0
    before = _files(p)
    r = approve(p)
    assert r.returncode == 1 and "rounds/r3/pricing/index.html line" in r.stderr and "rounds/r3/start" not in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)


def test_site_approve_refuses_a_path_outside_the_project(tmp_path):
    p = ready(tmp_path)
    page = p / "rounds" / "r3" / "start" / "index.html"
    plain = "<h1>start</h1>"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.png").write_bytes(b"outside")
    (p / "assets" / "escape").symlink_to(outside)                                            # a folder of the project that leads out of it
    for added, needle in (('<img src="../../../../outside/x.png">', "../../../../outside/x.png leads outside the project"),
                          ('<img src="../../../assets/escape/x.png">', "which is a link to a place outside the project")):
        before_text = mutate(page, plain, plain + added)
        settle(p, 3, "start")
        assert lint3(p).returncode == 0
        before = _files(p)
        r = approve(p)
        assert r.returncode == 2, (added, r.stdout, r.stderr)
        assert needle in r.stderr and "nothing was written" in r.stderr, (added, r.stderr)
        untouched(p, before)
        page.write_text(before_text, encoding="utf-8")
    settle(p, 3, "start")                                                                    # the page as it was written first
    assert lint3(p).returncode == 0
    # a stylesheet of the page is read the same way
    css = page.parent / "site.css"
    css.write_text(".a{background:url(../../../../../outside/x.png)}\n", encoding="utf-8")
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2 and "rounds/r3/start/site.css line 1" in r.stderr and "leads outside the project" in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)
    css.unlink()
    # a symbolic link inside a page folder is never copied
    (page.parent / "link.svg").symlink_to(outside / "x.png")
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2 and "rounds/r3/start/link.svg is a symbolic link" in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)


LINKED = "is a symbolic link: a page folder is copied as it is, and a link can lead out of the project"
BOARD_LINKED = "is a symbolic link: the pages board is read as it is, and a link can lead out of the project"


def test_site_approve_refuses_a_page_folder_that_is_a_symbolic_link(tmp_path):
    p = ready(tmp_path)
    folder = p / "rounds" / "r3" / "start"
    moved = tmp_path / "moved-start"                                                          # the page folder with its files, kept outside the project and reached through a link
    folder.rename(moved)
    symlink_or_skip(folder, moved)
    assert (folder / "index.html").is_file(), "the link leads to the page: the lint of the board is still current"
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert f"rounds/r3/start {LINKED}" in r.stderr and "nothing was written" in r.stderr and "1 problem(s)" in r.stderr, r.stderr
    untouched(p, before)
    # a link to a folder of the project is refused the same way: the page is read where it stands, not where a link says
    folder.unlink()
    inside = p / "rounds" / "r3" / "start-copy"
    shutil.copytree(moved, inside)
    symlink_or_skip(folder, inside)
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2 and f"rounds/r3/start {LINKED}" in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)
    folder.unlink()
    moved.rename(folder)
    shutil.rmtree(inside)
    assert approve(p).returncode == 0, "the same pages with no link go in"


def test_site_approve_refuses_rounds_a_round_or_the_board_file_that_is_a_symbolic_link(tmp_path):
    p = ready(tmp_path)
    rounds = p / "rounds"
    board = rounds / "r3" / "board.html"
    # the board file
    held = tmp_path / "board-elsewhere.html"
    board.rename(held)
    symlink_or_skip(board, held)
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2 and f"rounds/r3/board.html {BOARD_LINKED}" in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)
    board.unlink()
    held.rename(board)
    # the round: rounds/r3 leads to a folder that holds the board and both pages
    moved_round = tmp_path / "r3-elsewhere"
    (rounds / "r3").rename(moved_round)
    symlink_or_skip(rounds / "r3", moved_round)
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2 and f"rounds/r3 {BOARD_LINKED}" in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)
    (rounds / "r3").unlink()
    moved_round.rename(rounds / "r3")
    # rounds/ itself
    moved_rounds = tmp_path / "rounds-elsewhere"
    rounds.rename(moved_rounds)
    symlink_or_skip(rounds, moved_rounds)
    before = _files(p)
    r = approve(p)
    assert r.returncode == 2 and f"rounds {BOARD_LINKED}" in r.stderr, (r.stdout, r.stderr)
    untouched(p, before)
    r = approve(p, "--round", "3")                                                           # a named round is looked at the same way
    assert r.returncode == 2 and f"rounds {BOARD_LINKED}" in r.stderr, (r.stdout, r.stderr)
    rounds.unlink()
    moved_rounds.rename(rounds)
    assert approve(p).returncode == 0, "the same pages with no link go in"


def test_site_approve_refuses_a_folder_link_inside_a_page_folder_whatever_it_leads_to(tmp_path):
    p = ready(tmp_path)
    folder = p / "rounds" / "r3" / "start"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.png").write_bytes(b"outside")
    inner = folder / "img"
    inner.mkdir()
    (inner / "a.png").write_bytes(b"a picture of the page")
    for name, target in (("to-outside", outside), ("to-inside", inner)):
        symlink_or_skip(folder / name, target)
        settle(p, 3, "start")
        assert lint3(p).returncode == 0
        before = _files(p)
        r = approve(p)
        assert r.returncode == 2, (name, r.stdout, r.stderr)
        assert f"rounds/r3/start/{name} {LINKED}" in r.stderr and "nothing was written" in r.stderr, (name, r.stderr)
        untouched(p, before)
        (folder / name).unlink()


def test_site_approve_never_overwrites_and_replace_moves_the_old_site_aside(tmp_path):
    p = ready(tmp_path)
    assert approve(p).returncode == 0
    still = p / "site" / "start" / "shots" / "1440-light.png"                                # what `capture` leaves beside an approved page
    still.parent.mkdir()
    still.write_bytes(b"a still of the approved page")
    held = {f: (p / f).read_bytes() for f in _files(p) if f.startswith("site/")}
    r = approve(p)
    assert r.returncode == 1 and "site/ holds approved pages already" in r.stderr and "nothing was written" in r.stderr and "site approve --replace" in r.stderr, (r.stdout, r.stderr)
    assert {f: (p / f).read_bytes() for f in _files(p) if f.startswith("site/")} == held
    r = approve(p, "--replace")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "the previous site/ is in removed-2026-10-17/site/" in r.stdout
    assert {f[len("removed-2026-10-17/"):]: (p / f).read_bytes() for f in _files(p) if f.startswith("removed-2026-10-17/")} == held
    assert not (p / "site" / "start" / "shots").exists(), "the new pages have no stills until capture is run on them"
    assert sitedata.validate_site(p) == []
    r = approve(p, "--replace")                                                              # a second replace the same day: its own folder, the first is kept
    assert r.returncode == 0 and "removed-2026-10-17-2/site/" in r.stdout, (r.stdout, r.stderr)
    assert (p / "removed-2026-10-17" / "site" / "start" / "shots" / "1440-light.png").read_bytes() == b"a still of the approved page"
    assert (p / "removed-2026-10-17-2" / "site" / "site.json").is_file()
    assert not [d for d in p.iterdir() if d.name.startswith("site-new")]


def test_site_approve_with_replace_keeps_the_old_site_when_the_new_pages_fail(tmp_path):
    p = ready(tmp_path)
    assert approve(p).returncode == 0
    held = {f: (p / f).read_bytes() for f in _files(p) if f.startswith("site/")}
    page = p / "rounds" / "r3" / "start" / "index.html"
    mutate(page, "<h1>start</h1>", '<h1>start</h1><img src="https://example.invalid/x.png">')
    settle(p, 3, "start")
    assert lint3(p).returncode == 0
    r = approve(p, "--replace")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert {f: (p / f).read_bytes() for f in _files(p) if f.startswith("site/")} == held
    assert not [d for d in p.iterdir() if d.name.startswith(("removed-", "site-new"))]


def test_validate_site_names_what_is_wrong_with_the_record_and_the_pages(tmp_path):
    p = ready(tmp_path)
    assert approve(p).returncode == 0
    assert sitedata.validate_site(p) == []
    record = p / "site" / "site.json"
    original = record.read_text(encoding="utf-8")
    cases = (("tag", lambda d: d["choices"][0].update(tag="maybe"), "the tag is 'maybe', not rule or example"),
             ("rule without a source", lambda d: d["choices"][0].update(source=""), "a rule says where it was decided"),
             ("unknown layout", lambda d: d["pages"][0].update(layout="no-such-layout"), "is no id of page-layouts.json"),
             ("own layout of no word", lambda d: d["pages"][0].update(layout="own:"), "no own:<word>"),
             ("choice names a page that is not there", lambda d: d["choices"][1].update(pages=["ghost"]), "ghost, which is no page of the record"),
             ("schema", lambda d: d.update(schema=2), "schema is 2, not 1"),
             ("a path that is not the page's", lambda d: d["pages"][1].update(path="site/other/index.html"), "the path is 'site/other/index.html', not site/pricing/index.html"),
             ("a page id used twice", lambda d: d["pages"][1].update(id="start"), "start: the id is used twice"),
             ("no hero", lambda d: d.update(hero=""), "hero is empty"),
             ("the page was edited", lambda d: d["pages"][0].update(sha256="0" * 64), "site/start/index.html changed since it was approved"))
    for name, fn, needle in cases:
        mutate_json(record, fn)
        found = sitedata.validate_site(p)
        assert any(needle in x for x in found), (name, found)
        record.write_text(original, encoding="utf-8")
        assert sitedata.validate_site(p) == [], name
    # a page edited by hand after it was approved
    page = p / "site" / "start" / "index.html"
    kept = mutate(page, "<h1>start</h1>", "<h1>start, edited</h1>")
    found = sitedata.validate_site(p)
    assert found and "site/start/index.html changed since it was approved" in found[0] and "site approve --replace" in found[0], found
    page.write_text(kept, encoding="utf-8")
    assert sitedata.validate_site(p) == []
    page.unlink()
    assert any("site/start/index.html is missing" in x for x in sitedata.validate_site(p)), sitedata.validate_site(p)
    page.write_text(kept, encoding="utf-8")
    # the record itself: unreadable, gone
    record.write_text("{not json", encoding="utf-8")
    assert "site/site.json cannot be read" in sitedata.validate_site(p)[0]
    with pytest.raises(CliError) as e:
        sitedata.load_site(p)
    assert e.value.code == 1 and "site/site.json cannot be read" in e.value.message
    record.unlink()
    assert sitedata.validate_site(p) == ["site/site.json is missing: the approved pages are put there by `brand-creator site approve`"]
    with pytest.raises(CliError) as e:
        sitedata.load_site(p)
    assert e.value.code == 1 and "site/site.json is missing" in e.value.message


def test_a_record_may_name_a_layout_of_its_own_and_a_rule_needs_a_source():
    doc = {"schema": 1, "approved": "2026-11-04 approved start", "round": 3, "hero": "Ledger",
           "pages": [{"id": "start", "path": "site/start/index.html", "layout": "own:atlas", "sha256": "a" * 64},
                     {"id": "pricing", "path": "site/pricing/index.html", "layout": "walkthrough", "sha256": "b" * 64}],
           "choices": [{"id": "c1", "text": "The stamp appears once per view", "tag": "rule", "source": "DECISIONS.md 14", "pages": ["start"]},
                       {"id": "c2", "text": "Pricing sits under the stages", "tag": "example"}]}
    assert sitedata.record_problems(doc) == []
    doc["choices"][1]["tag"] = "rule"                                                        # a rule without where it was decided
    assert any("c2: a rule says where it was decided" in x for x in sitedata.record_problems(doc))
    doc["choices"][1]["source"] = "  "
    assert any("c2: a rule says where it was decided" in x for x in sitedata.record_problems(doc))
    assert sitedata.record_problems([]) == ["site/site.json is not a JSON object"]
    assert any("lacks" in x for x in sitedata.record_problems({"schema": 1}))


def test_rewrite_urls_reads_the_forms_of_a_path_and_keeps_the_rest(tmp_path):
    for d in ("assets/tokens", "assets/img", "rounds/r3/start", "rounds/r3/pricing"):
        (tmp_path / d).mkdir(parents=True)
    for f in ("assets/tokens/tokens.css", "assets/img/a b.png", "assets/img/m.svg", "rounds/r3/start/hero.svg", "rounds/r3/pricing/index.html"):
        (tmp_path / f).write_text("x", encoding="utf-8")
    moves = {"rounds/r3/start": "site/start", "rounds/r3/pricing": "site/pricing"}

    def html(text: str):
        return sitedata.rewrite_urls(text, "html", project=tmp_path, file_dir="rounds/r3/start", new_file_dir="site/start", moves=moves, label="rounds/r3/start/index.html")

    text = ("<!doctype html>\n<link rel=stylesheet href=../../../assets/tokens/tokens.css>\n<link rel='stylesheet' href='./hero.svg?v=2#a'>\n"
            '<img src="../../../assets/img/a%20b.png"><img src="../../../assets/img/a b.png"><use xlink:href="../../../assets/img/m.svg#i"/>\n'
            '<object data="../../../assets/img/m.svg"></object><div data-src="https://data-attribute.invalid/x.png" action="https://form.invalid/post"></div>\n'
            '<img srcset="../../../assets/img/m.svg, hero.svg 2x,data:image/png;base64,AA,BB 3x"><a href="../pricing/">p</a><a href="">e</a><a href="?q=1">q</a>\n')
    new, problems = html(text)
    assert problems == []
    assert "<link rel=stylesheet href=../../assets/tokens/tokens.css>" in new, "an unquoted value is rewritten in place"
    assert "href='./hero.svg?v=2#a'" in new, "a path in the page's folder keeps its query and fragment as written"
    assert 'src="../../assets/img/a%20b.png"' in new and 'src="../../assets/img/a b.png"' in new, "a percent-encoded path stays encoded, a plain one stays plain"
    assert 'xlink:href="../../assets/img/m.svg#i"' in new and '<object data="../../assets/img/m.svg">' in new
    assert 'data-src="https://data-attribute.invalid/x.png"' in new and 'action="https://form.invalid/post"' in new, "data-* and action load nothing"
    assert 'srcset="../../assets/img/m.svg, hero.svg 2x,data:image/png;base64,AA,BB 3x"' in new
    assert '<a href="../pricing/">p</a><a href="">e</a><a href="?q=1">q</a>' in new
    # the problems, one per URL, with the line they are on
    bad = ('<img src="https://a.invalid/x.png">\n<img src="//a.invalid/x.png"><img src="/x.png"><img src="nothere.png">\n<img src="../../../../../x.png">\n'
           '<a href="javascript:void(0)">go</a><img srcset="hero.svg 1x, https://a.invalid/y.png 2x">')
    new, problems = html(bad)
    assert [(c, m.split(": ", 1)[0]) for c, m in problems] == [(1, "rounds/r3/start/index.html line 1"), (1, "rounds/r3/start/index.html line 2"), (1, "rounds/r3/start/index.html line 2"),
                                                                (1, "rounds/r3/start/index.html line 2"), (2, "rounds/r3/start/index.html line 3"), (1, "rounds/r3/start/index.html line 4"),
                                                                (1, "rounds/r3/start/index.html line 4")], problems
    assert "uses the javascript: scheme" in problems[5][1] and "leads outside the project" in problems[4][1]
    # a stylesheet: url() in its three forms, @import in two, a comment is not read, the folder it is in decides what stays
    css = ('/* url(https://a.invalid/c.png) */ @import "../../../../assets/tokens/tokens.css"; @import url(\'../../../../assets/tokens/tokens.css\');\n'
           '.a{background:url(  "../../../../assets/img/m.svg"  )} .b{background:url(../x.svg)} .c{background:url(../hero.svg)}')
    (tmp_path / "rounds/r3/start/x.svg").write_text("x", encoding="utf-8")
    (tmp_path / "rounds/r3/start/css").mkdir()
    new, problems = sitedata.rewrite_urls(css, "css", project=tmp_path, file_dir="rounds/r3/start/css", new_file_dir="site/start/css", moves=moves)
    assert problems == []
    assert new == css.replace("../../../../assets", "../../../assets"), new


# ---------------------------------------------------------------- check gates the approved pages (site:record, site:pages, site:stills)
# The page-check reports and the stills of the approved pages are made by hand in the shape of group 1's tools (helpers.page_check_report, helpers.capture_record), so these tests need no browser.

import shutil

from helpers import capture_record, report
from pagecheck import report_tool

SITE_ROWS = ("site:record", "site:pages", "site:stills")


def approved(tmp_path: Path) -> Path:
    """The pages of round 3 approved into site/ (G4p recorded, `site approve` run): no page-check report and no stills of them yet."""
    p = ready(tmp_path)
    assert approve(p).returncode == 0
    return p


def settle_site(p: Path, *pages: str) -> None:
    """The page-check report and the stills `brand-creator page-check site/<id>/index.html` and `brand-creator capture site/<id>/index.html` leave behind (every page when none is named)."""
    for pid in pages or PAGES:
        page_check_report(p, f"site/{pid}/index.html", "pass")
        capture_record(p, f"site/{pid}/index.html")


def checked(tmp_path: Path) -> Path:
    p = approved(tmp_path)
    settle_site(p)
    return p


def run_check(p: Path):
    """-> (the result of `brand-creator check`, the site:* rows of its report by id)."""
    r = bc("check", project=p)
    assert r.returncode in (0, 1, 3), (r.stdout, r.stderr)
    return r, {x["id"]: x for x in report(p, "check")["results"] if x["id"].startswith("site:")}


def test_check_passes_the_approved_pages_that_are_as_approved_checked_and_captured(tmp_path):
    p = checked(tmp_path)
    got = run_check(p)[1]
    assert list(got) == list(SITE_ROWS), got
    assert [got[x]["status"] for x in SITE_ROWS] == ["pass", "pass", "pass"], got
    assert got["site:record"]["detail"] == "G4p is recorded; site/site.json is sound and each of its 2 page(s) is as approved (start, pricing)"
    assert got["site:pages"]["detail"] == "2 page(s) have a current passing page-check report: start, pricing"
    assert got["site:stills"]["detail"] == "2 page(s) have current stills: start, pricing"


def test_check_fails_a_hand_edited_approved_page(tmp_path):
    p = checked(tmp_path)
    assert run_check(p)[1]["site:record"]["status"] == "pass"
    page = p / "site" / "start" / "index.html"
    kept = mutate(page, "<h1>start</h1>", "<h1>start, edited by hand</h1>")
    r, got = run_check(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert got["site:record"]["status"] == "fail", got
    assert "site/start/index.html changed since it was approved" in got["site:record"]["detail"] and "site approve --replace" in got["site:record"]["detail"] and "put the approved page back" in got["site:record"]["detail"]
    assert "pricing" not in got["site:record"]["detail"], "only the page that changed is named"
    # what was made from the page is not a verdict on the page as it is now: the page-check report and the stills of that page are stale, the other page's are not
    for rid, cmd in (("site:pages", "page-check"), ("site:stills", "capture")):
        assert got[rid]["status"] == "skipped" and got[rid]["detail"].startswith("not verified: start: "), (rid, got[rid])
        assert f"brand-creator {cmd} site/start/index.html" in got[rid]["detail"] and "site/start/index.html changed" in got[rid]["detail"] and "pricing" not in got[rid]["detail"], got[rid]
    page.write_text(kept, encoding="utf-8")                                                  # the approved page put back
    assert [run_check(p)[1][x]["status"] for x in SITE_ROWS] == ["pass", "pass", "pass"]


def test_check_fails_g4p_without_site_json(tmp_path):
    p = ready(tmp_path)                                                                      # G4p recorded, `site approve` not run
    r, got = run_check(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert list(got) == ["site:record"] and got["site:record"]["status"] == "fail", got      # there are no pages to judge
    assert "G4p is recorded but site/site.json does not exist" in got["site:record"]["detail"] and "brand-creator site approve" in got["site:record"]["detail"]
    assert approve(p).returncode == 0                                                        # approved: the row passes (the pages are not checked yet)
    r, got = run_check(p)
    assert got["site:record"]["status"] == "pass" and got["site:pages"]["status"] == "skipped" and got["site:stills"]["status"] == "skipped", got
    # a record with no approval behind it is a failure too: nothing but `site approve` after G4p puts pages in site/
    (tmp_path / "other").mkdir()
    other = make_project(tmp_path / "other")
    (other / "site").mkdir()
    (other / "site" / "site.json").write_text("{}\n", encoding="utf-8")
    r, got = run_check(other)
    assert r.returncode == 1 and list(got) == ["site:record"] and got["site:record"]["status"] == "fail", (r.stdout, got)
    assert "exists but G4p, the owner's approval of the pages, is not recorded" in got["site:record"]["detail"] and "state --record G4p" in got["site:record"]["detail"]


def test_check_says_not_verified_without_a_page_check_of_each_site_page(tmp_path):
    p = approved(tmp_path)
    r, got = run_check(p)
    assert got["site:record"]["status"] == "pass"
    assert got["site:pages"]["status"] == "skipped" and got["site:pages"]["detail"].startswith("not verified: start: no page-check/"), got["site:pages"]
    for pid in PAGES:
        assert f"brand-creator page-check site/{pid}/index.html" in got["site:pages"]["detail"], got["site:pages"]
        assert f"brand-creator capture site/{pid}/index.html" in got["site:stills"]["detail"], got["site:stills"]
    assert got["site:stills"]["status"] == "skipped", got["site:stills"]
    # one page checked: only the other one is named
    page_check_report(p, "site/start/index.html", "pass")
    got = run_check(p)[1]
    assert got["site:pages"]["status"] == "skipped" and "brand-creator page-check site/pricing/index.html" in got["site:pages"]["detail"] and "site/start" not in got["site:pages"]["detail"], got["site:pages"]
    # a report that is no verdict says which rows it could not verify
    page_check_report(p, "site/pricing/index.html", "not-verified")
    got = run_check(p)[1]
    assert got["site:pages"]["status"] == "skipped" and "not a verdict" in got["site:pages"]["detail"] and "page:load: not verified: no view was measured" in got["site:pages"]["detail"], got["site:pages"]
    assert "brand-creator page-check site/pricing/index.html" in got["site:pages"]["detail"]
    # the report of another page is no report of this one
    folder = p / "assets" / "_checks"
    shutil.copy(folder / f"{report_tool('site/start/index.html')}.json", folder / f"{report_tool('site/pricing/index.html')}.json")
    got = run_check(p)[1]
    assert got["site:pages"]["status"] == "skipped" and "is the report of project site/start/index.html, not of the project page site/pricing/index.html" in got["site:pages"]["detail"], got["site:pages"]
    # a report of a page that was not measured as a project page (a built site given with --from) is no report of it either
    other = json.loads((folder / f"{report_tool('site/start/index.html')}.json").read_text(encoding="utf-8"))
    other["target"] = {"kind": "from", "page": None, "from": "/somewhere/else", "url": None}
    (folder / f"{report_tool('site/start/index.html')}.json").write_text(json.dumps(other), encoding="utf-8")
    got = run_check(p)[1]
    assert got["site:pages"]["status"] == "skipped" and "is the report of from /somewhere/else, not of the project page site/start/index.html" in got["site:pages"]["detail"], got["site:pages"]
    page_check_report(p, "site/start/index.html", "pass")                                    # both checked: it passes
    page_check_report(p, "site/pricing/index.html", "pass")
    assert run_check(p)[1]["site:pages"]["status"] == "pass"
    # the stills: one page captured, the other not; the capture of another page; a still that is gone; a still that is other bytes than the record lists
    capture_record(p, "site/start/index.html")
    got = run_check(p)[1]
    assert got["site:stills"]["status"] == "skipped" and "no site/pricing/shots/capture.json; run `brand-creator capture site/pricing/index.html`" in got["site:stills"]["detail"] and "site/start" not in got["site:stills"]["detail"], got["site:stills"]
    shutil.copytree(p / "site" / "start" / "shots", p / "site" / "pricing" / "shots")
    got = run_check(p)[1]
    assert "it is the capture of site/start/index.html, not of site/pricing/index.html" in got["site:stills"]["detail"] and got["site:stills"]["status"] == "skipped", got["site:stills"]
    capture_record(p, "site/pricing/index.html")
    assert run_check(p)[1]["site:stills"]["status"] == "pass"
    (p / "site" / "pricing" / "shots" / "390-dark.png").unlink()
    got = run_check(p)[1]
    assert got["site:stills"]["status"] == "skipped" and "site/pricing/shots/390-dark.png (the 390-dark still) is not there" in got["site:stills"]["detail"], got["site:stills"]
    capture_record(p, "site/pricing/index.html")
    (p / "site" / "start" / "shots" / "1440-light.png").write_bytes(b"another picture")
    got = run_check(p)[1]
    assert got["site:stills"]["status"] == "skipped" and "site/start/shots/1440-light.png is not the 1440-light still site/start/shots/capture.json lists" in got["site:stills"]["detail"], got["site:stills"]
    capture_record(p, "site/start/index.html")
    (p / "site" / "start" / "shots" / "capture.json").write_text("{not json", encoding="utf-8")
    got = run_check(p)[1]
    assert got["site:stills"]["status"] == "skipped" and "site/start/shots/capture.json is unusable" in got["site:stills"]["detail"], got["site:stills"]
    capture_record(p, "site/start/index.html")
    assert [run_check(p)[1][x]["status"] for x in SITE_ROWS] == ["pass", "pass", "pass"]


def test_check_fails_a_failing_page_check_of_a_site_page(tmp_path):
    p = checked(tmp_path)
    page_check_report(p, "site/pricing/index.html", "fail")
    r, got = run_check(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert got["site:pages"]["status"] == "fail", got
    assert got["site:pages"]["detail"].startswith("pricing: ") and "is failing (page:load:390-light)" in got["site:pages"]["detail"] and "start" not in got["site:pages"]["detail"], got["site:pages"]
    assert got["site:record"]["status"] == "pass" and got["site:stills"]["status"] == "pass", "the page is as approved, with current stills: only its brand-rule check fails"
    # a page that fails and a page that is not verified: the failure leads, the other is named after it
    (p / "assets" / "_checks" / f"{report_tool('site/start/index.html')}.json").unlink()
    got = run_check(p)[1]
    assert got["site:pages"]["status"] == "fail" and got["site:pages"]["detail"].startswith("pricing: ") and "; not verified: start: no page-check/" in got["site:pages"]["detail"], got["site:pages"]
    page_check_report(p, "site/pricing/index.html", "pass")
    page_check_report(p, "site/start/index.html", "pass")
    assert run_check(p)[1]["site:pages"]["status"] == "pass"


def test_check_fails_a_rule_choice_without_a_source(tmp_path):
    p = checked(tmp_path)
    assert run_check(p)[1]["site:record"]["status"] == "pass"
    record = p / "site" / "site.json"
    mutate_json(record, lambda d: d["choices"][0].update(source=""))                         # c1 is a rule: it says where it was decided
    r, got = run_check(p)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert got["site:record"]["status"] == "fail" and "c1: a rule says where it was decided" in got["site:record"]["detail"], got["site:record"]
    assert got["site:pages"]["status"] == "pass" and got["site:stills"]["status"] == "pass", "the pages are untouched: the record is what fails"
    mutate_json(record, lambda d: d["choices"][0].update(source="DECISIONS.md", tag="example"))   # an example needs no source
    assert run_check(p)[1]["site:record"]["status"] == "pass"
    mutate_json(record, lambda d: d["pages"][0].update(layout="no-such-layout"))
    got = run_check(p)[1]
    assert got["site:record"]["status"] == "fail" and "is no id of page-layouts.json" in got["site:record"]["detail"], got["site:record"]


def test_check_says_not_verified_when_a_site_still_is_stale(tmp_path):
    p = checked(tmp_path)
    assert run_check(p)[1]["site:stills"]["status"] == "pass"
    mutate(p / "assets" / "tokens" / "tokens.css", "#16191d", "#16191e")                     # a file the stills were taken from
    r, got = run_check(p)
    for pid in PAGES:
        assert f"{pid}: site/{pid}/shots/capture.json is stale (assets/tokens/tokens.css changed); run `brand-creator capture site/{pid}/index.html`" in got["site:stills"]["detail"], got["site:stills"]
    assert got["site:stills"]["status"] == "skipped" and got["site:stills"]["detail"].startswith("not verified: "), got["site:stills"]
    assert got["site:pages"]["status"] == "skipped", "the page-check reports were made from the same stylesheet"
    assert got["site:record"]["status"] == "pass", "the approved pages themselves did not change"
    # a capture that does not list the page among its inputs could never go stale
    settle_site(p)
    capture = p / "site" / "start" / "shots" / "capture.json"
    mutate_json(capture, lambda d: d.update(inputs=[i for i in d["inputs"] if i["path"] != "site/start/index.html"]))
    got = run_check(p)[1]
    assert got["site:stills"]["status"] == "skipped" and "it does not list site/start/index.html among the files it was made from" in got["site:stills"]["detail"], got["site:stills"]


def test_check_has_no_site_rows_without_g4p_or_site(tmp_path):
    p = make_project(tmp_path)
    r, got = run_check(p)
    assert got == {}, got
    (p / "site").mkdir()                                                                     # a folder named site that holds no record is the owner's own
    (p / "site" / "index.html").write_text(PAGE, encoding="utf-8")
    r, got = run_check(p)
    assert got == {}, got
    # a project in the middle of the site round: the pages board exists, nothing is approved yet
    (tmp_path / "other").mkdir()
    mid = pages_project(tmp_path / "other")
    assert lint3(mid).returncode == 0
    assert run_check(mid)[1] == {}
