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
from helpers import ROOT, bc, make_project, mutate, mutate_json, path_without, report

sys.path.insert(0, str(ROOT / "scripts" / "pagelib"))
import pagecheck  # noqa: E402
import qa_rules  # noqa: E402
from _common import Report, stale_inputs  # noqa: E402

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
<html lang="en"><head><meta charset="utf-8"><title>Built site</title></head>
<body><img src="img/dot.svg" width="32" height="32" alt=""><p>A built page, nothing else.</p></body></html>
"""
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
    assert [x["id"] for x in rep["results"]] == ["page:target", "page:load:390-light", "page:load:390-dark", "page:load:1440-light", "page:load:1440-dark"]
    assert all(x["status"] == "pass" for x in rep["results"][1:]) and row(rep, "page:target")["status"] == "info"
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
    assert rep["widths"] == [420, 800] and [x["id"] for x in rep["results"][1:]] == ["page:load:420-light", "page:load:800-light"]
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
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.json", "qa/rules.json", "FACTS.md", "BRAND-STATE.md"}   # a site elsewhere is not a project file
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
