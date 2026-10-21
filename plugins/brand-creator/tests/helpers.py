"""Shared helpers for the brand-creator test suite."""
from __future__ import annotations

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


# Off macOS there is no sips: a downscale of a PNG master names the explicit Pillow opt-in, an `emit tauri` its .icns writer.
OFF_MAC_DOWNSCALE = [] if sys.platform == "darwin" else ["--renderer=pillow"]
OFF_MAC_TAURI = [] if sys.platform == "darwin" else ["--renderer", "pillow"]

_FALLBACK = Path(tempfile.mkdtemp(prefix="bc-test-data-"))  # for commands that need a --data value but no dependencies


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


def bc(*args: str, project: Path | None = None, cwd: Path | None = None, env: dict | None = None,
       plugin: Path | None = None, data: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run bin/brand-creator. `plugin` runs a copy of the plugin; `project` adds --project (not for new/setup/prereq)."""
    exe = (plugin or ROOT) / "bin" / "brand-creator"
    full_env = {**os.environ, "BRAND_CREATOR_TODAY": "2026-10-17", **(env or {})}
    cmd = [str(exe)]
    d = data or data_dir() or _FALLBACK
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
        return block.replace("[[fill: Name one]]", name).replace("vote-one", f"vote-{name.lower()}")

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
