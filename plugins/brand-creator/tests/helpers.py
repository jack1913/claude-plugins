"""Shared helpers for the brand-creator test suite."""
from __future__ import annotations

import atexit
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "brand-creator"
FIXTURES = ROOT / "skills" / "brand-creator" / "references" / "examples" / "acme"  # the synthetic worked brand
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "emitters"))
sys.path.insert(0, str(ROOT / "scripts" / "booklib"))
sys.path.insert(0, str(ROOT / "scripts" / "boardlib"))
sys.path.insert(0, str(ROOT / "scripts" / "printlib"))
sys.path.insert(0, str(ROOT / "scripts" / "adaptlib"))
sys.path.insert(0, str(ROOT / "scripts" / "pagelib"))


# Off macOS there is no sips: a downscale of a PNG master names the explicit Pillow opt-in, an `emit tauri` its .icns writer.
OFF_MAC_DOWNSCALE = [] if sys.platform == "darwin" else ["--renderer=pillow"]
OFF_MAC_TAURI = [] if sys.platform == "darwin" else ["--renderer", "pillow"]


@functools.cache
def _no_setup_data() -> Path:
    """For commands that need a --data value but no dependencies, when no set-up data directory is given: made on first use, one per
    process, removed when the process exits."""
    d = Path(tempfile.mkdtemp(prefix="bc-test-data-"))
    atexit.register(shutil.rmtree, d, True)
    return d


def path_without(tmp_path: Path, *hidden: str, keep: tuple[str, ...] = ()) -> str:
    """A PATH string that cannot find the tools named in `hidden`: a folder of symlinks to what the brand-creator entry point needs (uv, python3,
    bash and the coreutils it calls) plus `keep`. System folders are NOT put on it: on Linux ripgrep and poppler live in /usr/bin, so a PATH
    made of 'our folder + /usr/bin' would not hide them (only Homebrew's folder keeps them out on a Mac)."""
    d = tmp_path / "pathbin"
    d.mkdir(exist_ok=True)
    for tool in ("uv", "python3", "bash", "sh", "env", "dirname", "readlink", "mkdir", "cat", "uname", "git", *keep):
        found = shutil.which(tool)
        if found and tool not in hidden and not (d / tool).exists():
            (d / tool).symlink_to(found)
    path = str(d)
    for tool in hidden:
        assert shutil.which(tool, path=path) is None, f"precondition: {tool} must be hidden, or the test proves nothing"
    return path


def data_dir() -> Path | None:
    d = os.environ.get("BRAND_CREATOR_DATA", "").strip()
    return Path(d) if d and (Path(d) / "setup.json").is_file() else None


def own_data(given: Path, into: Path) -> Path:
    """Make `into` a data directory of the tests' own and return it: every entry of the set-up data directory `given` (setup.json, the npm
    packages, Chromium) as a symlink, except the folders the tools write while they run (scratch, the names checker's cache), which `into`
    keeps for itself. The tools write scratch output under <data>/scratch, one folder per project path, and the tests make new project paths
    on every run: aimed at a developer's own data directory, they would leave that scratch there for good."""
    for e in given.resolve().iterdir():   # absolute targets: a relative one would be read from `into`
        if e.name not in ("scratch", "cache"):
            (into / e.name).symlink_to(e)
    return into


def android_sdk() -> tuple[Path, Path] | None:
    """(aapt2, android.jar) from the newest build-tools and platform of the Android SDK (ANDROID_HOME, ANDROID_SDK_ROOT, else the default macOS
    and Linux places); None when either is missing."""
    def ver(p: Path) -> tuple:
        return tuple(int(x) for x in p.name.removeprefix("android-").replace("-", ".").split(".") if x.isdigit())
    for root in [os.environ.get("ANDROID_HOME", ""), os.environ.get("ANDROID_SDK_ROOT", ""), str(Path.home() / "Library/Android/sdk"), str(Path.home() / "Android/Sdk")]:
        sdk = Path(root) if root.strip() else None
        if not (sdk and sdk.is_dir()):
            continue
        tools = sorted((p for p in (sdk / "build-tools").glob("*") if (p / "aapt2").is_file()), key=ver)
        jars = sorted((p for p in (sdk / "platforms").glob("android-*") if (p / "android.jar").is_file()), key=ver)
        if tools and jars:
            return tools[-1] / "aapt2", jars[-1] / "android.jar"
    return None


def bc(*args: str, project: Path | None = None, cwd: Path | None = None, env: dict | None = None,
       plugin: Path | None = None, data: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run bin/brand-creator. `plugin` runs a copy of the plugin; `project` adds --project (not for new/setup/prereq)."""
    exe = (plugin or ROOT) / "bin" / "brand-creator"
    full_env = {**os.environ, "BRAND_CREATOR_TODAY": "2026-10-17", **(env or {})}
    cmd = [str(exe)]
    d = data or data_dir() or _no_setup_data()
    cmd += ["--data", str(d)]
    cmd += list(args)
    if project is not None:
        cmd += ["--project", str(project)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=full_env, timeout=timeout)


def report(project: Path, tool: str) -> dict:
    return json.loads((project / "assets" / "_checks" / f"{tool}.json").read_text())


def downscale_report(project: Path, source: str | None = None) -> dict:
    """The downscale report of one master (assets/_checks/downscale/<slug>.json); without `source`, the most recently written one."""
    from _common import downscale_report_tool
    d = project / "assets" / "_checks" / "downscale"
    if source:
        return report(project, downscale_report_tool(source))
    files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime_ns)
    assert files, f"no downscale report under {d}"
    return json.loads(files[-1].read_text())


def failing(rep: dict) -> list[str]:
    return [r["id"] for r in rep["results"] if r["status"] == "fail"]


def mutate(path: Path, old: str, new: str, count: int = 1) -> str:
    """Apply a text mutation and PROVE it applied (a negative test whose mutation did not apply proves nothing)."""
    before = path.read_text(encoding="utf-8")
    assert old in before, f"mutation did not apply: {old!r} not found in {path}"
    after = before.replace(old, new, count)
    assert after != before, f"mutation did not change {path}"
    path.write_text(after, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == after
    return before


def make_project(tmp: Path, slug: str = "acme", tier: str = "quick", name: str = "Acme") -> Path:
    r = bc("new", slug, "--name", name, "--tier", tier, "--root", str(tmp), data=tmp / "data-unused")
    assert r.returncode == 0, r.stderr
    return tmp / slug


def install_fixture(project: Path, *, tokens=True, logo=True, board=True, qa=True) -> None:
    if tokens:
        (project / "tokens").mkdir(exist_ok=True)
        for f in (FIXTURES / "tokens").glob("*.json"):
            shutil.copy2(f, project / "tokens" / f.name)
    if logo:
        (project / "assets" / "logo").mkdir(parents=True, exist_ok=True)
        for f in (FIXTURES / "assets" / "logo").iterdir():
            if f.is_file():
                shutil.copy2(f, project / "assets" / "logo" / f.name)
    if qa:  # the QA examples: rules, state sets, the status glyphs, the motion proof and its demo page
        for sub in ("qa", "motion", "assets/states", "tray", "assets/tray-src"):
            if (FIXTURES / sub).is_dir():
                shutil.copytree(FIXTURES / sub, project / sub, dirs_exist_ok=True)
    if board:
        (project / "rounds" / "r1").mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURES / "rounds" / "r1" / "board.html", project / "rounds" / "r1" / "board.html")
        # round 1 waits for the style pick (G1s); a fixture that builds a round 1 pick board records the owner's skip
        r = bc("state", "--record", "G1s", "skipped by owner", project=project)
        assert r.returncode == 0, r.stderr


def make_r2_board(project: Path, rnd: int = 2) -> Path:
    """Derive a valid refine board from the round 1 example page: round 2, or round `rnd` when a test needs a refine board later on."""
    import re
    src = (FIXTURES / "rounds" / "r1" / "board.html").read_text(encoding="utf-8")
    page = src.replace('data-round="1" data-board="pick"', f'data-round="{rnd}" data-board="refine"')
    # a refine board has one direction, no map, no strategy core, no none-of-these
    for sid in ("positioning-map", "strategy-core", "none-of-these", "weak-points"):
        page, n = re.subn(r'<section class="block" id="[a-z]+" data-section="%s">.*?</section>' % sid, "", page, flags=re.S)
        assert n == 1, sid
    page, n = re.subn(r'<article class="direction" data-section="direction" data-name="(Lantern|Keystone)".*?</article>', "", page, flags=re.S)
    assert n == 2
    extra = '''
  <section class="block" data-section="what-changed"><h2>What changed since the review</h2><p>Compass: the dot moved to the optical centre.</p></section>
  <section class="block" data-section="weak-points"><h2>Weak points</h2><p>At 16 px the dot is two pixels wide.</p></section>
  <section class="block" data-section="losers"><h2>Kept as losers</h2>
    <div data-section="loser" data-name="Lantern"><p data-field="reason">Too soft next to the category's tool marks.</p></div>
    <div data-section="loser" data-name="Keystone"><p data-field="reason">The wedge reads as a bucket at small sizes.</p></div>
  </section>
'''
    marker = '<section class="block" id="directions">'
    assert page.count(marker) == 1
    page = page.replace(marker, extra + marker)
    out = project / "rounds" / f"r{rnd}" / "board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def mutate_json(path: Path, fn) -> None:
    """Apply fn(doc) to a JSON file and prove the document changed."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    before = json.dumps(doc, sort_keys=True)
    fn(doc)
    assert json.dumps(doc, sort_keys=True) != before, f"mutation did not change {path}"
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


TEST_FONT = ROOT / "tests" / "fixtures" / "fonts" / "TestFont-subset.ttf"  # Inter subset, OFL (see the README next to it)


def fonttools(code: str, *args: str) -> subprocess.CompletedProcess:
    """Run a Python snippet with fontTools (the version the scripts pin) in an isolated uv environment; argv follows."""
    return subprocess.run(["uv", "run", "--no-project", "--quiet", "--with", "fonttools==4.62.1", "--with", "brotli==1.1.0",
                           "python", "-I", "-c", code, *args], capture_output=True, text=True, timeout=300)


def font_variant(dst: Path, *, static: bool = False, family: str | None = None, no_licence: bool = False, fs_type: int | None = None) -> Path:
    """A modified copy of the OFL test font, written to dst: a static instance, a renamed family, no licence text, an OS/2 fsType."""
    code = """
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
dst, static, family, no_licence, fs_type = sys.argv[1], sys.argv[2] == "1", sys.argv[3], sys.argv[4] == "1", sys.argv[5]
f = TTFont(sys.argv[6])
if static:
    f = instancer.instantiateVariableFont(f, {"wght": 400, "opsz": 14}, inplace=False)
if family:
    for n in f["name"].names:
        if n.nameID in (1, 4, 16):
            n.string = family
if no_licence:
    f["name"].names = [n for n in f["name"].names if n.nameID not in (0, 13, 14)]
if fs_type != "-":
    f["OS/2"].fsType = int(fs_type)
f.save(dst)
"""
    r = fonttools(code, str(dst), "1" if static else "0", family or "", "1" if no_licence else "0",
                  "-" if fs_type is None else str(fs_type), str(TEST_FONT))
    assert r.returncode == 0, r.stderr
    return dst


def fill_markers(project: Path, text: str = "Acme sample text for this slot.") -> int:
    """Replace every [[fill: ...]] marker of the book's chapter files (a stand-in for the agent writing the chapters)."""
    import re
    n = 0
    for f in sorted((project / "book" / "chapters").glob("*.md")):
        body = f.read_text(encoding="utf-8")
        new, k = re.subn(r"\[\[fill:.*?\]\](?!\])", text, body, flags=re.S)
        if k:
            f.write_text(new, encoding="utf-8")
            n += k
    return n


STYLE_STAND_IN = "Filled in for the test fixture."
STYLE_TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def fill_style_board(template: str, names: tuple[str, ...] = ("Harbor", "Ember", "Quarry", "Meadow")) -> str:
    """The style board template as a finished page that must pass board-lint: the territory article repeated once per name and every
    [[fill: ...]] marker outside an HTML comment replaced with stand-in text (a link, a colour, a tiny inlined image where the
    marker asks for one). The committed copy is tests/fixtures/style-board-filled.html; a test keeps the two in step."""
    import re
    m = re.search(r'      <article class="territory".*?</article>\n', template, re.S)
    assert m, "the template has no territory article"
    first = m.group(0)

    def named(block: str, name: str) -> str:
        return block.replace("[[fill: Name one]]", name)

    more = "".join(named(first, n) for n in names[1:])
    marker = re.search(r"      <!-- \[\[fill: articles for territories two to four.*?-->\n", template, re.S)
    assert marker, "the template has no 'articles for territories two to four' comment"
    page = template.replace(first, named(first, names[0]), 1).replace(marker.group(0), more, 1)
    for word, name in zip(("one", "two", "three", "four"), names):
        page = page.replace(f"[[fill: Name {word}]]", name)

    def stand_in(mm: "re.Match[str]") -> str:
        s = mm.group(0)[len("[[fill:"):-2].strip()
        if s.startswith("language code"):
            return "en"
        if s == "Brand":
            return "Acme"
        if s == "YYYY-MM-DD":
            return "2026-10-17"
        if s.startswith("#hex"):
            return "#3b5b8c"
        if s.startswith("https://"):
            return "https://example.com/reference"
        if s.startswith("data:image"):
            return STYLE_TINY_PNG
        return STYLE_STAND_IN

    out = []
    for piece in re.split(r"(<!--.*?-->)", page, flags=re.S):      # markers inside HTML comments stay as the template wrote them
        out.append(piece if piece.startswith("<!--") else re.sub(r"\[\[fill:.*?\]\](?!\])", stand_in, piece, flags=re.S))
    return "".join(out)


MOTION_STAND_IN = "Filled in for the test fixture."


def fill_motion_board(template: str, names: tuple[str, ...] = ("Settle", "Bounce", "Glide"), *, rnd: int = 2, first: bool = True,
                      statuses: dict | None = None, brand: str = "Acme") -> str:
    """The motion board template as a finished page that must pass board-lint: the variant article repeated once per name and every [[fill: ...]] marker outside an HTML
    comment replaced with stand-in text. `first` is the first motion board of a project, which does without the two blocks a later one needs (What changed, Weak points);
    `statuses` maps a variant name to the proof line of its card (default pass). The folders, the stills and the reports of the variants are the test's to make."""
    import re
    m = re.search(r'      <article class="variant".*?</article>\n', template, re.S)
    assert m, "the template has no variant article"
    block = m.group(0)
    marker = re.search(r"      <!-- \[\[fill: articles for variants two and three.*?-->\n", template, re.S)
    assert marker, "the template has no 'articles for variants two and three' comment"

    def named(b: str, name: str) -> str:
        return b.replace("[[fill: Name one]]", name).replace('data-proof="[[fill: pass or fail]]"', f'data-proof="{(statuses or {}).get(name, "pass")}"')

    page = template.replace(block, named(block, names[0]) if names else "", 1).replace(marker.group(0), "".join(named(block, n) for n in names[1:]), 1)
    for word, name in zip(("one", "two", "three"), names):
        page = page.replace(f"[[fill: Name {word}]]", name)
    if first:   # the first motion board of a project has no earlier board to say what changed since
        for sid in ("what-changed", "weak-points"):
            page, n = re.subn(r'  <!-- OPTIONAL \(required from the second motion board; delete in the first one\) -->\n  <section class="block(?: n)?" id="[a-z]+" data-section="%s">.*?</section>\n\n' % sid, "", page, flags=re.S)
            assert n == 1, sid
        page, n = re.subn(r'      <li><a href="#(?:changed|weak)">[^<]*</a></li><!-- OPTIONAL: delete with its section below \(the first motion board\) -->\n', "", page)
        assert n == 2, "the table of contents lists the two optional sections"

    def stand_in(mm: "re.Match[str]") -> str:
        s = mm.group(0)[len("[[fill:"):-2].strip()
        if s.startswith("language code"):
            return "en"
        return {"Brand": brand, "N": str(rnd), "YYYY-MM-DD": "2026-10-17", "number of stills": "25"}.get(s, MOTION_STAND_IN)

    out = []
    for piece in re.split(r"(<!--.*?-->)", page, flags=re.S):      # markers inside HTML comments stay as the template wrote them
        out.append(piece if piece.startswith("<!--") else re.sub(r"\[\[fill:.*?\]\](?!\])", stand_in, piece, flags=re.S))
    return "".join(out)


def write_site_capture(project: Path, name: str = "example", url: str = "https://example.com/reference", *, picture: str = STYLE_TINY_PNG, date: str = "2026-10-17",
                       final_url: str | None = None) -> Path:
    """research/site-refs/<name>/capture.json as `brand-creator capture --url` writes it (scripts/CONTRACT.md, "capture"), without the pictures: the sha256 of `picture` (a data: URI, the tiny PNG the
    website references board filler inlines by default) is the one of the thumbnail the record lists, so a board that inlines `picture` for `url` is a capture of that address. The 1440 view carries other bytes."""
    import base64
    import hashlib
    thumb = hashlib.sha256(base64.b64decode(picture.split(",", 1)[1])).hexdigest()
    doc = {"schema": 1, "tool": "capture", "source": {"url": url, "final_url": final_url or url, "status": 200, "title": "Example"}, "date": date,
           "views": [{"view": "1440", "width": 1440, "height": 900, "scheme": "light", "file": "1440.png", "sha256": hashlib.sha256(b"1440 of " + url.encode()).hexdigest()},
                     {"view": "390", "width": 390, "height": 844, "scheme": "light", "file": "390.png", "sha256": hashlib.sha256(b"390 of " + url.encode()).hexdigest()}],
           "full": {"file": "1440-full.png", "sha256": hashlib.sha256(b"full of " + url.encode()).hexdigest(), "height": 2725, "cut": False},
           "thumbs": [{"file": "thumb-1440.jpg", "width": 480, "sha256": thumb}, {"file": "thumb-390.jpg", "width": 160, "sha256": hashlib.sha256(b"thumb 390 of " + url.encode()).hexdigest()}]}
    out = project / "research" / "site-refs" / name / "capture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return out


def fill_site_refs_board(template: str, names: tuple[str, ...] = ("Ledger", "Atlas", "Quay", "Harbour"), *, rnd: int = 2, brand: str = "Acme") -> str:
    """The website references board template as a finished page that must pass board-lint: the group article repeated once per name and every [[fill: ...]] marker outside an HTML
    comment replaced with stand-in text (a link, a date, a tiny inlined image where the marker asks for one). The three references of a group are the template's own."""
    import re
    m = re.search(r'      <article class="group".*?</article>\n', template, re.S)
    assert m, "the template has no group article"
    first = m.group(0)
    marker = re.search(r"      <!-- \[\[fill: articles for groups two to four.*?-->\n", template, re.S)
    assert marker, "the template has no 'articles for groups two to four' comment"

    def named(block: str, name: str) -> str:
        return block.replace("[[fill: Name one]]", name)

    page = template.replace(first, named(first, names[0]), 1).replace(marker.group(0), "".join(named(first, n) for n in names[1:]), 1)
    for word, name in zip(("one", "two", "three", "four"), names):
        page = page.replace(f"[[fill: Name {word}]]", name)

    def stand_in(mm: "re.Match[str]") -> str:
        s = mm.group(0)[len("[[fill:"):-2].strip()
        if s.startswith("language code"):
            return "en"
        return {"Brand": brand, "N": str(rnd), "YYYY-MM-DD": "2026-10-17"}.get(s) or (
            "https://example.com/reference" if s.startswith("https://") else STYLE_TINY_PNG if s.startswith("data:image") else STYLE_STAND_IN)

    out = []
    for piece in re.split(r"(<!--.*?-->)", page, flags=re.S):      # markers inside HTML comments stay as the template wrote them
        out.append(piece if piece.startswith("<!--") else re.sub(r"\[\[fill:.*?\]\](?!\])", stand_in, piece, flags=re.S))
    return "".join(out)


SITE_FROM_REFS = "The Ledger group of the references board: its structure and its rhythm, never its look."   # the Takes from line of a card the test did not word: it names a group of the references board


def fill_site_board(template: str, names: tuple[str, ...] = ("Ledger", "Atlas"), *, rnd: int = 2, first: bool = True, stage: str = "hero", checks: dict | None = None,
                    colds: dict | None = None, layouts: dict | None = None, from_refs: dict | None = None, reflex: dict | None = None, brand: str = "Acme",
                    pages: tuple[str, ...] = ("start", "pricing"), hero: str = "Ledger", choices: tuple | None = None) -> str:
    """The site board template as a finished page that must pass board-lint: the variant article repeated once per name and every [[fill: ...]] marker outside an HTML comment replaced with stand-in
    text. `first` is the first board of its stage, which does without the two blocks a later one needs (What changed, Weak points); `stage` is the data-site-stage; `checks` maps a variant name to the
    check line of its card (pass or fail, default pass), `colds` to its cold line (ship or fix, default ship), `layouts` to its layout id (default walkthrough), `from_refs` to its Takes from line
    (default SITE_FROM_REFS) and `reflex` to its reflex line (default "no hits"). The folders, the stills, the reports and the cold reviews of the variants are the test's to make.
    At the pages stage (`stage` "pages") the page cards, the choices and the questions of the pages come from the three comments of the template (see fill_site_pages_board): `pages` are the page ids, `hero`
    the data-hero, `choices` the choice items; `names` is not used."""
    import re
    if stage == "pages":
        return fill_site_pages_board(template, pages, rnd=rnd, first=first, hero=hero, checks=checks, colds=colds, layouts=layouts, from_refs=from_refs, choices=choices, brand=brand)
    m = re.search(r'      <article class="variant".*?</article>\n', template, re.S)
    assert m, "the template has no variant article"
    block = m.group(0)
    marker = re.search(r"      <!-- \[\[fill: articles for variants two and three.*?-->\n", template, re.S)
    assert marker, "the template has no 'articles for variants two and three' comment"

    def named(b: str, name: str) -> str:
        b = b.replace("[[fill: Name one]]", name).replace('data-check="[[fill: pass or fail]]"', f'data-check="{(checks or {}).get(name, "pass")}"')
        b = b.replace("[[fill: layout id]]", (layouts or {}).get(name, "walkthrough"))
        b = re.sub(r'(data-field="from-refs">)\[\[fill:[^\]]*\]\]', lambda mm: mm.group(1) + (from_refs or {}).get(name, SITE_FROM_REFS), b)
        b = re.sub(r'(data-field="reflex">)\[\[fill:[^\]]*\]\]', lambda mm: mm.group(1) + (reflex or {}).get(name, "no hits"), b)
        return re.sub(r"\[\[fill: ship or fix\]\]", (colds or {}).get(name, "ship"), b)

    page = template.replace(block, named(block, names[0]) if names else "", 1).replace(marker.group(0), "".join(named(block, n) for n in names[1:]), 1)
    for word, name in zip(("one", "two", "three"), names):
        page = page.replace(f"[[fill: Name {word}]]", name)
    page = page.replace('data-board="site" data-site-stage="hero"', f'data-board="site" data-site-stage="{stage}"', 1)
    return _finish_site_board(page, first=first, rnd=rnd, brand=brand)


def _finish_site_board(page: str, *, first: bool, rnd: int, brand: str) -> str:
    """The tail of fill_site_board and fill_site_pages_board: the first board of a stage drops What changed and Weak points (and their entries of the table of contents), then every [[fill: ...]] marker
    outside an HTML comment becomes stand-in text."""
    import re
    if first:   # the first board of a stage has no earlier board to say what changed since
        for sid in ("what-changed", "weak-points"):
            page, n = re.subn(r'  <!-- OPTIONAL \(required from the second site board of a stage; delete in the first one\) -->\n  <section class="block(?: n)?" id="[a-z]+" data-section="%s">.*?</section>\n\n' % sid, "", page, flags=re.S)
            assert n == 1, sid
        page, n = re.subn(r'      <li><a href="#(?:changed|weak)">[^<]*</a></li><!-- OPTIONAL: delete with its section below \(the first hero board\) -->\n', "", page)
        assert n == 2, "the table of contents lists the two optional sections"

    def stand_in(mm: "re.Match[str]") -> str:
        s = mm.group(0)[len("[[fill:"):-2].strip()
        if s.startswith("language code"):
            return "en"
        if s.startswith("no hits"):
            return "no hits"
        if s.startswith("every tell page-check found"):
            return "none found"
        return {"Brand": brand, "N": str(rnd), "YYYY-MM-DD": "2026-10-17", "by in-thread or by agent": "by in-thread"}.get(s, MOTION_STAND_IN)

    out = []
    for piece in re.split(r"(<!--.*?-->)", page, flags=re.S):      # markers inside HTML comments stay as the template wrote them
        out.append(piece if piece.startswith("<!--") else re.sub(r"\[\[fill:.*?\]\](?!\])", stand_in, piece, flags=re.S))
    return "".join(out)


SITE_CHOICES = (("c1", "rule", "The stamp appears once per view", "the stamp appears once per view", "start pricing"),
                ("c2", "example", "Pricing sits under the stages", "", "start"))   # (id, tag, text, data-source, data-pages): the first rule is the line DECISIONS.md of the test projects holds


def fill_site_pages_board(template: str, pages: tuple[str, ...] = ("start", "pricing"), *, rnd: int = 3, first: bool = True, hero: str = "Ledger", checks: dict | None = None,
                          colds: dict | None = None, layouts: dict | None = None, from_refs: dict | None = None, choices: tuple | None = None, brand: str = "Acme") -> str:
    """The site board template at the pages stage as a finished page that must pass board-lint: the "variants" section becomes the pages section of the template's second comment (one article per id of
    `pages`), the choices section of its first comment goes in before My call, the questions of its third comment replace question 1, and <body> says data-site-stage="pages" and data-hero. `checks` maps a
    page id to its check line (pass or fail, default pass); `layouts` to its layout id (default walkthrough); `colds` to its cold line (ship or fix): a page not in `colds` has no cold line (it is optional on
    a page); `from_refs` to its Takes from line (default the hero's structure; None leaves the line out); `choices` is a tuple of (id, tag, text, data-source, data-pages or None) like SITE_CHOICES. The folders,
    the stills, the reports and the cold reviews of the pages are the test's to make."""
    import re
    got_choices = re.search(r'  <!-- PAGES STAGE, the choices .*?\n(  <section class="block n" id="choices".*?  </section>)\n  -->\n', template, re.S)
    got_pages = re.search(r'  <!-- PAGES STAGE, the pages .*?\n(  <section class="block n" id="pages".*?  </section>)\n  -->\n', template, re.S)
    got_questions = re.search(r'  <!-- PAGES STAGE, the questions .*?\n(      <li data-section="question" data-n="1">.*?</ol></li>)\n  -->\n', template, re.S)
    assert got_choices and got_pages and got_questions, "the template has no three PAGES STAGE comments"
    block = re.search(r'      <article class="page".*?</article>\n', got_pages.group(1), re.S)
    assert block, "the pages comment has no page article"

    def card(b: str, pid: str) -> str:
        b = b.replace("[[fill: page id]]", pid).replace('data-check="[[fill: pass or fail]]"', f'data-check="{(checks or {}).get(pid, "pass")}"').replace("[[fill: layout id]]", (layouts or {}).get(pid, "walkthrough"))
        text = (from_refs or {}).get(pid, "The structure and the rhythm of the hero, never the look of a reference.")
        if text is None:
            b, n = re.subn(r'          <dt>Takes from</dt><dd data-field="from-refs">.*?</dd>\n', "", b)
            assert n == 1
        else:
            b = re.sub(r'(data-field="from-refs">)\[\[fill:[^\]]*\]\]', lambda mm: mm.group(1) + text, b)
        if pid in (colds or {}):
            b = b.replace('data-cold="[[fill: ship or fix]]"', f'data-cold="{colds[pid]}"').replace("<b>[[fill: ship or fix]]</b>", f"<b>{colds[pid]}</b>")
            b = re.sub(r"\[\[fill: OPTIONAL: its first finding[^\]]*\]\]", "The first screen says what only this brand could say.", b)
        else:
            b, n = re.subn(r'        <p class="cold" data-cold=.*?</p>\n', "", b)
            assert n == 1
        return b

    section = got_pages.group(1).replace(block.group(0), "".join(card(block.group(0), pid) for pid in pages)) + "\n"
    items = "".join(f'      <li data-choice="{c}" data-tag="{t}" data-source="{src}"' + (f' data-pages="{pg}"' if pg is not None else "") + f">{text}</li>\n"
                    for c, t, text, src, pg in (choices if choices is not None else SITE_CHOICES))
    chosen, n = re.subn(r"    <ul>\n.*?    </ul>\n", lambda mm: "    <ul>\n" + items + "    </ul>\n", got_choices.group(1) + "\n", flags=re.S)
    assert n == 1
    page, n = re.subn(r'  <section class="block n" id="variants">.*?</section>\n', lambda mm: section, template, count=1, flags=re.S)
    assert n == 1, "the template has no variants section"
    page = page.replace('<li><a href="#variants">Heroes</a></li>', '<li><a href="#pages">Pages</a></li>', 1).replace("<li><a href=\"#call\">My call</a></li>", '<li><a href="#choices">Choices</a></li><li><a href="#call">My call</a></li>', 1)
    page, n = re.subn(r"(  <!-- With a judge: add data-judge)", lambda mm: chosen + "\n" + mm.group(1), page, count=1)
    assert n == 1
    page, n = re.subn(r'      <li data-section="question" data-n="1" data-lists="variants">.*?</ol></li>\n', lambda mm: got_questions.group(1) + "\n", page, count=1, flags=re.S)
    assert n == 1, "the template has no hero question"
    page = page.replace('data-board="site" data-site-stage="hero"', f'data-board="site" data-site-stage="pages" data-hero="{hero}"', 1)
    return _finish_site_board(page, first=first, rnd=rnd, brand=brand)


SITE_VIEWS = (("1440-light", 1440, 900, "light"), ("1440-dark", 1440, 900, "dark"), ("390-light", 390, 844, "light"), ("390-dark", 390, 844, "dark"))   # the four first screens `capture <page>` takes


def page_check_report(p: Path, page: str, status: str = "pass", tells: tuple[str, ...] = (), also: tuple[str, ...] = ()) -> Path:
    """The report `brand-creator page-check <page>` writes for a page of the project, made by hand so that no browser is needed: group 1's Report class under group 1's name for it
    (pagecheck.report_tool), its inputs the page and the built tokens' stylesheet (and the project files named in `also`: a real report lists BRAND-STATE.md, qa/rules.json and FACTS.md too; "BRAND-STATE.md#g4-rules" is the file by one of its parts, as a real report lists it, plain "BRAND-STATE.md" the whole file, as an older report did), `target` at the top level as page_check.py puts it, one tell:<id> row for each tell of page-tells.json (a
    warning for each id in `tells`, a pass for the others) and, for status "fail", a failing page:load row, for "not-verified" a skipped one. -> the report's path."""
    import _common
    import pagecheck
    assert status in ("pass", "fail", "not-verified"), status
    def listed(spec: str):   # "<file>" or "<file>#<part>"
        name, _, part = spec.partition("#")
        return _common.PartInput(p / name, part) if part else p / name

    rep = _common.Report(pagecheck.report_tool(page), p, [p / page, p / "assets" / "tokens" / "tokens.css", *(listed(f) for f in also)], renderer="chromium")
    rep.add("page:target", "info", "what was checked", detail=f"project page {page}; widths 390; schemes light")
    if status == "fail":
        rep.add("page:load:390-light", "fail", "the page loads without an error", detail="a request to another origin was stopped: https://example.invalid/x.png")
    elif status == "not-verified":
        rep.add("page:load", "skipped", "the page loads without an error", detail="not verified: no view was measured")
    known = [t["id"] for t in pagecheck.load_tells()["tells"]]
    assert set(tells) <= set(known), (tells, known)
    for t in pagecheck.load_tells()["tells"]:
        if t["id"] in tells:
            rep.add(f"tell:{t['id']}", "warn", t["name"], detail=f"1 found: {t['name']} (at 390 px)", tell=t["id"], hits=[{"selector": "h1", "text": "x", "widths": [390]}])
        else:
            rep.add(f"tell:{t['id']}", "pass", t["name"], detail="none found in 1 view(s)", tell=t["id"], hits=[])
    assert rep.status == status, (rep.status, status)
    rep.extra["target"] = {"kind": "project", "page": page, "from": None, "url": None}
    out = rep.write()
    _common._OPEN_REPORTS.remove(rep)   # written by hand, never finished: nothing of the test process is left open
    return out


def capture_record(p: Path, page: str) -> Path:
    """The stills and the record `brand-creator capture <page>` writes beside a page (<the page's folder>/shots/), made by hand so that no browser is needed: the four first-screen stills and the full
    one, each its own bytes, and capture.json in the shape scripts/CONTRACT.md gives it, its inputs the page and the built tokens' stylesheet. -> the path of capture.json."""
    import hashlib
    import json as _json

    from _common import sha256_bytes, sha256_file
    from px_lib import Img

    def picture(name: str, h: int = 8) -> bytes:
        return Img(8, h, "#" + hashlib.sha256(f"{page}|{name}".encode()).hexdigest()[:6]).png()

    shots = (p / page).parent / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    views = []
    for view, width, height, scheme in SITE_VIEWS:
        data = picture(view)
        (shots / f"{view}.png").write_bytes(data)
        views.append({"view": view, "width": width, "height": height, "scheme": scheme, "file": f"{view}.png", "sha256": sha256_bytes(data)})
    full = picture("full", 16)
    (shots / "1440-light-full.png").write_bytes(full)
    inputs = [{"path": x, "sha256": sha256_file(p / x)} for x in sorted((page, "assets/tokens/tokens.css")) if (p / x).is_file()]
    out = shots / "capture.json"
    out.write_text(_json.dumps({"schema": 1, "tool": "capture", "source": {"page": page}, "date": "2026-10-17", "views": views,
                                "full": {"file": "1440-light-full.png", "sha256": sha256_bytes(full), "height": 16, "cut": False}, "inputs": inputs, "problems": []}, indent=2) + "\n", encoding="utf-8")
    return out


def cold_review_record(p: Path, page: str, verdict: str = "ship", *, by: str = "in-thread", findings: tuple[str, ...] = ("The first screen says what only this brand could say.",),
                       leave_out: tuple[str, ...] = (), add: tuple[str, ...] = (), rules: bool = False) -> Path:
    """The cold-review.md a reader of a page's four stills, brief/BRIEF.md and FACTS.md alone leaves beside the page: the verdict first, `by:`, the `inputs:` with the sha256 of each file as it is now, then the
    findings as numbered lines (the prompt fragment of references/prompt-fragments.md, Review). `leave_out` drops listed inputs and `add` lists more files of the project, for a test that breaks the rule;
    `rules` adds the seventh input, the G4 rules part of BRAND-STATE.md as `- BRAND-STATE.md#g4-rules sha256:<hex>`, the sha256 of the part as it is now (what `brand-creator state --part g4-rules` prints).
    Call it after capture_record: the stills must be there. -> the review's path."""
    from _common import part_sha256, sha256_file
    folder = (p / page).parent
    base = folder.relative_to(p).as_posix()
    files = [f for f in [f"{base}/shots/{v}.png" for v in ("1440-light", "1440-dark", "390-light", "390-dark")] + ["brief/BRIEF.md", "FACTS.md"] if f not in leave_out] + list(add)
    listed = [f"- {f} sha256:{sha256_file(p / f)}" for f in files] + ([f"- BRAND-STATE.md#g4-rules sha256:{part_sha256(p / 'BRAND-STATE.md', 'g4-rules')}"] if rules else [])
    body = [f"verdict: {verdict}", f"by: {by}", "inputs:"] + listed + [""] + [f"{i}. {t}" for i, t in enumerate(findings, 1)]
    out = folder / "cold-review.md"
    out.write_text("\n".join(body) + "\n", encoding="utf-8")
    return out


def symlink_or_skip(link: Path, target: Path) -> None:
    """Make a real symbolic link `link` -> `target` (a folder link when the target is a folder). Where the OS cannot make one (Windows without the privilege) the test is skipped, and the skip says so:
    a refusal of symbolic links that did not run is NOT VERIFIED, which is not a pass."""
    import pytest
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"NOT VERIFIED: this OS cannot make a symbolic link here ({type(e).__name__}: {e}), so the symbolic-link refusals did not run")
