"""page-check: the command, its three kinds of target, the measuring path (render.mjs page-measure) and the report.

The Chromium tests carry requires_setup and requires_node; the rest run without a browser (a usage error, the missing tokens or node and the
URL rule are all decided before one starts). The projects of the exit-2 and exit-3 tests are plain `new` projects: those refusals come first."""
import base64
import functools
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from helpers import ROOT, bc, install_fixture, make_project, mutate, mutate_json, path_without, report

sys.path.insert(0, str(ROOT / "scripts" / "pagelib"))
import pagecheck  # noqa: E402
import qa_rules  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import CliError, Report, stale_inputs  # noqa: E402

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Acme</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="../assets/tokens/tokens.css">
<style>
  body { margin: 0; background: var(--color-bg); color: var(--color-text); }
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
  body { background: #f9f7ee; color: #0d1b2d; }
  @media (prefers-color-scheme: dark) { body { background: #0e141d; color: #f0eee7; } }
</style></head>
<body><img src="img/dot.svg" width="32" height="32" alt=""><p>A built page, nothing else.</p></body></html>
"""   # the Acme colours written out: a built site elsewhere does not link the project's tokens.css
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
    assert all(x["status"] == "pass" for x in rep["results"][1:] if x["id"] != "page:mark-file") and row(rep, "page:target")["status"] == "info"
    assert row(rep, "page:mark-file")["status"] == "info" and "no brand mark is shown" in row(rep, "page:mark-file")["detail"]   # a page without a mark says so
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
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.json", "assets/tokens/tokens.css", "qa/rules.json", "FACTS.md", "BRAND-STATE.md"} | set(
        pagecheck.logo_files(acme, qa_rules.load(acme)[0]))   # a site elsewhere is not a project file (the logo files are: a mark is judged against them);
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
    copy = acme / "pages" / "mark-copy.svg"   # a copy of the master the page uses, named like a mark
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(acme / "assets" / "logo" / "mark.svg", copy)
    write_page(acme, mark_page('<img class="mark" src="mark-copy.svg" width="48" height="48" alt="Acme">'))
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 0, r.stdout + r.stderr
    ok = mark_rows_of(rep)
    assert [x["status"] for x in ok.values()] == ["pass", "pass", "pass"], ok
    assert ok["page:mark-file"]["files"] == ["assets/logo/mark.svg"] and "assets/logo/mark.svg" in ok["page:mark-file"]["detail"]
    mutate(copy, "#007d71", "#007d72")   # one byte of the copy
    r, rep = check_page(acme, "--schemes", "light")
    assert r.returncode == 1, r.stdout + r.stderr
    bad = mark_rows_of(rep)["page:mark-file"]
    assert bad["status"] == "fail" and "none of the logo files of the project" in bad["detail"] and "/pages/mark-copy.svg" in bad["detail"], bad
    assert [(o["selector"], o["kind"], o["found_by"], o["width"], o["scheme"]) for o in bad["offenders"]] == [("body > header > img.mark", "img", "name", 390, "light")]


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
    assert measures["views"][0]["marks"][0]["kind"] == "img"
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
    for name in ("site-logo", "bookmark", "marketing-hero", "siteMark", "lockup", "wordmark-x", "plain", "hidden-logo", "near", "diagonal", "awayfromit"):
        (pages / f"{name}.svg").write_text(dot.replace("r=\"3\"", f'r="{3 + len(name) % 3}"'), encoding="utf-8")   # different bytes for each, none a logo file
    body = """<img id="a" src="site-logo.svg" width="40" height="40" alt="" style="position: absolute; left: 100px; top: 600px">
<img src="near.svg" width="10" height="10" alt="" style="position: absolute; left: 150px; top: 600px">
<img src="diagonal.svg" width="10" height="10" alt="" style="position: absolute; left: 148px; top: 642px">
<img src="awayfromit.svg" width="10" height="10" alt="" style="position: absolute; left: 100px; top: 800px">
<img src="bookmark.svg" width="12" height="12" alt=""><img src="marketing-hero.svg" width="12" height="12" alt=""><img src="siteMark.svg" width="12" height="12" alt="">
<img src="hidden-logo.svg" width="12" height="12" alt="" style="display: none">
<div class="bg" style="width: 20px; height: 20px; background: url(lockup.svg)"></div>
<div class="pseudo"></div>
<a href="#top" data-brand-mark><img src="plain.svg" width="16" height="16" alt=""></a>
<div data-brand-mark>no image</div>"""
    style = ".pseudo::before { content: ''; display: block; width: 12px; height: 12px; background: url(wordmark-x.svg); }\n"
    write_page(acme, PAGE.replace("</style>", style + "</style>").replace("</main>", body + "\n</main>"))
    r, rep = check_page(acme, "--schemes", "light")
    (v,) = json.loads(Path(rep["measures"]).read_text(encoding="utf-8"))["views"]
    got = {(m["kind"], m["url"]): m for m in v["marks"]}
    assert set(got) == {("img", "/pages/site-logo.svg"), ("img", "/pages/siteMark.svg"), ("background", "/pages/lockup.svg"), ("background", "/pages/wordmark-x.svg"),
                        ("img", "/pages/plain.svg"), ("other", None), ("img", "/pages/hidden-logo.svg")}, sorted(got, key=str)   # bookmark and marketing are images; the hidden logo is a mark that is not shown
    hidden = got[("img", "/pages/hidden-logo.svg")]
    assert hidden["visible"] is False and hidden["named"] and not hidden["marked"] and hidden["nearest_px"] is None   # it is reported as not shown, and no neighbour is looked for
    assert {i["url"] for i in v["images"]} >= {"/pages/bookmark.svg", "/pages/marketing-hero.svg", "/pages/near.svg"} and "/pages/hidden-logo.svg" not in {i["url"] for i in v["images"]}
    a = got[("img", "/pages/site-logo.svg")]
    assert a["named"] and not a["marked"] and a["declared"] is None and a["visible"] and a["own"] is True
    assert a["rect"] == {"x": 100, "y": 600, "width": 40, "height": 40}
    assert (a["nearest_px"], a["nearest_sel"]) == (8, "body > main > img:nth-of-type(3)"), a   # the box 8 px right and 2 px under the corner, not the one 10 px to the right
    assert got[("img", "/pages/plain.svg")]["marked"] and got[("img", "/pages/plain.svg")]["declared"] == "" and got[("other", None)]["visible"]
    pseudo = got[("background", "/pages/wordmark-x.svg")]
    assert pseudo["pseudo"] == "::before" and pseudo["rect"] is None and pseudo["height_px"] == 12
    assert got[("background", "/pages/lockup.svg")]["rect"]["width"] == 20


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_marks_collector_stops_at_its_caps_and_says_how_many_there_were(acme):
    pages = acme / "pages"
    pages.mkdir(exist_ok=True)
    for name in ("site-logo", "plain"):
        (pages / f"{name}.svg").write_text(DOT, encoding="utf-8")   # not a logo file, so the marks fail the row and the row names the cut
    body = "".join(f'<img src="site-logo.svg?{n}" width="4" height="4" alt="">' for n in range(105)) + "".join(f'<img src="plain.svg?{n}" width="4" height="4" alt="">' for n in range(305))
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
