#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator site approve [--round N] [--replace] [--project DIR]: put the approved pages of the site round into site/.

    brand-creator site approve                  the latest round, which must be a site board at the pages stage
    brand-creator site approve --round 5        the pages board of round 5
    brand-creator site approve --replace        site/ holds approved pages already: move it to removed-<date>/site/ and write the new ones

The owner approved the pages (G4p recorded) and the pages board of the round was linted since the last change to it. For each page card of that board, rounds/r<N>/<id>/ is copied into
site/<id>/ except shots/ and cold-review.md, and every path in an .html or .css file that points at a file of the project outside the page's folder is written again so that it leads to the same
file from site/<id>/ (src, href, poster, srcset, url() in a <style>, a style attribute and a .css file; a link to a sibling page leads to site/<other>/). Paths inside the folder, #..., data:, mailto: and tel:
stay. site/site.json (schema 1) records the approval, the round, the hero, each page (layout, sha256 of the written index.html) and each choice of the board, tagged rule (with where it was decided) or example.
Approved pages are references for whoever builds the real site, never fill-in templates.

Nothing is written when any page fails. An existing site/ stops the run unless --replace is given, which moves it to removed-<date>/site/ first (it is never deleted).
Exit 0 written. Exit 1: G4p not recorded; no current, passing board-lint report of the board; a page that cannot go (a network address, a path starting with /, a file that is not there, a page without its
layout or index.html); site/ already holds pages. Exit 2: usage; a round that is not a site board at the pages stage; a path that leaves the project; a symbolic link in a page folder, or one that is
rounds/, rounds/r<N>/, the board file or a page folder itself.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "boardlib"))
sys.path.insert(0, str(HERE / "pagelib"))   # boardlib/siteboard.py names the page-check report of a page with pagelib/pagecheck.py
from _common import (EXIT_FAIL, EXIT_USAGE, STATE_FILE, CliError, Parser, add_project_arg, confine, fail, find_project, gate_recorded, list_rounds, main_guard,  # noqa: E402
                     sha256_bytes, sha256_file, stale_inputs, today)
from boardpage import page_kind, page_marker, read_page  # noqa: E402
import siteboard  # noqa: E402
import sitedata  # noqa: E402

LINT_REPORT = "assets/_checks/board-lint.json"
EXCLUDED_FILE = "cold-review.md"     # not copied from the top of a page folder, nor is the folder shots/ (capture writes it again beside the approved page)
EXCLUDED_DIR = "shots"
JUNK = (".DS_Store",)
SHOWN = 12                           # problems listed in a message before "and N more"


def old_page_reports(project: Path, board_rel: str, page_ids: list[str]) -> bool:
    """True when the page-check report of a page of the board lists BRAND-STATE.md whole: a report made before page-check held that file by its G4 rules (the part "g4-rules", _common.PART_READERS)."""
    folder = board_rel.rsplit("/", 1)[0]
    return any(project / STATE_FILE in siteboard.made_from(project, f"assets/_checks/{siteboard.report_tool(f'{folder}/{pid}/index.html')}.json") for pid in page_ids)


def lint_problem(project: Path, board_rel: str, page_ids: list[str]) -> str | None:
    """Why assets/_checks/board-lint.json is not a current, passing lint of the board, or None. Current is `check`'s rule: no file it was made from is gone or changed (the board itself is one of them).
    A page-check report holds BRAND-STATE.md by its G4 rules only (an input with a "part", _common.PART_READERS), and so does the lint through it: recording G4p, G5, G6 or the phase leaves both current,
    and a changed G4 record or "(rule)" line makes both stale: the pages are checked again (`page_ids`), then the board is linted. The lint holds the whole file too when a rule's source is found
    only there (siteboard.choices_rows): a write to it then makes the lint stale, and linting again is enough. A report made when it listed the whole file is stale after any write to it:
    the message says to check the pages again before the board is linted."""
    cmd = f"brand-creator board-lint {board_rel}"
    again = f"lint the pages board first: {cmd}"
    f = project / LINT_REPORT
    if not f.is_file():
        return f"there is no board-lint report ({LINT_REPORT}): {again}"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            return f"{LINT_REPORT} is not a report: {again}"
        stale = stale_inputs(project, doc)
        listed = {r.get("path") for r in doc.get("inputs", []) if isinstance(r, dict)}
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as e:
        return f"{LINT_REPORT} cannot be read ({type(e).__name__}: {e}): {again}"
    if doc.get("page") != board_rel:
        return f"the board-lint report is for {doc.get('page')}, not {board_rel}: {again}"
    if board_rel not in listed:
        stale.append(f"it does not list {board_rel} among the files it was made from")
    if stale:
        extra = ""
        whole, rules = f"{STATE_FILE} changed", f"{STATE_FILE} (the G4 rules) changed"
        if set(stale) <= {whole, rules}:   # only BRAND-STATE.md changed
            checks = "; ".join(f"brand-creator page-check {board_rel.rsplit('/', 1)[0]}/{pid}/index.html" for pid in page_ids)
            pages = f"check each page again{' (' + checks + ')' if checks else ''}, then lint the board"
            if rules in stale:
                extra = f" (the G4 rules changed, which the page-check reports of the pages were made from: {pages})"
            elif old_page_reports(project, board_rel, page_ids):
                extra = f" (recording a gate changes BRAND-STATE.md, which the page-check reports of the pages were made from: {pages})"
            else:
                extra = " (recording a gate changes BRAND-STATE.md, which a rule of the board cites as its source: lint the board again)"
        return f"the board-lint report is stale ({'; '.join(stale[:3])}){extra}: {again}"
    if doc.get("status") != "pass":
        return f"the board-lint report of {board_rel} is {doc.get('status')!r}, not pass: change the board as its rows say, then lint it again: {cmd}"
    return None


def choices_of(root, page_ids: list[str]) -> list[dict]:
    """The choices of the board, in page order, as site.json holds them: id, text, tag, source (the words of data-source, "" when it has none) and pages (data-pages, else every page of the board)."""
    out = []
    for li in (n for n in root.walk() if siteboard.CHOICE_ATTR in n.attrs):
        named = [x for x in re.split(r"[\s,]+", li.attrs.get("data-pages", "").strip()) if x] if "data-pages" in li.attrs else list(page_ids)
        out.append({"id": li.attrs[siteboard.CHOICE_ATTR].strip(), "text": re.sub(r"\s+", " ", li.text()).strip(), "tag": li.attrs.get("data-tag", "").strip(),
                    "source": re.sub(r"\s+", " ", li.attrs.get("data-source", "")).strip(), "pages": named})
    return out


def listed(problems: list[str], limit: int = SHOWN) -> str:
    return "\n".join(f"  - {p}" for p in problems[:limit]) + (f"\n  - and {len(problems) - limit} more" if len(problems) > limit else "")


def link_problem(project: Path, path_rel: str, what: str, as_it_is: str) -> str | None:
    """Why the project-relative `path_rel` (the board file, or a page folder) cannot be read as it stands, or None: a part of it below the project (rounds, rounds/r<N>, the folder or the file) is a
    symbolic link, wherever it leads (a link is looked at part by part: os.walk follows the top folder it is given, and a link higher up leads the whole page elsewhere), or the real path is not inside the
    project (`confine`, which names `what`). `as_it_is` ends the sentence the way the link refusals inside a page folder do: "<path> is a symbolic link: <as_it_is>, and a link can lead out of the project"."""
    here, parts = project, []
    for part in Path(path_rel).parts:
        here, parts = here / part, [*parts, part]
        if here.is_symlink():
            return f"{'/'.join(parts)} is a symbolic link: {as_it_is}, and a link can lead out of the project"
    try:
        confine(project, path_rel, what=what, read=True)
    except CliError as e:
        return e.message
    return None


def plan_page(project: Path, v, moves: dict[str, str], problems: list[tuple[int, str]]) -> list[tuple[str, Path, bytes | None]]:
    """What goes into site/<id>/ for one page -> [(path inside the page folder, source file, the new bytes or None to copy the file as it is)]. Problems are added to `problems` as (exit code, sentence).
    `approve` has refused a page folder that is a link (or behind one) by now, so the top of the walk is a folder of the project; the links below it are refused here."""
    src = project / v.dir
    out: list[tuple[str, Path, bytes | None]] = []
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        here = Path(dirpath).relative_to(src).as_posix()
        here = "" if here == "." else here
        dirnames[:] = sorted(d for d in dirnames if not (here == "" and d == EXCLUDED_DIR))
        for d in dirnames:
            if (Path(dirpath) / d).is_symlink():   # named as it stands in the page folder: `rel` would follow the link, and a link out of the project has no project-relative path
                problems.append((EXIT_USAGE, f"{v.dir}/{here + '/' if here else ''}{d} is a symbolic link: a page folder is copied as it is, and a link can lead out of the project"))
        for name in sorted(filenames):
            if (here == "" and name == EXCLUDED_FILE) or name in JUNK:
                continue
            f = Path(dirpath) / name
            inside = f"{here}/{name}" if here else name
            shown = f"{v.dir}/{inside}"
            if f.is_symlink():
                problems.append((EXIT_USAGE, f"{shown} is a symbolic link: a page folder is copied as it is, and a link can lead out of the project"))
                continue
            kind = {".html": "html", ".css": "css"}.get(f.suffix.lower())
            if kind is None:
                out.append((inside, f, None))
                continue
            try:
                text = f.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                problems.append((EXIT_FAIL, f"{shown} is not UTF-8 text, so the paths in it cannot be read"))
                continue
            file_dir = f"{v.dir}/{here}" if here else v.dir
            new_dir = f"{moves[v.dir]}/{here}" if here else moves[v.dir]
            new, found = sitedata.rewrite_urls(text, kind, project=project, file_dir=file_dir, new_file_dir=new_dir, moves=moves, label=shown)
            problems += [(p.code, p.message) for p in found]
            out.append((inside, f, new.encode("utf-8") if new != text else None))
    return out


def stage_dir(project: Path) -> Path:
    """A new folder in the project for the pages to be written into before they take the place of site/ (so a failure half way leaves no half-written site/)."""
    n = os.getpid()
    while True:
        d = project / f"site-new-{n}"
        try:
            d.mkdir()
        except FileExistsError:
            n += 1
            continue
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(d, 0o777 & ~umask)
        return d


def removed_root(project: Path) -> Path:
    """removed-<date>/, or removed-<date>-2/ ... when that folder has a site/ already: the first one where the old site/ can go."""
    n = 1
    while True:
        d = project / (f"removed-{today()}" + (f"-{n}" if n > 1 else ""))
        if not (d / "site").exists():
            return d
        n += 1


def approve(project: Path, round_arg: int | None, replace: bool) -> int:
    g4p = gate_recorded(project, "G4p")
    if not g4p:
        fail(EXIT_FAIL, "site approve needs the owner's approval of the pages (G4p) recorded first. Get it, then run: "
                        "brand-creator state --record G4p \"approved <pages>; rules <choice ids>\"")
    rounds = list_rounds(project)
    if round_arg is None and not rounds:
        fail(EXIT_USAGE, "there is no round yet (rounds/): site approve copies the pages of the round that holds the pages board")
    n = round_arg if round_arg is not None else rounds[-1][0]
    board_rel = f"rounds/r{n}/board.html"
    board = project / board_rel
    linked = link_problem(project, board_rel, "pages board", "the pages board is read as it is")   # before anything is read through it
    if linked:
        fail(EXIT_USAGE, linked)
    if not board.is_file():
        fail(EXIT_USAGE, f"{board_rel} does not exist: site approve copies the pages of a site board at the pages stage (--round N)")
    root = read_page(board)
    kind, stage = page_kind(root), siteboard.stage_of(root)
    if kind != "site" or stage != "pages":
        fail(EXIT_USAGE, f"{board_rel} is not a site board at the pages stage (data-board={kind!r}, data-site-stage={stage!r}): site approve copies the pages of that board "
                         f"(the latest round is the default; --round N names another)")
    lint = lint_problem(project, board_rel, [c.attrs.get(siteboard.PAGE_ATTR, "").strip() for c in siteboard.page_cards(root)])
    if lint:
        fail(EXIT_FAIL, lint)
    site = project / sitedata.SITE_DIR
    if (site.exists() or site.is_symlink()) and not replace:
        fail(EXIT_FAIL, "site/ holds approved pages already; nothing was written. To approve the pages of this round instead, run: brand-creator site approve --replace "
                        "(the old site/ moves to removed-<date>/site/; it is never deleted)")

    problems_of_board, named = siteboard.page_problems(siteboard.page_cards(root))
    if problems_of_board:
        fail(EXIT_FAIL, "the pages board has no usable page card (" + "; ".join(problems_of_board[:3]) + f"): change the board, then lint it: brand-creator board-lint {board_rel}")
    unsafe = [m for pid, _ in named if (m := link_problem(project, f"rounds/r{n}/{pid}", "page folder", "a page folder is copied as it is"))]   # before SiteVariant reads the page through it
    if unsafe:
        fail(EXIT_USAGE, f"nothing was written: {len(unsafe)} problem(s) stop the pages of {board_rel}\n" + listed(unsafe))
    pages = [siteboard.SiteVariant(project, n, pid, card, noun="page") for pid, card in named]
    marker = page_marker(root)
    hero = marker.attrs.get(siteboard.HERO_ATTR, "").strip() if marker is not None else ""
    problems: list[tuple[int, str]] = []
    if not hero:
        problems.append((EXIT_FAIL, f"the <body> of {board_rel} names no hero (data-hero)"))
    moves = {v.dir: f"{sitedata.SITE_DIR}/{v.name}" for v in pages}
    plans: dict[str, list[tuple[str, Path, bytes | None]]] = {}
    for v in pages:
        if not (project / v.dir).is_dir() or not (project / v.page).is_file():
            problems.append((EXIT_FAIL, f"{v.page} is missing: a page card needs its folder and index.html"))
            continue
        if not v.layout:
            problems.append((EXIT_FAIL, f"{v.page} declares no data-layout, so no layout reference can be recorded"))
        plans[v.name] = plan_page(project, v, moves, problems)

    doc = {"schema": sitedata.SCHEMA, "approved": g4p, "round": n, "hero": hero, "pages": [], "choices": choices_of(root, [v.name for v in pages])}
    for v in pages:
        if v.name not in plans:
            continue
        index = next((new for inside, f, new in plans[v.name] if inside == "index.html"), None)
        sha = sha256_bytes(index) if index is not None else sha256_file(project / v.page)
        doc["pages"].append({"id": v.name, "path": f"{sitedata.SITE_DIR}/{v.name}/index.html", "layout": v.layout, "sha256": sha})
    if not problems:
        problems += [(EXIT_FAIL, p) for p in sitedata.record_problems(doc)]
    if problems:
        code = EXIT_USAGE if any(c == EXIT_USAGE for c, _ in problems) else EXIT_FAIL
        fail(code, f"nothing was written: {len(problems)} problem(s) stop the pages of {board_rel}\n" + listed([m for _, m in problems]))

    stage_root = stage_dir(project)
    moved_to: Path | None = None
    try:
        for v in pages:
            for inside, f, new in plans[v.name]:
                dst = stage_root / v.name / inside
                dst.parent.mkdir(parents=True, exist_ok=True)
                if new is None:
                    shutil.copy2(f, dst)
                else:
                    dst.write_bytes(new)
        (stage_root / "site.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if site.exists() or site.is_symlink():
            aside = removed_root(project)
            aside.mkdir(exist_ok=True)
            shutil.move(str(site), str(aside / "site"))
            moved_to = aside
        os.replace(stage_root, site)
    except BaseException:
        if moved_to is not None and not site.exists():
            shutil.move(str(moved_to / "site"), str(site))   # put the old site/ back: the new one did not make it
        shutil.rmtree(stage_root, ignore_errors=True)       # the staging folder is this run's own
        raise
    print(f"approved {len(pages)} page(s) of round {n} into site/: {', '.join(v.name for v in pages)}")
    print(f"wrote {sitedata.SITE_FILE}: hero {hero}; {len(doc['choices'])} choice(s), "
          f"{sum(1 for c in doc['choices'] if c['tag'] == 'rule')} rule(s) and {sum(1 for c in doc['choices'] if c['tag'] == 'example')} example(s)")
    if moved_to is not None:
        print(f"the previous site/ is in {moved_to.name}/site/")
    print("next, for each page (the approved copy has no stills yet):")
    for v in pages:
        print(f"  brand-creator capture site/{v.name}/index.html")
        print(f"  brand-creator page-check site/{v.name}/index.html")
    print("then: brand-creator check")
    return 0


def main() -> int:
    ap = Parser(prog="brand-creator site", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("approve",), help="approve: put the approved pages of the pages board into site/")
    add_project_arg(ap)
    ap.add_argument("--round", type=int, help="the round of the pages board (default: the latest round)")
    ap.add_argument("--replace", action="store_true", help="site/ holds approved pages already: move it to removed-<date>/site/ and write the pages of this round")
    a = ap.parse_args()
    if a.round is not None and a.round < 0:
        raise CliError(EXIT_USAGE, "--round takes a round number (0 or more)")
    return approve(find_project(a.project), a.round, a.replace)


main_guard(main)
