"""page-check, the judging half: what a page check is about, how it is aimed, and the rows it reports.

`brand-creator page-check` measures one rendered page against the brand. Measuring happens in the browser (`render.mjs page-measure`, with the
in-page collectors of `page_measure.mjs`); this module turns those raw facts into report rows against the project's tokens, FACTS.md and the `page`
block of qa/rules.json. It holds the pieces other tools import (`board_lint.py`, `check.py` and the later kit call them; nobody writes a second
version):

  report_tool(ident)      the report name `page-check/<slug>-<hash6>` of one target. `ident` is the project-relative posix path of a project
                          page, `from:<real DIR>/<page>` for a built site given with --from, or `url:<URL>` for a page on this machine.
  is_loopback_url(url)    the one loopback rule: http or https on localhost, 127.0.0.1 or [::1], and nothing else.

Each family of rows is a function `(rep, measures, ctx)` listed in ROW_CHECKS; a later check (colours, fonts, marks, claims ...) adds its function to
the list and reads the same Ctx. The rows of the first one, `load_rows`, are `page:load:<width>-<scheme>`.

Standard library plus scripts/lib (_common, qa_rules) only. This folder is outside scripts/lib/, so a change here does not make every pack stale. The
only reads are the project's own files and, with --from, the folder it names (read only: it is copied, never written).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import qa_rules
from _common import CliError, EXIT_CANNOT, EXIT_USAGE, Report, confine, fail, rel, scratch_dir

REPORT_DIR = "page-check"
SCHEMES = ("light", "dark")
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")
FROM_MAX_FILES = 5000
FROM_MAX_BYTES = 200 * 1024 * 1024
FROM_SKIPPED = (".git", "node_modules")   # never copied, never counted
TOKENS_FILE = "assets/tokens/tokens.json"
SHOWN = 3                                 # how many items of a list a row's detail names


# ---------------------------------------------------------------- shared helpers

def is_loopback_url(url: str) -> bool:
    """True only for an http or https URL with no user name or password whose host, as written, is localhost, 127.0.0.1 or [::1] (any letter case). The host is
    the text in the URL, not what a parser turns it into: 127.1, 0x7f000001, 2130706433, [0:0:0:0:0:0:0:1] and %6cocalhost are refused although a browser would
    go to this machine. A URL with whitespace, a control character or a backslash is refused outright: parsers disagree on those, and the host the browser would
    go to must be the one read here. Twin of isLoopbackUrl in scripts/lib/_common.mjs (a test pins both to one table of cases)."""
    if not isinstance(url, str) or re.search(r"[\s\x00-\x1f\x7f\\]", url):
        return False
    try:
        parts = urlsplit(url)
        parts.port   # a port that is no number raises here
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and "@" not in parts.netloc and (parts.hostname or "") in LOOPBACK_HOSTS


def report_tool(ident: str) -> str:
    """The report tool name (-> assets/_checks/page-check/<slug>-<hash6>.json) of one target: one report per page, so a run on one page never touches the
    report of another. The slug is the page's file stem (for a URL, the stem of its path's last segment), else `page`; the hash is the first six hex of the
    sha256 of the ident (see the module docstring)."""
    if ident.startswith("url:"):
        segments = [s for s in urlsplit(ident[4:]).path.split("/") if s]
        name = segments[-1] if segments else ""
    else:
        name = ident.removeprefix("from:").rsplit("/", 1)[-1]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", Path(name).stem).strip("-").lower() or "page"
    return f"{REPORT_DIR}/{slug}-{hashlib.sha256(ident.encode()).hexdigest()[:6]}"


def parse_widths(text: str) -> list[int]:
    """--widths 360,390,1440 -> [360, 390, 1440]; anything that is not a whole number from 200 to 4000 is a usage error."""
    items = [t.strip() for t in text.split(",")]
    bad = [t for t in items if not re.fullmatch(r"\d+", t)]
    if bad:
        fail(EXIT_USAGE, f"--widths: {bad[0]!r} is not a whole number from {qa_rules.PAGE_WIDTH_MIN} to {qa_rules.PAGE_WIDTH_MAX}")
    return qa_rules.validate_page_widths([int(t) for t in items], "--widths")


def parse_schemes(text: str) -> list[str]:
    """--schemes light,dark -> ["light", "dark"]; a scheme other than light or dark, or one twice, is a usage error."""
    items = [t.strip() for t in text.split(",")]
    for t in items:
        if t not in SCHEMES:
            fail(EXIT_USAGE, f"--schemes: {t!r} is not a colour scheme (light or dark)")
    if len(set(items)) != len(items):
        fail(EXIT_USAGE, "--schemes: a scheme is listed twice")
    return items


# ---------------------------------------------------------------- the target

@dataclass
class Target:
    kind: str                    # "project" (a page of the project), "from" (a built site anywhere, copied and served from there) or "url" (this machine)
    ident: str                   # what the report name is made from (see report_tool)
    page: str | None = None      # project: the project-relative posix path; from: the path inside the folder; url: None
    from_dir: Path | None = None
    url: str | None = None
    file: Path | None = None     # the page on disk (project, from)

    def describe(self) -> str:
        return {"project": f"project page {self.page}", "from": f"built site {self.from_dir}, page {self.page}", "url": f"page {self.url}"}[self.kind]

    def as_report(self) -> dict:
        return {"kind": self.kind, "page": self.page, "from": str(self.from_dir) if self.from_dir else None, "url": self.url}


def _inside(root: Path, path: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(root)))
        return True
    except ValueError:
        return False


def _survey(folder: Path) -> tuple[int, int]:
    """(files, bytes) a --from copy would hold: .git and node_modules and every symlink are left out. Stops counting once a limit is passed."""
    files = size = 0
    for here, dirs, names in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if d not in FROM_SKIPPED and not os.path.islink(os.path.join(here, d))]
        for n in names:
            p = os.path.join(here, n)
            if os.path.islink(p):
                continue
            files += 1
            size += os.path.getsize(p)
            if files > FROM_MAX_FILES or size > FROM_MAX_BYTES:
                return files, size
    return files, size


def resolve_target(project: Path, page: str | None, from_dir: str | None, url: str | None) -> Target:
    """The one target of a run. Every refusal here is a usage error (exit 2) and happens before anything is written."""
    if url and (page or from_dir):
        fail(EXIT_USAGE, "two targets: give a page of the project, --from DIR with a page, or --url URL, not several")
    if url:
        if not is_loopback_url(url):
            fail(EXIT_USAGE, f"--url {url}: page-check runs offline and measures only a page on this machine (http or https on localhost, 127.0.0.1 or [::1]); "
                             "for a remote page, build it locally and use --from DIR")
        return Target("url", f"url:{url}", url=url)
    if from_dir:
        if not page:
            fail(EXIT_USAGE, "--from DIR needs the page to check, written relative to DIR: brand-creator page-check --from DIR index.html")
        folder = Path(from_dir).expanduser()
        if not folder.is_dir():
            fail(EXIT_USAGE, f"--from {from_dir}: not a folder")
        folder = Path(os.path.realpath(folder))
        lexical = Path(os.path.normpath(page))
        if lexical.is_absolute():   # an absolute page must lie inside the folder
            try:
                lexical = Path(os.path.realpath(lexical)).relative_to(folder)
            except ValueError:
                fail(EXIT_USAGE, f"page {page} is not inside {folder}: write it relative to --from DIR")
        if ".." in lexical.parts or not (folder / lexical).is_file():
            fail(EXIT_USAGE, f"page not found in {folder}: {page}")
        cur = folder
        for part in lexical.parts:
            cur = cur / part
            if part in FROM_SKIPPED or cur.is_symlink():
                fail(EXIT_USAGE, f"page {page} is behind {part!r}, which --from does not copy (.git, node_modules and symlinks are left out)")
        page_rel = lexical.as_posix()
        files, size = _survey(folder)
        if files > FROM_MAX_FILES or size > FROM_MAX_BYTES:
            fail(EXIT_USAGE, f"--from {folder} holds more than {FROM_MAX_FILES} files or {FROM_MAX_BYTES // (1024 * 1024)} MB (.git, node_modules and symlinks not counted): "
                             "point --from at the built site alone")
        return Target("from", f"from:{folder.as_posix()}/{page_rel}", page=page_rel, from_dir=folder, file=folder / page_rel)
    if not page:
        fail(EXIT_USAGE, "no target: give a page of the project, --from DIR with a page, or --url URL")
    try:
        abs_page = confine(project, page, what="page")
    except CliError:
        fail(EXIT_USAGE, f"page {page} is outside the project {project}: for a built site elsewhere use --from DIR <page>")
    if not abs_page.is_file():
        fail(EXIT_USAGE, f"page not found: {page}")
    page_rel = rel(project, abs_page)
    return Target("project", page_rel, page=page_rel, file=abs_page)


def stage_from_copy(project: Path, target: Target) -> Path:
    """--from: copy the folder into a new run folder <data>/scratch/<project>/page-check/<hash6>/<n>/ and return it; the browser is pointed at the copy.
    The source is only read. `n` is one more than the highest run folder already there."""
    assert target.kind == "from" and target.from_dir
    base = scratch_dir(project, f"{REPORT_DIR}/{report_tool(target.ident).rsplit('-', 1)[1]}")
    taken = [int(d.name) for d in base.iterdir() if d.is_dir() and d.name.isdigit()]
    dst = base / str(max(taken, default=0) + 1)

    def skip(here: str, names: list[str]) -> list[str]:   # a symlink, a pipe or a socket is not copied (a pipe would block the copy)
        return [n for n in names if n in FROM_SKIPPED or os.path.islink(os.path.join(here, n))
                or not (os.path.isdir(os.path.join(here, n)) or os.path.isfile(os.path.join(here, n)))]

    shutil.copytree(target.from_dir, dst, symlinks=False, ignore=skip)
    return dst


# ---------------------------------------------------------------- what a run knows

@dataclass
class Ctx:
    """Everything a family of rows reads besides the measures."""
    project: Path
    target: Target
    widths: list[int]
    schemes: list[str]
    rules: dict                   # qa/rules.json with the proposals filled in (qa_rules.load)
    tokens: dict                  # assets/tokens/tokens.json
    extra: dict = field(default_factory=dict)   # what a row family adds to the report at its top level


def load_tokens(project: Path) -> dict:
    f = project / TOKENS_FILE
    if not f.is_file():
        fail(EXIT_CANNOT, f"{TOKENS_FILE} is missing: run `brand-creator tokens` first (page-check judges a page against the built tokens)")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_CANNOT, f"{TOKENS_FILE} cannot be read ({e}): run `brand-creator tokens` again")
    if not isinstance(doc, dict):
        fail(EXIT_CANNOT, f"{TOKENS_FILE} is not a tokens file: run `brand-creator tokens` again")
    return doc


def base_inputs(project: Path, target: Target) -> list[Path]:
    """The files every page check stands on: the built tokens, the rules, the facts and the state of the project, and the page (a project target)."""
    files = [project / TOKENS_FILE, project / qa_rules.RULES_FILE, project / "FACTS.md", project / "BRAND-STATE.md"]
    if target.kind == "project" and target.file:
        files.append(target.file)
    return files


def served_project_files(project: Path, measures: dict) -> list[Path]:
    """Every project file the browser was served in any view (a stylesheet, tokens.css, a script, an image, a font), so a change to one makes the report stale."""
    root = Path(os.path.realpath(project))
    out = {}
    for v in measures.get("views", []):
        for s in v.get("served", []) if isinstance(v, dict) else []:
            p = Path(s)
            if p.is_file() and _inside(root, p):
                out[os.path.realpath(p)] = p
    return sorted(out.values())


# ---------------------------------------------------------------- rows

def _names(items: list, n: int = SHOWN) -> str:
    shown = [str(i) for i in items[:n]]
    return "; ".join(shown) + (f"; and {len(items) - n} more" if len(items) > n else "")


def load_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:load:<width>-<scheme>: the page loaded in that view without a page or console error, a failed request to its own files or (a project page or a
    built site) a request to another origin. A page on this machine (--url) may ask other origins; they are aborted, and that is a warning."""
    views = {(v.get("width"), v.get("scheme")): v for v in measures.get("views", []) if isinstance(v, dict)}
    if not views:
        rep.add("page:load", "skipped", "the page was rendered", detail="not verified: no view was measured")
        return
    for width in ctx.widths:
        for scheme in ctx.schemes:
            rid, label, v = f"page:load:{width}-{scheme}", f"{width}px {scheme}", views.get((width, scheme))
            if v is None or v.get("error"):
                rep.add(rid, "fail", label, detail=f"could not render: {(v or {}).get('error') or 'the view is not in the measurements'}")
                continue
            errors, failed, other = v.get("errors", []), v.get("failed_local", []), v.get("non_local", [])
            problems = []
            if errors:
                problems.append(f"{len(errors)} page or console error(s): {_names(errors, 2)}")
            if failed:
                problems.append(f"{len(failed)} failed request(s) to the page's own files: {_names(failed)}")
            if other:
                problems.append(f"{len(other)} request(s) to another origin, aborted ({_names(other)})" if ctx.target.kind == "url"
                                else f"{len(other)} request(s) to another origin: {_names(other)} (a page checked offline asks nobody)")
            extra = {"console_errors": errors, "failed_local_requests": failed, "non_local_requests": other,
                     "viewport": v.get("viewport"), "height": v.get("height"), "lang": v.get("lang")}
            if errors or failed or (other and ctx.target.kind != "url"):
                rep.add(rid, "fail", label, detail="; ".join(problems), **extra)
            elif other:
                rep.add(rid, "warn", label, detail="aborted: page-check runs offline: " + problems[0], **extra)
            else:
                vp = v.get("viewport") or {}
                rep.add(rid, "pass", label, detail=f"loaded at {vp.get('width', width)}x{vp.get('height', '?')}, page height {v.get('height', '?')} px, "
                                                  f"{len(v.get('resources', {}))} image file(s), no page or console error, no failed or outside request", **extra)


ROW_CHECKS = [load_rows]   # each (rep, measures, ctx); the later families of rows (colours, fonts, marks, motion, claims, rules, tells) are added here


def judge(rep: Report, measures: dict, ctx: Ctx, measures_path: Path) -> None:
    """Turn the measurements into the report: the target row, every family of rows, the project files the browser was served, and the keys written
    at the top level of the report (`target`, `widths`, `schemes`, `measures`, and what a family adds to ctx.extra)."""
    source = qa_rules.RULES_FILE if (ctx.project / qa_rules.RULES_FILE).is_file() else "proposals (no qa/rules.json)"
    rep.add("page:target", "info", "what was checked", detail=f"{ctx.target.describe()}; widths {', '.join(map(str, ctx.widths))}; "
                                                              f"schemes {', '.join(ctx.schemes)}; Chromium {measures.get('chromium', 'unknown')}; thresholds from {source}")
    for check in ROW_CHECKS:
        check(rep, measures, ctx)
    if ctx.target.kind == "project":
        rep.inputs.extend(served_project_files(ctx.project, measures))
    rep.extra.update({"target": ctx.target.as_report(), "widths": ctx.widths, "schemes": ctx.schemes, "measures": str(measures_path), **ctx.extra})
