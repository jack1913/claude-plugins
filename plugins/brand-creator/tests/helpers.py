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
sys.path.insert(0, str(ROOT / "scripts" / "printlib"))
sys.path.insert(0, str(ROOT / "scripts" / "adaptlib"))


_FALLBACK = Path(tempfile.mkdtemp(prefix="bc-test-data-"))  # for commands that need a --data value but no dependencies


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


def make_r2_board(project: Path) -> Path:
    """Derive a valid round 2 refine board from the round 1 example page."""
    import re
    src = (FIXTURES / "rounds" / "r1" / "board.html").read_text(encoding="utf-8")
    page = src.replace('data-round="1" data-board="pick"', 'data-round="2" data-board="refine"')
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
    out = project / "rounds" / "r2" / "board.html"
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
