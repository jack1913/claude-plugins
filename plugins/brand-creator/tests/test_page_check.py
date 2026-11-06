"""page-check: the command, its three kinds of target, the measuring path (render.mjs page-measure) and the report.

The Chromium tests carry requires_setup and requires_node; the rest run without a browser (a usage error, the missing tokens or node and the
URL rule are all decided before one starts). The projects of the exit-2 and exit-3 tests are plain `new` projects: those refusals come first."""
import base64
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from helpers import ROOT, TEST_FONT, bc, install_fixture, make_project, mutate, mutate_json, path_without, report

sys.path.insert(0, str(ROOT / "scripts" / "pagelib"))
import pagecheck  # noqa: E402
import qa_rules  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import CliError, Report, forbidden_terms, stale_inputs  # noqa: E402

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Acme</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="../assets/tokens/tokens.css">
<style>
  body { margin: 0; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); }
  a { color: var(--color-accent); }
</style>
</head>
<body>
<main>
  <h1>Acme hand tools</h1>
  <p>Every tool has a published spare-parts list.</p>
  <p><a href="#parts">Spare parts</a></p>
</main>
</body>
</html>
"""
SITE_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Built site</title>
<style>
  body { background: #f9f7ee; color: #0d1b2d; font-family: ui-sans-serif, system-ui, sans-serif; }
  @media (prefers-color-scheme: dark) { body { background: #0e141d; color: #f0eee7; } }
</style></head>
<body><img src="img/dot.svg" width="32" height="32" alt=""><p>A built page, nothing else.</p></body></html>
"""   # the Acme colours and font stack written out: a built site elsewhere does not link the project's tokens.css
DOT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" width="8" height="8"><circle cx="4" cy="4" r="3" fill="#007d71"/></svg>\n'


def write_page(p: Path, text: str = PAGE, name: str = "pages/index.html") -> Path:
    f = p / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


def page_reports(p: Path) -> list[Path]:
    return sorted((p / "assets" / "_checks" / "page-check").glob("*.json")) if (p / "assets" / "_checks" / "page-check").is_dir() else []


def row(rep: dict, rid: str) -> dict:
    return next(r for r in rep["results"] if r["id"] == rid)


def build_site(folder: Path, page: str = SITE_PAGE) -> Path:
    (folder / "img").mkdir(parents=True)
    (folder / "index.html").write_text(page, encoding="utf-8")
    (folder / "img" / "dot.svg").write_text(DOT, encoding="utf-8")
    return folder


def walk_hashes(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


def tree(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


@contextmanager
def serve(folder: Path, redirects: dict | None = None, log: list | None = None, upgrades: list | None = None):
    """The folder served on 127.0.0.1 at a free port, for the length of the block. -> the base URL.
    `redirects` maps a path to where it answers 302 (a URL, or a function returning one, or None to serve the file); `log` collects the path of every GET;
    `upgrades`, when given, makes the server accept a WebSocket (like a dev server's hot reload) and collects the path of each one."""
    redirects = redirects or {}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(folder), **k)

        def log_message(self, *a, **k):
            pass

        def do_GET(self):
            if log is not None:
                log.append(self.path)
            if upgrades is not None and self.headers.get("Upgrade", "").lower() == "websocket":
                upgrades.append(self.path)
                accept = base64.b64encode(hashlib.sha1((self.headers["Sec-WebSocket-Key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                self.send_response(101, "Switching Protocols")
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept)
                self.end_headers()
                while self.rfile.read(1):   # the socket stays open until the browser closes it
                    pass
                return
            to = redirects.get(self.path)
            to = to() if callable(to) else to
            if not to:
                return super().do_GET()
            self.send_response(302)
            self.send_header("Location", to)
            self.send_header("Content-Length", "0")
            self.end_headers()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


LOOPBACK_YES = ["http://localhost:8000/x", "http://127.0.0.1/", "http://[::1]:3000/", "https://localhost/a?b=c", "http://LOCALHOST/", "HTTP://LOCALHOST:8080/x",
                "http://localhost", "http://localhost?q=1", "http://localhost:/", "http://[::1]/"]
LOOPBACK_NO = ["https://example.com/", "file:///x", "http://localhost.evil.test/", "http://evil.test/localhost", "http://localhost@evil/",
               "http://user:secret@localhost/", "http://evil.test\\@localhost/", "http://127.0.0.2/", "http://localhost:99999999/", "ftp://localhost/",
               " http://localhost/", "http://localhost/\n", "localhost:8000", "", "//localhost/x",
               # a host a parser turns into this machine is not written as one of the three: refused by both functions
               "http://127.1/", "http://0x7f000001/", "http://2130706433/", "http://[0:0:0:0:0:0:0:1]/", "http://%6cocalhost/", "http://127.0.0.1./", "http://localhost./",
               "http://[::ffff:127.0.0.1]/", "http://localhost:3000:80/", "http:localhost/x", "http:/localhost/x", "http:///localhost/x"]


# ---------------------------------------------------------------- no browser


def test_is_loopback_url_accepts_this_machine_only():
    for url in LOOPBACK_YES:
        assert pagecheck.is_loopback_url(url), url
    for url in LOOPBACK_NO:
        assert not pagecheck.is_loopback_url(url), url


@pytest.mark.requires_node
def test_the_node_twin_of_the_loopback_rule_answers_the_same_as_the_python_one():
    code = (f"import {{ isLoopbackUrl }} from {json.dumps((ROOT / 'scripts/lib/_common.mjs').as_uri())}; "
            "console.log(JSON.stringify(JSON.parse(process.argv[1]).map((u) => isLoopbackUrl(u))));")
    urls = LOOPBACK_YES + LOOPBACK_NO
    r = subprocess.run(["node", "--input-type=module", "-e", code, json.dumps(urls)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [pagecheck.is_loopback_url(u) for u in urls] == [True] * len(LOOPBACK_YES) + [False] * len(LOOPBACK_NO)


def test_the_report_is_named_after_the_page_and_the_hash_follows_the_ident():
    a = pagecheck.report_tool("pages/index.html")
    assert a == "page-check/index-" + hashlib.sha256(b"pages/index.html").hexdigest()[:6]
    assert pagecheck.report_tool("site/index.html") != a   # same stem, another page: another report
    f = pagecheck.report_tool("from:/srv/built/About us.html")
    assert f.startswith("page-check/about-us-") and f.endswith(hashlib.sha256(b"from:/srv/built/About us.html").hexdigest()[:6])
    assert pagecheck.report_tool("url:http://localhost:3000/docs/start.html") == "page-check/start-" + hashlib.sha256(b"url:http://localhost:3000/docs/start.html").hexdigest()[:6]
    assert pagecheck.report_tool("url:http://localhost:3000/").startswith("page-check/page-")
    assert pagecheck.report_tool("pages/.html").startswith("page-check/")


def test_the_page_block_of_qa_rules_has_proposals_and_checks_what_it_is_given(tmp_path):
    p = make_project(tmp_path)
    rules, source = qa_rules.load(p)
    assert source.startswith("proposals") and rules["page"] == {"widths": [360, 390, 768, 1024, 1440, 1920], "display_min_px": 20, "clear_space": 0.25, "rules": []}
    (p / "qa").mkdir()
    (p / "qa" / "rules.json").write_text(json.dumps({"schema": 1, "page": {"widths": [320 + 70, 1280], "clear_space": 0.5}}), encoding="utf-8")
    rules, source = qa_rules.load(p)
    assert source == "qa/rules.json" and rules["page"]["widths"] == [390, 1280] and rules["page"]["clear_space"] == 0.5 and rules["page"]["display_min_px"] == 20


@pytest.mark.parametrize("block", [{"widths": [100]}, {"widths": [390, 5000]}, {"widths": []}, {"widths": [390, 390]}, {"widths": "390"}, {"widths": [390.5]},
                                   {"widths": [True]}, {"nope": 1}, {"display_min_px": 0}, {"clear_space": "wide"}, {"rules": {}}])
def test_a_bad_page_block_in_qa_rules_is_a_usage_error_and_writes_no_report(tmp_path, block):
    p = make_project(tmp_path)
    write_page(p)
    (p / "qa").mkdir()
    (p / "qa" / "rules.json").write_text(json.dumps({"schema": 1, "page": block}), encoding="utf-8")
    r = bc("page-check", "pages/index.html", project=p)
    assert r.returncode == 2 and "qa/rules.json" in r.stderr and "page" in r.stderr, r.stderr
    assert page_reports(p) == []


def test_a_run_that_measured_no_view_is_not_verified_and_never_a_pass(tmp_path):
    p = make_project(tmp_path)
    ctx = pagecheck.Ctx(p, pagecheck.Target("project", "pages/index.html", page="pages/index.html"), [390], ["light"], qa_rules.load(p)[0], {})
    rep = Report("page-check/index-000000", p)
    pagecheck.load_rows(rep, {"schema": 1, "views": []}, ctx)
    assert [(r["id"], r["status"]) for r in rep.results] == [("page:load", "skipped")] and rep.status == "not-verified" and rep.exit_code() == 3
    rep = Report("page-check/index-000000", p)
    pagecheck.load_rows(rep, {"schema": 1, "views": [{"width": 390, "scheme": "light", "error": "loading http://x/: timed out"}]}, ctx)
    assert [(r["id"], r["status"]) for r in rep.results] == [("page:load:390-light", "fail")] and "timed out" in rep.results[0]["detail"] and rep.exit_code() == 1


def test_page_check_refuses_a_remote_url_two_targets_and_a_missing_page(tmp_path):
    p = make_project(tmp_path)
    write_page(p)
    site = build_site(tmp_path / "site")
    cases = [
        (["--url", "https://example.com/"], "this machine"),
        (["--url", "http://localhost.evil.test/"], "this machine"),
        (["--url", "file:///etc/hosts"], "this machine"),
        ([], "no target"),
        (["pages/index.html", "--url", "http://localhost:1/"], "two targets"),
        (["--from", str(site), "index.html", "--url", "http://localhost:1/"], "two targets"),
        (["pages/missing.html"], "page not found"),
        (["--from", str(site)], "needs the page"),
        (["--from", str(site), "missing.html"], "page not found"),
        (["--from", str(site), "../outside.html"], "page not found"),
        (["--from", str(tmp_path / "nowhere"), "index.html"], "not a folder"),
        (["pages/index.html", "--widths", "100"], "--widths"),
        (["pages/index.html", "--widths", "390,5000"], "--widths"),
        (["pages/index.html", "--widths", "390,390"], "--widths"),
        (["pages/index.html", "--widths", "39o"], "--widths"),
        (["pages/index.html", "--schemes", "sepia"], "--schemes"),
        (["pages/index.html", "--schemes", "light,light"], "--schemes"),
        (["pages/index.html", "--widths", ""], "--widths"),   # an empty value is a usage error, never the default
        (["pages/index.html", "--schemes", ""], "--schemes"),
    ]
    for args, why in cases:
        r = bc("page-check", *args, project=p)
        assert r.returncode == 2 and why in r.stderr, (args, r.returncode, r.stderr)
    outside = tmp_path / "elsewhere.html"
    outside.write_text(PAGE, encoding="utf-8")
    r = bc("page-check", str(outside), project=p)
    assert r.returncode == 2 and "outside the project" in r.stderr and "--from" in r.stderr
    assert page_reports(p) == [] and not (p / "assets" / "_checks").exists()


def test_a_site_folder_with_too_many_files_or_too_many_bytes_is_refused_before_anything_is_copied(tmp_path):
    p = make_project(tmp_path)
    many = build_site(tmp_path / "many")
    for i in range(pagecheck.FROM_MAX_FILES):
        (many / "img" / f"f{i}.txt").write_bytes(b"")
    heavy = build_site(tmp_path / "heavy")
    with open(heavy / "img" / "big.bin", "wb") as f:
        f.truncate(pagecheck.FROM_MAX_BYTES + 1)
    skipped = build_site(tmp_path / "skipped")   # .git, node_modules and symlinks are not counted, so these pass the limits (and are not copied)
    (skipped / "node_modules").mkdir()
    for i in range(pagecheck.FROM_MAX_FILES + 1):
        (skipped / "node_modules" / f"f{i}.txt").write_bytes(b"")
    for folder in (many, heavy):
        r = bc("page-check", "--from", str(folder), "index.html", project=p)
        assert r.returncode == 2 and "5000 files or 200 MB" in r.stderr, (folder.name, r.stderr)
    r = bc("page-check", "--from", str(skipped), "index.html", project=p)
    assert r.returncode == 3 and "brand-creator tokens" in r.stderr, r.stderr   # past the limits; stops at the missing tokens
    assert page_reports(p) == []


def test_page_check_needs_built_tokens(tmp_path):
    p = make_project(tmp_path)
    write_page(p)
    r = bc("page-check", "pages/index.html", project=p)
    assert r.returncode == 3 and "assets/tokens/tokens.json" in r.stderr and "brand-creator tokens" in r.stderr, r.stderr
    assert page_reports(p) == []


@pytest.mark.requires_node
def test_render_page_measure_refuses_what_page_check_would_never_send(tmp_path):
    """render.mjs is the second gate: a hand-written request is held to the same rules (exit 2, before a browser is started)."""
    p = make_project(tmp_path)
    write_page(p)
    other = tmp_path / "other"
    other.mkdir()
    (other / "index.html").write_text(SITE_PAGE, encoding="utf-8")
    data = tmp_path / "data"
    (data / "scratch").mkdir(parents=True)
    good = {"schema": 1, "root": str(p), "page": "pages/index.html", "url": None, "widths": [390], "schemes": ["light"], "selectors": [], "dsf": 1}
    cases = [
        ({"root": None, "page": None, "url": "https://example.com/"}, "this machine"),
        ({"root": None, "page": None, "url": "http://localhost.evil.test/"}, "this machine"),
        ({"root": None, "page": None, "url": "file:///etc/hosts"}, "this machine"),
        ({"url": "http://localhost:1/"}, "either root with page, or url"),
        ({"root": None, "page": None, "url": None}, "either root with page, or url"),
        ({"root": str(other), "page": "index.html"}, "project or a folder inside"),
        ({"root": str(data / "scratch")}, "project or a folder inside"),
        ({"root": str(p), "page": "../escape.html"}, "page not found"),
        ({"root": str(p), "page": "pages"}, "page not found"),
        ({"root": str(p), "page": "pages/missing.html"}, "page not found"),
        ({"widths": [100]}, "widths"),
        ({"widths": [390, 390]}, "widths"),
        ({"schemes": ["sepia"]}, "schemes"),
        ({"schemes": []}, "schemes"),
        ({"dsf": 4}, "dsf"),
        ({"selectors": [1]}, "selectors"),
        ({"schema": 2}, "schema"),
    ]
    for i, (change, why) in enumerate(cases):
        req = tmp_path / f"req{i}.json"
        req.write_text(json.dumps({**good, **change}), encoding="utf-8")
        r = subprocess.run(["node", str(ROOT / "scripts/render.mjs"), "page-measure", "--request", str(req), "--out", str(tmp_path / "out.json"), "--project", str(p)],
                           capture_output=True, text=True, env={**os.environ, "BRAND_CREATOR_DATA": str(data)})
        assert r.returncode == 2 and why in r.stderr, (change, r.returncode, r.stderr)
    assert not (tmp_path / "out.json").exists()
    r = subprocess.run(["node", str(ROOT / "scripts/render.mjs"), "page-measure", "--request", str(tmp_path / "req0.json"), "--out", str(p / "measures.json"), "--project", str(p)],
                       capture_output=True, text=True, env={**os.environ, "BRAND_CREATOR_DATA": str(data)})
    assert r.returncode == 2 and "outside the project" in r.stderr and not (p / "measures.json").exists()


@pytest.mark.requires_setup
def test_page_check_without_node_exits_3_and_names_the_fix(acme, tmp_path):
    write_page(acme)
    r = bc("page-check", "pages/index.html", project=acme, env={"PATH": path_without(tmp_path, "node")})
    assert r.returncode == 3 and "node not found" in r.stderr and "Install Node" in r.stderr, r.stdout + r.stderr
    assert page_reports(acme) == []


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_page_check_without_a_set_up_data_folder_exits_3_and_names_the_fix(acme, tmp_path):
    write_page(acme)
    empty = tmp_path / "empty-data"
    empty.mkdir()
    r = bc("page-check", "pages/index.html", project=acme, data=empty)
    assert r.returncode == 3 and "setup has not been run" in r.stderr and "/brand-creator:setup" in r.stderr, r.stdout + r.stderr
    (rep_file,) = page_reports(acme)   # a run that stops after its report was made records the failure, never leaves a pass standing
    assert json.loads(rep_file.read_text(encoding="utf-8"))["status"] == "fail"


# ---------------------------------------------------------------- with a browser


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_clean_page_passes_and_its_report_is_named_after_the_page(acme):
    write_page(acme)
    r = bc("page-check", "pages/index.html", "--widths", "390,1440", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    tool = pagecheck.report_tool("pages/index.html")
    assert tool == "page-check/index-" + hashlib.sha256(b"pages/index.html").hexdigest()[:6]
    assert page_reports(acme) == [acme / "assets" / "_checks" / f"{tool}.json"]
    rep = report(acme, tool)
    assert rep["tool"] == tool and rep["status"] == "pass"
    assert rep["target"] == {"kind": "project", "page": "pages/index.html", "from": None, "url": None}
    assert rep["widths"] == [390, 1440] and rep["schemes"] == ["light", "dark"]
    ids = [x["id"] for x in rep["results"]]
    assert ids[:5] == ["page:target", "page:load:390-light", "page:load:390-dark", "page:load:1440-light", "page:load:1440-dark"]
    assert ids[5:9] == ["page:colours:light", "page:colours:dark", "page:pairs:light", "page:pairs:dark"]
    assert all(x["status"] == "pass" for x in rep["results"][1:] if x["id"] not in ("page:mark-file", "page:display-size", "page:words")) and row(rep, "page:target")["status"] == "info"
    assert row(rep, "page:mark-file")["status"] == "info" and "no brand mark is shown" in row(rep, "page:mark-file")["detail"]   # a page without a mark says so
    assert row(rep, "page:display-size")["status"] == "info" and "no font.display token" in row(rep, "page:display-size")["detail"]   # Acme has no display face
    assert row(rep, "page:words")["status"] == "info" and "no forbidden words are listed" in row(rep, "page:words")["detail"]   # Acme lists none: nothing was looked for, which is not a pass
    paths = {i["path"] for i in rep["inputs"]}
    assert {"assets/tokens/tokens.json", "assets/tokens/tokens.css", "pages/index.html", "FACTS.md", "BRAND-STATE.md", "qa/rules.json"} <= paths
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    assert measures["schema"] == 1 and measures["chromium"] and len(measures["views"]) == 4
    assert measures["views"][0]["viewport"] == {"width": 390, "height": 844} and measures["views"][2]["viewport"] == {"width": 1440, "height": 900}
    assert not Path(rep["measures"]).resolve().is_relative_to(acme.resolve())   # the measurements are written outside the project
    assert stale_inputs(acme, rep) == []


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_that_asks_the_network_fails_its_load_row(acme):
    page = write_page(acme)
    mutate(page, "</main>", '<img src="https://example.invalid/pixel.png" alt="">\n</main>')
    r = bc("page-check", "pages/index.html", "--widths", "390", "--schemes", "light", project=acme)
    assert r.returncode == 1, r.stdout + r.stderr
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    assert rep["status"] == "fail"
    bad = row(rep, "page:load:390-light")
    assert bad["status"] == "fail" and "another origin" in bad["detail"] and "https://example.invalid/pixel.png" in bad["non_local_requests"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_with_a_script_error_or_a_missing_file_fails_its_load_row(acme):
    page = write_page(acme)
    mutate(page, "</main>", '<script>throw new Error("boom")</script><link rel="stylesheet" href="missing.css">\n</main>')
    r = bc("page-check", "pages/index.html", "--widths", "390", "--schemes", "dark", project=acme)
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(report(acme, pagecheck.report_tool("pages/index.html")), "page:load:390-dark")
    assert bad["status"] == "fail" and "boom" in bad["detail"] and "404 /pages/missing.css" in bad["failed_local_requests"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_report_goes_stale_when_a_file_the_page_loaded_changes(acme):
    write_page(acme)
    assert bc("page-check", "pages/index.html", "--widths", "390", "--schemes", "light", project=acme).returncode == 0
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    assert stale_inputs(acme, rep) == []
    mutate(acme / "assets" / "tokens" / "tokens.css", "--color-bg:", "--color-bg: /* changed */")
    assert stale_inputs(acme, rep) == ["assets/tokens/tokens.css changed"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_widths_come_from_qa_rules_json_unless_widths_overrides_them(acme):
    write_page(acme)
    mutate_json(acme / "qa" / "rules.json", lambda d: d.__setitem__("page", {"widths": [420, 800]}))
    assert bc("page-check", "pages/index.html", "--schemes", "light", project=acme).returncode == 0
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    assert rep["widths"] == [420, 800] and [x["id"] for x in rep["results"] if x["id"].startswith("page:load:")] == ["page:load:420-light", "page:load:800-light"]
    assert "thresholds from qa/rules.json" in row(rep, "page:target")["detail"]
    assert bc("page-check", "pages/index.html", "--schemes", "light", "--widths", "500", project=acme).returncode == 0
    assert report(acme, pagecheck.report_tool("pages/index.html"))["widths"] == [500]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_from_checks_a_copy_and_never_writes_where_the_site_is(acme, tmp_path):
    site = build_site(tmp_path / "built site")
    (site / ".git").mkdir()
    (site / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (site / "node_modules").mkdir()
    (site / "node_modules" / "dep.js").write_text("export default 1\n", encoding="utf-8")
    os.symlink(tmp_path, site / "link-out")
    before_site, before_project = walk_hashes(site), tree(acme)
    r = bc("page-check", "--from", str(site), "index.html", "--widths", "390", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    assert walk_hashes(site) == before_site and (site / "link-out").is_symlink()   # the source was only read
    tool = pagecheck.report_tool(f"from:{site.resolve().as_posix()}/index.html")
    assert tree(acme) - before_project == {f"assets/_checks/{tool}.json"}          # the project gained the report and nothing else
    rep = report(acme, tool)
    assert rep["target"] == {"kind": "from", "page": "index.html", "from": str(site.resolve()), "url": None}
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.json", "assets/tokens/tokens.css", "qa/rules.json", "FACTS.md", "BRAND-STATE.md", "brief/BRIEF.md"} | set(
        pagecheck.logo_files(acme, qa_rules.load(acme)[0]))   # a site elsewhere is not a project file (the logo files and the brief, where the forbidden words are read, are: a mark is judged against them);
    # tokens.css is read for the colours the browser renders for the tokens
    h = tool.rsplit("-", 1)[1]
    copies = list((Path(os.environ["BRAND_CREATOR_DATA"]) / "scratch").glob(f"*/page-check/{h}/1"))
    assert len(copies) == 1 and tree(copies[0]) == {"index.html", "img/dot.svg"}   # .git, node_modules and the symlink were left out
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    dot = measures["views"][0]["resources"]["/img/dot.svg"]
    assert dot == {"sha256": hashlib.sha256(DOT.encode()).hexdigest(), "content_type": "image/svg+xml"}   # an SVG is hashed byte for byte
    # a second run makes a second copy, and the site is still untouched
    assert bc("page-check", "--from", str(site), "index.html", "--widths", "390", project=acme).returncode == 0
    assert len(list((Path(os.environ["BRAND_CREATOR_DATA"]) / "scratch").glob(f"*/page-check/{h}/*"))) == 2 and walk_hashes(site) == before_site


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_built_site_that_asks_the_network_fails_but_a_page_on_this_machine_only_warns(acme, tmp_path):
    site = build_site(tmp_path / "site", SITE_PAGE.replace("</body>", '<img src="https://example.invalid/pixel.png" alt=""></body>'))
    r = bc("page-check", "--from", str(site), "index.html", "--widths", "390", "--schemes", "light", project=acme)
    assert r.returncode == 1, r.stdout + r.stderr
    from_tool = pagecheck.report_tool(f"from:{site.resolve().as_posix()}/index.html")
    assert row(report(acme, from_tool), "page:load:390-light")["status"] == "fail"
    with serve(site) as base:
        r = bc("page-check", "--url", f"{base}/index.html", "--widths", "390", "--schemes", "light", project=acme)
        assert r.returncode == 0, r.stdout + r.stderr
        rep = report(acme, pagecheck.report_tool(f"url:{base}/index.html"))
        assert rep["target"] == {"kind": "url", "page": None, "from": None, "url": f"{base}/index.html"} and rep["status"] == "pass"
        warned = row(rep, "page:load:390-light")
        assert warned["status"] == "warn" and "aborted: page-check runs offline" in warned["detail"] and warned["non_local_requests"] == ["https://example.invalid/pixel.png"]
        clean = build_site(tmp_path / "clean")
    with serve(clean) as base:
        assert bc("page-check", "--url", f"{base}/index.html", "--widths", "390", "--schemes", "light", project=acme).returncode == 0
        assert row(report(acme, pagecheck.report_tool(f"url:{base}/index.html")), "page:load:390-light")["status"] == "pass"
        gone = bc("page-check", "--url", f"{base}/gone.html", "--widths", "390", "--schemes", "light", project=acme)
        assert gone.returncode == 1 and "404 /gone.html" in gone.stdout


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_redirect_to_another_origin_is_stopped_and_the_other_server_never_hears_of_it(acme, tmp_path):
    site = build_site(tmp_path / "site")
    elsewhere = build_site(tmp_path / "elsewhere")
    heard: list[str] = []
    narrow = ("--widths", "390", "--schemes", "light")
    with serve(elsewhere, log=heard) as other, serve(site, redirects={
            "/login": f"{other}/index.html",                                     # a dev server that sends the browser to a login page elsewhere
            "/hop1": "/hop2", "/hop2": f"{other}/index.html",                    # a chain that starts at home
            "/r.svg": f"{other}/img/dot.svg"}) as base:                          # an image that lives elsewhere
        def load_row(path: str) -> dict:
            return row(report(acme, pagecheck.report_tool(f"url:{base}{path}")), "page:load:390-light")

        assert bc("page-check", "--url", f"{base}/index.html", *narrow, project=acme).returncode == 0   # the control: the clean page passes
        assert load_row("/index.html")["status"] == "pass" and heard == []
        for path in ("/login", "/hop1"):   # the page that would be measured is the other origin's: the view cannot be rendered
            r = bc("page-check", "--url", f"{base}{path}", *narrow, project=acme)
            bad = load_row(path)
            assert r.returncode == 1 and bad["status"] == "fail", (path, r.stdout + r.stderr)
            assert "could not render" in bad["detail"] and f"{other}/index.html" in bad["detail"], bad["detail"]
        assert heard == []
        mutate(site / "index.html", "</body>", '<img src="/r.svg" alt=""></body>')   # the deliberate break: a file the page loads is sent elsewhere
        r = bc("page-check", "--url", f"{base}/index.html", *narrow, project=acme)
        warned = load_row("/index.html")
        assert r.returncode == 0 and warned["status"] == "warn" and warned["non_local_requests"] == [f"{other}/img/dot.svg"], r.stdout + r.stderr
        assert heard == []
        mutate(site / "index.html", "<body>", f'<head><meta http-equiv="refresh" content="0;url={other}/index.html"></head><body>')   # a page that sends itself elsewhere
        r = bc("page-check", "--url", f"{base}/index.html", *narrow, project=acme)
        assert r.returncode == 1 and load_row("/index.html")["status"] == "fail" and heard == [], r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_redirect_that_stays_on_this_machine_is_followed_and_a_loop_or_a_changed_hop_fails(acme, tmp_path):
    site = build_site(tmp_path / "site")
    (site / "moved.html").write_text(SITE_PAGE.replace("img/dot.svg", "moved.svg"), encoding="utf-8")
    (site / "y.html").write_text(SITE_PAGE, encoding="utf-8")
    elsewhere = build_site(tmp_path / "elsewhere")
    heard: list[str] = []
    asked: list[int] = []

    def second_time_elsewhere():   # a hop that was fine when it was walked and sends the browser away when the browser follows it
        asked.append(1)
        return f"{other}/index.html" if len(asked) > 1 else None

    narrow = ("--widths", "390", "--schemes", "light")
    with serve(elsewhere, log=heard) as other, serve(site, redirects={"/old.html": "/index.html", "/moved.svg": "/img/dot.svg", "/loop": "/loop",
                                                                     "/start": "/y.html", "/y.html": second_time_elsewhere}) as base:
        def load(path: str):
            r = bc("page-check", "--url", f"{base}{path}", *narrow, project=acme)
            rep = report(acme, pagecheck.report_tool(f"url:{base}{path}"))
            return r, row(rep, "page:load:390-light"), rep

        r, ok, rep = load("/old.html")   # a page behind a redirect of its own
        assert r.returncode == 0 and ok["status"] == "pass", r.stdout + r.stderr
        assert json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"][0]["resources"]["/img/dot.svg"]["sha256"] == hashlib.sha256(DOT.encode()).hexdigest()
        r, ok, rep = load("/moved.html")   # an image behind a redirect of its own is loaded and hashed under the path it ended at
        assert r.returncode == 0 and ok["status"] == "pass", r.stdout + r.stderr
        assert json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"][0]["resources"]["/img/dot.svg"]["sha256"] == hashlib.sha256(DOT.encode()).hexdigest()
        r, bad, _ = load("/loop")   # a loop is stopped, not followed until the browser gives up
        assert r.returncode == 1 and bad["status"] == "fail" and "could not render" in bad["detail"]
        assert heard == []
        r, bad, _ = load("/start")   # the safety net: the view fails, and says the redirect was not stopped
        assert r.returncode == 1 and bad["status"] == "fail" and "not stopped" in bad["detail"], r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_on_this_machine_may_open_a_websocket_to_its_own_origin(acme, tmp_path):
    # a dev server's hot reload: the page asks its own server for a WebSocket. The browser must not block it (a document the measuring script answers itself
    # is not taken for one of this machine without the permission render.mjs grants), or every view of such a page would fail on a console error
    site = build_site(tmp_path / "site", SITE_PAGE.replace("</body>", "<script>new WebSocket('ws://' + location.host + '/hmr')</script></body>"))
    hmr: list[str] = []
    with serve(site, upgrades=hmr) as base:
        r = bc("page-check", "--url", f"{base}/index.html", "--widths", "390", "--schemes", "light", project=acme)
        assert r.returncode == 0, r.stdout + r.stderr
        ok = row(report(acme, pagecheck.report_tool(f"url:{base}/index.html")), "page:load:390-light")
        assert ok["status"] == "pass", ok
        assert hmr == ["/hmr"]   # the server was asked, once


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_websocket_to_another_origin_is_stopped_and_the_other_server_never_hears_of_it(acme, tmp_path):
    # a route does not see a WebSocket: the page's own are stopped one by one (a worker's are not, see CONTRACT)
    elsewhere = build_site(tmp_path / "elsewhere")
    heard: list[str] = []
    upgraded: list[str] = []
    hmr: list[str] = []
    narrow = ("--widths", "390", "--schemes", "light")
    with serve(elsewhere, log=heard, upgrades=upgraded) as other:
        socket_page = SITE_PAGE.replace("</body>", f"<script>new WebSocket('ws://' + location.host + '/hmr'); new WebSocket('{other.replace('http', 'ws')}/ws')</script></body>")
        site = build_site(tmp_path / "site", socket_page)
        with serve(site, upgrades=hmr) as base:   # on this machine: a warning, and the page's own socket is still let through
            r = bc("page-check", "--url", f"{base}/index.html", *narrow, project=acme)
            warned = row(report(acme, pagecheck.report_tool(f"url:{base}/index.html")), "page:load:390-light")
            assert r.returncode == 0 and warned["status"] == "warn", r.stdout + r.stderr
            assert warned["non_local_requests"] == [f"{other.replace('http', 'ws')}/ws"] and "aborted: page-check runs offline" in warned["detail"], warned
            assert hmr == ["/hmr"]
        assert heard == [] and upgraded == []
        # a project page and a built site: the same socket fails the view, as any other request to another origin does
        r = bc("page-check", "--from", str(site), "index.html", *narrow, project=acme)
        bad = row(report(acme, pagecheck.report_tool(f"from:{site.resolve().as_posix()}/index.html")), "page:load:390-light")
        assert r.returncode == 1 and bad["status"] == "fail" and "another origin" in bad["detail"] and f"{other.replace('http', 'ws')}/ws" in bad["non_local_requests"], r.stdout + r.stderr
        assert heard == [] and upgraded == []


# ---------------------------------------------------------------- colours and pairs


def check_page(p: Path, *args: str, page: str = "pages/index.html") -> tuple[subprocess.CompletedProcess, dict]:
    """page-check at one width (390) in both schemes, and its report."""
    r = bc("page-check", page, "--widths", "390", *args, project=p)
    return r, report(p, pagecheck.report_tool(page))


def synthetic_ctx(tmp_path: Path, tokens: dict, schemes=("light",)) -> pagecheck.Ctx:
    return pagecheck.Ctx(tmp_path, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [390], list(schemes), qa_rules.DEFAULTS, tokens)


def view(scheme: str = "light", **facts) -> dict:
    return {"width": 390, "scheme": scheme, "viewport": {"width": 390, "height": 844}, **facts}


TOKENS = {"modes": {"light": {"color.bg": {"hex": "#f9f7ee", "alpha": 1}, "color.text": {"hex": "#0d1b2d", "alpha": 1}, "color.veil": {"hex": "#0d1b2d", "alpha": 0.5}}},
          "pairs": [{"fg": "color.text", "bg": "color.bg", "kind": "ui-text", "min": 4.5, "modes": {"light": {"fg_hex": "#0d1b2d", "bg_hex": "#f9f7ee"}}}]}


def test_a_colour_a_unit_off_a_role_is_that_role_and_a_see_through_one_needs_a_see_through_role(tmp_path):
    """No browser: the matching rule of page:colours on constructed measurements. A hand-typed copy of a token a unit or two off in a channel is the same colour; four
    off is not. A see-through colour matches a see-through role of the same colour and alpha only."""
    colour = lambda hex_, alpha=1, sel="body > p": {"sel": sel, "prop": "color", "hex": hex_, "alpha": alpha, "count": 1, "also": []}
    ok = [colour("#f9f7ef"), colour("#0d1b2d"), colour("#0d1b2d", 0.5), colour("#0d1b2d", 0.505)]
    bad = [colour("#f9f7f2", sel="body > a"), colour("#0d1b2d", 0.6, sel="body > b"), colour("#f9f7ee", 0.5, sel="body > c")]
    ctx = synthetic_ctx(tmp_path, TOKENS)
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.colour_rows(rep, {"views": [view(colours=ok)]}, ctx)
    assert [(r["id"], r["status"]) for r in rep.results] == [("page:colours:light", "pass")]
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.colour_rows(rep, {"views": [view(colours=ok + bad)]}, ctx)
    (got,) = rep.results
    assert got["status"] == "fail" and [o["selector"] for o in got["offenders"]] == ["body > a", "body > b", "body > c"]
    assert got["offenders"][0]["nearest_role"] == "color.bg" and got["offenders"][1]["nearest_role"] == "color.veil" and got["offenders"][2]["nearest_role"] == "color.veil"
    assert "nearest see-through role color.veil" in got["detail"] and "OKLab distance" in got["detail"]
    no_veil = {"modes": {"light": {"color.text": {"hex": "#0d1b2d", "alpha": 1}}}}
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.colour_rows(rep, {"views": [view(colours=[colour("#0d1b2d", 0.5)])]}, synthetic_ctx(tmp_path, no_veil))
    assert rep.results[0]["status"] == "fail" and "the theme has no see-through colour" in rep.results[0]["detail"]
    rep = Report("page-check/x-000000", tmp_path)   # a theme the file does not hold, and a scheme no view was measured in, are never a pass
    pagecheck.colour_rows(rep, {"views": [view("dark", colours=ok)]}, synthetic_ctx(tmp_path, TOKENS, ("light", "dark")))
    assert [(r["id"], r["status"]) for r in rep.results] == [("page:colours:light", "skipped"), ("page:colours:dark", "skipped")]
    assert rep.exit_code() == 3


def test_load_modern_reads_the_modern_values_tokens_css_serves_and_nothing_else(tmp_path):
    """No browser: the oklch(), oklab() and color() values of the primitives, by custom property; hex values and other custom properties are left out."""
    (tmp_path / "assets" / "tokens").mkdir(parents=True)
    (tmp_path / "assets" / "tokens" / "tokens.css").write_text(""":root { --color-teal: #009b8c; --color-red: #ff0000; --motion-base: 200ms; --ease: cubic-bezier(0.2, 0, 0, 1); }
@supports (color: oklch(0 0 0)) {
  :root {
    --color-teal: oklch(0.6 0.15 185);
    --color-red: oklab(0.7 0.1  0.05 / 0.5);
    --color-wide: color(display-p3 1 0 0);
  }
}
:root { --color-line: var(--color-mist); }
""", encoding="utf-8")
    assert pagecheck.load_modern(tmp_path) == {"--color-teal": "oklch(0.6 0.15 185)", "--color-red": "oklab(0.7 0.1 0.05 / 0.5)", "--color-wide": "color(display-p3 1 0 0)"}
    (tmp_path / "assets" / "tokens" / "tokens.css").write_text(":root { --color-teal: #009b8c; }\n", encoding="utf-8")
    assert pagecheck.load_modern(tmp_path) == {}   # tokens that are all hex have no modern value
    (tmp_path / "assets" / "tokens" / "tokens.css").unlink()
    with pytest.raises(CliError) as e:
        pagecheck.load_modern(tmp_path)
    assert e.value.code == 3 and "tokens.css" in str(e.value)


# a token outside sRGB: tokens.json holds the hex the build gamut-mapped (#00978a); the browser clips the oklch() value itself and paints #009b8c, four units off
OUTSIDE = {"modes": {"light": {"color.accent": {"hex": "#00978a", "alpha": 1, "ref": "color.teal"}, "color.bg": {"hex": "#f9f7ee", "alpha": 1, "ref": "color.paper"},
                               "color.line": {"hex": "#ff5843", "alpha": 1, "ref": "color.red"}}},
           "pairs": [{"fg": "color.accent", "bg": "color.bg", "kind": "ui-text-large", "min": 3.0, "modes": {"light": {"fg_hex": "#00978a", "bg_hex": "#f9f7ee"}}}]}
MODERN = {"--color-teal": "oklch(0.6 0.15 185)", "--color-red": "oklch(0.7 0.25 30)"}
RENDERED = {"oklch(0.6 0.15 185)": "#009b8c", "oklch(0.7 0.25 30)": "#ff412d"}   # a canvas readback in Chromium; culori's toGamut gives #ff5843 for the red, 23 units off


def test_a_role_is_its_hex_and_the_colour_the_browser_renders_for_it_and_a_stranger_is_neither(tmp_path):
    """No browser: a colour outside sRGB is accepted in both forms in page:colours and in the declared-pair match, a colour that is neither is still named, and with
    no rendered value (a view that measured none) only the hex counts."""
    colour = lambda hex_, prop="color", sel="body > a": {"sel": sel, "prop": prop, "hex": hex_, "alpha": 1, "count": 1, "also": []}
    text = lambda fg, ground="#f9f7ee": {"sel": "body > a", "text": "link", "fg": fg, "fg_alpha": 1, "opacity": 1, "ground": ground, "ground_kind": "colour", "ground_sel": "body",
                                         "font_size_px": 14, "font_weight": 400}
    ctx = pagecheck.Ctx(tmp_path, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [390], ["light"], qa_rules.DEFAULTS, OUTSIDE, MODERN)
    both = {"views": [view(role_colours=RENDERED, colours=[colour("#00978a"), colour("#009b8c"), colour("#ff412d", "border-color", "body > p"), colour("#ff5843", "border-color", "body > p"),
                                                          colour("#f9f7ee", "background-color", "body")],
                           texts=[text("#009b8c"), text("#00978a")])]}
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.colour_rows(rep, both, ctx)
    pagecheck.pair_rows(rep, both, ctx)
    assert [(r["id"], r["status"]) for r in rep.results] == [("page:colours:light", "pass"), ("page:pairs:light", "pass")], [r["detail"] for r in rep.results]
    assert rep.results[1]["declared"] == 2 and rep.results[1]["texts_checked"] == 2   # the link in the hex and the link in the browser's colour are both the declared pair
    stranger = {"views": [view(role_colours=RENDERED, colours=[colour("#009b8f"), colour("#ff0000", "border-color", "body > p")], texts=[text("#009b8f")])]}   # 3 off the rendered teal; 5 and 66 off the others
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.colour_rows(rep, stranger, ctx)
    (got,) = rep.results
    assert got["status"] == "fail" and [(o["selector"], o["colour"]) for o in got["offenders"]] == [("body > a", "#009b8f"), ("body > p", "#ff0000")]
    assert got["offenders"][0]["nearest_role"] == "color.accent" and got["offenders"][0]["nearest_hex"] == "#009b8c"   # the nearer of the role's two colours is named
    unrendered = {"views": [view(colours=[colour("#009b8c")], texts=[text("#009b8c")])]}   # no `role_colours` in the view: only the hex of tokens.json is known
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.colour_rows(rep, unrendered, ctx)
    pagecheck.pair_rows(rep, unrendered, ctx)
    assert [r["status"] for r in rep.results] == ["fail", "fail"]   # 4 units off the hex, and an undeclared pair under 4.5:1 at 14 px


def test_a_text_filled_by_a_paint_server_is_not_verified_and_never_dropped_in_silence(tmp_path):
    """No browser: an SVG text filled with url(#gradient) has no colour; page:pairs says NOT verified, as it does for text over an image."""
    server = {"sel": "svg > text", "text": "Sale", "fg": None, "fg_alpha": 1, "opacity": 1, "ground": "#f9f7ee", "ground_kind": "colour", "ground_sel": "body", "font_size_px": 20,
              "font_weight": 700, "fill_server": True}
    ctx = synthetic_ctx(tmp_path, TOKENS)
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.pair_rows(rep, {"views": [view(texts=[server])]}, ctx)
    (got,) = rep.results
    assert got["status"] == "warn" and "NOT verified: text over an image" in got["detail"] and "paint server" in got["detail"], got["detail"]
    assert [o["selector"] for o in got["over_image"]] == ["svg > text"] and got["texts_checked"] == 1


def test_the_large_text_rule_and_the_direction_of_a_declared_pair(tmp_path):
    """No browser: 3:1 from 24 px, or from 18.66 px at weight 700; a declared pair passes whatever its ratio, and only in the direction it was declared."""
    grey, white = "#8c8c8c", "#ffffff"
    assert 3.0 <= pagecheck.wcag_ratio(grey, white) < 4.5
    text = lambda sel, size, weight, fg=grey, ground=white: {"sel": sel, "text": sel, "fg": fg, "fg_alpha": 1, "opacity": 1, "ground": ground, "ground_kind": "colour",
                                                           "ground_sel": "body", "font_size_px": size, "font_weight": weight}
    texts = [text("big", 24, 400), text("almost-big", 23.99, 400), text("bold", 18.66, 700), text("semibold", 18.66, 699), text("small-bold", 18.65, 700),
             text("declared", 12, 400, "#0d1b2d", "#f9f7ee"), text("reversed", 12, 400, "#f9f7ee", "#0d1b2d")]
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.pair_rows(rep, {"views": [view(texts=texts)]}, synthetic_ctx(tmp_path, TOKENS))
    (got,) = rep.results
    assert got["status"] == "fail" and got["declared"] == 1 and got["texts_checked"] == 7
    (small,) = got["failing"]   # texts with the same colours on the same ground and the same floor are one entry
    assert (small["selector"], small["also"], small["texts"], small["floor"], small["large"]) == ("almost-big", ["semibold", "small-bold"], 3, 4.5, False)
    big, reversed_ = got["undeclared"]
    assert (big["selector"], big["also"], big["texts"], big["floor"], big["large"]) == ("big", ["bold"], 2, 3.0, True) and reversed_["selector"] == "reversed"
    assert "declare them in pairs" in got["detail"] and "3 texts" in got["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_gradient_ground_is_not_verified_and_never_passed_in_silence(acme):
    """Text over a background image or gradient cannot be measured: the row says so and only warns."""
    page = write_page(acme)
    page.write_text(PAGE.replace("</style>", "  .hero { background: linear-gradient(var(--color-bg), var(--color-line)); }\n</style>")
                    .replace("<main>", '<main class="hero">'), encoding="utf-8")
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    for scheme in ("light", "dark"):
        pairs = row(rep, f"page:pairs:{scheme}")
        assert pairs["status"] == "warn" and "NOT verified: text over an image" in pairs["detail"], pairs
        assert {o["selector"] for o in pairs["over_image"]} >= {"body > main.hero > h1"}
        assert row(rep, f"page:colours:{scheme}")["status"] == "pass"   # a gradient's own colours are not read: the row passes on the colours it did read


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_colours_collector_reads_every_source_and_skips_what_is_not_shown(acme):
    page = write_page(acme)
    page.write_text(PAGE.replace("</style>", """  .box { border: 2px solid #123456; outline: 3px solid #00ff00; background: #ffeedd; }
  .hidden { display: none; color: #abcdef; } .invisible { visibility: hidden; color: #abcd01; } .clear { opacity: 0; color: #abcd02; }
  .away { position: absolute; left: -9999px; color: #abcd03; } .zero { font-size: 0; color: #abcd04; }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); color: #abcd06; }
  .sr2 { position: absolute; clip-path: inset(50%); color: #abcd09; }
  .fold { height: 0; overflow: hidden; } .fold p { color: #abcd08; }
  .hair { height: 1px; overflow: hidden; background: #aa0001; }
  details p { color: #abcd05; } details[open] p { color: #abcd07; }
  input::placeholder { color: #a1b2c3; }
</style>""").replace("</main>", """<p class="box">A box</p>
<p class="hidden">hidden</p><p class="invisible">invisible</p><p class="clear">clear</p><p class="away">away</p><p class="zero">zero</p>
<span class="sr">visually hidden</span><span class="sr2">hidden too</span><div class="fold"><p>folded</p></div><div class="hair"></div>
<details><summary>Closed</summary><p>closed content</p></details><details open><summary>Open</summary><p>open content</p></details>
<p lang="pl" data-sample="Price">Cena 12 zł</p>
<svg width="20" height="20" style="background: #c0ffee"><path d="M0 0h10v10z" fill="#bada55" stroke="#336699" stroke-width="2"/><circle cx="5" cy="5" r="3" fill="none"/>
  <rect id="hit" x="0" y="12" width="6" height="6" fill="#ff00ff" fill-opacity="0" stroke="#ff00fe" stroke-opacity="0" stroke-width="2"/>
  <line x1="4" y1="12" x2="20" y2="12" stroke="#12ab34" stroke-width="2"/><path d="M5 2v16" stroke="#34ab12" stroke-width="2" fill="#ab3412"/>
  <path d="M2 18L18 2" stroke="#0d1b2d" stroke-width="2"/><polyline points="2,2 18,18" stroke="#0d1b2d" stroke-width="2"/></svg>
<svg width="80" height="24"><defs><linearGradient id="grad"><stop offset="0" stop-color="#123456"/><stop offset="1" stop-color="#654321"/></linearGradient></defs>
  <text x="2" y="18" fill="url(#grad)">Sale</text></svg>
<input placeholder="Your name">
</main>"""), encoding="utf-8")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr   # the colours of the box, the SVG and the input are not the brand's
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    (v,) = measures["views"]
    seen = {(c["prop"], c["hex"]) for c in v["colours"]}
    assert {("border-color", "#123456"), ("outline-color", "#00ff00"), ("background-color", "#ffeedd"), ("background-color", "#c0ffee"), ("fill", "#bada55"),
            ("stroke", "#336699")} <= seen, sorted(seen)
    assert "text-decoration-color" in {p for p, _ in seen}   # the link's underline, drawn in the accent
    assert not {h for _, h in seen} & {"#abcdef", "#abcd01", "#abcd02", "#abcd03", "#abcd04"}   # display:none, visibility:hidden, opacity:0, off the page, font-size:0
    assert not {h for _, h in seen} & {"#abcd05", "#abcd06", "#abcd08", "#abcd09"}   # the content of a closed <details>, and what is cut to nothing: sr-only by clip, by clip-path, a folded box
    assert ("color", "#abcd07") in seen and ("background-color", "#aa0001") in seen   # an open <details>, and a hairline 1px high, are seen
    assert not any(c["hex"] == "#000000" and c["prop"] == "fill" for c in v["colours"])   # fill="none" paints nothing, and neither does the default fill of a diagonal path or polyline
    assert {("stroke", "#12ab34"), ("stroke", "#34ab12")} <= seen   # a horizontal line and a vertical path have a box of no height or no width, and their stroke is drawn
    assert not {h for _, h in seen} & {"#ff00ff", "#ff00fe"}   # an opacity of 0 paints nothing: an invisible hit area names no colour
    assert ("fill", "#ab3412") not in seen   # a shape with no area paints no fill; a <line> never has one, so its default black is not a colour either (the assertion below)
    texts = {t["sel"]: t for t in v["texts"]}
    h1 = texts["body > main > h1"]
    assert h1["text"] == "Acme hand tools" and h1["ground_kind"] == "colour" and h1["ground_sel"] == "body"
    assert pagecheck.same_rgb(parse_hex(h1["fg"]), parse_hex("#0d1b2d")) and pagecheck.same_rgb(parse_hex(h1["ground"]), parse_hex("#f9f7ee"))   # the Acme ink on the Acme paper
    assert h1["font_size_px"] == 32 and h1["font_weight"] == 700 and h1["lang"] == "en" and h1["sample_label"] is None and h1["rect"]["width"] > 0
    price = next(t for t in v["texts"] if t["text"].startswith("Cena"))
    assert price["sample_label"] == "Price" and price["lang"] == "pl"
    assert next(t for t in v["texts"] if t["text"] == "Your name")["fg"] == "#a1b2c3"   # the placeholder's own colour, not the input's
    assert not any(t["text"] in ("hidden", "invisible", "clear", "away", "zero", "visually hidden", "hidden too", "folded", "closed content") for t in v["texts"])
    assert {"open content", "Open", "Closed"} <= {t["text"] for t in v["texts"]}   # the summary of a closed <details> is shown
    sale = next(t for t in v["texts"] if t["text"] == "Sale")   # a text filled by a gradient is reported, with no colour: page:pairs says NOT verified
    assert sale["fg"] is None and sale["fill_server"] is True and sale["ground_kind"] == "colour"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_colour_that_is_not_a_token_fails_and_is_named(acme):
    page = write_page(acme)
    mutate(page, "a { color: var(--color-accent); }", "a { color: #d81b60; }")
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    for scheme in ("light", "dark"):   # the pink is a colour of neither theme
        bad = row(rep, f"page:colours:{scheme}")
        assert bad["status"] == "fail", bad
        assert {(o["property"], o["colour"]) for o in bad["offenders"]} == {("color", "#d81b60"), ("text-decoration-color", "#d81b60")}
        assert all(o["selector"].endswith(" > a") and o["nearest_role"].startswith("color.") and isinstance(o["distance"], float) and o["width"] == 390 for o in bad["offenders"])
        assert "color #d81b60" in bad["detail"] and "nearest role color." in bad["detail"] and "OKLab distance" in bad["detail"] and "at 390 px" in bad["detail"]
    assert row(rep, "page:load:390-light")["status"] == "pass"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_light_ground_left_in_the_dark_theme_fails_the_dark_row(acme):
    page = write_page(acme)
    light_bg = json.loads((acme / "assets" / "tokens" / "tokens.json").read_text(encoding="utf-8"))["modes"]["light"]["color.bg"]["hex"]
    mutate(page, "background: var(--color-bg);", f"background: {light_bg};")   # the light paper written as a literal: right in the light theme, wrong in the dark one
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    assert row(rep, "page:colours:light")["status"] == "pass" and row(rep, "page:pairs:light")["status"] == "pass"
    dark = row(rep, "page:colours:dark")
    assert dark["status"] == "fail" and [(o["selector"], o["property"], o["colour"]) for o in dark["offenders"]] == [("body", "background-color", light_bg)]
    assert dark["offenders"][0]["nearest_role"].startswith("color.") and dark["offenders"][0]["distance"] < 0.05
    pairs = row(rep, "page:pairs:dark")
    assert pairs["status"] == "fail" and "needs 4.5:1" in pairs["detail"] and f"on {light_bg}" in pairs["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_undeclared_pair_under_the_wcag_floor_fails_and_one_above_it_warns(acme):
    page = write_page(acme)
    mutate(page, "</style>", ".card { background: var(--color-line); padding: 8px; }\n  .note { margin: 0; font-size: 16px; color: var(--color-text); }\n</style>")
    mutate(page, "</main>", '<div class="card"><p class="note">Spare parts list</p></div>\n</main>')
    # the text colour on the line colour is no declared pair, and it is far above the floor: a warning that says what to do, and nothing fails
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    for scheme in ("light", "dark"):
        warned = row(rep, f"page:pairs:{scheme}")
        assert warned["status"] == "warn" and "declare them in pairs" in warned["detail"] and warned["failing"] == []
        assert [o["selector"] for o in warned["undeclared"]] == ["body > main > div.card > p.note"] and warned["undeclared"][0]["ratio"] > 4.5
        assert row(rep, f"page:colours:{scheme}")["status"] == "pass"   # every colour on the page is a role: only the pairing is new
    # the accent on the line colour is under 4.5:1 for text of 16 px
    mutate(page, "font-size: 16px; color: var(--color-text);", "font-size: 16px; color: var(--color-accent);")
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    for scheme in ("light", "dark"):
        bad = row(rep, f"page:pairs:{scheme}")
        (note,) = bad["failing"]
        assert bad["status"] == "fail" and note["selector"].endswith("p.note") and 3.0 <= note["ratio"] < 4.5 and note["floor"] == 4.5 and not note["large"]
        assert "needs 4.5:1 for normal text" in bad["detail"] and "not declared in pairs" in bad["detail"]
    # the same pair at 32 px is large text: the 3:1 floor, so it only warns again
    mutate(page, "font-size: 16px; color: var(--color-accent);", "font-size: 32px; color: var(--color-accent);")
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    for scheme in ("light", "dark"):
        warned = row(rep, f"page:pairs:{scheme}")
        assert warned["status"] == "warn" and warned["failing"] == [] and warned["undeclared"][0]["large"] is True



@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_token_outside_srgb_is_the_colour_the_browser_paints_and_an_off_token_colour_still_fails(acme):
    """tokens.css serves the role's real oklch() value, which the browser clips channel by channel; tokens.json holds the hex gamut-mapped by chroma reduction. The
    two differ by more than the rounding of a hex, and the token build accepts such a token. A page that uses only the tokens must pass: both colours are the role's."""
    page = write_page(acme)
    mutate(page, "</style>", "  .rule { border-bottom: 3px solid var(--color-line); }\n</style>")
    mutate(page, "</main>", '<p class="rule"></p>\n</main>')
    primitives = acme / "tokens" / "primitives.tokens.json"
    mutate_json(primitives, lambda d: d["color"]["teal"]["$value"].__setitem__("components", [0.6, 0.15, 185]))   # outside sRGB: the hex and the browser's colour differ by 4 units
    mutate_json(primitives, lambda d: d["color"]["mist"]["$value"].__setitem__("components", [0.7, 0.25, 30]))   # and by 23 units: a vivid red nobody pairs with text
    assert bc("tokens", "--fix-hex", project=acme).returncode == 0
    assert bc("tokens", project=acme).returncode == 0
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    tokens = json.loads((acme / "assets" / "tokens" / "tokens.json").read_text(encoding="utf-8"))
    (light,) = [x for x in measures["views"] if x["scheme"] == "light"]
    painted = {"color.accent": next(c for c in light["colours"] if c["prop"] == "color" and c["sel"].endswith(" > a")),
               "color.line": next(c for c in light["colours"] if c["prop"] == "border-bottom-color")}
    for role, least in (("color.accent", 4), ("color.line", 20)):   # the case this test is about (the dark roles are inside sRGB)
        gap = max(abs(x - y) for x, y in zip(parse_hex(painted[role]["hex"]), parse_hex(tokens["modes"]["light"][role]["hex"])))
        assert gap >= least > pagecheck.RGB_TOLERANCE, (role, painted[role]["hex"], tokens["modes"]["light"][role]["hex"])
    for scheme in ("light", "dark"):
        assert row(rep, f"page:colours:{scheme}")["status"] == "pass" and row(rep, f"page:pairs:{scheme}")["status"] == "pass", rep["results"]
        assert row(rep, f"page:pairs:{scheme}")["declared"] >= 1   # the link is the declared pair accent on bg, in the colour the browser paints
    mutate(page, "a { color: var(--color-accent); }", "a { color: #d81b60; }")   # a colour that is no token's
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    assert all(row(rep, f"page:colours:{s}")["status"] == "fail" for s in ("light", "dark"))


# ---------------------------------------------------------------- motion, claims and the before-publishing list

STANDARD_CURVE = "cubic-bezier(0.2, 0, 0, 1)"


def add_motion_tokens(p: Path) -> None:
    """The golden Acme holds duration.fast (150 ms) and no curve: add easing.standard and build again, so a page can be made of motion tokens (--easing-standard)."""
    mutate_json(p / "tokens" / "primitives.tokens.json", lambda d: d.__setitem__("easing", {"$type": "cubicBezier", "standard": {"$value": [0.2, 0, 0, 1]}}))
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr


def add_fact(p: Path, label: str, value: str) -> None:
    """A confirmed row of FACTS.md (after the template's example row)."""
    f = p / "FACTS.md"
    f.write_text(f.read_text(encoding="utf-8").replace("| YYYY-MM-DD |\n", f"| YYYY-MM-DD |\n| {label} | {value} | owner, intake | 2026-10-17 |\n", 1), encoding="utf-8")
    assert f"| {label} |" in f.read_text(encoding="utf-8")


def write_facts(folder: Path, *rows: tuple[str, str]) -> None:
    lines = ["# Acme: facts", "", "| fact | value | source | confirmed |", "|---|---|---|---|"] + [f"| {k} | {v} | owner, intake | 2026-10-17 |" for k, v in rows]
    (folder / "FACTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def decl(duration=150, easing=STANDARD_CURVE, source="transition", name="color", sel="body > a", **more) -> dict:
    return {"sel": sel, "source": source, "name": name, "duration_ms": duration, "easing": easing, "via": "style", "count": 1, "also": [], **more}


def motion_row(tmp_path: Path, tokens: dict, *decls: dict, **view_facts) -> dict:
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.motion_rows(rep, {"views": [view(motion_decls=list(decls), **view_facts)]}, synthetic_ctx(tmp_path, tokens))
    (got,) = rep.results
    return got


def with_motion(curves: dict, durations: dict | None = None) -> dict:
    return {**TOKENS, "motion": {"durations_ms": durations if durations is not None else {"duration.fast": 150, "duration.base": 320}, "curves": curves}}


def claim_run(text: str, sel: str = "body > p", label=None, lang: str = "") -> dict:
    return {"sel": sel, "text": text, "sample_label": label, "lang": lang}


def claims(tmp_path: Path, runs: list, samples=(), lang: str = "en") -> tuple[dict, list[dict], pagecheck.Ctx]:
    """page:claims on constructed measurements: the row, every row, and the Ctx (its `extra` holds the samples)."""
    rep = Report("page-check/x-000000", tmp_path)
    ctx = synthetic_ctx(tmp_path, TOKENS)
    pagecheck.claim_rows(rep, {"views": [view(lang=lang, claim_text=list(runs), samples=list(samples))]}, ctx)
    return rep.results[0], rep.results, ctx


# ---- no browser


def test_numbers_in_finds_the_claims_and_leaves_step_labels_and_identifiers_alone():
    found = lambda text, **kw: [n["text"] for n in pagecheck.numbers_in(text, **kw)]
    assert found("Tools are made in batches of 200") == ["200"]
    assert found("Step 3 of 4, page 1") == [] and found("Step 3 of 4", every=True) == ["3", "4"]   # a bare single digit is a label, unless every number is wanted
    assert found("5% off, 9 zł, $5, €5, 4K, 5m, 12 tys., 7 PLN") == ["5%", "9 zł", "$5", "€5", "4K", "5m", "12 tys.", "7 PLN"]   # a single digit next to a sign or a unit is a claim
    assert found("9 €, 5€, 7 $, 3 £, PLN 5, PLN5, EUR 9, USD 4, gbp 2, CHF 8") == ["9 €", "5€", "7 $", "3 £", "PLN 5", "PLN5", "EUR 9", "USD 4", "gbp 2", "CHF 8"]   # a sign after the number, a code before it
    assert found("Only 9 € today, 5 euros, PLNs 5, 5 EURO") == ["9 €"]                                                              # a word that only starts like a currency is not one
    assert found("mp3, A4, v1.2.3, 3rd, 3 steps, 3 minutes") == []                                                                  # written against letters, or not a unit
    assert found("2026-10-17, 24/7, 1.5x") == ["2026", "10", "17", "24", "1.5x"]                                                     # a digit run of two or more; 1.5 has two digits
    assert [canon for canon in (pagecheck.canonical_number(x) for x in ("1 200", "1 200", "1,200", "1.200", "1200"))] == ["1200"] * 5
    assert [pagecheck.canonical_number(x) for x in ("12,5", "12.50", "12.5", "0,500", "0.500")] == ["12.5", "12.5", "12.5", "0.5", "0.5"]
    assert [pagecheck.canonical_number(x) for x in ("100.000,50", "1.200,5", "1,200.50", "1.200.300,5", "1 200,50", "100 000,50")] == ["100000.5", "1200.5", "1200.5", "1200300.5", "1200.5", "100000.5"]   # the last separator is the decimal point


def test_a_number_backed_by_facts_passes(tmp_path):
    write_facts(tmp_path, ("batch size", "tools are made in batches of 200"), ("spare part", "a spare part costs 12,50 zł"), ("owners", "1 200 owners; 5% return"),
                ("status", "the online shop is in development"), ("(example) repair", "a decoy of 999 that is the template's"), ("full set", "the full set costs 100 000,50 zł"))
    runs = [claim_run("Tools are made in batches of 200."), claim_run("A spare part costs 12.5 zł", "body > b"), claim_run("1,200 owners, 5% return, step 3 of 4", "body > i"),
            claim_run("The online shop is in development", "body > u"), claim_run("The full set costs 100.000,50 zł", "body > s")]   # dot thousands and a decimal comma, the fact has a space
    got, results, ctx = claims(tmp_path, runs)
    assert [(r["id"], r["status"]) for r in results] == [("page:claims", "pass")], got["detail"]   # no sample: no page:samples row
    assert got["claims_checked"] == {"texts": 5, "numbers": 5, "status_words": 1} and ctx.extra["samples"] == []
    euro = claims(tmp_path, [claim_run("Only 9 € today, or 7 € per month, PLN 6 net")])[0]   # a price in euros or zloty is a claim, a single digit too
    assert euro["status"] == "fail" and [o["number"] for o in euro["unbacked_numbers"]] == ["9 €", "7 €", "PLN 6"], euro["detail"]   # (PLN 5 would be backed by the fact "5% return": numbers are compared as numbers)
    off = [claim_run("Tools are made in batches of 2000."), claim_run("Only 20 left", "body > b"), claim_run("It is 999 here", "body > i")]   # 2000, 20 and the template's decoy are no fact
    bad, _, _ = claims(tmp_path, off)
    assert bad["status"] == "fail" and [o["number"] for o in bad["unbacked_numbers"]] == ["2000", "20", "999"]
    assert 'data-sample="<label>"' in bad["detail"] and "\"Tools are made in batches of 2000.\"" in bad["detail"]
    nothing = tmp_path / "empty"
    nothing.mkdir()
    rep = Report("page-check/x-000000", nothing)   # no FACTS.md at all backs nothing
    pagecheck.claim_rows(rep, {"views": [view(lang="en", claim_text=[claim_run("Batches of 200")], samples=[])]}, synthetic_ctx(nothing, TOKENS))
    assert rep.results[0]["status"] == "fail"


def test_a_number_is_counted_once_however_many_views_show_it(tmp_path):
    write_facts(tmp_path, ("batch size", "200 per batch"))
    rep = Report("page-check/x-000000", tmp_path)
    runs = [claim_run("Batches of 200, now available"), claim_run("Only 20 left", "body > b")]
    views = [view(scheme=scheme, width=width, lang="en", claim_text=list(runs), samples=[]) for width in (390, 1280) for scheme in ("light", "dark")]
    views[3]["claim_text"] = runs + [claim_run("Wide screens: 45 pieces", "body > i")]   # text that only one view shows is counted too
    pagecheck.claim_rows(rep, {"views": views}, synthetic_ctx(tmp_path, TOKENS, ("light", "dark")))
    got = rep.results[0]
    assert got["claims_checked"] == {"texts": 3, "numbers": 3, "status_words": 1} and got["languages"] == {"en": 3}, got
    assert [(o["number"], o["width"]) for o in got["unbacked_numbers"]] == [("20", 390), ("45", 1280)]   # the first view that shows it is named
    passing = Report("page-check/x-000000", tmp_path)
    write_facts(tmp_path, ("batch size", "200 per batch, 20 per box, available"))
    pagecheck.claim_rows(passing, {"views": [view(scheme=s, width=w, lang="en", claim_text=list(runs[:2]), samples=[]) for w in (390, 1280) for s in ("light", "dark")]}, synthetic_ctx(tmp_path, TOKENS))
    assert passing.results[0]["status"] == "pass" and passing.results[0]["detail"].startswith("2 number(s) and 1 status word(s)"), passing.results[0]["detail"]


def test_a_status_word_needs_a_facts_value_that_says_so(tmp_path):
    write_facts(tmp_path, ("status", "the online shop is in development"))
    got, _, _ = claims(tmp_path, [claim_run("The online shop is in development."), claim_run("Now AVAILABLE!", "body > b"), claim_run("Launching soon: coming soon", "body > i")])
    assert got["status"] == "fail" and sorted(o["word"] for o in got["unbacked_status_words"]) == ["available", "coming soon", "launching"]   # whole words, any letter case
    assert "no FACTS.md value contains" in got["detail"]
    got, _, _ = claims(tmp_path, [claim_run("The unavailable shop is relaunching")])   # a status word inside another word is not one
    assert got["status"] == "pass"


def test_status_words_in_another_language_are_not_verified(tmp_path):
    write_facts(tmp_path, ("batch size", "200 per batch"), ("sklep", "sklep jest w przygotowaniu"))
    german = claims(tmp_path, [claim_run("Jetzt verfügbar: 200 Stück pro Charge")], lang="de")[0]
    assert german["status"] == "warn" and "status words NOT verified for de" in german["detail"] and german["languages"] == {"de": 1}
    broken = claims(tmp_path, [claim_run("Jetzt 300 Stück pro Charge")], lang="de")[0]
    assert broken["status"] == "fail" and "300" in broken["detail"] and "status words NOT verified for de" in broken["detail"]   # the numbers are still checked
    mixed = claims(tmp_path, [claim_run("Hello 200", "body > p"), claim_run("Bonjour 200", "body > b", lang="fr-CA")])[0]   # the closest lang of a block wins over the document's
    assert mixed["status"] == "warn" and mixed["languages"] == {"en": 1, "fr": 1} and "NOT verified for fr (" in mixed["detail"] and "for en" not in mixed["detail"]   # fr-CA is fr
    unknown = claims(tmp_path, [claim_run("Hello 200")], lang="")[0]   # a page that sets no lang: it cannot be told, and it says so
    assert unknown["status"] == "warn" and "an unknown language (the page sets no lang)" in unknown["detail"]
    polish = claims(tmp_path, [claim_run("Już wkrótce w sprzedaży"), claim_run("Sklep jest w przygotowaniu", "body > b")], lang="pl")[0]   # Polish words are listed: one is backed, one is not
    assert polish["status"] == "fail" and [o["word"] for o in polish["unbacked_status_words"]] == ["wkrótce"] and "NOT verified" not in polish["detail"]


def test_a_labelled_sample_is_listed_and_an_empty_label_is_not_a_sample(tmp_path):
    write_facts(tmp_path, ("batch size", "200 per batch"))
    runs = [claim_run("Now only 49 zł, available", "body > p > span", label="Price"), claim_run("Spare parts 200", "body > p"), claim_run("Hidden 77", "body > div", label="")]
    samples = [{"sel": "body > p > span", "label": "Price", "text": "Now only 49 zł, available"}, {"sel": "body > div", "label": " ", "text": "Hidden 77"}]
    got, results, ctx = claims(tmp_path, runs, samples)
    assert [(r["id"], r["status"]) for r in results] == [("page:claims", "fail"), ("page:samples", "info")]
    assert [o["number"] for o in got["unbacked_numbers"]] == ["77"] and "label the sample" in got["detail"] and got["unlabelled_samples"][0]["selector"] == "body > div"   # an empty label labels nothing
    assert ctx.extra["samples"] == [{"label": "Price", "text": "Now only 49 zł, available", "selector": "body > p > span", "view": "390-light"}] == results[1]["samples"]
    assert "Price (Now only 49 zł, available) in body > p > span, 390-light" in results[1]["detail"] and "before the page is published" in results[1]["detail"]


def words(tmp_path: Path, runs: list, *, terms=("revolutionary", "game-changer"), cliches=(), **view_facts) -> tuple[dict, list[dict]]:
    """page:words on constructed measurements, in a project whose brief lists `terms` under Forbidden and whose research/cliches.md lists `cliches`."""
    (tmp_path / "brief").mkdir(exist_ok=True)
    (tmp_path / "brief" / "BRIEF.md").write_text("# Brief\n\n## Forbidden\n\n<!-- one per bullet -->\n" + "".join(f"- {t}\n" for t in terms) + "\n## Decisions\n\n- not a term\n", encoding="utf-8")
    if cliches:
        (tmp_path / "research").mkdir(exist_ok=True)
        (tmp_path / "research" / "cliches.md").write_text("# Clichés\n\n## Forbidden\n\n" + "".join(f"- `{c}`\n" for c in cliches), encoding="utf-8")
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.word_rows(rep, {"views": [view(claim_text=list(runs), samples=[], **view_facts)]}, synthetic_ctx(tmp_path, TOKENS))
    (got,) = rep.results
    return got, rep.results


def test_a_forbidden_word_on_a_page_warns_and_names_it_and_a_page_without_one_passes(tmp_path):
    got, _ = words(tmp_path, [claim_run("Acme makes hand tools."), claim_run("A Revolutionary tool, and a game-changer.", "body > b")])
    assert got["id"] == "page:words" and got["status"] == "warn"   # a warning, never a failure (O6)
    assert sorted(h["word"] for h in got["forbidden_hits"]) == ["game-changer", "revolutionary"] and {h["selector"] for h in got["forbidden_hits"]} == {"body > b"}   # any letter case, one hit per word and block
    assert "'revolutionary' in body > b" in got["detail"] and "A Revolutionary tool" in got["detail"] and "reword" in got["detail"]
    clean, _ = words(tmp_path, [claim_run("Acme makes hand tools that last."), claim_run("Not revolutionaryx, nor a game-changerless one.", "body > b")])   # a word inside another word is not the word
    assert clean["status"] == "pass" and clean["forbidden_hits"] == [] and clean["forbidden_checked"] == 2 and clean["forbidden_words"] == ["revolutionary", "game-changer"] and "2 forbidden word(s)" in clean["detail"]


def test_the_forbidden_words_are_the_list_book_lint_applies_and_a_block_is_judged_once_across_views(tmp_path):
    got, _ = words(tmp_path, [claim_run("Our best-in-class tools, a true game-changer.")], terms=("game-changer",), cliches=("best-in-class",))   # brief/BRIEF.md and research/cliches.md, as book-lint reads them
    assert forbidden_terms(tmp_path) == ["game-changer", "best-in-class"] and sorted(h["word"] for h in got["forbidden_hits"]) == ["best-in-class", "game-changer"]
    rep = Report("page-check/x-000000", tmp_path)
    twice = [view(width=w, claim_text=[claim_run("A game-changer.")], samples=[]) for w in (390, 1440)]
    pagecheck.word_rows(rep, {"views": twice}, synthetic_ctx(tmp_path, TOKENS))
    assert [(h["word"], h["width"]) for h in rep.results[0]["forbidden_hits"]] == [("game-changer", 390)]   # the same block in a second view is one hit, named at the first view


def test_a_forbidden_word_in_a_labelled_sample_still_warns_and_says_it_is_in_a_sample(tmp_path):
    got, _ = words(tmp_path, [claim_run("A revolutionary price", "body > p > span", label="Price")])
    assert got["status"] == "warn" and got["forbidden_hits"][0]["sample"] == "Price" and "in a sample (Price)" in got["detail"]   # a made-up sentence is still wording the brand forbids


def test_no_list_of_forbidden_words_is_an_info_row_never_a_pass_and_an_unmeasured_page_is_not_verified(tmp_path):
    got, _ = words(tmp_path, [claim_run("A revolutionary tool.")], terms=())
    assert got["status"] == "info" and got["forbidden_hits"] == [] and got["forbidden_checked"] == 0 and "no forbidden words are listed" in got["detail"] and "brief/BRIEF.md" in got["detail"]
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.word_rows(rep, {"views": [view(error="boom")]}, synthetic_ctx(tmp_path, TOKENS))
    assert rep.results[0]["status"] == "skipped" and "not verified" in rep.results[0]["detail"]
    truncated, _ = words(tmp_path, [claim_run("Plain text.")], claim_text_total=3500)   # more blocks than were measured: no pass
    assert truncated["status"] == "warn" and "NOT verified beyond the first blocks" in truncated["detail"]


def test_a_copy_row_of_facts_md_backs_a_number_like_any_fact_and_only_its_value_counts(tmp_path):
    write_facts(tmp_path, ("copy: hero headline", "Tools built to last 25 years"), ("batch size", "200 per batch"))
    got, _, _ = claims(tmp_path, [claim_run("Tools built to last 25 years."), claim_run("Made in batches of 200", "body > b")])
    assert got["status"] == "pass" and got["unbacked_numbers"] == []   # the wording backs its number as a fact does
    got, _, _ = claims(tmp_path, [claim_run("Tools built to last 30 years.")])
    assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["30"]   # the label's own text backs nothing
    assert pagecheck.fact_values(tmp_path) == ["Tools built to last 25 years", "200 per batch"]


def test_the_facts_template_the_site_round_and_the_contract_state_the_copy_split_and_the_words_row():
    facts = (ROOT / "templates" / "FACTS.md").read_text(encoding="utf-8")
    assert "labelled `copy: <slot>`" in facts and "`copy: site H1`" in facts and "`copy: signature line`" in facts and "never uses a fact's `value` as it stands" in facts
    site_round = " ".join((ROOT / "skills" / "brand-creator" / "references" / "phases" / "07p-site-round.md").read_text(encoding="utf-8").split())
    for needle in ("A headline is never a fact's `value` as it stands", "quotes a `copy:` row of `FACTS.md`", "new wording the owner approves on the board", "`page:words`, never a failure",
                   "Forbidden"):
        assert needle in site_round, needle
    contract = " ".join((ROOT / "scripts" / "CONTRACT.md").read_text(encoding="utf-8").split())
    assert "**Word row.** `page:words`" in contract and "**Copy rows of `FACTS.md`.**" in contract and "never a `pass`" in contract
    assert pagecheck.ROW_CHECKS.index(pagecheck.word_rows) == pagecheck.ROW_CHECKS.index(pagecheck.claim_rows) + 1


def claims_of_page(tmp_path: Path, runs: list, title: str = "", h1=(), lang: str = "en") -> dict:
    """page:claims on constructed measurements of a page that has a title and headings: the row."""
    rep = Report("page-check/x-000000", tmp_path)
    pagecheck.claim_rows(rep, {"views": [view(lang=lang, claim_text=list(runs), samples=[], document={"title": title}, claim_h1=list(h1))]}, synthetic_ctx(tmp_path, TOKENS))
    return rep.results[0]


def test_numbers_in_reads_a_dotted_date_as_its_parts_and_a_space_group_only_as_thousands():
    num = lambda text, **kw: [(n["text"], n["number"], n.get("parts")) for n in pagecheck.numbers_in(text, **kw)]
    assert num("Premiera 15.11.2026") == [("15.11.2026", "15.11.2026", ["15", "11", "2026"])]                                       # dd.mm.yyyy: its parts, never a decimal
    assert num("Wypłata 30.10") == [("30.10", "30.1", ["30", "10"])]                                                                 # dd.mm is also the decimal 30.1
    assert num("Premiera 15.11.2026r., 5.11.2026 r.") == [("15.11.2026", "15.11.2026", ["15", "11", "2026"]), ("5.11.2026", "5.11.2026", ["5", "11", "2026"])]   # the Polish r. is no part of it
    assert num("Ocena 4.5, 1.5, 12.50, 99.99, 4.5 kg, 1.12 zł, 2026-11-15") == [("4.5", "4.5", None), ("1.5", "1.5", None), ("12.50", "12.5", None), ("99.99", "99.99", None), ("4.5 kg", "4.5", None),
                                                                             ("1.12 zł", "1.12", None), ("2026", "2026", None), ("11", "11", None), ("15", "15", None)]   # not a date: single digits, a month over 12, a unit
    assert [(t, parts) for t, _, parts in num("32.11.2026, 15.13.2026, 15.11.1850")] == [("32.11.2026", None), ("15.13.2026", None), ("15.11.1850", None)]   # not a day, month or year of ours: a plain number
    assert num("13 205,20 zł, 1 234 567, 12 000") == [("13 205,20 zł", "13205.2", None), ("1 234 567", "1234567", None), ("12 000", "12000", None)]
    assert num("In 2026 200 tools, 10 2345, 1 2345") == [("2026", "2026", None), ("200", "200", None), ("10", "10", None), ("2345", "2345", None), ("2345", "2345", None)]   # a first group of four digits, or a later one that is not three
    assert num("13\u00a0205,20 zł and 13\u202f205") == [("13\u00a0205,20 zł", "13205.2", None), ("13\u202f205", "13205", None)]                      # a no-break space groups too


def test_a_dotted_date_is_backed_by_its_parts_like_the_iso_form(tmp_path):
    write_facts(tmp_path, ("release", "premiera 2026-11-15"), ("payout", "wypłata 2026-10-30"), ("start", "start 2026-11-05"), ("rating", "rated 4.5 stars"))
    runs = [claim_run("Premiera 15.11.2026", "body > a"), claim_run("Premiera 15.11", "body > b"), claim_run("Wypłata 30.10", "body > i"), claim_run("Wypłata 30.10.2026r.", "body > u"),
            claim_run("Start 5.11.2026", "body > s"), claim_run("Start 05.11", "body > p"), claim_run("Ocena 4.5", "body > em")]   # a leading 0 on a day is the same day; 4.5 is a decimal and backed as one
    got = claims_of_page(tmp_path, runs, lang="pl")
    assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 7, got["detail"]
    off = claims_of_page(tmp_path, [claim_run("Premiera 16.11.2026", "body > a"), claim_run("Wypłata 31.10", "body > b"), claim_run("Premiera 15.12", "body > i"), claim_run("Ocena 4.6", "body > u")], lang="pl")
    assert off["status"] == "fail" and [o["number"] for o in off["unbacked_numbers"]] == ["16.11.2026", "31.10", "15.12", "4.6"], off["detail"]   # 16, 31 and 12 are in no fact
    write_facts(tmp_path, ("days", "ponad 30 dni"))
    assert claims_of_page(tmp_path, [claim_run("Wypłata 30.10")], lang="pl")["status"] == "fail"       # 30 alone is not enough: the date needs 10 too
    write_facts(tmp_path, ("days", "ponad 30 dni"), ("month", "miesiąc 10"))
    assert claims_of_page(tmp_path, [claim_run("Wypłata 30.10")], lang="pl")["status"] == "pass"
    write_facts(tmp_path, ("days", "ponad 30 dni"))
    assert claims_of_page(tmp_path, [claim_run("Wypłata 30.1")], lang="pl")["status"] == "fail"        # the decimal reading is a number of its own: 30.1 is not 30 and 1


def test_a_space_group_is_one_number_only_when_it_is_made_of_thousands(tmp_path):
    write_facts(tmp_path, ("set", "the full set costs 13 205,20 zł"), ("year", "founded in 2026 with 200 tools"))
    got = claims_of_page(tmp_path, [claim_run("Only 13 205,20 zł", "body > p"), claim_run("In 2026 200 tools", "body > b"), claim_run("Price 13\u00a0205,20 zł", "body > i")])
    assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 4, got["detail"]               # 13205.2, then 2026 and 200, then 13205.2 with a no-break space
    off = claims_of_page(tmp_path, [claim_run("In 2026 300 tools", "body > b"), claim_run("Only 13 206,20 zł", "body > p")])
    assert [o["number"] for o in off["unbacked_numbers"]] == ["300", "13 206,20 zł"], off["detail"]       # 2026 stays its own number: 300 alone is the claim


def test_a_copyright_year_and_an_error_pages_status_code_are_no_claims(tmp_path):
    write_facts(tmp_path, ("name", "Acme hand tools"))
    footer = [claim_run("© 2026 Acme. All rights reserved.", "body > footer"), claim_run("Copyright 2024–2026 Acme", "body > footer > p"), claim_run("(C) 2025 Acme", "body > footer > b"),
              claim_run("COPYRIGHT © 2024-2026", "body > footer > i"), claim_run("©2026", "body > footer > u")]
    got = claims_of_page(tmp_path, footer)
    assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 0, got["detail"]
    off = claims_of_page(tmp_path, [claim_run("Founded in 2026. © 2025 Acme", "body > p"), claim_run("Since 2024, copyright 2024", "body > b"), claim_run("Copyright holders: 2026 members", "body > i")])
    assert [o["number"] for o in off["unbacked_numbers"]] == ["2026", "2024", "2026"] and [o["selector"] for o in off["unbacked_numbers"]] == ["body > p", "body > b", "body > i"], off["detail"]   # only a year right after the sign is not a claim
    big = [claim_run("Błąd 404", "body > main > p"), claim_run("404", "body > main > div")]
    assert claims_of_page(tmp_path, big, title="Błąd 404 | Acme", h1=["404"], lang="pl")["claims_checked"]["numbers"] == 0
    assert claims_of_page(tmp_path, big, title="Błąd 404 | Acme", lang="pl")["status"] == "pass" and claims_of_page(tmp_path, big, title="Acme", h1=["Strona nie istnieje 404"], lang="pl")["status"] == "pass"   # the title alone, or the h1 alone
    lonely = claims_of_page(tmp_path, big, title="Acme", h1=["Strona nie istnieje"], lang="pl")   # an error word of the page's language, and no code in the title or h1
    assert lonely["status"] == "fail" and [o["number"] for o in lonely["unbacked_numbers"]] == ["404", "404"], lonely["detail"]    # a page that does not say it in its title or h1 is not an error page
    other = [*big, claim_run("500 firms trust us", "body > main > b"), claim_run("Costs 404 zł", "body > main > i"), claim_run("Version 404.5", "body > main > u"),
             claim_run("Tel. 600 123 456, 00-950 Warszawa, ul. Polna 12", "body > main > s")]
    got = claims_of_page(tmp_path, other, title="Błąd 404 | Acme", h1=["404"], lang="pl")
    assert [o["number"] for o in got["unbacked_numbers"]] == ["500", "404 zł", "404.5", "600 123 456", "00", "950", "12"], got["detail"]   # only that same bare number; phone, postal and street numbers are claims
    for number in ("200", "399", "600"):   # the only number of the title, with an error word of the page's language: still no status code, which is 400 to 599
        not_error = claims_of_page(tmp_path, [claim_run(f"Hello {number}", "body > p")], title=f"Error {number}")
        assert not_error["status"] == "fail" and [o["number"] for o in not_error["unbacked_numbers"]] == [number], (number, not_error["detail"])
    for number in ("400", "599"):
        assert claims_of_page(tmp_path, [claim_run(f"Hello {number}", "body > p")], title=f"Error {number}")["status"] == "pass", number
    # O10: the error word stands right beside the code, with nothing but spaces, a separator (- – — · • | : / and parentheses) or a filler word (page, site, strona, witryna) between them; an error word elsewhere in the text makes it a count
    for lang, title, code in (("en", "Error 404", "404"), ("en", "404 Not Found", "404"), ("pl", "404 · Nie znaleziono", "404"), ("pl", "Błąd 404 – strona nie istnieje", "404"),
                              ("en", "Service Unavailable 503", "503"), ("en", "Error: 500", "500"), ("pl", "Błąd | 404", "404"),
                              ("en", "404 Page Not Found", "404"), ("en", "404 - Page not found", "404"), ("en", "404 — Not Found", "404"), ("en", "404 / Not Found", "404"),
                              ("en", "Not Found (404)", "404"), ("en", "404 SITE NOT FOUND", "404"), ("pl", "404 – Strona nie istnieje", "404"), ("pl", "Błąd 404 – strona nie istnieje", "404"),
                              ("pl", "404 • Witryna niedostępna", "404")):
        page = claims_of_page(tmp_path, [claim_run(f"Hello {code}", "body > p")], title=title, lang=lang)
        assert page["status"] == "pass", (title, page["detail"])
    for lang, title, number in (("en", "450 tickets, all gone", "450"), ("en", "Gone in 450 seconds", "450"), ("pl", "Ponad 400 produktów, żaden niedostępny", "400"),
                                ("en", "Error in 404 places", "404"), ("pl", "500 firm. Błąd", "500"), ("en", "404 page views, all gone", "404")):
        count = claims_of_page(tmp_path, [claim_run(f"Hello {number}", "body > p")], title=title, lang=lang)
        assert count["status"] == "fail" and [o["number"] for o in count["unbacked_numbers"]] == [number], (title, count["detail"])


def claims_of_file(tmp_path: Path, runs: list, page: str = "pages/x.html", title: str = "", h1=(), lang: str = "en", url: str | None = None, kind: str = "project") -> dict:
    """page:claims on constructed measurements of a page with the given file name (a page of the project, of --from, or a URL on this machine): the row."""
    target = pagecheck.Target("url", f"url:{url}", url=url) if url else pagecheck.Target(kind, page, page=page)
    rep = Report("page-check/x-000000", tmp_path)
    ctx = pagecheck.Ctx(tmp_path, target, [390], ["light"], qa_rules.DEFAULTS, TOKENS)
    pagecheck.claim_rows(rep, {"views": [view(lang=lang, claim_text=list(runs), samples=[], document={"title": title}, claim_h1=list(h1))]}, ctx)
    return rep.results[0]


def test_a_page_named_after_a_status_code_is_an_error_page_whatever_its_title_and_heading_say(tmp_path):
    write_facts(tmp_path, ("name", "Acme hand tools"))
    label = [claim_run("Błąd 404", "body > main > p"), claim_run("404", "body > main > div > span"), claim_run("Strony nie ma", "body > main > h1")]   # a small label and a big code, neither in the title nor the h1
    for page, kind in (("404.html", "project"), ("pages/404.html", "project"), ("404.html", "from"), ("sub/dir/404.htm", "from"), ("404", "project")):
        got = claims_of_file(tmp_path, label, page, title="Acme", h1=["Strony nie ma"], kind=kind)
        assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 0, (page, kind, got["detail"])
    for url in ("http://localhost:8000/404.html", "http://127.0.0.1:5173/docs/404.html?x=1", "http://localhost:8000/404"):
        assert claims_of_file(tmp_path, label, title="Acme", h1=["Strony nie ma"], url=url)["status"] == "pass", url
    five = claims_of_file(tmp_path, [claim_run("Błąd 500", "body > p"), claim_run("Kod 500 i 404", "body > b")], "500.html", title="Acme")
    assert [o["number"] for o in five["unbacked_numbers"]] == ["404"], five["detail"]   # the code of the file name only: 404 is a claim on a 500 page
    for page in ("index.html", "404-old.html", "old-404.html", "4040.html", "40.html", "404.5.html", "pages/404/index.html", "200.html", "600.html", "399.html"):
        got = claims_of_file(tmp_path, label, page, title="Acme", h1=["Strony nie ma"])
        assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["404", "404"], (page, got["detail"])   # not a status code by its name: a page with no title or h1 code
    for url in ("http://localhost:8000/", "http://localhost:8000/404/", "http://localhost:8000/index.html?page=404"):
        assert claims_of_file(tmp_path, label, title="Acme", h1=["Strony nie ma"], url=url)["status"] == "fail", url
    assert pagecheck.target_stem(None) == "" and pagecheck.target_stem(pagecheck.Target("project", "a/404.html", page="a/404.html")) == "404"


def test_a_code_in_the_title_or_an_h1_counts_only_when_it_is_the_only_number_there(tmp_path):
    write_facts(tmp_path, ("name", "Acme hand tools"))
    big = [claim_run("Błąd 500+ firm nam ufa", "body > main > h1"), claim_run("Kod 500", "body > main > p")]
    plus = claims_of_file(tmp_path, big, h1=["Błąd 500+ firm nam ufa"], lang="pl")   # every heading of the plus cases holds an error word of the page's language: only the plus decides
    assert plus["status"] == "fail" and [o["number"] for o in plus["unbacked_numbers"]] == ["500", "500"], plus["detail"]   # a count with a plus is no status code
    assert claims_of_file(tmp_path, big, title="Błąd 500 + firm", h1=["Błąd 500 + firm nam ufa"], lang="pl")["status"] == "fail"
    lead = claims_of_file(tmp_path, big, h1=["Błąd +500 klientów"], lang="pl")
    assert lead["status"] == "fail" and [o["number"] for o in lead["unbacked_numbers"]] == ["500", "500"], lead["detail"]   # a plus before the number is a count too
    assert claims_of_file(tmp_path, big, title="Błąd + 500 klientów", lang="pl")["status"] == "fail" and claims_of_file(tmp_path, big, title="Error 500+", lang="en")["status"] == "fail"
    for lang, text in (("pl", "Błąd 500+ firm"), ("pl", "+500 · Błąd"), ("pl", "Błąd + 500 firm"), ("pl", "Błąd 500 + firm"),
                       ("en", "Error 500+"), ("en", "Error +500"), ("en", "Error + 500"), ("en", "Error 500 +")):
        assert pagecheck.status_codes([{"lang": lang, "claim_h1": [text]}]) == set() and pagecheck.status_codes([{"lang": lang, "document": {"title": text}}]) == set(), (lang, text)
        assert pagecheck.status_codes([{"lang": lang, "claim_h1": [text.replace("+", "")]}]) == {"500"}, (lang, text)   # the same words without the plus are the code: only the plus decides
    assert pagecheck.status_codes([{"lang": "pl", "claim_h1": ["500 firm. Błąd"]}]) == set()   # O10: an error word away from the number ("firm." between) makes it a count
    for title, h1, lang in (("Błąd 404 | Acme", [], "pl"), ("Acme", ["Strona nie istnieje 404"], "pl"), ("Acme", ["Error 500 – Acme"], "en"), ("404 – Nie znaleziono", ["404"], "pl")):
        code = "404" if "404" in title + "".join(h1) else "500"
        got = claims_of_file(tmp_path, [claim_run(f"Błąd {code}", "body > main > p"), claim_run(code, "body > div")], title=title, h1=h1, lang=lang)
        assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 0, (title, h1, got["detail"])
    two = [claim_run("Błąd 404", "body > main > p"), claim_run("Kod 500", "body > b")]
    for title, h1, lang in (("Acme 2026 – Błąd 404", [], "pl"), ("Acme", ["Błąd: 404 or 500"], "pl"), ("Acme", ["Błąd 404 – od 2026"], "pl"), ("Acme", ["Błąd 404, 404"], "pl"),
                            ("Acme", ["5 lat, błąd 404"], "pl"), ("Acme", ["Error 404 (1 of 3)"], "en"), ("Acme", ["Błąd 404 – © 2026 Acme"], "pl"), ("Acme", ["Błąd 404 – 5 maja"], "pl")):
        got = claims_of_file(tmp_path, two, title=title, h1=h1, lang=lang)
        assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["404", "500"], (title, h1, got["detail"])   # other numbers in the same text, a single digit or a copyright year too: it says nothing of an error
    single = claims_of_file(tmp_path, [claim_run("Od 500 sztuk", "body > main > p")], h1=["5 lat, 500 klientów"])
    assert single["status"] == "fail" and [o["number"] for o in single["unbacked_numbers"]] == ["500"], single["detail"]   # the 5 is no claim, but it is a number of the h1: 500 is not its code
    assert pagecheck.status_codes([{"lang": "pl", "claim_h1": ["5 lat, 500 klientów"]}]) == set() and pagecheck.status_codes([{"lang": "en", "claim_h1": ["Error 500 (1 of 3)"]}]) == set()
    mixed = claims_of_file(tmp_path, two, title="Błąd 404 | Acme", h1=["500+ firm nam ufa"], lang="pl")
    assert [o["number"] for o in mixed["unbacked_numbers"]] == ["500"], mixed["detail"]   # the title still holds the code, the h1 holds none


def test_a_code_in_a_title_or_an_h1_needs_an_error_word_of_the_pages_language_and_a_count_exempts_nothing(tmp_path):
    write_facts(tmp_path, ("name", "Acme hand tools"))
    codes = lambda lang, *h1, title="": pagecheck.status_codes([{"lang": lang, "document": {"title": title}, "claim_h1": list(h1)}])
    for lang, text, number in (("pl", "Ponad 400 projektów", "400"), ("pl", "Zaufało nam 500 firm", "500"), ("en", "Over 400 clients", "400")):   # a count in a heading says nothing of an error
        assert codes(lang, text) == set() and codes(lang, title=text) == set(), (lang, text)
        got = claims_of_file(tmp_path, [claim_run(text, "body > main > h1")], title="Acme", h1=[text], lang=lang)
        assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == [number], (text, got["detail"])   # the number is a claim, as anywhere else
        assert claims_of_file(tmp_path, [claim_run(text, "body > main > h1")], title=text, lang=lang)["status"] == "fail", text
    for lang, text, number in (("pl", "404 · Nie znaleziono", "404"), ("en", "Error 500", "500"), ("pl", "Błąd 404 – strona nie istnieje", "404")):   # the code with an error word of the page's language
        assert codes(lang, text) == {number} and codes(lang, title=text) == {number}, (lang, text)
        runs = [claim_run(text, "body > main > h1"), claim_run(number, "body > main > div")]
        for title, h1 in ((text, ()), ("Acme", (text,))):
            got = claims_of_file(tmp_path, runs, title=title, h1=h1, lang=lang)
            assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 0, (text, got["detail"])
    for lang, words in (("en", ("error", "not found", "forbidden", "unauthorized", "unavailable", "gone", "bad request", "server error")),
                        ("pl", ("błąd", "nie znaleziono", "nie istnieje", "brak dostępu", "odmowa dostępu", "niedostępna", "niedostępny"))):   # every listed word, in any letter case
        for word in words:
            for text in (f"{word} 403", f"403 – {word}", f"{word.upper()} 403", f"{word.capitalize()}: 403!", f"{word.replace(' ', chr(160))} 403"):
                assert codes(lang, text) == {"403"} and codes(lang, title=text) == {"403"}, (lang, text)
    assert codes("pl", "Error 500", "Not found 404") == set() and codes("en", "Błąd 500", "404 · Nie znaleziono") == set()   # the words of the page's language only
    for lang in ("de", "fr", ""):
        assert codes(lang, "Error 500", "Błąd 404", "Seite nicht gefunden 404", title="Not found 404") == set(), lang   # another language, or none: the file name only
    assert codes("pl-PL", "Błąd 404") == {"404"} and codes("EN-gb", "Error 404") == {"404"}                          # the primary language of the page decides
    assert codes("en", "500", title="Error | Acme") == set() and codes("en", "Error", "500") == set()                  # the word and the number are in the same text
    assert codes("en", "Terror 404", "Fiasco 500") == set() and codes("pl", "Nobłąd 404") == set()                 # a whole word, not a part of one
    assert codes("en", "Error 404 and Gone 500") == set() and codes("en", "Error 404, 2026") == set()                  # an error word does not lift the rule of the only number
    for text in ("Error 404 zł", "Error 404.5", "Error 404%", "Error €404", "Error 404 km", "Error 404k"):                # a number with a sign, a code or a unit is not a bare number
        assert codes("en", text) == set(), text
    assert [codes("en", f"Error {n}") for n in ("399", "600", "200")] == [set()] * 3 and [codes("en", f"Error {n}") for n in ("400", "599")] == [{"400"}, {"599"}]   # a status code is 400 to 599
    assert pagecheck.status_codes([{"claim_h1": ["Error 500"]}]) == set()                                              # a view that names no language
    label = [claim_run("Kod 404", "body > main > p"), claim_run("Over 400 clients", "body > main > h1")]
    for lang in ("en", "de", ""):   # the file name says it whatever the language, and the title and h1 need not hold the code
        got = claims_of_file(tmp_path, label, "404.html", title="Acme", h1=["Over 400 clients"], lang=lang)
        assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["400"], (lang, got["detail"])   # 404 is exempt, the count is still a claim
    assert pagecheck.status_codes([{"lang": "de", "claim_h1": ["Seite nicht gefunden"]}], pagecheck.Target("project", "404.html", page="404.html")) == {"404"}


def test_a_date_with_a_month_name_is_one_date_in_polish_and_english(tmp_path):
    num = lambda text, lang=None, **kw: [(n["text"], n["number"], n.get("parts")) for n in pagecheck.numbers_in(text, lang=lang, **kw)]
    assert num("Premiera 21 października 2026, 18:00", "pl") == [("21 października 2026", "21.10.2026", ["21", "10", "2026"]), ("18", "18", None), ("00", "00", None)]
    assert num("Wypłata 21 października i 5 maja", "pl") == [("21 października", "21/10", ["21", "10"]), ("5 maja", "5/5", ["5", "5"])]       # no year: a date too, a single-digit day as well
    assert num("ul. 3 Maja 12", "pl") == [("3 Maja", "3/5", ["3", "5"]), ("12", "12", None)]      # a single-digit day is a claim too, so a street of that name needs a fact like any address
    assert num("Październik 2026, października 2026 i w październiku 2026, GRUDZIEŃ 2026, maj 2026", "pl") == [
        ("Październik 2026", "10/2026", ["10", "2026"]), ("października 2026", "10/2026", ["10", "2026"]), ("październiku 2026", "10/2026", ["10", "2026"]),
        ("GRUDZIEŃ 2026", "12/2026", ["12", "2026"]), ("maj 2026", "5/2026", ["5", "2026"])]                                              # month and year: the nominative, genitive or locative, any letter case
    assert num("1 maja 2026 r., 1 maja 2026r., 02 lutego 2026", "pl") == [("1 maja 2026", "1.5.2026", ["1", "5", "2026"]), ("1 maja 2026", "1.5.2026", ["1", "5", "2026"]), ("02 lutego 2026", "02.2.2026", ["02", "2", "2026"])]   # the Polish r. is no part of it
    assert [n[2] for n in num("1 stycznia, 2 lutego, 3 marca, 4 kwietnia, 5 maja, 6 czerwca, 7 lipca, 8 sierpnia, 9 września, 10 października, 11 listopada, 12 grudnia", "pl")] == [
        [str(day), str(day)] for day in range(1, 13)]                                                                                  # all twelve genitives
    assert num("October 21, 2026", "en") == [("October 21, 2026", "21.10.2026", ["21", "10", "2026"])]
    assert num("21 October 2026", "en") == [("21 October 2026", "21.10.2026", ["21", "10", "2026"])]                                  # one date, not "21 October" and "October 2026"
    assert num("October 2026, OCTOBER 2026", "en") == [("October 2026", "10/2026", ["10", "2026"]), ("OCTOBER 2026", "10/2026", ["10", "2026"])]
    assert num("October 21, October 21st, 21 October, 21st October 2026, May 10 2026", "en") == [
        ("October 21", "21/10", ["21", "10"]), ("October 21st", "21/10", ["21", "10"]), ("21 October", "21/10", ["21", "10"]), ("21st October 2026", "21.10.2026", ["21", "10", "2026"]),
        ("May 10 2026", "10.5.2026", ["10", "5", "2026"])]
    assert num("We march 5 km and may 12 times, 3 may 2026", "en") == [("5 km", "5", None), ("12", "12", None), ("2026", "2026", None)]   # a lower-case month of English is a word; "may 2026" and "march 5" are not dates
    assert [n[0] for n in num("Dates: Sale ends May 2026. Sept 21, 2026", "en")] == ["May 2026", "21", "2026"]                         # a name that is not in full is not read
    # the page language decides: the other language's names, an unknown language and no language keep the numbers
    for text, lang in (("21 października 2026", "en"), ("October 21, 2026", "pl"), ("21 października 2026", "de"), ("21 października 2026", ""), ("21 października 2026", None)):
        assert [n[0] for n in num(text, lang)] == ["21", "2026"], (text, lang)
    assert [n[0] for n in num("21 października 2026 and October 5", pagecheck.ANY_LANGUAGE, every=True)] == ["21 października 2026", "October 5"]   # a FACTS.md value has no language
    assert pagecheck.month_dates("21 października", "fr") == [] and pagecheck.month_dates("21 października", "") == []


def test_a_date_with_a_month_name_is_backed_by_the_numbers_of_the_date_in_the_facts(tmp_path):
    write_facts(tmp_path, ("release", "premiera 2026-10-21"))
    pl = [claim_run("Premiera 21 października 2026", "body > a"), claim_run("Premiera 21 października", "body > b"), claim_run("Październik 2026", "body > i"), claim_run("w październiku 2026 r.", "body > u")]
    got = claims_of_page(tmp_path, pl, lang="pl")
    assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 4, got["detail"]                                           # each date is one number checked, backed by 2026, 10 and 21
    en = [claim_run("October 21, 2026", "body > a"), claim_run("21 October 2026", "body > b"), claim_run("October 2026", "body > i"), claim_run("21st of October", "body > p")]
    got = claims_of_page(tmp_path, en, lang="en")
    assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 3, got["detail"]                                           # "21st of October" is read as nothing (as it was)
    off = claims_of_page(tmp_path, [claim_run("Premiera 22 października 2026", "body > a"), claim_run("Listopad 2026", "body > b"), claim_run("21 grudnia", "body > i"), claim_run("Premiera 21 października 2026", "body > u")], lang="pl")
    assert off["status"] == "fail" and [o["number"] for o in off["unbacked_numbers"]] == ["22 października 2026", "Listopad 2026", "21 grudnia"], off["detail"]   # one finding per date, as written
    assert [o["context"] for o in off["unbacked_numbers"]][0] == "Premiera 22 października 2026"
    write_facts(tmp_path, ("days", "ponad 21 dni"), ("year", "od 2026"))
    assert claims_of_page(tmp_path, [claim_run("21 października 2026")], lang="pl")["status"] == "fail"       # 21 and 2026 are held, 10 is not: the date needs its month
    assert claims_of_page(tmp_path, [claim_run("21 października 2026")], lang="de")["status"] == "warn"       # another language keeps the numbers: 21 and 2026 are held (and its status words are not verified)
    assert claims_of_page(tmp_path, [claim_run("October 21, 2026")], lang="pl")["status"] == "pass"           # the other language's names are numbers in a Polish page
    write_facts(tmp_path, ("release", "premiera 21 października 2026"), ("start", "start: May 5, 2026"))
    dotted = claims_of_page(tmp_path, [claim_run("Premiera 21.10.2026", "body > a"), claim_run("Premiera 2026-10-21", "body > b"), claim_run("Start 5 maja", "body > i"), claim_run("Start 05.05.2026", "body > u"),
                                       claim_run("Premiera October 21, 2026", "body > s")], lang="pl")
    assert dotted["status"] == "pass", dotted["detail"]                                                                              # a date written with a month name in the facts backs the other forms
    write_facts(tmp_path, ("release", "premiera 21 października"))
    assert claims_of_page(tmp_path, [claim_run("Premiera 21.10")], lang="pl")["status"] == "pass"           # and a dotted 21.10 is backed by its two parts


def test_a_number_that_runs_past_a_month_name_is_not_part_of_the_date_and_a_day_with_a_comma_and_a_year_is(tmp_path):
    num = lambda text, lang="en", **kw: [(n["text"], n["number"], n.get("parts")) for n in pagecheck.numbers_in(text, lang=lang, **kw)]
    october = lambda text: (text, "21.10.2026", ["21", "10", "2026"])
    assert num("March 15% of users") == [("15%", "15", None)] and num("March 15 % of users") == [("15 %", "15", None)] and num("March 15‰ of users") == [("15‰", "15", None)]   # a percent is the claim, not the day of March
    assert num("May 3.5 kg") == [("3.5 kg", "3.5", None)] and num("October 12,5 users") == [("12,5", "12.5", None)]                      # a decimal number is not a day
    assert num("March 15.11.2026") == [("15.11.2026", "15.11.2026", ["15", "11", "2026"])]                                            # a dotted date is a dotted date, not the day of March
    assert num("October 21.2026") == [("21.2026", "21.2026", None)] and pagecheck.month_dates("October 21,20265", "en") == []        # a digit glued to the day, and a year of five digits
    assert num("October 21,2026") == [october("October 21,2026")] and num("October 21, 2026") == [october("October 21, 2026")]        # a comma and a year, with a space or without one, is the full date
    assert num("October 21 2026") == [october("October 21 2026")] and num("October 21st,2026") == [october("October 21st,2026")]
    assert num("Ends October 21,2026.") == [october("October 21,2026")] and num("Ends on October 21, 2026, at noon") == [october("October 21, 2026")]
    assert num("Sale ends October 21. 12 pieces left") == [("October 21", "21/10", ["21", "10"]), ("12", "12", None)]                  # a full stop after the day ends the sentence
    assert num("October 21, 15% off") == [("October 21", "21/10", ["21", "10"]), ("15%", "15", None)]                                   # a comma after the day, then a number that is not a year
    assert num("October 21, 5 people came") == [("October 21", "21/10", ["21", "10"])]                                                # (the 5 is a bare single digit)
    assert num("21 October 15% off") == [("21 October", "21/10", ["21", "10"]), ("15%", "15", None)]
    assert num("March 15% of users and October 21,2026", pagecheck.ANY_LANGUAGE, every=True) == [("15%", "15", None), october("October 21,2026")]   # a FACTS.md value reads them the same way
    # a Polish day is followed by the genitive of the month: the nominative or the locative after a day is no date
    assert num("21 października", "pl") == [("21 października", "21/10", ["21", "10"])]
    assert num("21 październik", "pl") == [("21", "21", None)] and num("21 październiku", "pl") == [("21", "21", None)]
    assert num("21 październik 2026", "pl") == [("21", "21", None), ("październik 2026", "10/2026", ["10", "2026"])]                 # the nominative with a year is the month and the year, and the 21 stays a number
    assert num("5 październik", "pl") == []                                                                                              # a bare single digit is no claim
    write_facts(tmp_path, ("users", "we have 200 users"), ("release", "premiera 2026-10-21"))
    got = claims_of_page(tmp_path, [claim_run("March 15% of users", "body > p")], lang="en")
    assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["15%"], got["detail"]                       # judged as a percent: 15 is no fact
    got = claims_of_page(tmp_path, [claim_run("October 21,2026", "body > p"), claim_run("October 21, 2026", "body > b")], lang="en")
    assert got["status"] == "pass" and got["claims_checked"]["numbers"] == 2, got["detail"]                                           # one date each, backed by 2026, 10 and 21
    got = claims_of_page(tmp_path, [claim_run("October 21,2027", "body > p")], lang="en")
    assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["October 21,2027"], got["detail"]          # the year is part of the date: 2027 is no fact
    write_facts(tmp_path, ("days", "ponad 21 dni"), ("month", "miesiąc 10"), ("share", "15% of users"))
    got = claims_of_page(tmp_path, [claim_run("October 21,2026", "body > p"), claim_run("March 15% of users", "body > b")], lang="en")
    assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["October 21,2026"], got["detail"]         # the 2026 is no fact, and the percent is backed


def test_a_dotted_date_has_two_digits_each_or_a_year_and_a_bare_decimal_stays_a_decimal(tmp_path):
    num = lambda text, **kw: [(n["text"], n["number"], n.get("parts")) for n in pagecheck.numbers_in(text, **kw)]
    assert num("12.5, 2.10, 10.1, 1.12, 4.5, 31.1, 9.99") == [("12.5", "12.5", None), ("2.10", "2.1", None), ("10.1", "10.1", None), ("1.12", "1.12", None), ("4.5", "4.5", None),
                                                           ("31.1", "31.1", None), ("9.99", "9.99", None)]   # one digit in the day or the month, and no year: a decimal only
    assert num("30.10, 05.11, 31.12, 12.12") == [("30.10", "30.1", ["30", "10"]), ("05.11", "05.11", ["05", "11"]), ("31.12", "31.12", ["31", "12"]), ("12.12", "12.12", ["12", "12"])]   # two digits each: a date, and still a decimal
    assert num("1.5.2026, 2.10.2026, 10.1.2026, 15.11.2026") == [("1.5.2026", "1.5.2026", ["1", "5", "2026"]), ("2.10.2026", "2.10.2026", ["2", "10", "2026"]),
                                                               ("10.1.2026", "10.1.2026", ["10", "1", "2026"]), ("15.11.2026", "15.11.2026", ["15", "11", "2026"])]   # a year: any number of digits
    assert num("1.5.2026r., 2.10.2026 r., 5.11.2026r.") == [("1.5.2026", "1.5.2026", ["1", "5", "2026"]), ("2.10.2026", "2.10.2026", ["2", "10", "2026"]), ("5.11.2026", "5.11.2026", ["5", "11", "2026"])]   # the r. is no part of it
    assert [(t, parts) for t, _, parts in num("1.5.1850, 1.5.20266")] == [("1.5.1850", None), ("1.5.20266", None)]   # not a year of ours: a plain number
    write_facts(tmp_path, ("release", "premiera 2026-12-05"), ("grade", "ocena 10.1"))
    runs = [claim_run("Ocena 12.5", "body > a"), claim_run("Ocena 2.10", "body > b"), claim_run("Ocena 10.1", "body > i"), claim_run("Premiera 12.05", "body > u"), claim_run("Premiera 5.12.2026", "body > s")]
    got = claims_of_page(tmp_path, runs, lang="pl")
    assert got["status"] == "fail" and [o["number"] for o in got["unbacked_numbers"]] == ["12.5", "2.10"], got["detail"]   # 12.5 and 2.10 are decimals no fact holds (the date 2026-12-05 is not a decimal); 10.1 is held as one
    write_facts(tmp_path, ("rating", "ocena 12.5 na 5"))
    assert claims_of_page(tmp_path, [claim_run("Ocena 12.5"), claim_run("Ocena 12", "body > b")], lang="pl")["unbacked_numbers"] == [
        {"number": "12", "selector": "body > b", "context": "Ocena 12", "width": 390}]                                   # a decimal in the facts is that decimal alone: 12.5 does not hold 12
    write_facts(tmp_path, ("payout", "wypłata 30.10"))
    held = claims_of_page(tmp_path, [claim_run("Wypłata 30"), claim_run("Dzień 10 zł", "body > i"), claim_run("Wypłata 5.11", "body > b")], lang="pl")
    assert [o["number"] for o in held["unbacked_numbers"]] == ["5.11"], held["detail"]   # a date in the facts (two digits each) still holds its day and its month; 5.11 is a decimal no fact holds


def test_a_view_that_measured_no_text_or_motion_is_not_verified_and_never_a_pass(tmp_path):
    for check, row_id in ((pagecheck.claim_rows, "page:claims"), (pagecheck.motion_rows, "page:motion")):
        for measures in ({"views": []}, {"views": [view()]}, {"views": [{"width": 390, "scheme": "light", "viewport": {"width": 390, "height": 844}, "error": "timed out"}]}):
            rep = Report("page-check/x-000000", tmp_path)
            ctx = synthetic_ctx(tmp_path, TOKENS)
            check(rep, measures, ctx)
            assert [(r["id"], r["status"]) for r in rep.results] == [(row_id, "skipped")] and rep.exit_code() == 3
            assert "not verified" in rep.results[0]["detail"]
            if check is pagecheck.claim_rows:
                assert ctx.extra["samples"] == []   # the key is always there: group 3 reads it


def test_a_keyword_easing_is_a_curve_only_when_a_token_holds_its_curve(tmp_path):
    standard = {"easing.standard": [0.2, 0, 0, 1]}
    assert motion_row(tmp_path, with_motion(standard), decl())["status"] == "pass"                                                   # cubic-bezier equal to the token, 150 ms is a token
    got = motion_row(tmp_path, with_motion(standard), decl(easing="ease"), decl(easing="linear", sel="body > b"), decl(easing="steps(4)", sel="body > i"))
    assert got["status"] == "fail" and [o["easing"] for o in got["offenders"]] == ["ease", "linear", "steps(4)"] and "no curve token (easing.standard cubic-bezier(0.2, 0, 0, 1))" in got["detail"]
    held = with_motion({**standard, "easing.ease": [0.25, 0.1, 0.25, 1], "easing.flat": [0, 0, 1, 1]})   # a token that equals the keyword's curve makes it a token
    assert motion_row(tmp_path, held, decl(easing="ease"), decl(easing="linear", sel="body > b"))["status"] == "pass"
    assert motion_row(tmp_path, held, decl(easing="steps(4, end)"))["status"] == "fail"                                              # steps() is no curve, whatever the tokens hold
    got = motion_row(tmp_path, with_motion(standard), decl(duration=151.0), decl(duration=0.5, sel="body > b"), decl(duration=320.0, sel="body > i"))
    assert got["status"] == "fail" and [o["duration_ms"] for o in got["offenders"]] == [151.0, 0.5] and "no motion duration token (duration.fast 150 ms, duration.base 320 ms)" in got["detail"]
    assert got["used"] == ["duration.base (320 ms)", "easing.standard (cubic-bezier(0.2, 0, 0, 1))"]
    nothing = Report("page-check/x-000000", tmp_path)   # a malformed motion block names no token
    pagecheck.motion_rows(nothing, {"views": [view(motion_decls=[decl()])]}, synthetic_ctx(tmp_path, {**TOKENS, "motion": {"durations_ms": {"a": "fast"}, "curves": {"b": [0, 1]}}}))
    assert nothing.results[0]["status"] == "fail" and "no motion tokens" in nothing.results[0]["detail"]


def test_a_page_that_moves_while_the_brand_has_no_motion_tokens_fails_and_says_so(tmp_path):
    for tokens in (TOKENS, with_motion({}, {})):
        got = motion_row(tmp_path, tokens, decl(source="animation", name="spin", duration=2000, easing="linear", sel="body > svg"), decl())
        assert got["status"] == "fail" and "the page moves" in got["detail"] and "no motion tokens" in got["detail"] and "animation spin on body > svg" in got["detail"], got["detail"]
        calm = motion_row(tmp_path, tokens)   # a page that does not move needs none
        assert calm["status"] == "pass" and "no transition or animation" in calm["detail"]


def test_a_scroll_driven_animation_and_smil_are_not_verified_and_only_warn(tmp_path):
    tokens = with_motion({"easing.standard": [0.2, 0, 0, 1]})
    got = motion_row(tmp_path, tokens, decl(), decl(source="animation", name="grow", duration=None, sel="body > i"))   # duration "auto": a scroll or view timeline
    assert got["status"] == "warn" and "run on a scroll or view timeline and have no duration" in got["detail"] and got["durations_checked"] == 1
    got = motion_row(tmp_path, tokens, decl(), motion_smil=2)
    assert got["status"] == "warn" and "2 SVG SMIL animation element(s)" in got["detail"]
    assert motion_row(tmp_path, tokens, decl(duration=151), motion_smil=2)["status"] == "fail"   # a real offender still fails


def test_a_state_rule_that_sets_only_a_duration_or_only_an_easing_is_checked_for_that_part_alone(tmp_path):
    tokens = with_motion({"easing.standard": [0.2, 0, 0, 1]})
    only_duration = lambda ms, **kw: decl(duration=ms, easing=None, name="", sel="a:hover", via="state", unset=["easing"], **kw)   # a:hover { transition-duration: ... }
    only_easing = lambda e, **kw: decl(duration=None, easing=e, name="", sel="b:hover", via="state", unset=["duration"], **kw)      # b:hover { transition-timing-function: ... }
    assert motion_row(tmp_path, tokens, only_duration(150), only_easing(STANDARD_CURVE))["status"] == "pass"   # the other half is the base rule's, which is read at rest
    got = motion_row(tmp_path, tokens, only_duration(999), only_easing("ease-in"))
    assert got["status"] == "fail" and [o["problems"] for o in got["offenders"]] == [[got["offenders"][0]["problems"][0]], [got["offenders"][1]["problems"][0]]]
    assert "lasts 999 ms" in got["offenders"][0]["problems"][0] and "eases with" not in got["offenders"][0]["problems"][0]   # a half that was not set is not a failure
    assert "eases with ease-in" in got["offenders"][1]["problems"][0] and "lasts" not in got["offenders"][1]["problems"][0]
    assert "transition on a:hover" in got["detail"] and "transition on b:hover" in got["detail"] and got["durations_checked"] == 1
    scroll = motion_row(tmp_path, tokens, only_easing(STANDARD_CURVE))   # no duration set is not a scroll-driven animation
    assert scroll["status"] == "pass" and "scroll or view" not in scroll["detail"]
    several = motion_row(tmp_path, tokens, only_duration(999, count=3))
    assert "(3 rules)" in several["detail"]                                                                      # a state is a rule, not an element
    assert "(3 elements)" in motion_row(tmp_path, tokens, decl(duration=999, count=3))["detail"]


def test_a_stylesheet_the_walk_could_not_read_is_not_verified_and_never_a_pass(tmp_path):
    tokens = with_motion({"easing.standard": [0.2, 0, 0, 1]})
    got = motion_row(tmp_path, tokens, motion_unread=2)
    assert got["status"] == "warn" and "NOT verified: 2 stylesheet(s) could not be read" in got["detail"] and "hover" in got["detail"], got["detail"]
    got = motion_row(tmp_path, tokens, decl(duration=999), motion_unread=1)
    assert got["status"] == "fail" and "NOT verified: 1 stylesheet(s)" in got["detail"]


# ---- with a browser


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_motion_declared_on_a_state_is_read_without_hovering_it(acme):
    add_motion_tokens(acme)
    page = write_page(acme)
    page.write_text(PAGE.replace("</style>", """  a { transition: color var(--duration-fast) var(--easing-standard); }
  a:hover { transition: color 999ms ease; }
  h1:hover { animation: pulse 777ms ease-in; }
  @keyframes pulse { from { opacity: 1 } to { opacity: .5 } }
</style>"""), encoding="utf-8")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:motion")
    assert bad["status"] == "fail", bad
    found = {(o["selector"], o["source"], o["name"], o["duration_ms"], o["easing"], o["via"]) for o in bad["offenders"]}
    assert ("a:hover", "transition", "color", 999, "ease", "state") in found and ("h1:hover", "animation", "pulse", 777, "ease-in", "state") in found, bad["offenders"]
    assert "transition of color on a:hover lasts 999 ms" in bad["detail"] and "animation pulse on h1:hover lasts 777 ms" in bad["detail"] and "eases with ease-in" in bad["detail"]
    page.write_text(PAGE.replace("</style>", """  a { transition: color var(--duration-fast) var(--easing-standard); }
  a:hover, a:focus-visible { transition: color var(--duration-fast) var(--easing-standard); }
  h1:hover { animation: pulse var(--duration-fast) var(--easing-standard); }
  @keyframes pulse { from { opacity: 1 } to { opacity: .5 } }
</style>"""), encoding="utf-8")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = row(rep, "page:motion")
    assert ok["status"] == "pass" and ok["used"] == ["duration.fast (150 ms)", f"easing.standard ({STANDARD_CURVE})"], ok
    assert {(d["selector"], d["via"]) for d in ok["declarations"]} == {("body > main > p:nth-of-type(2) > a", "style"), ("h1:hover", "state")}   # the same declaration as a rest rule is listed once


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_state_rule_is_read_wherever_the_stylesheet_keeps_it(acme):
    add_motion_tokens(acme)
    page = write_page(acme)
    page.write_text(PAGE.replace("</style>", """  .card { --slow: 888ms; }
  .card:hover { transition-duration: var(--slow); }
  .box { color: red; &:hover { transition: opacity 444ms var(--easing-standard); } & .inner:focus-visible { animation: pulse 333ms var(--easing-standard); } }
  @media (hover: hover) { .m:hover { transition: color 222ms var(--easing-standard); } }
  @media (prefers-reduced-motion: reduce) { .reduced:hover { transition: color 111ms var(--easing-standard); } }
  @media print { .printed:hover { transition: color 112ms var(--easing-standard); } }
  @supports (display: grid) { .s:active { transition: color 555ms var(--easing-standard); } }
  @supports (not-a-property: nope) { .t:active { transition: color 556ms var(--easing-standard); } }
  @layer base { .l:focus { transition: color 666ms var(--easing-standard); } }
  .quiet:hover { color: red; } .calm:hover { transition: none; animation: none; } .instant:hover { transition: color 0s; }
  @keyframes pulse { from { opacity: 1 } to { opacity: .5 } }
</style>""").replace("</main>", """<div class="card"><i>c</i></div><script>
  const sheet = new CSSStyleSheet(); sheet.replaceSync(".adopted:hover { transition: color 777ms var(--easing-standard); }");
  document.adoptedStyleSheets = [sheet];
</script></main>"""), encoding="utf-8")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:motion")
    got = {(o["selector"], o["source"], o["duration_ms"]) for o in bad["offenders"]}
    assert got == {(".card:hover", "transition", 888), (".box:hover", "transition", 444), (".box .inner:focus-visible", "animation", 333), (".m:hover", "transition", 222),
                   (".s:active", "transition", 555), (".l:focus", "transition", 666), (".adopted:hover", "transition", 777)}, sorted(got)   # not print, reduced motion, an unsupported @supports, none, 0s
    card = next(o for o in bad["offenders"] if o["selector"] == ".card:hover")
    assert card["problems"] and all("eases with" not in x for x in card["problems"]), card   # only the duration was set: the custom property of .card resolved


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_declaration_written_after_a_nested_rule_in_a_state_rule_is_read(acme):
    """Chromium keeps a declaration written after a nested rule apart from the rule's own (a nested-declarations rule with no selector): the rule's selector is its owner."""
    add_motion_tokens(acme)
    page = write_page(acme)
    page.write_text(PAGE.replace("</style>", """  .box:hover { & span { color: red; } transition: color var(--duration-fast) var(--easing-standard); }
  .tile { &:hover { & b { color: red; } animation: pulse var(--duration-fast) var(--easing-standard); } }
  .card:hover { @media (min-width: 1px) { & i { color: red; } transition: opacity var(--duration-fast) var(--easing-standard); } }
  @keyframes pulse { from { opacity: 1 } to { opacity: .5 } }
</style>"""), encoding="utf-8")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = row(rep, "page:motion")
    assert ok["status"] == "pass" and {(d["selector"], d["via"]) for d in ok["declarations"]} == {(".box:hover", "state"), (".tile:hover", "state"), (".card:hover", "state")}, ok
    mutate(page, "color var(--duration-fast)", "color 999ms")   # the declaration after the nested rule, a duration nobody defined
    mutate(page, "animation: pulse var(--duration-fast)", "animation: pulse 777ms")
    mutate(page, "opacity var(--duration-fast)", "opacity 555ms")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:motion")
    got = {(o["selector"], o["source"], o["duration_ms"]) for o in bad["offenders"]}
    assert bad["status"] == "fail" and got == {(".box:hover", "transition", 999), (".tile:hover", "animation", 777), (".card:hover", "transition", 555)}, (bad["status"], sorted(got))


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_duration_that_is_not_a_token_fails_and_a_token_duration_passes(acme):
    add_motion_tokens(acme)
    page = write_page(acme)
    mutate(page, "a { color: var(--color-accent); }", "a { color: var(--color-accent); transition: color var(--duration-fast) var(--easing-standard); }")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = row(rep, "page:motion")
    assert ok["status"] == "pass" and ok["used"] == ["duration.fast (150 ms)", f"easing.standard ({STANDARD_CURVE})"], ok
    assert [(d["source"], d["name"], d["duration_ms"], d["easing"]) for d in ok["declarations"]] == [("transition", "color", 150, STANDARD_CURVE)]
    mutate(page, "var(--duration-fast)", "200ms")   # a duration nobody defined
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:motion")
    assert bad["status"] == "fail" and [(o["name"], o["duration_ms"]) for o in bad["offenders"]] == [("color", 200)]
    assert "lasts 200 ms, which is no motion duration token (duration.fast 150 ms)" in bad["detail"] and "eases with" not in bad["detail"] and bad["offenders"][0]["selector"].endswith(" > a")
    mutate(page, "200ms var(--easing-standard)", "var(--duration-fast) ease-in")   # a token duration with a keyword no token equals
    r, rep = check_page(acme, "--schemes", "light")
    bad = row(rep, "page:motion")
    assert r.returncode == 1 and bad["status"] == "fail" and "eases with ease-in, which is no curve token (easing.standard cubic-bezier(0.2, 0, 0, 1))" in bad["detail"] and "lasts" not in bad["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_unbacked_number_fails_and_the_same_number_in_a_labelled_sample_is_listed_before_publishing(acme):
    add_fact(acme, "batch size", "tools are made in batches of 200")
    page = write_page(acme)
    mutate(page, "</main>", "<p>Tools are made in batches of 200.</p>\n</main>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and rep["samples"] == [] and not any(x["id"] == "page:samples" for x in rep["results"])   # backed by a fact; no sample, no row
    mutate(page, "batches of 200", "batches of 300")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:claims")
    assert bad["status"] == "fail" and [(o["number"], o["width"]) for o in bad["unbacked_numbers"]] == [("300", 390)] and "Tools are made in batches of 300." in bad["detail"]
    assert bad["unbacked_numbers"][0]["selector"].endswith(" > p:nth-of-type(3)") and "data-sample" in bad["detail"]
    mutate(page, "<p>Tools are made in batches of 300.", '<p data-sample="Batch size">Tools are made in batches of 300.')   # labelled: sample content, not a claim
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass"
    samples = row(rep, "page:samples")
    assert samples["status"] == "info" and "Batch size (Tools are made in batches of 300.)" in samples["detail"] and "390-light" in samples["detail"]
    assert rep["samples"] == samples["samples"] == [{"label": "Batch size", "text": "Tools are made in batches of 300.", "selector": "body > main > p:nth-of-type(3)", "view": "390-light"}]
    both = check_page(acme)[1]   # both themes: the sample is one entry, seen first in the light view
    assert both["samples"] == rep["samples"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_empty_sample_label_fails(acme):
    page = write_page(acme)
    mutate(page, "<p>Every tool has", '<p data-sample="">Every tool has')
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:claims")
    assert bad["status"] == "fail" and "label the sample" in bad["detail"] and [o["selector"] for o in bad["unlabelled_samples"]] == ["body > main > p:nth-of-type(1)"]
    assert rep["samples"] == [] and not any(x["id"] == "page:samples" for x in rep["results"])   # an empty label lists nothing
    mutate(page, 'data-sample=""', 'data-sample="Tagline"')
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0 and row(rep, "page:claims")["status"] == "pass" and [s["label"] for s in rep["samples"]] == ["Tagline"], r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_forbidden_word_on_a_real_page_warns_without_failing_and_a_copy_row_backs_its_number(acme):
    page = write_page(acme)
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    none = row(rep, "page:words")
    assert none["status"] == "info" and "no forbidden words are listed" in none["detail"] and [x["id"] for x in rep["results"]].index("page:words") == [x["id"] for x in rep["results"]].index("page:claims") + 1
    mutate(acme / "brief" / "BRIEF.md", "## Forbidden\n", "## Forbidden\n\n- revolutionary\n- game-changer\n")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:words")["status"] == "pass" and row(rep, "page:words")["forbidden_checked"] == 2
    mutate(page, "</main>", "<p>A Revolutionary way to make hand tools that last 25 years.</p>\n</main>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr   # 25 is no fact yet: the claims row fails, the words row only warns
    bad = row(rep, "page:words")
    assert bad["status"] == "warn" and [(h["word"], h["width"]) for h in bad["forbidden_hits"]] == [("revolutionary", 390)] and "A Revolutionary way to make hand tools" in bad["detail"]
    assert row(rep, "page:claims")["status"] == "fail" and [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["25"]
    add_fact(acme, "copy: hero headline", "A Revolutionary way to make hand tools that last 25 years.")   # the approved wording is a row of FACTS.md; its value backs the number
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr   # the words row is a warning, so the exit code is 0
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:words")["status"] == "warn"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_with_no_motion_and_no_unbacked_claim_passes_both_rows(acme):
    write_page(acme)
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    ids = [x["id"] for x in rep["results"]]
    assert "page:motion" in ids and "page:claims" in ids and ids.index("page:motion") < ids.index("page:claims") and "page:samples" not in ids
    motion = row(rep, "page:motion")
    assert motion["status"] == "pass" and motion["declarations"] == [] and "no transition or animation" in motion["detail"]
    claims_row = row(rep, "page:claims")
    assert claims_row["status"] == "pass" and claims_row["languages"] == {"en": claims_row["languages"]["en"]} and claims_row["unbacked_numbers"] == []
    assert rep["samples"] == []


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_motion_and_claims_collectors_read_what_is_declared_what_runs_and_what_a_block_says(acme):
    page = write_page(acme)
    page.write_text(PAGE.replace("</style>", """  .menu { display: none; transition: opacity 300ms ease-in-out; }
  .btn { transition: transform, opacity; transition-duration: 150ms; }
  .pair { transition: color 1s, background-color 2s linear, outline-color 0s; }
  .pulse::after { content: ""; animation: pulse 1.5s cubic-bezier(0.2, 0, 0, 1) infinite; }
  .quiet::before { transition: opacity 400ms; }
  .none { animation: none; transition: none; }
  .scroll { animation: grow linear both; animation-timeline: scroll(); }
  .nodur { animation: pulse both; } .nodur2 { animation-name: grow; animation-fill-mode: forwards; }
  @keyframes pulse { from { opacity: 1 } to { opacity: .5 } } @keyframes grow { from { scale: 1 } to { scale: 2 } }
  .ghost { opacity: 0; } .gone { display: none; } .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>""").replace("</main>", """<div class="menu">Menu</div><button class="btn">Go</button><p class="pair">Pair</p><p class="pulse">Pulse</p><p class="quiet">Quiet</p>
<p class="none">None</p><p class="scroll">Scroll</p><p class="nodur">No duration</p><p class="nodur2">No duration either</p>
<p class="blk">&euro;<b>5</b> for <i>2</i> items<br>9 pieces and 40 <span class="tag">%</span></p>
<p data-sample="Deal">Save 20% today</p>
<p data-sample="Outer">outer <span data-sample="">inner 88</span> <span>after 66</span></p>
<p class="ghost">Faded 55</p><p class="gone">Gone 99</p><p class="sr">Cut 98</p><details><summary>More</summary><p>Closed 97</p></details>
<div lang="pl">Już wkrótce</div><p>Step 3 of 4</p>
<select><option>Only 99 left</option></select><input value="Price 49 zł"><input type="submit" value="Buy 48 zł">
<script>document.querySelector("h1").animate([{ opacity: .9 }, { opacity: 1 }], { duration: 7000, iterations: Infinity, easing: "linear" });</script>
</main>"""), encoding="utf-8")
    rep = check_page(acme, "--schemes", "light")[1]
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    decls = {(d["source"], d["name"], d["duration_ms"], d["easing"], d["via"]): d for d in v["motion_decls"]}
    assert ("transition", "opacity", 300, "ease-in-out", "style") in decls and "div.menu" in decls[("transition", "opacity", 300, "ease-in-out", "style")]["sel"]   # display: none still moves when it opens
    assert {("transition", "transform", 150, "ease", "style"), ("transition", "opacity", 150, "ease", "style")} <= set(decls)                                              # a list of one duration is cycled over the properties
    assert {("transition", "color", 1000, "ease", "style"), ("transition", "background-color", 2000, "linear", "style")} <= set(decls)
    assert not any(k[0] == "transition" and k[2] == 0 for k in decls) and not any(k[1] == "outline-color" for k in decls)                                                  # a duration of 0 is no motion
    pulse = decls[("animation", "pulse", 1500, STANDARD_CURVE, "style")]
    assert "p.pulse" in pulse["sel"] and pulse["sel"].endswith("::after")                                                                                                                         # a generated pseudo-element
    assert not any("p.quiet" in d["sel"] for d in v["motion_decls"]) and not any(d["name"] == "none" for d in v["motion_decls"])                              # no content, no pseudo-element; none is none
    assert sum(1 for k in decls if k[:2] == ("animation", "pulse")) == 1                                                                                                    # the running CSS animation is the declared one, once
    assert ("script", "", 7000, "linear", "running") in decls and decls[("script", "", 7000, "linear", "running")]["sel"].endswith("h1")                                  # a script's, found while it runs
    assert "p.scroll" in decls[("animation", "grow", None, "linear", "style")]["sel"]                                                                               # animation-duration: auto
    assert not any("nodur" in d["sel"] for d in v["motion_decls"]) and sum(1 for k in decls if k[2] is None) == 1                                                          # a name and no duration on a time-based animation lasts 0: nothing moves, nothing to verify
    assert v["motion_smil"] == 0
    block = next(t for t in v["claim_text"] if "p.blk" in t["sel"] and t["sample_label"] is None)
    assert block["text"] == "€5 for 2 items 9 pieces and 40 %"                                                                                                              # inline elements join their block; <br> is a break
    assert next(t for t in v["claim_text"] if t["sample_label"] == "Deal")["text"] == "Save 20% today"
    outer = [t["text"] for t in v["claim_text"] if t["sample_label"] == "Outer"]
    inner = [t["text"] for t in v["claim_text"] if t["sample_label"] == ""]
    assert outer == ["outer after 66"] and inner == ["inner 88"]                                                                              # a sample's text is a run of its own
    texts = " | ".join(t["text"] for t in v["claim_text"])
    assert "Faded 55" in texts                                                                                                                                              # opacity 0 is still content
    assert not any(w in texts for w in ("Gone 99", "Cut 98", "Closed 97")) and "More" in texts                                                                              # display: none, cut to nothing, a closed <details>
    assert not any(w in texts for w in ("Only 99 left", "Price 49", "Buy 48")) and "No duration" in texts                                                                   # the text of an <option> and the value of an <input> are not read
    assert next(t for t in v["claim_text"] if t["text"] == "Już wkrótce")["lang"] == "pl" and next(t for t in v["claim_text"] if t["text"] == "Step 3 of 4")["lang"] == ""
    assert [(s["label"], s["text"]) for s in v["samples"]] == [("Deal", "Save 20% today"), ("Outer", "outer inner 88 after 66"), ("", "inner 88")]
    # the judge, on these facts: the unlabelled numbers and the Polish status word are named, the samples and 3 of 4 are not
    claims_row = row(rep, "page:claims")
    assert claims_row["status"] == "fail" and sorted(o["number"] for o in claims_row["unbacked_numbers"]) == ["40 %", "55", "88", "€5"]                                       # 88: an empty label labels nothing
    assert "20%" not in claims_row["detail"] and "after 66" not in claims_row["detail"] and "Step 3" not in claims_row["detail"]
    assert [o["word"] for o in claims_row["unbacked_status_words"]] == ["wkrótce"] and "NOT verified" not in claims_row["detail"] and claims_row["languages"].keys() == {"en", "pl"}
    assert [o["selector"] for o in claims_row["unlabelled_samples"]] == [next(s["sel"] for s in v["samples"] if s["label"] == "")]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_dotted_date_on_a_page_needs_the_numbers_of_the_date_in_the_facts(acme):
    add_fact(acme, "release", "premiera 2026-11-15")
    page = write_page(acme)
    mutate(page, '<html lang="en">', '<html lang="pl">')
    mutate(page, "</main>", "<p>Premiera 15.11.2026</p>\n</main>")   # the ISO fact backs the dotted form
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 1
    mutate(page, "Premiera 15.11.2026", "Premiera 16.11.2026")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["16.11.2026"]
    mutate(page, "Premiera 16.11.2026", "Wypłata 30.10")   # no year: its two numbers, 30 and 10
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["30.10"]
    add_fact(acme, "payout", "wypłata w dniu 30")
    assert check_page(acme, "--schemes", "light")[0].returncode == 1   # 10 is still missing
    add_fact(acme, "payout month", "w miesiącu 10")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0 and row(rep, "page:claims")["status"] == "pass", r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_digits_grouped_by_spaces_are_one_number_only_when_they_are_thousands(acme):
    add_fact(acme, "set", "the full set costs 13 205,20 zł")
    add_fact(acme, "year", "founded in 2026, with 200 tools")
    page = write_page(acme)
    mutate(page, "</main>", "<p>Only 13&nbsp;205,20 zł.</p><p>In 2026 200 tools.</p>\n</main>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 3
    mutate(page, "In 2026 200 tools", "In 2026 300 tools")   # 2026 is a number of its own: only 300 is the claim
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["300"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_copyright_year_is_no_claim_and_a_year_elsewhere_is(acme):
    page = write_page(acme)
    mutate(page, "</main>", "</main>\n<footer>&copy; 2026 Acme. Copyright 2024&ndash;2026 Acme. (c) 2025 Acme.</footer>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 0
    mutate(page, "(c) 2025 Acme.", "Founded 2025.")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["2025"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_status_code_of_an_error_page_is_no_claim_but_other_numbers_on_it_are(acme):
    page = write_page(acme)
    mutate(page, '<html lang="en">', '<html lang="pl">')   # the error words are those of the page's language
    mutate(page, "<title>Acme</title>", "<title>Błąd 404 | Acme</title>")
    mutate(page, "<h1>Acme hand tools</h1>", "<h1>Nie znaleziono</h1>\n  <p>Błąd 404</p><div style=\"font-size: 8rem\">404</div>")   # the title holds the code, the h1 does not
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 0
    mutate(page, "<title>Błąd 404 | Acme</title>", "<title>Acme</title>")   # neither the title nor the h1 holds it now: the page is not an error page
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["404", "404"]
    mutate(page, "<h1>Nie znaleziono</h1>", "<h1>404 · Nie znaleziono</h1>")   # the h1 alone holds it, with its error word
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    mutate(page, "</main>", "<p>500 firms. Tel. 600 123 456, 00-950 Warszawa, ul. Polna 12.</p>\n</main>")   # another number is a claim, and so are a phone number, a postal code and a street number
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["500", "600 123 456", "00", "950", "12"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_claims_collector_reads_the_title_and_the_h1_and_never_a_shadow_root(acme):
    page = write_page(acme)
    mutate(page, "</main>", """<div id="host"></div><p>Seen 321</p>
<script>document.getElementById("host").attachShadow({ mode: "open" }).innerHTML = "<h1>Shadow 777</h1><p>Shadow 888</p>";</script>
</main>""")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    assert v["document"]["title"] == "Acme" and v["claim_h1"] == ["Acme hand tools"]   # the h1 inside the shadow root is not listed
    assert "Seen 321" in " | ".join(t["text"] for t in v["claim_text"]) and not any("Shadow" in t["text"] for t in v["claim_text"])
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["321"]   # 777 and 888 are not read


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_named_after_its_status_code_is_an_error_page_and_a_count_with_a_plus_is_not_a_code(acme):
    body = "<h1>Nie znaleziono</h1>\n  <p>Błąd 404</p><div style=\"font-size: 8rem\"><span>404</span></div>"   # a small label and a big code: neither the title nor the h1 holds a number
    error = write_page(acme, PAGE.replace("<h1>Acme hand tools</h1>", body), name="pages/404.html")
    r, rep = check_page(acme, "--schemes", "light", page="pages/404.html")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 0
    write_page(acme, PAGE.replace("<h1>Acme hand tools</h1>", body), name="pages/not-found.html")   # the same page under another name is not an error page
    r, rep = check_page(acme, "--schemes", "light", page="pages/not-found.html")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["404", "404"]
    mutate(error, "</main>", "<p>Od 500 sztuk</p>\n</main>")   # another number on an error page is a claim
    r, rep = check_page(acme, "--schemes", "light", page="pages/404.html")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["500"]
    with serve(acme) as base:   # the file name of a page on this machine says it too
        mutate(error, "<p>Od 500 sztuk</p>\n", "")
        r = bc("page-check", "--url", f"{base}/pages/404.html", "--widths", "390", "--schemes", "light", project=acme)
        assert r.returncode == 0, r.stdout + r.stderr
        assert row(report(acme, pagecheck.report_tool(f"url:{base}/pages/404.html")), "page:claims")["claims_checked"]["numbers"] == 0
    page = write_page(acme)
    mutate(page, '<html lang="en">', '<html lang="pl">')   # the error words are those of the page's language: each h1 below holds one, so only the plus or the second number decides
    mutate(page, "<h1>Acme hand tools</h1>", "<h1>Błąd 500+</h1>")   # the only number of the h1, with a plus: a count, not a status code
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["500"]
    mutate(page, "<h1>Błąd 500+</h1>", "<h1>Błąd +500</h1>")   # a plus before the number is a count too
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["500"]
    mutate(page, "<h1>Błąd +500</h1>", "<h1>Błąd: 5 lat, 500 klientów</h1>")   # another number in the h1, a single digit too: 500 is not its status code
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["500"]
    mutate(page, "<h1>Błąd: 5 lat, 500 klientów</h1>", "<h1>Błąd 500</h1>")   # the same words with the code as the only number, and no plus: the status code
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["claims_checked"]["numbers"] == 0


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_count_in_a_heading_is_no_error_page_and_a_code_with_an_error_word_of_the_pages_language_is(acme):
    page = write_page(acme)
    for lang, h1, number in (("en", "Over 400 clients", "400"), ("pl", "Ponad 400 projektów", "400"), ("pl", "Zaufało nam 500 firm", "500")):
        write_page(acme, PAGE.replace('<html lang="en">', f'<html lang="{lang}">').replace("<h1>Acme hand tools</h1>", f"<h1>{h1}</h1>"))
        r, rep = check_page(acme, "--schemes", "light")
        assert r.returncode == 1, h1 + r.stdout + r.stderr
        assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == [number], h1   # a count in the heading exempts nothing
    mutate(page, "<h1>Zaufało nam 500 firm</h1>", "<h1>404 · Nie znaleziono</h1>\n  <p>404</p>")   # the code and an error word of the page's language (pl)
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 0
    mutate(page, '<html lang="pl">', '<html lang="en">')   # the same words on an English page are not error words
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["404", "404"]
    mutate(page, "<h1>404 · Nie znaleziono</h1>", "<h1>Error 404</h1>")   # English words on an English page
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    mutate(page, '<html lang="en">', '<html lang="de">')   # another language: the file name only
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["404", "404"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_date_with_a_month_name_on_a_page_is_one_date_that_needs_the_numbers_of_the_date_in_the_facts(acme):
    add_fact(acme, "release", "premiera 2026-10-21")
    page = write_page(acme)
    mutate(page, '<html lang="en">', '<html lang="pl">')
    mutate(page, "</main>", "<p>Premiera 21 października 2026</p><p>Październik 2026</p>\n</main>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 2
    mutate(page, '<html lang="pl">', '<html lang="en">')
    mutate(page, "<p>Premiera 21 października 2026</p><p>Październik 2026</p>", "<p>October 21, 2026</p><p>21 October 2026</p><p>October 2026</p>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 3
    mutate(page, "<p>October 2026</p>", "<p>October 2026</p><p>October 21,2026</p><p>March 15% of users</p>")   # the date with a comma and no space; the percent is no date
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["15%"] and row(rep, "page:claims")["claims_checked"]["numbers"] == 5
    mutate(page, "<p>October 2026</p><p>October 21,2026</p><p>March 15% of users</p>", "<p>October 2026</p>")
    mutate(page, "<p>21 October 2026</p>", "<p>22 October 2026</p>")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["22 October 2026"]   # one finding for the date, as written
    mutate(page, '<html lang="en">', '<html lang="de">')   # another language keeps the numbers: 22 is no fact
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["22"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_short_dotted_date_needs_two_digits_each_and_a_bare_decimal_is_a_decimal(acme):
    add_fact(acme, "release", "premiera 2026-12-05")
    page = write_page(acme)
    mutate(page, '<html lang="en">', '<html lang="pl">')
    mutate(page, "</main>", "<p>Premiera 12.05</p><p>Premiera 5.12.2026r.</p>\n</main>")   # two digits each, and a full date with a one-digit day glued to the Polish r.
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:claims")["status"] == "pass" and row(rep, "page:claims")["claims_checked"]["numbers"] == 2
    mutate(page, "<p>Premiera 12.05</p>", "<p>Premiera 12.5</p>")   # one digit for the month: the decimal 12.5, which the date does not hold
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    assert [o["number"] for o in row(rep, "page:claims")["unbacked_numbers"]] == ["12.5"]
    add_fact(acme, "grade", "ocena 12.5")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0 and row(rep, "page:claims")["status"] == "pass", r.stdout + r.stderr


# ---------------------------------------------------------------- the mark

MARK_STYLE = """  header { margin: 0; }
  .mark { display: block; margin: 0 0 16px 0; }
  main h1 { margin: 0; }
"""


def mark_page(mark_html: str, style: str = "") -> str:
    """The Acme page with a mark in a header above the main text: the mark has a block box and 16 px of its own free space below it."""
    return PAGE.replace("</style>", MARK_STYLE + style + "</style>").replace("<main>", "<header>" + mark_html + "</header>\n<main>")


def img(name: str, size: int = 48, extra: str = "") -> str:
    return f'<img class="mark" src="../assets/logo/{name}" width="{size}" height="{size}" alt="Acme"{extra}>'


def logo_hash(p: Path, name: str) -> str:
    return hashlib.sha256((p / "assets" / "logo" / name).read_bytes()).hexdigest()


def mark_rows_of(rep: dict) -> dict[str, dict]:
    return {x["id"]: x for x in rep["results"] if x["id"].startswith("page:mark-")}


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_mark_that_is_not_a_master_byte_for_byte_fails(acme):
    copy = acme / "pages" / "logo-copy.svg"   # a copy of the master the page uses, named like the logo
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(acme / "assets" / "logo" / "mark.svg", copy)
    write_page(acme, mark_page('<img class="mark" src="logo-copy.svg" width="48" height="48" alt="Acme">'))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = mark_rows_of(rep)
    assert [x["status"] for x in ok.values()] == ["pass", "pass", "pass"], ok
    assert ok["page:mark-file"]["files"] == ["assets/logo/mark.svg"] and "assets/logo/mark.svg" in ok["page:mark-file"]["detail"]
    mutate(copy, "#007d71", "#007d72")   # one byte of the copy
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = mark_rows_of(rep)["page:mark-file"]
    assert bad["status"] == "fail" and "none of the logo files of the project" in bad["detail"] and "/pages/logo-copy.svg" in bad["detail"], bad
    assert [(o["selector"], o["kind"], o["found_by"], o["width"], o["scheme"]) for o in bad["offenders"]] == [("body > header > img.mark", "img", "name", 390, "light")]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_file_named_logo_or_a_marked_element_is_a_mark_not_a_name_that_holds_the_word(acme):
    """logo.svg and data-brand-mark make a mark; partner-logo.svg and ikona-logowanie.svg, other drawings whose names only hold the word, do not."""
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    master = acme / "assets" / "logo" / "mark.svg"
    for name in ("logo.svg", "brand.svg"):
        shutil.copyfile(master, pages / name)                      # the master, under a name that says logo and under one that does not
    other = DOT.replace('r="3"', 'r="2"')                            # a drawing that is none of the logo files: a partner's logo, a login icon
    for name in ("partner-logo.svg", "ikona-logowanie.svg"):
        (pages / name).write_text(other, encoding="utf-8")
    both = '<img src="partner-logo.svg" width="24" height="24" alt="Partner"><img src="ikona-logowanie.svg" width="24" height="24" alt="Log in">'

    def run(html: str) -> tuple[dict, dict]:
        write_page(acme, mark_page(html))
        r, rep = check_page(acme, "--schemes", "light")
        return rep, mark_rows_of(rep)["page:mark-file"]

    # the page with the real logo (the master named logo.svg) and the two other drawings: one mark, and the row passes
    rep, row = run('<img class="mark" src="logo.svg" width="48" height="48" alt="Acme">' + both)
    assert row["status"] == "pass" and row["marks_checked"] == 1 and row["files"] == ["assets/logo/mark.svg"], row
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    assert [m["url"] for m in v["marks"]] == ["/pages/logo.svg"] and {i["url"] for i in v["images"]} == {"/pages/partner-logo.svg", "/pages/ikona-logowanie.svg"}
    # the copy named logo.svg is changed by one byte: it is a mark by its name and fails; the two other drawings are still no marks and are not named
    mutate(pages / "logo.svg", "#007d71", "#007d72")
    rep, row = run('<img class="mark" src="logo.svg" width="48" height="48" alt="Acme">' + both)
    assert row["status"] == "fail" and [(o["url"], o["found_by"]) for o in row["offenders"]] == [("/pages/logo.svg", "name")], row
    assert "partner-logo" not in row["detail"] and "ikona-logowanie" not in row["detail"], row
    # only the two other drawings: no mark on the page, so nothing fails and the row is the info row
    rep, row = run(both)
    assert row["status"] == "info" and "no brand mark is shown" in row["detail"], row
    # data-brand-mark makes a mark of an image with any name: the master under the name brand.svg passes, one byte changed fails, whatever its name
    rep, row = run('<img class="mark" data-brand-mark src="brand.svg" width="48" height="48" alt="Acme">' + both)
    assert row["status"] == "pass" and row["marks_checked"] == 1, row
    mutate(pages / "brand.svg", "#007d71", "#007d72")
    rep, row = run('<img class="mark" data-brand-mark src="brand.svg" width="48" height="48" alt="Acme">' + both)
    assert row["status"] == "fail" and [(o["url"], o["found_by"]) for o in row["offenders"]] == [("/pages/brand.svg", "attribute")], row
    # the same file without the attribute and without a name that says logo is only an image
    rep, row = run('<img class="mark" src="brand.svg" width="48" height="48" alt="Acme">' + both)
    assert row["status"] == "info", row


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_file_named_mark_wordmark_or_logo_with_a_suffix_is_a_mark_and_a_stem_that_only_holds_the_word_is_not(acme):
    """The name rule: the stem is logo, mark or wordmark, alone or followed by -, _ or @ and more (mark.svg, wordmark.svg, logo@2x.svg, mark-dark.svg, Wordmark_Light.svg). A stem that only
    starts with or holds one of the words (bookmark, marker, market-chart, partner-logo, ikona-logowanie, logowanie) is only an image. A candidate is then judged like any mark."""
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    candidates = ("mark.svg", "wordmark.svg", "logo@2x.svg", "mark-dark.svg", "Wordmark_Light.svg")
    others = ("bookmark.svg", "marker.svg", "market-chart.svg", "partner-logo.svg", "ikona-logowanie.svg", "logowanie.svg")
    for name in candidates:
        shutil.copyfile(acme / "assets" / "logo" / "mark.svg", pages / name)   # the master, under a name that says mark, wordmark or logo
    for name in others:
        (pages / name).write_text(DOT.replace('r="3"', 'r="2"'), encoding="utf-8")   # a drawing that is none of the logo files
    html = lambda names: "".join(f'<img src="{n}" width="48" height="48" alt="">' for n in names)

    def run(names) -> tuple[dict, dict]:
        write_page(acme, mark_page(html(names)))
        r, rep = check_page(acme, "--schemes", "light")
        return rep, mark_rows_of(rep)["page:mark-file"]

    # every candidate is a mark by its name and, being the master's bytes, passes; the other six are images and not judged
    rep, row = run(candidates + others)
    assert row["status"] == "pass" and row["marks_checked"] == len(candidates) and row["files"] == ["assets/logo/mark.svg"], row
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    assert {m["url"] for m in v["marks"]} == {f"/pages/{n}" for n in candidates} and all(m["named"] and not m["marked"] for m in v["marks"]), v["marks"]
    assert {i["url"] for i in v["images"]} == {f"/pages/{n}" for n in others}, v["images"]
    # one byte changed in each candidate: each is judged and fails by its name; none of the six other names is told of
    for name in candidates:
        mutate(pages / name, "#007d71", "#007d72")
    rep, row = run(candidates + others)
    assert row["status"] == "fail" and {(o["url"], o["found_by"]) for o in row["offenders"]} == {(f"/pages/{n}", "name") for n in candidates}, row
    assert not any(n.removesuffix(".svg") in row["detail"] for n in others), row["detail"]
    # the page with the six other names only: no mark, so nothing fails and the row is the info row
    rep, row = run(others)
    assert row["status"] == "info" and "no brand mark is shown" in row["detail"] and "logo, mark or wordmark" in row["detail"], row


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_mark_and_wordmark_name_a_mark_only_for_an_svg_file_and_logo_for_any_image(acme):
    """The name rule by file type: mark and wordmark (alone or followed by -, _ or @ and more) make a candidate only for an .svg file, so the photos of people named Mark on a team page
    (mark.jpg, Mark.png, mark-kowalski.jpg) and wordmark.png are only images; logo does for any type (logo.jpg, logo@2x.png). The bytes of a logo file, and data-brand-mark, find a mark
    whatever its name."""
    from px_lib import Img
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    logo = acme / "assets" / "logo"
    people = ("mark.jpg", "Mark.png", "mark-kowalski.jpg", "wordmark.png")
    candidates = ("mark.svg", "wordmark-dark.svg", "logo@2x.png", "logo.jpg")
    for n in people:
        (pages / n).write_bytes(Img(8, 8, "#" + hashlib.sha256(n.encode()).hexdigest()[:6]).png())   # a picture of its own, none of the logo files (the .jpg hold PNG bytes: the browser sniffs them)
    for n in candidates:
        shutil.copyfile(logo / ("mark.svg" if n.endswith(".svg") else "grid-mark-master.png"), pages / n)   # a logo file under a name that says logo, mark or wordmark
    html = lambda names: "".join(f'<img src="{n}" width="48" height="48" alt="">' for n in names)

    def run(page_html: str) -> tuple[dict, dict, dict]:
        write_page(acme, mark_page(page_html))
        r, rep = check_page(acme, "--schemes", "light")
        (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
        return rep, mark_rows_of(rep)["page:mark-file"], v

    # a team page: four pictures that are shown and are no marks, so nothing fails and the row is the info row
    rep, row, v = run(html(people))
    assert row["status"] == "info" and "no brand mark is shown" in row["detail"], row
    assert v["marks"] == [] and {i["url"] for i in v["images"]} == {f"/pages/{n}" for n in people}, v   # shown (they are in images), and not named
    # the four logo files under the other names are marks by their names, and being the logo files they pass
    rep, row, v = run(html(candidates))
    assert row["status"] == "pass" and row["marks_checked"] == len(candidates), row
    assert {m["url"] for m in v["marks"]} == {f"/pages/{n}" for n in candidates} and all(m["named"] and not m["marked"] for m in v["marks"]) and v["images"] == [], v
    # one byte changed in each: they are judged and fail by their names, the four pictures beside them are still not told of
    for n in candidates:
        if n.endswith(".svg"):
            mutate(pages / n, "#007d71", "#007d72")
        else:   # a raster: one byte more after the image
            before = (pages / n).read_bytes()
            (pages / n).write_bytes(before + b"\n")
            assert (pages / n).read_bytes() != before   # the mutation applied
    rep, row, v = run(html(people + candidates))
    assert row["status"] == "fail" and {(o["url"], o["found_by"]) for o in row["offenders"]} == {(f"/pages/{n}", "name") for n in candidates}, row
    assert not any(n in row["detail"] for n in people), row["detail"]
    # bytes find a mark under any name: the logo's raster as mark.png is a mark and passes; one byte more and it is a picture again
    shutil.copyfile(logo / "grid-mark-master.png", pages / "mark.png")
    rep, row, v = run(html(("mark.png",)))
    assert row["status"] == "pass" and row["marks_checked"] == 1 and row["files"] == ["assets/logo/grid-mark-master.png"], row
    assert v["marks"] == [] and [i["url"] for i in v["images"]] == ["/pages/mark.png"]   # not by its name
    assert [m["by"] for m in pagecheck.identified_marks(v, {logo_hash(acme, "grid-mark-master.png")})] == ["bytes"]
    (pages / "mark.png").write_bytes((pages / "mark.png").read_bytes() + b"\n")
    rep, row, v = run(html(("mark.png",)))
    assert row["status"] == "info", row
    # data-brand-mark finds one too, and it is judged: a picture named mark-kowalski.jpg that is marked is no logo file
    rep, row, v = run(html(people).replace('<img src="mark-kowalski.jpg"', '<img data-brand-mark src="mark-kowalski.jpg"'))
    assert row["status"] == "fail" and [(o["url"], o["found_by"]) for o in row["offenders"]] == [("/pages/mark-kowalski.jpg", "attribute")], row


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_report_goes_stale_when_a_logo_file_changes(acme):
    """A mark is judged against assets/logo/: a changed logo file, one the page never loads, makes the verdict stale."""
    copy = acme / "pages" / "mark-copy.svg"
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(acme / "assets" / "logo" / "mark.svg", copy)
    write_page(acme, mark_page('<img class="mark" src="mark-copy.svg" width="48" height="48" alt="Acme">'))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert {"assets/logo/mark.svg", "assets/logo/grid-mark.svg", "assets/logo/wordmark.svg"} <= {i["path"] for i in rep["inputs"]} and stale_inputs(acme, rep) == []
    mutate(acme / "assets" / "logo" / "wordmark.svg", "<svg", "<svg data-edited=\"1\"")
    assert stale_inputs(acme, rep) == ["assets/logo/wordmark.svg changed"]
    # a page with no mark: "no brand mark is shown" may rest on a logo's bytes (an image is a mark by being one), so a changed logo file makes that verdict stale too
    write_page(acme)
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0 and mark_rows_of(rep)["page:mark-file"]["status"] == "info", r.stdout + r.stderr
    assert {"assets/logo/mark.svg", "assets/logo/grid-mark.svg", "assets/logo/wordmark.svg"} <= {i["path"] for i in rep["inputs"]} and stale_inputs(acme, rep) == []
    mutate(acme / "assets" / "logo" / "mark.svg", "<svg", "<svg data-edited=\"1\"")
    assert stale_inputs(acme, rep) == ["assets/logo/mark.svg changed"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_mark_at_24_px_must_be_the_small_band_drawing(acme):
    """Acme's bands: 32 px and below is grid-mark.svg, above it mark.svg. The twin counts in either theme; a wordmark is in no band."""
    def run(html: str, *args: str) -> dict[str, dict]:
        write_page(acme, mark_page(html))
        return mark_rows_of(check_page(acme, *args)[1])

    wrong = run(img("mark.svg", 24))
    assert wrong["page:mark-file"]["status"] == "pass"   # it is a logo file ...
    band = wrong["page:mark-band"]
    assert band["status"] == "fail" and "assets/logo/mark.svg at 24 px, band small is assets/logo/grid-mark.svg" in band["detail"], band   # ... but not the drawing for 24 px
    assert [(o["height_px"], o["band"], o["drawing"]) for o in band["offenders"]] == [(24, "small", "assets/logo/grid-mark.svg")]
    right = run(img("grid-mark.svg", 24))
    assert right["page:mark-band"]["status"] == "pass" and "grid-mark.svg at 24 px (band small)" in right["page:mark-band"]["detail"]
    too_small = run(img("grid-mark.svg", 48))   # the coarse grid mark is for the small sizes only
    assert too_small["page:mark-band"]["status"] == "fail" and "band large is assets/logo/mark.svg" in too_small["page:mark-band"]["detail"]
    assert run(img("mark.svg", 48))["page:mark-band"]["status"] == "pass" and run(img("mark.svg", 33))["page:mark-band"]["status"] == "pass"
    assert run(img("grid-mark.svg", 32))["page:mark-band"]["status"] == "pass"   # 32 px is the edge of the small band
    # the dark twin of the band's drawing is the drawing in the dark theme (and a dark header on a light page may show it too)
    picture = ('<picture><source srcset="../assets/logo/grid-mark-dark.svg" media="(prefers-color-scheme: dark)">'
               '<img class="mark" src="../assets/logo/grid-mark.svg" width="24" height="24" alt="Acme"></picture>')
    both = run(picture)
    assert both["page:mark-band"]["status"] == "pass" and both["page:mark-file"]["status"] == "pass", both
    dark_only = run(img("grid-mark-dark.svg", 24), "--schemes", "light")
    assert dark_only["page:mark-band"]["status"] == "pass"
    measures = json.loads(Path(report(acme, pagecheck.report_tool("pages/index.html"))["measures"]).read_text(encoding="utf-8"))
    assert measures["views"][0]["marks"] == [] and measures["views"][0]["images"][0]["kind"] == "img"   # no name says logo: the judge found the mark by its bytes
    # a wordmark is not a drawing of a band: the band row says so and nothing fails
    word = run(img("wordmark.svg", 24))
    assert word["page:mark-file"]["status"] == "pass" and word["page:mark-band"]["status"] == "info" and "in no band" in word["page:mark-band"]["detail"]
    # the same bands written as `./assets/logo/x.svg` are the same bands: the wrong drawing is not passed as 'not banded'
    rules_file = acme / "qa" / "rules.json"
    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    rules["bands"] = [{**b, "drawing": "./" + b["drawing"]} for b in rules["bands"]]
    rules_file.write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")
    assert run(img("mark.svg", 24))["page:mark-band"]["status"] == "fail" and run(img("grid-mark.svg", 24))["page:mark-band"]["status"] == "pass"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_text_inside_the_clear_space_fails(acme):
    write_page(acme, mark_page(img("mark.svg", 48)))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = mark_rows_of(rep)["page:mark-clear-space"]   # 16 px of free space, and the proposal asks for 0.25 x 48 = 12
    assert ok["status"] == "pass" and ok["proposal"] is True and "a proposal until qa/rules.json sets page.clear_space" in ok["detail"], ok
    page = acme / "pages" / "index.html"
    mutate(page, "margin: 0 0 16px 0;", "margin: 0 0 4px 0;")   # the text of the page now starts 4 px under the mark
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = mark_rows_of(rep)["page:mark-clear-space"]
    assert bad["status"] == "fail" and 'body > main > h1 "Acme hand tools"' in bad["detail"] and "px away, needs 12 px" in bad["detail"], bad
    (o,) = bad["offenders"]
    assert (o["selector"], o["nearest"], o["needs_px"], o["height_px"]) == ("body > header > img.mark", "body > main > h1", 12, 48) and 3 <= o["nearest_px"] <= 7, o   # 4 px and the text's own leading
    assert mark_rows_of(rep)["page:mark-file"]["status"] == "pass"   # the file is right: only the space is not
    mutate_json(acme / "qa" / "rules.json", lambda d: d.__setitem__("page", {"clear_space": 0.05}))   # the owner sets a smaller share: 2.4 px
    r, rep = check_page(acme, "--schemes", "light")
    ok = mark_rows_of(rep)["page:mark-clear-space"]
    assert r.returncode == 0 and ok["status"] == "pass" and ok["proposal"] is False and "proposal" not in ok["detail"], ok


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_inline_svg_mark_is_compared_after_canonicalisation(acme):
    """An inline mark (data-brand-mark) is the same drawing as a logo file when it differs only in the order of attributes, white space, its size and labels, and a title."""
    inline = ('<svg data-brand-mark="assets/logo/mark.svg" class="mark" width="48" height="48" viewBox="0 0 64 64" aria-label="Acme home" xmlns="http://www.w3.org/2000/svg">\n'
              '  <title>Acme home</title>\n  <path   fill="#0d1b2d"   d="M32 6 58 54H6Z" />\n  <circle r="9" cx="32"\n  cy="41" fill="#007d71"></circle>\n</svg>')

    def run(html: str) -> dict[str, dict]:
        write_page(acme, mark_page(html))
        return mark_rows_of(check_page(acme, "--schemes", "light")[1])

    ok = run(inline)
    assert ok["page:mark-file"]["status"] == "pass" and ok["page:mark-file"]["files"] == ["assets/logo/mark.svg"], ok
    assert "inline SVG was compared after canonicalisation" in ok["page:mark-file"]["detail"] and ok["page:mark-band"]["status"] == "pass"
    for broken, why in ((inline.replace('fill="#007d71"', 'fill="#007d72"'), "draws none of the logo drawings"),   # one colour, one digit off
                        (inline.replace('viewBox="0 0 64 64"', 'viewBox="0 0 65 64"'), "draws none of the logo drawings"),
                        (inline.replace('r="9"', 'r="10"'), "draws none of the logo drawings"),
                        (inline.replace("</svg>", '<rect width="1" height="1"/></svg>'), "draws none of the logo drawings"),
                        (inline.replace('data-brand-mark="assets/logo/mark.svg"', 'data-brand-mark="assets/logo/wordmark.svg"'), "names assets/logo/wordmark.svg, but this mark is assets/logo/mark.svg"),
                        (inline.replace('data-brand-mark="assets/logo/mark.svg"', 'data-brand-mark="assets/logo/nowhere.svg"'), "which is not a logo file of the project")):
        got = run(broken)["page:mark-file"]
        assert got["status"] == "fail" and why in got["detail"], (why, got)
    assert run(inline.replace('data-brand-mark="assets/logo/mark.svg"', "data-brand-mark"))["page:mark-file"]["status"] == "pass"   # naming the file is optional
    assert run(inline.replace('data-brand-mark="assets/logo/mark.svg"', 'data-brand-mark="assets/logo/mark-dark.svg"'))["page:mark-file"]["status"] == "pass"   # a file and its twin are one
    assert run('<div data-brand-mark><p>Acme</p></div>')["page:mark-file"]["status"] == "fail"   # the attribute is on something that shows no image


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_image_with_the_bytes_of_a_logo_file_is_a_mark_whatever_it_is_called(acme):
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    shutil.copyfile(acme / "assets" / "logo" / "mark.svg", pages / "brand.svg")                                  # the master, under another name
    (pages / "badge.svg").write_text((acme / "assets" / "logo" / "mark.svg").read_text(encoding="utf-8").replace("#007d71", "#007d72"), encoding="utf-8")   # not the master
    write_page(acme, mark_page('<img class="mark" src="brand.svg" width="48" height="48" alt="Acme"><img src="badge.svg" width="48" height="48" alt="">'))
    r, rep = check_page(acme, "--schemes", "light")
    got = mark_rows_of(rep)
    assert got["page:mark-file"]["status"] == "pass" and got["page:mark-file"]["marks_checked"] == 1, got   # brand.svg is the master, badge.svg is just an image
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    (v,) = measures["views"]
    assert [m["url"] for m in v["marks"]] == [] and {i["url"] for i in v["images"]} == {"/pages/brand.svg", "/pages/badge.svg"}   # nothing in the names; the judge found brand.svg by its bytes
    assert pagecheck.identified_marks(v, {logo_hash(acme, "mark.svg")})[0]["by"] == "bytes" and len(pagecheck.identified_marks(v, {logo_hash(acme, "mark.svg")})) == 1


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_marks_collector_finds_marks_by_attribute_and_by_name_and_measures_the_gap(acme):
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    dot = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" width="8" height="8"><circle cx="4" cy="4" r="3" fill="#007d71"/></svg>\n'
    for name in ("logo", "logo-bg", "logo_pseudo", "logo-hidden", "logo-svgimage", "partner-logo", "ikona-logowanie", "logos", "bookmark", "marketing-hero", "siteMark", "lockup", "wordmark-x",
                 "plain", "near", "diagonal", "awayfromit"):
        (pages / f"{name}.svg").write_text(dot.replace("r=\"3\"", f'r="{3 + len(name) % 3}"'), encoding="utf-8")   # different bytes for each, none a logo file
    body = """<img id="a" src="logo.svg" width="40" height="40" alt="" style="position: absolute; left: 100px; top: 600px">
<img src="near.svg" width="10" height="10" alt="" style="position: absolute; left: 150px; top: 600px">
<img src="diagonal.svg" width="10" height="10" alt="" style="position: absolute; left: 148px; top: 642px">
<img src="awayfromit.svg" width="10" height="10" alt="" style="position: absolute; left: 100px; top: 800px">
<img src="bookmark.svg" width="12" height="12" alt=""><img src="marketing-hero.svg" width="12" height="12" alt=""><img src="siteMark.svg" width="12" height="12" alt="">
<img src="partner-logo.svg" width="12" height="12" alt=""><img src="ikona-logowanie.svg" width="12" height="12" alt=""><img src="logos.svg" width="12" height="12" alt="">
<img src="lockup.svg" width="12" height="12" alt=""><img src="wordmark-x.svg" width="12" height="12" alt="">
<img src="logo-hidden.svg" width="12" height="12" alt="" style="display: none">
<div class="bg" style="width: 20px; height: 20px; background: url(logo-bg.svg)"></div>
<svg width="14" height="14" aria-hidden="true"><image href="logo-svgimage.svg" width="14" height="14"/></svg>
<div class="pseudo"></div>
<a href="#top" data-brand-mark><img src="plain.svg" width="16" height="16" alt=""></a>
<div data-brand-mark>no image</div>"""
    style = ".pseudo::before { content: ''; display: block; width: 12px; height: 12px; background: url(logo_pseudo.svg); }\n"
    write_page(acme, PAGE.replace("</style>", style + "</style>").replace("</main>", body + "\n</main>"))
    r, rep = check_page(acme, "--schemes", "light")
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    got = {(m["kind"], m["url"]): m for m in v["marks"]}
    assert set(got) == {("img", "/pages/logo.svg"), ("background", "/pages/logo-bg.svg"), ("background", "/pages/logo_pseudo.svg"), ("image", "/pages/logo-svgimage.svg"),
                        ("img", "/pages/plain.svg"), ("other", None), ("img", "/pages/logo-hidden.svg"), ("img", "/pages/wordmark-x.svg")}, sorted(got, key=str)   # the hidden logo is a mark that is not shown
    assert {i["url"] for i in v["images"]} >= {"/pages/partner-logo.svg", "/pages/ikona-logowanie.svg", "/pages/logos.svg", "/pages/siteMark.svg", "/pages/lockup.svg"}   # a name that only holds the word, or says something else, is an image
    assert got[("img", "/pages/wordmark-x.svg")]["named"] and "/pages/wordmark-x.svg" not in {i["url"] for i in v["images"]}   # wordmark followed by - and more is a name candidate
    hidden = got[("img", "/pages/logo-hidden.svg")]
    assert hidden["visible"] is False and hidden["named"] and not hidden["marked"] and hidden["nearest_px"] is None   # it is reported as not shown, and no neighbour is looked for
    assert {i["url"] for i in v["images"]} >= {"/pages/bookmark.svg", "/pages/marketing-hero.svg", "/pages/near.svg"} and "/pages/logo-hidden.svg" not in {i["url"] for i in v["images"]}
    a = got[("img", "/pages/logo.svg")]
    assert a["named"] and not a["marked"] and a["declared"] is None and a["visible"] and a["own"] is True
    assert a["rect"] == {"x": 100, "y": 600, "width": 40, "height": 40}
    assert (a["nearest_px"], a["nearest_sel"]) == (8, "body > main > img:nth-of-type(3)"), a   # the box 8 px right and 2 px under the corner, not the one 10 px to the right
    assert got[("img", "/pages/plain.svg")]["marked"] and got[("img", "/pages/plain.svg")]["declared"] == "" and got[("other", None)]["visible"]
    pseudo = got[("background", "/pages/logo_pseudo.svg")]
    assert pseudo["pseudo"] == "::before" and pseudo["rect"] is None and pseudo["height_px"] == 12
    assert got[("background", "/pages/logo-bg.svg")]["rect"]["width"] == 20 and got[("image", "/pages/logo-svgimage.svg")]["named"]   # a relative href of an SVG image is read against the page


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_marks_collector_stops_at_its_caps_and_says_how_many_there_were(acme):
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    for name in ("logo", "plain"):
        (pages / f"{name}.svg").write_text(DOT, encoding="utf-8")   # not a logo file, so the marks fail the row and the row names the cut
    body = "".join(f'<img src="logo.svg?{n}" width="4" height="4" alt="">' for n in range(105)) + "".join(f'<img src="plain.svg?{n}" width="4" height="4" alt="">' for n in range(305))
    write_page(acme, PAGE.replace("</main>", body + "\n</main>"))
    r, rep = check_page(acme, "--schemes", "light")
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    assert (len(v["marks"]), v["marks_total"], len(v["images"]), v["images_total"]) == (100, 105, 300, 305)
    detail = mark_rows_of(rep)["page:mark-file"]["detail"]
    assert "105 marks at 390 px, 100 measured" in detail and "305 images at 390 px, 300 looked at" in detail, detail


# ---------------------------------------------------------------- the mark, no browser

def mark_entry(sel: str = "body > header > img", url: str = "/assets/logo/mark.svg", height: float | None = 48, **more) -> dict:
    """What the collector measures for a mark that is an `img` named like a logo."""
    return {"sel": sel, "kind": "img", "url": url, "own": True, "declared": None, "named": True, "marked": False, "visible": True,
            "rect": {"x": 0, "y": 0, "width": height, "height": height} if height else None, "nearest_px": None, "nearest_sel": None, "nearest_text": None, **more}


def judge_marks(p: Path, entries: list[dict], names: tuple[str, ...] = ("mark.svg", "grid-mark.svg", "grid-mark-dark.svg", "mark-dark.svg", "wordmark.svg"), scheme: str = "light",
                rules: dict | None = None, images: list | None = None, files: dict | None = None) -> dict[str, dict]:
    """mark_rows on constructed measurements: the logo files of `names` were served from assets/logo/, `files` maps a path to the sha256 of some other file that was served."""
    resources = {f"/assets/logo/{n}": {"sha256": logo_hash(p, n), "content_type": "image/svg+xml"} for n in names}
    resources.update({path: {"sha256": sha, "content_type": "image/svg+xml"} for path, sha in (files or {}).items()})
    ctx = pagecheck.Ctx(p, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [390], [scheme], rules or qa_rules.load(p)[0], {})
    rep = Report("page-check/x-000000", p)
    pagecheck.mark_rows(rep, {"views": [view(scheme, marks=entries, images=images or [], resources=resources)]}, ctx)
    return {r["id"]: r for r in rep.results}


@pytest.fixture
def logo_project(tmp_path) -> Path:
    p = make_project(tmp_path)
    install_fixture(p, tokens=False, board=False)   # assets/logo/ and qa/rules.json of the Acme example: bands small (up to 32 px) grid-mark.svg, large mark.svg
    return p


def test_the_band_rule_names_the_drawing_for_the_rendered_height_and_counts_the_dark_twin(logo_project):
    p = logo_project
    status = lambda rows: (rows["page:mark-file"]["status"], rows["page:mark-band"]["status"])
    assert status(judge_marks(p, [mark_entry(height=24)])) == ("pass", "fail")                       # mark.svg is the large drawing
    assert status(judge_marks(p, [mark_entry(url="/assets/logo/grid-mark.svg", height=24)])) == ("pass", "pass")
    assert status(judge_marks(p, [mark_entry(url="/assets/logo/grid-mark-dark.svg", height=24)], scheme="dark")) == ("pass", "pass")   # the twin counts in the dark theme ...
    assert status(judge_marks(p, [mark_entry(url="/assets/logo/grid-mark-dark.svg", height=24)], scheme="light")) == ("pass", "pass")   # ... and on a dark header of a light page
    assert status(judge_marks(p, [mark_entry(url="/assets/logo/mark-dark.svg", height=24)], scheme="dark")) == ("pass", "fail")
    for h, url, band in ((32, "grid-mark.svg", "pass"), (32.4, "grid-mark.svg", "pass"), (32.6, "grid-mark.svg", "fail"), (33, "grid-mark.svg", "fail"),
                         (32.6, "mark.svg", "pass"), (32, "mark.svg", "fail"), (4000, "mark.svg", "pass")):   # the height is rounded to a whole pixel, as the picker takes one
        assert judge_marks(p, [mark_entry(url=f"/assets/logo/{url}", height=h)])["page:mark-band"]["status"] == band, (h, url)
    word = judge_marks(p, [mark_entry(url="/assets/logo/wordmark.svg", height=24)])   # a wordmark is in no band
    assert (word["page:mark-file"]["status"], word["page:mark-band"]["status"]) == ("pass", "info") and "in no band" in word["page:mark-band"]["detail"]
    pseudo = judge_marks(p, [mark_entry(url="/assets/logo/mark.svg", height=None, pseudo="::before", height_px=24)])   # no box to read: the computed height decides
    assert pseudo["page:mark-band"]["status"] == "fail" and pseudo["page:mark-clear-space"]["status"] == "warn" and "NOT verified" in pseudo["page:mark-clear-space"]["detail"]
    unmeasured = judge_marks(p, [mark_entry(url="/assets/logo/mark.svg", height=None, pseudo="::before")])
    assert unmeasured["page:mark-band"]["status"] == "warn" and "NOT verified" in unmeasured["page:mark-band"]["detail"]
    no_bands = qa_rules.load(p)[0] | {"bands": []}
    assert judge_marks(p, [mark_entry(height=24)], rules=no_bands)["page:mark-band"]["status"] == "info"


def test_with_several_marks_each_is_judged_by_its_own_bands(logo_project):
    p = logo_project
    rules = qa_rules.load(p)[0] | {"bands": [], "marks": qa_rules.validate_marks({
        "a": {"bands": [{"name": "small", "max_px": 16, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "assets/logo/mark.svg"}]},
        "b": {"bands": [{"name": "all", "drawing": "assets/logo/wordmark.svg"}]}})}
    band = lambda *entries: judge_marks(p, list(entries), rules=rules)["page:mark-band"]
    assert band(mark_entry(url="/assets/logo/grid-mark.svg", height=16))["status"] == "pass"
    assert band(mark_entry(url="/assets/logo/grid-mark.svg", height=17))["status"] == "fail"       # mark a: 17 px is its large band
    assert band(mark_entry(url="/assets/logo/wordmark.svg", height=200))["status"] == "pass"       # mark b has one band for every size
    assert band(mark_entry(url="/assets/logo/mark.svg", height=17), mark_entry(sel="body > p > img", url="/assets/logo/wordmark.svg", height=8))["status"] == "pass"


def test_a_band_written_with_a_dot_slash_or_through_a_symlink_is_still_the_band(logo_project):
    """qa/rules.json is read as written (`./assets/logo/x.svg`); the files of a page are keyed by their resolved path. The two must meet, or a wrong drawing passes as 'not banded'."""
    p = logo_project
    plain = qa_rules.load(p)[0]
    dotted = plain | {"bands": [b | {"drawing": "./" + b["drawing"]} for b in plain["bands"]]}
    assert [b["drawing"] for b in dotted["bands"]] == ["./assets/logo/grid-mark.svg", "./assets/logo/mark.svg"]
    for rules in (plain, dotted):
        assert judge_marks(p, [mark_entry(height=24)], rules=rules)["page:mark-band"]["status"] == "fail"   # mark.svg at 24 px is not the small drawing, written either way
        bad = judge_marks(p, [mark_entry(height=24)], rules=rules)["page:mark-band"]
        assert "band small is assets/logo/grid-mark.svg" in bad["detail"] and bad["offenders"][0]["drawing"] == "assets/logo/grid-mark.svg", bad   # named as the project path
        assert judge_marks(p, [mark_entry(url="/assets/logo/grid-mark.svg", height=24)], rules=rules)["page:mark-band"]["status"] == "pass"   # the right drawing is not failed for the dot
        assert judge_marks(p, [mark_entry(url="/assets/logo/grid-mark-dark.svg", height=24)], rules=rules, scheme="dark")["page:mark-band"]["status"] == "pass"
        assert judge_marks(p, [mark_entry(height=48)], rules=rules)["page:mark-band"]["status"] == "pass"
    many = plain | {"bands": [], "marks": qa_rules.validate_marks({"a": {"bands": [{"name": "small", "max_px": 16, "drawing": "./assets/logo/../logo/grid-mark.svg"},
                                                                                      {"name": "large", "drawing": "assets//logo/mark.svg"}]}})}
    assert judge_marks(p, [mark_entry(height=24)], rules=many)["page:mark-band"]["status"] == "pass"       # 24 px is the large band of mark a
    assert judge_marks(p, [mark_entry(height=12)], rules=many)["page:mark-band"]["status"] == "fail"
    # a logo file that is a symlink inside the project is keyed by what it points to: a band naming the link is the band of that file
    (p / "assets" / "logo" / "large.svg").symlink_to("mark.svg")
    linked = plain | {"bands": [plain["bands"][0] | {"drawing": "assets/logo/grid-mark.svg"}, plain["bands"][1] | {"drawing": "assets/logo/large.svg"}]}
    assert judge_marks(p, [mark_entry(height=24)], rules=linked)["page:mark-band"]["status"] == "fail"
    assert judge_marks(p, [mark_entry(height=48)], rules=linked)["page:mark-band"]["status"] == "pass"
    named = judge_marks(p, [mark_entry(height=48, marked=True, declared="assets/logo/large.svg")], rules=linked)   # data-brand-mark names the link, the mark is the file it points to
    assert named["page:mark-file"]["status"] == "pass", named
    outside = plain | {"bands": [plain["bands"][0] | {"drawing": "../elsewhere/grid-mark.svg"}, plain["bands"][1]]}   # a drawing outside the project is no file of the project
    assert judge_marks(p, [mark_entry(height=24)], rules=outside)["page:mark-band"]["status"] == "fail"       # mark.svg is still the large band's drawing, so 24 px is wrong
    assert pagecheck.project_keys(p, "./assets/logo/../logo/mark.svg") == ["assets/logo/mark.svg", "assets/logo/mark-dark.svg"]
    assert pagecheck.project_keys(p, "../elsewhere/mark.svg") == [] and pagecheck.project_keys(p, "/etc/mark.svg") == []


def test_an_inline_svg_that_draws_through_use_is_not_verified_and_never_failed(logo_project):
    """A `<use>` points at a drawing the check does not follow: it may be the right mark, so the row warns 'NOT verified' instead of failing it."""
    p = logo_project
    master = (p / "assets" / "logo" / "mark.svg").read_text(encoding="utf-8")
    inline = lambda svg, **more: mark_entry(url=None, kind="inline-svg", marked=True, named=False, svg_markup=svg, **more)
    via_use = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><g id="m"><circle cx="32" cy="41" r="9"/></g></defs><use href="#m"/></svg>'
    got = judge_marks(p, [inline(via_use)])
    assert got["page:mark-file"]["status"] == "warn" and "NOT verified" in got["page:mark-file"]["detail"] and "<use>" in got["page:mark-file"]["detail"], got["page:mark-file"]
    assert got["page:mark-band"]["status"] == "info"    # nothing was verified as a banded drawing
    nested = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g><g><use href="sprite.svg#m"/></g></g></svg>'
    assert judge_marks(p, [inline(nested)])["page:mark-file"]["status"] == "warn"
    drawn = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="41" r="9"/></svg>'   # a different drawing, no <use>: still a fail
    assert judge_marks(p, [inline(drawn)])["page:mark-file"]["status"] == "fail"
    assert judge_marks(p, [inline(master, declared="")])["page:mark-file"]["status"] == "pass"        # the master itself, inline
    assert judge_marks(p, [inline(via_use), inline(drawn, sel="body > p > svg")])["page:mark-file"]["status"] == "fail"   # a fail anywhere is not hidden behind a warning


def test_a_mark_that_is_not_seen_a_declared_file_and_a_project_without_logo_files(logo_project, tmp_path):
    p = logo_project
    odd = mark_entry(url="/pages/elsewhere.svg", height=48)
    rows = judge_marks(p, [odd], files={"/pages/elsewhere.svg": "ab" * 32})
    assert rows["page:mark-file"]["status"] == "fail" and "none of the logo files of the project" in rows["page:mark-file"]["detail"]
    other_site = mark_entry(url="https://cdn.example/logo.svg", own=False)
    rows = judge_marks(p, [other_site])
    assert rows["page:mark-file"]["status"] == "warn" and "NOT verified" in rows["page:mark-file"]["detail"] and "another origin" in rows["page:mark-file"]["detail"]
    assert rows["page:mark-band"]["status"] == "info"   # nothing was verified as a banded drawing
    nofile = judge_marks(p, [mark_entry(url=None)])
    assert nofile["page:mark-file"]["status"] == "fail" and "shows no file" in nofile["page:mark-file"]["detail"]
    rows = judge_marks(p, [mark_entry(marked=True, named=False, declared="assets/logo/wordmark.svg")])   # it says wordmark and is the mark
    assert rows["page:mark-file"]["status"] == "fail" and "names assets/logo/wordmark.svg, but this mark is assets/logo/mark.svg" in rows["page:mark-file"]["detail"]
    hidden = judge_marks(p, [mark_entry(visible=False)])   # a mark that is not shown is not judged; the row says so
    assert list(hidden) == ["page:mark-file"] and hidden["page:mark-file"]["status"] == "info" and "1 marked or named" in hidden["page:mark-file"]["detail"]
    (tmp_path / "e").mkdir()
    empty = make_project(tmp_path / "e", slug="empty")   # a project with no logo files has nothing to compare with
    rows = judge_marks(empty, [mark_entry(height=24, nearest_px=1, nearest_sel="body > p")], names=())
    assert [rows[i]["status"] for i in ("page:mark-file", "page:mark-band", "page:mark-clear-space")] == ["skipped", "skipped", "fail"], rows   # the space needs no logo file
    assert not [i for i in rows if i.startswith("page:mark") and rows[i]["status"] == "pass"]
    bare = pagecheck.Ctx(p, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [390], ["light"], qa_rules.load(p)[0], {})
    rep = Report("page-check/x-000000", p)
    pagecheck.mark_rows(rep, {"views": [view(colours=[])]}, bare)   # measurements that hold no mark facts at all are not verified, never a pass
    assert [(r["id"], r["status"]) for r in rep.results] == [("page:mark-file", "skipped")]


def test_the_clear_space_is_a_share_of_the_marks_height_and_the_owner_can_change_it(logo_project):
    p = logo_project
    space = lambda px, height=40: judge_marks(p, [mark_entry(height=height, nearest_px=px, nearest_sel="body > p", nearest_text="Hello")])["page:mark-clear-space"]
    assert space(9.99)["status"] == "fail" and space(10)["status"] == "pass" and space(0)["status"] == "fail"   # 0.25 x 40 px: the edge is clear
    assert judge_marks(p, [mark_entry(height=40)])["page:mark-clear-space"]["status"] == "pass"                 # nothing else on the page
    bad = space(4)
    assert 'body > header > img (40 px high) has body > p "Hello" 4 px away, needs 10 px' in bad["detail"] and "a proposal" in bad["detail"], bad["detail"]
    owner = qa_rules.load(p)[0]
    owner["page"] = {**owner["page"], "clear_space": 0.05}
    owner["_from_file"] = [*owner["_from_file"], "page.clear_space"]
    rows = judge_marks(p, [mark_entry(height=40, nearest_px=4, nearest_sel="body > p")], rules=owner)
    assert rows["page:mark-clear-space"]["status"] == "pass" and "0.05 x the mark's rendered height" in rows["page:mark-clear-space"]["detail"] and "proposal" not in rows["page:mark-clear-space"]["detail"]


def test_the_canonical_form_of_an_svg_ignores_order_and_white_space_and_the_roots_size_but_not_the_drawing():
    ns = 'xmlns="http://www.w3.org/2000/svg"'
    base = f'<svg {ns} viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="Acme mark"><path d="M32 6 58 54H6Z" fill="#0d1b2d"/><circle cx="32" cy="41" r="9" fill="#007d71"/></svg>'
    same = [
        f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- a note -->\n<svg {ns}\n  height="24" width="24" viewBox="0 0 64   64" class="logo" style="display:block">\n<title>Home</title>\n'
        '<path fill="#0d1b2d"\n d="M32  6 58 54H6Z"></path>\n<circle r="9" cy="41" cx="32" fill="#007d71" /></svg>',
        f'<svg {ns} xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 64 64" data-brand-mark="x" id="m" focusable="false"><desc>d</desc>'
        '<path d="M32 6 58 54H6Z" fill="#0d1b2d"/><circle cx="32" cy="41" r="9" fill="#007d71"/></svg>',
        "﻿" + base,
    ]
    want = pagecheck.canonical_svg(base)
    assert want is not None
    for text in same:
        assert pagecheck.canonical_svg(text) == want, text
    differ = [base.replace("#007d71", "#007d72"), base.replace("0 0 64 64", "0 0 64 65"), base.replace("r=\"9\"", "r=\"8\""), base.replace("<circle", "<g><circle").replace("/></svg>", "/></g></svg>"),
              base.replace("</svg>", "<path d=\"M0 0\"/></svg>"), base.replace('<path d="M32 6 58 54H6Z" fill="#0d1b2d"/><circle cx="32" cy="41" r="9" fill="#007d71"/>',
                                                                              '<circle cx="32" cy="41" r="9" fill="#007d71"/><path d="M32 6 58 54H6Z" fill="#0d1b2d"/>'),   # drawn in another order
              base.replace('<path ', '<path stroke="red" ')]
    for text in differ:
        assert pagecheck.canonical_svg(text) != want, text
    # a wordmark drawn with live text: the letters that follow a child element are part of the drawing, not only the letters before it
    word = f'<svg {ns} viewBox="0 0 64 16"><text x="0" y="12">Ac<tspan>m</tspan>e</text></svg>'
    wanted = pagecheck.canonical_svg(word)
    assert wanted is not None
    for text in (word.replace("</tspan>e<", "</tspan>\n  e \n<"), word.replace(">Ac<", ">\nAc<"), word.replace("<text ", "<!-- c --><text ").replace("</tspan>", "</tspan><!-- c -->")):
        assert pagecheck.canonical_svg(text) == wanted, text
    for text in (word.replace("</tspan>e<", "</tspan>ZZZ<"), word.replace("</tspan>e<", "</tspan><"), word.replace("<tspan>m</tspan>e", "<tspan>m</tspan>"), word.replace(">Ac<", "><"),
                 word.replace("<tspan>m</tspan>e", "e<tspan>m</tspan>"), word.replace("</tspan>e<", "</tspan>e</text><text>x<")):   # other letters, none, in another place, or in another element
        assert pagecheck.canonical_svg(text) != wanted, text
    titled = f'<svg {ns} viewBox="0 0 64 16"><text>Ac<title>t</title>me</text></svg>'   # the text after an element that draws nothing still follows the text before it
    assert pagecheck.canonical_svg(titled) == pagecheck.canonical_svg(f'<svg {ns} viewBox="0 0 64 16"><text>Acme</text></svg>')
    assert pagecheck.canonical_svg(titled.replace(">me<", ">ZZ<")) != pagecheck.canonical_svg(f'<svg {ns} viewBox="0 0 64 16"><text>Acme</text></svg>')
    for text in ("", "not xml", "<svg", "<div/>", '<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>', None):
        assert pagecheck.canonical_svg(text) is None, text
    assert pagecheck.twin_of("assets/logo/mark.svg") == "assets/logo/mark-dark.svg" and pagecheck.twin_of("assets/logo/mark-dark.svg") == "assets/logo/mark.svg"
    assert pagecheck.twin_of("assets/logo/mark.png") == "assets/logo/mark.png"


def test_logo_files_are_the_logo_folder_and_the_drawings_the_rules_name_with_their_twins(logo_project, tmp_path):
    p = logo_project
    files = pagecheck.logo_files(p, qa_rules.load(p)[0])
    assert {"assets/logo/mark.svg", "assets/logo/mark-dark.svg", "assets/logo/grid-mark.svg", "assets/logo/grid-mark-master.png"} <= set(files)
    assert files["assets/logo/mark.svg"] == logo_hash(p, "mark.svg")
    (p / "elsewhere").mkdir()
    (p / "elsewhere" / "tool-a.svg").write_text("<svg/>", encoding="utf-8")
    (p / "elsewhere" / "tool-a-dark.svg").write_text("<svg/>", encoding="utf-8")
    outside = tmp_path / "outside.svg"
    outside.write_text("<svg/>", encoding="utf-8")
    os.symlink(outside, p / "assets" / "logo" / "leak.svg")   # a link that leads out of the project is not a logo file
    rules = qa_rules.load(p)[0] | {"bands": [], "marks": qa_rules.validate_marks({"a": {"bands": [{"name": "all", "drawing": "elsewhere/tool-a.svg"}]}})}
    files = pagecheck.logo_files(p, rules)
    assert {"elsewhere/tool-a.svg", "elsewhere/tool-a-dark.svg"} <= set(files) and "assets/logo/leak.svg" not in files
    (tmp_path / "b").mkdir()
    assert pagecheck.logo_files(make_project(tmp_path / "b", slug="bare"), qa_rules.DEFAULTS) == {}


# ---------------------------------------------------------------- fonts and the display face

BRAND_FONT = '@font-face { font-family: "Acme Sans"; src: url(fonts/TestFont-subset.ttf); }'
FONT_PAGE = PAGE.replace("</style>", f"  {BRAND_FONT}\n</style>")   # the clean page, with the brand's face declared (the token stack names "Acme Sans" in the tests that use it)
DISPLAY_PAGE = PAGE.replace("</style>", """  @font-face { font-family: "Acme Display"; src: url(fonts/TestFont-subset.ttf); }
  h1 { font-family: var(--font-display); font-size: 32px; }
</style>""")


def use_font_tokens(p: Path, **stacks: list[str]) -> None:
    """Set font.<name> tokens in the project's token sources (a name that exists is replaced, a new one added) and build them again."""
    mutate_json(p / "tokens" / "primitives.tokens.json", lambda d: d["font"].update({name: {"$value": stack} for name, stack in stacks.items()}))
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr


def install_test_font(p: Path) -> None:
    (p / "pages" / "fonts").mkdir(parents=True, exist_ok=True)
    (p / "pages" / "fonts" / TEST_FONT.name).write_bytes(TEST_FONT.read_bytes())
    (p / "pages" / "fonts" / "broken.woff2").write_bytes(b"this is not a font file " * 20)   # answered with 200, and no browser can read it


def usage(family: str, weight: int = 400, style: str = "normal", sel: str = "body > p", min_px: float = 16, platform=None, **more) -> dict:
    return {"family": family, "weight": weight, "style": style, "stack": f'"{family}", sans-serif', "count": 1, "sel": sel, "min_px": min_px, "min_sel": sel, "min_text": "Text",
            "platform": platform, **more}


def font_view(*entries: dict, faces=(), **more) -> dict:
    return view(font_usage=list(entries), font_faces=list(faces), **more)


def web(glyphs: int = 10) -> dict:
    return {"family": "Inter", "postscript": "Inter-Regular", "custom": True, "glyphs": glyphs}


def system(name: str = "Times", glyphs: int = 10) -> dict:
    return {"family": name, "postscript": name, "custom": False, "glyphs": glyphs}


FONT_TOKENS = {"other": {"font.sans": '"Acme Sans", system-ui, sans-serif', "font.mono": "ui-monospace, monospace", "font.display": '"Acme Display", serif',
                         "dimension.space-1": "4px"}}


def font_ctx(tmp_path: Path, tokens: dict = FONT_TOKENS, rules=None) -> pagecheck.Ctx:
    return pagecheck.Ctx(tmp_path, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [390], ["light"], rules or qa_rules.DEFAULTS, tokens)


def font_row(tmp_path: Path, measures: dict, tokens: dict = FONT_TOKENS, which=pagecheck.font_rows, rules=None) -> dict:
    rep = Report("page-check/x-000000", tmp_path)
    which(rep, measures, font_ctx(tmp_path, tokens, rules))
    (got,) = rep.results
    return got


def test_the_font_tokens_are_read_with_their_aliases_and_without_sizes():
    """No browser: every `font.*` stack of tokens.json `other`, quotes taken off; an alias is followed; a token that holds a size is no stack."""
    assert pagecheck.split_families("\"Acme Sans\", 'Noto  Serif', system-ui,  ,sans-serif") == ["Acme Sans", "Noto Serif", "system-ui", "sans-serif"]
    stacks = pagecheck.font_stacks({"other": {"font.body": "var(--font-sans)", "font.sans": "Inter, sans-serif", "font.size.base": "16px", "font.loop": "var(--font-loop)",
                                              "duration.fast": "150ms", "font.weight": 400}})
    assert stacks == {"font.body": ["Inter", "sans-serif"], "font.sans": ["Inter", "sans-serif"], "font.loop": ["var(--font-loop)"]}   # an alias that points at itself stays as written
    assert pagecheck.font_stacks({"other": {"duration.fast": "150ms"}}) == {} and pagecheck.font_stacks({}) == {}


def test_the_fonts_row_judges_constructed_measurements(tmp_path):
    """No browser: the three outcomes of page:fonts and what is never a pass."""
    loaded = [{"family": "Acme Sans", "weight": "normal", "style": "normal", "status": "loaded"}]
    good = font_view(usage("Acme Sans", platform=[web()]), usage("ui-monospace", sel="body > code", platform=[system("SF Mono")]),
                     usage("serif", sel="body > i", platform=[system()]), faces=loaded)
    got = font_row(tmp_path, {"views": [good]})
    assert got["status"] == "pass" and got["offenders"] == [] and "3 font(s)" in got["detail"], got
    # a family no token stack names fails; a generic one passes only when a stack writes it (monospace is in font.mono, cursive is in none)
    bad = font_row(tmp_path, {"views": [font_view(usage("Georgia", sel="body > h1", platform=[system("Georgia")]), usage("cursive", sel="body > b", platform=[system()]),
                                                  usage("monospace", sel="body > code", platform=[system("Menlo")]))]})
    assert bad["status"] == "fail" and [(o["family"], o["kind"]) for o in bad["offenders"]] == [("Georgia", "not-named"), ("cursive", "not-named")]
    assert 'body > h1 is set in "Georgia", which no font token names' in bad["detail"] and "Acme Sans" in bad["detail"]
    # a declared face that did not load, a declared face nothing covers, a name with no @font-face that is not installed, and an installed font of that name
    broken = [{"family": "Acme Sans", "weight": "normal", "style": "normal", "status": "error"}]
    err = font_row(tmp_path, {"views": [font_view(usage("Acme Sans", platform=[system()]), faces=broken)]})
    assert err["status"] == "fail" and err["offenders"][0]["kind"] == "not-loaded" and "its font file did not load (status error)" in err["detail"] and "Times" in err["detail"]
    idle = font_row(tmp_path, {"views": [font_view(usage("Acme Sans", platform=[system()]), faces=[{**broken[0], "status": "unloaded"}])]})
    assert idle["status"] == "fail" and "none of its @font-face rules covers this text (status unloaded)" in idle["detail"]
    tokens = {"other": {"font.sans": "Georgia, serif"}}
    absent = font_row(tmp_path, {"views": [font_view(usage("Georgia", platform=[system("DejaVu Serif")]))]}, tokens)
    assert absent["status"] == "fail" and "declares no @font-face for it and it is not installed on this machine" in absent["detail"]
    installed = font_row(tmp_path, {"views": [font_view(usage("Georgia", platform=[system("Georgia")]))]}, tokens)
    assert installed["status"] == "pass"
    # part of the glyphs in another font: a warning with the counts; a debugger that could not answer: NOT verified, never a pass
    partly = font_row(tmp_path, {"views": [font_view(usage("Acme Sans", platform=[web(35), system("Helvetica", 3)]), faces=loaded)]})
    assert partly["status"] == "warn" and "3 of 38 glyph(s) are drawn in another font" in partly["detail"] and partly["partly"][0]["kind"] == "partly-another-font"
    for platform, why in ((None, "could not say which font was used (target closed)"), ([], "reported no font")):
        silent = font_row(tmp_path, {"views": [font_view(usage("Acme Sans", platform=platform, platform_error="target closed"), faces=loaded)]})
        assert silent["status"] == "warn" and "NOT verified" in silent["detail"] and why in silent["detail"], silent
    # a later view that breaks what an earlier one passed is still caught, and an entry cut off at the cap is said so
    later = font_row(tmp_path, {"views": [font_view(usage("Acme Sans", platform=[web()]), faces=loaded), font_view(usage("Acme Sans", platform=[system()]), faces=broken, width=1440)]})
    assert later["status"] == "fail" and later["offenders"][0]["width"] == 1440
    cut = font_row(tmp_path, {"views": [font_view(usage("Acme Sans", platform=[web()]), faces=loaded, font_usage_total=75)]})
    assert cut["status"] == "warn" and "NOT verified beyond the first fonts of a view" in cut["detail"]
    # nothing to judge against, or nothing measured, is not verified
    assert font_row(tmp_path, {"views": [good]}, {"other": {"duration.fast": "150ms"}})["status"] == "skipped"
    assert font_row(tmp_path, {"views": []})["status"] == "skipped" and font_row(tmp_path, {"views": [view(error="x")]})["status"] == "skipped"


def test_a_web_font_the_browser_fell_back_to_is_not_the_familys_own_face(tmp_path):
    """No browser: a web font in the answer is a family's own only when the page declares that family and one of its faces loaded. A face in error, or a family the
    page never declares, whose text the browser drew in ANOTHER web font of the page (the body face its stack falls to) is not drawn."""
    tokens = {"other": {"font.sans": '"Acme Sans", system-ui, sans-serif', "font.display": '"Acme Display", "Acme Sans", serif'}}
    sans = {"family": "Acme Sans", "weight": "normal", "style": "normal", "status": "loaded"}
    display = {**sans, "family": "Acme Display"}
    h1 = lambda **kw: usage("Acme Display", weight=700, sel="body > h1", platform=[web()], **kw)   # the answer for the heading: only the fallback web font
    ok = font_row(tmp_path, {"views": [font_view(h1(), usage("Acme Sans", platform=[web()]), faces=[sans, display])]}, tokens)
    assert ok["status"] == "pass", ok   # the control: both faces loaded
    broken = font_row(tmp_path, {"views": [font_view(h1(), usage("Acme Sans", platform=[web()]), faces=[sans, {**display, "status": "error"}])]}, tokens)
    assert broken["status"] == "fail" and [(o["family"], o["kind"], o["faces"]) for o in broken["offenders"]] == [("Acme Display", "not-loaded", ["error"])], broken
    assert 'body > h1 is set in "Acme Display" (weight 700): its font file did not load (status error); Chromium used Inter (web font) 10 glyph(s)' in broken["detail"]
    undeclared = font_row(tmp_path, {"views": [font_view(h1(), usage("Acme Sans", platform=[web()]), faces=[sans])]}, tokens)
    assert undeclared["status"] == "fail" and "declares no @font-face for it and it is not installed on this machine" in undeclared["detail"] and "Inter (web font)" in undeclared["detail"]
    idle = font_row(tmp_path, {"views": [font_view(h1(), usage("Acme Sans", platform=[web()]), faces=[sans, {**display, "status": "unloaded"}])]}, tokens)
    assert idle["status"] == "fail" and "none of its @font-face rules covers this text (status unloaded)" in idle["detail"]
    # an installed font of that name is its own whatever the page declares
    named = font_row(tmp_path, {"views": [font_view(usage("Acme Display", platform=[system("Acme Display")]), faces=[{**display, "status": "error"}])]}, tokens)
    assert named["status"] == "pass"


def test_a_system_face_the_page_does_not_declare_is_looked_for_and_never_waved_through(tmp_path):
    """No browser: Roboto, Noto Sans and the like are also brand web fonts. Not declared by the page, they pass only where an installed font of that name is what the browser
    drew; where it drew something else the row says NOT verified (a warning: the stack is meant to fall through, so it is not a failure). The generic families and the
    operating-system aliases have no font of that name to look for and are the browser's own."""
    tokens = {"other": {"font.sans": 'Roboto, "Helvetica Neue", -apple-system, system-ui, sans-serif'}}
    got = lambda family, platform, faces=(): font_row(tmp_path, {"views": [font_view(usage(family, platform=platform), faces=list(faces))]}, tokens)
    here = got("Roboto", [system("Roboto")])
    assert here["status"] == "pass", here   # installed under that name
    missing = got("Roboto", [system("Times")])
    assert missing["status"] == "warn" and missing["offenders"] == []
    assert 'NOT verified: 1 font(s): "Roboto" (body > p): a system face the page does not declare and this machine does not have; Chromium used Times 10 glyph(s)' in missing["detail"]
    other_web_font = got("Roboto", [web()])
    assert other_web_font["status"] == "warn" and "Chromium used Inter (web font) 10 glyph(s)" in other_web_font["detail"]   # a page that forgot its @font-face
    assert got("Helvetica Neue", [system("Helvetica Neue")])["status"] == "pass" and got("Helvetica Neue", [system("Times")])["status"] == "warn"
    assert got("-apple-system", [system("Times")])["status"] == "pass" and got("system-ui", [system("Times")])["status"] == "pass"
    # declared by the page it is a web font like any other: it must have loaded
    face = {"family": "Roboto", "weight": "normal", "style": "normal", "status": "error"}
    assert got("Roboto", [web()], [face])["status"] == "fail"
    assert got("Roboto", [web()], [{**face, "status": "loaded"}])["status"] == "pass"


def test_the_display_size_row_judges_constructed_measurements(tmp_path):
    """No browser: the minimum applies to the display face, says when it is a proposal, and is an info row when there is no face to tell from body text."""
    row_of = lambda *entries, **kw: font_row(tmp_path, {"views": [font_view(*entries)]}, which=pagecheck.display_size_rows, **kw)
    small, big = usage("Acme Display", sel="body > h1", min_px=14, weight=700), usage("Acme Display", sel="body > h2", min_px=24)
    got = row_of(small, big)
    assert got["status"] == "fail" and got["small"][0]["selector"] == "body > h1" and got["small"][0]["font_size_px"] == 14 and got["smallest_px"] == 14
    assert "under 20 px" in got["detail"] and "a proposal" in got["detail"] and got["proposal"] is True
    assert row_of(big)["status"] == "pass" and "24 px or more" in row_of(big)["detail"]
    assert row_of(usage("Acme Display", min_px=19.99))["status"] == "fail" and row_of(usage("Acme Display", min_px=20))["status"] == "pass"   # 20 is allowed
    assert row_of(usage("Acme Sans", min_px=11))["status"] == "pass" and "no text on the page is set in the display face" in row_of(usage("Acme Sans", min_px=11))["detail"]
    owned = {**qa_rules.DEFAULTS, "page": {**qa_rules.DEFAULTS["page"], "display_min_px": 12}, "_from_file": ["page.display_min_px"]}
    set_by_owner = row_of(small, rules=owned)
    assert set_by_owner["status"] == "pass" and "a proposal" not in set_by_owner["detail"] and "qa/rules.json page.display_min_px" in set_by_owner["detail"] and set_by_owner["proposal"] is False
    assert row_of(small, rules={**owned, "page": {**owned["page"], "display_min_px": 15}})["status"] == "fail"
    none = font_row(tmp_path, {"views": [font_view(small)]}, {"other": {"font.sans": "Inter, sans-serif"}}, pagecheck.display_size_rows)
    assert none["status"] == "info" and "no font.display token" in none["detail"]
    same = font_row(tmp_path, {"views": [font_view(small)]}, {"other": {"font.sans": "Inter, sans-serif", "font.display": "Inter, sans-serif"}}, pagecheck.display_size_rows)
    assert same["status"] == "info" and "also the first family of font.sans" in same["detail"]
    assert font_row(tmp_path, {"views": []}, which=pagecheck.display_size_rows)["status"] == "skipped"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_family_the_tokens_do_not_name_fails(acme):
    page = write_page(acme)
    r, rep = check_page(acme)   # the control: the page sets its text in the brand's stack
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:fonts")["status"] == "pass"
    mutate(page, "font-family: var(--font-sans);", "font-family: Georgia, serif;")
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:fonts")
    assert bad["status"] == "fail" and {(o["family"], o["kind"]) for o in bad["offenders"]} == {("Georgia", "not-named")}
    assert {o["weight"] for o in bad["offenders"]} == {400, 700} and all(o["selector"].startswith("body") for o in bad["offenders"])
    assert 'is set in "Georgia", which no font token names' in bad["detail"] and "ui-sans-serif" in bad["detail"]
    # a generic family counts only when a stack names it: the Acme stack names sans-serif and system-ui, not monospace
    mutate(page, "font-family: Georgia, serif;", "font-family: monospace;")
    r, rep = check_page(acme)
    assert r.returncode == 1 and {o["family"] for o in row(rep, "page:fonts")["offenders"]} == {"monospace"}, r.stdout + r.stderr
    assert row(rep, "page:load:390-light")["status"] == "pass" and row(rep, "page:colours:light")["status"] == "pass"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_token_family_whose_file_does_not_load_fails(acme):
    use_font_tokens(acme, sans=["Acme Sans", "system-ui", "sans-serif"])
    install_test_font(acme)
    page = write_page(acme, FONT_PAGE)
    r, rep = check_page(acme)   # the control: the face loads and is what the browser drew
    assert r.returncode == 0, r.stdout + r.stderr
    ok = row(rep, "page:fonts")
    assert ok["status"] == "pass" and {f["family"] for f in ok["fonts"]} == {"Acme Sans"} and all(any(p["custom"] for p in f["platform"]) for f in ok["fonts"]), ok
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    assert [(f["family"], f["status"]) for f in measures["views"][0]["font_faces"]] == [("Acme Sans", "loaded")]
    # the break: the face points at a file that answers and is no font; the browser reports the face as in error and draws the text in its fallback
    mutate(page, "url(fonts/TestFont-subset.ttf)", "url(fonts/broken.woff2)")
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:fonts")
    assert bad["status"] == "fail" and {o["kind"] for o in bad["offenders"]} == {"not-loaded"} and all(o["faces"] == ["error"] for o in bad["offenders"])
    assert 'is set in "Acme Sans"' in bad["detail"] and "its font file did not load (status error)" in bad["detail"] and "Chromium used" in bad["detail"]
    assert not any(p["custom"] for o in bad["offenders"] for p in o["platform"])
    assert row(rep, "page:load:390-light")["status"] == "pass"   # the file was served: only the fonts row sees that nothing could be read from it
    # and a page that declares no face at all, for a family that is not installed
    mutate(page, '@font-face { font-family: "Acme Sans"; src: url(fonts/broken.woff2); }', "")
    r, rep = check_page(acme)
    assert r.returncode == 1 and "declares no @font-face for it and it is not installed on this machine" in row(rep, "page:fonts")["detail"], r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_display_face_that_fails_is_not_passed_by_the_body_web_font_its_stack_falls_to(acme):
    """The stack is `"Acme Display", "Acme Sans", serif`. When Acme Display does not load the browser draws the heading in Acme Sans, which IS a loaded web font of the page:
    the heading must still fail, because it is not drawn in the display face."""
    use_font_tokens(acme, sans=["Acme Sans", "system-ui", "sans-serif"], display=["Acme Display", "Acme Sans", "serif"])
    install_test_font(acme)
    page = write_page(acme, DISPLAY_PAGE.replace("</style>", f"  {BRAND_FONT}\n</style>"))
    r, rep = check_page(acme)   # the control: both faces load
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(rep, "page:fonts")["status"] == "pass"
    # the break: the display face points at a file that is no font
    mutate(page, '@font-face { font-family: "Acme Display"; src: url(fonts/TestFont-subset.ttf); }', '@font-face { font-family: "Acme Display"; src: url(fonts/broken.woff2); }')
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:fonts")
    assert bad["status"] == "fail", bad
    assert [(o["family"], o["kind"], o["faces"]) for o in bad["offenders"]] == [("Acme Display", "not-loaded", ["error"])]
    (offender,) = bad["offenders"]
    assert offender["platform"] and all(p["custom"] for p in offender["platform"])   # what Chromium drew the heading in: the body web font, which is why it used to pass
    assert 'is set in "Acme Display" (weight 700): its font file did not load (status error)' in bad["detail"] and "(web font)" in bad["detail"]
    # and a page that never declares the display face at all, with the same fallback
    mutate(page, '@font-face { font-family: "Acme Display"; src: url(fonts/broken.woff2); }', "")
    r, rep = check_page(acme)
    assert r.returncode == 1 and "declares no @font-face for it and it is not installed on this machine" in row(rep, "page:fonts")["detail"], r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_inline_text_in_another_font_is_not_charged_to_the_paragraph_around_it(acme):
    """`code` inside a paragraph is set in the mono stack. The debugger answers for an element and everything in it, so without taking the code off, the paragraph looked as if
    a few of its own glyphs were drawn in another font. The paragraph is the only text in the body face, so it is the probe whatever it holds."""
    use_font_tokens(acme, sans=["Acme Sans", "system-ui", "sans-serif"], mono=["ui-monospace", "monospace"])
    install_test_font(acme)
    text = "Install the widget with <code>npm i widget</code> and then run it."
    body = "  <h1>Acme hand tools</h1>\n  <p>Every tool has a published spare-parts list.</p>\n  <p><a href=\"#parts\">Spare parts</a></p>\n"
    assert body in FONT_PAGE
    write_page(acme, FONT_PAGE.replace("</style>", "  code { font-family: var(--font-mono); }\n</style>").replace(body, f"  <p>{text}</p>\n"))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    fonts = row(rep, "page:fonts")
    assert fonts["status"] == "pass" and fonts["partly"] == [], fonts
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    sans = next(u for u in v["font_usage"] if u["family"] == "Acme Sans")
    assert sans["sel"] == "body > main > p" and sans["inline_other"] == 1
    own = len("Install the widget with  and then run it.")   # 41 glyphs, 12 more with the code; a space that ends a wrapped line at 390 px is not drawn, so one less is the same text
    assert own - 1 <= sum(p["glyphs"] for p in sans["platform"]) <= own and all(p["custom"] for p in sans["platform"])
    assert {u["family"] for u in v["font_usage"]} == {"Acme Sans", "ui-monospace"}


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_display_text_under_the_minimum_fails_and_a_brand_with_no_display_face_gets_an_info_row(acme):
    page = write_page(acme)
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    info = row(rep, "page:display-size")
    assert info["status"] == "info" and "no font.display token" in info["detail"]   # Acme has no display face
    use_font_tokens(acme, sans=["Acme Sans", "system-ui", "sans-serif"], display=["Acme Display", "serif"])
    install_test_font(acme)
    page = write_page(acme, DISPLAY_PAGE.replace("</style>", f"  {BRAND_FONT}\n</style>"))
    r, rep = check_page(acme)   # the heading is 32 px in the display face
    assert r.returncode == 0, r.stdout + r.stderr
    ok = row(rep, "page:display-size")
    assert ok["status"] == "pass" and ok["display_face"] == "Acme Display" and ok["smallest_px"] == 32 and "32 px or more" in ok["detail"]
    assert "a proposal" in ok["detail"] and ok["proposal"] is True and row(rep, "page:fonts")["status"] == "pass"
    mutate(page, "font-size: 32px;", "font-size: 14px;")
    r, rep = check_page(acme)
    assert r.returncode == 1, r.stdout + r.stderr
    bad = row(rep, "page:display-size")
    assert bad["status"] == "fail" and [(o["selector"], o["font_size_px"]) for o in bad["small"]] == [("body > main > h1", 14)] and "under 20 px" in bad["detail"]
    assert row(rep, "page:fonts")["status"] == "pass"   # the face is the brand's and is drawn; only its size is wrong
    mutate_json(acme / "qa" / "rules.json", lambda d: d.__setitem__("page", {"display_min_px": 12}))   # the owner sets the minimum: no longer a proposal
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    kept = row(rep, "page:display-size")
    assert kept["status"] == "pass" and kept["proposal"] is False and "a proposal" not in kept["detail"] and kept["minimum_px"] == 12


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_fonts_collector_reports_the_faces_and_what_chromium_used(acme):
    """The facts: every FontFace with its status, and for each (first family, weight, style) of a shown text the platform font the browser drew it in. Hidden text is not
    a font in use, and an entry holds the smallest size of its elements (tests/node/pagefonts.test.mjs proves the probe mark is taken off again)."""
    use_font_tokens(acme, sans=["Acme Sans", "system-ui", "sans-serif"])
    install_test_font(acme)
    page = write_page(acme, FONT_PAGE.replace("</style>", """  @font-face { font-family: "Broken Face"; src: url(fonts/broken.woff2); }
  @font-face { font-family: "Unused Face"; src: url(fonts/TestFont-subset.ttf); }
  .broken { font-family: "Broken Face", serif; font-size: 15px; } .broken-small { font-family: "Broken Face", serif; font-size: 11px; }
  .gone { display: none; font-family: "Hidden Family"; } .fade { opacity: 0; font-family: "Faded Family"; }
</style>""").replace("</main>", """<p class="broken">Broken face</p><p class="broken-small">Broken face, small</p><p class="gone">hidden</p><p class="fade">faded</p>
</main>"""))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr   # Broken Face is no token's family
    measures = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))
    (v,) = measures["views"]
    assert {f["family"]: f["status"] for f in v["font_faces"]} == {"Acme Sans": "loaded", "Broken Face": "error", "Unused Face": "unloaded"}
    by = {(u["family"], u["weight"]): u for u in v["font_usage"]}
    assert not {fam for fam, _ in by} & {"Hidden Family", "Faded Family"}
    assert {fam for fam, _ in by} == {"Acme Sans", "Broken Face"} and by[("Acme Sans", 700)]["sel"] == "body > main > h1"
    assert any(p["custom"] for p in by[("Acme Sans", 400)]["platform"]) and all(set(p) == {"family", "postscript", "custom", "glyphs"} for p in by[("Acme Sans", 400)]["platform"])
    broken = by[("Broken Face", 400)]
    assert broken["count"] == 2 and broken["min_px"] == 11 and "p.broken-small" in broken["min_sel"] and broken["stack"].startswith('"Broken Face"')
    assert not any(p["custom"] for p in broken["platform"]) and "platform_error" not in broken
    assert v["font_usage"][0]["family"] == "Acme Sans"   # document order
    assert "font_usage_total" not in v and "font_faces_total" not in v
    assert not any("probe" in u for u in v["font_usage"])


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_face_that_lacks_a_character_the_text_uses_warns_and_does_not_fail(acme):
    use_font_tokens(acme, sans=["Acme Sans", "system-ui", "sans-serif"])
    install_test_font(acme)
    write_page(acme, FONT_PAGE.replace("<h1>Acme hand tools</h1>", "<h1>Acme hand tools \u0436</h1>"))   # a Cyrillic letter the Latin face does not hold: the browser draws it in another font
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    warned = row(rep, "page:fonts")
    assert warned["status"] == "warn" and "glyph(s) are drawn in another font" in warned["detail"] and warned["offenders"] == []
    assert [(o["family"], o["kind"]) for o in warned["partly"]] == [("Acme Sans", "partly-another-font")]


# ---------------------------------------------------------------- the brand's own rules (qa/rules.json page.rules)

ONE_MARK = {"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"}
SHORT_BUTTONS = {"id": "short-buttons", "kind": "max-words-per-control", "max": 3, "g4": "a button says at most three words"}
ACCENT_ROOM = {"id": "accent-room", "kind": "words-under-accent", "selector": "em.accent", "min": 2, "max": 6, "g4": "the accent has room"}


def set_page_rules(p: Path, *rules: dict) -> None:
    """qa/rules.json gets this list as page.rules (what else it holds stays)."""
    f = p / "qa" / "rules.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["page"] = {**doc.get("page", {}), "rules": list(rules)}
    f.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def record_g4(p: Path, line: str = "(rule) one mark per screen") -> None:
    """The owner approves the system rules at G4: the "(rule)" line is in BRAND-STATE.md Rules (G4) and the gate is recorded."""
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", f"- {line}")
    r = bc("state", "--record", "G4", "system rules GO", project=p)
    assert r.returncode == 0, r.stdout + r.stderr


def rule_row(rep: dict, rid: str) -> dict:
    return row(rep, f"page:rule:{rid}")


def test_the_page_rules_of_qa_rules_are_validated_and_normalised(tmp_path):
    """No browser: a good list loads with its strings stripped, a rule keeps only the keys of its kind, and the page block still takes the other keys beside it."""
    p = make_project(tmp_path)
    (p / "qa").mkdir()
    rules = [{"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "  one   mark per\tscreen "},
             {"id": "short-buttons", "kind": "max-words-per-control", "max": 0, "g4": "g", "selector": " .cta "},
             {"id": "calm-accent", "kind": "words-under-accent", "selector": "em", "min": 2, "g4": "g"},
             {"id": "calm-accent-2", "kind": "words-under-accent", "selector": "b", "max": 4, "g4": "g"},
             {"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "g"}]
    (p / "qa" / "rules.json").write_text(json.dumps({"schema": 1, "page": {"rules": rules, "clear_space": 0.5}}), encoding="utf-8")
    loaded, source = qa_rules.load(p)
    assert source == "qa/rules.json" and loaded["page"]["clear_space"] == 0.5 and "page.rules" in loaded["_from_file"]
    assert loaded["page"]["rules"] == [{"id": "one-mark", "kind": "max-marks-per-view", "g4": "one mark per screen", "max": 1},
                                       {"id": "short-buttons", "kind": "max-words-per-control", "g4": "g", "selector": ".cta", "max": 0},
                                       {"id": "calm-accent", "kind": "words-under-accent", "g4": "g", "selector": "em", "min": 2},
                                       {"id": "calm-accent-2", "kind": "words-under-accent", "g4": "g", "selector": "b", "max": 4},
                                       {"id": "no-eyebrow", "kind": "tell", "g4": "g", "tell": "eyebrow"}]
    assert qa_rules.load(make_project(tmp_path, slug="plain"))[0]["page"]["rules"] == []   # no rules: nothing is asked and no row is added


def bad_rule_blocks() -> list:
    ok = {"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"}
    words = {"id": "short-buttons", "kind": "max-words-per-control", "max": 3, "g4": "g"}
    accent = {"id": "accent", "kind": "words-under-accent", "selector": "em", "min": 1, "g4": "g"}
    return [{"rules": [{**ok, "kind": "max-links-per-view"}]}, {"rules": [{**ok, "kind": 7}]},                  # an unknown kind
            {"rules": [{**ok, "colour": "red"}]}, {"rules": [{**ok, "selector": "img"}]}, {"rules": [{**accent, "tell": "eyebrow"}]},   # a key the kind does not have
            {"rules": [{k: v for k, v in ok.items() if k != "max"}]}, {"rules": [{k: v for k, v in accent.items() if k != "selector"}]},   # a key the kind needs
            {"rules": [{k: v for k, v in accent.items() if k != "min"}]}, {"rules": [{"id": "t", "kind": "tell", "g4": "g"}]},
            {"rules": [{k: v for k, v in ok.items() if k != "g4"}]}, {"rules": [{**ok, "g4": ""}]}, {"rules": [{**ok, "g4": "  "}]}, {"rules": [{**ok, "g4": 3}]},
            {"rules": [{**ok, "id": "One Mark"}]}, {"rules": [{**ok, "id": ""}]}, {"rules": [{k: v for k, v in ok.items() if k != "id"}]}, {"rules": [ok, ok]},
            {"rules": [{**ok, "max": -1}]}, {"rules": [{**ok, "max": 1.5}]}, {"rules": [{**ok, "max": True}]}, {"rules": [{**ok, "max": "1"}]},
            {"rules": [{**accent, "max": 2, "min": 3}]}, {"rules": [{**words, "selector": ""}]}, {"rules": [{**words, "selector": 3}]}, {"rules": [{**words, "selector": "x" * 501}]},
            {"rules": [{"id": "t", "kind": "tell", "tell": "", "g4": "g"}]}, {"rules": ["one mark"]}, {"rules": [None]}]


@pytest.mark.parametrize("block", bad_rule_blocks())
def test_an_unknown_rule_kind_or_key_is_a_usage_error(tmp_path, block):
    p = make_project(tmp_path)
    write_page(p)
    (p / "qa").mkdir()
    (p / "qa" / "rules.json").write_text(json.dumps({"schema": 1, "page": block}), encoding="utf-8")
    r = bc("page-check", "pages/index.html", project=p)
    assert r.returncode == 2 and "qa/rules.json" in r.stderr and "page.rules" in r.stderr, r.stderr
    assert page_reports(p) == []   # refused before anything was opened or written


def test_the_rules_ask_the_browser_only_for_what_they_need():
    """No browser: the request names each selector once, in the order of the rules, and lists only the rules measured in the page's text; marks and tells need nothing."""
    rules = [ONE_MARK, {**SHORT_BUTTONS, "selector": ".cta"}, ACCENT_ROOM, {"id": "second", "kind": "words-under-accent", "selector": ".cta", "min": 1, "g4": "g"},
             {"id": "plain", "kind": "max-words-per-control", "max": 2, "g4": "g"}, {"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "g"}]
    selectors, asks = pagecheck.rule_request(rules)
    assert selectors == [".cta", "em.accent"]
    assert asks == [{"id": "short-buttons", "kind": "max-words-per-control", "selector": ".cta"}, {"id": "accent-room", "kind": "words-under-accent", "selector": "em.accent"},
                    {"id": "second", "kind": "words-under-accent", "selector": ".cta"}, {"id": "plain", "kind": "max-words-per-control"}]
    assert pagecheck.rule_request([]) == ([], []) and pagecheck.rule_request([ONE_MARK]) == ([], [])


def judge_rules(p: Path, rules: list[dict], views: list[dict]) -> dict[str, dict]:
    """rule_rows on constructed measurements: the page rules are `rules`, the views are as the browser would have measured them."""
    loaded = qa_rules.load(p)[0]
    loaded["page"]["rules"] = qa_rules.validate_page_rules(rules)
    ctx = pagecheck.Ctx(p, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [390], ["light"], loaded, {})
    rep = Report("page-check/x-000000", p)
    pagecheck.rule_rows(rep, {"views": views}, ctx)
    return {r["id"].removeprefix("page:rule:"): r for r in rep.results}


def tall_view(marks: list[dict], height: int = 3000, vh: int = 800, **more) -> dict:
    return {**view("light", marks=marks, images=[], resources={}, height=height, **more), "viewport": {"width": 390, "height": vh}}


def at(y: float, h: float = 40, sel: str = "body > img") -> dict:
    return mark_entry(sel=sel, height=h, rect={"x": 0, "y": y, "width": h, "height": h})


def test_marks_are_counted_in_screens_one_viewport_high_stepped_by_half_a_viewport(tmp_path):
    """No browser. Windows are 800 px high and start every 400 px; a mark is in the windows that hold the vertical middle of its box."""
    assert pagecheck.mark_windows(3000, 800)[:3] == [(0.0, 800.0), (400.0, 1200.0), (800.0, 1600.0)] and pagecheck.mark_windows(3000, 800)[-1] == (2400.0, 3200.0)
    assert pagecheck.mark_windows(500, 800) == [(0.0, 800.0)] and pagecheck.mark_windows(None, 800) == [(0.0, 800.0)] and pagecheck.mark_windows(800, 800) == [(0.0, 800.0)]
    p = make_project(tmp_path)
    count = lambda *ys, **kw: judge_rules(p, [ONE_MARK], [tall_view([at(y, sel=f"img:nth-of-type({i})") for i, y in enumerate(ys, 1)], **kw)])["one-mark"]["most_in_one_screen"]
    assert count() == 0 and count(100) == 1
    assert count(100, 700) == 2          # middles 120 and 720: both in the first window
    assert count(100, 1000) == 1         # middles 120 and 1020: 900 apart, no window holds both
    assert count(500, 1000) == 2         # middles 520 and 1020: the window from 400 to 1200
    assert count(0, 400, 800) == 2       # middles 20, 420, 820: no 800 px window from a multiple of 400 holds all three
    assert count(100, 1000, 2000, 2900) == 1 and count(2900, 2950, height=3000) == 2   # a mark at the very end of the page is in the last window
    assert count(100, 160, 220, vh=800, height=300) == 3   # a page shorter than the screen is one screen
    twin = at(100, sel="img.one")
    assert judge_rules(p, [ONE_MARK], [tall_view([twin, {**twin, "kind": "img"}, {**at(100, sel="img.two"), "named": False, "marked": False}])])["one-mark"]["most_in_one_screen"] == 1   # the same box found twice, and an image that is no mark
    hidden = judge_rules(p, [ONE_MARK], [tall_view([at(100), {**at(120, sel="img.hidden"), "visible": False}])])["one-mark"]
    assert hidden["most_in_one_screen"] == 1 and hidden["status"] == "pass", hidden   # a mark that is not shown is not in a screen
    pseudo = judge_rules(p, [ONE_MARK], [tall_view([at(100), mark_entry(sel="header::before", height=None, pseudo="::before", height_px=40)])])["one-mark"]
    assert pseudo["status"] == "warn" and "NOT verified: header::before" in pseudo["detail"], pseudo   # a pseudo-element has no box to place: said, never counted


def test_a_rule_is_tied_by_its_g4_words_in_a_recorded_rule_line(tmp_path):
    """No browser. A broken rule fails only when G4 is recorded and one recorded "(rule)" line holds its g4 words (white space and letter case ignored)."""
    p = make_project(tmp_path)
    two = [tall_view([at(100, sel="img.a"), at(300, sel="img.b")])]
    verdict = lambda: judge_rules(p, [ONE_MARK], two)["one-mark"]
    w = verdict()   # BRAND-STATE.md has no G4 and no rule line
    assert w["status"] == "warn" and w["tied"] is False and w["g4_line"] is None and "G4 is not recorded yet" in w["detail"] and "not a recorded G4 rule line yet" in w["detail"], w
    assert "2 brand marks in one screen, the rule allows 1" in w["detail"] and w["most_in_one_screen"] == 2 and w["rule"]["g4"] == "one mark per screen"
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule)  One MARK   per\tscreen, always")   # the line is written, the gate is not
    assert verdict()["status"] == "warn" and "G4 is not recorded yet" in verdict()["detail"]
    assert bc("state", "--record", "G4", "GO", project=p).returncode == 0
    f = verdict()
    assert f["status"] == "fail" and f["tied"] is True and f["g4_line"] == "(rule)  One MARK   per\tscreen, always" and "tied to the recorded G4 line" in f["detail"], f
    ok = judge_rules(p, [ONE_MARK], [tall_view([at(100, sel="img.a"), at(1500, sel="img.b")])])["one-mark"]
    assert ok["status"] == "pass" and "a recorded G4 rule" in ok["detail"] and ok["tied"] is True, ok
    other = judge_rules(p, [{**ONE_MARK, "g4": "two marks are fine"}], two)["one-mark"]   # G4 is recorded, but no line holds these words
    assert other["status"] == "warn" and other["tied"] is False and 'holds "two marks are fine"' in other["detail"] and "not a recorded G4 rule line yet" in other["detail"], other
    (p / "BRAND-STATE.md").unlink()
    gone = verdict()
    assert gone["status"] == "warn" and "BRAND-STATE.md cannot be read" in gone["detail"], gone


def test_a_short_g4_text_ties_a_rule_to_a_recorded_line_only_as_the_whole_line(tmp_path):
    """No browser. `rule`, `mark` or `per` are in some recorded "(rule)" line (the marker itself is "(rule)"), so they tie nothing: the g4 words need two content words of the line, or the whole line."""
    p = make_project(tmp_path)
    two = [tall_view([at(100, sel="img.a"), at(300, sel="img.b")])]
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule) Smart directions only\n- (rule) No one marks the page twice\n- (rule) One mark per screen, always\n- (rule) Calm")
    assert bc("state", "--record", "G4", "GO", project=p).returncode == 0
    verdict = lambda g4: judge_rules(p, [{**ONE_MARK, "g4": g4}], two)["one-mark"]
    for short in ("rule", "(rule)", "mark", "one", "per", "the mark", "a per", "calm always"):   # no content word, one, or two words that are not together in a line
        w = verdict(short)
        assert w["status"] == "warn" and w["tied"] is False and w["g4_line"] is None and "not a recorded G4 rule line yet" in w["detail"], (short, w)
    assert "too short" in verdict("rule")["detail"] and "at least 2 content words" in verdict("rule")["detail"] and "holds" in verdict("calm always")["detail"]
    for piece in ("art direction", "ne mark", "e mark per scr", "one marks per"):   # pieces of words, not words of a line: "smart directions", "no one marks", "mark per screen"
        w = verdict(piece)
        assert w["status"] == "warn" and w["tied"] is False and w["g4_line"] is None and "holds" in w["detail"], (piece, w)
    for words, line in (("one mark", "(rule) One mark per screen, always"), ("mark PER screen", "(rule) One mark per screen, always"), ("(rule) one mark per screen, always", "(rule) One mark per screen, always"),
                        ("Calm", "(rule) Calm"), ("(rule)  calm", "(rule) Calm")):   # two content words of a line, or a line whole (with or without its marker)
        f = verdict(words)
        assert f["status"] == "fail" and f["tied"] is True and f["g4_line"] == line, (words, f)
    # the earlier line "no one marks the page twice" holds "one mark" only inside "marks": "one mark" ties the later line that holds it as words, and "no one marks" ties the earlier one
    assert verdict("one mark")["g4_line"] == "(rule) One mark per screen, always" and verdict("no one marks")["g4_line"] == "(rule) No one marks the page twice"


def test_a_run_that_measured_nothing_is_not_verified_for_every_kind_of_rule(tmp_path):
    p = make_project(tmp_path)
    rows = judge_rules(p, [{"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "no eyebrow"}, ONE_MARK, SHORT_BUTTONS, ACCENT_ROOM], [])
    assert {k: rows[k]["status"] for k in ("no-eyebrow", "one-mark", "short-buttons", "accent-room")} == dict.fromkeys(("no-eyebrow", "one-mark", "short-buttons", "accent-room"), "skipped")
    assert all("not verified: no view was measured" in rows[k]["detail"] for k in ("no-eyebrow", "one-mark", "short-buttons", "accent-room"))
    failed_view = [{"width": 390, "scheme": "light", "viewport": {"width": 390, "height": 844}, "error": "could not load"}]
    assert judge_rules(p, [ONE_MARK], failed_view)["one-mark"]["status"] == "skipped"
    assert judge_rules(p, [{"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "no eyebrow"}], failed_view)["no-eyebrow"]["status"] == "skipped"


def test_the_words_rules_judge_constructed_facts(tmp_path):
    """No browser: the limit is exceeded only by more words than `max`; the accent window is min to max; the browser's complaint about a selector fails the row."""
    p = make_project(tmp_path)
    control = lambda words, text="x", sel="button": {"sel": sel, "text": text, "words": words, "via": "text"}
    facts = lambda *items: {"kind": "max-words-per-control", "selector": None, "matched": len(items), "shown": len(items), "items": list(items)}
    on = lambda rule_facts: [{**view("light"), "rule_facts": rule_facts}]
    rows = judge_rules(p, [SHORT_BUTTONS], on({"short-buttons": facts(control(3), control(2))}))
    assert rows["short-buttons"]["status"] == "pass" and rows["short-buttons"]["longest"] == 3 and rows["short-buttons"]["controls_checked"] == 2, rows
    rows = judge_rules(p, [SHORT_BUTTONS], on({"short-buttons": facts(control(5, "Get your free quote now", "button.cta"), control(4, "Get a quote", "a.btn"), control(3))}))
    bad = rows["short-buttons"]
    assert bad["status"] == "warn" and [(o["selector"], o["words"]) for o in bad["offenders"]] == [("button.cta", 5), ("a.btn", 4)] and 'button.cta "Get your free quote now" says 5 words' in bad["detail"], bad
    acc = lambda around: {"kind": "words-under-accent", "selector": "em", "matched": 1, "shown": 1, "items": [{"sel": "em", "parent_sel": "h1", "text": "x", "parent_text": "a b c", "own_words": 1,
                                                                                                            "parent_words": around + 1, "around_words": around}]}
    for around, status in ((1, "warn"), (2, "pass"), (6, "pass"), (7, "warn")):   # ACCENT_ROOM asks for 2 to 6 words around the accent
        assert judge_rules(p, [ACCENT_ROOM], on({"accent-room": acc(around)}))["accent-room"]["status"] == status, around
    assert "the rule asks for 2 to 6" in judge_rules(p, [ACCENT_ROOM], on({"accent-room": acc(7)}))["accent-room"]["detail"]
    assert [pagecheck._bound({"min": lo, "max": hi}) for lo, hi in ((2, 6), (3, 3), (3, None), (None, 4), (0, 0))] == ["2 to 6", "exactly 3", "at least 3", "at most 4", "exactly 0"]
    refused = {"accent-room": {"kind": "words-under-accent", "selector": "em[", "error": "'em[' is not a valid selector"}}
    row_ = judge_rules(p, [{**ACCENT_ROOM, "selector": "em["}], on(refused))["accent-room"]
    assert row_["status"] == "fail" and "not valid CSS" in row_["detail"] and "em[" in row_["detail"] and row_["tied"] is False, row_   # failed whether or not it is tied
    none = judge_rules(p, [ACCENT_ROOM], on({"accent-room": {"kind": "words-under-accent", "selector": "em.accent", "matched": 0, "shown": 0, "items": []}}))["accent-room"]
    assert none["status"] == "pass" and "matches no shown element" in none["detail"], none


CONTROLS_STYLE = """  main { padding: 8px; }
  button, input, .cta { display: inline-block; border: 0; margin: 4px; padding: 4px; font: inherit; color: var(--color-text); background: var(--color-bg); }
"""


def controls_page(body: str) -> str:
    return PAGE.replace("</style>", CONTROLS_STYLE + "</style>").replace("<p><a href=\"#parts\">Spare parts</a></p>", body)


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_four_word_button_fails_a_three_word_rule(acme):
    page = write_page(acme, controls_page("<p><button>Get a free quote</button> <button>Contact us</button></p>"))
    set_page_rules(acme, SHORT_BUTTONS)
    record_g4(acme, "(rule) a button says at most three words")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = rule_row(rep, "short-buttons")
    assert bad["status"] == "fail" and bad["tied"] is True and bad["g4_line"] == "(rule) a button says at most three words", bad
    assert [(o["selector"], o["text"], o["words"]) for o in bad["offenders"]] == [("body > main > p:nth-of-type(2) > button:nth-of-type(1)", "Get a free quote", 4)], bad
    assert 'says 4 words' in bad["detail"] and bad["max"] == 3 and bad["longest"] == 4 and bad["controls_checked"] == 2
    assert row(rep, "page:colours:light")["status"] == "pass" and row(rep, "page:fonts")["status"] == "pass"   # the page is otherwise the brand's: only the button is long
    mutate(page, "Get a free quote", "Get a quote")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = rule_row(rep, "short-buttons")
    assert ok["status"] == "pass" and ok["longest"] == 3 and "the longest says 3 word(s)" in ok["detail"] and ok["offenders"] == [], ok


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_two_marks_in_one_screen_fail_once_the_g4_line_is_recorded(acme):
    page = write_page(acme, mark_page(img("mark.svg", 48) + img("mark.svg", 48), ".mark + .mark { margin-top: 20px; }\n"))
    set_page_rules(acme, ONE_MARK)
    r, rep = check_page(acme, "--schemes", "light")   # the rule is not yet a recorded G4 line: a warning, and the exit code stays 0
    assert r.returncode == 0, r.stdout + r.stderr
    w = rule_row(rep, "one-mark")
    assert w["status"] == "warn" and w["tied"] is False and w["most_in_one_screen"] == 2 and "not a recorded G4 rule line yet" in w["detail"], w
    record_g4(acme)
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = rule_row(rep, "one-mark")
    assert bad["status"] == "fail" and bad["tied"] is True and bad["g4_line"] == "(rule) one mark per screen" and bad["max"] == 1, bad
    assert bad["screen"] == {"width": 390, "scheme": "light", "top": 0.0, "bottom": 844.0} and [m["y"] for m in bad["marks"]] == [0, 68], bad
    assert "2 brand marks in one screen, the rule allows 1" in bad["detail"] and "body > header > img.mark:nth-of-type(1) (0 px down)" in bad["detail"], bad["detail"]
    assert {k: v["status"] for k, v in mark_rows_of(rep).items()} == {"page:mark-file": "pass", "page:mark-band": "pass", "page:mark-clear-space": "pass"}   # the marks are right: there are two
    mutate(page, "margin-top: 20px;", "margin-top: 1500px;")   # the second mark is a screen and a half further down
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = rule_row(rep, "one-mark")
    assert ok["status"] == "pass" and ok["most_in_one_screen"] == 1 and "a recorded G4 rule" in ok["detail"], ok


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_untied_rule_only_warns(acme):
    write_page(acme, mark_page(img("mark.svg", 48) + img("mark.svg", 48), ".mark + .mark { margin-top: 20px; }\n"))
    set_page_rules(acme, ONE_MARK)
    record_g4(acme, "(rule) the accent is a fill, never text")   # G4 is recorded, but with another line: the rule is only a proposal
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    w = rule_row(rep, "one-mark")
    assert w["status"] == "warn" and w["tied"] is False and w["g4_line"] is None and 'holds "one mark per screen"' in w["detail"] and "only a warning" in w["detail"], w
    assert "G4 is not recorded" not in w["detail"]
    assert rep["status"] == "pass"   # a warning does not fail the report
    set_page_rules(acme, {**ONE_MARK, "g4": "the accent is a fill"})   # the words are in a recorded line now: the same break fails
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1 and rule_row(rep, "one-mark")["status"] == "fail" and rep["status"] == "fail", r.stdout + r.stderr


ACCENT_PAGE_BODY = """<h1>Build <em class="accent">faster</em> every day</h1>
  <h2>Now <em class="accent">go</em></h2>
  <p>Every tool has a published spare-parts list.</p>"""


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_words_under_an_accent_are_counted(acme):
    write_page(acme, PAGE.replace("</style>", "  em.accent { font-style: normal; font-weight: 700; }\n</style>").replace(
        "<h1>Acme hand tools</h1>\n  <p>Every tool has a published spare-parts list.</p>", ACCENT_PAGE_BODY))
    record_g4(acme, "(rule) the accent has room")
    set_page_rules(acme, ACCENT_ROOM)   # 2 to 6 words around an accent: "Build ... every day" has 3, "Now ..." has 1
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = rule_row(rep, "accent-room")
    assert bad["status"] == "fail" and bad["accents_checked"] == 2 and (bad["min"], bad["max"]) == (2, 6), bad
    assert [(o["selector"], o["text"], o["own_words"], o["around_words"], o["parent_text"]) for o in bad["offenders"]] == [("body > main > h2 > em.accent", "go", 1, 1, "Now go")], bad
    assert "has 1 word(s) around it in \"Now go\"" in bad["detail"] and "the rule asks for 2 to 6" in bad["detail"]
    set_page_rules(acme, {**ACCENT_ROOM, "min": 1})
    r, rep = check_page(acme, "--schemes", "light")
    ok = rule_row(rep, "accent-room")
    assert r.returncode == 0 and ok["status"] == "pass" and ok["accents_checked"] == 2 and "each with 1 to 6 word(s) around it" in ok["detail"], ok
    set_page_rules(acme, {**ACCENT_ROOM, "min": 4, "max": 4})
    r, rep = check_page(acme, "--schemes", "light")
    bad = rule_row(rep, "accent-room")
    assert r.returncode == 1 and sorted(o["around_words"] for o in bad["offenders"]) == [1, 3] and "exactly 4" in bad["detail"], bad
    set_page_rules(acme, {**ACCENT_ROOM, "selector": "em.nothing"})
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0 and "matches no shown element" in rule_row(rep, "accent-room")["detail"]


CONTROL_KINDS = """<p><button>Buy now</button> <button aria-label="Open the main menu"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M0 2h16v2H0z" fill="currentColor"/></svg></button>
  <input type="submit" value="Send it right now"> <a href="#parts" role="button" class="cta">&rarr; Next</a>
  <button style="display: none">Hidden one two three four five</button> <button style="opacity: 0">Faded one two three four five</button>
  <button>Sign-up and e-mail</button> <button><span>Two</span> <b>words</b></button> <button></button></p>
  <div class="cta">Learn more about us here</div>"""


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_controls_collector_counts_the_visible_text_or_the_accessible_name(acme):
    write_page(acme, controls_page(CONTROL_KINDS))
    set_page_rules(acme, {**SHORT_BUTTONS, "max": 99, "selector": "div.cta"})
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    facts = v["rule_facts"]["short-buttons"]
    assert facts["kind"] == "max-words-per-control" and facts["selector"] == "div.cta"
    by = {(i["text"], i["via"]): i["words"] for i in facts["items"]}
    assert by == {("Learn more about us here", "text"): 5,        # the rule's own selector
                  ("Open the main menu", "name"): 4,              # an icon button is its aria-label
                  ("Send it right now", "text"): 4,               # an input shows its value
                  ("Sign-up and e-mail", "text"): 5,              # a hyphenated compound is two words (Unicode word segmentation)
                  ("Buy now", "text"): 2, ("Two words", "text"): 2,
                  ("→ Next", "text"): 1,                     # an arrow is no word
                  ("", "none"): 0}, by
    assert [i["words"] for i in facts["items"]] == sorted((i["words"] for i in facts["items"]), reverse=True)   # the longest first
    assert facts["matched"] == 10 and facts["shown"] == 8   # the hidden and the transparent button have no words to count
    assert not any("Hidden" in i["text"] or "Faded" in i["text"] for i in facts["items"])
    assert v["selectors"]["div.cta"]["visible"] == 1   # the request's selectors are measured as boxes too
    set_page_rules(acme)   # no rules: the browser is asked for none
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "rule_facts" not in json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"][0]
    assert not [x for x in rep["results"] if x["id"].startswith("page:rule:")]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_selector_the_browser_refuses_fails_its_row(acme):
    write_page(acme, controls_page("<p><button>Buy now</button></p>"))
    set_page_rules(acme, {**SHORT_BUTTONS, "selector": "button["})
    r, rep = check_page(acme, "--schemes", "light")   # G4 is not recorded: it fails all the same, it cannot be judged
    assert r.returncode == 1, r.stdout + r.stderr
    bad = rule_row(rep, "short-buttons")
    assert bad["status"] == "fail" and "not valid CSS" in bad["detail"] and "button[" in bad["detail"] and "qa/rules.json page.rules" in bad["detail"], bad
    assert "error" in json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"][0]["selectors"]["button["]   # the box collector says so too


@pytest.mark.requires_node
def test_render_page_measure_refuses_a_rules_list_it_cannot_read(tmp_path):
    """render.mjs holds the optional `rules` of a request to its shape (exit 2, before a browser is started), as it does every other key."""
    p = make_project(tmp_path)
    write_page(p)
    data = tmp_path / "data"
    (data / "scratch").mkdir(parents=True)
    good = {"schema": 1, "root": str(p), "page": "pages/index.html", "url": None, "widths": [390], "schemes": ["light"], "selectors": [], "dsf": 1}
    for i, rules in enumerate(["x", {"id": "a"}, [1], [{"id": "a"}], [{"id": 3, "kind": "tell"}], [{"id": "a", "kind": "tell", "selector": ""}], [{"id": "a", "kind": "tell", "selector": 3}],
                               [{"id": f"r{n}", "kind": "tell"} for n in range(201)]]):
        req = tmp_path / f"rules{i}.json"
        req.write_text(json.dumps({**good, "rules": rules}), encoding="utf-8")
        r = subprocess.run(["node", str(ROOT / "scripts/render.mjs"), "page-measure", "--request", str(req), "--out", str(tmp_path / "out.json"), "--project", str(p)],
                           capture_output=True, text=True, env={**os.environ, "BRAND_CREATOR_DATA": str(data)})
        assert r.returncode == 2 and "rules must be a list of up to 200 objects" in r.stderr, (rules, r.returncode, r.stderr)
    assert not (tmp_path / "out.json").exists()


# ---------------------------------------------------------------- the generic tells (warnings)

TELL_IDS = ["eyebrow", "arrow-glued", "middot-run", "stock-second-action", "hero-text-budget", "styled-div-mock", "three-equal-tiles", "stray-box", "tilted-form"]
LONG_HERO = ("Every Acme tool is forged in one workshop, tested by the people who use it every day, and sold with a published list of its spare parts so that a worn "
             "handle or a bent blade is a small repair and never a reason to buy the whole tool again.")   # more than 45 words


def tells_page(lang: str = "en", second: str = "Learn more", hero_text: str = LONG_HERO) -> str:
    """One page that shows all nine tells, and the stock order of a product page: hero, three tiles, a box made of boxes, a sheet left outside its parent, a sign-up form on a tilted sheet, an FAQ, a closing band."""
    mock = "<i></i>" * 8
    style = """  nav, section, .mock { display: block; margin: 0; }
  .eyebrow { margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; }
  .tiles { display: flex; gap: 16px; }
  .tile { flex: 1 1 0; padding: 8px; }
  .mock { width: 300px; height: 200px; }
  .mock i { display: block; height: 12px; margin: 4px; border: 1px solid var(--color-text); }
  .sheets { height: 40px; }
  .sheet { position: relative; top: 120px; margin: 0; }
  .paper { transform: rotate(-3deg); }
  input, button, select { background: var(--color-bg); color: var(--color-text); border: 1px solid var(--color-text); font: inherit; }
"""
    return PAGE.replace('lang="en"', f'lang="{lang}"').replace("</style>", style + "</style>").replace(
        PAGE[PAGE.index("<main>"):PAGE.index("</main>") + len("</main>")], f"""<nav><a href="#a">Products</a> <a href="#b">Pricing</a></nav>
<main>
<section class="hero">
  <p class="eyebrow">Spare parts</p>
  <h1>Acme hand tools</h1>
  <p>{hero_text}</p>
  <p class="actions"><a class="go" href="#start">Start now →</a> <a class="second" href="#how">{second}</a></p>
  <p class="meta">Free shipping · Free returns · Lifetime spares</p>
</section>
<section class="tiles">
  <div class="tile"><h2>Hammers</h2><p>Forged.</p></div>
  <div class="tile"><h2>Saws</h2><p>Sharp.</p></div>
  <div class="tile"><h2>Planes</h2><p>True.</p></div>
</section>
<div class="mock">{mock}</div>
<div class="sheets"><p class="sheet">Sheet one</p></div>
<form class="paper" action="#"><label>Email <input name="email"></label> <button type="button">Sign up</button></form>
<section class="faq"><h2>FAQ</h2><details><summary>Can I repair a tool?</summary><p>Yes, with the spare-parts list.</p></details></section>
<section class="closing"><h2>Ready to order?</h2><p><a href="#order">Order a tool</a></p></section>
</main>""")


def tell_row(rep: dict, tid: str) -> dict:
    return row(rep, f"tell:{tid}")


def leaf(selector: str, levels: int = 2) -> str:
    """The last levels of a selector the check wrote, without its :nth-of-type counts: `section.hero > p.eyebrow`."""
    return " > ".join(re.sub(r":nth-of-type\(\d+\)", "", selector).split(" > ")[-levels:])


def tell_view(width: int = 1440, scheme: str = "light", lang: str = "en", **facts) -> dict:
    """A view as the browser would have measured it, with the candidates of the tells; what is not given is empty."""
    base = {"viewport": {"width": width, "height": 900}, "eyebrow": [], "arrows": [], "separators": [], "hero": {"found": False}, "boxes": [], "tiles": [], "headings": [], "details": [],
            "last_band": None, "strays": [], "tilts": []}
    return {"width": width, "scheme": scheme, "lang": lang, "viewport": {"width": width, "height": 900}, "tell_facts": {**base, **facts}}


def found_tells(*views: dict) -> dict:
    return pagecheck.find_tells({"views": list(views)}, pagecheck.load_tells())


def tell_rows_of(p: Path, views: list[dict], *rules: dict) -> dict[str, dict]:
    """tell_rows on constructed measurements; `rules` are page rules (a tell the owner adopted has no tell: row)."""
    loaded = qa_rules.load(p)[0]
    loaded["page"]["rules"] = qa_rules.validate_page_rules(list(rules))
    ctx = pagecheck.Ctx(p, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [1440], ["light"], loaded, {})
    rep = Report("page-check/x-000000", p)
    pagecheck.tell_rows(rep, {"views": views}, ctx)
    return {r["id"]: r for r in rep.results}


def test_the_tells_file_names_the_tells_the_page_check_knows():
    cfg = pagecheck.load_tells()
    assert pagecheck.tell_ids() == TELL_IDS and cfg["languages"] == ["en", "pl"] and [n["id"] for n in cfg["notes"]] == ["stock-anatomy"]


def test_the_tell_thresholds_are_applied_to_what_the_browser_collected():
    """No browser: each number of page-tells.json decides at its edge, on the candidates the collector reports."""
    eb = lambda **k: {"sel": "p.k", "text": "NEW", "words": 4, "uppercase": True, "letter_spacing_em": 0, "font_size_px": 12, "heading_sel": "h1", "heading_tag": "h1", "heading_font_size_px": 32, **k}
    hits = lambda tid, *views: found_tells(*views)["hits"][tid]
    assert len(hits("eyebrow", tell_view(eyebrow=[eb()]))) == 1                                              # 4 words, in capitals, smaller than the heading
    assert not hits("eyebrow", tell_view(eyebrow=[eb(words=5)]))                                             # 5 words is a sentence
    assert len(hits("eyebrow", tell_view(eyebrow=[eb(uppercase=False, letter_spacing_em=0.05)]))) == 1       # not in capitals, but tracked wide
    assert not hits("eyebrow", tell_view(eyebrow=[eb(uppercase=False, letter_spacing_em=0.049)]))
    assert not hits("eyebrow", tell_view(eyebrow=[eb(font_size_px=32)]))                                     # not smaller than the heading
    ar = lambda gap: {"sel": "a.go", "label": "Go →", "edge": "end", "glyph": "→", "gap_chars": gap}
    assert [len(hits("arrow-glued", tell_view(arrows=[ar(g)]))) for g in (0, 1, 2)] == [1, 1, 0]
    sep = lambda n, via="text": {"sel": "p.meta", "text": "a · b · c", "count": n, "via": via}
    assert [len(hits("middot-run", tell_view(separators=[sep(n)]))) for n in (1, 2, 3)] == [0, 1, 1]
    assert len(hits("middot-run", tell_view(separators=[sep(2), sep(2, "pseudo")]))) == 2                    # the same element, text and pseudo-elements: two ways to see it
    hero = lambda words, **k: {"found": True, "sel": "section.hero", "h1_sel": "h1", "top": 0, "words": words, "viewport_height": 900, "lang": "en", "actions": [], **k}
    assert [len(hits("hero-text-budget", tell_view(hero=hero(n)))) for n in (45, 46)] == [0, 1]
    act = lambda label, lang="en": {"sel": f"a.{label[:3]}", "label": label, "lang": lang}
    second = lambda label, lang="en", page_lang="en": hits("stock-second-action", tell_view(lang=page_lang, hero=hero(10, actions=[act("Start now"), act(label, lang)])))
    assert len(second("Learn more")) == 1 and len(second("LEARN MORE →")) == 1 and len(second("  Learn   more…")) == 1     # letter case, arrows, dots and white space do not hide it
    assert not second("Get a quote") and not second("Learn more about our tools")                            # only the stock label itself
    assert len(second("Dowiedz się więcej", "pl", "pl")) == 1 and len(second("Zobacz, jak to działa", "pl", "pl")) == 1 and not second("Learn more", "pl", "pl")
    assert not hits("stock-second-action", tell_view(hero=hero(10, actions=[act("Learn more")])))             # one action is not a second action
    assert not hits("stock-second-action", tell_view(hero=hero(10, actions=[act("Learn more"), act("Start now")])))   # it is the second one that counts
    box = lambda **k: {"id": 1, "parent": None, "sel": "div.mock", "width": 240, "height": 160, "styled": 8, "in_lists": 0, "in_cells": 0, "table": False, "list_area": 0, "media_px": {}, "headings": 0, "h1": 0, "labelled": False, **k}
    assert len(hits("styled-div-mock", tell_view(boxes=[box()]))) == 1
    for off in ({"width": 239}, {"height": 159}, {"styled": 7}, {"media_px": {"img": 600}}, {"labelled": True}):
        assert not hits("styled-div-mock", tell_view(boxes=[box(**off)])), off
    inner = box(id=2, parent=1, sel="div.mock > div.screen", styled=9)
    assert [h["selector"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=20), inner]))] == ["div.mock > div.screen"]   # the innermost box, not the page round it
    assert [h["selector"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=20, media_px={"img": 600}), inner]))] == ["div.mock > div.screen"]
    assert [h["selector"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=20), box(id=2, parent=1, sel="div.screen", styled=3)]))] == ["div.mock"]   # a part with too few is not it
    assert next(t for t in pagecheck.load_tells()["tells"] if t["id"] == "styled-div-mock")["threshold"]["max_icon_px"] == 48
    mock_with = lambda **media: len(hits("styled-div-mock", tell_view(boxes=[box(media_px=media)])))
    assert [mock_with(svg=24), mock_with(img=24), mock_with(svg=48, img=48), mock_with(svg=24, img=16)] == [1, 1, 1, 1]       # an img or svg of 48 x 48 px or less is an icon: it does not exempt the box
    assert [mock_with(svg=48.5), mock_with(img=49), mock_with(img=600), mock_with(svg=24, img=600)] == [0, 0, 0, 0]          # a larger one is a picture (the larger side counts)
    assert [mock_with(canvas=20), mock_with(video=20), mock_with(canvas=20, svg=24)] == [0, 0, 0]                              # a canvas or video exempts at any size
    assert [mock_with(picture=20), mock_with(picture=48, svg=24), mock_with(picture=20, img=24)] == [1, 1, 1]                  # a picture is as big as its img: a small one is an icon too
    assert [mock_with(picture=49), mock_with(picture=600), mock_with(picture=600, svg=24)] == [0, 0, 0]
    section = lambda **k: len(hits("styled-div-mock", tell_view(boxes=[box(**k)])))
    assert [section(h1=1, headings=1), section(h1=1, headings=7), section(headings=2), section(headings=9)] == [0, 0, 0, 0]   # a box with the h1, or with more than one heading, is a section of the page
    assert [section(headings=1), section(headings=0)] == [1, 1]                                                                 # one heading is a drawing's title
    assert [h["selector"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=20, h1=1, headings=3), inner]))] == ["div.mock > div.screen"]   # the page is not judged, the drawing in it is
    assert [h["selector"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=20, h1=1, headings=3), box(id=3, parent=1, sel="div.mock > div.band", styled=20, headings=2), inner]))] == ["div.mock > div.screen"]
    with pytest.raises(KeyError):   # a collector that left a field out is an error, not a box with no media and no lists
        found_tells(tell_view(boxes=[{k: v for k, v in box().items() if k != "media_px"}]))
    for left_out in ("in_cells", "table"):   # ... or a box with no cells and no table
        with pytest.raises(KeyError):
            found_tells(tell_view(boxes=[{k: v for k, v in box().items() if k != left_out}]))
    tabled = lambda **k: len(hits("styled-div-mock", tell_view(boxes=[box(**k)])))
    assert [tabled(styled=18, in_cells=18), tabled(styled=8, in_cells=8), tabled(styled=40, in_cells=40)] == [0, 0, 0]       # every styled part sits in a cell: a table of badges is data
    assert [tabled(styled=18, in_cells=17), tabled(styled=9, in_cells=8), tabled(styled=8, in_cells=0)] == [1, 1, 1]         # one part outside the cells, and the box is judged on all of them, the badges too
    assert [tabled(styled=18, table=True), tabled(styled=18, table=True, in_cells=3)] == [0, 0]                              # a table or a table section is data whatever is in it
    assert tabled(styled=12, in_cells=8, in_lists=4) == 1                                                                    # cells and list items are not added up: the box is neither a table nor a list
    assert [h["selector"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=20, in_cells=20), box(id=2, parent=1, sel="div.mock > div.screen", styled=9)]))] == ["div.mock > div.screen"]   # a drawing inside a cell is its own box
    listed = lambda **k: len(hits("styled-div-mock", tell_view(boxes=[box(**k)])))
    th = next(t for t in pagecheck.load_tells()["tells"] if t["id"] == "styled-div-mock")["threshold"]
    assert (th["max_unlisted_styled"], th["min_list_area_ratio"]) == (1, 0.8)
    assert [listed(styled=10, in_lists=10), listed(styled=40, in_lists=40, list_area=38400), listed(styled=8, in_lists=8)] == [0, 0, 0]       # the box is the list: every styled part is an item
    assert [listed(styled=11, in_lists=10), listed(styled=12, in_lists=10), listed(styled=20, in_lists=12)] == [0, 1, 1]                      # one styled part beside the list is excused, two are not
    assert [listed(styled=12, in_lists=10, list_area=n) for n in (30720, 30719, 38400)] == [0, 1, 0]                                           # or the items take 0.8 of the box (240 x 160 px)
    assert [listed(styled=12, in_lists=10, list_area=n, width=480, height=320) for n in (122880, 122879)] == [0, 1]                           # of the box, whatever its size
    assert [listed(styled=12, in_lists=10, list_area=30720, width=480, height=320)] == [1]                                                     # items that are a fifth of the box are no excuse
    assert listed(styled=12, in_lists=0, list_area=38400) == 1                                                                                 # no styled item, no items to excuse it
    assert listed(styled=8, in_lists=2) == 1                                                                                                   # every styled item counts, not one for the list: six others and two items make eight
    assert [h["text"] for h in hits("styled-div-mock", tell_view(boxes=[box(styled=16, in_lists=12)]))] == ["a box of 240 x 160 px made of 16 styled boxes, with no image over 48 px"]

    def tiles(widths=(300, 300, 300), heights=(100, 100, 100), tops=(0, 0, 0), lefts=(0, 316, 632)) -> list[dict]:
        return [{"sel": "section.tiles", "tiles": [{"sel": f"div:nth-of-type({i + 1})", "left": lefts[i], "top": tops[i], "width": widths[i], "height": heights[i]} for i in range(3)]}]
    tile_hits = lambda width=1440, **k: hits("three-equal-tiles", tell_view(width=width, tiles=tiles(**k)))
    assert len(tile_hits()) == 1 and len(tile_hits(widths=(300, 301, 302))) == 1 and not tile_hits(widths=(300, 301, 303))      # widths within 2 px
    assert len(tile_hits(heights=(100, 80, 90))) == 1 and not tile_hits(heights=(100, 79, 90))                                  # the shorter at least 0.8 of the taller
    assert len(tile_hits(width=1024)) == 1 and not tile_hits(width=1023)                                                          # a phone shows them stacked
    assert not tile_hits(tops=(0, 120, 240), lefts=(0, 0, 0)) and not tile_hits(lefts=(0, 250, 500))                             # stacked, or overlapping, is not a row
    assert len(found_tells(tell_view(width=390, eyebrow=[eb()]), tell_view(width=1440, eyebrow=[eb()]))["hits"]["eyebrow"]) == 1   # the same place in two views is one hit ...
    assert found_tells(tell_view(width=390, eyebrow=[eb()]), tell_view(width=1440, eyebrow=[eb()]))["hits"]["eyebrow"][0]["widths"] == [390, 1440]   # ... seen at both


def stray(sel: str = "div.sheet", text: str = "Sheet one", animating: bool = False, parent: tuple | None = ("below", 8), viewport: tuple | None = None) -> dict:
    """A stray-box candidate as the collector reports it: where it lies against its parent (side, px) and against the screen (edge, px)."""
    return {"sel": sel, "text": text, "animating": animating, "parent": {"sel": "div.stack", "side": parent[0], "px": parent[1]} if parent else None,
            "viewport": {"side": viewport[0], "px": viewport[1]} if viewport else None}


def test_the_stray_box_threshold_decides_at_its_edge_and_what_it_cannot_see_is_not_verified(tmp_path):
    """No browser: `min_outside_px` (8) applies to the distance from the parent and from the screen; an element still animating, a view with an animation still running and a view whose
    wait was cut off are NOT verified, never a hit; the tall window's own walk adds what only it shows."""
    assert next(t for t in pagecheck.load_tells()["tells"] if t["id"] == "stray-box")["threshold"] == {"min_outside_px": 8}
    hits = lambda *views: found_tells(*views)["hits"]["stray-box"]
    notes = lambda *views: found_tells(*views)["unverified"]["stray-box"]
    assert [len(hits(tell_view(strays=[stray(parent=("below", px))]))) for px in (2, 7, 7.99, 8, 80)] == [0, 0, 0, 1, 1]       # a candidate from 2 px: the tell asks for 8
    assert [len(hits(tell_view(strays=[stray(parent=None, viewport=("left", px))]))) for px in (7, 8)] == [0, 1]               # the screen has the same number
    assert [len(hits(tell_view(strays=[stray(parent=(side, 8))]))) for side in ("below", "above", "right", "left")] == [1, 1, 1, 1]
    (h,) = hits(tell_view(strays=[stray(parent=("below", 80))]))
    assert h["selector"] == "div.sheet" and h["text"] == '"Sheet one" is still shown 80 px below its parent div.stack after the page settled', h
    assert hits(tell_view(strays=[stray(parent=("right", 12))]))[0]["text"] == '"Sheet one" is still shown 12 px to the right of its parent div.stack after the page settled'
    assert hits(tell_view(strays=[stray(parent=None, viewport=("top", 30), text="")]))[0]["text"] == "is still shown 30 px past the top edge of the screen after the page settled"
    both = hits(tell_view(strays=[stray(parent=("below", 80), viewport=("left", 20))]))
    assert len(both) == 1 and both[0]["text"].endswith("80 px below its parent div.stack and 20 px past the left edge of the screen after the page settled"), both
    one_of_two = hits(tell_view(strays=[stray(parent=("below", 80), viewport=("left", 7))]))[0]["text"]
    assert "7 px" not in one_of_two and "80 px below" in one_of_two, one_of_two                                                 # the number that is under the threshold is not said
    assert [h["widths"] for h in hits(tell_view(width=390, strays=[stray()]), tell_view(width=1440, strays=[stray()]))] == [[390, 1440]]   # the same place in two views is one hit
    assert not notes(tell_view(strays=[stray()]))                                                                                # a view with no animation fact, as a page that does not move gives
    # an element that is still animating is no hit and no pass: its place is not known
    moving = tell_view(strays=[stray(sel="div.sway", animating=True)])
    moving["animations"] = {"waited": 0, "running": 1, "capped": False}
    assert not hits(moving) and len(notes(moving)) == 1 and notes(moving)[0].startswith("NOT verified at 1440 px: 1 animation(s) never end or wait for a scroll") and "still animating: div.sway" in notes(moving)[0], notes(moving)
    calm = tell_view(strays=[])                                                                                                   # an animation that never ends elsewhere on the page: the row is not a pass either
    calm["animations"] = {"waited": 2, "running": 3, "capped": False}
    assert not hits(calm) and notes(calm)[0].startswith("NOT verified at 1440 px: 3 animation(s) never end or wait for a scroll") and "still animating" not in notes(calm)[0]
    both_views = [{**calm, "width": 390}, {**moving, "width": 1440}]
    assert len(notes(*both_views)) == 1 and notes(*both_views)[0].startswith("NOT verified at 390, 1440 px:")
    elsewhere = tell_view(strays=[stray(sel="div.fixed-sheet"), stray(sel="div.sway", animating=True)])                           # a stray that is not animating is still a hit beside one that is
    elsewhere["animations"] = {"waited": 0, "running": 1, "capped": False}
    assert [h["selector"] for h in hits(elsewhere)] == ["div.fixed-sheet"] and notes(elsewhere)
    cut_off = tell_view(strays=[stray()])                                                                                         # the wait for the animations that end was cut off: the view is not judged
    cut_off["animations"] = {"waited": 4, "running": 1, "capped": True}
    assert not hits(cut_off) and len(notes(cut_off)) == 1 and notes(cut_off)[0].startswith("NOT verified at 1440 px: the page's animations were still running when the check stopped waiting"), notes(cut_off)
    p = make_project(tmp_path)                                                                                                    # the row: a warning that says NOT verified, with the hits it has, never a pass
    unseen = tell_rows_of(p, [moving])["tell:stray-box"]
    assert unseen["status"] == "warn" and unseen["hits"] == [] and unseen["detail"].startswith("NOT verified at 1440 px") and unseen["tell"] == "stray-box", unseen
    mixed = tell_rows_of(p, [elsewhere])["tell:stray-box"]
    assert mixed["status"] == "warn" and [h["selector"] for h in mixed["hits"]] == ["div.fixed-sheet"] and "1 found: div.fixed-sheet" in mixed["detail"] and "NOT verified at 1440 px" in mixed["detail"], mixed
    assert tell_rows_of(p, [tell_view(strays=[stray(parent=("below", 7))])])["tell:stray-box"]["status"] == "pass"                  # under the threshold: none found
    # the window 1300 px high: its own walk, the same thresholds
    tall = lambda *items, **facts: {"viewport": {"width": 1440, "height": 1300}, "animations": {"waited": 0, "running": 0, "capped": False}, "strays": list(items), **facts}
    only_tall = tell_view(strays=[], strays_tall=tall(stray(sel="div.late", parent=("below", 400))))
    (t,) = hits(only_tall)
    assert t["selector"] == "div.late" and t["widths"] == [1440] and t["text"].endswith("400 px below its parent div.stack after the page settled, in a window 1300 px high"), t
    assert not hits(tell_view(strays=[], strays_tall=tall(stray(parent=("below", 7)))))
    assert [h["text"].endswith("in a window 1300 px high") for h in hits(tell_view(strays=[stray()], strays_tall=tall(stray(), stray(sel="div.late"))))] == [False, True]   # seen at the view's own height too: said once
    assert len(hits(tell_view(strays=[stray()], strays_tall=tall(stray(), stray(sel="div.late"))))) == 2
    cut_tall = tell_view(strays=[], strays_tall=tall(stray(), animations={"waited": 1, "running": 1, "capped": True}))
    assert not hits(cut_tall) and notes(cut_tall)[0].startswith("NOT verified at 1440 px in a tall window: the page's animations were still running"), notes(cut_tall)
    late = tell_view(strays=[stray(animating=True)], strays_tall=tall(stray()))                                                    # the view's wait was cut off; the tall walk waited again and saw the box at rest
    late["animations"] = {"waited": 1, "running": 1, "capped": True}
    (found_late,) = hits(late)
    assert found_late["text"].endswith("after the page settled, in a window 1300 px high") and notes(late)[0].startswith("NOT verified at 1440 px: the page's animations were still running"), (found_late, notes(late))
    running_tall = tell_view(strays=[], strays_tall=tall(stray(animating=True), animations={"waited": 0, "running": 2, "capped": False}))
    assert not hits(running_tall) and notes(running_tall)[0].startswith("NOT verified at 1440 px in a tall window: 2 animation(s) never end")
    unmeasured = tell_view(strays=[], strays_tall={"viewport": {"width": 1440, "height": 1300}, "error": "page.setViewportSize: closed"})
    assert not hits(unmeasured) and notes(unmeasured) == ["NOT verified at 1440 px in a window 1300 px high: page.setViewportSize: closed"]
    assert not notes(tell_view(strays=[], strays_tall=tall()))                                                                    # a tall walk that found nothing and had no animation says nothing
    assert notes(tell_view(strays=[], strays_tall=tall(truncated=True))) == [pagecheck.ELEMENT_CAP_NOTE]
    for left_out in ("sel", "animating", "parent", "viewport", "text"):                                                           # a collector that left a field out is an error, not a box that is in place
        with pytest.raises(KeyError):
            found_tells(tell_view(strays=[{k: v for k, v in stray().items() if k != left_out}]))
    for left_out in ("sel", "side", "px"):
        with pytest.raises(KeyError):
            found_tells(tell_view(strays=[{**stray(), "parent": {k: v for k, v in stray()["parent"].items() if k != left_out}}]))


ICON = '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8"/></svg>'
PIXEL = '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="" width="600" height="120">'   # a picture that is 600 css px wide, as the page draws it
SMALL_PIXEL = PIXEL.replace('width="600" height="120"', 'width="20" height="20"')                # the same file drawn at 20 x 20 css px: an icon
MOCK_STYLE = """  .shot { width: 640px; height: 300px; margin: 0; border: 1px solid var(--color-text); }
  .shot .head { background: var(--color-accent); height: 24px; }
  .shot .row { border-bottom: 1px solid var(--color-text); height: 20px; }
  .shot .amt { background: var(--color-accent); }
  .shot svg { vertical-align: middle; fill: var(--color-text); }
  .shot ul { list-style: none; margin: 0; padding: 0; }
  .shot li { background: var(--color-bg); border: 1px solid var(--color-text); height: 20px; }
  .btn { display: inline-block; padding: 8px 16px; background: var(--color-accent); color: var(--color-bg); }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .card { border: 1px solid var(--color-text); padding: 12px; }
  .band { display: block; background: var(--color-accent); padding: 24px; }
  .shot .big { font-size: 28px; }
  .shot .foot { border-top: 1px solid var(--color-text); height: 20px; }
  .shot table { width: 100%; border-collapse: collapse; }
  .shot tr { background: var(--color-bg); }
  .shot th, .shot td { background: var(--color-bg); border: 1px solid var(--color-text); height: 20px; }
  .shot code { background: var(--color-bg); border: 1px solid var(--color-text); padding: 4px; }
"""


def page_with_main(main: str) -> str:
    """The test page with `main` as its main content and the styles of the styled-div-mock fixtures."""
    return PAGE.replace("</style>", MOCK_STYLE + "</style>").replace(PAGE[PAGE.index("<main>"):PAGE.index("</main>") + len("</main>")], f"<main>\n{main}\n</main>")


def mock_page(inside: str, panel: str = "figure") -> str:
    """A page whose one drawn thing is `inside`, in a box of 640 x 300 css px: the styled-div-mock tell looks at it."""
    return page_with_main(f'<h1>Acme hand tools</h1>\n<{panel} class="shot">{inside}</{panel}>')


def mock_tell(p: Path, page: str) -> dict:
    """The `tell:styled-div-mock` row of `page` at 1440 px, light."""
    write_page(p, page)
    r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=p)
    assert r.returncode in (0, 1), r.stdout + r.stderr   # the amounts of a drawn panel are not in FACTS.md: other rows may fail, the tell row is what is read
    return tell_row(report(p, pagecheck.report_tool("pages/index.html")), "styled-div-mock")


APP_ROWS = "".join(f'<div class="row">{ICON} Rent {n} <span class="amt">-{n}0.00</span></div>' for n in range(1, 7))
APP_PANEL = f'<div class="head">{ICON} Account</div>{APP_ROWS}'                              # a header, six rows of amounts, seven small svg icons: 13 styled boxes
CHECKLIST = "<ul>" + "".join(f"<li>Step {n} of the repair</li>" for n in range(1, 11)) + "</ul>"   # ten items, each with a background and a border
TIMELINE = "<ol>" + "".join(f'<li><span class="amt">{n}</span><div class="row">Stage {n}</div></li>' for n in range(1, 6)) + "</ol>"   # each item holds two more styled boxes


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_drawn_app_panel_with_small_icons_is_a_mock_up_and_a_styled_list_or_a_real_picture_is_not(acme):
    """The browser end to end: small svg icons do not exempt a drawn app screen, a styled list or timeline that is the whole box does not warn, and a picture larger than an icon still exempts."""
    mock_row = lambda inside, panel="figure": mock_tell(acme, mock_page(inside, panel))
    drawn = mock_row(APP_PANEL)
    assert drawn["status"] == "warn" and [leaf(h["selector"]) for h in drawn["hits"]] == ["main > figure.shot"] and "13 styled boxes" in drawn["hits"][0]["text"], drawn   # seven icons of 20 px
    assert mock_row(APP_PANEL + PIXEL)["status"] == "pass"                                      # the same panel with a real 600 px picture in it
    assert mock_row(APP_PANEL.replace(ICON, ICON.replace('"20"', '"48"')))["status"] == "warn"   # an icon of 48 x 48 px is still an icon
    assert mock_row(APP_PANEL.replace(ICON, ICON.replace('"20"', '"49"')))["status"] == "pass"   # one of 49 px is a picture
    assert mock_row(APP_PANEL + '<canvas width="20" height="20"></canvas>')["status"] == "pass"   # a canvas exempts at any size
    assert mock_row(APP_PANEL + f"<picture>{SMALL_PIXEL}</picture>")["status"] == "warn"         # a picture is as big as its img: 20 px is an icon, bare or in a picture
    assert mock_row(APP_PANEL + f'<picture><source srcset="x.webp" type="image/webp">{PIXEL}</picture>')["status"] == "pass"   # one of 600 px is a picture
    assert mock_row(CHECKLIST)["status"] == "pass"                                              # ten items with a background and a border (a ul in the box) ...
    assert mock_row(f"<div>{CHECKLIST}</div>")["status"] == "pass"                              # ... or in a box round it
    assert mock_row(TIMELINE)["status"] == "pass"                                               # five items, three styled boxes each, and nothing else in the box: every styled part is an item or in one
    two = mock_row(CHECKLIST + CHECKLIST.replace("ul", "ol"))
    assert two["status"] == "pass"                                                              # every styled part sits in the items of one list or the other
    assert mock_row(APP_ROWS + CHECKLIST)["status"] == "warn"                                   # six rows of amounts, their icons and chips are 12 boxes, beside the list


PAYMENTS = "<ul>" + "".join(f'<li>{ICON} Rent {n} <span class="amt">-{n}0.00</span></li>' for n in range(1, 7)) + "</ul>"   # six payment rows, each with a chip: 12 styled boxes
PAY_PANEL = f'<div class="head">{ICON} Account</div><div class="amt big">1,240.00</div>{PAYMENTS}<div class="foot"><span class="btn">Pay now</span></div>'   # a head, a big amount, the list, a footer with a button: 16
TIMELINE_7 = "<ol>" + "".join(f'<li><span class="amt">{n}</span><div class="row">Stage {n}</div></li>' for n in range(1, 8)) + "</ol>"   # seven items of three styled boxes each
TABLE = ("<table><thead><tr>" + "".join(f"<th>Column {n}</th>" for n in range(1, 4)) + "</tr></thead><tbody>"
         + "".join("<tr>" + "".join(f"<td>Row {r}, cell {c}</td>" for c in range(1, 4)) + "</tr>" for r in range(1, 6)) + "</tbody></table>")   # 3 + 15 = 18 cells with a background and a border
ERROR_CARD = '<div class="card"><code>404</code><h2>Page not found</h2><p>The page moved.</p><a class="btn" href="#a">Home</a> <a class="btn" href="#b">Back</a></div>'


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_list_excuses_only_a_box_that_is_the_list_or_nearly_all_of_it_and_a_table_is_data(acme):
    """The browser end to end (calibrated on a real brand site): an app panel whose styled boxes are mostly the items of one list still warns; a list, a table, a timeline and a card do not."""
    mock_row = lambda inside, panel="figure": mock_tell(acme, mock_page(inside, panel))
    shot_facts = lambda: next(b for b in json.loads(Path(report(acme, pagecheck.report_tool("pages/index.html"))["measures"]).read_text(encoding="utf-8"))["views"][0]["tell_facts"]["boxes"] if leaf(b["sel"], 1) == "figure.shot")
    drawn = mock_row(PAY_PANEL)
    assert drawn["status"] == "warn" and [leaf(h["selector"]) for h in drawn["hits"]] == ["main > figure.shot"] and "16 styled boxes" in drawn["hits"][0]["text"], drawn   # the six rows count one each
    shot = shot_facts()
    assert (shot["styled"], shot["in_lists"]) == (16, 12) and 0 < shot["list_area"] < 0.8 * shot["width"] * shot["height"], shot             # 16 - 12 + 1 = 5 when a list was one box: below the 8
    assert mock_row(PAY_PANEL + PIXEL)["status"] == "pass" and mock_row(PAY_PANEL + '<canvas width="20" height="20"></canvas>')["status"] == "pass"   # a picture or a canvas still exempts it
    assert mock_row(PAY_PANEL.replace(ICON, ICON.replace('"20"', '"49"')))["status"] == "pass"       # and an svg over 48 px is a picture
    table = mock_row(TABLE)
    assert table["status"] == "pass" and not table["hits"], table                                       # eighteen cells with a background and a border, and their rows: data, not boxes
    assert mock_row(f"<div>{TABLE}</div>")["status"] == "pass" and mock_row(TABLE + CHECKLIST)["status"] == "pass"   # in a box round it; and beside a list: the ten items and nothing else
    for name, inside in (("checklist", CHECKLIST), ("timeline", TIMELINE_7), ("error card", ERROR_CARD), ("a head over a checklist", f'<div class="head">Steps</div>{CHECKLIST}')):
        assert mock_row(inside)["status"] == "pass", name                                               # the list is the box, or all but one of its styled parts
    assert mock_row(f'<div class="head">Steps</div>{CHECKLIST}<div class="foot"></div>')["status"] == "warn"   # a head and a footer beside the list: two parts, and the list is not nearly all of the box
    steps = lambda ul_style="", li_height=20: CHECKLIST.replace("<ul>", f'<ul style="{ul_style}">').replace("<li>", f'<li style="height: {li_height}px">')   # ten items, 22 px tall unless said
    fixed = lambda ul, style="height: 600px": page_with_main(
        f'<h1>Acme hand tools</h1>\n<figure class="shot" style="{style}"><div class="head">Steps</div>{ul}<div class="foot"><span class="btn">Done</span></div></figure>')   # a head, a footer and a button beside the list
    column = "height: 600px; display: flex; flex-direction: column"
    assert mock_tell(acme, fixed(steps(li_height=52)))["status"] == "pass"                              # ten items of 54 px in a box of 602 px: the items are nearly all of the box (0.89 of its area)
    assert mock_tell(acme, fixed(steps("height: 520px")))["status"] == "warn"                           # the same ten small items in a list stretched to 520 px: the items fill 0.36 of the box, the list's room does not count
    stretched = mock_tell(acme, fixed(steps("flex: 1"), column))                                        # and a list stretched by a flex column to pin the footer
    assert stretched["status"] == "warn" and shot_facts()["list_area"] == 10 * 640 * 22, stretched      # only the ten items' own boxes are counted
    assert mock_tell(acme, fixed(steps("min-height: 0"), "height: 600px; display: grid; grid-template-rows: auto 1fr auto"))["status"] == "warn"   # a list in a 1fr grid row: the same
    pay = PAY_PANEL.replace("<ul>", '<ul style="flex: 1">')
    pinned = mock_tell(acme, page_with_main('<h1>Acme hand tools</h1>\n<figure class="shot" style="height: 700px; display: flex; flex-direction: column">' + pay + "</figure>"))
    assert pinned["status"] == "warn" and "16 styled boxes" in pinned["hits"][0]["text"], pinned        # the payment panel in a fixed-height column with a stretched list ...
    pinned_facts = shot_facts()
    assert pinned_facts["in_lists"] == 12 and pinned_facts["list_area"] < 0.25 * pinned_facts["width"] * pinned_facts["height"], pinned_facts   # ... its six items fill a fraction of the box


BADGE = '<span class="amt" style="border-radius: 9px; padding: 0 8px">In stock</span>'                                 # a status badge: a background and a radius
BADGE_TABLE = ("<table><thead><tr><th>Part</th><th>Status</th></tr></thead><tbody>"
               + "".join(f"<tr><td>Part {n}</td><td>{BADGE}</td></tr>" for n in range(1, 13)) + "</tbody></table>")   # an index table: twelve rows, each ending in a styled badge
CAROUSEL = ('<div class="head">Featured</div><ul style="display: flex; overflow: hidden; gap: 8px">'
            + "".join(f'<li style="flex: none; width: 200px; height: 140px">Part {n}</li>' for n in range(1, 11)) + '</ul><div class="foot"></div>')   # ten styled items of 202 x 142 px in a row that runs far past the box, between a head and a footer
PLAIN_LIST = "<ul>" + "".join(f'<li style="background: none; border: 0; height: 50px">Part {n}</li>' for n in range(1, 13)) + "</ul>"   # twelve items with no background and no border
STEPS_3 = "<ul>" + "".join(f"<li>Step {n}</li>" for n in range(1, 4)) + "</ul>"                                                   # three styled items
PLAIN_ROWS = "".join(f'<div class="row">Row {n}</div>' for n in range(1, 7))                                                    # six styled rows


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_styled_badges_in_the_cells_of_a_table_are_data_and_a_drawing_in_a_cell_or_beside_the_table_is_not(acme):
    """The browser end to end (calibrated on a real brand site): an index table whose rows end in a styled status badge does not warn; a drawn panel in one of its cells, or a styled head beside it, still does."""
    mock_row = lambda inside, panel="figure": mock_tell(acme, mock_page(inside, panel))
    shot_facts = lambda: {leaf(b["sel"], 1): b for b in json.loads(Path(report(acme, pagecheck.report_tool("pages/index.html"))["measures"]).read_text(encoding="utf-8"))["views"][0]["tell_facts"]["boxes"]}
    table = mock_row(BADGE_TABLE)
    assert table["status"] == "pass" and not table["hits"], table                                      # twelve badges in the tbody: the table is data, as its cells and rows are
    boxes = shot_facts()
    assert (boxes["figure.shot"]["styled"], boxes["figure.shot"]["in_cells"], boxes["figure.shot"]["table"]) == (12, 12, False), boxes["figure.shot"]   # every badge is in a cell
    assert (boxes["table"]["styled"], boxes["table"]["in_cells"], boxes["table"]["table"]) == (12, 12, True), boxes["table"]
    assert boxes["tbody"]["table"] is True and boxes["tbody"]["in_cells"] == 12                        # a table section too
    assert mock_row(f"<div>{BADGE_TABLE}</div>")["status"] == "pass"                                   # in a box round it
    assert mock_row(BADGE_TABLE.replace(BADGE, f"{ICON}{BADGE}"))["status"] == "pass"                  # an icon beside the badge (media, not a styled box)
    assert mock_row(f'<div class="head">Parts</div>{BADGE_TABLE}')["status"] == "warn"                 # one styled part outside the cells: the box is judged on all 13, the badges too
    beside = mock_row(f'{BADGE_TABLE}<div class="foot"></div><div class="foot"></div>')
    assert beside["status"] == "warn" and "14 styled boxes" in beside["hits"][0]["text"], beside
    drawn = mock_row(f'<table><tr><td><div style="min-height: 200px">{APP_PANEL}</div></td></tr></table>')
    assert drawn["status"] == "warn" and "13 styled boxes" in drawn["hits"][0]["text"], drawn          # a drawn app panel in a cell: its own box, in no cell of its own
    assert [leaf(h["selector"], 1) for h in drawn["hits"]] == ["div"], drawn
    assert mock_row(APP_PANEL)["status"] == "warn"                                                      # and the panel with no table round it, as before
    for name, inside in (("checklist", CHECKLIST), ("timeline", TIMELINE_7), ("error card", ERROR_CARD)):
        assert mock_row(inside)["status"] == "pass", name                                              # the cases that were data or one thing stay so


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_band_is_not_judged_as_a_whole_and_a_drawing_inside_it_still_is(acme):
    """O9, calibrated on a real brand site: a band of the page, a `<section>` (or role=region) with a heading as a direct child or named by aria-labelledby, is not a mock-up however many
    styled boxes it holds: the boxes inside it are judged on their own. A drawn app panel in a band still warns, and a section with no heading is judged as before."""
    mock_row = lambda inside, panel="section": mock_tell(acme, mock_page(inside, panel))
    legend = f"<div>{BADGE}{BADGE}{BADGE}</div>"
    cards = "<ul>" + "".join(f'<li><div class="card"><div class="head">Tool {n}</div><div class="foot"></div></div></li>' for n in range(1, 5)) + "</ul>"
    assert mock_row(f"{BADGE_TABLE}{legend}")["status"] == "warn"                                       # no heading: the box is judged as before, the table and the legend beside it
    for name, inside in (("an index table and a legend", f"<h2>Parts</h2>{BADGE_TABLE}{legend}"), ("a list of cards", f"<h2>Tools</h2>{cards}")):
        band = mock_row(inside)
        assert band["status"] == "pass" and not band["hits"], (name, band)                              # the two warnings of the pilot calibration
    named = mock_tell(acme, page_with_main(f'<h1>Acme hand tools</h1>\n<div role="region" aria-labelledby="parts" class="shot"><div><h3 id="parts">Parts</h3></div>{BADGE_TABLE}{legend}</div>'))
    assert named["status"] == "pass", named                                                             # a region named by a heading of its own that is not a direct child is a band too
    unnamed = mock_tell(acme, page_with_main(f'<h1>Acme hand tools</h1>\n<div role="region" aria-labelledby="parts" class="shot"><p id="parts">Parts</p>{BADGE_TABLE}{legend}</div>'))
    assert unnamed["status"] == "warn", unnamed                                                         # aria-labelledby that names no heading makes no band
    wrapped = mock_tell(acme, page_with_main(f'<h1>Acme hand tools</h1>\n<div class="wrap"><section class="shot"><h2>Parts</h2>{BADGE_TABLE}{legend}</section></div>'))
    assert wrapped["status"] == "pass" and not wrapped["hits"], wrapped                                 # a box round a band is not judged on what the band holds (a full-width background)
    beside = mock_tell(acme, page_with_main(f'<h1>Acme hand tools</h1>\n<div class="wrap"><section class="shot"><h2>Parts</h2>{BADGE_TABLE}</section><figure class="shot">{APP_PANEL}</figure></div>'))
    assert [leaf(h["selector"], 1) for h in beside["hits"]] == ["figure.shot"], beside                  # a drawing beside the band still warns, as its own box
    drawn = mock_row(f'<h2>Your account</h2><div style="min-height: 200px">{APP_PANEL}</div>')
    assert drawn["status"] == "warn" and [leaf(h["selector"], 1) for h in drawn["hits"]] == ["div"], drawn   # the drawing in the band is its own box
    deep = mock_row(f"<div><h2>Parts</h2></div>{BADGE_TABLE}{legend}")
    assert deep["status"] == "warn", deep                                                               # a heading inside a child is not the band's own


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_row_of_items_running_past_its_box_fills_no_more_of_it_than_the_box(acme):
    """The browser end to end: the ten items of a carousel between a head and a footer, most of them outside the box, do not make the list nearly all of the box."""
    mock_row = lambda inside: mock_tell(acme, mock_page(inside))
    shot_facts = lambda: next(b for b in json.loads(Path(report(acme, pagecheck.report_tool("pages/index.html"))["measures"]).read_text(encoding="utf-8"))["views"][0]["tell_facts"]["boxes"] if leaf(b["sel"], 1) == "figure.shot")
    carousel = mock_row(CAROUSEL)
    assert carousel["status"] == "warn" and [leaf(h["selector"]) for h in carousel["hits"]] == ["main > figure.shot"] and "12 styled boxes" in carousel["hits"][0]["text"], carousel
    shot = shot_facts()
    assert (shot["styled"], shot["in_lists"]) == (12, 10), shot                                        # the head, the footer and ten items
    assert 10 * 202 * 142 > 0.8 * shot["width"] * shot["height"]                                       # the items by themselves are larger than the box, which is what excused it
    assert shot["list_area"] == (3 * 202 + 11) * 142 and shot["list_area"] < 0.8 * shot["width"] * shot["height"], shot   # three whole items and 11 px of a fourth: what lies in the box
    assert shot["list_area"] <= shot["width"] * shot["height"]                                         # the union of the items, each clipped to the box, is never more than the whole
    assert mock_row(CAROUSEL.replace('<div class="head">Featured</div>', "").replace('<div class="foot"></div>', ""))["status"] == "pass"   # the row of items alone is the whole list: no part beside it
    fits = mock_row(CAROUSEL.replace("overflow: hidden; gap: 8px", "overflow: hidden").replace("width: 200px", "width: 62px"))
    assert fits["status"] == "warn" and shot_facts()["list_area"] == 10 * 64 * 142, fits               # ten items that all lie in the box are counted whole
    # ten items stacked in one place (a carousel whose slides lie on top of each other), between a head and a footer: the place they share is counted once
    stacked = ('<div class="head">Featured</div><ul style="position: relative; height: 142px">'
               + "".join(f'<li style="position: absolute; top: 0; left: 0; width: 200px; height: 140px">Part {n}</li>' for n in range(1, 11))
               + '</ul><div class="foot"></div>')
    deck = mock_row(stacked)
    assert shot_facts()["list_area"] == 202 * 142, shot_facts()                                        # one item's area, not ten (ten would be 286,840 px², more than 0.8 of the box)
    assert deck["status"] == "warn" and [leaf(h["selector"]) for h in deck["hits"]] == ["main > figure.shot"], deck
    half = mock_row(stacked.replace("top: 0; left: 0;", "top: 0; left: 0; transform: translateX(101px);", 1))
    assert shot_facts()["list_area"] == 202 * 142 + 101 * 142, shot_facts()                            # one slide moved half its width: the union grows by the half that no other covers


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_list_whose_items_are_not_styled_adds_nothing_to_the_list_share(acme):
    """The browser end to end: a long list with no background and no border in a panel is not an item list, so it cannot excuse the panel's six styled rows beside three styled list items."""
    mock_row = lambda inside: mock_tell(acme, page_with_main(f'<h1>Acme hand tools</h1>\n<figure class="shot" style="height: auto">{inside}</figure>'))
    shot_facts = lambda: next(b for b in json.loads(Path(report(acme, pagecheck.report_tool("pages/index.html"))["measures"]).read_text(encoding="utf-8"))["views"][0]["tell_facts"]["boxes"] if leaf(b["sel"], 1) == "figure.shot")
    panel = mock_row(PLAIN_ROWS + STEPS_3 + PLAIN_LIST)
    assert panel["status"] == "warn" and "9 styled boxes" in panel["hits"][0]["text"], panel          # six rows and three items: nine, and the three items fill little of the box
    shot = shot_facts()
    assert (shot["styled"], shot["in_lists"]) == (9, 3), shot
    assert shot["list_area"] == 3 * 640 * 22, shot                                                     # the three styled items; the twelve items of 640 x 50 px beside them add nothing
    assert 12 * 640 * 50 + shot["list_area"] >= 0.8 * shot["width"] * shot["height"]                   # counting them would make the items 0.8 of the box, and excuse it
    nine = mock_row(PLAIN_ROWS + "".join(f'<div class="row">More {n}</div>' for n in range(3)) + PLAIN_LIST)
    assert nine["status"] == "warn" and (shot_facts()["in_lists"], shot_facts()["list_area"]) == (0, 0), nine   # a list with no styled item is no list at all: it adds no item and no area
    assert mock_row(PLAIN_ROWS + STEPS_3 + STEPS_3 + PLAIN_LIST)["status"] == "warn" and shot_facts()["list_area"] == 6 * 640 * 22   # two styled lists: both counted, the plain one not


CARD = f'<div class="card">{ICON.replace("20", "24")} <p>Spare parts, listed</p></div>'     # a bordered card with a 24 px svg icon
LANDING = f'''<section class="hero"><h1>Acme hand tools</h1><p><a class="btn" href="#a">Start now</a> <a class="btn" href="#b">Price list</a></p></section>
<div class="grid">{CARD * 6}</div>
<div class="band"><p>Ready to order?</p></div>'''   # two buttons, six cards with an icon each and a band: ten styled boxes in the main, no picture over 24 px


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_of_cards_with_icons_is_not_a_mock_up_but_a_panel_drawn_in_it_is(acme):
    """The icons are not pictures, so the box round them must not be taken for a drawing: the page, or a band of it, holds an h1 or several headings."""
    one = mock_tell(acme, page_with_main(LANDING))
    assert one["status"] == "pass" and not one.get("hits"), one                                     # main holds the h1 (and 10 styled boxes): the page is not a mock-up
    assert mock_tell(acme, page_with_main(LANDING.replace("<h1>Acme hand tools</h1>", "<p>Acme hand tools</p>")))["status"] == "warn"   # the same, without any heading: nothing says it is a page
    bands = lambda cards: page_with_main(f'<h1>Acme hand tools</h1>\n<div class="band"><div class="grid">{cards}</div></div>')
    assert mock_tell(acme, bands(CARD.replace("<p>", "<h3>").replace("</p>", "</h3>") * 9))["status"] == "pass"   # a band of nine cards, a heading and an icon in each
    assert mock_tell(acme, bands(CARD * 9))["status"] == "warn"                                 # nine cards with no heading: a box of boxes, as before
    drawn = mock_tell(acme, page_with_main(LANDING + f'\n<figure class="shot">{APP_PANEL}</figure>'))
    assert drawn["status"] == "warn" and [leaf(h["selector"]) for h in drawn["hits"]] == ["main > figure.shot"], drawn   # the panel, and not the page it is in
    assert mock_tell(acme, page_with_main(LANDING + f'\n<figure class="shot">{APP_PANEL + PIXEL}</figure>'))["status"] == "pass"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_collector_reports_the_styled_boxes_in_list_items_their_area_and_the_size_of_the_media(acme):
    write_page(acme, mock_page(APP_PANEL + PIXEL + CHECKLIST + TIMELINE + f"<picture>{SMALL_PIXEL}</picture><h2>Recent</h2>"))
    bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=acme)
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    boxes = {leaf(b["sel"], 1): b for b in v["tell_facts"]["boxes"]}
    shot = boxes["figure.shot"]
    # the panel: header, six rows and six chips (13); the checklist: ten items (10); the timeline: five items of three (15); two lists, in the items of which 25 boxes sit
    assert shot["styled"] == 13 + 10 + 15 and shot["in_lists"] == 25, shot
    assert shot["media_px"] == {"svg": 20, "img": 600, "picture": 20}, shot                     # a picture as big as the img it draws
    assert (shot["headings"], shot["h1"]) == (1, 0) and (boxes["main"]["headings"], boxes["main"]["h1"]) == (2, 1), (shot, boxes["main"])   # the h2 in the panel, and the h1 beside it
    assert boxes["ul"]["styled"] == 10 and boxes["ul"]["in_lists"] == 10 and boxes["ul"]["media_px"] == {}
    assert boxes["ul"]["list_area"] == 10 * 640 * 22                                            # the ten li of 640 x 22 px, which fill their ul
    assert boxes["ol"]["list_area"] == 5 * 600 * 22 and boxes["ol"]["list_area"] < boxes["ol"]["width"] * boxes["ol"]["height"], boxes["ol"]   # the five li of 600 x 22 px: not the ol, which has 40 px of padding
    assert 0 < shot["list_area"] < boxes["ul"]["list_area"] + boxes["ol"]["list_area"], shot    # the two lists in the panel: the panel is 300 px tall and its contents run past it, so only the part of their items that lies in it is counted
    assert boxes["main"]["list_area"] == shot["list_area"]                                      # the page round it holds the same two lists, and its box ends where the panel's does


def test_the_stock_order_is_a_note_only_when_every_piece_is_there_in_order():
    hero = {"found": True, "sel": "section.hero", "h1_sel": "h1", "top": 0, "words": 10, "viewport_height": 900, "lang": "en", "actions": []}
    tiles = [{"sel": "section.tiles", "tiles": [{"sel": f"div:nth-of-type({i})", "left": 316 * (i - 1), "top": 500, "width": 300, "height": 100} for i in (1, 2, 3)]}]
    band = lambda **k: {"sel": "section.closing", "top": 1400, "words": 8, "headings": 1, "actions": 1, **k}
    view = lambda width=1440, **k: tell_view(width=width, **{"hero": hero, "tiles": tiles, "details": [{"sel": "details", "top": 900}], "last_band": band(), **k})
    got = found_tells(view())["anatomy"]
    assert got == {"view": "1440-light", "hero": 0, "tiles": 500, "faq": 900, "closing_band": 1400}, got
    assert found_tells(view(headings=[{"sel": "h2", "text": "Najczęstsze pytania", "top": 900}], details=[]))["anatomy"]["faq"] == 900   # a heading that is a word of the list does as an FAQ ...
    assert found_tells(view(headings=[{"sel": "h2", "text": "Pricing", "top": 900}], details=[]))["anatomy"] is None   # ... another heading does not
    assert found_tells(view(width=390))["anatomy"] is None                                                           # no row of tiles on a phone
    assert found_tells(view(details=[{"sel": "d", "top": 400}]))["anatomy"] is None                                  # the FAQ must come after the tiles
    for off in ({"top": 800}, {"words": 41}, {"headings": 0}, {"actions": 0}):
        assert found_tells(view(last_band=band(**off)))["anatomy"] is None, off                                      # a closing band: after the FAQ, short, a heading and an action
    assert found_tells(view(hero={**hero, "top": 600}))["anatomy"] is None                                           # the hero is first


def test_the_tell_rows_warn_never_fail_and_a_tell_the_owner_adopted_has_one_row_only(tmp_path):
    """No browser: a hit is a warning that names the place and the widths and says why; nothing found passes; no view is not verified; a page language without a list is not verified."""
    p = make_project(tmp_path)
    eb = {"sel": "p.eyebrow", "text": "SPARE PARTS", "words": 2, "uppercase": True, "letter_spacing_em": 0.12, "font_size_px": 12, "heading_sel": "h1", "heading_tag": "h1", "heading_font_size_px": 32}
    rows = tell_rows_of(p, [tell_view(width=390, eyebrow=[eb]), tell_view(width=1440, eyebrow=[eb])])
    assert [r for r in rows if r.startswith("tell:")] == [f"tell:{t}" for t in TELL_IDS] and "note:stock-anatomy" not in rows
    e = rows["tell:eyebrow"]
    assert e["status"] == "warn" and e["tell"] == "eyebrow" and e["hits"][0]["selector"] == "p.eyebrow" and e["hits"][0]["widths"] == [390, 1440], e
    assert "1 found: p.eyebrow" in e["detail"] and "SPARE PARTS" in e["detail"] and "390, 1440 px" in e["detail"] and pagecheck.load_tells()["tells"][0]["why"] in e["detail"], e["detail"]
    assert {k: r["status"] for k, r in rows.items() if k != "tell:eyebrow"} == {f"tell:{t}": "pass" for t in TELL_IDS if t != "eyebrow"}
    assert all(r["detail"] == "none found in 2 view(s)" and r["hits"] == [] for k, r in rows.items() if k != "tell:eyebrow")
    many = [{**eb, "sel": f"p.k{n}"} for n in range(9)]
    assert "and 3 more" in tell_rows_of(p, [tell_view(eyebrow=many)])["tell:eyebrow"]["detail"] and len(tell_rows_of(p, [tell_view(eyebrow=many)])["tell:eyebrow"]["hits"]) == 9   # six are named, all are kept
    none = tell_rows_of(p, [])
    assert {r["status"] for r in none.values()} == {"skipped"} and all("not verified: no view was measured" in r["detail"] for r in none.values())
    bad = [{"width": 390, "scheme": "light", "error": "could not load"}]
    assert {r["status"] for r in tell_rows_of(p, bad).values()} == {"skipped"}
    german = tell_rows_of(p, [tell_view(lang="de")])
    assert german["tell:stock-second-action"]["status"] == "warn" and "NOT verified: no word list for de" in german["tell:stock-second-action"]["detail"]
    assert {r["status"] for k, r in german.items() if k != "tell:stock-second-action"} == {"pass"}
    nolang = tell_rows_of(p, [tell_view(lang="")])["tell:stock-second-action"]
    assert nolang["status"] == "warn" and "an unknown language (the page sets no lang)" in nolang["detail"], nolang
    assert tell_rows_of(p, [tell_view(lang="en-GB")])["tell:stock-second-action"]["status"] == "pass" and tell_rows_of(p, [tell_view(lang="pl-PL")])["tell:stock-second-action"]["status"] == "pass"
    cut = tell_view()
    cut["tell_facts"]["truncated"] = True
    for tid in ("middot-run", "styled-div-mock", "three-equal-tiles", "stray-box"):
        assert tell_rows_of(p, [cut])[f"tell:{tid}"]["status"] == "warn" and "NOT verified beyond the first elements" in tell_rows_of(p, [cut])[f"tell:{tid}"]["detail"], tid
    assert tell_rows_of(p, [cut])["tell:eyebrow"]["status"] == "pass"
    adopted = tell_rows_of(p, [tell_view(eyebrow=[eb])], {"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "no eyebrow over a heading"})
    assert "tell:eyebrow" not in adopted and len([k for k in adopted if k.startswith("tell:")]) == len(TELL_IDS) - 1   # the rule's page:rule:no-eyebrow row speaks for it


def test_a_tell_rule_is_judged_like_the_other_rules(tmp_path):
    """No browser: a hit of an adopted tell warns until the rule is tied to a recorded G4 line and fails after; none found passes."""
    p = make_project(tmp_path)
    eb = {"sel": "p.eyebrow", "text": "SPARE PARTS", "words": 2, "uppercase": True, "letter_spacing_em": 0.12, "font_size_px": 12, "heading_sel": "h1", "heading_tag": "h1", "heading_font_size_px": 32}
    rule = {"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "no eyebrow over a heading"}
    seen, clean = [tell_view(eyebrow=[eb])], [tell_view()]
    w = judge_rules(p, [rule], seen)["no-eyebrow"]
    assert w["status"] == "warn" and w["tied"] is False and w["tell"] == "eyebrow" and w["hits"][0]["selector"] == "p.eyebrow" and "not a recorded G4 rule line yet" in w["detail"], w
    assert "1 found of the tell \"An eyebrow over a heading\": p.eyebrow" in w["detail"], w["detail"]
    ok = judge_rules(p, [rule], clean)["no-eyebrow"]
    assert ok["status"] == "pass" and ok["hits"] == [] and "none found of the tell" in ok["detail"] and "not a recorded G4 rule line yet" in ok["detail"], ok
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule) No eyebrow over a heading, ever")
    assert bc("state", "--record", "G4", "GO", project=p).returncode == 0
    f = judge_rules(p, [rule], seen)["no-eyebrow"]
    assert f["status"] == "fail" and f["tied"] is True and "tied to the recorded G4 line" in f["detail"], f
    assert judge_rules(p, [rule], clean)["no-eyebrow"]["status"] == "pass"
    german = judge_rules(p, [{**rule, "id": "no-stock", "tell": "stock-second-action"}], [tell_view(lang="de")])["no-stock"]   # a rule on a tell that needs a word list
    assert german["status"] == "warn" and "NOT verified: no word list for de" in german["detail"], german


def test_a_rule_that_names_no_tell_is_a_usage_error_before_a_page_is_opened(tmp_path):
    p = make_project(tmp_path)
    write_page(p)
    (p / "qa").mkdir()
    rules = [{"id": "no-sparkle", "kind": "tell", "tell": "sparkle", "g4": "no sparkle"}]
    (p / "qa" / "rules.json").write_text(json.dumps({"schema": 1, "page": {"rules": rules}}), encoding="utf-8")
    r = bc("page-check", "pages/index.html", project=p)
    assert r.returncode == 2 and "qa/rules.json" in r.stderr and "page.rules" in r.stderr and "'sparkle' is not a generic tell" in r.stderr and all(t in r.stderr for t in TELL_IDS), r.stderr
    assert page_reports(p) == []
    with pytest.raises(CliError) as e:
        pagecheck.check_tell_rules(qa_rules.validate_page_rules(rules))
    assert e.value.code == 2
    pagecheck.check_tell_rules(qa_rules.validate_page_rules([{**rules[0], "tell": "eyebrow"}, {"id": "x", "kind": "max-marks-per-view", "max": 1, "g4": "g"}]))   # a known tell, and a rule of another kind, pass


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_each_tell_is_found_on_a_page_built_to_show_it(acme):
    write_page(acme, tells_page())
    r = bc("page-check", "pages/index.html", "--widths", "390,1440", "--schemes", "light", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr   # tells warn, they never fail a page
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    assert rep["status"] == "pass" and [x["id"] for x in rep["results"] if x["id"].startswith("tell:")] == [f"tell:{t}" for t in TELL_IDS]
    assert {tid: tell_row(rep, tid)["status"] for tid in TELL_IDS} == dict.fromkeys(TELL_IDS, "warn")
    for tid in TELL_IDS:
        assert tell_row(rep, tid)["hits"] and tell_row(rep, tid)["tell"] == tid and "1 found" in tell_row(rep, tid)["detail"], tell_row(rep, tid)
    hit = lambda tid: tell_row(rep, tid)["hits"][0]
    assert leaf(hit("eyebrow")["selector"]) == "section.hero > p.eyebrow" and hit("eyebrow")["widths"] == [390, 1440] and "SPARE PARTS" in hit("eyebrow")["text"]   # as the reader sees it, in capitals
    assert leaf(hit("arrow-glued")["selector"], 3) == "section.hero > p.actions > a.go" and "Start now →" in hit("arrow-glued")["text"] and hit("arrow-glued")["widths"] == [390, 1440]
    assert leaf(hit("middot-run")["selector"]) == "section.hero > p.meta" and "2 separating dots" in hit("middot-run")["text"]
    assert leaf(hit("stock-second-action")["selector"], 3) == "section.hero > p.actions > a.second" and "Learn more" in hit("stock-second-action")["text"]
    assert leaf(hit("hero-text-budget")["selector"], 1) == "section.hero" and hit("hero-text-budget")["widths"] == [390, 1440]
    assert leaf(hit("styled-div-mock")["selector"]) == "main > div.mock" and "8 styled boxes" in hit("styled-div-mock")["text"] and hit("styled-div-mock")["widths"] == [390, 1440]
    assert leaf(hit("three-equal-tiles")["selector"]) == "main > section.tiles" and hit("three-equal-tiles")["widths"] == [1440]   # at 390 px they are not shown as a row of three
    assert leaf(hit("stray-box")["selector"]) == "div.sheets > p.sheet" and hit("stray-box")["widths"] == [390, 1440] and "\"Sheet one\" is still shown 80 px below its parent" in hit("stray-box")["text"]
    note = row(rep, "note:stock-anatomy")
    assert note["status"] == "info" and note["anatomy"]["view"] == "1440-light" and note["anatomy"]["hero"] < note["anatomy"]["tiles"] < note["anatomy"]["faq"] < note["anatomy"]["closing_band"], note
    assert row(rep, "page:colours:light")["status"] == "pass" and row(rep, "page:fonts")["status"] == "pass"   # the page is otherwise the brand's: only the patterns warn


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_with_none_of_the_patterns_passes_every_tell_row(acme):
    write_page(acme)
    r, rep = check_page(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    assert rep["status"] == "pass"
    assert {tid: tell_row(rep, tid)["status"] for tid in TELL_IDS} == dict.fromkeys(TELL_IDS, "pass") and all("none found in 2 view(s)" in tell_row(rep, t)["detail"] for t in TELL_IDS)
    assert not [x for x in rep["results"] if x["id"] == "note:stock-anatomy"]
    v = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"][0]["tell_facts"]
    assert v["hero"]["found"] and v["hero"]["words"] == 13 and v["hero"]["actions"][0]["label"] == "Spare parts" and not v["eyebrow"] and not v["arrows"] and not v["separators"] and not v["boxes"] and not v["tiles"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_bulleted_list_a_spaced_arrow_and_a_hidden_child_are_not_what_the_tells_look_for(acme):
    """A tell is judged on what a reader sees: a list with a marker on each line is no run of dots between items, an arrow set apart by drawn spaces is not glued, and a
    <template> beside three tiles is no fourth tile. A tell adopted as a tied rule would otherwise fail an ordinary page; an inline breadcrumb still fails it."""
    page = write_page(acme)
    mutate(page, "</style>", """  ul.ticks, ol.crumbs { list-style: none; padding: 0; }
  ul.ticks li::before { content: "•"; margin-right: 6px; }
  ol.crumbs { display: flex; } ol.crumbs li + li::before { content: "·"; margin: 0 4px; }
  .trio { display: flex; } .trio > div { flex: 1 1 0; }
</style>""")
    mutate(page, "</main>", """<ul class="ticks"><li>Forged steel heads</li><li>Spare parts listed</li><li>Repairs by post</li></ul>
  <p class="brk">• Forged steel heads<br>• Spare parts listed<br>• Repairs by post</p>
  <p><a href="#s">Spare parts&nbsp;&nbsp;&nbsp;&nbsp;→</a></p>
  <div class="trio"><div><h2>One</h2></div><div><h2>Two</h2></div><div><h2>Three</h2></div><template><div><h2>Not shown</h2></div></template></div>
</main>""")
    r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    assert tell_row(rep, "middot-run")["status"] == "pass" and tell_row(rep, "arrow-glued")["status"] == "pass", [tell_row(rep, t) for t in ("middot-run", "arrow-glued")]
    assert tell_row(rep, "three-equal-tiles")["status"] == "warn" and leaf(tell_row(rep, "three-equal-tiles")["hits"][0]["selector"]) == "main > div.trio"
    set_page_rules(acme, {"id": "no-dots", "kind": "tell", "tell": "middot-run", "g4": "no run of dots between items"})
    record_g4(acme, "(rule) no run of dots between items")
    r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr   # tied rules, and the page holds to them
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    assert rule_row(rep, "no-dots")["status"] == "pass" and rule_row(rep, "no-dots")["tied"] is True
    mutate(page, "</main>", '<ol class="crumbs"><li>Home</li><li>Tools</li><li>Saws</li></ol>\n</main>')   # a breadcrumb of dots in one row is the pattern
    r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=acme)
    assert r.returncode == 1, r.stdout + r.stderr
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    bad = rule_row(rep, "no-dots")
    assert bad["status"] == "fail" and [leaf(h["selector"], 1) for h in bad["hits"]] == ["ol.crumbs"] and "2 separating dots between its children" in bad["hits"][0]["text"], bad


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_in_german_says_its_stock_labels_are_not_verified(acme):
    write_page(acme, tells_page(lang="de", second="Mehr erfahren"))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    stock = tell_row(rep, "stock-second-action")
    assert stock["status"] == "warn" and "NOT verified: no word list for de" in stock["detail"] and stock["hits"] == [], stock
    assert tell_row(rep, "eyebrow")["status"] == "warn" and tell_row(rep, "arrow-glued")["status"] == "warn"   # the tells that need no word list are still found
    write_page(acme, tells_page(lang="pl", second="Dowiedz się więcej"), "pages/pl.html")
    r, rep = check_page(acme, "--schemes", "light", page="pages/pl.html")
    assert tell_row(rep, "stock-second-action")["status"] == "warn" and "Dowiedz się więcej" in tell_row(rep, "stock-second-action")["detail"] and "NOT verified" not in tell_row(rep, "stock-second-action")["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_eyebrow_over_a_heading_warns_and_an_adopted_eyebrow_rule_fails(acme):
    page = write_page(acme)
    mutate(page, "</style>", "  .eyebrow { margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; }\n</style>")
    mutate(page, "<h1>", '<p class="eyebrow">New release</p>\n  <h1>')
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr   # a tell is a warning
    e = tell_row(rep, "eyebrow")
    assert e["status"] == "warn" and leaf(e["hits"][0]["selector"]) == "main > p.eyebrow" and "NEW RELEASE" in e["hits"][0]["text"] and rep["status"] == "pass", e
    set_page_rules(acme, {"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "no eyebrow over a heading"})
    r, rep = check_page(acme, "--schemes", "light")   # adopted, but G4 is not recorded: still a warning, now on the rule's row
    assert r.returncode == 0, r.stdout + r.stderr
    w = rule_row(rep, "no-eyebrow")
    assert w["status"] == "warn" and w["tied"] is False and leaf(w["hits"][0]["selector"]) == "main > p.eyebrow" and "not a recorded G4 rule line yet" in w["detail"], w
    assert not [x for x in rep["results"] if x["id"] == "tell:eyebrow"]   # the rule speaks for the tell
    record_g4(acme, "(rule) no eyebrow over a heading")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = rule_row(rep, "no-eyebrow")
    assert bad["status"] == "fail" and bad["tied"] is True and bad["g4_line"] == "(rule) no eyebrow over a heading" and "NEW RELEASE" in bad["detail"], bad
    mutate(page, '<p class="eyebrow">New release</p>\n  ', "")
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = rule_row(rep, "no-eyebrow")
    assert ok["status"] == "pass" and ok["hits"] == [] and "a recorded G4 rule" in ok["detail"], ok


SOCIAL_FILL = {"lang": "en", "name": "Acme", "width": "1080", "height": "1080", "bg": "var(--color-bg)", "fg": "var(--color-text)", "muted": "var(--color-text)", "accent": "var(--color-accent)",
               "regulated_attr": "", "mark": "", "counter": "1 / 5", "kicker": "Spare parts", "headline": "Every tool has a published spare-parts list."}


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_social_post_kicker_is_reported_as_an_eyebrow(acme):
    """The plugin's own social post (templates/social/post-1x1.html) has a small, uppercase, tracked label above its headline: by the tell it is an eyebrow. It is reported and left as it is."""
    template = (ROOT / "templates" / "social" / "post-1x1.html").read_text(encoding="utf-8")
    html = template
    for key, value in SOCIAL_FILL.items():
        html = html.replace("{{" + key + "}}", value)
    assert "{{" not in html
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8"><link rel="stylesheet" href="../assets/tokens/tokens.css">')
    write_page(acme, html, "pages/post.html")
    r, rep = check_page(acme, "--schemes", "light", page="pages/post.html")
    e = tell_row(rep, "eyebrow")
    assert e["status"] == "warn" and [leaf(h["selector"]) for h in e["hits"]] == ["main > p.kicker"] and "SPARE PARTS" in e["hits"][0]["text"] and "in capitals" in e["hits"][0]["text"], e
    assert (ROOT / "templates" / "social" / "post-1x1.html").read_text(encoding="utf-8") == template   # nothing was changed


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_tells_collector_reports_the_candidates_a_page_shows(acme):
    style = """  .rule { height: 4px; background: var(--color-accent); }
  .lbl { margin: 0; font-size: 11px; letter-spacing: 0.1em; }
  .wrap > span { text-transform: uppercase; }
  ul.dots { list-style: none; padding: 0; display: flex; }
  ul.dots li + li::before { content: "·"; margin: 0 4px; }
  ul.ticks { list-style: none; padding: 0; }
  ul.ticks li::before { content: "•"; margin-right: 6px; }
  .arrow::after { content: " ›"; }
  .boxes { width: 300px; }
  .boxes div { border: 1px solid var(--color-text); height: 10px; margin: 2px; }
  .trio { display: flex; } .trio > div { flex: 1 1 0; }
"""
    body = """<nav><a href="#n1">Home →</a> <a href="#n2">About</a></nav>
<main>
<section class="hero">
  <h1>Collector page</h1>
  <nav class="inner"><a href="#q">Inner menu</a></nav>
  <p class="lbl">Seen from the shop</p><div class="rule"></div><h2>After a rule</h2>
  <p class="lbl">Not before</p><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="" width="20" height="20"><h2>After an image</h2>
  <h2>Heading</h2><h3>After a heading</h3>
  <ul class="menu"><li>Menu</li></ul><h3>After a list</h3>
  <div class="wrap"><span>Inside a wrapper</span></div><h3>Wrapped label</h3>
  <p>Three words here <a class="plain" href="#p">link</a></p>
  <p><a class="next" href="#x">Next</a> <a class="nudge" href="#y">Go -&gt;</a> <a class="icon" href="#z">→</a> <a class="after arrow" href="#w">Read</a> <button class="far">Back  ←</button></p>
</section>
<ul class="dots"><li>A</li><li>B</li><li>C</li></ul>
<p class="inline">One · <b>two</b> · three · four</p>
<p class="single">Only · one</p>
<ul class="ticks"><li>Forged steel heads</li><li>Spare parts listed</li><li>Repairs by post</li></ul>
<p class="brk">• Forged steel heads<br>• Spare parts listed<br>• Repairs by post</p>
<p class="mixed">• Forged steel · spare parts<br>• Repairs by post</p>
<article class="blocky">Intro • <div>• Item</div>• Tail</article>
<p class="spaced"><a class="gap" href="#g">Spare parts&nbsp;&nbsp;&nbsp;&nbsp;→</a> <a class="glue" href="#h">Repairs&nbsp;→</a></p>
<div class="boxes">""" + "<div></div>" * 8 + """</div>
<div class="boxes"><div></div><div></div><div></div><table><tr><td style="border:1px solid">a</td><td style="border:1px solid">b</td></tr></table>
<input style="border:1px solid"><input style="border:1px solid"><input style="border:1px solid"><input style="border:1px solid"><input style="border:1px solid"></div>
<div data-sample="a mock screen"><div class="boxes">""" + "<div></div>" * 8 + """</div></div>
<div class="trio"><div><h3>One</h3></div><div><h3>Two</h3></div><div><h3>Three</h3></div><template><div><h3>Not shown</h3></div></template></div>
<div class="trio"><div><h3>One</h3></div><div>No heading</div><div><h3>Three</h3></div></div>
<div class="trio"><div><h3>One</h3></div><div><h3>Two</h3></div><div><h3>Three</h3></div><div><h3>Four</h3></div></div>
</main>"""
    write_page(acme, PAGE.replace("</style>", style + "</style>").replace(PAGE[PAGE.index("<main>"):PAGE.index("</main>") + len("</main>")], body))
    bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=acme)   # the report is what is read; other rows of this odd page may fail
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    f = v["tell_facts"]
    assert f["viewport"] == {"width": 1440, "height": 900} and "truncated" not in f
    texts = {e["text"].lower(): e for e in f["eyebrow"]}
    assert set(texts) == {"seen from the shop", "inside a wrapper"}, sorted(texts)      # not "Not before" (an image sits between), not a heading before a heading, not a list
    shop = texts["seen from the shop"]
    assert (shop["words"], shop["uppercase"], shop["letter_spacing_em"], shop["font_size_px"], shop["heading_tag"], shop["heading_font_size_px"]) == (4, False, 0.1, 11, "h2", 24)   # the empty rule box is looked past
    wrapped = texts["inside a wrapper"]
    assert wrapped["uppercase"] is True and wrapped["sel"].endswith("div.wrap:nth-of-type(2)") and wrapped["heading_tag"] == "h3"   # a wrapper's text is styled by the span inside it
    arrows = {a["label"]: a for a in f["arrows"]}
    assert set(arrows) == {"Home →", "Go ->", "Read ›", "Back ←", "Spare parts →", "Repairs →"}, sorted(arrows)       # "Next" has no arrow, and "→" alone is an icon button
    assert (arrows["Home →"]["edge"], arrows["Home →"]["gap_chars"], arrows["Home →"]["glyph"]) == ("end", 1, "→")
    assert (arrows["Go ->"]["edge"], arrows["Go ->"]["glyph"]) == ("end", "->") and arrows["Read ›"]["gap_chars"] == 1 and arrows["Back ←"]["gap_chars"] == 1   # the ::after content is part of the label, white space collapses
    assert (arrows["Spare parts →"]["gap_chars"], arrows["Repairs →"]["gap_chars"]) == (4, 1)   # four no-break spaces are drawn, so the gap is 4; one is a gap of 1
    seps = {(s["sel"].split(" > ")[-1].split(":")[0], s["via"]): s["count"] for s in f["separators"]}
    assert seps == {("p.inline", "text"): 3, ("p.single", "text"): 1, ("p.mixed", "text"): 1, ("ul.dots", "pseudo"): 2}, seps   # a child element stands in the text as one unit
    # not candidates: a stacked list marked by ::before (ul.ticks), dots that start a line after a <br> (p.brk), dots at the edge of a line next to a block child (article.blocky); a marker that starts a line
    # is not counted where the same line also holds a separator (p.mixed: one)
    hero = f["hero"]
    assert hero["found"] and hero["sel"] == "body > main > section.hero" and hero["h1_sel"].endswith("h1") and hero["lang"] == "en"
    assert [a["label"] for a in hero["actions"]] == ["link", "Next", "Go ->", "→", "Read ›", "Back ←"]   # the nav inside the hero is not an action, the first six are kept
    assert hero["words"] == 35, hero["words"]                                           # the nav's words are not counted
    mocks = [b for b in f["boxes"] if b["styled"] == 8 and b["width"] == 300]
    assert [(m["labelled"], m["media_px"], m["in_lists"], m["list_area"]) for m in mocks] == [(False, {}, 0, 0), (True, {}, 0, 0)], f["boxes"]   # eight bordered boxes; the same inside a labelled sample
    assert not [b for b in f["boxes"] if b["sel"].endswith("div.boxes:nth-of-type(2)")]          # three bordered boxes: inputs and table cells do not count
    main = next(b for b in f["boxes"] if b["sel"] == "body > main")
    assert main["media_px"] == {"img": 20} and main["styled"] >= 16 and main["parent"] is None and all(b["parent"] is not None for b in f["boxes"] if b is not main)
    assert [t["sel"].endswith("div.trio:nth-of-type(4)") for t in f["tiles"]] == [True]          # exactly three shown children, each with a heading (the <template> in the first row is no tile; four, or one with no heading, is no row)
    tiles = f["tiles"][0]["tiles"]
    assert len({t["width"] for t in tiles}) == 1 and tiles[0]["left"] < tiles[1]["left"] < tiles[2]["left"] and len({t["top"] for t in tiles}) == 1
    assert [h["text"] for h in f["headings"]][:4] == ["Collector page", "After a rule", "After an image", "Heading"] and f["details"] == []
    assert f["last_band"]["sel"].endswith("div.trio:nth-of-type(6)") and f["last_band"]["headings"] == 4 and f["last_band"]["actions"] == 0


STRAY_STYLE = """  .stack { position: relative; height: 40px; margin: 0 0 160px; }
  .sheet { height: 24px; margin: 0; }
  .drop { animation: drop 150ms linear forwards; }
  @keyframes drop { to { transform: translateY(120px); } }
  .vanish { animation: vanish 150ms linear forwards; }
  @keyframes vanish { to { transform: translateY(120px); opacity: 0; } }
  .sway { animation: sway 1s linear infinite alternate; }
  @keyframes sway { from { transform: translateY(100px); } to { transform: translateY(140px); } }
  .clip { overflow: hidden; }
  .tall-only { position: absolute; left: 0; top: calc(100vh - 860px); }
"""


def stray_page(*stacks: str, style: str = "") -> str:
    """A page of short boxes (40 px high, 160 px apart), each holding the markup given: the stray-box tell looks at what the animations leave outside them."""
    body = "".join(f'<div class="stack">{x}</div>\n' for x in stacks)
    return PAGE.replace("</style>", STRAY_STYLE + style + "</style>").replace(PAGE[PAGE.index("<main>"):PAGE.index("</main>") + len("</main>")], f"<main>\n<h1>Acme hand tools</h1>\n{body}</main>")


def stray_check(p: Path, page: str) -> tuple[dict, dict]:
    """page-check at 1440 px, light, of `page`. -> (the stray-box row, the view as measured). The other rows of an odd page may fail: the tell row is what is read."""
    write_page(p, page)
    r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=p)
    assert r.returncode in (0, 1), r.stdout + r.stderr
    rep = report(p, pagecheck.report_tool("pages/index.html"))
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    return tell_row(rep, "stray-box"), v


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_box_an_animation_leaves_outside_its_parent_is_warned_and_a_hidden_clipped_or_unfinished_one_is_not(acme):
    """The pilot-style bug: sheets left on screen after their animation. Judged on the page after its animations ended: a sheet that ends outside its short parent is found; one that ends
    transparent, or inside an overflow: hidden parent, is not; an animation that never ends makes the tell NOT verified, never a pass."""
    row_, v = stray_check(acme, stray_page('<p class="sheet drop">Left behind</p>', '<p class="sheet vanish">Gone</p>', '<div class="clip"><p class="sheet drop">Clipped</p></div>',
                                           '<p class="sheet">Still</p>'))
    assert row_["status"] == "warn" and [leaf(h["selector"]) for h in row_["hits"]] == ["div.stack > p.sheet.drop"] and "NOT verified" not in row_["detail"], row_
    assert row_["hits"][0]["text"] == '"Left behind" is still shown 80 px below its parent body > main > div.stack:nth-of-type(1) after the page settled', row_["hits"]
    assert v["animations"]["running"] == 0 and v["animations"]["capped"] is False                                                   # the animations ended before the page was measured
    strays = {leaf(x["sel"]): x for x in v["tell_facts"]["strays"]}
    assert set(strays) == {"div.stack > p.sheet.drop"} and strays["div.stack > p.sheet.drop"]["animating"] is False, strays          # transparent, clipped and in place: not even candidates
    # an animation that never ends: where the sheet is depends on when the page was measured
    row_, v = stray_check(acme, stray_page('<p class="sheet sway">Swaying</p>'))
    assert row_["status"] == "warn" and row_["hits"] == [] and "NOT verified at 1440 px" in row_["detail"] and "never end" in row_["detail"] and "1 found" not in row_["detail"], row_
    assert v["animations"]["running"] >= 1
    (sway,) = v["tell_facts"]["strays"]
    assert sway["animating"] is True and sway["parent"]["side"] == "below" and sway["parent"]["px"] >= 60
    assert "still animating: " in row_["detail"] and leaf(sway["sel"]) in row_["detail"]
    # an animation that waits for a scroll never starts on a page that is not scrolled: the same
    row_, v = stray_check(acme, stray_page('<p class="sheet reveal">Scroll</p>', style="  .reveal { animation: drop linear both; animation-timeline: view(); }\n"))
    assert row_["status"] == "warn" and row_["hits"] == [] and "NOT verified at 1440 px" in row_["detail"] and "wait for a scroll" in row_["detail"], row_
    assert v["animations"]["running"] == 1 and v["tell_facts"]["strays"][0]["animating"] is True
    # an ancestor that clips cuts off only what lies outside its box: `main { overflow-x: hidden }` (its overflow-y computes to auto) still holds the sheet 80 px below its parent, so it is found
    row_, v = stray_check(acme, stray_page('<p class="sheet drop">Left behind</p>', style="  main { overflow-x: hidden; }\n"))
    assert row_["status"] == "warn" and [leaf(h["selector"]) for h in row_["hits"]] == ["div.stack > p.sheet.drop"] and "NOT verified" not in row_["detail"], row_
    assert row_["hits"][0]["text"] == '"Left behind" is still shown 80 px below its parent body > main > div.stack after the page settled', row_["hits"]
    (held,) = v["tell_facts"]["strays"]
    assert (held["parent"]["side"], held["parent"]["px"], held["animating"]) == ("below", 80, False), held
    for style in ("  main { overflow: hidden; padding-bottom: 400px; }\n", "  html, body { overflow-x: hidden; }\n"):   # a wrapper cut on both axes that is tall enough, and the viewport's own overflow
        row_, _ = stray_check(acme, stray_page('<p class="sheet drop">Left behind</p>', style=style))
        assert row_["status"] == "warn" and [leaf(h["selector"]) for h in row_["hits"]] == ["div.stack > p.sheet.drop"], (style, row_)
    # a wrapper that clips cuts off the sheet that ends wholly outside its box (the wrapper is as short as the sheet, which ends 120 px lower): not a candidate
    row_, v = stray_check(acme, stray_page('<div class="wrap"><p class="sheet drop">Cut off</p></div>', style="  .wrap { overflow-x: hidden; }\n"))
    assert row_["status"] == "pass" and row_["hits"] == [], row_
    assert v["tell_facts"]["strays"] == [], v["tell_facts"]["strays"]
    # both at once: the wrapper of the page holds the first sheet, the one inside a wrapper of its own is cut off
    row_, _ = stray_check(acme, stray_page('<p class="sheet drop">Left behind</p>', '<div class="wrap"><p class="sheet drop">Cut off</p></div>',
                                           style="  main { overflow-x: hidden; } .wrap { overflow-x: hidden; }\n"))
    assert row_["status"] == "warn" and [h["text"].split(" is still")[0] for h in row_["hits"]] == ['"Left behind"'], row_


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_box_that_is_out_of_place_only_in_a_tall_window_is_found_from_the_tall_walk(acme):
    """Each width is measured once more in a window 1300 px high: a box placed by the height of the window (here 100vh - 860 px, which is 40 px at the usual 900 and 440 px at 1300) shows only there."""
    row_, v = stray_check(acme, stray_page('<p class="sheet tall-only">Pushed down</p>'))
    assert v["tell_facts"]["strays"] == [] and v["viewport"] == {"width": 1440, "height": 900}                                          # at 900 px it sits at the foot of its parent
    tall = v["tell_facts"]["strays_tall"]
    assert tall["viewport"] == {"width": 1440, "height": 1300} and tall["animations"]["running"] == 0 and "truncated" not in tall and "error" not in tall
    assert [(leaf(x["sel"]), x["parent"]["side"], x["parent"]["px"]) for x in tall["strays"]] == [("div.stack > p.sheet.tall-only", "below", 400)], tall
    assert row_["status"] == "warn" and [h["widths"] for h in row_["hits"]] == [[1440]] and row_["hits"][0]["text"].endswith("400 px below its parent " + tall["strays"][0]["parent"]["sel"] + " after the page settled, in a window 1300 px high"), row_
    assert v["height"] < 1300 and v["viewport"]["height"] == 900, "the view itself keeps the viewport it is keyed by"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_box_the_window_cuts_off_sideways_is_not_a_stray_and_a_box_out_of_place_stands_for_its_children(acme):
    """With `overflow-x: hidden` on html and body, a box left past the left or right edge cannot be seen or scrolled to: not a candidate. A box left 2000 px to the left with two sheets
    inside it is one stray, the box: its children are out the same way only because it is."""
    for side in ("left: -2000px", "left: 2000px"):
        row_, v = stray_check(acme, stray_page('<p class="sheet off">Off</p>', style=f"  html, body {{ overflow-x: hidden; }} .off {{ position: relative; {side}; }}\n"))
        assert row_["status"] == "pass" and v["tell_facts"]["strays"] == [], (side, v["tell_facts"]["strays"])
    row_, v = stray_check(acme, stray_page('<div class="away"><p class="sheet">One</p><p class="sheet">Two</p></div>', style="  .away { position: relative; left: -2000px; }\n"))
    assert row_["status"] == "warn" and [leaf(h["selector"], 1) for h in row_["hits"]] == ["div.away"], row_["hits"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_what_only_the_tall_window_brings_is_kept_out_of_the_views_load_row(acme):
    """The tall window is for the stray-box tell alone: a page error or a missing file that only the resize to 1300 px brings is kept on `strays_tall` as `load`, and page:load,
    which is a failing row, reads only what the view logged at its own height."""
    script = "<script>addEventListener('resize', () => { if (innerHeight > 1000) null.boom(); });</script>"
    picture = '<picture><source media="(min-height: 1200px)" srcset="missing-tall.png"><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="" width="1" height="1"></picture>'
    for markup, said in ((script, "pageerror: "), (picture, "failed local request: 404 /pages/missing-tall.png")):
        write_page(acme, stray_page('<p class="sheet">Steady</p>' + markup))
        r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=acme)
        rep = report(acme, pagecheck.report_tool("pages/index.html"))
        load = row(rep, "page:load:1440-light")
        assert load["status"] == "pass", (said, load)
        (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
        assert v["errors"] == [] and v["failed_local"] == [] and v["non_local"] == [], (said, v["errors"], v["failed_local"])
        assert any(x.startswith(said) for x in v["tell_facts"]["strays_tall"]["load"]), (said, v["tell_facts"]["strays_tall"])
        stray = tell_row(rep, "stray-box")
        assert "in a window 1300 px high: the page logged " in stray["detail"] and "only after the resize, which page:load does not judge" in stray["detail"], (said, stray)   # said on the tell's row
        assert r.returncode in (0, 1), r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_that_is_scrolled_when_it_is_measured_has_nothing_stray_above_its_scroll_position(acme):
    """A page can be scrolled when the check measures it (a script, an `autofocus` field below the fold, a `#fragment` in the address): what lies above the scroll position is still on the page, and is not "past the
    top edge of the screen". The edges are those of the page, so the verdict is the one the same page gets unscrolled: a sheet left below its parent, and a box left above the top of the page, are still found."""
    tall = "main { padding-bottom: 1600px; } .above { position: absolute; left: 0; top: -2000px; } .narrow { width: 100px; }\n"
    for scroll in ("window.scrollTo(0, 700)", "window.scrollTo(0, document.documentElement.scrollHeight)"):   # a page scrolled part way, and to the foot
        script = f"<script>{scroll}</script>"
        row_, v = stray_check(acme, stray_page('<p class="sheet">Top of the page</p>', '<p class="sheet">Middle</p>' + script, style=tall))
        assert row_["status"] == "pass" and row_["hits"] == [], (scroll, row_)                                                          # the heading and the first sheet lie above the scroll position: not strays
        assert v["tell_facts"]["strays"] == [] and v["tell_facts"]["strays_tall"]["strays"] == [], (scroll, v["tell_facts"]["strays"], v["tell_facts"]["strays_tall"]["strays"])
        row_, v = stray_check(acme, stray_page('<p class="sheet drop">Left behind</p>', '<p class="sheet">Middle</p>' + script, style=tall))
        assert row_["status"] == "warn" and [leaf(h["selector"]) for h in row_["hits"]] == ["div.stack > p.sheet.drop"], (scroll, row_)    # the stray is found, and it is not the heading
        assert row_["hits"][0]["text"] == '"Left behind" is still shown 80 px below its parent body > main > div.stack:nth-of-type(1) after the page settled' and "top edge" not in row_["detail"], row_["hits"]
        row_, v = stray_check(acme, stray_page('<p class="sheet">Top of the page</p>', '<p class="sheet above">Above the page</p>' + script, style=tall))   # really above the top of the page: past the edge
        (above,) = v["tell_facts"]["strays"]
        assert above["text"] == "Above the page" and above["viewport"]["side"] == "top" and above["viewport"]["px"] > 1000 and above["parent"]["side"] == "above", above
        assert row_["status"] == "warn" and [h["text"].split(" is still")[0] for h in row_["hits"]] == ['"Above the page"'] and "past the top edge of the screen" in row_["hits"][0]["text"], row_
    # a page that is scrolled sideways: what lies left of the window is on the page, and no stray either
    row_, v = stray_check(acme, stray_page('<p class="sheet narrow">Narrow</p>', '<p class="sheet">Middle</p><script>window.scrollTo(300, 700)</script>', style=tall + "main { min-width: 2400px; }\n"))
    assert row_["status"] == "pass" and row_["hits"] == [] and v["tell_facts"]["strays"] == [] and v["tell_facts"]["strays_tall"]["strays"] == [], (row_, v["tell_facts"]["strays"])


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_stray_collector_reports_where_a_shown_box_lies_against_its_parent_and_the_screen(acme):
    """What the browser reports as `strays`: only a shown box, not fixed or sticky, with no ancestor that clips it, that lies wholly outside its parent or the screen by at least the tell's own 8 px (the request carries it)."""
    style = """  .right { position: relative; left: 1600px; } .left { position: relative; left: -2000px; }
  .fixed { position: fixed; top: 0; left: -2000px; } .sticky { position: sticky; top: 0; transform: translateY(300px); }
  .skip { position: absolute; left: -9999px; top: 0; } .ghost { position: absolute; left: -9999px; top: 0; }
  .hidden { transform: translateY(120px); visibility: hidden; } .none { transform: translateY(120px); display: none; }
  .faint { transform: translateY(120px); opacity: 0; } .near { transform: translateY(43px); } .hair { transform: translateY(41px); } .touching { transform: translateY(40px); }
  .overlap { transform: translateY(30px); } .layer { overflow: clip; }
"""
    page = stray_page('<p class="sheet drop">Below</p>', '<p class="sheet right">Right</p>', '<p class="sheet left">Left</p>', '<p class="sheet fixed">Fixed</p>', '<p class="sheet sticky">Sticky</p>',
                      '<a class="skip" href="#x">Skip to content</a><span class="ghost">Off screen</span>', '<p class="sheet hidden">Hidden</p>', '<p class="sheet none">None</p>',
                      '<p class="sheet faint">Faint</p>', '<p class="sheet near">Near</p>', '<p class="sheet hair">Hair</p>', '<p class="sheet touching">Touching</p>', '<p class="sheet overlap">Overlap</p>',
                      '<div class="layer"><p class="sheet drop">Clipped by overflow clip</p></div>', style=style)
    _, v = stray_check(acme, page)
    f = v["tell_facts"]
    assert "truncated" not in f
    found = {x["text"]: x for x in f["strays"]}
    assert set(found) == {"Below", "Right", "Left", "Off screen"}, sorted(found)         # not fixed, sticky, hidden, faint, a skip link, 3 px off (under the tell's 8), 1 px off, touching, overlapping or clipped
    assert set(found["Below"]) == {"sel", "text", "animating", "parent", "viewport"} and set(found["Below"]["parent"]) == {"sel", "side", "px"} and found["Below"]["viewport"] is None
    assert found["Below"]["parent"]["side"] == "below" and found["Below"]["parent"]["px"] == 80 and found["Below"]["animating"] is False
    assert (found["Right"]["parent"]["side"], found["Right"]["parent"]["px"]) == ("right", 160) and found["Right"]["viewport"] == {"side": "right", "px": 160}
    assert (found["Left"]["parent"]["side"], found["Left"]["parent"]["px"]) == ("left", 560) and found["Left"]["viewport"] == {"side": "left", "px": 560}
    assert found["Off screen"]["viewport"]["side"] == "left" and found["Off screen"]["viewport"]["px"] > 8000 and found["Off screen"]["parent"]["side"] == "left"
    assert found["Below"]["parent"]["sel"].endswith("div.stack:nth-of-type(1)")
    assert f["strays_tall"]["viewport"]["height"] == 1300 and [x["text"] for x in f["strays_tall"]["strays"]] == [x["text"] for x in f["strays"]]   # nothing there depends on the height


def many_stacks(n: int, inner: str) -> list[str]:
    return [inner] * n


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_more_than_a_hundred_offsets_under_the_tells_threshold_never_hide_a_real_stray(acme):
    """Candidates start at the tell's own 8 px (the request carries it), so 120 boxes 3 px out of place do not fill the list of 100 before the real stray."""
    small = '<p class="sheet small">tiny</p>'
    row_, v = stray_check(acme, stray_page(*many_stacks(120, small), '<p class="sheet drop">Left behind</p>', style="  .small { transform: translateY(43px); }\n"))
    f = v["tell_facts"]
    assert [x["text"] for x in f["strays"]] == ["Left behind"] and "strays_capped" not in f and "strays_truncated" not in f, [x["text"] for x in f["strays"]][:3]
    assert row_["status"] == "warn" and [h["text"].split(" is still")[0] for h in row_["hits"]] == ['"Left behind"'] and "NOT verified" not in row_["detail"], row_


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_with_more_stray_boxes_than_the_list_holds_says_not_verified_and_never_passes_silently(acme):
    row_, v = stray_check(acme, stray_page(*many_stacks(104, '<p class="sheet drop">Left behind</p>')))
    f = v["tell_facts"]
    assert len(f["strays"]) == 100 and f["strays_capped"] is True and f["strays_truncated"] is True, (len(f["strays"]), f.get("strays_capped"))
    assert row_["status"] == "warn" and pagecheck.STRAY_CAP_NOTE in row_["detail"] and row_["hits"], row_


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_run_of_two_schemes_measures_the_tall_window_once_per_width(acme):
    write_page(acme, stray_page('<p class="sheet tall-only">Pushed down</p>'))
    r = bc("page-check", "pages/index.html", "--widths", "1440,1024", "--schemes", "light,dark", project=acme)
    assert r.returncode in (0, 1), r.stdout + r.stderr
    rep = report(acme, pagecheck.report_tool("pages/index.html"))
    views = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    assert [(v["width"], v["scheme"], "strays_tall" in v["tell_facts"]) for v in views] == [(1440, "light", True), (1440, "dark", False), (1024, "light", True), (1024, "dark", False)]
    row_ = tell_row(rep, "stray-box")
    assert row_["status"] == "warn" and sorted(w for h in row_["hits"] for w in h["widths"]) == [1024, 1440] and "NOT verified" not in row_["detail"], row_   # the dark views are no error and no note


def test_a_view_with_no_tall_walk_is_measured_in_the_other_scheme_and_the_cap_of_the_list_is_not_verified():
    hits = lambda *views: found_tells(*views)["hits"]["stray-box"]
    notes = lambda *views: found_tells(*views)["unverified"]["stray-box"]
    tall = {"viewport": {"width": 1440, "height": 1300}, "animations": {"waited": 0, "running": 0, "capped": False}, "strays": [stray(sel="div.late", parent=("below", 400))]}
    light, dark = tell_view(scheme="light", strays=[], strays_tall=tall), tell_view(scheme="dark", strays=[])
    assert [h["selector"] for h in hits(light, dark)] == ["div.late"] and notes(light, dark) == []
    assert notes(tell_view(strays=[stray()], strays_capped=True, strays_truncated=True)) == [pagecheck.STRAY_CAP_NOTE]
    assert notes(tell_view(strays=[], strays_tall={**tall, "strays": [], "truncated": True, "capped": True})) == [pagecheck.STRAY_CAP_NOTE]
    assert pagecheck.stray_min_px() == 8


# ---------------------------------------------------------------- a report input that stands for a part of a file: BRAND-STATE.md by its G4 rules (no browser)

import _common  # noqa: E402
from _common import PartInput, sha256_file  # noqa: E402

G4_PART_RULE = "(rule) one mark per screen"


def hand_report(p: Path, *, whole: bool = False) -> dict:
    """The report `page-check` writes for pages/index.html, made by hand so that no browser is needed: the inputs are pagecheck.base_inputs (BRAND-STATE.md by its "g4-rules" part), or, with `whole`, the same
    with BRAND-STATE.md as a whole file, the way older reports list it. -> the report as read."""
    page = write_page(p)
    inputs = pagecheck.base_inputs(p, pagecheck.Target("project", "pages/index.html", page="pages/index.html", file=page))
    if whole:
        inputs = [p / "BRAND-STATE.md" if isinstance(i, PartInput) else i for i in inputs]
    rep = Report(pagecheck.report_tool("pages/index.html"), p, inputs, renderer="chromium")
    rep.add("page:target", "info", "what was checked", detail="project page pages/index.html")
    rep.write()
    _common._OPEN_REPORTS.remove(rep)   # written by hand, never finished
    return report(p, pagecheck.report_tool("pages/index.html"))


def state_with_g4(tmp_path: Path) -> Path:
    p = make_project(tmp_path)
    record_g4(p, G4_PART_RULE)
    return p


def test_page_check_lists_brand_state_by_its_g4_rules_and_the_report_says_which_part(tmp_path):
    """The record of BRAND-STATE.md carries the part and the hash of its canonical text; the other inputs stay whole files; inputs_sha includes the part name; a record without a part is the whole file."""
    p = state_with_g4(tmp_path)
    rep = hand_report(p)
    mine = [i for i in rep["inputs"] if i["path"] == "BRAND-STATE.md"]
    assert mine == [{"path": "BRAND-STATE.md", "part": "g4-rules", "sha256": mine[0]["sha256"]}] and re.fullmatch(r"[0-9a-f]{64}", mine[0]["sha256"]), rep["inputs"]
    assert mine[0]["sha256"] != sha256_file(p / "BRAND-STATE.md"), "the hash is that of the part, not of the file"
    assert "pages/index.html" in {i["path"] for i in rep["inputs"]} and not [i for i in rep["inputs"] if i["path"] != "BRAND-STATE.md" and "part" in i], "every other input is a whole file"
    assert Report.inputs_sha(rep["inputs"]) == rep["inputs_sha"]
    renamed = [{**i, "part": "other-part"} if "part" in i else i for i in rep["inputs"]]
    assert Report.inputs_sha(renamed) != rep["inputs_sha"], "the part name is in inputs_sha"
    whole = [i for i in hand_report(p, whole=True)["inputs"] if i["path"] == "BRAND-STATE.md"]
    assert whole == [{"path": "BRAND-STATE.md", "sha256": sha256_file(p / "BRAND-STATE.md")}], "a record without a part is the whole file, as ever"


def test_a_report_held_by_the_g4_rules_stays_current_when_another_line_of_brand_state_changes(tmp_path):
    """The phase, a gate recorded later (G5, G6), a list line and a bullet that is no "(rule)" line change BRAND-STATE.md and leave the report current; so does white space inside a rule line."""
    p = state_with_g4(tmp_path)
    rep = hand_report(p)
    assert stale_inputs(p, rep) == []
    state = p / "BRAND-STATE.md"
    assert bc("state", "--set", "phase=P9", project=p).returncode == 0
    assert stale_inputs(p, rep) == []
    assert bc("state", "--record", "G5", "book approved", project=p).returncode == 0
    assert bc("state", "--record", "G6", "adoption go", project=p).returncode == 0
    assert stale_inputs(p, rep) == []
    mutate(state, "1. (...)", "1. an open question for the owner", count=2)                    # Change list and Still open
    mutate(state, f"- {G4_PART_RULE}", f"- {G4_PART_RULE}\n- a note under the rules that is no rule line")
    assert stale_inputs(p, rep) == []
    mutate(state, G4_PART_RULE, "(rule)   one  mark\tper screen")                               # the same words: white space is not a change
    assert stale_inputs(p, rep) == []
    old = hand_report(p, whole=True)                                                            # a report that lists the whole file does not enjoy this
    assert bc("state", "--set", "phase=P10", project=p).returncode == 0
    assert stale_inputs(p, old) == ["BRAND-STATE.md changed"]
    assert stale_inputs(p, rep) == []


def test_a_report_held_by_the_g4_rules_goes_stale_when_a_rule_line_or_the_g4_record_changes(tmp_path):
    """(m) a "(rule)" line edited, one more line, a line taken away, G4 recorded again; each makes the report stale and the sentence names the part."""
    state = "BRAND-STATE.md"
    changes = {
        "a rule line edited": lambda p: mutate(p / state, "one mark per screen", "two marks per screen"),
        "a rule line added": lambda p: mutate(p / state, f"- {G4_PART_RULE}", f"- {G4_PART_RULE}\n- (rule) no stock photos"),
        "a rule line taken away": lambda p: mutate(p / state, f"- {G4_PART_RULE}", "- (rule) (...)"),
        "the G4 record changed": lambda p: mutate(p / state, "system rules GO", "system rules GO, with a change"),
    }
    for what, change in changes.items():
        p = state_with_g4(tmp_path / what.replace(" ", "-"))
        rep = hand_report(p)
        assert stale_inputs(p, rep) == []
        change(p)
        assert stale_inputs(p, rep) == ["BRAND-STATE.md (the G4 rules) changed"], what
        again = hand_report(p)                                                                  # checked again, the report is current for the new rules
        assert stale_inputs(p, again) == [] and again["inputs_sha"] != rep["inputs_sha"], what
    p = state_with_g4(tmp_path / "recorded-twice")
    rep = hand_report(p)
    assert bc("state", "--record", "G4", "system rules, approved again", project=p).returncode == 0
    assert stale_inputs(p, rep) == ["BRAND-STATE.md (the G4 rules) changed"]
    p = make_project(tmp_path / "before-g4")                                                     # no G4 yet: the rule lines are not read, as page-check does not read them
    rep = hand_report(p)
    mutate(p / state, "- (rule) (...)", f"- {G4_PART_RULE}")
    assert stale_inputs(p, rep) == []
    assert bc("state", "--record", "G4", "system rules GO", project=p).returncode == 0
    assert stale_inputs(p, rep) == ["BRAND-STATE.md (the G4 rules) changed"], "recording G4 makes the rules count"


def test_a_part_that_cannot_be_read_makes_its_input_stale_and_says_why(tmp_path):
    """(m) BRAND-STATE.md that cannot be read, a part this plugin does not know, a part of another file and a part that is no name: stale, with a sentence that says why, never current."""
    p = state_with_g4(tmp_path)
    rep = hand_report(p)
    state = p / "BRAND-STATE.md"
    text = mutate(state, "---\n", "", count=1)                                                  # the opening line of the frontmatter is gone
    got = stale_inputs(p, rep)
    assert len(got) == 1 and got[0].startswith("BRAND-STATE.md (the G4 rules) cannot be read: ") and "has no frontmatter" in got[0], got
    broken = hand_report(p)                                                                     # a report made while it cannot be read is recorded, and reads as stale with the reason
    assert stale_inputs(p, broken) == got
    state.write_text(text, encoding="utf-8")
    assert stale_inputs(p, rep) == [] and stale_inputs(p, broken) == ["BRAND-STATE.md (the G4 rules) changed"], "readable again: the first is current, the one made in the dark is not"
    for part, words in (("no-such-part", "'no-such-part' is not a part this plugin can read (it reads: g4-rules)"), (7, "7 is not a part this plugin can read"), (None, "None is not a part this plugin can read")):
        doc = json.loads(json.dumps(rep))
        next(i for i in doc["inputs"] if i["path"] == "BRAND-STATE.md")["part"] = part
        got = stale_inputs(p, doc)
        assert len(got) == 1 and got[0].startswith("BRAND-STATE.md (") and "cannot be read" in got[0] and words in got[0], (part, got)
    doc = json.loads(json.dumps(rep))
    next(i for i in doc["inputs"] if i["path"] == "pages/index.html")["part"] = "g4-rules"
    got = stale_inputs(p, doc)
    assert got == ["pages/index.html (the G4 rules) cannot be read: 'g4-rules' is a part of BRAND-STATE.md, not of index.html"], got
    state.unlink()
    assert stale_inputs(p, rep) == ["BRAND-STATE.md is gone"], "a part of a file that is gone is gone"


def test_a_word_added_to_the_brief_or_the_cliches_list_makes_a_passing_report_stale(tmp_path):
    p = state_with_g4(tmp_path)
    (p / "brief").mkdir(exist_ok=True)
    (p / "brief" / "BRIEF.md").write_text("# Brief\n\n## Forbidden\n\n- revolutionary\n", encoding="utf-8")
    rep = hand_report(p)
    assert {"brief/BRIEF.md"} <= {i["path"] for i in rep["inputs"]} and "research/cliches.md" not in {i["path"] for i in rep["inputs"]}   # only the files that exist
    assert stale_inputs(p, rep) == []
    with (p / "brief" / "BRIEF.md").open("a", encoding="utf-8") as f:
        f.write("- game-changer\n")
    assert stale_inputs(p, rep) == ["brief/BRIEF.md changed"]
    (p / "research").mkdir(exist_ok=True)
    (p / "research" / "cliches.md").write_text("# Clichés\n\n## Forbidden\n\n- best-in-class\n", encoding="utf-8")
    rep = hand_report(p)
    assert "research/cliches.md" in {i["path"] for i in rep["inputs"]} and stale_inputs(p, rep) == []
    with (p / "research" / "cliches.md").open("a", encoding="utf-8") as f:
        f.write("- cutting-edge\n")
    assert stale_inputs(p, rep) == ["research/cliches.md changed"]


def test_the_docs_say_the_page_check_uses_the_brief_and_cliches_words_only_and_that_they_make_a_report_stale():
    flat = lambda *parts: " ".join(ROOT.joinpath(*parts).read_text(encoding="utf-8").split())
    for text in (flat("scripts", "CONTRACT.md"), flat("CHANGELOG.md"), flat("skills", "brand-creator", "references", "phases", "09-qa.md")):
        assert "lint.forbidden" in text, "the book's own list is named"
    contract = flat("scripts", "CONTRACT.md")
    assert "also applies the book's own `lint.forbidden`; the page check does not" in contract and "are inputs of the report: a change to either makes a `page-check` report stale" in contract
    assert "is not an input of the report" not in contract and "not part of what makes a report go out of date" not in flat("CHANGELOG.md") + flat("docs", "manual", "reference", "page-check.md")
    assert "the list `book-lint` applies" not in flat("skills", "brand-creator", "references", "phases", "09-qa.md") + contract + (ROOT / "scripts" / "page_check.py").read_text(encoding="utf-8")


def tilt(angle: float, by: str = "self", sel: str = "form.signup", tag: str = "form") -> dict:
    """A form or control drawn rotated, as the collector reports it."""
    return {"sel": sel, "tag": tag, "angle": angle, "by": by}


def test_the_tilted_form_threshold_decides_at_its_edge_and_a_capped_list_is_not_verified():
    """No browser: a rotation of 0.1 degrees or more, either way, is a hit; the hit names the element and who turns it; a full list says so."""
    assert next(t for t in pagecheck.load_tells()["tells"] if t["id"] == "tilted-form")["threshold"] == {"min_degrees": 0.1}
    hits = lambda *views: found_tells(*views)["hits"]["tilted-form"]
    assert [len(hits(tell_view(tilts=[tilt(a)]))) for a in (0.05, 0.1, -3, 180)] == [0, 1, 1, 1]
    (h,) = hits(tell_view(tilts=[tilt(-3, by="div.sheet", sel="input.email", tag="input")]))
    assert h["selector"] == "input.email" and "input" in h["text"] and "-3 degrees" in h["text"] and "the transform of div.sheet" in h["text"], h
    (own,) = hits(tell_view(tilts=[tilt(2)]))
    assert "its own transform" in own["text"]
    assert len(hits(tell_view(width=390, tilts=[tilt(2)]), tell_view(tilts=[tilt(2)]))) == 1 and hits(tell_view(width=390, tilts=[tilt(2)]), tell_view(tilts=[tilt(2)]))[0]["widths"] == [390, 1440]
    assert found_tells(tell_view(tilts=[tilt(2)], tilts_capped=True))["unverified"]["tilted-form"] == [pagecheck.TILT_CAP_NOTE]
    assert not found_tells(tell_view(tilts=[]))["unverified"]["tilted-form"]


TILT_STYLE = """  input, button, select { background: var(--color-bg); color: var(--color-text); border: 1px solid var(--color-text); font: inherit; }
  .sheet { width: 400px; padding: 12px; background: var(--color-text); }
  .tilt { transform: rotate(4deg); }
  .turn { rotate: 0.1turn; }
  .flat { transform: none; }
"""


def tilt_check(p: Path, body: str) -> tuple[dict, dict]:
    """page-check at 1440 px, light, of a page whose main holds `body`. -> (the tilted-form row, the view as measured)."""
    write_page(p, PAGE.replace("</style>", TILT_STYLE + "</style>").replace(PAGE[PAGE.index("<main>"):PAGE.index("</main>") + len("</main>")], f"<main>\n<h1>Acme hand tools</h1>\n{body}\n</main>"))
    r = bc("page-check", "pages/index.html", "--widths", "1440", "--schemes", "light", project=p)
    assert r.returncode in (0, 1), r.stdout + r.stderr
    rep = report(p, pagecheck.report_tool("pages/index.html"))
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    return tell_row(rep, "tilted-form"), v


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_form_drawn_rotated_warns_whoever_turns_it_and_an_upright_form_or_a_tilted_picture_does_not(acme):
    # the form sits on a tilted sheet: the form is the one hit, its field and button (turned with it) are not listed again
    row_, v = tilt_check(acme, '<div class="sheet tilt"><form class="signup" action="#"><label>Email <input name="email"></label> <button type="button">Go</button></form></div>')
    assert row_["status"] == "warn" and [leaf(h["selector"]) for h in row_["hits"]] == ["div.sheet.tilt > form.signup"], row_
    assert "4 degrees" in row_["hits"][0]["text"] and "div.sheet" in row_["hits"][0]["text"], row_["hits"]
    assert [t["tag"] for t in v["tell_facts"]["tilts"]] == ["form"] and v["tell_facts"]["tilts"][0]["angle"] == 4
    # a field of an upright form, turned by itself (the `rotate` property, 0.1 turn is 36 degrees), is a hit of its own; so is a lone select
    row_, _ = tilt_check(acme, '<form action="#"><input class="turn" name="a"></form><select class="tilt"><option>One</option></select>')
    assert row_["status"] == "warn" and sorted(leaf(h["selector"], 1) for h in row_["hits"]) == ["input.turn", "select.tilt"], row_
    assert any("36 degrees" in h["text"] and "its own transform" in h["text"] for h in row_["hits"]), row_["hits"]
    # an upright form on an upright sheet, and a tilted picture with no form control in it, are not the tell
    row_, v = tilt_check(acme, '<div class="sheet flat"><form action="#"><input name="a"> <button type="button">Go</button></form></div><div class="sheet tilt"><p>A tilted card with no field.</p><svg width="40" height="40"><rect width="40" height="40"/></svg></div>')
    assert row_["status"] == "pass" and row_["hits"] == [] and v["tell_facts"]["tilts"] == [], row_
    # a button outside a form is not a form control
    row_, _ = tilt_check(acme, '<div class="tilt"><button type="button">Not in a form</button></div>')
    assert row_["status"] == "pass", row_
    # a form turned in 3D (rotate: x, rotateY) or mirrored (scaleX(-1)), by itself or by its sheet, is not measured; a hidden tilted form is not shown
    row_, v = tilt_check(acme, '<form style="rotate: x 30deg" action="#"><input name="a"></form><form style="transform: rotateY(180deg)" action="#"><input name="b"></form>'
                               '<div style="transform: scaleX(-1)"><form action="#"><input name="c"></form></div><form class="tilt" style="display:none" action="#"><input name="d"></form>')
    assert row_["status"] == "pass" and v["tell_facts"]["tilts"] == [], (row_, v["tell_facts"]["tilts"])
    # a skew is not a rotation (skewY would read as one), nor is an uneven scale; a rotation with an even scale is one
    row_, v = tilt_check(acme, '<form style="transform: skewY(6deg)" action="#"><input name="a"></form><form style="transform: scale(2, 1)" action="#"><input name="b"></form>'
                               '<form style="transform: rotate(5deg) scale(1.5)" action="#"><input name="c"></form>')
    assert [t["angle"] for t in v["tell_facts"]["tilts"]] == [5], v["tell_facts"]["tilts"]
    # a 3D transform that turns nothing out of the plane (the perspective(1px) translateZ(0) hack) is read by its in-plane part
    row_, v = tilt_check(acme, '<form style="transform: perspective(1px) translateZ(0) rotate(4deg)" action="#"><input name="a"></form>')
    assert [t["angle"] for t in v["tell_facts"]["tilts"]] == [4], v["tell_facts"]["tilts"]
    # an in-plane turn written with an axis (rotate: z 10deg, or the vector 0 0 1) is measured
    row_, _ = tilt_check(acme, '<form style="rotate: z 10deg" action="#"><input name="a"></form><form style="rotate: 0 0 1 -12deg" action="#"><input name="b"></form>')
    assert row_["status"] == "warn" and len(row_["hits"]) == 2 and any("10 degrees" in h["text"] for h in row_["hits"]) and any("12 degrees" in h["text"] for h in row_["hits"]), row_["hits"]


# ---------------------------------------------------------------- page:first-screen


FOLD_CSS = """  .hero { padding: 0; } .hero h1, .hero p { margin: 8px; }
  .tall { display: block; height: 1200px; background: var(--color-line); }
  .gap { display: none; height: 1000px; }
  @media (max-width: 600px) { .gap { display: block; } }
"""


TALL_IMG = '<img width="1200" height="1200" alt="" src="data:image/svg+xml;utf8,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%271200%27 height=%271200%27%3E%3Crect width=%271200%27 height=%271200%27 fill=%27%23ccc%27/%3E%3C/svg%3E" style="display:block">'


def fold_page(hero: str, body: str = "") -> str:
    return PAGE.replace("</style>", FOLD_CSS + "</style>").replace(PAGE[PAGE.index("<main>"):PAGE.index("</main>") + len("</main>")], f"<main>\n{hero}\n{body}</main>")


def fold_row(p: Path, page: str, *widths: str) -> dict:
    write_page(p, page)
    r = bc("page-check", "pages/index.html", "--widths", ",".join(widths or ("390", "1440")), project=p)
    assert r.returncode in (0, 1, 3), r.stdout + r.stderr
    return row(report(p, pagecheck.report_tool("pages/index.html")), "page:first-screen")


def fold_view(width: int = 1440, scheme: str = "light", height: int = 900, **hero) -> dict:
    base = {"found": True, "sel": "section.hero", "h1_sel": "h1", "h1_text": "Acme hand tools", "h1_bottom": 80, "first_action": {"sel": "a.go", "label": "Start", "bottom": 160},
            "top": 0, "words": 10, "viewport_height": height, "lang": "en", "actions": []}
    v = tell_view(width=width, scheme=scheme, hero={**base, **hero})
    v["viewport"] = {"width": width, "height": height}
    return v


def fold_rows_of(tmp_path: Path, *views: dict) -> dict:
    rep = Report("page-check/x-000000", tmp_path)
    ctx = pagecheck.Ctx(tmp_path, pagecheck.Target("project", "pages/x.html", page="pages/x.html"), [1440], ["light"], qa_rules.DEFAULTS, {})
    pagecheck.first_screen_rows(rep, {"views": list(views)}, ctx)
    return rep.results[0]


def test_the_first_screen_row_judges_the_bottom_edge_against_each_views_own_window_height(tmp_path):
    """No browser: the heading and the first action must end inside the window height of the view (an edge exactly on the fold is inside); each view that falls over is named with its px and what."""
    ok = fold_rows_of(tmp_path, fold_view(h1_bottom=900, first_action={"sel": "a.go", "label": "Start", "bottom": 900}), fold_view(width=390, height=844, h1_bottom=844))
    assert ok["status"] == "pass" and "2 view(s)" in ok["detail"], ok
    only = fold_rows_of(tmp_path, fold_view(first_action=None))
    assert only["status"] == "pass" and "the hero's heading ends inside the first screen in 1 view(s)" in only["detail"], only
    r = fold_rows_of(tmp_path, fold_view(), fold_view(width=390, height=844, first_action={"sel": "a.go", "label": "Start", "bottom": 900.5}, h1_bottom=100))
    assert r["status"] == "warn" and "at 390-light (window 844 px high) the action a.go \"Start\" ends 56.5 px below the fold" in r["detail"] and "1440" not in r["detail"].split("; the first screen")[0], r
    both = fold_rows_of(tmp_path, fold_view(h1_bottom=1500))
    assert both["status"] == "warn" and "the heading h1 \"Acme hand tools\" ends 600 px below the fold" in both["detail"] and both["below_fold"][0]["px_below"] == 600, both


def test_a_view_with_no_window_height_is_named_not_measured_and_does_not_crash(tmp_path):
    v = fold_view(width=390)
    v["viewport"] = {"width": 390}
    del v["tell_facts"]["hero"]["viewport_height"]
    r = fold_rows_of(tmp_path, fold_view(), v)
    assert r["status"] == "warn" and "not measured at 390-light: no window height" in r["detail"], r


def test_the_first_screen_row_is_never_a_pass_for_what_it_did_not_measure(tmp_path):
    nohero = fold_rows_of(tmp_path, fold_view(found=False))
    assert nohero["status"] == "info" and nohero["detail"].startswith("not measured: the page has no hero"), nohero
    assert fold_rows_of(tmp_path)["status"] == "skipped"
    part = fold_rows_of(tmp_path, fold_view(), fold_view(width=390, height=844, found=False))
    assert part["status"] == "warn" and "not measured at 390-light: no shown h1 there" in part["detail"], part
    both = fold_rows_of(tmp_path, fold_view(h1_bottom=1500), fold_view(width=390, height=844, found=False))
    assert both["status"] == "warn" and "below the fold" in both["detail"] and "not measured at 390-light" in both["detail"], both
    noact = fold_rows_of(tmp_path, fold_view(first_action=None))
    assert noact["status"] == "pass" and "only its heading was measured" in noact["detail"] and " and first action" not in noact["detail"], noact
    two = fold_rows_of(tmp_path, fold_view(first_action=None), fold_view(scheme="dark", first_action=None))
    assert "at 1440-light, 1440-dark: only" in two["detail"], two


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_hero_that_fits_the_first_screen_passes(acme):
    got = fold_row(acme, fold_page('<section class="hero"><h1>Acme hand tools</h1><p><a href="#go">Start</a></p></section>'))
    assert got["status"] == "pass" and got["viewport_heights"] == [844, 900], got


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_heading_pushed_below_the_fold_by_a_tall_image_warns_with_the_view_and_the_px(acme):
    got = fold_row(acme, fold_page('<section class="hero">' + TALL_IMG + '<h1>Acme hand tools</h1><p><a href="#go">Start</a></p></section>'))
    assert got["status"] == "warn", got
    hits = {(o["width"], o["what"]) for o in got["below_fold"]}
    assert {(390, "heading"), (390, "action"), (1440, "heading"), (1440, "action")} == hits, got
    h = next(o for o in got["below_fold"] if (o["width"], o["what"]) == (1440, "heading"))
    assert h["px_below"] >= 300 and h["text"] == "Acme hand tools" and "below the fold" in got["detail"], got


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_action_below_the_fold_at_390_only_warns_for_390_and_not_for_1440(acme):
    got = fold_row(acme, fold_page('<section class="hero"><h1>Acme hand tools</h1><span class="gap"></span><p><a href="#go">Start</a></p></section>'))
    assert got["status"] == "warn" and {(o["width"], o["what"]) for o in got["below_fold"]} == {(390, "action")}, got
    assert "at 390-light" in got["detail"] and "at 1440" not in got["detail"], got


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_page_with_no_hero_is_not_measured_and_never_a_pass(acme):
    got = fold_row(acme, PAGE.replace("<h1>Acme hand tools</h1>", "<h2>Acme hand tools</h2>"))
    assert got["status"] == "info" and got["detail"].startswith("not measured: the page has no hero"), got


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_heading_straddling_the_fold_and_the_first_action_among_other_links_are_read_right(acme):
    # 390 is 844 high: the h1 starts inside and ends below
    hero = '<section class="hero"><span class="tall" style="height:790px"></span><h1 style="font-size:48px;margin:0">Acme hand tools</h1><p><a href="#go">Start</a></p></section>'
    got = fold_row(acme, fold_page(hero), "390")
    h = [o for o in got["below_fold"] if o["what"] == "heading"]
    assert got["status"] == "warn" and h and 0 < h[0]["px_below"] < 100, got
    # a nav link and a hidden button before the first shown action are skipped: the real action is below the fold, so taking either of them would pass
    hero2 = ('<section class="hero"><nav><a href="#n">Menu</a></nav><button style="display:none">Ghost</button><h1>Acme hand tools</h1>'
             '<span class="tall"></span><p><a href="#go">Start</a></p></section>')
    got2 = fold_row(acme, fold_page(hero2), "390")
    assert got2["status"] == "warn" and {o["text"] for o in got2["below_fold"] if o["what"] == "action"} == {"Start"}, got2
    # a second action below the fold is not the first
    hero3 = ('<section class="hero"><h1>Acme hand tools</h1><p><a href="#go">Start</a></p><span class="tall"></span><p><a href="#late">Later</a></p></section>')
    got3 = fold_row(acme, fold_page(hero3), "390")
    assert got3["status"] == "pass", got3
    # an icon link with no text and no aria-label is no action, even above the real one
    hero4 = ('<section class="hero"><h1>Acme hand tools</h1><a href="#i" style="display:inline-block;width:20px;height:20px"></a>'
             '<span class="tall"></span><p><a href="#go">Start</a></p></section>')
    got4 = fold_row(acme, fold_page(hero4), "390")
    assert got4["status"] == "warn" and {o["text"] for o in got4["below_fold"] if o["what"] == "action"} == {"Start"}, got4
    # a button that starts above the fold and ends below it is judged by its bottom edge
    hero5 = ('<section class="hero"><h1>Acme hand tools</h1><span class="tall" style="height:730px"></span>'
             '<p><a href="#go" style="display:block;height:90px">Start</a></p></section>')
    got5 = fold_row(acme, fold_page(hero5), "390")
    a = [o for o in got5["below_fold"] if o["what"] == "action"]
    assert got5["status"] == "warn" and a and 0 < a[0]["px_below"] < 90 and not [o for o in got5["below_fold"] if o["what"] == "heading"], got5


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_heading_hidden_at_390_is_named_not_measured_and_never_a_pass(acme):
    page = fold_page('<section class="hero"><h1>Acme hand tools</h1><p><a href="#go">Start</a></p></section>').replace("</style>", "@media (max-width: 600px) { .hero h1 { display: none; } }\n</style>")
    got = fold_row(acme, page)
    assert got["status"] == "warn" and "not measured at 390-light, 390-dark: no shown h1 there" in got["detail"], got


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_hero_title_wrapper_does_not_hide_the_action_below_the_fold(acme):
    """A BEM wrapper named for the hero around the h1 alone is no hero: the action is looked for in the section around it, and a button below the fold warns."""
    page = fold_page('<section class="hero"><div class="hero__title"><h1>Acme hand tools</h1></div><span class="tall"></span><p class="hero__actions"><a href="#go">Start</a></p></section>')
    r = fold_row(acme, page, "390")
    assert r["status"] == "warn" and 'the action' in r["detail"] and '"Start"' in r["detail"] and "below the fold" in r["detail"], r
