"""`brand-creator inline`: one self-contained copy of a try-out page, to be shown as a private page. Every refusal comes before anything is written, so these tests need no browser;
the one that compares the first screen of the page and of its copy needs Chromium (a set-up data directory)."""
import base64
import re
import shutil
from pathlib import Path

import pytest
import sitedata
from helpers import FIXTURES, TEST_FONT, bc, make_project, symlink_or_skip

LOGO = FIXTURES / "assets" / "logo" / "mark.svg"
# a 1 x 1 PNG, and a second one that differs: two files whose bytes tell the two apart
PNG_A = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=")
PNG_B = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
TOKENS = ":root{--color-bg:#f9f7ee;--color-text:#0d1b2d;--font-sans:ui-sans-serif,system-ui,sans-serif}\n"


def project(tmp_path: Path) -> Path:
    """A brand project with tokens.css, the Acme mark and a font where a try-out's paths lead, and no browser needed."""
    p = make_project(tmp_path)
    for rel, data in (("assets/tokens/tokens.css", TOKENS.encode()), ("assets/logo/mark.svg", LOGO.read_bytes()), ("assets/fonts/TestFont-subset.ttf", TEST_FONT.read_bytes())):
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    return p


def put(p: Path, rel: str, content: str | bytes) -> str:
    f = p / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return rel


def tryout(p: Path, head: str = "", body: str = "<h1>Atlas</h1>", name: str = "Atlas", extra: dict | None = None) -> str:
    for rel, content in (extra or {}).items():
        put(p, f"tryout/{name}/{rel}", content)
    return put(p, f"tryout/{name}/index.html",
               f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{name}</title>{head}</head><body>{body}</body></html>')


def files(p: Path) -> list[str]:
    return sorted(str(f.relative_to(p)) for f in p.rglob("*") if f.is_file())


def data_urls(text: str) -> list[bytes]:
    """The bytes every base64 data: URL of a text holds."""
    return [base64.b64decode(m.group(1)) for m in re.finditer(r"data:[\w/+.-]+;base64,([A-Za-z0-9+/=]+)", text)]


def share(p: Path, page: str, out: Path):
    return bc("inline", page, "--out", str(out), project=p)


def test_a_page_with_a_stylesheet_a_font_the_logo_and_a_script_becomes_one_file_that_loads_nothing(tmp_path):
    p = project(tmp_path)
    page = tryout(p, head=('<link rel="stylesheet" href="../../assets/tokens/tokens.css"><link rel="stylesheet" href="atlas.css">'
                           '<link rel="icon" href="../../assets/logo/mark.svg">'
                           '<style>@font-face{font-family:"Atlas Test";src:url(../../assets/fonts/TestFont-subset.ttf) format("truetype")}h1{font-family:"Atlas Test",sans-serif}</style>'
                           '<script src="atlas.js" defer></script>'),
                  body='<main><img src="../../assets/logo/mark.svg" alt="Acme" width="48" height="48"><h1>Atlas</h1><p id="p">loading</p></main>',
                  extra={"atlas.css": "body{margin:0;background:var(--color-bg);color:var(--color-text)}", "atlas.js": 'document.getElementById("p").textContent = "ready";'})
    out = tmp_path / "share" / "Atlas.html"
    r = share(p, page, out)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "wrote " in r.stdout and "5 file(s) inlined" in r.stdout and "assets/fonts/TestFont-subset.ttf" in r.stdout, r.stdout
    urls = [u for _, u in sitedata.urls_in(text, "html")]
    assert urls and all(u.startswith("data:") for u in urls), [u[:60] for u in urls if not u.startswith("data:")]     # nothing is named to load but data: URLs
    assert "<link" not in text.replace('<link rel="icon" href="data:', "") and "<script src" not in text and "tokens.css" not in text and "atlas.css" not in text
    assert "--color-bg:#f9f7ee" in text and 'document.getElementById("p").textContent = "ready";' in text
    assert set(data_urls(text)) == {LOGO.read_bytes(), TEST_FONT.read_bytes()}, "the mark and the font are in the file byte for byte"
    assert text.rindex('textContent = "ready"') > text.rindex("<h1>Atlas</h1>"), "a script with defer ran after the page: it goes to the end of the body"
    assert not any("share" in f or f.endswith("Atlas.html") for f in files(p)), "the copy was written outside the project"
    # the same inputs give the same bytes
    again = tmp_path / "share" / "Atlas-again.html"
    assert share(p, page, again).returncode == 0 and again.read_bytes() == out.read_bytes()


@pytest.mark.requires_setup
def test_the_copy_of_a_page_shows_the_same_first_screen_and_asks_the_network_for_nothing(acme, tmp_path):
    """The built tokens, a font, the logo and a deferred script: the first screen of the page and of its copy are the same pixels at 390 and 1440, light and dark, and the browser
    reports one request for the copy (itself), no other website and nothing failed."""
    from helpers import report
    put(acme, "assets/fonts/TestFont-subset.ttf", TEST_FONT.read_bytes())
    page = tryout(acme, head=('<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="../../assets/tokens/tokens.css"><link rel="stylesheet" href="atlas.css">'
                              '<style>@font-face{font-family:"Atlas Test";src:url(../../assets/fonts/TestFont-subset.ttf) format("truetype")}h1{font-family:"Atlas Test",sans-serif}</style>'
                              '<script src="atlas.js" defer></script>'),
                     body='<main><img src="../../assets/logo/mark.svg" alt="Acme" width="48" height="48"><h1>Atlas first screen</h1><p id="p">loading</p></main>',
                     extra={"atlas.css": "body{margin:0;background:var(--color-bg);color:var(--color-text)}main{padding:24px;background:url(../../assets/logo/mark.svg) no-repeat right top / 80px}",
                            "atlas.js": 'document.getElementById("p").textContent = "ready";'})
    copy = acme / "tryout" / "Atlas-share.html"                                   # under tryout/, so shot can open it; the real flow writes it outside the project
    r = share(acme, page, copy)
    assert r.returncode == 0, r.stderr
    shots = {}
    for name, target in (("page", page), ("copy", "tryout/Atlas-share.html")):
        r = bc("shot", target, "--out", str(tmp_path / name), "--dsf", "1", project=acme)
        assert r.returncode == 0, (name, r.stdout, r.stderr)
        rep = report(acme, "shot")
        shots[name] = rep["results"]
        for v in rep["results"]:
            assert v["status"] == "pass" and v["non_local_requests"] == [] and v["failed_local_requests"] == [] and v["console_errors"] == [] and v["broken_images"] == [], v
    assert all(v["local_requests"] == 1 for v in shots["copy"]), "the copy asks for itself and for nothing else"
    assert all(v["local_requests"] > 4 for v in shots["page"]), "the page it was made from asks for its files"
    for view in ("390-light", "390-dark", "1440-light", "1440-dark"):
        a, b = (tmp_path / "page" / f"{view}-00.png").read_bytes(), (tmp_path / "copy" / f"{view}-00.png").read_bytes()
        assert a == b, f"the first screen differs at {view}"


def test_a_stylesheet_is_read_from_its_own_folder_and_an_import_is_inlined_in_place(tmp_path):
    p = project(tmp_path)
    page = tryout(p, head='<link rel="stylesheet" href="css/site.css" media="screen and (min-width: 1px)">', body='<p class="a b">x</p>',
                  extra={"css/site.css": '@charset "utf-8";\n@import "part.css";\n.a{background:url(../img/a.png)}\n',
                         "css/part.css": '/* a comment that names </style> */\n.b{background:url("../img/b.svg#x")}\n',
                         "img/a.png": PNG_A, "img/b.svg": LOGO.read_bytes()})
    out = tmp_path / "out.html"
    r = share(p, page, out)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert '<style media="screen and (min-width: 1px)">/* a comment that names <\\/style> */\n.b{background:url("data:image/svg+xml;base64,' in text and '#x")}' in text, "the import sits where it was, with its own folder's paths"
    assert text.index(".b{background") < text.index(".a{background"), "the imported sheet comes before the rules of the sheet that imported it"
    assert "@charset" not in text and "@import" not in text and "../img" not in text and "part.css" not in text
    assert text.count("</style>") == 1 and "names <\\/style>" in text, "the text of a style never ends it"
    assert set(data_urls(text)) == {PNG_A, LOGO.read_bytes()}


def test_every_place_a_page_loads_a_file_from_becomes_a_data_url_and_a_link_is_left_alone(tmp_path):
    p = project(tmp_path)
    head = ('<link rel="icon" href="icon.png"><link rel="apple-touch-icon" href=\'icon.png\'><link rel="preload" href="icon.png" as="image">'
            '<link rel="canonical" href="https://example.invalid/atlas">')
    body = ('<img src=icon.png alt=x><img srcset="icon.png 1x, big.png 2x" src="icon.png" alt="">'
            '<picture><source srcset="big.png" media="(min-width: 600px)"><img src="icon.png" alt=""></picture>'
            '<div style="background-image:url(\'icon.png\')">x</div><video poster="icon.png"></video>'
            '<svg width="10" height="10"><image href="big.png" width="10" height="10"/></svg><object data="logo.svg" type="image/svg+xml"></object>'
            '<a href="other.html">other</a> <a href="https://example.invalid/">out</a>')
    page = tryout(p, head=head, body=body, extra={"icon.png": PNG_A, "big.png": PNG_B, "logo.svg": LOGO.read_bytes()})
    out = tmp_path / "out.html"
    r = share(p, page, out)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert set(data_urls(text)) == {PNG_A, PNG_B, LOGO.read_bytes()}
    assert not re.search(r"""(?:src|srcset|poster|data|href)=["']?(?:icon|big|logo)""", text), "no relative file is left"
    assert '<link rel="preload"' not in text, "a hint to preload is dropped"
    assert '<a href="other.html">other</a>' in text and '<a href="https://example.invalid/">out</a>' in text and '<link rel="canonical" href="https://example.invalid/atlas">' in text
    assert re.search(r'<img src="data:image/png;base64,[A-Za-z0-9+/=]+" alt=x>', text), "an unquoted value is quoted: a data: URL can end in ="
    assert "(min-width: 600px)" in text and text.count("data:image/png;base64,") >= 8


def test_a_script_is_inlined_safely_and_keeps_its_place_unless_it_was_deferred(tmp_path):
    p = project(tmp_path)
    page = tryout(p, head='<script src="early.js" integrity="sha384-x" crossorigin="anonymous" data-role="early"></script><script src="late.js" defer></script><script type="module" src="mod.js"></script>',
                  body="<p>one</p><script>inline()</script><p>two</p>",
                  extra={"early.js": 'var s = "</script><!-- not a comment";', "late.js": "late();", "mod.js": "const m = 1; export { m };"})
    out = tmp_path / "out.html"
    r = share(p, page, out)
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert '<script data-role="early">var s = "<\\/script><\\!-- not a comment";</script>' in text, text
    assert '<script type="module">const m = 1; export { m };</script>' in text
    assert text.count("</script>") == 4 and "integrity" not in text and "crossorigin" not in text and "<script src" not in text and "<script type=\"module\" src" not in text
    assert text.index('data-role="early"') < text.index("<p>one</p>") < text.index("inline()") < text.index("<p>two</p>") < text.index("late();") < text.index("</body>"), "only the deferred one moved"
    again = tmp_path / "again.html"
    assert share(p, page, again).returncode == 0 and again.read_bytes() == out.read_bytes()


REMOTE = [   # (what, where the markup goes, the markup, the files it names, the URL the refusal must name)
    ("a web font from a stylesheet link", "head", '<link rel="stylesheet" href="https://fonts.example.invalid/css?family=Inter">', {}, "https://fonts.example.invalid/css?family=Inter"),
    ("a font in a style element", "head", '<style>@font-face{font-family:X;src:url(https://cdn.example.invalid/x.woff2)}</style>', {}, "https://cdn.example.invalid/x.woff2"),
    ("a font in a local stylesheet", "head", '<link rel="stylesheet" href="site.css">', {"site.css": "p{color:red}\n@font-face{font-family:X;src:url('https://cdn.example.invalid/y.woff2')}\n"}, "https://cdn.example.invalid/y.woff2"),
    ("an import of another website", "head", '<link rel="stylesheet" href="site.css">', {"site.css": '@import url("https://fonts.example.invalid/z.css");\np{color:red}\n'}, "https://fonts.example.invalid/z.css"),
    ("a script", "head", '<script src="https://cdn.example.invalid/lib.js"></script>', {}, "https://cdn.example.invalid/lib.js"),
    ("a picture with no scheme", "body", '<img src="//cdn.example.invalid/a.png" alt="">', {}, "//cdn.example.invalid/a.png"),
    ("a picture in a srcset", "body", '<img src="a.png" srcset="a.png 1x, https://cdn.example.invalid/b.png 2x" alt="">', {"a.png": PNG_A}, "https://cdn.example.invalid/b.png"),
    ("a background in a style attribute", "body", '<div style="background:url(http://cdn.example.invalid/bg.png)">x</div>', {}, "http://cdn.example.invalid/bg.png"),
    ("a poster", "body", '<video poster="ftp://cdn.example.invalid/p.png"></video>', {}, "ftp://cdn.example.invalid/p.png"),
    ("a preconnect", "head", '<link rel="preconnect" href="https://fonts.example.invalid">', {}, "https://fonts.example.invalid"),
    ("a path that starts with a slash", "body", '<img src="/images/a.png" alt="">', {}, "/images/a.png"),
    ("a scheme that is not data:", "body", '<img src="file:///tmp/a.png" alt="">', {}, "file:///tmp/a.png"),
]


@pytest.mark.parametrize("what,where,markup,extra,url", REMOTE, ids=[r[0] for r in REMOTE])
def test_a_page_that_loads_from_another_website_exits_2_naming_the_url_and_writes_nothing(tmp_path, what, where, markup, extra, url):
    p = project(tmp_path)
    page = tryout(p, head=markup if where == "head" else "", body=markup if where == "body" else "<h1>Atlas</h1>", extra=extra)
    before = files(p)
    out = tmp_path / "share" / "Atlas.html"
    r = share(p, page, out)
    assert r.returncode == 2, (what, r.stdout, r.stderr)
    assert url in r.stderr and "nothing was written" in r.stderr and page in r.stderr, r.stderr
    said = "starts with / and leads to a place on a web server" if url == "/images/a.png" else "uses the file: scheme" if url.startswith("file:") else "is on another website"
    assert said in r.stderr, (what, r.stderr)
    assert not out.exists() and not out.parent.exists() and files(p) == before


# (what, the page's head or body, files it names, the sentence the refusal holds): each is exit 1, with nothing written
UNSUPPORTED = [   # (what, where the markup goes, the markup, the files it names, the sentence the refusal holds)
    ("a file that is not there", "body", "<img src=\"missing.png\" alt=\"\">", {}, "missing.png leads to tryout/Atlas/missing.png, which does not exist"),
    ("a folder", "body", "<img src=\"img\" alt=\"\">", {"img/a.png": PNG_A}, "which is a folder"),
    ("a video", "body", "<video src=\"clip.mp4\"></video>", {"clip.mp4": b"\x00\x00\x00\x18ftypmp42"}, "no type is known for .mp4"),
    ("a manifest", "head", "<link rel=\"manifest\" href=\"site.webmanifest\">", {"site.webmanifest": "{}"}, "no type is known for .webmanifest"),
    ("an import with a condition", "head", "<link rel=\"stylesheet\" href=\"site.css\">", {"site.css": "@import url(part.css) screen;\n", "part.css": "p{color:red}"}, "cannot be inlined: it has a condition"),
    ("a stylesheet that imports itself", "head", "<link rel=\"stylesheet\" href=\"a.css\">", {"a.css": "@import \"b.css\";", "b.css": "@import \"a.css\";"}, "imports itself"),
    ("a module that imports", "head", "<script type=\"module\" src=\"m.js\"></script>", {"m.js": "import { x } from \"./x.js\";\nx();"}, "a module that imports another file"),
    ("a base href", "head", "<base href=\"sub/\">", {}, "a <base href> changes every path"),
    ("a frame of a page", "body", "<iframe src=\"inner.html\"></iframe>", {"inner.html": "<p>x</p>"}, "a page inside the page"),
    ("an SVG use of another file", "body", "<svg><use href=\"sprite.svg#a\"></use></svg>", {"sprite.svg": LOGO.read_bytes()}, "SVG <use>"),
    ("an alternate stylesheet", "head", "<link rel=\"alternate stylesheet\" href=\"dark.css\" title=\"dark\">", {"dark.css": "p{color:red}"}, "alternate stylesheet"),
    ("a stylesheet that is not UTF-8", "head", "<link rel=\"stylesheet\" href=\"site.css\">", {"site.css": b"p{content:'\xff\xfe'}"}, "is not UTF-8 text"),
    # a shared page takes what a page loads as code only from a stylesheet or a script file, and nothing from a hidden file or folder, so a
    # page cannot carry a project file such as BRAND-STATE.md (or a .env) into a copy that is shown to others
    ("a stylesheet that is not a .css file", "head", "<link rel=\"stylesheet\" href=\"../../BRAND-STATE.md\">", {}, "BRAND-STATE.md is not a stylesheet: only a .css file"),
    ("an import of a file that is not .css", "head", "<link rel=\"stylesheet\" href=\"site.css\">", {"site.css": "@import \"notes.txt\";", "notes.txt": "p{color:red}"}, "notes.txt is not a stylesheet: only a .css file"),
    ("a script that is not a .js file", "head", "<script src=\"notes.txt\"></script>", {"notes.txt": "document.title = 1;"}, "notes.txt is not a script: only a .js or .mjs file"),
    ("a hidden file", "head", "<link rel=\"stylesheet\" href=\".private/site.css\">", {".private/site.css": "p{color:red}"}, "a hidden file or folder"),
    ("a picture in a hidden folder", "body", "<img src=\".cache/a.png\" alt=\"\">", {".cache/a.png": PNG_A}, "a hidden file or folder"),
]


@pytest.mark.parametrize("what,where,markup,extra,sentence", UNSUPPORTED, ids=[r[0] for r in UNSUPPORTED])
def test_a_page_with_something_that_cannot_be_inlined_exits_1_and_writes_nothing(tmp_path, what, where, markup, extra, sentence):
    p = project(tmp_path)
    page = tryout(p, head=markup if where == "head" else "", body=markup if where == "body" else "<h1>Atlas</h1>", extra=extra)
    before = files(p)
    out = tmp_path / "share" / "Atlas.html"
    r = share(p, page, out)
    assert r.returncode == 1, (what, r.stdout, r.stderr)
    assert sentence in r.stderr and "nothing was written" in r.stderr and "line" in r.stderr, r.stderr
    assert not out.exists() and files(p) == before


def test_a_file_outside_the_project_and_a_page_outside_it_exit_2(tmp_path):
    p = project(tmp_path)
    (tmp_path / "outside.png").write_bytes(PNG_A)
    page = tryout(p, body='<img src="../../../outside.png" alt="">')
    out = tmp_path / "share" / "Atlas.html"
    r = share(p, page, out)
    assert r.returncode == 2 and "leads outside the project" in r.stderr and not out.exists(), r.stderr
    (tmp_path / "loose.html").write_text("<p>x</p>", encoding="utf-8")
    r = share(p, str(tmp_path / "loose.html"), out)
    assert r.returncode == 2 and "outside the project" in r.stderr and not out.exists(), r.stderr
    # a link inside the project that leads out of it is outside too
    link = p / "tryout" / "Atlas" / "photo.png"
    symlink_or_skip(link, tmp_path / "outside.png")
    r = share(p, tryout(p, body='<img src="photo.png" alt="">'), out)
    assert r.returncode == 2 and "leads outside the project" in r.stderr and not out.exists(), r.stderr


def test_the_copy_goes_outside_the_project_or_under_tryout_and_nowhere_else(tmp_path):
    p = project(tmp_path)
    page = tryout(p, head='<link rel="stylesheet" href="../../assets/tokens/tokens.css">')
    before = {f: (p / f).read_bytes() for f in files(p)}
    for bad in (p / "assets" / "share.html", p / "share.html", p / "rounds" / "r1" / "share.html", p / "removed-2026-11-03" / "share.html", p / "tryoutx" / "share.html"):
        r = share(p, page, bad)
        assert r.returncode == 2 and "must be outside the project, or under tryout/" in r.stderr, (bad, r.stderr)
        assert not bad.exists()
    r = share(p, page, tmp_path / "share" / "copy.txt")
    assert r.returncode == 2 and "must be a .html file" in r.stderr
    r = bc("inline", page, project=p)                                                                  # no --out
    assert r.returncode == 2 and "--out" in r.stderr
    (tmp_path / "folder.html").mkdir()
    assert share(p, page, tmp_path / "folder.html").returncode == 2
    r = share(p, page, p / "tryout" / "Atlas" / "index.html")                                        # under tryout/, but it is the page itself
    assert r.returncode == 2 and "would overwrite" in r.stderr
    assert {f: (p / f).read_bytes() for f in before} == before, "no file of the project was touched by a refusal"
    # a link that leads from tryout/ into the rest of the project is the rest of the project: the file it leads to is judged, never written through
    put(p, "assets/held.html", "held")
    link = p / "tryout" / "Atlas" / "into-assets.html"
    symlink_or_skip(link, p / "assets" / "held.html")
    r = share(p, page, link)
    assert r.returncode == 2 and "must be outside the project, or under tryout/" in r.stderr and (p / "assets" / "held.html").read_text(encoding="utf-8") == "held", r.stderr
    # what is allowed: outside the project, and under tryout/
    assert share(p, page, tmp_path / "share" / "ok.html").returncode == 0
    assert share(p, page, p / "tryout" / "Atlas-share.html").returncode == 0 and (p / "tryout" / "Atlas-share.html").is_file()
    assert (p / "tryout" / "Atlas" / "index.html").read_text(encoding="utf-8").count("tokens.css") == 1, "the page itself is as it was"


def test_inline_takes_a_html_page_of_the_project_only(tmp_path):
    p = project(tmp_path)
    put(p, "tryout/Atlas/notes.txt", "x")
    out = tmp_path / "share" / "Atlas.html"
    for bad in ("tryout/Atlas/notes.txt", "tryout/Atlas/nothing.html", "tryout/Atlas"):
        r = share(p, bad, out)
        assert r.returncode == 2 and "is not a .html file of the project" in r.stderr and not out.exists(), (bad, r.stderr)
    r = bc("inline", "--help")
    assert r.returncode == 0 and "--out" in r.stdout and "self-contained" in r.stdout
