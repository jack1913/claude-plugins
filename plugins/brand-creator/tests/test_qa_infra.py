"""snapshot, verify-idempotent (+ the determinism rules), staleness, specs-due, size bands and the QA wiring of `check`.

Generators under test are tiny scripts written into the project by each test; counters live outside assets/ so a second run
really differs. Expected values are worked out by hand (dates, ages, hashes of known content)."""
import hashlib
import json
import os
import shlex
import shutil
import struct
import subprocess
import sys
import textwrap
import zipfile
import zlib
from pathlib import Path

import pytest
from helpers import OFF_MAC_DOWNSCALE, ROOT, bc, failing, make_project, mutate, mutate_json, report

import determinism
import qa_rules
from _common import CliError
from manifest import Manifest
from px_lib import Img

PY = shlex.quote(sys.executable)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def proj(tmp_path):
    p = make_project(tmp_path)
    (p / "assets").mkdir(exist_ok=True)
    return p


def gen(proj: Path, name: str, body: str) -> str:
    """Write tools/<name>.py and return the --cmd string that runs it from the project root."""
    f = proj / "tools" / f"{name}.py"
    f.parent.mkdir(exist_ok=True)
    f.write_text("import sys, pathlib\n"
                 "c = pathlib.Path('_counter'); n = int(c.read_text()) + 1 if c.exists() else 1; c.write_text(str(n))\n"
                 "out = pathlib.Path('assets/gen'); out.mkdir(parents=True, exist_ok=True)\n" + textwrap.dedent(body))
    return f"{PY} tools/{name}.py"


def idem(proj, *cmds, extra=()):
    args = ["verify-idempotent"]
    for c in cmds:
        args += ["--cmd", c]
    return bc(*args, *extra, project=proj)


def rows(proj, tool="idempotence"):
    return {r["id"]: r for r in report(proj, tool)["results"]}


# ================================================================ snapshot

def test_snapshot_take_diff_verify_by_hand_known_hashes(proj, tmp_path):
    (proj / "assets/a.txt").write_text("hello\n")
    r = bc("snapshot", "take", "assets", "--name", "one", "--out", "snaps/one.json", project=proj)
    assert r.returncode == 0, r.stderr
    doc = json.loads((proj / "snaps/one.json").read_text())
    assert doc["count"] == 1 and doc["dirs"][0]["files"]["a.txt"] == hashlib.sha256(b"hello\n").hexdigest()
    assert doc["dirs"][0]["files"]["a.txt"] == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"  # sha256("hello\n")
    r = bc("snapshot", "take", "assets", "--name", "two", "--out", "snaps/two.json", project=proj)
    assert bc("snapshot", "diff", "snaps/one.json", "snaps/two.json", project=proj).returncode == 0
    assert "identical" in bc("snapshot", "verify", "snaps/one.json", project=proj).stdout
    # change, add, remove
    (proj / "assets/a.txt").write_text("hello!\n")
    (proj / "assets/b.txt").write_text("new")
    r = bc("snapshot", "verify", "snaps/one.json", project=proj)
    assert r.returncode == 1 and "1 added, 0 removed, 1 changed" in r.stdout and "changed assets/a.txt" in r.stdout and "added assets/b.txt" in r.stdout
    bc("snapshot", "take", "assets", "--name", "three", "--out", "snaps/three.json", project=proj)
    (proj / "assets/a.txt").unlink()
    bc("snapshot", "take", "assets", "--name", "four", "--out", "snaps/four.json", project=proj)
    r = bc("snapshot", "diff", "snaps/three.json", "snaps/four.json", project=proj)
    assert r.returncode == 1 and "1 removed" in r.stdout and "removed assets/a.txt" in r.stdout
    r = bc("snapshot", "diff", "snaps/three.json", "snaps/four.json", "--ignore", "a.txt", project=proj)
    assert r.returncode == 0  # the glob removes the one difference


def test_a_snapshot_of_a_folder_outside_the_project_leaves_it_untouched(proj, tmp_path):
    target = tmp_path / "adoption-target"
    (target / "sub").mkdir(parents=True)
    (target / "sub/x.css").write_text("a{b:c}")
    (target / "y.html").write_text("<p>")
    (target / ".git").mkdir()
    (target / ".git/config").write_text("ignored")
    (target / "link").symlink_to(target / "y.html")
    before = {str(p.relative_to(target)): sha(p) for p in sorted(target.rglob("*")) if p.is_file() and not p.is_symlink()}
    r = bc("snapshot", "take", str(target), "--name", "pre", "--out", "snaps/pre.json", "--sha-list", "snaps/pre.sha", project=proj)
    assert r.returncode == 0, r.stderr
    after = {str(p.relative_to(target)): sha(p) for p in sorted(target.rglob("*")) if p.is_file() and not p.is_symlink()}
    assert before == after  # read only
    files = json.loads((proj / "snaps/pre.json").read_text())["dirs"][0]["files"]
    assert set(files) == {"sub/x.css", "y.html"}  # no .git, no symlink
    assert (proj / "snaps/pre.sha").read_text().splitlines()[0].endswith("  adoption-target/sub/x.css")
    (target / "y.html").write_text("<p>changed")
    assert bc("snapshot", "verify", "snaps/pre.json", project=proj).returncode == 1  # a safety proof that notices the target moved


def test_snapshot_refuses_outputs_outside_the_project_and_data_dir_and_bad_input(proj, tmp_path):
    (proj / "assets/a.txt").write_text("x")
    r = bc("snapshot", "take", "assets", "--out", str(tmp_path / "elsewhere.json"), project=proj)
    assert r.returncode == 2 and "must be inside the project or under the data directory" in r.stderr
    assert bc("snapshot", "take", "nothing-here", "--out", "s.json", project=proj).returncode == 2
    (proj / "other").mkdir()
    (proj / "other/assets").mkdir()
    r = bc("snapshot", "take", "assets", "other/assets", "--out", "s.json", project=proj)
    assert r.returncode == 2 and "both called assets" in r.stderr
    (proj / "bad.json").write_text("{}")
    assert bc("snapshot", "verify", "bad.json", project=proj).returncode == 2


# ================================================================ determinism rules (library)

def test_fixed_zip_is_byte_stable_sorted_and_passes_the_lint(tmp_path):
    entries = {"b/two.txt": b"2", "a/one.txt": b"1", "c.txt": b"3" * 1000}
    z1, z2 = determinism.fixed_zip(entries), determinism.fixed_zip(dict(reversed(list(entries.items()))))
    assert z1 == z2  # insertion order does not matter
    f = tmp_path / "x.zip"
    f.write_bytes(z1)
    with zipfile.ZipFile(f) as z:
        assert [i.filename for i in z.infolist()] == ["a/one.txt", "b/two.txt", "c.txt"]
        assert {tuple(i.date_time) for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    assert determinism.lint_file(f) == []


def test_the_zip_lint_catches_what_a_plain_zip_does(tmp_path):
    f = tmp_path / "plain.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr(zipfile.ZipInfo("z.txt", date_time=(2026, 10, 17, 9, 30, 0)), "z")
        z.writestr(zipfile.ZipInfo("a.txt", date_time=(2026, 10, 17, 9, 30, 0)), "a")
    probs = determinism.lint_file(f)
    assert any("not sorted" in p for p in probs) and any("real mtime" in p for p in probs)


def png_with(extra: bytes, im=None) -> bytes:
    base = (im or Img(2, 2, "#102030")).png()
    return base[:-12] + extra + base[-12:]  # before IEND


def chunk(t: bytes, d: bytes) -> bytes:
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)


def test_the_png_lint_flags_time_and_date_chunks_but_not_other_text(tmp_path):
    for name, extra, bad in (("time", chunk(b"tIME", struct.pack(">HBBBBB", 2026, 10, 17, 9, 30, 0)), True),
                             ("date", chunk(b"tEXt", b"date:create\x002026-10-17T09:30:00+00:00"), True),
                             ("title", chunk(b"tEXt", b"Title\x00Acme"), False)):
        f = tmp_path / f"{name}.png"
        f.write_bytes(png_with(extra))
        assert bool(determinism.lint_file(f)) is bad, name
    clean = tmp_path / "clean.png"
    clean.write_bytes(Img(2, 2, "#102030").png())
    assert determinism.lint_file(clean) == []  # px_lib writes no ancillary chunk at all


@pytest.mark.requires_magick
def test_magick_adds_date_chunks_by_default_and_the_documented_arguments_remove_them(tmp_path):
    plain, safe = tmp_path / "plain.png", tmp_path / "safe.png"
    subprocess.run(["magick", "-size", "4x4", "xc:#102030", str(plain)], check=True)
    subprocess.run(["magick", "-size", "4x4", "xc:#102030", *determinism.magick_png_args(), str(safe)], check=True)
    assert any("date" in p for p in determinism.lint_file(plain)), "the rule must detect what the real tool writes"
    assert determinism.lint_file(safe) == []
    safe2 = tmp_path / "safe2.png"
    subprocess.run(["magick", "-size", "4x4", "xc:#102030", *determinism.magick_png_args(), str(safe2)], check=True)
    assert sha(safe) == sha(safe2)


@pytest.mark.requires_gs
def test_normalise_pdf_fixes_dates_and_ids_without_breaking_the_file(tmp_path):
    ps = tmp_path / "a.ps"
    ps.write_text("%!PS\n/Helvetica findfont 20 scalefont setfont 20 100 moveto (Acme) show showpage\n")
    pdf = tmp_path / "a.pdf"
    subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dCompatibilityLevel=1.4", "-sDEVICE=pdfwrite", f"-sOutputFile={pdf}", str(ps)], check=True)
    raw = pdf.read_bytes()
    assert determinism.lint_file(pdf), "a fresh Ghostscript PDF carries a real date and an ID"
    fixed = determinism.normalise_pdf(raw)
    assert len(fixed) == len(raw) and determinism.normalise_pdf(fixed) == fixed  # same length (xref stays valid), idempotent
    out = tmp_path / "b.pdf"
    out.write_bytes(fixed)
    assert determinism.lint_file(out) == []
    info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True)
    assert info.returncode == 0 and "Pages:" in info.stdout and "1980" in info.stdout  # still a valid PDF, now dated 1980-01-01
    assert "1980" in next(l for l in info.stdout.splitlines() if l.startswith("CreationDate"))
    ids = [m for m in __import__("re").findall(rb"/ID\s*\[\s*<([0-9A-F]+)>\s*<([0-9A-F]+)>", fixed)[0]]
    assert all(set(i) == {ord("0")} for i in ids)  # the ID is zeroed


@pytest.mark.requires_gs
def test_a_pdf_with_object_streams_is_refused_not_silently_passed(tmp_path):
    """Ghostscript's default output hides its dates in a compressed stream: normalising it would change nothing, so it must say so."""
    ps = tmp_path / "a.ps"
    ps.write_text("%!PS\n/Helvetica findfont 20 scalefont setfont 20 100 moveto (Acme) show showpage\n")
    pdf = tmp_path / "a.pdf"
    subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite", f"-sOutputFile={pdf}", str(ps)], check=True)
    assert b"/ObjStm" in pdf.read_bytes()  # the premise: this Ghostscript compresses its object tables
    with pytest.raises(ValueError, match="compressed object streams"):
        determinism.normalise_pdf(pdf.read_bytes())
    assert any("object streams" in p for p in determinism.lint_file(pdf))


# ================================================================ verify-idempotent

def test_a_deterministic_chain_passes_twice_over(proj):
    cmd = gen(proj, "good", "pathlib.Path('assets/gen/a.txt').write_text('same'); pathlib.Path('assets/gen/b.png').write_bytes(open(sys.argv[1], 'rb').read())\n")
    (proj / "assets/seed.png").write_bytes(Img(3, 3, "#102030").png())
    r = idem(proj, cmd + " assets/seed.png")
    assert r.returncode == 0, r.stdout
    rr = rows(proj)
    assert rr["idempotence:trees"]["status"] == "pass" and "determinism:rules" in rr
    assert (proj / "_counter").read_text() == "2"  # the chain really ran twice


def test_the_emit_chain_is_idempotent_on_the_acme_pack(acme):
    r = bc("verify-idempotent", "--cmd", "{bc} emit web --project {project}", project=acme, timeout=600)
    assert r.returncode == 0, r.stdout
    assert rows(acme)["idempotence:trees"]["status"] == "pass" and rows(acme)["determinism:rules"]["status"] == "pass"


def test_a_generator_that_embeds_a_run_counter_fails(proj):
    cmd = gen(proj, "bad", "pathlib.Path('assets/gen/a.txt').write_text(f'run {n}')\n")
    r = idem(proj, cmd)
    assert r.returncode == 1
    assert failing(report(proj, "idempotence")) == ["idempotence:assets/gen/a.txt"]
    assert "make the generator deterministic" in rows(proj)["idempotence:assets/gen/a.txt"]["detail"]


def test_files_that_appear_or_vanish_between_runs_fail(proj):
    cmd = gen(proj, "flap", "pathlib.Path(f'assets/gen/only-run-{n}.txt').write_text('x')\n")
    r = idem(proj, cmd)
    assert r.returncode == 1
    bad = failing(report(proj, "idempotence"))
    assert "idempotence:assets/gen/only-run-2.txt" in bad  # a file the first run did not write


def allow(proj, entries):
    (proj / "qa").mkdir(exist_ok=True)
    (proj / "qa/idempotence.json").write_text(json.dumps({"schema": 1, "entries": entries}))


def test_an_allowlisted_difference_needs_a_reason_and_still_passes_its_substitute_check(proj):
    cmd = gen(proj, "stamped", "pathlib.Path('assets/gen/a.txt').write_text(f'stamp={n}\\nbody v1\\n')\n")
    allow(proj, [{"path": "assets/gen/a.txt", "reason": "the generator stamps its own run number", "substitute": {"check": "text-equal-except", "pattern": "stamp=\\d+"}}])
    r = idem(proj, cmd)
    assert r.returncode == 0, r.stdout
    row = rows(proj)["idempotence:assets/gen/a.txt"]
    assert row["status"] == "pass" and "the generator stamps" in row["detail"] and "text-equal-except" in row["detail"]
    # the same allowance cannot hide a real change of content
    cmd2 = gen(proj, "stamped2", "pathlib.Path('assets/gen/a.txt').write_text(f'stamp={n}\\nbody v{n}\\n')\n")
    r = idem(proj, cmd2)
    assert r.returncode == 1 and "FAILED, the two versions are not equivalent" in rows(proj)["idempotence:assets/gen/a.txt"]["detail"]


def test_a_png_that_differs_only_in_a_text_chunk_is_equal_by_pixels(proj):
    body = ("import struct, zlib\n"
            "sys.path.insert(0, %r)\nfrom px_lib import Img\n"
            "d = Img(2, 2, '#102030').png(); t = b'tEXt'; b = b'Comment\\x00run %%d' %% n\n"
            "ch = struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xFFFFFFFF)\n"
            "pathlib.Path('assets/gen/p.png').write_bytes(d[:-12] + ch + d[-12:])\n") % str(ROOT / "scripts/lib")
    cmd = gen(proj, "pngtext", body)
    allow(proj, [{"path": "assets/gen/*.png", "reason": "a comment chunk carries the run number", "substitute": {"check": "pixels-equal"}}])
    r = idem(proj, cmd)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["idempotence:assets/gen/p.png"]["status"] == "pass"
    cmd = gen(proj, "pngpix", body.replace("Img(2, 2, '#102030')", "Img(2 + n, 2, '#102030')"))
    assert idem(proj, cmd).returncode == 1  # the pixels differ too: the substitute check fails


def test_allowlist_entries_are_validated_and_a_stale_one_is_reported(proj):
    cmd = gen(proj, "good", "pathlib.Path('assets/gen/a.txt').write_text('same')\n")
    sub = {"check": "json-equal"}
    for entry, why in (({"path": "x", "reason": "", "substitute": sub}, "reason"),
                       ({"path": "x", "reason": "r"}, "substitute"),
                       ({"path": "x", "reason": "r", "substitute": {"check": "trust-me"}}, "substitute.check"),
                       ({"path": "x", "reason": "r", "substitute": {"check": "command"}}, "command"),
                       ({"path": "x", "reason": "r", "substitute": {"check": "text-equal-except"}}, "pattern")):
        allow(proj, [entry])
        r = idem(proj, cmd)
        assert r.returncode == 2 and why in r.stderr, (entry, r.stderr)
    allow(proj, [{"path": "assets/gen/never.txt", "reason": "was needed once", "substitute": sub}])
    r = idem(proj, cmd)
    assert r.returncode == 0
    assert rows(proj)["allowlist:assets/gen/never.txt"]["status"] == "warn"  # it matches no difference: the list cannot rot silently


def test_the_determinism_lint_fails_a_deterministic_but_dated_png(proj):
    body = ("d = open(sys.argv[1], 'rb').read()\n"
            "pathlib.Path('assets/gen/p.png').write_bytes(d)\n")
    f = proj / "assets/dated.png"
    f.write_bytes(png_with(chunk(b"tIME", struct.pack(">HBBBBB", 2026, 10, 17, 9, 30, 0))))
    cmd = gen(proj, "dated", body) + " assets/dated.png"
    r = idem(proj, cmd)
    assert r.returncode == 1
    assert any(i.startswith("determinism:") for i in failing(report(proj, "idempotence")))  # byte-stable, yet it breaks the rule
    assert idem(proj, cmd, extra=["--no-lint"]).returncode == 0
    assert rows(proj)["determinism:rules"]["status"] == "info"  # skipping the lint is printed, not hidden


def test_a_failing_command_and_a_bad_root_are_reported(proj):
    r = idem(proj, f"{PY} -c 'import sys; sys.exit(3)'")
    assert r.returncode == 1 and rows(proj)["idempotence:run1"]["status"] == "fail" and "exited 3" in rows(proj)["idempotence:run1"]["detail"]
    r = idem(proj, f"{PY} -c pass", extra=["--root", "../outside"])
    assert r.returncode == 2 and "outside the project" in r.stderr


# ================================================================ staleness

def test_staleness_records_and_compares_inputs_plugin_version_and_emitter_code(acme):
    assert bc("staleness", project=acme).returncode == 2  # nothing recorded yet
    r = bc("staleness", "--write", project=acme)
    assert r.returncode == 0, r.stderr
    doc = json.loads((acme / "tools/inputs.json").read_text())
    assert doc["schema"] == 1 and doc["plugin_version"] == json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    paths = {i["path"] for i in doc["inputs"]}
    assert {"tokens/primitives.tokens.json", "assets/logo/mark.svg", "qa/rules.json"} <= paths
    assert any(e["path"] == "scripts/emitters/web.py" for e in doc["emitters"])
    tok = next(i for i in doc["inputs"] if i["path"] == "tokens/primitives.tokens.json")
    assert tok["sha256"] == sha(acme / "tokens/primitives.tokens.json")
    r = bc("staleness", project=acme)
    assert r.returncode == 0 and "pack is current" in r.stdout


def test_a_changed_new_or_removed_input_makes_the_pack_stale(acme):
    bc("staleness", "--write", project=acme)
    mutate(acme / "assets/logo/mark.svg", 'r="9"', 'r="8"')
    r = bc("staleness", project=acme)
    assert r.returncode == 1 and "staleness:input:assets/logo/mark.svg" in failing(report(acme, "staleness"))
    bc("staleness", "--write", project=acme)
    assert bc("staleness", project=acme).returncode == 0
    (acme / "assets/logo/extra.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><path d="M0 0h1v1z"/></svg>')
    r = bc("staleness", project=acme)
    assert r.returncode == 1 and "is new since the pack was built" in rows(acme, "staleness")["staleness:input:assets/logo/extra.svg"]["detail"]
    bc("staleness", "--write", project=acme)
    (acme / "assets/logo/extra.svg").rename(acme / "assets/logo/extra.moved")
    assert bc("staleness", project=acme).returncode == 1


def test_a_newer_plugin_or_changed_emitter_code_makes_the_pack_stale(acme, plugin_copy):
    bc("staleness", "--write", project=acme)
    assert bc("staleness", project=acme, plugin=plugin_copy).returncode == 0  # an identical copy of the plugin
    mutate(plugin_copy / "scripts/emitters/web.py", "def ", "def  ", 1)  # a change of emitter code
    r = bc("staleness", project=acme, plugin=plugin_copy)
    assert r.returncode == 1 and "staleness:emitters" in failing(report(acme, "staleness"))
    assert "scripts/emitters/web.py" in rows(acme, "staleness")["staleness:emitters"]["detail"]
    shutil.copy2(ROOT / "scripts/emitters/web.py", plugin_copy / "scripts/emitters/web.py")
    mutate_json(plugin_copy / ".claude-plugin/plugin.json", lambda d: d.__setitem__("version", "9.9.9"))
    r = bc("staleness", project=acme, plugin=plugin_copy)
    assert r.returncode == 1 and "staleness:plugin-version" in failing(report(acme, "staleness"))


def test_needles_keep_a_sibling_documents_quoted_sentence_honest(acme):
    (acme / "README.md").write_text("The pack ships a 180 px touch icon\nfor home screens.\n")
    r = bc("staleness", "--write", "--needle", "README.md::The pack ships a 180 px touch icon for home screens.", project=acme)
    assert r.returncode == 0, r.stderr  # whitespace and line breaks do not matter
    assert bc("staleness", project=acme).returncode == 0
    mutate(acme / "README.md", "180 px", "192 px")
    r = bc("staleness", project=acme)
    assert r.returncode == 1 and "staleness:needle:README.md" in failing(report(acme, "staleness"))
    r = bc("staleness", "--write", "--needle", "README.md::no such sentence", project=acme)
    assert r.returncode == 2 and "needle not found" in r.stderr


def test_check_runs_the_staleness_comparison_when_inputs_json_exists(acme):
    assert not any(r["id"].startswith("staleness") for r in (bc("check", project=acme) and report(acme, "check")["results"]))
    bc("staleness", "--write", project=acme)
    assert any(r["id"] == "staleness:current" and r["status"] == "pass" for r in (bc("check", project=acme) and report(acme, "check")["results"]))
    mutate(acme / "assets/logo/mark.svg", 'r="9"', 'r="8"')
    bc("check", project=acme)
    assert "staleness:input:assets/logo/mark.svg" in failing(report(acme, "check"))


# ================================================================ specs-due

def specs_rows():
    """Every spec row: platform-specs.json and the print_region rows of print-regions.json (both files, read by hand)."""
    doc = json.loads((ROOT / "scripts/emitters/platform-specs.json").read_text())
    doc["rows"].update(json.loads((ROOT / "scripts/emitters/print-regions.json").read_text())["rows"])
    return doc


def due(plugin, today, *args):
    return bc("specs-due", "--json", *args, plugin=plugin, env={"BRAND_CREATOR_TODAY": today})


def test_specs_due_lists_unverified_and_secondary_rows_and_the_stale_ones(plugin_copy):
    doc = specs_rows()
    unconfirmed = {k for k, v in doc["rows"].items() if v["status"] in ("U", "R")}
    r = due(plugin_copy, "2026-10-17")
    out = json.loads(r.stdout)
    assert r.returncode == 0 and {x["id"] for x in out["rows"]} == unconfirmed and not any(x["stale"] for x in out["rows"])
    assert all(any("status" in why for why in x["reasons"]) for x in out["rows"])
    verified = next(k for k, v in doc["rows"].items() if v["status"] == "V" and v["checked"] == "2026-10-17")
    # 2026-10-17 + 179 days = 2027-04-14 (14 + 30 + 31 + 31 + 28 + 31 + 14): still fresh, one day left
    assert verified not in {x["id"] for x in json.loads(due(plugin_copy, "2027-04-14").stdout)["rows"]}
    soon = {x["id"]: x for x in json.loads(due(plugin_copy, "2027-04-14", "--within", "5").stdout)["rows"]}
    assert verified in soon and soon[verified]["days_left"] == 1 and "becomes stale in 1 day" in soon[verified]["reasons"][0]
    late = {x["id"]: x for x in json.loads(due(plugin_copy, "2027-04-16").stdout)["rows"]}  # 181 days: stale
    assert late[verified]["stale"] is True and late[verified]["age_days"] == 181 and "stale: checked 2026-10-17, 181 days ago" in late[verified]["reasons"][0]


def test_fail_on_due_is_the_release_gate(plugin_copy):
    assert due(plugin_copy, "2026-10-17", "--fail-on-due").returncode == 0  # unconfirmed rows alone do not fail it
    r = due(plugin_copy, "2027-04-16", "--fail-on-due")
    assert r.returncode == 1
    text = bc("specs-due", plugin=plugin_copy, env={"BRAND_CREATOR_TODAY": "2027-04-16"}).stdout
    assert "STALE" in text and "recheck: https://" in text


def test_the_limit_is_the_files_own_stale_after_days(plugin_copy):
    mutate_json(plugin_copy / "scripts/emitters/platform-specs.json", lambda d: d.__setitem__("stale_after_days", 10))
    rows_ = json.loads(due(plugin_copy, "2026-10-28").stdout)["rows"]  # 11 days after 2026-10-17
    assert rows_ and all(x["stale"] for x in rows_) and len(rows_) == len(specs_rows()["rows"])


def test_check_warns_about_stale_or_unverified_rows_a_pack_was_built_from(acme):
    assert bc("emit", "web", project=acme).returncode == 0
    r = bc("check", project=acme, env={"BRAND_CREATOR_TODAY": "2026-10-17"})
    warns = [x["id"] for x in report(acme, "check")["results"] if x["id"].startswith("specs:")]
    stamped = json.loads((acme / "assets/manifest.json").read_text())["specs"]
    assert {x for x in warns} == {f"specs:{k}" for k, v in stamped.items() if v["status"] == "U" or v["stale"]}


# ================================================================ size bands and the manifest

BANDS = {"schema": 1, "bands": [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"},
                                {"name": "large", "drawing": "assets/logo/mark.svg"}]}


def rules_file(proj, doc):
    (proj / "qa").mkdir(exist_ok=True)
    (proj / "qa/rules.json").write_text(json.dumps(doc))


def test_one_function_picks_the_drawing_for_a_body_size():
    bands = qa_rules.validate_bands(BANDS["bands"])
    assert [qa_rules.pick_band(bands, s)["name"] for s in (1, 16, 32, 33, 180, 1024)] == ["small", "small", "small", "large", "large", "large"]
    assert qa_rules.pick_band(bands, 16)["drawing"] == "assets/logo/grid-mark.svg"
    assert qa_rules.pick_band([], 16) is None  # no bands defined: no rule


@pytest.mark.parametrize("bands,why", [
    ([{"name": "a", "max_px": 32}], "name and a drawing"),
    ([{"name": "a", "drawing": "x"}, {"name": "b", "drawing": "y"}], "only the last band may omit max_px"),
    ([{"name": "a", "max_px": 32, "drawing": "x"}, {"name": "b", "max_px": 16, "drawing": "y"}], "above the previous band"),
    ([{"name": "a", "max_px": 32, "drawing": "x"}, {"name": "b", "max_px": 64, "drawing": "y"}], "the last band covers every larger size"),
    ([{"name": "a", "max_px": 32, "drawing": "x"}], "the last band covers every larger size"),
    ([{"name": "a", "max_px": 32, "drawing": "x"}, {"name": "a", "drawing": "y"}], "unique"),
    ([{"name": "a", "max_px": 32, "drawing": "x", "colour": "red"}], "unknown keys"),
    ("small", "must be a list"),
])
def test_malformed_bands_exit_2(proj, bands, why):
    rules_file(proj, {"schema": 1, "bands": bands})
    r = bc("downscale", "--source", "x.png", project=proj)
    assert r.returncode == 2 and why in r.stderr, r.stderr


def test_a_slot_records_its_band_and_an_off_rule_slot_needs_an_exemption(proj):
    rules_file(proj, BANDS)
    m = Manifest(proj)
    assert m.put_slot("assets/s/16.png", b"a", emitter="t", specs=[], slot="favicon", size_px=16) is True
    m.put_slot("assets/s/64.png", b"b", emitter="t", specs=[], slot="touch", size_px=64, qa=["downscale"])
    assert m.artefacts["assets/s/16.png"]["band"] == "small" and m.artefacts["assets/s/64.png"]["band"] == "large"
    assert m.artefacts["assets/s/16.png"]["size"] == "16x16" and m.artefacts["assets/s/64.png"]["qa"] == ["downscale"]
    with pytest.raises(CliError) as e:
        m.put_slot("assets/s/x.png", b"c", emitter="t", specs=[], slot="odd", size_px=16, band="large")
    assert e.value.code == 1 and "needs a stated exemption" in e.value.message
    assert "assets/s/x.png" not in m.artefacts
    m.put_slot("assets/s/x.png", b"c", emitter="t", specs=[], slot="odd", size_px=16, band="large", exemption="the store crops the grid mark")
    assert m.artefacts["assets/s/x.png"]["band"] == "large" and m.artefacts["assets/s/x.png"]["exemption"] == "the store crops the grid mark"
    with pytest.raises(CliError) as e:
        m.put_slot("assets/s/y.png", b"d", emitter="t", specs=[], slot="odd", size_px=16, band="huge", exemption="because")
    assert e.value.code == 2 and "unknown band" in e.value.message
    m.save()
    again = Manifest(proj)
    assert again.put_slot("assets/s/16.png", b"a", emitter="t", specs=[], slot="favicon", size_px=16) is False  # put on byte change only
    assert "assets/s/16.png" in again.unchanged
    plain = make_project(proj.parent, "other")
    with pytest.raises(CliError) as e:
        Manifest(plain).put_slot("assets/s/z.png", b"d", emitter="t", specs=[], slot="s", size_px=16, band="small")
    assert e.value.code == 2 and "defines no bands" in e.value.message


def test_check_gates_the_band_rule_from_the_manifest(proj):
    rules_file(proj, BANDS)
    m = Manifest(proj)
    m.put_slot("assets/s/16.png", b"a", emitter="t", specs=[], slot="favicon", size_px=16)
    m.save()
    assert next(x for x in (bc("check", project=proj) and report(proj, "check")["results"]) if x["id"] == "manifest:bands")["status"] == "pass"
    mutate_json(proj / "assets/manifest.json", lambda d: d["artefacts"][0].__setitem__("band", "large"))  # tampered: off the rule, no exemption
    r = bc("check", project=proj)
    assert r.returncode == 1 and "manifest:bands" in failing(report(proj, "check"))
    row = next(x for x in report(proj, "check")["results"] if x["id"] == "manifest:bands")
    assert "assets/s/16.png" in row["detail"] and "no exemption" in row["detail"]
    mutate_json(proj / "assets/manifest.json", lambda d: d["artefacts"][0].__setitem__("exemption", "owner accepted the fine drawing here"))
    bc("check", project=proj)
    assert "manifest:bands" not in failing(report(proj, "check"))
    rules_file(proj, {"schema": 1})  # the rules lost their bands: a recorded band no longer means anything
    bc("check", project=proj)
    assert "manifest:bands" in failing(report(proj, "check"))


# ================================================================ QA wiring in `check`

def ds_row(report_doc: dict, source: str) -> dict:
    from _common import downscale_report_tool
    return next(x for x in report_doc["results"] if x["id"] == f"report:{downscale_report_tool(source)}")


def test_a_manifest_row_that_asks_for_a_qa_gate_cannot_skip_it(acme):
    master = "assets/logo/grid-mark-master.png"
    m = Manifest(acme)
    m.put("assets/s/icon.png", Img(16, 16, "#007d71").png(), emitter="t", specs=[], qa=["downscale"], downscale_source=master)
    m.save()
    r = bc("check", project=acme)
    row = ds_row(report(acme, "check"), master)
    assert r.returncode == 3 and row["status"] == "skipped"
    assert f"run `brand-creator downscale --source {master}`" in row["detail"]
    assert bc("downscale", "--source", master, *OFF_MAC_DOWNSCALE, project=acme).returncode == 0
    bc("check", project=acme)
    assert ds_row(report(acme, "check"), master)["status"] == "pass"
    # the report goes stale when its input changes
    mutate_json(acme / "qa/rules.json", lambda d: d["downscale"].__setitem__("accent_min_px", 5))
    bc("check", project=acme)
    st = ds_row(report(acme, "check"), master)
    assert st["status"] == "skipped" and "stale" in st["detail"] and "qa/rules.json changed" in st["detail"]


def test_a_passing_downscale_report_on_another_file_does_not_satisfy_a_row(acme):
    """The Apple-master hole: the row asks for the proof of ITS master; a passing report on a different file must not stand in for it."""
    fine, grid = "assets/logo/mark.svg", "assets/logo/grid-mark-master.png"
    m = Manifest(acme)
    m.put("assets/s/icon.png", Img(16, 16, "#007d71").png(), emitter="t", specs=[], qa=["downscale"], downscale_source=fine)
    m.save()
    assert bc("downscale", "--source", grid, *OFF_MAC_DOWNSCALE, project=acme).returncode == 0   # a passing proof, but of the grid master
    assert bc("downscale", "--source", fine, "--renderer", "resvg", project=acme).returncode == 1   # the row's own master fails the rule
    r = bc("check", project=acme)
    res = report(acme, "check")
    assert r.returncode == 1 and ds_row(res, fine)["status"] == "fail"
    assert "downscale:16px" in ds_row(res, fine)["detail"]
    assert ds_row(res, grid)["status"] == "pass"   # the other report is gated on its own, and passing
    # the row cannot be moved onto the passing report by editing the row alone: the report names its source
    mutate_json(acme / "assets/manifest.json", lambda d: d["artefacts"][0].__setitem__("downscale_source", grid))
    bc("check", project=acme)
    assert ds_row(report(acme, "check"), grid)["status"] == "pass"   # now it IS the row's master: that is the honest way to pass
    # a report whose recorded source differs from the file name it sits under does not count
    from _common import downscale_report_tool
    f = acme / "assets/_checks/downscale" / (downscale_report_tool(grid).split("/")[1] + ".json")
    mutate_json(f, lambda d: d.__setitem__("source", fine))
    bc("check", project=acme)
    assert ds_row(report(acme, "check"), grid)["status"] == "skipped" and "measured" in ds_row(report(acme, "check"), grid)["detail"]


def test_a_downscale_row_without_a_recorded_master_fails(acme):
    m = Manifest(acme)
    m.put("assets/s/icon.png", Img(16, 16, "#007d71").png(), emitter="t", specs=[], qa=["downscale"])
    m.save()
    r = bc("check", project=acme)
    assert r.returncode == 1 and "qa:downscale" in failing(report(acme, "check"))
    assert "downscale_source" in next(x for x in report(acme, "check")["results"] if x["id"] == "qa:downscale")["detail"]


def test_put_slot_records_the_downscale_master_and_defaults_to_the_file_itself(proj):
    m = Manifest(proj)
    m.put_slot("assets/s/a.png", b"a", emitter="t", specs=[], slot="s", size_px=16, qa=["downscale"])
    m.put_slot("assets/s/b.png", b"b", emitter="t", specs=[], slot="s", size_px=16, qa=["downscale"], downscale_source="assets/s/a.png")
    assert m.artefacts["assets/s/a.png"]["downscale_source"] == "assets/s/a.png"
    assert m.artefacts["assets/s/b.png"]["downscale_source"] == "assets/s/a.png"


def test_a_failing_qa_report_that_exists_fails_check_even_without_a_manifest_request(acme):
    assert bc("downscale", "--source", "assets/logo/mark.svg", "--renderer", "resvg", project=acme).returncode == 1
    r = bc("check", project=acme)
    res = report(acme, "check")
    assert r.returncode == 1 and any(i.startswith("report:downscale/mark-") for i in failing(res))
    assert "downscale:16px" in next(x for x in res["results"] if x["id"].startswith("report:downscale/mark-"))["detail"]


def test_an_unknown_qa_gate_in_the_manifest_fails(acme):
    m = Manifest(acme)
    m.put("assets/s/icon.png", Img(4, 4, "#007d71").png(), emitter="t", specs=[], qa=["vibes"])
    m.save()
    r = bc("check", project=acme)
    assert r.returncode == 1 and "qa:vibes" in failing(report(acme, "check"))


def test_every_qa_report_the_new_tools_write_is_a_gate_in_check(acme):
    """states, family, motion, fontcheck and idempotence reports are gated as soon as they exist."""
    assert bc("states-check", project=acme).returncode == 0
    ids = {x["id"]: x["status"] for x in (bc("check", project=acme) and report(acme, "check")["results"])}
    assert ids["report:states"] == "pass"
    mutate_json(acme / "qa/states.json", lambda d: d["sets"][0]["states"].__setitem__("dup", "assets/states/idle.png"))
    assert bc("states-check", project=acme).returncode == 1
    r = bc("check", project=acme)
    assert r.returncode == 1 and "report:states" in failing(report(acme, "check"))


# ================================================================ motion reports in `check`: one per proof file (assets/_checks/motion/<slug>-<hash6>.json)

def motion_report(project: Path, proof: str, status: str = "pass") -> Path:
    """The report `shot --motion` writes for a proof, written by hand: these tests need no browser."""
    from _common import motion_report_tool
    f = project / "assets" / "_checks" / (motion_report_tool(proof) + ".json")
    f.parent.mkdir(parents=True, exist_ok=True)
    inputs = [{"path": proof, "sha256": sha(project / proof)}] if (project / proof).is_file() else []
    row = {"id": "motion:demo:control", "status": "fail" if status == "fail" else "pass", "label": "control", "detail": "x"}
    f.write_text(json.dumps({"tool": motion_report_tool(proof), "version": "0", "inputs_sha": "0" * 64, "inputs": inputs, "renderer": "x",
                             "results": [row], "status": status, "proof": proof}, indent=2) + "\n")
    return f


def put_proof(project: Path, rel_path: str) -> str:
    """A proof file (`check` only hashes it) at a project path."""
    f = project / rel_path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text('{"schema": 1, "cases": []}\n')
    return rel_path


def motion_row(project: Path, proof: str) -> dict:
    from _common import motion_report_tool
    return next(x for x in report(project, "check")["results"] if x["id"] == f"report:{motion_report_tool(proof)}")


def test_a_motion_report_is_gated_as_a_downscale_one_is_current_failing_or_stale(proj):
    proof = put_proof(proj, "motion/proof.json")
    motion_report(proj, proof)
    assert bc("check", project=proj).returncode == 0 and motion_row(proj, proof)["status"] == "pass"
    mutate(proj / proof, '"cases": []', '"cases": [ ]')   # the proof changed since the report was made
    r = bc("check", project=proj)
    row = motion_row(proj, proof)
    assert r.returncode == 3 and row["status"] == "skipped" and "stale" in row["detail"] and "motion/proof.json changed" in row["detail"]
    assert f"brand-creator shot --motion {proof}" in row["detail"]
    mutate(proj / proof, '"cases": [ ]', '"cases": []')
    motion_report(proj, proof, "fail")
    r = bc("check", project=proj)
    assert r.returncode == 1 and motion_row(proj, proof)["status"] == "fail" and "motion:demo:control" in motion_row(proj, proof)["detail"]


def test_two_motion_proofs_are_two_reports_and_a_passing_one_never_stands_in_for_a_failing_one(proj):
    a, b = put_proof(proj, "motion/proof.json"), put_proof(proj, "motion/hero.json")
    motion_report(proj, a)
    motion_report(proj, b, "fail")
    r = bc("check", project=proj)
    assert r.returncode == 1
    assert motion_row(proj, a)["status"] == "pass" and motion_row(proj, b)["status"] == "fail"
    assert len(list((proj / "assets/_checks/motion").glob("*.json"))) == 2
    from _common import motion_report_tool
    assert motion_report_tool(a) != motion_report_tool("rounds/r2/proof.json")   # the same file name in another folder is another report


@pytest.mark.parametrize("bad", [[1], {"proof": "motion/proof.json", "inputs": None, "status": "pass"}, {"proof": "motion/proof.json", "inputs": [{"sha256": "0" * 64}], "status": "pass"},
                                 {"proof": "motion/proof.json", "inputs": [], "status": "fail", "results": [7]}])
def test_a_report_that_is_json_but_no_report_is_its_own_failing_row_never_a_crash(proj, bad):
    """0.4.1 stopped `check` with a traceback on a report that is valid JSON but no report (board-lint already said it cannot be read): it is the report's own failing row now, for a
    gated motion report and for a downscale report, which is read for its source before it is gated."""
    proof = put_proof(proj, "motion/proof.json")
    motion_report(proj, proof).write_text(json.dumps(bad))
    down = proj / "assets" / "_checks" / "downscale" / "mark-000000.json"
    down.parent.mkdir(parents=True, exist_ok=True)
    down.write_text(json.dumps(bad))
    r = bc("check", project=proj)
    assert r.returncode == 1 and "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr
    rows = {x["id"]: x for x in report(proj, "check")["results"]}
    for got in (motion_row(proj, proof), rows["report:downscale/mark-000000"]):
        assert got["status"] == "fail" and "cannot be read as a report" in got["detail"] and "re-run `brand-creator" in got["detail"], got


AGAIN_CASES = {   # a report `check` reads again after its generic row passed: what is in the project, what the report holds, the row it must give (id, status, words in its detail)
    "contrast results null": ({"assets/tokens/tokens.json": {}, "qa/rules.json": {"schema": 1, "cvd": {"min_delta_e": 10.0}}},
                              ("contrast", {"status": "pass", "inputs": [], "results": None}), ("report:contrast:cvd", "skipped", "no colour-vision rows")),
    "contrast result 7": ({"assets/tokens/tokens.json": {}, "qa/rules.json": {"schema": 1, "cvd": {"min_delta_e": 10.0}}},
                          ("contrast", {"status": "pass", "inputs": [], "results": [7]}), ("report:contrast:cvd", "skipped", "no colour-vision rows")),
    "book output null": ({"book.html": "<!doctype html><title>b</title>"}, ("book", {"status": "pass", "inputs": [], "output": None}),
                         ("book:generated", "fail", "records no output it wrote")),
    "book output path null": ({"book.html": "<!doctype html><title>b</title>"}, ("book", {"status": "pass", "inputs": [], "output": {"path": None, "sha256": "x"}}),
                              ("book:generated", "fail", "records no output it wrote")),
    "frames cases null": ({"motion/proof.json": {"schema": 1, "cases": []}}, ("frames", {"proof": "motion/proof.json", "inputs": [], "status": "pass", "results": [], "cases": None}),
                          ("report:frames", "fail", "cannot be read as a report")),
    "frames results null": ({"motion/proof.json": {"schema": 1, "cases": []}}, ("frames", {"proof": "motion/proof.json", "inputs": [], "status": "pass", "results": None}),
                            ("report:frames", "fail", "cannot be read as a report")),
    "frames id is a list": ({"motion/proof.json": {"schema": 1, "cases": []}}, ("frames", {"proof": "motion/proof.json", "inputs": [], "status": "pass", "results": [{"id": [1], "status": "pass"}]}),
                            ("report:frames", "fail", "cannot be read as a report")),
    "adapters list": ({"BRAND.md": "# brand\n"}, ("adapters", [1]), ("report:adapters", "fail", "cannot be read as a report")),
    "adapters outputs null": ({"BRAND.md": "# brand\n"}, ("adapters", {"status": "pass", "inputs": [], "outputs": None}), ("adapters:BRAND.md", "fail", "does not record writing it")),
    "adapters output without sha256": ({"BRAND.md": "# brand\n"}, ("adapters", {"status": "pass", "inputs": [], "outputs": {"BRAND.md": {"path": "BRAND.md"}}}),
                                       ("adapters:BRAND.md", "fail", "does not record writing it")),
    "applied-skill list": ({".claude/skills/acme-brand/SKILL.md": "---\nname: acme-brand\n---\n"}, ("applied-skill", [1]), ("report:applied-skill", "fail", "cannot be read as a report")),
    "applied-skill output null": ({".claude/skills/acme-brand/SKILL.md": "---\nname: acme-brand\n---\n"}, ("applied-skill", {"status": "pass", "inputs": [], "output": None}),
                                  ("applied-skill:file", "fail", "records no output it wrote")),
}


@pytest.mark.parametrize("case", sorted(AGAIN_CASES))
def test_a_report_check_reads_again_after_its_row_passed_never_stops_check(proj, case):
    """Beyond the generic report row, `check` reads some reports again (the colour-vision rows, the book's output, the stills a frames report vouches for, what the adapters and the applied
    skill wrote). A report there that is JSON but not the report it should be gives a row that says so, never a traceback (0.4.1 stopped on every one of these)."""
    from _common import frames_report_tool
    files, (tool, doc), (rid, status, words) = AGAIN_CASES[case]
    for rel_path, body in files.items():
        f = proj / rel_path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body if isinstance(body, str) else json.dumps(body))
    name = frames_report_tool("motion/proof.json") if tool == "frames" else tool
    rf = proj / "assets" / "_checks" / f"{name}.json"
    rf.parent.mkdir(parents=True, exist_ok=True)
    rf.write_text(json.dumps(doc))
    r = bc("check", project=proj)
    assert "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr
    rows = {x["id"]: x for x in report(proj, "check")["results"]}
    got = rows[f"report:{name}" if rid == "report:frames" else rid]
    assert got["status"] == status and words in got["detail"], got


def test_a_proof_under_rounds_history_or_removed_is_an_exploration_listed_and_never_gated(proj):
    from _common import history_files, sha256_file, write_history_manifest
    tries = [put_proof(proj, p) for p in ("rounds/r2/proof.json", "history/r1/motion/proof.json", "removed-2026-10-21/proof.json", "motion/removed-old/proof.json")]
    hist = proj / "history"
    write_history_manifest(hist, {f.relative_to(hist).as_posix(): sha256_file(f) for f in history_files(hist)})   # frozen the way `freeze` writes it
    for t in tries:
        motion_report(proj, t, "fail")   # each would fail the check if it were gated
    r = bc("check", project=proj)
    assert r.returncode == 0, r.stdout
    for t in tries:
        row = motion_row(proj, t)
        assert row["status"] == "info" and "exploration proof, not gated" in row["detail"] and t in row["detail"], t
    near = put_proof(proj, "motion/rounds-proof.json")   # "rounds" in a file name is not a rounds/ folder
    motion_report(proj, near, "fail")
    assert bc("check", project=proj).returncode == 1 and motion_row(proj, near)["status"] == "fail"


KINDS = ROOT / "tests" / "fixtures" / "motion-proof-kinds.json"   # the one table of cases the Python rule and its JavaScript twin (tests/node/common.test.mjs) are both pinned to


def test_the_proof_kind_rule_answers_the_shared_table_of_cases(tmp_path):
    """motion_proof_kind: gated, exploration (under rounds/, history/ or a removed-*/ folder) or gone. The table is read by the JavaScript twin too (motionProofKind), so
    that `frames`, which decides where its stills go by it, and `check`, which decides what it gates, cannot come to tell two paths apart differently."""
    from _common import motion_proof_kind
    cases = json.loads(KINDS.read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 20 and {c["kind"] for c in cases} == {"gated", "exploration", "gone"}
    for i, c in enumerate(cases):
        project = tmp_path / f"p{i}"
        project.mkdir()
        for f in c["files"]:
            (project / f).parent.mkdir(parents=True, exist_ok=True)
            (project / f).write_text("x\n")
        assert motion_proof_kind(project, c["proof"]) == c["kind"], c["why"]


def test_a_motion_report_whose_proof_is_gone_is_a_warning_that_names_it(proj):
    motion_report(proj, "motion/gone.json")        # the proof was never there, or moved away
    motion_report(proj, "rounds/r2/gone.json")     # an exploration proof that is gone is a gone proof first
    r = bc("check", project=proj)
    assert r.returncode == 0, r.stdout
    for p in ("motion/gone.json", "rounds/r2/gone.json"):
        row = motion_row(proj, p)
        assert row["status"] == "warn" and p in row["detail"] and "no longer exists" in row["detail"] and "removed-<date>/" in row["detail"]
        assert "assets/_checks/motion/gone-" in row["detail"] or "assets/_checks/motion/gone" in row["detail"]


def test_a_manifest_row_that_asks_for_motion_needs_a_passing_gated_report(proj):
    m = Manifest(proj)
    m.put("assets/s/mark.png", Img(16, 16, "#007d71").png(), emitter="t", specs=[], qa=["motion"])
    m.save()
    qa = lambda: next(x for x in report(proj, "check")["results"] if x["id"] == "qa:motion")   # noqa: E731
    r = bc("check", project=proj)
    assert r.returncode == 3 and qa()["status"] == "skipped" and "brand-creator shot --motion <proof.json>" in qa()["detail"]
    motion_report(proj, put_proof(proj, "rounds/r2/proof.json"))   # a passing report of an exploration proof does not count
    assert bc("check", project=proj).returncode == 3 and qa()["status"] == "skipped"
    stale = put_proof(proj, "motion/old.json")
    motion_report(proj, stale)
    mutate(proj / stale, '"cases": []', '"cases": [ ]')             # a stale one does not count either
    assert bc("check", project=proj).returncode == 3 and qa()["status"] == "skipped"
    good = put_proof(proj, "motion/proof.json")
    motion_report(proj, good)
    r = bc("check", project=proj)
    assert qa()["status"] == "pass" and "report:motion/proof-" in qa()["detail"]
    assert r.returncode == 3   # the stale report still says "not verified" on its own row, as it should
    mutate(proj / stale, '"cases": [ ]', '"cases": []')
    assert bc("check", project=proj).returncode == 0


def test_a_motion_json_of_an_earlier_version_is_still_gated_with_a_warning_to_run_the_proof_again(proj):
    legacy = proj / "assets/_checks/motion.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"tool": "motion", "version": "0", "inputs_sha": "0" * 64, "inputs": [], "renderer": "x", "status": "fail",
                                  "results": [{"id": "motion:demo-page:cls:normal", "status": "fail", "label": "cls", "detail": "x"}]}) + "\n")
    r = bc("check", project=proj)
    res = {x["id"]: x for x in report(proj, "check")["results"]}
    assert r.returncode == 1 and res["report:motion"]["status"] == "fail" and "motion:demo-page:cls:normal" in res["report:motion"]["detail"]
    warn = res["report:motion:legacy"]
    assert warn["status"] == "warn" and "assets/_checks/motion/<slug>-<hash6>.json" in warn["detail"] and "brand-creator shot --motion <proof.json>" in warn["detail"]
    assert "removed-<date>/" in warn["detail"]
    mutate_json(legacy, lambda d: (d.__setitem__("status", "pass"), d["results"][0].__setitem__("status", "pass")))
    m = Manifest(proj)
    m.put("assets/s/mark.png", Img(16, 16, "#007d71").png(), emitter="t", specs=[], qa=["motion"])
    m.save()
    r = bc("check", project=proj)
    res = {x["id"]: x for x in report(proj, "check")["results"]}
    assert r.returncode == 0 and res["report:motion"]["status"] == "pass" and res["qa:motion"]["status"] == "pass" and res["report:motion:legacy"]["status"] == "warn"
