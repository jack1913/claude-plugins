"""The rows of a motion board (data-board="motion"): a round after G3 that tries the signature move as variants, each a page of its own.

A motion round is one folder per variant, rounds/rN/<name>/: index.html (the move where it will be seen, the approved mark in place), proof.json (a page case named <name> whose
page is that index.html and whose static is an approved master of assets/logo/) and the stills `frames` took of it (frames/<name>/strip.png, reduced.png, frames.json; its report says
they are of the page as it is now). The board shows one card per variant, an element with
data-motion-variant="<name>": the strip and the reduced still (data-field="strip" and "reduced", both <img>), a link to the live page (data-field="live"), a proof line
(data-proof="pass|fail" and its text) and the fields What it is, Cost and Degrades to (data-field="what-it-is", "cost", "degrades-to"). Each row is one result for the whole board
and names the variants it fails (scripts/CONTRACT.md, "Board contract"). The folder of boardlib is outside scripts/lib/, so a change here does not make every pack stale.
Standard library only; no clock and no network.
"""
from __future__ import annotations

import base64
import binascii
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, unquote_to_bytes

from _common import CliError, Report, confine, frames_report_tool, gate_recorded, motion_report_tool, rel, sha256_bytes, sha256_file, stale_inputs
from boardpage import FILL, GENERIC_NAME, WORD_NAME, Node
import motionspec

ATTR = "data-motion-variant"
FIRST_COUNT = 3   # the first motion board of a project shows exactly this many variants; a later one (the refine loop) shows one or more
FIELDS = (("what-it-is", "What it is"), ("cost", "Cost"), ("degrades-to", "Degrades to"))
FOLDER_NAME = re.compile(r"[A-Za-z0-9_-]+")   # the name is also the folder rounds/rN/<name>/ and the case folder frames/<name>/ (`frames` keeps only these characters)


def cards(root: Node) -> list[Node]:
    """The variant cards of a page: every element that carries data-motion-variant, in page order."""
    return [n for n in root.walk() if ATTR in n.attrs]


class Variant:
    """One variant of the round: its name, its card on the page and where its files are (project-relative, posix)."""

    def __init__(self, rnd: int, name: str, card: Node):
        self.name, self.card = name, card
        self.dir = f"rounds/r{rnd}/{name}"
        self.proof = f"{self.dir}/proof.json"
        self.frames = f"{self.dir}/frames/{name}"
        self.report = f"assets/_checks/{motion_report_tool(self.proof)}.json"
        self.frames_report = f"assets/_checks/{frames_report_tool(self.proof)}.json"


def shown(problems: list[str], limit: int = 6) -> str:
    return "; ".join(problems[:limit]) + (f"; and {len(problems) - limit} more" if len(problems) > limit else "")


def add_row(rep: Report, rid: str, label: str, problems: list[str], passed: str) -> None:
    rep.add(rid, "fail" if problems else "pass", label, detail=shown(problems) if problems else passed)


# ---------------------------------------------------------------- the gates of the round

def motion_off(project: Path) -> tuple[bool | None, str]:
    """(whether motion/motion.json says nothing moves, the reason it gives), read as `brand-creator motion` and `state` read it (motionspec.decision): one that `motion` refuses is never read
    as "nothing moves" here, so it is (None, the message of the motion spec). A refused file that says "on" is (False, that message): it cannot record that nothing moves, whatever else is wrong
    with it (check fails it in motion:spec). Absent is not off."""
    try:
        d = motionspec.decision(project)
    except CliError as e:
        return (False if says_on(project) else None), e.message
    return d["motion"] == "off", motionspec.one_line(d.get("reason", ""))


def says_on(project: Path) -> bool:
    """Whether motion/motion.json is a JSON object whose "motion" is "on", valid in itself or not."""
    try:
        doc = json.loads((project / motionspec.FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and doc.get("motion") == "on"


def gate_rows(rep: Report, project: Path) -> None:
    """motion:g3 (a motion round follows the approved design) and motion:off (it contradicts a recorded "nothing moves")."""
    g3 = gate_recorded(project, "G3")
    rep.add("motion:g3", "pass" if g3 else "fail", "a motion round follows the approved design (G3)",
            detail=f"G3: {g3}" if g3 else "a motion round follows the approved design (G3): record the owner's approval of the refined board first (`brand-creator state --record G3 \"<decision>\"`)")
    off, why = motion_off(project)
    if (project / motionspec.FILE).is_file():   # the lint report is stale once the answer changes (on to off, say): `check` asks for the lint again
        rep.inputs.append(project / motionspec.FILE)
    label = "a motion round does not contradict a recorded \"nothing moves\""
    if off is None:
        rep.add("motion:off", "skipped", label, detail=f"not verified: {why}; `brand-creator motion` refuses the file with the same message: fix it, then lint again")
    elif off:
        rep.add("motion:off", "fail", label, detail=f"nothing moves is recorded: a motion round contradicts it ({motionspec.FILE}: {why}); turning it on is a rule change: edit {motionspec.FILE}, "
                                                    "then run `brand-creator check --cascade` with the old wording as its value")
    elif why:   # it says "on" but `motion` refuses it: no contradiction, and the error is said here too
        rep.add("motion:off", "pass", label, detail=f"{motionspec.FILE} says the brand moves, so it records no \"nothing moves\"; it is not valid in itself ({why}): "
                                                    "fix it, `brand-creator check` fails it in motion:spec")
    else:
        rep.add("motion:off", "pass", label, detail=f"{motionspec.FILE} does not say nothing moves" if (project / motionspec.FILE).is_file() else "no motion/motion.json: motion is not decided yet")


# ---------------------------------------------------------------- the variants and their files

def name_problems(found: list[Node], first: bool) -> tuple[list[str], list[tuple[str, Node]]]:
    """-> (what is wrong with the count and the names of the cards, the cards whose name can be a variant: (name, card))."""
    problems: list[str] = []
    if first and len(found) != FIRST_COUNT:
        problems.append(f"{len(found)} variant card(s) found, the first motion board of a project shows exactly {FIRST_COUNT}")
    if not first and not found:
        problems.append("no variant card found, a later motion board shows 1 or more")
    named: list[tuple[str, Node]] = []
    seen: list[str] = []
    for i, card in enumerate(found, 1):
        nm = card.attrs.get(ATTR, "").strip()
        label = nm or f"#{i}"
        if not WORD_NAME.match(nm) or GENERIC_NAME.match(nm):
            problems.append(f'{label}: {ATTR} must be a word of 3+ letters (not "A", "Variant 2", "Option B")')
        elif not FOLDER_NAME.fullmatch(nm):
            problems.append(f"{label}: the name is also the folder rounds/rN/<name>/: letters, digits, - and _ only")
        elif nm.lower() in seen:
            problems.append(f"{nm}: duplicate variant name")
        else:
            named.append((nm, card))
        seen.append(nm.lower())
    return problems, named


def proof_problems(project: Path, v: Variant) -> list[str]:
    """What is wrong with a variant's proof.json: a page case named after the variant that proves the page the card links, the variant's index.html (a proof copied from an earlier round
    still points at the old one), and compares the rest frame with an approved master of assets/logo/ (a variant has no still of its own)."""
    try:
        doc = json.loads((project / v.proof).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{v.name}: {v.proof} cannot be read as JSON ({e})"]
    cases = doc.get("cases") if isinstance(doc, dict) else None
    if not isinstance(cases, list):
        return [f'{v.name}: {v.proof} has no list of cases ({{"schema": 1, "cases": [...]}})']
    case = next((c for c in cases if isinstance(c, dict) and c.get("name") == v.name), None)
    if case is None:
        have = ", ".join(str(c.get("name")) for c in cases if isinstance(c, dict)) or "none"
        return [f"{v.name}: {v.proof} has no case named {v.name} (it has: {have})"]
    if case.get("type") != "page":
        return [f"{v.name}: the case {v.name} of {v.proof} is not a page case (type {json.dumps(case.get('type'))})"]
    page = case.get("page")
    if not (isinstance(page, str) and page.strip()):
        return [f"{v.name}: the page case of {v.proof} names no page"]
    out = []
    if posixpath.normpath(page.strip()) != f"{v.dir}/index.html":
        out.append(f"{v.name}: the page case of {v.proof} shows {page}, not {v.dir}/index.html, the page the card links (a proof copied from an earlier round and not updated: point its page at {v.dir}/index.html)")
    still = case.get("static")
    if not (isinstance(still, str) and still.strip()):
        out.append(f"{v.name}: the page case of {v.proof} names no static (the approved master, for example assets/logo/mark.svg)")
    elif not posixpath.normpath(still.strip()).startswith("assets/logo/"):
        out.append(f"{v.name}: the static {still} of {v.proof} is not an approved master of assets/logo/ (the rest frame is compared with the approved mark, never with a still of the variant's own)")
    elif not (project / posixpath.normpath(still.strip())).is_file():
        out.append(f"{v.name}: the static {still} of {v.proof} does not exist")
    return out


def link_problem(v: Variant, page_rel: str, rnd: int) -> str | None:
    """The card links the live page: an <a data-field="live"> with an href; on the board of the round itself (rounds/rN/board.html) it leads to the variant's index.html."""
    links = list(v.card.find_all(data_field="live"))
    href = links[0].attrs.get("href", "").strip() if links else ""
    if not href:
        return f'{v.name}: the card has no link to the live page (<a data-field="live" href="{v.name}/index.html">)'
    if posixpath.dirname(page_rel) == f"rounds/r{rnd}":
        target = posixpath.normpath(posixpath.join(f"rounds/r{rnd}", re.split(r"[?#]", href, maxsplit=1)[0]))
        if target != f"{v.dir}/index.html":
            return f"{v.name}: the live link {href!r} does not lead to {v.dir}/index.html"
    return None


def spelling_problem(project: Path, v: Variant, rnd: int) -> str | None:
    """The folder of a variant is there under the very name the card has, letter case included, as the round's folder lists it. A disk that does not tell letter cases apart (macOS, Windows) opens rounds/rN/Settle/ for a
    folder called settle, but `shot --motion` and `frames` name their reports after the proof as the disk spells it, so the reports this board asks for (named after the card) would never be made: read from the listing, the
    folder is wrong in the same words on every kind of disk. None when it is spelt alike, or when there is no folder at all (files_problems says that)."""
    try:
        listed = sorted(e.name for e in (project / "rounds" / f"r{rnd}").iterdir())
    except OSError:
        return None
    alike = [e for e in listed if e.lower() == v.name.lower()]
    if v.name in listed or not alike:
        return None
    return (f"{v.name}: the card and its folder must be spelt alike, letter case included: the card says {v.name}, the folder is rounds/r{rnd}/{alike[0]}/ (rename one to match the other: "
            "`shot --motion` and `frames` name their reports after the folder as the disk spells it, so a card spelt otherwise never finds them)")


def files_problems(project: Path, v: Variant, page_rel: str, rnd: int) -> list[str]:
    spelling = spelling_problem(project, v, rnd)
    if spelling:
        return [spelling]
    if not (project / v.dir).is_dir():
        return [f"{v.name}: {v.dir}/ does not exist (one folder per variant: index.html, proof.json and the stills of `brand-creator frames {v.proof} --count 25`)"]
    out = []
    if not (project / v.dir / "index.html").is_file():
        out.append(f"{v.name}: {v.dir}/index.html is missing (the move where it will be seen, the approved mark in place)")
    if not (project / v.proof).is_file():
        out.append(f"{v.name}: {v.proof} is missing (a page case named {v.name})")
    else:
        out += proof_problems(project, v)
    out += [f"{v.name}: {v.frames}/{key}.png is missing: run `brand-creator frames {v.proof} --count 25`" for key in ("strip", "reduced") if not (project / v.frames / f"{key}.png").is_file()]
    link = link_problem(v, page_rel, rnd)
    return out + ([link] if link else [])


# ---------------------------------------------------------------- the proof of each variant, and the stills the card shows

def read_report(project: Path, report: str, proof: str) -> tuple[dict | None, list[str]]:
    """The report of `proof` at `report`, read as `check` reads one: (its document, why it is stale). Stale: it cannot be read, it is the report of another proof, or a file it was made from is gone or changed
    (_common.stale_inputs, the rule `check` applies)."""
    try:
        doc = json.loads((project / report).read_text(encoding="utf-8"))
        stale = [] if doc.get("proof") == proof else [f"it is the report of {doc.get('proof')}"]
        return doc, stale + stale_inputs(project, doc)
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as e:
        return None, [f"it cannot be read ({type(e).__name__}: {e})"]


def made_from(project: Path, report: str) -> list[Path]:
    """The files the report at `report` was made from, its own `inputs`: the proof, the page and every file the page loaded (tokens.css, a stylesheet, a script). A report that is missing or cannot be
    read lists none here: motion:proof and motion:stills say so."""
    try:
        return [project / rec["path"] for rec in json.loads((project / report).read_text(encoding="utf-8"))["inputs"]]
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return []


def unverified_rows(doc: dict) -> list[str]:
    """What a motion report says it could not verify: each skipped row of it, as the row's id and its detail on one line. `shot --motion` skips a row for a move driven by
    requestAnimationFrame, and also for a CSS animation (a percentage translation on a pseudo-element, a still that cannot be placed over the mark)."""
    rows = doc.get("results") if isinstance(doc.get("results"), list) else []
    return [f"{r.get('id')}: {motionspec.one_line(r.get('detail', ''))}" for r in rows if isinstance(r, dict) and r.get("status") == "skipped"]


def unverified_why(doc: dict, cmd: str) -> tuple[str, str]:
    """For a motion report that is no verdict (its status is not pass or fail): -> (what it could not verify, how to go on). The first is up to three of its not-verified rows, each cut at 400 characters, or
    that it lists none; the second says what to change and to run `cmd` again, and only when a row names requestAnimationFrame that such a move stays not verified however often the proof runs. One wording
    for board-lint (a variant's report) and `check` (the report of a proof of the project)."""
    said = unverified_rows(doc)
    quoted = " | ".join(s if len(s) <= 400 else s[:397].rstrip() + "..." for s in said[:3]) + (f" | and {len(said) - 3} more" if len(said) > 3 else "")
    if any("requestAnimationFrame" in s for s in said):   # only a row that names it says the move is driven by it
        how = ("the proof steps through CSS animations, CSS transitions and element.animate() (Web Animations) only, so a move driven by requestAnimationFrame "
               f"stays not verified however often it runs: write the move with one of them, then run `{cmd}`")
    else:
        how = f"change the page or the proof as the rows say, then run `{cmd}`" if said else f"run `{cmd}`"
    return (quoted if said else "it lists no row that is not verified"), how


def report_problems(project: Path, v: Variant) -> list[str]:
    """The variant's motion report (`shot --motion <its proof.json>`) is there and current, and the card's proof line says what it says."""
    cmd = f"brand-creator shot --motion {v.proof}"
    problems: list[str] = []
    status = None
    if not (project / v.report).is_file():
        problems.append(f"{v.name}: no motion report of {v.proof}: run `{cmd}`")
    else:
        doc, stale = read_report(project, v.report, v.proof)
        status = doc.get("status") if doc and not stale else None
        if stale:
            problems.append(f"{v.name}: the motion report is stale ({shown(stale, 3)}): run `{cmd}`")
        elif status not in ("pass", "fail"):
            quoted, how = unverified_why(doc, cmd)
            problems.append(f"{v.name}: the motion report is {status!r}, not a verdict ({quoted}): {how}")
            status = None
    lines = [n for n in v.card.walk() if "data-proof" in n.attrs]
    if len(lines) != 1:
        problems.append(f'{v.name}: the card needs one proof line (data-proof="pass" or "fail" and its text), it has {len(lines)}')
        return problems
    claimed = lines[0].attrs["data-proof"].strip()
    if claimed not in ("pass", "fail"):
        problems.append(f'{v.name}: data-proof must be "pass" or "fail", got {claimed!r}')
    elif status in ("pass", "fail") and claimed != status:
        problems.append(f'{v.name}: the card says data-proof="{claimed}" and the motion report says {status}')
    if not lines[0].nonempty():
        problems.append(f"{v.name}: the proof line has no text")
    return problems


def shown_bytes(project: Path, page: Path, src: str) -> tuple[bytes | None, str]:
    """The bytes of the picture a card shows: a data: URI decoded, or the project file a relative path names (read from the page's own folder, as a browser would).
    -> (bytes, "") or (None, why). A picture from the network, or by an absolute path, is not the project's file."""
    src = src.strip()
    if not src:
        return None, "has no src"
    if src[:5].lower() == "data:":
        head, comma, body = src.partition(",")
        if not comma:
            return None, "is a data: URI with no data"
        try:
            return (base64.b64decode(body, validate=True) if head.lower().endswith(";base64") else unquote_to_bytes(body)), ""
        except (binascii.Error, ValueError):
            return None, "is a data: URI that cannot be decoded"
    if re.match(r"(?:[a-z][a-z0-9+.-]*:|/)", src, re.I):
        return None, f"is {src[:48]!r}: a motion board shows the project's own file by a relative path, or a data: URI (nothing from the network)"
    try:
        f = confine(project, page.parent / unquote(re.split(r"[?#]", src, maxsplit=1)[0]), what="picture")
    except CliError:
        return None, f"is {src[:48]!r}, which is outside the project (a motion board shows the project's own files)"
    if not f.is_file():
        return None, f"names {rel(project, f)}, which does not exist"
    return f.read_bytes(), ""


def frames_report_problems(project: Path, v: Variant) -> list[str]:
    """The variant's `frames` report is there, current (the page and every file it loaded are what the stills were taken of) and passing for the variant's case: the stills are of the page as it is now."""
    cmd = f"brand-creator frames {v.proof} --count 25"
    if not (project / v.frames_report).is_file():
        return [f"{v.name}: no frames report of {v.proof}: run `{cmd}`"]
    doc, stale = read_report(project, v.frames_report, v.proof)
    if stale:
        return [f"{v.name}: the frames report is stale ({shown(stale, 3)}): run `{cmd}`"]
    results = [r for r in doc.get("results", []) if isinstance(r, dict)] if isinstance(doc.get("results"), list) else []
    row = next((r for r in results if r.get("id") == f"frames:{v.name}"), None)
    if row is None:
        return [f"{v.name}: the frames report has no row for the case {v.name} (it has: {', '.join(str(r.get('id')) for r in results) or 'none'}): run `{cmd}`"]
    if row.get("status") != "pass":
        why = re.sub(r"\s+", " ", str(row.get("detail", ""))).strip()
        return [f"{v.name}: frames:{v.name} is {row.get('status')} in the frames report" + (f" ({why[:160]})" if why else "") + f": run `{cmd}`"]
    return []


def stills_problems(project: Path, page: Path, v: Variant) -> list[str]:
    """The stills are of the page as it is now (the `frames` report), and the strip and the reduced still the card shows are the bytes frames.json lists (by sha256), the frames.json `frames` wrote for this variant's proof."""
    cmd = f"brand-creator frames {v.proof} --count 25"
    where = f"{v.frames}/frames.json"
    out = frames_report_problems(project, v)
    try:
        doc = json.loads((project / where).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return out + [f"{v.name}: {where} cannot be read ({type(e).__name__}): run `{cmd}`"]
    if not isinstance(doc, dict):
        return out + [f"{v.name}: {where} is not a JSON object: run `{cmd}`"]
    if doc.get("proof") != v.proof or doc.get("case") != v.name:
        out.append(f"{v.name}: {where} is the stills of {doc.get('proof')} (case {doc.get('case')}), not of {v.proof} (a folder copied from an earlier round): run `{cmd}`")
    for key in ("strip", "reduced"):
        entry = doc.get(key)
        want = entry.get("sha256") if isinstance(entry, dict) else None
        if not (isinstance(want, str) and re.fullmatch(r"[0-9a-f]{64}", want)):
            out.append(f"{v.name}: {where} lists no {key} with a sha256: run `{cmd}`")
            continue
        listed = entry.get("file")
        f = project / listed if isinstance(listed, str) and listed and ".." not in Path(listed).parts and not Path(listed).is_absolute() else None
        if f is None or not f.is_file():
            out.append(f"{v.name}: {where} lists {listed} for the {key}, which is not there: run `{cmd}`")
        elif sha256_file(f) != want:
            out.append(f"{v.name}: {listed} is not the {key} {where} lists (its sha256 differs): run `{cmd}`")
        imgs = [n for n in v.card.find_all(data_field=key) if n.tag == "img"]
        if len(imgs) != 1:
            out.append(f'{v.name}: the card needs one <img data-field="{key}"> (the {key} of the move), it has {len(imgs)}')
            continue
        data, why = shown_bytes(project, page, imgs[0].attrs.get("src", ""))
        if data is None:
            out.append(f"{v.name}: the {key} picture {why}")
        elif sha256_bytes(data) != want:
            out.append(f"{v.name}: the {key} picture the card shows is not the one {where} lists (sha256 {sha256_bytes(data)[:12]} against {want[:12]}): show {v.frames}/{key}.png, taken by `{cmd}`")
    return out


def field_problems(v: Variant) -> list[str]:
    """What it is, Cost and Degrades to are filled in: some text, no placeholder and no [[fill: ...]] marker left."""
    out = []
    for fid, label in FIELDS:
        nodes = list(v.card.find_all(data_field=fid))
        text = " ".join(n.text() for n in nodes)
        if not any(n.nonempty() for n in nodes):
            out.append(f'{v.name}: {label} is missing or empty (data-field="{fid}" inside the card)')
        elif FILL in text:
            out.append(f"{v.name}: {label} still holds a [[fill: ...]] marker")
    return out


# ---------------------------------------------------------------- the board

def variant_rows(rep: Report, project: Path, rnd: int, root: Node, page: Path, first: bool) -> None:
    """motion:variants, motion:files, motion:proof, motion:stills and motion:fields for the cards of the page (the first motion board of a project, `first`, shows exactly three)."""
    page_rel = rel(project, page)
    problems, named = name_problems(cards(root), first)
    add_row(rep, "motion:variants", "the variants: their number, and a word for each", problems,
            f"{len(named)} variant(s): {', '.join(n for n, _ in named)}" + (" (the first motion board)" if first else ""))
    variants = [Variant(rnd, nm, card) for nm, card in named]
    for rid, label, ask, ok in (
            ("motion:files", "each variant has its folder: page, proof and stills", lambda v: files_problems(project, v, page_rel, rnd), "folder, index.html, proof.json (a page case of that index.html, its static an approved master), strip and reduced still"),
            ("motion:proof", "each variant's proof is current and the card says what it found", lambda v: report_problems(project, v), "a current motion report each, and the proof line of each card says its status"),
            ("motion:stills", "the stills on the cards are those `frames` took of the page as it is now", lambda v: stills_problems(project, page, v),
             "a current passing frames report each, and the strip and the reduced still of each card are the files frames.json lists, sha256 for sha256"),
            ("motion:fields", "each card says what it is, what it costs and what it degrades to", field_problems, "What it is, Cost and Degrades to are filled in on every card")):
        if not variants:
            rep.add(rid, "skipped", label, detail="not verified: there is no variant card to look at (motion:variants says why)")
            continue
        add_row(rep, rid, label, [p for v in variants for p in ask(v)], ok)
    for v in variants:   # the report of the lint is stale as soon as one of these changes: `check` re-reads their hashes
        rep.inputs += [project / v.proof, project / v.dir / "index.html", project / v.frames / "frames.json", project / v.frames / "strip.png", project / v.frames / "reduced.png", project / v.report, project / v.frames_report]
        rep.inputs += made_from(project, v.report) + made_from(project, v.frames_report)   # and the files the two reports were made from: a move that lives in the page's stylesheet or script
