"""templates/finish.sh.tpl, filled and run for real: the stage-4 steps (book, book-pdf, emit print, emit presskit, emit social --posts) and the stage-5
packs (profiles) in the chain of the Standard tier, through to `check`, and the chain of a brand that moves. These two runs are the end-to-end proof;
the chain's own branches (which step runs, what it says, when it stops) are tests/test_finish_chain_steps.py, which runs the same template against a
stand-in for `brand-creator`. The one thing those rely on from the real CLI is tested here: a node tool that wrote its report prints `report: <path>`.

The Acme smoke runs the Full-tier chain with every emitter on the way (tests/smoke/acme.sh). Here the chain is the Standard tier, with the target list cut to
the cheap emitters (the template's own edit point, block 2)."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, fill_markers, mutate, report

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg, pytest.mark.requires_gs, pytest.mark.requires_pdftotext,
              pytest.mark.timeout(1200)]   # a whole chain per test: about 280 s at most on a laptop under load, more on CI
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


def test_a_brand_that_moves_takes_fresh_stills_before_the_book_in_the_chain(acme, tmp_path):
    fin = prepare(acme, "standard", "web")
    assert bc("book", "--init", project=acme).returncode == 0
    assert fill_markers(acme) > 10
    mutate(acme / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    (acme / "motion" / "motion.json").write_text(json.dumps({"schema": 1, "motion": "on", "signature": {"name": "Press", "description": "The dot presses down two pixels and comes back.", "where": ["app icon"]}}))
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    in_order(out, ["gates", "motion", "shot --motion motion/proof.json", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])      # proved, then the stills: the book reads both
    assert "motion is on: signature Press" in out
    doc = json.loads((acme / "motion/frames/demo-page/frames.json").read_text())
    assert len(doc["frames"]) == 25 and "check: PASS" in out
    assert 'data-motion-demo="demo-page"' in (acme / "book.html").read_text() and "jumps between" not in out and "no stills" not in out      # a smooth replay of the stills the chain took


RAF_MOTION = (("#dot { animation: press 320ms steps(2, end) 1 both; }", "#dot { }"),      # the move is drawn by requestAnimationFrame: the proof cannot step through it
              ("</main>", '</main>\n<script>if (!matchMedia("(prefers-reduced-motion: reduce)").matches) { const t0 = performance.now(), dot = document.getElementById("dot"); '
                          '(function tick(now) { const k = Math.min(1, (now - t0) / 320); dot.style.transform = "translateY(" + Math.round(2 * Math.sin(Math.PI * k)) + "px)"; '
                          'if (k < 1) requestAnimationFrame(tick); })(t0); }</script>'))


def test_a_proof_that_is_not_verified_prints_the_path_of_the_report_it_wrote_which_the_chain_reads(acme):
    """The chain goes on after an exit 3 of `shot --motion` only when it printed `report: <path>` of a file that is there (wrote_report in the template;
    test_finish_chain_steps.py drives that branch with a stand-in that answers so). The real command: a move driven by requestAnimationFrame cannot be
    stepped through, so the proof exits 3 and says which report it wrote, named as the disk spells the proof."""
    for edit in RAF_MOTION:
        mutate(acme / "motion/demo.html", *edit)
    r = bc("shot", "--motion", "motion/proof.json", project=acme)
    assert r.returncode == 3, r.stdout + r.stderr
    printed = [ln.removeprefix("report: ") for ln in r.stdout.splitlines() if ln.startswith("report: ")]
    assert len(printed) == 1 and Path(printed[0]).is_file(), r.stdout
    assert json.loads(Path(printed[0]).read_text())["status"] == "not-verified"


def test_the_chain_takes_stills_only_for_a_brand_that_moves_and_has_a_page_case_to_take_them_of(acme):
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    m = re.search(r"if (python3 -c '.*?') 2>/dev/null; then\n\s+read -r -a FRAMES_OPTS <<< \"\$FRAMES_ARGS\"\n\s+step \"frames motion/proof\.json \$FRAMES_ARGS\"", tpl)
    assert m, "the template has no condition for the frames step"
    def wants() -> bool:
        return subprocess.run(["bash", "-c", m.group(1) + " 2>/dev/null"], cwd=acme).returncode == 0
    spec, on = acme / "motion" / "motion.json", {"schema": 1, "motion": "on", "signature": {"name": "Press", "description": "It presses.", "where": ["app icon"]}}
    assert not wants()                                                                       # no motion.json: motion is not decided, nothing to take
    spec.write_text(json.dumps(on))
    assert wants()                                                                           # on, and the proof has a page case
    spec.write_text(json.dumps({"schema": 1, "motion": "off", "reason": "The owner wants a still brand."}))
    assert not wants()                                                                       # nothing moves
    spec.write_text(json.dumps(on))
    proof = json.loads((acme / "motion/proof.json").read_text())
    (acme / "motion/proof.json").write_text(json.dumps({**proof, "cases": [c for c in proof["cases"] if c["type"] != "page"]}))
    assert not wants()                                                                       # on, but `frames` needs a page that moves the mark
    (acme / "motion/proof.json").write_text("{not json")
    assert not wants()                                                                       # a proof that cannot be read takes nothing (the book step says what is wrong with it)
    (acme / "motion/proof.json").write_text(json.dumps(proof))
    assert wants()


def test_the_template_names_every_step_the_cli_gates_by_tier():
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    body = "\n".join(ln for ln in tpl.splitlines() if not ln.lstrip().startswith("#"))
    assert subprocess.run(["bash", "-n", str(ROOT / "templates/finish.sh.tpl")]).returncode == 0
    assert "TARGETS+=(profiles)" in body and "TARGETS+=(print)" in body and "TARGETS+=(android chrome-ext msix)" in body
    assert 'step "book";' in body and 'step "book-pdf";' in body and 'emit presskit' in body and "print-check" in body and "--posts" in body
    # the emitters, then the gates (the book reads their reports), then the book, the book PDF and the press kit (it holds the PDF), then staleness and check
    order = [body.index(s) for s in ('for t in "${TARGETS[@]}"; do emit_one', 'step "gates"', 'verify-idempotent', 'step "motion"', 'step "shot --motion motion/proof.json"', 'step "frames motion/proof.json $FRAMES_ARGS"', 'step "book";', 'step "book-pdf";',
                                     '"${BC[@]}" emit presskit', "staleness --write")]
    assert order == sorted(order)
    # nothing in the chain writes the owner's chapters
    assert '"${BC[@]}" book --init' not in body
