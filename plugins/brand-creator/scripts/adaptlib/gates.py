"""What `brand-creator check` gates for the stage-4c artefacts: adoption.json and ADOPTION.md, BRAND.md and DESIGN.md, the applied skill or the brand kit around it.

Each is a generated file: the report of the command that wrote it must be current and passing (the generic report gate in check.py), the file
must still be the bytes the report recorded (a hand edit fails), and the sources it was made from must not have changed (not verified when
they did). adoption.json is data: its pins, numbering and accounting are checked and ADOPTION.md must be what it renders. A repository with a wiring record
(`adoption wiring`) gets the row `adoption:wiring:<label>`: it fails when the after record lost an item of the before record that nobody dropped.
A project with a kit (kit.json in the skill folder) is gated through the `kit` report instead of the applied skill's: `kit:file` fails when a file the report recorded is gone
or is other bytes, `kit:state` says not verified when the brand changed after the build. The `kit-check` report (`kit check`) is expected as well, and `kit:checked` says not
verified when a file was added to the kit or taken out of it after that report.
"""
from __future__ import annotations

import json
from pathlib import Path

import adapt
import adoptdata as ad
import kitlib
from _common import CliError, Report, read_state, sha256_file


def present(project: Path) -> dict:
    """What the project has of the generated artefacts: the adapter files, and for the skill folder either the kit (its folder, relative, when kit.json is there) or the plain applied skill
    (its SKILL.md, relative): never both, because a kit's SKILL.md is the kit's to gate."""
    out = {"adapters": [f for f in (adapt.BRAND_FILE, adapt.DESIGN_FILE) if (project / f).is_file()], "skill": None, "kit": None}
    try:
        sp = f"{adapt.SKILL_DIR}/{adapt.skill_name(project)}/SKILL.md"
        if kitlib.exists(project):
            out["kit"] = kitlib.kit_rel(project)
        elif (project / sp).is_file():
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
    if p["kit"]:
        out.append(("kit", "brand-creator kit build --yes"))
        out.append(("kit-check", "brand-creator kit check"))
    return out


def _report(project: Path, tool: str) -> dict | None:
    """The report `tool` wrote, or None when there is none or it is no JSON object (the generic report gate of `check` says which)."""
    f = project / "assets" / "_checks" / f"{tool}.json"
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


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
        for _rid, label, entry in ([] if ad.verify_wiring(doc) else ad.wiring_records(doc)):   # a record of the wrong shape is adoption:data's to name
            after = entry.get("after")
            if not after:
                rep.add(f"adoption:wiring:{label}", "info", "the wiring is recorded before the redesign",
                        detail=f"only the before record exists: record --after when the redesign is applied (`brand-creator adoption wiring --repo {label} --after`)")
                continue
            lost, dropped = ad.wiring_lost(entry, after["items"])
            if lost:
                more = f" and {len(lost) - 5} more" if len(lost) > 5 else ""
                rep.add(f"adoption:wiring:{label}", "fail", "the redesign lost no wiring that nobody dropped",
                        detail=f"{len(lost)} item(s) of the before record are gone from the after record and nobody dropped them: {', '.join(lost[:5])}{more}. "
                               f"Put each back and record --after again, or record why it goes: `brand-creator adoption wiring --repo {label} --drop \"ITEM::REASON\"`")
            else:
                rep.add(f"adoption:wiring:{label}", "pass", "the redesign lost no wiring that nobody dropped",
                        detail=f"{len(entry['before']['items'])} items before, {len(after['items'])} after; {len(dropped)} dropped with a reason")
    p = present(project)
    if p["adapters"]:
        r = _report(project, "adapters")
        outs = (r or {}).get("outputs")
        outs = outs if isinstance(outs, dict) else {}
        for fname in p["adapters"]:
            if r is None:
                continue   # the generic report gate already says it is missing or no report
            rec = outs.get(fname)
            if not (isinstance(rec, dict) and isinstance(rec.get("sha256"), str)):
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
            rec = r.get("output")
            if not isinstance(rec, dict):
                rep.add("applied-skill:file", "fail", "the applied skill is the bytes `applied-skill` wrote",
                        detail="the applied-skill report records no output it wrote: run `brand-creator applied-skill --yes`")
            else:
                same = rec.get("path") == p["skill"] and sha256_file(project / p["skill"]) == rec.get("sha256")
                rep.add("applied-skill:file", "pass" if same else "fail", "the applied skill is the bytes `applied-skill` wrote",
                        detail="unchanged since it was generated" if same else f"{p['skill']} differs from what was generated: it was edited by hand. Change the sources and run `brand-creator applied-skill --yes`")
            if r.get("status") == "pass" and r.get("adapter_state_sha") != adapt.state_sha(project):
                rep.add("applied-skill:state", "skipped", "the applied skill was made from the current BRAND-STATE.md and FACTS.md",
                        detail="not verified: the name, rules, facts or motion spec changed since the applied-skill report; run `brand-creator applied-skill --yes` again")
    if p["kit"]:
        kit_rows(project, rep, p["kit"])
        kit_check_rows(project, rep)


def kit_rows(project: Path, rep: Report, kit: str) -> None:
    """kit:file and kit:state, from the `kit` report: every file it recorded writing is still there with the bytes it wrote, and the brand it was made from has not changed since."""
    r = _report(project, "kit")
    if r is None:
        return   # the generic report gate already says it is missing or no report
    again = "change the brand project and run `brand-creator kit build --yes`"
    outs = r.get("outputs")
    if not (isinstance(outs, dict) and outs):
        rep.add("kit:file", "fail", "the kit is the bytes `kit build` wrote", detail="the kit report records no outputs it wrote: run `brand-creator kit build --yes`")
    else:
        differ, odd = [], []
        for rel, sha in sorted(outs.items()):
            if not (kitlib.is_sha(sha) and kitlib.recorded_path(rel)):
                odd.append(rel)   # a record that is no sha256 of a file of the kit is named, never opened
                continue
            f = project / kit / rel
            if not f.is_file():
                differ.append(f"{rel} (missing)")
            elif sha256_file(f) != sha:
                differ.append(rel)
        if odd:
            rep.add("kit:file", "fail", "the kit is the bytes `kit build` wrote",
                    detail=f"the kit report holds {len(odd)} output record(s) that cannot be compared with a file of the kit ({', '.join(odd[:4])}): run `brand-creator kit build --yes`")
        elif differ:
            more = f", and {len(differ) - 4} more" if len(differ) > 4 else ""
            rep.add("kit:file", "fail", "the kit is the bytes `kit build` wrote",
                    detail=f"{len(differ)} kit file(s) differ from what was generated: {', '.join(differ[:4])}{more}. They were edited by hand or removed: {again}")
        else:
            rep.add("kit:file", "pass", "the kit is the bytes `kit build` wrote", detail=f"{len(outs)} generated files unchanged since they were generated")
    if r.get("status") == "pass":
        try:
            now = (adapt.state_sha(project), kitlib.sources_sha(project))
        except CliError as e:
            rep.add("kit:state", "skipped", "the kit was made from the brand as it is now", detail=f"not verified: the brand's sources cannot be read ({e.message}); run `brand-creator kit build --yes` again")
            return
        if (r.get("adapter_state_sha"), r.get("kit_sources_sha")) != now:
            rep.add("kit:state", "skipped", "the kit was made from the brand as it is now",
                    detail="not verified: the name, rules, facts, tokens, logos, band drawings, fonts, reference pages, masters or motion spec changed since the kit report; run `brand-creator kit build --yes` again")


def kit_check_rows(project: Path, rep: Report) -> None:
    """kit:checked, from the `kit-check` report: a passing report stands for the files it read (the generic report gate sees one that changed or went), not for a file added to the kit since,
    so the report records the kit's tree (`kit_tree_sha`) and this row says not verified when a file was added to the kit or taken out of it after `kit check` ran. No row while the tree matches."""
    r = _report(project, "kit-check")
    if r is None or r.get("status") != "pass":
        return   # the generic report gate already says it is missing, failing or stale
    try:
        now = kitlib.tree_sha(project)
    except CliError:
        return
    if r.get("kit_tree_sha") != now:
        rep.add("kit:checked", "skipped", "the kit is the one `kit check` read",
                detail="not verified: a file was added to the kit, or taken out of it, after the kit-check report; run `brand-creator kit check` again")
