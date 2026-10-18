#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator launch-todo: LAUNCH.md, the owner's checklist before the name and the brand go public.

Written from files already in the project, in this order: trademark first (the owner-run register links of the names screening), domains and
handles with the date they were checked ("recheck before buying"), e-mail, the repository, package and app-id renames (the identifiers the
adoption survey read), the print hand-off when print files exist, and the decisions that are the owner's. templates/LAUNCH.md holds the frame.

It reads local files only. Nothing outward is ever executed: no purchase, no filing, no registration, no account, no message, no network call
(the module imports no network library, and a test checks that). Boxes you ticked in an earlier LAUNCH.md stay ticked (they are matched by the
id in the comment at the end of each box), so the file can be generated again after a new names run or adoption survey.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "booklib"))
sys.path.insert(0, str(HERE / "adaptlib"))
import adoptdata as ad  # noqa: E402
import bookdata  # noqa: E402
from _common import (EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard, plugin_root, read_state,  # noqa: E402
                     write_bytes_if_changed)

DOC = "LAUNCH.md"
ID_RE = re.compile(r"<!-- id:([A-Za-z0-9_.:-]+) -->")
BOX_RE = re.compile(r"\[( |x|X)\]")
REGISTRY_ORDER = ["npm", "github", "docker-org", "docker-user", "pypi", "crates", "brew-formula", "brew-cask"]
REGISTRY_LABEL = {"npm": "npm package", "github": "GitHub user or org", "docker-org": "Docker Hub org", "docker-user": "Docker Hub user",
                  "pypi": "PyPI project", "crates": "crates.io crate", "brew-formula": "Homebrew formula", "brew-cask": "Homebrew cask"}
RECHECK = "recheck before buying"


def old_ticks(project: Path) -> dict[str, bool]:
    f = project / DOC
    out: dict[str, bool] = {}
    if f.is_file():
        for ln in f.read_text(encoding="utf-8").splitlines():
            ids, box = ID_RE.findall(ln), BOX_RE.findall(ln)
            if len(ids) == 1 and len(box) == 1:
                out[ids[0]] = box[0].lower() == "x"
    return out


class Boxes:
    def __init__(self, ticks: dict[str, bool]):
        self.ticks, self.used = ticks, []

    def box(self, id_: str) -> str:
        if id_ in self.used:
            fail(EXIT_USAGE, f"internal error: box id {id_} used twice")
        self.used.append(id_)
        return "[x]" if self.ticks.get(id_) else "[ ]"

    def item(self, id_: str, text: str) -> str:
        return f"- {self.box(id_)} {text} <!-- id:{id_} -->"


def cell(t) -> str:
    return re.sub(r"\s+", " ", str(t)).replace("|", "\\|").strip()


def names_report(project: Path):
    f = project / "assets" / "_checks" / "names.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def pick_candidate(rep: dict, wanted: str | None, slug: str) -> str:
    cands = rep.get("candidates", [])
    if wanted:
        if wanted not in cands:
            fail(EXIT_USAGE, f"--name {wanted!r} is not in the names screening (candidates: {', '.join(cands)}); run `brand-creator names {wanted}` first")
        return wanted
    if len(cands) == 1:
        return cands[0]
    if slug in cands:
        return slug
    fail(EXIT_USAGE, f"the names screening has several candidates ({', '.join(cands)}) and none is the project slug: say which with --name")


def verdict_seed(project: Path) -> list[str]:
    files = sorted((project / "research" / "names").glob("*-verdict.md")) if (project / "research" / "names").is_dir() else []
    if not files:
        return []
    out, inside = [], False
    for ln in files[-1].read_text(encoding="utf-8").splitlines():
        if re.match(r"^##\s+", ln):
            inside = ln.lower().startswith("## launch todo")
            continue
        m = re.match(r"^- \[[ xX]\]\s+(.*\S)\s*$", ln) if inside else None
        if m:
            out.append(m.group(1))
    return out


def sec_trademark(bx: Boxes, project: Path, rep, cand, notes: list) -> str:
    if rep is None:
        notes.append(("names", "warn", "no names screening on file", "run `brand-creator names <name> --plan` (and then `--yes` once the owner agrees to send the names), then generate this file again"))
        return ("No name screening is on file, so there are no register links here. Run `brand-creator names <name>` (it lists which services receive the name and "
                "needs your OK first), then generate this file again.\n\n" + bx.item("tm-search", "Search the trademark registers of your market (and the EU and WIPO) for the name, in the classes that match what you sell"))
    L = [f"Name screened: **{cand}**. Region: {rep.get('region') or 'not given'}. Screening checked {rep.get('checked')}. {RECHECK[0].upper() + RECHECK[1:]}: registers change daily.", ""]
    links = next((t["links"] for t in rep.get("trademark_links", []) if t["candidate"] == cand), [])
    for i, lk in enumerate(links, 1):
        L.append(bx.item(f"tm-link-{i}", f"{lk['office']} ({lk['kind']}): {lk['url']} ({lk['note']})"))
    if not links:
        notes.append(("trademark", "warn", "no register links for the name", "the names report holds none for it"))
    L.append(bx.item("tm-decide", "Decide, with your attorney if you use one, whether to file and in which classes; record the answer in the decisions below"))
    seed = verdict_seed(project)
    if seed:
        L += ["", "From the naming memo's launch seed:", ""] + [bx.item(f"seed-{i}", t) for i, t in enumerate(seed, 1)]
    return "\n".join(L)


def sec_domains(bx: Boxes, rep, cand) -> str:
    if rep is None:
        return "No screening on file: nothing to list. Run `brand-creator names <name>` first."
    cells = [r for r in rep["results"] if r.get("candidate") == cand and str(r.get("source", "")).startswith(".")]
    date = rep.get("checked", "")
    L = [f"Checked {date}, {RECHECK}. The state is what the registry answered that day (REGISTERED, NOT-FOUND or UNKNOWN). NOT-FOUND is not a promise "
         "that the domain can be bought: price, reserved and premium names and pending releases are not covered.", "",
         f"| domain | state on {date} | your decision |", "|---|---|---|"]
    for r in cells:
        L.append(f"| {cand}{r['source']} | {r['state']} | {bx.box('dom' + r['source'])} buy <!-- id:dom{r['source']} --> |")
    if not cells:
        L.append("| (no domain was screened) | | |")
    return "\n".join(L)


def sec_handles(bx: Boxes, rep, cand) -> str:
    if rep is None:
        return "No screening on file: nothing to list."
    date = rep.get("checked", "")
    cells = {r["source"]: r for r in rep["results"] if r.get("candidate") == cand and not str(r.get("source", "")).startswith(".")}
    L = [f"Checked {date}, {RECHECK}.", ""]
    if cells:
        L += [f"| where | name | state on {date} | your decision |", "|---|---|---|---|"]
        for s in [x for x in REGISTRY_ORDER if x in cells] + sorted(set(cells) - set(REGISTRY_ORDER)):
            L.append(f"| {REGISTRY_LABEL.get(s, s)} | {cand} | {cells[s]['state']} | {bx.box('handle-' + s)} take it up <!-- id:handle-{s} --> |")
    manual = next((m["links"] for m in rep.get("manual_links", []) if m["candidate"] == cand), [])
    if manual:
        L += ["", "Social handles are not checked by any program; look yourself:", ""]
        L += [bx.item(f"social-{re.sub(r'[^a-z0-9]+', '-', m['service'].lower()).strip('-')}", f"{m['service']}: {m['url']}") for m in manual]
    if not cells and not manual:
        L.append("The screening profile did not check registries; the profile `software` does.")
    return "\n".join(L)


def sec_email(bx: Boxes, project: Path) -> str:
    facts = bookdata.facts(project)
    have = bookdata.fact_value(facts, "contact email")
    L = [f"FACTS.md `contact email`: {have if have else 'no row yet'}.", ""]
    L.append(bx.item("mail-domain", "Choose the domain the mailboxes live on (the domain decision above comes first)"))
    L.append(bx.item("mail-box", "Create the mailbox the stationery, the e-mail signature and the site will show, then add a `contact email` row to FACTS.md"))
    L.append(bx.item("mail-spf", "Set up SPF, DKIM and DMARC for the domain with your mail provider"))
    return "\n".join(L)


def sec_deploy(bx: Boxes, project: Path) -> str:
    doc = ad.load(project)
    mf = project / "assets" / "manifest.json"
    web = [r for r in (json.loads(mf.read_text(encoding="utf-8")).get("artefacts", []) if mf.is_file() else []) if r["path"].startswith("assets/web/")]
    L = [bx.item("deploy-first", "Decide what goes live first and on which host"),
         bx.item("deploy-dns", "Point the domain you bought at it (the DNS records are yours to set; allow time for them to spread)")]
    L.append(bx.item("deploy-web", f"Put the web files of the pack ({len(web)} under `assets/web/`) and the Open Graph card on the site" if web
                     else "Put the pack's web files and the Open Graph card on the site (the web pack is not built yet: `brand-creator emit web`)"))
    if doc is not None:
        c = ad.counts(doc)
        L.append(bx.item("deploy-adopt", f"Finish the adoption list before the name goes public: ADOPTION.md has {c['done']} of {sum(c.values())} rows done"))
    else:
        L.append(bx.item("deploy-adopt", "Adopt the brand in your product repositories before the name goes public (`brand-creator adoption survey`)"))
    return "\n".join(L)


def sec_renames(bx: Boxes, project: Path) -> str:
    doc = ad.load(project)
    L = []
    if doc is None or not doc.get("identifiers"):
        L += ["No adoption survey with identifiers is on file: run `brand-creator adoption survey --repo <dir>` to list the repository, package and app-id names that carry the old name."
              if doc is None else "The adoption survey found no package, bundle or app identifiers."]
    else:
        L += [f"Identifiers read by the adoption survey of {doc['survey'].get('date')}. The new value is yours to choose; renaming a repository or a package id is an outward step "
              "(the host redirects old addresses, a store treats a changed id as a new app).", "",
              "| repo | where | what | current value | new value (yours) | done |", "|---|---|---|---|---|---|"]
        for it in doc["identifiers"]:
            rid = "rename-" + hashlib.sha1(f"{it['repo']}|{it['file']}|{it['what']}".encode()).hexdigest()[:8]
            L.append(f"| {cell(ad.repo_label(doc, it['repo']))} | `{cell(it['file'])}` | {cell(it['what'])} | `{cell(it['value'])}` |  | "
                     f"{bx.box(rid)} <!-- id:{rid} --> {ad.MARK}")
        L += [""]
        L += [bx.item(f"rename-repo-{r['id']}", f"Rename the repository `{r['label']}` on its host (the host redirects the old address) {ad.MARK}") for r in doc["repos"]]
    return "\n".join(L)


def sec_print(bx: Boxes, project: Path) -> str:
    mf = project / "assets" / "manifest.json"
    rows = [r for r in json.loads(mf.read_text(encoding="utf-8")).get("artefacts", []) if r.get("emitter") == "print" and r["path"].endswith(".pdf")] if mf.is_file() else []
    if not rows:
        return ""
    L = ["## Print hand-off", "",
         "The files below are the pack's print PDFs. A file named `rgb-proof` is an RGB proof, not print-ready; a file named `pdfx4-candidate` is a candidate that "
         "the printer must preflight. Nothing in brand-creator can check PDF/X conformance.", ""]
    L += [f"- `{r['path']}`" for r in sorted(rows, key=lambda r: r["path"])]
    L += ["", bx.item("print-printer", "Choose the printer and ask for their file requirements: bleed, safe distance, output profile, PDF/X version (the pack's default bleed is a proposal, not theirs)"),
          bx.item("print-profile", "Get the printer's CMYK output profile and re-run `emit print --icc <profile>`; brand-creator bundles none"),
          bx.item("print-preflight", "Preflight the files with the printer's own tool or the printer's check"),
          bx.item("print-proof", "Get the printer's proof and approve it before the run: screen colours are not the print"),
          "", "Spot colours: record each as the ink's name plus its Lab target, measured from the printer's swatch book or proof; a hex value never equals a spot ink.", ""]
    try:
        doc, _ = bookdata.tokens(project)
        L += ["| role | screen value (light) | spot ink name | Lab target |", "|---|---|---|---|"]
        for k in sorted(doc["modes"]["light"]):
            L.append(f"| {k[6:] if k.startswith('color.') else k} | {doc['modes']['light'][k]['hex']} |  |  |")
        L.append("")
    except Exception:   # tokens not built: the table is simply not offered
        pass
    return "\n".join(L) + "\n"


def sec_decisions(bx: Boxes, project: Path) -> str:
    st = read_state(project)
    fixed = ["Is the name approved for use? (the answer of the trademark step; screening is not clearance)",
             "Which domain is primary, and which defensive ones to buy",
             "The new repository, package and app-id names (the list above)",
             "Which registries and handles to take up"]
    L = [bx.item(f"decide-{i}", t) for i, t in enumerate(fixed, 1)]
    open_ = bookdata.bullets(bookdata.section_lines(st, "Still open"))
    open_ += [m.group(1).strip() for ln in bookdata.section_lines(st, "Still open") if (m := re.match(r"^\s*\d+[.)]\s+(.*\S)\s*$", ln))]
    open_ = [t for t in dict.fromkeys(open_) if not re.search(r"\(\.\.\.\)", t)]
    if open_:
        L += ["", "Carried over from BRAND-STATE.md, Still open:", ""] + [bx.item(f"open-{i}", t) for i, t in enumerate(open_, 1)]
    return "\n".join(L)


def main() -> int:
    ap = Parser(prog="brand-creator launch-todo", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--name", help="the candidate of the names screening this list is for (default: the only one, or the project slug)")
    a = ap.parse_args()
    project = find_project(a.project)
    st = read_state(project)
    name = str(st.get("name", "") or st.get("slug", "") or "Brand")
    tpl = plugin_root() / "templates" / "LAUNCH.md"
    if not tpl.is_file():
        fail(EXIT_USAGE, f"template missing: {tpl}")
    rep_in = Report("launch-todo", project, renderer="n/a (generated text)")
    notes: list = []
    nrep = names_report(project)
    cand = pick_candidate(nrep, a.name, str(st.get("slug", ""))) if nrep else None
    for f in (project / "assets" / "_checks" / "names.json", project / ad.FILE, project / "FACTS.md", project / "assets" / "manifest.json"):
        if f.is_file():
            rep_in.inputs.append(f)
    bx = Boxes(old_ticks(project))
    sections = {"trademark": sec_trademark(bx, project, nrep, cand, notes), "domains": sec_domains(bx, nrep, cand), "handles": sec_handles(bx, nrep, cand),
                "email": sec_email(bx, project), "deploy": sec_deploy(bx, project), "renames": sec_renames(bx, project), "print": sec_print(bx, project), "decisions": sec_decisions(bx, project)}
    out = tpl.read_text(encoding="utf-8").replace("{{name}}", name)
    total = len(bx.used)
    ticked = sum(1 for i in bx.used if bx.ticks.get(i))
    sections["progress"] = f"Progress: {ticked} of {total} boxes ticked."
    for k, v in sections.items():
        out = out.replace("{{" + k + "}}", v + ("\n" if k == "print" and v else ""))
    left = re.findall(r"\{\{[a-z]+\}\}", out)
    if left:
        fail(EXIT_USAGE, f"internal error: placeholders left in the template: {left}")
    out = re.sub(r"\n{3,}", "\n\n", out).rstrip("\n") + "\n"
    stale = sorted(set(bx.ticks) - set(bx.used))
    changed = write_bytes_if_changed(confine(project, DOC, what=DOC), out.encode("utf-8"))
    rep_in.add("launch:written", "pass", f"{DOC} generated", detail=("written" if changed else "unchanged") + f", {total} boxes, {ticked} ticked")
    for k, st_, label, detail in notes:
        rep_in.add(f"launch:{k}", st_, label, detail=detail)
    if stale:
        rep_in.add("launch:ticks", "warn", "boxes ticked earlier that no longer exist", detail=f"{len(stale)} id(s) dropped: {', '.join(stale[:6])}")
    rep_in.add("launch:outward", "info", "nothing outward was executed", detail="this command reads local files and writes LAUNCH.md only")
    return rep_in.finish()


main_guard(main)
