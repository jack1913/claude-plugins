"""templates/finish.sh.tpl, filled and run: the stage-4 steps (book, book-pdf, emit print, emit presskit, emit social --posts) and the stage-5 packs
(profiles; android, chrome-ext and msix at the Full tier) in the chain, each gated by the tier like the CLI, and the whole chain through to `check`.

The Acme smoke runs the Full-tier chain with every emitter on the way (tests/smoke/acme.sh). Here the chain is the Standard tier, with the target list cut to
the cheap emitters (the template's own edit point, block 2) so that the new steps, their order and their gates can be proved in minutes."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, fill_markers, mutate, report

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg, pytest.mark.requires_gs, pytest.mark.requires_pdftotext]
TAG = "a repair guide is in every box"


def prepare(acme: Path, tier: str, targets: str) -> Path:
    """A project with FACTS.md at `tier`, the round-level gates `check` wants, and tools/finish.sh filled from the template with `targets` (no apple line)."""
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    for k, v in (("tier", tier), ("content_languages", "en")):
        assert bc("state", "--set", f"{k}={v}", project=acme).returncode == 0
    for cmd in (("logo-sheet",), ("board-lint", "rounds/r1/board.html"), ("shot", "rounds/r1/board.html")):
        assert bc(*cmd, project=acme).returncode == 0, cmd
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    new, n = re.subn(r"^TARGETS=\(.*\)$", f"TARGETS=({targets})", tpl, flags=re.M)
    assert n == 1 and f"TARGETS=({targets})" in new
    new, n = re.subn(r'^\[ "\$\(uname\)" = Darwin \] && TARGETS\+=\(apple\).*$', "", new, flags=re.M)
    assert n == 1 and "TARGETS+=(apple)" not in new
    fin = acme / "tools" / "finish.sh"
    fin.parent.mkdir(exist_ok=True)
    fin.write_text(new)
    fin.chmod(0o755)
    return fin


def run(fin: Path, tmp_path: Path, **env_extra) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{ROOT / 'bin'}:{os.environ['PATH']}", "BRAND_CREATOR_TODAY": "2026-10-17", "BRAND_CREATOR_DATA": os.environ.get("BRAND_CREATOR_DATA", ""),
           **env_extra}
    env.pop("BRAND_CREATOR_ROOT", None)
    return subprocess.run(["bash", str(fin)], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=1200)


def steps(out: str) -> list[str]:
    return re.findall(r"^== (.+)$", out, re.M)


def in_order(out: str, names: list[str]) -> None:
    ss = steps(out)
    pos = []
    for n in names:
        hits = [i for i, s in enumerate(ss) if s == n or s.startswith(n + " ")]
        assert hits, f"step {n!r} did not run: {ss}"
        pos.append(hits[0])
    assert pos == sorted(pos) and len(set(pos)) == len(pos), dict(zip(names, pos))


def test_the_standard_chain_runs_profiles_print_posts_book_and_press_kit_in_order_through_to_check(acme, tmp_path):
    fin = prepare(acme, "standard", "web social")
    assert bc("book", "--init", project=acme).returncode == 0
    assert fill_markers(acme) > 10
    mutate(acme / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    r = run(fin, tmp_path, TAGLINE=TAG, PRINT_REGION="EU", IMAGE_BASE_URL="https://img.example.com/brand", POST_FACTS="spare parts;repair guide;batch size")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    # the new steps, in the order the chain documents: emitters (profiles and print among them), print-check, the gates, then book, book-pdf and the press kit (the book reads the gates' reports)
    in_order(out, ["tokens", "contrast", "emit web", "emit social", "emit profiles", "emit print", "print-check", "gates", "book", "book-pdf", "emit presskit"])
    assert "check: PASS" in out and "unrecognized arguments" not in out
    # what each step made
    for f in ("assets/profiles/avatar-400.png", "assets/profiles/linkedin-banner-1584x396.png", "assets/social/posts/carousel-4x5-01.png", "assets/social/posts/post-1x1.png",
              "assets/print/business-card-front.rgb-proof.pdf", "book.html", "book.pdf", "assets/presskit/acme-press-kit.zip"):
        assert (acme / f).is_file(), f
    # multi-word options arrived whole: the posts took three FACTS labels (one of them has a space), the print tagline is one argument
    assert (acme / "assets/social/posts/carousel-4x5-05.png").is_file() and not (acme / "assets/social/posts/carousel-4x5-06.png").exists()
    assert "profile-avatar" in json.dumps(json.loads((acme / "assets/manifest.json").read_text())["specs"])
    # the press kit holds the book the chain built just before it
    import zipfile
    names = zipfile.ZipFile(acme / "assets/presskit/acme-press-kit.zip").namelist()
    assert "acme-press-kit/book/book.pdf" in names
    # every gate that exists passed, and the reports of the new steps are in check
    rep = report(acme, "check")
    ids = {x["id"]: x["status"] for x in rep["results"]}
    for k in ("report:emit-profiles", "report:emit-print", "report:print-check", "report:emit-presskit", "report:emit-social", "report:book", "report:book-lint", "report:book-pdf",
              "tierb:labels", "tierb:profiles"):
        assert ids.get(k) == "pass", (k, ids.get(k))
    assert rep["status"] == "pass"
    # the chain is what the owner runs again after every change: a second run must pass too (a book built before the gates would be stale by now)
    r2 = run(fin, tmp_path, TAGLINE=TAG, PRINT_REGION="EU", IMAGE_BASE_URL="https://img.example.com/brand", POST_FACTS="spare parts;repair guide;batch size")
    assert r2.returncode == 0 and "check: PASS" in r2.stdout + r2.stderr, (r2.stdout + r2.stderr)[-3000:]


def test_without_chapters_the_book_is_skipped_loudly_and_the_press_kit_says_it_has_no_book(acme, tmp_path):
    fin = prepare(acme, "standard", "web")
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    assert "== book: skipped (no book/chapters/" in out and "== book-pdf" not in out and "== print-check" not in out and "== emit print" not in out
    in_order(out, ["emit web", "emit profiles", "gates", "book: skipped", "emit presskit"])
    assert not (acme / "book.html").exists() and not (acme / "assets/print").exists()
    import zipfile
    assert "acme-press-kit/book/book.pdf" not in zipfile.ZipFile(acme / "assets/presskit/acme-press-kit.zip").namelist()
    assert "no book PDF in the kit" in json.dumps(report(acme, "emit-presskit"))
    assert "check: PASS" in out


@pytest.mark.parametrize("env", [{"PRINT_REGION": "EU"}, {"POST_FACTS": "spare parts"}])
def test_a_value_for_a_step_the_tier_does_not_allow_stops_the_chain_before_any_step(acme, tmp_path, env):
    fin = prepare(acme, "quick", "web")
    r = run(fin, tmp_path, **env)
    out = r.stdout + r.stderr
    assert r.returncode == 2 and "Standard and Full tier" in out and "state --set tier=standard" in out, out
    assert steps(out) == [] and not (acme / "assets/web").exists()          # not one step ran


def test_the_quick_chain_keeps_its_shape_no_profiles_no_press_kit_no_print(acme, tmp_path):
    fin = prepare(acme, "quick", "web")
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    ss = steps(out)
    assert not any(s.startswith(("emit profiles", "emit print", "emit presskit", "emit android")) for s in ss), ss
    assert "check: PASS" in out and not (acme / "assets/profiles").exists() and not (acme / "assets/presskit").exists()


def test_the_template_names_every_step_the_cli_gates_by_tier():
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    body = "\n".join(ln for ln in tpl.splitlines() if not ln.lstrip().startswith("#"))
    assert subprocess.run(["bash", "-n", str(ROOT / "templates/finish.sh.tpl")]).returncode == 0
    assert "TARGETS+=(profiles)" in body and "TARGETS+=(print)" in body and "TARGETS+=(android chrome-ext msix)" in body
    assert 'step "book";' in body and 'step "book-pdf";' in body and 'emit presskit' in body and "print-check" in body and "--posts" in body
    # the emitters, then the gates (the book reads their reports), then the book, the book PDF and the press kit (it holds the PDF), then staleness and check
    order = [body.index(s) for s in ('for t in "${TARGETS[@]}"; do emit_one', 'step "gates"', 'verify-idempotent', 'step "book";', 'step "book-pdf";', '"${BC[@]}" emit presskit', "staleness --write")]
    assert order == sorted(order)
    # nothing in the chain writes the owner's chapters
    assert '"${BC[@]}" book --init' not in body
