"""How `brand-creator cleanup` reads the rounds of a project: the stage of each round, which rounds must stay, and what board-lint reads from the earlier ones.
Standard library only; nothing here writes. The rules are in scripts/CONTRACT.md, "cleanup".

A round is a folder rounds/r<N>/ with a board.html. Its stage comes from the board it declares (style, mark = pick and refine, motion, site-refs, site-hero, site-pages);
a round that cannot be placed is "unknown" and is always kept. The keep-set grows to a fixed point: the latest round of each stage, the latest pick board, the unknown rounds,
the owner's --keep, the earlier rounds a kept board's lint reads (lint_context_keeps), the rounds BRAND-STATE.md and site/site.json name, every round a source file names (text,
URLs, links; a kept round is a source too, and reaches the rounds its files point at by relative path) and every round a report of kept work lists as an input.
It also holds the two questions of board-lint that look at earlier rounds and are asked of a chosen list of rounds (first_motion, style_rearmed), so board-lint and cleanup
cannot disagree about them.
"""
from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
from pathlib import Path
from typing import Iterator, NamedTuple
from urllib.parse import unquote

import siteboard
import sitedata
from _common import EXIT_FAIL, CliError, list_rounds, read_state
from boardpage import KINDS, MIN_TERRITORIES, declared_round, is_style_board, page_kind, page_marker, read_page, territory_count

Rounds = list[tuple[int, Path]]

ASCII_ROUND = re.compile(r"r(0|[1-9][0-9]*)", re.A)          # the only folder names cleanup works on: r + ASCII digits, no leading zero
ROUND_PART = re.compile(r"r([0-9]+)", re.A | re.I)
REF = re.compile(r"rounds(?:\\/|\\\\|/|\\|%2f|%5c)r([0-9]+)(?![0-9])", re.I | re.A)    # rounds/r3, rounds\r3, rounds\/r3, rounds\\r3, rounds%2Fr3, any letter case
REL = re.compile(r"((?:\.\.[/\\])+)r([0-9]+)(?![0-9])[/\\]", re.I | re.A)               # ../r3/ and ..\r3\ in a file of a kept round
MD_TARGET = re.compile(r"\]\(\s*<?([^)\s>]+)|(?:src|href)\s*=\s*[\"']([^\"']+)[\"']", re.I)
SCHEME = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//)")
STAGE_OF_KIND = {"style": "style", "pick": "mark", "refine": "mark", "motion": "motion", "site-refs": "site-refs"}
SOURCE_SKIP_DIRS = (".git", "node_modules")
NUL_WINDOW = 8192
MAX_REASONS = 40


class Info(NamedTuple):
    kind: str | None        # the data-board value as written, or None
    stage: str              # style, mark, motion, site-refs, site-hero, site-pages, unknown
    raw_stage: str | None   # data-site-stage as written on a site board


# ---------------------------------------------------------------- the two questions of board-lint that read earlier rounds

def first_motion(project: Path, rnd: int, rounds: Rounds | None = None) -> bool:
    """Whether the motion board of round `rnd` is the first motion board: no earlier round (of `rounds`, default every round folder of the project) holds a board that declares data-board="motion"."""
    return not any(page_kind(read_page(d / "board.html")) == "motion" for n, d in (list_rounds(project) if rounds is None else rounds) if n < rnd)


def style_reads(project: Path, rnd: int, reset_rounds: list[int], rounds: Rounds | None = None) -> tuple[int, list[int], dict]:
    """What style_rearmed reads of the rounds before `rnd`: (the rejected round, or -1; the rounds that declare a style board after it in reset_rounds; the pages by round)."""
    pages = {n: read_page(path / "board.html") for n, path in (list_rounds(project) if rounds is None else rounds) if n < rnd}
    pages = {n: root for n, root in pages.items() if page_kind(root) not in ("motion", "site-refs", "site")}   # a motion round, a website references round or a site round is not a round the owner rejected, and no style board lies in it
    last = max((n for n, root in pages.items() if page_kind(root) != "style"), default=-1)
    declared = [n for n, root in pages.items() if page_kind(root) == "style" and n > last and n in reset_rounds]
    return last, declared, pages


def style_rearmed(project: Path, rnd: int, reset_rounds: list[int], g1s_round: int | None, rounds: Rounds | None = None) -> tuple[bool, str]:
    """After a full rejection the pick board of reset round `rnd` needs a new style board and a style pick recorded after it.
    The rejected round is the highest earlier round whose board is not a style board. The new style board is a style board in a
    round listed in reset_rounds that lies after the rejected round and before `rnd` (the latest one counts); a page that only says
    data-board="style" counts when it declares its own round and holds MIN_TERRITORIES named territories with content, as the style lint
    asks. G1s must have been recorded when that round or a later style board was on disk (g1s_round, written by `state --record G1s`).
    `rounds` (default: every round folder) is the list of rounds to read. Returns (ok, detail)."""
    last, declared, pages = style_reads(project, rnd, reset_rounds, rounds)
    styles = [n for n in declared if is_style_board(pages[n], n)]
    rejected = f"the rejected round is r{last}" if last >= 0 else "no earlier pick or refine round was found"

    def not_counted(n: int) -> str:
        said = declared_round(pages[n])
        if said != n:
            return f'r{n} declares data-round="{said}" (a copied page)' if said is not None else f"r{n} declares no data-round"
        return f"r{n} has {territory_count(pages[n])} of the {MIN_TERRITORIES} territories a style board needs"

    if not styles:
        span = f"between r{last} and r{rnd}" if last >= 0 else f"before r{rnd}"
        thin = ", ".join(not_counted(n) for n in sorted(declared))
        return False, ("after a full rejection, show a new style board in a reset round before the next pick board "
                       f"(a page with data-board=\"style\" in a round listed in reset_rounds, {span}; {rejected})"
                       + (f". Not counted as a style board: {thin}" if thin else ""))
    new = max(styles)
    if g1s_round is None or g1s_round < new:
        return False, ("G1s still holds the pick from before the rejection: record the owner's new pick with state --record G1s "
                       f"\"picked <territory>\" (g1s_round is {'missing' if g1s_round is None else g1s_round}; the new style board is "
                       f"r{new}, and the record must come after it)")
    return True, f"the new style board r{new} comes after the rejected round and the pick was recorded after it (g1s_round {g1s_round}; {rejected})"


def hero_source(project: Path, rnd: int, root, rounds: Rounds | None = None) -> int | None:
    """The round of the hero board that holds the variant card the <body data-hero> of the pages board `root` names (the first match, as site:hero-first takes it), or None."""
    marker = page_marker(root)
    hero = marker.attrs.get(siteboard.HERO_ATTR, "").strip() if marker is not None else ""
    if not hero:
        return None
    for n, _board, hroot in siteboard.hero_boards(project, rnd, rounds):
        if hero in [c.attrs.get(siteboard.SITE_ATTR, "").strip() for c in siteboard.cards(hroot)]:
            return n
    return None


# ---------------------------------------------------------------- stages

def classify(rounds: Rounds) -> dict[int, Info]:
    """The stage of each round, read from rounds/rN/board.html."""
    out: dict[int, Info] = {}
    for n, d in rounds:
        root = read_page(d / "board.html")
        kind = page_kind(root) if root is not None else None
        raw_stage = siteboard.stage_of(root) if root is not None and kind == "site" else None
        stage = "unknown"
        if root is not None and kind in KINDS and declared_round(root) == n:
            if kind == "site":
                stage = {"hero": "site-hero", "pages": "site-pages"}.get(raw_stage or "", "unknown")
            else:
                stage = STAGE_OF_KIND[kind]
        out[n] = Info(kind, stage, raw_stage)
    return out


def reset_and_g1s(project: Path) -> tuple[list[int], int | None]:
    """(reset_rounds, g1s_round) of BRAND-STATE.md. A g1s_round that is set and not a whole number stops the run."""
    st = read_state(project)
    raw = str(st.get("g1s_round", "") or "").strip()
    if raw and not re.fullmatch(r"[0-9]+", raw, re.A):
        raise CliError(EXIT_FAIL, f'BRAND-STATE.md: g1s_round is "{raw}", not a whole number; cleanup does not guess which round the style pick was recorded against')
    return st.reset_rounds(), int(raw) if raw else None


def site_round(project: Path) -> int | None:
    """The `round` of site/site.json, read only when the file is there. Present and not a whole number: the run stops."""
    if not (Path(project) / sitedata.SITE_FILE).is_file():
        return None
    doc = sitedata.load_site(project)
    if "round" not in doc:
        return None
    v = doc["round"]
    if not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
        shown = json.dumps(v, ensure_ascii=False)
        raise CliError(EXIT_FAIL, f"{sitedata.SITE_FILE}: round is {shown}, not a whole number; cleanup does not guess which round the approved site came from")
    return v


# ---------------------------------------------------------------- the rounds board-lint reads

def lint_context_keeps(project: Path, rounds: Rounds, kept: set[int], reset_rounds: list[int]) -> list[tuple[int, str]]:
    """(round, reason) of the earlier rounds the lint of each kept board reads (rule 4): the first motion board; the first site board of the stage; the website references board;
    the hero board the data-hero card is on; the rejected round and the style boards a reset round's pick board reads."""
    out: list[tuple[int, str]] = []
    pages = {n: read_page(d / "board.html") for n, d in rounds}
    kinds = {n: (page_kind(r), siteboard.stage_of(r) if r is not None and page_kind(r) == "site" else None) for n, r in pages.items()}
    for n in sorted(kept):
        kind, stage = kinds.get(n, (None, None))
        if kind == "motion":
            earlier = [m for m, (k, _s) in kinds.items() if m < n and k == "motion"]
            if earlier:
                out.append((min(earlier), f"first motion board (board-lint of r{n} reads it)"))
        elif kind == "site":
            if stage in siteboard.STAGES:
                earlier = [m for m, (k, s) in kinds.items() if m < n and k == "site" and s == stage]
                if earlier:
                    out.append((min(earlier), f"first site board of the {stage} stage (board-lint of r{n} reads it)"))
            ref = siteboard.references_board(project, n, rounds)
            if ref is not None:
                out.append((ref[0], f"website references board (board-lint of r{n} reads it)"))
            if stage == "pages":
                src = hero_source(project, n, pages[n], rounds)
                if src is not None:
                    out.append((src, f"hero board of the card r{n} names in data-hero"))
        elif kind == "pick" and n >= 2 and n in reset_rounds:
            last, declared, _pages = style_reads(project, n, reset_rounds, rounds)
            if last >= 0:
                out.append((last, f"rejected round (board-lint of r{n} reads it)"))
            out += [(m, f"style board of the reset (board-lint of r{n} reads it)") for m in declared]
    return out


def lint_answers(project: Path, rounds: Rounds | None, kept: set[int], all_rounds: Rounds, reset_rounds: list[int], g1s_round: int | None) -> dict[tuple[int, str], object]:
    """The answer to each question board-lint asks of the earlier rounds, for every kept board, computed over `rounds` (None: every round folder)."""
    out: dict[tuple[int, str], object] = {}
    for n, d in all_rounds:
        if n not in kept:
            continue
        root = read_page(d / "board.html")
        kind = page_kind(root)
        if kind == "motion":
            out[(n, "whether it is the first motion board")] = first_motion(project, n, rounds)
        elif kind == "site":
            stage = siteboard.stage_of(root)
            out[(n, "whether it is the first site board of its stage")] = siteboard.is_first(project, n, stage, rounds)
            ref = siteboard.references_board(project, n, rounds)
            out[(n, "which website references board it reads")] = ref[0] if ref else None
            if stage == "pages":
                out[(n, "which hero board holds the card data-hero names")] = hero_source(project, n, root, rounds)
        elif kind == "pick" and n >= 2 and n in reset_rounds:
            out[(n, "whether the style pick was re-armed after the rejection")] = style_rearmed(project, n, reset_rounds, g1s_round, rounds)[0]
    return out


def lint_context_problems(project: Path, all_rounds: Rounds, kept: set[int], reset_rounds: list[int], g1s_round: int | None) -> list[str]:
    """The questions whose answer for a kept board is not the same on the kept rounds as on every round: each one a sentence ([] when none differs)."""
    kept_rounds = [(n, d) for n, d in all_rounds if n in kept]
    before = lint_answers(project, None, kept, all_rounds, reset_rounds, g1s_round)
    after = lint_answers(project, kept_rounds, kept, all_rounds, reset_rounds, g1s_round)
    gone = ", ".join(f"r{n}" for n, _ in all_rounds if n not in kept)
    return [(f"cleanup would change how board-lint reads rounds/r{n}/board.html ({q}): this is a bug in cleanup's keep rules; keep the round board-lint reads with --keep "
             f"(rounds it would remove: {gone}) and report it") for (n, q), v in sorted(before.items()) if after.get((n, q)) != v]


# ---------------------------------------------------------------- reading references

class Ref(NamedTuple):
    rnd: int
    where: str      # path:line (project-relative) or a sentence
    shown: str      # what was written


def _snippet(text: str, start: int) -> str:
    end = start
    while end < len(text) and end - start < 80 and text[end] not in " \t\r\n\"'<>)`":
        end += 1
    return text[start:end]


def _url_round(url: str, file_dir: str) -> int | None:
    u = re.split(r"[#?]", url.strip(), maxsplit=1)[0]
    if not u or SCHEME.match(u):
        return None
    u = unquote(u).replace("\\", "/")
    resolved = posixpath.normpath(u.lstrip("/") if u.startswith("/") else posixpath.join(file_dir, u))
    parts = resolved.split("/")
    if len(parts) >= 2 and parts[0].lower() == "rounds" and (m := ROUND_PART.fullmatch(parts[1])):
        return int(m.group(1))
    return None


def _strings(doc) -> Iterator[str]:
    if isinstance(doc, str):
        yield doc
    elif isinstance(doc, dict):
        for k, v in doc.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(doc, list):
        for v in doc:
            yield from _strings(v)


def refs_in_text(text: str, shown: str, *, suffix: str = ".txt", file_dir: str = "", in_round: bool = False) -> list[Ref]:
    """Every round `text` (the file `shown`, a project-relative path) names: rule 6 (the pattern, and each relative URL that resolves into rounds/rN/, by the kind of file),
    and with `in_round` rule 7 (../r3/ written in a file of a kept round, resolved against the file's folder). A .json file is read as raw text and as its decoded strings."""
    refs: list[Ref] = []
    for m in REF.finditer(text):
        refs.append(Ref(int(m.group(1)), f"{shown}:{text.count(chr(10), 0, m.start()) + 1}", _snippet(text, m.start())))
    kind = "css" if suffix == ".css" else "html" if suffix in (".html", ".htm", ".svg") else None
    urls: list[tuple[int, str]] = []
    if kind is not None:
        urls = sitedata.urls_in(text, kind)
    elif suffix in (".md", ".markdown"):
        urls = [(text.count("\n", 0, m.start()) + 1, m.group(1) or m.group(2)) for m in MD_TARGET.finditer(text)]
    for line, url in urls:
        n = _url_round(url, file_dir)
        if n is not None:
            refs.append(Ref(n, f"{shown}:{line}", url[:80]))
    if in_round:
        for m in REL.finditer(text):
            parts = posixpath.normpath(posixpath.join(file_dir, m.group(0).replace("\\", "/"))).split("/")
            if len(parts) >= 2 and parts[0].lower() == "rounds" and (r := ROUND_PART.fullmatch(parts[1])):
                refs.append(Ref(int(r.group(1)), f"{shown}:{text.count(chr(10), 0, m.start()) + 1}", m.group(0)))
    return refs


def read_text_source(path: Path, shown: str) -> str | None:
    """The text of a file: None for a binary file (a NUL byte in the first 8 KiB); decoded as UTF-8 with surrogateescape, so a file in another encoding is still searched (the pattern is ASCII).
    A file that cannot be read stops the run."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise CliError(EXIT_FAIL, f"cannot read {shown}: {e.strerror or e}") from None
    if b"\0" in data[:NUL_WINDOW]:
        return None
    return data.decode("utf-8", errors="surrogateescape")


def refs_in_file(path: Path, shown: str, *, in_round: bool = False) -> list[Ref]:
    text = read_text_source(path, shown)
    if text is None:
        return []
    suffix = path.suffix.lower()
    refs = refs_in_text(text, shown, suffix=suffix, file_dir=posixpath.dirname(shown), in_round=in_round)
    if suffix == ".json":
        try:
            doc = json.loads(text)
        except ValueError as e:
            raise CliError(EXIT_FAIL, f"cannot read {shown}: it is not valid JSON ({e}); cleanup reads a .json file as its decoded strings too, so it will not guess") from None
        seen = {(r.rnd, r.where) for r in refs}
        for s in _strings(doc):
            for m in REF.finditer(s):
                r = Ref(int(m.group(1)), shown, _snippet(s, m.start()))
                if (r.rnd, r.where) not in seen:
                    seen.add((r.rnd, r.where))
                    refs.append(r)
    return refs


def link_ref(project: Path, path: Path, shown: str) -> Ref | None:
    """A symbolic link whose target lies in rounds/rN/ keeps round N; the link is not followed for reading."""
    real = os.path.realpath(path)
    rounds_real = os.path.realpath(Path(project) / "rounds")
    if real.startswith(rounds_real + os.sep):
        parts = real[len(rounds_real) + 1:].split(os.sep)
        if (m := ROUND_PART.fullmatch(parts[0])):
            return Ref(int(m.group(1)), shown, f"symbolic link to {os.readlink(path)}")
    return None


def walk_project(root: Path, project: Path, *, skip_rounds: bool) -> Iterator[tuple[Path, str, bool]]:
    """(path, project-relative posix path, is a symbolic link) of every file and link under `root`, sorted, links not followed. Not entered: .git, node_modules, any folder named removed-*, history/ at the top of
    the project, and with skip_rounds the round folders under rounds/."""
    proj = Path(project)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        here_rel = here.relative_to(proj).as_posix() if here != proj else ""
        keep_dirs = []
        for name in sorted(dirnames):
            full = here / name
            sub = f"{here_rel}/{name}" if here_rel else name
            if full.is_symlink():
                yield full, sub, True
                continue
            if name in SOURCE_SKIP_DIRS or name.startswith("removed-") or sub == "history":
                continue
            if skip_rounds and here_rel == "rounds" and re.fullmatch(r"r(\d+)", name):
                continue
            keep_dirs.append(name)
        dirnames[:] = keep_dirs
        for name in sorted(filenames):
            full = here / name
            yield full, (f"{here_rel}/{name}" if here_rel else name), full.is_symlink()


def is_source(shown: str) -> bool:
    """Whether a project-relative file is read as a source of references: not cleanup's own records, not the drawing brief of a round, not a report (read by rule 8 instead)."""
    parts = shown.split("/")
    name = parts[-1]
    if len(parts) == 2 and parts[0] == "qa" and (fnmatch.fnmatch(name, "*-cleanup-plan*.txt") or fnmatch.fnmatch(name, "*-cleanup-removed*.txt")):
        return False
    if len(parts) == 2 and parts[0] == "brief" and fnmatch.fnmatch(name, "canvas-round-*.md"):
        return False
    if name == "capture.json" or (parts[:2] == ["assets", "_checks"] and name.lower().endswith(".json")):
        return False
    return True


class ReportRec(NamedTuple):
    shown: str
    subjects: list[str]
    inputs: list[str]
    in_checks: bool


def report_record(path: Path, shown: str) -> ReportRec:
    """A report (assets/_checks/**/*.json, or a capture.json): the pages and proofs it is about, and the files it was made from. One that does not parse stops the run."""
    text = read_text_source(path, shown)
    try:
        doc = json.loads(text if text is not None else "")
    except ValueError as e:
        raise CliError(EXIT_FAIL, f"cannot read {shown}: it is not valid JSON ({e}); cleanup does not guess what a report is about") from None
    subjects: list[str] = []
    if isinstance(doc, dict):
        run = doc.get("run") if isinstance(doc.get("run"), dict) else {}
        for holder in (doc, run.get("target"), doc.get("target"), doc.get("source")):
            if isinstance(holder, dict) and isinstance(holder.get("page"), str):
                subjects.append(holder["page"])
        if isinstance(doc.get("proof"), str):
            subjects.append(doc["proof"])
        inputs = [i["path"] for i in doc.get("inputs", []) if isinstance(i, dict) and isinstance(i.get("path"), str)] if isinstance(doc.get("inputs"), list) else []
    else:
        inputs = []
    return ReportRec(shown, list(dict.fromkeys(subjects)), inputs, shown.startswith("assets/_checks/"))


def path_round(p: str) -> int | None:
    """The round a project-relative path lies in (rounds/rN/...), or None."""
    m = re.match(r"^(?:\./)*rounds/r([0-9]+)(?:/|$)", p.replace("\\", "/"), re.I | re.A)
    return int(m.group(1)) if m else None


class Scan:
    """What the files outside the round folders say, read once: the references (rule 6) and the reports (rule 8). A kept round is scanned when it becomes one."""

    def __init__(self, project: Path):
        self.project = Path(project)
        self.refs: list[Ref] = []
        self.reports: list[ReportRec] = []
        self._read_outside()

    def _read_outside(self) -> None:
        proj = self.project
        for path, shown, is_link in walk_project(proj, proj, skip_rounds=True):
            if is_link:
                r = link_ref(proj, path, shown)
                if r is not None:
                    self.refs.append(r)
                continue
            if shown.endswith("/capture.json") or shown == "capture.json" or (shown.startswith("assets/_checks/") and shown.lower().endswith(".json")):
                self.reports.append(report_record(path, shown))
            if is_source(shown):
                self.refs += refs_in_file(path, shown)
        self._read_documents()

    def _read_documents(self) -> None:
        """The documents outside the project that tools/cascade.json (`also`) and FAMILY.md (`parent_docs`) list, read only, as `check --cascade` reads them. One that is missing stops the run."""
        proj = self.project
        listed: list[tuple[str, Path]] = []
        cfg = proj / "tools" / "cascade.json"
        if cfg.is_file():
            try:
                doc = json.loads(cfg.read_text(encoding="utf-8", errors="surrogateescape"))
            except (OSError, ValueError) as e:
                raise CliError(EXIT_FAIL, f"cannot read tools/cascade.json: {e}") from None
            also = doc.get("also", []) if isinstance(doc, dict) else []
            listed += [(f"{x} (tools/cascade.json)", (proj / x).expanduser()) for x in also if isinstance(x, str) and x.strip()]
        fam = proj / "FAMILY.md"
        if fam.is_file():
            m = re.search(r"```json family-check\n(.*?)```", read_text_source(fam, "FAMILY.md") or "", re.S)
            try:
                docs = json.loads(m.group(1)).get("parent_docs", []) if m else []
            except ValueError:
                docs = []
            listed += [(f"{x} (FAMILY.md)", (fam.parent / x).expanduser()) for x in docs if isinstance(x, str)]
        for label, p in listed:
            if p.is_file():
                files = [p]
            elif p.is_dir():
                files = sorted(q for q in p.rglob("*") if q.is_file())
            else:
                raise CliError(EXIT_FAIL, f"cannot read {label}: it does not exist; a document named for the cascade must be there, or cleanup cannot see what it refers to")
            for f in files:
                text = read_text_source(f, label)
                if text is not None:
                    self.refs += [r._replace(where=label) for r in refs_in_text(text, label)]

    def scan_round(self, folder: Path) -> tuple[list[Ref], list[ReportRec]]:
        """The references in the files of a kept round (rule 6 on its text, rule 7 on its relative paths, links) and the capture.json records in it."""
        proj = self.project
        refs: list[Ref] = []
        reports: list[ReportRec] = []
        for path, shown, is_link in walk_project(folder, proj, skip_rounds=False):
            if is_link:
                r = link_ref(proj, path, shown)
                if r is not None:
                    refs.append(r)
                continue
            if path.name == "capture.json":
                reports.append(report_record(path, shown))
            if is_source(shown):
                refs += refs_in_file(path, shown, in_round=True)
        return refs, reports


# ---------------------------------------------------------------- the keep-set

class Keep(NamedTuple):
    reasons: dict[int, list[str]]       # round -> why it stays, in the order found
    infos: dict[int, Info]
    removable_reports: list[str]        # reports of removed work, project-relative


def compute_keep(project: Path, rounds: Rounds, extra: list[int], *, scan: Scan | None = None) -> Keep:
    """The keep-set of the rounds (rules 1 to 8) and the reports of removed work. Raises CliError (exit 1) for what cannot be read."""
    project = Path(project)
    have = {n for n, _ in rounds}
    dirs = dict(rounds)
    infos = classify(rounds)
    reset_rounds, g1s = reset_and_g1s(project)
    site_n = site_round(project)
    scan = scan or Scan(project)
    reasons: dict[int, list[str]] = {}
    grew = False

    def add(n: int, why: str) -> None:
        nonlocal grew
        if n not in have:
            return
        if n not in reasons:
            reasons[n] = []
            grew = True
        if why not in reasons[n] and len(reasons[n]) < MAX_REASONS:
            reasons[n].append(why)

    for stage in sorted({i.stage for i in infos.values()} - {"unknown"}):
        add(max(n for n, i in infos.items() if i.stage == stage), "latest of its stage")
    picks = [n for n, i in infos.items() if i.kind == "pick" and i.stage == "mark"]
    if picks:
        add(max(picks), "latest pick board")
    for n, i in infos.items():
        if i.stage == "unknown":
            add(n, "no board cleanup can place: it removes only rounds it can place")
    for n in extra:
        add(n, "kept with --keep")
    if g1s is not None:
        add(g1s, "g1s_round in BRAND-STATE.md")
    if site_n is not None:
        add(site_n, "site/site.json round")
    for r in scan.refs:
        add(r.rnd, f"referenced: {r.where} ({r.shown})")

    scanned: set[int] = set()
    reports = list(scan.reports)
    while True:
        grew = False
        for n in sorted(reasons):
            if n in scanned:
                continue
            scanned.add(n)
            refs, found = scan.scan_round(dirs[n])
            reports += found
            for r in refs:
                if r.rnd != n:
                    add(r.rnd, f"referenced: {r.where} ({r.shown})")
            grew = True
        for m, why in lint_context_keeps(project, rounds, set(reasons), reset_rounds):
            add(m, why)
        for rep in reports:
            rounds_of = [path_round(s) for s in rep.subjects]
            dead = bool(rep.subjects) and all(m in have and m not in reasons for m in rounds_of)
            if not dead:
                for p in rep.inputs:
                    m = path_round(p)
                    if m is not None:
                        add(m, f"input of the report {rep.shown} ({p})")
        if not grew:
            break
    removable = sorted({rep.shown for rep in scan.reports if rep.in_checks and rep.subjects
                        and all((m := path_round(s)) is not None and m in have and m not in reasons for s in rep.subjects)})
    return Keep(reasons, infos, removable)
