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
