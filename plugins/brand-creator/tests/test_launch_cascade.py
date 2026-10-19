"""launch-todo (LAUNCH.md, the owner's checklist; nothing outward is ever executed) and check --cascade over every project artefact.

The names screening is replayed from tests/fixtures/names (no network). Expected counts come from the names report's own data (links) or from
the fixture repository, counted by hand. A mutation test plants the old value in one place and asserts that the plant applied and the gate fails."""
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, make_project, mutate, mutate_json, path_without

sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "names"))
import build as fxbuild  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "names"
OLD = "Zq-7 phrase"
SECTIONS = ["Trademark first", "Domains", "Handles and registries", "E-mail", "Deploy", "Repositories, packages and app ids", "Decisions for you"]


def tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def row(p: Path, rid: str, tool="check") -> dict:
    rep = json.loads((p / "assets" / "_checks" / f"{tool}.json").read_text())
    return next(r for r in rep["results"] if r["id"] == rid)


def names(p: Path, *cands, region="PL", tlds="com,io"):
    r = bc("names", *cands, "--tlds", tlds, "--region", region, "--offline", str(FX / "software"), project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads((p / "assets" / "_checks" / "names.json").read_text())


@pytest.fixture
def proj(tmp_path):
    return make_project(tmp_path, tier="full")


# ================================================================ launch-todo

def test_without_a_names_screening_the_file_says_so_and_offers_no_links(proj):
    r = bc("launch-todo", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    t = (proj / "LAUNCH.md").read_text()
    assert "No name screening is on file" in t and "tm-link" not in t and "| domain |" not in t.replace("(no domain", "")
    assert row(proj, "launch:names", "launch-todo")["status"] == "warn"


def test_several_candidates_need_a_name_and_the_choice_must_be_one_of_them(proj):
    names(proj, fxbuild.TAKEN, fxbuild.GONE)
    r = bc("launch-todo", project=proj)
    assert r.returncode == 2 and "say which with --name" in r.stderr and not (proj / "LAUNCH.md").exists()
    r = bc("launch-todo", "--name", "nothere", project=proj)
    assert r.returncode == 2 and "not in the names screening" in r.stderr


def test_launch_md_puts_the_trademark_first_then_dated_domains_handles_email_renames_and_decisions(proj):
    rep = names(proj, fxbuild.TAKEN, fxbuild.GONE)
    assert bc("launch-todo", "--name", fxbuild.GONE, project=proj).returncode == 0
    t = (proj / "LAUNCH.md").read_text()
    assert re.findall(r"^## (.+)$", t, re.M) == SECTIONS                                    # the order is the point: trademark first
    links = next(x["links"] for x in rep["trademark_links"] if x["candidate"] == fxbuild.GONE)
    assert len(re.findall(r"id:tm-link-\d+", t)) == len(links) and "ewyszukiwarka.pue.uprp.gov.pl" in t and "tmdn.org/tmview" in t
    assert "never queries a trademark register and never files" in t
    assert "Checked 2026-10-17, recheck before buying" in t
    dom = re.findall(rf"^\| {fxbuild.GONE}(\.[a-z]+) \| ([A-Z-]+) \| \[ \] buy", t, re.M)
    assert dom == [(".com", "NOT-FOUND"), (".io", "NOT-FOUND")]
    cells = {r["source"] for r in rep["results"] if r["candidate"] == fxbuild.GONE and not r["source"].startswith(".")}
    handle_rows = re.findall(r"^\| ([A-Za-z0-9. ]+) \| " + fxbuild.GONE + r" \| ([A-Z-]+) \|", t, re.M)
    assert len(handle_rows) == len(cells) == 8 and {s for _w, s in handle_rows} == {"NOT-FOUND"}
    assert "granite" not in t                                                                # only the chosen candidate is listed
    assert "FACTS.md `contact email`: no row yet." in t and "id:mail-box" in t
    assert re.search(r"id:decide-1 -->", t) and t.index("Trademark first") < t.index("## Domains") < t.index("## Decisions for you")


def test_launch_md_never_says_a_name_is_available_free_or_clear(proj):
    names(proj, fxbuild.TAKEN, fxbuild.GONE)
    assert bc("launch-todo", "--name", fxbuild.GONE, project=proj).returncode == 0
    t = (proj / "LAUNCH.md").read_text()
    assert not re.search(r"(?i)\b(available|free|clear|cleared)\b", t), re.findall(r"(?i).{30}\b(available|free|clear|cleared)\b.{20}", t)
    assert {s for s in re.findall(r"\| (REGISTERED|NOT-FOUND|UNKNOWN) \|", t)} <= {"REGISTERED", "NOT-FOUND", "UNKNOWN"}


def test_nothing_outward_is_executed_and_only_the_launch_files_are_written(proj):
    names(proj, fxbuild.TAKEN, fxbuild.GONE)
    before = tree(proj)
    assert bc("launch-todo", "--name", fxbuild.GONE, project=proj).returncode == 0
    after = tree(proj)
    assert sorted(set(after) - set(before)) == ["LAUNCH.md", "assets/_checks/launch-todo.json"]
    assert {k for k in before if after.get(k) != before[k]} == set()
    src = (ROOT / "scripts" / "launch.py").read_text()
    for banned in ("socket", "urllib", "http.client", "requests", "smtplib", "ftplib", "ssl", "subprocess", "webbrowser"):
        assert not re.search(rf"^\s*(import|from)\s+{re.escape(banned)}\b", src, re.M), f"launch.py imports {banned}: it must stay a local-files-only command"
    assert row(proj, "launch:outward", "launch-todo")["status"] == "info"


def test_ticks_survive_a_second_generation_and_a_vanished_box_is_reported(proj):
    names(proj, fxbuild.TAKEN, fxbuild.GONE)
    assert bc("launch-todo", "--name", fxbuild.GONE, project=proj).returncode == 0
    f = proj / "LAUNCH.md"
    total = len(re.findall(r"id:[A-Za-z0-9_.:-]+ -->", f.read_text()))
    assert f"Progress: 0 of {total} boxes ticked." in f.read_text()
    mutate(f, "- [ ] Decide, with your attorney", "- [x] Decide, with your attorney")
    mutate(f, "| [ ] buy <!-- id:dom.io -->", "| [x] buy <!-- id:dom.io -->")
    assert bc("launch-todo", "--name", fxbuild.GONE, project=proj).returncode == 0
    t = f.read_text()
    assert "- [x] Decide, with your attorney" in t and "| [x] buy <!-- id:dom.io -->" in t and "| [ ] buy <!-- id:dom.com -->" in t
    assert f"Progress: 2 of {total} boxes ticked." in t
    # a new screening without .io: the ticked .io box has no place any more, and the report says so
    names(proj, fxbuild.TAKEN, fxbuild.GONE, tlds="com")
    assert bc("launch-todo", "--name", fxbuild.GONE, project=proj).returncode == 0
    assert "dom.io" not in f.read_text() and "- [x] Decide, with your attorney" in f.read_text()
    assert row(proj, "launch:ticks", "launch-todo")["status"] == "warn" and "dom.io" in row(proj, "launch:ticks", "launch-todo")["detail"]


def test_open_questions_of_brand_state_are_carried_into_the_decisions(proj):
    mutate(proj / "BRAND-STATE.md", "1. (...)\n\n## Liked", "1. Whether the tagline may mention repairs.\n2. (...)\n\n## Liked")
    names(proj, fxbuild.GONE)
    assert bc("launch-todo", project=proj).returncode == 0
    t = (proj / "LAUNCH.md").read_text()
    assert "Whether the tagline may mention repairs." in t and "(...)" not in t


@pytest.mark.requires_rg
def test_the_rename_list_comes_from_the_adoption_survey_and_is_marked_as_a_record_of_the_other_repo(proj, tmp_path):
    repo = tmp_path / "shop"
    shutil.copytree(ROOT / "tests" / "fixtures" / "target-repo", repo)
    names(proj, fxbuild.GONE)
    assert bc("adoption", "survey", "--repo", f"{repo}=shop", "--old-name", "Oldco", project=proj).returncode == 0
    ids = json.loads((proj / "adoption.json").read_text())["identifiers"]
    assert bc("launch-todo", project=proj).returncode == 0
    t = (proj / "LAUNCH.md").read_text()
    rows = [ln for ln in t.splitlines() if re.match(r"^\| shop \| `", ln)]
    assert len(rows) == len(ids) == 5 and all(ln.rstrip().endswith("<!-- target-repo -->") for ln in rows)
    assert any("`oldco-app`" in ln and "package name" in ln for ln in rows)
    assert "Rename the repository `shop`" in t


def test_the_print_hand_off_appears_only_with_print_files_and_never_equates_hex_with_a_spot_colour(acme):
    names(acme, fxbuild.GONE)
    assert bc("launch-todo", project=acme).returncode == 0
    assert "## Print hand-off" not in (acme / "LAUNCH.md").read_text()
    (acme / "assets" / "manifest.json").write_text(json.dumps({"artefacts": [
        {"path": "assets/print/letterhead.rgb-proof.pdf", "emitter": "print", "sha256": "0" * 64, "bytes": 1},
        {"path": "assets/print/letterhead.print.json", "emitter": "print", "sha256": "0" * 64, "bytes": 1}]}))
    assert bc("launch-todo", project=acme).returncode == 0
    t = (acme / "LAUNCH.md").read_text()
    assert "## Print hand-off" in t and "`assets/print/letterhead.rgb-proof.pdf`" in t and "print.json`" not in t.split("## Print hand-off")[1].split("Spot colours")[0]
    assert "RGB proof, not print-ready" in t and "bundles none" in t and "printer's proof" in t
    assert "a hex value never equals a spot ink" in t
    assert "| accent | #007d71 |  |  |" in t and "| bg | #f9f7ee |  |  |" in t                # name and Lab target are left for the printer's swatch
    assert re.findall(r"^## (.+)$", t, re.M) == SECTIONS[:6] + ["Print hand-off", "Decisions for you"]


# ================================================================ check --cascade

PLANT = {
    "book source": ("book/chapters/idea.md", "# Idea\n\nplaceholder\n"),
    "README": ("README.md", "# Acme\n\nplaceholder\n"),
    "token source": ("tokens/primitives.tokens.json", '{"color": {"note": "placeholder"}}\n'),
    "text asset": ("assets/notes/readme.txt", "placeholder\n"),
    "template in the project": ("tpl/card.html", "<p>placeholder</p>\n"),
    "built book": ("book.html", "<p>placeholder</p>\n"),
    "BRAND.md": ("BRAND.md", "# Acme\n\nplaceholder\n"),
    "DESIGN.md": ("DESIGN.md", "---\nname: Acme\n---\nplaceholder\n"),
    "LAUNCH.md": ("LAUNCH.md", "# launch\n\nplaceholder\n"),
    "applied skill": (".claude/skills/acme-brand/SKILL.md", "---\nname: acme-brand\n---\nplaceholder\n"),
    "FAMILY.md": ("FAMILY.md", "# FAMILY\n\nplaceholder\n"),
    "latest round": ("rounds/r2/board.html", "<p>placeholder</p>\n"),
    "social build html": ("assets/social/_build/github-social.html", "<p>placeholder</p>\n"),
    "social post build html": ("assets/social/_build/posts/launch.html", "<p>placeholder</p>\n"),
    "apple frame build html": ("assets/apple/_build/frame-1.html", "<p>placeholder</p>\n"),
}


def write(p: Path, rel_: str, text: str):
    f = p / rel_
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    return f


@pytest.mark.parametrize("where", sorted(PLANT))
def test_the_old_value_is_found_in_every_kind_of_project_artefact(proj, where):
    rel_, body = PLANT[where]
    f = write(proj, rel_, body)
    write(proj, "rounds/r1/board.html", "<p>earlier round</p>\n")
    r = bc("check", "--cascade", OLD, project=proj)
    assert row(proj, f"cascade:{OLD}")["status"] == "pass", "the plant is not there yet: the baseline must pass"
    mutate(f, "placeholder", f"the old value {OLD} is still here")
    r = bc("check", "--cascade", OLD, project=proj)
    cas = row(proj, f"cascade:{OLD}")
    assert r.returncode == 1 and cas["status"] == "fail", r.stdout
    assert any(h.startswith(rel_ + ":") for h in cas["hits"]) and rel_ in cas["detail"]


def test_what_records_a_decision_or_is_generated_or_frozen_is_not_searched(proj):
    for rel_, body in {"history/2026-10-17-x/board.html": f"<p>{OLD}</p>", "decisions/ADR-1.md": f"{OLD}\n", "DECISIONS.md": f"{OLD}\n",
                       "removed-2026-10-17/book.html": f"<p>{OLD}</p>", "assets/_checks/x.json": json.dumps({"detail": OLD}), "assets/manifest.json": json.dumps({"artefacts": [], "note": OLD})}.items():
        assert OLD in write(proj, rel_, body).read_text()
    write(proj, "rounds/r1/board.html", f"<p>{OLD}</p>")
    write(proj, "rounds/r2/board.html", "<p>latest</p>")
    mutate(proj / "BRAND-STATE.md", "## Notes", f"## Notes\n\n{OLD} was decided against.")
    bc("check", "--cascade", OLD, project=proj)       # other gates may fail here (a history folder nobody froze): only the cascade row is the point
    cas = row(proj, f"cascade:{OLD}")
    assert cas["status"] == "pass" and cas["hits"] == [] and "history/, decisions, BRAND-STATE.md" in row(proj, "cascade:scope")["detail"]


def test_a_document_outside_the_project_is_searched_when_named_and_a_missing_one_fails(proj, tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "README.md").write_text(f"The family says {OLD}.\n")
    (parent / "sub").mkdir()
    (parent / "sub" / "rules.md").write_text("placeholder\n")
    assert bc("check", "--cascade", OLD, project=proj).returncode == 0                      # not named: not searched
    (proj / "tools").mkdir(exist_ok=True)
    (proj / "tools" / "cascade.json").write_text(json.dumps({"schema": 1, "also": ["../parent/README.md", "../parent/sub"]}))
    r = bc("check", "--cascade", OLD, project=proj)
    cas = row(proj, f"cascade:{OLD}")
    assert r.returncode == 1 and cas["hits"] == ["also:../parent/README.md:1"]
    assert (parent / "README.md").read_text() == f"The family says {OLD}.\n"                # read only
    mutate(parent / "sub" / "rules.md", "placeholder", f"{OLD} again")
    cas = (bc("check", "--cascade", OLD, project=proj), row(proj, f"cascade:{OLD}"))[1]
    assert "also:../parent/sub/rules.md:1" in cas["hits"]
    mutate_json(proj / "tools" / "cascade.json", lambda d: d["also"].append("../parent/gone.md"))
    r = bc("check", "--cascade", "nothing", project=proj)
    assert r.returncode == 1 and "gone.md" in row(proj, "cascade:also")["detail"]
    mutate_json(proj / "tools" / "cascade.json", lambda d: d.update({"colour": 1}))
    r = bc("check", "--cascade", "nothing", project=proj)
    assert r.returncode == 2 and "unknown key" in r.stderr


def test_the_parent_documents_of_a_family_file_and_the_also_flag_are_searched(proj, tmp_path):
    parent = tmp_path / "family"
    parent.mkdir()
    (parent / "FAMILY.md").write_text(f"parent rule: {OLD}\n")
    block = '{"schema": 1, "family": "F", "parent_docs": ["../family/FAMILY.md"]}'
    (proj / "FAMILY.md").write_text(f"# FAMILY: F\n\n```json family-check\n{block}\n```\n")
    r = bc("check", "--cascade", OLD, project=proj)
    assert r.returncode == 1 and row(proj, f"cascade:{OLD}")["hits"] == ["also:../family/FAMILY.md:1"]
    (proj / "FAMILY.md").write_text("# FAMILY: F\n")
    assert bc("check", "--cascade", OLD, project=proj).returncode == 0
    r = bc("check", "--cascade", OLD, "--also", str(parent / "FAMILY.md"), project=proj)
    assert r.returncode == 1
    assert bc("check", "--also", str(parent), project=proj).returncode == 2


def test_a_flag_that_ignores_case_finds_the_other_spellings(proj):
    write(proj, "README.md", f"{OLD.upper()} here\n")
    assert bc("check", "--cascade", OLD, project=proj).returncode == 0
    assert bc("check", "--cascade", OLD, "--ignore-case", project=proj).returncode == 1


def test_adoption_records_of_the_old_value_warn_and_do_not_fail(proj):
    write(proj, "ADOPTION.md", f"# adoption\n\n| 1 | to do | `README.md` | `{OLD}` | x | <!-- target-repo -->\n")
    r = bc("check", "--cascade", OLD, project=proj)
    cas = row(proj, f"cascade:{OLD}")
    assert r.returncode == 0 and cas["status"] == "warn" and cas["recorded"] == 1 and "adoption work list" in cas["detail"]
    mutate(proj / "ADOPTION.md", "# adoption", f"# adoption of {OLD}")
    r = bc("check", "--cascade", OLD, project=proj)
    assert r.returncode == 1 and row(proj, f"cascade:{OLD}")["hits"] == ["ADOPTION.md:1"]      # a line that is not a record of a repository is a leftover


@pytest.mark.requires_rg
def test_the_old_values_inside_adoption_json_are_by_design_but_an_old_name_in_a_row_text_is_a_leftover(proj, tmp_path):
    repo = tmp_path / "shop"
    shutil.copytree(ROOT / "tests" / "fixtures" / "target-repo", repo)
    assert bc("adoption", "survey", "--repo", f"{repo}=shop", "--old-name", "Oldco", project=proj).returncode == 0
    doc = json.loads((proj / "adoption.json").read_text())
    assert "Oldco" in json.dumps(doc["terms"]) and any("Oldco" in r["find"] for r in doc["rows"])    # the old name is in the data: it is what was found
    r = bc("check", "--cascade", "Oldco", project=proj)
    cas = row(proj, "cascade:Oldco")
    assert r.returncode == 0 and cas["status"] == "warn" and cas["hits"] == [] and cas["recorded"] > 0
    mutate_json(proj / "adoption.json", lambda d: d["rows"][0].update({"change": "Rename Oldco to the new name"}))
    r = bc("check", "--cascade", "Oldco", project=proj)
    assert row(proj, "cascade:Oldco")["hits"] == ["adoption.json.rows[0].change"] and r.returncode == 1


def _pdf(text: str) -> bytes:
    """A one-page PDF with one line of text, written by hand (xref offsets computed)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    stream = f"BT /F1 12 Tf 10 50 Td ({text}) Tj ET"
    objs[3] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


@pytest.mark.requires_pdftotext
def test_a_pdf_is_searched_as_text_and_print_pdfs_are_said_to_hold_outlines(proj):
    f = proj / "book.pdf"
    f.write_bytes(_pdf("clean text"))
    assert bc("check", "--cascade", "STALEWORD", project=proj).returncode == 0
    f.write_bytes(_pdf("this STALEWORD survived"))
    assert b"STALEWORD" in f.read_bytes()
    r = bc("check", "--cascade", "STALEWORD", project=proj)
    assert r.returncode == 1 and row(proj, "cascade:STALEWORD")["hits"] == ["book.pdf (pdf text):1"]
    f.write_bytes(_pdf("clean text"))
    write(proj, "assets/print/card.rgb-proof.pdf", "%PDF-1.4 outlined")
    r = bc("check", "--cascade", "STALEWORD", project=proj)
    assert r.returncode == 0 and "print PDF(s) (their text is outlines" in row(proj, "cascade:scope")["detail"]


def test_a_pdf_that_cannot_be_read_as_text_is_not_verified_never_a_pass(proj, tmp_path):
    (proj / "book.pdf").write_bytes(_pdf("anything"))
    path = path_without(tmp_path, "pdftotext")   # not "/usr/bin": on Linux that is where poppler lives
    r = bc("check", "--cascade", "STALEWORD", project=proj, env={"PATH": path})
    assert r.returncode == 3 and row(proj, "cascade:pdf")["status"] == "skipped" and "pdftotext" in row(proj, "cascade:pdf")["detail"]
