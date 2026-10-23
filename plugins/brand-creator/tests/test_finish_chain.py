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


def test_a_brand_that_moves_takes_fresh_stills_before_the_book_in_the_chain(acme, tmp_path):
    fin = prepare(acme, "standard", "web")
    assert bc("book", "--init", project=acme).returncode == 0
    assert fill_markers(acme) > 10
    mutate(acme / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    (acme / "motion" / "motion.json").write_text(json.dumps({"schema": 1, "motion": "on", "signature": {"name": "Press", "description": "The dot presses down two pixels and comes back.", "where": ["app icon"]}}))
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    in_order(out, ["gates", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])      # the stills first: the book reads them
    doc = json.loads((acme / "motion/frames/demo-page/frames.json").read_text())
    assert len(doc["frames"]) == 25 and "check: PASS" in out
    assert 'data-motion-demo="demo-page"' in (acme / "book.html").read_text() and "jumps between" not in out and "no stills" not in out      # a smooth replay of the stills the chain took


ON = {"schema": 1, "motion": "on", "signature": {"name": "Press", "description": "The dot presses down two pixels and comes back.", "where": ["app icon"]}}


def moving_brand(acme: Path, tier: str) -> Path:
    """A project at `tier` whose book chapters are filled and whose motion is on (the Acme proof has a page case): the chain of a brand that moves."""
    fin = prepare(acme, tier, "web")
    assert bc("book", "--init", project=acme).returncode == 0
    assert fill_markers(acme) > 3
    mutate(acme / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    (acme / "motion" / "motion.json").write_text(json.dumps(ON))
    return fin


STILLS_LINE = "finish.sh: frames could not take the stills (see above); the book keeps the stills of the last run that worked, if any, and check says why"
NO_MOTION = ("animation: press 320ms steps(2, end) 1 both;", "")      # nothing on the page moves: `frames` has nothing to step through and exits 1


def test_a_page_frames_cannot_step_through_does_not_stop_the_chain_the_book_is_built_without_a_replay_and_check_says_why(acme, tmp_path):
    fin = moving_brand(acme, "standard")
    mutate(acme / "motion/demo.html", *NO_MOTION)
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert out.count(STILLS_LINE) == 1 and "no seekable motion" in out, out[-3000:]                 # one line, after the reason `frames` gave
    in_order(out, ["gates", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])                # and the chain went on: the book, its PDF and the kit
    html = (acme / "book.html").read_text()
    assert "data-motion-demo" not in html and (acme / "book.pdf").is_file() and (acme / "assets/presskit/acme-press-kit.zip").is_file()        # all three were built
    row = next(x for x in report(acme, "check")["results"] if x["id"].startswith("report:frames/"))
    assert row["status"] == "fail" and "frames:demo-page" in row["detail"]                          # check says why
    assert r.returncode == 1 and "check: FAIL" in out


def test_a_page_frames_can_no_longer_step_through_leaves_the_book_the_stills_of_the_last_run_that_worked_with_a_warning(acme, tmp_path):
    fin = moving_brand(acme, "standard")
    assert bc("frames", "motion/proof.json", "--count", "9", project=acme).returncode == 0         # an earlier run that worked
    mutate(acme / "motion/demo.html", *NO_MOTION)                                                   # and then the page lost its motion
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert out.count(STILLS_LINE) == 1, out[-3000:]
    in_order(out, ["gates", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])
    assert 'data-motion-demo="demo-page"' in (acme / "book.html").read_text()                       # the replay of the older stills is in the book ...
    assert "did not pass for demo-page, so its stills may be older than the page" in out            # ... with a warning from the build, so the line above does not say the book has none
    assert r.returncode == 1 and "check: FAIL" in out


def stubbed_frames(tmp_path: Path, code: int) -> str:
    """A PATH on which brand-creator is the real one, except that `frames` stops at once with `code` (3: Chromium cannot run)."""
    d = tmp_path / "stub"
    d.mkdir()
    exe = d / "brand-creator"
    exe.write_text(f'#!/usr/bin/env bash\ncase " $* " in *" frames "*) echo "stub: frames cannot run" >&2; exit {code} ;; esac\nexec "{ROOT / "bin" / "brand-creator"}" "$@"\n')
    exe.chmod(0o755)
    return f"{d}:{ROOT / 'bin'}:{os.environ['PATH']}"


@pytest.mark.parametrize("how, code", [("a strip wider than Chromium writes", 2), ("frames cannot run", 3)])
def test_any_failure_of_frames_but_a_page_it_cannot_step_through_stops_the_chain_with_its_exit_code(acme, tmp_path, how, code):
    fin = moving_brand(acme, "standard")
    env = {}
    if code == 2:
        mutate(acme / "motion/demo.html", "#mark { display: block; width: 64px; height: 64px; }", "#mark { display: block; width: 1400px; height: 64px; }")      # 25 stills of 2800 px: usage error
    else:
        env["PATH"] = stubbed_frames(tmp_path, code)
    r = run(fin, tmp_path, **env)
    out = r.stdout + r.stderr
    assert r.returncode == code, (how, out[-3000:])                                                 # the exit code of `frames`, not the 0 or 1 of a chain that went on
    assert f"finish.sh: frames stopped with exit {code} (see above); check has no failing report to gate, so the chain stops here" in out and STILLS_LINE not in out
    ss = steps(out)
    assert ss[-1] == "frames motion/proof.json --count 25" and "book" not in ss and "check: PASS" not in out, ss                  # nothing after it ran
    assert not (acme / "book.html").exists() and not (acme / "assets/presskit").exists()


def test_frames_args_in_block_2_sets_the_stills_so_a_wide_mark_can_take_fewer_without_editing_the_chain(acme, tmp_path):
    fin = moving_brand(acme, "standard")
    assert 'FRAMES_ARGS="${FRAMES_ARGS:---count 25}"' in fin.read_text()                                  # an option of block 2, like the others
    mutate(acme / "motion/demo.html", "#mark { display: block; width: 64px; height: 64px; }", "#mark { display: block; width: 1400px; height: 64px; }")      # 25 stills do not fit
    r = run(fin, tmp_path, FRAMES_ARGS="--count 20")                                                # 20 of 2800 px do (frames says 23 fit)
    out = r.stdout + r.stderr
    assert "frames motion/proof.json --count 20" in steps(out) and "frames stopped" not in out and STILLS_LINE not in out, out[-3000:]
    assert len(json.loads((acme / "motion/frames/demo-page/frames.json").read_text())["frames"]) == 20


def test_the_quick_chain_takes_no_stills_because_its_book_has_no_motion_chapter(acme, tmp_path):
    fin = moving_brand(acme, "quick")                                                               # motion is on and the proof has a page case: the Standard chain takes stills
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    ss = steps(out)
    assert not any(s.startswith("frames") for s in ss) and "book" in ss and "book-pdf" in ss, ss
    assert not (acme / "motion/frames").exists() and not list((acme / "assets/_checks").glob("frames/*"))
    assert 'data-chapter="motion"' not in (acme / "book.html").read_text() and "check: PASS" in out


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


def test_the_quick_chain_keeps_its_shape_avatar_only_no_press_kit_no_print(acme, tmp_path):
    fin = prepare(acme, "quick", "web")
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    ss = steps(out)
    assert not any(s.startswith(("emit print", "emit presskit", "emit android")) for s in ss), ss
    assert any(s.startswith("emit profiles") for s in ss), ss     # the Quick tier writes the avatar only
    assert sorted(f.name for f in (acme / "assets/profiles").glob("*.png")) == ["avatar-400.png", "avatar-800.png"]
    assert "check: PASS" in out and not (acme / "assets/presskit").exists()


def test_the_template_names_every_step_the_cli_gates_by_tier():
    tpl = (ROOT / "templates/finish.sh.tpl").read_text()
    body = "\n".join(ln for ln in tpl.splitlines() if not ln.lstrip().startswith("#"))
    assert subprocess.run(["bash", "-n", str(ROOT / "templates/finish.sh.tpl")]).returncode == 0
    assert "TARGETS+=(profiles)" in body and "TARGETS+=(print)" in body and "TARGETS+=(android chrome-ext msix)" in body
    assert 'step "book";' in body and 'step "book-pdf";' in body and 'emit presskit' in body and "print-check" in body and "--posts" in body
    # the emitters, then the gates (the book reads their reports), then the book, the book PDF and the press kit (it holds the PDF), then staleness and check
    order = [body.index(s) for s in ('for t in "${TARGETS[@]}"; do emit_one', 'step "gates"', 'verify-idempotent', 'step "frames motion/proof.json $FRAMES_ARGS"', 'step "book";', 'step "book-pdf";',
                                     '"${BC[@]}" emit presskit', "staleness --write")]
    assert order == sorted(order)
    # nothing in the chain writes the owner's chapters
    assert '"${BC[@]}" book --init' not in body
