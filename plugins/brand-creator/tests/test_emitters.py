"""emit web and emit social: structure, stable URLs, fingerprints, idempotence, spec-driven sizes, mutation tests."""
import ast
import json
import re
import shutil
from pathlib import Path

import pytest
from helpers import ROOT, bc, failing, make_project, install_fixture, mutate, mutate_json, report

import specs
from pxio import png_size, read_ico_sizes, read_png

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]
WEB = "assets/web"


def web(p, *extra, **kw):
    return bc("emit", "web", *extra, project=p, **kw)


def social(p, *extra, **kw):
    return bc("emit", "social", "--tagline", "Dependable small-batch tools", *extra, project=p, **kw)


def manifest(p):
    return json.loads((p / "assets" / "manifest.json").read_text())


# ---------------------------------------------------------------- web

def test_web_emits_the_documented_files_at_the_spec_sizes(acme):
    r = web(acme)
    assert r.returncode == 0, r.stdout
    base = acme / WEB
    assert sorted(str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()) == [
        "apple-touch-icon.png", "favicon.ico", "head.html", "icon.svg", "icons/icon-192.png", "icons/icon-512.png",
        "icons/maskable-512.png", "icons/monochrome-512.png", "site.webmanifest"]
    fs = specs.sizes("favicon-set")
    pwa = specs.sizes("pwa-manifest")
    assert read_ico_sizes((base / "favicon.ico").read_bytes()) == [(s, s) for s in fs["ico_layers"]]
    assert png_size((base / "apple-touch-icon.png").read_bytes()) == (fs["apple_touch"],) * 2
    for s in pwa["any"]:
        assert png_size((base / f"icons/icon-{s}.png").read_bytes()) == (s, s)
    assert png_size((base / f"icons/maskable-{pwa['maskable']}.png").read_bytes()) == (pwa["maskable"],) * 2
    assert report(acme, "emit-web")["status"] == "pass"


def test_apple_touch_icon_is_opaque_and_maskable_content_is_inside_the_safe_circle(acme):
    assert web(acme).returncode == 0
    w, h, px = read_png((acme / WEB / "apple-touch-icon.png").read_bytes())
    assert all(px[i] == 255 for i in range(3, len(px), 4))
    mw, mh, mp = read_png((acme / WEB / "icons/maskable-512.png").read_bytes())
    bg = tuple(mp[:3])
    ink = [(i % mw, i // mw) for i in range(mw * mh) if max(abs(mp[i * 4 + c] - bg[c]) for c in range(3)) > 8]
    assert ink
    radius = specs.sizes("pwa-manifest")["maskable_safe_radius"] * mw
    assert max(((x - (mw - 1) / 2) ** 2 + (y - (mh - 1) / 2) ** 2) ** 0.5 for x, y in ink) <= radius + 1.5
    # the plain any-purpose 512 icon is NOT confined to the circle (a separate maskable file exists for that)
    aw, ah, ap = read_png((acme / WEB / "icons/icon-512.png").read_bytes())
    corners = [(0, 0), (aw - 1, 0)]
    assert any(ap[(y * aw + x) * 4 + 3] == 0 for x, y in corners)


def test_icon_svg_switches_with_prefers_color_scheme_and_is_pure_vector(acme):
    assert web(acme).returncode == 0
    svg = (acme / WEB / "icon.svg").read_text()
    assert "prefers-color-scheme:dark" in svg and 'class="bc-l"' in svg and 'class="bc-d"' in svg
    assert "#0d1b2d" in svg and "#f0eee7" in svg  # both artworks
    assert bc("check", project=acme).returncode in (0, 3)  # the generated icon passes mark_lint


def test_head_and_manifest_use_stable_favicon_and_fingerprint_only_referenced_icons(acme):
    assert web(acme).returncode == 0
    head = (acme / WEB / "head.html").read_text()
    assert '<link rel="icon" href="/favicon.ico" sizes="32x32">' in head  # stable URL, no ?v=
    assert re.search(r'href="/icon\.svg\?v=[0-9a-f]{8}"', head)
    assert re.search(r'href="/apple-touch-icon\.png\?v=[0-9a-f]{8}"', head)
    assert re.search(r'href="/site\.webmanifest\?v=[0-9a-f]{8}"', head)
    assert 'content="#f9f7ee" media="(prefers-color-scheme: light)"' in head and 'content="#0e141d" media="(prefers-color-scheme: dark)"' in head
    wm = json.loads((acme / WEB / "site.webmanifest").read_text())
    assert wm["name"] == "Acme" and wm["theme_color"] == "#f9f7ee"
    purposes = [(i["sizes"], i["purpose"]) for i in wm["icons"]]
    assert purposes == [("192x192", "any"), ("512x512", "any"), ("512x512", "maskable"), ("512x512", "monochrome")]
    assert all(re.search(r"\?v=[0-9a-f]{8}$", i["src"]) for i in wm["icons"])
    assert len({i["src"] for i in wm["icons"]}) == 4  # one purpose per file, never combined


def test_second_run_writes_nothing_and_fingerprints_follow_the_bytes(acme):
    assert web(acme).returncode == 0
    files = sorted(p for p in (acme / WEB).rglob("*") if p.is_file())
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    head1 = (acme / WEB / "head.html").read_text()
    r = web(acme)
    assert r.returncode == 0 and "0 written, 9 unchanged" in r.stdout
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    # change the artwork: icon.svg, the touch icon and PWA icons get new fingerprints, favicon.ico keeps its URL
    mutate(acme / "assets/logo/mark.svg", "#007d71", "#b0125a")
    assert web(acme).returncode == 0
    head2 = (acme / WEB / "head.html").read_text()
    assert head1 != head2
    assert re.search(r'href="/favicon\.ico"', head2) and "favicon.ico?" not in head2
    assert re.search(r"icon\.svg\?v=([0-9a-f]{8})", head1).group(1) != re.search(r"icon\.svg\?v=([0-9a-f]{8})", head2).group(1)
    assert manifest(acme)["artefacts"]  # every file is recorded with its hash


def test_unchanged_artwork_keeps_every_fingerprint(acme):
    assert web(acme).returncode == 0
    h1 = (acme / WEB / "head.html").read_text()
    assert web(acme).returncode == 0
    assert (acme / WEB / "head.html").read_text() == h1


def test_manifest_json_lists_artefacts_and_stamps_the_spec_rows(acme):
    assert web(acme).returncode == 0
    m = manifest(acme)
    paths = [a["path"] for a in m["artefacts"]]
    assert paths == sorted(paths) and f"{WEB}/favicon.ico" in paths
    fav = next(a for a in m["artefacts"] if a["path"].endswith("favicon.ico"))
    assert fav["emitter"] == "web" and set(fav["specs"]) == {"favicon-set", "favicon-search"} and len(fav["sha256"]) == 64
    assert set(m["specs"]) == {"favicon-search", "favicon-set", "pwa-manifest"}
    assert m["specs"]["favicon-search"]["status"] == "V" and m["specs"]["favicon-set"]["status"] == "R"
    assert all(set(v) == {"status", "checked", "source_url", "stale"} for v in m["specs"].values())
    r = report(acme, "emit-web")
    assert any(x["id"] == "spec" and "secondary source" in x["detail"] for x in r["results"])  # R rows warn


def test_web_needs_gate_g3_tokens_and_vector_marks(tmp_path):
    p = make_project(tmp_path)
    install_fixture(p)
    r = web(p)
    assert r.returncode == 1 and "G3" in r.stderr
    assert bc("state", "--record", "G3", "ok", project=p).returncode == 0
    r = web(p)
    assert r.returncode == 3 and "brand-creator tokens" in r.stderr  # tokens not built yet
    assert bc("tokens", project=p).returncode == 0
    mutate(p / "assets/logo/mark.svg", "<circle", '<text x="1" y="1">A</text><circle')
    r = web(p)
    assert r.returncode == 1 and "mark_lint" in r.stderr
    assert not (p / WEB).exists()


def test_monochrome_derivation_refuses_complex_art_unless_an_authored_file_is_given(acme):
    svg = acme / "assets/logo/mark.svg"
    mutate(svg, "<path", '<defs><linearGradient id="g"><stop offset="0" stop-color="#000"/></linearGradient></defs><path')
    r = web(acme)
    assert r.returncode == 1 and "icons:monochrome" in failing(report(acme, "emit-web"))
    mono = acme / "assets/logo/mark-mono.svg"
    mono.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M32 6 58 54H6Z" fill="#000"/></svg>')
    r = web(acme, "--svg-mono", "assets/logo/mark-mono.svg")
    assert r.returncode == 0, r.stdout


def test_base_path_prefixes_every_url(acme):
    assert web(acme, "--base-path", "/static/").returncode == 0
    head = (acme / WEB / "head.html").read_text()
    assert 'href="/static/favicon.ico"' in head and 'href="/static/icon.svg?v=' in head
    wm = json.loads((acme / WEB / "site.webmanifest").read_text())
    assert all(i["src"].startswith("/static/icons/") for i in wm["icons"])
    assert web(acme, "--base-path", "relative/").returncode == 2


# ---------------------------------------------------------------- spec-driven sizes (mutation on a copy of the plugin)

def test_changing_a_spec_row_changes_the_output_sizes(acme, plugin_copy):
    path = plugin_copy / "scripts/emitters/platform-specs.json"
    mutate_json(path, lambda d: d["rows"]["favicon-set"]["sizes"].__setitem__("apple_touch", 152))
    mutate_json(path, lambda d: d["rows"]["pwa-manifest"]["sizes"].__setitem__("any", [96, 384]))
    r = web(acme, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert png_size((acme / WEB / "apple-touch-icon.png").read_bytes()) == (152, 152)
    assert png_size((acme / WEB / "icons/icon-96.png").read_bytes()) == (96, 96)
    assert png_size((acme / WEB / "icons/icon-384.png").read_bytes()) == (384, 384)


def test_a_stale_spec_row_warns(acme, plugin_copy):
    mutate_json(plugin_copy / "scripts/emitters/platform-specs.json", lambda d: d["rows"]["pwa-manifest"].__setitem__("checked", "2025-01-01"))
    r = web(acme, plugin=plugin_copy)
    assert r.returncode == 0 and "is stale" in r.stdout
    assert manifest(acme)["specs"]["pwa-manifest"]["stale"] is True


def test_platform_specs_rows_are_complete():
    doc = specs.load()
    assert doc["stale_after_days"] > 0
    for rid, row in doc["rows"].items():
        assert row["status"] in "VRU" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["checked"]) and row["source_url"].startswith("https://"), rid
        assert row["checked"] == "2026-10-17"
    assert {"favicon-search", "favicon-set", "pwa-manifest", "open-graph", "github-social", "readme-header"} <= set(doc["rows"])
    assert doc["rows"]["open-graph"]["sizes"] == {"width": 1200, "height": 630}
    assert doc["rows"]["github-social"]["sizes"] == {"width": 1280, "height": 640}
    assert doc["rows"]["readme-header"]["status"] == "U"


# ---------------------------------------------------------------- social

def _repo_files(p):
    return sorted(f.name for f in (p / "assets/social").glob("*.png") if f.name.startswith(("github-social", "readme-header")))


def test_social_skips_the_github_preview_and_readme_headers_when_no_repository_is_listed(acme):
    """PF-1: a bakery has no GitHub page. The Open Graph card is written; the preview and README headers are skipped with an info row."""
    r = social(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    assert list((acme / "assets/social").glob("og-*.png")) and _repo_files(acme) == []
    rows = {x["id"]: x for x in report(acme, "emit-social")["results"]}
    assert rows["note:repo-images"]["status"] == "info" and "no code repository is listed" in rows["note:repo-images"]["detail"]
    assert not any(k.startswith("file:github") or k.startswith("file:readme") for k in rows)
    assert "github-social" not in json.dumps(manifest(acme))


@pytest.mark.parametrize("where,text", [
    ("brief/BRIEF.md", "# Brief\n\n- Offer: a tool\n- Repository: https://github.com/example-org/example-tool\n"),
    ("brief/BRIEF.md", "# Brief\n\n- Required surfaces: website, favicon set, README header.\n"),
    ("INVENTORY.md", "# inventory\n\n## Targets read\n\n| repo | path | branch |\n|---|---|---|\n| tool-cli | ../tool-cli | main |\n"),
])
def test_social_writes_the_github_preview_and_readme_headers_when_a_repository_is_listed(acme, where, text):
    f = acme / where
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    assert social(acme).returncode == 0
    assert _repo_files(acme) == ["github-social-1280x640.png", "readme-header-dark.png", "readme-header-light.png"]


def test_social_ignores_the_template_placeholders_of_the_inventory_and_forced_no_wins(acme):
    (acme / "INVENTORY.md").write_text("## Targets read\n\n| repo | path | branch or commit read | read on |\n|---|---|---|---|\n| (...) | (...) | (...) | YYYY-MM-DD |\n")
    assert social(acme).returncode == 0 and _repo_files(acme) == []
    (acme / "brief").mkdir(exist_ok=True)
    (acme / "brief" / "BRIEF.md").write_text("- Repository: https://github.com/example-org/example-tool\n")
    assert social(acme, "--repo-images", "no").returncode == 0 and _repo_files(acme) == []
    assert social(acme).returncode == 0 and len(_repo_files(acme)) == 3

def test_social_images_have_the_spec_sizes_and_the_og_url_follows_the_bytes(acme):
    r = social(acme, "--repo-images", "yes")
    assert r.returncode == 0, r.stdout + r.stderr
    out = acme / "assets/social"
    og = specs.sizes("open-graph")
    ogs = sorted(out.glob("og-*.png"))
    assert len(ogs) == 1 and re.fullmatch(rf"og-{og['width']}x{og['height']}-[0-9a-f]{{8}}\.png", ogs[0].name)
    assert png_size(ogs[0].read_bytes()) == (og["width"], og["height"])
    gh = specs.sizes("github-social")
    assert png_size((out / f"github-social-{gh['width']}x{gh['height']}.png").read_bytes()) == (gh["width"], gh["height"])
    rh = specs.sizes("readme-header")
    for mode in ("light", "dark"):
        assert png_size((out / f"readme-header-{mode}.png").read_bytes()) == (rh["width"], rh["height"])
    # the dark header is really dark and the light one really light
    lw, lh, lp = read_png((out / "readme-header-light.png").read_bytes())
    dw, dh, dp = read_png((out / "readme-header-dark.png").read_bytes())
    assert lp[0] > 200 and dp[0] < 60
    first = ogs[0].name
    assert social(acme).returncode == 0
    assert sorted(p.name for p in out.glob("og-*.png")) == [first]  # same bytes, same URL
    r = social(acme, "--name", "Acme Tools")  # a different card: new bytes, new URL
    assert r.returncode == 0
    names = sorted(p.name for p in out.glob("og-*.png"))
    assert len(names) == 2 and first in names
    assert "superseded" in r.stdout and "removed-<date>" in r.stdout


def test_social_second_run_is_idempotent(acme):
    assert social(acme).returncode == 0
    files = sorted(p for p in (acme / "assets/social").glob("*.png"))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    r = social(acme)
    assert r.returncode == 0 and "0 written" in r.stdout
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}


def test_site_url_writes_absolute_meta_tags(acme):
    assert social(acme).returncode == 0
    assert not (acme / "assets/social/og-meta.html").exists()
    assert social(acme, "--site-url", "https://example.invalid/").returncode == 0
    meta = (acme / "assets/social/og-meta.html").read_text()
    og = next((acme / "assets/social").glob("og-*.png")).name
    assert f'<meta property="og:image" content="https://example.invalid/{og}">' in meta
    assert 'content="1200"' in meta and 'content="630"' in meta
    assert social(acme, "--site-url", "ftp://nope").returncode == 2


def test_social_needs_g3_tokens_and_a_complete_template(tmp_path, acme):
    (tmp_path / "x").mkdir()
    p = make_project(tmp_path / "x")
    install_fixture(p)
    r = social(p)
    assert r.returncode == 1 and "G3" in r.stderr
    bad = tmp_path / "bad-card.html"
    bad.write_text("<p>{{name}} {{unknown}}</p>")
    r = social(acme, "--template", str(bad))
    assert r.returncode == 1 and "unfilled placeholders" in r.stderr and "unknown" in r.stderr
    assert social(acme, "--template", str(tmp_path / "missing.html")).returncode == 2


def test_social_card_output_is_html_escaped(acme):
    r = social(acme, "--name", "<script>alert(1)</script> & Co")
    assert r.returncode == 0
    html = (acme / "assets/social/_build/og.html").read_text()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_social_emits_nothing_when_the_renderer_is_missing(acme, tmp_path):
    r = social(acme, data=tmp_path / "nosetup")
    assert r.returncode == 3 and "setup" in r.stderr
    assert not list((acme / "assets/social").glob("og-*.png"))


# ---------------------------------------------------------------- static: no literal pixel sizes in emitters

def _spec_numbers():
    doc = json.loads((ROOT / "scripts/emitters/platform-specs.json").read_text())
    nums = set()

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            nums.add(x)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    for row in doc["rows"].values():
        walk(row["sizes"])
    # whole numbers below 8 are scale factors, counts and indices (2x, 3 layers), not pixel sizes: they appear in code for other reasons
    return {n for n in nums if not (isinstance(n, int) and n < 8)}


EMITTER_FILES = ["web.py", "social.py", "_emit.py", "manifest.py", "specs.py", "apple.py", "windows.py", "linux.py", "tray.py", "tauri.py", "wallet.py",
                 "developer.py", "print.py", "presskit.py", "android.py", "chrome_ext.py", "msix.py", "tierb.py", "profiles.py"]


@pytest.mark.parametrize("name", EMITTER_FILES)
def test_emitters_contain_no_literal_sizes_from_the_spec_table(name):
    nums = _spec_numbers()
    assert {192, 512, 1200, 630, 1280, 640, 320, 180, 48} <= nums
    tree = ast.parse((ROOT / "scripts/emitters" / name).read_text())
    # a constant named ..._S is a duration in seconds (a timeout), not a pixel size that happens to equal one
    seconds = {id(a.value) for a in ast.walk(tree) if isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id.endswith("_S") for t in a.targets)}
    hits = [(n.lineno, n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant) and not isinstance(n.value, bool)
            and isinstance(n.value, (int, float)) and n.value in nums and id(n) not in seconds]
    assert hits == [], f"{name} hard-codes sizes that belong in platform-specs.json: {hits}"
    text = (ROOT / "scripts/emitters" / name).read_text()
    assert not re.search(r"\b\d{2,4}x\d{2,4}\b", text), f"{name} contains a literal WxH size"
