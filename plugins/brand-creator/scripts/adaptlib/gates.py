"""What `brand-creator check` gates for the stage-4c artefacts: adoption.json and ADOPTION.md, BRAND.md and DESIGN.md, the applied skill.

Each is a generated file: the report of the command that wrote it must be current and passing (the generic report gate in check.py), the file
must still be the bytes the report recorded (a hand edit fails), and the sources it was made from must not have changed (not verified when
they did). adoption.json is data: its pins, numbering and accounting are checked and ADOPTION.md must be what it renders.
"""
from __future__ import annotations

import json
from pathlib import Path

import adapt
import adoptdata as ad
from _common import CliError, Report, read_state, sha256_file


def present(project: Path) -> dict:
    out = {"adapters": [f for f in (adapt.BRAND_FILE, adapt.DESIGN_FILE) if (project / f).is_file()], "skill": None}
    try:
        sp = f"{adapt.SKILL_DIR}/{adapt.skill_name(project)}/SKILL.md"
        if (project / sp).is_file():
            out["skill"] = sp
    except CliError:
        pass
    return out


def expected_reports(project: Path) -> list[tuple[str, str]]:
    p = present(project)
    out = []
    if p["adapters"]:
        out.append(("adapters", "brand-creator adapters --brand-md --design-md"))
    if p["skill"]:
        out.append(("applied-skill", "brand-creator applied-skill --yes"))
    return out


def _report(project: Path, tool: str) -> dict | None:
    f = project / "assets" / "_checks" / f"{tool}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except ValueError:
        return None


def rows(project: Path, rep: Report) -> None:
    doc = ad.load(project) if (project / ad.FILE).is_file() else None
    if doc is not None:
        bad = ad.verify(doc)
        name = str(read_state(project).get("name", "") or read_state(project).get("slug", "") or "Brand")
        f = project / ad.DOC
        if not f.is_file():
            bad.append(f"{ad.DOC} is missing: run `brand-creator adoption render`")
        elif f.read_text(encoding="utf-8") != ad.render(doc, name):
            bad.append(f"{ad.DOC} is not what adoption.json renders: it was edited by hand (progress goes through `adoption status`, rows through `adoption survey`)")
        rep.add("adoption:data", "fail" if bad else "pass", "adoption.json is consistent and ADOPTION.md is what it renders",
                detail="; ".join(bad[:4]) if bad else f"{len(doc['rows'])} rows, pins match; {ad.sentence(doc)}")
        still, _gone = ad.drift(doc)
        if still:
            rep.add("adoption:drift", "warn", "rows marked done still match at the last survey", detail=f"row(s) {ad.ranges(still)}: survey again, or the change is not finished")
    p = present(project)
    if p["adapters"]:
        r = _report(project, "adapters")
        outs = (r or {}).get("outputs", {})
        for fname in p["adapters"]:
            if r is None:
                continue   # the generic report gate already says it is missing
            rec = outs.get(fname)
            if rec is None:
                rep.add(f"adapters:{fname}", "fail", f"{fname} was written by `brand-creator adapters`", detail=f"{fname} exists but the adapters report does not record writing it: run `brand-creator adapters`")
            elif sha256_file(project / fname) != rec["sha256"]:
                rep.add(f"adapters:{fname}", "fail", f"{fname} is the bytes `adapters` wrote",
                        detail=f"{fname} differs from what was generated: it was edited by hand. Change the sources and run `brand-creator adapters`")
            else:
                rep.add(f"adapters:{fname}", "pass", f"{fname} is the bytes `adapters` wrote", detail="unchanged since it was generated")
        if r is not None and r.get("status") == "pass" and r.get("adapter_state_sha") != adapt.state_sha(project):
            rep.add("adapters:state", "skipped", "the adapters were made from the current BRAND-STATE.md and FACTS.md",
                    detail="not verified: the name, architecture, edition, approval, rules, facts or motion spec changed since the adapters report; run `brand-creator adapters` again")
    if p["skill"]:
        r = _report(project, "applied-skill")
        if r is not None:
            rec = r.get("output", {})
            same = rec.get("path") == p["skill"] and sha256_file(project / p["skill"]) == rec.get("sha256")
            rep.add("applied-skill:file", "pass" if same else "fail", "the applied skill is the bytes `applied-skill` wrote",
                    detail="unchanged since it was generated" if same else f"{p['skill']} differs from what was generated: it was edited by hand. Change the sources and run `brand-creator applied-skill --yes`")
            if r.get("status") == "pass" and r.get("adapter_state_sha") != adapt.state_sha(project):
                rep.add("applied-skill:state", "skipped", "the applied skill was made from the current BRAND-STATE.md and FACTS.md",
                        detail="not verified: the name, rules, facts or motion spec changed since the applied-skill report; run `brand-creator applied-skill --yes` again")
