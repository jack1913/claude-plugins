"""page-check: the command, its three kinds of target, the measuring path (render.mjs page-measure) and the report.

The Chromium tests carry requires_setup and requires_node; the rest run without a browser (a usage error, the missing tokens or node and the
URL rule are all decided before one starts). The projects of the exit-2 and exit-3 tests are plain `new` projects: those refusals come first."""
import base64
import functools
import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from helpers import ROOT, TEST_FONT, bc, make_project, mutate, mutate_json, path_without, report

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
    assert all(x["status"] == "pass" for x in rep["results"][1:] if x["id"] != "page:display-size") and row(rep, "page:target")["status"] == "info"
    assert row(rep, "page:display-size")["status"] == "info" and "no font.display token" in row(rep, "page:display-size")["detail"]   # Acme has no display face
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
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.json", "assets/tokens/tokens.css", "qa/rules.json", "FACTS.md", "BRAND-STATE.md"}   # a site elsewhere is not a project file;
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
